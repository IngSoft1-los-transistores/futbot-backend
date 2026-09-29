import pytest
from app.schemas.coord import Coord
from app.engine.primitives import MatchEngine
from app.behaviors.executor import ejecutar_comportamiento
from app.behaviors.loader import _cache


@pytest.fixture
def integration_setup():
    """Estado estático de simulación simulando un ciclo/tick del motor de juego."""
    players_data = {
        "p1": {
            "position": Coord(x=10.0, y=10.0),
            "club_id": "CLUB_A",
            "is_on_field": True,
            "own_goal": Coord(x=0.0, y=30.0),
            "enemy_goal": Coord(x=100.0, y=30.0),
            "speed": 5.0,
            "power": 70.0,
            "behavior_id": "beh_delantero_test",
        },
        "aliado_1": {
            "position": Coord(x=20.0, y=10.0),
            "club_id": "CLUB_A",
            "is_on_field": True,
        },
    }
    ball_pos = Coord(x=10.5, y=10.0)  # Balón cerca de p1
    engine = MatchEngine(players_data, ball_pos)
    engine._ball_possessor_id = "p1"  # Le asignamos la posesión inicial
    return engine


def test_integracion_executor_y_comportamiento_ofensivo(integration_setup):
    engine = integration_setup

    # Simular la función de comportamiento de un jugador (p1 pateará al arco si tiene la pelota)
    def script_delantero(player):
        if player.tengo_pelota():
            arco = player.encontrar_arco_enemigo()
            player.patear_pelota(arco)

    # Inyectamos dinámicamente el comportamiento en el loader/cache para la prueba
    _cache["beh_delantero_test"] = script_delantero

    # Ejecutamos el ciclo del motor mediante el executor de tu compañero
    ejecutar_comportamiento("p1", engine)

    # Verificamos que la primitiva 'patear_pelota' resolvió correctamente en la física de MatchEngine
    assert engine.ball_position() == Coord(x=100.0, y=30.0)
    assert engine.player_has_ball("p1") is False


def test_integracion_executor_movimiento_sin_pelota(integration_setup):
    engine = integration_setup
    engine._ball_possessor_id = None  # Nadie tiene la pelota

    # Simular comportamiento defensivo (correr hacia la pelota si no la tiene)
    def script_correr_a_pelota(player):
        if not player.tengo_pelota():
            pelota = player.encontrar_pelota()
            player.correr(pelota)

    _cache["beh_delantero_test"] = script_correr_a_pelota

    # Ejecutamos el comportamiento
    ejecutar_comportamiento("p1", engine)

    # p1 estaba en (10,10) y la pelota en (10.5, 10). Al estar a distancia 0.5 (< speed 5.0), llega exacto.
    assert engine.player_position("p1") == Coord(x=10.5, y=10.0)