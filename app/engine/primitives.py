import math
from typing import Dict, Optional

from app.behaviors.interfaces import IMatchEngine
from app.schemas.coord import Coord

# Field dimensions
# Placeholder for testing purposes
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0


class MatchEngine(IMatchEngine):
    """
    Modulo de resolución de primitivas.
    Cumple con la interfaz IMatchEngine requerida por el modulo de comportamientos
    """
    def __init__(self, players_data: Dict, ball_pos: Coord):
        self._players = players_data
        self._ball_pos = ball_pos
        self._ball_possessor_id: Optional[str] = None
        self._errors: Dict[str, list] = {}

    def _distance(self, c1:Coord, c2:Coord) -> float:
        """Funcion auxiliar para calcular distancia euclidiana"""
        return math.hypot(c1.x - c2.x, c1.y - c2.y)
    #--------------Acciones------------------
    
    def apply_pass(self, player_id: str,target: Coord) -> None:
        """Sends ball toward indicated coordinates with a force/speed proportional to player's 'power' attribute"""
        power = self._players[player_id]["power"]

        self._ball_possessor_id = None

        self._ball_pos = target
        
    def apply_shot(self, player_id: str, target: Coord) -> None:
        """Propels the ball with the maximum available power towards destination"""
        power = self._players[player_id]["power"]

        self._ball_possessor_id = None
        
        self._ball_pos = target

    def apply_movement(self, player_id: str, target: Coord) -> None:
        """Shifts player's coordinates toward the target, with a movement per tick determined by their 'speed' attribute"""
        player = self._players[player_id]
        current_pos = player["position"]
        max_speed = player["speed"]

        distance = self._distance(current_pos, target)

        if distance > max_speed and distance > 0:
            ratio = max_speed / distance
            new_x = current_pos.x + (target.x - current_pos.x) * ratio
            new_y = current_pos.y + (target.y - current_pos.y) * ratio
            player["position"] = Coord(x=new_x, y=new_y)
        else:
            player["position"] = target


    #-------------------Consultas----------------------------


    def ball_position(self) -> Coord:
        """Returns real time ball's coordinates"""
        return self._ball_pos

    def nearest_teammate_position(self, player_id: str) -> Coord:
        """Returns player's closest ally excluding itself and non playing allies"""
        me = self._players[player_id]
        my_pos = me["position"]

        allies = [
            p for p_id, p in self._players.items()
            if p_id != player_id
            and p["club_id"] == me["club_id"]
            and p.get("is_on_field", True)
        ]

        if not allies:
            return my_pos

        closest_ally = min(
            allies,
            key=lambda p: self._distance(my_pos, p["position"])
        )
        return closest_ally["position"]

    def nearest_opponent_position(self, player_id: str) -> Coord:
        """Returns closest enemy coordinates"""
        me = self._players[player_id]
        my_pos = me["position"]

        enemies = [
            p for p in self._players.values()
            if p["club_id"] != me["club_id"]
            and p.get("is_on_field", True)
        ]

        if not enemies:
            return my_pos

        closest_enemy = min(
            enemies,
            key=lambda p: self._distance(my_pos, p["position"])
        )
        return closest_enemy["position"]

    def own_goal_position(self, player_id: str) -> Coord:
        """Returns own goal coordinates"""
        return self._players[player_id]["own_goal"]

    def opponent_goal_position(self, player_id: str) -> Coord:
        """Returns enemies goal coordinates"""
        return self._players[player_id]["enemy_goal"]

    def player_position(self, player_id: str) -> Coord:
        """Returns player's coordinates"""
        return self._players[player_id]["position"]

    def player_has_ball(self, player_id: str) -> bool:
        """Returns true if ball is in player's control radius"""
        if self._ball_possessor_id == player_id:
            return True
        else:
            return False
        
    def team_has_ball(self, player_id: str) -> bool:
        """Returns true if player's club is in control of the ball"""
        if self._ball_possessor_id is None:
            return False

        my_club = self._players[player_id]["club_id"]
        possessor_club = self._players[self._ball_possessor_id]["club_id"]
        return my_club == possessor_club

#-------------------------Precondiciones y metadatos-----------------------

    def is_inside_field(self, coord:Coord) -> bool:
        return 0.0 <= coord.x <= FIELD_WIDTH and 0.0 <= coord.y <= FIELD_HEIGHT

    def player_is_on_field(self, player_id: str) -> bool:
        return self._players[player_id].get("is_on_field", True)

    def assigned_behavior(self, player_id: str) -> str:
        return self._players[player_id].get("behavior_id", "")

    def register_error(self, player_id: str, message: str) -> None:
        if player_id not in self._errors:
            self._errors[player_id] = []
        self._errors[player_id].append(message)