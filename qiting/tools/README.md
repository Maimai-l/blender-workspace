# Helper tools (Qiting)

These are copied from [`../../xingyuan/tools`](../../xingyuan/tools/README.md) and adapted. They run in the cloud session (Linux, Python 3 with numpy, Pillow, SciPy and OpenCV) and reach the Blender PC over MCP.

## Setup

- Environment: `BLENDER_MCP_URL` and `EXEC_MCP_URL`, as in the Xingyuan tools.
- Project folder on the PC: `C:\Users\blender\Documents\qiting`.
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

## Measuring and comparing

| Tool | Use |
| --- | --- |
| `gridcrop.py <img> x0 y0 x1 y1 out [zoom] [step]` | Crop, enlarge and draw a pixel grid in original coordinates, to read positions by eye |
| `calq.py <view.json>` | Pinhole camera fit. It extends `calib.py`. Observation types: fixed points, image columns of known points, and silhouette tips (leftmost or rightmost) or top/bottom points of horizontal circles, such as eaves, drums and coping. Options: fixed focal length (`f_px`), principal-point shift for cropped photos (`shift`), fixed camera height (`fix_z`). Writes `<view>_sol.json` with `loc`, `target`, `lens`, `roll` and the optional Blender lens shift |
| `cal/*.json` | Inputs and solutions for the five comparison views: W02, P340d, W01, P419 and Paf3b |
| `cmpview.py <cal> <ref image> [--scale] [--crop] [--samples] [--extra]` | Renders a solved camera at the photo's aspect and fetches the image. Writes `renders/sbs_<cal>.jpg`, the reference beside the render, and `renders/ovl_<cal>.jpg`, a 50 % blend. Hides the plaza and the temporary ground when the camera stands below the plaza |
| `rh "hero_a hero_b" [samples] [scale]` | Beauty shots from `../scripts/lib/heroes.py`, through `../scripts/render_heroes.py` |
| `rl '<shots>' [samples] [extra]` | Ad-hoc inspection shots through `../scripts/render_list.py` |

The Xingyuan tools for its aerial photo and its delivery sheets were left out: `aer3d.py`, `ortho*.py`, `roofscan.py`, `worldplan.py`, `sheets.py`, `rv`, `rvc` and `rvs`. They depend on Xingyuan's own data.
