import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.room import (
    MAX_LEAGUE_CLUBS,
    MIN_LEAGUE_CLUBS,
    Room,
    ROOM_TYPE_PUBLIC,
    ROOM_TYPE_PRIVATE,
    ROOM_STATUS_CANCELLED,
    ROOM_STATUS_IN_PROGRESS,
    ROOM_STATUS_FINISHED,
)
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.schemas.league import LeagueResponse, ListLeagueResponse, CreateLeague
from app.services.exceptions_league import (
    DuplicateLeagueName,
    InvalidLeaguePassword,
    MaxClubsBelowMin,
    MaxClubsTooHigh,
    MinClubsTooLow,
    PasswordNotAllowedOnPublicLeague,
)
from app.services.squad_validator import validate_squad_selection

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
        validate_squad_selection(db, creator_club.id, data.starters, data.substitutes)

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

        squad_entries = []
        for selection in data.starters:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
                    role=ROLE_STARTER,
                )
            )
        for selection in data.substitutes:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=selection.player_id,
                    behavior_id=selection.behavior_id,
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
