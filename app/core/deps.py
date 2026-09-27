from fastapi import HTTPException, status

from app.models.club import Club

"""Shared FastAPI dependencies."""


def get_current_club() -> Club:
    """Placeholder until login (SCRUM-58): rejects every request with 401."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "detail": "Token inválido o ausente",
            "error_code": "INVALID_TOKEN",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
