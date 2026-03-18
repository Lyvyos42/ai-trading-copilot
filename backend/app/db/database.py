import ssl as _ssl
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

def _build_engine_args(raw_url: str):
    """
    asyncpg does not accept `sslmode` as a keyword argument — it uses an ssl context.
    Strip sslmode (and other unsupported params) from the URL and pass ssl separately.
    """
    if not raw_url.startswith("postgresql"):
        return raw_url, {}

    # Ensure we use asyncpg driver
    url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    # Strip sslmode from query string — asyncpg requires ssl= context, not sslmode=
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs.pop("sslmode", None)
    clean_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    return clean_url, {"ssl": _ssl_ctx}

_db_url, _connect_args = _build_engine_args(settings.database_url)

engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
