"""MCP server implementation for crypto market data."""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .config import DEFAULT_CONFIG, ServerConfig
from .exchange_client import ExchangeClient
from .errors import CryptoMCPError
from .pubsub import RedisPubSub

# Global server config - can be overridden via environment or init
_config = DEFAULT_CONFIG
server = FastMCP("crypto-market-mcp")
_client = ExchangeClient(config=_config)
_pubsub: Optional[RedisPubSub] = None


def _serialize(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    return obj


@server.tool()
async def get_ticker(symbol: str) -> Dict[str, Any]:
    """Get the latest ticker for a trading pair (e.g. BTC/USDT)."""
    try:
        ticker = _client.get_ticker(symbol)
        return _serialize(ticker)
    except CryptoMCPError as exc:
        return {"error": str(exc)}


@server.tool()
async def get_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 100) -> List[Dict[str, Any]]:
    """Get historical OHLCV candles for a symbol.

    timeframe: one of 1m, 5m, 15m, 1h, 4h, 1d
    limit: number of candles to return
    """
    try:
        candles = _client.get_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return _serialize(candles)
    except CryptoMCPError as exc:
        return [{"error": str(exc)}]


@server.tool()
async def get_order_book(symbol: str, limit: int = 20) -> Dict[str, Any]:
    """Get the current order book snapshot for a symbol."""
    try:
        ob = _client.get_order_book(symbol, limit=limit)
        return ob
    except CryptoMCPError as exc:
        return {"error": str(exc)}


@server.tool()
async def stream_ticker(symbol: str, interval_seconds: float = 2.0) -> Dict[str, Any]:
    """Return a single ticker snapshot for a symbol.

    NOTE: This is a simplified version for testability. For true streaming,
    you would declare this tool differently or handle streaming at the client
    level by polling this endpoint.
    """

    try:
        ticker = _client.get_ticker(symbol)
        return _serialize(ticker)
    except CryptoMCPError as exc:
        return {"error": str(exc)}


def main() -> None:
    """Entry point to run the MCP server over stdio."""
    server.run()


async def start_worker() -> None:
    """Start a pub/sub worker that processes requests from Redis.
    
    This allows the server to operate in worker mode, processing requests
    published to Redis channels instead of stdio.
    """
    global _pubsub, _config
    
    if not _config.pubsub.enabled:
        raise RuntimeError("Pub/sub is not enabled in configuration")
    
    _pubsub = RedisPubSub(_config.redis, _config.pubsub)
    await _pubsub.connect()
    
    # Register tool handlers
    _pubsub.register_handler("get_ticker", get_ticker)
    _pubsub.register_handler("get_ohlcv", get_ohlcv)
    _pubsub.register_handler("get_order_book", get_order_book)
    _pubsub.register_handler("stream_ticker", stream_ticker)
    
    print(f"Worker started, listening on {_config.pubsub.request_channel}")
    
    try:
        await _pubsub.start_worker()
    finally:
        await _pubsub.disconnect()


def configure_server(config: ServerConfig) -> None:
    """Configure the server with custom settings.
    
    Args:
        config: ServerConfig instance with desired settings
    """
    global _config, _client
    _config = config
    _client = ExchangeClient(config=config)


if __name__ == "__main__":  # pragma: no cover
    main()
