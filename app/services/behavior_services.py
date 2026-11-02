from fastapi import HTTPException, status

from sqlalchemy.orm import Session
from sqlalchemy import or_, not_

from app.models.behavior import Behavior
from app.models.squad_entry import SquadEntry
from app.models.room import Room, ROOM_STATUS_CANCELLED, ROOM_STATUS_FINISHED
from app.db.base import ahora_utc

def get_all_behavior(db: Session, club_id: str):
    return db.query(Behavior).filter(
        or_(
            Behavior.club_id == club_id,
            Behavior.club_id == None
        )
    ).all()

def erase_behavior_from_club(db: Session, club_id: str, behavior_id: str):
    
    # Buscamos el comportamiento por id
    behavior = db.query(Behavior).filter(
        Behavior.id == behavior_id,
        Behavior.deleted_at == None
        ).first()

    # Validacion de existencia y pertenencia al club
    if not behavior:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El comportamiento no existe."
        )

    if behavior.club_id != club_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar este comportamiento."
        )

    # Verificacion de uso
    in_use = (
        db.query(SquadEntry)
        .join(Room, SquadEntry.room_id == Room.id)
        .filter(
            SquadEntry.behavior_id == behavior_id,
            not_(Room.status.in_([ROOM_STATUS_FINISHED, ROOM_STATUS_CANCELLED]))
        )
        .first()
    )

    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede eliminar un comportamiento asignado en alguna plantilla: primero hay que reemplazarlo"
        )

    # Borrado
    behavior.deleted_at = ahora_utc()
    db.commit()
    return True

