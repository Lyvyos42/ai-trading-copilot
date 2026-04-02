"""
Stripe billing endpoints:
  POST /api/v1/billing/checkout    — create Stripe Checkout session
  POST /api/v1/billing/portal      — create Stripe Customer Portal session
  POST /api/v1/billing/webhook     — Stripe webhook handler
  GET  /api/v1/billing/status      — current subscription status
"""
import stripe
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.config import settings
from app.db.database import get_db
from app.models.user import User

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

# Map tier names to Stripe Price IDs
_TIER_PRICES = {
    "retail": lambda: settings.stripe_price_retail,
    "pro": lambda: settings.stripe_price_pro,
    "enterprise": lambda: settings.stripe_price_enterprise,
}


class CheckoutRequest(BaseModel):
    tier: str  # "retail", "pro", or "enterprise"
    success_url: str = "https://app.quantneuraledge.com/dashboard?checkout=success"
    cancel_url: str = "https://app.quantneuraledge.com/pricing?checkout=cancelled"


@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    token_payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session for subscription."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing not configured")

    if req.tier not in _TIER_PRICES:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {req.tier}")

    price_id = _TIER_PRICES[req.tier]()
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Price not configured for {req.tier}")

    # Resolve user from DB (auto-create if first Supabase login)
    user_id = token_payload.get("sub")
    email = token_payload.get("email", "")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(id=user_id, email=email, hashed_password="", tier="free")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    stripe.api_key = settings.stripe_secret_key

    # Get or create Stripe customer
    if not user.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email or token_payload.get("email", ""),
            metadata={"user_id": str(user.id)},
        )
        user.stripe_customer_id = customer.id
        await db.commit()

    session = stripe.checkout.Session.create(
        customer=user.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"user_id": str(user.id), "tier": req.tier},
    )

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/portal")
async def create_portal(
    token_payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe Customer Portal session for managing subscription."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing not configured")

    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")

    stripe.api_key = settings.stripe_secret_key
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url="https://app.quantneuraledge.com/dashboard",
    )

    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events — subscription lifecycle."""
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    stripe.api_key = settings.stripe_secret_key

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    log.info("stripe_webhook", event_type=event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"status": "ok"}


@router.get("/status")
async def billing_status(
    token_payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current subscription status."""
    user_id = token_payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    return {
        "tier": user.tier if user else "free",
        "has_billing": bool(user and user.stripe_customer_id),
        "stripe_customer_id": user.stripe_customer_id if user else None,
    }


# -- Webhook handlers ---------------------------------------------------------

async def _handle_checkout_completed(data: dict, db: AsyncSession):
    """Upgrade user tier after successful checkout."""
    user_id = data.get("metadata", {}).get("user_id")
    tier = data.get("metadata", {}).get("tier")
    subscription_id = data.get("subscription")

    if not user_id or not tier:
        log.warning("stripe_checkout_missing_metadata", data=data)
        return

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            tier=tier,
            stripe_subscription_id=subscription_id,
            subscription_status="active",
        )
    )
    await db.commit()
    log.info("stripe_tier_upgraded", user_id=user_id, tier=tier)


async def _handle_subscription_updated(data: dict, db: AsyncSession):
    """Handle subscription changes (upgrade/downgrade/renewal)."""
    subscription_id = data.get("id")
    status = data.get("status")  # active, past_due, canceled, etc.
    customer_id = data.get("customer")

    # Map Stripe price to tier
    items = data.get("items", {}).get("data", [])
    price_id = items[0]["price"]["id"] if items else None

    tier = _price_to_tier(price_id) if price_id else None

    values = {"subscription_status": status}
    if tier:
        values["tier"] = tier

    await db.execute(
        update(User)
        .where(User.stripe_customer_id == customer_id)
        .values(**values)
    )
    await db.commit()
    log.info("stripe_subscription_updated", customer=customer_id, status=status, tier=tier)


async def _handle_subscription_deleted(data: dict, db: AsyncSession):
    """Downgrade to free when subscription is canceled."""
    customer_id = data.get("customer")
    await db.execute(
        update(User)
        .where(User.stripe_customer_id == customer_id)
        .values(tier="free", subscription_status="canceled")
    )
    await db.commit()
    log.info("stripe_subscription_canceled", customer=customer_id)


async def _handle_payment_failed(data: dict, db: AsyncSession):
    """Mark subscription as past_due on payment failure."""
    customer_id = data.get("customer")
    await db.execute(
        update(User)
        .where(User.stripe_customer_id == customer_id)
        .values(subscription_status="past_due")
    )
    await db.commit()
    log.warning("stripe_payment_failed", customer=customer_id)


def _price_to_tier(price_id: str) -> str | None:
    """Map Stripe Price ID back to tier name."""
    if price_id == settings.stripe_price_retail:
        return "retail"
    elif price_id == settings.stripe_price_pro:
        return "pro"
    elif price_id == settings.stripe_price_enterprise:
        return "enterprise"
    return None
