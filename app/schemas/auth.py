"""Entrada y salida del inicio de sesion segun el contrato."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, SecretStr


class LoginRequest(BaseModel):
    email: str
    password: SecretStr


class LoginResponse(BaseModel):
    expires_at: int
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    club_id: UUID


class CurrentUserResponse(BaseModel):
    user_id: UUID
    club_id: UUID


class RefreshRequest(BaseModel):
    refresh_token: SecretStr
