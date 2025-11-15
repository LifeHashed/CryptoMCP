from types import SimpleNamespace

from crypto_market_mcp.exchange_client import ExchangeClient, OHLCV, Ticker
from crypto_market_mcp.config import ServerConfig, ExchangeConfig, CacheConfig


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


def test_exchange_client_basic(monkeypatch):
    # Patch ccxt.binance to our dummy
    import crypto_market_mcp.exchange_client as ec

    monkeypatch.setattr(ec, "ccxt", SimpleNamespace(binance=DummyCCXT))

    config = ServerConfig(exchange=ExchangeConfig(name="binance"), cache=CacheConfig(ttl_seconds=60, maxsize=128))
    client = ExchangeClient(config=config)

    ticker = client.get_ticker("BTC/USDT")
    assert isinstance(ticker, Ticker)
    assert ticker.price == 50000.0

    candles = client.get_ohlcv("BTC/USDT", timeframe="1h", limit=2)
    assert len(candles) == 2
    assert isinstance(candles[0], OHLCV)

    ob = client.get_order_book("BTC/USDT", limit=5)
    assert "bids" in ob and "asks" in ob
