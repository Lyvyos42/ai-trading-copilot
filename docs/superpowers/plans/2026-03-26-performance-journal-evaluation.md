# Performance Dashboard + Signal Journal + Evaluation Loop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add outcome tracking to signals, auto-evaluate TP/SL hits, expose public performance analytics, and build authenticated signal journal — turning QNE from "generates signals" into "proves track record."

**Architecture:** Extend Signal model with outcome/pnl fields (auto-migrated). New evaluation endpoint checks ACTIVE signals against live prices. Six public performance API endpoints aggregate historical data. Frontend: `/performance` page (public, no auth) with equity curve, monthly heatmap, agent leaderboard; `/journal` page (auth required) with filters, detail view, personal stats.

**Tech Stack:** FastAPI + SQLAlchemy async (Neon PostgreSQL), Next.js 14 + Tailwind CSS, current electric blue design system, yfinance for price data, SVG charts (no chart library — lightweight).

---

## File Structure

### Backend — New Files
- `backend/app/api/routes/evaluation.py` — Evaluation loop endpoint (POST /api/v1/signals/evaluate)
- `backend/app/api/routes/performance.py` — 6 public performance endpoints (GET /api/v1/performance/*)

### Backend — Modified Files
- `backend/app/models/signal.py` — Add outcome, exit_price, resolved_at, pnl_pct, max_favorable_excursion, max_adverse_excursion columns
- `backend/app/main.py` — Register new routers + add ALTER TABLE migrations for new columns
- `backend/app/api/routes/signals.py` — Update `_signal_to_dict()` to include new fields, enhance PATCH outcome endpoint to accept exit_price/pnl
- `backend/app/api/routes/portfolio.py` — Sync signal outcome when position is closed

### Frontend — New Files
- `frontend/app/performance/page.tsx` — Public performance dashboard page
- `frontend/app/journal/page.tsx` — Authenticated signal journal page
- `frontend/components/EquityCurve.tsx` — SVG line chart component
- `frontend/components/MonthlyHeatmap.tsx` — Monthly returns grid
- `frontend/components/CalibrationChart.tsx` — Confidence vs win rate scatter
- `frontend/components/AgentLeaderboard.tsx` — Agent ranking table
- `frontend/components/SignalDetailModal.tsx` — Signal detail overlay for journal

### Frontend — Modified Files
- `frontend/lib/api.ts` — Add performance + journal API functions, update Signal interface
- `frontend/components/Navbar.tsx` — Add Performance and Journal nav links

---

## Task 1: Signal Model Upgrade

**Files:**
- Modify: `backend/app/models/signal.py:27-48`
- Modify: `backend/app/main.py:38-46` (migration array)
- Modify: `backend/app/api/routes/signals.py:357-381` (`_signal_to_dict`)

- [ ] **Step 1: Add new columns to Signal model**

In `backend/app/models/signal.py`, add these columns after line 46 (`status` column):

```python
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)  # WIN, LOSS, EXPIRED, None
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)  # best unrealized %
    max_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)    # worst unrealized %
```

- [ ] **Step 2: Add ALTER TABLE migrations in main.py**

In `backend/app/main.py`, extend the `_migrations` list (around line 38-40):

```python
        _migrations = [
            "ALTER TABLE signals ADD COLUMN timeframe_levels TEXT DEFAULT '{}'",
            "ALTER TABLE signals ADD COLUMN outcome VARCHAR",
            "ALTER TABLE signals ADD COLUMN exit_price FLOAT",
            "ALTER TABLE signals ADD COLUMN resolved_at TIMESTAMP",
            "ALTER TABLE signals ADD COLUMN pnl_pct FLOAT",
            "ALTER TABLE signals ADD COLUMN max_favorable_excursion FLOAT",
            "ALTER TABLE signals ADD COLUMN max_adverse_excursion FLOAT",
        ]
```

- [ ] **Step 3: Update `_signal_to_dict` to include new fields**

In `backend/app/api/routes/signals.py`, update the `_signal_to_dict` function to add the new fields to the dict:

```python
def _signal_to_dict(signal: Signal, state: dict | None = None) -> dict:
    d = {
        "signal_id": str(signal.id),
        "ticker": signal.ticker,
        "asset_class": signal.asset_class,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit_1": signal.take_profit_1,
        "take_profit_2": signal.take_profit_2,
        "take_profit_3": signal.take_profit_3,
        "confidence_score": signal.confidence_score,
        "agent_votes": signal.agent_votes,
        "reasoning_chain": signal.reasoning_chain,
        "strategy_sources": signal.strategy_sources,
        "timeframe_levels": signal.timeframe_levels or {},
        "status": signal.status,
        "outcome": getattr(signal, "outcome", None),
        "exit_price": getattr(signal, "exit_price", None),
        "resolved_at": (signal.resolved_at.isoformat() + "Z") if getattr(signal, "resolved_at", None) else None,
        "pnl_pct": getattr(signal, "pnl_pct", None),
        "timestamp": (signal.created_at.isoformat() + "Z") if signal.created_at else None,
        "expiry_time": (signal.expiry_time.isoformat() + "Z") if signal.expiry_time else None,
    }
    if state:
        d["pipeline_latency_ms"] = state.get("pipeline_latency_ms")
        d["agent_detail"] = _build_agent_detail(state)
    return d
```

Note: `getattr` with default is used because existing DB rows won't have these columns until migration runs — this prevents AttributeError on first boot before ALTER TABLE executes.

- [ ] **Step 4: Enhance PATCH outcome endpoint with exit_price and pnl_pct**

In `backend/app/api/routes/signals.py`, update `OutcomeRequest` and `set_signal_outcome`:

```python
class OutcomeRequest(BaseModel):
    outcome: str  # "WIN" or "LOSS"
    exit_price: float | None = None
    pnl_pct: float | None = None


@router.patch("/{signal_id}/outcome")
async def set_signal_outcome(
    signal_id: str,
    body: OutcomeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    if body.outcome not in ("WIN", "LOSS", "EXPIRED"):
        raise HTTPException(status_code=400, detail="outcome must be WIN, LOSS, or EXPIRED")

    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    owner_id = (user.get("sub") or user.get("id") or user.get("user_id")) if user else None
    if user and signal.user_id and signal.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your signal")

    signal.status = body.outcome
    signal.outcome = body.outcome
    if body.exit_price is not None:
        signal.exit_price = body.exit_price
    if body.pnl_pct is not None:
        signal.pnl_pct = body.pnl_pct
    signal.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(signal)
    return _signal_to_dict(signal)
```

- [ ] **Step 5: Test migration locally**

Run: `cd C:/Users/Liv/ai-trading-copilot/backend && python -c "from app.models.signal import Signal; print('Model OK:', [c.name for c in Signal.__table__.columns])"`

Expected: prints column list including outcome, exit_price, resolved_at, pnl_pct, max_favorable_excursion, max_adverse_excursion

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/signal.py backend/app/main.py backend/app/api/routes/signals.py
git commit -m "feat: add outcome/pnl fields to Signal model with auto-migration"
```

---

## Task 2: Evaluation Loop Endpoint

**Files:**
- Create: `backend/app/api/routes/evaluation.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create evaluation.py**

Create `backend/app/api/routes/evaluation.py`:

```python
"""
POST /api/v1/signals/evaluate — check all ACTIVE signals against current prices.
Auto-resolves signals where TP1 or SL has been hit.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.db.database import get_db
from app.models.signal import Signal
from app.data.market_data import fetch_market_data

router = APIRouter(prefix="/api/v1/signals", tags=["evaluation"])


@router.post("/evaluate")
async def evaluate_signals(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check all ACTIVE signals and auto-resolve if TP1 or SL hit."""
    result = await db.execute(
        select(Signal).where(Signal.status == "ACTIVE")
    )
    active_signals = result.scalars().all()

    evaluated = []
    resolved = []
    errors = []

    for signal in active_signals:
        try:
            market = await fetch_market_data(signal.ticker)
            current_price = market.get("current_price") or market.get("price", 0)
            if not current_price:
                errors.append({"signal_id": str(signal.id), "ticker": signal.ticker, "error": "no price data"})
                continue

            # Calculate excursion from entry
            if signal.entry_price and signal.entry_price > 0:
                if signal.direction == "LONG":
                    excursion_pct = ((current_price - signal.entry_price) / signal.entry_price) * 100
                else:  # SHORT
                    excursion_pct = ((signal.entry_price - current_price) / signal.entry_price) * 100

                # Update MFE/MAE
                current_mfe = getattr(signal, "max_favorable_excursion", None) or 0
                current_mae = getattr(signal, "max_adverse_excursion", None) or 0
                if excursion_pct > current_mfe:
                    signal.max_favorable_excursion = round(excursion_pct, 4)
                if excursion_pct < current_mae:
                    signal.max_adverse_excursion = round(excursion_pct, 4)

            # Check TP/SL hit
            outcome = _check_tp_sl(signal, current_price)

            if outcome:
                pnl_pct = _calc_pnl_pct(signal, current_price)
                signal.status = outcome
                signal.outcome = outcome
                signal.exit_price = current_price
                signal.pnl_pct = round(pnl_pct, 4)
                signal.resolved_at = datetime.now(timezone.utc)
                resolved.append({
                    "signal_id": str(signal.id),
                    "ticker": signal.ticker,
                    "direction": signal.direction,
                    "outcome": outcome,
                    "exit_price": current_price,
                    "pnl_pct": round(pnl_pct, 4),
                })
            else:
                evaluated.append({
                    "signal_id": str(signal.id),
                    "ticker": signal.ticker,
                    "current_price": current_price,
                    "status": "STILL_ACTIVE",
                })

        except Exception as exc:
            errors.append({"signal_id": str(signal.id), "ticker": signal.ticker, "error": str(exc)})

    # Check for expired signals (past expiry_time)
    now = datetime.now(timezone.utc)
    for signal in active_signals:
        if signal.expiry_time and signal.expiry_time.replace(tzinfo=timezone.utc) < now and signal.status == "ACTIVE":
            signal.status = "EXPIRED"
            signal.outcome = "EXPIRED"
            signal.resolved_at = now
            resolved.append({
                "signal_id": str(signal.id),
                "ticker": signal.ticker,
                "outcome": "EXPIRED",
            })

    await db.commit()

    return {
        "total_active": len(active_signals),
        "still_active": len(evaluated),
        "resolved": len(resolved),
        "errors": len(errors),
        "resolved_signals": resolved,
        "error_details": errors,
    }


def _check_tp_sl(signal: Signal, current_price: float) -> str | None:
    """Return 'WIN' if TP1 hit, 'LOSS' if SL hit, None otherwise."""
    if signal.direction == "LONG":
        if current_price >= signal.take_profit_1:
            return "WIN"
        if current_price <= signal.stop_loss:
            return "LOSS"
    else:  # SHORT
        if current_price <= signal.take_profit_1:
            return "WIN"
        if current_price >= signal.stop_loss:
            return "LOSS"
    return None


def _calc_pnl_pct(signal: Signal, exit_price: float) -> float:
    """Calculate P&L percentage based on direction."""
    if not signal.entry_price or signal.entry_price == 0:
        return 0.0
    if signal.direction == "LONG":
        return ((exit_price - signal.entry_price) / signal.entry_price) * 100
    else:
        return ((signal.entry_price - exit_price) / signal.entry_price) * 100
```

- [ ] **Step 2: Register evaluation router in main.py**

In `backend/app/main.py`, add to imports:

```python
from app.api.routes import auth, signals, portfolio, agents, backtest, debate, market, news, profiles, session
from app.api.routes import evaluation
```

And add to router registration (after `session.router`):

```python
app.include_router(evaluation.router)
```

- [ ] **Step 3: Sync portfolio close → signal outcome**

In `backend/app/api/routes/portfolio.py`, update `close_position` to sync outcome back to the signal. After line 120 (`position.realized_pnl = round(realized, 2)`), add:

```python
    # Sync outcome to linked signal
    if position.signal_id:
        sig_result = await db.execute(select(Signal).where(Signal.id == position.signal_id))
        linked_signal = sig_result.scalar_one_or_none()
        if linked_signal and linked_signal.status in ("ACTIVE", "EXECUTED"):
            linked_signal.outcome = "WIN" if realized > 0 else "LOSS"
            linked_signal.status = linked_signal.outcome
            linked_signal.exit_price = close_price
            linked_signal.pnl_pct = round(
                realized / (position.entry_price * position.quantity) * 100, 4
            ) if position.entry_price and position.quantity else 0
            linked_signal.resolved_at = datetime.now(timezone.utc)
```

Also add import at the top of portfolio.py:

```python
from app.models.signal import Signal  # already imported, just verify it's there
```

- [ ] **Step 4: Test evaluation endpoint manually**

Run backend: `cd C:/Users/Liv/ai-trading-copilot/backend && uvicorn app.main:app --reload --port 8000`

Test: `curl -X POST http://localhost:8000/api/v1/signals/evaluate -H "Authorization: Bearer <token>" -H "Content-Type: application/json"`

Expected: JSON with total_active, still_active, resolved counts

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/evaluation.py backend/app/main.py backend/app/api/routes/portfolio.py
git commit -m "feat: add evaluation loop with TP/SL auto-detection and portfolio-signal sync"
```

---

## Task 3: Performance API (Public, No Auth)

**Files:**
- Create: `backend/app/api/routes/performance.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: Create performance.py with all 6 endpoints**

Create `backend/app/api/routes/performance.py`:

```python
"""
Public performance endpoints — no auth required.
Aggregates all resolved signals for public track record.
"""
from datetime import datetime, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.signal import Signal

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("/summary")
async def performance_summary(db: AsyncSession = Depends(get_db)):
    """Total signals, win rate, avg confidence, avg pnl."""
    total_result = await db.execute(select(func.count()).select_from(Signal))
    total = total_result.scalar() or 0

    resolved_result = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.outcome.in_(["WIN", "LOSS"]))
    )
    resolved = resolved_result.scalar() or 0

    win_result = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.outcome == "WIN")
    )
    wins = win_result.scalar() or 0

    active_result = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.status == "ACTIVE")
    )
    active = active_result.scalar() or 0

    avg_conf_result = await db.execute(
        select(func.avg(Signal.confidence_score)).select_from(Signal)
    )
    avg_confidence = round(avg_conf_result.scalar() or 0, 1)

    avg_pnl_result = await db.execute(
        select(func.avg(Signal.pnl_pct)).select_from(Signal).where(Signal.pnl_pct.isnot(None))
    )
    avg_pnl = round(avg_pnl_result.scalar() or 0, 2)

    return {
        "total_signals": total,
        "resolved_signals": resolved,
        "active_signals": active,
        "wins": wins,
        "losses": resolved - wins,
        "win_rate_pct": round(wins / resolved * 100, 1) if resolved > 0 else 0,
        "avg_confidence": avg_confidence,
        "avg_pnl_pct": avg_pnl,
    }


@router.get("/equity-curve")
async def equity_curve(db: AsyncSession = Depends(get_db)):
    """Array of {date, cumulative_pnl_pct} for resolved signals ordered by resolved_at."""
    result = await db.execute(
        select(Signal.resolved_at, Signal.pnl_pct)
        .where(Signal.pnl_pct.isnot(None))
        .where(Signal.resolved_at.isnot(None))
        .order_by(Signal.resolved_at)
    )
    rows = result.all()

    curve = []
    cumulative = 0.0
    for resolved_at, pnl_pct in rows:
        cumulative += pnl_pct
        curve.append({
            "date": resolved_at.isoformat() + "Z" if resolved_at else None,
            "pnl_pct": round(pnl_pct, 2),
            "cumulative_pnl_pct": round(cumulative, 2),
        })

    return {"curve": curve}


@router.get("/by-asset-class")
async def by_asset_class(db: AsyncSession = Depends(get_db)):
    """Win rate breakdown by asset class."""
    result = await db.execute(
        select(
            Signal.asset_class,
            func.count().label("total"),
            func.sum(case((Signal.outcome == "WIN", 1), else_=0)).label("wins"),
            func.avg(Signal.pnl_pct).label("avg_pnl"),
            func.avg(Signal.confidence_score).label("avg_conf"),
        )
        .where(Signal.outcome.in_(["WIN", "LOSS"]))
        .group_by(Signal.asset_class)
    )
    rows = result.all()

    return {
        "asset_classes": [
            {
                "asset_class": row.asset_class,
                "total": row.total,
                "wins": row.wins,
                "win_rate_pct": round(row.wins / row.total * 100, 1) if row.total > 0 else 0,
                "avg_pnl_pct": round(row.avg_pnl or 0, 2),
                "avg_confidence": round(row.avg_conf or 0, 1),
            }
            for row in rows
        ]
    }


@router.get("/by-agent")
async def by_agent(db: AsyncSession = Depends(get_db)):
    """Agent accuracy — which agent's direction call matched the final outcome most often."""
    result = await db.execute(
        select(Signal.agent_votes, Signal.direction, Signal.outcome)
        .where(Signal.outcome.in_(["WIN", "LOSS"]))
    )
    rows = result.all()

    agent_stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0, "avg_confidence": []})
    agent_names = ["fundamental", "technical", "sentiment", "macro", "order_flow", "regime_change", "correlation"]

    for agent_votes_data, direction, outcome in rows:
        if not isinstance(agent_votes_data, dict):
            continue
        for agent_name in agent_names:
            vote = agent_votes_data.get(agent_name, {})
            if not isinstance(vote, dict) or not vote.get("direction"):
                continue
            agent_stats[agent_name]["total"] += 1
            vote_dir = vote["direction"]
            conf = vote.get("confidence", 0)
            agent_stats[agent_name]["avg_confidence"].append(conf or 0)

            # Agent was correct if their direction matched AND signal was a WIN,
            # or their direction was opposite AND signal was a LOSS
            if (vote_dir == direction and outcome == "WIN") or (vote_dir != direction and outcome == "LOSS"):
                agent_stats[agent_name]["correct"] += 1

    leaderboard = []
    for name in agent_names:
        stats = agent_stats[name]
        total = stats["total"]
        correct = stats["correct"]
        confs = stats["avg_confidence"]
        leaderboard.append({
            "agent": name,
            "total_signals": total,
            "correct_calls": correct,
            "accuracy_pct": round(correct / total * 100, 1) if total > 0 else 0,
            "avg_confidence": round(sum(confs) / len(confs), 1) if confs else 0,
        })

    leaderboard.sort(key=lambda x: x["accuracy_pct"], reverse=True)
    return {"agents": leaderboard}


@router.get("/calibration")
async def calibration(db: AsyncSession = Depends(get_db)):
    """Confidence vs actual win rate — bucketed by 10% intervals."""
    result = await db.execute(
        select(Signal.confidence_score, Signal.outcome)
        .where(Signal.outcome.in_(["WIN", "LOSS"]))
    )
    rows = result.all()

    buckets: dict[int, dict] = {}
    for conf, outcome in rows:
        bucket = int(conf // 10) * 10  # 0, 10, 20, ..., 90
        bucket = min(bucket, 90)
        if bucket not in buckets:
            buckets[bucket] = {"total": 0, "wins": 0}
        buckets[bucket]["total"] += 1
        if outcome == "WIN":
            buckets[bucket]["wins"] += 1

    calibration_data = []
    for bucket in sorted(buckets.keys()):
        total = buckets[bucket]["total"]
        wins = buckets[bucket]["wins"]
        calibration_data.append({
            "confidence_range": f"{bucket}-{bucket + 10}",
            "confidence_midpoint": bucket + 5,
            "total": total,
            "wins": wins,
            "actual_win_rate_pct": round(wins / total * 100, 1) if total > 0 else 0,
        })

    return {"calibration": calibration_data}


@router.get("/monthly")
async def monthly_returns(db: AsyncSession = Depends(get_db)):
    """Monthly returns for heatmap — grouped by year/month."""
    result = await db.execute(
        select(Signal.resolved_at, Signal.pnl_pct)
        .where(Signal.pnl_pct.isnot(None))
        .where(Signal.resolved_at.isnot(None))
        .order_by(Signal.resolved_at)
    )
    rows = result.all()

    monthly: dict[str, dict] = {}
    for resolved_at, pnl_pct in rows:
        key = resolved_at.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = {"total_pnl_pct": 0, "signal_count": 0, "wins": 0, "losses": 0}
        monthly[key]["total_pnl_pct"] += pnl_pct
        monthly[key]["signal_count"] += 1
        if pnl_pct > 0:
            monthly[key]["wins"] += 1
        else:
            monthly[key]["losses"] += 1

    return {
        "months": [
            {
                "month": key,
                "total_pnl_pct": round(data["total_pnl_pct"], 2),
                "signal_count": data["signal_count"],
                "wins": data["wins"],
                "losses": data["losses"],
                "win_rate_pct": round(data["wins"] / data["signal_count"] * 100, 1) if data["signal_count"] > 0 else 0,
            }
            for key, data in sorted(monthly.items())
        ]
    }
```

- [ ] **Step 2: Register performance router in main.py**

In `backend/app/main.py`, add to imports:

```python
from app.api.routes import evaluation, performance
```

And register:

```python
app.include_router(performance.router)
```

- [ ] **Step 3: Test all endpoints**

```bash
curl http://localhost:8000/api/v1/performance/summary
curl http://localhost:8000/api/v1/performance/equity-curve
curl http://localhost:8000/api/v1/performance/by-asset-class
curl http://localhost:8000/api/v1/performance/by-agent
curl http://localhost:8000/api/v1/performance/calibration
curl http://localhost:8000/api/v1/performance/monthly
```

Expected: All return JSON (possibly empty data arrays if no resolved signals yet)

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/performance.py backend/app/main.py
git commit -m "feat: add 6 public performance API endpoints (no auth)"
```

---

## Task 4: Frontend API Functions + Types

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add performance types and API functions**

At the end of `frontend/lib/api.ts`, add:

```typescript
// ─── Performance (Public) ─────────────────────────────────────────────────────

export interface PerformanceSummary {
  total_signals: number;
  resolved_signals: number;
  active_signals: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  avg_confidence: number;
  avg_pnl_pct: number;
}

export interface EquityCurvePoint {
  date: string;
  pnl_pct: number;
  cumulative_pnl_pct: number;
}

export interface AssetClassPerformance {
  asset_class: string;
  total: number;
  wins: number;
  win_rate_pct: number;
  avg_pnl_pct: number;
  avg_confidence: number;
}

export interface AgentPerformance {
  agent: string;
  total_signals: number;
  correct_calls: number;
  accuracy_pct: number;
  avg_confidence: number;
}

export interface CalibrationBucket {
  confidence_range: string;
  confidence_midpoint: number;
  total: number;
  wins: number;
  actual_win_rate_pct: number;
}

export interface MonthlyReturn {
  month: string;
  total_pnl_pct: number;
  signal_count: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
}

// Public endpoints — no auth needed, use plain fetch with retry
async function publicFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getPerformanceSummary(): Promise<PerformanceSummary> {
  return publicFetch("/api/v1/performance/summary");
}

export async function getEquityCurve(): Promise<{ curve: EquityCurvePoint[] }> {
  return publicFetch("/api/v1/performance/equity-curve");
}

export async function getByAssetClass(): Promise<{ asset_classes: AssetClassPerformance[] }> {
  return publicFetch("/api/v1/performance/by-asset-class");
}

export async function getByAgent(): Promise<{ agents: AgentPerformance[] }> {
  return publicFetch("/api/v1/performance/by-agent");
}

export async function getCalibration(): Promise<{ calibration: CalibrationBucket[] }> {
  return publicFetch("/api/v1/performance/calibration");
}

export async function getMonthlyReturns(): Promise<{ months: MonthlyReturn[] }> {
  return publicFetch("/api/v1/performance/monthly");
}

// ─── Evaluation ───────────────────────────────────────────────────────────────

export async function evaluateSignals() {
  return apiFetch("/api/v1/signals/evaluate", { method: "POST" });
}

// ─── Journal (uses existing listSignals with extended params) ─────────────────

export async function getJournalSignals(params: {
  limit?: number;
  offset?: number;
  ticker?: string;
  outcome?: string;
  asset_class?: string;
  min_confidence?: number;
  max_confidence?: number;
}): Promise<Signal[]> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.ticker) searchParams.set("ticker", params.ticker);
  if (params.outcome) searchParams.set("outcome", params.outcome);
  if (params.asset_class) searchParams.set("asset_class", params.asset_class);
  if (params.min_confidence) searchParams.set("min_confidence", String(params.min_confidence));
  if (params.max_confidence) searchParams.set("max_confidence", String(params.max_confidence));
  return apiFetch(`/api/v1/signals/journal?${searchParams.toString()}`);
}
```

- [ ] **Step 2: Update Signal interface to include new fields**

In `frontend/lib/api.ts`, update the `Signal` interface (around line 80):

```typescript
export interface Signal {
  signal_id: string;
  ticker: string;
  asset_class: string;
  direction: "LONG" | "SHORT";
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2: number;
  take_profit_3: number;
  confidence_score: number;
  agent_votes: Record<string, AgentVote | boolean | null>;
  reasoning_chain: string[];
  strategy_sources: string[];
  timeframe_levels?: { scalp?: TimeframeLevels; swing?: TimeframeLevels };
  status: string;
  outcome?: string | null;
  exit_price?: number | null;
  resolved_at?: string | null;
  pnl_pct?: number | null;
  timestamp: string;
  expiry_time: string;
  pipeline_latency_ms?: number;
  conviction_tier?: string;
  agent_detail?: Record<string, unknown>;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api.ts
git commit -m "feat: add performance + journal API types and fetch functions"
```

---

## Task 5: Journal API Endpoint (Backend)

**Files:**
- Modify: `backend/app/api/routes/signals.py`

- [ ] **Step 1: Add journal endpoint with filters**

In `backend/app/api/routes/signals.py`, add after the `list_signals` endpoint:

```python
@router.get("/journal")
async def journal_signals(
    limit: int = 50,
    offset: int = 0,
    ticker: str | None = None,
    outcome: str | None = None,
    asset_class: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Full signal history with filters — for authenticated journal page."""
    query = select(Signal).order_by(desc(Signal.created_at))

    if user:
        uid = user.get("sub") or user.get("id") or user.get("user_id")
        if uid:
            query = query.where(Signal.user_id == uid)

    if ticker:
        query = query.where(Signal.ticker == ticker.upper().strip())
    if outcome:
        query = query.where(Signal.outcome == outcome.upper())
    if asset_class:
        query = query.where(Signal.asset_class == asset_class)
    if min_confidence is not None:
        query = query.where(Signal.confidence_score >= min_confidence)
    if max_confidence is not None:
        query = query.where(Signal.confidence_score <= max_confidence)

    query = query.offset(offset).limit(min(limit, 200))
    result = await db.execute(query)
    signals = result.scalars().all()
    return [_signal_to_dict(s) for s in signals]
```

**Important:** This endpoint must be registered BEFORE the `/{signal_id}` route, otherwise FastAPI will try to match "journal" as a signal_id. Move it right after `list_signals` (the `@router.get("")` handler).

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/routes/signals.py
git commit -m "feat: add /journal endpoint with filters for signal history"
```

---

## Task 6: Equity Curve SVG Component

**Files:**
- Create: `frontend/components/EquityCurve.tsx`

- [ ] **Step 1: Create SVG line chart component**

Create `frontend/components/EquityCurve.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import type { EquityCurvePoint } from "@/lib/api";

interface EquityCurveProps {
  data: EquityCurvePoint[];
}

export function EquityCurve({ data }: EquityCurveProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[300px]">
        <span className="text-muted-foreground font-mono text-xs">NO RESOLVED SIGNALS YET</span>
      </div>
    );
  }

  const W = 800;
  const H = 280;
  const PAD = { top: 20, right: 20, bottom: 30, left: 60 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const values = data.map((d) => d.cumulative_pnl_pct);
  const minY = Math.min(0, ...values);
  const maxY = Math.max(0, ...values);
  const rangeY = maxY - minY || 1;

  const scaleX = (i: number) => PAD.left + (i / (data.length - 1 || 1)) * plotW;
  const scaleY = (v: number) => PAD.top + plotH - ((v - minY) / rangeY) * plotH;

  const pathD = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(1)} ${scaleY(d.cumulative_pnl_pct).toFixed(1)}`)
    .join(" ");

  // Gradient fill area
  const areaD = `${pathD} L ${scaleX(data.length - 1).toFixed(1)} ${scaleY(0).toFixed(1)} L ${scaleX(0).toFixed(1)} ${scaleY(0).toFixed(1)} Z`;

  const lastVal = values[values.length - 1];
  const isPositive = lastVal >= 0;
  const strokeColor = isPositive ? "hsl(142, 65%, 42%)" : "hsl(0, 68%, 52%)";
  const fillId = isPositive ? "eq-grad-bull" : "eq-grad-bear";

  // Y-axis ticks
  const yTicks: number[] = [];
  const step = rangeY / 4;
  for (let i = 0; i <= 4; i++) {
    yTicks.push(minY + step * i);
  }

  // Zero line
  const zeroY = scaleY(0);

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">EQUITY CURVE</span>
        <span className={`text-sm font-mono font-bold ${isPositive ? "text-bull" : "text-bear"}`}>
          {lastVal >= 0 ? "+" : ""}{lastVal.toFixed(2)}%
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="eq-grad-bull" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(142, 65%, 42%)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="hsl(142, 65%, 42%)" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="eq-grad-bear" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(0, 68%, 52%)" stopOpacity="0" />
            <stop offset="100%" stopColor="hsl(0, 68%, 52%)" stopOpacity="0.3" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={scaleY(tick)} x2={W - PAD.right} y2={scaleY(tick)} stroke="hsl(0,0%,13%)" strokeWidth="0.5" />
            <text x={PAD.left - 8} y={scaleY(tick) + 3} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="end">
              {tick.toFixed(1)}%
            </text>
          </g>
        ))}

        {/* Zero line */}
        <line x1={PAD.left} y1={zeroY} x2={W - PAD.right} y2={zeroY} stroke="hsl(0,0%,20%)" strokeWidth="1" strokeDasharray="4,4" />

        {/* Area fill */}
        <path d={areaD} fill={`url(#${fillId})`} />

        {/* Line */}
        <path d={pathD} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinejoin="round" />

        {/* End dot */}
        <circle cx={scaleX(data.length - 1)} cy={scaleY(lastVal)} r="3" fill={strokeColor} />
      </svg>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/EquityCurve.tsx
git commit -m "feat: add SVG equity curve chart component"
```

---

## Task 7: Monthly Heatmap + Calibration + Agent Leaderboard Components

**Files:**
- Create: `frontend/components/MonthlyHeatmap.tsx`
- Create: `frontend/components/CalibrationChart.tsx`
- Create: `frontend/components/AgentLeaderboard.tsx`

- [ ] **Step 1: Create MonthlyHeatmap**

Create `frontend/components/MonthlyHeatmap.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";
import type { MonthlyReturn } from "@/lib/api";

interface MonthlyHeatmapProps {
  data: MonthlyReturn[];
}

const MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function MonthlyHeatmap({ data }: MonthlyHeatmapProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[200px]">
        <span className="text-muted-foreground font-mono text-xs">NO MONTHLY DATA YET</span>
      </div>
    );
  }

  // Group by year
  const byYear: Record<string, Record<number, MonthlyReturn>> = {};
  for (const m of data) {
    const [year, month] = m.month.split("-");
    if (!byYear[year]) byYear[year] = {};
    byYear[year][parseInt(month) - 1] = m;
  }

  const years = Object.keys(byYear).sort();

  function cellColor(pnl: number): string {
    if (pnl > 5) return "bg-bull/20 text-bull";
    if (pnl > 0) return "bg-bull/10 text-bull";
    if (pnl === 0) return "bg-muted text-muted-foreground";
    if (pnl > -5) return "bg-bear/10 text-bear";
    return "bg-bear/20 text-bear";
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">MONTHLY RETURNS</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="text-[9px] font-mono text-muted-foreground px-1 py-1 text-left">YEAR</th>
              {MONTH_LABELS.map((m) => (
                <th key={m} className="text-[9px] font-mono text-muted-foreground px-1 py-1 text-center w-[60px]">{m}</th>
              ))}
              <th className="text-[9px] font-mono text-muted-foreground px-1 py-1 text-center">YTD</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => {
              const yearData = byYear[year];
              const ytd = Object.values(yearData).reduce((sum, m) => sum + m.total_pnl_pct, 0);
              return (
                <tr key={year}>
                  <td className="text-[10px] font-mono font-bold text-foreground px-1 py-0.5">{year}</td>
                  {Array.from({ length: 12 }, (_, i) => {
                    const m = yearData[i];
                    return (
                      <td key={i} className="px-0.5 py-0.5">
                        {m ? (
                          <div className={cn("text-center text-[10px] font-mono font-bold rounded px-1 py-1", cellColor(m.total_pnl_pct))}>
                            {m.total_pnl_pct >= 0 ? "+" : ""}{m.total_pnl_pct.toFixed(1)}%
                          </div>
                        ) : (
                          <div className="text-center text-[10px] font-mono text-muted-foreground/30 px-1 py-1">—</div>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-0.5 py-0.5">
                    <div className={cn("text-center text-[10px] font-mono font-bold rounded px-1 py-1", cellColor(ytd))}>
                      {ytd >= 0 ? "+" : ""}{ytd.toFixed(1)}%
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create CalibrationChart**

Create `frontend/components/CalibrationChart.tsx`:

```tsx
"use client";

import type { CalibrationBucket } from "@/lib/api";

interface CalibrationChartProps {
  data: CalibrationBucket[];
}

export function CalibrationChart({ data }: CalibrationChartProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[260px]">
        <span className="text-muted-foreground font-mono text-xs">NO CALIBRATION DATA YET</span>
      </div>
    );
  }

  const W = 400;
  const H = 260;
  const PAD = { top: 20, right: 20, bottom: 30, left: 50 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const scaleX = (v: number) => PAD.left + (v / 100) * plotW;
  const scaleY = (v: number) => PAD.top + plotH - (v / 100) * plotH;

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">CONFIDENCE CALIBRATION</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {/* Perfect calibration line */}
        <line
          x1={scaleX(0)} y1={scaleY(0)} x2={scaleX(100)} y2={scaleY(100)}
          stroke="hsl(0,0%,20%)" strokeWidth="1" strokeDasharray="4,4"
        />

        {/* Axis labels */}
        <text x={W / 2} y={H - 4} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="middle">
          CONFIDENCE %
        </text>
        <text x={12} y={H / 2} fill="hsl(0,0%,42%)" fontSize="9" fontFamily="monospace" textAnchor="middle" transform={`rotate(-90, 12, ${H / 2})`}>
          WIN RATE %
        </text>

        {/* Grid */}
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={PAD.left} y1={scaleY(v)} x2={W - PAD.right} y2={scaleY(v)} stroke="hsl(0,0%,10%)" strokeWidth="0.5" />
            <text x={PAD.left - 6} y={scaleY(v) + 3} fill="hsl(0,0%,42%)" fontSize="8" fontFamily="monospace" textAnchor="end">{v}</text>
          </g>
        ))}

        {/* Data points */}
        {data.map((bucket, i) => {
          const cx = scaleX(bucket.confidence_midpoint);
          const cy = scaleY(bucket.actual_win_rate_pct);
          const r = Math.max(4, Math.min(12, bucket.total * 1.5));
          const isAboveLine = bucket.actual_win_rate_pct >= bucket.confidence_midpoint;
          return (
            <g key={i}>
              <circle
                cx={cx} cy={cy} r={r}
                fill={isAboveLine ? "hsl(142, 65%, 42%, 0.3)" : "hsl(0, 68%, 52%, 0.3)"}
                stroke={isAboveLine ? "hsl(142, 65%, 42%)" : "hsl(0, 68%, 52%)"}
                strokeWidth="1"
              />
              <text x={cx} y={cy - r - 4} fill="hsl(0,0%,60%)" fontSize="8" fontFamily="monospace" textAnchor="middle">
                {bucket.actual_win_rate_pct.toFixed(0)}%
              </text>
            </g>
          );
        })}
      </svg>
      <p className="text-[9px] font-mono text-muted-foreground mt-1">
        Dots above the diagonal = model is underconfident (good). Below = overconfident.
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Create AgentLeaderboard**

Create `frontend/components/AgentLeaderboard.tsx`:

```tsx
"use client";

import { cn } from "@/lib/utils";
import type { AgentPerformance } from "@/lib/api";

interface AgentLeaderboardProps {
  data: AgentPerformance[];
}

const AGENT_COLORS: Record<string, string> = {
  fundamental: "text-[hsl(220,91%,54%)]",
  technical: "text-[hsl(38,85%,52%)]",
  sentiment: "text-[hsl(142,65%,42%)]",
  macro: "text-[hsl(280,75%,58%)]",
  order_flow: "text-[hsl(201,90%,52%)]",
  regime_change: "text-[hsl(0,68%,52%)]",
  correlation: "text-[hsl(170,70%,45%)]",
};

export function AgentLeaderboard({ data }: AgentLeaderboardProps) {
  if (!data.length) {
    return (
      <div className="panel p-6 flex items-center justify-center h-[200px]">
        <span className="text-muted-foreground font-mono text-xs">NO AGENT DATA YET</span>
      </div>
    );
  }

  return (
    <div className="panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">AGENT LEADERBOARD</span>
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-left">#</th>
            <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-left">AGENT</th>
            <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">ACCURACY</th>
            <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">SIGNALS</th>
            <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">AVG CONF</th>
          </tr>
        </thead>
        <tbody>
          {data.map((agent, i) => (
            <tr key={agent.agent} className="border-b border-border/50">
              <td className="text-[10px] font-mono text-muted-foreground py-1.5">{i + 1}</td>
              <td className={cn("text-[11px] font-mono font-bold py-1.5 uppercase", AGENT_COLORS[agent.agent] || "text-foreground")}>
                {agent.agent.replace("_", " ")}
              </td>
              <td className="text-right">
                <span className={cn(
                  "text-[11px] font-mono font-bold",
                  agent.accuracy_pct >= 55 ? "text-bull" : agent.accuracy_pct >= 45 ? "text-foreground" : "text-bear"
                )}>
                  {agent.accuracy_pct.toFixed(1)}%
                </span>
              </td>
              <td className="text-[10px] font-mono text-muted-foreground text-right py-1.5">{agent.total_signals}</td>
              <td className="text-[10px] font-mono text-muted-foreground text-right py-1.5">{agent.avg_confidence.toFixed(0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/MonthlyHeatmap.tsx frontend/components/CalibrationChart.tsx frontend/components/AgentLeaderboard.tsx
git commit -m "feat: add monthly heatmap, calibration chart, and agent leaderboard components"
```

---

## Task 8: Performance Dashboard Page

**Files:**
- Create: `frontend/app/performance/page.tsx`
- Modify: `frontend/components/Navbar.tsx`

- [ ] **Step 1: Create /performance page**

Create `frontend/app/performance/page.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Activity, BarChart2, Target, Zap, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { wakeBackend, getPerformanceSummary, getEquityCurve, getByAssetClass, getByAgent, getCalibration, getMonthlyReturns } from "@/lib/api";
import type { PerformanceSummary, EquityCurvePoint, AssetClassPerformance, AgentPerformance, CalibrationBucket, MonthlyReturn } from "@/lib/api";
import { EquityCurve } from "@/components/EquityCurve";
import { MonthlyHeatmap } from "@/components/MonthlyHeatmap";
import { CalibrationChart } from "@/components/CalibrationChart";
import { AgentLeaderboard } from "@/components/AgentLeaderboard";

export default function PerformancePage() {
  const [summary, setSummary] = useState<PerformanceSummary | null>(null);
  const [curve, setCurve] = useState<EquityCurvePoint[]>([]);
  const [assetClasses, setAssetClasses] = useState<AssetClassPerformance[]>([]);
  const [agents, setAgents] = useState<AgentPerformance[]>([]);
  const [calibration, setCalibration] = useState<CalibrationBucket[]>([]);
  const [monthly, setMonthly] = useState<MonthlyReturn[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    wakeBackend();
    Promise.allSettled([
      getPerformanceSummary().then(setSummary),
      getEquityCurve().then((r) => setCurve(r.curve)),
      getByAssetClass().then((r) => setAssetClasses(r.asset_classes)),
      getByAgent().then((r) => setAgents(r.agents)),
      getCalibration().then((r) => setCalibration(r.calibration)),
      getMonthlyReturns().then((r) => setMonthly(r.months)),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="live-dot mx-auto mb-3" />
          <p className="text-[10px] font-mono text-muted-foreground tracking-widest">LOADING PERFORMANCE DATA</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">Performance Dashboard</h1>
        <p className="text-xs font-mono text-muted-foreground mt-1">
          Live track record — all signals, all agents, full transparency
        </p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard
            label="TOTAL SIGNALS"
            value={String(summary.total_signals)}
            icon={<Activity className="h-3.5 w-3.5 text-primary" />}
          />
          <StatCard
            label="WIN RATE"
            value={`${summary.win_rate_pct}%`}
            icon={<Target className="h-3.5 w-3.5 text-bull" />}
            valueColor={summary.win_rate_pct >= 50 ? "text-bull" : "text-bear"}
          />
          <StatCard
            label="AVG P&L"
            value={`${summary.avg_pnl_pct >= 0 ? "+" : ""}${summary.avg_pnl_pct}%`}
            icon={summary.avg_pnl_pct >= 0 ? <TrendingUp className="h-3.5 w-3.5 text-bull" /> : <TrendingDown className="h-3.5 w-3.5 text-bear" />}
            valueColor={summary.avg_pnl_pct >= 0 ? "text-bull" : "text-bear"}
          />
          <StatCard
            label="AVG CONFIDENCE"
            value={`${summary.avg_confidence}`}
            icon={<Zap className="h-3.5 w-3.5 text-warn" />}
          />
        </div>
      )}

      {/* Active / Resolved badges */}
      {summary && (
        <div className="flex items-center gap-4 mb-6">
          <div className="flex items-center gap-1.5">
            <div className="live-dot" />
            <span className="text-[10px] font-mono text-muted-foreground">
              {summary.active_signals} ACTIVE
            </span>
          </div>
          <span className="text-[10px] font-mono text-muted-foreground">
            {summary.wins}W / {summary.losses}L resolved
          </span>
        </div>
      )}

      {/* Equity Curve */}
      <div className="mb-6">
        <EquityCurve data={curve} />
      </div>

      {/* Two-column: Monthly Heatmap + Asset Class Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <MonthlyHeatmap data={monthly} />

        {/* Asset Class Breakdown */}
        <div className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart2 className="h-3.5 w-3.5 text-primary" />
            <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">BY ASSET CLASS</span>
          </div>
          {assetClasses.length === 0 ? (
            <div className="flex items-center justify-center h-[120px]">
              <span className="text-muted-foreground font-mono text-xs">NO DATA YET</span>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-left">CLASS</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">SIGNALS</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">WIN RATE</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-1.5 text-right">AVG P&L</th>
                </tr>
              </thead>
              <tbody>
                {assetClasses.map((ac) => (
                  <tr key={ac.asset_class} className="border-b border-border/50">
                    <td className="text-[11px] font-mono font-bold text-foreground py-1.5 uppercase">{ac.asset_class}</td>
                    <td className="text-[10px] font-mono text-muted-foreground text-right py-1.5">{ac.total}</td>
                    <td className={cn("text-[11px] font-mono font-bold text-right py-1.5", ac.win_rate_pct >= 50 ? "text-bull" : "text-bear")}>
                      {ac.win_rate_pct.toFixed(1)}%
                    </td>
                    <td className={cn("text-[10px] font-mono text-right py-1.5", ac.avg_pnl_pct >= 0 ? "text-bull" : "text-bear")}>
                      {ac.avg_pnl_pct >= 0 ? "+" : ""}{ac.avg_pnl_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Two-column: Agent Leaderboard + Calibration */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <AgentLeaderboard data={agents} />
        <CalibrationChart data={calibration} />
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, valueColor }: { label: string; value: string; icon: React.ReactNode; valueColor?: string }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center gap-1.5 mb-1.5">
        {icon}
        <span className="text-[9px] font-mono font-bold text-muted-foreground tracking-widest">{label}</span>
      </div>
      <span className={cn("text-lg font-mono font-bold", valueColor || "text-foreground")}>{value}</span>
    </div>
  );
}
```

- [ ] **Step 2: Add Performance and Journal links to Navbar**

In `frontend/components/Navbar.tsx`, add navigation links for `/performance` and `/journal`. Find the nav links section and add:

```tsx
<Link href="/performance" className={cn("text-[10px] font-mono tracking-wider transition-colors", pathname === "/performance" ? "text-primary" : "text-muted-foreground hover:text-foreground")}>
  PERFORMANCE
</Link>
<Link href="/journal" className={cn("text-[10px] font-mono tracking-wider transition-colors", pathname === "/journal" ? "text-primary" : "text-muted-foreground hover:text-foreground")}>
  JOURNAL
</Link>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/performance/page.tsx frontend/components/Navbar.tsx
git commit -m "feat: add public performance dashboard page with charts"
```

---

## Task 9: Signal Detail Modal

**Files:**
- Create: `frontend/components/SignalDetailModal.tsx`

- [ ] **Step 1: Create signal detail overlay**

Create `frontend/components/SignalDetailModal.tsx`:

```tsx
"use client";

import { X, TrendingUp, TrendingDown, Clock, Target, Shield } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Signal } from "@/lib/api";

interface SignalDetailModalProps {
  signal: Signal;
  onClose: () => void;
}

export function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  const isLong = signal.direction === "LONG";
  const isWin = signal.outcome === "WIN";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="panel-raised relative w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        {/* Close */}
        <button onClick={onClose} className="absolute top-3 right-3 text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold", isLong ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear")}>
            {signal.direction}
          </div>
          <span className="text-lg font-mono font-bold">{signal.ticker}</span>
          <span className="text-[10px] font-mono text-muted-foreground uppercase">{signal.asset_class}</span>
          {signal.outcome && (
            <div className={cn("px-2 py-0.5 rounded text-[10px] font-mono font-bold ml-auto", isWin ? "bg-bull/10 text-bull" : "bg-bear/10 text-bear")}>
              {signal.outcome} {signal.pnl_pct != null && `(${signal.pnl_pct >= 0 ? "+" : ""}${signal.pnl_pct.toFixed(2)}%)`}
            </div>
          )}
        </div>

        {/* Price levels */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <LevelCell label="ENTRY" value={signal.entry_price} />
          <LevelCell label="STOP LOSS" value={signal.stop_loss} color="text-bear" />
          <LevelCell label="TP1" value={signal.take_profit_1} color="text-bull" />
          <LevelCell label="TP2" value={signal.take_profit_2} color="text-bull" />
          {signal.exit_price && <LevelCell label="EXIT" value={signal.exit_price} color={isWin ? "text-bull" : "text-bear"} />}
        </div>

        {/* Confidence + Meta */}
        <div className="flex items-center gap-4 mb-4 text-[10px] font-mono text-muted-foreground">
          <span>CONF: <span className="text-foreground font-bold">{signal.confidence_score}</span></span>
          <span>STATUS: <span className="text-foreground font-bold">{signal.status}</span></span>
          <span><Clock className="inline h-3 w-3" /> {new Date(signal.timestamp).toLocaleString()}</span>
        </div>

        {/* Agent Votes */}
        {signal.agent_votes && typeof signal.agent_votes === "object" && (
          <div className="mb-4">
            <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">AGENT VOTES</span>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-2">
              {Object.entries(signal.agent_votes).map(([agent, vote]) => {
                if (typeof vote !== "object" || vote === null) return null;
                const v = vote as { direction?: string; confidence?: number };
                if (!v.direction) return null;
                return (
                  <div key={agent} className="flex items-center justify-between bg-surface-2 rounded px-2 py-1">
                    <span className="text-[10px] font-mono text-foreground uppercase">{agent.replace("_", " ")}</span>
                    <div className="flex items-center gap-1.5">
                      <span className={cn("text-[10px] font-mono font-bold", v.direction === "LONG" ? "text-bull" : "text-bear")}>
                        {v.direction}
                      </span>
                      <span className="text-[9px] font-mono text-muted-foreground">{v.confidence ?? 0}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Reasoning Chain */}
        {signal.reasoning_chain && signal.reasoning_chain.length > 0 && (
          <div className="mb-4">
            <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">REASONING CHAIN</span>
            <div className="mt-2 space-y-1">
              {signal.reasoning_chain.map((step, i) => (
                <div key={i} className="text-[11px] font-mono text-foreground/80 flex gap-2">
                  <span className="text-muted-foreground shrink-0">{i + 1}.</span>
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strategy Sources */}
        {signal.strategy_sources && signal.strategy_sources.length > 0 && (
          <div>
            <span className="text-[10px] font-mono font-bold text-muted-foreground tracking-widest">STRATEGIES</span>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {signal.strategy_sources.map((s, i) => (
                <span key={i} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-primary/10 text-primary">{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function LevelCell({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="data-cell">
      <span className="data-cell-label">{label}</span>
      <span className={cn("data-cell-value", color || "text-foreground")}>{value.toFixed(2)}</span>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/SignalDetailModal.tsx
git commit -m "feat: add signal detail modal for journal page"
```

---

## Task 10: Signal Journal Page

**Files:**
- Create: `frontend/app/journal/page.tsx`

- [ ] **Step 1: Create /journal page**

Create `frontend/app/journal/page.tsx`:

```tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Filter, ChevronLeft, ChevronRight, TrendingUp, TrendingDown, Target, BarChart2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { wakeBackend, getJournalSignals, listSignals } from "@/lib/api";
import type { Signal } from "@/lib/api";
import { SignalDetailModal } from "@/components/SignalDetailModal";

const PAGE_SIZE = 20;

export default function JournalPage() {
  const router = useRouter();
  const [user, setUser] = useState<unknown>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  // Filters
  const [tickerFilter, setTickerFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [assetFilter, setAssetFilter] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        // Also check localStorage for demo user
        const token = localStorage.getItem("token");
        if (!token) {
          router.push("/login");
          return;
        }
      }
      setUser(session?.user || { demo: true });
    });
  }, [router]);

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getJournalSignals({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        ticker: tickerFilter || undefined,
        outcome: outcomeFilter || undefined,
        asset_class: assetFilter || undefined,
      });
      setSignals(data);
    } catch {
      // Fallback to basic listSignals if journal endpoint not deployed yet
      try {
        const data = await listSignals(PAGE_SIZE);
        setSignals(data);
      } catch { /* ignore */ }
    } finally {
      setLoading(false);
    }
  }, [page, tickerFilter, outcomeFilter, assetFilter]);

  useEffect(() => {
    if (user) {
      wakeBackend();
      fetchSignals();
    }
  }, [user, fetchSignals]);

  // Personal stats
  const totalSignals = signals.length;
  const wins = signals.filter((s) => s.outcome === "WIN").length;
  const losses = signals.filter((s) => s.outcome === "LOSS").length;
  const resolved = wins + losses;
  const winRate = resolved > 0 ? ((wins / resolved) * 100).toFixed(1) : "—";
  const avgPnl = signals.filter((s) => s.pnl_pct != null).reduce((sum, s) => sum + (s.pnl_pct || 0), 0);

  if (!user) return null;

  return (
    <div className="min-h-screen p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-bold tracking-tight">Signal Journal</h1>
        <p className="text-xs font-mono text-muted-foreground mt-1">Your complete signal history with outcomes and analysis</p>
      </div>

      {/* Personal Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="panel p-3">
          <span className="text-[9px] font-mono text-muted-foreground tracking-widest">TOTAL SIGNALS</span>
          <div className="text-lg font-mono font-bold">{totalSignals}</div>
        </div>
        <div className="panel p-3">
          <span className="text-[9px] font-mono text-muted-foreground tracking-widest">WIN RATE</span>
          <div className={cn("text-lg font-mono font-bold", Number(winRate) >= 50 ? "text-bull" : resolved > 0 ? "text-bear" : "text-foreground")}>
            {winRate}{winRate !== "—" && "%"}
          </div>
        </div>
        <div className="panel p-3">
          <span className="text-[9px] font-mono text-muted-foreground tracking-widest">W / L</span>
          <div className="text-lg font-mono font-bold">
            <span className="text-bull">{wins}</span>
            <span className="text-muted-foreground"> / </span>
            <span className="text-bear">{losses}</span>
          </div>
        </div>
        <div className="panel p-3">
          <span className="text-[9px] font-mono text-muted-foreground tracking-widest">CUMULATIVE P&L</span>
          <div className={cn("text-lg font-mono font-bold", avgPnl >= 0 ? "text-bull" : "text-bear")}>
            {avgPnl >= 0 ? "+" : ""}{avgPnl.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            className="input-terminal pl-7 w-[140px]"
            placeholder="Ticker..."
            value={tickerFilter}
            onChange={(e) => { setTickerFilter(e.target.value.toUpperCase()); setPage(0); }}
          />
        </div>
        <select
          className="input-terminal w-[120px]"
          value={outcomeFilter}
          onChange={(e) => { setOutcomeFilter(e.target.value); setPage(0); }}
        >
          <option value="">All Outcomes</option>
          <option value="WIN">WIN</option>
          <option value="LOSS">LOSS</option>
          <option value="EXPIRED">EXPIRED</option>
        </select>
        <select
          className="input-terminal w-[120px]"
          value={assetFilter}
          onChange={(e) => { setAssetFilter(e.target.value); setPage(0); }}
        >
          <option value="">All Classes</option>
          <option value="stocks">Stocks</option>
          <option value="crypto">Crypto</option>
          <option value="fx">Forex</option>
          <option value="commodities">Commodities</option>
          <option value="indices">Indices</option>
        </select>
        {(tickerFilter || outcomeFilter || assetFilter) && (
          <button
            className="btn btn-ghost text-[9px]"
            onClick={() => { setTickerFilter(""); setOutcomeFilter(""); setAssetFilter(""); setPage(0); }}
          >
            CLEAR
          </button>
        )}
      </div>

      {/* Signal Table */}
      <div className="panel overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-[200px]">
            <div className="live-dot" />
          </div>
        ) : signals.length === 0 ? (
          <div className="flex items-center justify-center h-[200px]">
            <span className="text-muted-foreground font-mono text-xs">NO SIGNALS FOUND</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-surface-2">
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-left">DATE</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-left">TICKER</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-left">DIR</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-right">ENTRY</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-right">CONF</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-center">OUTCOME</th>
                  <th className="text-[9px] font-mono text-muted-foreground py-2 px-3 text-right">P&L</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((signal) => (
                  <tr
                    key={signal.signal_id}
                    className="border-b border-border/50 hover:bg-surface-2/50 cursor-pointer transition-colors"
                    onClick={() => setSelectedSignal(signal)}
                  >
                    <td className="text-[10px] font-mono text-muted-foreground py-2 px-3">
                      {new Date(signal.timestamp).toLocaleDateString()}
                    </td>
                    <td className="text-[11px] font-mono font-bold text-foreground py-2 px-3">{signal.ticker}</td>
                    <td className="py-2 px-3">
                      <span className={cn("text-[10px] font-mono font-bold", signal.direction === "LONG" ? "text-bull" : "text-bear")}>
                        {signal.direction}
                      </span>
                    </td>
                    <td className="text-[10px] font-mono text-foreground text-right py-2 px-3">{signal.entry_price.toFixed(2)}</td>
                    <td className="text-[10px] font-mono text-foreground text-right py-2 px-3">{signal.confidence_score}</td>
                    <td className="text-center py-2 px-3">
                      {signal.outcome ? (
                        <span className={cn(
                          "text-[9px] font-mono font-bold px-1.5 py-0.5 rounded",
                          signal.outcome === "WIN" ? "bg-bull/10 text-bull" : signal.outcome === "LOSS" ? "bg-bear/10 text-bear" : "bg-warn/10 text-warn"
                        )}>
                          {signal.outcome}
                        </span>
                      ) : (
                        <span className="text-[9px] font-mono text-muted-foreground">ACTIVE</span>
                      )}
                    </td>
                    <td className={cn("text-[10px] font-mono font-bold text-right py-2 px-3",
                      signal.pnl_pct != null ? (signal.pnl_pct >= 0 ? "text-bull" : "text-bear") : "text-muted-foreground"
                    )}>
                      {signal.pnl_pct != null ? `${signal.pnl_pct >= 0 ? "+" : ""}${signal.pnl_pct.toFixed(2)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-border">
          <span className="text-[9px] font-mono text-muted-foreground">
            Page {page + 1} · {signals.length} results
          </span>
          <div className="flex items-center gap-1">
            <button className="btn btn-ghost p-1" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button className="btn btn-ghost p-1" disabled={signals.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/journal/page.tsx
git commit -m "feat: add authenticated signal journal page with filters and detail view"
```

---

## Task 11: Final Integration + Deploy

- [ ] **Step 1: Verify all imports and registrations in main.py**

Ensure `backend/app/main.py` has:
```python
from app.api.routes import auth, signals, portfolio, agents, backtest, debate, market, news, profiles, session
from app.api.routes import evaluation, performance
# ...
app.include_router(evaluation.router)
app.include_router(performance.router)
```

- [ ] **Step 2: Run backend locally and test**

```bash
cd C:/Users/Liv/ai-trading-copilot/backend
uvicorn app.main:app --reload --port 8000
```

Test all new endpoints return valid JSON (even if empty).

- [ ] **Step 3: Run frontend locally and test**

```bash
cd C:/Users/Liv/ai-trading-copilot/frontend
npm run dev
```

Visit:
- `http://localhost:3000/performance` — should load with empty-state placeholders
- `http://localhost:3000/journal` — should redirect to login if not authenticated

- [ ] **Step 4: Final commit + push**

```bash
git add -A
git status  # verify no secrets
git commit -m "feat: Phase 5 — Performance Dashboard, Signal Journal, Evaluation Loop"
git push origin main
```

- [ ] **Step 5: Verify deployment**

- Check Render dashboard for successful backend deploy
- Check Vercel dashboard for successful frontend deploy
- Visit `https://app.quantneuraledge.com/performance`
- Visit `https://app.quantneuraledge.com/journal`

---

## Summary of Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/signals/evaluate` | Required | Auto-check ACTIVE signals against TP/SL |
| GET | `/api/v1/signals/journal` | Optional | Filtered signal history |
| GET | `/api/v1/performance/summary` | None | Totals, win rate, avg P&L |
| GET | `/api/v1/performance/equity-curve` | None | Cumulative P&L curve |
| GET | `/api/v1/performance/by-asset-class` | None | Win rate by asset class |
| GET | `/api/v1/performance/by-agent` | None | Agent accuracy leaderboard |
| GET | `/api/v1/performance/calibration` | None | Confidence vs actual win rate |
| GET | `/api/v1/performance/monthly` | None | Monthly returns for heatmap |
