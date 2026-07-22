"""Persistência e metadados de itens da biblioteca de mídia."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.object_storage import get_object_storage
from app.db.models import LibraryAsset
from app.modules.sources.media import extract_thumbnail, make_image_thumbnail, probe_media

logger = get_logger("library")


def save_to_library(
    db: Session,
    *,
    user_id: int,
    source_path: Path,
    filename: str,
    kind: str,
) -> LibraryAsset:
    """Copia um arquivo já salvo no disco para a biblioteca do usuário."""
    settings = get_settings()
    asset = LibraryAsset(
        user_id=user_id,
        kind=kind,
        filename=filename,
        path="",
        thumbnail_path=None,
    )
    db.add(asset)
    db.flush()

    dest_dir = settings.user_library_dir(user_id) / str(asset.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    shutil.copy2(source_path, dest)
    asset.path = str(dest.relative_to(settings.storage_dir))

    try:
        info = probe_media(dest)
        asset.duration = info.duration if kind == "video" else None
        asset.width = info.width or None
        asset.height = info.height or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("probe da biblioteca falhou (%s): %s", filename, exc)

    thumb = dest_dir / "thumb.jpg"
    try:
        if kind == "video":
            at = min(1.0, (asset.duration or 2.0) * 0.1)
            extract_thumbnail(dest, at, thumb)
        else:
            make_image_thumbnail(dest, thumb)
        asset.thumbnail_path = str(thumb.relative_to(settings.storage_dir))
    except Exception as exc:  # noqa: BLE001
        logger.warning("thumbnail da biblioteca falhou (%s): %s", filename, exc)
        asset.thumbnail_path = None

    storage = get_object_storage()
    storage.put_file(dest, asset.path)
    if asset.thumbnail_path and thumb.is_file():
        storage.put_file(thumb, asset.thumbnail_path)

    db.commit()
    db.refresh(asset)
    return asset


def delete_library_files(asset: LibraryAsset) -> None:
    settings = get_settings()
    storage = get_object_storage()
    if asset.path:
        (settings.storage_dir / asset.path).unlink(missing_ok=True)
        storage.delete_prefix(asset.path)
    if asset.thumbnail_path:
        (settings.storage_dir / asset.thumbnail_path).unlink(missing_ok=True)
        storage.delete_prefix(asset.thumbnail_path)
    asset_dir = settings.user_library_dir(asset.user_id) / str(asset.id)
    shutil.rmtree(asset_dir, ignore_errors=True)
    storage.delete_prefix(f"library/{asset.user_id}/{asset.id}/")
