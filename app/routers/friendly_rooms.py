from fastapi import APIRouter, Depends, HTTPException, status
from pydantic.alias_generators import to_camel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club, get_current_user
from app.db.session import get_db
from app.models.club import Club
from app.models.room import ROOM_STATUS_IN_PROGRESS
from app.models.user import User
from app.schemas.friendly_room import (
    CreateFriendlyRoomRequest,
    FriendlyRoomRead,
    FriendlyRoomResponse,
    FriendlyRoomStartRead,
)
from app.services.friendly_rooms import get_friendly_room, start_friendly_match
from app.services.friendly_service import FriendlyService

router = APIRouter(
    prefix="/api/friendly/rooms",
    tags=["Friendly Rooms"]
)

@router.post(
    "",
    response_model=FriendlyRoomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear sala de partido amistoso"
)

async def create_friendly_room(
    payload: CreateFriendlyRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Sanity check para ver que el usuario autenticado tenga un club asignado (redundante)
    if not current_user.club:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario autenticado no tiene un club asociado."
        )
    service = FriendlyService(db)
    return service.create_room(club_id=str(current_user.club.id), request=payload)


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
        room_id=room_id, match_id=match.id, status=to_camel(ROOM_STATUS_IN_PROGRESS)
    )
