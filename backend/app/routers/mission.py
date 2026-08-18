from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.mission import Mission
from app.models.flight_zone import FlightZone
from app.models.detection import ParentModelDiseaseClassification
from app.schemas.detection import (
    ZoneMatchRequest,
    ZoneMatchResponse,
    DetectionCreate,
    DetectionIngestResponse,
    ZoneSummary,
    MissionSummaryResponse,
)
from app.crud.zone import match_zone_in_db
from app.crud.detection import ingest_detections
import logging

router = APIRouter(prefix="/missions", tags=["Missions"])
logger = logging.getLogger("app.routers.mission")

@router.post("/{mission_id}/match-zone", response_model=ZoneMatchResponse)
async def match_zone(
    mission_id: int,
    payload: ZoneMatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Spatially matches a coordinate point (lat, lon) against all FlightZones for the mission.
    Returns the matching zone_id, or null if outside all zones.
    """
    # Verify mission exists first
    stmt = select(Mission).where(Mission.mission_id == mission_id)
    res = await db.execute(stmt)
    mission = res.scalar_one_or_none()
    if not mission:
        raise HTTPException(
            status_code=404,
            detail=f"Mission {mission_id} not found."
        )

    try:
        zone_id = await match_zone_in_db(db, mission_id, payload.lat, payload.lon)
        return ZoneMatchResponse(zone_id=zone_id)
    except Exception as e:
        logger.error(f"Error matching zone: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Zone matching failed: {str(e)}"
        )

@router.post("/{mission_id}/detections", response_model=DetectionIngestResponse)
async def post_detections(
    mission_id: int,
    detections: list[DetectionCreate],
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests a list of detections from a flight. Spatially matches each detection
    to a FlightZone in memory, and bulk inserts them in a single transaction.
    """
    # Verify mission exists
    stmt = select(Mission).where(Mission.mission_id == mission_id)
    res = await db.execute(stmt)
    mission = res.scalar_one_or_none()
    if not mission:
        raise HTTPException(
            status_code=404,
            detail=f"Mission {mission_id} not found."
        )

    try:
        inserted, unmatched = await ingest_detections(db, mission_id, detections)
        await db.commit()
        return DetectionIngestResponse(inserted=inserted, unmatched=unmatched)
    except Exception as e:
        logger.error(f"Detection ingestion failed for mission {mission_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Detection ingestion failed: {str(e)}"
        )

@router.get("/{mission_id}/summary", response_model=MissionSummaryResponse)
async def get_mission_summary(
    mission_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculates and returns a summary for the mission including:
    - Mission metadata
    - Per-zone breakdown (dominant class, detection counts, average confidence)
    - Mission health score (% of zones with healthy dominant class or 0 disease detections)
    """
    # 1. Fetch Mission metadata
    mission_stmt = select(Mission).where(Mission.mission_id == mission_id)
    res = await db.execute(mission_stmt)
    mission = res.scalar_one_or_none()
    if not mission:
        raise HTTPException(
            status_code=404,
            detail=f"Mission {mission_id} not found."
        )

    try:
        # 2. Fetch all flight zones for this mission
        zone_stmt = select(FlightZone).where(FlightZone.mission_id == mission_id)
        res = await db.execute(zone_stmt)
        zones = res.scalars().all()

        # 3. Query counts & average confidence grouped by zone
        summary_stmt = select(
            ParentModelDiseaseClassification.zone_id,
            func.count(ParentModelDiseaseClassification.id).label("count"),
            func.avg(ParentModelDiseaseClassification.confidence_score).label("avg_confidence")
        ).where(
            ParentModelDiseaseClassification.mission_id == mission_id
        ).group_by(
            ParentModelDiseaseClassification.zone_id
        )
        res = await db.execute(summary_stmt)
        zone_aggregates = {row.zone_id: (row.count, row.avg_confidence) for row in res.all()}

        # 4. Fetch dominant class per zone
        class_stmt = select(
            ParentModelDiseaseClassification.zone_id,
            ParentModelDiseaseClassification.detected_class,
            func.count(ParentModelDiseaseClassification.id).label("class_count")
        ).where(
            ParentModelDiseaseClassification.mission_id == mission_id
        ).group_by(
            ParentModelDiseaseClassification.zone_id,
            ParentModelDiseaseClassification.detected_class
        )
        res = await db.execute(class_stmt)
        
        zone_classes = {}
        for row in res.all():
            if row.zone_id not in zone_classes:
                zone_classes[row.zone_id] = {}
            zone_classes[row.zone_id][row.detected_class] = row.class_count

        # 5. Build summary objects and health metric
        zones_breakdown = []
        healthy_zones_count = 0

        for zone in zones:
            counts = zone_classes.get(zone.zone_id, {})
            dominant_class = None
            if counts:
                # Get the class with the maximum detection count in this zone
                dominant_class = max(counts, key=counts.get)

            det_count, avg_conf = zone_aggregates.get(zone.zone_id, (0, 0.0))

            # A zone is considered healthy if:
            # - There are 0 detections in it, OR
            # - The dominant detected class is "healthy"
            if det_count == 0 or dominant_class == "healthy":
                healthy_zones_count += 1

            zones_breakdown.append(
                ZoneSummary(
                    zone_id=zone.zone_id,
                    zone_label=zone.zone_label,
                    dominant_class=dominant_class,
                    detection_count=det_count,
                    avg_confidence=float(avg_conf) if avg_conf is not None else 0.0
                )
            )

        # Health score is % of healthy zones
        total_zones = len(zones)
        health_score = 100.0
        if total_zones > 0:
            health_score = (healthy_zones_count / total_zones) * 100.0

        return MissionSummaryResponse(
            mission=mission,
            zones_breakdown=zones_breakdown,
            health_score=health_score
        )
    except Exception as e:
        logger.error(f"Failed to generate summary for mission {mission_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate mission summary: {str(e)}"
        )


@router.post("/ai-report-summary")
async def generate_ai_report_summary(payload: dict):
    """
    Generates AI Agronomic Intelligence summary, yield risk analysis,
    and chemical/biological prescriptions for the mission report using Google Gemini.
    """
    from app.services.ai_service import AIService

    mission_id = payload.get("mission_id", 1)
    crop_class = payload.get("crop_class")
    health_score = float(payload.get("health_score", 100.0))
    detections = payload.get("detections", [])
    zones = payload.get("zones", [])

    return AIService.generate_agronomic_report(
        mission_id=mission_id,
        crop_class=crop_class,
        health_score=health_score,
        detections=detections,
        zones=zones
    )

