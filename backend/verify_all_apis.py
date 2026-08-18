import urllib.request
import json
import os
import io
from PIL import Image

BASE_URL = "http://127.0.0.1:8001"

def test_get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def test_post(endpoint, payload):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def test_multipart(endpoint, file_path):
    url = f"{BASE_URL}{endpoint}"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(file_path)}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "Mozilla/5.0"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)

def run_all_tests():
    print("=" * 70)
    print("PROJECT JATAYU — FULL REST API & PIPELINE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Root
    s, d = test_get("/")
    msg = d.get('message') if isinstance(d, dict) else str(d)
    print(f"1. GET /                                 -> Status {s} | {msg}")

    # 2. Model Status
    s, d = test_get("/api/inference/model-status")
    print(f"2. GET /api/inference/model-status       -> Status {s} | Ready: {d.get('ready')} | Ensemble: {d.get('model_name')} | Device: {d.get('device')}")

    # 3. Model Registry Inventory
    s, d = test_get("/api/inference/model-registry")
    parents = d.get("parent", {}).get("parent_models", [])
    children = d.get("children", [])
    print(f"3. GET /api/inference/model-registry     -> Status {s} | Parents Loaded: {len(parents)} | Child Models Available: {len(children)}")
    for c in children:
        print(f"     * {c.get('display_name')} ({c.get('folder')}): weights_found={c.get('has_weights')}")

    # 4. Groq Status
    s, d = test_get("/api/inference/groq-status")
    print(f"4. GET /api/inference/groq-status        -> Status {s} | Configured: {d.get('configured')} | VLM: {d.get('vlm_model')} | Report: {d.get('report_model')}")

    # 5. UTMS Sync Mission
    sync_payload = {
        "mission_id": 999,
        "drone_id": "DRONE_01",
        "phase": "survey",
        "status": "in_progress",
        "boundary_coordinates": [
            [12.9716, 77.5946],
            [12.9720, 77.5946],
            [12.9720, 77.5950],
            [12.9716, 77.5950]
        ]
    }
    s, d = test_post("/api/utms/sync-mission", sync_payload)
    print(f"5. POST /api/utms/sync-mission           -> Status {s} | Mission synced: {d.get('mission_id') if isinstance(d, dict) else d}")

    # 6. Match Zone
    s, d = test_post("/api/missions/999/match-zone", {"lat": 12.9718, "lon": 77.5948})
    print(f"6. POST /api/missions/999/match-zone     -> Status {s} | Matched: {d}")

    # 7. Ingest Detections
    det_payload = [
        {
            "lat": 12.9718,
            "lon": 77.5948,
            "detected_class": "Tomato___Late_blight",
            "confidence_score": 0.92,
            "model_version": "v1.0",
            "plant_class": "Tomato",
            "x_center": 0.5,
            "y_center": 0.5
        }
    ]
    s, d = test_post("/api/missions/999/detections", det_payload)
    print(f"7. POST /api/missions/999/detections     -> Status {s} | Inserted count: {d.get('inserted') if isinstance(d, dict) else d} | Unmatched: {d.get('unmatched') if isinstance(d, dict) else ''}")

    # 8. Mission Summary
    s, d = test_get("/api/missions/999/summary")
    print(f"8. GET /api/missions/999/summary         -> Status {s} | Health Score: {d.get('health_score') if isinstance(d, dict) else d}% | Zones: {len(d.get('zones_breakdown', [])) if isinstance(d, dict) else 0}")

    # 9. AI Report Summary
    report_payload = {
        "mission_id": 999,
        "crop_class": "Tomato",
        "health_score": 65.0,
        "detections": det_payload,
        "zones": [{"zone_id": 1, "detection_count": 1}]
    }
    s, d = test_post("/api/missions/ai-report-summary", report_payload)
    print(f"9. POST /api/missions/ai-report-summary  -> Status {s} | Engine: {d.get('ai_engine') if isinstance(d, dict) else 'N/A'}")
    if isinstance(d, dict):
        print(f"     Pathogen: {d.get('primary_pathogen')}")
        print(f"     Farmer Advisory: {d.get('farmer_advisory')}")

    # 10. Frame Detection Inference (Image)
    img = Image.new("RGB", (300, 300), color=(20, 120, 20))
    test_img_path = "live_test_frame.jpg"
    img.save(test_img_path, format="JPEG")
    s, d = test_multipart("/api/inference/infer/image", test_img_path)
    print(f"10. POST /api/inference/infer/image      -> Status {s} | Response: {d.get('status') if isinstance(d, dict) else d}")

    # 11. Video Frame Detection Inference
    s, d = test_multipart("/api/inference/infer/video-frame", test_img_path)
    print(f"11. POST /api/inference/infer/video-frame-> Status {s} | Response: {d.get('status') if isinstance(d, dict) else d}")

    if os.path.exists(test_img_path):
        os.remove(test_img_path)

if __name__ == "__main__":
    run_all_tests()
