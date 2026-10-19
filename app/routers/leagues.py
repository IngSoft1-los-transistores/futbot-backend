from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_current_club
from app.db.session import get_db
from app.models.user import User
from app.models.club import Club
from app.schemas.league import (
    CreateLeague,
    JoinLeagueRequest,
    JoinLeagueResponse,
    LeagueDetailRead,
    LeagueResponse,
    ListLeagueResponse,
)
from app.services.exceptions_player import AppException
from app.services.league_service import LeagueService, create_league, get_league, join_league

router = APIRouter(
    prefix="/api",
    tags=["Leagues"]
)


@router.get(
    "/leagues",
    response_model=list[ListLeagueResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar ligas registradas"
)
def list_leagues(
    name: str | None = Query(default=None, max_length=80, description="Filtra por nombre (contiene)"),
    current_user: User = Depends(get_current_user),     # valida el token: sin él responde 401
    db: Session = Depends(get_db),
):
    return LeagueService(db).list_leagues(name=name)


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
