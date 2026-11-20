# Helper tools (Mana cafe)

The tools specific to the Mana cafe. The general ones (`bmcp.py`, `pcx.py`, `execc.py`, `fetch.py`, `upload.py`,
`push.py`, `rdefer.py`, `calib.py`, `calq.py`, `gridcrop.py`) are in the shared [`../../tools`](../../tools/README.md)
since 2026-11-20; run them from `mana_cafe/` as `python3 -I ../tools/<tool>.py` so they pick this project. They run in
the cloud session (Linux, Python 3 with numpy, Pillow, SciPy) and reach the Blender PC over MCP (`BLENDER_MCP_URL`,
`EXEC_MCP_URL`). The project folder on the PC is `D:\Blender\Projects\mana_cafe`; the work folder in the session is
`~/.cache/mana_cafe`. Run the Python tools with `python3 -I`.

| Tool | Use |
| --- | --- |
| `pyrun.py <scripts/proc/x.py> [args]` | pushes `scripts/lib` and `scripts/proc` (shared `push.py`), then runs a data-processing script on the PC with Blender's bundled Python, outside Blender. `<PC project>\pylib` holds numba, SciPy, Pillow and rasterio for it |
| `rr.py <name> [--scale] [--samples] [--res WxH] [--cam] [--border x0 y0 x1 y1] [--png] [--pre code]` | renders from a timer, fetches the image to `~/.cache/mana_cafe/renders/`. It leaves the scene at the given resolution and camera |
| `regrade.py <name> "<code>"` | saves the last render again with other display settings (look, exposure, curve) and prints tone statistics of a few picture regions; no re-render |
| `depthcheck.py <render> [depth name] [--fetch]` | measures a render by band of real view distance (shadows, midtones, highlights, blue/red), from the depth pass that `scripts/depth_pass.py` writes (run it through `../tools/rdefer.py`) |
| `tiles.py <image> [cols rows]` | cuts a render into overlapping tiles for region-by-region inspection |

The PC downloads through the local proxy `127.0.0.1:7897` (`proc/ph_get.py`); direct downloads from S3 are slow there.
