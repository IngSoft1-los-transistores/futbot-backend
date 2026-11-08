from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from app.models.behavior import Behavior
from app.behaviors.validator import validate
from app.schemas.behaviors import BehaviorCreate, BehaviorUpdate
from fastapi import HTTPException, status

def get_all_behavior(db: Session, club_id: str):
    return db.query(Behavior).filter(
        or_(
            Behavior.club_id == club_id,
            Behavior.club_id == None
        )
    ).all()

def existing_behavior_with_name(
        db: Session, 
        name: str, 
        club_id: str,
        exclude_behavior_id: str = None
):
    query = select(Behavior).where(
            Behavior.club_id == club_id,
            Behavior.name == name,
            Behavior.deleted_at.is_(None),
        )
    if exclude_behavior_id is not None:
        query = query.where(Behavior.id != exclude_behavior_id)

    return db.scalar(query)

def create_behavior(db: Session, data: BehaviorCreate, club_id: str):
    # Verificacion de si existe con comportamiento con el mismo nombre dentro del club
    existing_behavior = existing_behavior_with_name(db, data.name, club_id)

    if existing_behavior:
        raise ValueError(f"Ya existe un comportamiento con el nombre '{data.name}'")

    # Validar el código del comportamiento antes de persistirlo
    validate(data.code)
    
    try:
        new_behavior = Behavior(
            name=data.name, 
            code=data.code, 
            club_id=club_id,
            is_preprogrammed=False
        )
        db.add(new_behavior)
        db.commit()
        db.refresh(new_behavior)
        return new_behavior
    except Exception:
        db.rollback()
        raise

def get_behavior_by_id(db: Session, behavior_id: str, club_id: str):
    behavior = db.query(Behavior).filter(
        Behavior.club_id == club_id,
        Behavior.id == behavior_id,
        Behavior.deleted_at.is_(None)
    ).first()
    return behavior

def update_behavior(db: Session, behavior_id: str, data: BehaviorUpdate, club_id: str):
    behavior = get_behavior_by_id(db, behavior_id, club_id)
    if not behavior:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comportamiento inexistente"
        )

    existing_behavior = existing_behavior_with_name(db, data.name, club_id, behavior_id)
    if existing_behavior:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un comportamiento con el nombre '{data.name}'"
        )
    
    # Validar el código del comportamiento antes de actualizarlo
    validate(data.code)

    try:
        behavior.name = data.name
        behavior.code = data.code
        db.commit()
        db.refresh(behavior)
        return behavior
    except Exception:
        db.rollback()
        raise