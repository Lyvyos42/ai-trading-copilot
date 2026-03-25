"""
Agent Scanner Service — per-user, opt-in market opportunity screener.

Called by APScheduler every 5 minutes. For each user with an enabled
ScannerConfig whose interval has elapsed, runs a lightweight Claude Haiku
screen on their chosen symbols (up to max_concurrent in parallel).

Cost: ~$0.001 per symbol scan (Haiku, ~500 tokens). Full pipeline is NOT
used here — only when the user manually clicks "RUN AI ANALYSIS".
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import structlog

from app.config import settings
from app.providers.router import model_router
from app.data.market_data import fetch_market_data, resolve_ticker
from app.db.database import AsyncSessionLocal
from app.models.alert import MarketAlert, ScannerConfig
from sqlalchemy import select

log = structlog.get_logger()

# Threshold: only save + broadcast if Haiku scores >= this
CONFIDENCE_THRESHOLD = 72

_SCREEN_PROMPT = """\
You are a quantitative trading screener. Analyse the market setup below and score it.

Ticker: {ticker}
Direction bias: {direction_hint}
Current price: {price}
Price change today: {change_pct}%
ATR (14): {atr}
Recent closes (last 10 bars): {closes}
Recent headlines: {headlines}

Respond ONLY with a valid JSON object — no markdown, no explanation:
{{
  "score": <integer 0-100, how strong this setup is>,
  "direction": "<LONG or SHORT>",
  "summary": "<one sentence explaining the setup, max 120 chars>"
}}

Score >= 72 means a high-conviction opportunity worth alerting the user.
Score < 72 means no clear edge — do not force an alert.
"""


async def _screen_symbol(ticker: str, news_headlines: list[str]) -> dict | None:
    """
    Run a single lightweight Haiku screening call for one symbol.
    Returns parsed JSON dict or None if score < threshold or call fails.
    """
    try:
        data = await fetch_market_data(ticker)
        price      = data.get("close", 0)
        change_pct = data.get("price_change_pct", 0)
        atr        = data.get("atr", 0)
        closes     = data.get("closes", [])[-10:]

        # Simple direction hint from recent momentum
        direction_hint = "LONG" if change_pct >= 0 else "SHORT"

        headlines_str = "\n".join(f"- {h}" for h in news_headlines[:5]) or "No recent headlines"

        prompt = _SCREEN_PROMPT.format(
            ticker=ticker,
            direction_hint=direction_hint,
            price=price,
            change_pct=round(change_pct, 2),
            atr=round(atr, 4),
            closes=closes,
            headlines=headlines_str,
        )

        raw = await model_router.complete(
            user=prompt,
            tier="lightweight",
            max_tokens=150,
            agent_name="Scanner",
        )
        result = json.loads(raw)

        score     = int(result.get("score", 0))
        direction = result.get("direction", "LONG").upper()
        summary   = result.get("summary", "")[:200]

        if score < CONFIDENCE_THRESHOLD or direction not in ("LONG", "SHORT"):
            return None

        return {
            "ticker":    ticker,
            "direction": direction,
            "confidence": float(score),
            "summary":   summary,
            "entry_hint": float(price),
        }

    except Exception as exc:
        log.warning("scanner_screen_failed", ticker=ticker, error=str(exc))
        return None


async def _fetch_headlines_for_ticker(ticker: str) -> list[str]:
    """Pull last 3 scraped headlines mentioning this ticker from the DB."""
    try:
        from app.models.news import NewsArticle
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(NewsArticle.headline)
                .where(NewsArticle.tickers.contains(ticker))
                .order_by(NewsArticle.scraped_at.desc())
                .limit(3)
            )
            return [row[0] for row in result.all()]
    except Exception:
        return []


async def run_scanner_for_user(user_id: str, cfg: ScannerConfig) -> list[dict]:
    """
    Scan all symbols in cfg.symbols, respecting max_concurrent.
    Returns list of alert dicts that passed the confidence threshold.
    """
    symbols   = cfg.symbols or []
    semaphore = asyncio.Semaphore(cfg.max_concurrent)

    async def _guarded_screen(ticker: str) -> dict | None:
        async with semaphore:
            headlines = await _fetch_headlines_for_ticker(ticker)
            return await _screen_symbol(ticker, headlines)

    tasks   = [_guarded_screen(sym) for sym in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    alerts = []
    for r in results:
        if isinstance(r, dict) and r is not None:
            alerts.append(r)
    return alerts


async def scanner_job() -> None:
    """
    APScheduler entry point — called every 5 minutes.
    Checks every enabled ScannerConfig and runs scans that are due.
    """
    from app.api.websocket import broadcast_alert

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScannerConfig).where(ScannerConfig.enabled == True)  # noqa: E712
        )
        configs = result.scalars().all()

    if not configs:
        return

    log.info("scanner_job_start", configs=len(configs))

    for cfg in configs:
        # Check if enough time has elapsed since last scan
        if cfg.last_scan_at:
            last = cfg.last_scan_at.replace(tzinfo=timezone.utc) if cfg.last_scan_at.tzinfo is None else cfg.last_scan_at
            elapsed_min = (now - last).total_seconds() / 60
            if elapsed_min < cfg.interval_minutes:
                continue  # Not due yet

        try:
            alerts = await run_scanner_for_user(cfg.user_id, cfg)
        except Exception as exc:
            log.error("scanner_user_failed", user_id=cfg.user_id, error=str(exc))
            continue

        # Persist alerts + broadcast via WebSocket
        if alerts:
            async with AsyncSessionLocal() as session:
                for alert_data in alerts:
                    alert = MarketAlert(
                        user_id    = cfg.user_id,
                        ticker     = alert_data["ticker"],
                        direction  = alert_data["direction"],
                        confidence = alert_data["confidence"],
                        summary    = alert_data["summary"],
                        entry_hint = alert_data["entry_hint"],
                    )
                    session.add(alert)
                await session.commit()

                # Broadcast each alert to the user's WebSocket connection
                for alert_data in alerts:
                    try:
                        await broadcast_alert(cfg.user_id, {
                            "ticker":     alert_data["ticker"],
                            "direction":  alert_data["direction"],
                            "confidence": alert_data["confidence"],
                            "summary":    alert_data["summary"],
                            "entry_hint": alert_data["entry_hint"],
                            "timestamp":  now.isoformat() + "Z",
                        })
                    except Exception as exc:
                        log.warning("scanner_broadcast_failed", error=str(exc))

            log.info("scanner_user_complete",
                     user_id=cfg.user_id,
                     symbols_scanned=len(cfg.symbols),
                     alerts_fired=len(alerts))

        # Update last_scan_at
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ScannerConfig).where(ScannerConfig.user_id == cfg.user_id)
            )
            fresh_cfg = result.scalar_one_or_none()
            if fresh_cfg:
                fresh_cfg.last_scan_at = now
                await session.commit()
