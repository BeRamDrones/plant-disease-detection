"""
Identify unnamed disease classes (Class_0, Class_1, ...) using ONLY local
filename patterns — no API, no internet, no cost.

WHY THIS CAN WORK
------------------
Many plant-disease datasets (PlantVillage-style exports, or datasets later
re-exported through Roboflow) keep the ORIGINAL disease name baked into the
image filename, e.g.:

    Tomato___Early_blight_0182.JPG
    Apple___Cedar_apple_rust0341_jpg.rf.9f2a1c4b8e7d.jpg
    Powdery_Mildew_034.png

Roboflow re-exports often append a suffix like "_jpg.rf.<hash>" but keep the
original name as a prefix. This script:

1. For each unnamed class (Class_0, Class_1, ...), finds every image that has
   at least one labeled bounding box of that class.
2. Strips the Roboflow-style hash suffix and file extension, cleans up
   separators (_, -, ___, digits at the end), and extracts a candidate
   disease-name string from each filename.
3. Tallies the cleaned names across all matching images and picks the most
   common one as the suggestion — plus a confidence score based on how
   consistent the filenames were.
4. Also builds a visual montage (cropped bounding-box regions) per class, same
   as before, so you can eyeball it against the filename-based guess.
5. Writes everything to a review file — nothing is auto-applied to your real
   data.yaml until you approve it and run with --apply.

THIS WILL NOT WORK WELL IF:
- Filenames are pure random hashes / camera-generated names (IMG_0001.jpg,
  DSC_2934.jpg) with no disease name in them — in that case confidence will
  come back low/blank and you'll need another method (manual review, or the
  API-based script) for those specific classes.
- A folder mixes multiple diseases under one class id inconsistently — you'll
  see this as low confidence / a fragmented vote in the review file.

USAGE
-----
    # Step 1: scan + infer names from filenames -> review file + montages
    python identify_unnamed_classes_local.py --root "C:\\...\\_ANNOTATED_CLASSES"

    # Step 2: open the review file + montage images, fill in approved_name
    #          for anything the filename inference got right (or correct it)

    # Step 3: apply approved names into each data.yaml (backs up originals)
    python identify_unnamed_classes_local.py --root "C:\\...\\_ANNOTATED_CLASSES" --apply

Requires: pip install pillow pyyaml
"""

import argparse
import random
import re
from collections import Counter
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

GENERIC_NAME_PATTERN = re.compile(r"^class[_\s]?\d+$", re.IGNORECASE)
MAX_IMAGES_TO_SCAN = 2000       # cap per class, for speed on very large datasets
MAX_SAMPLE_FOR_NAME_VOTE = 500  # how many matching images to use for the filename vote
SAMPLES_PER_MONTAGE = 6
THUMB_SIZE = 220

# Roboflow suffix pattern: "..._jpg.rf.<32charhash>" / "..._png.rf.<hash>" etc.
ROBOFLOW_SUFFIX = re.compile(r"_(jpg|jpeg|png|bmp)\.rf\.[0-9a-fA-F]+$", re.IGNORECASE)
TRAILING_NUMBER = re.compile(r"[\s_\-]*\d+$")
NON_ALNUM_RUN = re.compile(r"[_\-.]+")


def find_crop_dirs(root: Path):
    return sorted(p.parent for p in root.glob("*/data.yaml"))


def label_path_for_image(image_path: Path) -> Path:
    parts = list(image_path.parts)
    for i, part in enumerate(parts):
        if part == "images":
            parts[i] = "labels"
            break
    return Path(*parts).with_suffix(".txt")


def clean_filename_to_candidate(filename_stem: str, crop_name: str) -> str:
    """Turn a raw filename stem into a candidate disease-name string."""
    s = ROBOFLOW_SUFFIX.sub("", filename_stem)  # strip "_jpg.rf.<hash>" if present

    # PlantVillage-style separator: "Tomato___Early_blight_0182" -> take the part after "___"
    if "___" in s:
        s = s.split("___", 1)[1]

    # strip a trailing run of digits (image index/counter)
    s = TRAILING_NUMBER.sub("", s)

    # normalize separators to spaces
    s = NON_ALNUM_RUN.sub(" ", s).strip()

    if not s:
        return ""

    # drop a leading/trailing mention of the crop name itself (redundant info)
    words = s.split()
    crop_words = crop_name.lower().split()
    words = [w for w in words if w.lower() not in crop_words]
    s = " ".join(words).strip()

    return s.title()


def is_probably_random(candidate: str) -> bool:
    """Filters out junk like 'Img 0001', 'Dsc 2934', pure hex-looking strings,
    or anything too short/generic to be a real disease name."""
    if not candidate or len(candidate) < 3:
        return True
    lowered = candidate.lower()
    junk_prefixes = ("img", "dsc", "photo", "image", "screenshot", "frame", "capture")
    if any(lowered.startswith(p) for p in junk_prefixes):
        return True
    if re.fullmatch(r"[0-9a-f\s]+", lowered):  # looks like a hex hash
        return True
    return False


def collect_class_images_and_crops(crop_dir: Path, class_id: int, max_montage_crops: int):
    """Returns (list_of_image_paths_with_this_class, list_of_bbox_crops_for_montage)."""
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    all_images = [p for p in (crop_dir / "images").rglob("*") if p.suffix.lower() in img_exts]
    random.shuffle(all_images)

    matching_images = []
    montage_crops = []
    scanned = 0

    for img_path in all_images:
        if scanned >= MAX_IMAGES_TO_SCAN or len(matching_images) >= MAX_SAMPLE_FOR_NAME_VOTE:
            break
        scanned += 1
        label_path = label_path_for_image(img_path)
        if not label_path.exists():
            continue
        try:
            with open(label_path, "r") as f:
                lines = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            continue

        matching = [ln for ln in lines if int(float(ln.split()[0])) == class_id]
        if not matching:
            continue

        matching_images.append(img_path)

        if len(montage_crops) < max_montage_crops:
            try:
                with Image.open(img_path) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    for ln in matching:
                        if len(montage_crops) >= max_montage_crops:
                            break
                        parts = ln.split()
                        xc, yc, bw, bh = (float(v) for v in parts[1:5])
                        x1 = max(0, int((xc - bw / 2) * w))
                        y1 = max(0, int((yc - bh / 2) * h))
                        x2 = min(w, int((xc + bw / 2) * w))
                        y2 = min(h, int((yc + bh / 2) * h))
                        if x2 - x1 < 5 or y2 - y1 < 5:
                            continue
                        montage_crops.append(im.crop((x1, y1, x2, y2)).copy())
            except Exception:
                pass

    return matching_images, montage_crops


def vote_name_from_filenames(image_paths, crop_name: str):
    """Returns (best_name, confidence 0-1, vote_breakdown dict, n_considered)."""
    candidates = []
    for p in image_paths:
        candidate = clean_filename_to_candidate(p.stem, crop_name)
        if candidate and not is_probably_random(candidate):
            candidates.append(candidate)

    if not candidates:
        return "uncertain", 0.0, {}, len(image_paths)

    counts = Counter(candidates)
    best_name, best_count = counts.most_common(1)[0]
    confidence = best_count / len(candidates)
    return best_name, confidence, dict(counts.most_common(5)), len(image_paths)


def build_montage(crops, label_text: str):
    tiles = crops[:SAMPLES_PER_MONTAGE]
    if not tiles:
        return None
    cols = min(3, len(tiles)) or 1
    rows = (len(tiles) + cols - 1) // cols
    pad = 6
    header_h = 30

    montage = Image.new(
        "RGB",
        (cols * THUMB_SIZE + (cols + 1) * pad, header_h + rows * THUMB_SIZE + (rows + 1) * pad),
        color=(30, 30, 30),
    )
    draw = ImageDraw.Draw(montage)
    draw.text((pad, 6), label_text, fill=(255, 255, 255))

    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        tile = tile.copy()
        tile.thumbnail((THUMB_SIZE, THUMB_SIZE))
        x = pad + c * (THUMB_SIZE + pad)
        y = header_h + pad + r * (THUMB_SIZE + pad)
        montage.paste(tile, (x, y))

    return montage


def main():
    parser = argparse.ArgumentParser(description="Locally infer unnamed disease class names from filenames")
    parser.add_argument("--root", type=str, required=True, help="Path to _ANNOTATED_CLASSES folder")
    parser.add_argument("--apply", action="store_true", help="Apply approved names from the review file into each data.yaml")
    parser.add_argument("--min-confidence", type=float, default=0.6,
                         help="Only auto-fill approved_name if filename-vote confidence is >= this (default 0.6). "
                              "Lower-confidence suggestions still appear but you must approve them by hand.")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    random.seed(args.seed)

    root = Path(args.root)
    review_path = root / "_class_id_review.yaml"
    montage_dir = root / "_montages"

    if args.apply:
        if not review_path.exists():
            raise FileNotFoundError(f"No review file found at {review_path} — run without --apply first.")
        with open(review_path, "r") as f:
            review = yaml.safe_load(f) or {}

        for crop_name, entries in review.items():
            crop_dir = root / crop_name
            data_yaml_path = crop_dir / "data.yaml"
            if not data_yaml_path.exists():
                print(f"[skip] {crop_name}: data.yaml not found")
                continue
            with open(data_yaml_path, "r") as f:
                data = yaml.safe_load(f)

            names = data.get("names")
            changed = False
            for entry in entries:
                cid = entry["class_id"]
                approved = entry.get("approved_name")
                if not approved or str(approved).strip().lower() in ("", "uncertain", "none"):
                    print(f"  [skip] {crop_name} class {cid}: no approved_name set in review file")
                    continue
                names[cid] = approved
                changed = True
                print(f"  [applied] {crop_name} class {cid} -> {approved}")

            if changed:
                backup_path = data_yaml_path.with_suffix(".yaml.bak")
                if not backup_path.exists():
                    backup_path.write_text(data_yaml_path.read_text())
                data["names"] = names
                with open(data_yaml_path, "w") as f:
                    yaml.safe_dump(data, f, sort_keys=False)
                print(f"[done] {crop_name}: data.yaml updated (original backed up at {backup_path.name})")
        return

    # ---- discovery + filename-based suggestion mode ----
    crop_dirs = find_crop_dirs(root)
    if not crop_dirs:
        print(f"No crop folders with data.yaml found under {root}")
        return

    review = {}
    for crop_dir in crop_dirs:
        crop_name = crop_dir.name
        data_yaml_path = crop_dir / "data.yaml"
        with open(data_yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}
        names = data.get("names")
        if names is None:
            continue

        items = [(int(k), v) for k, v in names.items()] if isinstance(names, dict) else list(enumerate(names))
        unnamed = [(cid, name) for cid, name in items if GENERIC_NAME_PATTERN.match(str(name))]
        if not unnamed:
            continue

        print(f"\n{'=' * 60}\n{crop_name}: {len(unnamed)} unnamed class(es)\n{'=' * 60}")
        crop_entries = []
        for cid, generic_name in unnamed:
            print(f"  scanning class {cid} ({generic_name})...")
            image_paths, montage_crops = collect_class_images_and_crops(crop_dir, cid, SAMPLES_PER_MONTAGE)
            if not image_paths:
                print(f"    [warn] no labeled examples found for class {cid} — skipping")
                continue

            best_name, confidence, breakdown, n = vote_name_from_filenames(image_paths, crop_name)
            print(f"    -> filename vote: {best_name} (confidence {confidence:.0%} over {n} images)")
            if breakdown:
                top = ", ".join(f"{k}={v}" for k, v in breakdown.items())
                print(f"       top candidates: {top}")

            montage = build_montage(montage_crops, f"{crop_name} - {generic_name} (id {cid})")
            montage_path = None
            if montage is not None:
                crop_montage_dir = montage_dir / crop_name
                crop_montage_dir.mkdir(parents=True, exist_ok=True)
                montage_path = crop_montage_dir / f"{crop_name}_{generic_name}.jpg"
                montage.save(montage_path, quality=90)

            auto_approved = best_name if (confidence >= args.min_confidence and best_name != "uncertain") else None

            crop_entries.append(
                {
                    "class_id": cid,
                    "original_name": generic_name,
                    "montage": str(montage_path) if montage_path else None,
                    "suggested_name": best_name,
                    "confidence": round(confidence, 2),
                    "n_images_considered": n,
                    "top_candidates": breakdown,
                    "approved_name": auto_approved,  # pre-filled ONLY if confidence >= --min-confidence
                }
            )

        if crop_entries:
            review[crop_name] = crop_entries

    with open(review_path, "w") as f:
        yaml.safe_dump(review, f, sort_keys=False, allow_unicode=True)

    print(f"\n{'=' * 60}")
    print(f"Review file written: {review_path}")
    print(f"Montage images in : {montage_dir}")
    print(f"Entries with confidence >= {args.min_confidence:.0%} were pre-filled in 'approved_name'.")
    print("STILL double-check those against the montage image before applying — a filename")
    print("pattern can be consistent and still wrong (e.g. dataset organized by symptom stage,")
    print("not disease). Everything below the confidence threshold needs manual approval.")
    print("Then run with --apply.")
    print("=" * 60)


if __name__ == "__main__":
    main()