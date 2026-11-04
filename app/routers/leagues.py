from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club, get_current_user
from app.db.session import get_db
from app.models.club import Club
from app.models.user import User
from app.schemas.league import (
    CreateLeague,
    LeagueResponse,
    LeagueStanding,
    ListLeagueResponse,
)
from app.services.exceptions_league import LeagueNotFound
from app.services.exceptions_player import AppException
from app.services.league_service import (
    LeagueService,
    create_league,
    get_league_standings,
)

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


@router.get(
    "/leagues/{league_id}/standings",
    response_model=list[LeagueStanding],
    status_code=status.HTTP_200_OK,
    summary="Consultar la tabla de posiciones de una liga",
)
def league_standings(
    league_id: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LeagueStanding]:
    try:
        return get_league_standings(db, league_id)
    except LeagueNotFound as error:
        raise HTTPException(status_code=404, detail=error.message) from error
