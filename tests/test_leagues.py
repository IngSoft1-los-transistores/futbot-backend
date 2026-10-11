from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import MAX_LEAGUE_CLUBS, MIN_LEAGUE_CLUBS, ROOM_STATUS_WAITING_GUEST, Room
from app.models.squad_entry import (
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
    SquadEntry,
)
from app.models.user import User


def test_crear_liga(
    client: TestClient,
    db: Session,
    club: Club,
    comportamiento_prueba: Behavior,
    jugadores_del_club: list[Player],
    auth_headers,
):
    response = client.post(
        "/api/leagues",
        headers=auth_headers,
        json={
            "name": "Liga de Prueba",
            "min_clubs": 3,
            "max_clubs": 4,
            "match_duration": 90,
            "starters": [
                {
                    "player_id": str(jugadores_del_club[i].id),
                    "behavior_id": str(comportamiento_prueba.id),
                }
                for i in range(3)
            ],
            "substitutes": [
                {
                    "player_id": str(jugadores_del_club[i].id),
                    "behavior_id": str(comportamiento_prueba.id),
                }
                for i in range(3, 6)
            ],
        },
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Liga de Prueba"
    assert response.json()["creator_id"] == club.id
    # Room
    room = db.scalars(select(Room)).one()
    assert club.id == room.creator_club_id
    assert room.status == ROOM_STATUS_WAITING_GUEST
    assert room.password_hash is None

    # Enrollment
    enrollments = db.scalars(select(Enrollment)).all()
    assert len(enrollments) == 1
    assert enrollments[0].club_id == club.id

    # SquadEntry
    squad_entries = db.scalars(select(SquadEntry)).all()
    assert len(squad_entries) == 6
    assert sum(entry.role == ROLE_STARTER for entry in squad_entries) == 3
    assert sum(entry.role == ROLE_SUBSTITUTE for entry in squad_entries) == 3


def payload_liga(
    jugadores_del_club,
    comportamiento_prueba,
    **cambios,
) -> dict:
    payload = {
        "name": "Liga de Prueba",
        "min_clubs": 3,
        "max_clubs": 4,
        "match_duration": 90,
        "starters": [
            {
                "player_id": str(jugadores_del_club[i].id),
                "behavior_id": str(comportamiento_prueba.id),
            }
            for i in range(3)
        ],
        "substitutes": [
            {
                "player_id": str(jugadores_del_club[i].id),
                "behavior_id": str(comportamiento_prueba.id),
            }
            for i in range(3, 6)
        ],
    }

    payload.update(cambios)
    return payload


def test_crear_liga_min_clubs_invalido(
    client: TestClient,
    db: Session,
    jugadores_del_club: list[Player],
    comportamiento_prueba: Behavior,
    auth_headers,
):
    payload = payload_liga(jugadores_del_club, comportamiento_prueba, min_clubs=2)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == f"La liga debe tener al menos {MIN_LEAGUE_CLUBS} clubes."
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_max_clubs_invalido(
    client: TestClient,
    db: Session,
    jugadores_del_club: list[Player],
    comportamiento_prueba: Behavior,
    auth_headers,
):
    payload = payload_liga(jugadores_del_club, comportamiento_prueba, max_clubs=31)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == f"La liga debe tener maximo {MAX_LEAGUE_CLUBS} clubes."
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_max_menor_que_min(
    client: TestClient,
    db: Session,
    jugadores_del_club: list[Player],
    comportamiento_prueba: Behavior,
    auth_headers,
):
    payload = payload_liga(jugadores_del_club, comportamiento_prueba, min_clubs=5)
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "La cantidad de clubes maximos respecto a los minimos es inconsistente."
    )
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_jugador_repetido(
    client: TestClient,
    db: Session,
    jugadores_del_club: list[Player],
    comportamiento_prueba: Behavior,
    auth_headers,
):
    repetido = jugadores_del_club[0]
    comportamiento = comportamiento_prueba.id

    payload = payload_liga(
        jugadores_del_club,
        comportamiento_prueba,
        starters=[
            {"player_id": str(repetido.id), "behavior_id": str(comportamiento)},
            {"player_id": str(repetido.id), "behavior_id": str(comportamiento)},
            {"player_id": str(jugadores_del_club[1].id), "behavior_id": str(comportamiento)},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == f"El jugador con id:{repetido.id} no puede repetirse"
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_jugador_de_otro_club(
    client, db, jugadores_del_club, comportamiento_prueba, crear_player, club, auth_headers
):
    otro_user = User(username="otro", email="otro@otro.com", password_hash="otro-hash")
    otro_user.club = Club(name="Club Ajeno")
    db.add(otro_user)
    db.commit()

    ajeno = crear_player(otro_user.club.id, name="Ajeno")
    comportamiento = comportamiento_prueba.id
    payload = payload_liga(
        jugadores_del_club,
        comportamiento_prueba,
        starters=[
            {"player_id": str(ajeno.id), "behavior_id": str(comportamiento)},
            {"player_id": str(jugadores_del_club[0].id), "behavior_id": str(comportamiento)},
            {"player_id": str(jugadores_del_club[1].id), "behavior_id": str(comportamiento)},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"El jugador {ajeno.name} con id:{ajeno.id} no pertenece al club "
        f"{club.name} con id:{club.id}"
    )
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_comportamiento_inexistente(
    client, db, jugadores_del_club, comportamiento_prueba, auth_headers
):

    inexistente = str(uuid4())

    payload = payload_liga(
        jugadores_del_club,
        comportamiento_prueba,
        starters=[
            {
                "player_id": str(jugadores_del_club[0].id),
                "behavior_id": str(comportamiento_prueba.id),
            },
            {
                "player_id": str(jugadores_del_club[1].id),
                "behavior_id": str(comportamiento_prueba.id),
            },
            {"player_id": str(jugadores_del_club[2].id), "behavior_id": inexistente},
        ],
    )
    response = client.post("/api/leagues", headers=auth_headers, json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == f"El comportamiento con id:{inexistente} es invalido"
    assert db.scalars(select(Room)).all() == []


def test_crear_liga_nombre_repetido(
    client, db, jugadores_del_club, comportamiento_prueba, auth_headers
):

    payload = payload_liga(jugadores_del_club, comportamiento_prueba)

    response_1 = client.post("/api/leagues", headers=auth_headers, json=payload)
    assert response_1.status_code == 201

    response_2 = client.post("/api/leagues", headers=auth_headers, json=payload)
    assert response_2.status_code == 400
    assert response_2.json()["detail"] == "El nombre Liga de Prueba ya existe, elija otro"
    assert len(db.scalars(select(Room)).all()) == 1


def test_crear_liga_sin_token(client, jugadores_del_club, comportamiento_prueba):

    payload = payload_liga(jugadores_del_club, comportamiento_prueba)

    response = client.post("/api/leagues", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Sesión inválida o vencida"
