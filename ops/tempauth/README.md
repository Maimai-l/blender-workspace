# 临时授权（2026-11-18 装好并验收）

给普通对话 AI 临时使用电脑的命令执行能力：按次数加时间限制，只能在用户勾选的 `D:\Projects\` 子文件夹里执行，执行前先过一遍检查规则。命令以隐藏的沙盒账号 `aitemp` 的身份运行，这个账号只对授权的文件夹有权限。界面加在现有 MCP 控制台上，作为“临时授权”页。

- `proto/`：界面原型，2026-11-16 交给用户确认，已发布为 artifact。
  - `tempauth.js`：页面逻辑，用面板自带的 Endfield 组件，数据是模拟的。
  - `tempauth.css`：新增的样式。
  - `build.py`：把面板的 tokens、组件库、字体（中文字体裁成用到的字）和这两个文件打包成单个 HTML。运行时需要面板的 `static/` 目录。
- 用户确认界面后再实现网关、沙盒账号和面板接口，做成安装包，由用户在主账号以管理员身份运行一次。

## 2026-11-18：后端设计和沙盒测试
- 设计写在《MCP 控制台需求》第 5 节（Claude Docs：https://claude.ai/artifact/9t2Xn1CTVpmrb3fh1yidSn）：网关（blender 账号，8086）+ 授权助手（SYSTEM 服务，只做五件事）+ 隐藏的标准用户 aitemp。边界是账号、文件权限、防火墙；执行前检查只作提醒。
- 用户已定：可以装系统级的助手服务；允许联网时走 Clash 7899；D 盘权限和装包要仔细设计并实测。
- 用户已经清楚 D 盘默认给 Authenticated Users 修改权、agent.token 对 Users 可读这些现状，不用再提醒，直接在设计里处理。
- `test/aitemp_test.ps1`（管理员 PowerShell 7 运行，`-Undo` 撤销）+ `test/runner.py`（以 aitemp 身份运行）：建账号、按 5.2 加权限（D 盘顶层：程序目录拒绝写入，其余拒绝读写；D:\ 根目录文件拒绝；受保护位置显式拒绝）、按 5.4 加防火墙规则（本机端口除 7899 外拦截；断网规则），再分断网和联网两轮检查文件、程序、装包、本机端口、联网、账号、吊销，报告写到 `D:\Projects\aitemp-test\report.md`。
- aitemp 的密码不落盘：测试包每次随机重设；以后由助手服务启动时重设并只留在内存里。

### 第一次测试（2026-11-18 15:19，60 项未通过 26 项）的结论和改动
- 程序目录拒绝 `W` 会连程序都跑不了：icacls 的 `W` 含 SYNCHRONIZE（和 READ_CONTROL），打开和执行文件都要 SYNCHRONIZE。改为只拒绝 `WD,AD,WEA,WA,D,DC`。
- Windows 防火墙的按账号规则管不到本机回环（127.0.0.1 上的转写台、agent、Clash 都连得上，断网时还能经 7899 上网）。改用 WFP：`test/wfp.cs`（Add-Type 加载）在 ALE_AUTH_CONNECT_V4/V6 层按 aitemp 的 SID 拦 127.0.0.0/8 和 ::1，联网时再加一条更高权重的放行 127.0.0.1:7899；过滤器持久，自带 provider 和 sublayer，`Remove()` 只删自己加的。结构体布局已用 VS 的 cl 按 SDK 头文件算过，和 C# 一致（FWPM_FILTER0 200 字节）。
- 外网直连一律拦（防火墙规则 AITemp-Direct），联网只能经 Clash 7899。
- 火绒对 svchost 弹窗：测试包里以别的账号启动程序（Secondary Logon 服务）、改防火墙（mpssvc）、加 WFP 过滤器（BFE）都在 svchost 里执行，火绒会提示，属于预期。

### 第二次测试（15:37，62 项未通过 10 项）
- WFP 生效：本机回环全部拦住（测试用的 47123 也连不上），断网时 7899 也连不上，联网时只放行 7899；外网直连一律拦，经 7899 能翻墙。
- 剩下的 10 项都是 D 盘程序运行不了：icacls 连具体权限也自动加 SYNCHRONIZE（Get-Acl 读到掩码 0x00110156）。改用 `test/denywrite.ps1`（Windows PowerShell 5.1 + .NET FileSystemAccessRule），实测掩码 0x00010156。以后助手服务给目录加拒绝项也要避开 SYNCHRONIZE。

### 第三次测试（15:48，62 项未通过 1 项）
- 程序全部能跑：conda 的 python、`python -m venv`（3.8 秒）、node、npm、git、`blender -b`（2.3 秒）。程序目录的拒绝写入生效（往 conda 的 site-packages 写文件被拒）。
- 装包：断网时 venv 的 pip、npm、git clone 都失败；联网时 venv 里 `pip install six`、`npm install is-number`、`git clone` 都成功。PYTHONUSERBASE、npm 全局目录都指向授权文件夹的 `.aitemp`。
- 本机回环、外网直连、文件、账号、吊销全部符合预期。
- 唯一未通过的是测试本身的问题：`pip install --user tomli` 里的 tomli 已在 conda base，pip 什么也没装就返回成功，所以 `--user` 其实没测到。已改成装 conda base 没有的 cowsay，并检查它确实装在 `.aitemp\pyuser` 下；放进第二阶段的验收测试里一起跑。
- 用时：给 `D:\ProgramData` 加拒绝写入要 55 秒（文件多），以后安装时做一次即可，签发授权不用重做；断网时 npm 要重试约 70 秒才放弃，已在环境变量里把 npm 重试改为 1 次、间隔 2～5 秒。

## 第二阶段实现（2026-11-18）
| 文件 | 作用 |
|---|---|
| `helper/AitempHelper.cs` + `wfp.cs` | 授权助手，Windows 服务 `AITempHelper`（SYSTEM）。C# 5，用 .NET Framework 自带的 csc 编译，安装包在电脑上现编。命名管道 `\\.\pipe\aitemp-helper`，只给 blender 账号读写。日志 `C:\ProgramData\BlenderMCP\aitemp-helper.log` |
| `gateway/gateway.py` | 网关（blender 账号，标准库）。8086 对外 MCP（`/t/<令牌>/mcp`，7 个工具），8087 管理接口（令牌在 `C:\ProgramData\BlenderMCP\tempauth.token`）。数据 `C:\Users\blender\TempAuth\tempauth.db`。由 agent.py 随代理启动。`--demo` 用假助手，可在 Linux 上测 |
| `install.ps1` + `stage.py` | 安装包：`python3 ops/tempauth/stage.py <目录>` 把文件和 SHA256 整理好，传到 `D:\Projects\mcp-console-stage\tempauth\`，用户在主账号管理员 PowerShell 7 运行 |
| `test/accept.py` | 装好后在 blender 账号跑的验收测试，报告 `D:\Projects\aitemp-test\accept-report.md` |

要点：
- **每条授权一个本地组** `AITemp-<授权编号>`，授权文件夹上只加这个组的“修改”权限。运行前把 aitemp 临时加进组、`LogonUser` 拿令牌、立刻移出：令牌里的组在登录时就定了，所以同时有几条授权时，一条授权的命令碰不到另一条的文件夹。令牌按授权缓存。aitemp 自己的拒绝项始终有效。
- 命令：`CreateProcessAsUser` 进单独的窗口站 `AITempWS\Default`（服务所在的窗口站 aitemp 进不去，控制台程序会初始化失败），作业对象（结束即杀子进程、8 GB 内存、低于正常优先级），一次一条；输出留头尾各 96 KB，每行先按 UTF-8、不行再按 GBK 解。shell 可选 cmd、powershell（-EncodedCommand，先切 UTF-8 输出）、bash（Git Bash）。
- 读写文件、列目录：助手模拟 aitemp + 授权组的身份做，边界还是账号权限；另按真实路径（解析联接）核一遍在授权文件夹里。
- 环境变量：TEMP、pip/npm/uv 缓存、`PYTHONUSERBASE`、npm 全局目录都指到 `<文件夹>\.aitemp\`；PATH 固定（conda、D:\Program Files、git、Blender、系统目录）；联网时 `HTTP(S)_PROXY=127.0.0.1:7899`；npm 重试 1 次。
- 联网：WFP 按命令切换（一次一条，所以不会串）；命令结束恢复断网。
- 巡查：每 20 秒和每条命令结束后，结束不在当前作业里的 aitemp 进程（防经计划任务、WMI 绕出作业）。
- 自检：D 盘新出现的顶层目录自动按数据目录拒绝；以 aitemp 身份跑一段探测脚本（受保护位置、本机端口、外网）。
- 网关：执行前检查只作提醒；一次调用最多等 75 秒（Cloudflare 约 100 秒断开），没跑完给任务编号；执行前确认同样等 75 秒，之后对方用 get_command_result 取结果。执行和写文件计次，助手没启动成功会退回次数。吊销：令牌失效 + 结束作业（实测接口 2 ms 返回）；10 分钟内可恢复，之后（或到期、用完）撤掉文件夹权限、删组。
- 控制台：`/api/grants` 等转给网关的管理接口，网关事件转推到页面；`POST /api/fs/pick` 在主账号桌面弹出选择文件夹的对话框。浏览器拿不到从资源管理器拖进来的文件夹的完整路径，所以签发框支持粘贴路径、拖入文字路径、“浏览…”和页内浏览。
- 网关演示测试（Linux，假助手）和界面截图测试（Playwright）都过了；真机要装好后跑 `test/accept.py`。

## 安装和验收（2026-11-18）
- 17:20 用户运行安装包：服务 AITempHelper 1.0.0 启动，网关由重启后的 agent.py 拉起。
- 第一次验收发现三处问题，助手改为 1.0.1（安装包 `-HelperOnly`）：
  1. 巡查和新命令启动有竞态：上一条命令结束后的巡查把正在创建（还没放进作业）的 cmd 当成漏网进程结束了，CreateProcessAsUser 报拒绝访问。巡查改为全程持有 runLock。
  2. git clone 失败：授权文件夹在 `D:\Projects` 下两级以上时，中间目录（继承了拒绝）连属性都读不到，git 建目录时逐级 stat 整条路径就失败。改为给中间各级目录加授权组的“读属性”（不继承，用 SetFileSecurity 写，不遍历子目录），释放时撤掉。第三轮测试的文件夹正好在 `D:\Projects` 下一级，所以没暴露。
  3. 指到授权外的联接，模拟 aitemp 后解析不出真实路径，列出来是空文件夹（没泄露，但提示不对）。改为先以 SYSTEM 解析真实路径再判断。
- 1.0.1 验收 40 项全部通过（不再需要命令间停顿），报告 `D:\Projects\aitemp-test\accept-report.md`。经 tmcp.maimaiqiu.work 从云端实测：initialize 1.8 秒，run_command 以 aitemp 执行，计次正确，错误令牌 404。
- 另一处之前没想到的：Python 的 `open()` 以 GENERIC_READ|GENERIC_WRITE 打开命名管道，GENERIC_WRITE 含 FILE_APPEND_DATA，对管道就是 CreateNewInstance；管道权限只给 ReadWrite 时客户端打不开。已给 blender 加上。
- 测试用的授权都已吊销；签发框的“上次选择”已清掉，不会默认选到测试文件夹。

## 浏览器授权（网关 1.1.0，2026-11-18）
设计稿：https://claude.ai/artifact/LcJk7ZdCP3XRGqsR6Vbth3 （9 张画板）。用户定下的规则：
- 可以只授权浏览器；浏览器操作不计次数，不需要执行前确认。
- 登录按网站域名（eTLD+1，`site_of`）区分，名称取网页标题，不手动命名。
- 执行中需要登录时，对方调用 `request_login`，请求出现在控制台右下角浮层；执行中完成的登录默认保存；被拒绝后对方可以再次请求。

实现：
- 每条带浏览器的授权一个 Playwright MCP（`C:\Program Files\BlenderMCP\node\node_modules\@playwright\mcp\cli.js`，stdio），参数 `--isolated --headless --proxy-server http://127.0.0.1:7899 --proxy-bypass "<-loopback>"`：回环地址也交给代理，请求落在代理节点上，碰不到本机服务（实测 `localtest.me`、`127.0.0.1.nip.io` 都没打到本机探针）。另有网址检查（只许 http/https，拦本机和局域网地址）和工具白名单（不给上传本地文件、执行任意代码）。
- 输出目录：有文件夹的授权放 `<第一个文件夹>\downloads`；仅浏览器的放 `TempAuth\browser\<编号>\output`，授权释放时删除。
- 保存的登录：`TempAuth\logins\<域名>.json`（该域名的 cookies 和 localStorage）。签发时选中的登录合并成 storageState 交给浏览器启动，启动后立即删掉临时文件。
- `request_login(url, reason)` 最多等 75 秒；没处理完返回 `pending` 和请求编号，对方用 `check_login` 继续等；结果 `logged_in`、`declined`、`cancelled`（主人取消、10 分钟未处理或授权失效）。登录写入用内部的 `browser_run_code_unsafe`（`addCookies` + 刷新），不对外提供。
- 控制台（主账号）：“去登录”或“新建登录”用有界面的 Edge（同一个 Playwright MCP，`--browser msedge --isolated`）打开登录页，每 2 秒读一次 cookies 的域名作为“已记录的网站”；点“完成”时读 storageState，只把选中的域名交给网关 `POST /admin/logins/save`。
- 管理接口新增：`GET logins`、`POST logins/<域名>/delete`、`POST logins/save`、`GET logins/requests`、`POST logins/requests/<编号>`（start、decline、cancel）。事件：`login.created/changed/resolved`、`logins.changed`；控制台自己发 `loginwin.changed`。
- 测试：PC 上用备用端口 18086/18087 跑过真实浏览器（打开网页 1.2 秒、截图、本机/局域网/file:// 被拦、evaluate 被拒、完整登录流程、吊销 0.19 秒）。界面在 Linux 上用 `gateway.py --demo` + `console.py --demo`（演示用的登录窗口 `DemoWin`）和 Playwright 跑通：新建登录、仅浏览器签发、登录请求、去登录、完成（对方拿到 `logged_in`）、拒绝（`declined`）。
- 安装：`install.ps1 -ConsoleOnly` 现在同时更新网关（第 1、4、5 步）；装完由维护会话结束旧网关进程，agent.py 重新拉起。

## 网关 2.0：对外结果规范（2026-11-18）
- 规范在《MCP 控制台需求》第 6 节。所有工具声明 outputSchema，结果放 structuredContent（content 里同一份 JSON）；失败为 {"error": {code, message, retryable, details}}，错误码 18 个；时刻 UTC ISO 8601、时长 *_ms、大小 *_bytes；message 英文。
- 命令和登录请求是“编号 + status + next”；退出码非 0 为 failed 且 isError。grant_info 按能力分组（folders、browser），只列适用的设置。
- 浏览器结果：快照文件读出后放进结果（最多 60 KB）、截图只留图片、PDF 作为嵌入资源；去掉 filename 参数；Playwright 自己生成的文件处理后删除，网页下载的文件保留。
- 带浏览器的授权次数用完后仍是 active（浏览器不计次），命令和写文件返回 limit_reached。
- 验收：accept.py 42/42、browser_accept.py 27/27，经 tmcp 从云端实测通过。本地测试：`gateway.py --demo` 加 scratchpad 里的 v2test.py 思路（每个结果按 outputSchema 校验）。
