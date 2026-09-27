from pydantic import BaseModel

"""Friendly room schemas."""


class FriendlyRoomStartRead(BaseModel):
    room_id: str
    match_id: str
    status: str


class FriendlyRoomPlayerRead(BaseModel):
    player_id: str
    name: str
    role: str
    behavior_id: str
    behavior_name: str


class FriendlyRoomClubRead(BaseModel):
    club_id: str
    club_name: str
    players: list[FriendlyRoomPlayerRead]


class FriendlyRoomRead(BaseModel):
    room_id: str
    room_code: str | None
    status: str
    # Set once the match was started.
    match_id: str | None
    home_club: FriendlyRoomClubRead
    away_club: FriendlyRoomClubRead | None
