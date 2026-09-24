import ast
import logging
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
# Importar `app.models` registra las diez tablas en `Base.metadata`. Sin este
# import, `create_all()` no tendria nada que crear.
"""Creacion del schema y carga de los comportamientos preprogramados."""

import app.models  # noqa: F401
from app.db.base import Base
from app.models.behavior import Behavior

logger = logging.getLogger(__name__)

# Directorio donde viven los comportamientos por defecto del sistema.
DIRECTORIO_DEFAULTS = Path(__file__).resolve().parent.parent / "behaviors" / "defaults"


def crear_tablas(engine: Engine) -> None:
    """Crea las tablas que todavia no existen.
    `create_all()` **no es una migracion**: crea lo que falta y no toca lo que
    ya esta.
    """
    Base.metadata.create_all(bind=engine)


def _leer_comportamiento(archivo: Path) -> tuple[str, str, str | None]:
    """Extrae el nombre, el codigo y la descripcion de un archivo de defaults.
    La descripcion sale del docstring del modulo
    """
    codigo = archivo.read_text(encoding="utf-8")
    # `ast.parse` ademas valida la sintaxis: un default mal escrito hace fallar
    # el arranque con un error claro, en vez de guardarse roto en la base.
    descripcion = ast.get_docstring(ast.parse(codigo))
    return archivo.stem, codigo, descripcion


def cargar_comportamientos_por_defecto(db: Session) -> int:
    """Inserta o actualiza los comportamientos preprogramados del sistema.
    Devuelve cuantos comportamientos quedaron cargados.
    """
    archivos = sorted(DIRECTORIO_DEFAULTS.glob("*.py"))

    for archivo in archivos:
        if archivo.name == "__init__.py":
            continue

        nombre, codigo, descripcion = _leer_comportamiento(archivo)

        existente = db.scalars(
            select(Behavior).where(
                Behavior.club_id.is_(None), Behavior.name == nombre
            )
        ).one_or_none()

        if existente is None:
            db.add(
                Behavior(
                    club_id=None,
                    name=nombre,
                    description=descripcion,
                    code=codigo,
                    is_preprogrammed=True,
                )
            )
            logger.info("Comportamiento por defecto cargado: %s", nombre)
        elif existente.code != codigo or existente.description != descripcion:
            # El archivo cambio desde el ultimo arranque: se actualiza la fila
            # en lugar de crear una segunda con el mismo nombre. Asi editar un
            # default en el repositorio se refleja al reiniciar.
            existente.code = codigo
            existente.description = descripcion
            logger.info("Comportamiento por defecto actualizado: %s", nombre)

    db.commit()
    # Se cuenta en la base y no con `len(archivos)`: lo que importa reportar es
    # cuantas filas quedaron realmente, que es lo que el test de idempotencia
    # verifica que no crezca entre arranques.
    return db.scalar(
        select(func.count()).select_from(Behavior).where(Behavior.club_id.is_(None))
    )