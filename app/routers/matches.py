"""Consulta del ultimo estado publicado por el motor."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.match_state import MatchState
from app.services.match_state import (
    MatchAccessDenied, MatchNotFound, MatchStateUnavailable, get_match_state,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get(
    "/{match_id}/state", response_model=MatchState,
    responses={
        401: {"description": "Sesion ausente, invalida o vencida"},
        403: {"description": "El usuario no pertenece a ninguno de los clubes del partido"},
        404: {"description": "Partido inexistente"},
        409: {"description": "El motor aun no publico el estado inicial"},
    },
)
def read_match_state(
    match_id: UUID, response: Response,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> MatchState:
    try:
        state = get_match_state(db, str(match_id), user)
    except MatchNotFound as error:
        raise HTTPException(status_code=404, detail="El partido no existe") from error
    except MatchAccessDenied as error:
        raise HTTPException(status_code=403, detail="No tenes acceso a este partido") from error
    except MatchStateUnavailable as error:
        raise HTTPException(status_code=409, detail="El motor todavia no publico el estado del partido") from error
    response.headers["Cache-Control"] = "no-store"
    return state
