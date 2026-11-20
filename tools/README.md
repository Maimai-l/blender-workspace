# Shared session-side tools

The tools every project and the maintenance sessions use to reach the Blender PC from the cloud session (Linux,
Python 3; the camera tools also need numpy, SciPy and Pillow). They used to be copied into each project's `tools/`
(Xingyuan → Qiting → Awakening → Mana cafe), which left five diverging copies and made maintenance work borrow
`qiting/tools`. Since 2026-11-20 there is one copy here; a project's `tools/` keeps only what is specific to it.

Run the Python tools with `python3 -I`. The MCP addresses come from `BLENDER_MCP_URL` and `EXEC_MCP_URL`
(see `.mcp.json`); in the cloud session the proxy adds the credentials and its CA bundle is used automatically.

## Which project a run belongs to (`xyp.py`)

1. `XY_PROJECT=<project folder name or path>`;
2. otherwise the folder of the script being run, when it is inside `<repo>/<project>/` (a project tool);
3. otherwise the current directory, when it is inside `<repo>/<project>/`.

With a project: `PC_ROOT` is `D:\Blender\Projects\<project>` (override `XY_PC_ROOT`), the session work folder is
`~/.cache/<project>` (override `XY_WORK`) with `crops/ renders/ deliver/ ref/` and links to the project's
`refs/crops`, `tools/cal` and `refs/pages`. Without one (ops work from the repo root) the project-free tools still
work and the work folder is `~/.cache/pc-tools`; `push.py`, `xy` and `--pc-root` stop with a clear message.

On the PC, everything the tools themselves need lives in `D:\Projects\pc-tools` (`XY_PC_TOOLS`), never in a project
folder: `brelay.py` and `pack.py` (sources in `pc/`, uploaded or updated automatically when their md5 differs) and the
transfer scratch `tmp\`, which `ops/pc_tidy.sh` clears.

## Tools

| Tool | Use |
| --- | --- |
| `pcx.py` | Reaches the PC through the exec server only. `pcx.py bash "<cmd>"` runs Git Bash as the `blender` account; `pcx.py code "<python>"` / `pcx.py blender file.py ["prepended code"]` run code in the live Blender via `pc/brelay.py` and the add-on socket `127.0.0.1:9876` (long jobs keep running while it polls); `pcx.py fetch <remote> <local>` / `pcx.py put <local> <remote>` copy files of any size. In Python: `pcx.bash`, `pcx.blender`, `pcx.fetch`, `pcx.put`, `pcx.put_text`, `pcx.wait_file` |
| `bmcp.py` | Blender MCP client: `bmcp.py run file.py ["X = 1"] [--out f]`, `bmcp.py code "..."`, `bmcp.py tools`. Falls back to the exec route when the endpoint is down; `XY_VIA_EXEC=1` forces that route, `0` forbids it |
| `execc.py` | Low-level exec MCP client (`execc.py bash "<cmd>"`). Only the 7 tools allowed in `.claude/settings.json` can be called |
| `fetch.py <remote> <local>`, `upload.py <local> <remote>` | One file from / to the PC through exec (`pcx.fetch` / `pcx.put`) |
| `putbig.py <local> <remote>` | Large uploads through exec, as parallel base64 pieces joined on the PC |
| `upload_mcp.py <local> <remote> [chunk_kB]` | Upload through Blender's Python (`execute_blender_code`), about 1 MB/s; skips files whose md5 already matches |
| `rdefer.py <script.py> ["PRE = 1"] [--timeout s]` | Runs a long Blender script from a `bpy.app.timers` callback, so the MCP reply returns at once (the tunnel cuts replies at about 100 s), then waits for its output file through exec and prints it. Output goes to `<PC project>\renders\job_<id>.txt`, or `pc-tools\tmp` without a project |
| `push.py [files]` | Copies `<project>/scripts/lib/*.py` to `<PC project>\lib` and `scripts/proc/*.py` (if any) to `<PC project>\proc`, in one Blender call |
| `xy push \| run file.py \| runonly file.py \| code "..."` | Shell shortcut: push, then run in Blender |
| `calib.py`, `calq.py` | Pinhole camera fits from image points (`calq.py` adds silhouette tips of circles, single coordinates, polylines, leaning verticals, fixed focal length, shift and vertical stretch). See `xingyuan/docs/lessons.md` and the Qiting README |
| `gridcrop.py <img> x0 y0 x1 y1 out [zoom] [step]` | Crop, enlarge and draw a pixel grid in original coordinates |
| `pc/brelay.py`, `pc/pack.py` | PC-side helpers of `pcx.py` (run with Blender's bundled Python). `brelay.py` writes its result and the `.done` marker even when Blender is not running, so callers never hang |

Measured limits: exec's Bash returns at most 30,000 characters and its Read 25,000 tokens of text; a single exec
call through these clients may take up to about 90 s (the session's built-in `mcp__exec__*` tools give up after about
30 s). Keep every Blender MCP reply small: an 11 MB reply made the Blender MCP server exit on 2026-11-01.

## Examples

```bash
python3 -I tools/pcx.py bash "ls /d/Projects"                       # ops work, no project
cd qiting && python3 -I ../tools/rdefer.py scripts/stats.py         # project from the cwd
XY_PROJECT=mana_cafe tools/xy push                                  # project from the environment
```

## Writing a project tool

Put it in `<project>/tools/` and start it with

```python
import os, sys
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools')]
import xyp, bmcp, pcx      # xyp.PROJ / PC_ROOT / PTOOLS / S now refer to this project
```

Shell scripts set `SHARED=$(cd "$TOOLS/../../tools" && pwd)` and `export XY_PROJECT="$(dirname "$TOOLS")"`
(see `qiting/tools/rl`). Anything useful beyond one project belongs here instead, with its README row.
