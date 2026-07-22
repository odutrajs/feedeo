from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.models import Asset, AssetKind, Project, Scene, StageRun


class StageContext:
    """Everything a stage needs to do its work: db session, project, storage paths and logging."""

    def __init__(self, db: Session, project: Project, stage_run: StageRun):
        self.db = db
        self.project = project
        self.stage_run = stage_run
        self.settings: Settings = get_settings()
        self._logger = get_logger(f"stage.{stage_run.stage}")

    # --- logging (console + persisted on the StageRun row) -------------------

    def log(self, message: str) -> None:
        self._logger.info("[project=%s] %s", self.project.id, message)
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.stage_run.log = (self.stage_run.log or "") + f"[{timestamp}] {message}\n"
        self.db.commit()

    def set_status(self, message: str) -> None:
        """Update the human-friendly live status shown in the UI."""
        self.stage_run.status_message = message
        self.db.commit()

    # --- storage helpers ------------------------------------------------------

    @property
    def project_dir(self) -> Path:
        path = self.settings.project_dir(self.project.id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def subdir(self, name: str) -> Path:
        path = self.project_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relpath(self, path: Path) -> str:
        return str(path.relative_to(self.settings.storage_dir))

    def abspath(self, rel: str) -> Path:
        return self.settings.storage_dir / rel

    # --- asset helpers ----------------------------------------------------------

    def next_version(self, kind: AssetKind, scene_id: int | None = None) -> int:
        current = (
            self.db.query(Asset)
            .filter(
                Asset.project_id == self.project.id,
                Asset.kind == kind,
                Asset.scene_id == scene_id,
            )
            .count()
        )
        return current + 1

    def save_asset(
        self,
        kind: AssetKind,
        path: Path,
        scene: Scene | None = None,
        meta: dict | None = None,
    ) -> Asset:
        """Register a file as the current asset of its kind, versioning previous ones."""
        scene_id = scene.id if scene else None
        previous = (
            self.db.query(Asset)
            .filter(
                Asset.project_id == self.project.id,
                Asset.kind == kind,
                Asset.scene_id == scene_id,
                Asset.is_current.is_(True),
            )
            .all()
        )
        for old in previous:
            old.is_current = False
        asset = Asset(
            project_id=self.project.id,
            scene_id=scene_id,
            kind=kind,
            version=self.next_version(kind, scene_id),
            is_current=True,
            path=self.relpath(path),
            meta=meta or {},
        )
        self.db.add(asset)
        self.db.commit()
        return asset

    def current_asset(self, kind: AssetKind, scene_id: int | None = None) -> Asset | None:
        return (
            self.db.query(Asset)
            .filter(
                Asset.project_id == self.project.id,
                Asset.kind == kind,
                Asset.scene_id == scene_id,
                Asset.is_current.is_(True),
            )
            .one_or_none()
        )


class Stage(ABC):
    """A pipeline step. Implementations must be idempotent: re-running replaces outputs."""

    name: str = "stage"
    label: str = "Stage"

    @abstractmethod
    def run(self, ctx: StageContext) -> None: ...
