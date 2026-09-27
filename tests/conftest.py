import os

# Test-only secret, set before importing the app.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-production"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 - registra las tablas en Base.metadata
from app.db.base import Base
from app.db.session import _crear_engine, get_db
from app.main import app
from app.models.club import Club
from app.models.player import Player
from app.models.user import User

"""Fixtures compartidas por todos los tests."""

@pytest.fixture
def engine(tmp_path) -> Generator[Engine, None, None]:
    """Engine contra una base SQLite temporal, propia de cada test.
    """
    engine = _crear_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session, None, None]:
    """Sesion de base de datos apuntando a la base temporal del test."""
    fabrica = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    sesion = fabrica()
    try:
        yield sesion
    finally:
        sesion.close()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP con la dependencia de base de datos redirigida al test.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# --- Helpers de creacion de datos ---


@pytest.fixture
def club(db: Session) -> Club:
    """Crea un usuario con su club y los deja persistidos."""
    usuario = User(
        username="tester",
        email="tester@futbot.test",
        password_hash="hash-de-prueba",
    )
    db.add(usuario)
    db.flush()

    club = Club(user_id=usuario.id, name="Club de Prueba")
    db.add(club)
    db.commit()

    return club


def crear_player(db: Session, club_id: str, **overrides) -> Player:
    """Crea un jugador con PACSS validos (60 en cada atributo suma 300)."""
    atributos = {
        "power": 60,
        "agility": 60,
        "control": 60,
        "speed": 60,
        "strength": 60,
    }
    atributos.update(overrides)

    player = Player(club_id=club_id, name="Jugador de Prueba", **atributos)
    db.add(player)
    db.commit()

    return player