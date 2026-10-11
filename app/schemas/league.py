
from pydantic import BaseModel, ConfigDict, Field

from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT


class SquadSelection(BaseModel):
    player_id: str
    behavior_id: str


class CreateLeague(BaseModel):
    name: str
    min_clubs: int = Field(gt=0)
    max_clubs: int = Field(gt=0)
    match_duration: int = Field(gt=0)
    starters: list[SquadSelection] = Field(
        min_length=STARTER_COUNT, max_length=STARTER_COUNT
    )
    substitutes: list[SquadSelection] = Field(
        min_length=SUBSTITUTE_COUNT, max_length=SUBSTITUTE_COUNT
    )


class LeagueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    is_private: bool
    started: bool
    creator_id: str
    code_to_join: str
