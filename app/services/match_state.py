"""Lectura autorizada y publicacion atomica del estado completo de un tick."""
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.match import Match
from app.models.match_player import MatchPlayer
from app.models.match_state import MatchStateRecord
from app.models.player import Player
from app.models.user import User
from app.schemas.match_state import ClubState, MatchState, MatchTick, PlayerState


class MatchNotFound(Exception):
    pass


class MatchAccessDenied(Exception):
    pass


class MatchStateUnavailable(Exception):
    pass


class StaleMatchState(Exception):
    pass


def get_match_state(db: Session, match_id: str, user: User) -> MatchState:
    """No inicializa, ejecuta comportamientos ni avanza el reloj."""
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFound
    club_id = db.scalar(select(Club.id).where(Club.user_id == user.id))
    if club_id not in (match.home_club_id, match.away_club_id):
        raise MatchAccessDenied
    # Leer el payload completo en una sola consulta evita mezclar revisiones.
    payload = db.scalar(select(MatchStateRecord.payload).where(MatchStateRecord.match_id == match_id))
    if payload is None:
        raise MatchStateUnavailable
    return MatchState.model_validate(payload)


def publish_match_state(
    db: Session, match_id: str, tick: MatchTick, *, expected_revision: int
) -> MatchState:
    """El motor llama al inicio y al completar cada tick; debe hacer commit.

    Una revision esperada de cero crea el estado inicial. Los siguientes ticks
    deben indicar la revision publicada anteriormente. Una lectura HTTP nunca
    llama a esta funcion. El motor debe capturar el tick bajo su propio lock.
    """
    if expected_revision < 0:
        raise ValueError("La revision no puede ser negativa")
    tick = MatchTick.model_validate(tick.model_dump())
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFound
    if match.status not in ("in_progress", "paused", "finished"):
        raise ValueError("El partido todavia no fue iniciado")
    if tick.current_time > match.duration_seconds:
        raise ValueError("El tiempo supera la duracion del partido")
    previous = db.scalar(select(MatchStateRecord.payload).where(MatchStateRecord.match_id == match_id))
    if previous is not None:
        if previous["revision"] != expected_revision:
            raise StaleMatchState
        if previous["status"] == "finished":
            raise ValueError("El partido ya termino")
        if tick.current_time < previous["current_time"]:
            raise ValueError("El tiempo no puede retroceder")
    elif expected_revision != 0:
        raise StaleMatchState
    if match.status == "finished" and tick.status != "finished":
        raise ValueError("No se puede reabrir un partido terminado")

    roster = db.execute(select(MatchPlayer, Player).join(
        Player, MatchPlayer.player_id == Player.id
    ).where(MatchPlayer.match_id == match_id)).all()
    ticks = {str(player.player_id): player for player in tick.players}
    if len(ticks) != len(tick.players) or set(ticks) != {entry.player_id for entry, _ in roster}:
        raise ValueError("El tick debe incluir exactamente los jugadores del partido, sin duplicados")
    clubs = {match.home_club_id, match.away_club_id}
    if any(entry.club_id not in clubs or player.club_id != entry.club_id for entry, player in roster):
        raise ValueError("La alineacion contiene jugadores de otro club")
    owner = str(tick.ball.owner_player_id) if tick.ball.owner_player_id else None
    if owner is not None and (owner not in ticks or not ticks[owner].on_field):
        raise ValueError("El poseedor de la pelota debe estar en cancha")
    for action in tick.actions:
        if action.player_id is not None and str(action.player_id) not in ticks:
            raise ValueError("La accion pertenece a un jugador ajeno al partido")
        if action.club_id is not None and str(action.club_id) not in clubs:
            raise ValueError("La accion pertenece a un club ajeno al partido")
    home = db.get(Club, match.home_club_id)
    away = db.get(Club, match.away_club_id)
    state = MatchState(
        match_id=match.id, revision=expected_revision + 1,
        home_club=ClubState(club_id=home.id, name=home.name),
        away_club=ClubState(club_id=away.id, name=away.name),
        status=tick.status, score=tick.score,
        result=f"{tick.score.home}-{tick.score.away}",
        current_time=tick.current_time,
        remaining_time=max(0, match.duration_seconds - tick.current_time),
        duration_seconds=match.duration_seconds,
        ball=tick.ball, actions=tick.actions,
        players=[PlayerState(
            **ticks[entry.player_id].model_dump(), club_id=entry.club_id,
            name=player.name, behavior_id=entry.behavior_id,
            has_ball=owner == entry.player_id,
        ) for entry, player in sorted(roster, key=lambda row: row[0].player_id)],
    )
    # sqlite3 en modo legacy no abre la transaccion con SELECT. Sin BEGIN,
    # liberar el primer savepoint confirmaria el tick antes del commit del motor.
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    # El savepoint revierte tambien marcador/estado si falla la publicacion.
    with db.begin_nested():
        if expected_revision == 0:
            try:
                db.add(MatchStateRecord(match_id=match_id, revision=1, payload=state.model_dump(mode="json")))
                db.flush()
            except IntegrityError as error:
                raise StaleMatchState from error
        else:
            result = db.execute(update(MatchStateRecord).where(
                MatchStateRecord.match_id == match_id,
                MatchStateRecord.revision == expected_revision,
            ).values(revision=state.revision, payload=state.model_dump(mode="json")))
            if result.rowcount != 1:
                raise StaleMatchState
        match.status = tick.status
        match.home_goals = tick.score.home
        match.away_goals = tick.score.away
        db.flush()
    return state
