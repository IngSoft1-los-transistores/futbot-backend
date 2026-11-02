from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.enrollment import Enrollment
from app.models.room import Room, ROOM_STATUS_WAITING_GUEST, ROOM_STATUS_IN_PROGRESS, ROOM_STATUS_CANCELLED
from app.models.club import Club
from app.models.user import User
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

    # Validacion de sesion de usuario
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    # Validar usuario autenticado y coincidencia con el club_id
    user = None
    if token:
        try:
            from app.core.security import decode_access_token
            from app.models.auth_session import AuthSession
            from time import time
            claims = decode_access_token(token)
            session = db.get(AuthSession, claims.get("sid"))
            if session and not session.revoked and session.expires_at > time():
                user = db.get(User, claims.get("sub"))
        except Exception:
            pass

    club_obj = db.get(Club, club_id) if club_id else None

    if not user or not club_obj or club_obj.user_id != user.id:
        await websocket.close(code=4008, reason="No autorizado o token invalido.")
        db.close()
        return

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

    # Funcion auxiliar para generar el payload fresco
    def get_room_payload():
        db.expire_all()
        enrollments = db.query(Enrollment).filter(Enrollment.room_id == league_id).all()
        inscribed_clubs = [e.club_id for e in enrollments]

        creator_club = db.query(Club).filter(Club.id == room.creator_club_id).first()
        creator_name = creator_club.name if creator_club else "Desconocido"

        return{
            "type": "room_info",
            "league_id": room.id,
            "league_name": room.name,
            "creator_club_id": room.creator_club_id,
            "creator_club_name": creator_name,
            "inscribed_clubs": inscribed_clubs,
            "current_participants": len(inscribed_clubs),
            "min_clubs": room.min_clubs,
            "max_clubs": room.max_clubs,
            "status": room.status,
            "can_start": len(inscribed_clubs) >= room.min_clubs
        }

    initial_data = get_room_payload()
    db.close()

    # Envia informacion de sala al cliente conectado
    await websocket.send_json(initial_data)

    # Broadcast general cuando se une alguien
    await league_manager.broadcast_waiting(league_id, get_room_payload())

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            bind = db.get_bind()
            # Acciones
            with Session(bind) as action_db:
                current_room = action_db.query(Room).filter(Room.id == league_id).first()

                if action == "leave_room":
                    # Abandono de liga para clubs que no son el creador
                    if current_room and club_id == current_room.creator_club_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "El creador no puede abandonar la liga, debe cancelarla."
                        })
                        continue

                    enrollment_to_delete = action_db.query(Enrollment).filter(
                        Enrollment.room_id == league_id,
                        Enrollment.club_id == club_id
                    ).first()

                    if enrollment_to_delete:
                        action_db.delete(enrollment_to_delete)
                        action_db.commit()

                    # Notificar el abandono
                    updated_payload = get_room_payload()
                    await league_manager.broadcast_waiting(league_id, updated_payload)
                    await websocket.close(code=1000)
                    break

                elif action in ["start_league", "cancel_league"]:
                    if not current_room:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Liga inexistente"
                        })
                        continue

                    if club_id != current_room.creator_club_id:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Solo el creador puede realizar esta accion."
                        })
                        continue

                    # Inicio de Liga
                    if action == "start_league":
                        current_participants = action_db.query(Enrollment).filter(Enrollment.room_id == league_id).count()
                        if current_participants < current_room.min_clubs:
                            await websocket.send_json({
                                "type": "error",
                                "message": f"Se requiere al menos {current_room.min_clubs} clubes para iniciar."
                            })
                            continue

                        current_room.status = ROOM_STATUS_IN_PROGRESS
                        action_db.commit()

                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_started",
                            "redirect_url": f"/league/{league_id}/active"
                        })

                    elif action == "cancel_league":
                        current_room.status = ROOM_STATUS_CANCELLED
                        action_db.commit()
                        
                        await league_manager.broadcast_waiting(league_id, {
                            "type": "league_cancelled",
                            "redirect_url": "/home"
                        })

    except WebSocketDisconnect:
        league_manager.disconnect_waiting(league_id, club_id)
        
        bind = db.get_bind()
        with Session(bind) as action_db:
            # Reconstruccion de payload por desconexion
            enrollments = action_db.query(Enrollment).filter(Enrollment.room_id == league_id).all()
            inscribed_clubs = [e.club_id for e in enrollments]
            payload_disc = {
                "type": "room_info",
                "league_id": room.id,
                "league_name": room.name,
                "creator_club_id": room.creator_club_id,
                "inscribed_clubs": inscribed_clubs,
                "current_participants": len(inscribed_clubs),
                "min_clubs": room.min_clubs,
                "max_clubs": room.max_clubs,
                "status": room.status,
                "can_start": len(inscribed_clubs) >= room.min_clubs
            }
            await league_manager.broadcast_waiting(league_id, payload_disc)