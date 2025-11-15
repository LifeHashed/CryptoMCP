"""Tests for Redis pub/sub worker functionality."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from crypto_market_mcp.config import PubSubConfig, RedisConfig
from crypto_market_mcp.pubsub import RedisPubSub


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("redis", reason="redis package not installed"),
    reason="Redis not available"
)
class TestRedisPubSub:
    """Tests for Redis pub/sub functionality."""

    @pytest.fixture
    async def pubsub_client(self):
        """Create a pub/sub client for testing."""
        redis_config = RedisConfig(host="localhost", port=6379, db=2)
        pubsub_config = PubSubConfig(
            enabled=True,
            request_channel="test:requests",
            response_channel="test:responses"
        )
        
        client = RedisPubSub(redis_config, pubsub_config)
        try:
            await client.connect()
            # Clear test channels
            if client._redis:
                await client._redis.delete("test:requests", "test:responses")
            yield client
        except Exception:
            pytest.skip("Redis server not available")
        finally:
            await client.disconnect()

    async def test_connect_disconnect(self):
        """Test connecting and disconnecting from Redis."""
        redis_config = RedisConfig(host="localhost", port=6379, db=2)
        pubsub_config = PubSubConfig(enabled=True)
        
        client = RedisPubSub(redis_config, pubsub_config)
        
        try:
            await client.connect()
            assert client._redis is not None
            # Test ping
            assert await client._redis.ping()
            
            await client.disconnect()
        except Exception:
            pytest.skip("Redis server not available")

    async def test_register_handler(self, pubsub_client):
        """Test registering a tool handler."""
        async def dummy_handler(arg1: str) -> dict:
            return {"result": arg1}
        
        pubsub_client.register_handler("test_tool", dummy_handler)
        assert "test_tool" in pubsub_client._request_handlers
        assert pubsub_client._request_handlers["test_tool"] == dummy_handler

    async def test_publish_request_and_response(self, pubsub_client):
        """Test publishing a request and receiving a response."""
        # Register a simple handler
        async def echo_handler(message: str) -> dict:
            return {"echo": message}
        
        pubsub_client.register_handler("echo", echo_handler)
        
        # Start worker in background
        worker_task = asyncio.create_task(pubsub_client.start_worker())
        
        # Give worker time to subscribe
        await asyncio.sleep(0.5)
        
        try:
            # Publish request
            result = await pubsub_client.publish_request(
                "echo",
                {"message": "hello"},
                timeout=5.0
            )
            
            assert result == {"echo": "hello"}
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    async def test_request_timeout(self, pubsub_client):
        """Test that requests timeout when no worker responds."""
        with pytest.raises(TimeoutError, match="timed out"):
            await pubsub_client.publish_request(
                "nonexistent_tool",
                {},
                timeout=1.0
            )

    async def test_worker_handles_unknown_tool(self, pubsub_client):
        """Test that worker returns error for unknown tools."""
        # Start worker in background
        worker_task = asyncio.create_task(pubsub_client.start_worker())
        await asyncio.sleep(0.5)
        
        try:
            result = await pubsub_client.publish_request(
                "unknown_tool",
                {},
                timeout=5.0
            )
            pytest.fail("Should have raised an exception")
        except Exception as e:
            assert "Unknown tool" in str(e)
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    async def test_worker_handles_handler_exception(self, pubsub_client):
        """Test that worker catches and returns handler exceptions."""
        async def failing_handler(arg: str) -> dict:
            raise ValueError("Handler error")
        
        pubsub_client.register_handler("failing_tool", failing_handler)
        
        # Start worker
        worker_task = asyncio.create_task(pubsub_client.start_worker())
        await asyncio.sleep(0.5)
        
        try:
            result = await pubsub_client.publish_request(
                "failing_tool",
                {"arg": "test"},
                timeout=5.0
            )
            pytest.fail("Should have raised an exception")
        except Exception as e:
            assert "Handler error" in str(e)
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    async def test_multiple_concurrent_requests(self, pubsub_client):
        """Test handling multiple concurrent requests."""
        async def slow_handler(value: int) -> dict:
            await asyncio.sleep(0.1)
            return {"result": value * 2}
        
        pubsub_client.register_handler("slow_tool", slow_handler)
        
        # Start worker
        worker_task = asyncio.create_task(pubsub_client.start_worker())
        await asyncio.sleep(0.5)
        
        try:
            # Send multiple requests concurrently
            tasks = [
                pubsub_client.publish_request("slow_tool", {"value": i}, timeout=5.0)
                for i in range(5)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Verify all results
            for i, result in enumerate(results):
                assert result == {"result": i * 2}
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    async def test_malformed_request_handling(self, pubsub_client):
        """Test that worker ignores malformed requests."""
        # Start worker
        worker_task = asyncio.create_task(pubsub_client.start_worker())
        await asyncio.sleep(0.5)
        
        try:
            # Publish malformed JSON
            await pubsub_client._redis.publish(
                pubsub_client._pubsub_config.request_channel,
                "not valid json {["
            )
            
            # Worker should not crash, just ignore the message
            await asyncio.sleep(0.5)
            
            # Verify worker is still running by sending valid request
            async def test_handler() -> dict:
                return {"ok": True}
            
            pubsub_client.register_handler("test", test_handler)
            result = await pubsub_client.publish_request("test", {}, timeout=3.0)
            assert result == {"ok": True}
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
class TestRedisPubSubWithoutRedis:
    """Tests for pub/sub when Redis is not available."""

    def test_import_error_on_init(self):
        """Test that ImportError is raised when redis package is missing."""
        with patch.dict("sys.modules", {"redis.asyncio": None}):
            with pytest.raises(ImportError, match="redis package with async support"):
                redis_config = RedisConfig()
                pubsub_config = PubSubConfig(enabled=True)
                RedisPubSub(redis_config, pubsub_config)
