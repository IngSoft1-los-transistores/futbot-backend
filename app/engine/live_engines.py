# app/engine/live_engines.py
from typing import TYPE_CHECKING

from app.engine.state import Team

if TYPE_CHECKING:
    from app.engine.match_engine import MatchEngine

# match_id -> engine of the match currently running in this process
engines: dict[str, "MatchEngine"] = {}


def club_has_dt(match_id: str, home_club_id: str, club_id: str) -> bool:
    engine = engines.get(match_id)
    if engine is None:
        return False
    team = Team.HOME if club_id == home_club_id else Team.AWAY
    return engine.has_dt(team)