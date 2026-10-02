from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.player import PlayerCreate, PlayerResponse
from app.services.exceptions_player import AppException
from app.services.player_service import create_player

router = APIRouter(prefix="/api", tags=["create player"])


# Ticket: BE [BE] Endpoint Crear Jugador de Club
@router.post("/players", status_code=201, response_model=PlayerResponse)
def create_player_endpoint(
    player_data: PlayerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        player = create_player(db, current_user.club.id, player_data)
        return player

    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


"""
Pasos para probar el endpoint de crear jugador:

1. Preparar los datos de prueba:
   python -m app.core.test_player

2. Levantar el servidor:
   uvicorn app.main:app --reload

3. Abrir Swagger:
   http://localhost:8000/docs

4. Ejecutar los tests:
   pytest -v tests/test_players.py

Si hay problemas con la base de datos, eliminar futbot.db
y volver a ejecutar el paso 1.

Nota: el test test_requires_authentication puede fallar hasta
integrar el sistema de autenticación real.
"""
