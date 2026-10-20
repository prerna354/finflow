"""Tiny Redis cache helpers. If Redis has a problem, the API still works (just slower)."""
import json
import logging

from app.core.redis import redis_client

log = logging.getLogger(__name__)


def cache_get(key: str):
    try:
        value = redis_client.get(key)
        return json.loads(value) if value else None
    except Exception:
        log.exception("cache_get failed")
        return None


def cache_set(key: str, value, ttl: int = 30):
    try:
        redis_client.set(key, json.dumps(value), ex=ttl)
    except Exception:
        log.exception("cache_set failed")


def cache_delete(*keys: str):
    try:
        if keys:
            redis_client.delete(*keys)
    except Exception:
        log.exception("cache_delete failed")


def payments_cache_key(user_id) -> str:
    return f"payments:{user_id}"


STATS_CACHE_KEY = "admin:stats"
