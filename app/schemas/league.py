from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT
from app.schemas.friendly_room import JoinPlayerSelection


class JoinLeagueRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Only checked when the league is private.
    password: str | None = None
    starters: list[JoinPlayerSelection] = Field(
        alias="titulares", min_length=STARTER_COUNT, max_length=STARTER_COUNT
    )
    substitutes: list[JoinPlayerSelection] = Field(
        alias="suplentes", min_length=SUBSTITUTE_COUNT, max_length=SUBSTITUTE_COUNT
    )


class JoinLeagueResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    enrollment_id: str
    club_id: str
    league_id: str
