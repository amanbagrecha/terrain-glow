---
name: run-terrain-glow
description: Run, drive, screenshot or test the Terrain Glow fused-render app (terrain_glow/index.html). Load a place, switch composite (Mosaic, Best day, Median, Single date), check the Fused fetch code (fetch_worker.py) and its timing.
---

# Memo: run Terrain Glow

Run all commands from `terrain_glow/`.

## 1. Fetch code only (most changes)

Uses the same specs as `terrain.py`. It does not use the cache or the UI. It prints JSON (label, scenes, seconds) and writes a PNG.

```sh
.venv/bin/python -I .claude/skills/run-terrain-glow/fetch_smoke.py day
.venv/bin/python -I .claude/skills/run-terrain-glow/fetch_smoke.py single 35.3606 138.7274 22 1.7778 preview winter 2026-02-15
```

Args, in order: `comp lat lon span aspect quality season date out`. The default is Fuji, 16:9, preview, winter, `/tmp/terrain_glow_smoke.png`. Elevation and imagery run one after the other. Two Fused map calls in one process stop with `CancelledError`.

## 2. Real UI

```sh
.verification/tg launch
.verification/tg open "ratio=16:9&comp=day&lat=35.3606&lon=138.7274&span=22&season=winter&name=Mount Fuji"
.verification/tg wait "!W.document.body.classList.contains('loading') && !W.document.body.classList.contains('partial')" --timeout 180
.verification/tg state
.verification/tg shot fuji-day
.verification/tg cleanup
```

Screenshots go to `.verification/runs/<run>/`. For the selectors, other commands and timings, see `.verification/SKILL.md`.

## Gotchas

- Give `lat`, `lon`, `span` and `season` in the URL. A `place=` value alone does not move the frame.
- In `state`, "from cache" means that no fetch ran. To test the fetch code, use path 1 or a new frame.
- Each load starts a new `fetch_worker.py` process, so an edit takes effect on the next load.
- If one cold load takes 80 to 140 s, Fused was slow to start. Run it again before you blame the code.
- `tg click` gives "Cannot read properties of null (reading 'scrollIntoView')": the selector is not on the page.
- In Single date mode, `tg sweep` reports the `.scene` chips as "outside the panel". That strip scrolls sideways.
