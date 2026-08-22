from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class AgronomicReport(Base):
    __tablename__ = "agronomic_report"

    report_id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(
        Integer,
        ForeignKey("mission.mission_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ai_engine = Column(String(100), nullable=False)
    crop = Column(String(100), nullable=False)
    health_score = Column(Float, nullable=False)
    risk_level = Column(String(100), nullable=False)
    yield_impact = Column(String(100), nullable=True)
    executive_summary = Column(Text, nullable=True)
    primary_pathogen = Column(String(200), nullable=True)
    chemical_prescription = Column(Text, nullable=True)
    biological_remedy = Column(Text, nullable=True)
    drone_action_plan = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    mission = relationship("Mission", back_populates="reports")

    def __repr__(self) -> str:
        return f"<AgronomicReport id={self.report_id} mission_id={self.mission_id} crop={self.crop}>"
