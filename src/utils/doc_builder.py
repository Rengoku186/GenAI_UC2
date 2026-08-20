"""Dynamic Markdown documentation builder — produces the exact format requested:

  # Program Description
  # Methods
  # Important Calculations
"""

from __future__ import annotations
from pathlib import Path
from src.orchestrator.state import ChunkMetadata, DocSection


# Chunks that describe infrastructure rather than business logic
_INFRA_TYPES = {"header", "import", "package", "constant"}

# Chunk names / name prefixes that are structural rather than user-facing
_SKIP_NAMES = {"HEADER", "PACKAGE_AND_IMPORTS"}

# Noise patterns injected by the code_refiner mock that add no value
_NOISE_PATTERNS = (
    "(Refined v",
    "Refined rule addressing",
    "Business rules list is empty",
)


def _clean(text: str) -> str:
    """Strips refiner-mock noise from a text field."""
    # Remove '(Refined vN)' suffix anywhere in the string
    import re
    text = re.sub(r'\s*\(Refined v\d+\)', '', text).strip()
    return text


def _clean_rules(rules: list[str]) -> list[str]:
    """Filters out stub/noise rules and cleans remaining ones."""
    cleaned = []
    for r in rules:
        if any(pat in r for pat in _NOISE_PATTERNS):
            continue
        cleaned.append(_clean(r))
    return cleaned


def _is_business_chunk(chunk: ChunkMetadata) -> bool:
    if chunk.name in _SKIP_NAMES:
        return False
    if chunk.chunk_type.lower() in _INFRA_TYPES:
        return False
    return True


def _detect_calculations(doc: DocSection) -> list[str]:
    """Returns only the business_rules that look like formulas / calculations."""
    calc_keywords = {
        "=", "*", "/", "%", "formula", "rate", "calculation",
        "balance", "payment", "fee", "penalty", "limit", "surcharge",
        "round", "scale", "total", "sum", "multiply", "divide",
    }
    calcs = []
    for rule in doc.business_rules:
        rule_lower = rule.lower()
        if any(k in rule_lower for k in calc_keywords):
            calcs.append(rule)
    return calcs


def _format_method_section(chunk: ChunkMetadata, doc: DocSection) -> list[str]:
    lines: list[str] = []

    lines.append(f"## `{chunk.name}`")
    lines.append("")

    # Purpose
    purpose = _clean(doc.purpose)
    lines.append(f"**Purpose:** {purpose}")
    lines.append("")

    # Inputs
    inputs = [_clean(i) for i in doc.inputs if i and i != "No parameters"]
    if inputs:
        lines.append("**Inputs:**")
        for inp in inputs:
            lines.append(f"- `{inp}`")
        lines.append("")

    # Outputs
    outputs = [_clean(o) for o in doc.outputs if o and o != "void"]
    if outputs:
        lines.append("**Outputs:**")
        for out in outputs:
            lines.append(f"- `{out}`")
        lines.append("")

    return lines


class DocBuilder:
    """Builds Markdown documentation from pipeline DocSection objects."""

    @staticmethod
    def build(
        source_filename: str,
        chunks: list[ChunkMetadata],
        docs: dict[str, DocSection],
        class_name: str = "",
    ) -> str:
        """Generates documentation in the format:
            # Program Description
            # Methods
            # Important Calculations
        """
        stem = Path(source_filename).stem
        if not class_name:
            class_name = stem[0].upper() + stem[1:] if stem else "Service"

        business_chunks = [c for c in chunks if _is_business_chunk(c)]

        lines: list[str] = []

        # ── Program Description ───────────────────────────────────────────────
        lines += [
            f"# {class_name}",
            "",
            "## Program Description",
            "",
        ]

        # Derive an overall description from the documented chunks
        major_purposes = [
            _clean(docs[c.chunk_id].purpose)
            for c in chunks
            if c.chunk_id in docs and _is_business_chunk(c)
            and len(docs[c.chunk_id].purpose) > 40
            and not any(n in docs[c.chunk_id].purpose for n in _NOISE_PATTERNS)
        ]

        if major_purposes:
            lines.append(f"Legacy application `{source_filename}` that provides the following capabilities:")
            lines.append("")
            for p in major_purposes[:10]: # limit to top 10 to avoid bloat
                lines.append(f"- {p}")
            lines.append("")
        else:
            lines.append(f"Legacy application `{source_filename}`.")
            lines.append("")

        lines += ["---", ""]

        # ── Per-Method Documentation ──────────────────────────────────────────
        lines += [
            "## Methods",
            "",
        ]

        for chunk in chunks:
            if not _is_business_chunk(chunk):
                continue
            doc = docs.get(chunk.chunk_id)
            if doc:
                lines.extend(_format_method_section(chunk, doc))

        lines += ["---", ""]

        # ── Important Calculations ────────────────────────────────────────────
        lines += [
            "## Important Calculations",
            "",
        ]

        all_calcs: list[str] = []
        for c in chunks:
            if not _is_business_chunk(c):
                continue
            d = docs.get(c.chunk_id)
            if d:
                calcs = _detect_calculations(d)
                # Clean and add to overall list
                for calc in calcs:
                    clean_calc = _clean(calc)
                    if clean_calc not in all_calcs:
                        all_calcs.append(clean_calc)

        if all_calcs:
            for calc in all_calcs:
                lines.append(f"- {calc}")
            lines.append("")
        else:
            lines.append("_No important calculations detected._")
            lines.append("")

        return "\n".join(lines)
