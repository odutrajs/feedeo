"""Geração de posts estáticos/carrosséis (roda em background após o POST)."""

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.object_storage import get_object_storage
from app.db.models import SocialPost, SocialSlide
from app.modules.images.service import generate_image
from app.modules.social.compose import compose_slide
from app.modules.social.planner import plan_post
from app.modules.workspace.context import brand_identity

logger = get_logger("social")

# Fundo gerado em 4:5 (múltiplos de 64 para o Flux) e recortado para 1080x1350
BG_WIDTH, BG_HEIGHT = 1088, 1344


def generate_post(post_id: int) -> None:
    from app.db.base import db_session

    settings = get_settings()
    with db_session() as db:
        post = db.get(SocialPost, post_id)
        if post is None:
            return
        workspace = post.workspace
        post.status = "running"
        post.error = None
        db.commit()

        out_dir = settings.storage_dir / "workspaces" / str(workspace.id) / "posts" / str(post.id)
        storage = get_object_storage()

        brand = brand_identity(workspace)
        logo_path = (
            settings.storage_dir / workspace.logo_path if workspace.logo_path else None
        )

        try:
            language = str((post.meta or {}).get("language", "pt-BR"))
            logger.info(
                "Post %s (%s): planejando com contexto do workspace %s",
                post.id, post.kind, workspace.id,
            )
            plan = plan_post(workspace, post.brief, post.kind, language)

            post.caption = plan.caption
            post.hashtags = plan.hashtags
            for old in list(post.slides):
                db.delete(old)
            db.flush()

            total = len(plan.slides)
            for i, slide_plan in enumerate(plan.slides):
                logger.info("Post %s: gerando slide %d/%d", post.id, i + 1, total)
                bg_path = out_dir / f"slide_{i:02d}_bg.png"
                bg_path.parent.mkdir(parents=True, exist_ok=True)
                bg_path.write_bytes(
                    generate_image(slide_plan.image_prompt, width=BG_WIDTH, height=BG_HEIGHT)
                )

                composed_path = out_dir / f"slide_{i:02d}.jpg"
                compose_slide(
                    background_path=bg_path,
                    output_path=composed_path,
                    headline=slide_plan.headline,
                    body=slide_plan.body,
                    brand=workspace.name,
                    slide_number=i + 1,
                    slide_total=total,
                    show_swipe_hint=(post.kind == "carousel" and i == 0),
                    logo_path=logo_path,
                    accent_color=brand["primary_color"] or None,
                    text_theme=brand["text_theme"],
                )

                slide = SocialSlide(
                    post_id=post.id,
                    index=i,
                    headline=slide_plan.headline,
                    body=slide_plan.body,
                    image_prompt=slide_plan.image_prompt,
                    image_path=str(bg_path.relative_to(settings.storage_dir)),
                    composed_path=str(composed_path.relative_to(settings.storage_dir)),
                )
                db.add(slide)
                db.commit()
                storage.put_file(bg_path, slide.image_path)
                storage.put_file(composed_path, slide.composed_path)

            post.status = "completed"
            logger.info("Post %s concluído com %d slide(s)", post.id, total)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao gerar post %s", post_id)
            db.rollback()
            post = db.get(SocialPost, post_id)
            post.status = "failed"
            post.error = str(exc)
        db.commit()
