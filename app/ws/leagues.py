"""League list events over an authenticated WebSocket."""
import asyncio
import json
import logging
from time import time

import anyio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.dependencies import get_current_club, get_current_user
from app.core.security import decode_access_token
from app.db.session import get_db
from app.ws.manager import league_list_manager
from app.ws.matches import HEARTBEAT_SECONDS, error_message

router = APIRouter()
logger = logging.getLogger(__name__)
AUTH_TIMEOUT_SECONDS = 10
MAX_AUTH_MESSAGE_LENGTH = 4096


def authenticate(bind, token: str) -> float:
    """Applies the REST session checks and returns the token expiry."""
    with Session(bind) as db:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        get_current_club(get_current_user(credentials, db))
    return decode_access_token(token)["exp"]


async def receive_token(socket: WebSocket) -> str:
    raw = await asyncio.wait_for(socket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    if len(raw) > MAX_AUTH_MESSAGE_LENGTH:
        raise ValueError("Mensaje demasiado grande")
    auth = json.loads(raw)
    if (
        not isinstance(auth, dict)
        or auth.get("type") != "auth"
        or not isinstance(auth.get("token"), str)
    ):
        raise ValueError("Autenticación requerida")
    return auth["token"]


def is_pong(raw: str) -> bool:
    try:
        return json.loads(raw) == {"type": "pong"}
    except ValueError:
        return False


@router.websocket("/ws/leagues")
async def league_list_stream(socket: WebSocket, db: Session = Depends(get_db)):
    origin = socket.headers.get("origin")
    if origin and origin not in get_settings().cors_origins_list:
        await socket.close(code=1008)
        return
    await socket.accept()
    queue = received = changed = None
    try:
        try:
            token = await receive_token(socket)
        except (ValueError, TimeoutError):
            await error_message(socket, 401, "Sesión inválida o vencida")
            return
        bind = db.get_bind()
        expires_at = await run_in_threadpool(authenticate, bind, token)
        # Subscribe before confirming, so every event after "subscribed" reaches the client.
        queue = league_list_manager.subscribe()
        await socket.send_json({"type": "subscribed"})

        received = asyncio.create_task(socket.receive_text())
        changed = asyncio.create_task(queue.get())
        next_ping = time() + HEARTBEAT_SECONDS
        pong_deadline = None
        while True:
            deadline = min(expires_at, pong_deadline or next_ping)
            done, _ = await asyncio.wait(
                {received, changed},
                timeout=max(0, deadline - time()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if time() >= expires_at:
                await error_message(socket, 401, "Sesión inválida o vencida")
                return
            if pong_deadline and time() >= pong_deadline:
                await socket.close(code=1011, reason="Sin respuesta al heartbeat")
                return
            if received in done:
                if not is_pong(received.result()):
                    await socket.close(code=1008, reason="Mensaje inesperado")
                    return
                pong_deadline = None
                next_ping = time() + HEARTBEAT_SECONDS
                received = asyncio.create_task(socket.receive_text())
            if changed in done:
                await socket.send_json(changed.result())
                changed = asyncio.create_task(queue.get())
            if not pong_deadline and time() >= next_ping:
                # Revalidating the session is what closes the socket after a logout.
                await run_in_threadpool(authenticate, bind, token)
                await socket.send_json({"type": "ping"})
                pong_deadline = time() + HEARTBEAT_SECONDS
    except (HTTPException, JWTError):
        await error_message(socket, 401, "Sesión inválida o vencida")
    except WebSocketDisconnect:
        pass
    except (SQLAlchemyError, OSError):
        logger.exception("No se pudo transmitir el listado de ligas")
        await error_message(socket, 503, "No se pudo actualizar el listado de ligas.")
    finally:
        if queue is not None:
            league_list_manager.unsubscribe(queue)
        with anyio.CancelScope(shield=True):
            tasks = [task for task in (received, changed) if task]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
