"""
Content-based language detection with an AI fallback for ambiguous cases.

Design principles:
  - File extension is a WEAK PRIOR ONLY, not the decision - a `.txt` file full
    of COBOL should still be detected as COBOL. This directly replaces the
    old extension-only `detect_language()`.
  - Cheap, deterministic heuristic scoring runs first (regex signature
    matching against known syntax markers per language). This handles the
    overwhelming majority of real files with zero AI cost or latency.
  - An LLM classification call is used ONLY when the heuristic is genuinely
    unsure (no language scores above LANG_DETECT_CONFIDENCE_THRESHOLD). This
    keeps AI usage proportional to actual ambiguity at scale, rather than
    calling an LLM once per file in a large codebase.
  - Results are cached in-memory by content hash, so identical file content
    (duplicates, generated copies) is never re-classified twice in one run.
  - Every detection failure degrades gracefully (falls back to heuristic
    best-guess, then to "unknown") rather than raising and killing a scan
    over one unclassifiable file.
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.utils.llm import get_llm
from src.utils.log_config import get_logger

logger = get_logger(__name__)

# --- Configuration (env-overridable) ----------------------------------------

CONFIDENCE_THRESHOLD = float(os.getenv("LANG_DETECT_CONFIDENCE_THRESHOLD", "0.6"))
MIXED_MARGIN = float(os.getenv("LANG_DETECT_MIXED_MARGIN", "0.15"))
MIXED_MIN_SCORE = float(os.getenv("LANG_DETECT_MIXED_MIN_SCORE", "0.25"))
USE_LLM_FALLBACK = os.getenv("LANG_DETECT_USE_LLM_FALLBACK", "true").lower() == "true"
LLM_MAX_CONTENT_CHARS = int(os.getenv("LANG_DETECT_LLM_MAX_CHARS", "6000"))
EXTENSION_HINT_WEIGHT = float(os.getenv("LANG_DETECT_EXTENSION_WEIGHT", "0.75"))
MAX_TRANSIENT_RETRIES = int(os.getenv("LANG_DETECT_MAX_TRANSIENT_RETRIES", "2"))
BACKOFF_BASE_SECONDS = float(os.getenv("LANG_DETECT_BACKOFF_BASE_SECONDS", "1.0"))
BACKOFF_MAX_SECONDS = float(os.getenv("LANG_DETECT_BACKOFF_MAX_SECONDS", "10.0"))


@dataclass
class LanguageDetectionResult:
    language: str
    confidence: float
    method: str  # "heuristic" | "heuristic_low_confidence" | "llm" | "llm_failed_fallback_heuristic"
    evidence: Dict[str, float] = field(default_factory=dict)  # normalized per-language scores


class TransientLLMError(Exception):
    """Network/timeout/rate-limit errors - retryable with backoff, distinct
    from a malformed/unparseable LLM response."""


# --- Heuristic content signatures -------------------------------------------
# Each signal is a regex pattern + a weight + a cap on how many matches count
# (so one COBOL file with 200 PERFORM statements doesn't drown out a file
# with fewer but more decisive markers like PROGRAM-ID).

@dataclass(frozen=True)
class _Signal:
    pattern: "re.Pattern"
    weight: float
    max_count: int = 5


LANGUAGE_SIGNALS: Dict[str, List[_Signal]] = {
    "cobol": [
        _Signal(re.compile(r"\bIDENTIFICATION\s+DIVISION\b", re.IGNORECASE), 3.0, 1),
        _Signal(re.compile(r"\bPROGRAM-ID\b", re.IGNORECASE), 3.0, 1),
        _Signal(re.compile(r"\bPROCEDURE\s+DIVISION\b", re.IGNORECASE), 3.0, 1),
        _Signal(re.compile(r"\bWORKING-STORAGE\s+SECTION\b", re.IGNORECASE), 2.5, 1),
        _Signal(re.compile(r"\bDATA\s+DIVISION\b", re.IGNORECASE), 2.0, 1),
        _Signal(re.compile(r"\bPIC(?:TURE)?\s+[9XSAV(),.\-]+", re.IGNORECASE), 1.0, 8),
        _Signal(re.compile(r"\bPERFORM\b", re.IGNORECASE), 0.5, 10),
        _Signal(re.compile(r"\bMOVE\s+.+\s+TO\s+", re.IGNORECASE), 0.5, 10),
        _Signal(re.compile(r"\bSTOP\s+RUN\b", re.IGNORECASE), 1.5, 2),
        _Signal(re.compile(r"^\s{6,}[\w-]+\.\s*$", re.MULTILINE), 0.3, 15),  # paragraph names
    ],
    "vb": [
        _Signal(re.compile(r'Attribute\s+VB_Name\s*=', re.IGNORECASE), 3.0, 1),
        _Signal(re.compile(r"\bOption\s+Explicit\b", re.IGNORECASE), 1.5, 1),
        _Signal(re.compile(r"^\s*(?:Public|Private|Friend)?\s*(?:Sub|Function)\s+\w+",
                            re.MULTILINE | re.IGNORECASE), 1.0, 10),
        _Signal(re.compile(r"\bEnd\s+(?:Sub|Function|If|With|Select)\b", re.IGNORECASE), 0.7, 10),
        _Signal(re.compile(r"\bDim\s+\w+\s+As\s+\w+", re.IGNORECASE), 0.7, 10),
        _Signal(re.compile(r"\bMsgBox\b", re.IGNORECASE), 1.0, 3),
        _Signal(re.compile(r"\bOn\s+Error\s+(?:Resume\s+Next|GoTo)", re.IGNORECASE), 1.5, 2),
    ],
    "java": [
        _Signal(re.compile(r"\bpackage\s+[\w.]+\s*;"), 2.0, 1),
        _Signal(re.compile(r"\bimport\s+java\.[\w.]+\s*;"), 1.5, 5),
        _Signal(re.compile(r"\bpublic\s+(?:final\s+)?(?:class|interface|enum)\s+\w+"), 2.5, 1),
        _Signal(re.compile(r"\bpublic\s+static\s+void\s+main\s*\("), 3.0, 1),
        _Signal(re.compile(r"\b@Override\b"), 1.0, 5),
        _Signal(re.compile(r"\bSystem\.(?:out|err)\.println\s*\("), 1.0, 5),
        _Signal(re.compile(r"[;{}]\s*$", re.MULTILINE), 0.05, 40),  # weak C-family density signal
    ],
}

# Weak prior only - contributes a small nudge, never decides the outcome on
# its own. A file with strong content signals for a *different* language
# than its extension suggests will still be classified by content.
EXTENSION_HINTS: Dict[str, str] = {
    ".cbl": "cobol", ".cob": "cobol", ".cobol": "cobol", ".cpy": "cobol", ".pco": "cobol",
    ".bas": "vb", ".cls": "vb", ".vb": "vb", ".vbs": "vb", ".frm": "vb", ".ctl": "vb", ".vba": "vb",
    ".java": "java", ".jav": "java",
}

SUPPORTED_LANGUAGES = list(LANGUAGE_SIGNALS.keys())

LLM_SYSTEM_PROMPT = """You are a source-code language classifier for a legacy \
modernization project. Given a snippet of source code, identify which of the \
following languages it is written in: {supported_languages}, "mixed" (if it \
genuinely combines two or more of these in one file), or "unknown" (if it \
matches none of them, or you cannot tell). Base your answer only on syntax \
actually present in the snippet - do not guess from the file name.

Respond with ONLY a single valid JSON object, no markdown fences, no prose:
{{
  "language": "<one of: {supported_languages}, mixed, unknown>",
  "confidence": <float 0-1>,
  "reasoning": "<one short sentence citing specific syntax you saw>"
}}
"""

LLM_USER_TEMPLATE = """FILE: {file_path}

CODE SNIPPET:
```
{content}
```
"""

TRUNCATION_NOTE = "\n\n[... snippet truncated at {max_chars} characters for classification ...]"


def _heuristic_scores(content: str, file_path: Optional[str] = None) -> Dict[str, float]:
    raw_scores: Dict[str, float] = {lang: 0.0 for lang in LANGUAGE_SIGNALS}
    for lang, signals in LANGUAGE_SIGNALS.items():
        for sig in signals:
            count = min(len(sig.pattern.findall(content)), sig.max_count)
            raw_scores[lang] += count * sig.weight

    if file_path:
        ext = os.path.splitext(file_path)[1].lower()
        hinted_lang = EXTENSION_HINTS.get(ext)
        if hinted_lang:
            raw_scores[hinted_lang] += EXTENSION_HINT_WEIGHT

    return raw_scores


def _normalize(raw_scores: Dict[str, float]) -> Dict[str, float]:
    total = sum(raw_scores.values())
    if total <= 0:
        return {k: 0.0 for k in raw_scores}
    return {k: v / total for k, v in raw_scores.items()}


def _top_two(normalized: Dict[str, float]) -> List[Tuple[str, float]]:
    return sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)[:2]


def _classify_heuristically(content: str, file_path: Optional[str]) -> LanguageDetectionResult:
    raw = _heuristic_scores(content, file_path)
    normalized = _normalize(raw)
    ranked = _top_two(normalized)

    if not ranked or ranked[0][1] == 0.0:
        return LanguageDetectionResult("unknown", 0.0, "heuristic", normalized)

    top_lang, top_conf = ranked[0]

    # Genuinely ambiguous between two languages -> "mixed" rather than
    # forcing a coin-flip decision between them.
    if len(ranked) == 2:
        second_lang, second_conf = ranked[1]
        if top_conf >= MIXED_MIN_SCORE and (top_conf - second_conf) <= MIXED_MARGIN:
            return LanguageDetectionResult("mixed", top_conf, "heuristic", normalized)

    if top_conf >= CONFIDENCE_THRESHOLD:
        return LanguageDetectionResult(top_lang, top_conf, "heuristic", normalized)

    return LanguageDetectionResult(top_lang, top_conf, "heuristic_low_confidence", normalized)


def _prepare_snippet(content: str) -> str:
    """Language identity is almost always evident early in a file (package/
    import statements, PROGRAM-ID, Attribute VB_Name, etc.), so we only need
    a bounded sample - not the whole file - to classify large files cheaply.
    Always truncates with an explicit marker, never silently."""
    if len(content) <= LLM_MAX_CONTENT_CHARS:
        return content
    return content[:LLM_MAX_CONTENT_CHARS] + TRUNCATION_NOTE.format(max_chars=LLM_MAX_CONTENT_CHARS)


def _extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Could not extract JSON from LLM response: {raw_text[:200]}")


def _invoke_with_backoff(llm, messages, file_path: str) -> str:
    last_exc: Exception = TransientLLMError("no attempts made")
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            response = llm.invoke(messages)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:  # noqa: BLE001 - any provider/network/SDK error
            last_exc = exc
            logger.warning(
                "Transient LLM error during language classification, retrying",
                extra={"file_path": file_path, "attempt": attempt,
                       "event": "lang_detect_llm_transient_error"},
                exc_info=True,
            )
            if attempt < MAX_TRANSIENT_RETRIES:
                delay = min(BACKOFF_BASE_SECONDS * (2 ** attempt), BACKOFF_MAX_SECONDS)
                time.sleep(delay)
                continue
    raise TransientLLMError(
        f"Language classification LLM call failed after "
        f"{MAX_TRANSIENT_RETRIES + 1} attempts: {last_exc}"
    ) from last_exc


def _classify_with_llm(
    file_path: str, content: str, heuristic_result: LanguageDetectionResult
) -> LanguageDetectionResult:
    """Only called when the heuristic scorer is genuinely unsure. Degrades
    gracefully to the heuristic's own best guess if the LLM call fails for
    any reason - a classification hiccup should never crash a large scan."""
    try:
        llm = get_llm(temperature=0.0)
        system_prompt = LLM_SYSTEM_PROMPT.format(
            supported_languages=", ".join(SUPPORTED_LANGUAGES)
        )
        user_prompt = LLM_USER_TEMPLATE.format(
            file_path=file_path, content=_prepare_snippet(content)
        )
        messages = [("system", system_prompt), ("human", user_prompt)]

        raw_text = _invoke_with_backoff(llm, messages, file_path)
        data = _extract_json(raw_text)

        language = str(data.get("language", "unknown")).strip().lower()
        if language not in SUPPORTED_LANGUAGES + ["mixed", "unknown"]:
            logger.warning(
                f"LLM returned an unrecognized language label {language!r}, "
                f"treating as 'unknown'",
                extra={"file_path": file_path, "event": "lang_detect_llm_bad_label"},
            )
            language = "unknown"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        logger.info(
            "Language classified via LLM fallback",
            extra={"file_path": file_path, "event": "lang_detect_llm_success"},
        )
        return LanguageDetectionResult(
            language=language,
            confidence=confidence,
            method="llm",
            evidence=heuristic_result.evidence,
        )
    except Exception as exc:  # noqa: BLE001 - never let classification kill a scan
        logger.error(
            f"LLM language classification failed, falling back to heuristic "
            f"best guess: {exc}",
            extra={"file_path": file_path, "event": "lang_detect_llm_failed"},
        )
        return LanguageDetectionResult(
            language=heuristic_result.language or "unknown",
            confidence=heuristic_result.confidence,
            method="llm_failed_fallback_heuristic",
            evidence=heuristic_result.evidence,
        )


class LanguageDetector:
    """Stateful detector with an in-memory content-hash cache, so identical
    file content encountered more than once in a run (duplicate/generated
    copies) is never re-classified. For very large, long-running deployments
    this cache could be swapped for a persistent store (e.g. a small SQLite
    table keyed by content hash) to survive across process restarts - the
    interface below (`detect`) would not need to change."""

    def __init__(self, use_llm_fallback: bool = USE_LLM_FALLBACK):
        self.use_llm_fallback = use_llm_fallback
        self._cache: Dict[str, LanguageDetectionResult] = {}

    def detect(self, file_path: str, content: str) -> LanguageDetectionResult:
        if not content or not content.strip():
            logger.warning(
                "Empty file content, cannot detect language",
                extra={"file_path": file_path, "event": "lang_detect_empty_content"},
            )
            return LanguageDetectionResult("unknown", 0.0, "empty_content")

        content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
        if content_hash in self._cache:
            cached = self._cache[content_hash]
            logger.debug(
                "Language detection cache hit",
                extra={"file_path": file_path, "event": "lang_detect_cache_hit"},
            )
            return cached

        start = time.perf_counter()
        result = _classify_heuristically(content, file_path)

        if result.method == "heuristic_low_confidence" and self.use_llm_fallback:
            result = _classify_with_llm(file_path, content, result)

        latency_ms = round((time.perf_counter() - start) * 1000, 1)
        logger.info(
            "Language detected",
            extra={
                "file_path": file_path,
                "language": result.language,
                "event": "lang_detect_result",
                "latency_ms": latency_ms,
            },
        )

        self._cache[content_hash] = result
        return result


# Module-level default instance for simple call sites that don't need a
# custom-configured detector.
_default_detector = LanguageDetector()


def detect_language(file_path: str, content: Optional[str] = None) -> str:
    """Backward-compatible convenience wrapper returning just the language
    string, matching the old function's signature/behavior for any external
    call sites that only need the label. Prefer calling
    `LanguageDetector.detect()` directly when you already have the file
    content in memory, to avoid a redundant disk read."""
    if content is None:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    return _default_detector.detect(file_path, content).language
