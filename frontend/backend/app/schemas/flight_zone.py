from pydantic import BaseModel, model_validator
from typing import Optional
from app.schemas.mission import GeoJSONPolygon
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

class FlightZoneBase(BaseModel):
    mission_id: int
    zone_geometry: GeoJSONPolygon
    zone_label: str
    crop_class: Optional[str] = None

class FlightZoneCreate(FlightZoneBase):
    pass

class FlightZoneResponse(BaseModel):
    zone_id: int
    mission_id: int
    zone_geometry: GeoJSONPolygon
    zone_label: str
    crop_class: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def convert_geometry(cls, data):
        if not isinstance(data, dict):
            zg = getattr(data, "zone_geometry", None)
            zone_geom_val = None
            if zg is not None:
                try:
                    shapely_geom = to_shape(zg)
                    zone_geom_val = mapping(shapely_geom)
                except Exception:
                    pass
            
            return {
                "zone_id": getattr(data, "zone_id"),
                "mission_id": getattr(data, "mission_id"),
                "zone_geometry": zone_geom_val,
                "zone_label": getattr(data, "zone_label"),
                "crop_class": getattr(data, "crop_class"),
            }
        return data

    class Config:
        from_attributes = True
