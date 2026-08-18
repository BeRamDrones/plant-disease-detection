from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import List, Tuple, Optional
from app.models.mission import MissionPhase, MissionStatus
try:
    from geoalchemy2.shape import to_shape
    from shapely.geometry import mapping
except ImportError:
    to_shape = None
    mapping = None

class GeoJSONPolygon(BaseModel):
    type: str = Field("Polygon", pattern="^Polygon$")
    coordinates: List[List[Tuple[float, float]]]

class UTMSSyncMission(BaseModel):
    mission_id: int
    drone_id: str
    phase: MissionPhase
    status: MissionStatus
    boundary_points: Optional[GeoJSONPolygon] = None
    crop_class: Optional[str] = None

class MissionResponse(BaseModel):
    mission_id: int
    drone_id: str
    phase: MissionPhase
    status: MissionStatus
    boundary_points: Optional[GeoJSONPolygon] = None
    crop_class: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data):
        # Check if the input is an ORM object (has attributes rather than keys)
        if not isinstance(data, dict):
            bp = getattr(data, "boundary_points", None)
            boundary_points_val = None
            if bp is not None:
                try:
                    shapely_geom = to_shape(bp)
                    boundary_points_val = mapping(shapely_geom)
                except Exception:
                    pass
            
            # Map attributes to a dictionary structure
            return {
                "mission_id": getattr(data, "mission_id"),
                "drone_id": getattr(data, "drone_id"),
                "phase": getattr(data, "phase"),
                "status": getattr(data, "status"),
                "boundary_points": boundary_points_val,
                "crop_class": getattr(data, "crop_class"),
                "created_at": getattr(data, "created_at"),
                "updated_at": getattr(data, "updated_at"),
            }
        return data

    class Config:
        from_attributes = True
