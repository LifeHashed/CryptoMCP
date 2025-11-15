"""Exchange client abstraction using ccxt."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import ccxt

from .config import DEFAULT_CONFIG
from .errors import ExchangeUnavailableError, InvalidSymbolError, InvalidTimeRangeError
from .cache import TTLCache


@dataclass
class Ticker:
    symbol: str
    price: float
    timestamp: int


@dataclass
class OHLCV:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class ExchangeClient:
    """High-level wrapper around ccxt for a single exchange."""

    def __init__(self, *, config=DEFAULT_CONFIG) -> None:
        exchange_name = config.exchange.name
        try:
            exchange_class = getattr(ccxt, exchange_name)
        except AttributeError as exc:
            raise ExchangeUnavailableError(f"Unsupported exchange: {exchange_name}") from exc

        self._exchange = exchange_class({"enableRateLimit": config.exchange.enable_rate_limit})
        self._cache = TTLCache(ttl_seconds=config.cache.ttl_seconds, maxsize=config.cache.maxsize)

    def _load_markets(self) -> Dict[str, Any]:
        return self._cache.get_or_set("markets", lambda: self._exchange.load_markets())

    def _ensure_symbol(self, symbol: str) -> None:
        markets = self._load_markets()
        if symbol not in markets:
            raise InvalidSymbolError(f"Symbol not found on {self._exchange.id}: {symbol}")

    def get_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker for a trading pair."""
        self._ensure_symbol(symbol)
        try:
            ticker = self._cache.get_or_set(("ticker", symbol), lambda: self._exchange.fetch_ticker(symbol))
        except Exception as exc:  # ccxt raises many different errors
            raise ExchangeUnavailableError(str(exc)) from exc

        return Ticker(symbol=symbol, price=float(ticker["last"]), timestamp=int(ticker["timestamp"] or 0))

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "1h",
        *,
        limit: int = 100,
        since: Optional[int] = None,
    ) -> List[OHLCV]:
        """Fetch historical OHLCV data.

        - `timeframe` is constrained to common values for simplicity.
        - Either `limit` or `since` can be given; ccxt handles validation, but we
          also guard obvious bad values.
        """
        if limit <= 0:
            raise InvalidTimeRangeError("limit must be positive")

        self._ensure_symbol(symbol)

        cache_key = ("ohlcv", symbol, timeframe, limit, since)

        def _fetch() -> List[OHLCV]:
            try:
                data = self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since)
            except Exception as exc:
                raise ExchangeUnavailableError(str(exc)) from exc
            return [
                OHLCV(
                    timestamp=int(t),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v),
                )
                for t, o, h, l, c, v in data
            ]

        return self._cache.get_or_set(cache_key, _fetch)

    def get_order_book(self, symbol: str, *, limit: int = 20) -> Dict[str, Any]:
        """Fetch order book for a symbol, mainly for richer real-time snapshots."""
        self._ensure_symbol(symbol)

        cache_key = ("orderbook", symbol, limit)

        def _fetch() -> Dict[str, Any]:
            try:
                return self._exchange.fetch_order_book(symbol, limit=limit)
            except Exception as exc:
                raise ExchangeUnavailableError(str(exc)) from exc

        return self._cache.get_or_set(cache_key, _fetch)
