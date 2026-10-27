---
name: terrain-glow
description: Shaded-relief explorer. Gets Copernicus DEM elevation and cloud-free Sentinel-2 imagery for a place and frame size, finds places by name and lists Sentinel-2 dates.
approve: []
---
# Terrain Glow

The page draws the hillshade, colour looks, 3D view, PNG and clips in the browser. The Python files
get the data on Fused with the Fused account that FusedRender is signed in to (its credentials store,
`~/.fused/credentials` or `$FUSED_RENDER_FUSED_CREDENTIALS`).
The Sentinel-2 library is `sentinel_utils` from fusedio/udfs at commit `PACKAGE_COMMIT` (tg_common.py). The first call
downloads it to `.fused/cache/sentinel_utils/<commit>/`. Set `SENTINEL_UTILS_PATH` to use another copy.
Results go to `.fused/cache/` (data) and `.fused/data/exports/` (saved images and clips).

An area is a centre (`lat`, `lon`), a long side in km (`span`, 2 to 50) and a frame shape
(`aspect` = width / height, 0.4 to 2.5). `quality` sets the pixel size: `preview` (about 18 m, one tile),
`high` (10 m, up to 2048 px, tiles of 1024 px that run in parallel), `print` (6.5 m, up to 3600 px).

## terrain.py
Starts or checks the data jobs for one area. The jobs run in the background (one for elevation, one for
imagery) and write `.fused/cache/<version>/dem/<key>/` and `.fused/cache/<version>/img/<key>/`. Call it again until both
parts are "done". It returns at once.
- Args: `lat` (float, default 45.9763), `lon` (float, default 7.6586), `span` (float km, default 14),
  `aspect` (float, default 0.8), `quality` (str, "preview" | "high" | "print", default "high"),
  `comp` (str, "lc" least-cloudy | "day" the clearest day that covers all of the frame, gaps fill from other days | "median" | "single", default "lc"),
  `season` (str, "summer" | "winter" | "year" | "custom", default "summer"), `start`, `end` (str "YYYY-MM-DD",
  for "custom"), `date` (str "YYYY-MM-DD", required when comp is "single"), `reset` (bool, default false,
  starts failed parts again), `job`, `title` (str, default "", id and title of the download-manager row)
- Returns: `{"plan": {"bbox", "km", "img": {"width", "height", "nx", "ny", "pixel_m"}, "dem": {...}},
  "start": str, "end": str, "dem": {"state", "files": {"bin": path}, "meta", "seconds"},
  "img": {"state", "files", "meta", "seconds"}}`. `state` is "running", "done", "error" or "login".
  When FusedRender is not signed in to Fused, the result also has `"login": true` and `"creds_stamp"` (the modification time of
  the credentials file, or null). A login error starts again by itself when the credentials file is newer than that error.
  While the imagery runs, `img` also has `ready` (indexes of finished tiles), `generation` and `tile` (path
  pattern `.../tile_{i}.bin`: one RGBA uint8 tile of `plan.img.tile` pixels, tiles row-major from the north-west).
  `dem.bin` is float32 metres in 0.1 m steps (row 0 = north), `img.bin` is RGBA uint8 = sqrt(reflectance) of B04, B03, B02, B08.
- Example: `{"action":"py","app":"terrain-glow","file":"terrain.py","args":{"lat":36.1,"lon":-112.11,"span":24,"aspect":1.7778,"quality":"high"}}`

## scenes.py
Lists the Sentinel-2 dates for an area and a date range, with the mean cloud cover. Reads the catalog;
writes only a cache file.
- Args: `lat`, `lon` (float), `span` (float km, default 14), `aspect` (float, default 0.8),
  `season` (str, default "summer"), `start`, `end` (str "YYYY-MM-DD", for "custom"), `cloud` (float max %, default 80)
- Returns: `{"start": str, "end": str, "bbox": [w, s, e, n], "scenes": [{"date": str, "cloud": float, "tiles": int}]}`
- Example: `{"action":"py","app":"terrain-glow","file":"scenes.py","args":{"lat":45.9763,"lon":7.6586,"season":"summer"}}`

## geocode.py
Finds places by name, or names a point, with the Photon geocoder. Reads the network; writes only a cache file.
- Args: `q` (str, default ""), `lat`, `lon` (float, default 0), `reverse` (bool, default false)
- Returns: `[{"name": str, "detail": str, "lat": float, "lon": float, "span": float km}]`
- Example: `{"action":"py","app":"terrain-glow","file":"geocode.py","args":{"q":"Mont Blanc"}}`

## save_export.py
Saves one exported file (PNG, MP4 or WebM, base64) to `.fused/data/exports/`. Writes that folder.
- Args: `name` (str file name, default "terrain-glow.png"), `data` (str base64, required)
- Returns: `{"path": str, "bytes": int}`
- Example: `{"action":"py","app":"terrain-glow","file":"save_export.py","args":{"name":"test.png","data":"iVBORw0KGgo="}}`
