"""Simple caching utilities for Crypto Market MCP server."""
from __future__ import annotations

import json
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


class RedisCache:
    """Redis-backed cache with TTL support.
    
    Uses Redis for distributed caching across multiple server instances.
    """

    def __init__(self, ttl_seconds: int = 10, redis_host: str = "localhost", 
                 redis_port: int = 6379, redis_db: int = 0, redis_password: Optional[str] = None) -> None:
        try:
            import redis
            self._redis = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=False  # We'll handle encoding ourselves
            )
            self._ttl = ttl_seconds
            # Test connection
            self._redis.ping()
        except ImportError:
            raise ImportError("redis package is required for RedisCache. Install with: uv add redis")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis at {redis_host}:{redis_port}: {e}")

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes for Redis storage."""
        return json.dumps(value).encode('utf-8')

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes from Redis to Python object."""
        if data is None:
            return None
        return json.loads(data.decode('utf-8'))

    def get(self, key: Hashable) -> Optional[Any]:
        try:
            data = self._redis.get(str(key))
            if data is None:
                return None
            return self._deserialize(data)
        except Exception:
            return None

    def set(self, key: Hashable, value: Any) -> None:
        try:
            data = self._serialize(value)
            self._redis.setex(str(key), self._ttl, data)
        except Exception:
            pass  # Silently fail cache writes

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = factory()
        self.set(key, value)
        return value
