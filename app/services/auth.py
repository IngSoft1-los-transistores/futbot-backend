"""Autenticacion de cuentas existentes."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginResponse


class InvalidCredentialsError(Exception):
    pass


class MissingClubError(Exception):
    pass


def login(db: Session, email: str, password: str) -> LoginResponse:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    if user.club is None:
        raise MissingClubError
    return LoginResponse(accessToken=create_access_token(user.id), clubId=user.club.id)
