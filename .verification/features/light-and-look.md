# Light and look

The user changes the sun direction and height, the relief strength and height, the imagery layer and the colour look. The image changes at once, with no data call.

## Sub-features

- `light-wheel` turns the light with the compass wheel.
- `light-preset` applies Classic, Dawn, Golden, Noon, Dramatic, Overcast.
- `light-steps` sets sun height, relief and height with the Low/Mid/High, Soft/Medium/Strong and 1×/2×/3× steps.
- `layer` switches Natural, Infrared, NDVI glow, Relief.
- `look` applies Natural, Golden, Alpenglow, Swiss, Moonlight, Mono.

## How to get to it (user POV)

- Drag the sun around the wheel in the Light section, or use the arrow keys.
- Choose a preset button or a step button in the Light section.
- Choose a layer in Imagery, or press `1` to `4`. Choose a look swatch, or press `L`.

## Driving it with tg

Preconditions:

- Baseline open, drawn.

- **Preset.** `tg shot light-before`, `tg click '.preset[data-v="golden"]'`, `tg shot light-golden`. `tg state` shows `az: 255`, `alt: 14`; the two screenshots differ in the shadows.
- **Wheel.** `tg turn-wheel 210` drags the sun along the ring. It prints `az_now` near 210; `tg shot light-wheel` shows the sun at SSW on the wheel and new shadows.
- **Layer.** `tg click '#layerSeg button[data-v="false"]'`, `tg shot layer-infrared`. Vegetation is red. `tg state` shows `layer: false`.
- **Look.** `tg click '.look[data-v="alpenglow"]'`, `tg shot look-alpenglow`. `tg state` shows `look: alpenglow`.
- **No data call.** `tg state` `footer` is unchanged and `loading` stays false after each step.

## Gotchas

- Light changes do not call Python. If `loading` turns true, a data param changed by mistake.
- The light preset label in the Light heading shows "Custom" when the values match no preset.
