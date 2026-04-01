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

    # FRED (Federal Reserve Economic Data) — free, get key at https://fred.stlouisfed.org/docs/api/fred/
    fred_api_key: str = ""

    # Tiingo — financial news + market data. Free tier: 500 req/day
    tiingo_api_key: str = ""

    # Alpaca — paper trading + market data. Free paper trading account.
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"  # paper trading default

    # QuiverQuant — alternative data (congressional trades, insider activity)
    quiver_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_retail: str = ""     # Stripe Price ID for $49/mo Retail
    stripe_price_pro: str = ""        # Stripe Price ID for $149/mo Pro
    stripe_price_enterprise: str = "" # Stripe Price ID for $499/mo Enterprise

    # Auth
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    # Supabase — set SUPABASE_URL + SUPABASE_JWT_SECRET in Render env vars
    supabase_url: str = ""          # e.g. https://xxxx.supabase.co
    supabase_jwt_secret: str = ""   # optional legacy HS256 secret
    # Admin — set ADMIN_SECRET in Render env vars to protect the promote endpoint
    admin_secret: str = "change_me_admin_secret"

    # Provider tier configuration (format: "provider:model")
    provider_tier_premium: str = "anthropic:claude-opus-4-6"
    provider_tier_standard: str = "anthropic:claude-sonnet-4-6"
    provider_tier_lightweight: str = "anthropic:claude-haiku-4-5-20251001"

    # OpenAI (for embeddings only — Memory Layer)
    openai_api_key: str = ""

    # Memory Layer
    memory_enabled: bool = True
    memory_retrieval_k: int = 8
    memory_relevance_threshold: float = 0.4

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
