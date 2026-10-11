import secrets
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.behavior import Behavior
from app.models.club import Club
from app.models.enrollment import Enrollment
from app.models.player import Player
from app.models.room import MAX_LEAGUE_CLUBS, MIN_LEAGUE_CLUBS, ROOM_TYPE_PUBLIC, Room
from app.models.squad_entry import ROLE_STARTER, ROLE_SUBSTITUTE, SquadEntry
from app.schemas.league import CreateLeague, LeagueResponse
from app.services.exceptions_league import (
    ComportamientoInvalido,
    JugadorNoExiste,
    JugadorNoPerteneceAlClub,
    JugadorRepetido,
    MaximosClubsInvalido,
    MaximosRespectoMinimosClubs,
    MinimoClubsInvalido,
    NombreUnicoInvalido,
)


def create_league(db: Session, datos: CreateLeague, club_creador: Club) -> LeagueResponse:
    try:
        _validar_nombre_unico(db, datos.name)
        _validar_cantidad_clubs(datos.min_clubs, datos.max_clubs)

        # 2. Guardar los resultados de las validaciones.
        jugadores = _validar_escuadra(
            db,
            club_creador,
            datos.starters,
            datos.substitutes,
        )

        comportamientos = _validar_comportamientos(db, datos.starters, datos.substitutes)

        # Crear la liga.
        codigo = _generar_codigo_unico(db)

        #Crear la liga y el enrollment del club creador.
        room = Room(
            name=datos.name,
            min_clubs=datos.min_clubs,
            max_clubs=datos.max_clubs,
            match_duration_minutes=datos.match_duration,
            type=ROOM_TYPE_PUBLIC,
            code=codigo,
            creator_club_id=club_creador.id,
        )
        db.add(room)
        db.flush() # Flush para obtener el ID de la liga recién creada antes de crear el enrollment y las entradas del escuadra.

        enrollment = Enrollment(
            room_id=room.id,
            club_id=club_creador.id,
        )
        db.add(enrollment)

        # Crear las entradas usando los objetos validados.
        jugadores_por_id = {j.id: j for j in jugadores}
        comportamientos_por_id = {b.id: b for b in comportamientos}

        squad_entries = []

        for starter in datos.starters:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=jugadores_por_id[starter.player_id].id,
                    behavior_id=comportamientos_por_id[starter.behavior_id].id,
                    role=ROLE_STARTER,
                )
            )

        for substitute in datos.substitutes:
            squad_entries.append(
                SquadEntry(
                    room_id=room.id,
                    player_id=jugadores_por_id[substitute.player_id].id,
                    behavior_id=comportamientos_por_id[substitute.behavior_id].id,
                    role=ROLE_SUBSTITUTE,
                )
            )

        db.add_all(squad_entries)
        db.flush()

        response = LeagueResponse(
            id=room.id,
            name=room.name,
            is_private=False,
            started=False,
            creator_id=room.creator_club_id,
            code_to_join=room.code,
        )

        db.commit()
        return response
    # Si ocurre cualquier excepción, hacemos rollback de la transacción y propagamos la excepción.
    except Exception:
        db.rollback()
        raise


def _validar_nombre_unico(db: Session, name: str) -> None:
    room = db.scalar(select(Room).where(func.lower(Room.name) == name.lower()))

    if room is not None:
        raise NombreUnicoInvalido(name)


def _validar_cantidad_clubs(min_clubs: int, max_clubs: int) -> None:
    if min_clubs < MIN_LEAGUE_CLUBS:
        raise MinimoClubsInvalido(min_clubs)

    if max_clubs > MAX_LEAGUE_CLUBS:
        raise MaximosClubsInvalido(max_clubs)

    if max_clubs < min_clubs:
        raise MaximosRespectoMinimosClubs(max_clubs, min_clubs)


def _validar_escuadra(db, club_creador, starters, substitutes):
    todos = starters + substitutes
    player_ids = [s.player_id for s in todos]

    conteo = Counter(player_ids)
    for player_id, cantidad in conteo.items():
        if cantidad > 1:
            raise JugadorRepetido(str(player_id))
    # Validar que todos los jugadores existan y pertenezcan al club creador.
    jugadores = db.scalars(select(Player).where(Player.id.in_(player_ids))).all()
    ids_encontrados = {j.id for j in jugadores}
    ids_faltantes = set(player_ids) - ids_encontrados

    if ids_faltantes:
        primer_faltante = next(iter(ids_faltantes))
        raise JugadorNoExiste(str(primer_faltante))

    for jugador in jugadores:
        if jugador.club_id != club_creador.id:
            raise JugadorNoPerteneceAlClub(
                club_id=club_creador.id,
                nombre_club=club_creador.name,
                player_id=jugador.id,
                nombre_player=jugador.name,
            )

    return jugadores


def _validar_comportamientos(db, starters, substitutes):
    todos = starters + substitutes
    behavior_ids = [s.behavior_id for s in todos]

    comportamientos_validos = db.scalars(
        select(Behavior).where(Behavior.id.in_(behavior_ids))
    ).all()

    comportamientos_validos_ids = {b.id for b in comportamientos_validos}

    comportamientos_invalidos = set(behavior_ids) - comportamientos_validos_ids

    if comportamientos_invalidos:
        primer_invalido = next(iter(comportamientos_invalidos))
        raise ComportamientoInvalido(str(primer_invalido))

    return comportamientos_validos


def _generar_codigo_unico(db: Session) -> str:
    for _ in range(10):
        codigo = secrets.token_hex(4) # Genera un código hexadecimal de 8 caracteres para la liga.
        existe = db.scalar(select(Room).where(Room.code == codigo))
        # Si no existe ninguna liga con ese codigo, lo devolvemos.
        if existe is None:
            return codigo

    raise RuntimeError("No se pudo generar un código único para la liga.")
