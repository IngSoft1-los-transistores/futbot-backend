from pydantic import BaseModel

"""Friendly room schemas."""


class FriendlyRoomStartRead(BaseModel):
    room_id: str
    match_id: str
    status: str
