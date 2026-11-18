# 临时授权（设计中，2026-11-18）

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
