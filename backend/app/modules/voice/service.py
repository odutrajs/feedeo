"""Módulo 2: geração de narração via ElevenLabs (voz personalizada)."""

import httpx

from app.core.config import get_settings

API_BASE = "https://api.elevenlabs.io/v1"


def synthesize(
    text: str,
    voice_id: str | None = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.3,
    speed: float = 1.0,
) -> bytes:
    """Generate narration audio (mp3 44.1kHz 128kbps) for the given text."""
    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ELEVENLABS_API_KEY não configurada (backend/.env)")

    voice = voice_id or settings.elevenlabs_voice_id
    response = httpx.post(
        f"{API_BASE}/text-to-speech/{voice}",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": settings.elevenlabs_api_key},
        json={
            "text": text,
            "model_id": settings.elevenlabs_model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "speed": speed,
            },
        },
        timeout=300,
    )
    if response.status_code != 200:
        raise RuntimeError(f"ElevenLabs retornou {response.status_code}: {response.text[:500]}")
    return response.content
