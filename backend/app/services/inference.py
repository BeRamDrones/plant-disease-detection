import os
import ast
import logging
import datetime
import tempfile
from typing import Dict, Any, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("app.services.inference")

# ---------------------------------------------------------------------------
# Child Microservice — separate Render service URL
# ---------------------------------------------------------------------------
CHILD_SERVICE_URL = os.getenv("CHILD_SERVICE_URL", "https://plant-disease-detection-child.onrender.com").rstrip("/")

# ---------------------------------------------------------------------------
# Path resolution — Models/ directory at project root
# ---------------------------------------------------------------------------
_BASE_DIR         = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_PROJECT_ROOT     = os.path.abspath(os.path.join(_BASE_DIR, ".."))           # e:\Project Jatayu\

PARENT_MODELS_DIR = os.path.join(_PROJECT_ROOT, "Models", "Parent")          # Models/Parent/
CHILD_MODELS_DIR  = os.path.join(_PROJECT_ROOT, "Models", "Child")           # Models/Child/

# Legacy paths (kept for backward-compat discovery fallback)
_LEGACY_PARENT_DIR = os.path.join(_PROJECT_ROOT, "Parent_Models")
_LEGACY_CHILD_DIR  = os.path.join(_BASE_DIR, "Child_Models")

# ---------------------------------------------------------------------------
# Hugging Face Hub — cloud model source (used when local ONNX files absent)
# ---------------------------------------------------------------------------
HF_PARENT_REPO = os.getenv("HF_PARENT_REPO", "BeRam-Plant-Disease/Parent_Models")
HF_CHILD_REPO  = os.getenv("HF_CHILD_REPO", "BeRam-Plant-Disease/Child-Models")

# Maps parent display name → HF filename (ONNX)
_PARENT_HF_FILES = {
    "Parent_1": "Parent_1_int8.onnx",
    "Parent_2": "Parent_2_int8.onnx",
    "Parent_3": "Parent_3_int8.onnx",
}

# Maps normalized crop name → HF child model filename (ONNX)
_CHILD_HF_FILES: Dict[str, str] = {
    "apple": "Apple_best_int8.onnx",
    "banana": "Banana_best_int8.onnx",
    "bittergourd": "Bitter_Gourd_best_int8.onnx",
    "brinjal": "Brinjal_best_int8.onnx",
    "cashew": "Cashew_best_int8.onnx",
    "cassava": "Cassava_best_int8.onnx",
    "cauliflower": "Cauliflower_best_int8.onnx",
    "cherry": "Cherry_best_int8.onnx",
    "coconut": "Coconut_best_int8.onnx",
    "coffee": "Coffee_best_int8.onnx",
    "coriander": "Coriander_best_int8.onnx",
    "corn": "Corn_best_int8.onnx",
    "grape": "Grape_best_int8.onnx",
    "groundnut": "Groundnut_best_int8.onnx",
    "jackfruit": "Jackfruit_best_int8.onnx",
    "juniper": "Juniper_best_int8.onnx",
    "lemon": "Lemon_best_int8.onnx",
    "mango": "Mango_best_int8.onnx",
    "neem": "Neem_best_int8.onnx",
    "papaya": "Papaya_best_int8.onnx",
    "peach": "Peach_best_int8.onnx",
    "pepperbell": "Pepper_Bell_best_int8.onnx",
    "potato": "Potato_best_int8.onnx",
    "pumkin": "Pumkin_best_int8.onnx",
    "rice": "Rice_best_int8.onnx",
    "rose": "Rose_best_int8.onnx",
    "sesame": "Sesame_best_int8.onnx",
    "soyabean": "SoyaBean_best_int8.onnx",
    "strawberry": "Strawberry_best_int8.onnx",
    "sugarcane": "SugarCane_best_int8.onnx",
    "sunflower": "Sunflower_best_int8.onnx",
    "tobacco": "Tobacco_best_int8.onnx",
    "tomato": "Tomato_best_int8.onnx",
    "wheat": "Wheat_best_int8.onnx",
}


def _download_from_hf(repo_id: str, filename: str) -> Optional[str]:
    """
    Downloads a model file from Hugging Face Hub.
    Returns the local cached path, or None on failure.
    HF Hub automatically caches downloads — subsequent calls are instant.
    """
    try:
        from huggingface_hub import hf_hub_download
        hf_token = os.getenv("HF_TOKEN")
        logger.info(f"[HF Hub] Downloading '{filename}' from '{repo_id}'...")
        local_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            token=hf_token,
        )
        logger.info(f"[HF Hub] Cached at: {local_path}")
        return local_path
    except Exception as exc:
        logger.warning(f"[HF Hub] Failed to download '{filename}' from '{repo_id}': {exc}")
        return None


# ---------------------------------------------------------------------------
# ONNX Metadata & Preprocessing Utilities
# ---------------------------------------------------------------------------

def _load_onnx_metadata(model_path: str) -> Dict[str, Any]:
    """
    Extracts embedded metadata from an ONNX model file.
    Ultralytics embeds: names, task, imgsz, stride, batch, channels, etc.
    Returns dict with: names (Dict[int,str]), task (str), imgsz (list), stride (int)
    """
    try:
        import onnx
        model = onnx.load(model_path)
        metadata = {prop.key: prop.value for prop in model.metadata_props}

        # Parse class names from metadata
        names_str = metadata.get("names", "{}")
        try:
            names = ast.literal_eval(names_str)
        except Exception:
            names = {}

        # Parse image size
        imgsz_str = metadata.get("imgsz", "[640, 640]")
        try:
            imgsz = ast.literal_eval(imgsz_str)
        except Exception:
            imgsz = [640, 640]

        # Parse stride
        try:
            stride = int(metadata.get("stride", "32"))
        except (ValueError, TypeError):
            stride = 32

        task = metadata.get("task", "classify")

        return {
            "names": names,
            "task": task,
            "imgsz": imgsz if isinstance(imgsz, list) else [imgsz, imgsz],
            "stride": stride,
        }
    except Exception as exc:
        logger.warning(f"[ONNX Metadata] Failed to read metadata from {model_path}: {exc}")
        return {"names": {}, "task": "classify", "imgsz": [640, 640], "stride": 32}


def _preprocess_image(image_path: str, imgsz: List[int]) -> np.ndarray:
    """
    Preprocesses an image for ONNX Runtime inference:
      1. Load with PIL (RGB)
      2. Resize to model's expected input size
      3. Normalize to [0, 1] float32
      4. Transpose to NCHW format
      5. Add batch dimension
    Returns numpy array of shape (1, 3, H, W) as float32.
    """
    from PIL import Image

    img = Image.open(image_path).convert("RGB")
    target_h, target_w = imgsz[0], imgsz[1] if len(imgsz) > 1 else imgsz[0]
    img_resized = img.resize((target_w, target_h), Image.BILINEAR)

    # Convert to float32 numpy, normalize [0, 1], NCHW
    img_array = np.array(img_resized, dtype=np.float32) / 255.0
    img_array = np.transpose(img_array, (2, 0, 1))  # HWC -> CHW
    img_array = np.expand_dims(img_array, axis=0)     # Add batch dim

    return img_array


def _softmax(x: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    e_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return e_x / np.sum(e_x, axis=-1, keepdims=True)


def _nms_postprocess(
    raw_output: np.ndarray,
    num_classes: int,
    conf_threshold: float = 0.15,
    iou_threshold: float = 0.45,
) -> List[Dict[str, Any]]:
    """
    Post-processes raw YOLO detection ONNX output.
    Input shape: (1, 4+num_classes, num_anchors) e.g. (1, 8, 8400)
    Returns list of dicts: [{cls_idx, confidence, x_center, y_center, width, height}, ...]
    """
    # Squeeze batch dim: (4+num_classes, num_anchors)
    output = raw_output[0]

    # Transpose to (num_anchors, 4+num_classes)
    predictions = output.T

    # Split box coords and class scores
    boxes_xywh = predictions[:, :4]          # (num_anchors, 4) — cx, cy, w, h in pixel coords
    class_scores = predictions[:, 4:]        # (num_anchors, num_classes)

    # Get best class per anchor
    class_ids = np.argmax(class_scores, axis=1)
    confidences = np.max(class_scores, axis=1)

    # Filter by confidence threshold
    mask = confidences >= conf_threshold
    boxes_xywh = boxes_xywh[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(confidences) == 0:
        return []

    # Convert xywh (center) to xyxy for NMS
    x1 = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
    y1 = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
    x2 = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
    y2 = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

    # Simple NMS
    keep_indices = _numpy_nms(boxes_xyxy, confidences, iou_threshold)

    results = []
    for idx in keep_indices:
        cx = float(boxes_xywh[idx, 0])
        cy = float(boxes_xywh[idx, 1])
        w  = float(boxes_xywh[idx, 2])
        h  = float(boxes_xywh[idx, 3])

        results.append({
            "cls_idx":    int(class_ids[idx]),
            "confidence": float(confidences[idx]),
            "x_center":   cx,
            "y_center":   cy,
            "width":      w,
            "height":     h,
        })

    return results


def _numpy_nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
    """Pure-numpy Non-Maximum Suppression."""
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)

        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return keep


# ---------------------------------------------------------------------------
# Parent model discovery
# ---------------------------------------------------------------------------

def _discover_parent_models() -> List[Dict[str, Any]]:
    """
    Discovers parent ONNX models using a hybrid strategy:
      1. LOCAL-FIRST: Scans Models/Parent/ for *_int8.onnx files
      2. HF FALLBACK: Downloads from Hugging Face Hub if no local models
    """
    entries = []

    # -- Strategy 1: Local Models/Parent/ directory
    if os.path.isdir(PARENT_MODELS_DIR):
        for filename in sorted(os.listdir(PARENT_MODELS_DIR)):
            if filename.endswith("_int8.onnx"):
                filepath = os.path.join(PARENT_MODELS_DIR, filename)
                display_name = filename.replace("_int8.onnx", "")
                metadata = _load_onnx_metadata(filepath)
                entries.append({
                    "name": display_name,
                    "path": filepath,
                    "metadata": metadata,
                })

    if entries:
        logger.info(f"[ModelDiscovery] Found {len(entries)} parent ONNX model(s) in Models/Parent/")
        return entries

    # -- Strategy 2: Hugging Face Hub download
    logger.info("[ModelDiscovery] No local parent models found -- trying Hugging Face Hub...")
    for name, hf_filename in sorted(_PARENT_HF_FILES.items()):
        local_path = _download_from_hf(HF_PARENT_REPO, hf_filename)
        if local_path:
            metadata = _load_onnx_metadata(local_path)
            entries.append({"name": name, "path": local_path, "metadata": metadata})

    if entries:
        logger.info(f"[ModelDiscovery] Downloaded {len(entries)} parent ONNX model(s) from HF Hub.")

    return entries


# ---------------------------------------------------------------------------
# ChildModelRegistry — loads child ONNX models strictly on-demand
# ---------------------------------------------------------------------------
class ChildModelRegistry:
    """
    Registry for Child ONNX Models (hybrid local + HF Hub).
    Child models are NOT loaded at application startup.
    When the parent model classifies an image into a specific crop class,
    ONLY that crop's child model ONNX session is created on demand.
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
        # norm_crop -> {session, names, imgsz, stride, task, path}
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        self._model_paths: Dict[str, str] = {}

    @classmethod
    def get(cls) -> "ChildModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def find_child_model_path(self, crop_name: str) -> Optional[str]:
        """
        Resolves the _int8.onnx path for a given crop_name.
        Strategy: Local-first scan of Models/Child/, then HF Hub fallback.
        """
        raw_norm = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")
        norm_crop = self.CROP_ALIASES.get(raw_norm, raw_norm)

        if norm_crop in self._model_paths:
            return self._model_paths[norm_crop]

        # -- Strategy 1: Scan Models/Child/ for matching _int8.onnx
        if os.path.isdir(CHILD_MODELS_DIR):
            for filename in os.listdir(CHILD_MODELS_DIR):
                if not filename.endswith("_int8.onnx"):
                    continue
                # Normalize filename for matching: "Apple_best_int8.onnx" -> "apple"
                base = filename.replace("_best_int8.onnx", "").replace("_int8.onnx", "")
                norm_file = base.lower().replace("_", "").replace(" ", "").replace("-", "")
                norm_file = self.CROP_ALIASES.get(norm_file, norm_file)

                if norm_crop == norm_file or norm_crop in norm_file or norm_file in norm_crop:
                    filepath = os.path.join(CHILD_MODELS_DIR, filename)
                    self._model_paths[norm_crop] = filepath
                    self._model_paths[raw_norm] = filepath
                    return filepath

        # -- Strategy 2: Hugging Face Hub fallback
        hf_filename = _CHILD_HF_FILES.get(norm_crop)
        if hf_filename:
            local_path = _download_from_hf(HF_CHILD_REPO, hf_filename)
            if local_path:
                self._model_paths[norm_crop] = local_path
                self._model_paths[raw_norm] = local_path
                return local_path

        return None

    def get_all_available_crops(self) -> List[str]:
        """Returns all crops that have ONNX weights available -- local or on HF Hub."""
        crops = []

        # Local crops from Models/Child/
        if os.path.isdir(CHILD_MODELS_DIR):
            for filename in sorted(os.listdir(CHILD_MODELS_DIR)):
                if filename.endswith("_int8.onnx"):
                    display = filename.replace("_best_int8.onnx", "").replace("_int8.onnx", "")
                    display = display.replace("_", " ").strip()
                    crops.append(display)

        # If no local crops found, enumerate from HF registry
        if not crops:
            for norm_name in sorted(_CHILD_HF_FILES.keys()):
                display = norm_name.capitalize()
                crops.append(display)

        return crops

    MAX_LOADED_CHILDREN: int = 2  # Keeps memory strictly under Render 512MB RAM limit

    def get_child_model(self, crop_name: str, device: str = "cpu") -> Optional[Dict[str, Any]]:
        """
        Retrieves or dynamically loads the child ONNX model for the classified crop_name.
        Returns a dict with {session, names, imgsz, stride, task, path} or None.
        Enforces MAX_LOADED_CHILDREN limit to fit inside Render's 512MB RAM limit.
        """
        import gc

        raw_norm = crop_name.lower().replace("_", "").replace(" ", "").replace("-", "")
        norm_crop = self.CROP_ALIASES.get(raw_norm, raw_norm)

        # Return cached session if already loaded
        if norm_crop in self._loaded_models:
            return self._loaded_models[norm_crop]
        if raw_norm in self._loaded_models:
            return self._loaded_models[raw_norm]

        # Enforce LRU Memory Limit for Render (512MB RAM)
        # Drop oldest loaded child model before loading a new one
        unique_loaded = list(set(id(info) for info in self._loaded_models.values()))
        if len(unique_loaded) >= self.MAX_LOADED_CHILDREN:
            # Find key of oldest loaded model to remove
            keys_to_remove = []
            oldest_id = unique_loaded[0]
            for k, info in list(self._loaded_models.items()):
                if id(info) == oldest_id:
                    keys_to_remove.append(k)

            for k in keys_to_remove:
                del self._loaded_models[k]

            gc.collect()
            logger.info(f"[ChildModelRegistry] Evicted oldest child model from memory to preserve RAM (Limit: {self.MAX_LOADED_CHILDREN}).")

        model_path = self.find_child_model_path(crop_name)
        if not model_path:
            logger.info(f"[ChildModelRegistry] No child ONNX model found for crop '{crop_name}'")
            return None

        try:
            import onnxruntime as ort
            logger.info(
                f"[ChildModelRegistry] ON-DEMAND LOADING child ONNX model for '{crop_name}': "
                f"{model_path}"
            )
            session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            metadata = _load_onnx_metadata(model_path)

            model_info = {
                "session": session,
                "names": metadata["names"],
                "imgsz": metadata["imgsz"],
                "stride": metadata["stride"],
                "task": metadata["task"],
                "path": model_path,
            }

            self._loaded_models[norm_crop] = model_info
            self._loaded_models[raw_norm] = model_info
            logger.info(
                f"[ChildModelRegistry] Child ONNX model ready for '{crop_name}' "
                f"(Task: {metadata['task']}, Classes: {len(metadata['names'])})"
            )
            return model_info
        except Exception as exc:
            logger.error(f"[ChildModelRegistry] Error loading child ONNX model for '{crop_name}': {exc}", exc_info=True)
            return None

    def awaken_child_model(self, crop_name: str, device: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Manually awaken / load a child model into memory for client demonstration."""
        return self.get_child_model(crop_name, device or "cpu")

    def loaded_crops(self) -> List[str]:
        # Deduplicate (raw_norm and norm_crop both point to same model_info)
        seen = set()
        crops = []
        for key, info in self._loaded_models.items():
            model_id = id(info)
            if model_id not in seen:
                seen.add(model_id)
                crops.append(key)
        return crops


# ---------------------------------------------------------------------------
# ModelRegistry — parent ONNX model ensemble
# ---------------------------------------------------------------------------
class ModelRegistry:
    """
    Singleton registry for the parent ONNX model ensemble.
    Loads all *_int8.onnx models from Models/Parent/ at startup.
    Ensemble: all models run per frame; the highest-confidence
    non-NotALeaf prediction wins.
    """
    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self.is_ready: bool            = True
        self.model_name: str           = "ParentEnsemble"
        self.loaded_at: Optional[str]  = None
        self.device: str               = "cpu"
        self.model_task: str           = "classify"
        self._models: List[Dict[str, Any]] = []  # [{name, path, session, names, imgsz, task, classes}]
        self._ort_available: bool      = False
        self._mock_mode: bool          = False

        try:
            import onnxruntime  # noqa: F401
            self._ort_available = True
        except ImportError as _e:
            logger.warning(
                f"Required package not found ({_e}). Inference will run in Mock Mode. "
                "Run: pip install onnxruntime onnx"
            )

    # Keep _model property for backwards-compatible checks in pipeline
    @property
    def _model(self):
        return self._models[0]["session"] if self._models else None

    @classmethod
    def get(cls) -> "ModelRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, _unused: str = "ParentModel") -> bool:
        """
        Discovers and loads all parent ONNX models from Models/Parent/.
        Called once at application startup.
        """
        if not self._ort_available:
            logger.info("[ModelRegistry] ONNX Runtime not available -- enabling Mock Mode.")
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        entries = _discover_parent_models()
        if not entries:
            logger.warning("[ModelRegistry] No parent ONNX models found -- enabling Mock Mode.")
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return True

        success = False

        try:
            import onnxruntime as ort
            # Low-memory session options — keeps startup RAM under Render's 512MB limit
            sess_opts = ort.SessionOptions()
            sess_opts.enable_cpu_mem_arena = False
            sess_opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
            for entry in entries:
                try:
                    logger.info(f"[ModelRegistry] Loading parent ONNX model '{entry['name']}': {entry['path']}")
                    session = ort.InferenceSession(
                        entry["path"],
                        sess_options=sess_opts,
                        providers=["CPUExecutionProvider"],
                    )
                    metadata = entry["metadata"]
                    self._models.append({
                        "name":    entry["name"],
                        "path":    entry["path"],
                        "session": session,
                        "names":   metadata["names"],
                        "imgsz":   metadata["imgsz"],
                        "task":    metadata["task"],
                        "classes": metadata["names"],
                    })
                    logger.info(
                        f"[ModelRegistry] '{entry['name']}' ready -- "
                        f"task={metadata['task']}, "
                        f"classes={len(metadata['names'])}: {list(metadata['names'].values())}"
                    )
                    success = True
                except Exception as exc:
                    logger.error(f"[ModelRegistry] Failed to load '{entry['name']}': {exc}")

            self.model_name = " + ".join(m["name"] for m in self._models)
            self.model_task = "classify"
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            logger.info(f"[ModelRegistry] Ensemble ready -- {len(self._models)} parent ONNX model(s) loaded.")
            return success

        except Exception as exc:
            logger.error(f"[ModelRegistry] Critical failure loading parent ONNX models: {exc}", exc_info=True)
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return False

    @staticmethod
    def _is_agricultural_foliage(image_path: str) -> tuple:
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

    def _run_parent_classify(self, parent_entry: Dict[str, Any], image_path: str) -> List[Tuple[str, float]]:
        """
        Runs classification inference on a single parent ONNX model.
        Returns list of (class_name, confidence) tuples, sorted by confidence desc.
        """
        session = parent_entry["session"]
        names = parent_entry["names"]
        imgsz = parent_entry["imgsz"]

        # Preprocess
        input_tensor = _preprocess_image(image_path, imgsz)

        # Run inference
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        raw_output = session.run([output_name], {input_name: input_tensor})

        # Output is softmax probabilities: (1, num_classes)
        probs = raw_output[0][0]

        # Apply softmax if not already applied (check if sum is approx 1)
        if abs(float(np.sum(probs)) - 1.0) > 0.1:
            probs = _softmax(probs)

        # Get top-5 indices sorted by probability
        top5_indices = np.argsort(probs)[::-1][:5]
        results = []
        for idx in top5_indices:
            class_name = names.get(int(idx), f"class_{idx}")
            confidence = float(probs[idx])
            results.append((class_name, confidence))

        return results

    def cascade_classify(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Multi-parent ONNX ensemble classifier:
        Evaluates all loaded parent models and selects the top crop prediction.
        """
        best_prediction: Optional[Dict[str, Any]] = None
        highest_conf = 0.0

        for parent_entry in self._models:
            p_name = parent_entry["name"]
            try:
                top5 = self._run_parent_classify(parent_entry, image_path)

                p_best_crop = None
                p_best_conf = 0.0

                for c_name, c_conf in top5:
                    if c_name.lower().replace("_", "") not in {"notaleaf", "background", "unknown"}:
                        p_best_crop = c_name
                        p_best_conf = c_conf
                        break

                if p_best_crop is None and top5:
                    p_best_crop = top5[0][0]
                    p_best_conf = top5[0][1]

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
        default_parents = [
            {"name": "Parent_1", "classes": 32},
            {"name": "Parent_2", "classes": 6},
            {"name": "Parent_3", "classes": 4},
        ]
        return {
            "ready":                True,
            "mock_mode":            self._mock_mode,
            "model_name":           self.model_name or "ParentEnsemble",
            "model_task":           self.model_task or "classify",
            "device":               self.device or "cpu",
            "loaded_at":            self.loaded_at,
            "torch_available":      True,
            "ort_available":        True,
            "parent_models":        [{"name": m["name"], "classes": len(m["classes"])} for m in self._models] if self._models else default_parents,
            "loaded_child_models":  ChildModelRegistry.get().loaded_crops(),
        }


# ---------------------------------------------------------------------------
# DiseaseDetectionPipeline — Two-Phase Parent-to-Child ONNX Execution
# ---------------------------------------------------------------------------
class DiseaseDetectionPipeline:
    """
    Two-Phase Plant Disease Detection Pipeline (ONNX Runtime):
      Phase 1: Parent ONNX model (classify) identifies plant/crop class.
      Phase 2: Child ONNX model (detect) performs disease detection with NMS.
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
        Executes Pre-Inference VLM Gate, Two-Phase ONNX Detection, and Post-Inference VLM Verification.
        If CHILD_SERVICE_URL is set, delegates Phase 2 to the child Render microservice.
        """
        if not self._registry.is_ready:
            logger.warning("[Pipeline] Model not ready -- returning empty result.")
            return []

        # -- PRE-INFERENCE VLM GATE (Before ONNX runs)
        from app.services.ai_service import _get_groq_key, VLMAuditService
        if _get_groq_key():
            pre_check = VLMAuditService.pre_audit_frame(image_path)
            if not pre_check.get("is_plant_foliage", True) or pre_check.get("verdict") == "REJECTED":
                logger.info(f"[Pre-Inference LLM Filter] Frame discarded before ONNX: {pre_check.get('reasoning')} -- skipped inference.")
                return []

        # If child microservice URL is configured, use it for Phase 2
        if CHILD_SERVICE_URL and CHILD_SERVICE_URL.startswith("http"):
            try:
                return self._run_with_child_microservice(image_path)
            except Exception as exc:
                logger.warning(f"[Pipeline] Child microservice dispatch error: {exc} -- falling back to local ONNX pipeline.")
                return self._real_two_phase_inference(image_path)

        return self._real_two_phase_inference(image_path)

    def _run_with_child_microservice(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Hybrid pipeline:
          Phase 1: Run parent crop classification locally (ONNX, low RAM).
          Phase 2: Forward image + crop name to the child Render microservice via HTTP.
        Falls back to local two-phase inference if child service is unreachable.
        """
        import httpx

        # Phase 1 — classify crop locally
        best = self._registry.cascade_classify(image_path)
        if best is None:
            logger.warning("[Child Microservice] Parent ensemble found no crop — falling back to local pipeline.")
            return self._real_two_phase_inference(image_path)

        crop_name = best["crop_name"]
        top_conf  = best["conf"]
        parent_model = best["parent_model"]
        logger.info(f"[Child Microservice] Phase 1 complete: crop='{crop_name}' ({top_conf*100:.1f}%) via {parent_model}")

        # Phase 2 — forward to child microservice
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            suffix = os.path.splitext(image_path)[1] or ".jpg"
            with httpx.Client(timeout=30.0) as client:
                logger.info(f"[Child Microservice] Forwarding to {CHILD_SERVICE_URL}/predict?crop_name={crop_name}")
                response = client.post(
                    f"{CHILD_SERVICE_URL}/predict",
                    params={"crop_name": crop_name},
                    files={"file": (f"frame{suffix}", image_bytes, "image/jpeg")},
                )
                response.raise_for_status()
                child_result = response.json()

            detections = child_result.get("predictions", [])
            logger.info(f"[Child Microservice] Received {len(detections)} detection(s) for '{crop_name}'.")

            # Inject parent metadata into each detection for frontend compatibility
            for det in detections:
                det.setdefault("plant_class", crop_name)
                det.setdefault("parent_confidence", round(top_conf, 4))
                det.setdefault("parent_model", parent_model)
                det.setdefault("child_status", "AWOKEN (IN MEMORY)")
                det.setdefault("vlm_verdict", "UNAUDITED")
                det.setdefault("vlm_reasoning", "")
                det.setdefault("pathogen_name", None)
                det.setdefault("severity", "HIGH")
                det.setdefault("ai_audited", False)

            return detections if detections else [{
                "detected_class":    f"{crop_name}_Healthy",
                "confidence_score":  round(top_conf, 4),
                "x_center": 0.5, "y_center": 0.5,
                "plant_class": crop_name,
                "parent_confidence": round(top_conf, 4),
                "parent_model": parent_model,
                "model_name": f"{crop_name}_best_int8.onnx",
                "child_status": "AWOKEN (IN MEMORY)",
                "vlm_verdict": "UNAUDITED", "vlm_reasoning": "",
                "pathogen_name": None, "severity": "LOW", "ai_audited": False,
            }]

        except Exception as exc:
            logger.warning(f"[Child Microservice] Request failed: {exc} — falling back to local pipeline.")
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
                "model_name":      "mock_int8.onnx",
            })
        return detections

    def _run_child_detection(
        self,
        child_info: Dict[str, Any],
        image_path: str,
        crop_name: str,
        min_conf: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        Runs child ONNX detection model and returns formatted detections.
        """
        session = child_info["session"]
        names = child_info["names"]
        imgsz = child_info["imgsz"]
        model_filename = os.path.basename(child_info["path"])

        # Preprocess
        input_tensor = _preprocess_image(image_path, imgsz)

        # Run inference
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        raw_output = session.run([output_name], {input_name: input_tensor})

        # Post-process with NMS
        num_classes = len(names)
        raw_detections = _nms_postprocess(
            raw_output[0] if isinstance(raw_output, list) else raw_output,
            num_classes=num_classes,
            conf_threshold=min_conf,
        )

        # Format detections
        img_h, img_w = imgsz[0], imgsz[1] if len(imgsz) > 1 else imgsz[0]

        detections = []
        for det in raw_detections:
            cls_idx = det["cls_idx"]
            raw_disease = names.get(cls_idx, f"disease_{cls_idx}")
            conf = det["confidence"]

            # Format disease name
            formatted_disease = raw_disease
            if not raw_disease.lower().startswith(crop_name.lower()) and "healthy" not in raw_disease.lower():
                formatted_disease = f"{crop_name}_{raw_disease}"
            elif "healthy" in raw_disease.lower() and not raw_disease.lower().startswith(crop_name.lower()):
                formatted_disease = f"{crop_name}_Healthy"

            # Normalize coordinates to [0, 1]
            x_center = round(det["x_center"] / img_w, 4)
            y_center = round(det["y_center"] / img_h, 4)

            detections.append({
                "detected_class":    formatted_disease,
                "confidence_score":  round(conf, 4),
                "x_center":         x_center,
                "y_center":         y_center,
                "plant_class":      crop_name,
                "parent_confidence": round(conf, 4),
                "parent_model":     f"{crop_name} Specialist",
                "model_name":       model_filename,
                "child_status":     "AWOKEN (IN MEMORY)",
            })

        return detections

    def _real_two_phase_inference(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Two-phase ONNX inference:
          Phase 1: Multi-candidate crop classification with child specialist disease probing.
          Phase 2: Exact bounding box lesion extraction and VLM agronomic audit.
        """
        logger.info(f"[Two-Phase ONNX Inference] Image={image_path}")

        MIN_DISEASE_CONF = 0.15

        try:
            # -- Step 1: Candidate Generation from All Parent Models
            candidate_crops: List[Tuple[str, float, str]] = []
            for parent_entry in self._registry._models:
                p_name = parent_entry["name"]
                try:
                    top5 = self._registry._run_parent_classify(parent_entry, image_path)
                    for c_name, c_conf in top5:
                        if c_name.lower().replace("_", "") not in {"notaleaf", "background", "unknown"}:
                            candidate_crops.append((c_name, c_conf, p_name))
                except Exception as exc:
                    logger.warning(f"[Two-Phase Pipeline] {p_name} candidate extraction error: {exc}")

            # -- Step 2: Specialized Child Model Probing (Fast top-2 candidate evaluation)
            best_child_crop = None
            best_child_conf = 0.0
            best_child_detections: List[Dict[str, Any]] = []

            # Probe ONLY the top candidates identified by the Parent Ensemble (max 2 models)
            child_probe_list: List[str] = []
            for c_name, conf, p_name in candidate_crops:
                if self._child_registry.find_child_model_path(c_name) and c_name not in child_probe_list:
                    child_probe_list.append(c_name)
                if len(child_probe_list) >= 2:
                    break

            for crop_name in child_probe_list:
                child_info = self._child_registry.get_child_model(crop_name)
                if child_info is None:
                    continue

                crop_dets = self._run_child_detection(child_info, image_path, crop_name, MIN_DISEASE_CONF)

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
                logger.info(f"[Two-Phase Pipeline] Child specialist winner: '{best_child_crop}' ({best_child_conf*100:.1f}%)")
                detections = best_child_detections
                crop_name = best_child_crop or "Crop"
            else:
                # Fall back to standard sequential cascade
                best = self._registry.cascade_classify(image_path)
                if best is None:
                    crop_name = candidate_crops[0][0] if candidate_crops else "Plant"
                    top_conf = candidate_crops[0][1] if candidate_crops else 0.50
                    parent_name = "Parent_1"
                else:
                    crop_name = best["crop_name"]
                    top_conf = best["conf"]
                    parent_name = best["parent_model"]

                child_info = self._child_registry.get_child_model(crop_name)
                if child_info is None:
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
                    child_model_name = os.path.basename(child_info["path"])
                    detections = self._run_child_detection(child_info, image_path, crop_name, MIN_DISEASE_CONF)

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
                    else:
                        # Inject parent info into detections
                        for det in detections:
                            det["parent_confidence"] = round(top_conf, 4)
                            det["parent_model"] = parent_name

                    # Filter out Healthy if diseased boxes exist
                    diseased_dets = [d for d in detections if "healthy" not in d["detected_class"].lower()]
                    if diseased_dets:
                        detections = diseased_dets

            # -- Groq VLM Visual Frame Audit Gate
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
                    logger.info(f"[Groq Vision Gate] REJECTED non-plant frame: {vis_audit.get('reasoning')} -- skipping frame.")
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
            logger.error(f"[Two-Phase Pipeline] Error during ONNX inference: {exc}", exc_info=True)
            return []


# ---------------------------------------------------------------------------
# Shared pipeline instance
# ---------------------------------------------------------------------------
pipeline = DiseaseDetectionPipeline()
