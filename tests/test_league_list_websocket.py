"""Tests for the /ws/leagues channel."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

import app.ws.leagues as league_stream
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.ws.manager import league_list_manager
from tests.test_league_join import make_club, make_league, make_players, squad_body
from tests.test_league_join import url as join_url

ORIGIN = "http://localhost:5173"


def token_of(auth_headers: dict[str, str]) -> str:
    return auth_headers["Authorization"].removeprefix("Bearer ")


def connect(client: TestClient, origin: str = ORIGIN):
    return client.websocket_connect("/ws/leagues", headers={"origin": origin})


def subscribe(socket, token: str) -> None:
    socket.send_json({"type": "auth", "token": token})
    assert socket.receive_json() == {"type": "subscribed"}


@pytest.fixture
def creator(db: Session) -> Club:
    return make_club(db, "creador")


@pytest.fixture
def players(db: Session, club: Club) -> list[Player]:
    return make_players(db, club.id)


@pytest.fixture
def behavior(db: Session) -> Behavior:
    behavior = Behavior(
        name="Preprogramado", code="def behavior(player):\n    pass", is_preprogrammed=True
    )
    db.add(behavior)
    db.commit()
    return behavior


# --- Events ---


def test_join_broadcasts_league_updated_to_every_socket(
    client: TestClient, db: Session, auth_headers, creator: Club,
    players: list[Player], behavior: Behavior,
) -> None:
    league_id = make_league(db, creator).id
    token = token_of(auth_headers)

    with connect(client) as first, connect(client) as second:
        subscribe(first, token)
        subscribe(second, token)
        r = client.post(
            join_url(league_id), json=squad_body(players, behavior), headers=auth_headers
        )

        expected = {
            "event": "LEAGUE_UPDATED",
            "payload": {"leagueId": league_id, "enrolledClubs": 2},
        }
        assert r.status_code == 200
        assert first.receive_json() == expected
        assert second.receive_json() == expected


def test_failed_join_does_not_broadcast(
    client: TestClient, db: Session, auth_headers, creator: Club,
    players: list[Player], behavior: Behavior,
) -> None:
    full = make_league(db, creator, name="Llena", max_clubs=3)
    for name in ("rival1", "rival2"):
        db.add(Enrollment(room_id=full.id, club_id=make_club(db, name).id))
    db.commit()
    full_id = full.id
    open_id = make_league(db, creator, name="Abierta").id
    body = squad_body(players, behavior)

    with connect(client) as socket:
        subscribe(socket, token_of(auth_headers))
        failed = client.post(join_url(full_id), json=body, headers=auth_headers)
        joined = client.post(join_url(open_id), json=body, headers=auth_headers)

        assert (failed.status_code, joined.status_code) == (400, 200)
        # The first event is the successful join's, so the failed one emitted nothing.
        assert socket.receive_json()["payload"]["leagueId"] == open_id


def test_join_succeeds_when_the_notification_fails(
    client: TestClient, db: Session, auth_headers, creator: Club,
    players: list[Player], behavior: Behavior, monkeypatch,
) -> None:
    monkeypatch.setattr(league_list_manager, "broadcast", Mock(side_effect=RuntimeError("caido")))
    league_id = make_league(db, creator).id

    r = client.post(join_url(league_id), json=squad_body(players, behavior), headers=auth_headers)

    assert r.status_code == 200


# --- Protocol ---


@pytest.mark.parametrize("message", [{"type": "auth", "token": "invalido"}, {"type": "hola"}])
def test_invalid_auth_closes_with_4401(client: TestClient, message: dict) -> None:
    with connect(client) as socket:
        socket.send_json(message)

        assert socket.receive_json()["status"] == 401
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 4401


def test_disallowed_origin_closes_with_1008(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        with connect(client, origin="https://untrusted.example"):
            pass
    assert closed.value.code == 1008


def test_heartbeat_pings_and_logout_closes_the_socket(
    client: TestClient, auth_headers, monkeypatch,
) -> None:
    monkeypatch.setattr(league_stream, "HEARTBEAT_SECONDS", 0.1)

    with connect(client) as socket:
        subscribe(socket, token_of(auth_headers))
        assert socket.receive_json() == {"type": "ping"}
        socket.send_json({"type": "pong"})
        assert client.post("/api/auth/logout", headers=auth_headers).status_code == 204

        message = socket.receive_json()
        while message == {"type": "ping"}:
            socket.send_json({"type": "pong"})
            message = socket.receive_json()
        assert message["status"] == 401
