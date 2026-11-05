from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.friendly_room import CreateFriendlyRoomRequest, PlayerSelection, RoomStatus
from app.services.friendly_service import FriendlyService, generate_room_code

# La validacion de la plantilla se prueba en test_squad_validator.py.


# ─── FIXTURES MOCK DE ENTRADA ───

@pytest.fixture
def valid_payload():
    """Genera un payload válido con 3 starters y 3 substitutes."""
    behavior_id = str(uuid4())
    return CreateFriendlyRoomRequest(
        starters=[
            PlayerSelection(player_id=str(uuid4()), behavior_id=behavior_id)
            for _ in range(3)
        ],
        substitutes=[
            PlayerSelection(player_id=str(uuid4()), behavior_id=behavior_id)
            for _ in range(3)
        ]
    )


@pytest.fixture
def mock_db():
    """Mock de la sesión de SQLAlchemy."""
    return MagicMock()


# ─── TESTS UNITARIOS DE CREACIÓN DE SALA (CREATE_ROOM) ───

@patch("app.services.friendly_service.validate_squad_selection")
@patch("app.services.friendly_service.generate_room_code", return_value="ROOM12")
def test_create_room_unit_success(mock_code, mock_validate, mock_db, valid_payload):
    """Verifica que create_room cree y persista los objetos en la DB correctamente."""
    service = FriendlyService(mock_db)

    # Mock de colisión de código: primero None (no existe en DB)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Asignar un ID ficticio al new_room cuando se ejecuta db.flush
    def fake_flush():
        # Busca el objeto Room que fue agregado a la DB y le asigna un ID
        for call in mock_db.add.call_args_list:
            obj = call[0][0]
            if hasattr(obj, "id") and getattr(obj, "id") is None:
                obj.id = "room-uuid-123"

    mock_db.flush.side_effect = fake_flush

    club_id = "club-unit-test"
    result = service.create_room(club_id, valid_payload)

    # 1. Validar llamada a validación
    mock_validate.assert_called_once_with(
        mock_db, club_id, valid_payload.starters, valid_payload.substitutes
    )

    # 2. Validar llamadas a la sesión de SQLAlchemy
    assert mock_db.add.call_count == 8  # 1 Room + 1 Enrollment + 6 SquadEntries
    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()

    # 3. Validar respuesta del servicio
    assert result.room_id == "room-uuid-123"
    assert result.room_code == "ROOM12"
    assert result.status == RoomStatus.WAITING_GUEST.value
    assert result.home_club == club_id


@patch("app.services.friendly_service.validate_squad_selection")
def test_create_room_saves_the_selected_ids(mock_validate, mock_db, valid_payload):
    """Las SquadEntry guardan los ids tal como llegaron, sin traducirlos."""
    mock_db.query.return_value.filter.return_value.first.return_value = None

    def assign_room_id():
        # La sala (Room) es lo único que se agrega antes del flush.
        mock_db.add.call_args.args[0].id = "room-uuid-123"

    mock_db.flush.side_effect = assign_room_id

    FriendlyService(mock_db).create_room("club-unit-test", valid_payload)

    saved = [
        (call.args[0].player_id, call.args[0].behavior_id)
        for call in mock_db.add.call_args_list
        if hasattr(call.args[0], "player_id")
    ]
    expected = [
        (s.player_id, s.behavior_id)
        for s in valid_payload.starters + valid_payload.substitutes
    ]
    assert saved == expected


def test_generate_room_code_format():
    """Prueba unitaria auxiliar para la función generadora de códigos."""
    code = generate_room_code(length=6)
    assert len(code) == 6
    assert code.isalnum()
    assert code.isupper()
