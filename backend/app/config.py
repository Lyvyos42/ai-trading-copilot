from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database — defaults to SQLite so the app works on Render without a DB env var
    database_url: str = "sqlite+aiosqlite:///./trading.db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Anthropic
    anthropic_api_key: str = ""

    # Market Data
    polygon_api_key: str = ""
    alpha_vantage_api_key: str = ""
    binance_api_key: str = ""
    binance_secret_key: str = ""
    oanda_api_key: str = ""

    # Auth
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # App
    environment: str = "development"
    log_level: str = "INFO"

    # CORS — comma-separated origins. Override via ALLOWED_ORIGINS env var.
    allowed_origins: str = "http://localhost:3000,https://*.vercel.app,https://app.quantneuraledge.com,https://quantneuraledge.com"

    # Rate limits per tier (requests per minute)
    rate_limits: dict = {
        "free": 10,
        "retail": 60,
        "pro": 300,
        "enterprise": 999999,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
