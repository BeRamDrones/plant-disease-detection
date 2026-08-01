from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.mission import MissionResponse

class ZoneMatchRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the point")
    lon: float = Field(..., description="Longitude of the point")

class ZoneMatchResponse(BaseModel):
    zone_id: Optional[int] = None

class DetectionCreate(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of the detection")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude of the detection")
    detected_class: str = Field(..., description="Detected crop/disease class")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    image_ref: Optional[str] = Field(None, description="Reference path or URL to the image frame")
    model_version: str = Field(..., description="ML model version")

class DetectionIngestResponse(BaseModel):
    inserted: int = Field(..., description="Number of detections successfully inserted")
    unmatched: int = Field(..., description="Number of detections that fell outside all known zones")

class ZoneSummary(BaseModel):
    zone_id: int
    zone_label: str
    dominant_class: Optional[str] = Field(None, description="Dominant detected class in the zone")
    detection_count: int = Field(..., description="Number of detections in this zone")
    avg_confidence: float = Field(..., description="Average confidence score of detections in this zone")

class MissionSummaryResponse(BaseModel):
    mission: MissionResponse
    zones_breakdown: List[ZoneSummary]
    health_score: float = Field(..., description="Percentage of zones that are healthy (dominant class is healthy or 0 detections)")
