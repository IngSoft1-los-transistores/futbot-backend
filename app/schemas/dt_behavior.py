from pydantic import BaseModel, ConfigDict


class DtBehaviorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    behavior_id: str
    name: str
