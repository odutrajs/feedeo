from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys
    openai_api_key: str = ""
    elevenlabs_api_key: str = ""

    # Defaults
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" (placeholder; troque pela sua voz clonada)
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    openai_text_model: str = "gpt-4o"
    fal_key: str = ""
    # Modelo premium para imagens de vídeos, posts estáticos e carrosséis.
    fal_image_model: str = "fal-ai/flux-2-pro"
    whisper_model_size: str = "small"

    # Auth (JWT)
    jwt_secret: str = "dev-secret-troque-em-producao"
    jwt_expires_minutes: int = 60 * 24 * 7  # 7 dias

    # Stripe (assinatura recorrente) — preencha no .env
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # Price IDs dos planos recorrentes no Stripe (price_...)
    stripe_price_creator: str = ""
    stripe_price_pro: str = ""
    stripe_price_studio: str = ""

    # Paths / infra
    database_url: str = f"sqlite:///{REPO_DIR / 'storage' / 'app.db'}"
    storage_dir: Path = REPO_DIR / "storage"
    log_level: str = "INFO"

    # MinIO / S3 (docker-compose.yml na raiz sobe o MinIO nessas portas).
    # Deixe minio_endpoint vazio para desativar e usar apenas disco local.
    minio_endpoint: str = "localhost:9010"
    minio_access_key: str = "creators"
    minio_secret_key: str = "creators123"
    minio_bucket: str = "creators-media"
    minio_secure: bool = False

    # Redis (comunicação com o scheduler)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    scheduler_channel: str = "scheduler:new"
    scheduler_url: str = "http://localhost:8090"

    # Instagram OAuth (API do Instagram com Instagram Login)
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_redirect_uri: str = "http://localhost:8005/api/auth/instagram/callback"
    # URL pública que o Instagram usa para baixar o vídeo (ex.: túnel cloudflared)
    public_base_url: str = ""
    # URL do frontend para redirecionar após OAuth
    frontend_url: str = "http://localhost:3001"

    # Video defaults
    video_width: int = 1080
    video_height: int = 1920
    video_fps: int = 30

    @property
    def projects_dir(self) -> Path:
        return self.storage_dir / "projects"

    @property
    def music_dir(self) -> Path:
        return self.storage_dir / "music"

    @property
    def library_dir(self) -> Path:
        return self.storage_dir / "library"

    def project_dir(self, project_id: int) -> Path:
        return self.projects_dir / str(project_id)

    def user_library_dir(self, user_id: int) -> Path:
        return self.library_dir / str(user_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
