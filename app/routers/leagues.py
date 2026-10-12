import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.session import get_db
from app.models.club import Club
from app.schemas.league import (
    JoinLeagueRequest,
    JoinLeagueResponse,
    LeagueDetailRead,
    LeagueSummaryRead,
    LeagueUpdatedPayload,
)
from app.services.exceptions_player import AppException
from app.services.league_service import (
    count_enrolled_clubs,
    get_league,
    join_league,
    list_open_leagues,
)
from app.ws.manager import league_list_manager

router = APIRouter(prefix="/api", tags=["Leagues"])
logger = logging.getLogger(__name__)


@router.post("/leagues/{league_id}/join", response_model=JoinLeagueResponse)
def join_league_endpoint(
    league_id: str,
    payload: JoinLeagueRequest,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> JoinLeagueResponse:
    try:
        response = join_league(db, league_id, club, payload)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e
    _publish_league_updated(db, response.league_id)
    return response


def _publish_league_updated(db: Session, league_id: str) -> None:
    # Best-effort: the join is already committed, so a failed notice must not turn it into a 500.
    try:
        enrolled_clubs = count_enrolled_clubs(db, league_id)
        league_list_manager.broadcast(
            "LEAGUE_UPDATED",
            LeagueUpdatedPayload(league_id=league_id, enrolled_clubs=enrolled_clubs),
        )
    except Exception:
        logger.exception("No se pudo notificar LEAGUE_UPDATED")


@router.get("/leagues/{league_id}", response_model=LeagueDetailRead)
def read_league_endpoint(
    league_id: str,
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> LeagueDetailRead:
    try:
        return get_league(db, league_id, club)
    except AppException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"detail": e.message, "error_code": e.code},
        ) from e


@router.get("/leagues", response_model=list[LeagueSummaryRead])
def list_leagues_endpoint(
    db: Session = Depends(get_db),
    club: Club = Depends(get_current_club),
) -> list[LeagueSummaryRead]:
    return list_open_leagues(db, club)
