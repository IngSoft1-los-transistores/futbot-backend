from pydantic import BaseModel

"""Friendly room schemas."""


class FriendlyRoomStartRead(BaseModel):
    """Response of `POST /api/friendly/rooms/{room_id}/start`.

    `match_id` lets the client connect straight to `/ws/match/{match_id}`
    without an extra request.
    """

    room_id: str
    match_id: str
    status: str
