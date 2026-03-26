# Phase 4 — Session Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-time Session Mode alongside the existing Research Mode, with 8 session-specific agents, a separate pipeline, 14 hard veto rules, and a dedicated frontend with session timer, P&L tracking, and coaching feedback.

**Architecture:** Session Mode is a parallel pipeline that shares auth, DB, providers, and profiles with Research Mode. It lives under `backend/app/agents/session/` with its own `SessionState` TypedDict and `session_graph.py`. The frontend adds a RESEARCH|SESSION mode toggle in the Navbar and a new `/session` page. Session agents inherit from the same `BaseAgent` class and use `model_router` for LLM calls.

**Tech Stack:** FastAPI, LangGraph (asyncio.gather), Anthropic Claude (via ModelRouter), Next.js 14, TypeScript, Tailwind CSS

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/app/agents/session/__init__.py` | Package exports for all 8 session agents |
| `backend/app/agents/session/timer.py` | `SessionTimer` — kill zone detection (NY Open, London, Asia, Tokyo) |
| `backend/app/agents/session/risk.py` | `SessionRisk` — real-time session drawdown tracking |
| `backend/app/agents/session/sentiment.py` | `SessionSentiment` — live news flow during active session |
| `backend/app/agents/session/technical.py` | `SessionTechnical` — intraday levels, VWAP, ORB, 1-5min chart focus |
| `backend/app/agents/session/order_flow.py` | `SessionOrderFlow` — real-time tape reading, bid/ask imbalance |
| `backend/app/agents/session/correlation.py` | `SessionCorrelation` — cross-asset session moves |
| `backend/app/agents/session/trader.py` | `SessionTrader` — session-context synthesis (Opus tier) |
| `backend/app/agents/session/coach.py` | `SessionCoach` — tilt detection, psychological monitoring |
| `backend/app/pipeline/session_state.py` | `SessionState` TypedDict — session-specific state fields |
| `backend/app/pipeline/session_graph.py` | Session pipeline: Timer → 5 parallel analysts → Trader → Risk → Coach |
| `backend/app/pipeline/session_risk_gate.py` | 14 session-specific hard veto rules (pure Python) |
| `backend/app/api/routes/session.py` | Session API: start, stop, analyze, status, history |

### Backend — Modified Files
| File | Change |
|------|--------|
| `backend/app/main.py` | Register session router |
| `backend/app/pipeline/state.py` | No change (SessionState is separate) |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/app/session/page.tsx` | Session Mode page — timer, compact signals, P&L, coach panel |
| `frontend/components/SessionTimer.tsx` | Kill zone countdown + session clock |
| `frontend/components/SessionSignalCard.tsx` | Compact signal cards optimized for fast execution |
| `frontend/components/CoachPanel.tsx` | Non-blocking coach feedback sidebar |
| `frontend/components/SessionPnL.tsx` | Running P&L tracker for session |

### Frontend — Modified Files
| File | Change |
|------|--------|
| `frontend/components/Navbar.tsx` | Add RESEARCH \| SESSION mode toggle |
| `frontend/lib/api.ts` | Add session API functions |
| `frontend/components/icons/GeoIcons.tsx` | Add session icon if needed |

---

## Task 1: SessionState TypedDict [COMPLETED]

**Files:**
- Create: `backend/app/pipeline/session_state.py`

- [ ] **Step 1: Create SessionState**

```python
# backend/app/pipeline/session_state.py
from typing import TypedDict, Any


class SessionState(TypedDict, total=False):
    # Session identity
    session_id: str
    user_id: str
    ticker: str
    asset_class: str
    strategy_profile: str

    # Session context
    session_start_time: str          # ISO timestamp
    session_duration_minutes: int    # elapsed
    kill_zone: str                   # "NY_OPEN" | "LONDON" | "ASIA" | "TOKYO" | "NONE"
    kill_zone_active: bool
    kill_zone_minutes_remaining: int

    # Market data (intraday focus)
    market_data: dict[str, Any]      # OHLCV + intraday indicators
    news_context: dict[str, Any]     # live headlines

    # Session agent outputs
    timer_analysis: dict[str, Any]
    session_technical: dict[str, Any]
    session_sentiment: dict[str, Any]
    session_order_flow: dict[str, Any]
    session_correlation: dict[str, Any]
    session_risk: dict[str, Any]
    session_trader_signal: dict[str, Any]
    coach_feedback: dict[str, Any]

    # Session risk gate
    session_risk_gate_result: dict[str, Any]

    # Session P&L tracking
    session_trades: list[dict[str, Any]]   # list of fills in this session
    session_pnl: float                     # running P&L in USD
    session_pnl_pct: float                 # running P&L in %
    session_high_water: float              # peak P&L in session
    session_drawdown_pct: float            # current drawdown from session peak
    session_trade_count: int               # number of trades this session

    # Pipeline metadata
    reasoning_chain: list[str]
    errors: list[str]
    analysis_count_this_session: int       # for session rate limiting
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.pipeline.session_state import SessionState; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/pipeline/session_state.py
git commit -m "feat(session): add SessionState TypedDict"
```

---

## Task 2: Session Timer Agent

**Files:**
- Create: `backend/app/agents/session/__init__.py`
- Create: `backend/app/agents/session/timer.py`

- [ ] **Step 1: Create package init**

```python
# backend/app/agents/session/__init__.py
from .timer import SessionTimer
from .risk import SessionRisk
from .sentiment import SessionSentiment
from .technical import SessionTechnical
from .order_flow import SessionOrderFlow
from .correlation import SessionCorrelation
from .trader import SessionTrader
from .coach import SessionCoach

__all__ = [
    "SessionTimer",
    "SessionRisk",
    "SessionSentiment",
    "SessionTechnical",
    "SessionOrderFlow",
    "SessionCorrelation",
    "SessionTrader",
    "SessionCoach",
]
```

Note: This will fail to import until all agent files exist. Create it now, verify later.

- [ ] **Step 2: Create SessionTimer agent**

```python
# backend/app/agents/session/timer.py
"""
SessionTimer — Kill zone detection and session timing.

Kill zones (UTC):
  - TOKYO:   00:00 - 03:00 UTC
  - LONDON:  07:00 - 10:00 UTC
  - NY_OPEN: 13:30 - 16:00 UTC
  - OVERLAP: 13:30 - 16:30 UTC (London + NY overlap)

Pure Python — no LLM needed. Provides session context to all other agents.
"""
from datetime import datetime, timezone
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState


# Kill zone windows in UTC (hour, minute) → (hour, minute)
KILL_ZONES = {
    "TOKYO":   ((0, 0),   (3, 0)),
    "LONDON":  ((7, 0),   (10, 0)),
    "NY_OPEN": ((13, 30), (16, 0)),
    "OVERLAP": ((13, 30), (16, 30)),
}


class SessionTimer(BaseAgent):
    """Determines which kill zone is active and session timing context."""

    def __init__(self):
        super().__init__("SessionTimer", tier="lightweight")

    async def analyze(self, state: SessionState) -> dict:
        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute

        active_zone = "NONE"
        minutes_remaining = 0

        for zone_name, ((sh, sm), (eh, em)) in KILL_ZONES.items():
            start_min = sh * 60 + sm
            end_min = eh * 60 + em
            if start_min <= current_minutes < end_min:
                active_zone = zone_name
                minutes_remaining = end_min - current_minutes
                break

        # Find next upcoming kill zone if none active
        next_zone = None
        next_zone_minutes = 9999
        if active_zone == "NONE":
            for zone_name, ((sh, sm), _) in KILL_ZONES.items():
                start_min = sh * 60 + sm
                delta = start_min - current_minutes
                if delta < 0:
                    delta += 1440  # wrap to next day
                if delta < next_zone_minutes:
                    next_zone_minutes = delta
                    next_zone = zone_name

        # Session elapsed time
        session_start = state.get("session_start_time", now.isoformat())
        try:
            start_dt = datetime.fromisoformat(session_start.replace("Z", "+00:00"))
            elapsed_min = int((now - start_dt).total_seconds() / 60)
        except (ValueError, TypeError):
            elapsed_min = 0

        return {
            "kill_zone": active_zone,
            "kill_zone_active": active_zone != "NONE",
            "kill_zone_minutes_remaining": minutes_remaining,
            "next_kill_zone": next_zone,
            "next_kill_zone_minutes": next_zone_minutes if next_zone else None,
            "session_elapsed_minutes": elapsed_min,
            "utc_time": now.strftime("%H:%M UTC"),
            "market_phase": self._get_market_phase(current_minutes),
        }

    @staticmethod
    def _get_market_phase(current_minutes: int) -> str:
        """Broad market phase classification."""
        if 0 <= current_minutes < 180:
            return "ASIA_SESSION"
        elif 180 <= current_minutes < 420:
            return "ASIA_CLOSE_EUROPE_PRE"
        elif 420 <= current_minutes < 600:
            return "LONDON_SESSION"
        elif 600 <= current_minutes < 810:
            return "LONDON_AFTERNOON"
        elif 810 <= current_minutes < 960:
            return "NY_SESSION"
        elif 960 <= current_minutes < 1200:
            return "NY_AFTERNOON"
        else:
            return "AFTER_HOURS"
```

- [ ] **Step 3: Verify syntax**

Run: `cd backend && python -m py_compile app/agents/session/timer.py && echo "OK"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/session/__init__.py backend/app/agents/session/timer.py
git commit -m "feat(session): add SessionTimer agent with kill zone detection"
```

---

## Task 3: Five Parallel Session Analysts

**Files:**
- Create: `backend/app/agents/session/technical.py`
- Create: `backend/app/agents/session/sentiment.py`
- Create: `backend/app/agents/session/order_flow.py`
- Create: `backend/app/agents/session/correlation.py`
- Create: `backend/app/agents/session/risk.py`

These follow the exact same pattern as Research Mode agents (inherit BaseAgent, implement `analyze()`, have `_mock_analysis()` fallback).

- [ ] **Step 1: Create SessionTechnical**

```python
# backend/app/agents/session/technical.py
"""
SessionTechnical — Intraday levels, VWAP, ORB, momentum on 1-15min timeframes.
Focuses on session-specific setups rather than daily/weekly analysis.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session-focused technical analyst for intraday trading.
You analyze 1-minute to 15-minute charts during active trading sessions.

Focus on:
- VWAP (Volume Weighted Average Price) — where is price relative to VWAP?
- Opening Range Breakout (ORB) — first 15-30 min range broken?
- Intraday support/resistance from today's price action
- Momentum (RSI 14 on 5min, MACD on 1min)
- Volume profile — where are high-volume nodes?
- Micro market structure — higher highs/lows or lower highs/lows?

Respond in JSON:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 0-100,
  "vwap_position": "ABOVE" | "BELOW" | "AT",
  "orb_status": "BREAKOUT_LONG" | "BREAKOUT_SHORT" | "INSIDE" | "NOT_SET",
  "intraday_trend": "UP" | "DOWN" | "RANGE",
  "key_levels": {"support": float, "resistance": float},
  "momentum_score": -100 to 100,
  "reasoning": "..."
}"""


class SessionTechnical(BaseAgent):
    def __init__(self):
        super().__init__("SessionTechnical", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})

        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')} "
            f"(remaining: {timer.get('kill_zone_minutes_remaining', '?')}min)\n"
            f"Market Phase: {timer.get('market_phase', 'UNKNOWN')}\n"
            f"Current Price: {market.get('close', 'N/A')}\n"
            f"VWAP: {market.get('vwap', 'N/A')}\n"
            f"Day High: {market.get('high', 'N/A')} | Day Low: {market.get('low', 'N/A')}\n"
            f"Volume: {market.get('volume', 'N/A')}\n"
            f"RSI(14): {market.get('rsi_14', 'N/A')}\n"
            f"ATR: {market.get('atr', 'N/A')}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=800)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_tech".encode()).hexdigest()[:8], 16)
        conf = 45 + (seed % 40)
        direction = ["LONG", "SHORT", "NEUTRAL"][seed % 3]
        price = state.get("market_data", {}).get("close", 100)
        return {
            "direction": direction,
            "confidence": conf,
            "vwap_position": "ABOVE" if seed % 2 == 0 else "BELOW",
            "orb_status": "INSIDE",
            "intraday_trend": "RANGE",
            "key_levels": {"support": round(price * 0.995, 2), "resistance": round(price * 1.005, 2)},
            "momentum_score": (seed % 60) - 30,
            "reasoning": f"Mock intraday analysis for {ticker}.",
        }
```

- [ ] **Step 2: Create SessionSentiment**

```python
# backend/app/agents/session/sentiment.py
"""
SessionSentiment — Live news flow during active trading session.
Focuses on real-time headlines that could move price in the next 5-30 minutes.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session sentiment analyst monitoring live news for intraday impact.

Focus on:
- Breaking headlines in the last 30 minutes
- Social media sentiment shifts (Twitter/X, StockTwits)
- Options flow anomalies (unusual call/put activity)
- Sector-wide moves that could affect this ticker
- Analyst upgrades/downgrades issued today

Rate urgency: FLASH (trade now), DEVELOPING (watch), BACKGROUND (no immediate impact).

Respond in JSON:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 0-100,
  "urgency": "FLASH" | "DEVELOPING" | "BACKGROUND",
  "headline_sentiment": -1.0 to 1.0,
  "key_headlines": ["..."],
  "options_flow": "BULLISH" | "BEARISH" | "NEUTRAL" | "UNKNOWN",
  "reasoning": "..."
}"""


class SessionSentiment(BaseAgent):
    def __init__(self):
        super().__init__("SessionSentiment", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        news = state.get("news_context", {})
        timer = state.get("timer_analysis", {})
        ticker = state.get("ticker", "UNKNOWN")

        headlines = news.get("ticker_headlines", [])[:10]
        market_headlines = news.get("market_headlines", [])[:5]

        user_msg = (
            f"Ticker: {ticker}\n"
            f"Session Phase: {timer.get('market_phase', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')}\n"
            f"\nTicker-specific headlines:\n"
            + "\n".join(f"- {h}" for h in headlines) + "\n"
            f"\nBroad market headlines:\n"
            + "\n".join(f"- {h}" for h in market_headlines) + "\n"
            f"\nSentiment stats: {news.get('sentiment_stats', {})}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_sent".encode()).hexdigest()[:8], 16)
        return {
            "direction": "NEUTRAL",
            "confidence": 40 + (seed % 25),
            "urgency": "BACKGROUND",
            "headline_sentiment": round((seed % 200 - 100) / 100, 2),
            "key_headlines": [],
            "options_flow": "UNKNOWN",
            "reasoning": f"Mock session sentiment for {ticker} — no live headlines available.",
        }
```

- [ ] **Step 3: Create SessionOrderFlow**

```python
# backend/app/agents/session/order_flow.py
"""
SessionOrderFlow — Real-time tape reading during active session.
Focuses on order book depth, large block prints, and aggressor side.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session order flow analyst reading the tape in real-time.

Focus on:
- Bid/ask imbalance at top of book
- Large block trades (> 3x average size)
- Aggressor side (who is lifting offers vs hitting bids)
- Dark pool prints vs lit market
- VPIN (Volume-synchronized Probability of Informed Trading)
- Absorption patterns (large resting orders not moving)

Respond in JSON:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 0-100,
  "bid_ask_imbalance": -1.0 to 1.0,
  "aggressor_side": "BUYERS" | "SELLERS" | "BALANCED",
  "block_trade_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "tape_speed": "FAST" | "NORMAL" | "SLOW",
  "absorption_detected": bool,
  "reasoning": "..."
}"""


class SessionOrderFlow(BaseAgent):
    def __init__(self):
        super().__init__("SessionOrderFlow", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})

        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')}\n"
            f"Price: {market.get('close', 'N/A')}\n"
            f"Volume: {market.get('volume', 'N/A')}\n"
            f"Avg Volume: {market.get('avg_volume_30d', 'N/A')}\n"
            f"Bid: {market.get('bid', 'N/A')} | Ask: {market.get('ask', 'N/A')}\n"
            f"Day range: {market.get('low', 'N/A')} - {market.get('high', 'N/A')}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_flow".encode()).hexdigest()[:8], 16)
        return {
            "direction": ["LONG", "SHORT", "NEUTRAL"][seed % 3],
            "confidence": 40 + (seed % 35),
            "bid_ask_imbalance": round((seed % 200 - 100) / 100, 2),
            "aggressor_side": "BALANCED",
            "block_trade_bias": "NEUTRAL",
            "tape_speed": "NORMAL",
            "absorption_detected": False,
            "reasoning": f"Mock session order flow for {ticker}.",
        }
```

- [ ] **Step 4: Create SessionCorrelation**

```python
# backend/app/agents/session/correlation.py
"""
SessionCorrelation — Cross-asset session moves.
Monitors correlated instruments for confirmation or divergence signals.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session correlation analyst tracking cross-asset moves in real-time.

Focus on:
- Sector ETF vs individual stock divergence
- Index futures (ES, NQ, YM) direction
- VIX intraday moves (fear gauge)
- DXY (dollar) impact on the asset
- Treasury yields intraday
- Correlated instruments moving first (leading indicators)

Respond in JSON:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 0-100,
  "sector_alignment": "ALIGNED" | "DIVERGING" | "MIXED",
  "index_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "vix_trend_intraday": "RISING" | "FALLING" | "FLAT",
  "dxy_impact": "TAILWIND" | "HEADWIND" | "NEUTRAL",
  "leading_signals": ["..."],
  "reasoning": "..."
}"""


class SessionCorrelation(BaseAgent):
    def __init__(self):
        super().__init__("SessionCorrelation", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})

        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Asset Class: {state.get('asset_class', 'equity')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')}\n"
            f"Market Phase: {timer.get('market_phase', 'UNKNOWN')}\n"
            f"Price: {market.get('close', 'N/A')}\n"
            f"VIX: {market.get('vix', 'N/A')}\n"
            f"DXY: {market.get('dxy', 'N/A')}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_corr".encode()).hexdigest()[:8], 16)
        return {
            "direction": "NEUTRAL",
            "confidence": 35 + (seed % 30),
            "sector_alignment": "MIXED",
            "index_bias": "NEUTRAL",
            "vix_trend_intraday": "FLAT",
            "dxy_impact": "NEUTRAL",
            "leading_signals": [],
            "reasoning": f"Mock session correlation for {ticker}.",
        }
```

- [ ] **Step 5: Create SessionRisk**

```python
# backend/app/agents/session/risk.py
"""
SessionRisk — Real-time session drawdown and position risk tracking.
Monitors P&L, max loss limits, and position exposure within the session.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session risk manager monitoring real-time position risk.

Focus on:
- Session P&L relative to session max loss limit
- Position size relative to account
- Unrealized drawdown from session high
- Time-based risk (approaching kill zone close)
- Number of trades this session (overtrading detection)
- Correlation of open positions

Respond in JSON:
{
  "risk_level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
  "max_position_pct": 0.5 to 5.0,
  "session_drawdown_warning": bool,
  "overtrading_flag": bool,
  "time_risk": "OK" | "WINDING_DOWN" | "CLOSE_POSITIONS",
  "recommended_action": "CONTINUE" | "REDUCE" | "STOP_TRADING",
  "reasoning": "..."
}"""


class SessionRisk(BaseAgent):
    def __init__(self):
        super().__init__("SessionRisk", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        pnl = state.get("session_pnl", 0)
        pnl_pct = state.get("session_pnl_pct", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        trade_count = state.get("session_trade_count", 0)
        kz_remaining = timer.get("kill_zone_minutes_remaining", 999)

        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Session P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"Session Drawdown: {drawdown:.2f}%\n"
            f"Trade Count This Session: {trade_count}\n"
            f"Kill Zone Remaining: {kz_remaining}min\n"
            f"Kill Zone Active: {timer.get('kill_zone_active', False)}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=500)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        drawdown = state.get("session_drawdown_pct", 0)
        trade_count = state.get("session_trade_count", 0)
        risk_level = "LOW"
        if drawdown > 3:
            risk_level = "HIGH"
        elif drawdown > 1.5:
            risk_level = "MODERATE"
        return {
            "risk_level": risk_level,
            "max_position_pct": 2.0 if risk_level == "LOW" else 1.0,
            "session_drawdown_warning": drawdown > 2.0,
            "overtrading_flag": trade_count > 8,
            "time_risk": "OK",
            "recommended_action": "CONTINUE" if risk_level in ("LOW", "MODERATE") else "REDUCE",
            "reasoning": f"Mock session risk — drawdown {drawdown:.1f}%, {trade_count} trades.",
        }
```

- [ ] **Step 6: Verify all 5 agents compile**

Run: `cd backend && python -m py_compile app/agents/session/technical.py && python -m py_compile app/agents/session/sentiment.py && python -m py_compile app/agents/session/order_flow.py && python -m py_compile app/agents/session/correlation.py && python -m py_compile app/agents/session/risk.py && echo "ALL OK"`
Expected: `ALL OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/session/technical.py backend/app/agents/session/sentiment.py backend/app/agents/session/order_flow.py backend/app/agents/session/correlation.py backend/app/agents/session/risk.py
git commit -m "feat(session): add 5 parallel session analysts"
```

---

## Task 4: Session Trader [COMPLETED] + Coach Agents

**Files:**
- Create: `backend/app/agents/session/trader.py`
- Create: `backend/app/agents/session/coach.py`

- [ ] **Step 1: Create SessionTrader (Opus tier)**

```python
# backend/app/agents/session/trader.py
"""
SessionTrader — Session-context synthesis agent (Opus tier).
Takes all 5 session analyst outputs + timer context and produces a session trade signal.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

BASE_SYSTEM_PROMPT = """You are the Session Trader for QuantNeuralEdge. You synthesize
real-time session analysis from 5 specialist agents into actionable intraday trade decisions.

You operate in KILL ZONE windows where institutional order flow is highest.
Your decisions must be fast, precise, and risk-aware.

Input agents:
1. SessionTechnical — intraday levels, VWAP, ORB, momentum
2. SessionSentiment — live news, options flow, urgency
3. SessionOrderFlow — tape reading, bid/ask imbalance, blocks
4. SessionCorrelation — cross-asset confirmation/divergence
5. SessionRisk — drawdown, position limits, time risk

Rules:
- If SessionRisk says STOP_TRADING → direction must be NEUTRAL
- If kill zone is closing (< 10 min) → tighten stops, no new entries
- If 3+ agents disagree on direction → NEUTRAL with reasoning
- Entry must be within 0.3% of current price (session precision)
- Always provide SCALP levels (tight) — no swing levels in session mode

Respond in JSON:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": 0-100,
  "entry": float,
  "stop_loss": float,
  "take_profit_1": float,
  "take_profit_2": float,
  "position_size_pct": 0.5-3.0,
  "trade_type": "SCALP" | "INTRADAY" | "NO_TRADE",
  "urgency": "EXECUTE_NOW" | "WAIT_FOR_LEVEL" | "NO_TRADE",
  "agent_agreement": 0-5,
  "reasoning": "...",
  "risk_reward_ratio": float
}"""


class SessionTrader(BaseAgent):
    def __init__(self):
        super().__init__("SessionTrader", tier="premium")

    def _build_system_prompt(self, profile_slug: str) -> str:
        try:
            from app.profiles.manager import profile_manager
            profile = profile_manager.get_profile(profile_slug)
            if profile.prompt_block:
                return f"{BASE_SYSTEM_PROMPT}\n\n=== STRATEGY PROFILE: {profile.name.upper()} ===\n{profile.prompt_block}"
        except Exception:
            pass
        return BASE_SYSTEM_PROMPT

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        tech = state.get("session_technical", {})
        sent = state.get("session_sentiment", {})
        flow = state.get("session_order_flow", {})
        corr = state.get("session_correlation", {})
        risk = state.get("session_risk", {})
        market = state.get("market_data", {})
        profile = state.get("strategy_profile", "balanced")

        user_msg = (
            f"=== SESSION CONTEXT ===\n"
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')} "
            f"({timer.get('kill_zone_minutes_remaining', '?')}min remaining)\n"
            f"Market Phase: {timer.get('market_phase', 'UNKNOWN')}\n"
            f"Session P&L: {state.get('session_pnl_pct', 0):+.2f}%\n"
            f"Trades This Session: {state.get('session_trade_count', 0)}\n"
            f"\nCurrent Price: {market.get('close', 'N/A')}\n"
            f"ATR: {market.get('atr', 'N/A')}\n"
            f"\n=== TECHNICAL ===\n{json.dumps(tech, indent=1, default=str)}\n"
            f"\n=== SENTIMENT ===\n{json.dumps(sent, indent=1, default=str)}\n"
            f"\n=== ORDER FLOW ===\n{json.dumps(flow, indent=1, default=str)}\n"
            f"\n=== CORRELATION ===\n{json.dumps(corr, indent=1, default=str)}\n"
            f"\n=== SESSION RISK ===\n{json.dumps(risk, indent=1, default=str)}\n"
        )

        system = self._build_system_prompt(profile)

        try:
            raw = await self._call_llm(system, user_msg, max_tokens=1200)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            # Validate entry is near current price
            price = market.get("close", 0)
            entry = data.get("entry", price)
            if price and abs(entry - price) / price > 0.003:
                data["entry"] = price
            return data
        except Exception:
            return self._mock_signal(state)

    def _mock_signal(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_trader".encode()).hexdigest()[:8], 16)
        price = state.get("market_data", {}).get("close", 100)
        atr = state.get("market_data", {}).get("atr", price * 0.01)
        direction = ["LONG", "SHORT", "NEUTRAL"][seed % 3]
        sl = round(price - atr * 0.8, 2) if direction == "LONG" else round(price + atr * 0.8, 2)
        tp1 = round(price + atr * 1.0, 2) if direction == "LONG" else round(price - atr * 1.0, 2)
        tp2 = round(price + atr * 1.8, 2) if direction == "LONG" else round(price - atr * 1.8, 2)
        return {
            "direction": direction,
            "confidence": 40 + (seed % 35),
            "entry": price,
            "stop_loss": sl,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "position_size_pct": 1.5,
            "trade_type": "SCALP" if direction != "NEUTRAL" else "NO_TRADE",
            "urgency": "WAIT_FOR_LEVEL" if direction != "NEUTRAL" else "NO_TRADE",
            "agent_agreement": 3,
            "reasoning": f"Mock session signal for {ticker}.",
            "risk_reward_ratio": 1.8,
        }
```

- [ ] **Step 2: Create SessionCoach**

```python
# backend/app/agents/session/coach.py
"""
SessionCoach — Psychological monitoring, tilt detection, and behavioral coaching.
Non-blocking overlay — provides feedback but does not block trades.
"""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a trading psychology coach monitoring a live trading session.

Your job is to detect emotional and behavioral patterns that lead to poor decisions:

TILT INDICATORS:
- Revenge trading after a loss (quick re-entry, larger size)
- Overtrading (too many trades in short time)
- FOMO (chasing price after missing a move)
- Hesitation (not executing on clear setups)
- Position size escalation after losses
- Trading outside kill zone (low-probability hours)

POSITIVE REINFORCEMENT:
- Acknowledge good discipline (sitting out unclear setups)
- Praise proper position sizing
- Note when trader follows their plan

Be direct but supportive. Speak like a mentor, not a therapist.
Max 2-3 sentences. No fluff.

Respond in JSON:
{
  "tilt_detected": bool,
  "tilt_type": "REVENGE" | "FOMO" | "OVERTRADING" | "HESITATION" | "ESCALATION" | "OFF_HOURS" | "NONE",
  "tilt_severity": 0-10,
  "message": "...",
  "recommendation": "CONTINUE" | "PAUSE_5MIN" | "REDUCE_SIZE" | "END_SESSION",
  "positive_note": "..." | null
}"""


class SessionCoach(BaseAgent):
    def __init__(self):
        super().__init__("SessionCoach", tier="lightweight")

    async def analyze(self, state: SessionState) -> dict:
        timer = state.get("timer_analysis", {})
        trade_count = state.get("session_trade_count", 0)
        pnl = state.get("session_pnl", 0)
        pnl_pct = state.get("session_pnl_pct", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        trades = state.get("session_trades", [])
        elapsed = timer.get("session_elapsed_minutes", 0)
        kz_active = timer.get("kill_zone_active", False)

        # Build trade history summary for coach
        recent_trades = trades[-5:] if trades else []
        trade_summary = ""
        for t in recent_trades:
            trade_summary += f"  {t.get('direction','?')} {t.get('ticker','?')} → {t.get('result','?')} ({t.get('pnl', 0):+.2f})\n"

        user_msg = (
            f"=== SESSION STATUS ===\n"
            f"Session Duration: {elapsed}min\n"
            f"Kill Zone Active: {kz_active}\n"
            f"Trade Count: {trade_count}\n"
            f"Session P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
            f"Session Drawdown: {drawdown:.2f}%\n"
            f"\n=== RECENT TRADES ===\n{trade_summary or '  No trades yet.'}\n"
        )

        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=400)
            data = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            return data
        except Exception:
            return self._mock_coaching(state)

    def _mock_coaching(self, state: SessionState) -> dict:
        trade_count = state.get("session_trade_count", 0)
        drawdown = state.get("session_drawdown_pct", 0)
        kz_active = state.get("timer_analysis", {}).get("kill_zone_active", False)

        tilt = "NONE"
        severity = 0
        message = "Session looking good. Stay disciplined."
        recommendation = "CONTINUE"
        positive = None

        if trade_count > 8:
            tilt = "OVERTRADING"
            severity = 6
            message = f"{trade_count} trades this session. Slow down — quality over quantity."
            recommendation = "PAUSE_5MIN"
        elif drawdown > 3:
            tilt = "REVENGE"
            severity = 7
            message = f"Down {drawdown:.1f}% — don't chase it back. Take a break."
            recommendation = "REDUCE_SIZE"
        elif not kz_active:
            tilt = "OFF_HOURS"
            severity = 4
            message = "No kill zone active. Low-probability environment. Consider waiting."
            recommendation = "PAUSE_5MIN"
        elif trade_count == 0:
            positive = "Patience is a position. Wait for the setup."

        return {
            "tilt_detected": tilt != "NONE",
            "tilt_type": tilt,
            "tilt_severity": severity,
            "message": message,
            "recommendation": recommendation,
            "positive_note": positive,
        }
```

- [ ] **Step 3: Verify compilation**

Run: `cd backend && python -m py_compile app/agents/session/trader.py && python -m py_compile app/agents/session/coach.py && echo "OK"`
Expected: `OK`

- [ ] **Step 4: Verify full package import**

Run: `cd backend && python -c "from app.agents.session import SessionTimer, SessionTrader, SessionCoach; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/session/trader.py backend/app/agents/session/coach.py
git commit -m "feat(session): add SessionTrader (Opus) and SessionCoach agents"
```

---

## Task 5: Session Risk Gate [COMPLETED] (14 Rules)

**Files:**
- Create: `backend/app/pipeline/session_risk_gate.py`

- [ ] **Step 1: Create session risk gate**

```python
# backend/app/pipeline/session_risk_gate.py
"""
Session Risk Gate — 14 hard veto rules for Session Mode.

Pure Python. No AI. Cannot be overridden by agent reasoning.
Separate from Research Mode risk gate (different risk profile for intraday).
"""
from datetime import datetime, timezone


def run_session_risk_gate(state: dict) -> dict:
    """
    Evaluate 14 session-specific hard veto rules.

    Returns:
        {
            "passed": bool,
            "triggered_rules": [...],
            "mode": "NORMAL" | "COOLDOWN" | "BLOCKED",
        }
    """
    timer = state.get("timer_analysis", {})
    market = state.get("market_data", {})
    risk = state.get("session_risk", {})
    trader = state.get("session_trader_signal", {})

    triggered = []
    mode = "NORMAL"

    # ── Rule 1: No kill zone active → BLOCK new entries ──────────────────
    kz_active = timer.get("kill_zone_active", False)
    direction = trader.get("direction", "NEUTRAL")
    if not kz_active and direction != "NEUTRAL":
        triggered.append({
            "rule": 1, "name": "no_kill_zone",
            "reason": "No kill zone active — new entries blocked outside institutional hours",
        })

    # ── Rule 2: Kill zone closing (< 5 min remaining) → BLOCK new entries ─
    kz_remaining = timer.get("kill_zone_minutes_remaining", 999)
    if kz_active and kz_remaining < 5 and direction != "NEUTRAL":
        triggered.append({
            "rule": 2, "name": "kill_zone_closing",
            "reason": f"Kill zone closing in {kz_remaining}min — no new entries",
        })

    # ── Rule 3: Session drawdown > 3% → BLOCKED ─────────────────────────
    session_dd = state.get("session_drawdown_pct", 0)
    if session_dd > 3:
        triggered.append({
            "rule": 3, "name": "session_max_drawdown",
            "reason": f"Session drawdown {session_dd:.1f}% exceeds 3% limit — session should end",
        })

    # ── Rule 4: Session drawdown > 1.5% → COOLDOWN (reduce size) ────────
    if 1.5 < session_dd <= 3:
        triggered.append({
            "rule": 4, "name": "session_drawdown_warning",
            "reason": f"Session drawdown {session_dd:.1f}% — entering cooldown, halve position sizes",
        })
        if mode == "NORMAL":
            mode = "COOLDOWN"

    # ── Rule 5: More than 10 trades in session → BLOCK ──────────────────
    trade_count = state.get("session_trade_count", 0)
    if trade_count >= 10:
        triggered.append({
            "rule": 5, "name": "overtrading",
            "reason": f"{trade_count} trades this session — overtrading limit reached",
        })

    # ── Rule 6: More than 5 trades in session → COOLDOWN ────────────────
    if 5 < trade_count < 10:
        triggered.append({
            "rule": 6, "name": "overtrading_warning",
            "reason": f"{trade_count} trades — approaching overtrading limit, be selective",
        })
        if mode == "NORMAL":
            mode = "COOLDOWN"

    # ── Rule 7: VIX > 35 (session threshold lower than research) → BLOCK ─
    vix = market.get("vix", 0)
    if vix > 35:
        triggered.append({
            "rule": 7, "name": "session_extreme_vix",
            "reason": f"VIX at {vix:.1f} — too volatile for intraday entries",
        })

    # ── Rule 8: Session Risk says STOP_TRADING → BLOCK ──────────────────
    if risk.get("recommended_action") == "STOP_TRADING":
        triggered.append({
            "rule": 8, "name": "risk_agent_stop",
            "reason": "Session Risk agent recommends stopping",
        })

    # ── Rule 9: Coach tilt severity >= 7 → BLOCK ────────────────────────
    coach = state.get("coach_feedback", {})
    tilt_severity = coach.get("tilt_severity", 0)
    if tilt_severity >= 7:
        triggered.append({
            "rule": 9, "name": "tilt_detected",
            "reason": f"Coach detected tilt (severity {tilt_severity}/10) — {coach.get('tilt_type', 'UNKNOWN')}",
        })

    # ── Rule 10: Coach recommends END_SESSION → BLOCK ───────────────────
    if coach.get("recommendation") == "END_SESSION":
        triggered.append({
            "rule": 10, "name": "coach_end_session",
            "reason": "Coach recommends ending session",
        })

    # ── Rule 11: Session duration > 4 hours → BLOCK ─────────────────────
    elapsed = timer.get("session_elapsed_minutes", 0)
    if elapsed > 240:
        triggered.append({
            "rule": 11, "name": "session_too_long",
            "reason": f"Session running {elapsed}min (>4 hours) — fatigue risk",
        })

    # ── Rule 12: 3 consecutive losses → COOLDOWN ────────────────────────
    trades = state.get("session_trades", [])
    if len(trades) >= 3:
        last_3 = trades[-3:]
        if all(t.get("result") == "LOSS" for t in last_3):
            triggered.append({
                "rule": 12, "name": "consecutive_losses",
                "reason": "3 consecutive losses — take a break before next trade",
            })
            if mode == "NORMAL":
                mode = "COOLDOWN"

    # ── Rule 13: Position size > 3% in COOLDOWN mode → BLOCK ────────────
    pos_size = trader.get("position_size_pct", 0)
    if mode == "COOLDOWN" and pos_size > 1.5:
        triggered.append({
            "rule": 13, "name": "cooldown_size_limit",
            "reason": f"Position size {pos_size:.1f}% too large for cooldown mode (max 1.5%)",
        })

    # ── Rule 14: Agent agreement < 2/5 → BLOCK ──────────────────────────
    agent_agreement = trader.get("agent_agreement", 5)
    if agent_agreement < 2 and direction != "NEUTRAL":
        triggered.append({
            "rule": 14, "name": "low_session_consensus",
            "reason": f"Only {agent_agreement}/5 session agents agree — insufficient consensus",
        })

    # ── Determine final gate status ──────────────────────────────────────
    hard_block_rules = {1, 2, 3, 5, 7, 8, 9, 10, 11, 14}
    hard_blocks = [t for t in triggered if t["rule"] in hard_block_rules]

    if hard_blocks:
        mode = "BLOCKED"

    passed = mode not in ("BLOCKED",)

    return {
        "passed": passed,
        "triggered_rules": triggered,
        "mode": mode,
        "rules_checked": 14,
        "hard_blocks": len(hard_blocks),
        "warnings": len(triggered) - len(hard_blocks),
    }
```

- [ ] **Step 2: Verify syntax + basic test**

Run: `cd backend && python -c "
from app.pipeline.session_risk_gate import run_session_risk_gate
# Empty state should pass
r = run_session_risk_gate({})
print(f'Empty: passed={r[\"passed\"]}, mode={r[\"mode\"]}')
# Kill zone not active should block
r2 = run_session_risk_gate({'timer_analysis': {'kill_zone_active': False}, 'session_trader_signal': {'direction': 'LONG'}})
print(f'No KZ: passed={r2[\"passed\"]}, rules={[t[\"name\"] for t in r2[\"triggered_rules\"]]}')
"`
Expected: Empty passes, no-KZ blocks with `no_kill_zone`

- [ ] **Step 3: Commit**

```bash
git add backend/app/pipeline/session_risk_gate.py
git commit -m "feat(session): add 14-rule session risk gate (pure Python)"
```

---

## Task 6: Session Pipeline [COMPLETED] Graph

**Files:**
- Create: `backend/app/pipeline/session_graph.py`

- [ ] **Step 1: Create session pipeline**

```python
# backend/app/pipeline/session_graph.py
"""
Session Mode Pipeline — LangGraph-style async pipeline for intraday trading.

Flow:
  Timer → 5 parallel analysts → SessionTrader (Opus) → SessionRisk → Coach → Risk Gate → Output
"""
import asyncio
import time
import structlog
from datetime import datetime, timezone

from app.pipeline.session_state import SessionState
from app.pipeline.session_risk_gate import run_session_risk_gate
from app.agents.session.timer import SessionTimer
from app.agents.session.technical import SessionTechnical
from app.agents.session.sentiment import SessionSentiment
from app.agents.session.order_flow import SessionOrderFlow
from app.agents.session.correlation import SessionCorrelation
from app.agents.session.risk import SessionRisk
from app.agents.session.trader import SessionTrader
from app.agents.session.coach import SessionCoach

log = structlog.get_logger()

# Singletons
_timer = SessionTimer()
_technical = SessionTechnical()
_sentiment = SessionSentiment()
_order_flow = SessionOrderFlow()
_correlation = SessionCorrelation()
_risk = SessionRisk()
_trader = SessionTrader()
_coach = SessionCoach()


async def _safe(coro, name: str, state: SessionState) -> tuple[str, dict]:
    """Run an agent coroutine safely, catching exceptions."""
    try:
        result = await coro
        return name, result
    except Exception as e:
        log.error("session_agent_error", agent=name, error=str(e))
        return name, {"error": str(e), "direction": "NEUTRAL", "confidence": 0}


async def run_session_pipeline(
    ticker: str,
    market_data: dict,
    news_context: dict | None = None,
    session_state: dict | None = None,
    profile: str = "balanced",
) -> dict:
    """
    Run the full session analysis pipeline.

    Args:
        ticker: Symbol to analyze
        market_data: Current OHLCV + indicators
        news_context: Live headlines (optional)
        session_state: Existing session state (P&L, trades, etc.)
        profile: Strategy profile slug

    Returns:
        Complete session analysis result dict
    """
    t0 = time.time()
    ss = session_state or {}

    state: SessionState = {
        "ticker": ticker,
        "asset_class": market_data.get("asset_class", "equity"),
        "strategy_profile": profile,
        "market_data": market_data,
        "news_context": news_context or {},
        # Carry forward session state
        "session_id": ss.get("session_id", ""),
        "session_start_time": ss.get("session_start_time", datetime.now(timezone.utc).isoformat()),
        "session_pnl": ss.get("session_pnl", 0),
        "session_pnl_pct": ss.get("session_pnl_pct", 0),
        "session_high_water": ss.get("session_high_water", 0),
        "session_drawdown_pct": ss.get("session_drawdown_pct", 0),
        "session_trade_count": ss.get("session_trade_count", 0),
        "session_trades": ss.get("session_trades", []),
        "analysis_count_this_session": ss.get("analysis_count_this_session", 0) + 1,
        "reasoning_chain": [],
        "errors": [],
    }

    # ── Stage 1: Timer (pure Python, instant) ───────────────────────────
    timer_result = await _timer.analyze(state)
    state["timer_analysis"] = timer_result
    state["reasoning_chain"].append(
        f"[Timer] Kill zone: {timer_result.get('kill_zone', 'NONE')}, "
        f"Phase: {timer_result.get('market_phase', 'UNKNOWN')}"
    )

    # ── Stage 2: 5 parallel session analysts ─────────────────────────────
    results = await asyncio.gather(
        _safe(_technical.analyze(state), "session_technical", state),
        _safe(_sentiment.analyze(state), "session_sentiment", state),
        _safe(_order_flow.analyze(state), "session_order_flow", state),
        _safe(_correlation.analyze(state), "session_correlation", state),
        _safe(_risk.analyze(state), "session_risk", state),
    )

    for key, result in results:
        state[key] = result
        direction = result.get("direction", "NEUTRAL")
        confidence = result.get("confidence", 0)
        state["reasoning_chain"].append(f"[{key}] {direction} ({confidence}%)")

    # ── Stage 3: Session Trader synthesis (Opus) ─────────────────────────
    trader_result = await _trader.analyze(state)
    state["session_trader_signal"] = trader_result
    state["reasoning_chain"].append(
        f"[SessionTrader] {trader_result.get('direction', 'NEUTRAL')} "
        f"({trader_result.get('confidence', 0)}%) — "
        f"{trader_result.get('trade_type', 'NO_TRADE')}"
    )

    # ── Stage 4: Coach overlay (non-blocking) ────────────────────────────
    coach_result = await _coach.analyze(state)
    state["coach_feedback"] = coach_result
    if coach_result.get("tilt_detected"):
        state["reasoning_chain"].append(
            f"[Coach] TILT: {coach_result.get('tilt_type')} "
            f"(severity {coach_result.get('tilt_severity')}/10)"
        )

    # ── Stage 5: Session Risk Gate (14 rules, pure Python) ───────────────
    gate_result = run_session_risk_gate(state)
    state["session_risk_gate_result"] = gate_result
    if not gate_result["passed"]:
        state["reasoning_chain"].append(
            f"[RiskGate] BLOCKED — {', '.join(r['name'] for r in gate_result['triggered_rules'][:3])}"
        )

    # ── Build final output ───────────────────────────────────────────────
    elapsed_ms = int((time.time() - t0) * 1000)

    signal = trader_result.copy()
    signal.update({
        "ticker": ticker,
        "mode": "SESSION",
        "strategy_profile": profile,
        "kill_zone": timer_result.get("kill_zone", "NONE"),
        "kill_zone_active": timer_result.get("kill_zone_active", False),
        "kill_zone_minutes_remaining": timer_result.get("kill_zone_minutes_remaining", 0),
        "market_phase": timer_result.get("market_phase", "UNKNOWN"),
        "risk_gate_passed": gate_result["passed"],
        "risk_gate_mode": gate_result["mode"],
        "risk_gate_rules": gate_result["triggered_rules"],
        "coach": coach_result,
        "session_risk": state.get("session_risk", {}),
        "agent_votes": _build_agent_votes(state),
        "reasoning_chain": state["reasoning_chain"],
        "pipeline_latency_ms": elapsed_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Override direction if blocked
    if not gate_result["passed"]:
        signal["direction"] = "NEUTRAL"
        signal["trade_type"] = "NO_TRADE"
        signal["urgency"] = "NO_TRADE"

    return signal


def _build_agent_votes(state: SessionState) -> list[dict]:
    """Extract direction + confidence from each session agent for frontend display."""
    votes = []
    for key, label in [
        ("session_technical", "Technical"),
        ("session_sentiment", "Sentiment"),
        ("session_order_flow", "OrderFlow"),
        ("session_correlation", "Correlation"),
        ("session_risk", "Risk"),
    ]:
        data = state.get(key, {})
        votes.append({
            "agent": label,
            "direction": data.get("direction", "NEUTRAL"),
            "confidence": data.get("confidence", 0),
        })
    return votes
```

- [ ] **Step 2: Verify syntax**

Run: `cd backend && python -m py_compile app/pipeline/session_graph.py && echo "OK"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/pipeline/session_graph.py
git commit -m "feat(session): add session pipeline graph (Timer → 5 analysts → Trader → Coach → RiskGate)"
```

---

## Task 7: Session API [COMPLETED] Routes

**Files:**
- Create: `backend/app/api/routes/session.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create session API routes**

```python
# backend/app/api/routes/session.py
"""
Session Mode API — start/stop sessions, run session analysis, get session status.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.api.routes.signals import get_current_user, get_market_data
from app.services.news_context import get_news_context
from app.pipeline.session_graph import run_session_pipeline

router = APIRouter(prefix="/api/v1/session", tags=["session"])

# In-memory session store (per-user active session)
# In production this would be Redis or DB-backed
_active_sessions: dict[str, dict] = {}


class StartSessionRequest(BaseModel):
    ticker: str
    profile: str = "balanced"


class SessionAnalyzeRequest(BaseModel):
    ticker: str | None = None  # defaults to session ticker


# ── POST /start — Start a new session ─────────────────────────────────────
@router.post("/start")
async def start_session(req: StartSessionRequest, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)

    # Check tier — Session Mode requires Pro or higher
    tier = getattr(user, "tier", "free")
    if tier not in ("pro", "enterprise", "admin"):
        raise HTTPException(status_code=403, detail="Session Mode requires Pro plan or higher")

    # End any existing session
    if user_id in _active_sessions:
        _active_sessions[user_id]["ended_at"] = datetime.now(timezone.utc).isoformat()

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    session = {
        "session_id": session_id,
        "user_id": user_id,
        "ticker": req.ticker.upper(),
        "profile": req.profile,
        "session_start_time": now,
        "session_pnl": 0,
        "session_pnl_pct": 0,
        "session_high_water": 0,
        "session_drawdown_pct": 0,
        "session_trade_count": 0,
        "session_trades": [],
        "analysis_count_this_session": 0,
        "signals": [],
    }
    _active_sessions[user_id] = session

    return {
        "session_id": session_id,
        "ticker": req.ticker.upper(),
        "profile": req.profile,
        "started_at": now,
        "status": "ACTIVE",
    }


# ── POST /analyze — Run session analysis ──────────────────────────────────
@router.post("/analyze")
async def session_analyze(req: SessionAnalyzeRequest, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.get(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session. Call POST /start first.")

    ticker = (req.ticker or session["ticker"]).upper()

    # Get market data
    market_data = await get_market_data(ticker)

    # Get news context
    news_context = await get_news_context(ticker)

    # Run session pipeline
    result = await run_session_pipeline(
        ticker=ticker,
        market_data=market_data,
        news_context=news_context,
        session_state=session,
        profile=session.get("profile", "balanced"),
    )

    # Update session state
    session["analysis_count_this_session"] = session.get("analysis_count_this_session", 0) + 1
    session["signals"].append({
        "timestamp": result.get("timestamp"),
        "direction": result.get("direction"),
        "confidence": result.get("confidence"),
        "risk_gate_passed": result.get("risk_gate_passed"),
    })

    return result


# ── GET /status — Get current session status ──────────────────────────────
@router.get("/status")
async def session_status(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.get(user_id)
    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session["session_id"],
        "ticker": session["ticker"],
        "profile": session.get("profile", "balanced"),
        "started_at": session["session_start_time"],
        "analysis_count": session.get("analysis_count_this_session", 0),
        "trade_count": session.get("session_trade_count", 0),
        "pnl": session.get("session_pnl", 0),
        "pnl_pct": session.get("session_pnl_pct", 0),
    }


# ── POST /stop — End the current session ──────────────────────────────────
@router.post("/stop")
async def stop_session(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.pop(user_id, None)
    if not session:
        return {"status": "NO_SESSION"}

    return {
        "status": "ENDED",
        "session_id": session["session_id"],
        "ticker": session["ticker"],
        "analysis_count": session.get("analysis_count_this_session", 0),
        "trade_count": session.get("session_trade_count", 0),
        "final_pnl": session.get("session_pnl", 0),
        "final_pnl_pct": session.get("session_pnl_pct", 0),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 2: Register session router in main.py**

Add to `backend/app/main.py` imports:
```python
from app.api.routes import session as session_router_module
```

Add to router includes (after profiles):
```python
app.include_router(session_router_module.router)
```

- [ ] **Step 3: Verify syntax**

Run: `cd backend && python -m py_compile app/api/routes/session.py && echo "OK"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/session.py backend/app/main.py
git commit -m "feat(session): add session API routes (start/analyze/status/stop)"
```

---

## Task 8: Frontend [COMPLETED] — API Functions + Types

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add session types and API functions to api.ts**

Add these interfaces and functions at the end of `frontend/lib/api.ts`:

```typescript
// ── Session Mode types ────────────────────────────────────────────────────

export interface SessionSignal {
  direction: string;
  confidence: number;
  entry: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  position_size_pct: number;
  trade_type: string;
  urgency: string;
  agent_agreement: number;
  reasoning: string;
  risk_reward_ratio: number;
  ticker: string;
  mode: string;
  strategy_profile: string;
  kill_zone: string;
  kill_zone_active: boolean;
  kill_zone_minutes_remaining: number;
  market_phase: string;
  risk_gate_passed: boolean;
  risk_gate_mode: string;
  risk_gate_rules: { rule: number; name: string; reason: string }[];
  coach: {
    tilt_detected: boolean;
    tilt_type: string;
    tilt_severity: number;
    message: string;
    recommendation: string;
    positive_note: string | null;
  };
  session_risk: {
    risk_level: string;
    recommended_action: string;
  };
  agent_votes: { agent: string; direction: string; confidence: number }[];
  reasoning_chain: string[];
  pipeline_latency_ms: number;
  timestamp: string;
}

export interface SessionStatus {
  active: boolean;
  session_id?: string;
  ticker?: string;
  profile?: string;
  started_at?: string;
  analysis_count?: number;
  trade_count?: number;
  pnl?: number;
  pnl_pct?: number;
}

// ── Session Mode API functions ────────────────────────────────────────────

export async function startSession(ticker: string, profile: string = "balanced") {
  return apiFetch("/api/v1/session/start", {
    method: "POST",
    body: JSON.stringify({ ticker, profile }),
  });
}

export async function runSessionAnalysis(ticker?: string) {
  return apiFetch("/api/v1/session/analyze", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  }) as Promise<SessionSignal>;
}

export async function getSessionStatus(): Promise<SessionStatus> {
  return apiFetch("/api/v1/session/status");
}

export async function stopSession() {
  return apiFetch("/api/v1/session/stop", { method: "POST" });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat(session): add session API types and functions to frontend"
```

---

## Task 9: Frontend [COMPLETED] — Navbar Mode Toggle

**Files:**
- Modify: `frontend/components/Navbar.tsx`

- [ ] **Step 1: Add RESEARCH | SESSION toggle to Navbar**

Read `Navbar.tsx` fully first, then add a mode toggle between the logo and the nav items. The toggle should:
- Show "RESEARCH" and "SESSION" as two clickable segments
- Store mode in localStorage as `qne-mode`
- Navigate to `/dashboard` when RESEARCH selected, `/session` when SESSION selected
- SESSION should show a small "PRO" badge since it requires Pro tier

Add after the logo section, before the nav items:

```tsx
{/* Mode toggle */}
<div className="flex items-center gap-0.5 mx-3 p-0.5 rounded border border-border/50 bg-muted/20">
  <Link
    href="/dashboard"
    className={cn(
      "px-2.5 py-1 text-[9px] font-mono font-bold rounded transition-colors",
      !pathname?.startsWith("/session")
        ? "bg-primary/10 text-primary"
        : "text-muted-foreground hover:text-foreground"
    )}
  >
    RESEARCH
  </Link>
  <Link
    href="/session"
    className={cn(
      "px-2.5 py-1 text-[9px] font-mono font-bold rounded transition-colors flex items-center gap-1",
      pathname?.startsWith("/session")
        ? "bg-primary/10 text-primary"
        : "text-muted-foreground hover:text-foreground"
    )}
  >
    SESSION
    <span className="text-[7px] text-amber-400 border border-amber-400/30 rounded px-0.5">PRO</span>
  </Link>
</div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/Navbar.tsx
git commit -m "feat(session): add RESEARCH | SESSION mode toggle to Navbar"
```

---

## Task 10: Frontend [COMPLETED] — Session Page + Components

**Files:**
- Create: `frontend/app/session/page.tsx`
- Create: `frontend/components/SessionTimer.tsx`
- Create: `frontend/components/CoachPanel.tsx`
- Create: `frontend/components/SessionSignalCard.tsx`
- Create: `frontend/components/SessionPnL.tsx`

This is the largest frontend task. Each component is focused:

- [ ] **Step 1: Create SessionTimer component**

```tsx
// frontend/components/SessionTimer.tsx
"use client";

import { Clock, Zap, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionTimerProps {
  killZone: string;
  killZoneActive: boolean;
  minutesRemaining: number;
  marketPhase: string;
  sessionElapsed: number;
  utcTime: string;
}

const KILL_ZONE_COLORS: Record<string, string> = {
  TOKYO:   "text-purple-400 border-purple-400/30 bg-purple-400/5",
  LONDON:  "text-blue-400 border-blue-400/30 bg-blue-400/5",
  NY_OPEN: "text-bull border-bull/30 bg-bull/5",
  OVERLAP: "text-amber-400 border-amber-400/30 bg-amber-400/5",
  NONE:    "text-muted-foreground border-border/50 bg-muted/10",
};

export function SessionTimer({ killZone, killZoneActive, minutesRemaining, marketPhase, sessionElapsed, utcTime }: SessionTimerProps) {
  const hours = Math.floor(sessionElapsed / 60);
  const mins = sessionElapsed % 60;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-primary" />
          <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">SESSION TIMER</span>
        </div>
        <span className="text-[9px] font-mono text-muted-foreground">{utcTime}</span>
      </div>

      {/* Kill Zone Status */}
      <div className={cn(
        "rounded border px-3 py-2 mb-3",
        KILL_ZONE_COLORS[killZone] || KILL_ZONE_COLORS.NONE
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {killZoneActive ? (
              <Zap className="h-3 w-3 animate-pulse" />
            ) : (
              <AlertTriangle className="h-3 w-3 opacity-50" />
            )}
            <span className="text-[11px] font-mono font-bold">
              {killZoneActive ? killZone.replace("_", " ") : "NO KILL ZONE"}
            </span>
          </div>
          {killZoneActive && (
            <span className={cn(
              "text-[10px] font-mono font-bold",
              minutesRemaining < 10 ? "text-bear animate-pulse" : ""
            )}>
              {minutesRemaining}m left
            </span>
          )}
        </div>
      </div>

      {/* Session elapsed + phase */}
      <div className="flex items-center justify-between text-[9px] font-mono">
        <span className="text-muted-foreground">
          Session: <span className="text-foreground font-bold">{hours}h {mins}m</span>
        </span>
        <span className="text-muted-foreground">
          Phase: <span className="text-foreground">{marketPhase.replace(/_/g, " ")}</span>
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create CoachPanel component**

```tsx
// frontend/components/CoachPanel.tsx
"use client";

import { Brain, AlertTriangle, CheckCircle2, Pause, HandMetal } from "lucide-react";
import { cn } from "@/lib/utils";

interface CoachPanelProps {
  tiltDetected: boolean;
  tiltType: string;
  tiltSeverity: number;
  message: string;
  recommendation: string;
  positiveNote: string | null;
}

const TILT_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  REVENGE:     AlertTriangle,
  FOMO:        AlertTriangle,
  OVERTRADING: AlertTriangle,
  HESITATION:  Pause,
  ESCALATION:  AlertTriangle,
  OFF_HOURS:   AlertTriangle,
  NONE:        CheckCircle2,
};

const RECOMMENDATION_COLORS: Record<string, string> = {
  CONTINUE:    "text-bull border-bull/30 bg-bull/5",
  PAUSE_5MIN:  "text-warn border-warn/30 bg-warn/5",
  REDUCE_SIZE: "text-warn border-warn/30 bg-warn/5",
  END_SESSION: "text-bear border-bear/30 bg-bear/5",
};

export function CoachPanel({ tiltDetected, tiltType, tiltSeverity, message, recommendation, positiveNote }: CoachPanelProps) {
  const TiltIcon = TILT_ICONS[tiltType] || CheckCircle2;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="h-3.5 w-3.5 text-primary" />
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">SESSION COACH</span>
        {tiltDetected && (
          <span className="ml-auto text-[8px] font-mono font-bold px-1.5 py-0.5 rounded bg-bear/10 text-bear border border-bear/30">
            TILT {tiltSeverity}/10
          </span>
        )}
      </div>

      {/* Main message */}
      <div className={cn(
        "rounded border px-3 py-2 mb-2",
        tiltDetected ? "border-warn/30 bg-warn/5" : "border-bull/20 bg-bull/5"
      )}>
        <div className="flex items-start gap-2">
          <TiltIcon className={cn("h-3 w-3 mt-0.5 shrink-0", tiltDetected ? "text-warn" : "text-bull")} />
          <p className="text-[11px] font-mono text-foreground/90 leading-relaxed">{message}</p>
        </div>
      </div>

      {/* Recommendation badge */}
      <div className={cn(
        "inline-flex items-center gap-1 px-2 py-1 rounded border text-[8px] font-mono font-bold",
        RECOMMENDATION_COLORS[recommendation] || RECOMMENDATION_COLORS.CONTINUE
      )}>
        {recommendation.replace(/_/g, " ")}
      </div>

      {/* Positive note */}
      {positiveNote && (
        <div className="mt-2 flex items-start gap-1.5">
          <HandMetal className="h-2.5 w-2.5 text-bull mt-0.5 shrink-0" />
          <span className="text-[9px] font-mono text-bull/80">{positiveNote}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create SessionSignalCard component**

```tsx
// frontend/components/SessionSignalCard.tsx
"use client";

import { TrendingUp, TrendingDown, Minus, ShieldCheck, ShieldX, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SessionSignal } from "@/lib/api";

interface SessionSignalCardProps {
  signal: SessionSignal;
}

export function SessionSignalCard({ signal }: SessionSignalCardProps) {
  const isLong = signal.direction === "LONG";
  const isShort = signal.direction === "SHORT";
  const isNeutral = signal.direction === "NEUTRAL";
  const DirectionIcon = isLong ? TrendingUp : isShort ? TrendingDown : Minus;
  const dirColor = isLong ? "text-bull" : isShort ? "text-bear" : "text-muted-foreground";

  return (
    <div className={cn(
      "rounded-lg border bg-background overflow-hidden",
      isLong ? "border-bull/30" : isShort ? "border-bear/30" : "border-border"
    )}>
      {/* Header */}
      <div className={cn(
        "flex items-center justify-between px-4 py-2",
        isLong ? "bg-bull/5" : isShort ? "bg-bear/5" : "bg-muted/10"
      )}>
        <div className="flex items-center gap-2">
          <DirectionIcon className={cn("h-4 w-4", dirColor)} />
          <span className={cn("text-sm font-mono font-bold", dirColor)}>
            {signal.direction}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground">
            {signal.ticker}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border",
            signal.urgency === "EXECUTE_NOW"
              ? "text-bull border-bull/30 bg-bull/10 animate-pulse"
              : signal.urgency === "WAIT_FOR_LEVEL"
                ? "text-warn border-warn/30 bg-warn/10"
                : "text-muted-foreground border-border"
          )}>
            {signal.urgency.replace(/_/g, " ")}
          </span>
          <span className={cn("text-sm font-mono font-bold", dirColor)}>
            {signal.confidence}%
          </span>
        </div>
      </div>

      {/* Levels grid */}
      {!isNeutral && (
        <div className="grid grid-cols-4 gap-px bg-border/30">
          {[
            { label: "ENTRY", value: signal.entry, color: "text-foreground" },
            { label: "STOP", value: signal.stop_loss, color: "text-bear" },
            { label: "TP1", value: signal.take_profit_1, color: "text-bull" },
            { label: "TP2", value: signal.take_profit_2, color: "text-bull" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-background px-3 py-2 text-center">
              <div className="text-[8px] font-mono text-muted-foreground">{label}</div>
              <div className={cn("text-[12px] font-mono font-bold", color)}>
                {typeof value === "number" ? value.toFixed(2) : "—"}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center gap-3 px-4 py-2 border-t border-border/30">
        <span className="text-[8px] font-mono text-muted-foreground">
          R:R <span className="text-foreground font-bold">{signal.risk_reward_ratio?.toFixed(1) || "—"}</span>
        </span>
        <span className="text-[8px] font-mono text-muted-foreground">
          Size <span className="text-foreground font-bold">{signal.position_size_pct?.toFixed(1)}%</span>
        </span>
        <span className="text-[8px] font-mono text-muted-foreground">
          Agree <span className="text-foreground font-bold">{signal.agent_agreement}/5</span>
        </span>
        <div className="ml-auto flex items-center gap-1">
          {signal.risk_gate_passed ? (
            <ShieldCheck className="h-3 w-3 text-bull" />
          ) : (
            <ShieldX className="h-3 w-3 text-bear" />
          )}
          <span className={cn(
            "text-[8px] font-mono font-bold",
            signal.risk_gate_passed ? "text-bull" : "text-bear"
          )}>
            {signal.risk_gate_mode}
          </span>
        </div>
      </div>

      {/* Agent votes */}
      <div className="flex items-center gap-1 px-4 py-1.5 border-t border-border/20 bg-muted/5">
        {signal.agent_votes?.map((vote) => (
          <span
            key={vote.agent}
            className={cn(
              "text-[7px] font-mono font-bold px-1.5 py-0.5 rounded border",
              vote.direction === "LONG" ? "text-bull border-bull/20 bg-bull/5" :
              vote.direction === "SHORT" ? "text-bear border-bear/20 bg-bear/5" :
              "text-muted-foreground border-border/30"
            )}
          >
            {vote.agent.slice(0, 4).toUpperCase()} {vote.confidence}%
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create SessionPnL component**

```tsx
// frontend/components/SessionPnL.tsx
"use client";

import { DollarSign, TrendingUp, TrendingDown, BarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionPnLProps {
  pnl: number;
  pnlPct: number;
  tradeCount: number;
  analysisCount: number;
}

export function SessionPnL({ pnl, pnlPct, tradeCount, analysisCount }: SessionPnLProps) {
  const isPositive = pnl >= 0;
  const PnLIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="rounded-lg border border-border bg-background p-4">
      <div className="flex items-center gap-2 mb-3">
        <DollarSign className="h-3.5 w-3.5 text-primary" />
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">SESSION P&L</span>
      </div>

      <div className="flex items-baseline gap-2 mb-3">
        <PnLIcon className={cn("h-5 w-5", isPositive ? "text-bull" : "text-bear")} />
        <span className={cn("text-2xl font-mono font-bold", isPositive ? "text-bull" : "text-bear")}>
          ${Math.abs(pnl).toFixed(2)}
        </span>
        <span className={cn("text-sm font-mono", isPositive ? "text-bull" : "text-bear")}>
          ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <BarChart2 className="h-3 w-3 text-muted-foreground" />
          <span className="text-[9px] font-mono text-muted-foreground">
            Trades: <span className="text-foreground font-bold">{tradeCount}</span>
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-mono text-muted-foreground">
            Analyses: <span className="text-foreground font-bold">{analysisCount}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create Session page**

```tsx
// frontend/app/session/page.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Activity, Play, Square, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/useAuth";
import { SymbolSearch } from "@/components/SymbolSearch";
import { ProfileSelector } from "@/components/ProfileSelector";
import { SessionTimer } from "@/components/SessionTimer";
import { SessionPnL } from "@/components/SessionPnL";
import { SessionSignalCard } from "@/components/SessionSignalCard";
import { CoachPanel } from "@/components/CoachPanel";
import {
  startSession,
  runSessionAnalysis,
  getSessionStatus,
  stopSession,
  type SessionSignal,
  type SessionStatus,
} from "@/lib/api";

export default function SessionPage() {
  const { isLoggedIn, tier } = useAuth();
  const isPro = tier === "pro" || tier === "enterprise" || tier === "admin";

  const [activeTicker, setActiveTicker] = useState("AAPL");
  const [activeProfile, setActiveProfile] = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("qne-profile") || "balanced";
    return "balanced";
  });

  const [sessionActive, setSessionActive] = useState(false);
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [signals, setSignals] = useState<SessionSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Latest signal data for timer/coach
  const latestSignal = signals[signals.length - 1] || null;

  // Check session status on mount
  useEffect(() => {
    if (!isLoggedIn) return;
    getSessionStatus().then((status) => {
      if (status.active) {
        setSessionActive(true);
        setSessionStatus(status);
        setActiveTicker(status.ticker || "AAPL");
      }
    }).catch(() => {});
  }, [isLoggedIn]);

  // Save profile to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") localStorage.setItem("qne-profile", activeProfile);
  }, [activeProfile]);

  const handleStartSession = useCallback(async () => {
    if (!isLoggedIn || !isPro) return;
    setLoading(true);
    setError(null);
    try {
      await startSession(activeTicker, activeProfile);
      setSessionActive(true);
      setSignals([]);
      const status = await getSessionStatus();
      setSessionStatus(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn, isPro, activeTicker, activeProfile]);

  const handleStopSession = useCallback(async () => {
    setLoading(true);
    try {
      await stopSession();
      setSessionActive(false);
      setSessionStatus(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to stop session");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleAnalyze = useCallback(async () => {
    if (!sessionActive) return;
    setAnalyzing(true);
    setError(null);
    try {
      const result = await runSessionAnalysis();
      setSignals((prev) => [...prev, result]);
      // Refresh status
      const status = await getSessionStatus();
      setSessionStatus(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, [sessionActive]);

  // Pro gate
  if (!isPro && isLoggedIn) {
    return (
      <div className="h-[calc(100vh-72px)] flex items-center justify-center bg-background">
        <div className="text-center max-w-md px-6">
          <Zap className="h-10 w-10 text-amber-400 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-foreground mb-2">Session Mode requires Pro</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Real-time intraday analysis with kill zone detection, psychological coaching,
            and session risk management.
          </p>
          <a
            href="/pricing"
            className="inline-flex items-center gap-2 px-4 py-2 rounded border border-amber-400/30 bg-amber-400/10 text-amber-400 text-sm font-mono font-bold hover:bg-amber-400/20 transition-colors"
          >
            Upgrade to Pro
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-72px)] flex flex-col bg-background overflow-hidden">

      {/* Session Control Bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-[hsl(0_0%_3%)] shrink-0">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", sessionActive ? "bg-bull animate-pulse" : "bg-muted-foreground")} />
          <span className="text-[10px] font-mono font-bold text-primary tracking-widest">
            SESSION MODE
          </span>
        </div>

        {!sessionActive ? (
          <>
            <SymbolSearch value={activeTicker} onChange={setActiveTicker} />
            <ProfileSelector value={activeProfile} onChange={setActiveProfile} compact />
            <button
              onClick={handleStartSession}
              disabled={loading || !isLoggedIn}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border border-bull/50 text-bull hover:bg-bull/10 transition-colors disabled:opacity-40"
            >
              <Play className="h-3 w-3" />
              START SESSION
            </button>
          </>
        ) : (
          <>
            <span className="text-[11px] font-mono font-bold text-foreground">{activeTicker}</span>
            <span className="text-[9px] font-mono text-muted-foreground">{activeProfile.toUpperCase()}</span>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border transition-colors",
                analyzing
                  ? "border-border/40 text-muted-foreground/50 cursor-not-allowed"
                  : "border-primary/50 text-primary hover:bg-primary/10"
              )}
            >
              <Activity className={cn("h-3 w-3", analyzing && "animate-spin")} />
              {analyzing ? "ANALYZING…" : "RUN ANALYSIS"}
            </button>
            <button
              onClick={handleStopSession}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1 rounded text-[10px] font-mono font-bold border border-bear/50 text-bear hover:bg-bear/10 transition-colors ml-auto disabled:opacity-40"
            >
              <Square className="h-3 w-3" />
              END SESSION
            </button>
          </>
        )}
      </div>

      {error && (
        <div className="px-4 py-2 bg-bear/10 border-b border-bear/30 text-[10px] font-mono text-bear">
          {error}
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Left — Signals feed */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {!sessionActive && signals.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <Zap className="h-10 w-10 text-primary/20" />
              <div className="text-[11px] font-mono text-muted-foreground max-w-sm">
                Start a session to begin real-time intraday analysis.
                Select a ticker and strategy profile, then click START SESSION.
              </div>
            </div>
          )}

          {signals.map((sig, i) => (
            <SessionSignalCard key={`${sig.timestamp}-${i}`} signal={sig} />
          ))}
        </div>

        {/* Right Sidebar — Timer + P&L + Coach */}
        <div className="hidden lg:flex w-72 shrink-0 border-l border-border flex-col gap-3 p-3 overflow-y-auto">

          {/* Timer */}
          <SessionTimer
            killZone={latestSignal?.kill_zone || "NONE"}
            killZoneActive={latestSignal?.kill_zone_active || false}
            minutesRemaining={latestSignal?.kill_zone_minutes_remaining || 0}
            marketPhase={latestSignal?.market_phase || "UNKNOWN"}
            sessionElapsed={sessionStatus ? Math.floor((Date.now() - new Date(sessionStatus.started_at || Date.now()).getTime()) / 60000) : 0}
            utcTime={new Date().toISOString().slice(11, 16) + " UTC"}
          />

          {/* P&L */}
          <SessionPnL
            pnl={sessionStatus?.pnl || 0}
            pnlPct={sessionStatus?.pnl_pct || 0}
            tradeCount={sessionStatus?.trade_count || 0}
            analysisCount={sessionStatus?.analysis_count || 0}
          />

          {/* Coach */}
          {latestSignal?.coach && (
            <CoachPanel
              tiltDetected={latestSignal.coach.tilt_detected}
              tiltType={latestSignal.coach.tilt_type}
              tiltSeverity={latestSignal.coach.tilt_severity}
              message={latestSignal.coach.message}
              recommendation={latestSignal.coach.recommendation}
              positiveNote={latestSignal.coach.positive_note}
            />
          )}

          {/* Reasoning chain */}
          {latestSignal?.reasoning_chain && latestSignal.reasoning_chain.length > 0 && (
            <div className="rounded-lg border border-border bg-background p-4">
              <div className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest mb-2">
                REASONING CHAIN
              </div>
              <div className="space-y-1">
                {latestSignal.reasoning_chain.map((step, i) => (
                  <div key={i} className="text-[9px] font-mono text-muted-foreground leading-relaxed">
                    {step}
                  </div>
                ))}
              </div>
              <div className="mt-2 text-[8px] font-mono text-muted-foreground/50">
                {latestSignal.pipeline_latency_ms}ms
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add frontend/app/session/page.tsx frontend/components/SessionTimer.tsx frontend/components/CoachPanel.tsx frontend/components/SessionSignalCard.tsx frontend/components/SessionPnL.tsx
git commit -m "feat(session): add Session page with timer, coach, signal cards, P&L"
```

---

## Task 11: Final [COMPLETED] Integration + Deploy

- [ ] **Step 1: Verify backend compiles**

Run: `cd backend && python -c "from app.api.routes.session import router; print('Session router OK')" && python -m py_compile app/pipeline/session_graph.py && echo "ALL OK"`

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Full commit + push**

```bash
git add -A
git status  # review what's staged
git commit -m "feat: Phase 4 — Session Mode (8 agents, pipeline, risk gate, frontend)"
git push
```

- [ ] **Step 4: Test on live site**

1. Navigate to app.quantneuraledge.com
2. Verify RESEARCH | SESSION toggle in navbar
3. Click SESSION — should show Pro gate if not Pro, or session page if Pro
4. Start session → run analysis → verify signal card, timer, coach, reasoning chain
5. Verify Research Mode still works unchanged
