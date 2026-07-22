"""Geração premium de imagens via FLUX.2 Pro (fal.ai)."""

import os

import fal_client
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("images")

MAX_RETRIES = 3

SANITIZE_PREFIX = (
    "SAFETY REWRITE: Reinterpret the scene below in a way that is completely safe "
    "for all audiences. Remove any nudity, violence, sexual or suggestive elements. "
    "Keep the same mood, composition and artistic style but make it family-friendly.\n\n"
)


def _ensure_fal_key() -> None:
    settings = get_settings()
    if not settings.fal_key:
        raise RuntimeError("FAL_KEY não configurada (backend/.env)")
    os.environ.setdefault("FAL_KEY", settings.fal_key)


def generate_image(prompt: str, width: int = 1024, height: int = 1536) -> bytes:
    """Gera uma imagem em alta qualidade e retorna os bytes em PNG."""
    _ensure_fal_key()
    settings = get_settings()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Gerando imagem com %s em %dx%d (tentativa %d/%d)",
                settings.fal_image_model,
                width,
                height,
                attempt,
                MAX_RETRIES,
            )
            result = fal_client.subscribe(
                settings.fal_image_model,
                arguments={
                    "prompt": prompt,
                    "image_size": {"width": width, "height": height},
                    "output_format": "png",
                    "enable_safety_checker": True,
                    "safety_tolerance": "2",
                },
            )

            images = result.get("images", [])
            if not images:
                raise RuntimeError("A API fal.ai não retornou imagens")

            nsfw = result.get("has_nsfw_concepts", [])
            if nsfw and nsfw[0]:
                logger.warning(
                    "Imagem bloqueada pelo safety checker (tentativa %d/%d), sanitizando...",
                    attempt,
                    MAX_RETRIES,
                )
                prompt = SANITIZE_PREFIX + prompt
                continue

            image_url = images[0]["url"]
            resp = httpx.get(image_url, timeout=60)
            resp.raise_for_status()
            return resp.content

        except Exception as exc:
            if attempt >= MAX_RETRIES:
                raise
            logger.warning(
                "Erro na geração de imagem (tentativa %d/%d): %s",
                attempt,
                MAX_RETRIES,
                exc,
            )

    raise RuntimeError("Falha ao gerar imagem após todas as tentativas")


def regenerate_scene_image(project_id: int, scene_id: int) -> None:
    """Regenerate a single scene image (used by the review flow in the panel)."""
    from app.db.base import db_session
    from app.db.models import AssetKind, Project, Scene, StageRun, StageStatus
    from app.pipeline.stage import StageContext

    with db_session() as db:
        project = db.get(Project, project_id)
        scene = db.get(Scene, scene_id)
        stage_run = StageRun(project_id=project_id, stage="images", status=StageStatus.running)
        db.add(stage_run)
        db.commit()
        ctx = StageContext(db, project, stage_run)
        try:
            if not scene.image_prompt:
                raise RuntimeError("Cena não tem prompt de imagem")
            ctx.log(f"Regenerando imagem da cena {scene.index}")
            png = generate_image(scene.image_prompt)
            version = ctx.next_version(AssetKind.image, scene.id)
            path = ctx.subdir("images") / f"scene_{scene.index:02d}_v{version}.png"
            path.write_bytes(png)
            ctx.save_asset(AssetKind.image, path, scene=scene, meta={"prompt": scene.image_prompt})
            stage_run.status = StageStatus.done
            ctx.log("Imagem regenerada")
        except Exception as exc:
            stage_run.status = StageStatus.failed
            stage_run.error = str(exc)
            logger.exception("Falha ao regenerar imagem da cena %s", scene_id)
        db.commit()
