"""Módulo 4: planejamento visual.

Gera primeiro um style guide global (identidade visual do vídeo) e depois
um prompt de imagem por cena que embute esse guia, garantindo consistência
entre todas as imagens do mesmo vídeo.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings

Motion = Literal["zoom_in", "zoom_out", "pan_left", "pan_right"]


class ScenePlan(BaseModel):
    scene_index: int = Field(description="Índice da cena (começando em 0)")
    image_prompt: str = Field(
        description=(
            "Prompt completo em inglês para gerar a imagem desta cena, "
            "já incorporando o style guide global"
        )
    )
    motion: Motion = Field(description="Movimento de câmera aplicado sobre a imagem")


class VisualPlan(BaseModel):
    style_guide: str = Field(
        description=(
            "Identidade visual global do vídeo em inglês: estilo artístico, paleta de "
            "cores, iluminação, atmosfera e técnica. Aplicado a todas as cenas."
        )
    )
    scene_plans: list[ScenePlan] = Field(description="Um plano por cena, na ordem")


SYSTEM_PROMPT = """\
Você é um diretor de arte especialista em vídeos verticais curtos feitos com imagens
geradas por IA.

Sua tarefa:
1. Definir um STYLE GUIDE global para o vídeo: estilo artístico, paleta de cores,
   iluminação e atmosfera. Todas as imagens do vídeo devem parecer parte da mesma obra.
2. Para cada cena, escrever um prompt de imagem em inglês que:
   - descreva a composição em formato VERTICAL (9:16);
   - inclua o sujeito principal e os elementos importantes da cena;
   - termine repetindo os elementos-chave do style guide (estilo, paleta, iluminação);
   - evite texto/letras dentro da imagem;
   - REGRA DE SEGURANÇA: os prompts devem ser totalmente seguros para APIs de geração
     de imagem. Nunca inclua nudez, violência gráfica, conteúdo sexual ou sugestivo.
     Para cenas com temas sensíveis (escravidão, prisão, tortura), foque na emoção
     e na atmosfera sem representar o sofrimento físico diretamente;
   - mantenha continuidade: personagens ou cenários recorrentes devem ser descritos
     da mesma forma em todas as cenas em que aparecem.
3. Escolher um movimento de câmera por cena (zoom_in, zoom_out, pan_left, pan_right),
   variando entre cenas consecutivas.
"""


def generate_visual_plan(
    scenes: list[dict],
    topic: str,
    style_preset: str | None = None,
) -> VisualPlan:
    settings = get_settings()
    client = get_openai()

    scene_lines = "\n".join(
        f"Cena {s['index']} ({s['role']}): narração: {s['narration']!r} | "
        f"visual: {s['visual_description']!r}"
        for s in scenes
    )
    user = f"Tema do vídeo: {topic}\n\nCenas:\n{scene_lines}"
    if style_preset:
        user += f"\n\nEstilo desejado pelo usuário: {style_preset}"

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format=VisualPlan,
    )
    plan = completion.choices[0].message.parsed
    if plan is None or not plan.scene_plans:
        raise RuntimeError("O modelo não retornou um plano visual válido")
    return plan
