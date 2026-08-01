from sqlalchemy import select, insert
from shapely.geometry import Point
from geoalchemy2.shape import to_shape
from app.models.flight_zone import FlightZone
from app.models.detection import ParentModelDiseaseClassification
from datetime import datetime, timezone
import logging

logger = logging.getLogger("app.crud.detection")

async def ingest_detections(db, mission_id: int, detections_data) -> tuple[int, int]:
    """
    Ingests a list of detection objects for a specific mission.
    Pre-resolves which FlightZone each detection belongs to in memory to optimize database hits.
    Performs a bulk insert of all detections.
    Returns (inserted_count, unmatched_count).
    """
    logger.info(f"Ingesting detections for mission {mission_id} (count: {len(detections_data)})")

    # 1. Fetch zones for the mission
    stmt = select(FlightZone).where(FlightZone.mission_id == mission_id)
    res = await db.execute(stmt)
    zones = res.scalars().all()

    # Pre-parse geometries into shapely shapes
    zone_polygons = []
    for zone in zones:
        try:
            poly = to_shape(zone.zone_geometry)
            zone_polygons.append((zone.zone_id, poly))
        except Exception as e:
            logger.error(f"Error parsing geometry for zone {zone.zone_id}: {str(e)}")

    logger.debug(f"Loaded {len(zone_polygons)} zones for detection containment check on mission {mission_id}")

    # 2. Match each detection coordinates to the zones
    records_to_insert = []
    unmatched_count = 0
    now_utc = datetime.now(timezone.utc)

    for det in detections_data:
        point = Point(det.lon, det.lat)
        matched_zone_id = None

        for zone_id, poly in zone_polygons:
            try:
                if poly.contains(point):
                    if matched_zone_id is not None:
                        logger.warning(
                            f"Overlapping zones found in mission {mission_id} for detection point ({det.lon}, {det.lat}). "
                            f"First match: zone_id={matched_zone_id}, current match: zone_id={zone_id}"
                        )
                        continue
                    matched_zone_id = zone_id
            except Exception as e:
                logger.error(f"Error testing point containment during ingestion: {str(e)}")

        if matched_zone_id is None:
            unmatched_count += 1
            logger.debug(f"Detection at ({det.lat}, {det.lon}) is unmatched (outside all zones)")

        records_to_insert.append({
            "mission_id": mission_id,
            "zone_id": matched_zone_id,
            "detected_class": det.detected_class,
            "confidence_score": det.confidence_score,
            "lat": det.lat,
            "lon": det.lon,
            "image_ref": det.image_ref,
            "model_version": det.model_version,
            "detected_at": now_utc
        })

    # 3. Perform bulk insert
    inserted_count = 0
    if records_to_insert:
        await db.execute(insert(ParentModelDiseaseClassification), records_to_insert)
        inserted_count = len(records_to_insert)
        logger.info(
            f"Successfully bulk inserted {inserted_count} detections for mission {mission_id}. "
            f"Unmatched: {unmatched_count}"
        )

    return inserted_count, unmatched_count
