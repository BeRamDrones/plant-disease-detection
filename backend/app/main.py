import logging
import uvicorn
from fastapi import FastAPI
from app.routers import utms_router, mission_router

# Set up logging configuration for structured console output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("app.main")

app = FastAPI(
    title="Project Jatayu Backend",
    description="FastAPI + PostgreSQL/PostGIS backend for drone-based plant disease detection system",
    version="1.0.0"
)

# Register API routers with the '/api' prefix
app.include_router(utms_router, prefix="/api")
app.include_router(mission_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "status": "online",
        "message": "Project Jatayu Backend is active and running."
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
