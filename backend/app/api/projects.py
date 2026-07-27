from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import (
    EditCutUpdate,
    EditStyleOut,
    EditTransitionOut,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    RegenerateImageRequest,
    RunRequest,
    SceneUpdate,
    StageRunOut,
)
from app.db.base import get_db
from app.db.models import (
    EditCut,
    Project,
    ProjectMode,
    ProjectStatus,
    Scene,
    StageRun,
    StageStatus,
    User,
)
from app.pipeline.orchestrator import enqueue_pipeline, latest_stage_run, stage_order_for

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_or_404(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "Projeto não encontrado")
    return project


@router.post("", response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    try:
        mode = ProjectMode(body.mode)
    except ValueError:
        raise HTTPException(400, f"Modo desconhecido: {body.mode}")
    config = dict(body.config or {})
    if mode == ProjectMode.edit and "review_stages" not in config:
        # Pausa após a análise para o usuário revisar os cortes antes do render
        config["review_stages"] = ["edit_analysis"]
    if mode == ProjectMode.join:
        config.setdefault("transition", "fade")
        config.setdefault("aspect", "9:16")
        config.pop("review_stages", None)
    workspace_id = None
    if body.workspace_id is not None:
        from app.db.models import Workspace

        workspace = db.get(Workspace, body.workspace_id)
        if workspace is None or workspace.user_id != user.id:
            raise HTTPException(404, f"Projeto (workspace) {body.workspace_id} não encontrado")
        workspace_id = body.workspace_id
    project = Project(
        user_id=user.id,
        workspace_id=workspace_id,
        topic=body.topic,
        title=body.title,
        mode=mode,
        language=body.language,
        config=config,
    )
    db.add(project)
    db.commit()
    # Projetos de criativo/edição esperam upload de mídia antes de rodar
    if body.autostart and mode == ProjectMode.generative:
        enqueue_pipeline(db, project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(get_subscribed_user)
):
    return (
        db.query(Project)
        .filter(Project.user_id == user.id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.get("/edit-styles", response_model=list[EditStyleOut])
def list_edit_styles():
    """Presets de estilo disponíveis para o modo de edição automática.

    Registrado antes de /{project_id} para não colidir com a rota dinâmica.
    """
    from app.modules.editing.styles import EDIT_STYLES

    return [
        EditStyleOut(id=s.id, label=s.label, description=s.description)
        for s in EDIT_STYLES.values()
    ]


@router.get("/edit-transitions", response_model=list[EditTransitionOut])
def list_edit_transitions():
    """Transições disponíveis para o modo edit, com prévia em vídeo de cada uma.

    As prévias são geradas na primeira chamada e cacheadas em storage/transitions.
    Registrado antes de /{project_id} para não colidir com a rota dinâmica.
    """
    from app.modules.editing.transitions import TRANSITIONS, ensure_previews, preview_relpath

    ensure_previews()
    return [
        EditTransitionOut(
            id=t.id,
            label=t.label,
            description=t.description,
            preview_path=preview_relpath(t.id),
        )
        for t in TRANSITIONS
    ]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    return get_project_or_404(db, project_id, user)


@router.get("/{project_id}/stages", response_model=list[StageRunOut])
def get_stage_status(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Latest run of each stage, in pipeline order (for the progress UI)."""
    project = get_project_or_404(db, project_id, user)
    result = []
    for name in stage_order_for(project.mode):
        run = latest_stage_run(db, project_id, name)
        if run:
            result.append(run)
    return result


@router.post("/{project_id}/run", response_model=ProjectOut)
def run_project(
    project_id: int,
    body: RunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    project = get_project_or_404(db, project_id, user)
    if body.from_stage and body.from_stage not in stage_order_for(project.mode):
        raise HTTPException(400, f"Etapa desconhecida: {body.from_stage}")
    if project.mode == ProjectMode.join:
        from app.db.models import SourceAsset, SourceStatus

        videos = (
            db.query(SourceAsset)
            .filter(
                SourceAsset.project_id == project.id,
                SourceAsset.kind == "video",
                SourceAsset.status != SourceStatus.failed,
            )
            .count()
        )
        if videos < 2:
            raise HTTPException(
                400, "Envie pelo menos 2 vídeos para juntar com transição"
            )
    enqueue_pipeline(db, project, from_stage=body.from_stage)
    return project


@router.post("/{project_id}/approve", response_model=ProjectOut)
def approve_stage(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Approve the stage currently awaiting review and resume the pipeline."""
    project = get_project_or_404(db, project_id, user)
    run = (
        db.query(StageRun)
        .filter(StageRun.project_id == project_id, StageRun.status == StageStatus.awaiting_review)
        .order_by(StageRun.started_at.desc())
        .first()
    )
    if run is None:
        raise HTTPException(400, "Nenhuma etapa aguardando revisão")
    run.status = StageStatus.done
    db.commit()
    order = stage_order_for(project.mode)
    next_index = order.index(run.stage) + 1
    if next_index < len(order):
        enqueue_pipeline(db, project, from_stage=order[next_index])
    else:
        project.status = ProjectStatus.completed
        db.commit()
    return project


@router.post("/{project_id}/reject", response_model=ProjectOut)
def reject_stage(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Reject the stage awaiting review: re-run it from scratch."""
    project = get_project_or_404(db, project_id, user)
    run = (
        db.query(StageRun)
        .filter(StageRun.project_id == project_id, StageRun.status == StageStatus.awaiting_review)
        .order_by(StageRun.started_at.desc())
        .first()
    )
    if run is None:
        raise HTTPException(400, "Nenhuma etapa aguardando revisão")
    run.status = StageStatus.failed
    run.error = "Rejeitada pelo usuário"
    db.commit()
    enqueue_pipeline(db, project, from_stage=run.stage)
    return project


@router.patch("/{project_id}/scenes/{scene_id}")
def update_scene(
    project_id: int,
    scene_id: int,
    body: SceneUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    get_project_or_404(db, project_id, user)
    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        raise HTTPException(404, "Cena não encontrada")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(scene, field, value)
    db.commit()
    return {"ok": True}


@router.post("/{project_id}/scenes/{scene_id}/regenerate-image")
def regenerate_image(
    project_id: int,
    scene_id: int,
    body: RegenerateImageRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Regenerate the image of a single scene (runs in background)."""
    get_project_or_404(db, project_id, user)
    scene = db.get(Scene, scene_id)
    if scene is None or scene.project_id != project_id:
        raise HTTPException(404, "Cena não encontrada")
    if body.prompt_override:
        scene.image_prompt = body.prompt_override
        db.commit()

    from app.modules.images.service import regenerate_scene_image

    background.add_task(regenerate_scene_image, project_id, scene_id)
    return {"ok": True, "message": "Regeneração iniciada"}


# ── Modo edit: revisão dos cortes ─────────────────────────────────────────


@router.patch("/{project_id}/edit-cuts/{cut_id}")
def update_edit_cut(
    project_id: int,
    cut_id: int,
    body: EditCutUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Inverte a decisão de um trecho (manter/cortar) antes do render."""
    get_project_or_404(db, project_id, user)
    cut = db.get(EditCut, cut_id)
    if cut is None or cut.project_id != project_id:
        raise HTTPException(404, "Trecho não encontrado")
    if body.action not in ("keep", "cut"):
        raise HTTPException(400, "Ação deve ser 'keep' ou 'cut'")
    cut.action = body.action
    cut.meta = {**(cut.meta or {}), "manual": True}
    db.commit()
    return {"ok": True}
