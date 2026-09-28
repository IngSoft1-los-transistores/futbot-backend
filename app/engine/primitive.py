import math
from dataclasses import dataclass
from typing import NamedTuple, Optional, Tuple

# Field dimensions
# Placeholder for testing purposes
FIELD_WIDTH = 100.0
FIELD_HEIGHT = 60.0

class Coord(NamedTuple):
    x: float
    y: float

    def distance_to(self, other: "Coord") -> float:
        """Calculates euclidean distance between two points"""
        return math.hypot(self.x - other.x, self.y - other.y)

    def is_within_bounds(self) -> bool:
        """Returns True if coordinates are within bounds of the playing field"""
        return 0.0 <= self.x <= FIELD_WIDTH and 0.0 <= self.y <= FIELD_HEIGHT

    def clamp_to_bounds(self) -> "Coord":
        """Clamps coordinates inside playing field bounds"""
        clamped_x = max(0.0, min(self.x, FIELD_WIDTH))
        clamped_y = max(0.0, min(self.y, FIELD_HEIGHT))
        return Coord(clamped_x, clamped_y)

@dataclass(frozen=True)
class PACSSattributes:
    power: float    #Kick strength
    agility: float  #Kick cooldown
    control: float  #Ball control radius
    speed: float    #Player's max displacement per tic
    strength: float #Player's physical imposition in collisions

@dataclass(frozen=True)
class PlayerState:
    id: str
    position: Coord
    attributes: PACSSattributes
    is_on_field: bool

@dataclass(frozen=True)
class GameSnapshot:
    """Immutable global game state readable by player"""
    current_player: PlayerState
    ball_position: Coord
    ball_possessor_id: Optional[str]
    allies: Tuple[PlayerState, ...]
    enemies: Tuple[PlayerState, ...]
    own_goal: Coord
    enemy_goal: Coord

class ActionIntent:
    """Registers player's intent sent by player's script"""
    def __init__(self):
        self.type: Optional[str] = None
        self.target: Optional[Coord] = None
        self.power_applied: float = 0.0

    def set_action(self, action_type: str, target: Coord, power_applied: float = 0.0):
        #Validates and clamps coordinates before intent
        clamped_target = target.clamp_to_bounds()
        self.type = action_type
        self.target = clamped_target
        self.power_applied = power_applied

class PlayerContext:
    """Object that implements the 11 primitive functions within the player behavior execution environment"""
    def __init__(self, snapshot: GameSnapshot, intent: ActionIntent):
        self._snapshot = snapshot
        self._intent = intent
        self._me = snapshot.current_player

    def make_a_pass(self, target: Coord) -> None:
        """Sends ball toward indicated coordinates with a force/speed proportional to player's 'power' attribute"""
        if not isinstance(target, Coord):
            target = Coord(target[0], target[1])

        applied_power = self._me.attributes.power * 0.5
        self._intent.set_action("MAKE_A_PASS", target, power_applied=applied_power)

    def kick_ball(self, target: Coord) -> None:
        """Propels the ball with the maximum available power towards destination"""
        if not isinstance(target, Coord):
            target = Coord(target[0], target[1])
        
        applied_power = self._me.attributes.power
        self._intent.set_action("KICK_BALL", target, power_applied=applied_power)

    def run(self, target: Coord) -> None:
        """Shifts player's coordinates toward the target, with a movement per tick determined by their 'speed' attribute"""
        if not isinstance(target, Coord):
            target = Coord(target[0], target[1])

        clamped_target = target.clamp_to_bounds()
        current_pos = self._me.position
        distance = current_pos.distance_to(clamped_target)
        max_step = self._me.attributes.speed

        if distance > max_step and distance > 0:
            ratio = max_step /distance
            new_x = current_pos.x + (clamped_target.x - current_pos.x) * ratio
            new_y = current_pos.y + (clamped_target.y - current_pos.y) * ratio
            effective_target = Coord(new_x, new_y)
        else:
            effective_target = clamped_target

        self._intent.set_action("RUN", effective_target)

    def find_ball(self) -> Coord:
        """Returns real time ball's coordinates"""
        return self._snapshot.ball_position

    def find_ally(self) -> Optional[Coord]:
        """Returns player's closest ally excluding itself and non playing allies"""
        active_allies = [
            p for p in self._snapshot.allies
            if p.is_on_field and p.id != self._me.id
        ]
        #Placeholder check for testing
        if not active_allies:
            return None

        my_pos = self._me.position
        closest = min(active_allies, key=lambda p: my_pos.distance_to(p.position))
        return closest.position

    def find_enemy(self) -> Optional[Coord]:
        """Returns closest enemy coordinates"""
        active_enemies = [
            p for p in self._snapshot.enemies
            if p.is_on_field
        ]
        #Placeholder check for testing
        if not active_enemies:
            return None

        my_pos = self._me.position
        closest = min(active_enemies, key=lambda p: my_pos.distance_to(p.position))
        return closest.position

    def find_own_goal(self) -> Coord:
        """Returns own goal coordinates"""
        return self._snapshot.own_goal

    def find_enemy_goal(self) -> Coord:
        """Returns enemies goal coordinates"""
        return self._snapshot.enemy_goal

    def find_my_coordinates(self) -> Coord:
        """Returns player's coordinates"""
        return self._me.position

    def has_ball(self) -> bool:
        """Returns true if ball is in player's control radius"""
        possesses = False
        if self._snapshot.ball_possessor_id == self._me.id:
            possesses = True
        return possesses

    def club_has_ball(self) -> bool:
        """Returns true if player's club is in control of the ball"""
        if self._snapshot.ball_possessor_id is None:
            return False
        if self.has_ball():
            return True

        ally_ids = {p.id for p in self._snapshot.allies if p.is_on_field}
        return self._snapshot.ball_possessor_id in ally_ids
