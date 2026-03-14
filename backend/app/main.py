"""
AI Multi-Agent Trading Copilot — FastAPI backend
"""
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.routes import auth, signals, portfolio, agents, backtest, debate
from app.api.websocket import router as ws_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Auto-create all tables (works with SQLite and PostgreSQL)
        from app.db.database import engine, Base
        import app.models.user  # noqa: F401
        import app.models.signal  # noqa: F401
        import app.models.portfolio  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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
        # App still starts — DB will be retried on first request

    log.info("startup", environment=settings.environment, version="1.0.0")
    yield
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
_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
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
