"""Cliente Redis compartilhado — usado para comunicação com o scheduler."""

import json
from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=True,
    )


def publish_schedule_event(action: str, job: dict) -> None:
    """Publica evento no canal Redis para o scheduler Go receber."""
    settings = get_settings()
    rdb = get_redis()
    event = {"action": action, "job": job}
    rdb.publish(settings.scheduler_channel, json.dumps(event, default=str))
