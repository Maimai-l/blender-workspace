"""MCP 代理（运行在 blender 账号里）。

只监听 127.0.0.1，替控制台启动/停止四条 MCP 服务（Blender、Unity、命令执行、浏览器）的 mcp-proxy、
打开 Blender 和 Unity、返回状态和日志。
每次启动生成新令牌，写到 C:\\ProgramData\\BlenderMCP\\agent.token，控制台凭它调用。
只用 Python 标准库。
"""
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IS_WIN = os.name == "nt"
HOME = Path.home()
PORT = int(os.environ.get("BMCP_AGENT_PORT", "8766"))
ROOT = Path(os.environ.get("BMCP_ROOT", r"C:\Program Files\BlenderMCP"))
TOKEN_FILE = Path(os.environ.get("BMCP_AGENT_TOKEN_FILE", r"C:\ProgramData\BlenderMCP\agent.token"))
NODE = os.environ.get("BMCP_NODE") or (str(ROOT / "node" / "node.exe") if (ROOT / "node" / "node.exe").exists() else None) \
    or shutil.which("node") or r"C:\Program Files\nodejs\node.exe"
PROXY_JS = Path(os.environ.get("BMCP_PROXY_JS", str(ROOT / "node" / "node_modules" / "mcp-proxy" / "dist" / "bin" / "mcp-proxy.mjs")))

# Blender
ADDON_PORT = int(os.environ.get("BMCP_ADDON_PORT", "9876"))
BLENDER_EXE = os.environ.get("BMCP_BLENDER_EXE", r"D:\Program Files\Blender Foundation\Blender 5.2\blender.exe")

# Unity
UNITY_HUB = os.environ.get("UMCP_UNITY_HUB", r"D:\Program Files\Unity Hub\Unity Hub.exe")
UNITY_EXE = os.environ.get("UMCP_UNITY_EXE", r"D:\Program Files\Editor\Unity.exe")  # 现有的 6000.4.2f1
UNITY_EDITORS = Path(os.environ.get("UMCP_UNITY_EDITORS", r"D:\Unity\Editors"))      # 以后用 Hub 装的其它版本
UNITY_PROJECTS = Path(os.environ.get("UMCP_UNITY_PROJECTS", r"D:\Unity\Projects"))
UNITY_PROJECT = os.environ.get("UMCP_UNITY_PROJECT", "")  # 指定要打开的工程；留空则自动选
UNITY_STATUS_DIR = HOME / ".unity-mcp"                    # MCP for Unity 插件写状态文件的位置
UNITY_DEFAULT_BRIDGE = 6400

# 浏览器：Playwright MCP 驱动无界面的 Edge，用单独的配置文件；出站经主账号的 Clash（见 browser_proxy）
PLAYWRIGHT_CLI = Path(os.environ.get("WMCP_CLI", str(ROOT / "node" / "node_modules" / "@playwright" / "mcp" / "cli.js")))
BROWSER_PROFILE = Path(os.environ.get("WMCP_PROFILE", str(HOME / "BrowserMCP-profile")))
BROWSER_RUN = Path(os.environ.get("WMCP_LOG_DIR", str(HOME / "BrowserMCP-run")))
BROWSER_CLASH_PORTS = [int(x) for x in os.environ.get("WMCP_CLASH_PORTS", "7899,7897").split(",") if x.strip().isdigit()]

SERVICES = {
    "blender": {
        "label": "Blender",
        "port": int(os.environ.get("BMCP_MCP_PORT", "8080")),
        "secret": Path(os.environ.get("BMCP_SECRET_FILE", str(HOME / "blender-mcp-secret.txt"))),
        "log": Path(os.environ.get("BMCP_LOG_DIR", str(HOME / "BlenderMCP-run"))) / "proxy.log",
        "exe": os.environ.get("BMCP_MCP_EXE", str(ROOT / "bin" / "blender-mcp.exe")),
        "args": [],
    },
    "unity": {
        "label": "Unity",
        "port": int(os.environ.get("UMCP_MCP_PORT", "8082")),
        "secret": Path(os.environ.get("UMCP_SECRET_FILE", str(HOME / "unity-mcp-secret.txt"))),
        "log": Path(os.environ.get("UMCP_LOG_DIR", str(HOME / "UnityMCP-run"))) / "proxy.log",
        "exe": os.environ.get("UMCP_MCP_EXE", str(ROOT / "bin" / "mcp-for-unity.exe")),
        "args": ["--transport", "stdio"],
    },
    # 命令执行：Claude Code 2.1.311 的 claude mcp serve（Read、Edit、Write、Bash 等工具），不登录、不联网
    "exec": {
        "label": "命令执行",
        "port": int(os.environ.get("XMCP_MCP_PORT", "8084")),
        "secret": Path(os.environ.get("XMCP_SECRET_FILE", str(HOME / "exec-mcp-secret.txt"))),
        "log": Path(os.environ.get("XMCP_LOG_DIR", str(HOME / "ExecMCP-run"))) / "proxy.log",
        "exe": os.environ.get("XMCP_EXE", str(ROOT / "claude-mcp" / "claude.exe")),
        "args": ["mcp", "serve"],
        # Cloudflare 约 100 秒断开；mcp-proxy 在 90 秒时先给云端返回错误
        "proxy_args": ["--requestTimeout", "90000"],
        "cwd": Path(os.environ.get("XMCP_WORK_DIR", str(HOME / "ExecMCP"))),  # 命令默认在这里运行
        "env": {
            "DISABLE_UPDATES": "1", "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1", "DISABLE_FEEDBACK_COMMAND": "1",
            "CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY": "1",
            "CLAUDE_CODE_DISABLE_CRON": "1", "CLAUDE_CODE_DISABLE_WORKFLOWS": "1",
        },
        "image": None,  # 停止时按端口结束进程树，不按 claude.exe 进程名结束
    },
    "browser": {
        "label": "浏览器",
        "port": int(os.environ.get("WMCP_MCP_PORT", "8088")),
        "secret": Path(os.environ.get("WMCP_SECRET_FILE", str(HOME / "browser-mcp-secret.txt"))),
        "log": BROWSER_RUN / "proxy.log",
        "exe": None,   # 用 NODE 运行 PLAYWRIGHT_CLI，见 mcp_start
        "args": [str(PLAYWRIGHT_CLI), "--browser", "msedge", "--headless",
                 "--user-data-dir", str(BROWSER_PROFILE), "--output-dir", str(BROWSER_RUN / "output"),
                 # 省 token：操作后不附整页快照、不回传截图、不生成代码；不收网页自己注册的工具（防提示注入）
                 "--snapshot-mode", "none", "--image-responses", "omit", "--codegen", "none", "--no-webmcp"],
        "proxy_args": ["--requestTimeout", "90000"],
        "cwd": BROWSER_RUN,
        "image": None,
    },
}

NO_TELEMETRY = {"DISABLE_TELEMETRY": "true", "UNITY_MCP_DISABLE_TELEMETRY": "true", "MCP_DISABLE_TELEMETRY": "true"}
NO_WINDOW = 0x08000000 if IS_WIN else 0
NEW_GROUP = 0x00000200 if IS_WIN else 0
TOKEN = secrets.token_hex(32)


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.stdout.decode("oem" if IS_WIN else "utf-8", errors="replace")
    except Exception:
        return ""


def listening_pid(port):
    """返回监听该端口的进程 PID；没人监听返回 None。只看系统表，不去连接端口。"""
    if IS_WIN:
        for line in run(["netstat", "-ano", "-p", "TCP"]).splitlines():
            p = line.split()
            if len(p) >= 5 and p[1].rsplit(":", 1)[-1] == str(port) and p[2] in ("0.0.0.0:0", "[::]:0", "*:*"):
                try:
                    return int(p[4])
                except ValueError:
                    return -1
        return None
    out = run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"]).split()  # 仅用于在非 Windows 上测试
    if out and out[0].isdigit():
        return int(out[0])
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return -1
    except OSError:
        return None


def process_running(image):
    if IS_WIN:
        out = run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"])
        return any(line.lower().startswith(f'"{image.lower()}"') for line in out.splitlines())
    return bool(run(["pgrep", "-f", Path(image).stem]).strip())


def kill_tree(pid):
    if IS_WIN:
        run(["taskkill", "/PID", str(pid), "/T", "/F"])
    else:
        run(["pkill", "-TERM", "-P", str(pid)])
        run(["kill", "-TERM", str(pid)])


def read_secret(path):
    data = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    if not data.get("KEY") or not data.get("PATH"):
        raise ValueError("密钥文件里缺少 KEY 或 PATH")
    return data


def tail(path, lines=120):
    if not path.exists():
        return "（还没有日志）"
    text = path.read_bytes()[-200_000:].decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


# ---------- Unity 编辑器 ----------

def unity_latest_status():
    """读插件最新的状态文件：端口、工程路径、心跳、是否在重载。"""
    try:
        files = sorted(UNITY_STATUS_DIR.glob("unity-mcp-status-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        data = json.loads(files[0].read_text(encoding="utf-8-sig"))
        age = time.time() - files[0].stat().st_mtime
        hb = data.get("last_heartbeat")
        if hb:
            try:
                t = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc) if hb.endswith("Z") else t.astimezone()
                age = (datetime.now(timezone.utc) - t).total_seconds()
            except ValueError:
                pass
        return {"port": data.get("unity_port"), "project_path": data.get("project_path") or "",
                "reloading": bool(data.get("reloading")), "age": age}
    except Exception:
        return None


def unity_project_dir(p):
    """状态文件里的路径可能是 Assets 目录，也可能是工程根目录。"""
    p = Path(p)
    return p.parent if p.name.lower() == "assets" else p


def unity_status():
    st = unity_latest_status()
    running = process_running("Unity.exe")
    port = st["port"] if st and isinstance(st.get("port"), int) else UNITY_DEFAULT_BRIDGE
    project = unity_project_dir(st["project_path"]).name if st and st["project_path"] else ""
    return {
        "app_running": running,
        "bridge_port": port,
        "bridge_listening": running and listening_pid(port) is not None,
        "reloading": bool(running and st and st["reloading"] and st["age"] < 60),
        "project": project,
    }


def editor_version(project):
    f = project / "ProjectSettings" / "ProjectVersion.txt"
    try:
        m = re.search(r"^m_EditorVersion:\s*(\S+)", f.read_text(encoding="utf-8-sig"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def pick_project():
    """依次取：环境变量指定的工程 > 上次连过的工程 > Projects 目录下唯一的工程。"""
    if UNITY_PROJECT:
        return Path(UNITY_PROJECT)
    st = unity_latest_status()
    if st and st["project_path"]:
        p = unity_project_dir(st["project_path"])
        if editor_version(p):
            return p
    try:
        found = [d for d in UNITY_PROJECTS.iterdir() if d.is_dir() and editor_version(d)]
    except OSError:
        found = []
    return found[0] if len(found) == 1 else None


def unity_start():
    if process_running("Unity.exe"):
        return {"ok": True, "msg": "Unity 已经开着"}
    env = app_env()
    project = pick_project()
    if project:
        ver = editor_version(project)
        exe = UNITY_EDITORS / ver / "Editor" / "Unity.exe" if ver else None
        if not (exe and exe.exists()) and Path(UNITY_EXE).exists():
            exe = Path(UNITY_EXE)  # 版本对不上时 Unity 会自己弹窗询问
        if exe and exe.exists():
            subprocess.Popen([str(exe), "-projectPath", str(project)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, env=env, creationflags=NEW_GROUP)
            return {"ok": True, "msg": f"已打开 Unity 工程 {project.name}，加载完成后桥接会自动启动"}
    if Path(UNITY_HUB).exists():
        subprocess.Popen([UNITY_HUB], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, env=env, creationflags=NEW_GROUP)
        why = "没有可直接打开的工程" if not project else f"没找到 {project.name} 对应版本的编辑器"
        return {"ok": True, "msg": f"{why}，已打开 Unity Hub"}
    return {"ok": False, "msg": f"找不到 Unity Hub：{UNITY_HUB}"}


# ---------- Blender ----------

def blender_status():
    return {"app_running": process_running(Path(BLENDER_EXE).name or "blender.exe"),
            "addon_listening": listening_pid(ADDON_PORT) is not None}


def blender_start():
    if process_running(Path(BLENDER_EXE).name):
        return {"ok": True, "msg": "Blender 已经开着"}
    if not Path(BLENDER_EXE).exists():
        return {"ok": False, "msg": f"找不到 Blender：{BLENDER_EXE}"}
    subprocess.Popen([BLENDER_EXE], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, env=app_env(), creationflags=NEW_GROUP)
    return {"ok": True, "msg": "已打开 Blender，记得在侧栏点 Connect"}


# ---------- 浏览器的出站：经 Clash ----------
# 7899 是给浏览器专用的 Clash 入口（Clash Verge 的全局扩展配置里加的 listener，proxy 指向 GLOBAL），
# 不受 Clash 全局模式影响，直连模式下也走节点；没有它时退回 7897（只在规则或全局模式下才走节点）。

def browser_proxy():
    for port in BROWSER_CLASH_PORTS:
        if listening_pid(port) is not None:
            return port
    return None


def kill_browser_edge():
    """结束用浏览器配置文件的 Edge 进程，否则配置文件会被锁住，下次启动失败。"""
    if not IS_WIN:
        return
    prof = str(BROWSER_PROFILE).replace("'", "''")
    run(["powershell.exe", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'msedge.exe' -and $_.CommandLine -and "
         f"$_.CommandLine.Contains('{prof}') }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"], timeout=20)


# ---------- MCP 服务（mcp-proxy + stdio 服务端） ----------

def mcp_start(name):
    svc = SERVICES[name]
    if listening_pid(svc["port"]) is not None:
        return {"ok": True, "msg": f"{svc['label']} MCP 服务已经在运行"}
    try:
        s = read_secret(svc["secret"])
    except Exception as e:
        return {"ok": False, "msg": f"读不到 {svc['label']} 的密钥文件：{e}"}
    exe = svc["exe"] or NODE
    needed = [(Path(NODE), "Node.js"), (PROXY_JS, "mcp-proxy"), (Path(exe), Path(exe).stem)]
    if name == "browser":
        needed.append((PLAYWRIGHT_CLI, "Playwright MCP"))
    for p, what in needed:
        if not p.exists():
            return {"ok": False, "msg": f"找不到 {what}：{p}"}
    svc["log"].parent.mkdir(parents=True, exist_ok=True)
    cwd = svc.get("cwd")
    if cwd:
        cwd.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUNBUFFERED="1", **NO_TELEMETRY)
    if name == "exec":
        # 去掉继承来的 Claude、Anthropic 相关变量：它们会改变 claude mcp serve 提供的工具，也可能带着凭证。
        # 也去掉代理变量：开启“blender 网络代理”时它们指向本机的 Clash，claude.exe 经本机地址连 Clash 就绕过了防火墙规则
        for k in [k for k in env if k.upper().startswith(("CLAUDE", "ANTHROPIC"))
                  or k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")]:
            del env[k]
    env.update(svc.get("env", {}))
    extra = []
    if name == "browser":
        for k in [k for k in env if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")]:
            del env[k]
        port = browser_proxy()
        if port:
            extra = ["--proxy-server", f"http://127.0.0.1:{port}", "--proxy-bypass", "localhost,127.0.0.1,<-loopback>"]
        kill_browser_edge()
    args = [NODE, str(PROXY_JS), "--host", "127.0.0.1", "--port", str(svc["port"]), "--server", "stream",
            "--streamEndpoint", "/" + s["PATH"], "--apiKey", s["KEY"], *svc.get("proxy_args", []),
            "--", exe, *svc["args"], *extra]
    with open(svc["log"], "wb") as log:
        subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=env, cwd=str(cwd) if cwd else None, creationflags=NO_WINDOW | NEW_GROUP)
    for _ in range(30):
        time.sleep(0.5)
        if listening_pid(svc["port"]) is not None:
            return {"ok": True, "msg": f"{svc['label']} MCP 服务已启动"}
    return {"ok": False, "msg": f"{svc['label']} MCP 服务没在 15 秒内起来，看日志"}


def mcp_stop(name):
    svc = SERVICES[name]
    pid = listening_pid(svc["port"])
    if pid is None:
        return {"ok": True, "msg": f"{svc['label']} MCP 服务本来就没运行"}
    if pid > 0:
        kill_tree(pid)
    image = svc.get("image", Path(svc["exe"]).name if svc["exe"] else None)
    if IS_WIN and image:
        run(["taskkill", "/IM", image, "/T", "/F"])
    if name == "browser":
        kill_browser_edge()
    for _ in range(20):
        time.sleep(0.25)
        if listening_pid(svc["port"]) is None:
            return {"ok": True, "msg": f"{svc['label']} MCP 服务已停止"}
    return {"ok": False, "msg": "停止失败，端口仍被占用"}


# ---------- blender 账号联网方式：直连 / 经主账号的 Clash ----------
# 改的是本账号的系统代理（浏览器、Unity Hub 读这个）和用户环境变量 HTTP(S)_PROXY（git、Unity 包管理器读这个）。
INET_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
ENV_KEY = "Environment"
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY")
NET_TEST_FILE = HOME / ".bmcp-net.json"  # 仅在非 Windows 上测试用


def _reg_get(sub, name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _reg_set(sub, name, value):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, sub) as k:
        if value is None:
            try:
                winreg.DeleteValue(k, name)
            except OSError:
                pass
        elif isinstance(value, int):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)
        else:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)


def _notify_changes():
    """让正在运行的程序重新读取代理设置；环境变量只对之后新开的程序生效。"""
    import ctypes
    from ctypes import wintypes
    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(None, 39, None, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
    wininet.InternetSetOptionW(None, 37, None, 0)  # INTERNET_OPTION_REFRESH
    result = wintypes.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 3000, ctypes.byref(result))


def net_status():
    if IS_WIN:
        enabled = _reg_get(INET_KEY, "ProxyEnable") == 1
        server = _reg_get(INET_KEY, "ProxyServer") or ""
    else:
        try:
            d = json.loads(NET_TEST_FILE.read_text())
        except Exception:
            d = {}
        enabled, server = bool(d.get("enabled")), d.get("server", "")
    m = re.fullmatch(r"(?:https?://)?127\.0\.0\.1:(\d+)", server.strip())
    if enabled and m:
        return {"mode": "clash", "port": int(m.group(1))}
    return {"mode": "other" if enabled else "direct", "port": None, "server": server if enabled else ""}


def net_set(mode, port=None):
    if mode == "clash":
        if not (port and 0 < port < 65536):
            return {"ok": False, "msg": "端口不对"}
        server = f"127.0.0.1:{port}"
        if IS_WIN:
            _reg_set(INET_KEY, "ProxyServer", server)
            _reg_set(INET_KEY, "ProxyOverride", "localhost;127.*;<local>")
            _reg_set(INET_KEY, "ProxyEnable", 1)
            for n in PROXY_VARS:
                _reg_set(ENV_KEY, n, f"http://{server}")
            _reg_set(ENV_KEY, "NO_PROXY", "localhost,127.0.0.1,::1")
            _notify_changes()
        else:
            NET_TEST_FILE.write_text(json.dumps({"enabled": True, "server": server}))
        return {"ok": True, "msg": f"Clash 代理已开启（端口 {port}）"}
    if IS_WIN:
        _reg_set(INET_KEY, "ProxyEnable", 0)
        for n in (*PROXY_VARS, "NO_PROXY"):
            _reg_set(ENV_KEY, n, None)
        _notify_changes()
    else:
        NET_TEST_FILE.write_text(json.dumps({"enabled": False, "server": ""}))
    return {"ok": True, "msg": "Clash 代理已关闭"}


def app_env():
    """启动 Unity / Blender 时用的环境变量：按本账号当前的联网方式带上或去掉代理。"""
    env = dict(os.environ, **NO_TELEMETRY)
    for n in (*PROXY_VARS, "NO_PROXY"):
        env.pop(n, None)
        env.pop(n.lower(), None)
    if IS_WIN:
        for n in (*PROXY_VARS, "NO_PROXY"):
            v = _reg_get(ENV_KEY, n)
            if v:
                env[n] = v
    return env


def status():
    out = {"ok": True}
    for name, svc in SERVICES.items():
        out[name] = {"proxy_pid": listening_pid(svc["port"]), "secret_ok": svc["secret"].exists()}
    out["blender"].update(blender_status())
    out["browser"].update({"clash_port": browser_proxy(), "installed": PLAYWRIGHT_CLI.exists()})
    out["unity"].update(unity_status())
    out["net"] = net_status()
    return out


APPS = {"blender": blender_start, "unity": unity_start}


def route(method, path):
    parts = [p for p in path.split("/") if p]
    if method == "GET" and parts == ["status"]:
        return status
    if method == "GET" and len(parts) == 2 and parts[0] == "log" and parts[1] in SERVICES:
        return lambda: {"ok": True, "log": tail(SERVICES[parts[1]]["log"])}
    if method == "POST" and len(parts) == 3 and parts[0] == "mcp" and parts[1] in SERVICES and parts[2] in ("start", "stop"):
        return (lambda: mcp_start(parts[1])) if parts[2] == "start" else (lambda: mcp_stop(parts[1]))
    if method == "POST" and len(parts) == 3 and parts[0] == "app" and parts[1] in APPS and parts[2] == "start":
        return APPS[parts[1]]
    if method == "POST" and parts == ["net", "direct"]:
        return lambda: net_set("direct")
    if method == "POST" and len(parts) == 3 and parts[:2] == ["net", "clash"] and parts[2].isdigit():
        return lambda: net_set("clash", int(parts[2]))
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "bmcp-agent"

    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method):
        if self.headers.get("Host", "") not in (f"127.0.0.1:{PORT}", f"localhost:{PORT}"):
            return self._send(403, {"ok": False, "msg": "bad host"})
        if not secrets.compare_digest(self.headers.get("X-Agent-Token", ""), TOKEN):
            return self._send(401, {"ok": False, "msg": "bad token"})
        fn = route(method, self.path.split("?")[0])
        if not fn:
            return self._send(404, {"ok": False, "msg": "not found"})
        try:
            self._send(200, fn())
        except Exception as e:
            self._send(500, {"ok": False, "msg": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self._handle("POST")


class ExclusiveServer(ThreadingHTTPServer):
    """Windows 上独占端口：默认的 SO_REUSEADDR 允许第二个进程绑定同一端口，结果两个进程同时监听。"""
    allow_reuse_address = not IS_WIN
    daemon_threads = True

    def server_bind(self):
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    try:
        srv = ExclusiveServer(("127.0.0.1", PORT), Handler)
    except OSError:
        sys.exit(0)  # 已有一个代理在运行
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(TOKEN, encoding="utf-8")
    srv.serve_forever()


if __name__ == "__main__":
    main()
