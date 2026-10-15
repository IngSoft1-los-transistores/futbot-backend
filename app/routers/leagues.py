from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.league import LeagueResponse
from app.services.league_service import LeagueService

router = APIRouter(
    prefix="/api/leagues",
    tags=["Leagues"]
)


@router.get(
    "",
    response_model=list[LeagueResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar ligas registradas"
)
def list_leagues(
    name: str | None = Query(default=None, max_length=80, description="Filtra por nombre (contiene)"),
    current_user: User = Depends(get_current_user),     # valida el token: sin él responde 401
    db: Session = Depends(get_db),
):
    return LeagueService(db).list_leagues(name=name)