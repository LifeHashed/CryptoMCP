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


@dataclass
class ServerConfig:
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


DEFAULT_CONFIG = ServerConfig()
