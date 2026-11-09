# Awakening II — progress log

Deadline: 04:30 Tuesday 2026-11-10, Toronto time (`TZ=America/Toronto date`).
Wake-ups scheduled (send_later, this session): hourly 11:36 → 03:36, plus 04:02 (Toronto).

## Decisions
- Frame: 1920×1040 (1.85:1 theatrical, same as the benchmark so side-by-sides line up), 24 fps.
- Everything renders in the cloud sandbox (4 CPUs, 15 GB here, numpy + numba + OpenCV +
  scikit-image installed with pip). The PC is optional (only if a measured need appears).
- Robot: modelled as SDF parts (smooth forms, no polygons) → marching-cubes meshes → our own
  numba rasterizer writes passes (part/material id, depth, normal, light, shadow, object-space
  position) → our look engine draws the frame (ink, cel fills, designed shadows, decals, moss).
- Backgrounds: painted per shot in screen space by our gouache engine (multiplane layers).
- Effects, birds: drawn 2D cels with 2–3 hard tones, on 2s.
- Git: work on branch `claude/blissful-pascal-n67qmw` and also push to `main` (CLAUDE.md).
- Times in this log are Toronto time (check with `TZ=America/Toronto date`; do not estimate).

## Done
- 10:40 wake-ups scheduled; benchmark extracted (`/home/user/bench_work/moss_keeper.mp4`,
  untrusted clone in `/home/user/bench_untrusted/`).
- 10:50 `notes/benchmark.md`: shot-by-shot critique of both films + scorecard.

- 11:00 engine core: `engine/r3d.py` (SDF modelling, marching cubes, numba rasteriser, shadow
  map), `ink.py` (edge classes → traced chains → tapered variable-width strokes), `cel.py`
  (fills, designed shadows, per-pixel material/panel functions), `rig.py` (rigid parts, mirror).
- 11:05 three concepts (`design/concept_*.jpg`); picked A → "the Warden" (`design/README.md`).
- 11:10 Warden model (`robot/warden.py`): shrine-roof carapace, lidded lamp eyes, furnace grille.
  Face states WIP (`design/warden_faces_wip.jpg`), key poses (`robot/poses.py`).
- 11:20 storyboard from real shot cameras (`shots/shotdefs.py`, `shots/board.py`,
  `board/storyboard_*.jpg`), alternatives for 4 key beats (`board/alternatives.jpg`: picked
  face A, rise B, launch A, sky A), full-res layouts for the painter (`board/layouts/`),
  Phase 2 BG specs (`notes/bg_specs.md`).
- Helpers running (background agents): gouache BG engine + S01/S16/S11 paintings
  (`engine/gouache/`, `bg/`), effects (`engine/fx/`), birds (`engine/birds/`), sound (`audio/`).

- 11:30 robot surface (`robot/surface.py`, `robot/build.py`): moss cushions placed from the
  kneeling pose, painted tufts, flowers, the old tree + soil on the left roof half, designed
  chip/primer/rust/streak decals (box-projected AA coverage maps). Sky-fill shadow tone.
- 11:35 style frame `style/style_S01.png` (BG S01 + robot + ground shadow + haze + light wrap
  + bloom/grade). S01 camera moved to the robot's front-right (the one-knee kneel reads there).
- 11:40 production renderer: `shots/render_shot.py` (robot drawing cached per pose; 2D camera
  follows the 3D one via an anchor; ground shadows; dual-light cel for the S03 ray) and
  `shots/shotfx.py` (one class per shot: painting + layer order + light + effects + birds).
  Assembly + QA: `tools/assemble.py vN --qa`. Frames go to /home/user/aw2_frames/<shot>/.

- 11:45 v1 render started in the sandbox (3 groups, logs /home/user/aw2_logs/g*.log).
- 11:50 vines (`engine/vines.py`, `robot/vineplan.py`): verlet chains from down-facing
  surfaces, rooted ones snap during the rise; rivets along seams (`robot/build.py`).
- 12:05 PC render farm: `tools/pc.py` (sync / bg / render / status / encode / fetch) and
  `tools/pc_worker.py`. PC: C:\Users\blender\Documents\awakening2\{code,pylib,cache,frames};
  Blender's Python 3.13 + pylib (numba, cv2, skimage, scipy, PIL, imageio-ffmpeg). The PC
  cannot reach github.com reliably, so code goes up as a tarball (`pc.py sync`), and the
  background paintings are regenerated on the PC from the deterministic gouache code
  (`pc.py bg S01 ...`, 6–25 s each). Detached PC jobs must use `( nohup ... & )`.
  ~6 workers fit in the PC's free RAM (18 GB of 32).

- 12:00–12:15 v1 rendered on the PC (7 workers ran out of RAM on some chunks; refilled with
  `pc.py render v1fill --skip --workers 4`). v2 fixes made meanwhile (sandbox code, not yet on
  the PC): vines everywhere, subtler rivets, head less bowed, less haze/bloom, refined rise
  poses (KNEEL_SINK, PUSH_PLANT, PUSH_UP, STAND_RISE, STAND_TORSO_UP), level-eyed face cameras
  (`face_cam`, roll keys), a low sunrise ray for S03, eyelid crease, S04 framing, bigger bird,
  S16 redesigned as an arc (`s16_root`), tilt drift fix (distance-based scale, matching depth),
  bounded layer cache, contiguous chunk scheduling (pc_worker).
- Sound: helper finished (audio/README.md); mix.wav follows cues.json v1.

## Next
1. v1: encode on the PC, mux mix.wav, QA sheets, commit + push.
2. v2: sync code, regenerate BGs on the PC (painter's Phase 3), render with 5 workers.
2. Phase 2 BGs arriving from the painter (fallbacks are used until each bg/<shot>/layers.json
   exists). 3. Polish rounds: weathering contrast on the robot, rivets, vines, BG fixes.

## Open problems
- Robot reads a little pink/clean in haze: needs darker, weathered paint and stronger value split.
- BG S01 mid trees look like stacked bonsai pads (feedback sent to the painter).
