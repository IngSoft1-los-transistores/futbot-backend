from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.player import PlayerCreate, PlayerResponse
from app.services.exceptions_player import AppException
from app.services.player_service import create_player

router = APIRouter(prefix="/api", tags=["create player"])


# Ticket: BE [BE] Endpoint Crear Jugador de Club
@router.post("/players", status_code=201, response_model=PlayerResponse)
def create_player_endpoint(
    player_data: PlayerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        player = create_player(db, current_user.club.id, player_data)
        return player

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
