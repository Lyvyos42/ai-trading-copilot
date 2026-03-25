"""
AI Multi-Agent Trading Copilot — FastAPI backend
"""
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import auth, signals, portfolio, agents, backtest, debate, market, news
from app.api.routes.scanner import router as scanner_router, alerts_router
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
        ]
        async with engine.begin() as conn:
            for _stmt in _migrations:
                try:
                    await conn.execute(_text(_stmt))
                except Exception:
                    pass  # column already exists — safe to ignore

        # Seed demo user
        from app.db.database import AsyncSessionLocal
        from app.models.user import User
        from app.auth.jwt import hash_password
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            existing = await session.execute(select(User).where(User.email == "demo@tradingcopilot.ai"))
            if not existing.scalar_one_or_none():
                session.add(User(
                    id="00000000-0000-0000-0000-000000000001",
                    email="demo@tradingcopilot.ai",
                    hashed_password=hash_password("demo1234"),
                    tier="pro",
                ))
                await session.commit()

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
        # Kick off an immediate first scrape on startup
        import asyncio
        from app.services.news_scraper import scrape_all_feeds
        asyncio.create_task(scrape_all_feeds())
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
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"https://.*\.vercel\.app"
        r"|https://app\.quantneuraledge\.com"
        r"|https://quantneuraledge\.com"
        r"|http://localhost:\d+"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(signals.router)
app.include_router(portfolio.router)
app.include_router(agents.router)
app.include_router(backtest.router)
app.include_router(debate.router)
app.include_router(market.router)
app.include_router(news.router)
app.include_router(scanner_router)
app.include_router(alerts_router)
app.include_router(ws_router)


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "agents": 6,
        "strategies": 80,
    }


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
