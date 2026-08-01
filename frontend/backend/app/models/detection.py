from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class ParentModelDiseaseClassification(Base):
    __tablename__ = "parent_model_disease_classification"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(
        Integer,
        ForeignKey("flight_zone.zone_id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    mission_id = Column(
        Integer,
        ForeignKey("mission.mission_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    detected_class = Column(String(100), nullable=False)
    confidence_score = Column(Float, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    image_ref = Column(String(1000), nullable=True)
    model_version = Column(String(100), nullable=False)
    detected_at = Column(DateTime(timezone=True), nullable=False)

    mission = relationship("Mission", back_populates="detections")
    zone = relationship("FlightZone", back_populates="detections")

    def __repr__(self) -> str:
        return (
            f"<ParentModelDiseaseClassification id={self.id} "
            f"class={self.detected_class} conf={self.confidence_score}>"
        )
