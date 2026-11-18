# PC 与 MCP 运维手册

这份手册写给负责维护的会话：电脑和三条 MCP 服务的现状、检查方法、收尾清理和排障。
建模和渲染的经验在根目录的 `CLAUDE.md` 和各项目的 README 里，这里不重复。
最后核对：2026-11-12。
给用户看的《Windows 主机维护手册》（https://claude.ai/artifact/S5uXRXaX1HmHiDhErUSg4Y）也由我们维护：这里的服务、路径、端口有变动时，同步改手册对应的标签页。

## 1. 管线

```
云端会话 ──(代理注入凭证)──▶ Cloudflare 隧道（cloudflared，主账号运行，protocol http2，约 100 秒断开回复）
  bmcp.maimaiqiu.work → 127.0.0.1:8080 mcp-proxy → blender-mcp.exe (stdio) → Blender 插件 127.0.0.1:9876 → blender.exe
  umcp.maimaiqiu.work → 127.0.0.1:8082 mcp-proxy → mcp-for-unity.exe (stdio) → Unity 编辑器桥接 6400/6401
  xmcp.maimaiqiu.work → 127.0.0.1:8084 mcp-proxy --requestTimeout 90000 → claude.exe mcp serve (2.1.311)
  wmcp.maimaiqiu.work → 127.0.0.1:8088 mcp-proxy --requestTimeout 90000 → Playwright MCP 0.0.85 → 无界面 Edge → Clash 浏览器专用入口 127.0.0.1:7899（proxy: GLOBAL，不受 Clash 全局模式影响）
```

| 组件 | 位置 | 运行账号 | 说明 |
| --- | --- | --- | --- |
| 控制台 `panel.py` | `C:\Program Files\BlenderMCP\panel\`，`127.0.0.1:8765` | 主账号 | 开关隧道、外网探测（不带密钥时返回 401 算正常）；其余转给 agent |
| agent `agent.py` | 同上，`127.0.0.1:8766` | blender | 开机由“启动”文件夹里的 `MCP 代理.lnk` 拉起。负责启停三条 mcp-proxy、打开 Blender/Unity、切换联网方式（直连或经 Clash 7897） |
| 隧道配置 | 主账号 `%LOCALAPPDATA%\BlenderMCP\cloudflared.yml`（每次开启时重新生成） | 主账号 | 隧道 ID 在 `panel.py` 里 |
| 密钥 | `C:\Users\blender\{blender,unity,exec}-mcp-secret.txt` | | `KEY=`、`PATH=` 两行，mcp-proxy 用作 `--apiKey` 和 `--streamEndpoint` |
| 服务日志 | `C:\Users\blender\{BlenderMCP,UnityMCP,ExecMCP}-run\proxy.log` | | 服务每次启动时清空重写 |
| exec 工作目录 | `C:\Users\blender\ExecMCP` | | Bash 的起始目录，两次会话之间应为空 |
| agent 令牌 | `C:\ProgramData\BlenderMCP\agent.token` | | blender 账号可读，所以经 exec 可以直接调用 agent |

- exec 启动时会去掉 `CLAUDE*`、`ANTHROPIC*` 和代理变量，所以 exec 里的命令上不了外网。
- blender 账号对 `C:\Program Files\BlenderMCP\` 没有写权限。要改 `agent.py`、`panel.py` 或换服务版本，就做成安装包，请用户在主账号的管理员 PowerShell 7 里运行。
- 同一台电脑上的其他服务：`0.0.0.0:17860` 是用户自己的 FireRedASR2S 转写台，开着局域网共享，属正常；`7897` 是 Clash Verge；Tailscale 也在运行。

- 2026-11-18 起控制台是 v2（`ops/console/`：连接状态页、Clash 联动、浏览器线路），装法和测试见那里的 README。临时授权（tmcp → 8086）还没部署。

## 2. 健康检查

从沙箱执行，几秒钟就能完成：

```bash
for h in bmcp umcp xmcp; do curl -s -o /dev/null -w "$h %{http_code}\n" -X POST -H 'Content-Type: application/json' -H 'User-Agent: ops' --data '{}' https://$h.maimaiqiu.work/mcp; done
```

不带密钥时返回 401 就是正常的。经代理带上凭证时，`initialize` 应返回 200。

在 PC 上查 agent 的状态（经 exec）：

```bash
curl -s -H "Host: 127.0.0.1:8766" -H "X-Agent-Token: $(cat /c/ProgramData/BlenderMCP/agent.token)" http://127.0.0.1:8766/status
```

同一个接口还能做这些操作，都用 POST：

- `/mcp/<blender|unity|exec>/start` 和 `/stop`：启停对应服务。不要停 exec，否则自己的通道也会断。
- `/app/blender/start`、`/app/unity/start`：打开 Blender 或 Unity。
- `/net/direct`：切换为直连。

在 Blender 里先读当前打开的文件和物体数，不要直接改场景：`print(bpy.data.filepath, len(bpy.data.objects))`。

## 3. 收尾清理（每次工作结束都做）

```bash
python3 -I ops/tidy.py scan                # 只列出，不删除
python3 -I ops/tidy.py clean               # 删除工具副产物，跳过 60 分钟内的新文件
python3 -I ops/tidy.py clean --min-age 0   # 会话结束、确认没有后台任务时用
```

`ops/pc_tidy.sh` 经 exec 在 Git Bash 里运行。只要还有后台任务在跑（`blender -b`、`pc_worker`、`gouache.render`、`brelay.py`、`pack.py`、ffmpeg），它就只列出、不删除。
它自动删除的只有工具副产物：

| 规则 | 来源 |
| --- | --- |
| `<项目>\tmp\*` | `pcx.py`、`putbig.py` 的中转文件和 `pk_*` 分片目录 |
| `<项目>\renders\job_*.txt`、`*.done`、`*.tmp` | `rdefer.py`、`heroes_run.py`、`cmpview.py` 的输出和完成标记 |
| `*.tmp.png` | 被中断的渲染进程留下的半张帧 |
| 项目根目录下的 `enc_*`、`list_v*.txt`、`pipeline_*`、`bg_S*.log`、`*code.tgz`、`pip*.log`、`build.log` | Awakening II 渲染农场（`pc.py`）的日志和上传包 |
| 只剩 `_done` 的 `frames_*` 目录 | 渲染农场的辅助任务目录 |
| `Temp\*.tmp`，7 天以上 | 临时文件；被程序占用的会保留 |

每一项删除都追加到 `D:\Blender\Projects\_迁移日志\cleanup_<日期>.log`（这个目录也存着 2026-11-11 迁移和之前几次清理的记录）。

脚本最后一节列出需要人工判断的内容：

- exec 工作目录里的东西；
- `Documents` 里除 `vocabulary.db` 和目录联接以外的东西；
- 家目录、桌面、下载里多出来的东西；
- 后台进程；
- 服务日志的大小；
- 磁盘剩余空间。

人工判断时这样处理：

- 有用的就移到对应项目里（QA 截图放项目文件夹，可复用的脚本收进仓库）；
- 确认无用的就删掉，并在当天的清理日志里写一行；
- 项目文件（`.blend`、`.blend1`、交付物、最终帧）不在自动清理范围内。旧版本的渲染输出要先确认不用，再删。

## 4. 排障对照

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 三个域名都返回 530 | 隧道没开（cloudflared 在主账号） | 只能在控制台里开，blender 账号停不了也启动不了它 |
| 某个域名返回 502 | 该服务的 mcp-proxy 没在运行 | 经 exec 调用 agent 的 `/mcp/<名字>/start`；Blender 端点的备用路径是 `qiting/tools/pcx.py` |
| Unity 返回 502 | 编辑器没开，或 Unity MCP 服务没启动 | 先确认编辑器真的开着（见第 5 节的问题 1），再调用 `/mcp/unity/start` |
| 调用约 100 秒后没有回复 | Cloudflare 断开了回复 | 长任务放到 Blender 计时器里跑，再轮询结果文件（`rdefer.py`） |
| Unity 报 “upstream request failed” | 域重载后桥接端口在 6400 和 6401 之间切换了 | `set_active_instance` 指定当前端口 |
| exec 的 Write 拒绝写入 | 目标文件已存在，且这次没有先读过 | 先 Read，或者写到新文件再 `mv`（`pcx.put_text`） |
| Blender 打开的是空场景 | Blender 重启过 | 先打开对应项目的 `.blend`，再执行任何改动 |
| Blender 崩溃或被关掉，9876 端口没有监听 | Blender 没在运行 | 经 exec 调用 agent 的 `/app/blender/start`，或直接运行 `blender.exe`（都在会话 2 里启动）。插件（模块名 `addon`）随 Blender 启动自动开始监听，打开文件后由 `load_post` 回调重新开启，不需要有人点 Connect |

## 5. 已知问题（2026-11-12）

1. **agent 把 Unity Hub 的 `unity.exe serve` 当成了编辑器。**
   - 原因：`process_running("Unity.exe")` 用的是 `tasklist /FI "IMAGENAME eq Unity.exe"`，进程名不区分大小写，会匹配到 Hub 的 `resources\unity.exe`。控制台的 `pids("Unity.exe")` 也是同样的写法。
   - 后果：只要 Unity Hub 开着，状态里就会显示 Unity 正在运行，“打开 Unity” 只会回答 “Unity 已经开着”，实际什么都不做。
   - 临时办法：经 exec 直接启动编辑器 `"/d/Program Files/Editor/Unity.exe" -projectPath "D:/Unity/Projects/<工程>"`，等桥接端口开始监听后，再调用 `/mcp/unity/start`。
   - 根治：按完整路径判断进程（不在 `D:\Program Files\Unity Hub\` 下的才算编辑器），需要发安装包。
2. **Blender 的 `proxy.log` 已有 215 MB。** 每次调用的完整代码都会写进去，只在服务重启时清空，大约每天增长 45 MB。在没有其他会话使用 Blender 时，经 agent 调用 `stop` 再 `start` 就能清空。根治办法是让 agent 按大小轮转日志，需要发安装包。
3. `Temp\93e22641-…tmp`（48 MB，2026-10-26）一直被某个进程占用，清理时会跳过。
4. `C:\Program Files\BlenderMCP\` 里有两份 `panel.bak-*` 和三份 `panel\backup-before-*`，是历次升级留下的备份。blender 账号删不了，下次发安装包时一起清掉。

## 6. MAA 与雷电模拟器（迁移到 blender 账号）

> 托管流程的总览和当前状态见 `ops/maa/README.md`，改流程时先更新那份。本节保留迁移过程和排查细节。

### maa-cli（托管用，2026-11-15 起）

| 内容 | 位置 |
| --- | --- |
| `maa.exe`（maa-cli 0.7.8，已核对 SHA256） | `D:\Projects\MAA\maa.exe`，和复制版界面 MAA 放在一起，共用其中的 MaaCore v6.22 和 `resource\` |
| 配置（仓库里的源文件在 `ops/maa/config/`） | `D:\Projects\maa-cli\config\`：`profiles\default.toml`（连接设置）、`tasks\daily.toml`（照搬界面版的日常队列）、`tasks\wake.toml`（只开游戏，测试用） |
| 启动脚本（源文件 `ops/maa/run.ps1`） | `D:\Projects\maa-cli\run.ps1` |
| 日志 | `D:\Projects\maa-cli\logs\runs.log`（每次运行一行）、`<时间>-<任务>.out`（任务汇总）、`.err`、`.log`；MaaCore 的详细日志在 `state\debug\asst.log` |

- 数据导出（2026-11-15 起）：`daily` 每次都在最后加跑仓库识别和干员识别，`inventory` 任务只做识别（不消耗任何东西，约 130 秒）。
  - maa-cli 只把识别结果写进 MaaCore 的 `state\debug\asst.log`。`run.ps1` 跑完后调用 `export_data.py` 取出结果，写到 `D:\Projects\maa-cli\export\depot_<时间>.json`、`operbox_<时间>.json`，并更新 `*_latest.json`。
  - 格式和界面版的 `data\DepotData.json`、`OperBoxData.json` 相同。首次运行的结果和界面版 12:14 那份逐项一致。
- 运行：`powershell -NoProfile -ExecutionPolicy Bypass -File D:\Projects\maa-cli\run.ps1 -Task daily`，`-KeepEmulator` 跑完不关模拟器。
- 脚本会依次做这些事：开模拟器 → 等安卓开机完成 → 运行 `maa run <任务> --batch` → 关模拟器 → 在 `runs.log` 里记一行。
- 以下情况脚本拒绝运行，退出码 91–94：
  - 已有一次 `run.ps1` 在运行；
  - 任一账号开着 MAA 界面版（`Get-Process` 能看到所有会话的进程）；
  - 模拟器开在别的会话里；
  - 安卓 180 秒内没开机。
- 经 exec 启动时用 `Start-Process` 让它脱离 exec 后台运行，再轮询 `runs.log`。exec 内置工具 30 秒就断，不能等它跑完。
- 临时命令要设置 `MAA_CONFIG_DIR`、`MAA_STATE_DIR`、`MAA_CACHE_DIR`、`MAA_DATA_DIR`，值和 `run.ps1` 里的一致。例如 `maa fight 1-7`、`maa run daily --dry-run`；`maa list` 列出已有任务。
- 活动关数据由 maa-cli 自己从 `api.maa.plus` 热更新，电脑能直连。`maa update`、`maa install`、`maa self update` 要从 GitHub 下载，电脑直连不上 GitHub，不要用。
- 更新 MaaCore 和基础资源的办法：偶尔用 `--skip-startup-auto-run` 启动一次复制版界面 MAA，等它自动更新完再关掉。它经 blender 账号的系统代理更新，会走 MAA 自己的更新源。更新后要确认 `maa.exe` 还在。
- 截图走 adb，实测平均 155 ms；界面版用的雷电专用截图接口是 30 ms。慢一些，但不影响使用。
- 实测：`wake` 两次，54–55 秒到主界面，退出码 0，模拟器已关。`daily` 在 2026-11-15 19:35 完整跑过一次：剿灭开关、开游戏、EX/S 队列、基建、理智、公招、信用、奖励、识别、森空岛同步都正常，用时 821 秒，退出码 0。
- 计划任务（blender 账号，“只在用户登录时运行”，2026-11-15 经用户同意创建）：`MAA-cli daily 0000`、`MAA-cli daily 0800`、`MAA-cli daily 1200`，每个都运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\Projects\maa-cli\run.ps1 -Task daily`。
  - 用一个临时计划任务跑过 `wake`：从计划任务程序启动、会话断开时都正常（53 秒，退出码 0），测完已删除这个临时任务。
  - 第一次真正的 `daily` 是 2026-11-16 0:00，之后要看 `runs.log` 和 `.out` 的汇总确认。
  - 电脑重启后要有人登录一次 blender 账号，否则这些任务和 MCP 服务一样都不会运行。

### 森空岛同步（2026-11-15 起，用户明确同意 exec 为此联网）

- 位置：`D:\Projects\skland\`（`npm install skland-kit@0.3.5 qrcode@1.5.4`，脚本源文件在 `arknights/skland/`）。
  - 凭证在 blender 账号自己的 `C:\Users\blender\.skland\store`：森空岛的 cred/token，以及鹰角登录凭证 `hg:oauth`。凭证只留在电脑上，不进仓库、不传到云端会话。
- `node login.mjs`：生成 `D:\Projects\skland\qr.png`，用户用森空岛 App 扫码确认，3 分钟内有效；进度写在 `login.status`。
  - 二维码只在电脑上打开，不发到对话里。
  - 2026-11-15 已登录，角色“吉尔伽美什”。
- `node sync.mjs`：导出到 `D:\Projects\maa-cli\export\`。
  - `skland_info_*.json`：干员的技能等级、专精、模组，基建各设施（等级、驻扎干员、心情、无人机），以及肉鸽、剿灭、日常等；
  - `skland_cultivate_*.json`：库存，109 种物品，比 MAA 仓库识别的 82 种更全。
  - 森空岛凭证失效时，会用 `hg:oauth` 重新换取；这一步也失败就退出码 3，需要重新扫码。
  - 库存接口不接受 skland-kit 的默认签名，会返回 401，所以 `sync.mjs` 按 RIIC-Web 的 `mowerSklandSignedHeaders` 单独签名。
- `run.ps1` 每次跑完 MAA 后都会运行一次 `sync.mjs`，结果记进 `runs.log`。
- 交叉核对（2026-11-15）：MAA 的干员识别比森空岛少 2 名，是阿米娅的术师和医疗形态，MAA 不统计；其余 416 名的精英化和等级两边完全一致。
- 基建现状（森空岛）：控制中枢 5 级、发电站 3 个、贸易站 2 个、制造站 4 个（都是 3 级），即 243 布局；宿舍 4 个。

### 基建改建 243 → 333（2026-11-15，用户同意）
- B102 由中级作战记录改产赤金。B303（原经验站）逐级降级拆除，返还高级加固建材 5、进阶 3、基础 1，原址新建贸易站，现为 2 级。现在是 3 个贸易站、2 个赤金站、1 个经验站。
- B303 升 3 级需要 120 架无人机和 5 个高级加固建材（拆除时已返还）。由用户在游戏里操作，大约 23:00 后无人机就够了。
- 改建期间，`daily.toml` 和 `infrast.toml` 的无人机设为 `_NotUse`。每次运行同步森空岛后，`after_rebuild.py` 会检查：3 个贸易站都到 3 级，就自动改回 `"Money"`。
- 新增任务：`infrast`（只做基建换班）、`chips`（芯片本，倍率固定 1，按目标掉落数停下）。
- 界面操作工具 `arknights/tools/ui.py`：截图缩到 960×540 传回，坐标按 5/3 换算后点击。适合一次性的界面操作；游戏是 Unity 绘制，没有可读的界面树。

### 剿灭开关（2026-11-15 起）
- `daily` 一天跑三次，每次都打剿灭的话，周上限（1800 合成玉）满了以后每天白耗约 75 理智。
- `annihilation_gate.py`（源文件 `ops/maa/`）在每次 `daily` 前运行。它读最近一次森空岛导出：本周已满，就把 `daily.toml` 里 `# >>> annihilation` 到 `# <<< annihilation` 之间的任务注释掉；没满就恢复。
- 每周一 4:00 重置。重置前的导出按“未满”处理，所以周一 8:00 那次会打。

### 作业（prts.plus）与活动关自动导航（2026-11-15 起）
- 作业站接口 `https://prts.maa.plus/copilot/query?level_keyword=<关卡 id，如 act55side_ex03>&order_by=hot`，电脑能直连，云端沙箱连不上。
- `copilot.ps1`（源文件 `ops/maa/`）：`-Uri prts://<id>[,prts://<id>…] [-Raid normal|raid|both] [-KeepEmulator]`。
  - 只给一个作业时，要先停在关卡页（能看到“开始行动”）。
  - maa-cli 给多个作业时会自动导航，但**只认主线关卡**。活动关会在主界面无限滑动找关卡，实测要手动结束 `maa.exe`。
- `ev_run.py`（源文件 `arknights/tools/`，用 agent-ocr 的 venv 运行）解决活动关导航：
  - 先截图做 OCR，确认画面后再点认出来的文字：主界面横幅“时间啊”→ 区域名 → `TL-EX-n`。
  - 在关卡页读出当前理智和消耗，够才运行 `maa copilot prts://<id> --formation --raid <模式>`，不够就停下。
  - 认不出预期的画面就报错、回主界面，不盲点。早期版本盲点屏幕中央，误进过时装商店，没有购买。
  - 主界面的判断用“仓库”加“理智/”：快捷菜单里也有“终端”“采购中心”。
  - 队列 `QUEUE` 写在脚本里；完成记录在 `state\ev_done.json`，失败计数在 `state\ev_fail.json`，同一项失败 2 次就跳过。
  - `run.ps1` 在 `daily` 里先运行 `maa run wake` 打开游戏，再运行 `ev_run.py`，最后关掉 OCR 服务，释放显存。
- 突袭由 MaaCore 自己切换（`ChangeToRaidDifficulty`，重复执行也没问题），脚本不用点“突袭”。
- 2026-11-16 加固（起因见下面的内存问题）：
  - **漏怪即退**：作业运行时每 3 秒截图，只识别顶栏两小块：敌人计数 `k/n` 和它右边的生命值。认出敌人计数才相信读到的生命值。连续两次低于开局值，就结束 MAA 并放弃这局。规则：放弃会全额退还理智；二星通关不退理智，也拿不到三星首通奖励。
  - **放弃流程**（实测）：齿轮约在 (100, 72) → 确认框“放弃行动将会恢复N理智（全部返还）/ 是否放弃行动？”，点靠下的“放弃行动” → “任务失败 / 点击画面以继续” → 结算画面“理智返还 N”。MAA 界园的放弃流程用的是集成战略的确认框，位置不同。
  - 失败后同一关当场重打一次，两次运行都失败才计 1 次失败。
  - 每次打作业前检查剩余可分配内存（commit），不足 6 GB 这次就先不打。
  - OCR 服务改用 CPU（`AGENT_OCR_DEVICE=cpu`），每次检查约 1.2 秒。GPU 版仅加载 CUDA 就要占 3.6 GB。`ev_run.py` 退出时一定关掉 OCR 服务。

### 内存不足导致的作业中断（2026-11-15 夜到 11-16）
- 系统日志 2004（Resource-Exhaustion-Detector）记了多次虚拟内存不足：
  - Blender 做效果图时占到 56 GB，渲染完仍占着 38 GB；
  - 模拟器进程占 10–16 GB（设置是 6 GB 内存，进程开得越久占得越多）；
  - 总上限约 49.7 GB（32 GB 内存加约 18 GB 虚拟内存）。
- 后果：
  - MaaCore 截图拿到空图，报 “image is empty / Unhandled out of memory”，作业中断，战斗停在暂停画面；
  - 显卡驱动超时（LiveKernelEvent 141）；
  - adb 崩溃，模拟器离线；
  - 日常的 MAA 卡在暂停画面里等了 3 个多小时。
- 用户在电脑上做大型渲染后，重启 Blender 能释放内存。日常会检查内存，不够就跳过作业。

### agent-ocr（屏幕文字识别，2026-11-15 安装）
- 位置：`D:\Projects\agent-ocr\`，包括 `ocr.py`、`ocr_server.py`、`README.md`（用户提供）、`install.ps1`、`start_ocr.ps1`（这两个的副本在 `ops/pc/agent_ocr_*.ps1`）。
  - venv 是 `.venv`（约 1.6 GB），用 Blender 自带的 Python 3.13 创建。电脑上没有独立的 Python；Anaconda 在 `D:\ProgramData`，它的 8 个环境里都没有 paddle 或 onnxruntime。
  - 用户主账号的 `.paddlex` 里有 4 月下载的 PP-OCRv5 模型，blender 账号没有读取权限。
- 包：paddleocr 3.7.0、paddlex 3.7.2、onnxruntime-gpu 1.32.0，以及 pip 装的 CUDA 13.5 和 cuDNN 9.28 运行库，不装 PaddlePaddle。
  - 下载走阿里云 PyPI 镜像，清华作备用，约 11 MB/s。
  - 模型从 ModelScope 下载（`PADDLE_PDX_MODEL_SOURCE=modelscope`），缓存在 `C:\Users\blender\.paddlex`。
- 服务端口是 **8767**：8765 是面板，8766 是 agent。调用时设置 `AGENT_OCR_PORT=8767`，或者传 `--url http://127.0.0.1:8767`。
- 后端是 onnxruntime / gpu:0，PP-OCRv6 medium。预热一次约 29 毫秒；一张 1600×900 游戏截图约 250 毫秒。
- 模拟器在断开的会话里，`mss` 截屏截不到。要用 `adb exec-out screencap -p` 存成文件，再 `ocr.py --image`。

### 2026-11-15 状态（界面版）

- 复制版放在 `D:\Projects\MAA`（v6.22，由 `D:\Program Files\MAA-v6.18.0-win-x64` 复制而来，blender 账号可写）。
  - 目前**待命**：定时和定时唤醒都关了，blender 账号里也没有它的唤醒任务。
  - 主账号的原始配置（定时 0:00、8:00、12:00 已开启）存在 `config\gui.new.json.orig`。
- 用户传给电脑的文件放在 `D:\Downloads`（不是用户目录下的 Downloads）。
- 2026-11-15 16:13 用户关掉了主账号 MAA 的定时和定时唤醒，`MaaWakeup_E5C60EF7` 已删除（主账号 MAA 日志里有记录，配置也核对过）。下面这条是之前的情况。
- 主账号的 MAA 已由用户关闭，但它的唤醒任务 `MaaWakeup_E5C60EF7` 还在主账号的计划任务里：每个定时前 5 分钟（23:55、7:55、11:55）会重新拉起主账号的 MAA，到点照常运行。
  - blender 账号看不到、也改不了这个任务。
  - 用户在主账号里关掉 MAA 的“定时唤醒”和定时（或者删掉这个任务）之前，blender 这边的定时不能开，否则 0:00 两个 MAA 会抢同一个模拟器。
- 完成切换：
  1. 确认主账号的唤醒任务已经去掉；
  2. 把 `.orig` 复制回 `gui.new.json` 和 `gui.new.json.bak`；
  3. 用 `--skip-startup-auto-run` 启动 MAA，它会自己重新注册唤醒任务；
  4. 请用户在 blender 的 MAA 里重新填一次 GitHub Token（见下面“试运行的结果”第 5 条）。

### 试运行的结果（2026-11-15）

1. 用 `ldconsole.exe launch --index 0` 在会话 2 里启动雷电：虚拟机注册正常，安卓 2 秒内开机完成。会话已断开，但 adb 截图和 MAA 的雷电截图接口（30 ms）都正常，不是黑屏。
2. 明日方舟仍是登录状态。只开“开始唤醒”的测试配置，55 秒就进了主界面。
3. **MAA 普通启动会先倒计时 10 秒，然后自动跑一轮**，日志里显示为 `Timer wait time: 10`，和 `RunDirectly` 设置无关。只要不是想马上跑任务，就要带 `--skip-startup-auto-run` 启动。经 exec 启动用 `powershell Start-Process`，这样进程能脱离 exec 独立运行。
4. 改 `gui.new.json` 时，值必须是 MAA 认识的。例如 `PostActions` 不能为空，要写 `"None"`、`"ExitEmulator"` 这类名字；任何一个字段解析失败，MAA 就整份改用 `gui.new.json.bak`。所以测试配置要同时写进 `.json` 和 `.json.bak`；只在 MAA 关闭时改，因为它退出时会把内存里的配置写回文件。
5. MAA 用 Windows 的按账号加密保存密钥，复制到 blender 账号后解不开，日志会报“加解密失败”“Token 无效”。目前受影响的只有 GitHub Token：检查更新会改用 MAA 自己的源，功能不受影响。
6. adb 服务（5037）仍由主账号会话里的 adb 持有；两边用的都是 `D:\leidian\LDPlayer9\adb.exe`，版本相同，可以共用。不要换别的 adb，不同版本的客户端会把服务端重启掉。
7. 模拟器控制命令：
   - `ldconsole.exe list2` 列出实例；
   - `isrunning --index 0` 查看是否在运行；
   - `quit --index 0` 关闭实例；
   - `adb -s emulator-5554 shell getprop sys.boot_completed` 查看安卓是否开机完成。

## 7. exec 调用时长

- 本会话内置的 exec 工具（`mcp__exec__*`）单次调用超过约 30 秒就报 “upstream request failed”。2026-11-15 实测：25 秒能返回，33 秒失败。
- 用仓库里的直接 HTTP 客户端（`execc.py`、`pcx.py`）调用时，50 秒仍能正常返回；上限是 mcp-proxy 的 90 秒。
- 所以长等待要么用 `pcx.wait_file` 这类直接客户端，要么拆成多次短调用。

## 8. 仓库里的 PC 脚本（`ops/pc/`）

这些脚本取自 exec 工作目录，适合在 PC 上直接调用，用 `powershell.exe -NoProfile -File` 运行：

| 脚本 | 用途 |
| --- | --- |
| `probe9876.ps1` | 直接连接 Blender 插件的 socket，发送 `get_scene_info`，判断插件是否存活（不经过 MCP） |
| `pdf_page.ps1 -Pdf a.pdf -Out p.png [-Page 0] [-Width 2400]` | 用 Windows 自带的 PDF 引擎把一页渲染成 PNG |
| `resize.ps1 -Src in.jpg -Out out.jpg [-Max 1600]` | 按 EXIF 方向缩小图片 |
| `sheet.ps1 -Src <目录> -Out sheet.jpg [-Filter *.jpg] [-Cols 4]` | 为一个目录里的图片做带文件名的拼图 |

## 9. Clash Verge（2026-11-15）
- 用户主账号运行 Clash Verge Rev。内核是 mihomo v1.19.21（`verge-mihomo.exe`，由 `clash_verge_service` 服务启动），混合端口 `127.0.0.1:7897`，规则模式，没有开 TUN。blender 账号的系统代理也指向 7897。
- 控制接口没有开 HTTP 端口，用命名管道 `\\.\pipe\verge-mihomo`。blender 账号能直接访问，不需要密钥。
- `clashctl.py`（源文件 `ops/pc/`，电脑上在 `D:\Projects\pc-tools\`，用 Blender 自带的 Python 运行）：
  - `status`、`groups`：只查询；
  - `test` / `best [组]`：测各节点延迟，`best` 再切到最快的节点；
  - `use 组 节点`：切到指定节点；
  - `mode rule|global|direct`：切模式，`direct` 相当于关掉代理；
  - `check`：测直连和走 7897 时能否访问 GitHub。
  - 改节点和模式会影响整台电脑，因为主账号的系统代理也走这个内核。
- GitHub 直连不稳定：0.27 版插件下载到一半断过一次，改走 7897 后续传成功。下载大文件时用 `curl -x http://127.0.0.1:7897 -C -`。

## 10. SketchUp 导入（2026-11-15）
- Blender 插件 Sketchup Importer 0.27（RedHaloStudio，SHA256 与 GitHub 公布的一致），装在 blender 账号的 Blender 5.2 用户插件目录，安装包在 `D:\Blender\Addons\sketchup_importer\`。
  - 插件带 Python 3.13 版本的扩展模块和 SketchUp SDK 的 DLL，能读到 SketchUp 2025.1。
- 相机和变换的英寸换算由插件处理，结果正确。
- 坐标离原点很远的模型（地理定位、导入的 DWG）导入后要平移回原点。
- 地理定位有两种物体：
  - `Location Terrain` 是带高程的 Google 地形，是效果图里的山，要保留并显示；
  - `Location Snapshot` 是平面卫星图，浮在原坐标 z=0 处，要排除。
- 检查远景时，相机或视图的远裁剪距离要设到几十千米。2026-11-15 用默认裁剪距离预览，远山被切掉，误判成地形不全。

## 11. 奖励周期核对（2026-11-16）
- **剿灭**：当期剿灭（轮换的那个）打满 400 击杀，单次最多 370 合成玉；常驻的切尔诺伯格、龙门外环、龙门市区分别是 260、330、350（campaign_table 的 gainLadders）。所以每周要打 5 次才满 1800。
  - 剿灭开关在每次日常里都打，直到森空岛显示本周已满；每次花 25 理智加 1 张常态事务代理卡。
  - 代理卡来自日常任务奖励，会过期。
- **保全派驻**（climb_tower_table）：
  - 每期奖励上限是数据增补条 60、数据增补仪 24，用户库存约 729、403，价值低；
  - 本期 tower_season_12 到 2026-12-15，复刻关“荒废灯塔”的记录已是 6/6，可以用代理卡扫荡，每次 2 张；
  - 建议只在代理卡快过期、剿灭又用不完时扫。maa-cli 的 `ssscopilot` 是打保全战斗用的，不能扫荡。
- **领取奖励**：除免费单抽（recruit）外全部打开：邮件、幸运墙合成玉（orundum）、限时开采许可（mining）、特别访问月卡（specialaccess）、活动签到（signinevent）。
- **信用作战**（credit_fight）保持关闭：OF-1 每次 12 理智才换 30 信用。

## 12. 保留端口与 LocalSend（2026-11-17）
- Hyper-V/WSL 的网络组件（winnat、HNS）每次开机在动态端口段（49152–65535）里随机保留若干 100 个一段的端口。查看：`netsh int ipv4 show excludedportrange protocol=tcp`（或 `udp`）。
- 2026-11-17 重启后 TCP 53229–53328 被保留，用户的 LocalSend（默认 53317）报 socket error、起不了服务器。
- 处理（主账号管理员 PowerShell）：`net stop winnat`，`netsh int ipv4 add excludedportrange protocol=tcp startport=53317 numberofports=1`（udp 同样一条），`net start winnat`。带 `*` 的是管理员保留，永久有效，程序自己仍能绑定；Hyper-V 不会再占。加保留时端口不能正被占用，要先退出 LocalSend。现在 TCP、UDP 的 53317 和 50000–50059 都是管理员保留。
- 不要用改 LocalSend 端口来绕开：它的组播发现也用这个端口，改了就搜不到其他设备（2026-11-17 改成 43317 时就是这样）。
