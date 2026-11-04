import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.schemas.behaviors import BehaviorRead
from app.services.behavior_services import get_all_behavior
from app.schemas.behavior_simulation import SimulationTicketCreate, SimulationTicketRead
from app.services.behavior_simulation import get_simulation_resources


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["behaviors"])

# Diccionario para almacenar tickets de simulación de comportamiento
_ws_tickets: dict[str, dict] = {}

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
        return get_all_behavior(db, club_id)
    except SQLAlchemyError as e:
        logger.error(f"Error al obtener comportamientos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al obtener comportamientos"
        )

@router.post(
    "/behaviors/simulate",
    status_code=status.HTTP_201_CREATED,
    response_model=SimulationTicketRead,
)
def create_simulation_ticket(
    request_data: SimulationTicketCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crea un ticket para la simulación de comportamiento y lo devuelve al front.
    El front debe usar este ticket para conectarse al websocket de simulación.
    """
    
    try:
        # Verifico que el jugador y el comportamiento existan
        player, behavior = get_simulation_resources(
            db=db, 
            player_id=request_data.player_id,
            behavior_id=request_data.behavior_id, 
            club_id=current_user.club.id
        )
        ticket = str(uuid.uuid4())
        _ws_tickets[ticket] = {
            "user_id": current_user.id,
            "player_id": request_data.player_id,
            "behavior_id": request_data.behavior_id,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)  # El ticket expira en 5 minutos
        }

        return {"ticket": ticket}
    except ValueError as error:
        logger.warning(f"Error al crear ticket de simulación: {error}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error)
        ) from error
    except Exception as e:
        logger.error(f"Error al crear ticket de simulación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al crear ticket de simulación"
        )
