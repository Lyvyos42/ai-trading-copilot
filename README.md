# AI Multi-Agent Trading Copilot

A modular SaaS platform combining **80+ quantitative strategies** from *151 Trading Strategies* (Kakushadze & Serur, 2018) with a **6-agent LLM architecture** powered by Claude.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Signal Pipeline (DAG)                     │
│                                                                   │
│  ┌──────────────────────────────────────────┐                    │
│  │           Analyst Team (parallel)         │                    │
│  │  [Fundamental] [Technical] [Sentiment]    │                    │
│  │               [Macro]                     │                    │
│  └──────────────────────┬───────────────────┘                    │
│                         ↓                                        │
│              ┌──────────────────────┐                            │
│              │   Bull / Bear Debate  │                            │
│              └──────────┬───────────┘                            │
│                         ↓                                        │
│              ┌──────────────────────┐                            │
│              │     Risk Manager      │                            │
│              └──────────┬───────────┘                            │
│                         ↓                                        │
│              ┌──────────────────────┐                            │
│              │    Trader Agent       │ ← claude-opus-4-6          │
│              └──────────┬───────────┘                            │
│                         ↓                                        │
│                  Final Signal + TP/SL                             │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM Orchestration | LangGraph + LangChain |
| Primary LLM | Claude Opus 4.6 (Trader) + Sonnet 4.6 (Analysts) |
| Backend | Python 3.11 + FastAPI |
| Frontend | Next.js 14 + TradingView Lightweight Charts |
| Database | TimescaleDB (PostgreSQL 15) |
| Cache / Bus | Redis 7 |
| Containerization | Docker Compose |

## Quick Start

### Prerequisites
- Docker Desktop
- An Anthropic API key (get one at console.anthropic.com)
- (Optional) Polygon.io and Alpha Vantage API keys for live data

### 1. Clone and configure

```bash
git clone <repo>
cd ai-trading-copilot
cp .env.example .env
```

Edit `.env` and set:
```
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start the full stack

```bash
docker compose up --build
```

This starts:
- **PostgreSQL/TimescaleDB** on port 5432
- **Redis** on port 6379
- **FastAPI backend** on port 8000
- **Next.js frontend** on port 3000

### 3. Open the app

Navigate to [http://localhost:3000](http://localhost:3000)

- Demo account: `demo@tradingcopilot.ai` / `demo1234`

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start with local postgres/redis running
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

All endpoints under `/api/v1`. JWT required via `Authorization: Bearer <token>`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/signals/generate` | Trigger multi-agent analysis |
| GET | `/api/v1/signals/{id}` | Retrieve signal details |
| GET | `/api/v1/portfolio/positions` | Current positions + P&L |
| POST | `/api/v1/portfolio/execute` | Execute a trade signal |
| GET | `/api/v1/agents/status` | Health of all 6 agents |
| GET | `/api/v1/backtest/{strategy}` | Run historical backtest |
| POST | `/api/v1/debate/trigger` | Force bull/bear debate |
| WS | `/ws/v1/signals/stream` | Real-time signal stream |

### Example: Generate a Signal

```bash
curl -X POST http://localhost:8000/api/v1/signals/generate \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "timeframe": "1D", "asset_class": "stocks"}'
```

### Sample Signal Response

```json
{
  "signal_id": "550e8400-e29b-41d4-a716-446655440000",
  "ticker": "AAPL",
  "direction": "LONG",
  "entry_price": 227.50,
  "stop_loss": 220.10,
  "take_profit_1": 238.60,
  "take_profit_2": 245.90,
  "take_profit_3": 257.20,
  "confidence_score": 78.4,
  "agent_votes": [
    {"agent": "FundamentalAnalyst", "direction": "LONG", "confidence": 82.0, "reasoning": "..."},
    {"agent": "TechnicalAnalyst", "direction": "LONG", "confidence": 75.0, "reasoning": "..."},
    {"agent": "SentimentAnalyst", "direction": "LONG", "confidence": 68.0, "reasoning": "..."},
    {"agent": "MacroAnalyst", "direction": "NEUTRAL", "confidence": 55.0, "reasoning": "..."}
  ],
  "reasoning_chain": ["EMA crossover bullish", "RSI not overbought", "Earnings beat last quarter"],
  "strategy_sources": ["price_momentum_3.1", "ema_crossover_3.11", "earnings_momentum_3.2"]
}
```

---

## Strategies Implemented

| Strategy | Ref | Asset Class |
|----------|-----|-------------|
| Price Momentum | 3.1 | Stocks |
| Earnings Momentum | 3.2 | Stocks |
| Value Factor | 3.3 | Stocks |
| Pairs Trading | 3.8 | Stocks |
| Mean Reversion (Clusters) | 3.9 | Stocks |
| EMA Crossover Systems | 3.11-3.13 | Stocks |
| Stat Arb (Markowitz) | 3.18 | Stocks |
| Sector Rotation | 4.1 | ETFs |
| VIX Basis | 7.2 | Volatility |
| FX Carry | 8.2 | Forex |
| ANN Crypto | 18.2 | Crypto |
| Sentiment (Naive Bayes) | 18.3 | Crypto |
| Macro Momentum | 19.2 | Global Macro |
| Announcement Trading | 19.5 | Global Macro |

---

## Pricing Tiers

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | Paper trading, 3 strategies, delayed data |
| Retail | $49/mo | All strategies, real-time data, 100 signals/day |
| Pro | $199/mo | API access, custom agent tuning, webhooks |
| Enterprise | $499/mo | Dedicated infra, white-label, SLA |

---

## Project Structure

```
ai-trading-copilot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── agents/              # 6 LangGraph agents
│   │   │   ├── base.py
│   │   │   ├── fundamental.py
│   │   │   ├── technical.py
│   │   │   ├── sentiment.py
│   │   │   ├── macro.py
│   │   │   ├── risk_manager.py
│   │   │   └── trader.py
│   │   ├── pipeline/
│   │   │   ├── graph.py         # LangGraph DAG
│   │   │   └── state.py         # Shared state TypedDict
│   │   ├── api/routes/          # REST endpoints
│   │   ├── strategies/          # Pure quant implementations
│   │   ├── models/              # Pydantic response models
│   │   ├── db/                  # SQLAlchemy + init SQL
│   │   ├── data/                # Market data service
│   │   └── auth/                # JWT + middleware
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/                     # Next.js App Router pages
│   │   ├── page.tsx             # Landing
│   │   ├── dashboard/           # Main trading terminal
│   │   ├── signals/             # Signal history
│   │   ├── portfolio/           # Portfolio tracker
│   │   ├── pricing/             # Subscription tiers
│   │   └── login/               # Auth
│   ├── components/              # React components
│   │   ├── TradingChart.tsx     # TradingView chart
│   │   ├── SignalCard.tsx       # Signal display
│   │   ├── AgentStatus.tsx      # Agent health indicators
│   │   └── Sidebar.tsx          # Navigation
│   ├── lib/
│   │   ├── api.ts               # API client + mock data
│   │   └── websocket.ts         # WS client hook
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Risk Management Rules

The Risk Manager agent enforces portfolio-level constraints from the spec:

- **Max drawdown**: 15% (circuit breaker stops new signals)
- **Position sizing**: Kelly criterion, half-Kelly default, max 5% per position
- **Sector concentration**: Max 30% per sector
- **Correlation limit**: New positions must have ρ < 0.7 with existing
- **Vol targeting**: 10% annualized portfolio volatility
- **Dollar neutrality**: Enforced for stat-arb strategies (3.18)

---

## Development Notes

- **Anti-repainting**: All signals generated on confirmed (closed) bars only, enforced at framework level
- **Mock mode**: If no API keys are set, the system runs with realistic mock data — fully functional for development and demos
- **Agent fallbacks**: If any analyst agent fails, the pipeline continues with remaining agents' outputs
- **Audit trail**: Every agent decision and debate transcript is logged to `agent_logs` table

---

*Built with Claude API · LangGraph · FastAPI · Next.js*
