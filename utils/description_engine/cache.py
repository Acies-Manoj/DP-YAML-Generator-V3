"""
cache.py — File-based cache for generated descriptions.
Avoids redundant LLM calls across sessions by fingerprinting
table name + column structure + optional user context.
"""

import os
import json
import hashlib
from pathlib import Path


class DescriptionCache:
    """Simple file-based JSON cache keyed by table schema fingerprint."""

    def __init__(self, cache_dir: str = ".desc_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

    def _fingerprint(self, table_name: str, columns: list[dict], user_context: str = None) -> str:
        """
        Generate MD5 fingerprint from table name + sorted column names + types
        + optional user context. Different context = different fingerprint = fresh LLM call.
        """
        key_parts = [table_name] + sorted(
            f"{c.get('name', '')}:{c.get('data_type', '')}"
            for c in columns
        )
        # Append context to fingerprint so cached results are context-specific
        if user_context:
            key_parts.append(f"ctx:{user_context.strip()}")
        raw = "|".join(key_parts).encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def _cache_path(self, fingerprint: str) -> Path:
        return self.cache_dir / f"{fingerprint}.json"

    def get(self, table_name: str, columns: list[dict], user_context: str = None) -> dict | None:
        """
        Return cached descriptions if available, else None.
        user_context is included in the key — different context = cache miss.
        """
        fp = self._fingerprint(table_name, columns, user_context=user_context)
        path = self._cache_path(fp)
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def set(self, table_name: str, columns: list[dict], result: dict, user_context: str = None) -> None:
        """
        Save result to cache file named by fingerprint.
        user_context is included in the key so context-specific results are stored separately.
        """
        fp = self._fingerprint(table_name, columns, user_context=user_context)
        path = self._cache_path(fp)
        try:
            with open(path, "w") as f:
                json.dump(result, f, indent=2)
        except IOError as e:
            # Non-fatal — cache write failure shouldn't break the app
            print(f"[DescriptionCache] Warning: could not write cache: {e}")

    def clear(self, table_name: str, columns: list[dict], user_context: str = None) -> None:
        """Remove a specific cache entry."""
        fp = self._fingerprint(table_name, columns, user_context=user_context)
        path = self._cache_path(fp)
        if path.exists():
            path.unlink()

    def clear_all(self) -> int:
        """Clear all cache files. Returns count of deleted files."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count