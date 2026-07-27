from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ProjectCreate(BaseModel):
    topic: str = Field(min_length=3, description="Tema ou ideia do vídeo / brief do criativo")
    title: str | None = None
    mode: str = "generative"  # generative | creative | edit | join
    language: str = "pt-BR"
    config: dict = Field(default_factory=dict)
    autostart: bool = True
    workspace_id: int | None = None


class SceneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    index: int
    role: str
    narration_text: str
    visual_description: str
    estimated_duration: float
    start_time: float | None
    end_time: float | None
    image_prompt: str | None
    motion: str | None
    visual_source: str = "ai_image"
    source_segment_id: int | None = None
    source_asset_id: int | None = None


class SourceSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    index: int
    start: float
    end: float
    duration: float
    thumbnail_path: str | None
    preview_path: str | None
    transcript: str
    description: str
    tags: list
    score: float
    score_reason: str
    enabled: bool
    meta: dict


class SourceAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str
    path: str
    status: str
    duration: float | None
    width: int | None
    height: int | None
    error: str | None
    created_at: datetime
    segments: list[SourceSegmentOut] = []


class SegmentUpdate(BaseModel):
    enabled: bool | None = None


class EditCutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    index: int
    start: float
    end: float
    duration: float
    action: str
    reason: str
    transcript: str
    detail: str
    thumbnail_path: str | None
    preview_path: str | None
    meta: dict


class EditCutUpdate(BaseModel):
    action: str  # keep | cut


class EditStyleOut(BaseModel):
    id: str
    label: str
    description: str


class EditTransitionOut(BaseModel):
    id: str
    label: str
    description: str
    preview_path: str | None  # relativo a /media (None para "auto")


class LibraryAssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str
    path: str
    thumbnail_path: str | None
    duration: float | None
    width: int | None
    height: int | None
    created_at: datetime


class AttachLibraryRequest(BaseModel):
    library_ids: list[int] = Field(min_length=1)


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scene_id: int | None
    kind: str
    version: int
    is_current: bool
    path: str
    meta: dict
    created_at: datetime


class StageRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    status: str
    attempt: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    log: str
    status_message: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    topic: str
    mode: str = "generative"
    language: str
    status: str
    config: dict
    error: str | None
    workspace_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    scenes: list[SceneOut] = []
    stage_runs: list[StageRunOut] = []
    assets: list[AssetOut] = []
    sources: list[SourceAssetOut] = []
    edit_cuts: list[EditCutOut] = []


class SceneUpdate(BaseModel):
    narration_text: str | None = None
    visual_description: str | None = None
    image_prompt: str | None = None
    motion: str | None = None


class RunRequest(BaseModel):
    from_stage: str | None = None


class RegenerateImageRequest(BaseModel):
    prompt_override: str | None = None


# ── Workspaces (projetos do usuário) e posts sociais ─────────────────────


class BrandIdentity(BaseModel):
    primary_color: str = ""
    secondary_color: str = ""
    visual_style: str = ""
    text_theme: str = "dark"  # dark | light


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = ""


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    brand: BrandIdentity | None = None


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    logo_path: str | None = None
    brand: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    video_count: int = 0
    post_count: int = 0


class SocialSlideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    index: int
    headline: str
    body: str
    image_prompt: str
    image_path: str | None
    composed_path: str | None


class SocialPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    kind: str
    brief: str
    status: str
    caption: str
    hashtags: list
    error: str | None
    created_at: datetime
    slides: list[SocialSlideOut] = []


class SocialPostCreate(BaseModel):
    kind: str = "static"  # static | carousel
    brief: str = Field(min_length=3)
    language: str = "pt-BR"


class WorkspaceDetail(WorkspaceOut):
    projects: list[ProjectOut] = []
    posts: list[SocialPostOut] = []


class PlatformAccountCreate(BaseModel):
    platform: str
    name: str
    credentials: dict = Field(default_factory=dict)


class PlatformAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    name: str
    active: bool
    created_at: datetime


class PublicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int | None = None
    social_post_id: int | None = None
    account_id: int
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    external_id: str | None
    error: str | None

    @field_serializer("scheduled_at", "published_at")
    def serialize_dt(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ── Instagram Insights ───────────────────────────────────────────────


class MediaInsightsOut(BaseModel):
    """Métricas de uma publicação individual no Instagram."""
    media_id: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saved: int = 0
    reach: int = 0
    views: int = 0
    total_interactions: int = 0
    reposts: int = 0
    avg_watch_time_ms: int = 0
    video_view_total_time_ms: int = 0
    extra: dict = Field(default_factory=dict)


class MediaInfoOut(BaseModel):
    """Metadados básicos de uma mídia do Instagram."""
    id: str
    caption: str | None = None
    media_type: str | None = None
    media_product_type: str | None = None
    permalink: str | None = None
    thumbnail_url: str | None = None
    timestamp: str | None = None
    like_count: int | None = None
    comments_count: int | None = None


class PublicationInsightsOut(BaseModel):
    """Insights completos de uma publicação (metadados + métricas)."""
    publication_id: int
    external_id: str
    media_info: MediaInfoOut | None = None
    insights: MediaInsightsOut


class AccountInsightsOut(BaseModel):
    """Métricas agregadas do perfil do Instagram."""
    ig_user_id: str
    period: str = "day"
    reach: int = 0
    views: int = 0
    follower_count: int = 0
    extra: dict = Field(default_factory=dict)


class RecentMediaOut(BaseModel):
    """Mídia listada do perfil com métricas rápidas."""
    id: str
    caption: str | None = None
    media_type: str | None = None
    media_product_type: str | None = None
    permalink: str | None = None
    thumbnail_url: str | None = None
    media_url: str | None = None
    timestamp: str | None = None
    like_count: int | None = None
    comments_count: int | None = None
    insights: MediaInsightsOut | None = None


class WorkspaceInsightsSummary(BaseModel):
    """Resumo de insights de todas as publicações de um workspace."""
    workspace_id: int
    account: AccountInsightsOut | None = None
    publications: list[PublicationInsightsOut] = []
    total_views: int = 0
    total_reach: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_saved: int = 0
    publication_count: int = 0
