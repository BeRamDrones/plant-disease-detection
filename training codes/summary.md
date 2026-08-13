# Plant Disease Detection — Training Pipeline Summary

This folder contains **four standalone Python scripts** that together cover the full lifecycle of building a drone-based plant disease detection dataset and training YOLO models on it.

```
fast_scrape.py                    ← Step 1: Collect images from the internet
identify_unnamed_classes_local.py ← Step 2: Fix anonymous class names in datasets
augment.py                        ← Step 3: Augment existing annotated datasets
multi_train.py                    ← Step 4: Train one YOLO model per crop/dataset
```

---

## 1. `fast_scrape.py` — Multi-Source Image Scraper

### What it does
Collects raw images for each plant/disease class from **three sources in parallel**:
- **iNaturalist** — research-grade biodiversity observation photos (primary source; most reliable)
- **DuckDuckGo Image Search** — general web images via targeted search queries
- **Wikimedia Commons** — open-licensed botanical photos

After downloading, it runs a **quality filtering pipeline** on every image:
1. **Corruption check** — verifies the file can actually be opened by PIL
2. **Size check** — rejects images smaller than 150 px on any side (`MIN_SIDE_PX`)
3. **Aspect ratio check** — drops images wider/taller than 2.5× the other axis (strips banners, logos)
4. **Blur detection** — uses Laplacian variance via OpenCV; images below `BLUR_THRESHOLD = 40.0` are discarded
5. **Perceptual hash deduplication** — computes a pHash for each image and removes near-duplicates within a Hamming distance of 8 (`PHASH_DISTANCE`)

Surviving images are then split 80% train / 10% valid / 10% test and moved into `train/<class>/`, `valid/<class>/`, `test/<class>/` directories. A CSV audit file is produced at the end.

### Why multi-threading?
Downloads are I/O-bound, not CPU-bound. `concurrent.futures.ThreadPoolExecutor` with `MAX_WORKERS = 15` lets 15 HTTP requests happen simultaneously, cutting scraping time by ~10–15× over sequential code. Quality checks also run in parallel for the same reason.

### Key configuration (top of file)
| Variable | Default | What to change |
|---|---|---|
| `INAT_TARGET` | 750 | Max candidates to pull from iNaturalist per class |
| `DDG_PER_QUERY` | 100 | Results per DuckDuckGo search query |
| `WIKI_PER_TERM` | 50 | Wikimedia results per search term |
| `SPLIT_RATIOS` | 80/10/10 | Dataset split percentages |
| `MIN_SIDE_PX` | 150 | Minimum image dimension in pixels |
| `BLUR_THRESHOLD` | 40.0 | Lower = accept blurrier images |
| `PHASH_DISTANCE` | 8 | Higher = remove more near-duplicate images |
| `MAX_WORKERS` | 15 | Parallel download threads |

### How to add new classes
In the `CLASSES` dict (around line 42), add a new entry:
```python
"YourCrop___disease_state": {
    "inat_taxon": "Scientific Name",       # Used to resolve taxon ID on iNaturalist
    "ddg": [
        "your search query 1 drone view",  # Use specific, descriptive queries
        "your search query 2 top down",
    ],
    "wikimedia": ["plant name overhead"],
},
```

### How to run
```bash
pip install duckduckgo-search requests pillow imagehash opencv-python
python fast_scrape.py
```
Outputs: `train/`, `valid/`, `test/` directories + `scrape_audit_fast.csv`

### When to use
- You are starting a new dataset from scratch and have no existing images
- You need a specific crop/disease not covered by existing public datasets
- You want a fast, automated pipeline with built-in quality control

---

## 2. `identify_unnamed_classes_local.py` — Class Name Recovery Tool

### What it does
When datasets are exported from tools like **Roboflow**, class names sometimes get replaced with generic placeholders like `Class_0`, `Class_1`, etc., and the actual disease name is only preserved inside the image filenames. This script recovers those names **entirely offline** — no API key, no internet, no cost.

#### How name recovery works
1. Scans every image in each class folder and finds images whose `.txt` label files reference that class ID
2. Extracts the original disease name from the filename using pattern matching:
   - Strips Roboflow-style hash suffixes like `_jpg.rf.9f2a1c4b8e7d`
   - Handles PlantVillage-style separators: `Tomato___Early_blight_0182` → `Early Blight`
   - Removes trailing digit counters and normalizes separators
3. Runs a **majority vote** across all matching filenames and picks the most common candidate as the suggested name, plus a confidence score
4. Builds a **visual montage** (grid of cropped bounding-box regions) for each unnamed class so you can visually confirm the guess
5. Writes everything to `_class_id_review.yaml` — **nothing changes in your actual data until you explicitly run with `--apply`**

#### Limitations (documented in the file)
- **Will not work** if filenames are pure random camera names like `IMG_0001.jpg` (confidence comes back low)
- **Low confidence** if one folder mixes multiple diseases under the same class ID

### Two-step workflow

**Step 1 — Scan and suggest:**
```bash
python identify_unnamed_classes_local.py --root "path/to/_ANNOTATED_CLASSES"
```
This creates `_class_id_review.yaml` and saves montage images to `_montages/`.

**Step 2 — Review and apply:**
Open `_class_id_review.yaml`. Each entry has:
- `suggested_name` — the filename-based best guess
- `confidence` — fraction of filenames that agreed (e.g. `0.87`)
- `approved_name` — pre-filled if confidence >= 0.6 (configurable via `--min-confidence`)
- `montage` — path to the visual grid image for that class

Correct any wrong `approved_name` values manually, then apply:
```bash
python identify_unnamed_classes_local.py --root "path/to/_ANNOTATED_CLASSES" --apply
```
The script backs up the original `data.yaml` as `data.yaml.bak` before overwriting.

### Key flags
| Flag | Default | Purpose |
|---|---|---|
| `--root` | (required) | Path to the folder containing all annotated class subfolders |
| `--apply` | off | Apply `approved_name` values from the review file into `data.yaml` |
| `--min-confidence` | 0.6 | Only auto-fill `approved_name` above this threshold |
| `--seed` | 0 | Random seed for reproducible montage sampling |

### When to use
- You received a dataset where class names are `Class_0`, `Class_1`, etc.
- You downloaded a Roboflow export and the `data.yaml` lost the disease names
- You need to audit and fix class labels before training

---

## 3. `augment.py` — Dataset Augmentation for YOLO Annotation

### What it does
Takes an **existing annotated YOLO dataset** (images + `.txt` label files) and generates synthetic augmented copies of each training image to expand the dataset size.

For each original training image, it creates `AUG_PER_IMAGE` (default: 3) augmented variants using the **Albumentations** library. Each augmented image gets a matching label file with bounding box coordinates transformed to match.

#### Augmentation transforms applied
| Transform | Probability | Effect |
|---|---|---|
| `HorizontalFlip` | 50% | Mirror left-right |
| `VerticalFlip` | 20% | Mirror top-bottom |
| `Rotate(limit=25°)` | 60% | Random rotation up to ±25° |
| `RandomBrightnessContrast` | 50% | Lighting variation |
| `HueSaturationValue` | 40% | Color shift (hue/saturation/value) |
| `MotionBlur(blur_limit=3)` | 20% | Simulates camera motion / drone vibration |
| `RandomScale(limit=0.15)` | 40% | Zooms in or out by up to 15% |
| `CoarseDropout` | 30% | Randomly blacks out small regions (occlusion simulation) |

Bounding boxes are **automatically adjusted** to stay valid after each transform. Any box that ends up entirely out-of-frame after transformation is dropped.

#### Safe to re-run
The script writes a `augment_progress.txt` file in each class folder. If interrupted and restarted, it skips images already processed and only augments new ones. Augmented files are named `<original>_aug0.jpg`, `<original>_aug1.jpg`, etc., and are written directly into the same `train/` folder so no `data.yaml` changes are needed.

### Configuration (top of file)
```python
TARGET_CLASSES = ["Rice", "Cassava", ...]  # List your class folder names here
BASE_DIR = r""                             # <-- Set to your root dataset directory
AUG_PER_IMAGE = 3                          # Augmented copies per original image
```

### How to run
```bash
pip install albumentations opencv-python
python augment.py
```

### When to use
- Your training set has fewer images than needed (aim for >= 500-1000 per class)
- The model is overfitting (training accuracy >> validation accuracy)
- You want the model to be robust to lighting changes, rotation, and partial occlusions
- After scraping with `fast_scrape.py` but before running `multi_train.py`

> **Note:** Do not augment validation or test sets — they should remain original images so metrics reflect real-world performance.

---

## 4. `multi_train.py` — Sequential Multi-Dataset YOLO Trainer

### What it does
Trains a separate **YOLO11 detection model** for each crop/disease dataset found in the base directory, one after the other. This is ideal when you have multiple independent crop folders (e.g., one per crop type) each with its own `data.yaml`.

#### Intelligent model auto-selection
Rather than using one fixed model for all datasets, the script picks the right YOLO11 variant based on how many training images each dataset has:

| Training images | Model selected | Batch size |
|---|---|---|
| < 5,000 | `yolo11m.pt` (medium) | 16 |
| 5,000 – 27,999 | `yolo11l.pt` (large) | 12 |
| >= 28,000 | `yolo11x.pt` (extra-large) | 8 |

This avoids using a massive model on a tiny dataset (overfitting) or a tiny model on a huge dataset (underfitting) without any manual tuning.

#### Pre-training data validation
Before training starts, the script checks every dataset for:
- Minimum image count (>= 50 per split by default)
- Corrupt or unreadable image files
- Missing label files
- Empty label files (warns if >30% are empty)
- Class IDs out of range for the declared `nc`
- **Train/val data leakage** — detects if any validation image is byte-identical to a training image (would inflate validation metrics)

Training only begins if all checks pass. Use `--skip-validation` to bypass for trusted datasets.

#### Power-off / crash recovery
Every epoch writes a `last.pt` checkpoint. If the process is killed (power cut, crash, Ctrl+C), the script detects the orphaned checkpoint on the next run and calls `model.train(resume=True)` — YOLO picks up from exactly the last completed epoch. A `TRAINING_COMPLETE.txt` marker is written when a dataset finishes, so already-completed datasets are silently skipped on re-runs.

#### Training hyperparameters (global, top of file)
| Parameter | Value | Notes |
|---|---|---|
| `IMGSZ` | 640 | Input image size |
| `EPOCHS` | 100 | Max epochs (early stopping via PATIENCE) |
| `PATIENCE` | 15 | Stop if mAP doesn't improve for 15 epochs |
| `DEVICE` | `"0"` | GPU index (change to `"cpu"` for CPU) |
| `WORKERS` | 16 | DataLoader worker threads |
| `CACHE` | `"disk"` | Cache images to disk for faster epoch loading |
| `AMP` | True | Mixed precision (FP16) — halves VRAM usage |
| `COS_LR` | True | Cosine learning rate schedule |
| `SAVE_PERIOD` | 1 | Save checkpoint every epoch |
| `CLOSE_MOSAIC` | 10 | Disable mosaic aug in last 10 epochs |

These settings are tuned for an **RTX 4090 (24 GB VRAM) + 64 GB RAM**. Adjust `batch`, `WORKERS`, and `CACHE` for your hardware.

### How to run

**Basic (auto-detect all datasets, auto-select model):**
```bash
python multi_train.py --base-dir "path/to/your/datasets"
```

**Train only specific crops:**
```bash
python multi_train.py --base-dir "path/to/datasets" --only Rice Mango
```

**Force a specific model for all datasets:**
```bash
python multi_train.py --base-dir "path/to/datasets" --model yolo11x.pt
```

**Skip data integrity checks (for trusted datasets):**
```bash
python multi_train.py --base-dir "path/to/datasets" --skip-validation
```

**Custom output directory:**
```bash
python multi_train.py --base-dir "path/to/datasets" --output-dir "path/to/runs"
```

### Expected dataset folder structure
Each subfolder under `--base-dir` must have this layout:
```
<base_dir>/
  CropName/
    data.yaml        <- nc, names, train/val/test paths
    images/
      train/
      val/
      test/
    labels/
      train/
      val/
      test/
```

### Output structure
```
runs_det/
  CropName/
    CropName_det/
      weights/
        best.pt      <- best model (use this for inference)
        last.pt      <- latest checkpoint (used for resume)
      results.csv    <- mAP, precision, recall per epoch
      TRAINING_COMPLETE.txt  <- written when done
  training_status.json  <- global state tracker
  _fixed_yamls/         <- auto-corrected yaml copies used during training
```

### When to use
- You have multiple independent crop datasets and want to train them all without babysitting each one
- You need power-off safety (long overnight training sessions)
- You want auto model sizing instead of manually guessing the right YOLO variant

---

## Complete Pipeline — Recommended Order

```
1. fast_scrape.py
   └─ Collect ~750 quality images per class from iNat / DDG / Wikimedia
      Output: train/, valid/, test/ image folders

2. identify_unnamed_classes_local.py   (only if needed)
   └─ Fix Class_0, Class_1, ... labels using filename patterns
      Output: updated data.yaml files

3. augment.py
   └─ Expand training set 3x with augmented image+label pairs
      Output: _aug0/_aug1/_aug2 images written into existing train/ folders

4. multi_train.py
   └─ Train YOLO11 model for each crop, auto-select model size
      Output: best.pt weights + metrics per crop
```

---

## Dependencies Quick Reference

```bash
# Scraper
pip install duckduckgo-search requests pillow imagehash opencv-python

# Class name recovery
pip install pillow pyyaml

# Augmentation
pip install albumentations opencv-python

# Training
pip install ultralytics pillow pyyaml
```

> **GPU requirement for training:** YOLO11x/l training is practical only with a CUDA-capable GPU (>= 8 GB VRAM recommended). The scraper, class recovery, and augmentation scripts are CPU-only and run fine on any machine.
