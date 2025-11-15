# Crypto Market MCP

Python-based Model Context Protocol (MCP) server for real-time and historical cryptocurrency market data using ccxt.

## Features

- MCP tools for:
  - `get_ticker(symbol)` – latest ticker for a trading pair
  - `get_ohlcv(symbol, timeframe, limit)` – historical OHLCV candles
  - `get_order_book(symbol, limit)` – order book snapshot
  - `stream_ticker(symbol, interval_seconds)` – streaming-style ticker updates via polling
- Pluggable exchange backend (default: Binance via `ccxt`)
- **Redis cache support** for distributed caching across multiple server instances
- **Redis Pub/Sub** for delegating requests to worker pools
- Simple TTL cache fallback (in-memory)
- Structured error handling
- Small CLI chatbot client to exercise the MCP server.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

Or with `uv`:
```powershell
uv sync
```

## Running the MCP server

The server is installed as a console script named `crypto-market-mcp`.

### Standard mode (stdio)
```powershell
crypto-market-mcp
```

It speaks MCP over stdio, so it can be wired into any MCP-compatible host.

### Worker mode (Redis Pub/Sub)
Start one or more workers to process requests via Redis:
```powershell
crypto-market-worker
```

Configure via environment variables:
```powershell
$env:REDIS_HOST="localhost"
$env:USE_REDIS_CACHE="true"
crypto-market-worker
```

See [REDIS_INTEGRATION.md](REDIS_INTEGRATION.md) for detailed Redis setup and usage.

## Chatbot client

A small chatbot is provided to exercise the MCP server locally.

```powershell
crypto-market-chatbot
```

Example conversation:

```text
you> price BTC/USDT
mcp> {"symbol": "BTC/USDT", "price": 50000.0, ...}

you> ohlcv BTC/USDT
mcp> [ {"timestamp": ..., "open": ...}, ... ]
```

## Running tests

```powershell
pytest
```

This runs unit tests for the cache, exchange client wrapper, and MCP tools.
