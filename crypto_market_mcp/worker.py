"""Worker entry point for Redis pub/sub mode."""
from __future__ import annotations

import asyncio
import os
import sys

from crypto_market_mcp.config import CacheConfig, PubSubConfig, RedisConfig, ServerConfig
from crypto_market_mcp.server import configure_server, start_worker


def main() -> None:
    """Start a Redis pub/sub worker."""
    # Build config from environment variables
    config = ServerConfig(
        cache=CacheConfig(
            use_redis=os.getenv("USE_REDIS_CACHE", "true").lower() == "true",
            ttl_seconds=int(os.getenv("CACHE_TTL", "10"))
        ),
        redis=RedisConfig(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD")
        ),
        pubsub=PubSubConfig(
            enabled=True,
            request_channel=os.getenv("REQUEST_CHANNEL", "crypto_mcp:requests"),
            response_channel=os.getenv("RESPONSE_CHANNEL", "crypto_mcp:responses")
        )
    )
    
    configure_server(config)
    
    try:
        asyncio.run(start_worker())
    except KeyboardInterrupt:
        print("\nWorker stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
