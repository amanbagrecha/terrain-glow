import json
import os
import shutil
import subprocess
import sys
import time

import tg_common as tg

WORKER = os.path.join(tg.APP_DIR, "fetch_worker.py")
LOCK_AGE = 20
MAX_RUN = 480
MAX_ATTEMPTS = 3
KEEP_ENTRIES = 40
SCENE_CAP = {"lc": 30, "day": 30, "median": 20, "single": 1}
PREVIEW_SCENE_CAP = {"lc": 12, "day": 12, "median": 10, "single": 1}


def _is_worker(pid):
    try:
        out = subprocess.run(["ps", "-p", str(int(pid)), "-o", "command="], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, TypeError, ValueError, subprocess.SubprocessError):
        return False
    return WORKER in out


def _prune(part):
    root = os.path.join(tg.CACHE_DIR, part)
    try:
        entries = sorted((os.path.join(root, n) for n in os.listdir(root)), key=os.path.getmtime, reverse=True)
    except OSError:
        return
    for path in entries[KEEP_ENTRIES:]:
        status = tg.read_json(os.path.join(path, "status.json")) or {}
        if status.get("state") != "running":
            shutil.rmtree(path, ignore_errors=True)


def _spawn(part_dir, part, spec, attempts):
    os.makedirs(part_dir, exist_ok=True)
    lock = os.path.join(part_dir, "lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        if time.time() - os.path.getmtime(lock) < LOCK_AGE:
            return {"state": "running", "elapsed": 0}
        os.utime(lock)
    log = open(os.path.join(part_dir, "log.txt"), "a")
    proc = subprocess.Popen([sys.executable, WORKER, part_dir, part, json.dumps(spec)], cwd=tg.APP_DIR,
                            stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    log.close()
    tg.write_json(os.path.join(part_dir, "status.json"),
                  {"state": "running", "pid": proc.pid, "started": time.time(), "step": "start",
                   "attempts": attempts})
    _prune(part)
    return {"state": "running", "elapsed": 0}


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _fail(part_dir, message):
    tg.write_json(os.path.join(part_dir, "status.json"), {"state": "error", "message": message})
    return {"state": "error", "message": message, "code": None}


def _state(part_dir, part, spec, reset):
    status_path = os.path.join(part_dir, "status.json")
    status = tg.read_json(status_path) or {}
    state = status.get("state")
    if state == "error" and status.get("code") == "login" and (_mtime(tg.CREDENTIALS) or 0) > (_mtime(status_path) or 0):
        reset = True
    if state == "done":
        meta = tg.read_json(os.path.join(part_dir, "meta.json"))
        binary = os.path.join(part_dir, f"{part}.bin")
        if meta and os.path.exists(binary):
            return {"state": "done", "files": {"bin": tg.rel(binary)}, "meta": meta, "seconds": status.get("seconds")}
    if state == "error" and not reset:
        return {"state": "error", "message": status.get("message", "The request failed."), "code": status.get("code")}
    attempts = 0 if reset else status.get("attempts", 0)
    if state == "running":
        age = time.time() - status.get("started", 0)
        if _is_worker(status.get("pid")):
            if age < MAX_RUN:
                return {"state": "running", "elapsed": int(age), "step": status.get("step", ""),
                        "ready": status.get("ready", []), "generation": status.get("generation", 0),
                        "tile": tg.rel(os.path.join(part_dir, "tile_{i}.bin"))}
            os.kill(int(status["pid"]), 15)
            return _fail(part_dir, f"The data job took more than {MAX_RUN // 60} minutes. Use Preview quality or a smaller area.")
        if attempts >= MAX_ATTEMPTS:
            return _fail(part_dir, f"The data job stopped {attempts} times. See log.txt in the app cache.")
    if not os.path.exists(tg.CREDENTIALS):
        return {"state": "login"}
    lock = os.path.join(part_dir, "lock")
    try:
        if time.time() - os.path.getmtime(lock) >= LOCK_AGE:
            os.remove(lock)
    except FileNotFoundError:
        pass
    return _spawn(part_dir, part, spec, attempts + 1)


def specs(lat, lon, span, aspect, quality, comp, season, start="", end="", date=""):
    span = round(tg.clamp(span, 2.0, 50.0), 2)
    aspect = round(tg.clamp(aspect, 0.4, 2.5), 4)
    quality = quality if quality in tg.QUALITY else "high"
    comp = comp if comp in tg.COMPS else "lc"
    season = season if season in tg.SEASONS else "summer"
    layout = tg.plan(lat, lon, span, aspect, quality)
    if comp == "single":
        if not date:
            raise ValueError("Single date needs a date (YYYY-MM-DD).")
        first, last = date, date
    else:
        first, last = tg.date_range(lat, season, start, end)
    bbox = layout["bbox"]
    dem_spec = {"part": "dem", "bbox": bbox, "grid": layout["dem"]}
    img_spec = {"part": "img", "bbox": bbox, "grid": layout["img"], "comp": comp, "start": first, "end": last,
                "mask": None if comp == "single" else "no_cloud", "scene_cap": (PREVIEW_SCENE_CAP if quality == "preview" else SCENE_CAP)[comp]}
    return layout, first, last, dem_spec, img_spec


def main(lat: float = 45.9763, lon: float = 7.6586, span: float = 14.0, aspect: float = 0.8,
         quality: str = "high", comp: str = "lc", season: str = "summer", start: str = "", end: str = "",
         date: str = "", job: str = "", title: str = "", reset: bool = False):
    layout, first, last, dem_spec, img_spec = specs(lat, lon, span, aspect, quality, comp, season, start, end, date)
    dem_dir = os.path.join(tg.CACHE_DIR, "dem", tg.key_of(dem_spec))
    img_dir = os.path.join(tg.CACHE_DIR, "img", tg.key_of(img_spec))
    shared = {"job": job, "title": title or "Terrain Glow"}
    dem_spec.update(shared, sibling=os.path.join(img_dir, "status.json"))
    img_spec.update(shared, sibling=os.path.join(dem_dir, "status.json"))
    dem = _state(dem_dir, "dem", dem_spec, reset)
    img = _state(img_dir, "img", img_spec, reset)
    out = {"plan": layout, "start": first, "end": last, "dem": dem, "img": img}
    if "login" in (dem.get("code"), img.get("code"), dem["state"], img["state"]):
        out["login"] = True
        out["creds_stamp"] = _mtime(tg.CREDENTIALS)
    return out
