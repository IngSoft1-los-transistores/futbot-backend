from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.room import (
    Room,
    ROOM_TYPE_PUBLIC,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_FINISHED,
)
from app.schemas.league import LeagueResponse

STARTED_STATUSES = (ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)


def like_pattern(text: str) -> str:
    """Arma un patron 'contiene' tratando %, _ y \\ como texto normal."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class LeagueService:
    def __init__(self, db: Session):
        self.db = db

    def list_leagues(self, name: str | None = None) -> list[LeagueResponse]:
        # Cantidad de clubes inscriptos por sala
        counts = (
            select(Enrollment.room_id.label("room_id"), func.count(Enrollment.club_id).label("total"))
            .group_by(Enrollment.room_id)
            .subquery()
        )

        query = (
            select(Room, func.coalesce(counts.c.total, 0))
            .outerjoin(counts, counts.c.room_id == Room.id)      # una liga sin inscriptos cuenta 0
            .where(
                Room.type == ROOM_TYPE_PUBLIC,
                Room.status != ROOM_STATUS_CANCELLED,
            )
            .order_by(Room.name, Room.id)
        )

        clean_name = (name or "").strip()
        if clean_name:
            query = query.where(Room.name.ilike(like_pattern(clean_name), escape="\\"))

        return [
            LeagueResponse(
                id=room.id,
                name=room.name,
                participants_count=total,
                started=room.status in STARTED_STATUSES,
                is_private=False,
            )
            for room, total in self.db.execute(query).all()
        ]