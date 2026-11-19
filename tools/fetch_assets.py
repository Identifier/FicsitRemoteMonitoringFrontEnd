"""Fetch the assets the tracker needs but that aren't checked in (game art isn't ours to redistribute):

  - map-tiles/  map tile pyramid, downloaded from satisfactoryinteractivemap.com
  - img/*.png  vehicle pictures, downloaded from the Satisfactory wiki (satisfactory.wiki.gg)
  - img/icons/<name>.png  item and building icons for the Production and Power tabs (also from the wiki)

  python tools/fetch_assets.py

Pillow (pip install pillow) is optional; with it the pictures are shrunk (vehicles 96 px, icons 64 px).
"""
import argparse
import concurrent.futures
import http.client
import io
import json
import pathlib
import random
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "FicsitRemoteMonitoringFrontEnd/1.0 (asset fetch)"}
WIKI_API = "https://satisfactory.wiki.gg/api.php"
MAP_TILE_URL = "https://satisfactoryinteractivemap.com/tiles/game"
MAP_ZOOMS = range(1, 6)
DOWNLOAD_ATTEMPTS = 5
DOWNLOAD_WORKERS = 4
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
# tracker image name -> wiki file name
VEHICLE_IMAGES = {
    "factory-cart": "Factory Cart.png", "golden-factory-cart": "Golden Factory Cart.png", "tractor": "Tractor.png",
    "truck": "Truck.png", "fluid-truck": "Fluid Truck.png", "explorer": "Explorer.png",
    "cyber-wagon": "Cyber Wagon.png", "train": "Electric Locomotive.png", "drone": "Drone.png",
}

# buildings shown with an icon on the Production and Power tabs (every item in items.json gets one too)
ICON_BUILDINGS = [
    "Smelter", "Foundry", "Constructor", "Assembler", "Manufacturer", "Refinery", "Packager", "Blender",
    "Particle Accelerator", "Converter", "Quantum Encoder", "Miner Mk.1", "Miner Mk.2", "Miner Mk.3", "Water Extractor",
    "Oil Extractor", "Resource Well Pressurizer", "Resource Well Extractor", "Biomass Burner", "Coal-Powered Generator",
    "Fuel-Powered Generator", "Geothermal Generator", "Nuclear Power Plant", "Alien Power Augmenter", "Power Storage",
    "AWESOME Sink", "AWESOME Shop", "Storage Container", "Industrial Storage Container", "Personal Storage Box",
    "Pipeline Pump Mk.1", "Pipeline Pump Mk.2", "Valve", "Pipeline Junction", "Pipeline T-Junction", "Fluid Buffer",
    "Industrial Fluid Buffer", "Truck Station", "Train Station", "Freight Platform", "Fluid Freight Platform",
    "Empty Platform", "Drone Port", "Dimensional Depot Uploader", "Space Elevator", "The HUB", "Radar Tower",
    "Hypertube Entrance", "Craft Bench", "Equipment Workshop", "Lookout Tower", "Blueprint Designer",
    "Power Switch", "Priority Power Switch",
    "Medical Storage Box", "Hazard Storage Box",
    "Geyser",   # resource node type (geothermal), listed with the ores on the Progression tab
]
# things a player can carry that items.json doesn't list (Inventory tab)
ICON_EXTRA = ["FICSIT Coupon", "Hard Drive"]
icon_slug = lambda name: re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")   # same rule as the page's iconSlug()


def valid_webp(data):
    return (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            and int.from_bytes(data[4:8], "little") + 8 == len(data))


def valid_map_tile(path):
    if not path.is_file():
        return False
    try:
        with path.open("rb") as f:
            data = f.read()
    except FileNotFoundError:
        return False
    return valid_webp(data)


def retry_delay(attempt, retry_after=None):
    try:
        return min(60, max(0, float(retry_after)))
    except (TypeError, ValueError):
        return min(30, 2 ** (attempt - 1)) + random.uniform(0, 0.5)


def read_url(req, label, validate=None):
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        retry_after = None
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
            if validate is None or validate(data):
                return data
            error = ValueError("response failed validation")
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE_HTTP:
                raise RuntimeError(f"Could not download {label}: HTTP {e.code}") from e
            error = e
            retry_after = e.headers.get("Retry-After")
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            error = e
        if attempt == DOWNLOAD_ATTEMPTS:
            raise RuntimeError(f"Could not download {label} after {attempt} attempts: {error}") from error
        delay = retry_delay(attempt, retry_after)
        print(f"{label}: {error}; retrying in {delay:.1f}s ({attempt + 1}/{DOWNLOAD_ATTEMPTS})", flush=True)
        time.sleep(delay)


def download_map_tile(z, x, y):
    url = f"{MAP_TILE_URL}/{z}/{y}/{x}.webp"
    out = ROOT / "map-tiles" / str(z) / str(y) / f"{x}.webp"
    if valid_map_tile(out):
        return
    req = urllib.request.Request(url, headers=UA)
    data = read_url(req, f"map tile {z}/{y}/{x}", valid_webp)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(out.name + ".tmp")
    temp.write_bytes(data)
    temp.replace(out)


def fetch_map_tiles():
    tiles = [(z, x, y) for z in MAP_ZOOMS for y in range(2 ** z) for x in range(2 ** z)]
    missing, cached = [], 0
    for z, x, y in tiles:
        path = ROOT / "map-tiles" / str(z) / str(y) / f"{x}.webp"
        if valid_map_tile(path):
            cached += 1
        else:
            missing.append((z, x, y))
    if not missing:
        print(f"map tiles: {cached}/{len(tiles)} already downloaded")
        return
    if cached:
        print(f"map tiles: resuming with {cached}/{len(tiles)} already downloaded")
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        jobs = [pool.submit(download_map_tile, z, x, y) for z, x, y in missing]
        for done, job in enumerate(concurrent.futures.as_completed(jobs), 1):
            job.result()
            if done % 100 == 0:
                print(f"map tiles: {cached + done}/{len(tiles)} downloaded")
    print(f"map tiles: {cached + len(missing)}/{len(tiles)} downloaded")


def wiki_urls(files):
    """wiki file name -> download URL (50 titles per API call)"""
    urls = {}
    total = (len(files) + 49) // 50
    print(f"wiki file URLs: looking up {len(files)} files", flush=True)
    for batch, k in enumerate(range(0, len(files), 50), 1):
        titles = "|".join("File:" + f for f in files[k:k + 50])
        q = urllib.parse.urlencode({"action": "query", "titles": titles, "prop": "imageinfo", "iiprop": "url", "format": "json"})
        req = urllib.request.Request(f"{WIKI_API}?{q}", headers=UA)
        pages = json.loads(read_url(req, f"wiki file URL batch {batch}/{total}"))["query"]["pages"]
        urls.update({p["title"].removeprefix("File:"): p["imageinfo"][0]["url"] for p in pages.values() if p.get("imageinfo")})
        print(f"wiki file URLs: {batch}/{total} batches resolved", flush=True)
    return urls


def download_image(out, url, size, Image):
    data = read_url(urllib.request.Request(url, headers=UA), out.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_name(out.name + ".tmp")
    if Image:
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        im.save(temp, format="PNG", optimize=True)
    else:
        temp.write_bytes(data)
    temp.replace(out)


def download(wanted, size, label):
    """wanted: {output path: wiki file name}"""
    pending = {out: wiki_file for out, wiki_file in wanted.items()
               if not out.is_file() or out.stat().st_size == 0}
    cached = len(wanted) - len(pending)
    if not pending:
        print(f"{label}: {cached}/{len(wanted)} already downloaded")
        return
    print(f"{label}: {cached}/{len(wanted)} already downloaded; resolving URLs for {len(pending)} files", flush=True)
    urls = wiki_urls(sorted(set(pending.values())))
    try:
        from PIL import Image
    except ImportError:
        Image = None
    missing, tasks = [], {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        for out, wiki_file in pending.items():
            url = urls.get(wiki_file)
            if not url:
                missing.append(wiki_file)
                continue
            tasks[pool.submit(download_image, out, url, size, Image)] = out
        for done, job in enumerate(concurrent.futures.as_completed(tasks), 1):
            job.result()
            if done % 10 == 0 or done == len(tasks):
                print(f"{label}: {cached + done}/{len(wanted)} files ready", flush=True)
    if missing:
        print(f"{label}: not on the wiki: {', '.join(missing)}")


def fetch_images():
    download({ROOT / "img" / f"{name}.png": f for name, f in VEHICLE_IMAGES.items()}, 96, "vehicle pictures")


def fetch_icons():
    items = [i["name"] for i in json.loads((ROOT / "items.json").read_text(encoding="utf-8"))]
    download({ROOT / "img" / "icons" / f"{icon_slug(n)}.png": f"{n}.png" for n in items + ICON_BUILDINGS + ICON_EXTRA}, 64, "item/building icons")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch the tracker's map tiles, vehicle pictures and item/building icons")
    ap.add_argument("--skip-images", action="store_true", help="skip vehicle pictures and item/building icons")
    args = ap.parse_args()
    fetch_map_tiles()
    if not args.skip_images:
        fetch_images()
        fetch_icons()
    sys.exit(0)
