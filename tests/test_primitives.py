import pytest
from app.schemas.coord import Coord
from app.engine.primitives import MatchEngine

@pytest.fixture
def match_setup():
    """Estado estatico del juego usando los esquemas reales del proyecto"""
    players_data = {
        "p1": {
            "position": Coord(x=10.0, y=10.0),
            "club_id": "CLUB_A",
            "is_on_field": True,
            "own_goal": Coord(x=0.0, y=30.0),
            "enemy_goal": Coord(x=100.0, y=30.0),
            "speed": 5.0,
            "power": 70.0,
            "control": 2.0,
            "behavior_id": "beh_01"
        },
        "aliado_cercano": {
            "position": Coord(x=14.0, y=13.0), 
            "club_id": "CLUB_A",
            "is_on_field": True,
            "speed": 4.0,
        },
        "enemigo_cercano": {
            "position": Coord(x=13.0, y=14.0), 
            "club_id": "CLUB_B",
            "is_on_field": True,
            "speed": 6.0,
        },
        "aliado_banca": {
            "position": Coord(x=11.0, y=10.0),
            "club_id": "CLUB_A",
            "is_on_field": False,
        }
    }
    ball_pos = Coord(x=10.5, y=10.0)

    engine = MatchEngine(players_data, ball_pos)
    engine._ball_possessor_id = "p1"
    return engine

# --- Tests de Consultas ---

def test_consultas_posiciones_y_arcos(match_setup):
    engine = match_setup
    assert engine.ball_position() == Coord(x=10.5, y=10.0)
    assert engine.player_position("p1") == Coord(x=10.0, y=10.0)
    assert engine.own_goal_position("p1") == Coord(x=0.0, y=30.0)
    assert engine.opponent_goal_position("p1") == Coord(x=100.0, y=30.0)


def test_busquedas_euclidianas_mas_cercanos(match_setup):
    engine = match_setup
    # Excluye al propio jugador y a jugadores fuera de la cancha
    assert engine.nearest_teammate_position("p1") == Coord(x=14.0, y=13.0)
    assert engine.nearest_opponent_position("p1") == Coord(x=13.0, y=14.0)


def test_evaluacion_de_posesion(match_setup):
    engine = match_setup
    assert engine.player_has_ball("p1") is True
    assert engine.team_has_ball("p1") is True
    assert engine.team_has_ball("enemigo_cercano") is False


# --- Tests de Acciones / Física ---

def test_correr_respetando_atributo_speed(match_setup):
    engine = match_setup
    # Intenta moverse a (30,10) [distancia 20], pero su speed máximo es 5
    engine.apply_movement("p1", Coord(x=30.0, y=10.0))
    assert engine.player_position("p1") == Coord(x=15.0, y=10.0)


def test_correr_dentro_del_rango_speed(match_setup):
    engine = match_setup
    # Moverse a (13,10) toma 3 unidades (menor a speed=5) -> Llega exacto
    engine.apply_movement("p1", Coord(x=13.0, y=10.0))
    assert engine.player_position("p1") == Coord(x=13.0, y=10.0)


def test_pasar_actualiza_posicion_pelota_y_libera_posesion(match_setup):
    engine = match_setup
    target = Coord(x=25.0, y=25.0)

    engine.apply_pass("p1", target)

    assert engine.ball_position() == target
    assert engine.player_has_ball("p1") is False


def test_patear_actualiza_posicion_pelota(match_setup):
    engine = match_setup
    target = Coord(x=100.0, y=30.0)

    engine.apply_shot("p1", target)

    assert engine.ball_position() == target
    assert engine.player_has_ball("p1") is False


def test_validaciones_de_limite_de_cancha(match_setup):
    engine = match_setup
    assert engine.is_inside_field(Coord(x=50.0, y=30.0)) is True
    assert engine.is_inside_field(Coord(x=-5.0, y=30.0)) is False
    assert engine.is_inside_field(Coord(x=105.0, y=30.0)) is False