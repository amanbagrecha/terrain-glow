---
name: verify-terrain-glow
description: Drive the Terrain Glow fused-render app (shaded-relief explorer, terrain_glow/index.html) in a private headless Chrome to prove UI behavior - loading an area on Fused, light and look controls, frame ratios, PNG and clip export, caption editing, place picker, login state. Use after any change to index.html or the .py files, or to reproduce a bug.
---

# Verify Terrain Glow

The app is a fused-render view: `terrain_glow/index.html` runs inside the fused-render shell, and its Python
files (`terrain.py`, `scenes.py`, `geocode.py`, `save_export.py`) run on the fused-render server. Imagery and
elevation come from Fused (remote engine) under the Fused login of this computer. The harness is
`.verification/tg`, a small CLI over Chrome DevTools. It drives a private headless Chrome; it never touches
the user's own browser or the built-in browser pane.

## Launch

1. The fused-render server must already run (the desktop app). The harness reads its origin from
   `$FUSED_RENDER_ORIGIN`, else `~/.fused-render/server.json`. Do not start a second server for a normal run.
2. Start a run (own Chrome profile, own port, own evidence folder):

   ```sh
   terrain_glow/.verification/tg launch              # 1440 x 900, light theme
   terrain_glow/.verification/tg launch --dark --port 9412
   ```

   It prints `{"run", "evidence", "port", "origin"}`. Only one run at a time per checkout (`runs/current.json`).
3. Open the app and wait until a real image is drawn (body has no `loading` class):

   ```sh
   terrain_glow/.verification/tg open "place=matterhorn&ratio=4:5&cap=1&ct="
   ```

   Ready means the terrain is drawn, not that the page answered. A cold area takes 10 to 21 s (data jobs on
   Fused; sometimes 80 to 140 s when Fused is slow to start); a cached area is ready in about 2 s. The first open after a `pyproject.toml` change also installs the
   app environment (the shell shows "Preparing terrain_glow"), which can take some minutes.

## Doctor

```sh
terrain_glow/.verification/tg doctor
```

Read-only. Checks the server answers `/api/config`, this run's Chrome is alive, the page has the
`fused-app` marker. It also reports `package_cached` (the first data call downloads the package) and `fused_login`. With
`fused_login: false` every data load ends in the login card (see features/login-state.md); that is correct
behavior, not a harness fault.

## Drive

Use real user paths: `tg click <css selector>` sends a real mouse press and release at the element centre
inside the app frame. Stable handles:

| Control | Selector |
|---|---|
| View switch | `#viewSwitch button[data-view="relief"]`, `[data-view="3d"]`, `[data-view="map"]` |
| Frame ratio | `.ratio[data-v="1:1"]`, `"4:5"`, `"9:16"`, `"16:9"`, `"1.91:1"`, `"3:2"`, `"free"` |
| Imagery layer | `#layerSeg button[data-v="true"]`, `"false"`, `"ndvi"`, `"relief"` |
| Composite | `#compSeg button[data-v="lc"]`, `"day"`, `"median"`, `"single"` |
| Light preset | `.preset[data-v="classic"]`, `"dawn"`, `"golden"`, `"noon"`, `"dramatic"`, `"soft"` |
| Sun height, relief, height | `#altSeg button[data-v="12"]`, `#strSeg button[data-v="1"]`, `#exagSeg button[data-v="3"]` |
| Look | `.look[data-v="golden"]` (natural, golden, alpenglow, swiss, moonlight, mono) |
| Places picker | `#placesBtn`, then `#placesPop button[data-id="grandcanyon"]` |
| Map picker | `#pickMap`, then `#mapUse` |
| Export | `#savePng`, `#recClip` (click again to stop), size `#out`, caption switch `#capSwitch` |
| Clip settings | `#clipBtn` opens `#clipMenu`; motion `#clipSeg button[data-v="orbit"]` or `"sweep"`, length `#durSeg button[data-v="5"]` (5, 10, 15, 30) |
| Caption text | `#cap .ct`, `#cap .cs`, `#cap .cc` (contenteditable; use `tg type`) |

Other commands: `tg state` (params + visible status as JSON), `tg wait "<js condition with W>" --timeout 60`,
`tg set k=v ...` (preconditions only, never as proof), `tg type "#cap .ct" "New title"`,
`tg eval "<js function body with W>"` (prints the return value), `tg touch "#gl" --pinch 2` or `--drag 80` (real touch input).
`tg sweep 390x844 844x390 ... --shots <prefix>` checks the layout at each app size (exit 1 on an issue). With no size it checks
the current size. `--touch` turns on touch input, so the `(pointer: coarse)` rules (larger targets) apply.
`tg click "#signIn"` is refused unless the page has the login stub: on a real server it opens the Fused sign-in in the browser.
`tg --size 390x844 <command>` runs one command at that app size. The size override ends with the command, so give it to every command
of a small-screen recipe.
`tg open "<query>" --stub login` (or `login-phone`, `login-fail`) answers `terrain.py` and the sign-in API inside the page as if this
computer is signed out. It never touches `~/.fused/credentials`. See features/login-state.md.
A data change (place, ratio, quality, composite, dates) starts a load; follow it with
`tg wait "!W.document.body.classList.contains('loading')" --timeout 180`.

## Evidence

- `tg shot <name>` writes `<run folder>/<name>.png`. Take one before and one after each action.
- `tg state` after each action; keep its JSON in the report (params prove the URL state, `resolution` and
  `footer` prove the data plan and whether it came from cache).
- Exports: after `#savePng` or `#recClip`, wait for the toast (`tg wait "W.document.getElementById('toast').textContent.includes('Saved')"`),
  then `tg exports` copies the new files from `terrain_glow/.fused/data/exports/` into the run folder and prints
  their sizes. A clip is proved by its size and by decoding it (duration and frame size), not by the toast alone.
- Persistence: reopen with the same query (`tg open "<same query>"`) and compare `tg state`.
- The run folder is `terrain_glow/.verification/runs/<run id>/`. It is git-ignored and is not in a `.fused` export.

## Cleanup

```sh
terrain_glow/.verification/tg cleanup
```

Stops only the Chrome this run started (by its process group), deletes its profile, removes
`runs/current.json`, and keeps every screenshot and export copy. It never stops the fused-render server.
Files the app wrote to `.fused/data/exports/` stay (they are the app's own output).

## Helpers

- `tg` runs `control.py` with `uv run --with websocket-client` (needs `uv` and Google Chrome).
- `control.py --help` lists every command.

Feature map: [features/README.md](features/README.md).
