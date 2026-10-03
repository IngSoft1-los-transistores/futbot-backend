from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.behaviors.loader import precargar_preprogramados
from app.core.config import settings
from app.db.init_db import cargar_comportamientos_por_defecto, crear_tablas
from app.db.session import SessionLocal, engine
from app.routers import health, auth, behaviors, friendly_rooms

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara la base antes de aceptar el primer request."""
    crear_tablas(engine)

    db = SessionLocal()
    try:
        cargar_comportamientos_por_defecto(db)
        precargar_preprogramados(db)
    finally:
        db.close()

    yield


app = FastAPI(title="FutBot API", lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return JSONResponse(
        status_code=error.status_code,
        content={
            "detail": jsonable_encoder(error.detail),
            "error_code": error_codes.get(error.status_code, "HTTP_ERROR"),
        },
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(error.errors()),
            "error_code": "VALIDATION_ERROR",
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled application error")
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(friendly_rooms.router)
app.include_router(auth.router)
app.include_router(behaviors.router)
