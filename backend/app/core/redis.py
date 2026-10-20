import redis
import redis.asyncio as aioredis

from app.core.config import settings

CHANNEL = "txn_updates"

# Normal (blocking) client: used by the API and by Celery workers
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_async_redis():
    """Async client: used by the WebSocket endpoint."""
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)
