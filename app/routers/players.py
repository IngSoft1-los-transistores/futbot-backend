from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.test_player import get_current_club_id
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
    1. Levantar el servidor (uvicorn app.main:app --reload, para crear la base de datos y las tablas) y luego detenerlo (Ctrl + C).
    2. Ejecutar el script scripts/test_data_player.py (python -c "from scripts.test_data_player import crear_datos_prueba; crear_datos_prueba()") para crear un usuario y un club 
       de prueba. Esto generará un access token y un club_id que se imprimirán en la consola.
    3. Copiar el club_id generado e ingresarlo en el archivo scripts/get_data_player.py en 
       la función get_current_club_id() para que devuelva el club_id de prueba.
    4. Levantar el servidor (uvicorn app.main:app --reload).
    5. Usar swagger (http://localhost:8000/docs) para probar el endpoint POST /api/players. 
       Ingresar los datos del jugador en el cuerpo de la solicitud y enviar la solicitud.
    6. Para probar los tests, ejecutar pytest -v tests/test_players.py. Esto ejecutará los tests definidos en el archivo tests/test_players.py y mostrará los resultados en la consola.

    Ante cualquier errror, ejecutar rm -v futbot.db para eliminar la base de datos y volver a ejecutar el script scripts/test_data_player.py para crear un nuevo usuario y club de prueba.
"""
