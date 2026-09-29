from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.config import settings
from app.db.init_db import cargar_comportamientos_por_defecto, crear_tablas
from app.db.session import SessionLocal, engine
from app.routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepara la base antes de aceptar el primer request."""
    crear_tablas(engine)

    db = SessionLocal()
    try:
        cargar_comportamientos_por_defecto(db)
    finally:
        db.close()

    yield


app = FastAPI(title="FutBot API", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def manejar_error_http(request: Request, error: HTTPException) -> JSONResponse:
    try:
        error_code = HTTPStatus(error.status_code).name
    except ValueError:
        error_code = "HTTP_ERROR"
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail, "error_code": error_code},
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def manejar_error_validacion(request: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(error.errors()), "error_code": "VALIDATION_ERROR"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
