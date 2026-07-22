"""Endpoints de insights do Instagram — métricas de publicações e perfil."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.api.schemas import (
    AccountInsightsOut,
    MediaInfoOut,
    MediaInsightsOut,
    PublicationInsightsOut,
    RecentMediaOut,
    WorkspaceInsightsSummary,
)
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import PlatformAccount, Publication, User, Workspace

router = APIRouter(prefix="/api/insights", tags=["insights"])
logger = get_logger("insights")


def _get_ig_account(db: Session, user: User, workspace_id: int) -> PlatformAccount:
    """Busca conta Instagram ativa do workspace ou levanta 400."""
    account = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.user_id == user.id,
            PlatformAccount.platform == "instagram",
            PlatformAccount.workspace_id == workspace_id,
            PlatformAccount.active == True,  # noqa: E712
        )
        .first()
    )
    if not account:
        raise HTTPException(400, "Nenhuma conta do Instagram conectada a este workspace")
    return account


# ── Insights de uma publicação específica ────────────────────────────


@router.get("/publication/{publication_id}", response_model=PublicationInsightsOut)
def get_publication_insights(
    publication_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Busca insights de uma publicação específica pelo ID da Publication."""
    from app.modules.platforms.instagram import InstagramPublisher

    pub = db.get(Publication, publication_id)
    if not pub:
        raise HTTPException(404, "Publicação não encontrada")

    account = db.get(PlatformAccount, pub.account_id)
    if not account or account.user_id != user.id:
        raise HTTPException(404, "Publicação não encontrada")

    if pub.status != "published" or not pub.external_id:
        raise HTTPException(400, "Publicação ainda não foi publicada no Instagram")

    publisher = InstagramPublisher()

    is_reel = True
    if pub.social_post_id:
        is_reel = False

    insights = publisher.get_media_insights(
        credentials=account.credentials,
        media_id=pub.external_id,
        is_reel=is_reel,
    )
    media_info_raw = publisher.get_media_info(
        credentials=account.credentials,
        media_id=pub.external_id,
    )

    media_info = MediaInfoOut(**media_info_raw) if media_info_raw else None

    return PublicationInsightsOut(
        publication_id=pub.id,
        external_id=pub.external_id,
        media_info=media_info,
        insights=MediaInsightsOut(
            media_id=insights.media_id,
            likes=insights.likes,
            comments=insights.comments,
            shares=insights.shares,
            saved=insights.saved,
            reach=insights.reach,
            views=insights.views,
            total_interactions=insights.total_interactions,
            reposts=insights.reposts,
            avg_watch_time_ms=insights.avg_watch_time_ms,
            video_view_total_time_ms=insights.video_view_total_time_ms,
            extra=insights.extra,
        ),
    )


# ── Insights do perfil / conta ───────────────────────────────────────


@router.get("/account", response_model=AccountInsightsOut)
def get_account_insights(
    workspace_id: int = Query(...),
    period: str = Query("day", regex="^(day|week|days_28|month)$"),
    since: int | None = Query(None),
    until: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Busca insights agregados do perfil do Instagram."""
    from app.modules.platforms.instagram import InstagramPublisher

    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace.user_id != user.id:
        raise HTTPException(404, "Workspace não encontrado")

    account = _get_ig_account(db, user, workspace_id)
    publisher = InstagramPublisher()

    result = publisher.get_account_insights(
        credentials=account.credentials,
        period=period,
        since=since,
        until=until,
    )

    return AccountInsightsOut(
        ig_user_id=result.ig_user_id,
        period=result.period,
        reach=result.reach,
        views=result.views,
        follower_count=result.follower_count,
        extra=result.extra,
    )


# ── Resumo completo de um workspace ─────────────────────────────────


@router.get("/workspace/{workspace_id}", response_model=WorkspaceInsightsSummary)
def get_workspace_insights(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Busca insights de todas as publicações de um workspace + perfil."""
    from app.modules.platforms.instagram import InstagramPublisher

    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace.user_id != user.id:
        raise HTTPException(404, "Workspace não encontrado")

    account = _get_ig_account(db, user, workspace_id)
    publisher = InstagramPublisher()

    # Insights do perfil
    account_insights_raw = publisher.get_account_insights(
        credentials=account.credentials,
        period="day",
    )
    account_insights = AccountInsightsOut(
        ig_user_id=account_insights_raw.ig_user_id,
        period=account_insights_raw.period,
        reach=account_insights_raw.reach,
        views=account_insights_raw.views,
        follower_count=account_insights_raw.follower_count,
        extra=account_insights_raw.extra,
    )

    # Publicações deste workspace com external_id (publicadas no IG)
    pubs = (
        db.query(Publication)
        .filter(
            Publication.account_id == account.id,
            Publication.status == "published",
            Publication.external_id.isnot(None),
        )
        .order_by(Publication.published_at.desc())
        .limit(50)
        .all()
    )

    publications: list[PublicationInsightsOut] = []
    total_views = total_reach = total_likes = 0
    total_comments = total_shares = total_saved = 0

    for pub in pubs:
        is_reel = pub.social_post_id is None
        try:
            insights = publisher.get_media_insights(
                credentials=account.credentials,
                media_id=pub.external_id,
                is_reel=is_reel,
            )
            media_info_raw = publisher.get_media_info(
                credentials=account.credentials,
                media_id=pub.external_id,
            )
            media_info = MediaInfoOut(**media_info_raw) if media_info_raw else None

            pub_insights = PublicationInsightsOut(
                publication_id=pub.id,
                external_id=pub.external_id,
                media_info=media_info,
                insights=MediaInsightsOut(
                    media_id=insights.media_id,
                    likes=insights.likes,
                    comments=insights.comments,
                    shares=insights.shares,
                    saved=insights.saved,
                    reach=insights.reach,
                    views=insights.views,
                    total_interactions=insights.total_interactions,
                    reposts=insights.reposts,
                    avg_watch_time_ms=insights.avg_watch_time_ms,
                    video_view_total_time_ms=insights.video_view_total_time_ms,
                    extra=insights.extra,
                ),
            )
            publications.append(pub_insights)

            total_views += insights.views
            total_reach += insights.reach
            total_likes += insights.likes
            total_comments += insights.comments
            total_shares += insights.shares
            total_saved += insights.saved
        except Exception:
            logger.warning("Falha ao buscar insights de pub %d (%s)", pub.id, pub.external_id)

    return WorkspaceInsightsSummary(
        workspace_id=workspace_id,
        account=account_insights,
        publications=publications,
        total_views=total_views,
        total_reach=total_reach,
        total_likes=total_likes,
        total_comments=total_comments,
        total_shares=total_shares,
        total_saved=total_saved,
        publication_count=len(publications),
    )


# ── Mídias recentes do perfil (com insights opcionais) ───────────────


@router.get("/recent-media", response_model=list[RecentMediaOut])
def get_recent_media(
    workspace_id: int = Query(...),
    limit: int = Query(25, ge=1, le=50),
    include_insights: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Lista mídias recentes do perfil do Instagram, com insights opcionais."""
    from app.modules.platforms.instagram import InstagramPublisher

    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace.user_id != user.id:
        raise HTTPException(404, "Workspace não encontrado")

    account = _get_ig_account(db, user, workspace_id)
    publisher = InstagramPublisher()

    raw_media = publisher.list_recent_media(
        credentials=account.credentials,
        limit=limit,
    )

    results: list[RecentMediaOut] = []
    for m in raw_media:
        item = RecentMediaOut(
            id=m["id"],
            caption=m.get("caption"),
            media_type=m.get("media_type"),
            media_product_type=m.get("media_product_type"),
            permalink=m.get("permalink"),
            thumbnail_url=m.get("thumbnail_url"),
            timestamp=m.get("timestamp"),
            like_count=m.get("like_count"),
            comments_count=m.get("comments_count"),
        )

        if include_insights:
            is_reel = m.get("media_product_type", "").upper() == "REELS"
            try:
                ins = publisher.get_media_insights(
                    credentials=account.credentials,
                    media_id=m["id"],
                    is_reel=is_reel,
                )
                item.insights = MediaInsightsOut(
                    media_id=ins.media_id,
                    likes=ins.likes,
                    comments=ins.comments,
                    shares=ins.shares,
                    saved=ins.saved,
                    reach=ins.reach,
                    views=ins.views,
                    total_interactions=ins.total_interactions,
                    reposts=ins.reposts,
                    avg_watch_time_ms=ins.avg_watch_time_ms,
                    video_view_total_time_ms=ins.video_view_total_time_ms,
                    extra=ins.extra,
                )
            except Exception:
                logger.warning("Falha ao buscar insights de %s", m["id"])

        results.append(item)

    return results
