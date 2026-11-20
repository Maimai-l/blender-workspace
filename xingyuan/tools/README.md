# Helper tools

These scripts run in the cloud session (Linux, Python 3 with numpy, Pillow, SciPy, OpenCV). They talk to Blender and to the exec server on the Blender PC through MCP over HTTP. They were written during the two build rounds; [`../docs/lessons.md`](../docs/lessons.md) explains how they were used.

## Setup

- The general tools (`bmcp.py`, `execc.py`, `fetch.py`, `upload.py`, `push.py`, `xy`, `xyp.py`, `calib.py`) moved to
  the shared [`../../tools`](../../tools/README.md) on 2026-11-20; the scripts here import them from there, and the
  shell scripts (`rl`, `rh`, `rv`, `rvc`, `rvs`) call them with `XY_PROJECT` set to this project.
- Environment: `BLENDER_MCP_URL` and `EXEC_MCP_URL`, from the environment the repo's `.mcp.json` uses.
- Project folder on the PC: `D:\Blender\Projects\xingyuan` (`C:\Users\blender\Documents\xingyuan` is a junction to it).
- Work folder: `~/.cache/xingyuan`, with `crops/`, `renders/`, `deliver/` and links to `../refs/pages`
  (`ref/xingyuan-images/`), `../refs/crops` (`refc/`) and `cal/`.
- Run the Python tools with `python3 -I`. To talk to Blender, e.g. `cd xingyuan && ../tools/xy code "..."`.

**Before running anything that changes the scene, check which file Blender has open.** For example: `../tools/xy code "import bpy; print(bpy.data.filepath, len(bpy.data.objects))"` from `xingyuan/`. Blender may have been restarted or switched to another project.

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
| `../../tools/calib.py` (shared) | Pinhole camera fit from world-to-image point pairs (least squares), with variants for bounds, a free aspect ratio and lens shift. Inputs and results: `cal/*.json`. |
| `aer3d.py` | The solved aerial camera (`cal/aerial_p.json`): `project(X)` gives the full-resolution pixel of a plan point; `ground(u, v, z)` casts a pixel onto a horizontal plane. |
| `ortho.py`, `ortho_arr.py`, `ortho_grid.py` | Rectify the aerial onto a plane at a chosen height, with a metre grid. Used to read plan positions. |
| `crop.py`, `gridcrop.py`, `pxgrid.py` | Crops of the reference pages, optionally with a pixel or metre grid. |
| `roofscan.py`, `worldplan.py` | One-off readings from round 1: roof profile from the section page; plan sheet scaled to metres. |

The full-resolution aerial is `../refs/pages/杏园介绍-01_10.jpg`. The comparison crops in `../refs/crops/` relate to it by `crop = full × 0.32044`, with `y_crop = y_full × 0.32044 − 71.556`.
