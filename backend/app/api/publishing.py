"""Contas de plataforma, publicações e publicação via Instagram."""

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import PlatformAccountCreate, PlatformAccountOut, PublicationOut
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import (
    Asset,
    AssetKind,
    PlatformAccount,
    Project,
    Publication,
    PublishLog,
    User,
)

router = APIRouter(prefix="/api/publishing", tags=["publishing"])
logger = get_logger("publishing")
settings = get_settings()


# ── Accounts CRUD ────────────────────────────────────────────────────


@router.get("/accounts", response_model=list[PlatformAccountOut])
def list_accounts(
    db: Session = Depends(get_db), user: User = Depends(get_subscribed_user)
):
    return (
        db.query(PlatformAccount)
        .filter(PlatformAccount.user_id == user.id, PlatformAccount.active == True)  # noqa: E712
        .all()
    )


@router.post("/accounts", response_model=PlatformAccountOut)
def create_account(
    body: PlatformAccountCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    account = PlatformAccount(
        user_id=user.id,
        platform=body.platform,
        name=body.name,
        credentials=body.credentials,
    )
    db.add(account)
    db.commit()
    return account


@router.delete("/accounts/{account_id}")
def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    account = db.get(PlatformAccount, account_id)
    if account is None or account.user_id != user.id:
        raise HTTPException(404, "Conta não encontrada")
    account.active = False
    db.commit()
    return {"ok": True}


# ── Publications ─────────────────────────────────────────────────────


@router.get("/publications", response_model=list[PublicationOut])
def list_publications(
    project_id: int | None = None,
    social_post_id: int | None = None,
    workspace_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    q = (
        db.query(Publication)
        .join(PlatformAccount, PlatformAccount.id == Publication.account_id)
        .filter(PlatformAccount.user_id == user.id)
        .order_by(Publication.created_at.desc())
    )
    if project_id:
        q = q.filter(Publication.project_id == project_id)
    if social_post_id:
        q = q.filter(Publication.social_post_id == social_post_id)
    if workspace_id:
        q = q.filter(PlatformAccount.workspace_id == workspace_id)
    return q.all()


# ── Publish to Instagram ────────────────────────────────────────────


class PublishRequest(BaseModel):
    project_id: int
    platform: str = "instagram_reels"


def _do_publish_instagram(publication_id: int) -> None:
    """Executa a publicação em background."""
    from app.db.base import db_session
    from app.modules.platforms.instagram import InstagramPublisher

    with db_session() as db:
        pub = db.get(Publication, publication_id)
        if not pub:
            return

        account = db.get(PlatformAccount, pub.account_id)
        project = db.get(Project, pub.project_id)
        if not account or not project:
            pub.status = "failed"
            pub.error = "Conta ou projeto não encontrado"
            return

        # Buscar vídeo renderizado
        video_asset = (
            db.query(Asset)
            .filter(
                Asset.project_id == project.id,
                Asset.kind == AssetKind.video,
                Asset.is_current == True,  # noqa: E712
            )
            .first()
        )
        if not video_asset:
            pub.status = "failed"
            pub.error = "Vídeo não encontrado"
            return

        # Buscar metadados de publicação
        publish_meta_asset = (
            db.query(Asset)
            .filter(
                Asset.project_id == project.id,
                Asset.kind == AssetKind.publish_meta,
                Asset.is_current == True,  # noqa: E712
            )
            .first()
        )

        title = project.title or project.topic
        description = ""
        hashtags: list[str] = []

        if publish_meta_asset:
            meta_path = settings.storage_dir / publish_meta_asset.path
            if meta_path.is_file():
                meta_data = json.loads(meta_path.read_text())
                for p in meta_data.get("platforms", []):
                    if "reels" in p.get("platform", "").lower() or "instagram" in p.get("platform", "").lower():
                        title = p.get("title", title)
                        description = p.get("description", "")
                        hashtags = p.get("hashtags", [])
                        break

        # Montar URL pública do vídeo
        if not settings.public_base_url:
            pub.status = "failed"
            pub.error = "PUBLIC_BASE_URL não configurado"
            return

        video_url = f"{settings.public_base_url}/media/{video_asset.path}"

        pub.status = "uploading"
        db.commit()

        db.add(PublishLog(publication_id=pub.id, level="info", message=f"Enviando vídeo: {video_url}"))
        db.commit()

        try:
            from app.modules.platforms.base import UploadRequest

            publisher = InstagramPublisher()
            result = publisher.upload(
                credentials=account.credentials,
                request=UploadRequest(
                    video_path=Path(video_url),
                    title=title,
                    description=description,
                    hashtags=hashtags,
                    keywords=[],
                    category="",
                ),
            )
            pub.status = "published"
            pub.external_id = result.external_id
            pub.error = None
            db.add(PublishLog(
                publication_id=pub.id,
                level="info",
                message=f"Publicado com sucesso: {result.url}",
            ))
        except Exception as exc:
            logger.exception("Erro ao publicar no Instagram")
            pub.status = "failed"
            pub.error = str(exc)
            db.add(PublishLog(
                publication_id=pub.id,
                level="error",
                message=str(exc),
            ))


@router.post("/publish", response_model=PublicationOut)
def publish_to_platform(
    body: PublishRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Inicia a publicação de um projeto no Instagram."""
    project = db.get(Project, body.project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado")

    # Encontrar conta Instagram do workspace
    account = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.user_id == user.id,
            PlatformAccount.platform == "instagram",
            PlatformAccount.workspace_id == project.workspace_id,
            PlatformAccount.active == True,  # noqa: E712
        )
        .first()
    )
    if not account:
        raise HTTPException(400, "Nenhuma conta do Instagram conectada a este workspace")

    # Verificar se vídeo existe
    video = (
        db.query(Asset)
        .filter(
            Asset.project_id == project.id,
            Asset.kind == AssetKind.video,
            Asset.is_current == True,  # noqa: E712
        )
        .first()
    )
    if not video:
        raise HTTPException(400, "Projeto não tem vídeo renderizado")

    # Criar registro de publicação
    pub = Publication(
        project_id=project.id,
        account_id=account.id,
        status="scheduled",
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)

    background_tasks.add_task(_do_publish_instagram, pub.id)

    return pub


# ── Publish social post (imagem / carrossel) ─────────────────────────


class PublishPostRequest(BaseModel):
    social_post_id: int


def _do_publish_social_post(publication_id: int) -> None:
    """Publica post estático ou carrossel no Instagram em background."""
    from app.db.base import db_session
    from app.db.models import SocialPost
    from app.modules.platforms.instagram import InstagramPublisher

    with db_session() as db:
        pub = db.get(Publication, publication_id)
        if not pub:
            return

        account = db.get(PlatformAccount, pub.account_id)
        post = db.get(SocialPost, pub.social_post_id) if pub.social_post_id else None
        if not account or not post:
            pub.status = "failed"
            pub.error = "Conta ou post não encontrado"
            return

        if not settings.public_base_url:
            pub.status = "failed"
            pub.error = "PUBLIC_BASE_URL não configurado"
            return

        image_urls: list[str] = []
        for slide in sorted(post.slides, key=lambda s: s.index):
            path = slide.composed_path or slide.image_path
            if path:
                image_urls.append(f"{settings.public_base_url}/media/{path}")

        if not image_urls:
            pub.status = "failed"
            pub.error = "Post sem imagens prontas"
            return

        caption_parts = [post.caption] if post.caption else []
        if post.hashtags:
            caption_parts.append(" ".join(f"#{h}" for h in post.hashtags))
        caption = "\n\n".join(caption_parts)

        pub.status = "uploading"
        db.commit()
        db.add(PublishLog(
            publication_id=pub.id,
            level="info",
            message=f"Publicando {post.kind} com {len(image_urls)} imagem(ns)",
        ))
        db.commit()

        try:
            publisher = InstagramPublisher()
            if post.kind == "carousel" and len(image_urls) >= 2:
                result = publisher.publish_carousel(
                    credentials=account.credentials,
                    image_urls=image_urls,
                    caption=caption,
                )
            else:
                result = publisher.publish_image(
                    credentials=account.credentials,
                    image_url=image_urls[0],
                    caption=caption,
                )

            from datetime import datetime, timezone

            pub.status = "published"
            pub.external_id = result.external_id
            pub.published_at = datetime.now(timezone.utc)
            pub.error = None
            db.add(PublishLog(
                publication_id=pub.id,
                level="info",
                message=f"Publicado com sucesso: {result.url}",
            ))
        except Exception as exc:
            logger.exception("Erro ao publicar post no Instagram")
            pub.status = "failed"
            pub.error = str(exc)
            db.add(PublishLog(
                publication_id=pub.id,
                level="error",
                message=str(exc),
            ))


@router.post("/publish-post", response_model=PublicationOut)
def publish_social_post(
    body: PublishPostRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Inicia a publicação de um post estático ou carrossel no Instagram."""
    from app.db.models import SocialPost, Workspace

    post = db.get(SocialPost, body.social_post_id)
    if not post:
        raise HTTPException(404, "Post não encontrado")
    if post.status != "completed":
        raise HTTPException(400, "Post ainda não está pronto para publicar")

    workspace = db.get(Workspace, post.workspace_id)
    if not workspace or workspace.user_id != user.id:
        raise HTTPException(404, "Post não encontrado")

    account = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.user_id == user.id,
            PlatformAccount.platform == "instagram",
            PlatformAccount.workspace_id == post.workspace_id,
            PlatformAccount.active == True,  # noqa: E712
        )
        .first()
    )
    if not account:
        raise HTTPException(400, "Nenhuma conta do Instagram conectada a este workspace")

    ready_slides = [
        s for s in post.slides if (s.composed_path or s.image_path)
    ]
    if not ready_slides:
        raise HTTPException(400, "Post sem imagens prontas")

    pub = Publication(
        project_id=None,
        social_post_id=post.id,
        account_id=account.id,
        status="scheduled",
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)

    background_tasks.add_task(_do_publish_social_post, pub.id)
    return pub
