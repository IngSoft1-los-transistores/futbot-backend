from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.get_data_player import get_current_club_id
from app.db.session import get_db
from app.schemas.player import PlayerCreate, PlayerResponse
from app.services.exceptions_player import AppException
from app.services.player_service import create_player

router = APIRouter(prefix="/api", tags=["create player"])


# Ticket: BE [BE] Endpoint Crear Jugador de Club
@router.post("/players", status_code=201, response_model=PlayerResponse)
def create_player_endpoint(
    player_data: PlayerCreate,
    db: Session = Depends(get_db),
    club_id: str = Depends(get_current_club_id),
):
    try:
        player = create_player(db, club_id, player_data) 
        return player

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


""" 
Pasos para pobar el endpoint de crear jugador:
    1. Levantar el servidor : uvicorn app.main:app --reload
    2. Ejecutar el core/test_data_player.py: python -c "from app.core.test_data_player import crear_datos_prueba; crear_datos_prueba()"
    3. Copiar y guardar el club_id generado en el archivo core/get_data_player.py en 
    4. Usar swagger (http://localhost:8000/docs) para probar el endpoint POST /api/players. 
    Ingresar los datos del jugador en el cuerpo de la solicitud y enviar la solicitud.
    5. Para probar los tests, ejecutar pytest -v tests/test_players.py. El test de "test_requires_authentication" dará FALSED hasta tener integrado el sistema de autenticación.

    Ante cualquier errror, ejecutar rm -v futbot.db para eliminar la base de datos y volver a ejecutar el script core/test_data_player.py para crear un nuevo usuario y club de prueba.
"""
