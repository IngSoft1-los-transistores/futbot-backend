from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.schemas.friendly_room import CreateFriendlyRoomRequest, FriendlyRoomResponse, JoinFriendlyRoomRequest, JoinFriendlyRoomResponse
from app.services.friendly_service import FriendlyService
from app.ws.manager import manager
from app.models.user import User

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

@router.post(
    "/{room_id}/join",
    response_model=JoinFriendlyRoomResponse,
    status_code=status.HTTP_200_OK,
    summary="Unirse a una sala de amistoso"
)

async def join_friendly_room(
    room_id: str,
    payload: JoinFriendlyRoomRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Mismo chequeo que al crear: el usuario autenticado necesita un club
    if not current_user.club:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario autenticado no tiene un club asociado."
        )
    service = FriendlyService(db)
    result = service.join_room(club_id=current_user.club.id, room_id=room_id, request=payload)
    await manager.broadcast(result.room_id, {
        "type": "guest_joined",
        "awayClub": result.away_club,
        "status": result.status,
    })
    return result
