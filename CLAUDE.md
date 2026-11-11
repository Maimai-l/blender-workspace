# Blender 工作区说明

## 约定
- 仓库改动默认直接提交并推送到 `main` 分支（用户已明确授权），不另开分支，也不建 PR。
- 工作文件存到 `D:\Blender\Projects\<项目>\`，保存时写绝对路径。C 盘是系统盘，大文件不要放 C 盘。
- 2026-11-11 把之前的项目都迁到了 D 盘：
  - Blender 项目（`xingyuan`、`qiting`、`awakening`、`awakening2`、`DungeonEscape`、`WordDefense`、`donut`）在 `D:\Blender\Projects\`；
  - Unity 工程在 `D:\Unity\Projects\`，包括误建的空工程 `My project`；
  - 小工具 `LDAdBlock`、`wawa` 在 `D:\Projects\`。
  - `C:\Users\blender\Documents\` 下的同名文件夹和 `C:\Users\blender\My project` 是指向 D 盘的目录联接，脚本里写死的旧路径照样能用。比较路径时先用 `os.path.realpath` 解析联接。
  - `Documents` 里只剩 `vocabulary.db`：Word Defense 按这个路径读词库。
- 渲染帧序列、视频、音频、QA 截图这类大文件或生成物只放在电脑的项目文件夹里，不提交到仓库（`.gitignore` 已排除视频和音频）；仓库里的图片只放缩小的预览，每张不超过约 1 MB。旧版本的渲染输出确认不用后就删掉。2026-11-11 清理过一次：仓库里的 Awakening 视频、音频和测试图都已移出。

## 环境（2026-10 实测）
- 用户电脑：Windows，CPU 为 i7-14700KF，显卡为 RTX 5070 Ti，有 C:、D: 两个盘。
- Blender 5.2.3 LTS（Python 3.13），装在 `D:\Program Files\Blender Foundation\Blender 5.2`，这也是脚本里 `os.getcwd()` 的结果，所以相对路径会落到安装目录。
- 用户目录是 `C:\Users\blender`，下面有 `Documents`、`Desktop`、`Downloads`、`OneDrive`。`Documents` 没有被 OneDrive 接管。临时目录是 `C:\Users\blender\AppData\Local\Temp`。
- 渲染引擎的标识符是 `BLENDER_EEVEE`、`BLENDER_WORKBENCH`、`CYCLES`，默认用 EEVEE。EEVEE 渲染 1080p 的 50% 不到 1 秒。
- Cycles 已设为用显卡渲染：偏好设置里计算设备是 `OPTIX`，只启用了 RTX 5070 Ti。新建场景时 `scene.cycles.device` 要设成 `GPU`，否则仍走 CPU。实测 960×540、256 采样：显卡 1.5 秒，CPU 4.4 秒。很小的渲染因为要加载内核，显卡反而略慢。
- 视口和 EEVEE 始终用显卡，与上面的 Cycles 设置无关。
- MCP 插件 1.8：资源库（Poly Haven、Sketchfab、Poly Pizza）和 3D 生成全部关闭，数据收集也关闭。
- Unity 6000.4.2f1（`D:\Program Files\Editor\Unity.exe`，从 Unity Hub 启动），当前项目是 `D:/Unity/Projects/Dungeon Escape`（2026-10-26 由 `Test 3D Project` 改名；项目自带的 git 远端 `Maimai-l/Test-3D-Project` 和 Unity Cloud 上的项目名没有改）。MCP 服务是 mcp-for-unity 3.4.11（地址来自 `UNITY_MCP_URL`），有 48 个工具，其中包括 `blender_bridge`。
- exec 服务（地址来自 `EXEC_MCP_URL`）从 2026-10-27 起是 Claude Code 2.1.311 作为 MCP 服务（服务名 `claude/tengu`），服务端提供 20 个工具，其中 13 个（Agent、WebFetch 等）在本仓库的 `.claude/settings.json` 里禁用，会话里能用的是 Bash、Read、Write、Edit、Glob、Grep、TaskStop 这 7 个。以 blender 账号运行，工作目录 `C:\Users\blender\ExecMCP`。Bash 是 Git Bash（MINGW64），路径写成 `/c/Users/...`；blender 账号只有 Windows PowerShell 5.1（没有 pwsh），用 `powershell.exe -NoProfile -Command` 调用。Node 是 `D:\Program Files\node.EXE`，npm 是 `D:\Program Files\npm.cmd`。
- 之前的 exec 服务 mcp-server-commands 0.8.2-bmcp.1 仍装在 `C:\Program Files\BlenderMCP\exec-mcp`，修复源码在 `Maimai-l/mcp-server-commands` 的 `bmcp-fixes` 分支（提交 `c5f936f`）。
- blender 账号对 `C:\Program Files\BlenderMCP\` 没有写权限，更新这里的服务要发安装包，由用户在主账号的管理员 PowerShell 7 里运行，再在控制台重启对应服务。
- Blender 和 Claude 的沙箱不共享文件系统。MCP 地址来自 `.mcp.json` 里的 `BLENDER_MCP_URL`，断线重连不会清掉场景。

## 经验
- 改完 `location`、`rotation` 等属性后要先 `view_layer.update()`，`matrix_world` 才会更新。
- 对齐或贴合物体时，用求值后的网格（含修改器）来量尺寸，不要用原始网格。
- 判断颜色看渲染结果，`material` 模式的预览光会把颜色冲淡。
- 最终展示图用 `render.render()` 加 `look(image="Render Result")`，视口里的 `rendered` 截图有噪点。
- 在 Windows 上判断能否写某个目录，要实际创建一个文件再删掉：Node 的 `fs.accessSync(p, W_OK)` 只看只读属性、不看权限，对没有写权限的目录也会通过。
- 不要靠赋值来试探偏好设置（`bpy.context.preferences`）：赋值会真的改掉设置，而且 Blender 退出时会自动保存偏好。只读取不改；非要改，先记下原值，用完改回去。
- Unity 编辑器在后台时 Play Mode 不走帧（开了 Run In Background 也一样），`EditorApplication.delayCall` 也不触发，但 `EditorApplication.update` 照常运行。无人值守跑 Play Mode 时，在 `update` 里先设 `EditorApplication.isPaused = true`，再调 `EditorApplication.Step()` 推帧；重开项目（`EditorApplication.OpenProject`）这类延后操作也挂到 `update` 上执行。
- 用 `Step()` 推帧时，`Time.timeScale` 为 0 的帧里 `unscaledDeltaTime` 也是 0，协程可能停在 `yield return null` 不再恢复，所以暂停期间要执行的逻辑放在 `Update` 里。这时 Unity 打印的 “JobTempAlloc” 内部提示可以忽略。
- 域重载（进出 Play Mode、重新编译、重开项目）后，mcp-for-unity 的端口可能在 6400 和 6401 之间切换，之后的调用报 “upstream request failed”，但 `mcpforunity://instances` 里实例仍显示在运行。用 `set_active_instance` 传当前端口号（如 `"6400"`）重新指定即可恢复。
- 电脑锁屏时（Windows 没有前台窗口），构建出的游戏窗口不往屏幕输出画面：`ScreenCapture` 截到的是旧画面（启动画面的底色 RGB 35,31,32），帧率计数会到上千，没有意义。截图要把摄像机渲染到 RenderTexture 再读回；测性能要让摄像机在正常游戏循环里渲染到 RenderTexture，几十帧后用 `ReadPixels` 等显卡做完再计时。不要循环调用 `Camera.Render()` 来测，在 URP 下每次约 100 毫秒，反映不了真实帧耗时。
- TextMeshPro 富文本 `<font="字体名" material="材质名">` 里的材质，按名字不区分大小写的哈希（`TMP_TextUtilities.GetHashCode`）查找。自己注册材质要用 `MaterialReferenceManager.AddFontMaterial(TMP_TextUtilities.GetHashCode(mat.name), mat)`；用 `GetSimpleHashCode` 会查不到，整段标签被原样显示成文字。同一个哈希重复添加会抛异常，先用 `TryGetMaterial` 判断。截图不一定拍到每种带标签的文字，自动测试里可以扫描 `GetParsedText()`，查有没有残留的 `<标签>`。
- TextMeshPro 在未激活的层级里量不出文字尺寸。要按文字高度排版的界面，先 `SetActive(true)`，再 `ForceMeshUpdate()`，然后读 `preferredHeight`。

## Anime short "Awakening" (2026-11): rendering a 2D-anime-looking film from Blender
- Project: `awakening/` (README there). The scene is built entirely by `awakening/scripts/build_all.py` from `scripts/lib/aw_*.py`; painted textures come from `awakening/paint/make_all.py` (numpy gouache kit), sound from `awakening/audio/make_audio.py`.
- Cel look in EEVEE: Shader-to-RGB on a white diffuse → hard thresholds → bands; the shadow colour is `base × cool multiplier` so textured bases keep working. Bake orientation-dependent weathering (moss on upward faces) into a colour attribute while the character is posed, so it does not move with the pose.
- Freestyle treats alpha-textured cards as opaque occluders (lines behind a transparent part of a card vanish). Render ink on its own view layer that excludes the cards (`as_render_pass`), and alpha-over the pass through a dilated cryptomatte of the actors. EEVEE has no object-index pass; the cryptomatte **asset** pass keys by the top parent, so one name (`J_root`) covers a whole parented rig. Set `line_thickness_mode = 'RELATIVE'` so test renders at 50 % keep the final line weight.
- Blender 5.2 compositor: everything is a socket (`node.inputs['Type'].default_value = 'BLOOM'`, Blur `Size` is a vector, Color Balance has duplicate socket names; pick by `.type`). `CompositorNodeMath` / `MixRGB` do not exist: use `ShaderNodeMath` / `ShaderNodeMix` inside the compositor tree. `scene.compositing_node_group` holds the tree.
- Encoding with the sequencer under `--factory-startup` applies AgX: set `view_transform = 'Standard'`, and set `image_settings.media_type = 'VIDEO'` before `file_format = 'FFMPEG'`. Blender 5 uses `sequence_editor.strips`.
- Particle emitter meshes render as grey surfaces even with `show_instancer_for_render = False`, `visible_camera = False` and a transparent material: make emitters vertex-only meshes (`emit_from = 'VERT'`). Bake point caches to disk before background renders that start mid-timeline. Objects with keyframed `hide_render` ignore a manual `hide_render = True` once the frame changes: move them away or exclude their collection when debugging.
- Scoped force fields: `settings.effector_weights.collection` keeps a wind from hitting every particle system.
- Background renders: `blender -b file.blend -P render_job.py -- start end outdir scale samples`; marker-bound cameras switch automatically; this scene took 2.4 s/frame at 1080p with two view layers. Two processes in parallel share the GPU well. Encode with a second headless Blender (`encode_job.py`).
- Uploading to the PC: `tools/upload_mcp.py` (base64 chunks through `execute_blender_code`) runs at ~1 MB/s; the exec `Write` route is ~20 kB/s. Contact sheets of many renders are cheaper to make inside Blender (`aw_sheet.py`, numpy on `image.pixels`) than to fetch each image.

## Reference-replication projects (lessons from Xingyuan, 2026-10)
- Before a project that rebuilds something from photos, drawings or plans, read `xingyuan/docs/lessons.md`. It complements the `blender-reference-replication` skill, which assumes clean front, side, back and top views:
  - For photos, aerials and site plans, calibrate the camera from known points first (`xingyuan/tools/calib.py`, `aer3d.py`).
  - Treat the photos as colour-graded and possibly stretched by the page layout.
- Reuse the Xingyuan code by copying it into the new project folder, rather than rewriting it.
  - `xingyuan/tools/`:
    - MCP clients for Blender (`bmcp.py`) and exec (`execc.py`);
    - push / run / render / fetch loops (`xy`, `rl`, `rh`, `rvs`, `fetch.py`);
    - reference/render side-by-sides and camera fitting.
    They derive the PC folder from the project folder name, `D:\Blender\Projects\<project>` (`xyp.py`; the older projects' `C:\Users\blender\Documents\<project>` paths are junctions to it); see `xingyuan/tools/README.md`.
  - `xingyuan/scripts/lib/` (Chinese timber architecture):
    - roofs: curved roofs with instanced tiles, ridges, bargeboards and finials (`xy_roof.py`);
    - parts: brackets, columns, bases, balusters and lanterns as instanced parts (`xy_parts.py`);
    - frames: framing, railings, wall bays, corridor and pavilion roofs (`xy_frame.py`, `xy_struct.py`);
    - halls with doors and windows (`xy_hall.py`); platforms and paving (`xy_site.py`); plaques, couplets and steles (`xy_props.py`);
    - materials (`xy_mats.py`); sky, sun and render settings (`xy_light.py`); viewport proxies (`xy_proxy.py`); trees and plants (`xy_plants.py`).
    Geometry checks are `xingyuan/scripts/check_*.py`. When copying, change `ROOT` in `xy_core.py` and `LIB` at the top of the run scripts to the new project.
- Before running anything that changes the Blender scene, print `bpy.data.filepath` and the object count. Blender may have been restarted or switched to another project. Give every project its own .blend under `D:\Blender\Projects\<project>\`.
- Derive random seeds with `zlib.crc32(name.encode())`; Python's `hash()` changes between Blender sessions.
- MCP servers listed in `.mcp.json` that a session did not load as tools can still be called directly over HTTP, with the same handshake as `xingyuan/tools/bmcp.py`.
  - Send a `User-Agent` header, or the proxy answers 403.
  - For exec, use only the 7 tools allowed in `.claude/settings.json`; `xingyuan/tools/execc.py` enforces that.
- Files on the PC:
  - In the exec Bash, Windows' `tar.exe` (`/c/Windows/System32/tar.exe`) lists and extracts .rar and .zip. Git Bash's own `tar` cannot read RAR.
  - Bring files into the sandbox with `xingyuan/tools/fetch.py`: Blender's Python reads them and sends them in 2 MB pieces, so videos and archives work too.
  - Keep every Blender MCP reply small. On 2026-11-01 one 11 MB reply (an 8 MB piece) made the Blender MCP server exit; the cloud endpoint then answered 502 until the service was restarted from the console.
  - When the Blender endpoint is down, `qiting/tools/pcx.py` reaches Blender through exec alone:
    - `pc/brelay.py` sends code to the add-on socket `127.0.0.1:9876`;
    - `pc/pack.py` wraps files into PNG pieces of at most 500 kB, which exec's Read returns unchanged. Bash output stops at 30,000 characters and text Read at 25,000 tokens.
- Calibrating photo cameras (Qiting, 2026-11):
  - Silhouette tips of circles fix a round building's distance and height, but not its azimuth. Add points that break the symmetry, such as columns or a stair.
  - Check the solved focal length against the EXIF value: in Qiting, W02 agreed to 1 %.
  - After solving, compare Blender's projection of a few points (`world_to_camera_view`) with the solver's. Qiting round 2 found two bugs this way: the roll sign in `xy_light.camera` (now fixed in both copies), and the vertical stretch `ky`, which needs `pixel_aspect_x = ky`.
  - Near points leave the focal length loose, and that moves everything far away. For far scenes, add plan points and check that the horizon falls between the skyline's tops and bases (`xingyuan/docs/lessons.md`, section 9).
- Blender jobs longer than about 100 s (full-scene renders, geometry checks) lose their MCP reply in the tunnel. Run them from `bpy.app.timers` and poll a result file through exec (`qiting/tools/rdefer.py`, `cmpview.py`, `heroes_run.py`).
- Sandbox tooling:
  - installed: numpy, OpenCV, SciPy, Pillow, `ffmpeg` and `pdftoppm`;
  - `ezdxf` installs with pip, but reads DXF only;
  - nothing here reads DWG, so ask for DXF or PDF exports of CAD drawings.
