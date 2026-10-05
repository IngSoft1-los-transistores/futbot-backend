"""Punto de integración del motor: ticks en memoria y eventos durables."""
from collections import Counter
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ahora_utc
from app.engine.live_state import match_states
from app.models.goal import Goal
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import Room
from app.schemas.match_state import MatchState, MatchTick
from app.services.match_state import prepare_match_state, publish_prepared_state


class MatchStateSource(Protocol):
    def capture_state(self) -> MatchTick:
        """Captura un tick completo bajo el lock del motor, después de las acciones."""
        ...


def publish_engine_state(db: Session, match_id: str, engine: MatchStateSource, *, expected_revision: int) -> MatchState:
    return publish_engine_tick(db, match_id, engine.capture_state(), expected_revision=expected_revision)


def publish_engine_tick(db: Session, match_id: str, tick: MatchTick, *, expected_revision: int) -> MatchState:
    """Usar una sesión limpia y datos de creación ya confirmados.

    Solo hace commit ante goles o cambios de estado (pausa/reanudación/fin).
    Un fallo al persistir no publica el snapshot ni avanza su revisión.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError('El motor requiere una sesión sin cambios pendientes')
    with match_states.lock(match_id):
        state = prepare_match_state(db, match_id, tick, expected_revision=expected_revision)
        match = db.get(Match, match_id)
        goals = [action for action in state.actions if action.type == 'goal']
        counts = Counter(str(goal.club_id) for goal in goals)
        expected = Counter({
            match.home_club_id: state.score.home - match.home_goals,
            match.away_club_id: state.score.away - match.away_goals,
        })
        if any(count < 0 for count in expected.values()) or counts != expected:
            raise ValueError('Cada incremento del marcador requiere su evento de gol con club')
        significant = bool(goals) or match.status != state.status
        if significant:
            try:
                for goal in goals:
                    scorer = next((p for p in state.players if p.player_id == goal.player_id), None)
                    # En un gol en contra no se atribuye el gol al jugador rival.
                    scorer_id = str(scorer.player_id) if scorer and scorer.club_id == goal.club_id else None
                    db.add(Goal(match_id=match_id, club_id=str(goal.club_id), player_id=scorer_id,
                                second=int(state.current_time)))
                    if scorer_id:
                        entry = db.scalar(select(MatchPlayer).where(MatchPlayer.match_id == match_id, MatchPlayer.player_id == scorer_id))
                        entry.goals += 1
                match.home_goals, match.away_goals = state.score.home, state.score.away
                match.status = state.status
                if state.status == 'finished':
                    match.finished_at = ahora_utc()
                    room = db.get(Room, match.room_id)
                    if room.type == 'friendly':
                        room.status, room.finished_at = 'finished', match.finished_at
                    for player in state.players:
                        db.get(Player, str(player.player_id)).is_playing = False
                db.commit()
            except Exception:
                db.rollback()
                raise
        publish_prepared_state(state)
        return state
