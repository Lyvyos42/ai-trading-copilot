-- AI Trading Copilot - Database Initialization
-- Uses TimescaleDB for time-series tables

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    tier            TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'retail', 'pro', 'enterprise')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Signals ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signals (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
    ticker           TEXT NOT NULL,
    asset_class      TEXT NOT NULL DEFAULT 'stocks',
    timeframe        TEXT NOT NULL DEFAULT '1D',
    direction        TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price      DOUBLE PRECISION NOT NULL,
    stop_loss        DOUBLE PRECISION NOT NULL,
    take_profit_1    DOUBLE PRECISION NOT NULL,
    take_profit_2    DOUBLE PRECISION NOT NULL,
    take_profit_3    DOUBLE PRECISION NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    agent_votes      JSONB NOT NULL DEFAULT '[]',
    reasoning_chain  JSONB NOT NULL DEFAULT '[]',
    strategy_sources JSONB NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXECUTED', 'EXPIRED', 'CANCELLED')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expiry_time      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

-- Convert signals to TimescaleDB hypertable
SELECT create_hypertable('signals', 'created_at', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_signals_user_id ON signals(user_id);
CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);

-- ─── Positions ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE,
    signal_id     UUID REFERENCES signals(id) ON DELETE SET NULL,
    ticker        TEXT NOT NULL,
    asset_class   TEXT NOT NULL DEFAULT 'stocks',
    direction     TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    entry_price   DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION,
    quantity      DOUBLE PRECISION NOT NULL,
    stop_loss     DOUBLE PRECISION NOT NULL,
    take_profit_1 DOUBLE PRECISION NOT NULL,
    status        TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'STOPPED_OUT')),
    opened_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at     TIMESTAMPTZ,
    close_price   DOUBLE PRECISION,
    realized_pnl  DOUBLE PRECISION,
    is_paper      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_positions_user_id ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);

-- ─── OHLCV Price Data (TimescaleDB) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    timeframe   TEXT NOT NULL DEFAULT '1D',
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      BIGINT NOT NULL,
    vwap        DOUBLE PRECISION,
    PRIMARY KEY (time, ticker, timeframe)
);

SELECT create_hypertable('ohlcv', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker ON ohlcv(ticker, timeframe, time DESC);

-- ─── Agent Execution Logs ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name  TEXT NOT NULL,
    ticker      TEXT NOT NULL,
    signal_id   UUID REFERENCES signals(id) ON DELETE SET NULL,
    input       JSONB,
    output      JSONB,
    latency_ms  INTEGER,
    success     BOOLEAN NOT NULL DEFAULT TRUE,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('agent_logs', 'created_at', if_not_exists => TRUE);

-- ─── Strategy Backtest Results ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS backtest_results (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_name   TEXT NOT NULL,
    ticker          TEXT NOT NULL,
    period          TEXT NOT NULL,
    total_return    DOUBLE PRECISION,
    sharpe_ratio    DOUBLE PRECISION,
    max_drawdown    DOUBLE PRECISION,
    win_rate        DOUBLE PRECISION,
    total_trades    INTEGER,
    equity_curve    JSONB,
    trades          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Subscriptions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    tier            TEXT NOT NULL,
    stripe_sub_id   TEXT,
    status          TEXT NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Seed Data: Demo User ─────────────────────────────────────────────────────
-- Password: demo1234 (bcrypt hashed)
INSERT INTO users (id, email, hashed_password, tier)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'demo@tradingcopilot.ai',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGqB1dFqJkKqn0Ge3n1yxOzQVOW',
    'pro'
) ON CONFLICT (email) DO NOTHING;

-- ─── Useful Views ─────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW signal_performance AS
SELECT
    s.ticker,
    s.direction,
    s.confidence_score,
    s.entry_price,
    p.close_price,
    p.realized_pnl,
    CASE
        WHEN p.realized_pnl > 0 THEN 'WIN'
        WHEN p.realized_pnl < 0 THEN 'LOSS'
        ELSE 'OPEN'
    END AS outcome,
    s.created_at,
    p.closed_at
FROM signals s
LEFT JOIN positions p ON p.signal_id = s.id;
