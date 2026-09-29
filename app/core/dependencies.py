from fastapi import Header, HTTPException, status
from pydantic import BaseModel

class UserMock(BaseModel):
    id: str
    club_id: str

async def get_current_user(authorization: str = Header(None)) -> UserMock:
    """
    Mock de autenticacion.
    Borrar en merge.
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacion faltante o invalido"
        )

    return UserMock(
        id="usr-mock-1234",
        club_id="club-mock-5678"
    )