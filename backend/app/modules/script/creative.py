"""Copy de criativos de performance (modo creative).

Gera um roteiro de anúncio curto (máx. 15s) com a estrutura consagrada
em mídia paga: hook -> problema -> solução -> prova (opcional) -> CTA,
usando o inventário de trechos enviados pelo usuário como contexto, e
produz hooks alternativos para teste A/B (o hook responde por ~80% da
variação de performance de um criativo).
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings

CreativeRole = Literal["hook", "problem", "solution", "proof", "cta"]


class CreativeScene(BaseModel):
    role: CreativeRole = Field(description="Papel da cena na estrutura do anúncio")
    narration: str = Field(description="Texto exato narrado nesta cena")
    visual_description: str = Field(
        description=(
            "O que deve aparecer na tela: descreva pensando nos trechos de vídeo "
            "disponíveis (ex.: 'produto em close', 'pessoa usando o produto')"
        )
    )
    estimated_duration_seconds: float = Field(description="Duração estimada da narração")


class CreativeCopy(BaseModel):
    title: str = Field(description="Nome interno do criativo (curto)")
    angle: str = Field(
        description="Ângulo de marketing usado (ex.: dor -> alívio, prova social, curiosidade)"
    )
    hook: str = Field(description="Texto do hook principal (primeiros 3 segundos)")
    alternative_hooks: list[str] = Field(
        description="3 a 5 hooks alternativos com abordagens diferentes, para teste A/B"
    )
    call_to_action: str = Field(description="CTA final, curto e único")
    scenes: list[CreativeScene] = Field(description="Cenas em ordem: hook, problem, solution, proof, cta")

    @property
    def full_narration(self) -> str:
        return " ".join(scene.narration.strip() for scene in self.scenes)


SYSTEM_PROMPT = """\
Você é um copywriter sênior de criativos de performance (anúncios em vídeo para
TikTok, Reels e Shorts) com histórico de campanhas escaladas em mídia paga.

O criativo FINAL tem NO MÁXIMO 15 segundos. Seja extremamente econômico com palavras.

Estrutura OBRIGATÓRIA do roteiro (compacta para ≤15s):
1. hook (0-3s): pattern interrupt. Frase curta que para o scroll — pergunta direta,
   afirmação ousada, dado surpreendente ou dor nomeada. NUNCA comece com saudação,
   nome da marca ou "você sabia".
2. problem (2-4s): nomeie a dor exata do cliente, com as palavras que ele mesmo usa.
   O espectador precisa pensar "isso sou eu".
3. solution (4-6s): apresente o produto como a solução. Foque no benefício que
   resolve a dor mais rápido, não em lista de features. Mostre, não descreva.
4. proof (opcional, 1 cena curta ~2s): prova social, resultado, antes/depois ou dado.
   Se o tempo apertar, pule a proof e vá direto ao CTA.
5. cta (últimos 2-3s): UMA única ação, clara e no tom da plataforma
   ("toca no link", "arrasta pra cima", "vem ver"). CTA suave converte mais que
   agressivo em formato UGC.

Regras de escrita:
- Tom conversado, de pessoa real recomendando para um amigo (estilo UGC), não de
  comercial de TV.
- Frases curtas, faladas. Sem jargão, sem "[pausa]", sem emojis.
- Duração total entre {min_seconds} e {max_seconds} segundos (~2,5 palavras/segundo).
  NUNCA ultrapasse {max_seconds}s — conte as palavras e corte o que sobrar.
- Escreva TUDO no idioma: {language}. Narração, título e hooks precisam estar nesse idioma.
- Se houver TRECHOS DE VÍDEO disponíveis (transcrições/descrições abaixo), escreva a
  copy conectada ao que existe: as descrições visuais das cenas devem apontar para
  trechos que o anunciante realmente tem.
- Gere também 3 a 5 hooks alternativos com ângulos DIFERENTES entre si (dor, curiosidade,
  prova, contraste, urgência) — o hook é a variável nº 1 de performance e será testada.
"""


def generate_creative_copy(
    brief: str,
    language: str = "pt-BR",
    min_seconds: int = 10,
    max_seconds: int = 15,
    extra_instructions: str | None = None,
    segment_inventory: list[dict] | None = None,
) -> CreativeCopy:
    settings = get_settings()
    client = get_openai()

    system = SYSTEM_PROMPT.format(
        min_seconds=min_seconds, max_seconds=max_seconds, language=language
    )
    user = f"Brief do produto/oferta:\n{brief}"
    if segment_inventory:
        lines = []
        for seg in segment_inventory:
            lines.append(
                f"- [{seg['id']}] {seg['duration']:.1f}s | {seg['description']} "
                f"| tags: {', '.join(seg.get('tags') or [])} "
                f"| fala: {seg.get('transcript') or '(sem fala)'}"
            )
        user += "\n\nTRECHOS DE VÍDEO/IMAGEM DISPONÍVEIS (matéria-prima do anunciante):\n"
        user += "\n".join(lines)
    if extra_instructions:
        user += f"\n\nInstruções adicionais do anunciante: {extra_instructions}"

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=CreativeCopy,
    )
    copy = completion.choices[0].message.parsed
    if copy is None or not copy.scenes:
        raise RuntimeError("O modelo não retornou uma copy válida")
    return copy
