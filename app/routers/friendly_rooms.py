from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, UserMock
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
    current_user: UserMock = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = FriendlyService(db)
    return service.create_room(club_id=current_user.club_id, request=payload)