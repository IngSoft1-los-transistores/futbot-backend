from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.session import get_db
from app.models.club import Club
from app.schemas.league import CreateLeague, LeagueResponse
from app.services.exceptions_player import AppException
from app.services.league_service import create_league

router = APIRouter(prefix="/api", tags=["Create League"])


@router.post("/leagues", status_code=201, response_model=LeagueResponse)
def crear_liga_endpoint(
    league_data: CreateLeague,
    db: Session = Depends(get_db),
    current_club: Club = Depends(get_current_club),
) -> LeagueResponse:
    try:
        league = create_league(db, league_data, current_club)
        return league
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
