from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.mission import UTMSSyncMission, MissionResponse
from app.crud.mission import sync_mission_to_db
import logging

router = APIRouter(prefix="/utms", tags=["UTMS Webhook"])
logger = logging.getLogger("app.routers.utms")

@router.post("/sync-mission", response_model=MissionResponse)
async def sync_mission(payload: UTMSSyncMission, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint to receive mission data from the UTMS and upsert it into the database.
    Ensures transactional safety and error response mapping.
    """
    try:
        # DB writes are wrapped in a transaction block
        async with db.begin():
            mission = await sync_mission_to_db(db, payload)
        return mission
    except Exception as e:
        logger.error(f"Sync mission failed: {str(e)}", exc_info=True)
        # Return 400 Bad Request with a clear message instead of a stack trace
        raise HTTPException(
            status_code=400,
            detail=f"Webhook mission synchronization failed: {str(e)}"
        )
