"""Redis cache client initialization."""
from redis.asyncio import Redis
from src.config import settings


# Global Redis client
redis_client: Redis | None = None


async def init_redis() -> Redis:
    """Initialize Redis connection."""
    global redis_client
    
    redis_client = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # Test connection
    await redis_client.ping()
    return redis_client


async def close_redis():
    """Close Redis connection."""
    if redis_client:
        await redis_client.close()


def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return redis_client
