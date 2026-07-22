"""Assinatura recorrente via Stripe: checkout, portal do cliente e webhook.

Fluxo:
1. POST /api/billing/checkout {plan} → cria Checkout Session (mode=subscription)
   e devolve a URL do Stripe para o frontend redirecionar.
2. Stripe chama POST /api/billing/webhook nos eventos de assinatura; o backend
   atualiza subscription_status/plan/current_period_end do usuário.
3. POST /api/billing/portal → URL do Customer Portal (trocar cartão, cancelar).

Configure no backend/.env:
  STRIPE_SECRET_KEY=sk_...
  STRIPE_PUBLISHABLE_KEY=pk_...
  STRIPE_WEBHOOK_SECRET=whsec_...
  STRIPE_PRICE_CREATOR=price_...
  STRIPE_PRICE_PRO=price_...
  STRIPE_PRICE_STUDIO=price_...
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import User

router = APIRouter(prefix="/api/billing", tags=["billing"])
logger = get_logger("billing")

PLANS: dict[str, dict] = {
    "creator": {"label": "Criador", "price_display": "R$ 79/mês"},
    "pro": {"label": "Profissional", "price_display": "R$ 149/mês"},
    "studio": {"label": "Estúdio", "price_display": "R$ 399/mês"},
}


def _stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(
            503,
            "Stripe não configurado: defina STRIPE_SECRET_KEY no backend/.env",
        )
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _price_id_for(plan: str) -> str:
    settings = get_settings()
    price = {
        "creator": settings.stripe_price_creator,
        "pro": settings.stripe_price_pro,
        "studio": settings.stripe_price_studio,
    }.get(plan, "")
    if not price:
        raise HTTPException(
            503,
            f"Plano '{plan}' sem price configurado: defina STRIPE_PRICE_{plan.upper()} no backend/.env",
        )
    return price


def _ensure_customer(stripe, user: User, db: Session) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email, name=user.name, metadata={"user_id": str(user.id)}
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


# ── Endpoints chamados pelo frontend ─────────────────────────────────


class CheckoutRequest(BaseModel):
    plan: str = "pro"  # creator | pro | studio


class CheckoutResponse(BaseModel):
    url: str


@router.get("/plans")
def list_plans():
    """Planos disponíveis (para a página de assinatura)."""
    return [{"id": plan_id, **info} for plan_id, info in PLANS.items()]


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.plan not in PLANS:
        raise HTTPException(400, f"Plano desconhecido: {body.plan}")
    if user.subscription_status == "active":
        raise HTTPException(400, "Você já tem uma assinatura ativa")

    settings = get_settings()
    stripe = _stripe()
    customer_id = _ensure_customer(stripe, user, db)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": _price_id_for(body.plan), "quantity": 1}],
        subscription_data={"metadata": {"user_id": str(user.id), "plan": body.plan}},
        metadata={"user_id": str(user.id), "plan": body.plan},
        success_url=f"{settings.frontend_url}/billing?status=success",
        cancel_url=f"{settings.frontend_url}/billing?status=cancelled",
        allow_promotion_codes=True,
    )
    return CheckoutResponse(url=session.url)


class PortalResponse(BaseModel):
    url: str


@router.post("/portal", response_model=PortalResponse)
def create_portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Portal do cliente Stripe: trocar cartão, ver faturas, cancelar."""
    settings = get_settings()
    stripe = _stripe()
    if not user.stripe_customer_id:
        raise HTTPException(400, "Você ainda não tem uma assinatura")
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return PortalResponse(url=session.url)


# ── Webhook do Stripe ─────────────────────────────────────────────────


def _sync_subscription(db: Session, subscription: dict) -> None:
    """Atualiza o usuário a partir do objeto subscription do Stripe."""
    user = None
    user_id = (subscription.get("metadata") or {}).get("user_id")
    if user_id and str(user_id).isdigit():
        user = db.get(User, int(user_id))
    if user is None:
        customer_id = subscription.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user is None:
        logger.warning("webhook: usuário não encontrado para subscription %s", subscription.get("id"))
        return

    status = subscription.get("status", "")
    # Mapeia status do Stripe → status interno
    if status in ("active", "trialing"):
        user.subscription_status = "active"
    elif status in ("past_due", "unpaid", "incomplete"):
        user.subscription_status = "past_due"
    else:  # canceled, incomplete_expired...
        user.subscription_status = "canceled"

    user.stripe_subscription_id = subscription.get("id")
    plan = (subscription.get("metadata") or {}).get("plan")
    if plan:
        user.plan = plan
    period_end = subscription.get("current_period_end")
    if period_end:
        user.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
    db.commit()
    logger.info(
        "assinatura sincronizada: user=%s status=%s plan=%s",
        user.id,
        user.subscription_status,
        user.plan,
    )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    stripe = _stripe()
    payload = await request.body()

    if settings.stripe_webhook_secret:
        signature = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.stripe_webhook_secret
            )
        except Exception:
            raise HTTPException(400, "Assinatura do webhook inválida")
    else:
        import json

        event = json.loads(payload)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        subscription_id = data.get("subscription")
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            _sync_subscription(db, subscription)
    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _sync_subscription(db, data)
    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            user.subscription_status = "past_due"
            db.commit()

    return {"received": True}
