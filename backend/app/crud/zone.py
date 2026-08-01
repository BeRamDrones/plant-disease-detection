from sqlalchemy import select
from shapely.geometry import Point
from geoalchemy2.shape import to_shape
from app.models.flight_zone import FlightZone
import logging

logger = logging.getLogger("app.crud.zone")

async def match_zone_in_db(db, mission_id: int, lat: float, lon: float) -> int | None:
    """
    Spatially matches coordinates (lat, lon) to one of the FlightZone polygons of the mission.
    Returns the matching zone_id, or None if the point lies outside all zones.
    If multiple zones overlap, returns the first match and logs a warning.
    """
    # 1. Query all flight zones for this mission
    stmt = select(FlightZone).where(FlightZone.mission_id == mission_id)
    res = await db.execute(stmt)
    zones = res.scalars().all()

    if not zones:
        logger.debug(f"No zones found in database for mission_id {mission_id}")
        return None

    # 2. Construct Shapely Point with order: Point(lon, lat)
    point = Point(lon, lat)
    matched_zone_id = None

    # 3. Check each zone's geometry for containment
    for zone in zones:
        try:
            # Convert GeoAlchemy Geometry element to Shapely Polygon
            polygon = to_shape(zone.zone_geometry)
            if polygon.contains(point):
                if matched_zone_id is not None:
                    logger.warning(
                        f"Point ({lon}, {lat}) falls in multiple overlapping zones for mission {mission_id}. "
                        f"First match was zone_id={matched_zone_id}, also matched zone_id={zone.zone_id}."
                    )
                    continue
                matched_zone_id = zone.zone_id
        except Exception as e:
            logger.error(f"Failed to check geometry containment for zone {zone.zone_id}: {str(e)}")

    return matched_zone_id
