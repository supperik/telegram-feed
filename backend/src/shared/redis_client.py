import redis.asyncio as redis

from shared.config import get_settings


def make_redis_client() -> "redis.Redis":
    s = get_settings()
    return redis.from_url(s.redis_dsn, decode_responses=True)
