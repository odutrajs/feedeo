"""Instagram OAuth flow (Instagram Login API).

1. GET  /api/auth/instagram/connect?workspace_id=N  → redireciona p/ Instagram
2. GET  /api/auth/instagram/callback?code=...&state=... → troca code por token,
   salva PlatformAccount e redireciona de volta ao frontend
3. GET  /api/auth/instagram/status?workspace_id=N → verifica se o workspace
   já tem conta IG conectada
4. DELETE /api/auth/instagram/disconnect?workspace_id=N → desconecta conta
"""

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_subscribed_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import PlatformAccount, User, Workspace

router = APIRouter(prefix="/api/auth/instagram", tags=["instagram-auth"])
logger = get_logger("instagram.auth")
settings = get_settings()

IG_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
IG_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
IG_GRAPH_URL = "https://graph.instagram.com"

SCOPES = "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights"


@router.get("/connect")
def instagram_connect(
    workspace_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Redireciona o usuário para a tela de autorização do Instagram.

    Aceita JWT via header Authorization ou query ?token= (para <a href>).
    """
    if not settings.instagram_app_id:
        raise HTTPException(500, "INSTAGRAM_APP_ID não configurado")

    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.user_id != user.id:
        raise HTTPException(404, "Workspace não encontrado")

    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": str(workspace_id),
    }
    url = f"{IG_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/callback")
def instagram_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """Callback do OAuth: troca code por token e salva a conta.

    Chamado pelo Instagram (redirect do browser) — sem JWT. O dono do
    workspace é resolvido via state=workspace_id.
    """
    workspace_id = int(state) if state.isdigit() else None
    if not workspace_id:
        raise HTTPException(400, "state inválido")

    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(404, "Workspace não encontrado")
    user_id = workspace.user_id

    # 1. Trocar code por short-lived token
    token_resp = httpx.post(
        IG_TOKEN_URL,
        data={
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": settings.instagram_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    if token_resp.status_code != 200:
        logger.error("Erro ao trocar code: %s", token_resp.text)
        raise HTTPException(400, f"Erro ao obter token: {token_resp.text}")

    token_data = token_resp.json()
    short_token = token_data["access_token"]
    ig_user_id = str(token_data["user_id"])

    # 2. Trocar por long-lived token (60 dias)
    ll_resp = httpx.get(
        f"{IG_GRAPH_URL}/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.instagram_app_secret,
            "access_token": short_token,
        },
        timeout=30,
    )
    if ll_resp.status_code == 200:
        ll_data = ll_resp.json()
        access_token = ll_data["access_token"]
        expires_in = ll_data.get("expires_in", 5184000)
    else:
        logger.warning("Falha ao gerar long-lived token, usando short-lived")
        access_token = short_token
        expires_in = 3600

    # 3. Buscar perfil do usuário
    profile_resp = httpx.get(
        f"{IG_GRAPH_URL}/v22.0/me",
        params={
            "fields": "user_id,username,name,profile_picture_url",
            "access_token": access_token,
        },
        timeout=30,
    )
    username = ig_user_id
    profile_picture = None
    if profile_resp.status_code == 200:
        profile = profile_resp.json()
        username = profile.get("username", ig_user_id)
        profile_picture = profile.get("profile_picture_url")

    # 4. Salvar ou atualizar PlatformAccount
    existing = (
        db.query(PlatformAccount)
        .filter(
            PlatformAccount.user_id == user_id,
            PlatformAccount.platform == "instagram",
            PlatformAccount.workspace_id == workspace_id,
        )
        .first()
    )

    credentials = {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "expires_in": expires_in,
        "profile_picture_url": profile_picture,
    }

    if existing:
        existing.name = f"@{username}"
        existing.credentials = credentials
        existing.active = True
    else:
        account = PlatformAccount(
            user_id=user_id,
            workspace_id=workspace_id,
            platform="instagram",
            name=f"@{username}",
            credentials=credentials,
        )
        db.add(account)

    db.commit()
    logger.info("Instagram conectado: @%s (workspace=%s)", username, workspace_id)

    # 5. Redirecionar de volta ao frontend (página do workspace)
    redirect_url = f"{settings.frontend_url}/workspaces/{workspace_id}?instagram_connected=1"
    return RedirectResponse(redirect_url)


@router.get("/status")
def instagram_status(
    workspace_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Verifica se um workspace tem conta IG conectada."""
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
        return {"connected": False}

    return {
        "connected": True,
        "account_id": account.id,
        "name": account.name,
        "profile_picture_url": account.credentials.get("profile_picture_url"),
    }


@router.delete("/disconnect")
def instagram_disconnect(
    workspace_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_subscribed_user),
):
    """Desconecta a conta do Instagram de um workspace."""
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
    if account:
        account.active = False
        db.commit()
    return {"ok": True}
