from pydantic import BaseModel, Field
from datetime import datetime

class DroneBase(BaseModel):
    drone_id: str = Field(..., description="Matches UTMS format e.g. AG-DRONE-001")
    model_name: str
    status: str
    last_seen_at: datetime

class DroneCreate(DroneBase):
    pass

class DroneResponse(DroneBase):
    created_at: datetime

    class Config:
        from_attributes = True
