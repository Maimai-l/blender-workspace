# Blender 工作区说明

## 约定
- 仓库改动默认直接提交并推送到 `main` 分支（用户已明确授权），不另开分支，也不建 PR。
- 工作文件存到 `C:\Users\blender\Documents\`，保存时写绝对路径。

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
