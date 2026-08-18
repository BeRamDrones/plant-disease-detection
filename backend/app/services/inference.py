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
            if not os.path.isdir(folder_path) or folder.lower() in {"temp", "tmp", "__pycache__"}:
                continue
            # Look for best.pt, Parent_3.pt, or any valid model .pt inside
            target_pt = None
            for root, _dirs, files in os.walk(folder_path):
                if "best.pt" in files:
                    target_pt = os.path.join(root, "best.pt")
                    break
                elif "Parent_3.pt" in files:
                    target_pt = os.path.join(root, "Parent_3.pt")
                    break
                else:
                    for f in sorted(files):
                        if f.endswith(".pt") and f != "last.pt":
                            target_pt = os.path.join(root, f)
                            break
                if target_pt:
                    break

            if target_pt:
                entries.append({
                    "name": folder,
                    "path": target_pt,
                })

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
    CROP_ALIASES: Dict[str, str] = {
        "eggplant": "brinjal",
        "brinjal": "brinjal",
        "aubergine": "brinjal",
        "soybean": "soyabean",
        "soya": "soyabean",
        "soy": "soyabean",
        "soyabean": "soyabean",
        "pumpkin": "pumkin",
        "pumkin": "pumkin",
        "peanut": "groundnut",
        "groundnut": "groundnut",
        "strawberry": "strawberry",
        "pepper": "pepperbell",
        "bellpepper": "pepperbell",
        "pepperbell": "pepperbell",
        "capsicum": "pepperbell",
        "sugarcane": "sugarcane",
        "sugar_cane": "sugarcane",
        "bittergourd": "bittergourd",
        "bitter_gourd": "bittergourd",
    }

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
        Matches folder names flexibly (e.g. 'Eggplant' -> 'Brinjal',
        'Soybean' -> 'SoyaBean', 'Pumpkin' -> 'Pumkin', 'Strawberry' -> 'pc1_Strawberry').
        """
        if not os.path.exists(CHILD_MODELS_DIR):
            logger.warning(f"[ChildModelRegistry] Child_Models directory not found at: {CHILD_MODELS_DIR}")
            return None

        raw_norm = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")
        norm_crop = self.CROP_ALIASES.get(raw_norm, raw_norm)

        if norm_crop in self._model_paths:
            return self._model_paths[norm_crop]

        for folder in os.listdir(CHILD_MODELS_DIR):
            folder_path = os.path.join(CHILD_MODELS_DIR, folder)
            if not os.path.isdir(folder_path) or folder == "Child_Models":
                continue

            norm_folder = folder.lower().replace("_", "").replace(" ", "").replace("-", "").replace("pc1", "")

            if norm_crop == norm_folder or norm_crop in norm_folder or norm_folder in norm_crop:
                for root, dirs, files in os.walk(folder_path):
                    if "best.pt" in files:
                        best_path = os.path.join(root, "best.pt")
                        self._model_paths[norm_crop] = best_path
                        self._model_paths[raw_norm] = best_path
                        return best_path

        return None

    def get_all_available_crops(self) -> List[str]:
        """Scans CHILD_MODELS_DIR and returns all crops that have valid best.pt weights."""
        if not os.path.exists(CHILD_MODELS_DIR):
            return []
        crops = []
        for folder in sorted(os.listdir(CHILD_MODELS_DIR)):
            folder_path = os.path.join(CHILD_MODELS_DIR, folder)
            if not os.path.isdir(folder_path) or folder == "Child_Models":
                continue
            for root, dirs, files in os.walk(folder_path):
                if "best.pt" in files:
                    clean_name = folder.replace("pc1_", "").strip()
                    crops.append(clean_name)
                    break
        return crops

    def get_child_model(self, crop_name: str, device: str) -> Optional[Any]:
        """
        Retrieves or dynamically loads the child model for the classified crop_name.
        STRICT RULE: Loads ONLY the requested crop's child model on demand.
        No other child model is loaded.
        """
        raw_norm = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")
        norm_crop = self.CROP_ALIASES.get(raw_norm, raw_norm)

        # Return cached instance if already loaded on-demand for this crop
        if norm_crop in self._loaded_models:
            return self._loaded_models[norm_crop]
        if raw_norm in self._loaded_models:
            return self._loaded_models[raw_norm]

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
            self._loaded_models[raw_norm] = child_model
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

    @staticmethod
    def _is_agricultural_foliage(image_path: str) -> tuple[bool, str]:
        """
        Fast local computer vision validator for agricultural foliage & leaves.
        Rejects:
          - Dark / blank frames or overexposed frames
          - Flat, solid backgrounds or synthetic UI screens
          - Human faces / indoor scenes
          - Non-vegetative scenes lacking chlorophyll color reflection
        """
        try:
            import cv2
            import numpy as np
            img_bgr = cv2.imread(image_path)
            if img_bgr is None:
                return False, "Unreadable image"

            h, w = img_bgr.shape[:2]
            total_pixels = h * w
            if total_pixels == 0:
                return False, "Empty image"

            # 1. Brightness bounds
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            mean_val = float(np.mean(gray))
            if mean_val < 15.0:
                return False, f"Too dark (brightness={mean_val:.1f} < 15)"
            if mean_val > 245.0:
                return False, f"Overexposed (brightness={mean_val:.1f} > 245)"

            # 2. Flat / Solid color screen check (std of pixel intensities)
            std_val = float(np.std(gray))
            if std_val < 8.0:
                return False, f"Flat/solid background (std={std_val:.1f} < 8.0)"

            # 3. Prominent human presence / Face rejection
            try:
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.15,
                    minNeighbors=6,
                    minSize=(int(min(h, w) * 0.15), int(min(h, w) * 0.15))
                )
                if len(faces) > 0:
                    return False, f"Human face detected ({len(faces)} face(s))"
            except Exception:
                pass

            # 4. Chlorophyll / Agricultural foliage ratio
            img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            lower_veg = np.array([20, 30, 30])
            upper_veg = np.array([95, 255, 255])
            veg_mask = cv2.inRange(img_hsv, lower_veg, upper_veg)
            veg_ratio = float(cv2.countNonZero(veg_mask)) / total_pixels

            # Excess Green Index (ExG = 2G - R - B)
            b, g, r = cv2.split(img_bgr.astype(np.float32))
            exg = 2 * g - r - b
            exg_ratio = float(np.count_nonzero(exg > 8.0)) / total_pixels

            # If frame has virtually no chlorophyll reflection or vegetative signature (< 5%)
            if veg_ratio < 0.05 and exg_ratio < 0.05:
                return False, f"No vegetative foliage signature (veg_ratio={veg_ratio*100:.1f}%, exg_ratio={exg_ratio*100:.1f}%)"

            return True, f"Foliage confirmed (veg={veg_ratio*100:.1f}%, exg={exg_ratio*100:.1f}%)"
        except Exception as e:
            return True, f"CV bypass: {e}"

    def cascade_classify(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Multi-parent neural ensemble classifier:
        Evaluates all loaded parent models (Parent1, Parent2, Parent3, ...) and selects the top crop prediction.
        """
        best_prediction: Optional[Dict[str, Any]] = None
        highest_conf = 0.0

        for parent_entry in self._models:
            p_name = parent_entry["name"]
            p_model = parent_entry["model"]
            try:
                p_results = p_model(image_path, device=self.device, verbose=False)
                if p_results and hasattr(p_results[0], "probs") and p_results[0].probs is not None:
                    p_r = p_results[0]
                    p_best_crop = None
                    p_best_conf = 0.0

                    for idx_tensor, conf_tensor in zip(p_r.probs.top5, p_r.probs.top5conf):
                        c_name = p_r.names.get(int(idx_tensor), f"class_{int(idx_tensor)}")
                        c_conf = float(conf_tensor)
                        if c_name.lower().replace("_", "") not in {"notaleaf", "background", "unknown"}:
                            p_best_crop = c_name
                            p_best_conf = c_conf
                            break

                    if p_best_crop is None:
                        p_best_crop = p_r.names.get(int(p_r.probs.top5[0]), "Plant")
                        p_best_conf = float(p_r.probs.top5conf[0])

                    logger.info(f"[Parent Ensemble] '{p_name}' Selected Crop: '{p_best_crop}' ({p_best_conf*100:.1f}%)")

                    if p_best_conf > highest_conf:
                        highest_conf = p_best_conf
                        best_prediction = {
                            "crop_name":    p_best_crop,
                            "conf":         p_best_conf,
                            "parent_model": p_name,
                            "num_classes":  len(parent_entry["classes"]),
                        }
            except Exception as exc:
                logger.warning(f"[Parent Ensemble] '{p_name}' error: {exc}")

        return best_prediction





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
        Executes Pre-Inference VLM Gate, Two-Phase YOLO Detection, and Post-Inference VLM Verification.
        """
        if not self._registry.is_ready:
            logger.warning("[Pipeline] Model not ready — returning empty result.")
            return []

        # ── PRE-INFERENCE VLM GATE (Before YOLO runs) ───────────────────────────
        from app.services.ai_service import _get_groq_key, VLMAuditService
        if _get_groq_key():
            pre_check = VLMAuditService.pre_audit_frame(image_path)
            if not pre_check.get("is_plant_foliage", True) or pre_check.get("verdict") == "REJECTED":
                logger.info(f"[Pre-Inference LLM Filter] Frame discarded before YOLO: {pre_check.get('reasoning')} — skipped inference.")
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
        Two-phase inference using dual parent model ensemble with specialized child verification:
          Phase 1: Multi-candidate crop classification with child specialist disease probing.
          Phase 2: Exact bounding box lesion extraction and VLM agronomic audit.
        """
        device = self._registry.device
        logger.info(f"[Two-Phase Inference] Image={image_path} | Device={device}")

        MIN_DISEASE_CONF = 0.15

        try:
            # ── Step 1: Candidate Generation from All Parent Models ───────────
            candidate_crops: List[tuple[str, float, str]] = []
            for parent_entry in self._registry._models:
                p_name = parent_entry["name"]
                p_model = parent_entry["model"]
                try:
                    p_res = p_model(image_path, device=device, verbose=False)
                    if p_res and hasattr(p_res[0], "probs") and p_res[0].probs is not None:
                        p_r = p_res[0]
                        for idx_t, conf_t in zip(p_r.probs.top5, p_r.probs.top5conf):
                            c_name = p_r.names.get(int(idx_t), "")
                            if c_name.lower().replace("_", "") not in {"notaleaf", "background", "unknown"}:
                                candidate_crops.append((c_name, float(conf_t), p_name))
                except Exception as exc:
                    logger.warning(f"[Two-Phase Pipeline] {p_name} candidate extraction error: {exc}")

            # ── Step 2: Specialized Child Model Probing ────────────────────────
            best_child_crop = None
            best_child_conf = 0.0
            best_child_detections: List[Dict[str, Any]] = []

            # Prioritize candidates that have child models
            child_probe_list: List[str] = []
            for c_name, conf, p_name in candidate_crops:
                if self._child_registry.find_child_model_path(c_name) and c_name not in child_probe_list:
                    child_probe_list.append(c_name)

            # If top candidates did not find child models, also probe all available child models
            all_available_children = self._child_registry.get_all_available_crops()
            for c in all_available_children:
                if c not in child_probe_list and self._child_registry.find_child_model_path(c):
                    child_probe_list.append(c)

            for crop_name in child_probe_list[:8]:
                child_model = self._child_registry.get_child_model(crop_name, device)
                if child_model is None:
                    continue

                c_model_name = os.path.basename(getattr(child_model, "ckpt_path", f"{crop_name}_best.pt"))
                c_results = child_model(image_path, device=device, conf=MIN_DISEASE_CONF, verbose=False)

                if c_results and len(c_results) > 0 and c_results[0].boxes and len(c_results[0].boxes) > 0:
                    c_res = c_results[0]
                    c_names = c_res.names
                    crop_dets = []
                    for box in c_res.boxes:
                        cls_idx = int(box.cls[0])
                        raw_disease = c_names.get(cls_idx, f"disease_{cls_idx}")
                        conf = float(box.conf[0])
                        if conf < MIN_DISEASE_CONF:
                            continue
                        
                        # Format disease name
                        formatted_disease = raw_disease
                        if not raw_disease.lower().startswith(crop_name.lower()) and "healthy" not in raw_disease.lower():
                            formatted_disease = f"{crop_name}_{raw_disease}"
                        elif "healthy" in raw_disease.lower() and not raw_disease.lower().startswith(crop_name.lower()):
                            formatted_disease = f"{crop_name}_Healthy"

                        xywhn = box.xywhn[0].tolist()
                        crop_dets.append({
                            "detected_class":    formatted_disease,
                            "confidence_score":  round(conf, 4),
                            "x_center":         round(xywhn[0], 4),
                            "y_center":         round(xywhn[1], 4),
                            "plant_class":      crop_name,
                            "parent_confidence": round(conf, 4),
                            "parent_model":     f"{crop_name} Specialist",
                            "model_name":       c_model_name,
                            "child_status":     "AWOKEN (IN MEMORY)",
                        })

                    # If disease lesions exist, filter out generic Healthy box
                    diseased_dets = [d for d in crop_dets if "healthy" not in d["detected_class"].lower()]
                    final_dets = diseased_dets if diseased_dets else crop_dets

                    if diseased_dets:
                        max_conf = max(d["confidence_score"] for d in diseased_dets)
                        logger.info(f"[Child Probe] '{crop_name}' detected disease with {max_conf*100:.1f}% confidence ({len(diseased_dets)} boxes).")
                        if max_conf > best_child_conf:
                            best_child_conf = max_conf
                            best_child_crop = crop_name
                            best_child_detections = final_dets

            # If a specialized child model confirmed disease, use it directly!
            if best_child_detections and best_child_conf >= 0.15:
                logger.info(f"[Two-Phase Pipeline] ✓ Child specialist winner: '{best_child_crop}' ({best_child_conf*100:.1f}%)")
                detections = best_child_detections
                crop_name = best_child_crop or "Crop"
            else:
                # Fall back to standard sequential cascade
                best = self._registry.cascade_classify(image_path)
                if best is None:
                    crop_name = candidate_crops[0][0] if candidate_crops else "Plant"
                    top_conf = candidate_crops[0][1] if candidate_crops else 0.50
                    parent_name = "Parent1"
                else:
                    crop_name = best["crop_name"]
                    top_conf = best["conf"]
                    parent_name = best["parent_model"]

                child_model = self._child_registry.get_child_model(crop_name, device)
                if child_model is None:
                    detections = [{
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
                else:
                    child_model_name = os.path.basename(getattr(child_model, "ckpt_path", f"{crop_name}_best.pt"))
                    child_results = child_model(image_path, device=device, conf=MIN_DISEASE_CONF, verbose=False)
                    detections = []
                    if child_results and len(child_results) > 0 and child_results[0].boxes:
                        c_res = child_results[0]
                        for box in c_res.boxes:
                            cls_idx = int(box.cls[0])
                            raw_disease = c_res.names.get(cls_idx, f"disease_{cls_idx}")
                            conf = float(box.conf[0])
                            if conf < MIN_DISEASE_CONF:
                                continue
                            
                            formatted_disease = raw_disease
                            if not raw_disease.lower().startswith(crop_name.lower()) and "healthy" not in raw_disease.lower():
                                formatted_disease = f"{crop_name}_{raw_disease}"
                            elif "healthy" in raw_disease.lower() and not raw_disease.lower().startswith(crop_name.lower()):
                                formatted_disease = f"{crop_name}_Healthy"

                            xywhn = box.xywhn[0].tolist()
                            detections.append({
                                "detected_class":    formatted_disease,
                                "confidence_score":  round(conf, 4),
                                "x_center":         round(xywhn[0], 4),
                                "y_center":         round(xywhn[1], 4),
                                "plant_class":      crop_name,
                                "parent_confidence": round(top_conf, 4),
                                "parent_model":     parent_name,
                                "model_name":       child_model_name,
                                "child_status":     "AWOKEN (IN MEMORY)",
                            })

                        # Filter out Healthy if diseased boxes exist
                        diseased_dets = [d for d in detections if "healthy" not in d["detected_class"].lower()]
                        if diseased_dets:
                            detections = diseased_dets

                    if not detections:
                        detections = [{
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

            # ── Groq VLM Visual Frame Audit Gate (Applies to Image, Video & Live UAV) ──
            from app.services.ai_service import _get_groq_key, VLMAuditService
            if _get_groq_key() and detections:
                top_det = detections[0]
                vis_audit = VLMAuditService.audit_image_frame(
                    image_path=image_path,
                    crop_candidate=crop_name,
                    detected_class=top_det["detected_class"],
                    confidence=top_det["confidence_score"],
                )
                if vis_audit.get("verdict") == "REJECTED" or not vis_audit.get("is_crop_leaf", True):
                    logger.info(f"[Groq Vision Gate] REJECTED non-plant frame: {vis_audit.get('reasoning')} — skipping frame.")
                    return []

                # Enrich verified detections
                for det in detections[:2]:
                    det["vlm_verdict"]   = vis_audit.get("verdict", "VERIFIED")
                    det["vlm_reasoning"] = vis_audit.get("reasoning", "")
                    det["pathogen_name"] = vis_audit.get("pathogen_name")
                    det["severity"]      = "HIGH" if "healthy" not in det["detected_class"].lower() else "LOW"
                    det["ai_audited"]    = True

            return detections

        except Exception as exc:
            logger.error(f"[Two-Phase Pipeline] Error during inference: {exc}", exc_info=True)
            return []


# ---------------------------------------------------------------------------
# Shared pipeline instance
# ---------------------------------------------------------------------------
pipeline = DiseaseDetectionPipeline()
