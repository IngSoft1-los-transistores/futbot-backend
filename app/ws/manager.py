from fastapi import WebSocket

MAX_USERS = 2


class ConnectionManager:
    def __init__(self):
        self.rooms: dict[int, dict[int, WebSocket]] = {}        # { sala_id: { usuario_id: WebSocket } }

    def full_room(self, room_id: int, user_id: int) -> bool:
        users = self.rooms.get(room_id, {})
        return user_ide not in users and len(users) >= MAX_USERS

    async def connect(self, room_id: int, user_id: int, ws: WebSocket):
        self.rooms.setdefault(room_id, {})[user_id] = ws

    def disconnect(self, room_id: int, user_id: int):
        self.rooms.get(room_id, {}).pop(user_id, None)
        if room_id in self.rooms and not self.rooms[room_id]:
            del self.rooms[room_id]

    async def send(self, ws: WebSocket, message: dict):
        await ws.send_json(message)              # Solo a un usuario

    async def broadcast(self, room_id: int, message: dict):
        for ws in list(self.rooms.get(room_id, {}).values()):
            await ws.send_json(message)          # A toda la sala


manager = ConnectionManager()