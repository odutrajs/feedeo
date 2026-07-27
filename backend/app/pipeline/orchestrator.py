"""Pipeline orchestrator: runs stages in order as a state machine.

Stage order (see plan):
    script -> voice -> audio_sync -> visual_plan -> images -> captions -> render -> publish_meta

Each stage is idempotent. A project config may define `review_stages`
(list of stage names); after one of those stages finishes, the pipeline
pauses with status `awaiting_review` until the user approves it.
"""

import traceback
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import PipelineJob, Project, ProjectMode, ProjectStatus, StageRun, StageStatus
from app.pipeline.stage import Stage, StageContext

logger = get_logger("pipeline")


def build_stages(mode: ProjectMode = ProjectMode.generative) -> list[Stage]:
    # Imported lazily so heavy deps (whisper, ffmpeg helpers) only load in the worker.
    from app.modules.audio_sync.stage import AudioSyncStage
    from app.modules.captions.stage import CaptionsStage
    from app.modules.images.stage import ImagesStage
    from app.modules.publishing.stage import PublishMetaStage
    from app.modules.script.creative_stage import CreativeScriptStage
    from app.modules.script.stage import ScriptStage
    from app.modules.video.stage import RenderStage
    from app.modules.visual_plan.stage import VisualPlanStage
    from app.modules.visual_select.stage import VisualSelectStage
    from app.modules.voice.stage import VoiceStage

    if mode == ProjectMode.edit:
        from app.modules.editing.stage import EditAnalysisStage, EditRenderStage

        # Edição mágica: vídeo bruto -> análise de cortes -> render
        return [
            EditAnalysisStage(),
            EditRenderStage(),
        ]
    if mode == ProjectMode.join:
        from app.modules.editing.stage import JoinRenderStage

        # Juntar vídeos: N partes prontas -> normaliza + transição -> export
        return [JoinRenderStage()]
    if mode == ProjectMode.creative:
        # Criativo: copy de anúncio + seleção dos melhores trechos enviados
        return [
            CreativeScriptStage(),
            VoiceStage(),
            AudioSyncStage(),
            VisualSelectStage(),
            ImagesStage(),
            CaptionsStage(),
            RenderStage(),
            PublishMetaStage(),
        ]
    return [
        ScriptStage(),
        VoiceStage(),
        AudioSyncStage(),
        VisualPlanStage(),
        ImagesStage(),
        CaptionsStage(),
        RenderStage(),
        PublishMetaStage(),
    ]


STAGE_ORDER = [
    "script",
    "voice",
    "audio_sync",
    "visual_plan",
    "images",
    "captions",
    "render",
    "publish_meta",
]

EDIT_STAGE_ORDER = ["edit_analysis", "edit_render"]
JOIN_STAGE_ORDER = ["join_render"]


def stage_order_for(mode: ProjectMode) -> list[str]:
    if mode == ProjectMode.edit:
        return EDIT_STAGE_ORDER
    if mode == ProjectMode.join:
        return JOIN_STAGE_ORDER
    return STAGE_ORDER


def latest_stage_run(db: Session, project_id: int, stage: str) -> StageRun | None:
    return (
        db.query(StageRun)
        .filter(StageRun.project_id == project_id, StageRun.stage == stage)
        .order_by(StageRun.attempt.desc())
        .first()
    )


def run_pipeline(db: Session, project: Project, from_stage: str | None = None) -> None:
    """Run the pipeline for a project, starting at `from_stage` (or resuming automatically)."""
    stages = build_stages(project.mode)
    names = [s.name for s in stages]

    if from_stage is not None:
        if from_stage not in names:
            raise ValueError(f"Unknown stage: {from_stage}")
        start_index = names.index(from_stage)
    else:
        # Resume: first stage whose latest run is not done/skipped
        start_index = 0
        for i, name in enumerate(names):
            run = latest_stage_run(db, project.id, name)
            if run is None or run.status not in (StageStatus.done, StageStatus.skipped):
                start_index = i
                break
        else:
            start_index = len(names)

    project.status = ProjectStatus.running
    project.error = None
    db.commit()

    review_stages = set((project.config or {}).get("review_stages", []))

    for stage in stages[start_index:]:
        db.refresh(project)

        previous = latest_stage_run(db, project.id, stage.name)
        attempt = (previous.attempt + 1) if previous else 1
        stage_run = StageRun(
            project_id=project.id,
            stage=stage.name,
            status=StageStatus.running,
            attempt=attempt,
            started_at=datetime.now(timezone.utc),
        )
        db.add(stage_run)
        db.commit()

        ctx = StageContext(db, project, stage_run)
        logger.info("project=%s stage=%s attempt=%s starting", project.id, stage.name, attempt)
        try:
            stage.run(ctx)
        except Exception as exc:
            db.rollback()
            stage_run.status = StageStatus.failed
            stage_run.error = f"{exc}\n{traceback.format_exc()}"
            stage_run.finished_at = datetime.now(timezone.utc)
            project.status = ProjectStatus.failed
            project.error = f"Falha na etapa '{stage.name}': {exc}"
            db.commit()
            logger.exception("project=%s stage=%s failed", project.id, stage.name)
            return

        stage_run.finished_at = datetime.now(timezone.utc)

        if stage.name in review_stages:
            stage_run.status = StageStatus.awaiting_review
            project.status = ProjectStatus.awaiting_review
            db.commit()
            logger.info("project=%s stage=%s awaiting review", project.id, stage.name)
            return

        stage_run.status = StageStatus.done
        db.commit()

    project.status = ProjectStatus.completed
    db.commit()
    logger.info("project=%s pipeline completed", project.id)


def enqueue_pipeline(db: Session, project: Project, from_stage: str | None = None) -> PipelineJob:
    """Queue a pipeline run for the worker, cancelling stale queued jobs for the project."""
    (
        db.query(PipelineJob)
        .filter(PipelineJob.project_id == project.id, PipelineJob.status == "queued")
        .update({PipelineJob.status: "cancelled"})
    )
    job = PipelineJob(project_id=project.id, from_stage=from_stage, status="queued")
    project.status = ProjectStatus.queued
    db.add(job)
    db.commit()
    return job
