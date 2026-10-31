from sqlalchemy.orm import Session
from sqlalchemy import or_, select
from app.models.behavior import Behavior
from app.behaviors.validator import validate
from app.schemas.behaviors import BehaviorCreate

def get_all_behavior(db: Session, club_id: str):
    return db.query(Behavior).filter(
        or_(
            Behavior.club_id == club_id,
            Behavior.club_id == None
        )
    ).all()

def create_behavior(db: Session, data: BehaviorCreate, club_id: str):
    # Verificacion de si existe con comportamiento con el mismo nombre dentro del club
    existing_behavior = db.scalar(
        select(Behavior).where(
            Behavior.club_id == club_id,
            Behavior.name == data.name,
            Behavior.deleted_at.is_(None),
        )
    )

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
    except Exception as e:
        db.rollback()
        raise e
    