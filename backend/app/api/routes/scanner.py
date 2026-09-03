"""
Scanner configuration + alert history endpoints.

GET  /api/v1/scanner/config          — get user's scanner config
PUT  /api/v1/scanner/config          — save config (creates if missing)
GET  /api/v1/alerts                  — recent alerts for this user
PATCH /api/v1/alerts/{id}/read       — mark alert as read
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, get_optional_user
from app.db.database import get_db
from app.models.alert import ScannerConfig, MarketAlert
from app.models.user import User

router = APIRouter(prefix="/api/v1/scanner", tags=["scanner"])
alerts_router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

PREMIUM_TIERS = {"pro", "enterprise", "admin"}
MAX_SYMBOLS   = 20
VALID_INTERVALS = {15, 30, 60}


FREE_MAX_SYMBOLS = 5
PREMIUM_MAX_SYMBOLS = 20

async def _get_user_id_and_max_symbols(user: dict, db: AsyncSession) -> tuple[str, int]:
    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    tier = user.get("tier", "") or ""
    if not tier:
        result = await db.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one_or_none()
        tier = db_user.tier if db_user else "free"
    max_symbols = PREMIUM_MAX_SYMBOLS if tier in PREMIUM_TIERS else FREE_MAX_SYMBOLS
    return user_id, max_symbols



# ── Config schema ──────────────────────────────────────────────────────────────

class ScannerConfigIn(BaseModel):
    enabled:          bool       = False
    symbols:          list[str]  = Field(default_factory=list, max_length=MAX_SYMBOLS)
    max_concurrent:   int        = Field(default=2, ge=1, le=5)
    interval_minutes: int        = Field(default=30)

    def validate_symbols(self):
        cleaned = [s.upper().strip() for s in self.symbols if s.strip()]
        return list(dict.fromkeys(cleaned))[:MAX_SYMBOLS]  # dedupe, cap at 20


def _config_to_dict(cfg: ScannerConfig) -> dict:
    scans_per_hour = 60 / cfg.interval_minutes
    cost_per_hour  = round(len(cfg.symbols) * scans_per_hour * 0.001, 4)
    return {
        "enabled":          cfg.enabled,
        "symbols":          cfg.symbols,
        "max_concurrent":   cfg.max_concurrent,
        "interval_minutes": cfg.interval_minutes,
        "last_scan_at":     (cfg.last_scan_at.isoformat() + "Z") if cfg.last_scan_at else None,
        "estimated_cost_per_hour": cost_per_hour,
    }


# ── GET config ────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    user_id, max_symbols = await _get_user_id_and_max_symbols(user, db)
    result  = await db.execute(select(ScannerConfig).where(ScannerConfig.user_id == user_id))
    cfg     = result.scalar_one_or_none()
    if not cfg:
        return {
            "enabled": False, "symbols": [], "max_concurrent": 2,
            "interval_minutes": 30, "last_scan_at": None,
            "estimated_cost_per_hour": 0.0,
            "max_symbols": max_symbols,
        }
    data = _config_to_dict(cfg)
    data["max_symbols"] = max_symbols
    return data


# ── PUT config ────────────────────────────────────────────────────────────────

@router.put("/config")
async def save_config(
    body: ScannerConfigIn,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    user_id, max_symbols = await _get_user_id_and_max_symbols(user, db)

    if body.interval_minutes not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail="interval_minutes must be 15, 30, or 60")

    symbols = body.validate_symbols()[:max_symbols]

    result = await db.execute(select(ScannerConfig).where(ScannerConfig.user_id == user_id))
    cfg    = result.scalar_one_or_none()

    if cfg is None:
        cfg = ScannerConfig(user_id=user_id)
        db.add(cfg)

    cfg.enabled          = body.enabled
    cfg.symbols          = symbols
    cfg.max_concurrent   = body.max_concurrent
    cfg.interval_minutes = body.interval_minutes

    await db.commit()
    await db.refresh(cfg)
    data = _config_to_dict(cfg)
    data["max_symbols"] = max_symbols
    return data



# ── GET alerts ────────────────────────────────────────────────────────────────

@alerts_router.get("")
async def list_alerts(
    limit: int = 20,
    db:    AsyncSession = Depends(get_db),
    user:  dict | None  = Depends(get_optional_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user["sub"]
    result  = await db.execute(
        select(MarketAlert)
        .where(MarketAlert.user_id == user_id)
        .order_by(desc(MarketAlert.created_at))
        .limit(min(limit, 50))
    )
    alerts = result.scalars().all()
    return [_alert_to_dict(a) for a in alerts]


# ── PATCH alert read ──────────────────────────────────────────────────────────

@alerts_router.patch("/{alert_id}/read")
async def mark_read(
    alert_id: str,
    db:       AsyncSession = Depends(get_db),
    user:     dict | None  = Depends(get_optional_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await db.execute(select(MarketAlert).where(MarketAlert.id == alert_id))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Not your alert")

    alert.read = True
    await db.commit()
    return {"ok": True}


# ── POST auto/trigger ─────────────────────────────────────────────────────────

class ScanNowIn(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    replace_active: bool = True


@router.post("/auto/trigger")
async def trigger_auto_scan(
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    """Manually trigger an auto-scan for the current user (testing/on-demand)."""
    user_id, _max = await _get_user_id_and_max_symbols(user, db)

    result = await db.execute(
        select(ScannerConfig).where(ScannerConfig.user_id == user_id)
    )
    cfg = result.scalar_one_or_none()

    symbols = cfg.symbols if (cfg and cfg.symbols) else ["BTC-USD", "ETH-USD", "EURUSD=X", "GBPUSD=X", "XAUUSD"]

    from app.services.auto_scanner import run_auto_scan_for_user

    results = await run_auto_scan_for_user(user_id, symbols, replace_active=True)

    return {
        "symbols_scanned": len(symbols),
        "signals_generated": len(results),
        "signals": results,
    }


@router.post("/scan-now")
async def scan_now(
    body: ScanNowIn,
    db:   AsyncSession = Depends(get_db),
    user: dict         = Depends(get_current_user),
):
    """Instant zero-cost batch scan for dashboard symbols."""
    user_id, max_symbols = await _get_user_id_and_max_symbols(user, db)
    symbols = [s.upper().strip() for s in body.symbols if s.strip()][:max_symbols]
    if not symbols:
        symbols = ["BTC-USD", "EURUSD=X", "GBPUSD=X", "XAUUSD"]

    from app.services.auto_scanner import run_auto_scan_for_user

    results = await run_auto_scan_for_user(user_id, symbols, replace_active=body.replace_active)

    return {
        "symbols_scanned": len(symbols),
        "signals_generated": len(results),
        "signals": results,
    }



def _alert_to_dict(a: MarketAlert) -> dict:
    return {
        "id":          a.id,
        "ticker":      a.ticker,
        "direction":   a.direction,
        "confidence":  a.confidence,
        "summary":     a.summary,
        "entry_hint":  a.entry_hint,
        "read":        a.read,
        "created_at":  (a.created_at.isoformat() + "Z") if a.created_at else None,
    }
