import pytest
from app.schemas.coord import Coord
from app.engine.primitives import MatchEngine, PlayerState, HALF_WIDTH, HALF_HEIGHT


@pytest.fixture
def match_setup():
    """Estado estático del juego con PlayerState y PACSS reales."""
    players_data = {
        "p1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=0.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=100,  # Avanza ~0.6 por tick
            power=100,  # Balón avanza ~1.67 por tick
            control=100,
            is_on_field=True,
            behavior_id="beh_01",
        ),
        "aliado_1": PlayerState(
            club_id="CLUB_A",
            position=Coord(x=5.0, y=0.0),
            own_goal=Coord(x=-50.0, y=0.0),
            enemy_goal=Coord(x=50.0, y=0.0),
            speed=60,
            power=60,
            control=60,
            is_on_field=True,
            behavior_id="beh_02",
        ),
        "enemigo_1": PlayerState(
            club_id="CLUB_B",
            position=Coord(x=10.0, y=0.0),
            own_goal=Coord(x=50.0, y=0.0),
            enemy_goal=Coord(x=-50.0, y=0.0),
            speed=60,
            power=60,
            control=60,
            is_on_field=True,
            behavior_id="beh_03",
        ),
    }
    ball_pos = Coord(x=0.5, y=0.0)  # Cerca de p1 (dentro de su radio de control)
    engine = MatchEngine(players_data, ball_pos)
    return engine


def test_consultas_posiciones_y_arcos(match_setup):
    engine = match_setup
    assert engine.ball_position() == Coord(x=0.5, y=0.0)
    assert engine.player_position("p1") == Coord(x=0.0, y=0.0)
    assert engine.own_goal_position("p1") == Coord(x=-50.0, y=0.0)
    assert engine.opponent_goal_position("p1") == Coord(x=50.0, y=0.0)


def test_busqueda_aliados_y_enemigos(match_setup):
    engine = match_setup
    assert engine.nearest_teammate_position("p1") == Coord(x=5.0, y=0.0)
    assert engine.nearest_opponent_position("p1") == Coord(x=10.0, y=0.0)


def test_posesion_individual_y_de_equipo_con_companero(match_setup):
    engine = match_setup

    # p1 está cerca del balón al inicio
    assert engine.player_has_ball("p1") is True
    assert engine.team_has_ball("p1") is True

    # Movemos la pelota al radio de control de aliado_1
    engine._ball_pos = Coord(x=5.2, y=0.0)
    engine._update_possession_state()

    # Ahora p1 NO tiene la pelota individualmente, pero su EQUIPO SÍ la tiene
    assert engine.player_has_ball("p1") is False
    assert engine.player_has_ball("aliado_1") is True
    assert engine.team_has_ball("p1") is True

    # Si la tiene el rival
    engine._ball_pos = Coord(x=10.1, y=0.0)
    engine._update_possession_state()
    assert engine.team_has_ball("p1") is False


def test_movimiento_desplazamiento_fisico_por_tick(match_setup):
    engine = match_setup
    # p1 tiene speed=100 (~0.6 unidades por tick). Intenta ir a (10.0, 0.0)
    engine.apply_movement("p1", Coord(x=10.0, y=0.0))

    pos = engine.player_position("p1")
    assert pos.x < 10.0  # No se teletransporta
    assert pytest.approx(pos.x, abs=0.05) == 0.6  # Avanzó el paso máximo de 1 tick


def test_pase_y_remate_desplazamiento_gradual_del_balon(match_setup):
    engine = match_setup

    # Remate al arco rival en (50.0, 0.0)
    engine.apply_shot("p1", Coord(x=50.0, y=0.0))
    ball_pos = engine.ball_position()

    # El balón no llega inmediatamente al arco en 1 tick
    assert ball_pos.x < 50.0
    assert ball_pos.x > 0.5


def test_limite_de_cancha_centro_en_cero(match_setup):
    engine = match_setup

    assert engine.is_inside_field(Coord(x=0.0, y=0.0)) is True
    assert engine.is_inside_field(Coord(x=-50.0, y=-30.0)) is True
    assert engine.is_inside_field(Coord(x=50.0, y=30.0)) is True

    # Fuera del límite centrado en (0,0)
    assert engine.is_inside_field(Coord(x=-55.0, y=0.0)) is False
    assert engine.is_inside_field(Coord(x=55.0, y=0.0)) is False
    assert engine.is_inside_field(Coord(x=0.0, y=35.0)) is False

def test_disputa_de_pelota_gana_el_mas_cercano(match_setup):
    engine = match_setup
    # Colocamos a p1 en (0,0) y a aliado_1 en (0.8, 0). Pelota en (1.0, 0)
    # Aunque p1 está primero en el dict, aliado_1 está a dist 0.2 (más cerca) y p1 a 1.0.
    engine._players["p1"].position = Coord(x=0.0, y=0.0)
    engine._players["aliado_1"].position = Coord(x=0.8, y=0.0)
    engine._ball_pos = Coord(x=1.0, y=0.0)
    
    engine._update_possession_state()
    
    assert engine.player_has_ball("aliado_1") is True
    assert engine.player_has_ball("p1") is False


def test_conduccion_jugador_corre_con_la_pelota(match_setup):
    engine = match_setup
    # p1 tiene la pelota al inicio en (0,0) y pelota en (0.5, 0)
    assert engine.player_has_ball("p1") is True

    # Corre hacia (10, 0)
    engine.apply_movement("p1", Coord(x=10.0, y=0.0))

    # La pelota debió trasladarse junto al jugador
    assert engine.ball_position() == engine.player_position("p1")
    assert engine.player_has_ball("p1") is True


def test_remate_libera_posesion_y_avanza_en_ticks(match_setup):
    engine = match_setup
    assert engine.player_has_ball("p1") is True

    # Patear al arco
    engine.apply_shot("p1", Coord(x=50.0, y=0.0))

    # Inmediatamente pierde la posesión
    assert engine.player_has_ball("p1") is False

    pos_inicial = engine.ball_position().x

    # Simulamos el avance de la pelota en los ticks subsiguientes
    engine.advance_ball()
    pos_tick2 = engine.ball_position().x

    assert pos_tick2 > pos_inicial
    assert pos_tick2 < 50.0