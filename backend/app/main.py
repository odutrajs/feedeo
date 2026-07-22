from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.instagram_auth import router as instagram_auth_router
from app.api.library import router as library_router
from app.api.library import sources_library_router
from app.api.projects import router as projects_router
from app.api.publishing import router as publishing_router
from app.api.scheduler import router as scheduler_router
from app.api.sources import router as sources_router
from app.api.workspaces import router as workspaces_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.object_storage import get_object_storage
from app.db.base import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    get_object_storage().ensure_bucket()
    yield


app = FastAPI(title="virou.ai API", version="0.1.0", lifespan=lifespan)

_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
if settings.public_base_url:
    _cors_origins.append(settings.public_base_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(projects_router)
app.include_router(workspaces_router)
app.include_router(publishing_router)
app.include_router(scheduler_router)
app.include_router(instagram_auth_router)
app.include_router(sources_router)
app.include_router(sources_library_router)
app.include_router(library_router)

settings.storage_dir.mkdir(parents=True, exist_ok=True)


@app.get("/media/{key:path}")
def serve_media(key: str):
    """Serve mídia do disco local; se não estiver no disco, redireciona para o MinIO."""
    local_path = (settings.storage_dir / key).resolve()
    if not str(local_path).startswith(str(settings.storage_dir.resolve())):
        raise HTTPException(404, "Arquivo não encontrado")
    if local_path.is_file():
        return FileResponse(local_path)
    storage = get_object_storage()
    url = storage.presigned_url(key) if storage.exists(key) else None
    if url:
        return RedirectResponse(url)
    raise HTTPException(404, "Arquivo não encontrado")


@app.get("/api/health")
def health():
    return {"status": "ok"}
