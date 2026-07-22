from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


@lru_cache
def get_openai() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada (backend/.env)")
    return OpenAI(api_key=settings.openai_api_key)
