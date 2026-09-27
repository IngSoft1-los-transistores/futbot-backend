from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_club
from app.db.base import ahora_utc
from app.main import app
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import ESTADO_FINISHED, ESTADO_IN_PROGRESS, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import (
    STATE_CANCELLED,
    STATE_IN_PROGRESS,
    STATE_READY_TO_START,
    STATE_WAITING_GUEST,
    TYPE_FRIENDLY,
    TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROL_STARTER, ROL_SUBSTITUTE, SquadEntry
from app.models.user import User
from app.services.friendly_rooms import (
    is_behavior_in_active_match,
    start_friendly_match,
)
from tests.conftest import crear_player

"""Tests for POST /api/friendly/rooms/{room_id}/start."""

MATCH_DURATION_MINUTES = 5


# --- Data helpers ---


def create_club(db: Session, name: str) -> Club:
    user = User(username=name, email=f"{name}@futbot.test", password_hash="hash")
    db.add(user)
    db.flush()
    club = Club(user_id=user.id, name=name)
    db.add(club)
    db.commit()
    return club


def create_behavior(db: Session, club_id: str | None, name: str) -> Behavior:
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def comportamiento(jugador):\n    pass\n",
        is_preprogrammed=club_id is None,
    )
    db.add(behavior)
    db.commit()
    return behavior


def add_squad(db: Session, room: Room, club: Club, behavior: Behavior) -> list[Player]:
    db.add(Enrollment(room_id=room.id, club_id=club.id))
    players = [crear_player(db, club.id) for _ in range(6)]
    for index, player in enumerate(players):
        db.add(
            SquadEntry(
                room_id=room.id,
                player_id=player.id,
                behavior_id=behavior.id,
                role=ROL_STARTER if index < 3 else ROL_SUBSTITUTE,
            )
        )
    db.commit()
    return players


def create_friendly_room(db: Session, creator: Club, room_status: str) -> Room:
    room = Room(
        type=TYPE_FRIENDLY,
        creator_club_id=creator.id,
        min_clubs=2,
        max_clubs=2,
        match_duration_minutes=MATCH_DURATION_MINUTES,
        status=room_status,
    )
    db.add(room)
    db.commit()
    return room


def start_url(room_id: str) -> str:
    return f"/api/friendly/rooms/{room_id}/start"


# --- Fixtures ---


@pytest.fixture
def away_club(db: Session) -> Club:
    return create_club(db, "away")


@pytest.fixture
def default_behavior(db: Session) -> Behavior:
    return create_behavior(db, None, "correr")


@pytest.fixture
def ready_room(
    db: Session, club: Club, away_club: Club, default_behavior: Behavior
) -> Room:
    room = create_friendly_room(db, club, STATE_READY_TO_START)
    add_squad(db, room, club, default_behavior)
    add_squad(db, room, away_club, default_behavior)
    return room


@pytest.fixture
def login_as(client: TestClient) -> Callable[[Club], None]:
    """Authenticates as the given club (overrides the auth placeholder)."""

    def _login(club: Club) -> None:
        app.dependency_overrides[get_current_club] = lambda: club

    return _login


def assert_error(response, status_code: int, error_code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert body["error_code"] == error_code
    assert isinstance(body["detail"], str)


def count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# --- Success ---


def test_start_returns_ok_and_the_match_id(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    login_as(club)

    response = client.post(start_url(ready_room.id))

    assert response.status_code == 200
    match = db.scalars(select(Match)).one()
    assert response.json() == {
        "room_id": ready_room.id,
        "match_id": match.id,
        "status": STATE_IN_PROGRESS,
    }


def test_start_moves_room_and_match_to_in_progress(
    client: TestClient,
    login_as,
    club: Club,
    away_club: Club,
    ready_room: Room,
    db: Session,
) -> None:
    login_as(club)

    client.post(start_url(ready_room.id))

    db.refresh(ready_room)
    assert ready_room.status == STATE_IN_PROGRESS
    assert ready_room.started_at is not None

    match = db.scalars(select(Match)).one()
    assert match.status == ESTADO_IN_PROGRESS
    assert match.home_club_id == club.id
    assert match.away_club_id == away_club.id
    assert match.duration_seconds == MATCH_DURATION_MINUTES * 60
    assert match.started_at is not None


def test_start_creates_the_lineup_and_locks_the_players(
    client: TestClient,
    login_as,
    club: Club,
    ready_room: Room,
    default_behavior: Behavior,
    db: Session,
) -> None:
    login_as(club)

    client.post(start_url(ready_room.id))

    match_players = db.scalars(select(MatchPlayer)).all()
    assert len(match_players) == 12
    assert sum(mp.on_field for mp in match_players) == 6
    assert all(mp.behavior_id == default_behavior.id for mp in match_players)

    players = db.scalars(select(Player)).all()
    for player in players:
        db.refresh(player)
    assert all(player.is_playing for player in players)


def test_the_away_club_can_also_start(
    client: TestClient, login_as, away_club: Club, ready_room: Room
) -> None:
    login_as(away_club)

    assert client.post(start_url(ready_room.id)).status_code == 200


# --- Auth and access ---


def test_start_without_authentication_is_rejected(
    client: TestClient, ready_room: Room, db: Session
) -> None:
    response = client.post(start_url(ready_room.id))

    assert_error(response, 401, "INVALID_TOKEN")
    assert response.headers["www-authenticate"] == "Bearer"
    assert count(db, Match) == 0


def make_token(
    user_id: str,
    secret: str | None = None,
    expires_in: timedelta | None = timedelta(minutes=5),
) -> str:
    """Builds a token like the login endpoint does (`sub` = user id)."""
    settings = get_settings()
    claims = {"sub": user_id}
    if expires_in is not None:
        claims["exp"] = datetime.now(timezone.utc) + expires_in
    return jwt.encode(
        claims, secret or settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def test_start_with_a_valid_token(
    client: TestClient, club: Club, ready_room: Room
) -> None:
    response = client.post(
        start_url(ready_room.id),
        headers={"Authorization": f"Bearer {make_token(club.user_id)}"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-jwt",
        "Basic dXNlcjpwYXNz",
        "Bearer {wrong_secret}",
        "Bearer {expired}",
        "Bearer {without_exp}",
        "Bearer {unknown_user}",
    ],
)
def test_start_with_an_invalid_token_is_rejected(
    client: TestClient, club: Club, ready_room: Room, db: Session, authorization: str
) -> None:
    tokens = {
        "wrong_secret": make_token(club.user_id, secret="another-secret"),
        "expired": make_token(club.user_id, expires_in=timedelta(minutes=-1)),
        "without_exp": make_token(club.user_id, expires_in=None),
        "unknown_user": make_token("user-that-does-not-exist"),
    }

    response = client.post(
        start_url(ready_room.id),
        headers={"Authorization": authorization.format(**tokens)},
    )

    assert_error(response, 401, "INVALID_TOKEN")
    assert count(db, Match) == 0


def test_unknown_room_is_not_found(
    client: TestClient, login_as, club: Club
) -> None:
    login_as(club)

    assert_error(client.post(start_url("room-that-does-not-exist")), 404, "ROOM_NOT_FOUND")


def test_a_league_room_is_not_found(
    client: TestClient, login_as, club: Club, db: Session
) -> None:
    league = Room(
        type=TYPE_PUBLIC,
        name="Liga",
        creator_club_id=club.id,
        min_clubs=3,
        max_clubs=4,
        match_duration_minutes=MATCH_DURATION_MINUTES,
        status=STATE_READY_TO_START,
    )
    db.add(league)
    db.flush()  # generates league.id
    db.add(Enrollment(room_id=league.id, club_id=club.id))
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(league.id)), 404, "ROOM_NOT_FOUND")


def test_a_club_outside_the_room_is_forbidden(
    client: TestClient, login_as, ready_room: Room, db: Session
) -> None:
    login_as(create_club(db, "outsider"))

    assert_error(client.post(start_url(ready_room.id)), 403, "NOT_ROOM_MEMBER")
    assert count(db, Match) == 0


# --- Room state ---


def test_a_match_cannot_be_started_twice(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    login_as(club)
    client.post(start_url(ready_room.id))

    response = client.post(start_url(ready_room.id))

    assert_error(response, 400, "MATCH_ALREADY_STARTED")
    assert count(db, Match) == 1


def test_a_room_without_guest_is_not_full(
    client: TestClient,
    login_as,
    club: Club,
    default_behavior: Behavior,
    db: Session,
) -> None:
    room = create_friendly_room(db, club, STATE_WAITING_GUEST)
    add_squad(db, room, club, default_behavior)
    login_as(club)

    assert_error(client.post(start_url(room.id)), 400, "ROOM_NOT_FULL")


def test_a_cancelled_room_is_not_ready(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    ready_room.status = STATE_CANCELLED
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(ready_room.id)), 400, "ROOM_NOT_READY")


def test_a_concurrent_start_is_detected(
    engine: Engine, club: Club, ready_room: Room, db: Session
) -> None:
    """The other club starts the room after this request read it."""
    db.get(Room, ready_room.id)
    with engine.begin() as other_request:
        other_request.execute(
            update(Room)
            .where(Room.id == ready_room.id)
            .values(status=STATE_IN_PROGRESS, started_at=ahora_utc())
        )

    with pytest.raises(HTTPException) as error:
        start_friendly_match(db, ready_room.id, club)

    assert error.value.status_code == 400
    assert error.value.detail["error_code"] == "MATCH_ALREADY_STARTED"
    assert count(db, Match) == 0


# --- Squads ---


def assert_invalid_squad_without_side_effects(
    client: TestClient, room: Room, db: Session
) -> None:
    assert_error(client.post(start_url(room.id)), 400, "INVALID_SQUAD")
    db.refresh(room)
    assert room.status == STATE_READY_TO_START
    assert count(db, Match) == 0
    assert count(db, MatchPlayer) == 0


def test_a_squad_with_only_two_starters_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    starter = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id, SquadEntry.role == ROL_STARTER)
    ).first()
    db.delete(starter)
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_deleted_player_is_invalid(
    client: TestClient, login_as, club: Club, away_club: Club, ready_room: Room, db: Session
) -> None:
    player = db.scalars(select(Player).where(Player.club_id == away_club.id)).first()
    player.deleted_at = ahora_utc()
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_player_from_a_third_club_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id)
    ).first()
    entry.player_id = crear_player(db, create_club(db, "third").id).id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_player_already_playing_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    player = db.scalars(select(Player).where(Player.club_id == club.id)).first()
    player.is_playing = True
    db.commit()
    login_as(club)

    assert_error(client.post(start_url(ready_room.id)), 400, "INVALID_SQUAD")


def test_a_squad_with_another_clubs_behavior_is_invalid(
    client: TestClient, login_as, club: Club, away_club: Club, ready_room: Room, db: Session
) -> None:
    foreign_behavior = create_behavior(db, club.id, "home_only")
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == away_club.id)
    ).first()
    entry.behavior_id = foreign_behavior.id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


def test_a_squad_with_a_deleted_behavior_is_invalid(
    client: TestClient, login_as, club: Club, ready_room: Room, db: Session
) -> None:
    own_behavior = create_behavior(db, club.id, "deleted")
    own_behavior.deleted_at = ahora_utc()
    entry = db.scalars(
        select(SquadEntry)
        .join(Player, SquadEntry.player_id == Player.id)
        .where(Player.club_id == club.id)
    ).first()
    entry.behavior_id = own_behavior.id
    db.commit()
    login_as(club)

    assert_invalid_squad_without_side_effects(client, ready_room, db)


# --- Behavior lock ---


def test_behaviors_are_locked_only_while_the_match_is_active(
    client: TestClient,
    login_as,
    club: Club,
    ready_room: Room,
    default_behavior: Behavior,
    db: Session,
) -> None:
    unused_behavior = create_behavior(db, club.id, "unused")
    assert not is_behavior_in_active_match(db, default_behavior.id)

    login_as(club)
    client.post(start_url(ready_room.id))

    assert is_behavior_in_active_match(db, default_behavior.id)
    assert not is_behavior_in_active_match(db, unused_behavior.id)

    db.execute(update(Match).values(status=ESTADO_FINISHED))
    db.commit()
    assert not is_behavior_in_active_match(db, default_behavior.id)
