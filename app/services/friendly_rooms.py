from collections import Counter

from fastapi import HTTPException, status
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import ahora_utc
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.match import (
    ESTADO_IN_PROGRESS,
    ESTADO_PAUSED,
    ESTADO_PRE_MATCH,
    Match,
)
from app.models.match_player import MatchPlayer
from app.models.player import Player
from app.models.room import (
    STATE_FINISHED,
    STATE_IN_PROGRESS,
    STATE_READY_TO_START,
    TYPE_FRIENDLY,
    Room,
)
from app.models.squad_entry import (
    CANTIDAD_STARTERS,
    CANTIDAD_SUBSTITUTES,
    ROL_STARTER,
    ROL_SUBSTITUTE,
    SquadEntry,
)

"""Business logic for friendly rooms."""

# A friendly is always one home club against one away club.
FRIENDLY_CLUBS = 2

# Room states in which the match has already been started.
STARTED_ROOM_STATES = (STATE_IN_PROGRESS, STATE_FINISHED)

# Match states in which the lineup and its behaviors are locked.
ACTIVE_MATCH_STATES = (ESTADO_PRE_MATCH, ESTADO_IN_PROGRESS, ESTADO_PAUSED)


def _error(status_code: int, error_code: str, message: str) -> HTTPException:
    """Builds an HTTPException in the contract error shape."""
    return HTTPException(
        status_code=status_code,
        detail={"detail": message, "error_code": error_code},
    )


def _already_started() -> HTTPException:
    return _error(
        status.HTTP_400_BAD_REQUEST,
        "MATCH_ALREADY_STARTED",
        "El partido de esta sala ya fue iniciado",
    )


def _invalid_squad() -> HTTPException:
    return _error(
        status.HTTP_400_BAD_REQUEST,
        "INVALID_SQUAD",
        "Algún club no tiene sus 3 titulares y 3 suplentes con comportamientos válidos",
    )


def _validate_squads(
    rows: list[tuple[SquadEntry, Player, Behavior]], club_ids: set[str]
) -> None:
    """Checks that each club brings exactly 3 starters and 3 substitutes,
    all of them usable, each with a behavior the club is allowed to use.

    Checked at start time and not only on join: between joining and starting,
    a club may have deleted a player or a behavior.
    """
    roles_per_club: dict[str, Counter] = {club_id: Counter() for club_id in club_ids}

    for entry, player, behavior in rows:
        if player.club_id not in club_ids:
            raise _invalid_squad()
        if player.deleted_at is not None or player.is_playing:
            raise _invalid_squad()
        # A behavior is usable if it is preprogrammed (no club) or owned by
        # the player's club.
        if behavior.deleted_at is not None or behavior.club_id not in (
            None,
            player.club_id,
        ):
            raise _invalid_squad()
        roles_per_club[player.club_id][entry.role] += 1

    expected = Counter({ROL_STARTER: CANTIDAD_STARTERS, ROL_SUBSTITUTE: CANTIDAD_SUBSTITUTES})
    if any(roles != expected for roles in roles_per_club.values()):
        raise _invalid_squad()


def _start_simulation(match_id: str) -> None:
    """Hook where the match engine starts running the match.

    No-op until the engine exists (SCRUM-40 runs the behaviors each tick,
    SCRUM-42 broadcasts the state over `/ws/match/{match_id}`). It is called
    only after the commit, so the engine never runs a match that was rolled
    back. It must not block the request.
    """


def start_friendly_match(db: Session, room_id: str, club: Club) -> Match:
    """Starts the friendly match of a room on behalf of one of its clubs.

    Validation order matters: nothing about the room's state is revealed to a
    club that does not belong to it.
    """
    room = db.get(Room, room_id)
    # A league id is also "not found": this endpoint only knows friendlies.
    if room is None or room.type != TYPE_FRIENDLY:
        raise _error(
            status.HTTP_404_NOT_FOUND, "ROOM_NOT_FOUND", "La sala amistosa no existe"
        )

    club_ids = set(
        db.scalars(select(Enrollment.club_id).where(Enrollment.room_id == room.id))
    )
    if club.id not in club_ids:
        raise _error(
            status.HTTP_403_FORBIDDEN,
            "NOT_ROOM_MEMBER",
            "Tu club no pertenece a esta sala",
        )

    if room.status in STARTED_ROOM_STATES:
        raise _already_started()

    if len(club_ids) != FRIENDLY_CLUBS or room.creator_club_id not in club_ids:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "ROOM_NOT_FULL",
            "La sala todavía no tiene club local y visitante",
        )

    if room.status != STATE_READY_TO_START:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "ROOM_NOT_READY",
            "La sala no está lista para iniciar el partido",
        )

    # Single query for both squads (no N+1 over players and behaviors).
    rows = db.execute(
        select(SquadEntry, Player, Behavior)
        .join(Player, SquadEntry.player_id == Player.id)
        .join(Behavior, SquadEntry.behavior_id == Behavior.id)
        .where(SquadEntry.room_id == room.id)
    ).tuples().all()
    _validate_squads(rows, club_ids)

    home_club_id = room.creator_club_id
    (away_club_id,) = club_ids - {home_club_id}
    now = ahora_utc()

    # Conditional update: if both clubs start at the same time, both requests
    # pass the checks above, but only one of them can move the room out of
    # `ready_to_start`. A read-then-write would let both through.
    result = db.execute(
        update(Room)
        .where(Room.id == room.id, Room.status == STATE_READY_TO_START)
        .values(status=STATE_IN_PROGRESS, started_at=now)
    )
    if result.rowcount != 1:
        db.rollback()
        raise _already_started()

    # No pre-match stage this sprint: there is no interaction once started,
    # so the lineup is the one chosen when creating/joining the room.
    match = Match(
        room_id=room.id,
        home_club_id=home_club_id,
        away_club_id=away_club_id,
        status=ESTADO_IN_PROGRESS,
        duration_seconds=room.match_duration_minutes * 60,
        started_at=now,
    )
    db.add(match)
    db.flush()

    for entry, player, _behavior in rows:
        db.add(
            MatchPlayer(
                match_id=match.id,
                club_id=player.club_id,
                player_id=player.id,
                behavior_id=entry.behavior_id,
                on_field=entry.role == ROL_STARTER,
            )
        )
        # Locks the player: endpoints that edit or delete players must
        # reject it while `is_playing` is set.
        player.is_playing = True

    try:
        db.commit()
    except IntegrityError:
        # Second safety net: UNIQUE(room_id, home_club_id, away_club_id).
        db.rollback()
        raise _already_started()

    _start_simulation(match.id)
    return match


def is_behavior_in_active_match(db: Session, behavior_id: str) -> bool:
    """Tells whether a behavior is assigned to a player of an active match.

    Endpoints that edit or delete behaviors must reject the operation when
    this is true.
    """
    return db.scalar(
        select(
            exists()
            .where(MatchPlayer.behavior_id == behavior_id)
            .where(MatchPlayer.match_id == Match.id)
            .where(Match.status.in_(ACTIVE_MATCH_STATES))
        )
    )
