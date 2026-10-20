import secrets
from collections import Counter

from pydantic.alias_generators import to_camel
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import (
    MAX_LEAGUE_CLUBS,
    MIN_LEAGUE_CLUBS,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_FINISHED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_READY_TO_START,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_TYPE_PRIVATE,
    ROOM_TYPE_PUBLIC,
    Room,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.schemas.league import (
    CreateLeague,
    JoinLeagueRequest,
    JoinLeagueResponse,
    JoinLeagueSelection,
    LeagueDetailRead,
    LeagueResponse,
    LeagueSquadPlayerRead,
    ListLeagueResponse,
)
from app.services.exceptions_league import (
    AlreadyInLeague,
    DuplicateLeagueName,
    DuplicatePlayer,
    InvalidBehavior,
    InvalidLeaguePassword,
    InvalidSquadBehaviors,
    InvalidSquadPlayers,
    LeagueFull,
    LeagueLimitReached,
    LeagueNotFound,
    LeagueNotOpen,
    MaxClubsBelowMin,
    MaxClubsTooHigh,
    MinClubsTooLow,
    PasswordNotAllowedOnPublicLeague,
    PlayerNotFound,
    WrongLeaguePassword,
)

STARTED_STATUSES = (ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_FINISHED)

def fold(text: str) -> str:
    """normaliza para comparar sin distinguir mayusculas"""
    return text.casefold()


class LeagueService:
    def __init__(self, db: Session):
        self.db = db

    def list_leagues(self, name: str | None = None) -> list[ListLeagueResponse]:
        # Cantidad de clubes inscriptos por sala
        counts = (
            select(Enrollment.room_id.label("room_id"), func.count(Enrollment.club_id).label("total"))
            .group_by(Enrollment.room_id)
            .subquery()
        )

        query = (
            select(Room, func.coalesce(counts.c.total, 0))
            .outerjoin(counts, counts.c.room_id == Room.id)      # una liga sin inscriptos cuenta 0
            .where(
                Room.type.in_([ROOM_TYPE_PUBLIC, ROOM_TYPE_PRIVATE]),
                Room.status != ROOM_STATUS_CANCELLED,
            )
        )
        rows = [(room, total) for room, total in self.db.execute(query).all()]

        needle = fold((name or "").strip())
        if needle:
            rows = [(room, total) for room, total in rows if needle in fold(room.name or "")]
        rows.sort(key=lambda row: (fold(row[0].name or ""), row[0].id))

        return [
            ListLeagueResponse(
                id=room.id,
                name=room.name,
                participants_count=total,
                started=room.status in STARTED_STATUSES,
                is_private=room.type == ROOM_TYPE_PRIVATE,
            )
            for room, total in rows
        ]


MIN_LEAGUE_PASSWORD_LENGTH = 6
MAX_LEAGUE_PASSWORD_BYTES = 72  # límite de bcrypt
CODE_GENERATION_ATTEMPTS = 10


# Crea la liga, inscribe al club creador con su escuadra y devuelve la respuesta.
# Todo se guarda en una sola transacción: si algo falla, no queda nada a medias.
def create_league(db: Session, data: CreateLeague, creator_club: Club) -> LeagueResponse:
    try:
        # Primero las validaciones que no consultan la BD, después las que sí.
        _validate_club_limits(data.min_clubs, data.max_clubs)
        _validate_privacy(data.is_private, data.password)
        _validate_unique_name(db, data.name)
        players_by_name = _validate_squad(db, creator_club, data.starters, data.substitutes)
        behaviors = _validate_behaviors(db, data.starters, data.substitutes)

        # Una liga privada guarda el hash de la contraseña; una pública, None.
        password_hash = hash_password(data.password) if data.is_private else None

        room = Room(
            name=data.name,
            type=ROOM_TYPE_PRIVATE if data.is_private else ROOM_TYPE_PUBLIC,
            password_hash=password_hash,
            min_clubs=data.min_clubs,
            max_clubs=data.max_clubs,
            match_duration_minutes=data.match_duration,
            code=_generate_unique_code(db),
            creator_club_id=creator_club.id,
        )
        db.add(room)
        # Flush para obtener room.id antes de crear el enrollment y la escuadra.
        db.flush()

        db.add(Enrollment(room_id=room.id, club_id=creator_club.id))

        behaviors_by_id = {b.id: b for b in behaviors}

        squad_entries = []
        for selection in data.starters:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=players_by_name[selection.player_id].id,
                    behavior_id=behaviors_by_id[selection.behavior_id].id,
                    role=ROLE_STARTER,
                )
            )
        for selection in data.substitutes:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=players_by_name[selection.player_id].id,
                    behavior_id=behaviors_by_id[selection.behavior_id].id,
                    role=ROLE_SUBSTITUTE,
                )
            )
        db.add_all(squad_entries)
        db.flush()

        response = LeagueResponse(
            id=room.id,
            name=room.name,
            is_private=room.type == ROOM_TYPE_PRIVATE,
            started=False,
            creator_id=room.creator_club_id,
            code_to_join=room.code,
        )

        db.commit()
        return response
    # Ante cualquier error se revierte toda la transacción y se propaga.
    except Exception:
        db.rollback()
        raise


# Falla si ya existe una liga con ese nombre (sin distinguir mayúsculas).
def _validate_unique_name(db: Session, name: str) -> None:
    room = db.scalar(select(Room).where(func.lower(Room.name) == name.lower()))
    if room is not None:
        raise DuplicateLeagueName(name)


# Falla si el mínimo o el máximo de clubes están fuera de rango o son inconsistentes.
def _validate_club_limits(min_clubs: int, max_clubs: int) -> None:
    if min_clubs < MIN_LEAGUE_CLUBS:
        raise MinClubsTooLow(min_clubs)
    if max_clubs > MAX_LEAGUE_CLUBS:
        raise MaxClubsTooHigh(max_clubs)
    if max_clubs < min_clubs:
        raise MaxClubsBelowMin(max_clubs, min_clubs)


# Resuelve los jugadores por nombre dentro del club creador.
# Devuelve un dict nombre -> Player para crear la escuadra sin volver a consultar.
def _validate_squad(db: Session, creator_club: Club, starters, substitutes) -> dict[str, Player]:
    player_names = [s.player_id for s in starters + substitutes]

    for name, count in Counter(player_names).items():
        if count > 1:
            raise DuplicatePlayer(name)

    # Una sola consulta, filtrando por club y excluyendo los borrados lógicamente.
    players = db.scalars(
        select(Player).where(
            Player.club_id == creator_club.id,
            Player.deleted_at.is_(None),
            Player.name.in_(player_names),
        )
    ).all()
    players_by_name = {p.name: p for p in players}

    # Se reporta el primero en orden del payload.
    for name in player_names:
        if name not in players_by_name:
            raise PlayerNotFound(name)

    return players_by_name


# Valida que todos los comportamientos asignados existan.
# Devuelve los comportamientos ya consultados para reutilizarlos.
def _validate_behaviors(db: Session, starters, substitutes):
    behavior_ids = [s.behavior_id for s in starters + substitutes]

    behaviors = db.scalars(select(Behavior).where(Behavior.id.in_(behavior_ids))).all()
    invalid_ids = set(behavior_ids) - {b.id for b in behaviors}
    if invalid_ids:
        raise InvalidBehavior(str(next(iter(invalid_ids))))

    return behaviors


# Genera un código hexadecimal de 8 caracteres que no exista en otra sala.
def _generate_unique_code(db: Session) -> str:
    for _ in range(CODE_GENERATION_ATTEMPTS):
        code = secrets.token_hex(4)
        if db.scalar(select(Room).where(Room.code == code)) is None:
            return code

    raise RuntimeError("Could not generate a unique code for the league.")


# Valida la combinación is_private/password, antes de hashear.
def _validate_privacy(is_private: bool, password: str | None) -> None:
    if not is_private:
        if password:
            raise PasswordNotAllowedOnPublicLeague()
        return

    if not password:
        raise InvalidLeaguePassword("a password is required for private leagues")
    if len(password) < MIN_LEAGUE_PASSWORD_LENGTH:
        raise InvalidLeaguePassword(
            f"it must have at least {MIN_LEAGUE_PASSWORD_LENGTH} characters"
        )
    if len(password.encode("utf-8")) > MAX_LEAGUE_PASSWORD_BYTES:
        raise InvalidLeaguePassword(f"it cannot exceed {MAX_LEAGUE_PASSWORD_BYTES} bytes")
    if any(char.isspace() for char in password):
        raise InvalidLeaguePassword("it cannot contain spaces")


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
        _validate_join_squad(db, club.id, request.starters + request.substitutes)

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


def _validate_join_squad(db: Session, club_id: str, selections: list[JoinLeagueSelection]) -> None:
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


def get_league(db: Session, league_id: str, club: Club) -> LeagueDetailRead:
    room = db.get(Room, league_id)
    if room is None or room.type not in LEAGUE_TYPES:
        raise LeagueNotFound()

    club_ids = set(db.scalars(select(Enrollment.club_id).where(Enrollment.room_id == room.id)))
    is_enrolled = club.id in club_ids
    return LeagueDetailRead(
        league_id=room.id,
        name=room.name,
        is_private=room.type == ROOM_TYPE_PRIVATE,
        status=to_camel(room.status),
        min_clubs=room.min_clubs,
        max_clubs=room.max_clubs,
        enrolled_clubs=len(club_ids),
        match_duration_minutes=room.match_duration_minutes,
        is_enrolled=is_enrolled,
        my_squad=_load_club_squad(db, room.id, club.id) if is_enrolled else None,
    )


def _load_club_squad(db: Session, league_id: str, club_id: str) -> list[LeagueSquadPlayerRead]:
    rows = db.execute(
        select(SquadEntry.role, Player.id, Player.name, Behavior.id, Behavior.name)
        .join(Player, SquadEntry.player_id == Player.id)
        .join(Behavior, SquadEntry.behavior_id == Behavior.id)
        .where(SquadEntry.room_id == league_id, Player.club_id == club_id)
    ).all()
    squad = [
        LeagueSquadPlayerRead(
            player_id=player_id,
            name=player_name,
            role=role,
            behavior_id=behavior_id,
            behavior_name=behavior_name,
        )
        for role, player_id, player_name, behavior_id, behavior_name in rows
    ]
    # Starters first.
    squad.sort(key=lambda p: p.role != ROLE_STARTER)
    return squad
