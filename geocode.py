import json
import math
import os
import ssl
import urllib.parse
import urllib.request

import tg_common as tg

PHOTON = "https://photon.komoot.io"
SPAN_BY_KIND = {"peak": 10, "volcano": 18, "mountain_range": 40, "glacier": 16, "valley": 16, "fjord": 20,
                "bay": 20, "island": 24, "national_park": 40, "nature_reserve": 30, "water": 14, "city": 16,
                "town": 10, "village": 6, "hamlet": 5, "cliff": 6, "ridge": 12, "saddle": 8}


def _tls():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get(url):
    path = os.path.join(tg.CACHE_DIR, "geo", tg.key_of(url) + ".json")
    cached = tg.read_json(path)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": tg.USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12, context=_tls()) as r:
        data = json.loads(r.read().decode())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tg.write_json(path, data)
    return data


def _span(props, lat):
    extent = props.get("extent")
    if extent and len(extent) == 4:
        w = abs(extent[2] - extent[0]) * 111.32 * max(0.05, abs(math.cos(math.radians(lat))))
        h = abs(extent[1] - extent[3]) * 110.574
        size = max(w, h) * 1.15
        if size >= 2:
            return round(tg.clamp(size, 4, 50), 1)
    return SPAN_BY_KIND.get(props.get("osm_value"), SPAN_BY_KIND.get(props.get("type"), 14))


def _item(feature):
    props = feature.get("properties", {})
    lon, lat = feature["geometry"]["coordinates"][:2]
    name = props.get("name") or props.get("city") or props.get("county") or props.get("state") or "Unnamed place"
    kind = (props.get("osm_value") or props.get("type") or "").replace("_", " ")
    where = [props.get(k) for k in ("state", "country") if props.get(k) and props.get(k) != name]
    detail = " · ".join(([kind.capitalize()] if kind else []) + where)
    return {"name": name, "detail": detail, "lat": round(lat, 5), "lon": round(lon, 5), "span": _span(props, lat)}


def main(q: str = "", lat: float = 0.0, lon: float = 0.0, reverse: bool = False):
    if reverse:
        url = f"{PHOTON}/reverse?" + urllib.parse.urlencode({"lat": lat, "lon": lon, "lang": "en", "limit": 1})
    else:
        q = q.strip()
        if len(q) < 2:
            return []
        url = f"{PHOTON}/api/?" + urllib.parse.urlencode({"q": q, "limit": 7, "lang": "en"})
    data = _get(url)
    items, seen = [], set()
    for feature in data.get("features", []):
        item = _item(feature)
        tag = (item["name"], round(item["lat"], 2), round(item["lon"], 2))
        if tag not in seen:
            seen.add(tag)
            items.append(item)
    return items
