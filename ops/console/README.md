# MCP 控制台 v2

按《MCP 控制台需求》（Claude Docs：https://claude.ai/artifact/9t2Xn1CTVpmrb3fh1yidSn）和《MCP 控制台设计稿》（https://claude.ai/artifact/VGHaeyXed9rVSMYo9jLRcS）实现，替换 `C:\Program Files\BlenderMCP\panel\panel.py` 和它的 `static\`。agent.py（blender 账号）也在这里管理。

| 文件 | 作用 |
|---|---|
| `console.py` | 后端，主账号运行，127.0.0.1:8765，只用标准库。装到电脑上时改名为 `panel.py`，桌面快捷方式不用改 |
| `static/index.html`、`app.js`、`app.css` | 前端：两个页面按 1280×720 绘制、整体缩放；状态全部来自 `/api/status` 和事件流 |
| `static/ds/` | 设计系统（tokens、组件、贴图），取自设计稿 artifact 的 `ds/`。字体不进仓库：和旧版 `static\fonts` 的文件完全相同，安装时从旧版复制 |
| `agent.py` | blender 账号里的代理：启停各条 MCP 服务、打开 Blender/Unity、切换联网方式。2026-11-18 加了浏览器服务 |
| `install.ps1` | 安装包：核对 SHA256 → 装 Playwright MCP 0.0.85 → 关旧控制台 → 备份 panel → 替换 panel.py、agent.py、static → 给隧道加 wmcp 域名。主账号管理员 PowerShell 7 运行 |

## 第一阶段（2026-11-18 完成）：连接状态 + Clash 联动
- 接口：`GET /api/status`、`GET /api/events?t=令牌`（SSE：status.changed、action.done）、`POST /api/tunnel {on}`、`POST /api/routes/check`、`POST /api/routes/{线路}/service {on}`、`POST /api/routes/{线路}/app/launch`、`POST /api/proxy {on}`、`POST /api/proxy/best`。开关类是异步的（202，做完推送）；关闭外网和停服务的推送带“撤销”。
- 临时授权相关接口（grants、approvals、logs、rules、fs、sandbox）现在返回 501，页面显示“还没有部署”。环境变量 `BMCP_GRANT_DEPLOYED=1` 打开第四条线路的转发和检测。
- 检测：从外网 POST 各个域名的 /mcp。401 算服务正常，502 断在服务，530 或外网关闭断在外网访问，连不上断在外网域名；服务正常但应用没连上断在应用。线路状态变化后，旧的检测结论标为过时，改用实时状态。
- Clash 联动（经命名管道 `\\.\pipe\verge-mihomo`）：
  - 显示的节点是出站真实走的：经 7897 向 www.gstatic.com 发一个 CONNECT，再从 `/connections` 读这条连接的链路。用户的配置里兜底规则是直连，按规则名猜会猜错。
  - 开启网络代理前先试 7897 能否上网；不通就换节点：链路上一级是手动选择组就测速后换到最快的，是自动组（智能检测、故障转移）就让 Clash 立即重测。
  - Clash 是直连模式时照样开启，但提示实际不经过节点。
- 测试：`python3 console.py --demo` 用模拟数据（隧道、服务、Clash 都是假的），Playwright 截图核对设计稿；电脑上用 blender 账号在 18765 端口跑过真实环境（检测、启停 Blender 服务、开关代理、令牌和 Host 校验、Clash 链路读取）。隧道开关只在主账号可用（凭证在主账号）。

## 第二阶段（2026-11-18 实现）：临时授权
- 实现在 `ops/tempauth/`（授权助手、网关、安装包、验收测试），见那里的 README。
- `console.py`：`/api/grants`、`approvals`、`logs`、`rules`、`fs`、`sandbox` 转给网关的管理接口 127.0.0.1:8087；后台线程订阅网关的事件流，转推 `approval.created/resolved`、`log.created/updated`、`grant.changed`、`counts`；`POST /api/fs/pick` 弹出选择文件夹对话框。`C:\Program Files\BlenderMCP\tempauth\gateway.py` 存在即视为已部署。
- `agent.py`：第五个服务 `grant`（8086），直接用 Python 运行 gateway.py（不经 mcp-proxy），代理启动时自动拉起。
- 页面：`static/grants.js`（P2 授权列表与执行记录、P3/P4 签发、P5 待确认浮层（任何页面可见，可收起）、P6 规则与沙盒自检、记录详情）。
- 第四条线路的第三段改为“授权助手”：网关和助手都就绪才算接通。
- 浏览器授权（2026-11-18）：签发框分“文件夹”“浏览器”两项能力；侧栏“浏览器登录”管理保存的登录；待确认浮层同时显示命令确认和登录请求，“去登录”在主账号桌面打开 Edge 登录窗口（`/api/logins/window`、`/finish`、`/cancel`，只在 Windows 上可用，`--demo` 时用 `DemoWin` 模拟）。细节见 `ops/tempauth/README.md`。
- 界面文案：不用间隔号，按钮、标签、提示用书面语；网关和 agent 返回、会显示在页面上的提示也按此改过。

## 浏览器 MCP（2026-11-18）
方案见《Windows 主机维护手册》的「浏览器」页。实现要点：
- 第五条线路：wmcp.maimaiqiu.work → 127.0.0.1:**8088**（手册原写 8086，和需求文档里临时授权的 tmcp 撞了，改为 8088）→ mcp-proxy → `node C:\Program Files\BlenderMCP\node\node_modules\@playwright\mcp\cli.js`（0.0.85）→ 无界面 Edge，配置文件 `C:\Users\blender\BrowserMCP-profile`。
- 参数：`--browser msedge --headless --snapshot-mode none --image-responses omit --codegen none --no-webmcp`。`--no-webmcp` 是手册之外加的：不收网页自己注册的工具，少一个提示注入的入口。
- **Clash 联动**：mihomo 的入站（listener）如果写了 `proxy:`，这个入口的流量直接交给该代理，不看全局模式（源码 tunnel.go 的 resolveMetadata 先判断 SpecialProxy）。所以在 Clash Verge 的全局扩展配置里加一个只给浏览器用的入口 127.0.0.1:7899、`proxy: GLOBAL`，浏览器就总是走节点，电脑其余部分仍按 Clash 当前模式（现在是直连）。agent 启动浏览器时优先用 7899，没有就退回 7897；控制台第三段显示“出口”实际走的节点（经该入口发 CONNECT，从 `/connections` 读链路）。
- 停止服务时按配置文件路径结束残留的 Edge（实测打开页面时 7 个 Edge 进程，停止后 0 个）。
- 实测（blender 账号，测试端口）：25 个工具，打开 example.com、browser_find 正常；Clash 直连模式下经 7897 打开 google 报 ERR_CONNECTION_CLOSED，这正是要 7899 的原因。
- 云端：`.mcp.json` 加了 `browser`（`BROWSER_MCP_URL`），`.claude/settings.json` 禁用 `mcp__browser__browser_run_code_unsafe`。密钥在 `C:\Users\blender\browser-mcp-secret.txt`（KEY、PATH 各 64 位）。
