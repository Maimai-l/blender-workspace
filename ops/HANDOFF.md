# 维护会话交接（2026-11-20 晚）

新开对话时先读这里，再按需读各目录的 README。

## 当前状态
- 临时授权：助手 AITempHelper 1.0.2、网关 3.0.0（`ops/tempauth/`）。浏览器工具 3.0（11 个按任务设计的工具）、屏蔽列表 `ops/tempauth/gateway/blocklist.txt`、D 盘顶层目录可授权。验收 accept.py 45 项、browser_accept.py 32 项全部通过。设计见《MCP 控制台需求》第 6、7 节。
- 控制台：`ops/console/`，签发框含文件夹、浏览器、本机地址白名单、完整浏览器工具选项。
- 《Windows 主机维护手册》已同步到 2026-11-20 的状态。
- 会话侧工具已统一到仓库根目录 `tools/`（2026-11-20）：运维直接 `python3 -I tools/pcx.py bash "..."`，不要再借用 `qiting/tools`。电脑端辅助脚本和中转目录在 `D:\Projects\pc-tools`（自动补齐）。
- 测试授权已全部从网关数据库清掉；验收脚本跑完会恢复 `last_issue`，测试文件夹和暂存目录用完就删。

## 待办
- 开工先看《明日方舟托管：现状与对接》（https://claude.ai/artifact/FN2123fZA5U5CYn6hhrRUZ）的「需求与变更」表。
- 11-22 03:59 活动关闭：`sanity_plan.py` 会自动切关，不用手改；11-22 10:00 的提醒只剩清活动商店。
- 11-23 代理卡改去保全派驻（见 `ops/maa/README.md` 日历）。
- MAA 托管的设计依据是用户的《MAA 智能刷图调度器设计》（https://claude.ai/artifact/6c5EDFa1fy8J2jAwc3mP1c）。各期进度见 `ops/maa/README.md` 开头；下一步是第 3 期“理智不溢出”（事件触发的下次运行时间）。
- MAA 托管会经 Bark 推送到用户 iPhone（`ops/maa/notify.py`，key 在电脑 `C:\Users\blender\.bark\key`）。用户还想要状态页和“上号自动暂停”（方案 B、C：隧道子域名 + 主屏图标描述文件 + 快捷指令自动化），计划和第 3 期事件触发一起做。
- 保全派驻扫荡已自动化（`tower_sweep.py`），11-20 真机测试通过。
- 11-21 0:25 有一条自己设的提醒：核对 0:00 那次日常把理智打空了没有。
- 首次搜索约 16 秒（含启动浏览器），可考虑预热。

## 更新服务的流程
- `python3 ops/tempauth/stage.py <暂存目录>` → 打包上传到 `D:\Projects\mcp-console-stage\tempauth\` → 用户在主账号管理员 PowerShell 7 运行 `install.ps1`（`-HelperOnly` 只更新助手，`-ConsoleOnly` 更新网关和控制台）→ 经 agent（`POST /mcp/grant/stop`、`start`）重启网关 → 跑两套验收。
- 不要假设用户还没运行安装包：先查 `C:\Program Files\BlenderMCP\tempauth\gateway.py` 的版本和修改时间。
