"""Error hierarchy for Crypto Market MCP server."""
from __future__ import annotations


class CryptoMCPError(Exception):
    """Base error for the Crypto Market MCP server."""


class ExchangeUnavailableError(CryptoMCPError):
    """Raised when the upstream exchange API is unavailable or failing."""


class InvalidSymbolError(CryptoMCPError):
    """Raised when a requested trading pair / symbol is invalid."""


class InvalidTimeRangeError(CryptoMCPError):
    """Raised when a requested historical time range is invalid."""
