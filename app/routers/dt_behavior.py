from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_club
from app.db.session import get_db
from app.models.behavior import Behavior
from app.models.club import Club
from app.schemas.dt_behavior import DtBehaviorResponse
from app.services import dt_behavior_service
from app.services.exceptions_player import AppException

router = APIRouter(prefix="/api/club/dt-behavior", tags=["dt-behavior"])


def _to_response(behavior: Behavior | None) -> DtBehaviorResponse | None:
    if behavior is None:
        return None
    return DtBehaviorResponse(behavior_id=behavior.id, name=behavior.name)


@router.put("/{behavior_id}", response_model=DtBehaviorResponse)
def put_dt(
    behavior_id: str,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db),
):
    try:
        return _to_response(dt_behavior_service.assign_dt(db, club, behavior_id))
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("", status_code=204)
def delete_dt(
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db),
) -> None:
    try:
        dt_behavior_service.clear_dt(db, club)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("", response_model=DtBehaviorResponse | None)
def get_dt(club=Depends(get_current_club)):
    return _to_response(dt_behavior_service.get_dt(club))

