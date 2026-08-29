import hashlib
import json

import redis

from app.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def make_query_hash(repo_id: str, query_text: str) -> str:
    raw = f"{repo_id}:{query_text.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached_response(cache_key: str):
    value = redis_client.get(cache_key)
    if value:
        return json.loads(value)
    return None


def set_cached_response(cache_key: str, data: dict, ttl_seconds: int = None):
    ttl = ttl_seconds or settings.SEARCH_CACHE_TTL
    redis_client.setex(cache_key, ttl, json.dumps(data))