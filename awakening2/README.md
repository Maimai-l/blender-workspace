# Awakening II — a 75-second 2D anime short, drawn by our own look engine

A giant robot has knelt in an ancient forest for so long that moss, wildflowers and an old tree
grow over it. At sunrise a small bird lands on its shoulder, the first ray of light crosses its
face, a light flickers on inside its chest; the ground trembles, birds burst from the canopy,
it rises, lifts its head to a gap in the canopy, ignites its engines and tears into the golden
sky, leaving a curving trail of light and mist.

- Film: `deliver/awakening2.mp4` (latest) and `deliver/awakening2_vN.mp4` (each version):
  1920×1040 (1.85:1), 24 fps, H.264 + AAC.
- Benchmark study and scorecard: `notes/benchmark.md`. Progress log: `notes/progress.md`.

## How the frames are made (no image or video models anywhere)

| Stage | Code | What it does |
|---|---|---|
| Robot model | `robot/warden.py`, `engine/r3d.py`, `engine/rig.py` | The Warden is modelled as signed-distance-field parts (smooth forms, no visible polygons), meshed once with marching cubes, rigged as rigid parts. |
| Growth | `robot/surface.py`, `robot/vineplan.py` | Moss cushions, soil, an old tree and flowers are placed once from the kneeling pose (on upward faces), so they stay on-model in every later pose; vines hang from down-facing surfaces. |
| Passes | `engine/r3d.py` | Our own numba rasteriser writes passes, never final pixels: part / material id, depth, normals, world and part-space positions, cast-shadow map. |
| Look engine | `engine/cel.py`, `engine/ink.py`, `engine/look.py` | Turns passes into a drawn cel: designed hard-edged shadow shapes (threshold → clean-up → no islands → smooth edge), a sky-fill tone and a deep tone, hand-designed chipped paint / primer / rust patches / rust streaks (box-projected label maps with smooth edges), rivets, painted moss tufts, flowers, cel lamp-eyes; ink traced from id / depth / normal discontinuities into tapered, pressure-varied strokes that sit exactly on the fill edges. |
| Backgrounds | `engine/gouache/` | A gouache painting engine (bristle strokes, wet edges, dry brush, Oklab mixing, unique trees, aerial perspective) paints every shot's multiplane layers in screen space from the storyboard layouts. |
| Effects | `engine/fx/` | Drawn cel effects in 2–3 hard tones on 2s: billowing dust, soil pours and debris, leaves, the wind ring, engine flames, smears and impact frames, the light trail with mist billows; airbrushed light only in the photography pass. |
| Birds | `engine/birds/` | A Japanese white-eye drawn as a cel from one model (landing, hops, chirps, startle, take-off), and flocks. |
| Vines | `engine/vines.py` | Verlet chains drawn as inked strokes with cel leaves; rooted vines tear loose as the robot rises. |
| Shots | `shots/shotdefs.py`, `shots/anim.py`, `shots/shotfx.py`, `shots/render_shot.py` | Cameras, key poses (drawn on 2s/3s with holds), lights, layer order and effects per shot. The robot is redrawn only when its drawing changes; between drawings the cel and the painted layers move as 2D layers under a rostrum-style camera synced to the 3D camera, so pushes and tilts never read as a CG dolly. |
| Photography | `engine/comp.py` | Ground shadows, aerial haze, light wrap, bloom, grade, vignette, paper tooth and grain on 2s. |
| Sound | `audio/` | A fully synthesized score and sound design driven by `audio/cues.json`. |

Design work: `design/` (three concepts, the decision, model sheets, face states), storyboard
and layouts: `board/`, style frame: `style/`, QA sheets: `qa/<version>/`.

## Running it

- Sandbox (4 CPUs): `python3 shots/render_shot.py S08` renders a shot to `/home/user/aw2_frames/S08/`;
  `python3 tools/assemble.py vN --qa` encodes and writes the QA sheets.
- The Windows PC (28 threads) through the exec MCP: `python3 tools/pc.py sync`, `pc.py bg S01 ...`,
  `pc.py render vN --workers 7`, `pc.py status vN`, `pc.py encode vN`.

## Changes to the prompt, and why

- **Frame 1920×1040 (1.85:1)** instead of 1920×1080: theatrical framing, and the side-by-sides
  line up with the benchmark frame for frame (the prompt allowed either).
- **No Blender for the robot.** The prompt allowed Blender as a helper; we modelled the robot as
  signed-distance fields in our own code and rasterised the passes with our own numba
  rasteriser. That keeps every pass (part ids, part-space positions for decals, light and shadow
  masks) under our control and avoids moving gigabytes of passes between machines.
- **Heavy rendering on the Windows PC** (28 threads, through the exec MCP) instead of the
  4-CPU sandbox, with the same Python code: the PC renders the film in ~25 minutes, which made
  several polish rounds possible. Code goes up as a tarball because the PC cannot reach GitHub
  reliably; background paintings are regenerated there from their deterministic source.
- **Camera moves between drawings are 2D moves of the cels and painted layers** (a rostrum /
  multiplane camera synced to the 3D camera). The robot is only redrawn when its drawing
  changes (on 2s/3s, or once for a held pose). This is how cel animation works and it keeps
  pushes and tilts from reading as a CG dolly; the prompt asked for "camera on 1s, robot on
  2s/3s" and this is the faithful way to get both.
- **One-knee kneel** (a "resting knight") instead of the slumped two-knee kneel of our first
  boards: from the main camera it is the only pose that reads as kneeling at thumbnail size.
- **The first ray is a low sunrise beam** (8° above the horizon) through a gap in the trunks, not
  a shaft from the canopy above: the robot's bowed face points down, so only a low sun can light
  the face itself — and at sunrise that is what the sun does.

## Self-assessment and version history

### v1 (12:25) — first complete film
All 17 shots, the full soundtrack. Built with the first versions of every system; the shots
were rendered before most of the fixes below, so v1 is the baseline. Known problems at v1:
the face close-ups (S03/S07) are seen from a steep low angle with a dutch tilt and the face does
not read; the robot is washed pink by haze and bloom; S10 uses a fallback painting that breaks
at its top edge; S16's trail is a vertical plume that buries the light ribbon; S04's light
spill is a flat orange disc; S01's robot drifts against the painted floor during the tilt; no
vines yet; the rise is a simple blend between three poses.

### v2 (12:50)
- Vines on the robot (verlet chains drawn as inked strokes with cel leaves); rooted vines tear
  loose as it rises, the rest swing with the breeze and the motion.
- The rise rebuilt from seven key poses (sink, plant the hand, push, crouch, rise, stand, torso
  up, look up) on 3s with holds; sound cues retimed to them.
- Face shots: level-eyed cameras in front of the bowed face; the first ray is a low sunrise beam
  that lights the face (the brow throws a crescent shadow over the shut eyes), motes in the beam.
- The launch: a held crouch with the engines roaring behind it, two smear frames, two impact
  frames (black/gold), then a blast with ground dust rolls, debris, leaves and speed lines.
- The climax redesigned: the robot climbs along a big screen-space arc toward the sun, the trail
  of light and mist follows the arc (S16).
- All 14 backgrounds repainted by the painter's Phase 3 (golden sky with sculpted clouds, ground
  close-up, layered crowns instead of pads, rim-lit canopy for the flock).
- Fixes: S01 tilt drift, S10 painting window, S04 framing, bigger bird, less haze and bloom,
  rivets, tufts on the roof tree, S05 camera matched to its painting's horizon, flock between
  the canopy layers.
