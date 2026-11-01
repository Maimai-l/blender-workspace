# Helper tools

These scripts run in the cloud session (Linux, Python 3 with numpy, Pillow, SciPy, OpenCV). They talk to Blender and to the exec server on the Blender PC through MCP over HTTP. They were written during the two build rounds; [`../docs/lessons.md`](../docs/lessons.md) explains how they were used.

## Setup

- Environment: `BLENDER_MCP_URL` and `EXEC_MCP_URL`, from the environment the repo's `.mcp.json` uses. In the cloud session the proxy adds the credentials, and its CA bundle (`/root/.ccr/ca-bundle.crt`) is used when present. Override it with `XY_CA_BUNDLE`.
- Project folder on the PC: `XY_PC_ROOT`, default `C:\Users\blender\Documents\<project folder name>`.
- Work folder: `XY_WORK`, default `~/.cache/<project folder name>`. `xyp.py` creates it on first use:
  - output folders `crops/`, `renders/`, `deliver/`;
  - links to the reference images in `../refs/` and the camera fits in `cal/`.
- Run the Python tools with `python3 -I`; each adds its own folder to the import path.
- To reuse the tools in another project, copy this folder to `<project>/tools`, next to `<project>/scripts/lib` and `<project>/refs`.

## Talking to Blender and the PC

| Tool | Use |
| --- | --- |
| `bmcp.py` | Blender MCP client. `bmcp.py run file.py "X = 1"` runs a local file in Blender, with the given code prepended; `bmcp.py code "..."` runs inline code. |
| `push.py` | Copies every `../scripts/lib/*.py` to `lib\` in the project folder on the PC (for this project `C:\Users\blender\Documents\xingyuan\lib\`), in one call. |
| `xy` | `xy push`, `xy run file.py` (push, then run), `xy runonly file.py`, `xy code "..."`. |
| `fetch.py` / `upload.py` | Download or upload one file between the PC and the session, as base64 through Blender's Python. `fetch.py remote local [chunk_MB]` sends 8 MB pieces by default, so files of any size work; `upload.py` sends 300 kB pieces. |
| `execc.py` | exec server client: `execc.py bash "<command>"` runs in Git Bash on the PC as the `blender` account. Only the 7 tools that `.claude/settings.json` allows can be called. |

**Before running anything that changes the scene, check which file Blender has open.** For example: `xy code "import bpy; print(bpy.data.filepath, len(bpy.data.objects))"`. Blender may have been restarted or switched to another project.

## Rendering

| Tool | Use |
| --- | --- |
| `rl '<shots>' [samples] [extra]` | Ad-hoc shots through `../scripts/render_list.py`. Each shot is `(name, loc, target, lens, (w, h))`; the extra code sets e.g. `ELEV=40; AZIM=140`. Fetches the JPGs and tiles them into `renders/grid_<first>.jpg`. |
| `rh "hero_a hero_b" [samples] [scale]` | Beauty shots from `../scripts/lib/heroes.py`. |
| `rvs "aerial A2 ..." [samples] [scale]` | Comparison views from `../scripts/lib/views.py`, each with a reference/render side-by-side `renders/sbs_<view>.jpg`. |
| `rv`, `rvc` | One view from a dict / from a solved camera in `cal/`. |
| `sheets.py` | The labelled side-by-side sheets and the overview. Reads `deliver/对照_*.jpg` and writes `deliver/并排对比_*.jpg`. |

Render outputs on the PC go to `C:\Users\blender\Documents\xingyuan\renders\`. Inspection renders belong in `renders\_调试`, not next to the deliverables.

## Measuring the references

| Tool | Use |
| --- | --- |
| `calib.py` | Pinhole camera fit from world-to-image point pairs (least squares), with variants for bounds, a free aspect ratio and lens shift. Inputs and results: `cal/*.json`. |
| `aer3d.py` | The solved aerial camera (`cal/aerial_p.json`): `project(X)` gives the full-resolution pixel of a plan point; `ground(u, v, z)` casts a pixel onto a horizontal plane. |
| `ortho.py`, `ortho_arr.py`, `ortho_grid.py` | Rectify the aerial onto a plane at a chosen height, with a metre grid. Used to read plan positions. |
| `crop.py`, `gridcrop.py`, `pxgrid.py` | Crops of the reference pages, optionally with a pixel or metre grid. |
| `roofscan.py`, `worldplan.py` | One-off readings from round 1: roof profile from the section page; plan sheet scaled to metres. |

The full-resolution aerial is `../refs/pages/杏园介绍-01_10.jpg`. The comparison crops in `../refs/crops/` relate to it by `crop = full × 0.32044`, with `y_crop = y_full × 0.32044 − 71.556`.
