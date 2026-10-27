# Terrain Glow verification map

This folder is the maintained source for proving what a Terrain Glow user can do. Read this index, then use
the feature file as the recipe. All commands are `terrain_glow/.verification/tg ...` (written `tg` below).

## Baseline preconditions

- The fused-render desktop app runs; `tg launch` and `tg doctor` pass.
- This computer has a Fused login (`doctor` shows `fused_login: true`), except for login-state.md.
- Start each recipe with `tg open "place=matterhorn&lat=45.9763&lon=7.6586&span=14&name=Matterhorn&ratio=4:5&quality=high&comp=lc&season=summer&layer=true&look=natural&az=315&alt=40&view=relief&cap=1&ct=&cs=&cc="`.
- Never drive an instance that this run did not launch.

## Driving conventions

- Use `tg click` with the selectors in ../SKILL.md. `tg set` is only for preconditions.
- After a change that loads data, wait for the `loading` class to go before you take proof.
- Take a screenshot before and after the action, and `tg state` after it.

## Proof and skip reporting

- UI proof: screenshot plus `tg state` JSON from the same moment.
- Export proof: `tg exports` output (file name and bytes) plus a check of the file (image size or video decode).
- Name the feature ID with every artifact. Report a skipped path with the unmet precondition.

## Features

- [Load an area](./load-area.md): places picker, search, map pick, quality, composites, cache.
- [Light and look](./light-and-look.md): light wheel, presets, sun height, relief, height, layers, looks.
- [Frame and export](./frame-and-export.md): ratios, PNG, clips, caption editing.
- [Login state](./login-state.md): short sign-in card, one-click Fused sign-in, phone text.
- [Small screens](./small-screens.md): phone, tablet and short windows; touch targets; pinch zoom in 3D.
