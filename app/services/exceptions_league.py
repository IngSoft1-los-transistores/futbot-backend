from app.models.room import MAX_LEAGUE_CLUBS, MIN_LEAGUE_CLUBS
from app.services.exceptions_player import AppException


# Ticket: [BE] Create League
# Ya existe una liga con ese nombre (sin distinguir mayúsculas).
class DuplicateLeagueName(AppException):
    def __init__(self, name: str):
        self.name = name

        super().__init__(
            message=f"A league named '{name}' already exists. Choose another name.",
            code="DUPLICATE_LEAGUE_NAME",
        )

# El mínimo de clubes es menor al permitido (3).
class MinClubsTooLow(AppException):
    def __init__(self, min_clubs: int):
        self.min_clubs = min_clubs
        self.min = MIN_LEAGUE_CLUBS

        super().__init__(
            message=f"A league must have at least {self.min} clubs.",
            code="MIN_CLUBS_TOO_LOW",
        )

# El máximo de clubes supera el permitido (30).
class MaxClubsTooHigh(AppException):
    def __init__(self, max_clubs: int):
        self.max_clubs = max_clubs
        self.max = MAX_LEAGUE_CLUBS

        super().__init__(
            message=f"A league can have at most {self.max} clubs.",
            code="MAX_CLUBS_TOO_HIGH",
        )

# El máximo de clubes es menor que el mínimo.
class MaxClubsBelowMin(AppException):
    def __init__(self, max_clubs: int, min_clubs: int):
        self.max_clubs = max_clubs
        self.min_clubs = min_clubs

        super().__init__(
            message="The maximum number of clubs cannot be lower than the minimum.",
            code="MAX_CLUBS_BELOW_MIN",
        )

# El mismo jugador aparece más de una vez en la escuadra.
class DuplicatePlayer(AppException):
    def __init__(self, player_name: str):
        self.player_name = player_name

        super().__init__(
            message=f"Player '{player_name}' cannot appear more than once in the squad.",
            code="DUPLICATE_PLAYER",
        )

# No hay un jugador con ese nombre en el club creador.
class PlayerNotFound(AppException):
    def __init__(self, player_name: str):
        self.player_name = player_name

        super().__init__(
            message=f"Player '{player_name}' does not exist in your club.",
            code="PLAYER_NOT_FOUND",
        )

# El comportamiento asignado no existe.
class InvalidBehavior(AppException):
    def __init__(self, behavior_id: str):
        self.behavior_id = behavior_id

        super().__init__(
            message=f"Behavior with id:{behavior_id} is invalid.",
            code="INVALID_BEHAVIOR",
        )

# La contraseña de una liga privada es inválida (falta, es corta o tiene espacios).
class InvalidLeaguePassword(AppException):
    def __init__(self, reason: str):
        self.reason = reason

        super().__init__(
            message=f"Invalid league password: {reason}.",
            code="INVALID_LEAGUE_PASSWORD",
        )

# Una liga pública no puede tener contraseña.
class PasswordNotAllowedOnPublicLeague(AppException):
    def __init__(self):
        super().__init__(
            message="A public league cannot have a password.",
            code="PASSWORD_NOT_ALLOWED_ON_PUBLIC_LEAGUE",
        )
