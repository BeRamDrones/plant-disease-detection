"""
Drone crop dataset scraper — iNaturalist (primary) + DuckDuckGo + Wikimedia
Multi-threaded optimized version.
Target: ~750 quality images per class after filters
"""

from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
import requests
from PIL import Image
import imagehash
import cv2
import shutil, csv, logging, random, time
import concurrent.futures
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
INAT_TARGET      = 750    # candidates to attempt from iNaturalist
DDG_PER_QUERY    = 100    # DDG max per query
WIKI_PER_TERM    = 50     # Wikimedia results per search term

SPLIT_RATIOS     = {"train": 0.80, "valid": 0.10, "test": 0.10}
TEMP_DIR         = Path("temp_downloads_fast")
AUDIT_CSV        = Path("scrape_audit_fast.csv")

MIN_SIDE_PX      = 150
MAX_ASPECT_RATIO = 2.5
BLUR_THRESHOLD   = 40.0   
PHASH_DISTANCE   = 8
VALID_EXT        = (".jpg", ".jpeg", ".png", ".webp")

MAX_WORKERS      = 15

HEADERS = {
    "User-Agent": "DroneDatasetBot/2.0 (academic research, non-commercial; open-source-scraper)"
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Class definitions ─────────────────────────────────────────────────────────
CLASSES = {

    "Coriander___healthy": {
        "inat_taxon": "Coriandrum sativum",
        "ddg": [
            "coriander plant single plant nadir 1m drone leaf texture visible",
            "coriander plant top down close UAV low altitude leaves clear",
            "coriander crop foliage close up overhead drone view field",
        ],
        "wikimedia": ["coriander plant canopy overhead", "coriandrum sativum top view"],
    },
    "Linseed_(flax)___healthy": {
        "inat_taxon": "Linum usitatissimum",
        "ddg": [
            "linseed flax plant single plant nadir 2m drone leaf texture visible",
            "linseed flax plant top down close UAV low altitude leaves clear",
            "linseed crop plant close up overhead drone view field India",
        ],
        "wikimedia": ["flax plant canopy overhead", "linseed top view close"],
    },
    "Mint___healthy": {
        "inat_taxon": "Mentha arvensis",
        "ddg": [
            "mint pudina plant single plant nadir 1m drone leaf texture visible",
            "mint pudina plant top down close UAV low altitude leaves clear",
            "mint crop foliage close up overhead drone view field India",
        ],
        "wikimedia": ["mint plant canopy overhead", "mentha arvensis top view"],
    },
}


# ── Download helper ───────────────────────────────────────────────────────────

def download_url(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        if r.status_code == 200 and len(r.content) > 4000:
            dest.write_bytes(r.content)
            return True
    except Exception:
        pass
    return False

def thread_download(item: dict) -> bool:
    url = item["url"]
    dest = item["dest"]
    return download_url(url, dest)

def parallel_download(items: list[dict]) -> int:
    downloaded = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(thread_download, item): item for item in items}
        for future in concurrent.futures.as_completed(futures):
            if future.result():
                downloaded += 1
    return downloaded

# ── Source 1: iNaturalist ─────────────────────────────────────────────────────

def resolve_taxon_id(taxon_name: str) -> int | None:
    try:
        r = requests.get(
            "https://api.inaturalist.org/v1/taxa",
            params={"q": taxon_name, "rank": "species", "per_page": 1},
            timeout=10,
            headers=HEADERS
        )
        results = r.json().get("results", [])
        if results:
            return results[0]["id"]
    except Exception as e:
        log.warning("iNat taxon lookup failed for '%s': %s", taxon_name, e)
    return None

def fetch_inat(taxon_name: str, dest_dir: Path, limit: int) -> int:
    if not taxon_name:
        return 0

    taxon_id = resolve_taxon_id(taxon_name)
    if not taxon_id:
        return 0

    log.info("  iNat: taxon_id=%d for %s", taxon_id, taxon_name)

    per_page = 50
    page_pool = list(range(1, 150))
    random.shuffle(page_pool)

    pages_needed = (limit // per_page) + 15
    urls_to_download = []
    
    for page in page_pool[:pages_needed]:
        if len(urls_to_download) >= limit:
            break
        try:
            resp = requests.get(
                "https://api.inaturalist.org/v1/observations",
                params={
                    "taxon_id":      taxon_id,
                    "quality_grade": "research",
                    "photos":        "true",
                    "per_page":      per_page,
                    "page":          page,
                    "captive":       "false",
                },
                timeout=15,
                headers=HEADERS
            )
            resp.raise_for_status()
            observations = resp.json().get("results", [])

            if not observations:
                continue

            for obs in observations:
                for photo in obs.get("photos", []):
                    url = photo.get("url", "").replace("/square.", "/large.")
                    if not url or not url.startswith("http"):
                        continue
                    fname = dest_dir / f"inat_{taxon_id}_pg{page}_i{len(urls_to_download)}.jpg"
                    urls_to_download.append({"url": url, "dest": fname})
                    if len(urls_to_download) >= limit:
                        break
                if len(urls_to_download) >= limit:
                    break
                    
        except requests.HTTPError as e:
            log.warning("  iNat HTTP %s on page %d", e.response.status_code, page)
        except Exception as e:
            pass

    log.info(f"  iNat: discovered {len(urls_to_download)} image URLs. Downloading...")
    downloaded = parallel_download(urls_to_download)
    log.info(f"  iNat: downloaded {downloaded} images")
    return downloaded

# ── Source 2: DuckDuckGo ──────────────────────────────────────────────────────

def fetch_ddg(queries: list[str], dest_dir: Path) -> int:
    urls_to_download = []
    with DDGS() as ddgs:
        for query in queries:
            try:
                # new DDGS client might use max_results
                results = list(ddgs.images(
                    query,
                    max_results=DDG_PER_QUERY,
                ))
                for i, r in enumerate(results):
                    url = r.get("image", "")
                    if not url:
                        continue
                    ext = Path(url.split("?")[0]).suffix.lower()
                    if ext not in VALID_EXT:
                        ext = ".jpg"
                    fname = dest_dir / f"ddg_{query[:12].replace(' ','_')}_{i}_{len(urls_to_download)}{ext}"
                    urls_to_download.append({"url": url, "dest": fname})
            except DuckDuckGoSearchException as e:
                log.warning("  DDG Rate limit or error on '%s': %s", query, e)
            except Exception as e:
                log.warning("  DDG '%s' failed: %s", query, e)

    log.info(f"  DDG: discovered {len(urls_to_download)} image URLs. Downloading...")
    downloaded = parallel_download(urls_to_download)
    log.info(f"  DDG: downloaded {downloaded} images")
    return downloaded

# ── Source 3: Wikimedia Commons ───────────────────────────────────────────────

def fetch_wikimedia(search_terms: list[str], dest_dir: Path) -> int:
    urls_to_download = []

    for term in search_terms:
        try:
            resp = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action":       "query",
                    "generator":    "search",
                    "gsrnamespace": 6,
                    "gsrsearch":    f"filetype:bitmap {term}",
                    "gsrlimit":     WIKI_PER_TERM,
                    "prop":         "imageinfo",
                    "iiprop":       "url|size",
                    "iiurlwidth":   800,
                    "format":       "json",
                },
                timeout=15,
                headers=HEADERS
            )
            pages = resp.json().get("query", {}).get("pages", {})

            for pid, page in pages.items():
                info = page.get("imageinfo", [{}])[0]
                url  = info.get("thumburl") or info.get("url", "")
                if not url:
                    continue
                if not any(url.lower().split("?")[0].endswith(e) for e in VALID_EXT):
                    continue
                fname = dest_dir / f"wiki_{term[:10].replace(' ','_')}_{pid}.jpg"
                urls_to_download.append({"url": url, "dest": fname})

        except Exception as e:
            log.warning("  Wikimedia '%s' failed: %s", term, e)

    log.info(f"  Wiki: discovered {len(urls_to_download)} image URLs. Downloading...")
    downloaded = parallel_download(urls_to_download)
    log.info(f"  Wiki: downloaded {downloaded} images")
    return downloaded

# ── Quality pipeline ──────────────────────────────────────────────────────────

def validate(path: Path) -> tuple[bool, str]:
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as e:
        return False, f"corrupt:{e}"
    try:
        with Image.open(path) as img:
            img = img.convert("RGB")
            w, h = img.size
            if w < MIN_SIDE_PX or h < MIN_SIDE_PX:
                return False, f"too_small:{w}x{h}"
            if max(w / h, h / w) > MAX_ASPECT_RATIO:
                return False, "bad_aspect"
    except Exception as e:
        return False, f"pil_err:{e}"
    return True, ""

def blur_ok(path: Path) -> bool:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False
    return float(cv2.Laplacian(img, cv2.CV_64F).var()) >= BLUR_THRESHOLD

def process_file_quality(f: Path) -> dict:
    ok, reason = validate(f)
    if not ok:
        return {"file": f, "status": "invalid", "reason": reason}
    if not blur_ok(f):
        return {"file": f, "status": "blurry", "reason": "blurry"}
    try:
        with Image.open(f) as img:
            h = imagehash.phash(img)
            return {"file": f, "status": "ok", "hash": h}
    except Exception:
        return {"file": f, "status": "error", "reason": "hash_error"}

def run_quality_pipeline(src_dir: Path) -> list[Path]:
    files = [f for f in src_dir.iterdir()
             if f.is_file() and f.suffix.lower() in VALID_EXT]
    
    kept = []
    seen_hashes = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = executor.map(process_file_quality, files)
        
        for res in results:
            if res["status"] != "ok":
                continue
            
            h = res["hash"]
            if any((h - s) <= PHASH_DISTANCE for s in seen_hashes):
                continue
                
            seen_hashes.append(h)
            kept.append(res["file"])
            
    return kept

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    TEMP_DIR.mkdir(exist_ok=True)
    audit = []

    for class_name, cfg in CLASSES.items():
        log.info("═══ %s ═══", class_name)
        class_tmp = TEMP_DIR / class_name
        class_tmp.mkdir(exist_ok=True)

        inat_n = fetch_inat(cfg["inat_taxon"], class_tmp, limit=INAT_TARGET)
        ddg_n  = fetch_ddg(cfg["ddg"], class_tmp)
        wiki_n = fetch_wikimedia(cfg["wikimedia"], class_tmp)

        total_raw = inat_n + ddg_n + wiki_n
        log.info("  Raw total: %d  (iNat:%d  DDG:%d  Wiki:%d)",
                 total_raw, inat_n, ddg_n, wiki_n)

        kept = run_quality_pipeline(class_tmp)
        log.info("  After filters: %d / %d kept", len(kept), total_raw)

        if not kept:
            audit.append({"class": class_name, "raw": total_raw, "kept": 0,
                          "train": 0, "valid": 0, "test": 0})
            continue

        random.shuffle(kept)
        n = len(kept)
        t = int(n * SPLIT_RATIOS["train"])
        v = t + int(n * SPLIT_RATIOS["valid"])
        splits = {"train": kept[:t], "valid": kept[t:v], "test": kept[v:]}

        counts = {}
        for split_name, files in splits.items():
            dst = Path(split_name) / class_name
            dst.mkdir(parents=True, exist_ok=True)
            for f in files:
                shutil.move(str(f), str(dst / f"wild_fast_{f.name}"))
            counts[split_name] = len(files)
            log.info("  → %s: %d", split_name, len(files))

        audit.append({"class": class_name, "raw": total_raw,
                      "kept": len(kept), **counts})

    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    with AUDIT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["class","raw","kept","train","valid","test"])
        w.writeheader()
        w.writerows(audit)

    # Final summary
    print(f"\n{'Class':<32} {'Raw':>5} {'Kept':>5} {'Train':>6} {'Val':>5} {'Test':>5}")
    print("─" * 58)
    for r in audit:
        print(f"{r['class']:<32} {r.get('raw',0):>5} {r.get('kept',0):>5}"
              f" {r.get('train',0):>6} {r.get('valid',0):>5} {r.get('test',0):>5}")
    
    total_kept = sum(r.get("kept", 0) for r in audit)
    print(f"\nTotal images kept across all classes: {total_kept}")
    print(f"Full audit saved to: {AUDIT_CSV}")

if __name__ == "__main__":
    main()
