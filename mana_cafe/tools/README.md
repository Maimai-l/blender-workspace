# Helper tools (Mana cafe)

Copied from [`../../qiting/tools`](../../qiting/tools/README.md) and adapted. They run in the cloud session (Linux,
Python 3 with numpy, Pillow, SciPy) and reach the Blender PC over MCP (`BLENDER_MCP_URL`, `EXEC_MCP_URL`). The project
folder on the PC is `D:\Blender\Projects\mana_cafe`; the work folder in the session is `~/.cache/mana_cafe`.
Run the Python tools with `python3 -I`.

| Tool | Use |
| --- | --- |
| `bmcp.py`, `pcx.py`, `execc.py`, `fetch.py`, `upload.py` | as in Qiting: Blender and exec clients, file transfer |
| `push.py` | writes `../scripts/lib/*.py` to `<PC project>\lib` and `../scripts/proc/*.py` to `<PC project>\proc` |
| `rdefer.py <script.py> ["PRE = 1"]` | runs a Blender script from a timer and prints what it printed (long jobs) |
| `pyrun.py <scripts/proc/x.py> [args]` | runs a data-processing script on the PC with Blender's bundled Python, outside Blender. `<PC project>\pylib` holds numba, SciPy, Pillow and rasterio for it |
| `rr.py <name> [--scale] [--samples] [--res WxH] [--cam] [--border x0 y0 x1 y1] [--png] [--pre code]` | renders from a timer, fetches the image to `~/.cache/mana_cafe/renders/`. It leaves the scene at the given resolution and camera |
| `regrade.py <name> "<code>"` | saves the last render again with other display settings (look, exposure, curve) and prints tone statistics of a few picture regions; no re-render |
| `tiles.py <image> [cols rows]` | cuts a render into overlapping tiles for region-by-region inspection |
| `calib.py`, `calq.py`, `gridcrop.py` | camera fitting and reference crops, unchanged from Qiting |

The PC downloads through the local proxy `127.0.0.1:7897` (`proc/ph_get.py`); direct downloads from S3 are slow there.
