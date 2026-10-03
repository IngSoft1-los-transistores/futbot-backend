from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.friendly_room import CreateFriendlyRoomRequest, FriendlyRoomResponse
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