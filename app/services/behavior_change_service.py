from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.match_player import MatchPlayer


def behavior_belongs_to_club(db: Session, behavior_id: str, club_id: str) -> bool:
    found = db.scalar(
        select(Behavior.id).where(
            Behavior.id == behavior_id,
            or_(Behavior.club_id == club_id, Behavior.club_id.is_(None)),
            Behavior.deleted_at.is_(None),
        )
    )
    return found is not None

def save_current_behavior(db: Session, match_id: str, player_id: str, behavior_id: str) -> None:
    db.execute(
        update(MatchPlayer)
        .where(MatchPlayer.match_id == match_id, MatchPlayer.player_id == player_id)
        .values(behavior_id=behavior_id)
    )
    db.commit()
