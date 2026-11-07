"""Evento CHANGE_BEHAVIOR: valida el pedido, lo encola en el motor y responde por el socket."""

from fastapi import WebSocket
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.services.behavior_change_service import behavior_belongs_to_club


class BehaviorChangeRejected(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


def parse_payload(payload) -> tuple[str, str]:
    if not isinstance(payload, dict):
        raise BehaviorChangeRejected(422, "El payload es inválido.")
    player_id, behavior_id = payload.get("playerId"), payload.get("behaviorId")
    if not isinstance(player_id, str) or not isinstance(behavior_id, str):
        raise BehaviorChangeRejected(422, "playerId y behaviorId son obligatorios.")
    return player_id, behavior_id


def _behavior_is_available(bind, behavior_id: str, club_id: str) -> bool:
    with Session(bind) as db:
        return behavior_belongs_to_club(db, behavior_id, club_id)


async def handle_change_behavior(socket: WebSocket, bind, engine, club_id: str, payload) -> None:
    try:
        player_id, behavior_id = parse_payload(payload)
        if engine is None:
            raise BehaviorChangeRejected(409, "El partido no está en curso.")
        if not await run_in_threadpool(_behavior_is_available, bind, behavior_id, club_id):
            raise BehaviorChangeRejected(404, "El comportamiento no existe o no está disponible.")
        try:
            engine.request_behavior_change(club_id, player_id, behavior_id)
        except ValueError as error:
            raise BehaviorChangeRejected(400, str(error))
    except BehaviorChangeRejected as error:
        await socket.send_json({"type": "error", "status": error.status, "message": error.message})
        return
    await socket.send_json(
        {"event": "BEHAVIOR_CHANGED", "payload": {"playerId": player_id, "behaviorId": behavior_id}}
    )
