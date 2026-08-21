import io, gc, tempfile, os, logging
from PIL import Image
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from app.services.inference import ModelRegistry, ChildModelRegistry, CHILD_MODELS_DIR, pipeline, HF_PARENT_REPO, _download_from_hf

router = APIRouter(prefix="/inference", tags=["Inference"])
logger = logging.getLogger("app.routers.inference")


@router.get("/model-status")
async def model_status():
    """
    Returns the current readiness of the parent model.
    Frontend polls this endpoint every 2 s until ready == true.
    """
    return ModelRegistry.get().status()


@router.get("/model-registry")
async def model_registry():
    """
    Returns a full inventory of parent + child ONNX models.
    Scans Models/Child/ for *_int8.onnx files and reports status.
    """
    parent = ModelRegistry.get()
    child_reg = ChildModelRegistry.get()

    # Discover every child ONNX model
    children = []
    if os.path.isdir(CHILD_MODELS_DIR):
        for filename in sorted(os.listdir(CHILD_MODELS_DIR)):
            if not filename.endswith("_int8.onnx"):
                continue

            filepath = os.path.join(CHILD_MODELS_DIR, filename)

            # Extract display name: "Apple_best_int8.onnx" -> "Apple"
            display = filename.replace("_best_int8.onnx", "").replace("_int8.onnx", "")
            display = display.replace("_", " ")

            # Check if loaded in memory
            norm = display.lower().replace(" ", "").replace("_", "").replace("-", "")
            is_loaded = norm in child_reg._loaded_models

            # If loaded, extract metadata from the live session wrapper
            task = None
            class_count = None
            class_names = None
            if is_loaded:
                model_info = child_reg._loaded_models[norm]
                task = model_info.get("task", "detect")
                names = model_info.get("names", {})
                class_count = len(names)
                class_names = list(names.values()) if len(names) <= 30 else list(names.values())[:30]

            children.append({
                "folder":       filename,
                "display_name": display,
                "has_weights":  True,
                "weights_path": filepath,
                "is_loaded":    is_loaded,
                "task":         task,
                "class_count":  class_count,
                "class_names":  class_names,
            })

    return {
        "parent": parent.status(),
        "children": children,
        "child_models_dir": CHILD_MODELS_DIR,
        "total_available": len(children),
        "total_loaded": sum(1 for c in children if c["is_loaded"]),
    }


@router.post("/predict")
async def run_inference_predict(file: UploadFile = File(...)):
    """
    Direct prediction endpoint: reads image, collects garbage to free RAM,
    executes ONNX pipeline inference and returns predictions.
    """
    try:
        # Clear RAM before running inference
        gc.collect()

        # Read uploaded image bytes
        image_bytes = await file.read()
        
        # Save upload to a temp file for pipeline execution
        suffix = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            predictions = pipeline.run_inference(tmp_path)
            return {
                "status": "success",
                "model_used": "Parent_1_int8.onnx",
                "predictions": predictions
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"Inference error in /predict: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer/image")
async def infer_image(file: UploadFile = File(...)):
    """
    Accepts an image upload and runs inference with the ONNX pipeline.
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
    Accepts a single extracted video frame (JPEG/PNG) and runs ONNX inference.
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


@router.post("/awaken/{crop_name}")
async def awaken_child(crop_name: str):
    """
    Manually awakens / loads a specific crop's child ONNX model into memory.
    """
    device = ModelRegistry.get().device or "cpu"
    child_reg = ChildModelRegistry.get()
    model_info = child_reg.awaken_child_model(crop_name, device)
    if not model_info:
        raise HTTPException(
            status_code=404,
            detail=f"No child ONNX model found for crop '{crop_name}'"
        )
    return {
        "status": "awoken",
        "crop": crop_name,
        "device": device,
        "task": model_info.get("task", "detect"),
        "class_count": len(model_info.get("names", {})),
        "class_names": list(model_info.get("names", {}).values())[:30],
        "loaded_models": child_reg.loaded_crops(),
    }


from pydantic import BaseModel
from typing import Optional
from app.services.ai_service import VLMAuditService, AIService, _get_groq_key, _get_vlm_model, _get_report_model, set_groq_key


class AuditRequest(BaseModel):
    crop: str
    detected_class: str
    confidence: float
    zone: Optional[str] = None
    extra_context: Optional[str] = None
    image_base64: Optional[str] = None


class GroqKeyRequest(BaseModel):
    api_key: str


@router.get("/groq-status")
async def groq_status():
    key = _get_groq_key()
    return {
        "configured": bool(key),
        "masked_key": f"{key[:6]}...{key[-4:]}" if len(key) >= 10 else ("***" if key else "Not Configured"),
        "vlm_model": _get_vlm_model(),
        "report_model": _get_report_model(),
    }


@router.post("/set-groq-key")
async def update_groq_key(req: GroqKeyRequest):
    set_groq_key(req.api_key)
    key = _get_groq_key()
    return {
        "status": "ok",
        "configured": bool(key),
        "message": "Groq API key updated successfully! AI LLM & VLM reasoning is active.",
    }


@router.post("/audit-detection")
async def audit_detection(req: AuditRequest):
    """
    Groq VLM / LLM real-time audit & precision agronomic verification.
    """
    return VLMAuditService.audit_detection(
        crop=req.crop,
        detected_class=req.detected_class,
        confidence=req.confidence,
        zone=req.zone,
        extra_context=req.extra_context,
        image_base64=req.image_base64,
    )






