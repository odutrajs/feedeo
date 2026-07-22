from app.core.ai import get_openai
from app.core.config import get_settings
from app.modules.script.schema import Script

SYSTEM_PROMPT = """\
Você é um roteirista especialista em vídeos verticais curtos (TikTok, Reels, YouTube Shorts).

Regras do roteiro:
- O vídeo deve ter entre {min_seconds} e {max_seconds} segundos no total.
- A primeira cena é SEMPRE o gancho (role="hook"): uma frase forte, curiosa ou polêmica
  que prende a atenção nos primeiros 3 segundos. Nunca comece com saudações.
- Estrutura: hook -> intro (contexto rápido) -> development (2 a 5 cenas com o conteúdo
  principal) -> conclusion -> cta.
- Cada cena deve ter narração de 5 a 15 segundos (aprox. 2,5 palavras por segundo).
- A narração deve ser falada, natural e direta, sem marcações como "[pausa]" ou emojis.
- A descrição visual de cada cena descreve UMA imagem estática marcante que representa
  aquele momento (o vídeo é montado com imagens geradas por IA + movimento de câmera).
- Escreva narração e título no idioma: {language}.
- A duração estimada de cada cena deve ser coerente com o tamanho do texto narrado.
"""


def generate_script(
    topic: str,
    language: str = "pt-BR",
    min_seconds: int = 40,
    max_seconds: int = 75,
    extra_instructions: str | None = None,
) -> Script:
    settings = get_settings()
    client = get_openai()

    system = SYSTEM_PROMPT.format(
        min_seconds=min_seconds, max_seconds=max_seconds, language=language
    )
    user = f"Crie o roteiro completo de um vídeo sobre: {topic}"
    if extra_instructions:
        user += f"\n\nInstruções adicionais: {extra_instructions}"

    completion = client.beta.chat.completions.parse(
        model=settings.openai_text_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format=Script,
    )
    script = completion.choices[0].message.parsed
    if script is None or not script.scenes:
        raise RuntimeError("O modelo não retornou um roteiro válido")
    return script
