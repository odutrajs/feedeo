"""API de workspaces (projetos do usuário) e posts sociais (estáticos/carrosséis)."""

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import (
    SocialPostCreate,
    SocialPostOut,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.core.config import get_settings
from app.core.object_storage import get_object_storage
from app.db.base import get_db
from app.db.models import Project, SocialPost, User, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_LOGO_BYTES = 8 * 1024 * 1024  # 8 MB


def _get_workspace(db: Session, workspace_id: int, user: User) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado")
    return workspace


def _counts(db: Session, workspace: Workspace) -> dict:
    return {
        "video_count": db.query(Project).filter(Project.workspace_id == workspace.id).count(),
        "post_count": db.query(SocialPost)
        .filter(SocialPost.workspace_id == workspace.id)
        .count(),
    }


def _workspace_out(db: Session, workspace: Workspace) -> WorkspaceOut:
    return WorkspaceOut.model_validate(workspace).model_copy(update=_counts(db, workspace))


@router.post("", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    workspace = Workspace(
        user_id=user.id, name=body.name.strip(), description=body.description.strip()
    )
    db.add(workspace)
    db.commit()
    return _workspace_out(db, workspace)


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db), user: User = Depends(get_subscribed_user)
):
    workspaces = (
        db.query(Workspace)
        .filter(Workspace.user_id == user.id)
        .order_by(Workspace.created_at.desc())
        .all()
    )
    return [_workspace_out(db, w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    workspace = _get_workspace(db, workspace_id, user)
    projects = (
        db.query(Project)
        .filter(Project.workspace_id == workspace.id)
        .order_by(Project.created_at.desc())
        .all()
    )
    posts = (
        db.query(SocialPost)
        .filter(SocialPost.workspace_id == workspace.id)
        .order_by(SocialPost.created_at.desc())
        .all()
    )
    detail = WorkspaceDetail.model_validate(workspace).model_copy(
        update={
            **_counts(db, workspace),
            "projects": projects,
            "posts": posts,
        }
    )
    return detail


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: int,
    body: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    workspace = _get_workspace(db, workspace_id, user)
    if body.name is not None and body.name.strip():
        workspace.name = body.name.strip()
    if body.description is not None:
        workspace.description = body.description.strip()
    if body.brand is not None:
        workspace.brand = body.brand.model_dump()
    db.commit()
    return _workspace_out(db, workspace)


@router.put("/{workspace_id}/logo", response_model=WorkspaceOut)
async def upload_logo(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Envia/substitui a logo da marca usada nas artes dos posts."""
    workspace = _get_workspace(db, workspace_id, user)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in LOGO_EXTENSIONS:
        raise HTTPException(400, "Formato inválido; use PNG, JPG ou WEBP")

    data = await file.read()
    if len(data) > MAX_LOGO_BYTES:
        raise HTTPException(400, "Logo muito grande (máx. 8 MB)")

    settings = get_settings()
    logo_dir = settings.storage_dir / "workspaces" / str(workspace.id)
    logo_dir.mkdir(parents=True, exist_ok=True)
    # Remove logos antigas para não acumular versões
    for old in logo_dir.glob("logo.*"):
        old.unlink(missing_ok=True)
    logo_file = logo_dir / f"logo{ext}"
    logo_file.write_bytes(data)

    rel = str(logo_file.relative_to(settings.storage_dir))
    workspace.logo_path = rel
    db.commit()
    get_object_storage().put_file(logo_file, rel)
    return _workspace_out(db, workspace)


@router.delete("/{workspace_id}/logo", response_model=WorkspaceOut)
def delete_logo(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    workspace = _get_workspace(db, workspace_id, user)
    settings = get_settings()
    if workspace.logo_path:
        (settings.storage_dir / workspace.logo_path).unlink(missing_ok=True)
    workspace.logo_path = None
    db.commit()
    return _workspace_out(db, workspace)


@router.delete("/{workspace_id}")
def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Remove o workspace e seus posts; os vídeos ficam (desvinculados)."""
    workspace = _get_workspace(db, workspace_id, user)
    db.query(Project).filter(Project.workspace_id == workspace.id).update(
        {Project.workspace_id: None}
    )
    settings = get_settings()
    shutil.rmtree(settings.storage_dir / "workspaces" / str(workspace.id), ignore_errors=True)
    db.delete(workspace)
    db.commit()
    return {"ok": True}


# ── Posts sociais (imagem estática / carrossel) ─────────────────────────────


@router.post("/{workspace_id}/posts", response_model=SocialPostOut)
def create_post(
    workspace_id: int,
    body: SocialPostCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    workspace = _get_workspace(db, workspace_id, user)
    if body.kind not in ("static", "carousel"):
        raise HTTPException(400, "kind deve ser 'static' ou 'carousel'")
    post = SocialPost(
        workspace_id=workspace.id,
        kind=body.kind,
        brief=body.brief.strip(),
        status="queued",
        meta={"language": body.language},
    )
    db.add(post)
    db.commit()

    from app.modules.social.service import generate_post

    background.add_task(generate_post, post.id)
    return post


@router.post("/{workspace_id}/posts/{post_id}/regenerate", response_model=SocialPostOut)
def regenerate_post(
    workspace_id: int,
    post_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    _get_workspace(db, workspace_id, user)
    post = db.get(SocialPost, post_id)
    if post is None or post.workspace_id != workspace_id:
        raise HTTPException(404, "Post não encontrado")
    post.status = "queued"
    post.error = None
    db.commit()

    from app.modules.social.service import generate_post

    background.add_task(generate_post, post.id)
    return post


@router.delete("/{workspace_id}/posts/{post_id}")
def delete_post(
    workspace_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    _get_workspace(db, workspace_id, user)
    post = db.get(SocialPost, post_id)
    if post is None or post.workspace_id != workspace_id:
        raise HTTPException(404, "Post não encontrado")
    settings = get_settings()
    shutil.rmtree(
        settings.storage_dir / "workspaces" / str(workspace_id) / "posts" / str(post.id),
        ignore_errors=True,
    )
    db.delete(post)
    db.commit()
    return {"ok": True}
