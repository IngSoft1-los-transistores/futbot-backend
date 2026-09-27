"""Endpoint publico de inicio de sesion."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import InvalidCredentialsError, MissingClubError, login

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login_endpoint(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        return login(db, payload.email, payload.password.get_secret_value())
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
        
        
    #posiblemente innecesario, ya que para registrarse el usuario esta obligado a crear un club para asociarse, pero queda por si se rompe algo
        
    except MissingClubError as error:                                               
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta no tiene un club asociado",
        ) from error
