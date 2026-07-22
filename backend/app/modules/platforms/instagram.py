"""Instagram Content Publishing API — Reels, posts e carrosséis via Graph API.

Fluxos:
- Reel:      media (video_url, REELS) → poll → media_publish
- Imagem:    media (image_url) → media_publish
- Carrossel: N × media (image_url, is_carousel_item) → media (CAROUSEL) → media_publish
"""

import time

import httpx

from app.core.logging import get_logger
from app.modules.platforms.base import Publisher, UploadRequest, UploadResult

logger = get_logger("instagram.publisher")

GRAPH_API = "https://graph.instagram.com/v22.0"
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 60


class InstagramPublisher(Publisher):
    platform = "instagram"

    def validate_credentials(self, credentials: dict) -> bool:
        token = credentials.get("access_token")
        ig_user_id = credentials.get("ig_user_id")
        if not token or not ig_user_id:
            return False
        resp = httpx.get(
            f"{GRAPH_API}/me",
            params={"fields": "user_id,username", "access_token": token},
            timeout=15,
        )
        return resp.status_code == 200

    def upload(self, credentials: dict, request: UploadRequest) -> UploadResult:
        """Publica um Reel (vídeo)."""
        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]
        caption = _build_caption(request.title, request.description, request.hashtags)

        logger.info("Criando container de Reel para IG user %s", ig_user_id)
        container_id = _create_container(
            ig_user_id,
            token,
            {
                "video_url": str(request.video_path),
                "caption": caption,
                "media_type": "REELS",
            },
        )
        _wait_until_ready(container_id, token)
        media_id = _publish(ig_user_id, container_id, token)
        permalink = f"https://www.instagram.com/reel/{media_id}/"
        logger.info("Reel publicado: %s", permalink)
        return UploadResult(external_id=media_id, url=permalink)

    def publish_image(
        self,
        credentials: dict,
        image_url: str,
        caption: str,
    ) -> UploadResult:
        """Publica um post estático (1 imagem)."""
        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]

        logger.info("Criando container de imagem para IG user %s", ig_user_id)
        container_id = _create_container(
            ig_user_id,
            token,
            {"image_url": image_url, "caption": caption},
        )
        _wait_until_ready(container_id, token)
        media_id = _publish(ig_user_id, container_id, token)
        permalink = f"https://www.instagram.com/p/{media_id}/"
        logger.info("Post publicado: %s", permalink)
        return UploadResult(external_id=media_id, url=permalink)

    def publish_carousel(
        self,
        credentials: dict,
        image_urls: list[str],
        caption: str,
    ) -> UploadResult:
        """Publica um carrossel (2–10 imagens)."""
        if len(image_urls) < 2:
            raise RuntimeError("Carrossel precisa de pelo menos 2 imagens")
        if len(image_urls) > 10:
            image_urls = image_urls[:10]

        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]

        children: list[str] = []
        for i, url in enumerate(image_urls):
            logger.info("Criando item %d/%d do carrossel", i + 1, len(image_urls))
            child_id = _create_container(
                ig_user_id,
                token,
                {"image_url": url, "is_carousel_item": "true"},
            )
            _wait_until_ready(child_id, token)
            children.append(child_id)

        logger.info("Criando container CAROUSEL com %d itens", len(children))
        carousel_id = _create_container(
            ig_user_id,
            token,
            {
                "media_type": "CAROUSEL",
                "children": ",".join(children),
                "caption": caption,
            },
        )
        _wait_until_ready(carousel_id, token)
        media_id = _publish(ig_user_id, carousel_id, token)
        permalink = f"https://www.instagram.com/p/{media_id}/"
        logger.info("Carrossel publicado: %s", permalink)
        return UploadResult(external_id=media_id, url=permalink)


def _build_caption(title: str, description: str, hashtags: list[str]) -> str:
    parts = [title] if title else []
    if description:
        parts.append(description)
    if hashtags:
        parts.append(" ".join(f"#{h}" for h in hashtags))
    return "\n\n".join(parts)


def _create_container(ig_user_id: str, token: str, data: dict) -> str:
    resp = httpx.post(
        f"{GRAPH_API}/{ig_user_id}/media",
        data={**data, "access_token": token},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao criar container: {resp.text}")
    container_id = resp.json()["id"]
    logger.info("Container criado: %s", container_id)
    return container_id


def _wait_until_ready(container_id: str, token: str) -> None:
    for attempt in range(MAX_POLL_ATTEMPTS):
        status_resp = httpx.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code", "access_token": token},
            timeout=15,
        )
        if status_resp.status_code != 200:
            logger.warning("Poll falhou (attempt %d): %s", attempt, status_resp.text)
            time.sleep(POLL_INTERVAL)
            continue

        status_code = status_resp.json().get("status_code")
        logger.info("Container %s status: %s (attempt %d)", container_id, status_code, attempt)

        if status_code in ("FINISHED", None):
            # Imagens às vezes não retornam status_code (já prontas)
            if status_code == "FINISHED" or attempt >= 1:
                return
            # Sem status_code: aguarda 1 poll e segue
            time.sleep(2)
            return
        if status_code == "ERROR":
            error_msg = status_resp.json().get("status", "Erro desconhecido")
            raise RuntimeError(f"Container com erro: {error_msg}")

        time.sleep(POLL_INTERVAL)

    raise RuntimeError(f"Timeout aguardando container {container_id}")


def _publish(ig_user_id: str, container_id: str, token: str) -> str:
    resp = httpx.post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Erro ao publicar: {resp.text}")
    return resp.json()["id"]
