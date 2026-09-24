from pydantic import BaseModel

"""Esquemas del chequeo de salud de la API."""

class HealthRead(BaseModel):
    """Respuesta de `GET /api/health`.
    """

    status: str
    database_connected: bool