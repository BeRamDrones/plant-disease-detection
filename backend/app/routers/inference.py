from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from app.services.inference import ModelRegistry, ChildModelRegistry, CHILD_MODELS_DIR, pipeline
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


@router.get("/model-registry")
async def model_registry():
    """
    Returns a full inventory of parent + child models.
    For each child model directory under Child_Models/, reports:
      - folder name, display name, whether a best.pt was found,
        whether it's currently loaded in GPU memory, and its task type / class count.
    """
    parent = ModelRegistry.get()
    child_reg = ChildModelRegistry.get()

    # Discover every child model folder
    children = []
    if os.path.isdir(CHILD_MODELS_DIR):
        for folder in sorted(os.listdir(CHILD_MODELS_DIR)):
            folder_path = os.path.join(CHILD_MODELS_DIR, folder)
            if not os.path.isdir(folder_path):
                continue

            # Resolve display name (strip pc1_ prefix, replace underscores)
            display = folder.replace("pc1_", "").replace("_", " ")

            # Check if a best.pt exists anywhere inside the folder
            weights_path = None
            for root, _dirs, files in os.walk(folder_path):
                if "best.pt" in files:
                    weights_path = os.path.join(root, "best.pt")
                    break

            norm = folder.lower().replace("_", "").replace(" ", "").replace("-", "").replace("pc1", "")
            is_loaded = norm in child_reg._loaded_models

            # If loaded, extract task / class count from the live model object
            task = None
            class_count = None
            class_names = None
            if is_loaded:
                model = child_reg._loaded_models[norm]
                task = getattr(model, "task", "detect")
                names = getattr(model, "names", {})
                class_count = len(names)
                class_names = list(names.values()) if len(names) <= 30 else list(names.values())[:30]

            children.append({
                "folder":       folder,
                "display_name": display,
                "has_weights":  weights_path is not None,
                "weights_path": weights_path,
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


@router.post("/awaken/{crop_name}")
async def awaken_child(crop_name: str):
    """
    Manually awakens / loads a specific crop's child model into memory.
    Ideal for client demonstrations to show on-demand dynamic loading.
    """
    device = ModelRegistry.get().device or "cpu"
    child_reg = ChildModelRegistry.get()
    model = child_reg.awaken_child_model(crop_name, device)
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"No child model folder with weights found for crop '{crop_name}'"
        )
    return {
        "status": "awoken",
        "crop": crop_name,
        "device": device,
        "task": getattr(model, "task", "detect"),
        "class_count": len(getattr(model, "names", {})),
        "class_names": list(getattr(model, "names", {}).values())[:30],
        "loaded_models": child_reg.loaded_crops(),
    }


@router.post("/unload-children")
async def unload_children():
    """
    Resets loaded child models back to STANDBY.
    Useful for demonstration resets.
    """
    child_reg = ChildModelRegistry.get()
    count = len(child_reg._loaded_models)
    child_reg._loaded_models.clear()
    return {"status": "unloaded", "count_unloaded": count}





