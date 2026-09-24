from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generar_uuid

if TYPE_CHECKING:
    from app.models.enrollment import Room

"""Modelo de escuadra: los 6 jugadores elegidos y su comportamiento."""

# --- Roles dentro de la escuadra ---
ROL_STARTER = "starter"
ROL_SUBSTITUTE = "substitute"
ROLES_ESCUADRA = (ROL_STARTER, ROL_SUBSTITUTE)

# Cantidad exacta de cada rol, fijada por el alcance del proyecto.
CANTIDAD_STARTERS = 3
CANTIDAD_SUBSTITUTES = 3

class SquadEntry(Base):
    """Un jugador convocado por un club, con el comportamiento que le asigno.
    """

    __tablename__ = "squad_entries"
    __table_args__ = (
        CheckConstraint(
            f"role IN ('{ROL_STARTER}', '{ROL_SUBSTITUTE}')",
            name="ck_squad_entries_rol_valido",
        ),
        # El mismo jugador no puede ser convocado dos veces en la misma inscripcion
        UniqueConstraint(
            "enrollment_id", "player_id", name="ux_squad_entries_enrollment_player"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generar_uuid)

    enrollment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )

    # Sin CASCADE a proposito: el borrado de un jugador es logico.
    player_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("players.id"), nullable=False
    )

    # Comportamiento con el que el jugador arranca cada partido.
    behavior_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("behaviors.id"), nullable=False
    )

    # si es titular  o suplente
    role: Mapped[str] = mapped_column(String(10), nullable=False)

    room: Mapped["Room"] = relationship(back_populates="squad_entries")