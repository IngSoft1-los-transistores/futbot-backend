from fastapi.testclient import TestClient

# Origen del frontend, tal como lo declara el .env.example.
ORIGEN_FRONTEND = "http://localhost:5173"

"""Tests del endpoint de salud y del formato de error del contrato."""

def test_health_responde_ok_con_la_base_conectada(client: TestClient) -> None:
    """`GET /api/health` confirma que la API responde y la base contesta.
    """
    respuesta = client.get("/api/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok", "database_connected": True}


def test_health_no_requiere_autenticacion(client: TestClient) -> None:
    """El chequeo de salud es publico.
    """
    assert client.get("/api/health").status_code == 200


def test_el_origen_del_frontend_recibe_la_cabecera_cors(client: TestClient) -> None:
    """Una peticion desde el frontend recibe permiso de CORS.
    """
    respuesta = client.get("/api/health", headers={"Origin": ORIGEN_FRONTEND})

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_FRONTEND


def test_el_preflight_permite_el_header_de_autorizacion(client: TestClient) -> None:
    """El preflight habilita `Authorization`, que llevara el JWT.
    """
    respuesta = client.options(
        "/api/health",
        headers={
            "Origin": ORIGEN_FRONTEND,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_FRONTEND


def test_los_errores_usan_el_formato_unico_del_contrato(client: TestClient) -> None:
    """Todo error trae `detail` y `error_code`, como exige el contrato.
    """
    respuesta = client.get("/api/ruta-que-no-existe")

    assert respuesta.status_code == 404

    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "NOT_FOUND"
    assert isinstance(cuerpo["detail"], str)

    assert "errorCode" not in cuerpo