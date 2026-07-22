"""Armazenamento de objetos (MinIO/S3) para os vídeos e mídias do sistema.

O disco local (storage/) continua sendo o diretório de trabalho do ffmpeg;
o MinIO é a fonte durável: uploads do usuário, thumbnails/previews e vídeos
finais são espelhados para o bucket com a MESMA chave do caminho relativo
local (ex.: projects/6/video/final_v1.mp4). Se um arquivo não existir no
disco (outra máquina, cache limpo), ele é baixado do bucket sob demanda.

Se o MinIO estiver fora do ar, tudo continua funcionando só com o disco —
as operações aqui apenas registram um aviso.
"""

from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("object_storage")

_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".mp3": "audio/mpeg",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".json": "application/json",
}


class ObjectStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = None
        self._available: bool | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.settings.minio_endpoint)

    def _get_client(self):
        if self._client is None:
            from minio import Minio

            self._client = Minio(
                self.settings.minio_endpoint,
                access_key=self.settings.minio_access_key,
                secret_key=self.settings.minio_secret_key,
                secure=self.settings.minio_secure,
            )
        return self._client

    def ensure_bucket(self) -> bool:
        """Garante que o bucket existe. Retorna False se o MinIO estiver indisponível."""
        if not self.enabled:
            return False
        try:
            client = self._get_client()
            if not client.bucket_exists(self.settings.minio_bucket):
                client.make_bucket(self.settings.minio_bucket)
                logger.info("Bucket '%s' criado no MinIO", self.settings.minio_bucket)
            self._available = True
        except Exception as exc:
            self._available = False
            logger.warning("MinIO indisponível (%s); usando apenas disco local", exc)
        return self._available

    def _ready(self) -> bool:
        if not self.enabled:
            return False
        if self._available is None:
            self.ensure_bucket()
        return bool(self._available)

    # --- operações ------------------------------------------------------------

    def put_file(self, local_path: Path, key: str) -> bool:
        """Envia um arquivo local para o bucket (chave = caminho relativo ao storage)."""
        if not self._ready():
            return False
        try:
            content_type = _CONTENT_TYPES.get(local_path.suffix.lower(), "application/octet-stream")
            self._get_client().fput_object(
                self.settings.minio_bucket, key, str(local_path), content_type=content_type
            )
            logger.debug("MinIO put: %s", key)
            return True
        except Exception as exc:
            logger.warning("Falha ao enviar %s para o MinIO: %s", key, exc)
            return False

    def ensure_local(self, key: str) -> Path:
        """Garante que o objeto exista no disco local, baixando do bucket se preciso."""
        local_path = self.settings.storage_dir / key
        if local_path.exists():
            return local_path
        if not self._ready():
            raise FileNotFoundError(f"{key} não está no disco e o MinIO está indisponível")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._get_client().fget_object(self.settings.minio_bucket, key, str(local_path))
        logger.info("MinIO get: %s baixado para o disco", key)
        return local_path

    def exists(self, key: str) -> bool:
        if not self._ready():
            return False
        try:
            self._get_client().stat_object(self.settings.minio_bucket, key)
            return True
        except Exception:
            return False

    def presigned_url(self, key: str, expires_hours: int = 12) -> str | None:
        if not self._ready():
            return None
        try:
            return self._get_client().presigned_get_object(
                self.settings.minio_bucket, key, expires=timedelta(hours=expires_hours)
            )
        except Exception as exc:
            logger.warning("Falha ao gerar URL para %s: %s", key, exc)
            return None

    def delete_prefix(self, prefix: str) -> None:
        """Remove todos os objetos sob um prefixo (ex.: ao apagar uma fonte)."""
        if not self._ready():
            return
        try:
            client = self._get_client()
            for obj in client.list_objects(self.settings.minio_bucket, prefix=prefix, recursive=True):
                client.remove_object(self.settings.minio_bucket, obj.object_name)
        except Exception as exc:
            logger.warning("Falha ao remover prefixo %s do MinIO: %s", prefix, exc)


@lru_cache
def get_object_storage() -> ObjectStorage:
    return ObjectStorage()
