"""Tests for GET /api/leagues."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import (
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_TYPE_FRIENDLY,
    ROOM_TYPE_PRIVATE,
    Room,
)
from tests.test_league_join import make_club, make_league

URL = "/api/leagues"


@pytest.fixture
def creator(db: Session) -> Club:
    return make_club(db, "creador")


def test_lists_an_open_public_league_with_all_fields(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    league = make_league(db, creator, name="Liga Abierta", max_clubs=8)

    r = client.get(URL, headers=auth_headers)

    assert r.status_code == 200, r.json()
    assert r.json() == [
        {
            "leagueId": league.id,
            "name": "Liga Abierta",
            "status": "waitingGuest",
            "minClubs": 3,
            "maxClubs": 8,
            "enrolledClubs": 1,
            "matchDurationMinutes": 10,
            "isEnrolled": False,
        }
    ]


def test_lists_only_open_public_leagues(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    waiting = make_league(db, creator, name="Esperando")
    ready = make_league(db, creator, name="Lista", status=ROOM_STATUS_READY_TO_START)
    make_league(db, creator, name="Privada", type=ROOM_TYPE_PRIVATE,
                password_hash="hash-secreto")
    for status in (ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED, ROOM_STATUS_CANCELLED):
        make_league(db, creator, name=f"Liga {status}", status=status)
    db.add(Room(type=ROOM_TYPE_FRIENDLY, min_clubs=2, max_clubs=2,
                match_duration_minutes=10, creator_club_id=creator.id))
    db.commit()

    r = client.get(URL, headers=auth_headers)

    assert {league["leagueId"] for league in r.json()} == {waiting.id, ready.id}


def test_includes_full_leagues(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    league = make_league(db, creator, max_clubs=3)
    for name in ("rival1", "rival2"):
        db.add(Enrollment(room_id=league.id, club_id=make_club(db, name).id))
    db.commit()

    (item,) = client.get(URL, headers=auth_headers).json()

    assert (item["enrolledClubs"], item["maxClubs"]) == (3, 3)


def test_is_enrolled_only_in_the_own_leagues(
    client: TestClient, db: Session, auth_headers, club: Club, creator: Club,
) -> None:
    own = make_league(db, club, name="Mía")
    other = make_league(db, creator, name="Ajena")

    r = client.get(URL, headers=auth_headers)

    assert {league["leagueId"]: league["isEnrolled"] for league in r.json()} == {
        own.id: True,
        other.id: False,
    }


def test_newest_league_comes_first(
    client: TestClient, db: Session, auth_headers, creator: Club,
) -> None:
    now = datetime.now(timezone.utc)
    # Created first, so insertion order is the opposite of the expected one.
    older = make_league(db, creator, name="Vieja", created_at=now - timedelta(hours=1))
    newer = make_league(db, creator, name="Nueva", created_at=now)

    r = client.get(URL, headers=auth_headers)

    assert [league["leagueId"] for league in r.json()] == [newer.id, older.id]


def test_without_leagues_returns_an_empty_list(client: TestClient, auth_headers) -> None:
    r = client.get(URL, headers=auth_headers)

    assert r.status_code == 200
    assert r.json() == []


def test_without_token_returns_401(client: TestClient) -> None:
    r = client.get(URL)

    assert r.status_code == 401
