"""Simple caching utilities for Crypto Market MCP server."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Hashable, Optional, Tuple


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


class TTLCache:
    """Thread-safe TTL cache with max size.

    This is intentionally minimal and synchronous, suitable for wrapping
    blocking ccxt calls inside the MCP server implementation.
    """

    def __init__(self, ttl_seconds: int = 10, maxsize: int = 1024) -> None:
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._store: Dict[Hashable, CacheEntry] = {}

    def _purge_expired(self) -> None:
        now = time.time()
        to_delete = [k for k, v in self._store.items() if v.expires_at <= now]
        for k in to_delete:
            self._store.pop(k, None)

    def get(self, key: Hashable) -> Optional[Any]:
        with self._lock:
            self._purge_expired()
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.expires_at <= time.time():
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._purge_expired()
            if len(self._store) >= self._maxsize:
                # Simple eviction: remove oldest
                oldest_key = min(self._store.items(), key=lambda kv: kv[1].expires_at)[0]
                self._store.pop(oldest_key, None)
            self._store[key] = CacheEntry(value=value, expires_at=time.time() + self._ttl)

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value
