"""Small process-local TTL cache for provider responses.

Used to reuse Google Text Search / Details and Kakao rating enrichment across
searches without changing match thresholds or inventing missing data.
"""

from __future__ import annotations

import time
from typing import Generic, TypeVar

T = TypeVar("T")

_MISS = object()


class TtlCache(Generic[T]):
    def __init__(self, ttl_s: float, max_size: int = 2048) -> None:
        self._ttl_s = max(1.0, ttl_s)
        self._max_size = max(16, max_size)
        self._data: dict[object, tuple[float, T]] = {}

    def get(self, key: object) -> tuple[bool, T | None]:
        """Return ``(True, value)`` on hit (value may be None), else ``(False, None)``."""
        item = self._data.get(key)
        if item is None:
            return False, None
        expires_at, value = item
        if time.monotonic() >= expires_at:
            self._data.pop(key, None)
            return False, None
        return True, value

    def set(self, key: object, value: T) -> None:
        if len(self._data) >= self._max_size:
            # Drop roughly the oldest half of entries (insertion order in 3.7+).
            drop = max(1, len(self._data) // 2)
            for old_key in list(self._data.keys())[:drop]:
                self._data.pop(old_key, None)
        self._data[key] = (time.monotonic() + self._ttl_s, value)

    def clear(self) -> None:
        self._data.clear()
