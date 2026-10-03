from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, match_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[match_id].add(ws)

    def disconnect(self, match_id: str, ws: WebSocket) -> None:
        self._rooms[match_id].discard(ws)
        if not self._rooms[match_id]:
            del self._rooms[match_id]

    async def broadcast(self, match_id: str, event: dict) -> None:
        for ws in list(self._rooms.get(match_id, ())):
            try:
                await ws.send_json(event)
            except Exception:
                self.disconnect(match_id, ws)


manager = ConnectionManager()