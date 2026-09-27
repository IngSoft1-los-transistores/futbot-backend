from fastapi import HTTPException, status

from app.models.club import Club

"""Shared FastAPI dependencies."""


def get_current_club() -> Club:
    """Returns the club identified by the request's Bearer token.

    Placeholder until the login ticket (SCRUM-58) implements JWT
    verification: it replaces this body keeping the name and the `Club`
    return type, so routers that depend on it need no changes.

    It fails closed on purpose: while there is no real verification, every
    request is rejected with 401. It must never return a fixed club, or any
    anonymous caller would act as that club. Tests authenticate by
    overriding this dependency (`app.dependency_overrides`).
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "detail": "Token inválido o ausente",
            "error_code": "INVALID_TOKEN",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
