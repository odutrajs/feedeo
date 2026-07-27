import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    awaiting_review = "awaiting_review"
    completed = "completed"
    failed = "failed"


class ProjectMode(str, enum.Enum):
    generative = "generative"  # topic -> AI script -> AI images (fluxo original)
    creative = "creative"  # brief + mídia enviada -> anúncio (criativo)
    edit = "edit"  # vídeo bruto -> cortes/transições automáticos (edição mágica)
    join = "join"  # N vídeos prontos -> concat com transição (juntar vídeos)


class SourceStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class StageStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    awaiting_review = "awaiting_review"
    skipped = "skipped"


class AssetKind(str, enum.Enum):
    script = "script"
    audio = "audio"
    timeline = "timeline"
    style_guide = "style_guide"
    image = "image"
    captions = "captions"
    video = "video"
    publish_meta = "publish_meta"
    transcript = "transcript"  # transcrição bruta (modo edit)


class SubscriptionStatus(str, enum.Enum):
    none = "none"  # nunca assinou
    active = "active"  # assinatura em dia
    past_due = "past_due"  # pagamento falhou, em retry
    canceled = "canceled"  # cancelada / expirada


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    # Assinatura recorrente (Stripe)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(20), default="none")
    plan: Mapped[str | None] = mapped_column(String(40), nullable=True)  # creator | pro | studio
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    projects: Mapped[list["Project"]] = relationship(back_populates="user")
    library_assets: Mapped[list["LibraryAsset"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Workspace(Base):
    """Projeto do usuário (marca/campanha): agrupa vídeos e posts gerados e guarda
    a descrição/contexto usado como referência em todas as gerações."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    # Contexto completo: produto/marca, público-alvo, tom de voz, objetivos,
    # diferenciais, ofertas... — injetado nos prompts de vídeo e de posts.
    description: Mapped[str] = mapped_column(Text, default="")
    # Logo da marca (PNG/JPG) usada nas artes de posts/carrosséis.
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Identidade visual estruturada: primary_color, secondary_color (hex),
    # text_theme (dark|light) e visual_style (texto livre de direção de arte).
    brand: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="workspaces")
    projects: Mapped[list["Project"]] = relationship(back_populates="workspace")
    posts: Mapped[list["SocialPost"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class SocialPost(Base):
    """Post estático ou carrossel gerado a partir do contexto de um workspace."""

    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="static")  # static / carousel
    brief: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", index=True
    )  # queued / running / completed / failed
    caption: Mapped[str] = mapped_column(Text, default="")  # legenda do post
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workspace: Mapped[Workspace] = relationship(back_populates="posts")
    slides: Mapped[list["SocialSlide"]] = relationship(
        back_populates="post", order_by="SocialSlide.index", cascade="all, delete-orphan"
    )


class SocialSlide(Base):
    __tablename__ = "social_slides"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("social_posts.id"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    headline: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # fundo bruto
    composed_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # arte final
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    post: Mapped[SocialPost] = relationship(back_populates="slides")


class LibraryAsset(Base):
    """Mídia reutilizável do usuário (biblioteca) — independente de projeto."""

    __tablename__ = "library_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # video / image
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(500))  # relative to storage dir
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="library_assets")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    topic: Mapped[str] = mapped_column(Text)
    mode: Mapped[ProjectMode] = mapped_column(
        Enum(ProjectMode), default=ProjectMode.generative, index=True
    )
    language: Mapped[str] = mapped_column(String(10), default="pt-BR")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.draft, index=True
    )
    # Per-project settings: voice_id, style_preset, review_stages, target_duration...
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped[User] = relationship(back_populates="projects")
    workspace: Mapped[Workspace | None] = relationship(back_populates="projects")
    scenes: Mapped[list["Scene"]] = relationship(
        back_populates="project", order_by="Scene.index", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    stage_runs: Mapped[list["StageRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sources: Mapped[list["SourceAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    edit_cuts: Mapped[list["EditCut"]] = relationship(
        order_by="EditCut.start", cascade="all, delete-orphan"
    )


class SourceAsset(Base):
    """Mídia enviada pelo usuário (vídeo ou imagem) usada como matéria-prima do criativo."""

    __tablename__ = "source_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # video / image
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(500))  # relative to storage dir
    status: Mapped[SourceStatus] = mapped_column(Enum(SourceStatus), default=SourceStatus.uploaded)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="sources")
    segments: Mapped[list["SourceSegment"]] = relationship(
        back_populates="source", order_by="SourceSegment.start", cascade="all, delete-orphan"
    )


class SourceSegment(Base):
    """Trecho de um vídeo enviado, detectado por corte de cena e avaliado pela IA."""

    __tablename__ = "source_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_assets.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")  # descrição visual gerada por IA
    tags: Mapped[list] = mapped_column(JSON, default=list)  # ex.: ["product_closeup", "talking_head"]
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-10 qualidade p/ criativo
    score_reason: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # usuário pode excluir da seleção
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[SourceAsset] = relationship(back_populates="segments")

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


class EditCut(Base):
    """Modo edit: uma decisão de edição sobre um trecho do vídeo bruto (EDL).

    O vídeo inteiro é particionado em trechos consecutivos; cada um recebe
    action=keep|cut e um motivo. O usuário pode inverter decisões antes do render.
    """

    __tablename__ = "edit_cuts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("source_assets.id"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    action: Mapped[str] = mapped_column(String(10), default="keep")  # keep / cut
    # voice_command / retake / silence / filler / speech / manual
    reason: Mapped[str] = mapped_column(String(30), default="speech")
    transcript: Mapped[str] = mapped_column(Text, default="")
    detail: Mapped[str] = mapped_column(Text, default="")  # explicação legível da decisão
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[SourceAsset] = relationship()

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(40), default="development")  # hook/intro/development/conclusion/cta
    narration_text: Mapped[str] = mapped_column(Text)
    visual_description: Mapped[str] = mapped_column(Text, default="")
    estimated_duration: Mapped[float] = mapped_column(Float, default=0.0)
    # Filled by audio_sync (seconds, relative to full narration)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Filled by visual_plan
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    motion: Mapped[str | None] = mapped_column(String(40), nullable=True)  # zoom_in/zoom_out/pan_left/pan_right
    # Creative mode: which visual fills this scene
    visual_source: Mapped[str] = mapped_column(String(20), default="ai_image")  # ai_image / segment / source_image
    source_segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_segments.id"), nullable=True
    )
    source_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_assets.id"), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="scenes")
    assets: Mapped[list["Asset"]] = relationship(back_populates="scene")
    source_segment: Mapped[SourceSegment | None] = relationship()
    source_asset: Mapped[SourceAsset | None] = relationship()


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    scene_id: Mapped[int | None] = mapped_column(ForeignKey("scenes.id"), nullable=True, index=True)
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    path: Mapped[str] = mapped_column(String(500))  # relative to storage dir
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="assets")
    scene: Mapped[Scene | None] = relationship(back_populates="assets")


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    stage: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[StageStatus] = mapped_column(Enum(StageStatus), default=StageStatus.pending)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    status_message: Mapped[str] = mapped_column(String(300), default="")

    project: Mapped[Project] = relationship(back_populates="stage_runs")


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued/running/done/failed/cancelled
    # Optional: run only from this stage onward (used for reruns)
    from_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


# --- Módulo 9 (esqueleto): publicação automática -----------------------------


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    platform: Mapped[str] = mapped_column(String(40))  # youtube/tiktok/instagram...
    name: Mapped[str] = mapped_column(String(120))
    credentials: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    social_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("social_posts.id"), nullable=True, index=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled/uploading/published/failed
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublishLog(Base):
    __tablename__ = "publish_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    publication_id: Mapped[int] = mapped_column(ForeignKey("publications.id"), index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
