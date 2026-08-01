import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


# ---------------------------------------------------------------------------
# Enums — free strings replaced so bad data can't sneak in at the DB layer
# ---------------------------------------------------------------------------

class MissionPhase(str, enum.Enum):
    SURVEY = "survey"        # mapping flight — builds Flight_Zone polygons
    DETECTION = "detection"  # disease-detection flight — uses zones for point-in-polygon match


class MissionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class SeverityLevel(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CropClass(str, enum.Enum):
    # extend as your 14+ crop taxonomy grows — keeping this centralized
    # means every table references the same canonical set instead of
    # each table re-typing "Tomato" / "tomato" / "Tomatoe"
    APPLE = "apple"
    TOMATO = "tomato"
    POTATO = "potato"
    JACKFRUIT = "jackfruit"
    SOYABEAN = "soyabean"
    CAULIFLOWER = "cauliflower"
    CHERRY = "cherry"
    LEMON = "lemon"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Drone — was previously just a free-text drone_id string on every table
# ---------------------------------------------------------------------------

class Drone(Base):
    __tablename__ = "drone"

    drone_id = Column(String(100), primary_key=True)
    model_name = Column(String(150), nullable=False)
    camera_spec = Column(String(255), nullable=True)
    max_flight_time_min = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    missions = relationship("Flight_Mission", back_populates="drone")

    def __repr__(self):
        return f"<Drone id={self.drone_id} model={self.model_name}>"


# ---------------------------------------------------------------------------
# Flight_Mission — the missing link between your two flight phases
# ---------------------------------------------------------------------------

class Flight_Mission(Base):
    __tablename__ = "flight_mission"

    mission_id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(
        String(100), ForeignKey("drone.drone_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    phase = Column(Enum(MissionPhase), nullable=False, index=True)
    status = Column(Enum(MissionStatus), nullable=False, default=MissionStatus.SCHEDULED)

    # for a DETECTION mission, this points back at the SURVEY mission that
    # produced the zones being scanned — lets you trace the full pipeline run
    linked_survey_mission_id = Column(
        Integer, ForeignKey("flight_mission.mission_id", ondelete="SET NULL"), nullable=True
    )

    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    model_version = Column(String(100), nullable=True)  # e.g. "yolo11m_cls_v2"
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    drone = relationship("Drone", back_populates="missions")
    zones = relationship("Flight_Zone", back_populates="mission", cascade="all, delete-orphan")
    linked_survey_mission = relationship("Flight_Mission", remote_side=[mission_id])

    __table_args__ = (
        Index("ix_mission_drone_phase", "drone_id", "phase"),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ck_mission_end_after_start",
        ),
    )

    def __repr__(self):
        return f"<FlightMission id={self.mission_id} phase={self.phase} status={self.status}>"


class Flight_Zone(Base):
    __tablename__ = "flight_zone"

    zone_id = Column(Integer, primary_key=True, index=True)
    mission_id = Column(
        Integer, ForeignKey("flight_mission.mission_id", ondelete="CASCADE"), nullable=False, index=True
    )
    drone_id = Column(
        String(100), ForeignKey("drone.drone_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    crop_class = Column(Enum(CropClass), nullable=False)

    # GeoJSON-style polygon: {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
    # kept as JSON since you're doing in-app Shapely point-in-polygon rather
    # than DB-side spatial queries; if you ever need spatial indexing/queries
    # (e.g. "which zones overlap this bounding box"), swap this for
    # GeoAlchemy2's Geometry(Polygon) column instead.
    boundary_points = Column(JSON, nullable=False)

    mapped_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    mission = relationship("Flight_Mission", back_populates="zones")
    detections = relationship(
        "Parent_Model_Disease_Classification",
        back_populates="zone",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_flight_zone_drone_crop", "drone_id", "crop_class"),
        Index("ix_flight_zone_mission", "mission_id"),
    )

    def __repr__(self):
        return f"<Flight_Zone id={self.zone_id} drone={self.drone_id} crop={self.crop_class}>"


class Parent_Model_Disease_Classification(Base):
    __tablename__ = "parent_model_disease_classification"

    detected_class_id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(
        String(100), ForeignKey("drone.drone_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mission_id = Column(
        Integer, ForeignKey("flight_mission.mission_id", ondelete="CASCADE"), nullable=False, index=True
    )
    zone_id = Column(
        Integer,
        ForeignKey("flight_zone.zone_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detected_class = Column(Enum(CropClass), nullable=False, index=True)
    model_version = Column(String(100), nullable=True)  # parent-classifier weights used
    image_snapshot_url = Column(String(2048), nullable=False)
    confidence_score = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude_agl = Column(Float, nullable=False)
    heading = Column(Float, nullable=True)
    gimbal_pitch = Column(Float, nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    zone = relationship("Flight_Zone", back_populates="detections")
    child_detections = relationship(
        "Child_Models_Disease_Classification",
        back_populates="parent_detection",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_parent_confidence_range",
        ),
        CheckConstraint("altitude_agl >= 0", name="ck_parent_altitude_nonneg"),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90", name="ck_parent_lat_range"
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name="ck_parent_lon_range"
        ),
        Index("ix_parent_drone_detected_at", "drone_id", "detected_at"),
        Index("ix_parent_mission", "mission_id"),
    )

    def __repr__(self):
        return (
            f"<ParentDetection id={self.detected_class_id} class={self.detected_class} "
            f"conf={self.confidence_score:.2f}>"
        )


class Child_Models_Disease_Classification(Base):
    __tablename__ = "child_models_disease_classification"

    id = Column(Integer, primary_key=True, index=True)
    drone_id = Column(
        String(100), ForeignKey("drone.drone_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    flight_mission_id = Column(
        Integer, ForeignKey("flight_mission.mission_id", ondelete="CASCADE"), nullable=False, index=True
    )
    # a child detection only exists in relation to a parent crop detection —
    # made this NOT NULL (was nullable before, which doesn't match the domain)
    parent_detection_id = Column(
        Integer,
        ForeignKey(
            "parent_model_disease_classification.detected_class_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    detected_disease = Column(String(100), nullable=False, index=True)
    model_version = Column(String(100), nullable=True)  # child-classifier weights used
    confidence_score = Column(Float, nullable=False)
    severity_level = Column(Enum(SeverityLevel), nullable=True)
    image_snapshot_url = Column(String(2048), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    parent_detection = relationship(
        "Parent_Model_Disease_Classification", back_populates="child_detections"
    )

    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_child_confidence_range",
        ),
        Index("ix_child_drone_disease", "drone_id", "detected_disease"),
        Index("ix_child_mission_created", "flight_mission_id", "created_at"),
    )

    def __repr__(self):
        return (
            f"<ChildDetection id={self.id} disease={self.detected_disease} "
            f"severity={self.severity_level}>"
        )


# ---------------------------------------------------------------------------
# Sprinkler_System — previous version had only `id` with ~150 blank lines.
# Filled in a reasonable actuation-log shape; adjust fields to match what
# actually triggers a sprinkler (e.g. tied to a detected disease + zone).
# ---------------------------------------------------------------------------

class Sprinkler_System(Base):
    __tablename__ = "sprinkler_system"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(
        Integer, ForeignKey("flight_zone.zone_id", ondelete="CASCADE"), nullable=False, index=True
    )
    triggered_by_detection_id = Column(
        Integer,
        ForeignKey("child_models_disease_classification.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active = Column(Boolean, nullable=False, default=False)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    duration_sec = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    zone = relationship("Flight_Zone")
    triggered_by = relationship("Child_Models_Disease_Classification")

    __table_args__ = (
        CheckConstraint("duration_sec IS NULL OR duration_sec >= 0", name="ck_sprinkler_duration_nonneg"),
        Index("ix_sprinkler_zone_active", "zone_id", "is_active"),
    )

    def __repr__(self):
        return f"<SprinklerSystem id={self.id} zone={self.zone_id} active={self.is_active}>"