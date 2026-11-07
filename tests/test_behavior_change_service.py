import pytest

from app.db.base import ahora_utc
from app.models.behavior import Behavior
from app.services.behavior_change_service import behavior_belongs_to_club


def make_behavior(db, club_id, name="Mi comportamiento", deleted=False):
    behavior = Behavior(
        club_id=club_id,
        name=name,
        code="def decide(ctx): pass",
        is_preprogrammed=club_id is None,
        deleted_at=ahora_utc() if deleted else None,
    )
    db.add(behavior)
    db.commit()
    return behavior


def test_own_behavior_is_valid(db, club):
    behavior = make_behavior(db, club.id)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is True


def test_preprogrammed_behavior_is_valid(db, club, comportamiento_prueba):
    assert behavior_belongs_to_club(db, comportamiento_prueba.id, club.id) is True


def test_behavior_of_other_club_is_invalid(db, club, other_club):
    behavior = make_behavior(db, other_club.id)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is False


def test_deleted_behavior_is_invalid(db, club):
    behavior = make_behavior(db, club.id, deleted=True)
    assert behavior_belongs_to_club(db, behavior.id, club.id) is False


def test_unknown_behavior_is_invalid(db, club):
    assert behavior_belongs_to_club(db, "no-existe", club.id) is False
