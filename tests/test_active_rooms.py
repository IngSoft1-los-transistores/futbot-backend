import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.main import app
from app.db.session import get_db
from app.models.user import User
from app.models.club import Club
from app.models.room import (
    Room, 
    ROOM_TYPE_FRIENDLY, 
    ROOM_TYPE_PUBLIC, 
    ROOM_STATUS_WAITING_GUEST, 
    ROOM_STATUS_FINISHED, 
    ROOM_STATUS_CANCELLED,
    MIN_LEAGUE_CLUBS
)
from app.models.enrollment import Enrollment
from app.models.auth_session import AuthSession
from app.core.security import create_access_token, hash_password

client = TestClient(app)

@pytest.fixture
def db_session():
    """Proporciona una sesión de base de datos para preparar los datos de prueba."""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def setup_test_user_and_token(db_session: Session):
    """Crea un usuario de prueba único, su club, una sesión válida y genera un token JWT."""
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        username=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        password_hash=hash_password("password123")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    club = Club(
        user_id=user.id,
        name=f"Club_{unique_id}",
        ranking_points=100
    )
    db_session.add(club)
    db_session.commit()
    db_session.refresh(club)

    # Usamos un refresh_hash único para evitar conflictos de constraint UNIQUE
    auth_session = AuthSession(
        user_id=user.id,
        refresh_hash=f"refresh_hash_{unique_id}",
        revoked=False,
        expires_at=datetime.now(timezone.utc).timestamp() + 3600
    )
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)

    token = create_access_token(user_id=user.id, session_id=auth_session.id)
    return {"user": user, "club": club, "token": token}


def charm_room(db: Session, club_id: str, room_type: str, status: str, code: str, name: str = None):
    """Helper para crear salas e inscribir al club cumpliendo los constraints del modelo."""
    is_friendly = (room_type == ROOM_TYPE_FRIENDLY)
    room = Room(
        type=room_type,
        status=status,
        code=code,
        name=name if not is_friendly else None,
        creator_club_id=club_id,
        min_clubs=2 if is_friendly else MIN_LEAGUE_CLUBS,
        max_clubs=2 if is_friendly else 10,
        match_duration_minutes=5
    )
    db.add(room)
    db.commit()
    db.refresh(room)

    enrollment = Enrollment(
        room_id=room.id,
        club_id=club_id
    )
    db.add(enrollment)
    db.commit()
    return room


def test_ws_active_rooms_success_and_payload(db_session: Session, setup_test_user_and_token):
    """
    Criterio: Conexión válida acepta y envía el listado inicial con id y code,
    separando amistosos y ligas, y excluyendo finalizadas/canceladas.
    """
    club_id = setup_test_user_and_token["club"].id
    token = setup_test_user_and_token["token"]

    room_friendly = charm_room(db_session, club_id, ROOM_TYPE_FRIENDLY, ROOM_STATUS_WAITING_GUEST, f"F-{str(uuid.uuid4())[:4]}")
    room_league = charm_room(db_session, club_id, ROOM_TYPE_PUBLIC, ROOM_STATUS_WAITING_GUEST, f"L-{str(uuid.uuid4())[:4]}", name=f"Liga Test {str(uuid.uuid4())[:4]}")
    charm_room(db_session, club_id, ROOM_TYPE_PUBLIC, ROOM_STATUS_FINISHED, f"FIN-{str(uuid.uuid4())[:4]}", name=f"Liga Terminada {str(uuid.uuid4())[:4]}")
    charm_room(db_session, club_id, ROOM_TYPE_FRIENDLY, ROOM_STATUS_CANCELLED, f"CAN-{str(uuid.uuid4())[:4]}")

    with client.websocket_connect(f"/ws/rooms/active?token={token}") as websocket:
        data = websocket.receive_json()

        assert isinstance(data, list)
        assert len(data) == 2

        room_ids = {r["id"] for r in data}
        assert room_friendly.id in room_ids
        assert room_league.id in room_ids
        
        for r in data:
            assert "id" in r
            assert "code" in r
            assert "type" in r
            assert "status" in r


def test_ws_active_rooms_empty_list(db_session: Session, setup_test_user_and_token):
    """
    Criterio: Si no hay salas en curso, se devuelve un listado vacío [].
    """
    token = setup_test_user_and_token["token"]

    with client.websocket_connect(f"/ws/rooms/active?token={token}") as websocket:
        data = websocket.receive_json()
        assert isinstance(data, list)
        assert len(data) == 0


def test_ws_active_rooms_unauthorized(db_session: Session):
    """
    Criterio: Token inválido o ausente rechaza la conexión.
    """
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/rooms/active?token=token_invalido") as websocket:
            pass
