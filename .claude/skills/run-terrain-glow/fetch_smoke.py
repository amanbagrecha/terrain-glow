import json
import os
import sys
import time
import warnings

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, APP)
warnings.filterwarnings("ignore")

import numpy as np
from PIL import Image

import fetch_worker as fw
import terrain


def timed(fn, *args):
    t = time.time()
    return fn(*args), round(time.time() - t, 1)


def main(comp="day", lat=35.3606, lon=138.7274, span=22.0, aspect=1.7778, quality="preview", season="winter",
         date="", out="/tmp/terrain_glow_smoke.png"):
    t0 = time.time()
    su = fw._load_su()
    _, _, _, dem_spec, img_spec = terrain.specs(float(lat), float(lon), float(span), float(aspect), quality, comp,
                                                season, date=date)
    (_, dem), dem_s = timed(fw._fetch_dem, su, dem_spec)
    (data, meta), img_s = timed(fw._fetch_img, su, img_spec, lambda *a: None, lambda: None)
    total_s = round(time.time() - t0, 1)
    img = np.frombuffer(data, np.uint8).reshape(meta["height"], meta["width"], 4)
    Image.fromarray(img[..., :3]).save(out)
    print(json.dumps({"label": meta["label"], "scenes": meta["scenes"], "coverage": meta["coverage"],
                      "size": [meta["width"], meta["height"]], "dem_m": [round(dem["min"], 1), round(dem["max"], 1)],
                      "img_s": img_s, "dem_s": dem_s, "total_s": total_s, "png": out}))


if __name__ == "__main__":
    main(*sys.argv[1:])
