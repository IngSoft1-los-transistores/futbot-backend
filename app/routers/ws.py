from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.room import Room, ROOM_STATUS_WAITING_GUEST, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_CANCELLED
from app.models.club import Club
from app.ws.manager import room_manager as manager
from app.ws.manager import league_manager


router = APIRouter()


@router.websocket("/ws/friendly/{room_id}")
async def friendly_ws(
    websocket: WebSocket,
    room_id: str,
    club_id: str,
    db: Session = Depends(get_db),
):
    await websocket.accept()

    room_exists = db.query(Room).filter(Room.id == room_id).first() is not None
    enrolled = room_exists and db.query(Enrollment).filter(
        Enrollment.room_id == room_id,
        Enrollment.club_id == club_id,
    ).first() is not None

    db.close()

    if not room_exists:
        await websocket.close(code=4404)
        return

    if not enrolled:
        await websocket.close(code=4403)
        return

    await manager.connect(room_id, club_id, websocket)
    await manager.broadcast(room_id, {
        "type": "club_connected",
        "club_id": club_id,
    })

    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        manager.disconnect(room_id, club_id)
        await manager.broadcast(room_id, {
            "type": "club_disconnected",
            "club_id": club_id,
        })


@router.websocket("/ws/league/{league_id}/waiting")
async def league_waiting_room_ws(websocket: WebSocket,
                    league_id: str,
                    club_id: str,
                    db: Session = Depends(get_db),
):
    await websocket.accept()

    # Validar que la liga exista en BD
    room = db.query(Room).filter(Room.id == league_id).first()
    if not room or room.status != ROOM_STATUS_WAITING_GUEST:
        await websocket.close(code=4404, reason="La sala no existe o ya inició.")
        db.close()
        return

    # Validar que el usuario pertenece a la liga
    enrolled = db.query(Enrollment).filter(
        Enrollment.room_id == league_id,
        Enrollment.club_id == club_id,
    ).first() is not None

    if not enrolled:
        await websocket.close(code=4403, reason="El club no esta inscripto en esta liga.")
        db.close()
        return

    # Validar limite de clubs
    current_count = league_manager.get_rooms_user_count(league_id)
    if current_count >= room.max_clubs:
        await websocket.close(code=4008, reason="El lobby de espera esta lleno.")
        db.close()
        return

    # Registrar la conexion
    await league_manager.connect_waiting(league_id, club_id, websocket, room.max_clubs)

    # Informacion detallada para el estado inicial
    enrollments = db.query(Enrollment).filter(Enrollment.room_id == league_id).all()
    incribed_clubs = [e.club_id for e in enrollments]

    creator_club = db.query(Club).filter(Club.id == room.creator_club_id).first()
    creator_name = creator_club.name if creator_club else "Desconocido"

    initial_data = {
        "type": "room_info",
        "league_id": room.id,
        "league_name": room.name,
        "creator_club_id": room.creator_club_id,
        "creator_club_name": creator_name,
        "inscribed_clubs": incribed_clubs,
        "current_participants": len(incribed_clubs),
        "min_clubs": room.min_clubs,
        "max_clubs": room.max_clubs,
        "status": room.status,
        "can_start": len(incribed_clubs) >= room.min_clubs
    }

    db.close()

    # Envia informacion de sala al cliente conectado
    await websocket.send_json(initial_data)

    # Broadcast general cuando se une alguien
    await league_manager.broadcast_waiting(league_id, {
        "type": "club_joined_waiting",
        "club_id": club_id,
        "current_count": league_manager.get_rooms_user_count(league_id)
    })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            # Acciones del creador, hay validar que el usuario sea creador
            if action in ["start_league", "cancel_league"]:
                bind = db.get_bind()
                with Session(bind) as action_db:
                    current_room = action_db.query(Room).filter(Room.id == league_id).first()

                    # Validar existencia de liga
                    if not current_room:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Liga inexistente"
                        })
                        continue

                    # Validar que el usuario sea creador
                    if club_id != current_room.creator_club_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Solo el creador puede realizar esta accion."
                        })
                        continue

                    # Inicio de liga
                    if action == "start_league":
                        current_participants = league_manager.get_rooms_user_count(league_id)
                        if current_participants < current_room.min_clubs:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Se requiere al menos {current_room.min_clubs} clubes para iniciar."
                            })
                            continue

                        # Marcar la sala como iniciada en DB
                        current_room.status = ROOM_STATUS_IN_PROGRESS
                        action_db.commit()

                        # Avisar a los usuarios de la redireccion
                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_started",
                            "redirect_url": f"/league/{league_id}/active"
                        })

                    # Cancelacion de liga
                    elif action == "cancel_league":
                        # Marcar la liga como cancelada en DB
                        current_room.status = ROOM_STATUS_CANCELLED
                        action_db.commit()

                        # Avisar a todos los usuarios de la redireccion a homepage
                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_cancelled",
                            "redirect_url": "/home"
                        })

    except WebSocketDisconnect:
        league_manager.disconnect_waiting(league_id, club_id)
        
        # Avisar a todos los usuarios de la desconexion
        await league_manager.broadcast_waiting(league_id, {
            "type": "club_left_waiting",
            "club_id": club_id,
            "current_count": league_manager.get_rooms_user_count(league_id)
        })