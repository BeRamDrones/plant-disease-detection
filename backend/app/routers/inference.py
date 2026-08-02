from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from app.services.inference import ModelRegistry, pipeline
import tempfile, os, logging

router = APIRouter(prefix="/inference", tags=["Inference"])
logger = logging.getLogger("app.routers.inference")


@router.get("/model-status")
async def model_status():
    """
    Returns the current readiness of the parent model (best.pt).
    Frontend polls this endpoint every 2 s until ready == true.
    """
    return ModelRegistry.get().status()


@router.post("/infer/image")
async def infer_image(file: UploadFile = File(...)):
    """
    Accepts an image upload and runs inference with the parent model pipeline.
    Returns detected classes, confidence scores, and plant class.
    """
    registry = ModelRegistry.get()
    if not registry.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Model not ready yet. Please wait for the model to finish loading."
        )

    # Save upload to a temp file so pipeline can read it
    suffix = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        results = pipeline.run_inference(tmp_path)
        return {"status": "ok", "detections": results, "filename": file.filename}
    except Exception as exc:
        logger.error(f"Image inference error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.post("/infer/video-frame")
async def infer_video_frame(file: UploadFile = File(...)):
    """
    Accepts a single extracted video frame (JPEG/PNG) and runs inference.
    The frontend extracts frames from a video at N-second intervals and
    calls this endpoint for each frame.
    """
    registry = ModelRegistry.get()
    if not registry.is_ready:
        raise HTTPException(
            status_code=503,
            detail="Model not ready yet. Please wait for the model to finish loading."
        )

    suffix = ".jpg"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        results = pipeline.run_inference(tmp_path)
        return {"status": "ok", "detections": results}
    except Exception as exc:
        logger.error(f"Video-frame inference error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
