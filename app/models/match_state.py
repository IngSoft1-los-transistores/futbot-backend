"""Ultima instantanea completa del motor, compartida entre procesos."""
from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchStateRecord(Base):
    __tablename__ = "match_states"

    match_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
