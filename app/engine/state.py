from dataclasses import dataclass, field
from enum import Enum
import math

class Team(str, Enum):
    HOME = "home"
    AWAY = "away"

class MatchPhase(str, Enum):
    PRE = "pre"
    PLAY = "play"
    HYDRATION = "hydration"
    HALFTIME = "halftime"
    FINISHED = "finished"

@dataclass(frozen=True, slots=True) #vector 2D
class Vec2:
    x: float = 0.0
    y: float = 0.0

    #metodos especiales de suma, resta y multiplicacion
    def __add__(self, o: "Vec2") -> "Vec2": return Vec2(self.x + o.x, self.y + o.y)
    def __sub__(self, o: "Vec2") -> "Vec2": return Vec2(self.x - o.x, self.y - o.y)
    def __mul__(self, k: float) -> "Vec2": return Vec2(self.x * k, self.y * k)
    __rmul__ = __mul__
    
    def length(self) -> float: return math.hypot(self.x, self.y)
    
    def normalized(self) -> "Vec2":
        n = self.length()
        return Vec2(0.0, 0.0) if n == 0 else Vec2(self.x / n, self.y / n)
    
    #limita el tamaño maximo del vector, si es mayor lo escala a max_len
    def clamp_length(self, max_len: float) -> "Vec2":
        n = self.length()
        return self if n <= max_len else self * (max_len / n)

@dataclass(frozen=True, slots=True)
class GoalEvent:
    team: Team                 # equipo que suma el punto
    player_id: str | None      # autor; None si es gol en contra o no hay autor claro
    second: int                # segundo de juego (sin contar pausas)

@dataclass
class PlayerState:
    slots = True
    id: str 
    team: Team
    pos: Vec2
    speed: float
    control: float
    strength: float
    power: float
    agility: float
    vel: Vec2 = field(default_factory=Vec2)

@dataclass(slots=True)
class BallState:
    pos: Vec2
    vel: Vec2 = field(default_factory=Vec2)
    owner_id: int | None = None   # quién la controla, None si está libre
    last_kicker_id: str | None = None
    cooldown_ticks: int = 0  
    
@dataclass(slots=True)
class MatchState:
    players: list[PlayerState]
    ball: BallState
    score: dict[Team, int] = field(
        default_factory=lambda: {Team.HOME: 0, Team.AWAY: 0}
    )
    phase: MatchPhase = MatchPhase.PRE
    period: int = 0              # 1 a 4 (0 antes de empezar)
    tick_count: int = 0          # ticks totales del partido
    phase_tick: int = 0          # ticks transcurridos en la fase actual
    play_ticks: int = 0          # solo ticks de juego (para el reloj visible)
    goals: list[GoalEvent] = field(default_factory=list)
   

