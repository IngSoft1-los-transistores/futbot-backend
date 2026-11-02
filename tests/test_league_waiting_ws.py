"""Pruebas para el WebSocket del lobby de espera de una liga."""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import (
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PUBLIC,
    Room,
)


def crear_club_con_usuario(db: Session, nombre: str) -> Club:
    """Función auxiliar para crear un usuario y su club asociado (respetando Foreign Keys)."""
    usuario = User(
        username=nombre, 
        email=f"{nombre}@futbot.test", 
        password_hash="hash-de-prueba"
    )
    db.add(usuario)
    db.flush()
    nuevo_club = Club(user_id=usuario.id, name=f"Club {nombre}")
    db.add(nuevo_club)
    db.commit()
    return nuevo_club


@pytest.fixture
def test_league(db: Session, club: Club) -> Room:
    """Crea una liga de prueba en estado waiting_guest con el club fixture como creador e inscripto."""
    league = Room(
        id=str(uuid.uuid4()),
        type=ROOM_TYPE_PUBLIC,
        name="Liga Estelar",
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=5,
        match_duration_minutes=5,
        status=ROOM_STATUS_WAITING_GUEST,
    )
    db.add(league)
    db.commit()

    # Inscribir al club creador en la liga
    enrollment = Enrollment(
        room_id=league.id,
        club_id=club.id,
    )
    db.add(enrollment)
    db.commit()
    return league


def test_ws_connection_success(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica que un usuario inscripto pueda conectarse y reciba la información inicial de la sala."""
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}") as websocket:
        data = websocket.receive_json()
        
        assert data["type"] == "room_info"
        assert data["league_id"] == test_league.id
        assert data["league_name"] == "Liga Estelar"
        assert data["creator_club_id"] == club.id
        assert data["current_participants"] == 1
        assert data["min_clubs"] == 3
        assert data["max_clubs"] == 5
        assert data["status"] == ROOM_STATUS_WAITING_GUEST
        assert data["can_start"] is False


def test_ws_connection_reject_not_enrolled(client: TestClient, db: Session, test_league: Room):
    """Verifica que se rechace la conexión si el club no está inscripto en la liga."""
    fake_club_id = str(uuid.uuid4())

    # Al conectar con un club no inscripto, el endpoint cierra el socket con un código de política/error
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={fake_club_id}") as websocket:
        with pytest.raises(Exception):
            websocket.receive_json()


def test_ws_creator_starts_league(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica que el creador pueda iniciar la liga cuando se cumple el mínimo de clubes."""
    # Inscribir clubes adicionales en la BD para cumplir el `min_clubs = 3`
    second_club = crear_club_con_usuario(db, "segundo")
    third_club = crear_club_con_usuario(db, "tercero")

    db.add(Enrollment(room_id=test_league.id, club_id=second_club.id))
    db.add(Enrollment(room_id=test_league.id, club_id=third_club.id))
    db.commit()

    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}") as websocket:
        # 1. Consumir mensaje inicial de room_info
        websocket.receive_json()

        # 2. Enviar acción de iniciar liga
        websocket.send_json({"action": "start_league"})

        # 3. Leer los mensajes subsiguientes hasta encontrar el evento de inicio
        response = None
        for _ in range(2):
            msg = websocket.receive_json()
            if msg.get("type") == "league_started":
                response = msg
                break

        assert response is not None
        assert response["type"] == "league_started"
        assert response["redirect_url"] == f"/league/{test_league.id}/active"


def test_ws_creator_cancels_league(client: TestClient, db: Session, test_league: Room, club: Club):
    """Verifica que el creador pueda cancelar la liga y se notifique la redirección al home."""
    with client.websocket_connect(f"/ws/league/{test_league.id}/waiting?club_id={club.id}") as websocket:
        # Consumir mensaje inicial de room_info
        websocket.receive_json()

        # Enviar acción de cancelar liga
        websocket.send_json({"action": "cancel_league"})

        # Buscar el mensaje de cancelación en el stream de eventos
        response = None
        for _ in range(5):
            msg = websocket.receive_json()
            if msg.get("type") == "league_cancelled":
                response = msg
                break

        assert response is not None
        assert response["redirect_url"] == "/home"