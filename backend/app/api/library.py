"""API da biblioteca de mídia reutilizável."""

import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import AttachLibraryRequest, LibraryAssetOut, SourceAssetOut
from app.core.config import get_settings
from app.core.object_storage import get_object_storage
from app.db.base import get_db
from app.db.models import LibraryAsset, Project, SourceAsset, SourceStatus, User
from app.modules.library.service import delete_library_files, save_to_library

router = APIRouter(prefix="/api/library", tags=["library"])

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB por arquivo


def _safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^\w.\-]+", "_", name) or "arquivo"


@router.get("", response_model=list[LibraryAssetOut])
def list_library(
    db: Session = Depends(get_db), user: User = Depends(get_subscribed_user)
):
    return (
        db.query(LibraryAsset)
        .filter(LibraryAsset.user_id == user.id)
        .order_by(LibraryAsset.created_at.desc())
        .all()
    )


@router.post("", response_model=list[LibraryAssetOut])
async def upload_to_library(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Upload direto para a biblioteca (sem vincular a um projeto)."""
    settings = get_settings()
    tmp_dir = settings.library_dir / "_tmp" / str(user.id)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    created: list[LibraryAsset] = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            kind = "video"
        elif ext in IMAGE_EXTENSIONS:
            kind = "image"
        else:
            raise HTTPException(400, f"Formato não suportado: {upload.filename}")

        filename = _safe_filename(upload.filename or f"upload{ext}")
        tmp = tmp_dir / filename
        with tmp.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                out.write(chunk)
                if out.tell() > MAX_UPLOAD_BYTES:
                    out.close()
                    tmp.unlink(missing_ok=True)
                    raise HTTPException(413, f"Arquivo muito grande: {filename}")

        asset = save_to_library(
            db, user_id=user.id, source_path=tmp, filename=filename, kind=kind
        )
        tmp.unlink(missing_ok=True)
        created.append(asset)

    return created


@router.delete("/{asset_id}")
def delete_library_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    asset = db.get(LibraryAsset, asset_id)
    if asset is None or asset.user_id != user.id:
        raise HTTPException(404, "Item não encontrado na biblioteca")
    delete_library_files(asset)
    db.delete(asset)
    db.commit()
    return {"ok": True}


# ── Anexar biblioteca a um projeto (rota no router de sources) ─────────────

sources_library_router = APIRouter(
    prefix="/api/projects/{project_id}/sources", tags=["sources"]
)


@sources_library_router.post("/from-library", response_model=list[SourceAssetOut])
def attach_from_library(
    project_id: int,
    body: AttachLibraryRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Copia itens da biblioteca para o projeto e dispara a análise."""
    import shutil

    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado")

    settings = get_settings()
    storage = get_object_storage()
    uploads_dir = settings.project_dir(project.id) / "sources" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    created: list[SourceAsset] = []
    for lib_id in body.library_ids:
        lib = db.get(LibraryAsset, lib_id)
        if lib is None or lib.user_id != user.id:
            raise HTTPException(404, f"Item {lib_id} não encontrado na biblioteca")

        src_file = settings.storage_dir / lib.path
        if not src_file.is_file():
            # Tenta baixar do MinIO se só estiver remoto
            storage.ensure_local(lib.path)
            src_file = settings.storage_dir / lib.path
        if not src_file.is_file():
            raise HTTPException(404, f"Arquivo da biblioteca ausente: {lib.filename}")

        source = SourceAsset(
            project_id=project.id,
            kind=lib.kind,
            filename=lib.filename,
            path="",
            status=SourceStatus.uploaded,
            duration=lib.duration,
            width=lib.width,
            height=lib.height,
        )
        db.add(source)
        db.flush()

        dest = uploads_dir / f"{source.id}_{lib.filename}"
        shutil.copy2(src_file, dest)
        source.path = str(dest.relative_to(settings.storage_dir))
        created.append(source)

    db.commit()

    for source in created:
        storage.put_file(settings.storage_dir / source.path, source.path)

    from app.api.sources import _analysis_task

    for source in created:
        background.add_task(_analysis_task(project), source.id)
    return created
