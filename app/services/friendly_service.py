import random
import secrets
import string
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.room import (
    Room,
    ROOM_TYPE_FRIENDLY,
    ROOM_STATUS_WAITING_GUEST,
    ROOM_STATUS_READY_TO_START,
)

from app.models.enrollment import Enrollment
from app.models.squad_entry import (
    SquadEntry,
    ROLE_STARTER,
    ROLE_SUBSTITUTE,
)

from app.schemas.friendly_room import CreateFriendlyRoomRequest, FriendlyRoomResponse, RoomStatus, JoinFriendlyRoomRequest, JoinFriendlyRoomResponse
from app.services.squad_validator import validate_squad_selection

def generate_room_code(length: int = 6) -> str:
    """Genera un codigo alfanumerico unico para unirse a la sala de amistoso"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class FriendlyService:
    def __init__(self, db: Session):
        self.db = db

    def create_room(self, club_id: str, request: CreateFriendlyRoomRequest) -> FriendlyRoomResponse:

        # Validaciones de negocio
        validate_squad_selection(self.db, club_id, request.starters, request.substitutes)



        # Generacion de codigo unico de sala
        room_code = generate_room_code()
        while self.db.query(Room).filter(Room.code == room_code).first() is not None:
            room_code = generate_room_code()




        # Crear sala con estado waiting_guest
        new_room = Room(
            type=ROOM_TYPE_FRIENDLY,
            min_clubs=2,
            max_clubs=2,
            match_duration_minutes=10,
            status=ROOM_STATUS_WAITING_GUEST,
            creator_club_id=club_id,
            code=room_code
        )
        self.db.add(new_room)
        self.db.flush()




        # Registrar participacion del club creador de sala
        enrollment = Enrollment(
            room_id=new_room.id,
            club_id=club_id
        )
        self.db.add(enrollment)




        # Registrat los titulares y suplentes en SquadEntry
        for selection in request.starters:
            squad_entry = SquadEntry(
                room_id=new_room.id,
                player_id=selection.player_id,
                behavior_id=selection.behavior_id,
                role=ROLE_STARTER
            )
            self.db.add(squad_entry)

        for selection in request.substitutes:
            squad_entry = SquadEntry(
                room_id=new_room.id,
                player_id=selection.player_id,
                behavior_id=selection.behavior_id,
                role=ROLE_SUBSTITUTE                                
            )
            self.db.add(squad_entry)

        self.db.commit()

        return FriendlyRoomResponse(
            room_id=new_room.id,
            room_code=room_code,
            status=RoomStatus.WAITING_GUEST.value,
            home_club=club_id
        )
    
    def join_room(self, club_id: str, room_id: str, request: JoinFriendlyRoomRequest) -> JoinFriendlyRoomResponse:
        room = self.db.query(Room).filter(Room.id == room_id).first()

        valid_code = (
            room is not None
            and room.code is not None
            and secrets.compare_digest(room.code, request.code.strip().upper())
        )
        if not valid_code or room.type != ROOM_TYPE_FRIENDLY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sala no encontrada o codigo incorrecto"
            )

        if room.status != ROOM_STATUS_WAITING_GUEST:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La sala esta completa o fue iniciada."
                )

        validate_squad_selection(self.db, club_id, request.starters, request.substitutes)

        # Solo un invitado puede pasar de waiting_guest a ready_to_start
        reclaimed = (
            self.db.query(Room)
            .filter(Room.id == room.id, Room.status == ROOM_STATUS_WAITING_GUEST)
            .update({Room.status: ROOM_STATUS_READY_TO_START}, synchronize_session=False)
        )
        if reclaimed == 0:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La sala esta completa o fue iniciada."
                )

        self.db.add(Enrollment(room_id=room.id, club_id=club_id))
        for role, selections in (
            (ROLE_STARTER, request.starters),
            (ROLE_SUBSTITUTE, request.substitutes),
        ):
            for s in selections:
                self.db.add(SquadEntry(
                    room_id=room.id,
                    player_id=s.player_id,
                    behavior_id=s.behavior_id,
                    role=role,
                ))
        self.db.commit()

        return JoinFriendlyRoomResponse(
            room_id=room.id,
            status=RoomStatus.READY_TO_START.value,
            away_club=club_id,
        )