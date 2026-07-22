"""Dependências de autenticação/autorização compartilhadas pelos routers."""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.base import get_db
from app.db.models import User


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    # Fallback para redirects OAuth (ex.: Instagram connect via <a href>)
    token = request.query_params.get("token")
    if token:
        return token.strip()
    return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Usuário autenticado via JWT (header Authorization: Bearer <token>)."""
    token = _token_from_request(request)
    if not token:
        raise HTTPException(401, "Não autenticado")
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(401, "Sessão inválida ou expirada")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Usuário não encontrado")
    return user


def get_subscribed_user(user: User = Depends(get_current_user)) -> User:
    """Usuário autenticado com assinatura ativa (ou admin).

    Todo o uso da aplicação (workspaces, vídeos, posts, biblioteca, publicação)
    exige plano recorrente pago via Stripe. Antes de configurar as chaves do
    Stripe, use o usuário de teste (teste@virou.ai) que já tem assinatura ativa.
    """
    if user.role == "admin":
        return user
    if user.subscription_status != "active":
        raise HTTPException(
            402,
            "Assinatura necessária: escolha um plano para usar a plataforma",
        )
    return user
