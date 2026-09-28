from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.models.club import Club
from app.schemas.auth import UserRead, UserRegister
from app.services.auth_services import create_user_with_club

router = APIRouter(prefix="/api/auth", tags=["register"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    data: UserRegister,
    db: Session = Depends(get_db),
) -> UserRead:
    """usuario_existente = db.scalar(
        select(User).where(
            or_(
                User.username == data.username,
                User.email == data.email,
            )
        )
    )
    club_existente = db.scalar(
        select(Club).where(Club.name == data.club_name)
    )

    if usuario_existente is not None or club_existente is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario, email o nombre del club ya existe",
        )

    usuario = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(usuario)

    try:
        db.flush()
        club = Club(
            name=data.club_name,
            avatar_url=data.avatar_url or "https://url-por-defecto.com/avatar.png",
            ranking_points=0,
            user_id=usuario.id,  # el ID del usuario al club
        )
        db.add(club)
        db.commit()
        db.refresh(usuario)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario, email o nombre del club ya existe",
        )
"""
    return create_user_with_club(db, data)