# Load an area

The user picks a place (famous places list, search or map), and the app gets elevation and Sentinel-2 imagery on Fused, then draws it. A second visit to the same area comes from the cache.

## Sub-features

- `area-places` picks a famous place from the places picker.
- `area-search` finds a place by name.
- `area-map` frames a custom area on the map and renders it.
- `area-quality` changes Preview, High, Print and shows the pixel size.
- `area-composite` switches Mosaic (least cloudy), Best day, Median and Single date.
- `area-cache` shows "from cache" on a second visit.
- `area-progressive` shows the relief as soon as the elevation is in, then each imagery tile fades in (0.5 s) as it finishes on Fused.

## How to get to it (user POV)

- Choose the mountain button next to the search box, then a place. Or press `P`.
- Type a name in "Search a place" and choose a result. Or press `/`.
- Choose the map button (or the Map view), move the map, choose "Render this area".
- Choose a quality in the select next to the date range.

## Driving it with tg

Preconditions:

- Baseline open on Matterhorn, drawn.

- **Open picker.** `tg click "#placesBtn"`. `#placesPop` shows groups Mountains, Volcanoes, Glaciers and ice, Fjords, Canyons, Valleys.
- **Pick a canyon.** `tg click '#placesPop button[data-id="grandcanyon"]'`, then `tg wait "!W.document.body.classList.contains('loading')" --timeout 180`. `tg state` shows `name: Grand Canyon` and a `resolution` like `≈ 12 m per pixel · 1638 × 2048`.
- **Search.** `tg click "#q"`, `tg keys "Half Dome"`, `tg wait "W.document.querySelector('#results button[data-i]')" --timeout 20`, `tg shot search-results`, then `tg click '#results button[data-i="0"]'` and wait for the load. `tg state` shows the picked name.
- **Quality.** `tg select "#quality" preview`, wait for the load, `tg state`: `resolution` starts with `≈ 18 m`. Then `tg select "#quality" high`: `≈ 10 m` to `≈ 13 m` (depends on the area size).
- **Median.** `tg click '#compSeg button[data-v="median"]'`, wait, `tg state`. The caption subtitle says "Median composite" and `footer` names the scene count.
- **Best day.** `tg open "ratio=16:9&comp=day&lat=35.3606&lon=138.7274&span=22&season=winter&name=Mount Fuji"`, wait until `body` has no `loading` and no `partial` class, `tg state`. The caption subtitle says "Clearest day, <date>" (for Fuji, last winter: 15 Feb 2026), and the image has no date edge at the MGRS tile line near 138.8° E that "Mosaic" shows. ", gaps from other days" shows when a box filled its gaps from other days.
- **Cache.** `tg open "<baseline>"` a second time. `footer` contains "from cache" and `ready_s` is below 5 s.

## Gotchas

- Progressive tiles: on a new area, `body` gets the class `partial` and `#tileChip` reads `Imagery N of M tiles`. Save image and Record clip refuse until the class goes. Prove it with `tg wait "W.document.body.classList.contains('partial')"` and screenshots while N grows.

- A cold area takes 15 to 40 s; the first remote run of the day can take longer. Use `--timeout 180`.
- The map needs internet tiles from Esri. Without them the map is black but "Render this area" still works.
- Native selects (`#quality`, `#season`, `#out`, `#clip`) do not open as menus in headless Chrome. `tg select` sets the option and fires the same change event that a user choice fires.
