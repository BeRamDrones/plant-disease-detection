"""
Project Jatayu — Two-Stage AI Pipeline

Stage 1 │ Real-Time VLM Audit        │ Groq: qwen/qwen3-32b
        │ Trigger: per key detection  │ Validates YOLO output w/ reasoning
        │
Stage 2 │ Post-Mission Report Engine  │ Groq: llama-3.1-8b-instant
        │ Trigger: mission end (1x)   │ Full Farm Field Report JSON + PDF
"""

import os
import re
import json
import logging
import urllib.request
from typing import Dict, Any, List, Optional

logger = logging.getLogger("app.services.ai_service")

GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"


ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ─────────────────────────────────────────────────────────────────────────────
# Env helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_env_dict(path: str) -> Dict[str, str]:
    res: Dict[str, str] = {}
    if not os.path.exists(path):
        return res
    try:
        from dotenv import dotenv_values
        vals = dotenv_values(path)
        for k, v in vals.items():
            if v is not None and str(v).strip():
                res[k] = str(v).strip()
    except Exception:
        pass

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and v and k not in res:
                        res[k] = v
    except Exception:
        pass
    return res

def _get_groq_key() -> str:
    """Reads Groq API key dynamically from backend/.env, project .env, or system environment variables."""
    key_names = ["GROQ_API_KEY", "GROQ_KEY", "QWEN_API_KEY", "GROQ_VLM_KEY", "GROQ_VISION_KEY", "QWEN_KEY", "GROQ_APIKEY", "GROQ_QWEN_KEY"]

    # 1. Check system / process environment variables
    for k in key_names:
        val = os.getenv(k, "").strip()
        if val:
            return val

    # 2. Check backend/.env and root .env files
    search_paths = [
        ENV_PATH,
        os.path.join(os.path.dirname(ENV_PATH), "..", ".env"),
        os.path.join(os.path.dirname(ENV_PATH), "..", ".env.local"),
        os.path.join(os.path.dirname(ENV_PATH), ".env.local"),
    ]
    for env_path in search_paths:
        vals = _read_env_dict(env_path)
        for k in key_names:
            if vals.get(k):
                return vals[k]
    return ""

def set_groq_key(key: str) -> bool:
    clean_key = key.strip()
    os.environ["GROQ_API_KEY"] = clean_key
    _persist_env({"GROQ_API_KEY": clean_key})
    logger.info(f"[AIService] GROQ_API_KEY updated (length: {len(clean_key)})")
    return True

def _get_vlm_model() -> str:
    vals = _read_env_dict(ENV_PATH)
    if vals.get("GROQ_VLM_MODEL"):
        return vals["GROQ_VLM_MODEL"]
    return os.getenv("GROQ_VLM_MODEL", "qwen/qwen3.6-27b").strip()

def _get_report_model() -> str:
    vals = _read_env_dict(ENV_PATH)
    if vals.get("GROQ_REPORT_MODEL"):
        return vals["GROQ_REPORT_MODEL"]
    return os.getenv("GROQ_REPORT_MODEL", "llama-3.1-8b-instant").strip()

def _persist_env(updates: Dict[str, str]) -> None:
    try:
        lines: List[str] = []
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

        found = {k: False for k in updates}
        new_lines = []
        for line in lines:
            replaced = False
            for k, v in updates.items():
                if line.startswith(k + "=") or line.startswith(k + " "):
                    new_lines.append(f'{k}="{v}"\n')
                    found[k] = True
                    replaced = True
                    break
            if not replaced:
                new_lines.append(line)

        for k, v in updates.items():
            if not found[k]:
                new_lines.append(f'{k}="{v}"\n')

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning(f"[AIService] .env persist failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Core Groq caller (OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────

def _groq_chat(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 1024,
    timeout: int = 25,
) -> Optional[str]:
    """Single Groq chat completion call."""
    key = _get_groq_key()
    if not key:
        logger.warning("[AIService] GROQ_API_KEY not set — skipping AI call.")
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.15,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        req = urllib.request.Request(
            GROQ_BASE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        logger.warning(f"[AIService] Groq HTTP {e.code}: {body[:300]}")
    except Exception as e:
        logger.warning(f"[AIService] Groq call failed: {e}")
    return None


import base64
import time
import io
from PIL import Image

def _optimize_image_for_vlm(image_bytes: bytes, max_dim: int = 480) -> bytes:
    """Downscales image to max_dim and compresses as JPEG to reduce vision tokens and avoid rate limits."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("RGB")
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75, optimize=True)
            return buf.getvalue()
    except Exception:
        return image_bytes

def _groq_vision_chat(
    model: str,
    system: str,
    user_prompt: str,
    image_bytes: bytes,
    max_tokens: int = 256,
    timeout: int = 15,
) -> Optional[str]:
    """Groq vision chat completion call with optimized base64 image."""
    key = _get_groq_key()
    if not key:
        return None

    opt_bytes = _optimize_image_for_vlm(image_bytes, max_dim=480)
    b64_str = base64.b64encode(opt_bytes).decode("utf-8")
    vision_model = model if (model and model.strip()) else _get_vlm_model()

    payload = {
        "model": vision_model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_str}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }

    try:
        req = urllib.request.Request(
            GROQ_BASE_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        logger.warning(f"[AIService] Groq Vision HTTP {e.code}: {err_body[:200]}")
    except Exception as e:
        logger.warning(f"[AIService] Groq Vision call error: {e}")
    return None


def _parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Strips thinking tags, markdown fences, and extracts/parses JSON robustly."""
    if not text:
        return None

    # 1. Remove <think>...</think> blocks if present
    clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # 2. Try direct load after stripping markdown fences
    candidate = clean
    for prefix in ("```json", "```JSON", "```"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
    if candidate.endswith("```"):
        candidate = candidate[:-3]
    candidate = candidate.strip()

    try:
        return json.loads(candidate)
    except Exception:
        pass

    # 3. Search for json markdown block ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, flags=re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # 4. Search for outer-most { ... }
    first_brace = clean.find("{")
    last_brace = clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = clean[first_brace:last_brace + 1]
        try:
            return json.loads(json_str)
        except Exception:
            pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Real-Time VLM Audit  (llama-3.2-11b-vision-preview / qwen)
# ─────────────────────────────────────────────────────────────────────────────

class VLMAuditService:
    """
    MODEL 1: Real-Time VLM Audit
    Audits YOLO model detections using Groq Vision to reject non-plant scenes
    (faces, rooms, walls) and verify genuine plant pathology.
    """

    SYSTEM_PROMPT = (
        "You are an expert plant pathologist and computer vision auditor for Project Jatayu UAV. "
        "Your role is to verify YOLO model detections with scientific agronomic reasoning. "
        "Be concise, decisive, and output only valid JSON."
    )

    _last_pre_audit_time: float = 0.0
    _cached_pre_audit: Optional[Dict[str, Any]] = None

    @classmethod
    def pre_audit_frame(cls, image_path: str) -> Dict[str, Any]:
        """
        PRE-INFERENCE VLM GATE (Before YOLO runs):
        Visually inspects the camera frame to verify if genuine agricultural plant foliage exists.
        Immediately rejects:
          - Synthetic screens, text canvases, mock UI, error messages
          - Human faces, indoor rooms, walls, floors, keyboards, clothing
          - Non-agricultural objects and non-plant backgrounds
        """
        key = _get_groq_key()
        if not key:
            return {"is_plant_foliage": True, "verdict": "PASSED", "ai_audited": False}

        now = time.time()
        if now - cls._last_pre_audit_time < 1.5 and cls._cached_pre_audit is not None:
            return cls._cached_pre_audit

        try:
            with open(image_path, "rb") as f:
                img_data = f.read()

            system_prompt = (
                "You are an expert plant pathologist and autonomous UAV vision gatekeeper for Project Jatayu. "
                "Your role is to strictly inspect camera frames and REJECT any non-agricultural or non-plant scenes: "
                "such as computer screens, UI mockups, text canvases, error screens, indoor rooms, walls, furniture, "
                "people, clothing, vehicles, or artificial objects. "
                "You MUST only allow genuine living agricultural plant foliage, crop fields, or plant leaves to proceed. "
                "Output valid JSON only."
            )

            user_prompt = """Inspect this camera frame:
Does this image contain genuine living agricultural plant foliage, crop leaves, or a plant canopy?

Respond strictly in this JSON format:
{
  "is_plant_foliage": false,
  "verdict": "REJECTED",
  "reasoning": "<1-sentence concise description of what is visible in the frame>"
}"""

            raw = _groq_vision_chat(_get_vlm_model(), system_prompt, user_prompt, img_data, max_tokens=150)
            if raw:
                parsed = _parse_json_response(raw)
                if parsed:
                    is_leaf = bool(parsed.get("is_plant_foliage", False))
                    v_str = str(parsed.get("verdict", "")).upper()
                    if "REJECT" in v_str or not is_leaf:
                        is_leaf = False
                        verdict = "REJECTED"
                    else:
                        verdict = "VERIFIED"

                    res = {
                        "is_plant_foliage": is_leaf,
                        "verdict": verdict,
                        "reasoning": parsed.get("reasoning", ""),
                        "ai_audited": True,
                    }
                    cls._last_pre_audit_time = now
                    cls._cached_pre_audit = res
                    logger.info(f"[Pre-YOLO VLM Gate] verdict={verdict}, is_leaf={is_leaf}, reason={parsed.get('reasoning')}")
                    return res
        except Exception as exc:
            logger.warning(f"[Pre-YOLO VLM Gate] Error: {exc}")

        return {"is_plant_foliage": True, "verdict": "PASSED", "ai_audited": False}

    @classmethod
    def post_verify_detection(
        cls,
        image_path: str,
        crop: str,
        detected_class: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """
        POST-INFERENCE VLM VERIFICATION (After YOLO runs):
        Evaluates the YOLO crop & disease detection with Groq Vision.
        Verifies clinical symptom presence, determines scientific pathogen name,
        and assigns severity.
        """
        key = _get_groq_key()
        if not key:
            return {"verdict": "UNAUDITED", "pathogen_name": None, "severity": "MODERATE", "ai_audited": False}

        try:
            with open(image_path, "rb") as f:
                img_data = f.read()

            system_prompt = (
                "You are a Senior Plant Pathologist for Project Jatayu. "
                "Your role is to verify the YOLO crop species and disease classification against the actual leaf evidence in the frame. "
                "Provide clinical agronomic verification in valid JSON only."
            )

            user_prompt = f"""Verify this detection on the camera frame:
YOLO Plant Species : {crop}
YOLO Classification: {detected_class}
YOLO Confidence    : {confidence * 100:.1f}%

Respond strictly in this JSON format:
{{
  "verdict": "VERIFIED" | "REJECTED" | "UNCERTAIN",
  "pathogen_name": "<scientific pathogen name if diseased, e.g. Mycosphaerella fijiensis, or 'Healthy Foliage'>",
  "severity": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",
  "reasoning": "<1-sentence clinical justification>"
}}"""

            raw = _groq_vision_chat(_get_vlm_model(), system_prompt, user_prompt, img_data)
            if raw:
                parsed = _parse_json_response(raw)
                if parsed:
                    verdict = str(parsed.get("verdict", "VERIFIED")).upper()
                    logger.info(f"[Post-YOLO VLM Audit] verdict={verdict}, pathogen={parsed.get('pathogen_name')}, reason={parsed.get('reasoning')}")
                    return {
                        "verdict": verdict,
                        "pathogen_name": parsed.get("pathogen_name"),
                        "severity": parsed.get("severity", "MODERATE"),
                        "reasoning": parsed.get("reasoning", ""),
                        "ai_audited": True,
                    }
        except Exception as exc:
            logger.warning(f"[Post-YOLO VLM Audit] Error: {exc}")

        return {"verdict": "UNAUDITED", "pathogen_name": None, "severity": "MODERATE", "ai_audited": False}

    @classmethod
    def audit_image_frame(
        cls,
        image_path: str,
        crop_candidate: str,
        detected_class: str,
        confidence: float,
    ) -> Dict[str, Any]:
        """Backwards-compatible wrapper around post_verify_detection."""
        return cls.post_verify_detection(image_path, crop_candidate, detected_class, confidence)

    @classmethod
    def audit_detection(
        cls,
        crop: str,
        detected_class: str,
        confidence: float,
        zone: Optional[str] = None,
        extra_context: Optional[str] = None,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Audits a single key YOLO detection.
        Returns verdict, confidence adjustment, and reasoning.
        """
        model = _get_vlm_model()
        zone_str = f"Zone {zone}" if zone else "unknown zone"
        ctx = extra_context or "No additional field metadata available."

        user_prompt = f"""Audit this drone-captured detection:

Crop Species   : {crop}
Detected Class : {detected_class}
YOLO Confidence: {confidence * 100:.1f}%
Sector         : {zone_str}
Field Context  : {ctx}

Respond ONLY with this JSON:
{{
  "verdict": "VERIFIED" | "UNCERTAIN" | "REJECTED",
  "adjusted_confidence": <float 0-1>,
  "pathogen_name": "<scientific name if verified, else null>",
  "reasoning": "<1-sentence clinical justification>",
  "severity": "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
}}"""

        raw = None
        if image_base64:
            try:
                img_bytes = base64.b64decode(image_base64)
                raw = _groq_vision_chat(model, cls.SYSTEM_PROMPT, user_prompt, img_bytes)
            except Exception as e:
                logger.warning(f"[AIService] Failed to parse image_base64 for audit: {e}")

        if not raw:
            raw = _groq_chat(model, cls.SYSTEM_PROMPT, user_prompt, max_tokens=512)

        if raw:
            parsed = _parse_json_response(raw)
            if parsed:
                return {
                    "vlm_model": model,
                    "verdict": parsed.get("verdict", "UNCERTAIN"),
                    "adjusted_confidence": float(parsed.get("adjusted_confidence", confidence)),
                    "pathogen_name": parsed.get("pathogen_name"),
                    "reasoning": parsed.get("reasoning", ""),
                    "severity": parsed.get("severity", "MODERATE"),
                    "ai_audited": True,
                }

        # Fallback — pass-through with no audit
        return {
            "vlm_model": model,
            "verdict": "UNAUDITED",
            "adjusted_confidence": confidence,
            "pathogen_name": None,
            "reasoning": "VLM audit skipped (API key not configured or call failed).",
            "severity": "MODERATE" if confidence >= 0.7 else "LOW",
            "ai_audited": False,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Post-Mission Agronomy Report Engine  (llama-3.1-8b-instant)
# ─────────────────────────────────────────────────────────────────────────────

class AIService:
    """
    MODEL 2: Post-Mission Agronomy Report Engine
    Runs once at mission end. Generates full structured Farm Field Report.
    """

    SYSTEM_PROMPT = (
        "You are a Senior Agronomist and Precision Drone Farming Specialist for Project Jatayu. "
        "Generate a structured, professional agronomic report in valid JSON only. "
        "No markdown, no extra commentary — pure JSON."
    )

    @classmethod
    def is_configured(cls) -> bool:
        return bool(_get_groq_key())


    @classmethod
    def generate_agronomic_report(
        cls,
        mission_id: Any,
        crop_class: Optional[str],
        health_score: float,
        detections: List[Dict[str, Any]],
        zones: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Stage 2: Generates full Farm Field Report.
        Called once when user clicks COMPLETE MISSION.
        """
        # Aggregate detections
        disease_counts: Dict[str, int] = {}
        crops_identified: set = set()
        avg_confs: List[float] = []

        for d in detections:
            cls_name = d.get("detected_class", "unknown")
            disease_counts[cls_name] = disease_counts.get(cls_name, 0) + 1
            if d.get("plant_class"):
                crops_identified.add(d["plant_class"])
            if d.get("confidence_score"):
                avg_confs.append(float(d["confidence_score"]))

        crop_str = crop_class or (list(crops_identified)[0] if crops_identified else "Agricultural Crop")
        mean_conf = (sum(avg_confs) / len(avg_confs)) if avg_confs else 0.0
        active_diseases = [
            k for k in disease_counts
            if "healthy" not in k.lower() and k.lower() != "notaleaf"
        ]

        # Risk tier
        if health_score >= 80 and not active_diseases:
            risk_level, risk_color, yield_impact = "LOW / OPTIMAL", "#10B981", "< 3%"
        elif health_score >= 50:
            risk_level, risk_color, yield_impact = "MODERATE / CAUTION", "#F59E0B", "8–15%"
        else:
            risk_level, risk_color, yield_impact = "HIGH / CRITICAL", "#EF4444", "25–40%"

        report_model = _get_report_model()

        if cls.is_configured() and active_diseases:
            user_prompt = f"""Post-mission farm field disease survey analysis:

Crop Species      : {crop_str}
Canopy Health     : {health_score:.1f}%
Detected Diseases : {", ".join(active_diseases)}
Total Detections  : {len(detections)}
Avg Confidence    : {mean_conf * 100:.1f}%
Affected Zones    : {len([z for z in zones if z.get("detection_count", 0) > 0])} of {len(zones)} sectors

Generate a complete Farm Field Report JSON:
{{
  "executive_summary": "<2-sentence clinical diagnosis>",
  "diagnosis_verification_score": <integer 0-100>,
  "primary_pathogen": "<scientific name and classification>",
  "chemical_prescription": "<active ingredient + dosage per litre + application method>",
  "organic_remedy": "<organic/biological control agent + dosage>",
  "prevention_steps": ["<step 1>", "<step 2>", "<step 3>"],
  "drone_action_plan": "<altitude, speed, droplet size, grid pattern>",
  "farmer_advisory": "<plain-language 1-sentence action for farmer>"
}}"""

            raw = _groq_chat(report_model, cls.SYSTEM_PROMPT, user_prompt, max_tokens=1024)
            if raw:
                parsed = _parse_json_response(raw)
                if parsed:
                    return {
                        "ai_engine": f"Groq / {report_model}",
                        "crop": crop_str,
                        "health_score": round(health_score, 1),
                        "risk_level": risk_level,
                        "risk_color": risk_color,
                        "yield_impact": yield_impact,
                        "executive_summary": parsed.get("executive_summary", ""),
                        "diagnosis_verification_score": parsed.get("diagnosis_verification_score", 85),
                        "primary_pathogen": parsed.get("primary_pathogen", active_diseases[0] if active_diseases else "None"),
                        "chemical_prescription": parsed.get("chemical_prescription", ""),
                        "biological_remedy": parsed.get("organic_remedy", ""),
                        "prevention_steps": parsed.get("prevention_steps", []),
                        "drone_action_plan": parsed.get("drone_action_plan", ""),
                        "farmer_advisory": parsed.get("farmer_advisory", ""),
                    }

        # ── Built-in fallback engine ──────────────────────────────────────────
        dominant = active_diseases[0] if active_diseases else "healthy"
        norm = dominant.lower().replace("_", "")

        if "blight" in norm:
            chem = "Mancozeb 75% WP @ 2.5 g/L or Azoxystrobin 23% SC @ 1 ml/L via drone ULV."
            bio = "Trichoderma harzianum @ 5 g/L + Reynoutria sachalinensis extract."
            pathogen = "Phytophthora infestans / Alternaria solani (Fungal Oomycete Blight)"
            drone = "3.5 m altitude · 120-µm droplet · targeted grid on infected zones."
            summary = f"Severe foliar blighting on {crop_str}. Immediate sector containment advised."
            prevention = ["Remove infected plant debris promptly", "Ensure adequate row spacing for airflow", "Apply preventative copper-based spray before monsoon season"]
        elif "mildew" in norm:
            chem = "Wettable Sulfur 80% WDG @ 3 g/L or Hexaconazole 5% EC @ 2 ml/L."
            bio = "Potassium Bicarbonate 0.5% + cold-pressed Neem Oil."
            pathogen = "Erysiphe / Podosphaera spp. (Powdery/Downy Mildew)"
            drone = "Early-morning application at 3 m altitude to maximise leaf surface contact."
            summary = f"Powdery spore colonies on {crop_str}. Fungicidal barrier treatment required."
            prevention = ["Improve canopy ventilation through pruning", "Avoid overhead irrigation late in the day", "Use resistant cultivars in next season"]
        elif "rust" in norm:
            chem = "Propiconazole 25% EC @ 1 ml/L or Tebuconazole 250 EC."
            bio = "Bacillus subtilis (Serenade ASO) @ 4 ml/L."
            pathogen = "Puccinia spp. (Obligate Biotrophic Rust)"
            drone = "50 m quarantine buffer spray at 4 m altitude."
            summary = f"Rust pustules on {crop_str}. High spore load under current humidity."
            prevention = ["Scout fields weekly during humid periods", "Apply preventative strobilurin fungicide", "Eliminate volunteer host plants from field boundaries"]
        elif "spot" in norm or "septoria" in norm:
            chem = "Copper Oxychloride 50% WP @ 3 g/L or Chlorothalonil 75% WP."
            bio = "Pseudomonas fluorescens @ 5 g/L foliar spray."
            pathogen = "Cercospora / Septoria spp. (Foliar Spot Pathogen)"
            drone = "0.5 m/s scan speed at 3 m altitude to monitor lesion expansion."
            summary = f"Necrotic leaf spots across {crop_str}. Risk of premature defoliation."
            prevention = ["Rotate crops to break disease cycle", "Use certified disease-free seed", "Maintain balanced nitrogen fertilisation"]
        elif "virus" in norm or "mosaic" in norm:
            chem = "Vector control: Imidacloprid 17.8% SL @ 0.5 ml/L or Acetamiprid 20% SP."
            bio = "Beauveria bassiana @ 5 g/L + yellow sticky trap deployment."
            pathogen = "Begomovirus / Tobamovirus (Viral Mosaic Complex)"
            drone = "GPS-mark infected coordinates for physical rogueing operations."
            summary = f"Viral mosaic on {crop_str}. Immediate vector suppression critical."
            prevention = ["Rogue and destroy visibly infected plants", "Control aphid and whitefly vectors aggressively", "Use virus-indexed planting material only"]
        else:
            chem = "No chemical treatment required. Maintain micronutrient schedule."
            bio = "Preventative seaweed extract + beneficial microorganism soil drench."
            pathogen = "None (Healthy Crop)"
            drone = "Routine surveillance every 72 hours."
            summary = f"{crop_str} canopy is in robust health. Continue monitoring."
            prevention = ["Maintain regular UAV surveillance flights", "Keep soil pH optimised for crop", "Monitor weather forecasts for disease-risk conditions"]

        return {
            "ai_engine": "Jatayu Agronomic Neural Engine (Fallback)",
            "crop": crop_str,
            "health_score": round(health_score, 1),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "yield_impact": yield_impact,
            "executive_summary": summary,
            "diagnosis_verification_score": int(mean_conf * 100) if mean_conf else 75,
            "primary_pathogen": pathogen,
            "chemical_prescription": chem,
            "biological_remedy": bio,
            "prevention_steps": prevention,
            "drone_action_plan": drone,
            "farmer_advisory": summary.split(".")[0] + ". Consult your local agronomist.",
        }
