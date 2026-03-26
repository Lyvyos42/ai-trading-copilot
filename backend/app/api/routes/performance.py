"""
Public performance endpoints — no auth required.
Aggregates all resolved signals for public track record.
"""
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
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
            conf = vote.get("confidence", 0)
            agent_stats[agent_name]["avg_confidence"].append(conf or 0)

            if (vote["direction"] == direction and outcome == "WIN") or (vote["direction"] != direction and outcome == "LOSS"):
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
        bucket = int(conf // 10) * 10
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
