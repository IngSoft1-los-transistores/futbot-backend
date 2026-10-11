from app.models.room import MAX_LEAGUE_CLUBS, MIN_LEAGUE_CLUBS
from app.services.exceptions_player import AppException


# Ticket: [BE] Crear Liga
# Validar que el nombre de la liga no se encuentre utilizado.
class NombreUnicoInvalido(AppException):
    def __init__(self, nombre: str):
        self.nombre = nombre

        super().__init__(
            message=f"El nombre {nombre} ya existe, elija otro",
            code="NOMBRE_LIGA_EXISTENTE",
        )


# Validar que la cantidad minima de clubes sea al menos 3 clubes.
class MinimoClubsInvalido(AppException):
    def __init__(self, min_clubs: int):
        self.min_clubs = min_clubs
        self.min = MIN_LEAGUE_CLUBS

        super().__init__(
            message=f"La liga debe tener al menos {self.min} clubes.",
            code="MINIMO_CLUBES_EN_LIGA",
        )


# Validar que la cantidad máxima de clubes sea a lo sumo 30.
class MaximosClubsInvalido(AppException):
    def __init__(self, max_clubs: int):
        self.max_clubs = max_clubs
        self.max = MAX_LEAGUE_CLUBS
        super().__init__(
            message=f"La liga debe tener maximo {self.max} clubes.",
            code="MAXIMO_CLUBES_EN_LIGA",
        )


# Validar que la cantidad máxima de clubes sea válida respecto de la mínima.
class MaximosRespectoMinimosClubs(AppException):
    def __init__(self, max_clubs: int, min_clubs: int):
        self.max_clubs = max_clubs
        self.min_clubs = min_clubs
        super().__init__(
            message="La cantidad de clubes maximos respecto a los minimos es inconsistente.",
            code="MAXIMOS_INCONSISTENTE_RESPECTO_DE_MINIMOS",
        )

## Valida si el jugador es unico en el club
class JugadorRepetido(AppException):
    def __init__(self, player_id: str):
        self.player_id = player_id

        super().__init__(
            message=f"El jugador con id:{player_id} no puede repetirse",
            code="JUGADOR_REPETIDO",
        )


## Valida si el jugador existe en el club
class JugadorNoExiste(AppException):
    def __init__(self, player_id: str):
        self.player_id = player_id
        super().__init__(message="El jugador no existe", code="JUGADOR_INEXISTENTE")


## Valida si el jugador existe en el club
class JugadorNoPerteneceAlClub(AppException):
    def __init__(
        self, club_id: str, nombre_club: str, player_id: str, nombre_player: str
    ):
        self.club_id = club_id
        self.nombre_club = nombre_club
        self.player_id = player_id
        self.nombre_player = nombre_player
        super().__init__(
            message=f"El jugador {nombre_player} con id:{player_id} no pertenece al club {nombre_club} con id:{club_id}",
            code="JUGADOR_PERTENECE_A_OTRO_CLUB",
        )


# Validar los comportamientos asignados a cada jugador.
class ComportamientoInvalido(AppException):
    def __init__(self, comportamiento_id: str):
        self.comportamiento_id = comportamiento_id

        super().__init__(
            message=f"El comportamiento con id:{comportamiento_id} es invalido",
            code="COMPORTAMIENTO_INVALIDO",
        )
