from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import List
from enum import Enum

class RoomStatus(str, Enum):
    WAITING_GUEST = "waitingGuest"
    IN_PROGRESS = "inProgress"
    FINISHED = "finished"

class PlayerSelection(BaseModel):
    player_id: str = Field(..., example="uuid-player-1")
    behavior_id: str = Field(..., example="uuid-behavior-1")

class CreateFriendlyRoomRequest(BaseModel):
    starters: List[PlayerSelection]
    substitutes: List[PlayerSelection]

class FriendlyRoomResponse(BaseModel):
    room_id: str
    room_code: str
    status: str
    home_club: str

    class Config:
        populate_by_name = True


class FriendlyRoomStartRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    room_id: str
    match_id: str
    status: str


class FriendlyRoomPlayerRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    player_id: str
    name: str
    role: str
    behavior_id: str
    behavior_name: str


class FriendlyRoomClubRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    club_id: str
    club_name: str
    players: list[FriendlyRoomPlayerRead]


class FriendlyRoomRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    room_id: str
    room_code: str | None
    status: str
    # Set once the match was started.
    match_id: str | None
    home_club: FriendlyRoomClubRead
    away_club: FriendlyRoomClubRead | None
