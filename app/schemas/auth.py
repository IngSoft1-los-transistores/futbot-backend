"""Entrada y salida del inicio de sesion segun el contrato."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, SecretStr


class LoginRequest(BaseModel):
    email: str
    password: SecretStr


class LoginResponse(BaseModel):
    accessToken: str
    tokenType: Literal["bearer"] = "bearer"
    clubId: UUID
