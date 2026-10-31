import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.schemas.behaviors import BehaviorRead, BehaviorCreate
from app.services import behavior_services
from app.behaviors.validator import BehaviorValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["behaviors"])

@router.get(
        "/behaviors", 
        response_model=list[BehaviorRead],
        status_code=status.HTTP_200_OK)

def get_behaviors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> list[BehaviorRead]:
    try: 
        club_id = current_user.club.id
        return behavior_services.get_all_behavior(db, club_id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamientos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamientos"
        )
@router.post(
        "/behaviors", 
        response_model=BehaviorRead,
        status_code=status.HTTP_201_CREATED)

def create_behavior(
    data: BehaviorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> BehaviorRead:
    try:
        club_id = current_user.club.id
        new_behavior = behavior_services.create_behavior(db, data, club_id)
        return new_behavior
    except BehaviorValidationError as error:
        logger.warning(f"Error al crear comportamiento: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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