from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func
from app.models.drone import Drone
from app.models.mission import Mission
from shapely.geometry import shape
from geoalchemy2.shape import from_shape
import logging

logger = logging.getLogger("app.crud.mission")

async def sync_mission_to_db(db, sync_data) -> Mission:
    """
    Safely upserts a mission record based on incoming UTMS webhook data.
    Ensures that a stub Drone record exists if it doesn't already.
    """
    logger.info(
        f"Attempting sync of mission {sync_data.mission_id} for drone {sync_data.drone_id}"
    )

    # 1. Upsert Drone: ensure drone exists before mission creation
    drone_stmt = pg_insert(Drone).values(
        drone_id=sync_data.drone_id,
        model_name="UTMS Auto-Created Stub",
        status="active",
        last_seen_at=func.now(),
        created_at=func.now()
    ).on_conflict_do_nothing(
        index_elements=[Drone.drone_id]
    )
    
    await db.execute(drone_stmt)
    logger.debug(f"Ensured drone {sync_data.drone_id} exists in Drone table")

    # 2. Convert GeoJSON Polygon to GeoAlchemy WKBElement
    boundary_geom = None
    if sync_data.boundary_points is not None:
        try:
            geojson_dict = sync_data.boundary_points.model_dump()
            shapely_poly = shape(geojson_dict)
            boundary_geom = from_shape(shapely_poly, srid=4326)
            logger.debug("Successfully parsed boundary points GeoJSON into Shapely geometry")
        except Exception as e:
            logger.error(f"Failed to parse boundary points GeoJSON: {str(e)}")
            raise ValueError(f"Invalid boundary points geometry: {str(e)}")

    # 3. Upsert Mission using ON CONFLICT DO UPDATE
    mission_stmt = pg_insert(Mission).values(
        mission_id=sync_data.mission_id,
        drone_id=sync_data.drone_id,
        phase=sync_data.phase,
        status=sync_data.status,
        crop_class=sync_data.crop_class,
        boundary_points=boundary_geom,
        created_at=func.now(),
        updated_at=func.now()
    )

    update_dict = {
        "drone_id": mission_stmt.excluded.drone_id,
        "phase": mission_stmt.excluded.phase,
        "status": mission_stmt.excluded.status,
        "crop_class": mission_stmt.excluded.crop_class,
        "boundary_points": mission_stmt.excluded.boundary_points,
        "updated_at": func.now()
    }

    mission_stmt = mission_stmt.on_conflict_do_update(
        index_elements=[Mission.mission_id],
        set_=update_dict
    ).returning(Mission)

    res = await db.execute(mission_stmt)
    mission_row = res.scalar_one()

    logger.info(
        f"Mission {sync_data.mission_id} successfully upserted in the database"
    )
    return mission_row
