"""Planejamento de posts estáticos e carrosséis com base no contexto do workspace."""

from pydantic import BaseModel, Field

from app.core.ai import get_openai
from app.core.config import get_settings
from app.modules.workspace.context import brand_art_direction, workspace_context_block


class SlidePlan(BaseModel):
    headline: str = Field(
        description="Frase de destaque do slide (máx. 9 palavras, impacto imediato)"
    )
    body: str = Field(
        description=(
            "Texto de apoio: 1-2 frases curtas que desenvolvem a headline. "
            "Vazio quando a headline se basta (ex.: capa)."
        )
    )
    image_prompt: str = Field(
        description=(
            "Prompt EM INGLÊS para o fundo do slide: fotografia ou composição "
            "abstrata premium relacionada ao tema. A imagem NÃO deve conter texto, "
            "letras, logotipos nem interfaces. Descreva iluminação e paleta."
        )
    )


class PostPlan(BaseModel):
    caption: str = Field(
        description=(
            "Legenda completa do post para a plataforma: gancho na primeira linha, "
            "desenvolvimento curto e CTA no fim. Sem hashtags aqui."
        )
    )
    hashtags: list[str] = Field(description="8-15 hashtags relevantes, sem o caractere #")
    slides: list[SlidePlan]


STATIC_RULES = """\
Crie UM ÚNICO slide (post estático de feed):
- headline: o gancho/mensagem central do post.
- body: complemento curto ou vazio.
"""

CAROUSEL_RULES = """\
Crie um CARROSSEL de 6 a 8 slides com arco narrativo:
- Slide 1 (capa): gancho forte que faz a pessoa deslizar. body vazio ou mínimo.
- Slides do meio: um conceito por slide, progressão lógica (problema -> insight ->
  passos/valor). headline curta + body objetivo.
- Penúltimo: síntese ou resultado esperado.
- Último: CTA claro (seguir, salvar, comentar, comprar), coerente com o objetivo do projeto.
Os fundos devem ser visualmente coesos entre si (mesma paleta/estética), variando o motivo.
"""

SYSTEM_PROMPT = """\
Você é um diretor de arte e copywriter sênior de social media, especialista em posts
de feed (Instagram/LinkedIn) com alto salvamento e compartilhamento.

Regras gerais:
- Headlines curtas, concretas e sem clichê; nada de "desbloqueie o seu potencial".
- body sempre escaneável; sem emojis em headline, no máximo pontuais no body.
- image_prompt sempre em inglês, estética premium e coesa; NUNCA peça texto na imagem.
- Escreva headline, body, caption e hashtags no idioma: {language}.
{art_direction}
{kind_rules}
"""

ART_DIRECTION_TEMPLATE = """\
- IDENTIDADE VISUAL DA MARCA (obrigatória): TODO image_prompt deve refletir estas
  diretrizes para os fundos ficarem coesos com a marca — {art_direction}.
"""


def plan_post(workspace, brief: str, kind: str, language: str = "pt-BR") -> PostPlan:
    settings = get_settings()
    client = get_openai()

    art_direction = brand_art_direction(workspace)
    system = SYSTEM_PROMPT.format(
        language=language,
        kind_rules=CAROUSEL_RULES if kind == "carousel" else STATIC_RULES,
        art_direction=(
            ART_DIRECTION_TEMPLATE.format(art_direction=art_direction) if art_direction else ""
        ),
    )
    context = workspace_context_block(workspace)
    user = ""
    if context:
        user += context + "\n\n"
    user += f"Crie o {'carrossel' if kind == 'carousel' else 'post estático'} sobre: {brief}"

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=PostPlan,
    )
    plan = completion.choices[0].message.parsed
    if plan is None or not plan.slides:
        raise RuntimeError("O modelo não retornou um plano de post válido")
    if kind == "static":
        plan.slides = plan.slides[:1]
    return plan
