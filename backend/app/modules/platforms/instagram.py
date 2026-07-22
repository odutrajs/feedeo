"""Instagram Content Publishing & Insights API — via Graph API.

Fluxos de publicação:
- Reel:      media (video_url, REELS) → poll → media_publish
- Imagem:    media (image_url) → media_publish
- Carrossel: N × media (image_url, is_carousel_item) → media (CAROUSEL) → media_publish

Insights (requer scope instagram_business_manage_insights):
- Media insights:   GET /{media_id}/insights?metric=...
- Account insights: GET /{ig_user_id}/insights?metric=...&period=...
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from app.core.logging import get_logger
from app.modules.platforms.base import Publisher, UploadRequest, UploadResult

logger = get_logger("instagram.publisher")

GRAPH_API = "https://graph.instagram.com/v22.0"
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 60

# ── Métricas disponíveis por tipo de mídia (v22.0+) ─────────────────

REEL_METRICS = [
    "comments", "likes", "reach", "saved", "shares", "views",
    "total_interactions", "reposts",
    "ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
]

POST_METRICS = [
    "comments", "likes", "reach", "saved", "shares", "views",
    "total_interactions", "reposts",
]

ACCOUNT_METRICS = ["reach", "views", "follower_count"]


@dataclass
class MediaInsights:
    """Dados de insights de uma mídia do Instagram."""
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
    extra: dict = field(default_factory=dict)


@dataclass
class AccountInsights:
    """Dados de insights do perfil (período)."""
    ig_user_id: str
    period: str = "day"
    reach: int = 0
    views: int = 0
    follower_count: int = 0
    extra: dict = field(default_factory=dict)


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
        video_url = str(request.video_path)

        # Verificar acessibilidade do vídeo antes de enviar
        logger.info("Verificando acessibilidade do vídeo: %s", video_url)
        try:
            check_resp = httpx.head(video_url, timeout=15, follow_redirects=True)
            logger.info("HEAD %s → %d (content-type=%s, content-length=%s)",
                        video_url, check_resp.status_code,
                        check_resp.headers.get("content-type"),
                        check_resp.headers.get("content-length"))
            if check_resp.status_code != 200:
                raise RuntimeError(f"Vídeo inacessível (HTTP {check_resp.status_code}): {video_url}")
        except httpx.RequestError as e:
            raise RuntimeError(f"Vídeo inacessível (rede): {video_url} — {e}")

        logger.info("Criando container de Reel para IG user %s", ig_user_id)
        container_id = _create_container(
            ig_user_id,
            token,
            {
                "video_url": video_url,
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

    # ── Insights ─────────────────────────────────────────────────────

    def get_media_insights(
        self,
        credentials: dict,
        media_id: str,
        is_reel: bool = True,
    ) -> MediaInsights:
        """Busca insights de uma mídia publicada no Instagram.

        Requer scope instagram_business_manage_insights.
        """
        token = credentials["access_token"]
        metrics = REEL_METRICS if is_reel else POST_METRICS

        resp = httpx.get(
            f"{GRAPH_API}/{media_id}/insights",
            params={
                "metric": ",".join(metrics),
                "access_token": token,
            },
            timeout=30,
        )

        result = MediaInsights(media_id=media_id)

        if resp.status_code != 200:
            logger.warning("Erro ao buscar insights de %s: %s", media_id, resp.text)
            return result

        data = resp.json().get("data", [])
        for entry in data:
            name = entry.get("name", "")
            value = _extract_value(entry)
            if name == "likes":
                result.likes = value
            elif name == "comments":
                result.comments = value
            elif name == "shares":
                result.shares = value
            elif name == "saved":
                result.saved = value
            elif name == "reach":
                result.reach = value
            elif name == "views":
                result.views = value
            elif name == "total_interactions":
                result.total_interactions = value
            elif name == "reposts":
                result.reposts = value
            elif name == "ig_reels_avg_watch_time":
                result.avg_watch_time_ms = value
            elif name == "ig_reels_video_view_total_time":
                result.video_view_total_time_ms = value
            else:
                result.extra[name] = value

        logger.info(
            "Insights de %s: views=%d reach=%d likes=%d",
            media_id, result.views, result.reach, result.likes,
        )
        return result

    def get_media_info(self, credentials: dict, media_id: str) -> dict:
        """Busca metadados da mídia (permalink, thumbnail, timestamp, tipo)."""
        token = credentials["access_token"]
        resp = httpx.get(
            f"{GRAPH_API}/{media_id}",
            params={
                "fields": "id,caption,media_type,media_product_type,permalink,thumbnail_url,timestamp,like_count,comments_count",
                "access_token": token,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("Erro ao buscar info de %s: %s", media_id, resp.text)
            return {}
        return resp.json()

    def get_account_insights(
        self,
        credentials: dict,
        period: str = "day",
        since: int | None = None,
        until: int | None = None,
    ) -> AccountInsights:
        """Busca insights do perfil do Instagram.

        period: day, week, days_28, month
        since/until: unix timestamps opcionais para filtrar intervalo.
        """
        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]

        params: dict = {
            "metric": ",".join(ACCOUNT_METRICS),
            "period": period,
            "metric_type": "total_value",
            "access_token": token,
        }
        if since:
            params["since"] = since
        if until:
            params["until"] = until

        resp = httpx.get(
            f"{GRAPH_API}/{ig_user_id}/insights",
            params=params,
            timeout=30,
        )

        result = AccountInsights(ig_user_id=ig_user_id, period=period)

        if resp.status_code != 200:
            logger.warning("Erro ao buscar insights do perfil: %s", resp.text)
            return result

        data = resp.json().get("data", [])
        for entry in data:
            name = entry.get("name", "")
            value = _extract_value(entry)
            if name == "reach":
                result.reach = value
            elif name == "views":
                result.views = value
            elif name == "follower_count":
                result.follower_count = value
            else:
                result.extra[name] = value

        logger.info(
            "Account insights (%s): reach=%d views=%d followers=%d",
            period, result.reach, result.views, result.follower_count,
        )
        return result

    def list_recent_media(self, credentials: dict, limit: int = 25) -> list[dict]:
        """Lista mídias recentes do perfil do Instagram."""
        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]

        resp = httpx.get(
            f"{GRAPH_API}/{ig_user_id}/media",
            params={
                "fields": "id,caption,media_type,media_product_type,permalink,thumbnail_url,timestamp,like_count,comments_count",
                "limit": limit,
                "access_token": token,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("Erro ao listar mídias: %s", resp.text)
            return []
        return resp.json().get("data", [])


def _extract_value(entry: dict) -> int:
    """Extrai o valor numérico de um entry da resposta de insights."""
    total = entry.get("total_value", {})
    if isinstance(total, dict) and "value" in total:
        return int(total["value"])
    values = entry.get("values", [])
    if values:
        return int(values[0].get("value", 0))
    return 0


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
            params={"fields": "status_code,status,error_message", "access_token": token},
            timeout=15,
        )
        if status_resp.status_code != 200:
            logger.warning("Poll falhou (attempt %d): %s", attempt, status_resp.text)
            time.sleep(POLL_INTERVAL)
            continue

        data = status_resp.json()
        status_code = data.get("status_code")
        logger.info("Container %s status: %s (attempt %d)", container_id, status_code, attempt)

        if status_code in ("FINISHED", None):
            # Imagens às vezes não retornam status_code (já prontas)
            if status_code == "FINISHED" or attempt >= 1:
                return
            # Sem status_code: aguarda 1 poll e segue
            time.sleep(2)
            return
        if status_code == "ERROR":
            error_msg = data.get("error_message") or data.get("status") or "Erro desconhecido"
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
