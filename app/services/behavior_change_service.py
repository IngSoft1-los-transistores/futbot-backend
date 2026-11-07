from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior


def behavior_belongs_to_club(db: Session, behavior_id: str, club_id: str) -> bool:
    found = db.scalar(
        select(Behavior.id).where(
            Behavior.id == behavior_id,
            or_(Behavior.club_id == club_id, Behavior.club_id.is_(None)),
            Behavior.deleted_at.is_(None),
        )
    )
    return found is not None
