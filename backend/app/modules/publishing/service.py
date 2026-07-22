"""Módulo 8: preparação de metadados de publicação por plataforma."""

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings


class PlatformMeta(BaseModel):
    platform: str = Field(description="tiktok, instagram_reels ou youtube_shorts")
    title: str = Field(description="Título otimizado para a plataforma")
    description: str = Field(description="Descrição/legenda do post, já com quebras de linha")
    hashtags: list[str] = Field(description="Hashtags sem o caractere #, em ordem de relevância")
    keywords: list[str] = Field(description="Palavras-chave para SEO/busca")
    category: str = Field(description="Categoria do conteúdo na plataforma")


class PublishMeta(BaseModel):
    platforms: list[PlatformMeta] = Field(
        description="Metadados para tiktok, instagram_reels e youtube_shorts"
    )


SYSTEM_PROMPT = """\
Você é um especialista em distribuição de conteúdo de vídeo curto.
Para o vídeo descrito, gere metadados otimizados para cada plataforma:
- tiktok: título curto e direto, descrição breve com 3-5 hashtags de nicho + 1-2 amplas;
- instagram_reels: legenda com gancho na primeira linha, quebras de linha, CTA e até 10 hashtags;
- youtube_shorts: título com palavra-chave principal, descrição com contexto e keywords.
Escreva no mesmo idioma do roteiro.
"""


def generate_publish_meta(title: str, topic: str, narration: str, language: str) -> PublishMeta:
    settings = get_settings()
    client = get_openai()
    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Idioma: {language}\nTítulo do vídeo: {title}\nTema: {topic}\n\n"
                    f"Narração completa:\n{narration}"
                ),
            },
        ],
        response_format=PublishMeta,
    )
    meta = completion.choices[0].message.parsed
    if meta is None or not meta.platforms:
        raise RuntimeError("O modelo não retornou metadados de publicação")
    return meta
