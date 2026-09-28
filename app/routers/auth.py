from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db

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
    return create_user_with_club(db, data)