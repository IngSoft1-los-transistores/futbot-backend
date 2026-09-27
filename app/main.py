from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
