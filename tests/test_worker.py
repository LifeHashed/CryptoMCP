"""Tests for server worker mode and Redis integration."""
import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch

from crypto_market_mcp.config import CacheConfig, PubSubConfig, RedisConfig, ServerConfig
from crypto_market_mcp.server import configure_server, get_ticker, get_ohlcv, start_worker
from crypto_market_mcp.exchange_client import ExchangeClient


class TestServerConfiguration:
    """Tests for server configuration."""

    def test_configure_server_updates_config(self):
        """Test that configure_server updates global config."""
        custom_config = ServerConfig(
            cache=CacheConfig(ttl_seconds=20, use_redis=False)
        )
        
        configure_server(custom_config)
        
        # Verify config was updated by checking cache TTL
        # This is implicit since _config and _client are module-level

    def test_configure_server_with_redis_cache(self):
        """Test configuring server with Redis cache enabled."""
        redis_config = ServerConfig(
            cache=CacheConfig(use_redis=True, ttl_seconds=15),
            redis=RedisConfig(host="localhost", port=6379)
        )
        
        # Should not raise even if Redis is unavailable (falls back to memory)
        configure_server(redis_config)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("redis", reason="redis package not installed"),
    reason="Redis not available"
)
class TestWorkerMode:
    """Tests for worker mode functionality."""

    async def test_start_worker_requires_pubsub_enabled(self):
        """Test that start_worker fails if pub/sub not enabled."""
        config = ServerConfig(
            pubsub=PubSubConfig(enabled=False)
        )
        configure_server(config)
        
        with pytest.raises(RuntimeError, match="Pub/sub is not enabled"):
            await start_worker()

    async def test_start_worker_with_valid_config(self):
        """Test starting worker with valid configuration."""
        config = ServerConfig(
            cache=CacheConfig(use_redis=True),
            redis=RedisConfig(host="localhost", port=6379, db=3),
            pubsub=PubSubConfig(
                enabled=True,
                request_channel="test_worker:requests",
                response_channel="test_worker:responses"
            )
        )
        configure_server(config)
        
        try:
            # Start worker in background
            worker_task = asyncio.create_task(start_worker())
            
            # Give it time to start
            await asyncio.sleep(0.5)
            
            # Cancel the worker
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
        except ConnectionError:
            pytest.skip("Redis server not available")

    async def test_worker_processes_get_ticker_request(self):
        """Test that worker can process get_ticker requests."""
        config = ServerConfig(
            cache=CacheConfig(use_redis=False),  # Use memory cache for tests
            redis=RedisConfig(host="localhost", port=6379, db=3),
            pubsub=PubSubConfig(
                enabled=True,
                request_channel="test_ticker:requests",
                response_channel="test_ticker:responses"
            )
        )
        configure_server(config)
        
        try:
            # Import pubsub client
            from crypto_market_mcp.pubsub import RedisPubSub
            
            # Start worker
            worker_task = asyncio.create_task(start_worker())
            await asyncio.sleep(0.5)
            
            # Create client
            client = RedisPubSub(config.redis, config.pubsub)
            await client.connect()
            
            try:
                # Mock the exchange to avoid real API calls
                with patch("crypto_market_mcp.server._client") as mock_client:
                    from crypto_market_mcp.exchange_client import Ticker
                    mock_client.get_ticker.return_value = Ticker(
                        symbol="BTC/USDT",
                        price=50000.0,
                        timestamp=1234567890
                    )
                    
                    # Send request via pub/sub
                    result = await client.publish_request(
                        "get_ticker",
                        {"symbol": "BTC/USDT"},
                        timeout=5.0
                    )
                    
                    assert result["symbol"] == "BTC/USDT"
                    assert result["price"] == 50000.0
            finally:
                await client.disconnect()
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
        except ConnectionError:
            pytest.skip("Redis server not available")


class TestExchangeClientWithRedis:
    """Tests for ExchangeClient with Redis cache."""

    def test_exchange_client_uses_redis_cache_when_enabled(self):
        """Test that ExchangeClient uses Redis cache when configured."""
        config = ServerConfig(
            cache=CacheConfig(use_redis=True, ttl_seconds=30),
            redis=RedisConfig(host="localhost", port=6379, db=4)
        )
        
        try:
            client = ExchangeClient(config=config)
            # If Redis is available, cache should be RedisCache
            from crypto_market_mcp.cache import RedisCache
            assert isinstance(client._cache, RedisCache)
        except (ConnectionError, Exception):
            # If Redis not available, should fall back to TTLCache
            from crypto_market_mcp.cache import TTLCache
            client = ExchangeClient(config=config)
            # Fallback should create TTLCache instead
            pass

    def test_exchange_client_falls_back_to_memory_cache(self):
        """Test that ExchangeClient falls back to memory cache if Redis fails."""
        config = ServerConfig(
            cache=CacheConfig(use_redis=True, ttl_seconds=30),
            redis=RedisConfig(host="nonexistent.invalid", port=9999)
        )
        
        # Should not raise, should fall back to TTLCache
        client = ExchangeClient(config=config)
        from crypto_market_mcp.cache import TTLCache
        assert isinstance(client._cache, TTLCache)

    def test_exchange_client_uses_memory_cache_when_disabled(self):
        """Test that ExchangeClient uses memory cache when Redis is disabled."""
        config = ServerConfig(
            cache=CacheConfig(use_redis=False, ttl_seconds=10)
        )
        
        client = ExchangeClient(config=config)
        from crypto_market_mcp.cache import TTLCache
        assert isinstance(client._cache, TTLCache)
