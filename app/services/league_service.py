from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.schemas.friendly_room import JoinPlayerSelection
from app.schemas.league import JoinLeagueRequest, JoinLeagueResponse
from app.services.exceptions_league import (
    AlreadyInLeague,
    InvalidSquadBehaviors,
    InvalidSquadPlayers,
    LeagueFull,
    LeagueLimitReached,
    LeagueNotFound,
    LeagueNotOpen,
    WrongLeaguePassword,
)

LEAGUE_TYPES = (ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE)
# A league accepts clubs until it starts.
OPEN_LEAGUE_STATES = (ROOM_STATUS_WAITING_GUEST, ROOM_STATUS_READY_TO_START)
ACTIVE_LEAGUE_STATES = (*OPEN_LEAGUE_STATES, ROOM_STATUS_IN_PROGRESS)
MAX_ACTIVE_LEAGUES = 2


def join_league(
    db: Session, league_id: str, club: Club, request: JoinLeagueRequest
) -> JoinLeagueResponse:
    room = db.get(Room, league_id)
    if room is None or room.type not in LEAGUE_TYPES:
        raise LeagueNotFound()
    if room.status not in OPEN_LEAGUE_STATES:
        raise LeagueNotOpen()
    if room.type == ROOM_TYPE_PRIVATE and not verify_password(
        request.password or "", room.password_hash
    ):
        raise WrongLeaguePassword()

    try:
        _lock_open_league(db, room.id)
        _check_can_enroll(db, room, club.id)
        _validate_squad(db, club.id, request.starters + request.substitutes)

        enrollment = Enrollment(room_id=room.id, club_id=club.id)
        db.add(enrollment)
        for role, selections in (
            (ROLE_STARTER, request.starters),
            (ROLE_SUBSTITUTE, request.substitutes),
        ):
            db.add_all(
                SquadEntry(
                    room_id=room.id,
                    player_id=s.player_id,
                    behavior_id=s.behavior_id,
                    role=role,
                )
                for s in selections
            )
        db.flush()

        response = JoinLeagueResponse(
            enrollment_id=enrollment.id, club_id=club.id, league_id=room.id
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def _lock_open_league(db: Session, league_id: str) -> None:
    # No-op write that takes the room's write lock, so concurrent joins can't race the counts.
    locked = db.execute(
        update(Room)
        .where(Room.id == league_id, Room.status.in_(OPEN_LEAGUE_STATES))
        .values(status=Room.status)
        .execution_options(synchronize_session=False)
    ).rowcount
    if locked != 1:
        raise LeagueNotOpen()


def _check_can_enroll(db: Session, room: Room, club_id: str) -> None:
    already_enrolled = db.scalar(
        select(exists().where(Enrollment.room_id == room.id, Enrollment.club_id == club_id))
    )
    if already_enrolled:
        raise AlreadyInLeague()

    active_leagues = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Room, Room.id == Enrollment.room_id)
        .where(
            Enrollment.club_id == club_id,
            Room.type.in_(LEAGUE_TYPES),
            Room.status.in_(ACTIVE_LEAGUE_STATES),
        )
    )
    if active_leagues >= MAX_ACTIVE_LEAGUES:
        raise LeagueLimitReached(MAX_ACTIVE_LEAGUES)

    enrolled_clubs = db.scalar(
        select(func.count()).select_from(Enrollment).where(Enrollment.room_id == room.id)
    )
    if enrolled_clubs >= room.max_clubs:
        raise LeagueFull()


def _validate_squad(db: Session, club_id: str, selections: list[JoinPlayerSelection]) -> None:
    player_ids = {s.player_id for s in selections}
    if len(player_ids) != len(selections):
        raise InvalidSquadPlayers()

    own_players = db.scalar(
        select(func.count())
        .select_from(Player)
        .where(
            Player.id.in_(player_ids),
            Player.club_id == club_id,
            Player.deleted_at.is_(None),
        )
    )
    if own_players != len(player_ids):
        raise InvalidSquadPlayers()

    behavior_ids = {s.behavior_id for s in selections}
    usable_behaviors = db.scalar(
        select(func.count())
        .select_from(Behavior)
        .where(
            Behavior.id.in_(behavior_ids),
            Behavior.deleted_at.is_(None),
            # club_id IS NULL means preprogrammed.
            or_(Behavior.club_id == club_id, Behavior.club_id.is_(None)),
        )
    )
    if usable_behaviors != len(behavior_ids):
        raise InvalidSquadBehaviors()
