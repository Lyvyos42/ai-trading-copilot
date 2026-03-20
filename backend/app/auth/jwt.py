from datetime import datetime, timedelta, timezone
from typing import Any
import asyncio, httpx, logging

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.config import settings

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

ALGORITHM  = settings.jwt_algorithm
SECRET_KEY = settings.jwt_secret

# ── Supabase JWKS cache ────────────────────────────────────────────────────────
# Supabase now uses ECC (P-256) asymmetric keys — we fetch the public JWKS
# once and cache them. No shared secret needed.
_jwks_cache: list[dict] | None = None
_jwks_lock = asyncio.Lock()


async def _get_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    if not settings.supabase_url:
        return []
    async with _jwks_lock:
        if _jwks_cache:
            return _jwks_cache
        try:
            url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                r.raise_for_status()
                _jwks_cache = r.json().get("keys", [])
                log.info("Loaded %d Supabase JWKS keys", len(_jwks_cache))
        except Exception as e:
            log.warning("Could not fetch Supabase JWKS: %s", e)
            _jwks_cache = []
    return _jwks_cache or []


def _try_supabase_sync(token: str, jwks: list[dict]) -> dict | None:
    """Try to verify token against each JWKS key."""
    for key in jwks:
        try:
            return jwt.decode(
                token, key,
                algorithms=["ES256", "RS256", "HS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            continue
    return None


# ── Legacy HS256 (supabase_jwt_secret env var) ────────────────────────────────
def _try_legacy_supabase(token: str) -> dict | None:
    if not settings.supabase_jwt_secret:
        return None
    try:
        return jwt.decode(
            token, settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


# ── Custom JWT (demo user) ────────────────────────────────────────────────────
def _try_custom(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── Public decode_token (sync wrapper + async) ────────────────────────────────
def decode_token(token: str, _jwks: list[dict] | None = None) -> dict[str, Any]:
    jwks = _jwks or []

    # 1. Supabase JWKS (ECC / RSA)
    if jwks:
        result = _try_supabase_sync(token, jwks)
        if result:
            return result

    # 2. Supabase legacy HS256 secret
    result = _try_legacy_supabase(token)
    if result:
        return result

    # 3. Custom JWT (demo user + local dev)
    result = _try_custom(token)
    if result:
        return result

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def decode_token_async(token: str) -> dict[str, Any]:
    jwks = await _get_jwks()
    return decode_token(token, jwks)


# ── FastAPI dependencies ──────────────────────────────────────────────────────
async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    payload = await decode_token_async(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
    return user_id


async def get_current_user_tier(token: str = Depends(oauth2_scheme)) -> str:
    payload = await decode_token_async(token)
    return payload.get("tier", "free")


async def get_optional_user(
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False))
) -> dict | None:
    if not token:
        return None
    try:
        return await decode_token_async(token)
    except HTTPException:
        return None


# ── Password helpers (kept for demo user seeding) ─────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
