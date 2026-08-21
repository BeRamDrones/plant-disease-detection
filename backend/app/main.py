import os
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
# Application lifespan — UPDATED FOR LAZY LOADING (Fixes Render OOM)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Initializes the app without pre-loading models into RAM to respect Render's 512MB limit.
    Models will be loaded lazily on-demand during the first inference request.
    """
    logger.info("==" * 30)
    logger.info("Project Jatayu — starting up")

    # Log Hugging Face Hub connectivity status
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        logger.info(f"✓ HF_TOKEN configured (ends ...{hf_token[-4:]})")
    else:
        logger.warning("⚠ HF_TOKEN not set — HF Hub downloads from private repos may fail")

    logger.info("Configuring ModelRegistry for lazy on-demand loading...")
    
    # Initialize the registry but bypass the heavy `.load()` step that caused the memory crash
    registry = ModelRegistry.get()
    
    logger.info("✓ Backend ready — waiting for API requests to initialize ONNX engine")
    logger.info("==" * 30)

    yield  # Application is running

    logger.info("Project Jatayu — shutting down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Project Jatayu Backend",
    description=(
        "FastAPI + PostgreSQL/PostGIS backend for drone-based plant disease detection. "
        "Running optimized INT8 ONNX models with lazy-loading execution."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — dynamically handles trailing slashes that block Vercel requests
# ---------------------------------------------------------------------------
raw_frontend_url = os.getenv("FRONTEND_URL", "https://plant-disease-detection-ten-bay.vercel.app")

allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    raw_frontend_url.rstrip("/"),  # Strips the trailing slash to prevent CORS blocking
]

# Filter out empty strings
allowed_origins = [origin for origin in allowed_origins if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
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
        "model": "Lazy-loading ONNX initialized"
    }


if __name__ == "__main__":
    # Render assigns dynamic HOST and PORT environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)