import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.club import Club
from app.core.dependencies import get_current_user, get_current_club
from app.schemas.behaviors import BehaviorRead, BehaviorCreate, BehaviorUpdate
from app.services.behavior_services import get_all_behavior, erase_behavior_from_club
from app.services import behavior_services
from app.behaviors.validator import BehaviorValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["behaviors"])

@router.get(
        "/behaviors", 
        response_model=list[BehaviorRead],
        status_code=status.HTTP_200_OK)

def get_behaviors(
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> list[BehaviorRead]:
    try: 
        return behavior_services.get_all_behavior(db, club.id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamientos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamientos"
        )

@router.delete(
    "/behaviors/{behavior_id}",
    status_code=status.HTTP_204_NO_CONTENT
    )
def erase_behavior(
    behavior_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        club_id = current_user.club.id
        erase_behavior_from_club(db, club_id, behavior_id)
        return
    except HTTPException as he:
        raise he
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error al eliminar comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al eliminar comportamiento."
        )
@router.get(
        "/behaviors/{behavior_id}",
        response_model=BehaviorRead,
        status_code=status.HTTP_200_OK)
def get_behavior(
    behavior_id: str,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        behavior = behavior_services.get_behavior_by_id(db, behavior_id, club.id)
        if not behavior:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comportamiento no encontrado"
            )
        return behavior
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamiento"
        )

@router.post(
        "/behaviors", 
        response_model=BehaviorRead,
        status_code=status.HTTP_201_CREATED)

def create_behavior(
    data: BehaviorCreate,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        new_behavior = behavior_services.create_behavior(db, data, club.id)
        return new_behavior
    except BehaviorValidationError as error:
        logger.warning(f"Error al crear comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    except ValueError as error:
        logger.warning(f"Error al crear comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    
    except SQLAlchemyError as e:
        logger.error(f"Error al crear comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear comportamiento"
        )

@router.put(
        "/behaviors/{behavior_id}", 
        response_model=BehaviorRead,
        status_code=status.HTTP_200_OK)
def update_behavior(
    behavior_id: str,
    data: BehaviorUpdate,
    club: Club = Depends(get_current_club),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        updated_behavior = behavior_services.update_behavior(db, behavior_id, data, club.id)
        return updated_behavior
    except BehaviorValidationError as error:
        logger.warning(f"Error al actualizar comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error)
        )
    except SQLAlchemyError as e:
        logger.error(f"Error al actualizar comportamiento: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al actualizar comportamiento"
        )
