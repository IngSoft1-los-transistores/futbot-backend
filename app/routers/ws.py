from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.room import Room
from app.models.enrollment import Enrollment
from app.ws.manager import room_manager as manager

router = APIRouter()


@router.websocket("/ws/friendly/{room_id}")
async def friendly_ws(
    websocket: WebSocket,
    room_id: str,
    club_id: str,                        # TEMPORAL: ver pendientes
    db: Session = Depends(get_db),
):
    await websocket.accept()             # Acepta primero para poder cerrar con un codigo que el navegador reciba

    room_exists = db.query(Room).filter(Room.id == room_id).first() is not None
    enrolled = room_exists and db.query(Enrollment).filter(
        Enrollment.room_id == room_id, Enrollment.club_id == club_id
    ).first() is not None
    db.close()                           # No dejar la sesion abierta durante toda la conexion

    if not room_exists:
        await websocket.close(code=4404) # Sala inexistente
        return
    if not enrolled:
        await websocket.close(code=4403) # Tu club no participa en la sala
        return

    await manager.connect(room_id, club_id, websocket)
    await manager.broadcast(room_id, {"type": "club_connected", "club_id": club_id})

    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect(room_id, club_id)
        await manager.broadcast(room_id, {"type": "club_disconnected", "club_id": club_id})
