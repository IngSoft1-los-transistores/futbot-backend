from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_club
from app.db.session import get_db
from app.models.club import Club
from app.models.room import STATE_IN_PROGRESS
from app.schemas.friendly_room import FriendlyRoomRead, FriendlyRoomStartRead
from app.services.friendly_rooms import get_friendly_room, start_friendly_match

"""Friendly rooms router."""

router = APIRouter(prefix="/api/friendly/rooms", tags=["friendly"])


@router.get("/{room_id}", response_model=FriendlyRoomRead)
def read_friendly_room(
    room_id: str,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> FriendlyRoomRead:
    return get_friendly_room(db, room_id, club)


@router.post("/{room_id}/start", response_model=FriendlyRoomStartRead)
def start_friendly_room(
    room_id: str,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> FriendlyRoomStartRead:
    match = start_friendly_match(db, room_id, club)
    return FriendlyRoomStartRead(
        room_id=room_id, match_id=match.id, status=STATE_IN_PROGRESS
    )
