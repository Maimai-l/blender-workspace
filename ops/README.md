# PC 与 MCP 运维手册

这份手册写给负责维护的会话：电脑和三条 MCP 服务的现状、检查方法、收尾清理和排障。
建模和渲染的经验在根目录的 `CLAUDE.md` 和各项目的 README 里，这里不重复。
最后核对：2026-11-12。

## 1. 管线

```
云端会话 ──(代理注入凭证)──▶ Cloudflare 隧道（cloudflared，主账号运行，protocol http2，约 100 秒断开回复）
  bmcp.maimaiqiu.work → 127.0.0.1:8080 mcp-proxy → blender-mcp.exe (stdio) → Blender 插件 127.0.0.1:9876 → blender.exe
  umcp.maimaiqiu.work → 127.0.0.1:8082 mcp-proxy → mcp-for-unity.exe (stdio) → Unity 编辑器桥接 6400/6401
  xmcp.maimaiqiu.work → 127.0.0.1:8084 mcp-proxy --requestTimeout 90000 → claude.exe mcp serve (2.1.311)
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

## 5. 已知问题（2026-11-12）

1. **agent 把 Unity Hub 的 `unity.exe serve` 当成了编辑器。**
   - 原因：`process_running("Unity.exe")` 用的是 `tasklist /FI "IMAGENAME eq Unity.exe"`，进程名不区分大小写，会匹配到 Hub 的 `resources\unity.exe`。控制台的 `pids("Unity.exe")` 也是同样的写法。
   - 后果：只要 Unity Hub 开着，状态里就会显示 Unity 正在运行，“打开 Unity” 只会回答 “Unity 已经开着”，实际什么都不做。
   - 临时办法：经 exec 直接启动编辑器 `"/d/Program Files/Editor/Unity.exe" -projectPath "D:/Unity/Projects/<工程>"`，等桥接端口开始监听后，再调用 `/mcp/unity/start`。
   - 根治：按完整路径判断进程（不在 `D:\Program Files\Unity Hub\` 下的才算编辑器），需要发安装包。
2. **Blender 的 `proxy.log` 已有 215 MB。** 每次调用的完整代码都会写进去，只在服务重启时清空，大约每天增长 45 MB。在没有其他会话使用 Blender 时，经 agent 调用 `stop` 再 `start` 就能清空。根治办法是让 agent 按大小轮转日志，需要发安装包。
3. `Temp\93e22641-…tmp`（48 MB，2026-10-26）一直被某个进程占用，清理时会跳过。
4. `C:\Program Files\BlenderMCP\` 里有两份 `panel.bak-*` 和三份 `panel\backup-before-*`，是历次升级留下的备份。blender 账号删不了，下次发安装包时一起清掉。

## 6. 仓库里的 PC 脚本（`ops/pc/`）

这些脚本取自 exec 工作目录，适合在 PC 上直接调用，用 `powershell.exe -NoProfile -File` 运行：

| 脚本 | 用途 |
| --- | --- |
| `probe9876.ps1` | 直接连接 Blender 插件的 socket，发送 `get_scene_info`，判断插件是否存活（不经过 MCP） |
| `pdf_page.ps1 -Pdf a.pdf -Out p.png [-Page 0] [-Width 2400]` | 用 Windows 自带的 PDF 引擎把一页渲染成 PNG |
| `resize.ps1 -Src in.jpg -Out out.jpg [-Max 1600]` | 按 EXIF 方向缩小图片 |
| `sheet.ps1 -Src <目录> -Out sheet.jpg [-Filter *.jpg] [-Cols 4]` | 为一个目录里的图片做带文件名的拼图 |
