import argparse
import hashlib
import json
import signal
import sys
import traceback
from pathlib import Path
import yaml
from PIL import Image
from ultralytics import YOLO

# =============================================================================
# HARDWARE / TRAINING CONFIG — tuned for RTX 4090 (24GB VRAM) + 64GB RAM.
# Batch sizes are set per-model below; the rest applies to all variants.
# =============================================================================
IMGSZ        = 640
EPOCHS       = 100
PATIENCE     = 15
DEVICE       = "0"
WORKERS      = 16
CACHE        = "disk"
AMP          = True
COS_LR       = True
CLOSE_MOSAIC = 10
SEED         = 0
SAVE_PERIOD  = 1   # checkpoint every epoch → safe power-off recovery

# ---- data validation guards ----
MIN_IMAGES_PER_SPLIT     = 50
MAX_TRAIN_VAL_OVERLAP_RATIO = 0.0

# =============================================================================
# MODEL AUTO-SELECTION TABLE
# Picked by counting training images; --model flag overrides this entirely.
#
#   < 28,000 train images  →  yolo11l  (large)
#   ≥ 28,000 train images  →  yolo11x  (extra-large)
#
#   batch        — largest safe batch for RTX 4090 at 640px
#   dropout/mixup/weight_decay — regularisation; both models get the same
#                                values since data is always ≥ 15k here.
# =============================================================================
MODEL_M_THRESHOLD = 5_000    # images; below this -> yolo11m
MODEL_X_THRESHOLD = 28_000   # images; at/above this -> yolo11x

MODEL_CONFIGS = {
    # model weights   batch  dropout  mixup   weight_decay
    "yolo11m.pt": dict(batch=16, dropout=0.1, mixup=0.1, weight_decay=0.0008),
    "yolo11l.pt": dict(batch=12, dropout=0.1, mixup=0.1, weight_decay=0.0008),
    "yolo11x.pt": dict(batch=8,  dropout=0.1, mixup=0.1, weight_decay=0.0008),
}


def select_model(num_train_images: int) -> tuple:
    """Return (model_weights_filename, config_dict) for the given train image count.

        < 5,000 images   -> yolo11m.pt
        5,000-27,999      -> yolo11l.pt
        >= 28,000 images  -> yolo11x.pt
    """
    if num_train_images < MODEL_M_THRESHOLD:
        name = "yolo11m.pt"
    elif num_train_images < MODEL_X_THRESHOLD:
        name = "yolo11l.pt"
    else:
        name = "yolo11x.pt"
    return name, MODEL_CONFIGS[name]

# =============================================================================

# Global tracker for graceful exit on Ctrl+C
STATUS_FILE   = None
CURRENT_STATE = {}


def load_status(output_dir: Path) -> dict:
    """Load or initialize the training state tracking file."""
    global STATUS_FILE, CURRENT_STATE
    STATUS_FILE = output_dir / "training_status.json"
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                CURRENT_STATE = json.load(f)
        except Exception:
            CURRENT_STATE = {}
    else:
        CURRENT_STATE = {}
    return CURRENT_STATE


def update_status(crop_name: str, status: str, details: str = ""):
    """Save execution state to disk immediately."""
    global STATUS_FILE, CURRENT_STATE
    if STATUS_FILE:
        CURRENT_STATE[crop_name] = {"status": status, "details": details}
        with open(STATUS_FILE, "w") as f:
            json.dump(CURRENT_STATE, f, indent=4)


def handle_interrupt(sig, frame):
    """Save progress safely when user presses Ctrl+C."""
    print("\n\n[!] Interrupt signal received! Saving status and exiting cleanly...")
    sys.exit(0)


signal.signal(signal.SIGINT, handle_interrupt)


# =============================================================================
# MODEL AUTO-SELECTION
# =============================================================================

def count_images(img_dir: Path) -> int:
    """Count all image files under img_dir (recursive)."""
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    return sum(1 for p in img_dir.rglob("*") if p.suffix.lower() in img_exts)





# =============================================================================

def find_dataset_dirs(base_dir: Path):
    """Recursively find every directory that contains a data.yaml."""
    return sorted({p.parent for p in base_dir.rglob("data.yaml")})


def crop_label_for(dataset_dir: Path, base_dir: Path) -> str:
    """Build a unique, filesystem-safe name for a dataset dir."""
    return "_".join(dataset_dir.relative_to(base_dir).parts)


def _find_split_dir(dataset_dir: Path, split_names):
    """Look for an images folder for a given split."""
    for split in split_names:
        for layout in [dataset_dir / "images" / split, dataset_dir / split / "images"]:
            if layout.is_dir() and any(layout.iterdir()):
                return layout
    return None


def _label_path_for_image(image_path: Path) -> Path:
    """YOLO convention: labels live in a parallel 'labels' tree."""
    parts = list(image_path.parts)
    for i, part in enumerate(parts):
        if part == "images":
            parts[i] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def _file_hash(path: Path, chunk_size=1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def validate_dataset(dataset_dir: Path, train_dir: Path, val_dir: Path, nc: int):
    """Strict pre-training data checks."""
    problems = []

    def check_split(split_name, img_dir):
        img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        images = sorted(p for p in img_dir.rglob("*") if p.suffix.lower() in img_exts)

        if len(images) < MIN_IMAGES_PER_SPLIT:
            problems.append(f"{split_name}: only {len(images)} images found (< {MIN_IMAGES_PER_SPLIT} minimum)")
            return images, {}

        corrupt, missing_labels, empty_labels, bad_class_ids, hashes = [], [], [], [], {}

        for img_path in images:
            try:
                with Image.open(img_path) as im:
                    im.verify()
            except Exception:
                corrupt.append(img_path)
                continue

            hashes[img_path] = _file_hash(img_path)
            label_path = _label_path_for_image(img_path)

            if not label_path.exists():
                missing_labels.append(img_path)
                continue
            if label_path.stat().st_size == 0:
                empty_labels.append(img_path)
                continue

            try:
                with open(label_path, "r") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        cls_id = int(float(line.split()[0]))
                        if cls_id < 0 or cls_id >= nc:
                            bad_class_ids.append((img_path, cls_id))
                            break
            except Exception:
                bad_class_ids.append((img_path, "unparseable"))

        if corrupt:
            problems.append(f"{split_name}: {len(corrupt)} corrupt/unreadable image(s)")
        if missing_labels:
            problems.append(f"{split_name}: {len(missing_labels)} image(s) with no matching label file")
        if empty_labels:
            frac = len(empty_labels) / len(images)
            if frac > 0.3:
                problems.append(f"{split_name}: {len(empty_labels)}/{len(images)} ({frac:.0%}) label files are empty")
        if bad_class_ids:
            problems.append(f"{split_name}: {len(bad_class_ids)} label(s) reference a class id outside [0, {nc})")

        return images, hashes

    _, train_hashes = check_split("train", train_dir)
    _, val_hashes   = check_split("val",   val_dir)

    if train_hashes and val_hashes:
        train_hash_set = set(train_hashes.values())
        overlap = [p for p, h in val_hashes.items() if h in train_hash_set]
        if overlap:
            ratio = len(overlap) / len(val_hashes)
            if ratio > MAX_TRAIN_VAL_OVERLAP_RATIO:
                problems.append(
                    f"train/val leakage: {len(overlap)}/{len(val_hashes)} val images "
                    f"are byte-identical to a train image"
                )

    if problems:
        raise ValueError(f"Dataset validation failed for {dataset_dir}:\n  - " + "\n  - ".join(problems))


def build_fixed_data_yaml(
    dataset_dir: Path,
    crop_name: str,
    scratch_dir: Path,
    skip_validation: bool = False,
) -> tuple:
    """Auto-detect real image folders, write a corrected yaml, and return
    (fixed_yaml_path, train_image_count)."""
    original_yaml = dataset_dir / "data.yaml"
    with open(original_yaml, "r") as f:
        original = yaml.safe_load(f) or {}

    train_dir = _find_split_dir(dataset_dir, ["train"])
    val_dir   = _find_split_dir(dataset_dir, ["val", "valid"])
    test_dir  = _find_split_dir(dataset_dir, ["test"])

    if train_dir is None:
        raise FileNotFoundError(f"Could not find a train images folder under {dataset_dir}")
    if val_dir is None:
        raise FileNotFoundError(f"Could not find a val/valid images folder under {dataset_dir}")

    fixed = {
        "train": str(train_dir),
        "val":   str(val_dir),
        "nc":    original.get("nc"),
        "names": original.get("names"),
    }
    if test_dir is not None:
        fixed["test"] = str(test_dir)

    if fixed["nc"] is None or fixed["names"] is None:
        raise ValueError(f"{original_yaml} is missing 'nc' or 'names'")

    scratch_dir.mkdir(parents=True, exist_ok=True)
    fixed_yaml_path = scratch_dir / f"{crop_name}_data.yaml"
    with open(fixed_yaml_path, "w") as f:
        yaml.safe_dump(fixed, f, sort_keys=False)

    print(f"  [fixed yaml] train={train_dir}")
    print(f"  [fixed yaml] val  ={val_dir}")
    if test_dir is not None:
        print(f"  [fixed yaml] test ={test_dir}")

    n_train = count_images(train_dir)
    print(f"  [images]     {n_train:,} training images found")

    print(f"  [validating] checking {crop_name} for corrupt files...")
    if skip_validation:
        print(f"  [validating] SKIPPED (--skip-validation passed)")
    else:
        validate_dataset(dataset_dir, train_dir, val_dir, nc=fixed["nc"])
        print(f"  [validating] {crop_name} passed all checks")

    return fixed_yaml_path, n_train


# =============================================================================
# POWER-OFF RECOVERY
# =============================================================================

def detect_resume_state(run_dir: Path, crop_name: str) -> tuple:
    """Inspect disk + status file to decide what to do for this crop.

    Returns (state, checkpoint_path):
        'completed' — done marker exists; skip entirely.
        'poweroff'  — process was killed mid-run; last.pt exists, safe to resume.
        'fresh'     — no prior run; start from scratch.
    """
    done_marker = run_dir / "TRAINING_COMPLETE.txt"
    last_ckpt   = run_dir / "weights" / "last.pt"
    json_status = CURRENT_STATE.get(crop_name, {}).get("status", "")

    if done_marker.exists() or json_status == "completed":
        return "completed", None
    if last_ckpt.exists():
        return "poweroff", last_ckpt
    return "fresh", None


# =============================================================================

def train_one(dataset_dir: Path, base_dir: Path, output_dir: Path, args):
    crop_name       = crop_label_for(dataset_dir, base_dir)
    crop_output_dir = output_dir / crop_name
    run_dir         = crop_output_dir / f"{crop_name}_det"

    # ── Decide what to do ────────────────────────────────────────────────────
    state, ckpt_path = detect_resume_state(run_dir, crop_name)

    if state == "completed":
        print(f"\n[info] {crop_name} is already fully trained. Skipping.")
        update_status(crop_name, "completed", "Already trained")
        return

    print("\n" + "=" * 70)
    print(f"Training : {crop_name}")
    print(f"  dataset : {dataset_dir}")
    print(f"  output  : {crop_output_dir}")
    print(f"  state   : {state.upper()}")
    print("=" * 70)

    scratch_dir = output_dir / "_fixed_yamls"

    # ── POWER-OFF RESUME ─────────────────────────────────────────────────────
    if state == "poweroff":
        print(f"  [power-off recovery] Checkpoint found at {ckpt_path}")
        print(f"  [power-off recovery] Resuming — no epochs will be repeated.")
        update_status(crop_name, "in_progress", f"Resumed after power-off from {ckpt_path}")

        # Regenerate yaml in case scratch dir was wiped after reboot.
        # YOLO resume=True reads paths from the checkpoint itself, but having
        # the yaml present avoids edge-case errors on some versions.
        build_fixed_data_yaml(dataset_dir, crop_name, scratch_dir, skip_validation=True)

        model = YOLO(str(ckpt_path))
        model.train(resume=True)

    # ── FRESH START ───────────────────────────────────────────────────────────
    else:
        data_yaml, n_train = build_fixed_data_yaml(
            dataset_dir, crop_name, scratch_dir, skip_validation=args.skip_validation
        )

        # Auto-select model unless the user pinned one with --model
        if args.model is not None:
            model_weights = args.model
            cfg = MODEL_CONFIGS.get(model_weights, MODEL_CONFIGS["yolo11x.pt"])
            print(f"  [model] Using user-specified model: {model_weights}")
        else:
            model_weights, cfg = select_model(n_train)
            verdict = "≥" if n_train >= MODEL_X_THRESHOLD else "<"
            print(f"  [model] Auto-selected: {model_weights}  "
                  f"({n_train:,} train images {verdict} {MODEL_X_THRESHOLD:,} threshold)")

        print(f"  [model] batch={cfg['batch']}  dropout={cfg['dropout']}  "
              f"mixup={cfg['mixup']}  weight_decay={cfg['weight_decay']}")

        update_status(crop_name, "in_progress",
                      f"Fresh training with {model_weights} ({n_train:,} images)")

        model = YOLO(model_weights)
        model.train(
            data=str(data_yaml),
            project=str(crop_output_dir),
            name=f"{crop_name}_det",
            exist_ok=True,
            verbose=True,
            # Hardware / Speed
            imgsz=IMGSZ,
            epochs=EPOCHS,
            patience=PATIENCE,
            batch=cfg["batch"],
            device=DEVICE,
            workers=WORKERS,
            cache=CACHE,
            amp=AMP,
            cos_lr=COS_LR,
            close_mosaic=CLOSE_MOSAIC,
            seed=SEED,
            save_period=SAVE_PERIOD,
            # Overfitting guards — tuned per model/data size
            weight_decay=cfg["weight_decay"],
            dropout=cfg["dropout"],
            mixup=cfg["mixup"],
            mosaic=1.0,
        )

    # ── Mark complete ─────────────────────────────────────────────────────────
    done_marker = run_dir / "TRAINING_COMPLETE.txt"
    done_marker.parent.mkdir(parents=True, exist_ok=True)
    with open(done_marker, "w") as f:
        f.write("Training completed successfully.\n")

    update_status(crop_name, "completed", "Training complete")
    print(f"[done] {crop_name} training complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Train YOLO11 over multiple crop folders — auto-selects model by dataset size"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=r"C:\BeRam\plant disease\training1-6",
        help="Directory containing subfolders with data.yaml",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Where run outputs go (default: <base-dir>/../runs_det)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,   # None = auto-select per dataset; pass e.g. yolo11x.pt to override
        help="Override auto model selection (e.g. yolo11x.pt). "
             "If omitted, model is chosen automatically per dataset size.",
    )
    parser.add_argument(
        "--only",
        type=str,
        nargs="*",
        default=None,
        help="Optional list of dataset labels to train (train a subset).",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip pre-training data integrity checks.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"base_dir does not exist: {base_dir}")

    output_dir = Path(args.output_dir) if args.output_dir else base_dir.parent / "runs_det"
    output_dir.mkdir(parents=True, exist_ok=True)

    load_status(output_dir)

    dataset_dirs = find_dataset_dirs(base_dir)
    if args.only:
        dataset_dirs = [d for d in dataset_dirs if crop_label_for(d, base_dir) in args.only]

    if not dataset_dirs:
        print("No dataset folders with data.yaml found. Nothing to train.")
        return

    # ── Startup summary ───────────────────────────────────────────────────────
    print(f"\nFound {len(dataset_dirs)} dataset(s). Model auto-selection rule:")
    print(f"  < {MODEL_M_THRESHOLD:,} train images  ->  yolo11m.pt")
    print(f"  {MODEL_M_THRESHOLD:,}-{MODEL_X_THRESHOLD-1:,} train images  ->  yolo11l.pt")
    print(f"  >= {MODEL_X_THRESHOLD:,} train images  ->  yolo11x.pt")
    if args.model:
        print(f"  (overridden by --model {args.model})")

    print(f"\n{'Crop':<32} {'State':<22} {'Est. model'}")
    print("-" * 70)
    for d in dataset_dirs:
        lbl      = crop_label_for(d, base_dir)
        run_dir  = output_dir / lbl / f"{lbl}_det"
        state, _ = detect_resume_state(run_dir, lbl)

        if state == "completed":
            est_model = "(done)"
        elif args.model:
            est_model = args.model
        else:
            train_dir = _find_split_dir(d, ["train"])
            n = count_images(train_dir) if train_dir else 0
            est_model, _ = select_model(n)
            est_model = f"{est_model}  ({n:,} imgs)"

        tag = {"completed": "DONE", "poweroff": "RESUME (power-off)", "fresh": "FRESH"}.get(state, state)
        print(f"  {lbl:<30} {tag:<22} {est_model}")

    print()

    # ── Train ─────────────────────────────────────────────────────────────────
    results_log = []
    for dataset_dir in dataset_dirs:
        label = crop_label_for(dataset_dir, base_dir)
        try:
            train_one(dataset_dir, base_dir, output_dir, args)
            results_log.append((label, "success"))
        except Exception as e:
            print(f"[error] Training failed for {label}: {e}")
            traceback.print_exc()
            update_status(label, "failed", str(e))
            results_log.append((label, f"failed: {e}"))

    print("\n" + "=" * 70)
    print("Execution Summary")
    print("=" * 70)
    for name, status in results_log:
        print(f"  {name:<30} -> {status}")


if __name__ == "__main__":
    main()