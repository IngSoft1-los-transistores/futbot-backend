from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.session import get_db
from app.models.club import Club
from app.schemas.league import JoinLeagueRequest, JoinLeagueResponse
from app.services.exceptions_player import AppException
from app.services.league_service import join_league

router = APIRouter(prefix="/api", tags=["Leagues"])


@router.post("/leagues/{league_id}/join", response_model=JoinLeagueResponse)
def join_league_endpoint(
    league_id: str,
    payload: JoinLeagueRequest,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> JoinLeagueResponse:
    try:
        return join_league(db, league_id, club, payload)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e
