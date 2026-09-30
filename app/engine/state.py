"""Punto de integracion para el motor de simulacion (aun no implementado)."""
from typing import Protocol

from sqlalchemy.orm import Session

from app.schemas.match_state import MatchState, MatchTick
from app.services.match_state import publish_match_state


class MatchStateSource(Protocol):
    def capture_state(self) -> MatchTick:
        """Captura un tick completo bajo el lock del motor, despues de las acciones."""
        ...


def publish_engine_state(
    db: Session, match_id: str, engine: MatchStateSource, *, expected_revision: int
) -> MatchState:
    """Llamar al inicio y al finalizar cada tick; confirmar con db.commit()."""
    return publish_match_state(
        db, match_id, engine.capture_state(), expected_revision=expected_revision,
    )
