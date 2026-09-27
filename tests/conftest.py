"""Expone las fixtures existentes a todos los modulos de tests."""
import os

# Configuracion exclusiva de tests, antes de importar la aplicacion.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-key-not-for-production"

from tests.test_conf import client, club, db, engine  # noqa: E402, F401
