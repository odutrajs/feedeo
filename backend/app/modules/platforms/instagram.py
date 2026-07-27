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
    "total_interactions",
    "ig_reels_avg_watch_time", "ig_reels_video_view_total_time",
]

POST_METRICS = [
    "comments", "likes", "reach", "saved", "shares", "views",
    "total_interactions",
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
            # Evita rajada de downloads no túnel/CDN
            if i < len(image_urls) - 1:
                time.sleep(1.5)

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

        if resp.status_code != 200:
            logger.warning("Erro ao buscar insights de %s: %s", media_id, resp.text)
            raise RuntimeError(f"Insights indisponíveis ({resp.status_code}): {resp.text}")

        result = MediaInsights(media_id=media_id)
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
        """Lista mídias do perfil do Instagram, paginando até o limite."""
        token = credentials["access_token"]
        ig_user_id = credentials["ig_user_id"]
        fields = (
            "id,caption,media_type,media_product_type,permalink,"
            "thumbnail_url,media_url,timestamp,like_count,comments_count"
        )
        page_size = min(50, max(1, limit))
        results: list[dict] = []
        url: str | None = f"{GRAPH_API}/{ig_user_id}/media"
        params: dict | None = {
            "fields": fields,
            "limit": page_size,
            "access_token": token,
        }

        while url and len(results) < limit:
            resp = httpx.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                logger.warning("Erro ao listar mídias: %s", resp.text)
                break
            payload = resp.json()
            batch = payload.get("data") or []
            results.extend(batch)
            next_url = (payload.get("paging") or {}).get("next")
            url = next_url
            params = None  # next já inclui query string

        return results[:limit]


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


def _is_media_download_timeout(resp_text: str) -> bool:
    """Detecta timeout de download de mídia pelo Instagram (subcode 2207003)."""
    t = resp_text.lower()
    return (
        "2207003" in resp_text
        or '"code":-2' in resp_text.replace(" ", "")
        or "tempo limite" in t
        or ("timeout" in t and "download" in t)
        or "demora muito" in t
    )


def _warm_media_url(url: str) -> None:
    """Pré-aquece a URL pública para o Instagram baixar mais rápido."""
    try:
        head = httpx.head(url, timeout=20, follow_redirects=True)
        logger.info(
            "Warm HEAD %s → %s (type=%s len=%s)",
            url,
            head.status_code,
            head.headers.get("content-type"),
            head.headers.get("content-length"),
        )
        # Lê os primeiros bytes (ajuda cache no edge do túnel/CDN)
        with httpx.stream("GET", url, timeout=30, follow_redirects=True) as resp:
            for i, _chunk in enumerate(resp.iter_bytes(chunk_size=64 * 1024)):
                if i >= 1:
                    break
    except httpx.RequestError as e:
        logger.warning("Falha ao aquecer URL %s: %s", url, e)


def _create_container(
    ig_user_id: str,
    token: str,
    data: dict,
    *,
    retries: int = 3,
) -> str:
    media_url = data.get("image_url") or data.get("video_url")
    if media_url:
        _warm_media_url(str(media_url))

    last_error = ""
    for attempt in range(1, retries + 1):
        resp = httpx.post(
            f"{GRAPH_API}/{ig_user_id}/media",
            data={**data, "access_token": token},
            timeout=120,
        )
        if resp.status_code == 200:
            container_id = resp.json()["id"]
            logger.info("Container criado: %s", container_id)
            return container_id

        last_error = resp.text
        if _is_media_download_timeout(last_error) and attempt < retries:
            wait = attempt * 5
            logger.warning(
                "Timeout no download da mídia (tentativa %d/%d). Nova tentativa em %ds. url=%s",
                attempt,
                retries,
                wait,
                media_url,
            )
            if media_url:
                _warm_media_url(str(media_url))
            time.sleep(wait)
            continue

        break

    if _is_media_download_timeout(last_error):
        raise RuntimeError(
            "O Instagram não conseguiu baixar a mídia a tempo (timeout). "
            "Isso costuma acontecer com túnel Cloudflare instável. "
            "Tente publicar de novo ou use um PUBLIC_BASE_URL mais estável (CDN/S3). "
            f"Detalhe: {last_error}"
        )
    raise RuntimeError(f"Erro ao criar container: {last_error}")


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
