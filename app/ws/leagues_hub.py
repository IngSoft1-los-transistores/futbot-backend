import asyncio
import logging

from fastapi import WebSocket

from app.db.session import SessionLocal
from app.schemas.league import ListLeagueResponse
from app.services.league_service import LeagueService, filter_by_name

logger = logging.getLogger(__name__)


def load_leagues() -> list[ListLeagueResponse]:
    """Todas las ligas listables, leídas con una sesión propia (el canal vive más que un request)."""
    with SessionLocal() as db:
        return LeagueService(db).list_leagues()


class LeaguesHub:
    """Conexiones suscriptas al listado de ligas, cada una con su filtro por nombre."""

    def __init__(self):
        self.filters: dict[WebSocket, str] = {}
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Guarda el loop del servidor, para poder avisar desde hilos y código síncrono."""
        self.loop = loop

    def add(self, websocket: WebSocket) -> None:
        self.filters[websocket] = ""

    def set_filter(self, websocket: WebSocket, name: str) -> None:
        if websocket in self.filters:
            self.filters[websocket] = name

    def remove(self, websocket: WebSocket) -> None:
        self.filters.pop(websocket, None)

    async def send_list(self, websocket: WebSocket, leagues: list[ListLeagueResponse] | None = None) -> None:
        """Envía a una conexión el listado con su filtro aplicado."""
        if leagues is None:
            leagues = load_leagues()
        name = self.filters.get(websocket, "")
        await websocket.send_json({
            "type": "leagues",
            "name": name,
            "leagues": [league.model_dump(by_alias=True) for league in filter_by_name(leagues, name)],
        })

    async def broadcast(self) -> None:
        """Avisa que las ligas cambiaron: cada suscripto recibe su listado actualizado."""
        if not self.filters:
            return
        leagues = load_leagues()                     # una sola consulta para todos
        for websocket in list(self.filters):
            try:
                await self.send_list(websocket, leagues)
            except Exception:                        # conexión cerrada o rota: se da de baja
                self.remove(websocket)

    def notify_changed(self) -> None:
        """Pide un aviso desde código síncrono. No hace nada si nadie mira el listado."""
        loop = self.loop
        if loop is None or loop.is_closed() or not self.filters:
            return
        future = asyncio.run_coroutine_threadsafe(self.broadcast(), loop)
        future.add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(future) -> None:
        if not future.cancelled() and future.exception() is not None:
            logger.warning("No se pudo avisar el cambio de ligas", exc_info=future.exception())


leagues_hub = LeaguesHub()