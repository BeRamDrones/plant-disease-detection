import os
import sys
from app.services.inference import ModelRegistry, ChildModelRegistry, CHILD_MODELS_DIR, PARENT_MODELS_DIR, DiseaseDetectionPipeline

def test_models():
    print("=" * 60)
    print("PROJECT JATAYU — MODEL COORDINATION AUDIT")
    print("=" * 60)

    # 1. Test Parent Registry
    mr = ModelRegistry.get()
    mr.load()
    print(f"Parent Registry Ready: {mr.is_ready}")
    print(f"Parent Ensemble Name: {mr.model_name}")
    print(f"Compute Device: {mr.device}")
    for m in mr._models:
        print(f"  [Parent Model] {m['name']} -> Task: {m['task']}, Total Classes: {len(m['classes'])}")
        print(f"    Classes: {list(m['classes'].values())}")

    # 2. Test Child Models
    print("\n" + "=" * 60)
    print("CHILD MODELS DISCOVERY & MAPPING")
    print("=" * 60)
    cmr = ChildModelRegistry.get()
    child_folders = sorted([f for f in os.listdir(CHILD_MODELS_DIR) if os.path.isdir(os.path.join(CHILD_MODELS_DIR, f))])
    
    from ultralytics import YOLO

    for folder in child_folders:
        resolved_path = cmr.find_child_model_path(folder)
        if resolved_path and os.path.exists(resolved_path):
            try:
                model = YOLO(resolved_path)
                task = getattr(model, "task", "unknown")
                num_classes = len(model.names)
                print(f"  ✓ Crop: '{folder}' -> Resolved: {os.path.basename(resolved_path)} | Task: {task} | Classes: {num_classes}")
                print(f"      Classes: {list(model.names.values())}")
            except Exception as e:
                print(f"  ✗ Crop: '{folder}' -> Error loading weights: {e}")
        else:
            print(f"  ⚠ Crop: '{folder}' -> No best.pt found")

    print("\n" + "=" * 60)
    print("PARENT-TO-CHILD COORDINATION CHECK")
    print("=" * 60)
    # Check which parent classes have matching child models
    all_parent_classes = set()
    for m in mr._models:
        all_parent_classes.update(m['classes'].values())

    matched = []
    unmatched = []
    for p_cls in sorted(all_parent_classes):
        if p_cls.lower() in ("notaleaf", "background", "unknown"):
            continue
        c_path = cmr.find_child_model_path(p_cls)
        if c_path:
            matched.append((p_cls, c_path))
        else:
            unmatched.append(p_cls)

    print(f"Total Parent Crop Classes: {len(all_parent_classes) - 1}")
    print(f"Child Models Available ({len(matched)}):")
    for p_cls, path in matched:
        print(f"  ✓ {p_cls} -> {os.path.relpath(path, CHILD_MODELS_DIR)}")
    
    print(f"\nParent Crops with Fallback to Healthy/Parent Classification ({len(unmatched)}):")
    print(f"  {', '.join(unmatched)}")

if __name__ == "__main__":
    test_models()
