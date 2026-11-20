# Helper tools (Qiting)

The tools specific to Qiting. The general ones (MCP clients, `pcx.py`, file transfer, `rdefer.py`, `push.py`, `xy`,
`calib.py`, `calq.py`, `gridcrop.py`) were first written or extended here and moved to the shared
[`../../tools`](../../tools/README.md) on 2026-11-20; the scripts below import them from there.

## Setup

- Environment: `BLENDER_MCP_URL` and `EXEC_MCP_URL`.
- Project folder on the PC: `D:\Blender\Projects\qiting` (moved from `C:\Users\blender\Documents\qiting` on 2026-11-11; the old path is a junction to it).
- Work folder in the session: `~/.cache/qiting` (`ref/`, `renders/`, `view/`, and `cal/` linking to `tools/cal`).
- Run the Python tools with `python3 -I`; shared ones from this folder as `python3 -I ../tools/<tool>.py` (run from `qiting/`).

## History: the exec route and long jobs

On 2026-11-01 the cloud endpoint for Blender went down after an 11 MB reply, and the rest of round 1 reached Blender
through exec alone. That route became `pcx.py` (with `pc/brelay.py` and `pc/pack.py`), and `bmcp.py` learnt to fall
back to it. In round 2, replies longer than about 100 s were cut by the tunnel, so long renders and checks moved to
Blender timers polled through exec (`rdefer.py`, and `heroes_run.py`, `cmpview.py` below). Both now live in the
shared tools.

| Tool | Use |
| --- | --- |
| `heroes_run.py [names] [--samples] [--scale]` | Beauty shots. `../scripts/render_heroes.py` renders them one by one from timers. Each writes `renders\<name>.jpg.done` when saved; the batch ends with `renders\heroes.done`. Each shot is fetched as soon as it is done |
| `deliver.py` | Fills `交付\` on the PC (comparison renders, side-by-sides, beauty shots, notes) and refreshes the downscaled copies in `../deliverables` |

## Measuring and comparing

| Tool | Use |
| --- | --- |
| `../../tools/calq.py <view.json>` (shared) | Pinhole camera fit. It extends `calib.py`. Observation types: fixed points (`pt`); only the column (`u`) or only the row (`v`) of a known point; silhouette tips (`tipL`/`tipR`) and top/bottom points (`top`/`bot`) of horizontal circles, such as eaves, drums and coping; a point anywhere on a 3D polyline (`curve`, e.g. the stair axis); and the lean of a vertical edge through an image point (`lean`, e.g. a tower in the skyline, which pins the roll). Options: fixed focal length (`f_px`), principal-point shift for cropped photos (`shift`), a vertical pixel scale for stretched photos (`aspect`, solved as `ky`), fixed camera height (`fix_z`). Writes `<view>_sol.json` with `loc`, `target`, `lens`, `roll`, `ky` and the optional Blender lens shift |
| `edgefit.py <cal json> <image>` | Refines a solved camera by chamfer-matching the model's known edges (eaves, coping, lobed terrace rims, stair parapets, from `qt_dims`) to the photo's Canny edges, with optional radial distortion and `ky`. Used for A1 and A2 in round 2 |
| `cal/*.json` | Inputs and solutions for the seven comparison views: W02, P340d, W01, P419, Paf3b and the aerials A1, A2. A1 and A2 also hold far constraints from the master plan (紫云楼's terrace edge, the island) and, for A1, 78 skyline verticals |
| `cmpview.py <cal> <ref image> [--scale] [--crop] [--samples] [--extra]` | Renders a solved camera at the photo's aspect and fetches the image. Writes `renders/sbs_<cal>.jpg`, the reference beside the render, and `renders/ovl_<cal>.jpg`, a 50 % blend. `--extra "VX = {...}"` overrides view settings (sun, exposure, look, haze). Until round 2 it hid the plaza for cameras below it; the hillside is modelled now, so nothing is hidden |
| `rh "hero_a hero_b" [samples] [scale]` | Beauty shots from `../scripts/lib/heroes.py`, through `../scripts/render_heroes.py` |
| `rl '<shots>' [samples] [extra]` | Ad-hoc inspection shots through `../scripts/render_list.py` |

## Camera conventions (fixed in round 2)

Two errors in the round-1 rendering of solved cameras were found and fixed. The measurements were made in Python and were not affected; only the comparison renders were.

- **Roll.** `calib.py` turns a positive roll toward the camera's up vector. `xy_light.camera` applied `-roll`, so every calibrated render was turned by twice the solved roll. That is 6° for the dusk photo 419. It now applies `+roll`; the same fix went into `xingyuan/scripts/lib/xy_light.py`.
- **Vertical stretch (`ky`).** A photo stretched vertically by `ky` needs wider pixels in Blender: `pixel_aspect_x = ky`. Round 2 had first set `pixel_aspect_y = ky`, which squeezes the picture instead.

After the fixes, Blender's own projection (`world_to_camera_view`) of test points agrees with `calq.py` to 0.06 px for all seven cameras.

## Site layout (`../env/`)

| Tool | Use |
| --- | --- |
| `make_env.py` | Builds the round-2 site data from the DWG, the master plan and the aerials: plaza outline, paths and stairs, terrain, tree, lamp, hedge and sculpture positions. Writes `../scripts/lib/qt_env_data.py` (the layout) and `qt_env_grid.py` (0.5 m height, paving, water and bank grids, compressed) |
| `dwgsheet.py` | A crop of the DWG screenshot with a model-metre grid, to read the drawing in model coordinates |
| `rectify.py` | Orthorectifies a calibrated photo onto a horizontal plane at a given height, with the DWG drawn over it |
| `trace_ring.py` | Traces the ring path round the plaza from the DWG |

The Xingyuan tools for its aerial photo and its delivery sheets were left out: `aer3d.py`, `ortho*.py`, `roofscan.py`, `worldplan.py`, `sheets.py`, `rv`, `rvc` and `rvs`. They depend on Xingyuan's own data.
