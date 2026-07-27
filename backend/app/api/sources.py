"""Upload e gestão de mídia-fonte (vídeos/imagens do usuário) para criativos."""

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import SegmentUpdate, SourceAssetOut, SourceSegmentOut
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.object_storage import get_object_storage
from app.db.base import get_db
from app.db.models import Project, SourceAsset, SourceSegment, SourceStatus, User
from app.modules.library.service import save_to_library

logger = get_logger("sources.api")

router = APIRouter(prefix="/api/projects/{project_id}/sources", tags=["sources"])

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB por arquivo


def _get_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado")
    return project


def _safe_filename(name: str) -> str:
    name = Path(name).name
    return re.sub(r"[^\w.\-]+", "_", name) or "arquivo"


@router.post("", response_model=list[SourceAssetOut])
async def upload_sources(
    project_id: int,
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Recebe vários vídeos/imagens, salva, espelha na biblioteca e dispara a análise."""
    project = _get_project(db, project_id, user)
    settings = get_settings()
    uploads_dir = settings.project_dir(project.id) / "sources" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    video_only = project.mode.value in ("edit", "join")
    created: list[SourceAsset] = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            kind = "video"
        elif ext in IMAGE_EXTENSIONS and not video_only:
            kind = "image"
        elif ext in IMAGE_EXTENSIONS and video_only:
            raise HTTPException(400, "Este modo aceita apenas vídeos")
        else:
            raise HTTPException(400, f"Formato não suportado: {upload.filename}")

        filename = _safe_filename(upload.filename or f"upload{ext}")
        source = SourceAsset(
            project_id=project.id,
            kind=kind,
            filename=filename,
            path="",  # definido após sabermos o id
            status=SourceStatus.uploaded,
        )
        db.add(source)
        db.flush()

        dest = uploads_dir / f"{source.id}_{filename}"
        with dest.open("wb") as out:
            while chunk := await upload.read(1024 * 1024):
                out.write(chunk)
                if out.tell() > MAX_UPLOAD_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    db.rollback()
                    raise HTTPException(413, f"Arquivo muito grande: {filename}")
        source.path = str(dest.relative_to(settings.storage_dir))
        created.append(source)

    db.commit()

    # Espelha os uploads no MinIO (fonte durável dos vídeos)
    storage = get_object_storage()
    for source in created:
        storage.put_file(settings.storage_dir / source.path, source.path)

    # Salva cópia na biblioteca do usuário para reuso em outros projetos
    for source in created:
        try:
            save_to_library(
                db,
                user_id=user.id,
                source_path=settings.storage_dir / source.path,
                filename=source.filename,
                kind=source.kind,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "falha ao salvar na biblioteca (source=%s): %s", source.id, exc
            )

    for source in created:
        background.add_task(_analysis_task(project), source.id)
    return created


def _analysis_task(project: Project):
    """Modos edit/join não precisam da análise de visão/segmentos: só probe de metadados."""
    if project.mode.value in ("edit", "join"):
        from app.modules.editing.analysis import probe_source

        return probe_source
    from app.modules.sources.analysis import analyze_source

    return analyze_source


@router.get("", response_model=list[SourceAssetOut])
def list_sources(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    _get_project(db, project_id, user)
    return (
        db.query(SourceAsset)
        .filter(SourceAsset.project_id == project_id)
        .order_by(SourceAsset.created_at.asc())
        .all()
    )


@router.delete("/{source_id}")
def delete_source(
    project_id: int,
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    _get_project(db, project_id, user)
    source = db.get(SourceAsset, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(404, "Fonte não encontrada")
    settings = get_settings()
    # Remove arquivos (upload + thumbs/previews) do disco e do MinIO
    storage = get_object_storage()
    if source.path:
        (settings.storage_dir / source.path).unlink(missing_ok=True)
        storage.delete_prefix(source.path)
    derived_dir = settings.project_dir(project_id) / "sources" / str(source.id)
    shutil.rmtree(derived_dir, ignore_errors=True)
    storage.delete_prefix(f"projects/{project_id}/sources/{source.id}/")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.post("/{source_id}/reanalyze", response_model=SourceAssetOut)
def reanalyze_source(
    project_id: int,
    source_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    project = _get_project(db, project_id, user)
    source = db.get(SourceAsset, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(404, "Fonte não encontrada")
    source.status = SourceStatus.processing
    db.commit()

    background.add_task(_analysis_task(project), source.id)
    return source


@router.patch("/segments/{segment_id}", response_model=SourceSegmentOut)
def update_segment(
    project_id: int,
    segment_id: int,
    body: SegmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    _get_project(db, project_id, user)
    segment = db.get(SourceSegment, segment_id)
    if segment is None or segment.project_id != project_id:
        raise HTTPException(404, "Segmento não encontrado")
    if body.enabled is not None:
        segment.enabled = body.enabled
    db.commit()
    return segment
