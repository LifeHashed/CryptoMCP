"""Configuration for Crypto Market MCP server."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExchangeConfig:
    name: str = "binance"
    enable_rate_limit: bool = True


@dataclass
class CacheConfig:
    ttl_seconds: int = 10
    maxsize: int = 1024
    use_redis: bool = False


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True


@dataclass
class PubSubConfig:
    request_channel: str = "crypto_mcp:requests"
    response_channel: str = "crypto_mcp:responses"
    enabled: bool = False


@dataclass
class ServerConfig:
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    pubsub: PubSubConfig = field(default_factory=PubSubConfig)


DEFAULT_CONFIG = ServerConfig()
