import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.room import Room, ROOM_TYPE_FRIENDLY, ROOM_STATUS_WAITING_GUEST
from app.models.squad_entry import SquadEntry, ROLE_STARTER, ROLE_SUBSTITUTE


def test_create_friendly_room_unauthorized_without_token(client: TestClient):
    """
    Debe rechazar la peticion con 401 Unauthorized si no se envia el token.
    """
    response = client.post("/api/friendly/rooms", json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"

def test_create_friendly_room_unauthorized_invalid_token(client: TestClient):
    """
    Debe rechazar la peticion con 401 Unauthorized si el token es invalido.
    """
    headers = {"Authorization": "Bearer token.jwt.invalido"}
    response = client.post("/api/friendly/rooms", headers=headers, json={})
    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"

def test_create_friendly_room_integration_success(
        client: TestClient,
        db: Session,
        club,
        auth_headers: dict[str, str],
        crear_player,
        comportamiento_prueba,
):
    """
    Prueba el flujo punta a punta (HTTP -> Auth -> Service -> DB).
    """
    # Crear 6 jugadores para el club usando fixture
    jugadores = [crear_player(club.id, name=f"Jugador {i}") for i in range(1,7)]

    # Formatear payload con titulares y suplentes
    payload = {
        "starters": [
            {"player_id": str(p.id), "behavior_id": str(comportamiento_prueba.id)}
            for p in jugadores[:3]
        ],
        "substitutes": [
            {"player_id": str(p.id), "behavior_id": str(comportamiento_prueba.id)}
            for p in jugadores[3:]
        ],
    }

    # Peticion HTTP autenticada
    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)

    # asserciones de la respuesta http
    assert response.status_code == 201
    data = response.json()
    assert "room_id" in data
    assert "room_code" in data
    assert data["status"] == "waitingGuest"
    assert data["home_club"] == str(club.id)

    # verificacion de persistencia
    created_room = db.get(Room, data["room_id"])
    assert created_room is not None
    assert created_room.type == ROOM_TYPE_FRIENDLY
    assert created_room.status == ROOM_STATUS_WAITING_GUEST
    assert created_room.creator_club_id == club.id

    # verificacion de alineaciones
    squad_entries = db.query(SquadEntry).filter_by(room_id=data["room_id"]).all()
    assert len(squad_entries) == 6
    starters = [s for s in squad_entries if s.role == ROLE_STARTER]
    substitutes = [s for s in squad_entries if s.role == ROLE_SUBSTITUTE]
    assert len(starters) == 3
    assert len(substitutes) == 3

def test_create_friendly_room_validation_pydantic_int_input(
    client: TestClient, auth_headers: dict[str, str]
):
    """
    Pydantic debe rechazar entradas numéricas (422 Unprocessable Entity).
    """
    payload = {
        "starters": [
            {"player_id": 1, "behavior_id": "b-1"},  # int en vez de str
            {"player_id": "p-2", "behavior_id": "b-1"},
            {"player_id": "p-3", "behavior_id": "b-1"},
        ],
        "substitutes": [
            {"player_id": "p-4", "behavior_id": "b-1"},
            {"player_id": "p-5", "behavior_id": "b-1"},
            {"player_id": "p-6", "behavior_id": "b-1"},
        ],
    }

    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)
    assert response.status_code == 422

def test_create_friendly_room_duplicate_players_400(
    client: TestClient,
    club,
    auth_headers: dict[str, str],
    crear_player,
    comportamiento_prueba,
):
    """
    El servicio debe retornar 400 Bad Request si hay jugadores repetidos.
    """
    p1 = crear_player(club.id, name="Jugador 1")
    p2 = crear_player(club.id, name="Jugador 2")

    payload = {
        "starters": [
            {"player_id": str(p1.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p1.id), "behavior_id": str(comportamiento_prueba.id)},  # Repetido
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
        ],
        "substitutes": [
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
            {"player_id": str(p2.id), "behavior_id": str(comportamiento_prueba.id)},
        ],
    }

    response = client.post("/api/friendly/rooms", headers=auth_headers, json=payload)
    assert response.status_code == 400
    assert "mismo jugador" in response.json()["detail"].lower()