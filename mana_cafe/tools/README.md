# Helper tools (Qiting)

These are copied from [`../../xingyuan/tools`](../../xingyuan/tools/README.md) and adapted. They run in the cloud session (Linux, Python 3 with numpy, Pillow, SciPy and OpenCV) and reach the Blender PC over MCP.

## Setup

- Environment: `BLENDER_MCP_URL` and `EXEC_MCP_URL`, as in the Xingyuan tools.
- Project folder on the PC: `D:\Blender\Projects\qiting` (moved from `C:\Users\blender\Documents\qiting` on 2026-11-11; the old path is a junction to it, so the scripts' paths still work).
- Work folder in the session: `~/.cache/qiting`. It holds:
  - `ref/`: full-resolution references;
  - `renders/`;
  - `view/`;
  - `cal/`: a link to `tools/cal`.

Run the Python tools with `python3 -I`.

## Talking to Blender through exec (new in this project)

On 2026-11-01 the cloud endpoint for Blender went down: a fetch of an 11 MB response made the Blender MCP server exit, and its proxy was not restarted.

For the rest of that round the tools reached Blender through the **exec** server only. On 2026-11-07 the service was started again through the PC's agent, and the endpoint works.

`bmcp.py` now tries the Blender MCP endpoint first. If the endpoint is down (a 5xx answer or no answer), `execute_blender_code` falls back to the exec route below. `XY_VIA_EXEC=1` forces the exec route; `XY_VIA_EXEC=0` forbids it.

Files always travel through exec (`fetch.py`, `upload.py`), so the Blender MCP server never has to send a large reply.

| Tool | Use |
| --- | --- |
| `pcx.py` | The client for this route. `pcx.py code "..."` and `pcx.py blender file.py ["prepended code"]` run code in the live Blender. `pcx.py bash "..."` runs Git Bash on the PC. `pcx.py fetch <remote> <local>` and `pcx.py put <local> <remote>` copy files |
| `pc/brelay.py` | Installed in `<PC project>\tools\` and run with Blender's bundled Python. It sends a code file to the Blender MCP add-on's local socket, `127.0.0.1:9876`, and writes the printed output to a file. `pcx.blender` starts it in the background and polls for the result, so long jobs survive the 90 s request limit |
| `pc/pack.py` | Installed next to `brelay.py`. It wraps any file into lossless greyscale PNG pieces, 2000×250 px, each about 500 kB. exec's file reader returns images up to about 510 kB unchanged and re-encodes bigger ones as JPEG. `pcx.fetch` reads the pieces in parallel at about 1 MB/s |
| `bmcp.py`, `push.py`, `fetch.py`, `upload.py`, `xy`, `rl`, `rh` | As in Xingyuan, now on top of `pcx`. `push.py` writes all of `../scripts/lib/*.py` to `<PC project>\lib\` in one Blender call |

Limits of the exec tools, measured:

- Bash returns at most 30,000 characters of output.
- Read returns at most 25,000 tokens of text, and images up to 2000 px.

## Long jobs (new in round 2)

The tunnel in front of the Blender MCP endpoint drops a reply after about 100 s ("No data received"), even though `bmcp.py` waits 600 s. Renders of the full scene and the geometry checks take longer than that. So long jobs run from a Blender timer and report through a file, and the caller polls that file through exec. exec is a separate process, so it is not blocked while Blender works.

| Tool | Use |
| --- | --- |
| `pcx.wait_file(remote)` | Waits for a file on the PC, in rounds of 75 s of `test -f` in Git Bash, and returns its text |
| `rdefer.py <script.py> ["PRE = 1"]` | Runs any Blender script from a timer, writes what it prints to `renders\job_<id>.txt` and prints it here. Used for the checks and the statistics |
| `heroes_run.py [names] [--samples] [--scale]` | Beauty shots. `../scripts/render_heroes.py` renders them one by one from timers. Each writes `renders\<name>.jpg.done` when saved; the batch ends with `renders\heroes.done`. Each shot is fetched as soon as it is done |
| `cmpview.py` | Sets `defer` in the view, so `../scripts/render_view.py` renders from a timer and writes `<jpg>.done`, or `FAILED` and the traceback |

## Measuring and comparing

| Tool | Use |
| --- | --- |
| `gridcrop.py <img> x0 y0 x1 y1 out [zoom] [step]` | Crop, enlarge and draw a pixel grid in original coordinates, to read positions by eye |
| `calq.py <view.json>` | Pinhole camera fit. It extends `calib.py`. Observation types: fixed points (`pt`); only the column (`u`) or only the row (`v`) of a known point; silhouette tips (`tipL`/`tipR`) and top/bottom points (`top`/`bot`) of horizontal circles, such as eaves, drums and coping; a point anywhere on a 3D polyline (`curve`, e.g. the stair axis); and the lean of a vertical edge through an image point (`lean`, e.g. a tower in the skyline, which pins the roll). Options: fixed focal length (`f_px`), principal-point shift for cropped photos (`shift`), a vertical pixel scale for stretched photos (`aspect`, solved as `ky`), fixed camera height (`fix_z`). Writes `<view>_sol.json` with `loc`, `target`, `lens`, `roll`, `ky` and the optional Blender lens shift |
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
