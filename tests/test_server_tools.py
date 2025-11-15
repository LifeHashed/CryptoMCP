import asyncio
from types import SimpleNamespace

from crypto_market_mcp.config import CacheConfig, ExchangeConfig, ServerConfig
from crypto_market_mcp import exchange_client as ec_module
from crypto_market_mcp.exchange_client import ExchangeClient
import crypto_market_mcp.server as server_module
from crypto_market_mcp.server import get_ohlcv, get_order_book, get_ticker


class DummyCCXT:
    id = "dummy"

    def __init__(self, *_args, **_kwargs):
        self._markets = {"BTC/USDT": {"symbol": "BTC/USDT"}}

    def load_markets(self):
        return self._markets

    def fetch_ticker(self, symbol):
        return {"last": 50000.0, "timestamp": 1234567890}

    def fetch_ohlcv(self, symbol, timeframe="1h", limit=100, since=None):
        return [
            [1, 10, 20, 5, 15, 100],
            [2, 15, 25, 10, 20, 200],
        ]

    def fetch_order_book(self, symbol, limit=20):
        return {"bids": [[50000.0, 1.0]], "asks": [[50100.0, 2.0]]}


def setup_module(module):
    # Patch ccxt in the exchange_client module used by the server
    module._orig_ccxt = ec_module.ccxt
    ec_module.ccxt = SimpleNamespace(binance=DummyCCXT)

    # Also patch the already-instantiated client inside the server module
    server_module._client = ExchangeClient()


def teardown_module(module):
    ec_module.ccxt = module._orig_ccxt


def test_get_ticker_tool():
    result = asyncio.run(get_ticker("BTC/USDT"))
    assert result["symbol"] == "BTC/USDT"
    assert result["price"] == 50000.0


def test_get_ohlcv_tool():
    result = asyncio.run(get_ohlcv("BTC/USDT", timeframe="1h", limit=2))
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["open"] == 10.0


def test_get_order_book_tool():
    result = asyncio.run(get_order_book("BTC/USDT", limit=5))
    assert "bids" in result and "asks" in result
