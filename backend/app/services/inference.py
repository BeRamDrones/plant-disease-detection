import os
import logging
import datetime
import tempfile
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.inference")

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
_BASE_DIR         = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEIGHTS_DIR       = os.path.join(_BASE_DIR, "weights")
CHILD_MODELS_DIR  = os.path.join(_BASE_DIR, "Child_Models")
_PROJECT_ROOT     = os.path.abspath(os.path.join(_BASE_DIR, ".."))           # e:\Project Jatayu\
PARENT_MODELS_DIR = os.path.join(_PROJECT_ROOT, "Parent_Models")             # e:\Project Jatayu\Parent_Models\


def _discover_parent_models() -> List[Dict[str, str]]:
    """
    Scans Parent_Models/ for subdirectories containing best.pt weights.
    Returns a list of dicts: {name, path} sorted by folder name.
    Falls back to legacy backend/ParentModel.pt if Parent_Models/ is absent.
    """
    entries = []
    if os.path.isdir(PARENT_MODELS_DIR):
        for folder in sorted(os.listdir(PARENT_MODELS_DIR)):
            folder_path = os.path.join(PARENT_MODELS_DIR, folder)
            if not os.path.isdir(folder_path):
                continue
            # Look for best.pt anywhere inside
            for root, _dirs, files in os.walk(folder_path):
                if "best.pt" in files:
                    entries.append({
                        "name": folder,
                        "path": os.path.join(root, "best.pt"),
                    })
                    break

    if not entries:
        # Fallback to legacy single model
        legacy = os.path.join(_BASE_DIR, "ParentModel.pt")
        if os.path.exists(legacy):
            entries.append({"name": "ParentModel", "path": legacy})

    return entries


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
# ModelRegistry — dual parent model ensemble (Parent1 + Parent2)
# ---------------------------------------------------------------------------
class ModelRegistry:
    """
    Singleton registry for the dual parent model ensemble.
    Loads ALL models found in Parent_Models/ at startup.
    Ensemble: both models run per frame; the highest-confidence
    non-NotALeaf prediction wins.
    """
    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self.is_ready: bool            = False
        self.model_name: str           = "ParentEnsemble"  # display label
        self.loaded_at: Optional[str]  = None
        self.device: str               = "cpu"
        self.model_task: str           = "classify"
        self._models: List[Dict[str, Any]] = []  # [{name, path, model, classes}]
        self._torch_available: bool    = False
        self._mock_mode: bool          = False

        try:
            import ultralytics  # noqa: F401
            import torch        # noqa: F401
            self._torch_available = True
        except ImportError as _e:
            logger.warning(
                f"Required package not found ({_e}). Inference will run in Mock Mode. "
                "Run: pip install ultralytics torch torchvision"
            )

    # Keep _model property for backwards-compatible checks in pipeline
    @property
    def _model(self):
        return self._models[0]["model"] if self._models else None

    @classmethod
    def get(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, _unused: str = "ParentModel.pt") -> bool:
        """
        Discovers and loads all parent models from Parent_Models/.
        Called once at application startup.
        """
        if not self._torch_available:
            logger.info("[ModelRegistry] PyTorch/ultralytics not available — enabling Mock Mode.")
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        entries = _discover_parent_models()
        if not entries:
            logger.warning("[ModelRegistry] No parent models found anywhere — enabling Mock Mode.")
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        self.device = _best_device()
        success = False

        try:
            from ultralytics import YOLO
            for entry in entries:
                try:
                    logger.info(f"[ModelRegistry] Loading parent model '{entry['name']}': {entry['path']} → {self.device}")
                    model = YOLO(entry["path"])
                    model.to(self.device)
                    self._models.append({
                        "name":    entry["name"],
                        "path":    entry["path"],
                        "model":   model,
                        "task":    getattr(model, "task", "classify"),
                        "classes": model.names,
                    })
                    logger.info(
                        f"[ModelRegistry] ✓ '{entry['name']}' ready — "
                        f"task={getattr(model, 'task', 'classify')}, "
                        f"classes={len(model.names)}: {list(model.names.values())}"
                    )
                    success = True
                except Exception as exc:
                    logger.error(f"[ModelRegistry] Failed to load '{entry['name']}': {exc}")

            self.model_name = " + ".join(m["name"] for m in self._models)
            self.model_task = "classify"
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            logger.info(f"[ModelRegistry] ✓ Ensemble ready — {len(self._models)} parent model(s) loaded.")
            return success

        except Exception as exc:
            logger.error(f"[ModelRegistry] Critical failure loading parent models: {exc}", exc_info=True)
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return False

    def cascade_classify(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Dual parent model ensemble sequential cascade:
          1. Brightness / Blank Frame Gate: Discard blank or dark frames (< 15.0 brightness).
          2. Parent1 (32 crops + NotALeaf) Primary Gate:
             - If Parent1 top prediction is NotALeaf (>= 25% conf), reject frame as background.
             - Find top non-NotALeaf crop from Parent1. If conf >= 25% (out of 32 classes), accept it.
          3. Supplementary Parent2 Gate:
             - Only consulted if Parent1 has no confident crop and NotALeaf < 25%.
        """
        NON_LEAF = {"notaleaf", "background", "unknown", "noleaf"}
        MIN_CONF = 0.50

        # Step 0: Reject blank or dark frames immediately
        try:
            from PIL import Image, ImageStat
            with Image.open(image_path) as img:
                stat = ImageStat.Stat(img.convert("L"))
                mean_brightness = stat.mean[0]
                if mean_brightness < 15.0:
                    logger.info(f"[Parent Ensemble] Frame is dark / blank (brightness={mean_brightness:.1f} < 15.0) — skipping.")
                    return None
        except Exception:
            pass

        # Step 1: Run Parent1 (Primary 32-crop model with NotALeaf background detector)
        parent1_entry = next((m for m in self._models if "parent1" in m["name"].lower()), self._models[0] if self._models else None)
        if parent1_entry:
            try:
                p1_results = parent1_entry["model"](image_path, device=self.device, verbose=False)
                if p1_results and hasattr(p1_results[0], "probs") and p1_results[0].probs is not None:
                    p1_r = p1_results[0]
                    p1_top_idx  = int(p1_r.probs.top5[0])
                    p1_top_conf = float(p1_r.probs.top5conf[0])
                    p1_crop     = p1_r.names.get(p1_top_idx, f"class_{p1_top_idx}")
                    p1_norm     = p1_crop.lower().replace("_", "")

                    p1_top3 = [
                        f"{p1_r.names.get(int(p1_r.probs.top5[i]))}: {float(p1_r.probs.top5conf[i])*100:.1f}%"
                        for i in range(min(5, len(p1_r.probs.top5)))
                    ]
                    logger.info(f"[Parent Ensemble] 'Parent1' Top Predictions: {', '.join(p1_top3)}")

                    # Gate A: If top prediction is NotALeaf >= 20%, reject background
                    if p1_norm in NON_LEAF and p1_top_conf >= 0.20:
                        logger.info(
                            f"[Parent Ensemble] Parent1 detected '{p1_crop}' ({p1_top_conf*100:.1f}%) "
                            f"— frame is non-leaf / background, skipping."
                        )
                        return None

                    # Gate B: Top crop must be a valid crop with >= 50% confidence
                    if p1_norm not in NON_LEAF and p1_top_conf >= MIN_CONF:
                        logger.info(
                            f"[Parent Ensemble] Parent1 Identified Crop '{p1_crop}' ({p1_top_conf*100:.2f}%)"
                        )
                        return {
                            "crop_name":    p1_crop,
                            "conf":         p1_top_conf,
                            "parent_model": parent1_entry["name"],
                            "num_classes":  len(parent1_entry["classes"]),
                        }
            except Exception as exc:
                logger.warning(f"[Parent Ensemble] Parent1 check error: {exc}")

        # Step 2: Supplementary parent models (e.g. Parent2 for Cauliflower, Rice, Lemon, etc.)
        for entry in self._models:
            if "parent1" in entry["name"].lower():
                continue
            try:
                results = entry["model"](image_path, device=self.device, verbose=False)
                if not results:
                    continue
                r = results[0]
                if not hasattr(r, "probs") or r.probs is None:
                    continue

                top_idx   = int(r.probs.top5[0])
                top_conf  = float(r.probs.top5conf[0])
                crop_name = r.names.get(top_idx, f"class_{top_idx}")
                norm_name = crop_name.lower().replace("_", "")
                num_classes = len(entry["classes"])

                top3_info = [
                    f"{r.names.get(int(r.probs.top5[i]))}: {float(r.probs.top5conf[i])*100:.1f}%"
                    for i in range(min(3, len(r.probs.top5)))
                ]
                logger.info(f"[Parent Ensemble] '{entry['name']}' Supplementary Predictions: {', '.join(top3_info)}")

                # Require high confidence for supplementary models that lack background classes
                if norm_name not in NON_LEAF and top_conf >= 0.70:
                    return {
                        "crop_name":    crop_name,
                        "conf":         top_conf,
                        "parent_model": entry["name"],
                        "num_classes":  num_classes,
                    }
            except Exception as exc:
                logger.warning(f"[Parent Ensemble] '{entry['name']}' error: {exc}")

        logger.info("[Parent Ensemble] No confident crop prediction found — frame skipped.")
        return None





    def status(self) -> Dict[str, Any]:
        return {
            "ready":                self.is_ready,
            "mock_mode":            self._mock_mode,
            "model_name":           self.model_name,
            "model_task":           self.model_task,
            "device":               self.device,
            "loaded_at":            self.loaded_at,
            "torch_available":      self._torch_available,
            "parent_models":        [{"name": m["name"], "classes": len(m["classes"])} for m in self._models],
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
        Two-phase inference using the dual parent model ensemble:
          Phase 1: Both parent models classify the image — best non-NotALeaf
                   prediction wins (highest confidence across all parents).
          Phase 2: On-demand child specialist model performs disease detection.
        """
        device = self._registry.device
        logger.info(f"[Two-Phase Inference] Image={image_path} | Device={device}")

        MIN_LEAF_CONF    = 0.50
        MIN_DISEASE_CONF = 0.45

        try:
            # ── PHASE 1: Sequential Cascade Classification ────────────────────────
            # Parent1 scans first → if no valid crop found, Parent2 is tried
            best = self._registry.cascade_classify(image_path)

            if best is None:
                logger.info("[Phase 1] Cascade: all parent models returned NotALeaf / low confidence — skipping frame.")
                return []

            crop_name   = best["crop_name"]
            top_conf    = best["conf"]
            parent_name = best["parent_model"]

            if top_conf < MIN_LEAF_CONF:
                logger.info(
                    f"[Phase 1] Best ensemble prediction '{crop_name}' conf={top_conf*100:.1f}% "
                    f"< {MIN_LEAF_CONF*100:.0f}% — skipping as No Leaf."
                )
                return []

            logger.info(
                f"[Phase 1] Ensemble winner → '{crop_name}' ({top_conf*100:.2f}%) "
                f"via {parent_name}"
            )

            # ── PHASE 2: Child Model Disease Detection ───────────────────────────
            child_model = self._child_registry.get_child_model(crop_name, device)

            if child_model is None:
                logger.info(f"[Phase 2] No child model available for '{crop_name}' → Returning parent identification.")
                return [{
                    "detected_class":    f"{crop_name}_Healthy",
                    "confidence_score":  round(top_conf, 4),
                    "x_center":         0.5,
                    "y_center":         0.5,
                    "plant_class":      crop_name,
                    "parent_confidence": round(top_conf, 4),
                    "parent_model":     parent_name,
                    "model_name":       parent_name,
                    "child_status":     "STANDBY",
                }]

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
                    "parent_model":     parent_name,
                    "model_name":       child_model_name,
                    "child_status":     "AWOKEN (IN MEMORY)",
                }]

            c_res   = child_results[0]
            boxes   = c_res.boxes
            c_names = c_res.names
            detections: List[Dict[str, Any]] = []

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_idx = int(box.cls[0])
                    disease = c_names.get(cls_idx, f"disease_{cls_idx}")
                    conf    = float(box.conf[0])
                    if conf < MIN_DISEASE_CONF:
                        continue
                    xywhn = box.xywhn[0].tolist()
                    detections.append({
                        "detected_class":    disease,
                        "confidence_score":  round(conf, 4),
                        "x_center":         round(xywhn[0], 4),
                        "y_center":         round(xywhn[1], 4),
                        "plant_class":      crop_name,
                        "parent_confidence": round(top_conf, 4),
                        "parent_model":     parent_name,
                        "model_name":       child_model_name,
                        "child_status":     "AWOKEN (IN MEMORY)",
                    })

            if not detections:
                logger.info(f"[Phase 2] No disease boxes >= {MIN_DISEASE_CONF*100:.0f}% → Plant is Healthy.")
                detections.append({
                    "detected_class":    f"{crop_name}_Healthy",
                    "confidence_score":  round(top_conf, 4),
                    "x_center":         0.5,
                    "y_center":         0.5,
                    "plant_class":      crop_name,
                    "parent_confidence": round(top_conf, 4),
                    "parent_model":     parent_name,
                    "model_name":       child_model_name,
                    "child_status":     "AWOKEN (IN MEMORY)",
                })

            logger.info(f"[Phase 2] '{crop_name}' → {len(detections)} detection(s).")

            # ── Groq VLM Audit Integration (Applies across Image, Video & Live UAV) ──
            from app.services.ai_service import _get_groq_key, VLMAuditService
            if _get_groq_key() and detections:
                for det in detections[:2]:
                    try:
                        audit = VLMAuditService.audit_detection(
                            crop=det.get("plant_class", crop_name),
                            detected_class=det["detected_class"],
                            confidence=det["confidence_score"],
                        )
                        det["vlm_verdict"]         = audit.get("verdict", "VERIFIED")
                        det["vlm_reasoning"]       = audit.get("reasoning", "")
                        det["pathogen_name"]       = audit.get("pathogen_name")
                        det["severity"]            = audit.get("severity", "MODERATE")
                        det["ai_audited"]          = audit.get("ai_audited", True)
                        if "adjusted_confidence" in audit and audit["adjusted_confidence"]:
                            det["confidence_score"] = float(audit["adjusted_confidence"])
                    except Exception as _audit_err:
                        logger.warning(f"[VLM Audit] Skip audit: {_audit_err}")

            return detections

        except Exception as exc:
            logger.error(f"[Two-Phase Pipeline] Error during inference: {exc}", exc_info=True)
            return []


# ---------------------------------------------------------------------------
# Shared pipeline instance
# ---------------------------------------------------------------------------
pipeline = DiseaseDetectionPipeline()
