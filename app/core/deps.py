from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.club import Club

"""Shared FastAPI dependencies."""

# auto_error=False so a missing header also gets the contract error shape.
bearer_scheme = HTTPBearer(auto_error=False)


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "detail": "Token inválido o ausente",
            "error_code": "INVALID_TOKEN",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_club(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Club:
    """Returns the club of the user in the token (`sub` = user id, as issued by login)."""
    if credentials is None:
        raise _invalid_token()

    settings = get_settings()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require_exp": True},
        )
    except JWTError as error:
        raise _invalid_token() from error

    user_id = claims.get("sub")
    if not isinstance(user_id, str):
        raise _invalid_token()

    club = db.scalar(select(Club).where(Club.user_id == user_id))
    if club is None:
        raise _invalid_token()
    return club
