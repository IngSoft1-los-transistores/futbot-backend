# tests/test_dt_behavior.py
from datetime import datetime, timezone

from app.models.behavior import BEHAVIOR_KIND_DT, BEHAVIOR_KIND_PLAYER, Behavior

URL = "/api/club/dt-behavior"


def make_behavior(db, club, kind=BEHAVIOR_KIND_DT, name="my_dt"):
    behavior = Behavior(
        club_id=club.id,
        name=name,
        code="def behavior(player):\n    pass",
        is_preprogrammed=False,
        kind=kind,
    )
    db.add(behavior)
    db.commit()
    return behavior


def test_get_without_dt_returns_null(client, auth_headers):
    response = client.get(URL, headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_put_assigns_dt_and_get_returns_it(client, db, club, auth_headers):
    dt = make_behavior(db, club)
    response = client.put(f"{URL}/{dt.id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"behavior_id": dt.id, "name": "my_dt"}
    assert client.get(URL, headers=auth_headers).json()["behavior_id"] == dt.id


def test_put_replaces_previous_dt(client, db, club, auth_headers):
    first = make_behavior(db, club, name="dt_one")
    second = make_behavior(db, club, name="dt_two")
    client.put(f"{URL}/{first.id}", headers=auth_headers)
    client.put(f"{URL}/{second.id}", headers=auth_headers)
    assert client.get(URL, headers=auth_headers).json()["behavior_id"] == second.id


def test_put_unknown_behavior_returns_404(client, auth_headers):
    assert client.put(f"{URL}/does-not-exist", headers=auth_headers).status_code == 404


def test_put_behavior_of_other_club_returns_404(client, db, other_club, auth_headers):
    foreign = make_behavior(db, other_club)
    assert client.put(f"{URL}/{foreign.id}", headers=auth_headers).status_code == 404


def test_put_deleted_behavior_returns_404(client, db, club, auth_headers):
    dt = make_behavior(db, club)
    dt.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert client.put(f"{URL}/{dt.id}", headers=auth_headers).status_code == 404


def test_put_player_behavior_returns_400(client, db, club, auth_headers):
    player_behavior = make_behavior(db, club, kind=BEHAVIOR_KIND_PLAYER, name="not_dt")
    assert client.put(f"{URL}/{player_behavior.id}", headers=auth_headers).status_code == 400


def test_put_preprogrammed_behavior_returns_404(client, comportamiento_prueba, auth_headers):
    response = client.put(f"{URL}/{comportamiento_prueba.id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_clears_dt(client, db, club, auth_headers):
    dt = make_behavior(db, club)
    client.put(f"{URL}/{dt.id}", headers=auth_headers)
    assert client.delete(URL, headers=auth_headers).status_code == 204
    assert client.get(URL, headers=auth_headers).json() is None


def test_delete_without_dt_returns_404(client, auth_headers):
    assert client.delete(URL, headers=auth_headers).status_code == 404


def test_second_delete_returns_404(client, db, club, auth_headers):
    dt = make_behavior(db, club)
    client.put(f"{URL}/{dt.id}", headers=auth_headers)
    client.delete(URL, headers=auth_headers)
    assert client.delete(URL, headers=auth_headers).status_code == 404


def test_endpoints_require_authentication(client):
    assert client.get(URL).status_code == 401
    assert client.put(f"{URL}/x").status_code == 401
    assert client.delete(URL).status_code == 401
