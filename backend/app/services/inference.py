import os
import logging
import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.inference")

# ---------------------------------------------------------------------------
# Path resolution: check root of backend/ first, then weights/ subfolder
# ---------------------------------------------------------------------------
_BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEIGHTS_DIR = os.path.join(_BASE_DIR, "weights")


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
# ModelRegistry — singleton that tracks load state across the app lifetime
# ---------------------------------------------------------------------------
class ModelRegistry:
    """
    Singleton registry.  Call `get()` to obtain the shared instance.
    Loads the parent model (best.pt) onto the best available device.
    """
    _instance: Optional["ModelRegistry"] = None

    def __init__(self):
        self.is_ready: bool        = False
        self.model_name: str       = "best.pt"
        self.loaded_at: Optional[str] = None
        self.device: str           = "cpu"
        self.model_task: str       = "unknown"  # 'classify' | 'detect' | 'segment'
        self._model                = None
        self._torch_available: bool = False
        self._mock_mode: bool      = False

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

    # ------------------------------------------------------------------
    def load(self, parent_model_filename: str = "best.pt") -> bool:
        """
        Loads the parent YOLO model onto the best available device (GPU first).
        Must be called once at application startup via the lifespan event.
        """
        self.model_name = parent_model_filename

        if not self._torch_available:
            logger.info(
                "[ModelRegistry] PyTorch/ultralytics not available — enabling Mock Mode."
            )
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

        # ── Detect best device ──────────────────────────────────────────
        self.device = _best_device()

        try:
            from ultralytics import YOLO
            logger.info(
                f"[ModelRegistry] Loading YOLO model: {model_path} → device={self.device}"
            )
            self._model     = YOLO(model_path)
            self.model_task = getattr(self._model, "task", "unknown")

            # Move model weights to the chosen device
            # YOLO's .to() propagates to the underlying torch module
            self._model.to(self.device)

            self.is_ready  = True
            self.loaded_at = datetime.datetime.utcnow().isoformat() + "Z"
            logger.info(
                f"[ModelRegistry] ✓ Model ready — "
                f"file={parent_model_filename}, task={self.model_task}, device={self.device}"
            )
            return True

        except Exception as exc:
            logger.error(
                f"[ModelRegistry] Failed to load '{model_path}': {exc}",
                exc_info=True,
            )
            self._mock_mode = True
            self.is_ready   = True
            self.loaded_at  = datetime.datetime.utcnow().isoformat() + "Z"
            return False

    # ------------------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "ready":           self.is_ready,
            "mock_mode":       self._mock_mode,
            "model_name":      self.model_name,
            "model_task":      self.model_task,
            "device":          self.device,
            "loaded_at":       self.loaded_at,
            "torch_available": self._torch_available,
        }


# ---------------------------------------------------------------------------
# DiseaseDetectionPipeline
# ---------------------------------------------------------------------------
class DiseaseDetectionPipeline:
    """
    Phase 1 — Parent model (best.pt): crop / disease classification.
    Phase 2 — Child models (per-crop specialists): disease detection (WIP).

    Supports both YOLO task types automatically:
      • task=classify → result.probs   (top-k class probabilities)
      • task=detect   → result.boxes   (bounding boxes + class + conf)
    """

    def __init__(self):
        self._registry = ModelRegistry.get()

    @property
    def is_loaded(self) -> bool:
        return self._registry.is_ready

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def run_inference(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Gate: returns [] if model is not ready, preventing ghost detections.
        """
        if not self._registry.is_ready:
            logger.warning("[Pipeline] Model not ready — returning empty result.")
            return []

        if self._registry._mock_mode or self._registry._model is None:
            return self._mock_results(image_path)

        task = self._registry.model_task
        if task == "classify":
            # Grid/Tiled classification!
            # Crop image into 4 quadrants (2x2 grid) and classify each individually
            try:
                from PIL import Image
                img = Image.open(image_path)
                width, height = img.size

                quadrants = [
                    ("Top-Left",     (0,          0,           width // 2,  height // 2), 0.25, 0.25),
                    ("Top-Right",    (width // 2, 0,           width,       height // 2), 0.75, 0.25),
                    ("Bottom-Left",  (0,          height // 2, width // 2,  height),      0.25, 0.75),
                    ("Bottom-Right", (width // 2, height // 2, width,       height),      0.75, 0.75),
                ]

                all_detections = []
                for label, box, rel_x, rel_y in quadrants:
                    cropped = img.crop(box)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_quad:
                        cropped.save(tmp_quad.name, "JPEG")
                        quad_path = tmp_quad.name

                    try:
                        quad_dets = self._real_inference(quad_path)
                        for det in quad_dets:
                            det["x_center"] = rel_x
                            det["y_center"] = rel_y
                            det["grid_zone"] = label
                        all_detections.extend(quad_dets)
                    except Exception as quad_err:
                        logger.error(f"[Pipeline] Quadrant {label} inference failed: {quad_err}")
                    finally:
                        if os.path.exists(quad_path):
                            os.unlink(quad_path)

                return all_detections
            except Exception as e:
                logger.error(f"[Pipeline] Grid crop inference failed: {e}", exc_info=True)
                return self._real_inference(image_path)

        return self._real_inference(image_path)

    # ------------------------------------------------------------------
    def _mock_results(self, image_path: str) -> List[Dict[str, Any]]:
        """Simulated detections for demo / mock-mode environments."""
        import random
        logger.info(f"[Mock] Simulating inference for: {image_path}")
        diseases = [
            "healthy", "powdery_mildew", "rust", "blight",
            "leaf_spot", "mosaic_virus", "anthracnose", "downy_mildew",
        ]
        
        # Return mock detections in different grid zones!
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

    # ------------------------------------------------------------------
    def _real_inference(self, image_path: str) -> List[Dict[str, Any]]:
        """
        Runs the YOLO model on the given image path.

        Handles two YOLO task types:
          • classify → returns top-5 class probabilities as individual detections
          • detect   → returns bounding-box detections above a confidence threshold
        """
        logger.info(
            f"[Real Inference] image={image_path} | "
            f"task={self._registry.model_task} | device={self._registry.device}"
        )
        try:
            # Run inference on the selected device
            results = self._registry._model(
                image_path,
                device=self._registry.device,
                verbose=False,
            )

            detections: List[Dict[str, Any]] = []

            for result in results:
                task = self._registry.model_task

                # ── CLASSIFY task ────────────────────────────────────────────
                if task == "classify" or (
                    hasattr(result, "probs") and result.probs is not None
                ):
                    probs = result.probs
                    names = result.names          # int → class name

                    if probs is None:
                        continue

                    # Extract top-5 class indices and their confidence scores
                    top5_indices = probs.top5      # list[int]  — top-5 class indices
                    top5_confs   = probs.top5conf  # Tensor     — top-5 confidence values

                    top_idx = int(top5_indices[0])
                    top_conf = float(top5_confs[0])
                    top_name = names.get(top_idx, "").lower().replace("_", "")

                    # Any prediction with confidence < 0.90 or background class is classified as notaleaf
                    if top_conf < 0.90 or top_name in ["notaleaf", "background", "unknown"]:
                        logger.info(f"[Real Inference] Top prediction '{top_name}' conf={top_conf:.2f} (<0.90) — classifying as 'notaleaf'.")
                        return [{
                            "detected_class":   "notaleaf",
                            "confidence_score": round(top_conf, 4),
                            "x_center":        0.5,
                            "y_center":        0.5,
                            "rank":            1,
                            "plant_class":     "notaleaf",
                            "model_name":      "best.pt",
                        }]

                    for rank, (cls_idx, conf_t) in enumerate(
                        zip(top5_indices, top5_confs)
                    ):
                        cls_name = names.get(int(cls_idx), f"class_{cls_idx}")
                        conf     = float(conf_t)

                        # Skip background classes
                        if cls_name.lower().replace("_", "") in ["notaleaf", "background", "unknown"]:
                            continue

                        # Only include results with meaningful confidence
                        if conf < 0.01:
                            continue

                        detections.append({
                            "detected_class":   cls_name if conf >= 0.90 else "notaleaf",
                            "confidence_score": round(conf, 4),
                            "x_center":        0.5,          # classification has no bbox
                            "y_center":        0.5,
                            "rank":            rank + 1,     # 1 = top prediction
                            "plant_class":     names.get(int(top5_indices[0]), "unknown"),
                            "model_name":      "best.pt",
                        })

                    logger.info(
                        f"[Real Inference] classify → top prediction: "
                        f"'{detections[0]['detected_class']}' "
                        f"({detections[0]['confidence_score']*100:.1f}%)"
                        if detections else "[Real Inference] classify → no probs returned"
                    )

                # ── DETECT task ──────────────────────────────────────────────
                else:
                    boxes = result.boxes
                    names = result.names

                    if boxes is None or len(boxes) == 0:
                        continue

                    for box in boxes:
                        cls_idx  = int(box.cls[0])
                        cls_name = names.get(cls_idx, f"class_{cls_idx}")
                        conf     = float(box.conf[0])

                        if conf < 0.25:   # filter low-confidence noise
                            continue

                        xywhn = box.xywhn[0].tolist()
                        detections.append({
                            "detected_class":   cls_name,
                            "confidence_score": round(conf, 4),
                            "x_center":        round(xywhn[0], 4),
                            "y_center":        round(xywhn[1], 4),
                            "plant_class":     cls_name,
                            "model_name":      "best.pt",
                        })

                    logger.info(
                        f"[Real Inference] detect → {len(detections)} box(es) found"
                    )

            return detections

        except Exception as exc:
            logger.error(f"[Pipeline] Inference error: {exc}", exc_info=True)
            return []


# ---------------------------------------------------------------------------
# Module-level convenience: shared pipeline instance
# ---------------------------------------------------------------------------
pipeline = DiseaseDetectionPipeline()
