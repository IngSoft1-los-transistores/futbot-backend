from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import password_context
from app.models.club import Club
from app.models.user import User


@pytest.fixture
def login_user(db: Session) -> User:
    user = User(
        username="login-tester", email="login@futbot.test",
        password_hash=password_context.hash("correct-password"),
    )
    user.club = Club(name="Login Club")
    db.add(user)
    db.commit()
    return user


def test_login_success(client: TestClient, login_user: User) -> None:
    settings = get_settings()
    started_at = int(datetime.now(timezone.utc).timestamp())
    response = client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": "correct-password"},
    )
    finished_at = int(datetime.now(timezone.utc).timestamp())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"accessToken", "tokenType", "clubId"}
    assert body["tokenType"] == "bearer"
    assert body["clubId"] == login_user.club.id  # assert body["clubId"] == str(login_user.club.id)
    claims = jwt.decode(
        body["accessToken"], settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["sub"] == login_user.id #str(login_user.id)
    lifetime = settings.jwt_expire_minutes * 60
    assert started_at + lifetime <= claims["exp"] <= finished_at + lifetime
    assert set(claims) == {"sub", "exp"}
    with pytest.raises(JWTError):
        jwt.decode(body["accessToken"], "wrong-key", algorithms=[settings.jwt_algorithm])


@pytest.mark.parametrize("email,password", [
    ("missing@futbot.test", "correct-password"),
    ("login@futbot.test", "wrong-password"),
])
def test_login_invalid_credentials(
    client: TestClient, login_user: User, email: str, password: str
) -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Credenciales inválidas"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_without_club(client: TestClient, db: Session, login_user: User) -> None:
    db.delete(login_user.club)
    db.commit()
    db.expire_all()
    response = client.post(
        "/api/auth/login",
        json={"email": login_user.email, "password": "correct-password"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "La cuenta no tiene un club asociado"}


@pytest.mark.parametrize("payload", [{}, {"email": "login@futbot.test"}])
def test_login_requires_credentials(client: TestClient, payload: dict) -> None:
    assert client.post("/api/auth/login", json=payload).status_code == 422
