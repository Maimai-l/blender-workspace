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

## Done
- 10:40 wake-ups scheduled; benchmark extracted (`/home/user/bench_work/moss_keeper.mp4`,
  untrusted clone in `/home/user/bench_untrusted/`).
- 11:00 `notes/benchmark.md`: shot-by-shot critique of both films + scorecard.

- 12:00 engine core: `engine/r3d.py` (SDF modelling, marching cubes, numba rasteriser, shadow
  map), `ink.py` (edge classes → traced chains → tapered variable-width strokes), `cel.py`
  (fills, designed shadows, per-pixel material/panel functions), `rig.py` (rigid parts, mirror).
- 12:30 three concepts (`design/concept_*.jpg`); picked A → "the Warden" (`design/README.md`).
- 13:10 Warden model (`robot/warden.py`): shrine-roof carapace, lidded lamp eyes, furnace grille.
  Face states WIP (`design/warden_faces_wip.jpg`), key poses (`robot/poses.py`).
- 14:00 storyboard from real shot cameras (`shots/shotdefs.py`, `shots/board.py`,
  `board/storyboard_*.jpg`), alternatives for 4 key beats (`board/alternatives.jpg`: picked
  face A, rise B, launch A, sky A), full-res layouts for the painter (`board/layouts/`),
  Phase 2 BG specs (`notes/bg_specs.md`).
- Helpers running (background agents): gouache BG engine + S01/S16/S11 paintings
  (`engine/gouache/`, `bg/`), effects (`engine/fx/`), birds (`engine/birds/`), sound (`audio/`).

## Next
1. Robot surface: moss clumps, chipped paint + rust decals, flowers, the tree on the roof, vines.
2. Final model sheet + face states. 3. Style frame vs. benchmark. 4. Shot renderer + all shots.
5. Send Phase 2 BG specs when the painter reports. 6. v1 by ~21:00.

## Open problems
- (none yet)
