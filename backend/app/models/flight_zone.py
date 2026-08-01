from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

class FlightZone(Base):
    __tablename__ = "flight_zone"

    zone_id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(
        Integer,
        ForeignKey("mission.mission_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # PostGIS Polygon column for the subdivided zone geometry
    zone_geometry = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    zone_label = Column(String(50), nullable=False)
    crop_class = Column(String(100), nullable=True)

    mission = relationship("Mission", back_populates="zones")
    detections = relationship("ParentModelDiseaseClassification", back_populates="zone")

    def __repr__(self) -> str:
        return f"<FlightZone id={self.zone_id} mission_id={self.mission_id} label={self.zone_label}>"
