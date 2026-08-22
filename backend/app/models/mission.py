import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class MissionPhase(str, enum.Enum):
    survey = "survey"
    detection = "detection"

class MissionStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    aborted = "aborted"

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum

class Mission(Base):
    __tablename__ = "mission"

    mission_id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(
        String(100),
        ForeignKey("drone.drone_id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    phase = Column(Enum(MissionPhase), nullable=False)
    status = Column(Enum(MissionStatus), nullable=False)
    crop_class = Column(String(100), nullable=True)
    
    # Polygon boundary GeoJSON string
    boundary_points = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    drone = relationship("Drone", back_populates="missions")
    zones = relationship("FlightZone", back_populates="mission", cascade="all, delete-orphan")
    detections = relationship("ParentModelDiseaseClassification", back_populates="mission", cascade="all, delete-orphan")
    reports = relationship("AgronomicReport", back_populates="mission", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Mission id={self.mission_id} phase={self.phase} status={self.status}>"
