import asyncio
import logging
from collections.abc import Awaitable, Callable                     
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.engine.field import FieldConfig
from app.engine.match_engine import MatchEngine
from app.engine.schedule import build_schedule
from app.engine.setup import PlayerSpec, create_initial_state
from app.engine.state import Team
from app.models.goal import Goal
from app.models.match import ESTADO_FINISHED, ESTADO_IN_PROGRESS, Match
from app.models.match_player import MatchPlayer
from app.models.player import Player

logger = logging.getLogger(__name__)                                 

# (match_id, evento) -> None. Lo implementa el módulo WebSocket.
Notifier = Callable[[str, dict], Awaitable[None]]                     

_running: dict[str, asyncio.Task] = {}


def _make_on_finish(
    match_id: str,
    home_club_id: str,
    away_club_id: str,
    notifier: Notifier | None = None,                                 
):
    club_of = {Team.HOME: home_club_id, Team.AWAY: away_club_id}

    def _persist(state) -> None:                  # síncrono: corre en un hilo
        with SessionLocal() as db:                # sesión propia, no la del request
            m = db.get(Match, match_id)
            m.home_goals = state.score[Team.HOME]
            m.away_goals = state.score[Team.AWAY]
            m.status = ESTADO_FINISHED
            m.finished_at = datetime.now(timezone.utc)
            for g in state.goals:
                db.add(Goal(match_id=match_id, club_id=club_of[g.team],
                            player_id=g.player_id, second=g.second))
                if g.player_id is not None:
                    db.execute(
                        update(MatchPlayer)
                        .where(MatchPlayer.match_id == match_id,
                               MatchPlayer.player_id == g.player_id)
                        .values(goals=MatchPlayer.goals + 1)
                    )
            db.execute(update(Player)
                       .where(Player.id.in_([p.id for p in state.players]))
                       .values(is_playing=False))
            db.commit()

    async def on_finish(state) -> None:
        # 1. Persistir primero: un cliente que consulte la API tras el aviso
        #    tiene que ver el resultado ya guardado.
        await asyncio.to_thread(_persist, state)

        # 2. Notificar después. Si falla, el resultado ya está a salvo. 
        if notifier is None:
            return
        event = {
            "type": "MATCH_FINISHED",
            "match_id": match_id,
            "home_goals": state.score[Team.HOME],
            "away_goals": state.score[Team.AWAY],
            "goals": [
                {"club_id": club_of[g.team], "player_id": g.player_id,
                 "second": g.second}
                for g in state.goals
            ],
        }
        try:
            await notifier(match_id, event)
        except Exception:
            logger.exception("Falló la notificación del partido %s", match_id)

    return on_finish


def build_engine_from_db(
    db: Session, match_id: str, cfg,
    notifier: Notifier | None = None,                                
) -> MatchEngine:
    match = db.get(Match, match_id)
    if match is None:
        raise LookupError(f"Partido {match_id} no existe")

    rows = db.execute(
        select(MatchPlayer, Player)
        .join(Player, Player.id == MatchPlayer.player_id)
        .where(MatchPlayer.match_id == match_id, MatchPlayer.on_field.is_(True))
        .order_by(MatchPlayer.id)                 # orden estable entre ejecuciones
    ).all()

    home, away, behaviors = [], [], {}
    for mp, pl in rows:
        spec = PlayerSpec(pl.id, pl.speed, pl.control, pl.strength, pl.power, pl.agility)
        (home if mp.club_id == match.home_club_id else away).append(spec)
        behaviors[pl.id] = mp.behavior_id

    field = FieldConfig()
    state = create_initial_state(field, home, away)      # valida 3 por equipo
    schedule = build_schedule(
        match.duration_seconds, cfg.match_tick_rate,
        hydration_seconds=match.pause_duration_seconds,
        halftime_seconds=match.pause_duration_seconds,
    )
    return MatchEngine(
        state, field, cfg, behaviors, schedule=schedule,
        on_finish=_make_on_finish(
            match_id, match.home_club_id, match.away_club_id, notifier 
        ),
    )


def start_match(
    db: Session, match_id: str, cfg,
    notifier: Notifier | None = None,                                 
) -> None:
    """Punto de entrada para quien cierre el pre-partido."""
    if match_id in _running:
        raise RuntimeError("El partido ya está en curso")
    engine = build_engine_from_db(db, match_id, cfg, notifier)

    match = db.get(Match, match_id)
    match.status = ESTADO_IN_PROGRESS
    match.started_at = datetime.now(timezone.utc)
    ids = [p.id for p in engine.state.players]
    db.execute(update(Player).where(Player.id.in_(ids)).values(is_playing=True))
    db.commit()

    task = asyncio.create_task(engine.run(), name=f"match-{match_id}")
    _running[match_id] = task
    task.add_done_callback(lambda _t: _running.pop(match_id, None))