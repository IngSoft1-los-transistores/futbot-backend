from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class LeagueResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    participants_count: int
    started: bool
    is_private: bool