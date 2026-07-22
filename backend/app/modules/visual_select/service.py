"""Seleção visual do modo creative: a IA escolhe, para cada cena da copy, o melhor
trecho de vídeo/imagem enviado pelo usuário — ou um prompt de imagem IA como fallback."""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings

VisualChoice = Literal["segment", "ai_image"]


class SceneSelection(BaseModel):
    scene_index: int = Field(description="Índice da cena (começando em 0)")
    choice: VisualChoice = Field(
        description="'segment' para usar um trecho enviado, 'ai_image' para gerar imagem por IA"
    )
    segment_id: int | None = Field(
        default=None,
        description="Id do trecho escolhido (obrigatório quando choice='segment')",
    )
    reason: str = Field(description="Por que este visual serve a esta cena (curto)")
    image_prompt: str | None = Field(
        default=None,
        description=(
            "Prompt de imagem em inglês, formato vertical 9:16, sem texto na imagem "
            "(obrigatório quando choice='ai_image')"
        ),
    )


class VisualSelection(BaseModel):
    selections: list[SceneSelection] = Field(description="Uma seleção por cena, na ordem")


SYSTEM_PROMPT = """\
Você é um editor de vídeo especialista em criativos de performance (anúncios para
TikTok/Reels/Shorts). Você recebe:
1. As cenas do roteiro do anúncio (com papel, narração e descrição visual desejada).
2. O inventário de trechos de vídeo/imagem que o anunciante enviou, cada um com id,
   duração, descrição do que mostra, tags, nota de qualidade e potencial de hook.

Para CADA cena, escolha o visual:
- PREFIRA SEMPRE um trecho real ('segment') quando existir um compatível: material
  real do produto converte mais que imagem gerada. Use a descrição visual da cena
  como guia do que procurar.
- Para a cena de hook, priorize trechos com hook_potential alto (movimento,
  transformação, close chamativo).
- A duração do trecho importa: idealmente igual ou maior que a duração estimada da
  cena (trechos curtos demais congelam no último frame).
- NÃO repita o mesmo trecho em duas cenas, a menos que não haja alternativa.
- Só use 'ai_image' se nenhum trecho servir; nesse caso escreva um prompt de imagem
  em inglês, vertical 9:16, coerente com um anúncio do produto, sem texto na imagem.
"""


def select_visuals(
    scenes: list[dict],
    inventory: list[dict],
    brief: str,
) -> VisualSelection:
    settings = get_settings()
    client = get_openai()

    scene_lines = "\n".join(
        f"Cena {s['index']} ({s['role']}, ~{s['duration']:.1f}s): "
        f"narração: {s['narration']!r} | visual desejado: {s['visual_description']!r}"
        for s in scenes
    )
    inventory_lines = "\n".join(
        f"- id={seg['id']} | {seg['kind']} | {seg['duration']:.1f}s | nota {seg['score']:.1f} "
        f"| hook {seg['hook_potential']:.1f} | {seg['description']} "
        f"| tags: {', '.join(seg['tags'])} | fala: {seg['transcript'] or '(sem fala)'}"
        for seg in inventory
    )
    user = (
        f"Brief do anúncio: {brief}\n\nCenas:\n{scene_lines}\n\n"
        f"Inventário de trechos:\n{inventory_lines or '(nenhum trecho enviado)'}"
    )

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format=VisualSelection,
    )
    selection = completion.choices[0].message.parsed
    if selection is None or not selection.selections:
        raise RuntimeError("O modelo não retornou a seleção visual")
    return selection
