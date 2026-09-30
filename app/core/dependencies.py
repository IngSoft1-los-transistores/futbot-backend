from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

security = HTTPBearer()

class UserMock(BaseModel):
    id: str
    club_id: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserMock:
    """
    Mock de autenticacion.
    Borrar en merge.
    """

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticacion faltante o invalido"
        )

    return UserMock(
        id="usr-mock-1234",
        club_id="club-mock-5678"
    )