import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import utms_router, mission_router, inference_router
from app.services.inference import ModelRegistry

# Set up logging configuration for structured console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("app.main")


# ---------------------------------------------------------------------------
# Application lifespan — loads the parent model on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Loads the parent model (ParentModel.pt) before the server starts accepting
    requests, so the frontend's model-status poll resolves quickly.
    """
    logger.info("=" * 60)
    logger.info("Project Jatayu — starting up")
    logger.info("Loading parent model (ParentModel.pt)…")

    registry = ModelRegistry.get()
    success = registry.load("ParentModel.pt")

    if success:
        logger.info("✓ Parent model ready — accepting inference requests")
    else:
        logger.warning("⚠ Model load encountered issues — running in Mock Mode")

    logger.info("=" * 60)

    yield  # Application is running

    logger.info("Project Jatayu — shutting down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Project Jatayu Backend",
    description=(
        "FastAPI + PostgreSQL/PostGIS backend for drone-based plant disease detection. "
        "Parent model: ParentModel.pt (crop classifier) → child models (disease specialists)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow the Next.js dev server (port 3000) and any localhost origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(utms_router,       prefix="/api")
app.include_router(mission_router,    prefix="/api")
app.include_router(inference_router,  prefix="/api")


@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Project Jatayu Backend v2 is active.",
        "model": ModelRegistry.get().status(),
    }


if __name__ == "__main__":
    # Port 8001 — port 8000 is occupied by ndms_backend_service on this machine
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
