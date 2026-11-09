# Awakening — a 56-second anime short made in Blender

A giant, moss-covered robot has knelt in a forest for ages. At sunrise a small bird lands on its
shoulder, the first ray of light reaches its face, a lamp flickers on in its chest, the ground
trembles, birds burst from the trees, and the robot rises and launches into the golden sky.

The film is rendered as hand-drawn-looking 2D anime (Studio Ghibli as the style reference)
from a 3D scene that is built entirely from code, on the Blender PC, through the Blender MCP.

- Deliverable: `deliver/awakening.mp4` (1920×1080, 24 fps, H.264 + AAC), also on the PC at
  `C:\Users\blender\Documents\awakening\deliver\awakening.mp4`.
- Project file on the PC: `C:\Users\blender\Documents\awakening\awakening.blend` (rebuilt by
  `scripts/build_all.py`; textures in `tex\`, frames in `frames_final\`).

## How the anime look is made

| Element | Technique |
| --- | --- |
| Robot | Procedural bmesh model (`scripts/lib/aw_robot.py`), parts parented to empties (joints). Cel shader node group `AW_Cel` (`aw_shade.py`): Shader-to-RGB on a white diffuse → two hard bands + deep shadow, optional hard specular dot, backlight rim band. Weathering (rust patches, moss on faces that were up while it knelt) is baked per face corner into a colour attribute, so it stays put when the robot moves. Moss clumps, vines and a sapling are separate meshes parented to the parts. |
| Ink lines | Freestyle, on its own view layer `Ink` that excludes all transparent cards (Freestyle treats alpha cards as opaque occluders). Pen pressure: along-stroke taper, calligraphy, thickness noise, Perlin wobble, Bezier smoothing. The ink pass is composited onto the beauty layer through a dilated cryptomatte of the robot and birds. Line boil: the noise seeds change every second frame (`render_job.py`). |
| Timing | Robot keys are posed by hand (`aw_anim.py`) and stepped to twos with F-curve modifiers; cameras move on ones; effects on ones. |
| Backgrounds | A procedural gouache kit (`paint/`, numpy): trees, far forest strips, canopy overhangs, ground tile, grass, flowers, leaves, dust, sky. They are used as painted cards in a multiplane set (`aw_set.py`): foreground giants, midground rings and bushes, three far strips, a painted cloud layer, canopy overhangs placed per shot. Cards turn to face each shot's camera at the cut. |
| Light and air | One warm sun (backlight by default; it swings to the front for the face shot), a dim cool ambient, a volume box of mist, a spot light that only lights the mist (sun shafts), compositor depth fog from the mist pass (reduced on the actors), bloom, lift/gain grade, vignette, paper grain, fades. |
| Effects | Particle debris from the mossy parts while rising, leaves blown by the ignition, leaves spiralling down through the canopy gap, dust puff cards, a lumpy cel dust skirt for the shockwave, cel engine flames with flicker, a tapered emissive trail that follows the robot. |
| Sound | Fully synthesized soundtrack (`audio/make_audio.py`): wind, birds, lamp hum, tremor, groans, ignition, launch, pad. |

## Shots (24 fps)

| # | Time | Shot |
| --- | --- | --- |
| 1 | 0–7 s | Wide: the misty forest, the overgrown kneeling robot, slow push-in |
| 2 | 7–13 s | Shoulder: the small bird flies in and lands on the mossy pauldron |
| 3 | 13–18 s | Face: the first ray of sun slides down the weathered face |
| 4 | 18–23 s | Chest: the core lamp flickers on |
| 5 | 23–28 s | Wide: the ground trembles, dust puffs, birds burst from the trees, the small bird flees, the eyes wake |
| 6 | 28–38 s | Low angle: the robot slowly rises; soil, vines and leaves pour from its armour |
| 7 | 38–43 s | It lifts its head toward the canopy gap |
| 8 | 43–47 s | Engines sputter and ignite; a ring of wind crosses the forest |
| 9 | 47–49.3 s | Launch |
| 10 | 49.3–56 s | Up through the canopy gap: curving trail of light and mist, leaves spiral down, fade out |

## Rebuilding

Inside Blender on the PC (or through the tools below): push `scripts/lib/*.py` to
`C:\Users\blender\Documents\awakening\lib\`, run `scripts/build_all.py`, save. Render with
`blender -b awakening.blend -P lib/render_job.py -- <start> <end> <outdir> [scale%] [samples]`
(the job renders through the marker-bound cameras and writes a progress file), then encode with
`blender -b --factory-startup -P lib/encode_job.py -- <framedir> <out.mp4> 24 [audio.wav]`.

Textures: `python3 paint/make_all.py` regenerates `paint/out/` (about 40 s) deterministically;
`tools/upload_all.sh` copies them to `tex\` on the PC. Audio: `python3 audio/make_audio.py`.

## Tools (cloud session side)

`tools/` is the Qiting tool set (`bmcp.py`, `pcx.py`, `fetch.py`, `rdefer.py`, …) plus
`upload_mcp.py` (fast file upload through Blender's Python, ~1 MB/s) and `putbig.py` (through
exec). See `../qiting/tools/README.md`.
