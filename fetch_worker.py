import io
import json
import os
import re
import sys
import time
import urllib.request
import warnings


def _prefer_own_packages():
    own = [p for p in sys.path if p.endswith("site-packages")]
    sys.path[:] = own + [p for p in sys.path if p not in own]


def _use_certifi_roots():
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())


_prefer_own_packages()
_use_certifi_roots()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tg_common as tg

BANDS = ["B04", "B03", "B02", "B08"]
MAX_PIXELS = 200_000_000
CLOUD_CAP = {"lc": 60.0, "day": 60.0, "median": 50.0}
DAY_COVER = 99.5
LABEL = {"lc": "Least-cloudy mosaic", "day": "Clearest-day mosaic", "median": "Median composite"}
REMOTE_TIMEOUT = 150
MAX_WORKERS = 16
POLL_SECONDS = 0.05
FINAL_ERRORS = ("NoDataError", "ValueError")
QUERY_HEADERS = ("su_constants", "su_geometry", "su_time", "su_catalog")
BOX_HEADERS = QUERY_HEADERS + ("su_reader", "su_indices", "su_embeddings", "su_process", "su_statistical",
                               "su_download")
QUERY_CODE = """@fused.udf
def udf(bbox: str = "[]", start: str = "", end: str = "", cloud: float = 60.0):
    import json

    import su_catalog

    products = su_catalog.query(json.loads(bbox), (start, end), cloud_cover=cloud)
    return products[["date", "tile_id", "cloud_cover"]].reset_index(drop=True)
"""
BOX_CODE = """import io
import json


@fused.udf(cache_max_age="0s")
def udf(request: str = "{}", kind: str = "rgb", frame: str = "", day: str = "", cover: float = 99.5,
        fill_days: int = 8):
    import time

    import pandas as pd
    import su_catalog
    import su_constants
    import su_download

    t0 = time.perf_counter()
    req = json.loads(request)
    if kind == "dem":
        try:
            arr = su_download.get_data(req)
        except su_constants.NoDataError:
            arr = _empty(req, float("nan"), "float32")
        data, info = _dem_png(arr)
        return pd.DataFrame({"data": [data], "info": [json.dumps(info)]})
    info, arr = {}, None
    if frame and not day:
        area, dates = json.loads(frame), tuple(req["date"])
        days = su_catalog.clearest_days(su_catalog.query(area, dates, cloud_cover=req["cloud_cover"]), area)
        if not len(days):
            raise ValueError(f"No Sentinel-2 scene with less than {req['cloud_cover']:.0f}% cloud from {dates[0]} to "
                             f"{dates[1]}. Use a longer date range.")
        full = days[days["cover_pct"] >= cover]
        if len(full):
            day = str(full.iloc[0]["date"])
            info["scenes"] = int(full.iloc[0]["scenes"])
        else:
            info.update(fallback=True, scenes=int(days["scenes"].sum()))
    if frame and day:
        info["date"] = day
        try:
            arr = su_download.get_data({**req, "date": day})
        except su_constants.NoDataError:
            arr = _empty(req)
        info["filled"] = _fill(arr, req, day, fill_days)
    if arr is None:
        try:
            arr = su_download.get_data(req)
        except su_constants.NoDataError:
            arr = _empty(req)
    info["secs"] = round(time.perf_counter() - t0, 2)
    return pd.DataFrame({"data": [_rgb_png(arr)], "info": [json.dumps(info)]})


def _empty(req, value=0, dtype="uint16"):
    import numpy as np

    width, height = req["size"]
    return np.full((height, width, len([b for b in req["bands"] if b != "dataMask"])), value, dtype)


def _holes(arr):
    import numpy as np

    return np.nan_to_num(arr[..., :3].astype("float32")).sum(-1) <= 0


def _fill(arr, req, day, fill_days):
    import numpy as np
    import su_catalog
    import su_constants
    import su_geometry
    import su_reader

    holes = _holes(arr)
    if not holes.any():
        return 0
    ys, xs = np.nonzero(holes)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = su_geometry.make_geobox(req["area"], size=tuple(req["size"]), crs=req["crs"])[y0:y1, x0:x1]
    bb = sub.extent.to_crs("EPSG:4326").boundingbox
    area = [bb.left, bb.bottom, bb.right, bb.top]
    products = su_catalog.query(area, tuple(req["date"]), cloud_cover=req["cloud_cover"])
    products = products[products["date"] != day]
    if not len(products):
        return 0
    ranked = su_catalog.rank(products, area, order="day")
    order = list(dict.fromkeys(ranked["date"]))[:fill_days]
    names = [b for b in req["bands"] if b != "dataMask"]
    window, need, filled, start, size = arr[y0:y1, x0:x1], holes[y0:y1, x0:x1].copy(), 0, 0, 1
    while start < len(order) and need.any():
        group = ranked[ranked["date"].isin(order[start:start + size])]
        start, size = start + size, size * 2
        try:
            ds = su_reader.read_stack(group, names, sub, units="dn", resampling=req["resampling"],
                                      mosaicking="simple", mosaic_order="clearest_day", mask=req["mask"])
        except su_constants.NoDataError:
            continue
        got = need & (ds["dataMask"].values > 0)
        window[got] = np.stack([ds[n].values for n in names], axis=-1)[got]
        need &= ~got
        filled += int(got.sum())
    return filled


def _rgb_png(arr):
    import numpy as np
    from PIL import Image

    dn = np.nan_to_num(np.asarray(arr, dtype="float32"))
    enc = np.rint(np.sqrt(np.clip(dn / 10000.0, 0.0, 1.0)) * 255.0).astype("uint8")
    enc[_holes(dn)] = 0
    buf = io.BytesIO()
    Image.fromarray(enc).save(buf, "PNG")
    return buf.getvalue()


def _dem_png(arr):
    import math

    import numpy as np
    from PIL import Image

    z = np.asarray(arr, dtype="float64")[..., 0]
    ok = np.isfinite(z)
    lo, hi = (float(z[ok].min()), float(z[ok].max())) if ok.any() else (0.0, 0.0)
    step = max(0.1, math.ceil((hi - lo) / 65534 * 1000) / 1000)
    v = np.zeros(z.shape, "uint16")
    v[ok] = np.rint((z[ok] - lo) / step).astype("uint16") + 1
    buf = io.BytesIO()
    Image.fromarray(v).save(buf, "PNG")
    return buf.getvalue(), {"zmin": lo, "step": step}
"""
LOGIN_HINTS = ("badcredentials", "fused credentials", "credentials file", "fused login", "unauthorized",
               "invalid_grant", "refresh token")


def _report(spec, state, detail):
    origin = os.environ.get("FUSED_RENDER_ORIGIN")
    page = os.environ.get("FUSED_RENDER_PAGE")
    if not (origin and spec.get("job")):
        return
    body = {"id": spec["job"], "title": spec.get("title", "Terrain Glow"), "kind": "task", "state": state,
            "detail": detail}
    headers = {"Content-Type": "application/json", "X-Fused": "1"}
    if page:
        headers["X-Fused-Page"] = page
    try:
        req = urllib.request.Request(f"{origin}/api/jobs", data=json.dumps(body).encode(), headers=headers,
                                     method="POST")
        urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass


def _final_report(spec, own_state, message=""):
    sibling = tg.read_json(spec.get("sibling", "")) or {}
    other = sibling.get("state")
    if own_state == "error":
        _report(spec, "error", message[:200])
    elif other == "error":
        _report(spec, "error", sibling.get("message", "")[:200])
    elif other == "done":
        _report(spec, "done", "Elevation and imagery are ready")
    else:
        _report(spec, "running", "Elevation is ready" if spec["part"] == "dem" else "Imagery is ready")


def _status(part_dir, **fields):
    path = os.path.join(part_dir, "status.json")
    status = tg.read_json(path) or {}
    status.update(fields)
    tg.write_json(path, status)


def _short_error(exc):
    lines = [ln.strip() for ln in str(exc).splitlines() if ln.strip()]
    for ln in reversed(lines):
        if re.search(r"(Error|Exception)\b", ln):
            return ln[:400]
    return (lines[-1] if lines else type(exc).__name__)[:400]


def _is_login_error(exc):
    text = f"{type(exc).__name__} {exc}".lower()
    return any(h in text for h in LOGIN_HINTS)


def _load_su():
    warnings.filterwarnings("ignore")
    import fused

    fused.options.no_login = True
    fused.options.auth.credentials_path = tg.CREDENTIALS
    fused.options.show.enable_tqdm = False
    fused.options.request_timeout = REMOTE_TIMEOUT
    return tg.load_package(fused)


def _udf(name, code, modules):
    import fused

    folder = tg.package_dir(fused)
    headers = []
    for module in modules:
        with open(os.path.join(folder, f"{module}.py")) as f:
            headers.append({"module_name": module, "source_code": f.read()})
    return fused.models.Udf.model_validate(
        {"name": name, "type": "geopandas_v2", "entrypoint": "udf", "code": code, "headers": headers,
         "metadata": {}}, context={"import_globals": False, "load_parameter_list": True})


def _query(bbox, start, end, cloud):
    import fused

    return fused.run(_udf("terrain_glow_scenes", QUERY_CODE, QUERY_HEADERS), bbox=json.dumps(bbox), start=start,
                     end=end, cloud=float(cloud), engine="remote")


def _final_error(text):
    for name in FINAL_ERRORS:
        found = re.findall(rf"{name}: (.+)", text)
        if found:
            return found[-1].strip()
    return None


def _remote(udf, args):
    def submit(indices):
        pool = udf.map([args[i] for i in indices], max_workers=min(MAX_WORKERS, len(indices)), max_retry=0,
                       cache_max_age="0s")
        return pool, indices, set()

    pools, left, retried = [], set(range(len(args))), set()
    try:
        pools.append(submit(list(range(len(args)))))
        while left:
            again = []
            for pool, indices, seen in pools:
                for j, got in sorted(pool.results_now(return_exceptions=True).items()):
                    i = indices[j]
                    if j in seen or i not in left:
                        continue
                    seen.add(j)
                    if isinstance(got, BaseException) and i not in retried and _final_error(str(got)) is None:
                        retried.add(i)
                        again.append(i)
                        continue
                    left.discard(i)
                    yield i, got
            if again:
                pools.append(submit(again))
            if left:
                time.sleep(POLL_SECONDS)
    finally:
        for pool, _, _ in pools:
            pool.cancel(wait=True)


def _fetch(udf, args, on_result):
    done, first_error = [False] * len(args), ""
    for _ in range(2):
        todo = [i for i, ok in enumerate(done) if not ok]
        for k, got in _remote(udf, [args[i] for i in todo]):
            i = todo[k]
            if isinstance(got, BaseException):
                text = str(got)
                if "MAX_PIXELS" in text or _is_login_error(got):
                    raise RuntimeError(text) from got
                final = _final_error(text)
                if final:
                    raise ValueError(final)
                first_error = first_error or _short_error(got)
                continue
            on_result(i, got)
            done[i] = True
        if all(done):
            return
    raise RuntimeError(f"{done.count(False)} of {len(args)} tiles failed. {first_error}")


def _png(got):
    import numpy as np
    from PIL import Image

    return np.asarray(Image.open(io.BytesIO(got["data"].iloc[0]))), json.loads(got["info"].iloc[0])


def _stitch(tiles, nx, ny):
    import numpy as np

    rows = [np.concatenate(tiles[j * nx:(j + 1) * nx], axis=1) for j in range(ny)]
    return np.concatenate(rows, axis=0)


def _fetch_dem(su, spec):
    import numpy as np

    grid = spec["grid"]
    tw, th = grid["tile"]
    boxes = tg.tile_boxes(spec["bbox"], grid["nx"], grid["ny"])
    requests = [su.process_request(b, None, collection="cop-dem-glo-30", size=(tw, th), crs="EPSG:4326",
                                   resampling="bilinear", output="array") for b in boxes]
    tiles = [None] * len(boxes)

    def got(i, frame):
        v, info = _png(frame)
        tiles[i] = np.where(v > 0, info["zmin"] + (v.astype("float64") - 1) * info["step"], np.nan)

    _fetch(_udf("terrain_glow_box", BOX_CODE, BOX_HEADERS),
           [{"request": json.dumps(r), "kind": "dem"} for r in requests], got)
    arr = _stitch(tiles, grid["nx"], grid["ny"]).astype("float32")
    finite = np.isfinite(arr)
    if not finite.any():
        raise ValueError("The Copernicus DEM has no data for this area.")
    arr[~finite] = float(np.nanmin(arr))
    meta = {"width": int(arr.shape[1]), "height": int(arr.shape[0]), "min": float(arr.min()),
            "max": float(arr.max()), "pixel_m": grid["pixel_m"], "tiles": len(boxes), "bbox": spec["bbox"]}
    return arr.tobytes(), meta


def _scenes(spec):
    comp = spec["comp"]
    products = _query(spec["bbox"], spec["start"], spec["end"], CLOUD_CAP[comp])
    if len(products) == 0:
        raise ValueError(f"No Sentinel-2 scene with less than {CLOUD_CAP[comp]:.0f}% cloud from "
                         f"{spec['start']} to {spec['end']}. Use a longer date range.")
    return products


def _choose_cloud(comp, products, scene_cap, budget_scenes):
    k = max(1, min(scene_cap, budget_scenes))
    if len(products) <= k:
        return CLOUD_CAP[comp], len(products)
    return round(float(products["cloud_cover"].nsmallest(k).max()), 3) + 0.001, k


def _holes(arr):
    import numpy as np

    return np.nan_to_num(np.asarray(arr, dtype="float32")[..., :3]).sum(axis=-1) <= 0


def _fetch_img(su, spec, on_tile, restart):
    grid, comp = spec["grid"], spec["comp"]
    tw, th = grid["tile"]
    boxes = tg.tile_boxes(spec["bbox"], grid["nx"], grid["ny"])
    common = dict(bands=BANDS, size=(tw, th), crs="EPSG:4326", units="dn", output="array",
                  resampling="cubic" if grid["pixel_m"] < 9.5 else "nearest")
    udf = _udf("terrain_glow_box", BOX_CODE, BOX_HEADERS)
    tiles, infos = [None] * len(boxes), [{}] * len(boxes)

    def load(requests, indices=None, **extra):
        indices = list(range(len(requests))) if indices is None else indices

        def got(k, frame):
            i = indices[k]
            tiles[i], infos[i] = _png(frame)
            on_tile(i, tiles[i])

        _fetch(udf, [{"request": json.dumps(requests[i]), **extra} for i in indices], got)

    if comp == "single":
        load([su.process_request(b, spec["start"], mosaic_order="least_cloudy", **common) for b in boxes])
        scenes, label = None, f"Sentinel-2, {tg.nice_day(spec['start'])}"
    elif comp == "day":
        requests = [su.process_request(b, (spec["start"], spec["end"]), cloud_cover=CLOUD_CAP[comp],
                                       mask=spec["mask"], mosaic_order="clearest_day", **common) for b in boxes]
        frame = json.dumps(spec["bbox"])
        load(requests, frame=frame, cover=DAY_COVER)
        dates = [info.get("date") for info in infos]
        best = max(dict.fromkeys(dates), key=dates.count)
        odd = [i for i, d in enumerate(dates) if d != best]
        if odd:
            load(requests, odd, **(dict(frame=frame, day=best) if best else {}))
        scenes = next(info["scenes"] for info in infos if "scenes" in info)
        if best:
            filled = any(info.get("filled") for info in infos)
            label = f"Clearest day, {tg.nice_day(best)}" + (", gaps from other days" if filled else "")
        else:
            label = f"{LABEL[comp]}, {tg.nice_range(spec['start'], spec['end'])}"
    else:
        products = _scenes(spec)
        budget = int(MAX_PIXELS * 0.9 // (tw * th * (len(BANDS) + 1)))
        extra = dict(reducer="median") if comp == "median" else dict(mosaic_order="least_cloudy")
        for attempt in range(3):
            cloud, scenes = _choose_cloud(comp, products, spec["scene_cap"], budget)
            try:
                load([su.process_request(b, (spec["start"], spec["end"]), cloud_cover=cloud, mask=spec["mask"],
                                         **extra, **common) for b in boxes])
                break
            except RuntimeError as exc:
                if "MAX_PIXELS" not in str(exc):
                    raise
                if attempt == 2:
                    raise ValueError("Too many scenes for this area. Use a shorter date range or the Preview "
                                     "quality.") from exc
                restart()
                budget = max(1, min(budget, scenes) // 2)
        label = f"{LABEL[comp]}, {tg.nice_range(spec['start'], spec['end'])}"
    enc = _stitch(tiles, grid["nx"], grid["ny"])
    coverage = float((~_holes(enc)).mean())
    if coverage < 0.02:
        raise ValueError("No clear Sentinel-2 pixels for this area and date. Try other dates.")
    meta = {"width": int(enc.shape[1]), "height": int(enc.shape[0]), "pixel_m": grid["pixel_m"],
            "tiles": len(boxes), "coverage": round(coverage, 4), "scenes": scenes, "label": label,
            "start": spec["start"], "end": spec["end"], "comp": comp}
    return enc.tobytes(), meta


def _tile_writer(part_dir):
    ready = []

    def on_tile(i, arr):
        tg.write_bytes(os.path.join(part_dir, f"tile_{i}.bin"), arr.tobytes())
        ready.append(i)
        _status(part_dir, ready=sorted(set(ready)))

    def restart():
        ready.clear()
        _status(part_dir, ready=[], generation=time.time())

    def cleanup():
        for name in os.listdir(part_dir):
            if name.startswith("tile_") and name.endswith(".bin"):
                os.remove(os.path.join(part_dir, name))

    return on_tile, restart, cleanup


def list_scenes(spec_json):
    spec = json.loads(spec_json)
    _load_su()
    products = _query(spec["bbox"], spec["start"], spec["end"], spec["cloud"])
    scenes = []
    if len(products):
        table = products.groupby("date").agg(cloud=("cloud_cover", "mean"), tiles=("tile_id", "nunique"))
        scenes = [{"date": str(d), "cloud": round(float(r.cloud), 1), "tiles": int(r.tiles)}
                  for d, r in table.sort_index().iterrows()]
    print(json.dumps(scenes), flush=True)


def run(part_dir, part, spec_json):
    spec = json.loads(spec_json)
    t0 = time.time()
    _status(part_dir, state="running", pid=os.getpid(), started=t0, step="load")
    _report(spec, "running", "Elevation" if part == "dem" else "Sentinel-2 imagery")
    try:
        su = _load_su()
        _status(part_dir, step="fetch")
        on_tile, restart, cleanup = _tile_writer(part_dir)
        data, meta = _fetch_dem(su, spec) if part == "dem" else _fetch_img(su, spec, on_tile, restart)
        meta["seconds"] = round(time.time() - t0, 1)
        meta["bytes"] = len(data)
        tg.write_bytes(os.path.join(part_dir, f"{part}.bin"), data)
        tg.write_json(os.path.join(part_dir, "meta.json"), meta)
        _status(part_dir, state="done", seconds=meta["seconds"], step="done", ready=[])
        cleanup()
        print(f"{part} done in {meta['seconds']} s", flush=True)
        _final_report(spec, "done")
    except Exception as exc:
        message = _short_error(exc)
        print(f"{part} failed: {exc!r}", flush=True)
        code = "login" if _is_login_error(exc) else None
        _status(part_dir, state="error", message=message, code=code, seconds=round(time.time() - t0, 1))
        _final_report(spec, "error", message)
    finally:
        try:
            os.remove(os.path.join(part_dir, "lock"))
        except OSError:
            pass


if __name__ == "__main__":
    if sys.argv[1] == "scenes":
        list_scenes(sys.argv[2])
    else:
        run(*sys.argv[1:4])
