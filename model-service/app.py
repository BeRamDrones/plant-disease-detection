"""
model-service/app.py — Project Jatayu Child Inference Microservice
Runs on a separate Render instance (512MB RAM).
Loads ONE child ONNX model at a time from Hugging Face Hub, runs disease detection, returns predictions.
"""
import io
import gc
import os
import logging

from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import PureONNX engine (same directory — no package import needed)
from onnx_engine import load_child_model, _CHILD_HF_FILES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("child_service")

app = FastAPI(title="Project Jatayu — Child Model Inference Microservice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single active model slot (LRU: only 1 child loaded at a time to fit 512MB RAM)
_current_model = None
_current_crop: str = ""


def _get_or_load_model(crop_name: str):
    global _current_model, _current_crop
    norm = crop_name.lower().replace(" ", "").replace("_", "").replace("-", "")
    if _current_crop == norm and _current_model is not None:
        logger.info(f"[Cache] Reusing loaded model for '{crop_name}'")
        return _current_model
    # Evict current model before loading new one
    if _current_model is not None:
        logger.info(f"[Cache] Evicting '{_current_crop}' — loading '{norm}'")
        _current_model = None
        gc.collect()
    _current_model = load_child_model(crop_name)
    _current_crop = norm
    return _current_model


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Project Jatayu Child Inference Microservice",
        "mode": "ONNX Runtime (INT8)",
        "active_model": _current_crop or "none",
        "available_crops": sorted(_CHILD_HF_FILES.keys()),
    }


@app.get("/health")
def health():
    return {"status": "ok", "active_model": _current_crop or "none"}


@app.post("/predict")
async def predict(
    crop_name: str,
    file: UploadFile = File(...),
):
    """
    Accepts: crop_name (query param) + image file (multipart)
    Returns: unified predictions JSON with detected disease bounding boxes
    """
    try:
        gc.collect()
        image_bytes = await file.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        model = _get_or_load_model(crop_name)
        if model is None:
            raise HTTPException(
                status_code=404,
                detail=f"No child model available for crop '{crop_name}'. Check HF repo."
            )

        predictions = model.predict(image, crop_name=crop_name)
        return {
            "status": "success",
            "crop_name": crop_name,
            "model_used": f"{crop_name}_best_int8.onnx",
            "predictions": predictions,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Prediction error for '{crop_name}': {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))