"""Módulo 9 (esqueleto): interface de publicação em plataformas.

Nenhuma integração real ainda — este contrato define como os publishers
serão implementados no futuro (YouTube, TikTok, Instagram...), usando as
tabelas platform_accounts, publications e publish_logs já existentes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UploadRequest:
    video_path: Path
    title: str
    description: str
    hashtags: list[str]
    keywords: list[str]
    category: str


@dataclass
class UploadResult:
    external_id: str
    url: str | None = None


class Publisher(ABC):
    """Contrato de um publicador de plataforma."""

    platform: str = "base"

    @abstractmethod
    def validate_credentials(self, credentials: dict) -> bool:
        """Verifica se as credenciais da conta são válidas."""

    @abstractmethod
    def upload(self, credentials: dict, request: UploadRequest) -> UploadResult:
        """Envia o vídeo e retorna o identificador externo."""


# Registro de publishers; implementações futuras se registram aqui.
PUBLISHERS: dict[str, type[Publisher]] = {}
