from pydantic import BaseModel, Field
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