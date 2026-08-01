# Project Jatayu — Backend Server

FastAPI asynchronous backend for **Project Jatayu**, a drone-based plant disease detection system. Integrates with PostgreSQL + PostGIS, SQLAlchemy 2.0 ORM, Shapely for local spatial geometry operations, and dynamic PyTorch inference.

---

## Technical Stack
- **Web Framework**: FastAPI (Async)
- **Database**: PostgreSQL with PostGIS extension (hosted on port `5433` via Docker to prevent conflicts with standard host services)
- **ORM**: SQLAlchemy 2.0 (Async engine) + GeoAlchemy2 for spatial structures
- **Spatial Processing**: Shapely (Local polygon containment check)
- **Migrations**: Alembic (Async)
- **ML Capabilities**: PyTorch (.pt file integration weights)

---

## Quick Start Guide

### 1. Requirements Setup
Ensure python virtual environment is active and dependencies are loaded:
```bash
# Navigate to backend directory
cd backend

# Install dependencies
pip install -r requirements.txt
```

### 2. Boot Database Container
Make sure Docker Desktop is running, then boot the PostGIS database service:
```bash
docker compose up -d
```
*Note: The container binds to port `5433` on the host to avoid overlaps with pre-installed host PostgreSQL services.*

### 3. Apply Migrations
Apply Alembic database migrations to generate tables, datatypes, and GiST indexes:
```bash
alembic upgrade head
```

### 4. Start Development Server
Launch the FastAPI uvicorn engine:
```bash
uvicorn app.main:app --reload
```
Open **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** to test the interactive API docs.

---

## PyTorch Model Integration (.pt files)

To integrate your plant disease detection weights:
1. Drop your PyTorch model file named `parent_disease_model.pt` directly into the `backend/weights/` folder.
2. The folder structure has been pre-configured in `.gitignore` to prevent committing massive weights files to git.
3. The server uses [app/services/inference.py](file:///e:/Project%20Jatayu/backend/app/services/inference.py) to load the models. If `torch` is not installed or your `.pt` weights are missing, the server will log a warning and fall back to Mock mode so development can proceed seamlessly without crashes.

---

## API Endpoints

### 1. UTMS Webhook Sync
- **Endpoint**: `POST /api/utms/sync-mission`
- **Body**: Ingests mission coordinates (boundary points) and metadata.
- **Features**: Performs race-condition-safe `UPSERT` on `mission_id` in PostgreSQL and automatically creates stub Drone rows if missing.

### 2. Coordinate Zone Matching
- **Endpoint**: `POST /api/missions/{mission_id}/match-zone`
- **Body**: `{ "lat": float, "lon": float }`
- **Features**: Performs point-in-polygon check in memory and returns matching `zone_id`. Logs warning if boundaries overlap.

### 3. Bulk Detection Ingestion
- **Endpoint**: `POST /api/missions/{mission_id}/detections`
- **Body**: Array of detection logs from drone flights.
- **Features**: Pre-resolves flight zones for coordinate points in memory and executes optimized multi-row inserts into database.

### 4. Mission Summary
- **Endpoint**: `GET /api/missions/{mission_id}/summary`
- **Features**: Calculates average confidence, counts, and dominant disease class per zone. Returns overall mission health score (% of zones healthy or clean).

---

## Running Verification Tests
Execute unit tests checking models, schemas, and spatial geometry checks:
```bash
python -m unittest tests/test_backend.py
```
