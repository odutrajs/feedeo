"""Pipeline worker: polls the pipeline_jobs table and executes queued runs.

Usage: python worker.py
"""

import time

from app.core.logging import get_logger, setup_logging
from app.db.base import db_session, init_db
from app.db.models import PipelineJob, Project
from app.pipeline.orchestrator import run_pipeline

POLL_INTERVAL_SECONDS = 2.0

logger = get_logger("worker")


def claim_next_job() -> int | None:
    """Atomically claim the oldest queued job. Returns the job id or None."""
    with db_session() as db:
        job = (
            db.query(PipelineJob)
            .filter(PipelineJob.status == "queued")
            .order_by(PipelineJob.created_at.asc())
            .first()
        )
        if job is None:
            return None
        job.status = "running"
        return job.id


def process_job(job_id: int) -> None:
    with db_session() as db:
        job = db.get(PipelineJob, job_id)
        project = db.get(Project, job.project_id)
        logger.info("processing job=%s project=%s from_stage=%s", job.id, project.id, job.from_stage)
        try:
            run_pipeline(db, project, from_stage=job.from_stage)
            job.status = "done"
        except Exception:
            logger.exception("job=%s crashed", job_id)
            job.status = "failed"
        db.commit()


def main() -> None:
    setup_logging()
    init_db()
    logger.info("worker started, polling every %.1fs", POLL_INTERVAL_SECONDS)
    while True:
        job_id = claim_next_job()
        if job_id is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        process_job(job_id)


if __name__ == "__main__":
    main()
