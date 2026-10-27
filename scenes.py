import json
import os
import subprocess
import sys

import tg_common as tg

WORKER = os.path.join(tg.APP_DIR, "fetch_worker.py")


def main(lat: float = 45.9763, lon: float = 7.6586, span: float = 14.0, aspect: float = 0.8, season: str = "summer",
         start: str = "", end: str = "", cloud: float = 80.0):
    span = round(tg.clamp(span, 2.0, 50.0), 2)
    bbox = tg.area_bbox(lat, lon, span, round(tg.clamp(aspect, 0.4, 2.5), 4))[0]
    first, last = tg.date_range(lat, season if season in tg.SEASONS else "summer", start, end)
    spec = {"bbox": bbox, "start": first, "end": last, "cloud": cloud}
    path = os.path.join(tg.CACHE_DIR, "scenes", tg.key_of(spec) + ".json")
    cached = tg.read_json(path)
    if cached is not None:
        return cached
    proc = subprocess.run([sys.executable, WORKER, "scenes", json.dumps(spec)], cwd=tg.APP_DIR, capture_output=True,
                          text=True, timeout=55)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if proc.returncode != 0 or not lines:
        raise RuntimeError((proc.stderr.strip().splitlines() or ["The scene search failed."])[-1])
    out = {"start": first, "end": last, "bbox": bbox, "scenes": json.loads(lines[-1])}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tg.write_json(path, out)
    return out
