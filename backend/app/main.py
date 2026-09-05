"""
AI Multi-Agent Trading Copilot — FastAPI backend
"""
import os
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import auth, signals, portfolio, agents, backtest, debate, market, news, profiles, session
from app.api.routes import evaluation, performance, calendar, correlations, memory
from app.api.routes.scanner import router as scanner_router, alerts_router
from app.api.routes.paper_trading import router as paper_trading_router
from app.api.routes.billing import router as billing_router
from app.api.websocket import router as ws_router
from app.services.scheduler import start_scheduler, stop_scheduler

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Auto-create all tables (works with SQLite and PostgreSQL)
        from app.db.database import engine, Base
        import app.models.user  # noqa: F401
        import app.models.signal  # noqa: F401
        import app.models.portfolio  # noqa: F401
        import app.models.news   # noqa: F401
        import app.models.alert  # noqa: F401
        import app.models.memory  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # ── Column migrations (poor-man's Alembic) ────────────────────────────
        # create_all never alters existing tables, so new columns must be added
        # explicitly. Each statement is wrapped in try/except so it's idempotent:
        # PostgreSQL raises ProgrammingError, SQLite raises OperationalError,
        # both are silently ignored when the column already exists.
        from sqlalchemy import text as _text
        _migrations = [
            "ALTER TABLE signals ADD COLUMN timeframe_levels TEXT DEFAULT '{}'",
            "ALTER TABLE signals ADD COLUMN outcome VARCHAR",
            "ALTER TABLE signals ADD COLUMN exit_price FLOAT",
            "ALTER TABLE signals ADD COLUMN resolved_at TIMESTAMP",
            "ALTER TABLE signals ADD COLUMN pnl_pct FLOAT",
            "ALTER TABLE signals ADD COLUMN max_favorable_excursion FLOAT",
            "ALTER TABLE signals ADD COLUMN max_adverse_excursion FLOAT",
            # Probability model columns (Phase 5B)
            "ALTER TABLE signals ADD COLUMN probability_score FLOAT",
            "ALTER TABLE signals ADD COLUMN bullish_pct FLOAT",
            "ALTER TABLE signals ADD COLUMN bearish_pct FLOAT",
            "ALTER TABLE signals ADD COLUMN research_target FLOAT",
            "ALTER TABLE signals ADD COLUMN invalidation_level FLOAT",
            "ALTER TABLE signals ADD COLUMN risk_reward_ratio FLOAT",
            "ALTER TABLE signals ADD COLUMN analytical_window VARCHAR",
            "ALTER TABLE signals ADD COLUMN bull_case TEXT",
            "ALTER TABLE signals ADD COLUMN bear_case TEXT",
            "ALTER TABLE signals ADD COLUMN conviction_tier VARCHAR",
            # Signal mode column (auto-scanner)
            "ALTER TABLE signals ADD COLUMN signal_mode VARCHAR(20) DEFAULT 'AI'",
            # User model — active_profile column (Phase 3)
            "ALTER TABLE users ADD COLUMN active_profile VARCHAR DEFAULT 'balanced'",
            # Stripe billing columns
            "ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR UNIQUE",
            "ALTER TABLE users ADD COLUMN stripe_subscription_id VARCHAR",
            "ALTER TABLE users ADD COLUMN subscription_status VARCHAR DEFAULT 'none'",
        ]
        for _stmt in _migrations:
            try:
                async with engine.begin() as conn:
                    await conn.execute(_text(_stmt))
            except Exception:
                pass  # column already exists — safe to ignore

        # Seed demo user — only in development (never in production)
        if settings.environment == "development":
            from app.db.database import AsyncSessionLocal
            from app.models.user import User
            from app.auth.jwt import hash_password
            from sqlalchemy import select
            import secrets
            async with AsyncSessionLocal() as session:
                existing = await session.execute(select(User).where(User.email == "demo@tradingcopilot.ai"))
                if not existing.scalar_one_or_none():
                    demo_pw = secrets.token_urlsafe(24)
                    session.add(User(
                        id="00000000-0000-0000-0000-000000000001",
                        email="demo@tradingcopilot.ai",
                        hashed_password=hash_password(demo_pw),
                        tier="free",
                    ))
                    await session.commit()
                    log.info("demo_user_created", password=demo_pw)

        log.info("startup_db_ok", environment=settings.environment)
    except Exception as exc:
        log.error("startup_db_failed", error=str(exc))

    # Seed news table on first boot so the UI is never blank before the first scrape
    try:
        from sqlalchemy import func, select as sa_select
        from app.models.news import NewsArticle
        from app.db.database import AsyncSessionLocal as _ASL
        from app.services.news_scraper import insert_seed_articles
        async with _ASL() as _sess:
            count_result = await _sess.execute(sa_select(func.count()).select_from(NewsArticle))
            news_count = count_result.scalar_one()
        if news_count == 0:
            await insert_seed_articles()
    except Exception as exc:
        log.error("news_seed_failed", error=str(exc))

    # Start background news scraper (runs every 5 min)
    try:
        start_scheduler()
        # Kick off an immediate first scrape and signal resolution on startup
        import asyncio
        from app.services.news_scraper import scrape_all_feeds
        from app.services.scheduler import _resolve_job
        asyncio.create_task(scrape_all_feeds())
        asyncio.create_task(_resolve_job())
    except Exception as exc:
        log.error("scheduler_start_failed", error=str(exc))

    log.info("startup", environment=settings.environment, version="1.0.0")
    yield
    stop_scheduler()
    log.info("shutdown")


app = FastAPI(
    title="AI Multi-Agent Trading Copilot",
    description=(
        "A modular, multi-agent LLM-powered trading platform combining 80+ quantitative strategies "
        "from '151 Trading Strategies' with a 6-agent collaborative AI architecture."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.environment == "development" else None,
    redoc_url="/redoc" if settings.environment == "development" else None,
    openapi_url="/openapi.json" if settings.environment == "development" else None,
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── Security Headers ────────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if "x-render-origin-server" in response.headers:
            del response.headers["x-render-origin-server"]
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(signals.router)
app.include_router(portfolio.router)
app.include_router(agents.router)
app.include_router(backtest.router)
app.include_router(debate.router)
app.include_router(market.router)
app.include_router(news.router)
app.include_router(profiles.router)
app.include_router(scanner_router)
app.include_router(alerts_router)
app.include_router(session.router)
app.include_router(evaluation.router)
app.include_router(performance.router)
app.include_router(calendar.router)
app.include_router(correlations.router)
app.include_router(memory.router)
app.include_router(paper_trading_router)
app.include_router(billing_router)
app.include_router(ws_router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy"}


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Name the failure instead of hiding it.

    This used to log only str(exc) - no exception type, no traceback, no line -
    and return a bare "Internal server error". That is how a 500 on
    POST /signals/generate reached the UI with nothing to act on: the message
    named no cause, and the log did not name one either, so neither the user
    nor the server told us what broke.

    Two changes. The log now carries the exception TYPE and the full traceback,
    which is what makes a Render log searchable. And the response carries a
    short error_id that appears in both, so a screenshot of the UI can be tied
    to a specific log line.

    EXPOSE_ERROR_DETAIL controls whether the exception message itself is
    returned. It is ON by default while this app is pre-revenue and being
    debugged from screenshots, because an unnamed 500 has now cost three
    separate rounds of investigation. Exception messages can carry internal
    detail - table names, paths, query fragments - so turn it OFF (set it to
    "0") before this serves untrusted users at scale; the error_id still ties
    the report to the log line.
    """
    import traceback
    import uuid as _uuid

    error_id = _uuid.uuid4().hex[:8]
    log.error(
        "unhandled_exception",
        error_id=error_id,
        path=request.url.path,
        method=request.method,
        exc_type=type(exc).__name__,
        error=str(exc),
        traceback=traceback.format_exc(),
    )
    expose = os.getenv("EXPOSE_ERROR_DETAIL", "1").lower() not in ("0", "false", "no")
    detail = (f"{type(exc).__name__}: {exc}" if expose else "Internal server error")
    return JSONResponse(
        status_code=500,
        content={"detail": f"{detail} [ref {error_id}]", "error_id": error_id},
    )
