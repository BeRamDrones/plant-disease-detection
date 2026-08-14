import os
import logging
import datetime
import tempfile
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.inference")

# ---------------------------------------------------------------------------
# Path resolution: backend root, weights subfolder, and Child_Models directory
# ---------------------------------------------------------------------------
_BASE_DIR        = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEIGHTS_DIR      = os.path.join(_BASE_DIR, "weights")
CHILD_MODELS_DIR = os.path.join(_BASE_DIR, "Child_Models")


def _resolve_model_path(filename: str) -> Optional[str]:
    """
    Searches for a .pt file in priority order:
      1. backend/ root  (e.g. backend/best.pt)
      2. backend/weights/ subfolder
    Returns the first path that exists, or None.
    """
    for path in [os.path.join(_BASE_DIR, filename), os.path.join(WEIGHTS_DIR, filename)]:
        if os.path.exists(path):
            return path
    return None


def _best_device() -> str:
    """
    Returns the best available torch device string:
      'cuda'  → NVIDIA GPU present
      'mps'   → Apple Silicon GPU
      'cpu'   → fallback
    """
    try:
        import torch
        if torch.cuda.is_available():
            dev = f"cuda:{torch.cuda.current_device()}"
            name = torch.cuda.get_device_name(0)
            logger.info(f"[Device] GPU detected → {dev} ({name})")
            return dev
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            logger.info("[Device] Apple MPS detected → mps")
            return "mps"
    except Exception as e:
        logger.warning(f"[Device] Device detection error: {e} — using CPU")
    logger.info("[Device] No GPU found — using CPU")
    return "cpu"


# ---------------------------------------------------------------------------
# ChildModelRegistry — loads child models strictly on-demand for classified crop
# ---------------------------------------------------------------------------
class ChildModelRegistry:
    """
    Registry for Child Models.
    Child models are NOT loaded at application startup.
    When the parent model classifies an image into a specific crop class (e.g. 'Tomato'),
    ONLY that crop's child model is loaded into memory on demand.
    No other child models are loaded.
    """
    _instance: Optional["ChildModelRegistry"] = None

    def __init__(self):
        self._loaded_models: Dict[str, Any] = {}      # norm_crop -> YOLO model instance
        self._model_paths: Dict[str, str]   = {}      # norm_crop -> absolute file path

    @classmethod
    def get(cls) -> "ChildModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def find_child_model_path(self, crop_name: str) -> Optional[str]:
        """
        Dynamically resolves the best.pt path for a given crop_name.
        Matches folder names flexibly (e.g. 'BitterGourd' -> 'Bitter Gourd',
        'Strawberry' -> 'pc1_Strawberry', 'Sunflower' -> 'sunflower').
        """
        if not os.path.exists(CHILD_MODELS_DIR):
            logger.warning(f"[ChildModelRegistry] Child_Models directory not found at: {CHILD_MODELS_DIR}")
            return None

        norm_crop = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")

        if norm_crop in self._model_paths:
            return self._model_paths[norm_crop]

        for folder in os.listdir(CHILD_MODELS_DIR):
            folder_path = os.path.join(CHILD_MODELS_DIR, folder)
            if not os.path.isdir(folder_path):
                continue

            norm_folder = folder.lower().replace("_", "").replace(" ", "").replace("-", "").replace("pc1", "")

            if norm_crop == norm_folder or norm_crop in norm_folder or norm_folder in norm_crop:
                for root, dirs, files in os.walk(folder_path):
                    if "best.pt" in files:
                        best_path = os.path.join(root, "best.pt")
                        self._model_paths[norm_crop] = best_path
                        return best_path

        return None

    def get_child_model(self, crop_name: str, device: str) -> Optional[Any]:
        """
        Retrieves or dynamically loads the child model for the classified crop_name.
        STRICT RULE: Loads ONLY the requested crop's child model on demand.
        No other child model is loaded.
        """
        norm_crop = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")

        # Return cached instance if already loaded on-demand for this crop
        if norm_crop in self._loaded_models:
            return self._loaded_models[norm_crop]

        model_path = self.find_child_model_path(crop_name)
        if not model_path:
            logger.info(f"[ChildModelRegistry] No child model folder found for crop class '{crop_name}'")
            return None

        try:
            from ultralytics import YOLO
            logger.info(
                f"[ChildModelRegistry] ON-DEMAND LOADING child model for '{crop_name}': "
                f"{model_path} -> device={device}"
            )
            child_model = YOLO(model_path)
            child_model.to(device)
            self._loaded_models[norm_crop] = child_model
            logger.info(
                f"[ChildModelRegistry] ✓ Child model ready for '{crop_name}' "
                f"(Task: {getattr(child_model, 'task', 'detect')}, Classes: {len(child_model.names)})"
            )
            return child_model
        except Exception as exc:
            logger.error(f"[ChildModelRegistry] Error loading child model for '{crop_name}': {exc}", exc_info=True)
            return None

    def awaken_child_model(self, crop_name: str, device: Optional[str] = None) -> Optional[Any]:
        """Manually awaken / load a child model into memory for client demonstration."""
        dev = device or _best_device()
        return self.get_child_model(crop_name, dev)

    def loaded_crops(self) -> List[str]:
        return list(self._loaded_models.keys())


# ---------------------------------------------------------------------------
# ModelRegistry — singleton that tracks load state for Parent Model (best.pt)
# ---------------------------------------------------------------------------
class ModelRegistry:
    """
    Singleton registry. Call `get()` to obtain the shared instance.
    Loads the parent model (ParentModel.pt) onto the best available device.
    """
    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self.is_ready: bool           = False
        self.model_name: str          = "ParentModel.pt"
        self.loaded_at: Optional[str] = None
        self.device: str              = "cpu"
        self.model_task: str          = "unknown"  # 'classify' | 'detect' | 'segment'
        self._model                   = None
        self._torch_available: bool    = False
        self._mock_mode: bool         = False

        try:
            import ultralytics  # noqa: F401
            import torch        # noqa: F401
            self._torch_available = True
        except ImportError as _e:
            logger.warning(
                f"Required package not found ({_e}). Inference will run in Mock Mode. "
                "Run: pip install ultralytics torch torchvision"
            )

    @classmethod
    def get(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, parent_model_filename: str = "ParentModel.pt") -> bool:
        """
        Loads the parent YOLO model onto the best available device (GPU first).
        Must be called once at application startup via the lifespan event.
        """
        self.model_name = parent_model_filename

        if not self._torch_available:
            logger.info("[ModelRegistry] PyTorch/ultralytics not available — enabling Mock Mode.")
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        model_path = _resolve_model_path(parent_model_filename)
        if model_path is None:
            logger.warning(
                f"[ModelRegistry] '{parent_model_filename}' not found in "
                f"'{_BASE_DIR}' or '{WEIGHTS_DIR}'. Falling back to Mock Mode."
            )
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        self.device = _best_device()

        try:
            from ultralytics import YOLO
            logger.info(f"[ModelRegistry] Loading YOLO parent model: {model_path} → device={self.device}")
            self._model     = YOLO(model_path)
            self.model_task = getattr(self._model, "task", "unknown")
            self._model.to(self.device)

            self.is_ready  = True
            self.loaded_at = datetime.datetime.utcnow().isoformat() + "Z"
            logger.info(
                f"[ModelRegistry] ✓ Parent model ready — "
                f"file={parent_model_filename}, task={self.model_task}, device={self.device}"
            )
            return True

        except Exception as exc:
            logger.error(f"[ModelRegistry] Failed to load parent model '{model_path}': {exc}", exc_info=True)
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "ready":                self.is_ready,
            "mock_mode":            self._mock_mode,
            "model_name":           self.model_name,
            "model_task":           self.model_task,
            "device":               self.device,
            "loaded_at":            self.loaded_at,
            "torch_available":      self._torch_available,
            "loaded_child_models":  ChildModelRegistry.get().loaded_crops(),
        }


# ---------------------------------------------------------------------------
# DiseaseDetectionPipeline — Two-Phase Parent-to-Child Execution
# ---------------------------------------------------------------------------
class DiseaseDetectionPipeline:
    """
    Two-Phase Plant Disease Detection Pipeline:
      • Phase 1: Parent model (ParentModel.pt, task='classify') identifies plant/crop class.
      • Phase 2: Child model (loaded strictly on-demand for that specific crop)
                 performs disease detection (task='detect').
    """

    def __init__(self):
        self._registry = ModelRegistry.get()
        self._child_registry = ChildModelRegistry.get()

    @property
    def is_loaded(self) -> bool:
        return self._registry.is_ready

    def run_inference(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Gate: returns [] if model is not ready.
        Executes two-phase parent-to-child detection pipeline.
        """
        if not self._registry.is_ready:
            logger.warning("[Pipeline] Model not ready — returning empty result.")
            return []

        if self._registry._mock_mode or self._registry._model is None:
            return self._mock_results(image_path)

        return self._real_two_phase_inference(image_path)

    def _mock_results(self, image_path: str) -> List[Dict[str, Any]]:
        """Simulated detections for demo / mock-mode environments."""
        import random
        logger.info(f"[Mock] Simulating inference for: {image_path}")
        diseases = [
            "healthy", "powdery_mildew", "rust", "blight",
            "leaf_spot", "mosaic_virus", "anthracnose", "downy_mildew",
        ]

        quads = [
            ("Top-Left", 0.25, 0.25),
            ("Top-Right", 0.75, 0.25),
            ("Bottom-Left", 0.25, 0.75),
            ("Bottom-Right", 0.75, 0.75),
        ]

        detections = []
        selected_quads = random.sample(quads, k=random.randint(1, 3))
        for label, rel_x, rel_y in selected_quads:
            detections.append({
                "detected_class":   random.choice(diseases),
                "confidence_score": round(0.70 + random.random() * 0.28, 4),
                "x_center":        rel_x,
                "y_center":        rel_y,
                "grid_zone":       label,
                "plant_class":     "mock",
                "model_name":      "best.pt (mock)",
            })
        return detections

    def _real_two_phase_inference(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Two-phase Parent-to-Child inference implementation:
          Phase 1: Parent model (best.pt, classify) identifies plant class.
          Phase 2: On-demand loading of ONLY the child model for that plant class
                   to run disease detection (detect task).
        """
        device = self._registry.device
        logger.info(f"[Two-Phase Inference] Image={image_path} | Device={device}")

        try:
            # ── PHASE 1: Parent Model Classification ─────────────────────────────
            parent_results = self._registry._model(image_path, device=device, verbose=False)
            if not parent_results or len(parent_results) == 0:
                return []

            p_res = parent_results[0]
            if not hasattr(p_res, "probs") or p_res.probs is None:
                logger.warning("[Two-Phase Inference] Parent model did not return classification probabilities.")
                return []

            probs = p_res.probs
            names = p_res.names

            top5_indices = probs.top5
            top5_confs   = probs.top5conf

            top_idx  = int(top5_indices[0])
            top_conf = float(top5_confs[0])
            crop_name = names.get(top_idx, f"class_{top_idx}")
            crop_name_clean = crop_name.lower().replace("_", "")

            # Filter non-leaf / low confidence frames (< 50% confidence -> No Leaf)
            MIN_LEAF_CONF = 0.50
            MIN_DISEASE_CONF = 0.50

            if top_conf < MIN_LEAF_CONF or crop_name_clean in ["notaleaf", "background", "unknown", "noleaf"]:
                logger.info(
                    f"[Phase 1] Top prediction '{crop_name}' conf={top_conf*100:.1f}% "
                    f"(< {MIN_LEAF_CONF*100:.0f}%) → evaluated as No Leaf / non-foliage frame, skipping child model."
                )
                return []

            logger.info(f"[Phase 1] Parent classified crop as '{crop_name}' (Confidence: {top_conf*100:.2f}%)")

            # ── PHASE 2: Child Model Disease Detection ───────────────────────────
            # Load ONLY the child model corresponding to the parent's classified crop
            child_model = self._child_registry.get_child_model(crop_name, device)

            if child_model is None:
                # No child model folder available for this crop -> Return parent crop identification
                logger.info(f"[Phase 2] No child model available for '{crop_name}' → Returning parent crop identification.")
                return [{
                    "detected_class":    f"{crop_name}_Healthy",
                    "confidence_score":  round(top_conf, 4),
                    "x_center":         0.5,
                    "y_center":         0.5,
                    "plant_class":      crop_name,
                    "parent_confidence": round(top_conf, 4),
                    "parent_model":     "ParentModel.pt",
                    "model_name":       "ParentModel.pt",
                    "child_status":     "STANDBY",
                }]

            # Run child model detection on image with conf=0.50 threshold
            child_model_name = os.path.basename(getattr(child_model, "ckpt_path", f"{crop_name}_best.pt"))
            child_results = child_model(image_path, device=device, conf=MIN_DISEASE_CONF, verbose=False)
            if not child_results or len(child_results) == 0:
                return [{
                    "detected_class":    f"{crop_name}_Healthy",
                    "confidence_score":  round(top_conf, 4),
                    "x_center":         0.5,
                    "y_center":         0.5,
                    "plant_class":      crop_name,
                    "parent_confidence": round(top_conf, 4),
                    "parent_model":     "ParentModel.pt",
                    "model_name":       child_model_name,
                    "child_status":     "AWOKEN (IN MEMORY)",
                }]

            c_res = child_results[0]
            boxes = c_res.boxes
            c_names = c_res.names

            detections: List[Dict[str, Any]] = []

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_idx  = int(box.cls[0])
                    disease  = c_names.get(cls_idx, f"disease_{cls_idx}")
                    conf     = float(box.conf[0])

                    if conf < MIN_DISEASE_CONF:  # filter noise below 50%
                        continue

                    xywhn = box.xywhn[0].tolist()

                    detections.append({
                        "detected_class":    disease,
                        "confidence_score":  round(conf, 4),
                        "x_center":         round(xywhn[0], 4),
                        "y_center":         round(xywhn[1], 4),
                        "plant_class":      crop_name,
                        "parent_confidence": round(top_conf, 4),
                        "parent_model":     "ParentModel.pt",
                        "model_name":       child_model_name,
                        "child_status":     "AWOKEN (IN MEMORY)",
                    })

            if not detections:
                # Child model ran but found 0 disease bounding boxes above threshold -> Plant is Healthy
                logger.info(f"[Phase 2] Child model '{crop_name}' found no disease boxes >= {MIN_DISEASE_CONF*100:.0f}% → Plant is Healthy.")
                detections.append({
                    "detected_class":    f"{crop_name}_Healthy",
                    "confidence_score":  round(top_conf, 4),
                    "x_center":         0.5,
                    "y_center":         0.5,
                    "plant_class":      crop_name,
                    "parent_confidence": round(top_conf, 4),
                    "parent_model":     "ParentModel.pt",
                    "model_name":       child_model_name,
                    "child_status":     "AWOKEN (IN MEMORY)",
                })

            logger.info(f"[Phase 2] Child model '{crop_name}' completed → {len(detections)} detection(s) found.")
            return detections

        except Exception as exc:
            logger.error(f"[Two-Phase Pipeline] Error during inference: {exc}", exc_info=True)
            return []


# ---------------------------------------------------------------------------
# Shared pipeline instance
# ---------------------------------------------------------------------------
pipeline = DiseaseDetectionPipeline()
