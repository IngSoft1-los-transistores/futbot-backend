from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.squad_entry import STARTER_COUNT, SUBSTITUTE_COUNT
from app.schemas.friendly_room import FriendlyRoomPlayerRead, JoinPlayerSelection


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


class LeagueSummaryRead(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    league_id: str
    name: str
    status: str
    min_clubs: int
    max_clubs: int
    enrolled_clubs: int
    match_duration_minutes: int
    is_enrolled: bool


class LeagueUpdatedPayload(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    league_id: str
    enrolled_clubs: int


class LeagueDetailRead(LeagueSummaryRead):
    is_private: bool
    # Only the requesting club's squad; None when it is not enrolled.
    my_squad: list[FriendlyRoomPlayerRead] | None
