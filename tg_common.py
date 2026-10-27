import datetime as dt
import hashlib
import json
import math
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_VERSION = "v5"
CACHE_DIR = os.path.join(APP_DIR, ".fused", "cache", CACHE_VERSION)
EXPORT_DIR = os.path.join(APP_DIR, ".fused", "data", "exports")
PACKAGE_COMMIT = "ee94a99798532e5f2686bb30a0af2f9e6ce61a26"
PACKAGE_URL = f"https://github.com/fusedio/udfs/tree/{PACKAGE_COMMIT}/public/sentinel_utils/"
PACKAGE_DIR = os.path.join(APP_DIR, ".fused", "cache", "sentinel_utils", PACKAGE_COMMIT)
CREDENTIALS = os.environ.get("FUSED_RENDER_FUSED_CREDENTIALS") or os.path.expanduser("~/.fused/credentials")
USER_AGENT = "TerrainGlow/1.0 (fused-render app; contact: https://fused.io)"
COMPS = ("lc", "day", "median", "single")
SEASONS = ("summer", "winter", "year", "custom")
QUALITY = {"preview": (768, 12.0), "high": (2048, 10.0), "print": (3600, 6.5)}
TILE_PX = 1024
DEM_MIN_M = 15.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def area_bbox(lat, lon, span_km, aspect):
    w_km, h_km = (span_km, span_km / aspect) if aspect >= 1 else (span_km * aspect, span_km)
    dlat = h_km / 2 / 110.574
    dlon = w_km / 2 / (111.320 * max(math.cos(math.radians(lat)), 0.05))
    bbox = [round(lon - dlon, 6), round(lat - dlat, 6), round(lon + dlon, 6), round(lat + dlat, 6)]
    return bbox, w_km, h_km


def _grid(long_px, aspect):
    if aspect >= 1:
        w, h = long_px, max(64, round(long_px / aspect))
    else:
        w, h = max(64, round(long_px * aspect)), long_px
    nx, ny = math.ceil(w / TILE_PX), math.ceil(h / TILE_PX)
    tw, th = math.ceil(w / nx), math.ceil(h / ny)
    return {"width": tw * nx, "height": th * ny, "nx": nx, "ny": ny, "tile": [tw, th]}


def plan(lat, lon, span_km, aspect, quality):
    long_max, min_m = QUALITY.get(quality, QUALITY["high"])
    bbox, w_km, h_km = area_bbox(lat, lon, span_km, aspect)
    span_m = max(w_km, h_km) * 1000
    img_long = int(clamp(round(span_m / min_m), 256, long_max))
    dem_long = int(min(img_long, max(256, round(span_m / DEM_MIN_M))))
    img, dem = _grid(img_long, aspect), _grid(dem_long, aspect)
    img["pixel_m"] = round(w_km * 1000 / img["width"], 2)
    dem["pixel_m"] = round(w_km * 1000 / dem["width"], 3)
    return {"bbox": bbox, "km": [round(w_km, 3), round(h_km, 3)], "img": img, "dem": dem}


def tile_boxes(bbox, nx, ny):
    w, s, e, n = bbox
    dx, dy = (e - w) / nx, (n - s) / ny
    return [[round(w + i * dx, 7), round(n - (j + 1) * dy, 7), round(w + (i + 1) * dx, 7), round(n - j * dy, 7)]
            for j in range(ny) for i in range(nx)]


def _iso(d):
    return d.strftime("%Y-%m-%d")


def _last_window(today, m1, d1, m2, d2, wraps):
    for year in (today.year, today.year - 1, today.year - 2):
        start = dt.date(year - 1 if wraps else year, m1, d1)
        end = dt.date(year, m2, d2)
        if end < today:
            return start, end
    return start, end


def date_range(lat, season, start="", end="", today=None):
    today = today or dt.date.today()
    north = lat >= 0
    if season == "custom" and start and end:
        a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if b < a:
            a, b = b, a
        return _iso(a), _iso(b)
    if season == "year":
        return _iso(today - dt.timedelta(days=365)), _iso(today - dt.timedelta(days=1))
    if season == "winter":
        a, b = _last_window(today, 12, 15, 3, 15, True) if north else _last_window(today, 6, 15, 9, 15, False)
    else:
        a, b = _last_window(today, 6, 15, 9, 15, False) if north else _last_window(today, 12, 1, 3, 1, True)
    return _iso(a), _iso(b)


def key_of(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_json(path, obj):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def write_bytes(path, data):
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def rel(path):
    return os.path.relpath(path, APP_DIR)


def nice_range(start, end):
    a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    fa = f"{a.day} {a:%b}" + ("" if a.year == b.year else f" {a.year}")
    return f"{fa} – {b.day} {b:%b} {b.year}"


def nice_day(day):
    d = dt.date.fromisoformat(day)
    return f"{d.day} {d:%b} {d.year}"


def package_dir(fused):
    import shutil
    import tempfile

    if os.environ.get("SENTINEL_UTILS_PATH"):
        return os.environ["SENTINEL_UTILS_PATH"]
    if not os.path.isfile(os.path.join(PACKAGE_DIR, "meta.json")):
        os.makedirs(os.path.dirname(PACKAGE_DIR), exist_ok=True)
        tmp = tempfile.mkdtemp(dir=os.path.dirname(PACKAGE_DIR))
        try:
            fused.load(PACKAGE_URL).to_directory(tmp, overwrite=True)
            os.replace(tmp, PACKAGE_DIR)
        except OSError:
            if not os.path.isfile(os.path.join(PACKAGE_DIR, "meta.json")):
                raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return PACKAGE_DIR


def load_package(fused):
    return fused.load(package_dir(fused))
