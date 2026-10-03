from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.manager import manager

router = APIRouter()


@router.websocket("/ws/matches/{match_id}")
async def match_socket(ws: WebSocket, match_id: str):
    await manager.connect(match_id, ws)
    try:
        while True:
            await ws.receive_text()      # mantiene la conexión abierta
    except WebSocketDisconnect:
        manager.disconnect(match_id, ws)