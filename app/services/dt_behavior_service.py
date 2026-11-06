from sqlalchemy.orm import Session

from app.engine.live_engines import club_has_dt
from app.models.behavior import BEHAVIOR_KIND_DT, Behavior
from app.models.club import Club
from app.models.match import Match
from app.services.exceptions_dt import (
    BehaviorNotDt,
    BehaviorNotFound,
    ManualActionBlockedByDt,
    NoDtAssigned,
)


def assign_dt(db: Session, club: Club, behavior_id: str) -> Behavior:
    behavior = db.get(Behavior, behavior_id)
    if behavior is None or behavior.deleted_at is not None or behavior.club_id != club.id:
        raise BehaviorNotFound(behavior_id)
    if behavior.kind != BEHAVIOR_KIND_DT:
        raise BehaviorNotDt(behavior_id)
    club.dt_behavior_id = behavior.id
    db.commit()
    return behavior


def clear_dt(db: Session, club: Club) -> None:
    if club.dt_behavior_id is None:
        raise NoDtAssigned()
    club.dt_behavior_id = None
    db.commit()


def get_dt(club: Club) -> Behavior | None:
    behavior = club.dt_behavior
    if behavior is None or behavior.deleted_at is not None:
        return None
    return behavior


def ensure_manual_action_allowed(match: Match, club_id: str) -> None:
    """Call at the start of every manual substitution / behavior-change endpoint."""
    if club_has_dt(match.id, match.home_club_id, club_id):
        raise ManualActionBlockedByDt()
