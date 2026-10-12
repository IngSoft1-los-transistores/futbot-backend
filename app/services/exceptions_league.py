from app.services.exceptions_player import AppException


class LeagueNotFound(AppException):
    def __init__(self):
        super().__init__("La liga no existe", "LEAGUE_NOT_FOUND", status_code=404)


class LeagueNotOpen(AppException):
    def __init__(self):
        super().__init__("La liga ya no admite inscripciones", "LEAGUE_NOT_OPEN")


class WrongLeaguePassword(AppException):
    def __init__(self):
        super().__init__("La contraseña de la liga es incorrecta", "WRONG_LEAGUE_PASSWORD")


class AlreadyInLeague(AppException):
    def __init__(self):
        super().__init__("Tu club ya está inscripto en esta liga", "ALREADY_IN_LEAGUE")


class LeagueLimitReached(AppException):
    def __init__(self, limit: int):
        super().__init__(
            f"Ya estás participando en el máximo de {limit} ligas", "LEAGUE_LIMIT_REACHED"
        )


class LeagueFull(AppException):
    def __init__(self):
        super().__init__("La liga no tiene cupos disponibles", "LEAGUE_FULL")


# Same error for missing and foreign players, so other clubs' players stay hidden.
class InvalidSquadPlayers(AppException):
    def __init__(self):
        super().__init__(
            "Algún jugador elegido no existe, no es de tu club o está repetido",
            "INVALID_SQUAD_PLAYERS",
        )


class InvalidSquadBehaviors(AppException):
    def __init__(self):
        super().__init__(
            "Algún comportamiento elegido no existe o no es de tu club",
            "INVALID_SQUAD_BEHAVIORS",
        )
