# Small screens

The app works on a phone, a tablet and a small or short window. Nothing overlaps, nothing is cut, and the controls are large
enough for a finger.

## Sub-features

- `layout-sheet` when the window is at most 760 px wide and in portrait, the controls are a sheet at the bottom.
  The sheet is as high as its content, but not more than 52 % of the height. The image uses the remaining space. The hide button points down.
- `layout-sheet-columns` when the sheet is also 620 px wide or more, the controls are in two columns (Frame, Imagery, Look |
  Light, Export). Fine-tune is a full row below the columns, with its sliders in five columns. The sheet is not more than 60 % of the height.
  At 640 x 791, nothing scrolls when Fine-tune is closed.
- `layout-short` when the window is at most 520 px high (a phone on its side), the controls stay on the right (320 px).
- `layout-low-stage` when the image area is at most 480 px high, the brand line and the place details are hidden.
- `layout-narrow-stage` when the image area is at most 600 px wide, the view switch shows icons only and the title is smaller.
  At most 320 px wide, the title moves below the view switch. The image always starts below the title and the view switch.
- `touch-targets` with a touch screen (`pointer: coarse`), buttons and fields are at least 28 px high, and inputs use 16 px
  text (so iOS does not zoom when you type).
- `touch-3d` in 3D, one finger orbits and two fingers pinch to zoom. The mouse drag and the scroll wheel work as before.

## How to get to it (user POV)

- Open the app on a phone (FusedRender on the local network), or make the window small.

## Driving it with tg

Preconditions:

- Baseline open and drawn.

- **Sweep.** `tg sweep 1440x900 1280x720 1024x640 768x1024 760x1000 640x791 620x900 619x900 844x390 667x375 568x320 412x430 390x844 360x640 320x568 --shots small`. Every line has
  `"issues": []` and the exit code is 0. Look at each `small-<size>.png`.
- **Sheet without scroll.** `tg --size 640x791 eval "const b=W.document.getElementById('panelBody'); return b.scrollHeight - b.clientHeight"` is 0.
- **Touch targets.** `tg sweep 844x390 390x844 360x640 --touch`. No line has an `info` entry "small target".
- **Places on a phone.** `tg --size 390x844 click "#placesBtn"`, then
  `tg --size 390x844 eval "return W.document.getElementById('placesPop').getBoundingClientRect().bottom <= W.innerHeight"` is true.
- **Map on a phone.** `tg --size 390x844 click '#viewSwitch button[data-view="map"]' --settle 4`, `tg --size 390x844 shot map-390`.
  "Render this area" is on one line.
- **Pinch.** `tg --size 390x844 set view=3d`, then `tg --size 390x844 touch "#gl" --pinch 2`. `dist` goes to half.
  `--pinch 0.5` doubles it. `tg --size 390x844 touch "#gl" --drag 80` turns `yaw` by 28 degrees.

## Gotchas

- The headless Chrome has a mouse, so `(hover: none)` and `(pointer: coarse)` rules do not apply in it. `tg touch` and
  `tg sweep --touch` turn on touch input for that one command only.
- If `tg touch` changes nothing and a page listener sees no `touchstart`, the headless Chrome is stuck. Run `tg cleanup` and
  `tg launch` again; the mouse still works in that state, so it is not an app fault.
- The size override ends with each command. Put `--size` on every command of a recipe, or the page goes back to the window size.
