from app.behaviors.interfaces import IMatchEngine
from app.schemas.coord import Coord


class JugadorAPI:
    """El objeto `jugador` que recibe la funcion `comportamiento(jugador)`.

    Expone unicamente las primitivas definidas en la API de comportamientos
    (consultas y acciones). Cada instancia queda atada a un unico
    jugador_id: no hay forma de que el codigo ejecutado acceda a otro
    jugador, a otro club o al partido en si.

    Las acciones validan su precondicion antes de mutar el estado. Una
    accion invalida es un no-op silencioso: nunca levanta una excepcion,
    para que un comportamiento con una decision "ilegal" (ej. patear sin
    tener la pelota) simplemente no tenga efecto, en vez de cortar la
    ejecucion del resto de ese tick.
    """

    def __init__(self, jugador_id: str, engine: IMatchEngine) -> None:
        self._jugador_id = jugador_id
        self._engine = engine

    # --- Consultas ---
    def encontrar_pelota(self) -> Coord:
        return self._engine.pos_pelota()

    def encontrar_aliado(self) -> Coord:
        return self._engine.jugador_aliado_mas_cercano(self._jugador_id)

    def encontrar_enemigo(self) -> Coord:
        return self._engine.jugador_enemigo_mas_cercano(self._jugador_id)

    def encontrar_arco_aliado(self) -> Coord:
        return self._engine.arco_aliado(self._jugador_id)

    def encontrar_arco_enemigo(self) -> Coord:
        return self._engine.arco_enemigo(self._jugador_id)

    def encontrar_mis_coordenadas(self) -> Coord:
        return self._engine.pos_jugador(self._jugador_id)

    def tengo_pelota(self) -> bool:
        return self._engine.tiene_pelota(self._jugador_id)

    def club_tiene_pelota(self) -> bool:
        return self._engine.club_tiene_pelota(self._jugador_id)

    # --- Acciones ---
    def pasar(self, destino: Coord) -> None:
        if not self._engine.dentro_de_cancha(destino):
            return
        if not self._engine.tiene_pelota(self._jugador_id):
            return
        self._engine.aplicar_pase(self._jugador_id, destino)

    def patear_pelota(self, destino: Coord) -> None:
        if not self._engine.dentro_de_cancha(destino):
            return
        if not self._engine.tiene_pelota(self._jugador_id):
            return
        self._engine.aplicar_remate(self._jugador_id, destino)

    def correr(self, destino: Coord) -> None:
        if not self._engine.dentro_de_cancha(destino):
            return
        if not self._engine.jugador_en_cancha(self._jugador_id):
            return
        self._engine.aplicar_movimiento(self._jugador_id, destino)