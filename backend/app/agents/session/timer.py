"""
SessionTimer — Kill zone detection and session timing.

Kill zones (UTC):
  - TOKYO:   00:00 - 03:00 UTC
  - LONDON:  07:00 - 10:00 UTC
  - NY_OPEN: 13:30 - 16:00 UTC
  - OVERLAP: 13:30 - 16:30 UTC (London + NY overlap)

Pure Python — no LLM needed.
"""
from datetime import datetime, timezone
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState


KILL_ZONES = {
    "TOKYO":   ((0, 0),   (3, 0)),
    "LONDON":  ((7, 0),   (10, 0)),
    "NY_OPEN": ((13, 30), (16, 0)),
    "OVERLAP": ((13, 30), (16, 30)),
}


class SessionTimer(BaseAgent):
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

        next_zone = None
        next_zone_minutes = 9999
        if active_zone == "NONE":
            for zone_name, ((sh, sm), _) in KILL_ZONES.items():
                start_min = sh * 60 + sm
                delta = start_min - current_minutes
                if delta < 0:
                    delta += 1440
                if delta < next_zone_minutes:
                    next_zone_minutes = delta
                    next_zone = zone_name

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
