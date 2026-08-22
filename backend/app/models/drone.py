from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Drone(Base):
    __tablename__ = "drone"

    drone_id = Column(String(100), primary_key=True, index=True)
    model_name = Column(String(150), nullable=False)
    status = Column(String(50), nullable=False)  # e.g., "active", "idle", "maintenance"
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    missions = relationship("Mission", back_populates="drone", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Drone id={self.drone_id} model={self.model_name} status={self.status}>"
