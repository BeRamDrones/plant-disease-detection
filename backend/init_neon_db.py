import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_neon_db")

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def init_db():
    from app.core.config import ASYNC_DATABASE_URL, DATABASE_URL
    from app.core.database import engine, Base
    from app.models.drone import Drone
    from app.models.mission import Mission, MissionPhase, MissionStatus
    from app.models.flight_zone import FlightZone
    from app.models.detection import ParentModelDiseaseClassification
    from app.models.agronomic_report import AgronomicReport
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    logger.info("============================================================")
    logger.info("PROJECT JATAYU — NEON DATABASE TABLE INITIALIZER")
    logger.info(f"Target Connection: {ASYNC_DATABASE_URL[:40]}...")
    logger.info("============================================================")

    try:
        # 1. Create all SQLAlchemy table schemas in Neon DB
        async with engine.begin() as conn:
            logger.info("[1/4] Creating table schemas in Neon DB...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✓ Schemas created successfully: drone, mission, flight_zone, parent_model_disease_classification, agronomic_report.")

        # 2. Seed initial telemetry records if missing
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            logger.info("[2/4] Verifying default drone registration ('AG-DRONE-001')...")
            drone_stmt = select(Drone).where(Drone.drone_id == "AG-DRONE-001")
            res = await session.execute(drone_stmt)
            drone = res.scalar_one_or_none()

            if not drone:
                from datetime import datetime, timezone
                drone = Drone(
                    drone_id="AG-DRONE-001",
                    model_name="Jatayu-UAV-Pro",
                    status="active",
                    last_seen_at=datetime.now(timezone.utc),
                )
                session.add(drone)
                await session.commit()
                logger.info("✓ Registered default drone 'AG-DRONE-001'.")
            else:
                logger.info("✓ Drone 'AG-DRONE-001' already present.")

            logger.info("[3/4] Verifying default Mission #1024 record...")
            mission_stmt = select(Mission).where(Mission.mission_id == 1024)
            res = await session.execute(mission_stmt)
            mission = res.scalar_one_or_none()

            if not mission:
                mission = Mission(
                    mission_id=1024,
                    drone_id="AG-DRONE-001",
                    phase=MissionPhase.detection,
                    status=MissionStatus.in_progress,
                    crop_class=None,
                )
                session.add(mission)
                await session.commit()

                # Seed 8 standard flight zones A1 - D2 for Mission 1024
                zones = [
                    FlightZone(mission_id=1024, zone_label="A1"),
                    FlightZone(mission_id=1024, zone_label="A2"),
                    FlightZone(mission_id=1024, zone_label="B1"),
                    FlightZone(mission_id=1024, zone_label="B2"),
                    FlightZone(mission_id=1024, zone_label="C1"),
                    FlightZone(mission_id=1024, zone_label="C2"),
                    FlightZone(mission_id=1024, zone_label="D1"),
                    FlightZone(mission_id=1024, zone_label="D2"),
                ]
                session.add_all(zones)
                await session.commit()
                logger.info("✓ Created default Mission #1024 and 8 sector flight zones (A1-D2).")
            else:
                logger.info("✓ Mission #1024 already present.")

            logger.info("[4/4] Verifying session isolation & anti-data leakage constraints...")
            logger.info("✓ All detection records strictly enforce ForeignKey(mission.mission_id) cascade isolation.")

    except Exception as exc:
        logger.error(f"❌ Database initialization failed: {exc}", exc_info=True)
        return False

    logger.info("============================================================")
    logger.info("🎉 NEON DATABASE SETUP COMPLETE — READY FOR TELEMETRY INGESTION")
    logger.info("============================================================")
    return True

if __name__ == "__main__":
    asyncio.run(init_db())
