"""Content-hash based caching layer for Documenter and CodeGenerator LLM outputs."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger

logger = get_logger("ChunkCache")

_CACHE_DIR = Path(".cache")
_CACHE_FILE = _CACHE_DIR / "chunk_cache.json"


class ChunkCache:
    """
    Persistent, content-hash-keyed cache for chunk-level LLM outputs.

    Cache keys are SHA-256 hashes of raw_code + namespace (e.g. "doc" or "code").
    Cache values are JSON-serialisable dicts (model_dump() of Pydantic models).
    The cache is stored as a flat JSON file at .cache/chunk_cache.json.
    """

    _data: dict[str, Any] | None = None  # in-process singleton

    # ── Private helpers ────────────────────────────────────────────────────

    @classmethod
    def _load(cls) -> dict[str, Any]:
        if cls._data is None:
            if _CACHE_FILE.exists():
                try:
                    cls._data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                    logger.debug("ChunkCache: loaded %d entries from %s", len(cls._data), _CACHE_FILE)
                except Exception as exc:
                    logger.warning("ChunkCache: failed to load cache file (%s) — starting fresh.", exc)
                    cls._data = {}
            else:
                cls._data = {}
        return cls._data

    @classmethod
    def _save(cls) -> None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(cls._data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # ── Public API ─────────────────────────────────────────────────────────

    @classmethod
    def cache_key(cls, raw_code: str, namespace: str) -> str:
        """Returns a stable SHA-256 cache key for the given raw_code + namespace."""
        digest = hashlib.sha256(f"{namespace}:{raw_code}".encode("utf-8")).hexdigest()
        return digest

    @classmethod
    def get(cls, raw_code: str, namespace: str) -> dict[str, Any] | None:
        """
        Returns the cached dict for raw_code + namespace, or None on a cache miss.

        Args:
            raw_code:  The chunk's raw legacy source code.
            namespace: "doc" for DocSection results, "code" for GeneratedCode results.
        """
        key = cls.cache_key(raw_code, namespace)
        data = cls._load()
        hit = data.get(key)
        if hit is not None:
            logger.info("ChunkCache HIT [%s] key=%s...", namespace, key[:12])
        else:
            logger.debug("ChunkCache MISS [%s] key=%s...", namespace, key[:12])
        return hit

    @classmethod
    def put(cls, raw_code: str, namespace: str, value: dict[str, Any]) -> None:
        """
        Stores value (a Pydantic model_dump() dict) under the cache key.

        Args:
            raw_code:  The chunk's raw legacy source code.
            namespace: "doc" or "code".
            value:     JSON-serialisable dict to cache.
        """
        key = cls.cache_key(raw_code, namespace)
        data = cls._load()
        data[key] = value
        cls._data = data
        cls._save()
        logger.debug("ChunkCache PUT [%s] key=%s...", namespace, key[:12])

    @classmethod
    def invalidate(cls, raw_code: str, namespace: str) -> None:
        """Removes a single entry from the cache."""
        key = cls.cache_key(raw_code, namespace)
        data = cls._load()
        if key in data:
            del data[key]
            cls._data = data
            cls._save()

    @classmethod
    def clear(cls) -> None:
        """Clears the entire in-memory and on-disk cache."""
        cls._data = {}
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
        logger.info("ChunkCache: cache cleared.")

    @classmethod
    def stats(cls) -> dict[str, int]:
        """Returns basic cache statistics."""
        data = cls._load()
        return {"total_entries": len(data)}
