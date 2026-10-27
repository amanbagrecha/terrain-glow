# Frame and export

The user picks a frame for a social network, edits the caption on the image, then saves a PNG or records a short clip. The saved file has the frame size and the edited caption.

## Sub-features

- `frame-ratio` sets 1:1, 4:5, 9:16, 16:9, 1.91:1, 3:2 or Free; the area and the request follow the ratio.
- `caption-edit` edits title, subtitle and credit on the image.
- `export-png` saves a PNG at the social size (or full resolution).
- `export-clip` records a 3D orbit or light sweep clip of 5, 10, 15 or 30 s (MP4 in Chrome and Safari, WebM where MP4 is missing). A second click on the record button (or `R`) stops early and saves the part recorded so far.

## How to get to it (user POV)

- Choose a ratio in the Frame section.
- Click the text on the image and type. Enter ends the edit.
- Choose "Save image" or "Record clip" (or press `S` / `R`). The clip button under them ("Orbit · 10 s") opens the motion and length menu.

## Driving it with tg

Preconditions:

- Baseline open, drawn, caption on.

- **Ratio.** `tg click '.ratio[data-v="16:9"]'`, wait for load, `tg shot frame-16x9`. The frame is wide; `tg state` shows `ratio: 16:9` and a `resolution` with width greater than height.
- **Caption.** `tg type "#cap .ct" "Verification title"`, `tg shot caption-edit`. `tg state` shows `params.ct: Verification title`.
- **PNG.** `tg click "#savePng"`, `tg wait "W.document.getElementById('toast').textContent.includes('Saved')"`, `tg exports`. A new `.png` of 1600 × 900 (16:9 social size); check with `sips -g pixelWidth -g pixelHeight <file>`; open it and see "Verification title".
- **Clip.** `tg click "#clipBtn"`, `tg click '#durSeg button[data-v="5"]'`, `tg click "#recClip"`, `tg wait "W.document.getElementById('toast').textContent.includes('orbit')" --timeout 40`, `tg exports`. A new `-orbit.mp4` of about 5 s.
- **Stop.** Set length 30 s, `tg click "#recClip"`, `tg wait "W.document.getElementById('recLabel').textContent.startsWith('Stop')"`, `tg click "#recClip"` again. The saved clip is much shorter than 30 s.

## Gotchas

- Anchor downloads do not land in ~/Downloads in the built-in pane or in headless Chrome; the copy in `.fused/data/exports/` is the proof.
- Recording runs in real time (the chosen length, 10 s by default). A hidden tab slows it.
- Reset the caption after the run with the "Reset text" button so the next run starts clean.
