"""Contexto do workspace (projeto do usuário) injetado nas gerações."""

from app.db.models import Project, Workspace


def brand_identity(workspace: Workspace | None) -> dict:
    """Identidade visual normalizada do workspace (sempre com as chaves esperadas)."""
    raw = (getattr(workspace, "brand", None) or {}) if workspace else {}
    theme = str(raw.get("text_theme") or "dark").lower()
    if theme not in ("dark", "light"):
        theme = "dark"
    return {
        "primary_color": (raw.get("primary_color") or "").strip(),
        "secondary_color": (raw.get("secondary_color") or "").strip(),
        "visual_style": (raw.get("visual_style") or "").strip(),
        "text_theme": theme,
    }


def brand_art_direction(workspace: Workspace | None) -> str | None:
    """Direção de arte (paleta + estilo) para orientar os prompts de imagem. None se vazio."""
    brand = brand_identity(workspace)
    parts: list[str] = []
    palette = [c for c in (brand["primary_color"], brand["secondary_color"]) if c]
    if palette:
        parts.append(f"brand color palette {', '.join(palette)}")
    if brand["visual_style"]:
        parts.append(f"visual style: {brand['visual_style']}")
    if brand["text_theme"] == "light":
        parts.append("bright, airy, light background composition")
    else:
        parts.append("dark, moody, high-contrast composition")
    return "; ".join(parts) if palette or brand["visual_style"] else None


def workspace_context_block(workspace: Workspace | None) -> str | None:
    """Bloco de contexto para prompts de LLM; None se não houver workspace."""
    if workspace is None or not (workspace.description or "").strip():
        return None
    block = (
        f"CONTEXTO DO PROJETO \"{workspace.name}\" (use como referência obrigatória "
        "de marca, público, tom de voz e objetivos em tudo que você criar):\n"
        f"{workspace.description.strip()}"
    )
    brand = brand_identity(workspace)
    identity_bits = [
        b
        for b in (
            f"paleta {brand['primary_color']}/{brand['secondary_color']}".strip("/")
            if brand["primary_color"] or brand["secondary_color"]
            else "",
            f"estética: {brand['visual_style']}" if brand["visual_style"] else "",
        )
        if b
    ]
    if identity_bits:
        block += "\n\nIdentidade visual da marca: " + "; ".join(identity_bits) + "."
    return block


def project_extra_instructions(project: Project, config: dict) -> str | None:
    """Combina o contexto do workspace com as instruções do projeto de vídeo."""
    parts: list[str] = []
    context = workspace_context_block(project.workspace)
    if context:
        parts.append(context)
    instructions = (config or {}).get("script_instructions")
    if instructions:
        parts.append(str(instructions))
    return "\n\n".join(parts) if parts else None
