import math
from dataclasses import dataclass
from typing import Dict, Optional, List

from app.schemas.coord import Coord

# Dimensiones oficiales del campo (Centrado en (0,0))
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0
HALF_WIDTH = FIELD_WIDTH / 2.0 # 50.0
HALF_HEIGHT = FIELD_HEIGHT / 2.0 # 30.0

# Constantes para mapeo de PACSS (20 a 100)
PACSS_MINIMO = 20
PACSS_MAXIMO = 100

PLAYER_MIN_SPEED = 4.0 # unidades por segundo a speed=20
PLAYER_MAX_SPEED = 9.0 # unidades por segundo a speed=100

BALL_MIN_POWER = 10.0 # unidades por segundo a power=20
BALL_MAX_POWER = 25.0 # unidades por segundo a power=100

TICKS_PER_SECOND = 15.0 # Frecuencia simulada

@dataclass(slots=True)
class PlayerState:
    club_id: str
    position: Coord
    own_goal: Coord
    enemy_goal: Coord
    speed: int
    power: int
    control: int
    is_on_field: bool
    behavior_id: str


class MatchEngine:
    """
    Modulo de simulacion en memoria para resolucion de primitivas.
    """
    def __init__(self, players_data: Dict[str, PlayerState], ball_pos: Coord):
        self._players = players_data
        self._ball_pos = ball_pos
        self._ball_possessor_id: Optional[str] = None
        self._errors: Dict[str, List[str]] = {}
        self._update_possession_state()

    
    def _distance(self, c1:Coord, c2:Coord) -> float:
        """Funcion auxiliar para calcular distancia euclidiana"""
        return math.hypot(c1.x - c2.x, c1.y - c2.y)

    
    def _max_step_speed(self, speed_stat: int) -> float:
        """
        Convierte la nota de speed (20-100) a distancia maxima alcanzable en 1 tick.
        """
        clamped_speed = max(PACSS_MINIMO, min(PACSS_MAXIMO, speed_stat))
        ratio = (clamped_speed - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)
        per_second = PLAYER_MIN_SPEED + ratio * (PLAYER_MAX_SPEED - PLAYER_MIN_SPEED)
        return per_second / TICKS_PER_SECOND

    
    def _max_step_power(self, power_stat: int, pass_ratio: float = 1.0) -> float:
        """
        Convierte la nota de power (20-100) a la velocidad/desplazamiento del balon en 1 tick.
        """
        clamped_power = max(PACSS_MINIMO, min(PACSS_MAXIMO, power_stat))
        ratio = (clamped_power - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)
        per_second = BALL_MIN_POWER + ratio * (BALL_MAX_POWER - BALL_MIN_POWER)
        return (per_second * pass_ratio) / TICKS_PER_SECOND

    
    def _update_possession_state(self) -> None:
        """
        Asigna la posesion al jugador mas cercano dentro de su radio de control.
        """
        for p_id, player in self._players.items():
            if player.is_on_field:
                # El atributo control (20-100) se traduce a un radio de control
                control_radius = 1.0 + ((player.control - PACSS_MINIMO) / (PACSS_MAXIMO - PACSS_MINIMO)) * 2.0
                if self._distance(player.position, self._ball_pos) <= control_radius:
                    self._ball_possessor_id = p_id
                    return
        self._ball_possessor_id = None



    #--------------Acciones------------------
    
    def apply_pass(self, player_id: str,target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de limites de pase")
            return

        player = self._players[player_id]
        max_ball_step = self._max_step_power(player.power, pass_ratio=0.7) # pase proporcional 70%

        dist = self._distance(self._ball_pos, target)
        if dist > max_ball_step and dist > 0:
            ratio = max_ball_step / dist
            new_x = self._ball_pos.x + (target.x - self._ball_pos.x) * ratio
            new_y = self._ball_pos.y + (target.y - self._ball_pos.y) * ratio
            self._ball_pos = Coord(x=new_x, y=new_y)
        else:
            self._ball_pos = target

        self._ball_possessor_id = None
        self._update_possession_state()

    
    def apply_shot(self, player_id: str, target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de límites para tiro")
            return

        player = self._players[player_id]
        max_ball_step = self._max_step_power(player.power, pass_ratio=1.0)  # Máxima potencia

        dist = self._distance(self._ball_pos, target)
        if dist > max_ball_step and dist > 0:
            ratio = max_ball_step / dist
            new_x = self._ball_pos.x + (target.x - self._ball_pos.x) * ratio
            new_y = self._ball_pos.y + (target.y - self._ball_pos.y) * ratio
            self._ball_pos = Coord(x=new_x, y=new_y)
        else:
            self._ball_pos = target

        self._ball_possessor_id = None
        self._update_possession_state()

    
    def apply_movement(self, player_id: str, target: Coord) -> None:
        if not self.is_inside_field(target):
            self.register_error(player_id, "Coordenada fuera de límites para movimiento")
            return

        player = self._players[player_id]
        max_step = self._max_step_speed(player.speed)
        dist = self._distance(player.position, target)

        if dist > max_step and dist > 0:
            ratio = max_step / dist
            new_x = player.position.x + (target.x - player.position.x) * ratio
            new_y = player.position.y + (target.y - player.position.y) * ratio
            player.position = Coord(x=new_x, y=new_y)
        else:
            player.position = target

        self._update_possession_state()


    #-------------------Consultas----------------------------


    def ball_position(self) -> Coord:
        """
        Devuelve coordenadas en tiempo real de la pelota.
        """
        return self._ball_pos

    
    def nearest_teammate_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de aliado mas cercano al jugador excluyendose a si mismo.
        """
        me = self._players[player_id]

        allies = [
            p for p_id, p in self._players.items()
            if p_id != player_id
            and p.club_id == me.club_id
            and p.is_on_field
        ]
        if not allies:
            return me.position

        closest_ally = min(allies, key=lambda p: self._distance(me.position, p.position)
        )
        return closest_ally.position

    
    def nearest_opponent_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de enemigo mas cercano al jugador.
        """
        me = self._players[player_id]
    
        enemies = [
            p for p in self._players.values()
            if p.club_id != me.club_id
            and p.is_on_field
        ]
        if not enemies:
            return me.position

        closest_enemy = min(enemies, key=lambda p: self._distance(me.position, p.position)
        )
        return closest_enemy.position

    def own_goal_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de arco aliado.
        """
        return self._players[player_id].own_goal
    
    
    def opponent_goal_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas de arco enemigo.
        """
        return self._players[player_id].enemy_goal

    
    def player_position(self, player_id: str) -> Coord:
        """
        Devuelve coordenadas del jugador.
        """
        return self._players[player_id].position
    

    def player_has_ball(self, player_id: str) -> bool:
        """
        Devuelve True si el jugador es poseedor de la pelota.
        """
        return self._ball_possessor_id == player_id
    
        
    def team_has_ball(self, player_id: str) -> bool:
        """
        Devuelve True si equipo del jugador posee la pelota.
        """
        if self._ball_possessor_id is None:
            return False

        my_club = self._players[player_id].club_id
        possessor_club = self._players[self._ball_possessor_id].club_id
        return my_club == possessor_club

#-------------------------Precondiciones y metadatos-----------------------

    def is_inside_field(self, coord:Coord) -> bool:
        return -HALF_WIDTH <= coord.x <= HALF_WIDTH and -HALF_HEIGHT <= coord.y <= HALF_HEIGHT


    def player_is_on_field(self, player_id: str) -> bool:
        return self._players[player_id].is_on_field

    def assigned_behavior(self, player_id: str) -> str:
        return self._players[player_id].behavior_id

    def register_error(self, player_id: str, message: str) -> None:
        if player_id not in self._errors:
            self._errors[player_id] = []
        self._errors[player_id].append(message)