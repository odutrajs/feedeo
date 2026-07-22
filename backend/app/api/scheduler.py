"""Endpoints internos chamados pelo serviço de agendamento (Go scheduler).

Estes endpoints NÃO são chamados pelo frontend diretamente — apenas pelo scheduler.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, field_serializer
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import publish_schedule_event
from app.db.base import get_db
from app.db.models import (
    PlatformAccount,
    Publication,
    SocialPost,
    User,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = get_logger("scheduler")
settings = get_settings()


def _check_internal(x_scheduler_secret: str = Header(default="")):
    """Valida que a requisição vem do scheduler (secret compartilhado)."""
    if x_scheduler_secret != "internal":
        raise HTTPException(403, "Acesso negado")


# ── Execute: scheduler chama quando chega o horário ──────────────────


class ExecuteRequest(BaseModel):
    publication_id: int


class ExecuteResponse(BaseModel):
    success: bool
    external_id: str | None = None
    error: str | None = None


@router.post("/execute", response_model=ExecuteResponse, dependencies=[Depends(_check_internal)])
def execute_publication(
    body: ExecuteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Executa a publicação de um item agendado. Chamado pelo scheduler Go."""
    pub = db.get(Publication, body.publication_id)
    if not pub:
        return ExecuteResponse(success=False, error="Publicação não encontrada")

    if pub.status == "published":
        return ExecuteResponse(success=True, external_id=pub.external_id)

    # Determina se é vídeo (project) ou post social
    if pub.project_id:
        from app.api.publishing import _do_publish_instagram

        pub.status = "uploading"
        db.commit()
        background_tasks.add_task(_do_publish_instagram, pub.id)
        return ExecuteResponse(success=True)

    elif pub.social_post_id:
        from app.api.publishing import _do_publish_social_post

        pub.status = "uploading"
        db.commit()
        background_tasks.add_task(_do_publish_social_post, pub.id)
        return ExecuteResponse(success=True)

    return ExecuteResponse(success=False, error="Publicação sem project_id ou social_post_id")


# ── Pending: scheduler faz sync periódico ────────────────────────────


class PendingJobOut(BaseModel):
    id: str
    publication_id: int
    project_id: int | None = None
    social_post_id: int | None = None
    account_id: int
    platform: str
    scheduled_at: datetime
    status: str
    created_at: datetime

    @field_serializer("scheduled_at", "created_at")
    def serialize_dt(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/pending", response_model=list[PendingJobOut], dependencies=[Depends(_check_internal)])
def list_pending(db: Session = Depends(get_db)):
    """Retorna publicações agendadas pendentes para o scheduler sincronizar."""
    pubs = (
        db.query(Publication)
        .filter(
            Publication.status == "scheduled",
            Publication.scheduled_at.isnot(None),
        )
        .order_by(Publication.scheduled_at.asc())
        .all()
    )

    jobs = []
    for pub in pubs:
        account = db.get(PlatformAccount, pub.account_id)
        jobs.append(
            PendingJobOut(
                id=f"pub_{pub.id}_{int(pub.created_at.timestamp())}",
                publication_id=pub.id,
                project_id=pub.project_id,
                social_post_id=pub.social_post_id,
                account_id=pub.account_id,
                platform=account.platform if account else "unknown",
                scheduled_at=pub.scheduled_at,
                status="pending",
                created_at=pub.created_at,
            )
        )
    return jobs


# ── Schedule: frontend agenda uma publicação via backend ─────────────


class ScheduleRequest(BaseModel):
    project_id: int | None = None
    social_post_id: int | None = None
    scheduled_at: datetime  # ISO 8601


class ScheduleResponse(BaseModel):
    publication_id: int
    job_id: str
    scheduled_at: datetime


@router.post("/schedule", response_model=ScheduleResponse)
def schedule_publication(
    body: ScheduleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Agenda uma publicação para um horário futuro.

    O frontend chama este endpoint; o backend cria o registro no banco,
    depois notifica o scheduler Go via Redis Pub/Sub.
    """
    if not body.project_id and not body.social_post_id:
        raise HTTPException(400, "Informe project_id ou social_post_id")

    if body.scheduled_at.tzinfo is None:
        body.scheduled_at = body.scheduled_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if body.scheduled_at <= now:
        raise HTTPException(400, "scheduled_at deve ser no futuro")

    # Valida conteúdo e encontra conta
    workspace_id = None
    if body.project_id:
        from app.db.models import Project

        project = db.get(Project, body.project_id)
        if not project or project.user_id != user.id:
            raise HTTPException(404, "Projeto não encontrado")
        workspace_id = project.workspace_id

    elif body.social_post_id:
        post = db.get(SocialPost, body.social_post_id)
        if not post:
            raise HTTPException(404, "Post não encontrado")
        workspace_id = post.workspace_id

    account = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.user_id == user.id,
            PlatformAccount.platform == "instagram",
            PlatformAccount.workspace_id == workspace_id,
            PlatformAccount.active == True,  # noqa: E712
        )
        .first()
    )
    if not account:
        raise HTTPException(400, "Nenhuma conta Instagram conectada ao workspace")

    # Cria publicação com status scheduled
    pub = Publication(
        project_id=body.project_id,
        social_post_id=body.social_post_id,
        account_id=account.id,
        status="scheduled",
        scheduled_at=body.scheduled_at,
    )
    db.add(pub)
    db.commit()
    db.refresh(pub)

    # Notifica o scheduler Go via Redis
    job_id = f"pub_{pub.id}_{int(pub.created_at.timestamp())}"
    try:
        publish_schedule_event(
            action="schedule",
            job={
                "id": job_id,
                "publication_id": pub.id,
                "project_id": body.project_id,
                "social_post_id": body.social_post_id,
                "account_id": account.id,
                "platform": account.platform,
                "scheduled_at": body.scheduled_at.isoformat(),
                "status": "pending",
                "created_at": pub.created_at.isoformat(),
            },
        )
    except Exception as exc:
        logger.warning("Falha ao notificar scheduler via Redis: %s", exc)
        # Não falha — o scheduler tem sync fallback

    return ScheduleResponse(
        publication_id=pub.id,
        job_id=job_id,
        scheduled_at=body.scheduled_at,
    )


# ── Cancel: cancela um agendamento ───────────────────────────────────


class CancelRequest(BaseModel):
    publication_id: int


@router.post("/cancel-schedule")
def cancel_schedule(
    body: CancelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Cancela uma publicação agendada."""
    pub = db.get(Publication, body.publication_id)
    if not pub:
        raise HTTPException(404, "Publicação não encontrada")

    account = db.get(PlatformAccount, pub.account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(404, "Publicação não encontrada")

    if pub.status != "scheduled":
        raise HTTPException(400, f"Não é possível cancelar publicação com status '{pub.status}'")

    pub.status = "cancelled"
    db.commit()

    # Notifica scheduler
    job_id = f"pub_{pub.id}_{int(pub.created_at.timestamp())}"
    try:
        publish_schedule_event(
            action="cancel",
            job={"id": job_id, "publication_id": pub.id},
        )
    except Exception as exc:
        logger.warning("Falha ao notificar scheduler do cancelamento: %s", exc)

    return {"ok": True, "publication_id": pub.id}
