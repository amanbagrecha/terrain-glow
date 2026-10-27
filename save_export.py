import base64
import os
import re

import tg_common as tg

ALLOWED = (".png", ".webm", ".mp4")
MAX_BYTES = 200 * 1024 * 1024


def main(name: str = "terrain-glow.png", data: str = ""):
    base = os.path.basename(name)
    stem, ext = os.path.splitext(base)
    if ext.lower() not in ALLOWED:
        raise ValueError(f"File type must be one of {', '.join(ALLOWED)}")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "terrain-glow"
    if len(data) > MAX_BYTES * 4 // 3 + 4:
        raise ValueError("The file is too large")
    raw = base64.b64decode(data or "", validate=True)
    if not raw:
        raise ValueError("No file data")
    os.makedirs(tg.EXPORT_DIR, exist_ok=True)
    path = os.path.join(tg.EXPORT_DIR, stem + ext.lower())
    n = 2
    while os.path.exists(path):
        path = os.path.join(tg.EXPORT_DIR, f"{stem}-{n}{ext.lower()}")
        n += 1
    tg.write_bytes(path, raw)
    return {"path": tg.rel(path), "bytes": len(raw)}
