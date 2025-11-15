"""Redis Pub/Sub for delegating requests to the MCP server."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Callable, Dict, Optional

from .config import PubSubConfig, RedisConfig


class RedisPubSub:
    """Redis Pub/Sub client for request/response delegation.
    
    This allows multiple clients to send requests to a pool of workers
    that process them and return responses via Redis pub/sub channels.
    """

    def __init__(self, redis_config: RedisConfig, pubsub_config: PubSubConfig) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis_config = redis_config
            self._pubsub_config = pubsub_config
            self._redis: Optional[aioredis.Redis] = None
            self._pubsub: Optional[aioredis.client.PubSub] = None
            self._request_handlers: Dict[str, Callable] = {}
            self._pending_responses: Dict[str, asyncio.Future] = {}
        except ImportError:
            raise ImportError("redis package with async support is required. Install with: uv add redis")

    async def connect(self) -> None:
        """Connect to Redis and subscribe to channels."""
        import redis.asyncio as aioredis
        
        self._redis = aioredis.Redis(
            host=self._redis_config.host,
            port=self._redis_config.port,
            db=self._redis_config.db,
            password=self._redis_config.password,
            decode_responses=True
        )
        await self._redis.ping()

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    async def publish_request(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Any:
        """Publish a request and wait for response.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            timeout: Maximum time to wait for response
            
        Returns:
            The response from the worker
            
        Raises:
            TimeoutError: If no response received within timeout
        """
        request_id = str(uuid.uuid4())
        request = {
            "id": request_id,
            "tool": tool_name,
            "arguments": arguments
        }
        
        # Create future for response
        future = asyncio.Future()
        self._pending_responses[request_id] = future
        
        # Subscribe to response channel for this request
        if not self._pubsub:
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(self._pubsub_config.response_channel)
            asyncio.create_task(self._listen_responses())
        
        # Publish request
        await self._redis.publish(
            self._pubsub_config.request_channel,
            json.dumps(request)
        )
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            self._pending_responses.pop(request_id, None)
            raise TimeoutError(f"Request {request_id} timed out after {timeout}s")

    async def _listen_responses(self) -> None:
        """Listen for responses on the response channel."""
        async for message in self._pubsub.listen():
            if message["type"] == "message":
                try:
                    response = json.loads(message["data"])
                    request_id = response.get("id")
                    if request_id in self._pending_responses:
                        future = self._pending_responses.pop(request_id)
                        if "error" in response:
                            future.set_exception(Exception(response["error"]))
                        else:
                            future.set_result(response.get("result"))
                except Exception:
                    pass  # Ignore malformed responses

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """Register a handler for a specific tool.
        
        Args:
            tool_name: Name of the tool
            handler: Async function to handle the tool call
        """
        self._request_handlers[tool_name] = handler

    async def start_worker(self) -> None:
        """Start a worker that processes requests from the request channel.
        
        This should be called by server instances that want to process requests.
        """
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self._pubsub_config.request_channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    request = json.loads(message["data"])
                    request_id = request.get("id")
                    tool_name = request.get("tool")
                    arguments = request.get("arguments", {})
                    
                    # Find handler
                    handler = self._request_handlers.get(tool_name)
                    if not handler:
                        response = {
                            "id": request_id,
                            "error": f"Unknown tool: {tool_name}"
                        }
                    else:
                        try:
                            result = await handler(**arguments)
                            response = {
                                "id": request_id,
                                "result": result
                            }
                        except Exception as e:
                            response = {
                                "id": request_id,
                                "error": str(e)
                            }
                    
                    # Publish response
                    await self._redis.publish(
                        self._pubsub_config.response_channel,
                        json.dumps(response)
                    )
                except Exception:
                    pass  # Ignore malformed requests
