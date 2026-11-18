# MCP 控制台 v2

按《MCP 控制台需求》（Claude Docs：https://claude.ai/artifact/9t2Xn1CTVpmrb3fh1yidSn）和《MCP 控制台设计稿》（https://claude.ai/artifact/VGHaeyXed9rVSMYo9jLRcS）实现，替换 `C:\Program Files\BlenderMCP\panel\panel.py` 和它的 `static\`。agent.py（blender 账号）不变。

| 文件 | 作用 |
|---|---|
| `console.py` | 后端，主账号运行，127.0.0.1:8765，只用标准库。装到电脑上时改名为 `panel.py`，桌面快捷方式不用改 |
| `static/index.html`、`app.js`、`app.css` | 前端：两个页面按 1280×720 绘制、整体缩放；状态全部来自 `/api/status` 和事件流 |
| `static/ds/` | 设计系统（tokens、组件、贴图），取自设计稿 artifact 的 `ds/`。字体不进仓库：和旧版 `static\fonts` 的文件完全相同，安装时从旧版复制 |
| `install_console.ps1` | 安装包：核对 SHA256 → 关旧控制台 → 备份 panel → 替换。主账号管理员 PowerShell 7 运行 |

## 第一阶段（2026-11-18 完成）：连接状态 + Clash 联动
- 接口：`GET /api/status`、`GET /api/events?t=令牌`（SSE：status.changed、action.done）、`POST /api/tunnel {on}`、`POST /api/routes/check`、`POST /api/routes/{线路}/service {on}`、`POST /api/routes/{线路}/app/launch`、`POST /api/proxy {on}`、`POST /api/proxy/best`。开关类是异步的（202，做完推送）；关闭外网和停服务的推送带“撤销”。
- 临时授权相关接口（grants、approvals、logs、rules、fs、sandbox）现在返回 501，页面显示“还没有部署”。环境变量 `BMCP_GRANT_DEPLOYED=1` 打开第四条线路的转发和检测。
- 检测：从外网 POST 各个域名的 /mcp。401 算服务正常，502 断在服务，530 或外网关闭断在外网访问，连不上断在外网域名；服务正常但应用没连上断在应用。线路状态变化后，旧的检测结论标为过时，改用实时状态。
- Clash 联动（经命名管道 `\\.\pipe\verge-mihomo`）：
  - 显示的节点是出站真实走的：经 7897 向 www.gstatic.com 发一个 CONNECT，再从 `/connections` 读这条连接的链路。用户的配置里兜底规则是直连，按规则名猜会猜错。
  - 开启网络代理前先试 7897 能否上网；不通就换节点：链路上一级是手动选择组就测速后换到最快的，是自动组（智能检测、故障转移）就让 Clash 立即重测。
  - Clash 是直连模式时照样开启，但提示实际不经过节点。
- 测试：`python3 console.py --demo` 用模拟数据（隧道、服务、Clash 都是假的），Playwright 截图核对设计稿；电脑上用 blender 账号在 18765 端口跑过真实环境（检测、启停 Blender 服务、开关代理、令牌和 Host 校验、Clash 链路读取）。隧道开关只在主账号可用（凭证在主账号）。

## 第二阶段（待做）：临时授权
网关（tmcp.maimaiqiu.work → 8086）、沙盒账号 aitemp、执行前确认与检查、执行记录。需要管理员：建账号、给文件夹授权、在 Cloudflare 上给隧道加 tmcp 的 DNS 记录（`cloudflared tunnel route dns`，凭证在主账号）。
