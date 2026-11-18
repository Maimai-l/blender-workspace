"""MCP 控制台 v2（运行在主账号里），按《MCP 控制台需求》和《MCP 控制台设计稿》实现。

浏览器打开 http://127.0.0.1:8765 。两个页面：连接状态、临时授权（第二阶段）。
- 外网访问：Cloudflare 隧道，一条隧道按域名分到各条线路。
- 线路：外网域名 → 本机 MCP 服务 → 下游应用。MCP 服务、Blender、Unity 的开关转交给 blender 账号里的 agent.py。
- 网络代理：blender 账号经主账号的 Clash（mihomo）上网；同时经 Clash 的控制管道读模式、节点和延迟，
  开启代理时如果当前节点不通，自动换到最快的节点。
- 接口只对本机开放，都要令牌；令牌存在本账号的 %LOCALAPPDATA%\\BlenderMCP\\panel.token。
  事件推送（SSE）用 GET /api/events?t=令牌，因为 EventSource 不能带请求头。
- 只用 Python 标准库。`--demo` 用模拟数据运行，用于在别的机器上看界面。
"""
import json
import os
import queue
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IS_WIN = os.name == "nt"
DEMO = "--demo" in sys.argv
PORT = int(os.environ.get("BMCP_PANEL_PORT", "8765"))
AGENT_PORT = int(os.environ.get("BMCP_AGENT_PORT", "8766"))
TUNNEL_ID = os.environ.get("BMCP_TUNNEL_ID", "af64fe16-f93a-4202-ad5e-1b400e791398")
TUNNEL_CRED = Path(os.environ.get("BMCP_TUNNEL_CRED", str(Path.home() / ".cloudflared" / f"{TUNNEL_ID}.json")))
DATA = Path(os.environ.get("BMCP_DATA", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "BlenderMCP")))
AGENT_TOKEN_FILE = Path(os.environ.get("BMCP_AGENT_TOKEN_FILE", r"C:\ProgramData\BlenderMCP\agent.token"))
CLOUDFLARED = (os.environ.get("BMCP_CLOUDFLARED") or shutil.which("cloudflared")
               or r"C:\Program Files (x86)\cloudflared\cloudflared.exe")
CF_IMAGE = Path(CLOUDFLARED).name
TUNNEL_LOG = DATA / "cloudflared.log"
TUNNEL_CONFIG = DATA / "cloudflared.yml"
TOKEN_FILE = DATA / "panel.token"
CLASH_PIPE = os.environ.get("BMCP_CLASH_PIPE", r"\\.\pipe\verge-mihomo")
CLASH_TEST_URL = "https://www.gstatic.com/generate_204"
GRANT_DEPLOYED = os.environ.get("BMCP_GRANT_DEPLOYED") == "1"   # 第二阶段装好临时授权网关后打开

# 4 条线路：外网域名 → MCP 服务 → 下游应用
ROUTES = [
    {"id": "blender", "name": "Blender", "host": os.environ.get("BMCP_HOST", "bmcp.maimaiqiu.work"),
     "port": int(os.environ.get("BMCP_MCP_PORT", "8080")),
     "app": {"label": "Blender 插件", "port": int(os.environ.get("BMCP_ADDON_PORT", "9876")), "image": "blender.exe"}},
    {"id": "unity", "name": "Unity", "host": os.environ.get("UMCP_HOST", "umcp.maimaiqiu.work"),
     "port": int(os.environ.get("UMCP_MCP_PORT", "8082")),
     "app": {"label": "Unity 编辑器", "port": 6400, "image": "Unity.exe"}},
    {"id": "exec", "name": "命令执行", "host": os.environ.get("XMCP_HOST", "xmcp.maimaiqiu.work"),
     "port": int(os.environ.get("XMCP_MCP_PORT", "8084")), "app": None},
    {"id": "browser", "name": "浏览器", "host": os.environ.get("WMCP_HOST", "wmcp.maimaiqiu.work"),
     "port": int(os.environ.get("WMCP_MCP_PORT", "8088")), "app": {"label": "出口", "port": None, "image": None}},
    {"id": "grant", "name": "临时授权", "host": os.environ.get("TMCP_HOST", "tmcp.maimaiqiu.work"),
     "port": int(os.environ.get("TMCP_MCP_PORT", "8086")), "app": {"label": "授权管理", "port": None, "image": None}},
]
BY_ID = {r["id"]: r for r in ROUTES}
BREAKS = {"tunnel": "外网访问", "domain": "外网域名", "service": "服务", "app": "应用", "exit": "出口"}

NO_WINDOW = 0x08000000 if IS_WIN else 0
NEW_GROUP = 0x00000200 if IS_WIN else 0
TOKEN = secrets.token_hex(32)
LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 本机请求不走系统代理


def run(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.stdout.decode("oem" if IS_WIN else "utf-8", errors="replace")
    except Exception:
        return ""


def tail(path, lines=120):
    if not path.exists():
        return "（还没有日志）"
    text = path.read_bytes()[-200_000:].decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


# ======================================================================== 环境：真实电脑 / 演示数据

class RealEnv:
    """一次快照只调用一次 netstat 和一次 tasklist。"""

    def listening(self):
        ports = {}
        for line in run(["netstat", "-ano", "-p", "TCP"]).splitlines():
            p = line.split()
            if len(p) >= 5 and p[2] in ("0.0.0.0:0", "[::]:0", "*:*") and p[4].isdigit():
                try:
                    ports[int(p[1].rsplit(":", 1)[-1])] = int(p[4])
                except ValueError:
                    pass
        return ports

    def processes(self):
        found = {}
        for line in run(["tasklist", "/FO", "CSV", "/NH"]).splitlines():
            c = [x.strip('"') for x in line.split('","')]
            if len(c) > 1 and c[1].isdigit():
                found.setdefault(c[0].strip('"').lower(), []).append(int(c[1]))
        return found

    def agent(self, path, method="GET"):
        try:
            token = AGENT_TOKEN_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return {"ok": False, "offline": True, "msg": "blender 账号的代理没运行（找不到令牌）"}
        req = urllib.request.Request(f"http://127.0.0.1:{AGENT_PORT}{path}", method=method,
                                     data=b"" if method == "POST" else None,
                                     headers={"X-Agent-Token": token, "Host": f"127.0.0.1:{AGENT_PORT}"})
        try:
            with LOCAL.open(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"ok": False, "offline": e.code == 401, "msg": f"代理拒绝了请求（{e.code}），可能需要重启代理"}
        except Exception:
            return {"ok": False, "offline": True, "msg": "blender 账号的代理没运行"}

    def probe(self, host):
        req = urllib.request.Request(f"https://{host}/mcp", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "bmcp-console"})
        try:
            urllib.request.urlopen(req, timeout=12)
            return 200
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    # ---- 隧道
    def tunnel_running(self, procs):
        return bool(procs.get(CF_IMAGE.lower()))

    def tunnel_connections(self):
        log = tail(TUNNEL_LOG, 400)
        return max(0, log.count("Registered tunnel connection") - log.count("Unregistered tunnel connection"))

    def tunnel_start(self):
        if self.tunnel_running(self.processes()):
            return {"ok": True, "msg": "外网访问已经开启"}
        if not Path(CLOUDFLARED).exists():
            return {"ok": False, "msg": f"找不到 cloudflared：{CLOUDFLARED}"}
        if not TUNNEL_CRED.exists():
            return {"ok": False, "msg": f"找不到隧道凭证：{TUNNEL_CRED}"}
        DATA.mkdir(parents=True, exist_ok=True)
        q = lambda s: json.dumps(str(s), ensure_ascii=False)  # JSON 字符串也是合法的 YAML 字符串
        lines = [f"tunnel: {q(TUNNEL_ID)}", f"credentials-file: {q(TUNNEL_CRED)}", "protocol: http2",
                 "no-autoupdate: true", "ingress:"]
        for r in ROUTES:
            if r["id"] == "grant" and not GRANT_DEPLOYED:
                continue
            lines += [f"  - hostname: {q(r['host'])}", f"    service: {q('http://127.0.0.1:%d' % r['port'])}"]
        lines.append('  - service: "http_status:404"')
        TUNNEL_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with open(TUNNEL_LOG, "wb") as log:
            subprocess.Popen([CLOUDFLARED, "tunnel", "--config", str(TUNNEL_CONFIG), "run"],
                             stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             creationflags=NO_WINDOW | NEW_GROUP)
        for _ in range(40):
            time.sleep(0.5)
            if "Registered tunnel connection" in tail(TUNNEL_LOG, 400):
                return {"ok": True, "msg": "外网访问已开启"}
            if not self.tunnel_running(self.processes()):
                return {"ok": False, "msg": "cloudflared 启动后退出，请查看外网访问日志"}
        return {"ok": False, "msg": "20 秒内未连上 Cloudflare，请查看外网访问日志"}

    def tunnel_stop(self):
        found = self.processes().get(CF_IMAGE.lower(), [])
        for pid in found:
            run(["taskkill", "/PID", str(pid), "/T", "/F"] if IS_WIN else ["kill", "-TERM", str(pid)])
        for _ in range(20):
            time.sleep(0.25)
            if not self.tunnel_running(self.processes()):
                return {"ok": True, "msg": "外网访问已关闭"}
        return {"ok": False, "msg": "关闭失败，cloudflared 仍在运行"}

    # ---- Clash 控制管道（mihomo 的 REST 接口，走命名管道，不需要密钥）
    def clash(self, method, path, body=None, timeout=10):
        data = json.dumps(body).encode() if body is not None else b""
        req = (f"{method} {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n"
               f"Content-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n").encode() + data
        t0 = time.time()
        while True:
            try:
                f = open(CLASH_PIPE, "r+b", buffering=0)
                break
            except OSError:
                if time.time() - t0 > 2:
                    raise
                time.sleep(0.2)
        with f:
            f.write(req)
            raw = b""
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                raw += chunk
                if time.time() - t0 > timeout:
                    break
        head, _, payload = raw.partition(b"\r\n\r\n")
        code = int(head.split(b" ", 2)[1])
        if b"chunked" in head.lower():
            out, rest = b"", payload
            while rest:
                size_s, _, rest = rest.partition(b"\r\n")
                size = int(size_s.split(b";")[0] or b"0", 16)
                if size == 0:
                    break
                out, rest = out + rest[:size], rest[size + 2:]
            payload = out
        if code >= 400:
            raise OSError(f"clash {method} {path}: HTTP {code}")
        return json.loads(payload) if payload.strip() else None

    def trace(self, port, host="www.gstatic.com"):
        """经 Clash 的混合端口向 host 发一个 CONNECT 并保持住，从 Clash 的连接列表读出这条连接实际走的链路
        （节点在前、组在后）；读不到返回 None。"""
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=6)
        except OSError:
            return None
        try:
            s.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode())
            s.settimeout(6)
            try:
                s.recv(256)
            except OSError:
                pass
            for _ in range(5):
                for c in (self.clash("GET", "/connections") or {}).get("connections") or []:
                    if (c.get("metadata") or {}).get("host") == host and c.get("chains"):
                        return list(c["chains"])
                time.sleep(0.2)
            return None
        finally:
            s.close()

    def proxy_works(self, port):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(
            {"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"}))
        try:
            with opener.open(CLASH_TEST_URL, timeout=8) as r:
                return r.status == 204
        except Exception:
            return False


class DemoEnv:
    """模拟一台电脑：外网开着，Unity 服务停着，用于在没有 Windows 的地方看界面。"""

    def __init__(self):
        self.tunnel = True
        self.listen = {8080: 1, 8084: 2, 9876: 3, 8765: 4, 8088: 5}
        self.procs = {"blender.exe": [3]}
        self.net = {"mode": "clash", "port": 7897}
        self.node, self.mode = "香港 01", "rule"

    def listening(self):
        return dict(self.listen)

    def processes(self):
        return dict(self.procs)

    def agent(self, path, method="GET"):
        time.sleep(0.3)
        parts = [p for p in path.split("/") if p]
        if parts == ["status"]:
            return {"ok": True, "net": dict(self.net), "unity": {"bridge_port": 6400, "reloading": False, "project": "Dungeon Escape"},
                    "blender": {}, "exec": {}, "browser": {"clash_port": 7899, "installed": True}}
        if parts[0] == "mcp":
            port = BY_ID[parts[1]]["port"]
            time.sleep(1.5)
            if parts[2] == "start":
                self.listen[port] = 9
            else:
                self.listen.pop(port, None)
            return {"ok": True, "msg": "完成"}
        if parts[0] == "app":
            time.sleep(2)
            if parts[1] == "unity":
                self.procs["unity.exe"] = [7]
                self.listen[6400] = 7
            return {"ok": True, "msg": "已打开"}
        if parts[0] == "net":
            self.net = {"mode": "clash", "port": int(parts[2])} if parts[1] == "clash" else {"mode": "direct", "port": None}
            return {"ok": True, "msg": "完成"}
        return {"ok": False, "msg": "not found"}

    def probe(self, host):
        time.sleep(0.6)
        if not self.tunnel:
            return 530
        r = next(r for r in ROUTES if r["host"] == host)
        if r["id"] == "grant":
            return 530
        return 401 if r["port"] in self.listen else 502

    def tunnel_running(self, procs):
        return self.tunnel

    def tunnel_connections(self):
        return 4 if self.tunnel else 0

    def tunnel_start(self):
        time.sleep(2)
        self.tunnel = True
        return {"ok": True, "msg": "外网访问已开启"}

    def tunnel_stop(self):
        time.sleep(1)
        self.tunnel = False
        return {"ok": True, "msg": "外网访问已关闭"}

    def clash(self, method, path, body=None, timeout=10):
        if path == "/configs":
            if method == "PATCH":
                self.mode = body["mode"]
            return {"mode": self.mode, "mixed-port": 7897}
        if path == "/rules":
            return {"rules": [{"type": "Match", "payload": "", "proxy": "节点选择"}]}
        if path == "/proxies":
            return {"proxies": {"节点选择": {"type": "Selector", "now": self.node, "all": ["香港 01", "日本 02", "新加坡 03"]},
                                "GLOBAL": {"type": "Selector", "now": "节点选择", "all": []}}}
        if path.startswith("/proxies/") and "/delay" in path:
            time.sleep(0.2)
            name = urllib.parse.unquote(path.split("/")[2])
            return {"delay": {"香港 01": 86, "日本 02": 132, "新加坡 03": 171}.get(name, 200)}
        if path.startswith("/proxies/") and method == "PUT":
            self.node = body["name"]
            return None
        return {}

    def trace(self, port, host="www.gstatic.com"):
        if port == 7899:
            return ["日本 02", "GLOBAL"]
        return [self.node, "节点选择"] if self.mode != "direct" else ["DIRECT"]

    def proxy_works(self, port):
        return True


ENV = DemoEnv() if DEMO else RealEnv()


# ======================================================================== 事件推送

class Hub:
    def __init__(self):
        self.clients = []
        self.lock = threading.Lock()

    def add(self):
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.clients.append(q)
        return q

    def remove(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, event, data):
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    self.clients.remove(q)


HUB = Hub()
STATE_LOCK = threading.Lock()
BUSY = {}             # "tunnel" / "service:<id>" / "app:<id>" / "proxy" → "starting" | "stopping" | "launching"
CHECK = {"at": None, "running": False, "routes": {}}
CLASH = {"running": False, "mode": None, "group": None, "node": None, "delay": None, "at": None}
LAST = {"snapshot": None}
EXIT = {"port": None, "chain": [], "node": None, "delay": None, "at": None}   # 浏览器出口：经哪个 Clash 入口、实际走哪个节点
WAKE = threading.Event()


GROUP_TYPES = ("Selector", "URLTest", "Fallback", "LoadBalance", "Relay")


def clash_chain():
    """按实际走向找节点：规则模式从兜底规则（MATCH）的目标开始，全局模式从 GLOBAL 开始，沿各组当前选择一直走到具体节点。
    返回 (模式, 端口, 链路列表, 可切换的组)；直连模式链路为空。"""
    conf = ENV.clash("GET", "/configs")
    mode = (conf.get("mode") or "").lower()
    px = ENV.clash("GET", "/proxies")["proxies"]
    if mode == "global":
        start = "GLOBAL"
    elif mode == "rule":
        rules = (ENV.clash("GET", "/rules") or {}).get("rules") or []
        match = [r for r in rules if (r.get("type") or "").lower() == "match"]
        start = match[-1]["proxy"] if match else None
    else:
        start = None
    chain = []
    while start and len(chain) < 8:
        chain.append(start)
        p = px.get(start) or {}
        start = p.get("now") if p.get("type") in GROUP_TYPES else None
    selectors = [g for g in chain if (px.get(g) or {}).get("type") == "Selector" and g != "GLOBAL"]
    return mode, conf.get("mixed-port"), chain, (selectors[-1] if selectors else None), px


def node_delay(node):
    q = urllib.parse.quote(node, safe="")
    try:
        return ENV.clash("GET", f"/proxies/{q}/delay?timeout=4000&url={urllib.parse.quote(CLASH_TEST_URL, safe='')}",
                         timeout=8)["delay"]
    except Exception:
        return None


def traced():
    """(模式, 端口, 链路：节点在前、组在后, 全部代理) —— 按一条真实的出站连接读出来；读不到时按规则推断。"""
    conf = ENV.clash("GET", "/configs")
    mode, port = (conf.get("mode") or "").lower(), conf.get("mixed-port") or 7897
    px = ENV.clash("GET", "/proxies")["proxies"]
    if mode == "direct":
        return mode, port, ["DIRECT"], px
    chain = ENV.trace(port)
    if not chain:
        _, _, guess, _, _ = clash_chain()
        chain = list(reversed(guess))
    return mode, port, chain, px


def refresh_clash(measure=False):
    """读 Clash 的模式和出站实际走的节点；measure=True 时再测这个节点的延迟。"""
    try:
        mode, port, chain, _ = traced()
        node = chain[0] if chain else None
        group = chain[1] if len(chain) > 1 else None
        info = {"running": True, "mode": mode, "port": port, "group": group, "node": node, "chain": chain}
        if measure and node and node != "DIRECT":
            info["delay"], info["at"] = node_delay(node), time.strftime("%H:%M:%S")
        elif CLASH.get("node") == node:
            info["delay"], info["at"] = CLASH.get("delay"), CLASH.get("at")
        else:
            info["delay"], info["at"] = None, None
        CLASH.update(info)
    except Exception:
        CLASH.update({"running": False, "mode": None, "node": None, "group": None, "delay": None, "chain": []})


def clash_best():
    """让出站换到能用的最快节点：节点的上一级是手动选择组就测速后换过去；
    是自动组（智能检测、故障转移）就让 Clash 立即重新测速，由它自己换。返回新节点名或 None。"""
    mode, port, chain, px = traced()
    if len(chain) < 2:
        return None
    group = chain[1]
    gtype = (px.get(group) or {}).get("type")
    gq = urllib.parse.quote(group, safe="")
    if gtype in ("URLTest", "Fallback", "LoadBalance"):
        try:
            ENV.clash("GET", f"/group/{gq}/delay?timeout=4000&url={urllib.parse.quote(CLASH_TEST_URL, safe='')}", timeout=15)
        except Exception:
            pass
        refresh_clash(measure=True)
        return CLASH.get("node")
    best = None
    for node in px[group].get("all", []):
        if (px.get(node) or {}).get("type") in GROUP_TYPES or node in ("DIRECT", "REJECT"):
            continue
        d = node_delay(node)
        if d and (best is None or d < best[1]):
            best = (node, d)
    if not best:
        return None
    ENV.clash("PUT", f"/proxies/{gq}", {"name": best[0]})
    refresh_clash(measure=True)
    return best[0]


def refresh_exit(port, measure=False):
    """浏览器出口：经 port 这个 Clash 入口发一条连接，读出实际走的节点。"""
    if not port:
        EXIT.update({"port": None, "chain": [], "node": None, "delay": None, "at": None})
        return
    try:
        chain = ENV.trace(port) or []
    except Exception:
        chain = []
    node = chain[0] if chain else None
    info = {"port": port, "chain": chain, "node": node}
    if measure and node and node != "DIRECT":
        info["delay"], info["at"] = node_delay(node), time.strftime("%H:%M:%S")
    elif EXIT.get("node") != node:
        info["delay"], info["at"] = None, None
    EXIT.update(info)


def snapshot():
    listen, procs = ENV.listening(), ENV.processes()
    a = ENV.agent("/status")
    agent_online = a.get("ok", False) and not a.get("offline", False)
    tunnel_on = ENV.tunnel_running(procs)
    tunnel = {"state": BUSY.get("tunnel") or ("on" if tunnel_on else "off"),
              "connections": ENV.tunnel_connections() if tunnel_on else 0}
    routes = []
    for r in ROUTES:
        svc_up = r["port"] in listen
        svc = {"port": r["port"], "state": BUSY.get("service:" + r["id"]) or ("running" if svc_up else "stopped")}
        app = None
        if r["id"] == "blender":
            running = bool(procs.get("blender.exe"))
            connected = r["app"]["port"] in listen
            app = {"label": r["app"]["label"], "port": r["app"]["port"],
                   "state": BUSY.get("app:blender") or ("connected" if connected else ("open" if running else "closed"))}
        elif r["id"] == "unity":
            au = a.get("unity") or {}
            bridge = au.get("bridge_port") or 6400
            running = bool(procs.get("unity.exe"))
            connected = running and bridge in listen
            state = "reloading" if running and au.get("reloading") else ("connected" if connected else ("open" if running else "closed"))
            app = {"label": r["app"]["label"], "port": bridge, "state": BUSY.get("app:unity") or state,
                   "project": au.get("project", "")}
        elif r["id"] == "browser":
            ab = a.get("browser") or {}
            port = ab.get("clash_port")
            if port != EXIT.get("port"):
                refresh_exit(port)
            node = EXIT.get("node")
            state = "closed" if not port else ("direct" if node in (None, "DIRECT") else "connected")
            app = {"label": "出口", "port": port, "state": state, "node": node, "delay": EXIT.get("delay"),
                   "dedicated": port == 7899, "installed": bool(ab.get("installed"))}
        elif r["id"] == "grant":
            app = {"label": "授权管理", "port": None, "state": "connected" if GRANT_DEPLOYED else "closed",
                   "active": 0, "pending": 0, "deployed": GRANT_DEPLOYED}
        for k in ("app:" + r["id"],):          # 应用连上后清掉“正在打开”
            if BUSY.get(k) == "launching" and app and app["state"] == "connected":
                BUSY.pop(k, None)
        live_break = None
        if (r["id"] == "grant" and not GRANT_DEPLOYED) or (r["id"] == "browser" and not (app or {}).get("installed")):
            live_break = "undeployed"
        elif not tunnel_on:
            live_break = "tunnel"
        elif not svc_up:
            live_break = "service"
        elif app is not None and app["state"] != "connected":
            live_break = "exit" if r["id"] == "browser" else "app"
        chk = CHECK["routes"].get(r["id"])
        routes.append({"id": r["id"], "name": r["name"], "host": r["host"], "service": svc, "app": app,
                       "live": {"ok": live_break is None, "break": live_break},
                       "check": chk})
    net = a.get("net") or {}
    proxy = {"state": BUSY.get("proxy") or ("on" if net.get("mode") == "clash" else "off"),
             "port": net.get("port") or CLASH.get("port") or 7897,
             "clash": {k: CLASH.get(k) for k in ("running", "mode", "group", "node", "delay", "at", "chain")}}
    counted = [x for x in routes if x["live"]["break"] != "undeployed"]
    online = sum(1 for x in counted if x["live"]["ok"] and (not x["check"] or x["check"]["ok"] or x["check"]["stale"]))
    return {"ok": True, "tunnel": tunnel, "routes": routes, "online": online, "total": len(counted),
            "proxy": proxy, "agent": {"online": agent_online, "msg": a.get("msg", "")},
            "check": {"at": CHECK["at"], "running": CHECK["running"]},
            "grants": {"deployed": GRANT_DEPLOYED, "active": 0, "pending": 0}}


def mark_stale(snap):
    """线路状态变了，上一次检测的结论就过时了。"""
    for r in snap["routes"]:
        c = CHECK["routes"].get(r["id"])
        if c and not c["stale"] and c["live_sig"] != json.dumps(r["live"]):
            c["stale"] = True
            r["check"] = c


def poller():
    n = 0
    while True:
        try:
            if n % 15 == 0:
                refresh_clash(measure=(n % 60 == 0))
                if EXIT.get("port"):
                    refresh_exit(EXIT["port"], measure=(n % 60 == 0))
            with STATE_LOCK:
                snap = snapshot()
                mark_stale(snap)
            if snap != LAST["snapshot"]:
                LAST["snapshot"] = snap
                HUB.publish("status.changed", snap)
        except Exception as e:
            print("poller:", type(e).__name__, e, file=sys.stderr)
        n += 1
        WAKE.wait(2)
        WAKE.clear()


def kick():
    WAKE.set()


def background(key, target, fn, label, undo=None):
    """异步动作：先登记中间态，做完推送 action.done，再刷新状态。"""
    if BUSY.get(key):
        return {"ok": False, "msg": "上一个操作还没完成"}, 409
    BUSY[key] = target
    kick()

    def work():
        try:
            res = fn()
        except Exception as e:
            res = {"ok": False, "msg": f"{type(e).__name__}: {e}"}
        if not (key.startswith("app:") and res.get("ok")):
            BUSY.pop(key, None)
        HUB.publish("action.done", {"key": key, "ok": bool(res.get("ok")), "msg": res.get("msg", label),
                                   "undo": undo if res.get("ok") else None})
        kick()
        if key.startswith("app:"):
            time.sleep(60)
            if BUSY.get(key) == "launching":
                BUSY.pop(key, None)
                HUB.publish("action.done", {"key": key, "ok": False, "msg": "应用 60 秒内没有连上，请到电脑上看一下"})
                kick()

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "target": target}, 202


# ======================================================================== 动作

def act_tunnel(body):
    on = bool(body.get("on"))
    if on:
        return background("tunnel", "starting", ENV.tunnel_start, "外网访问已开启")
    return background("tunnel", "stopping", ENV.tunnel_stop, "外网访问已关闭", undo={"path": "/api/tunnel", "body": {"on": True}})


def act_service(rid, body):
    on = bool(body.get("on"))
    if rid == "grant" and not GRANT_DEPLOYED:
        return {"ok": False, "msg": "临时授权服务还没部署"}, 409
    verb = "start" if on else "stop"
    undo = None if on else {"path": f"/api/routes/{rid}/service", "body": {"on": True}}
    return background("service:" + rid, "starting" if on else "stopping",
                      lambda: ENV.agent(f"/mcp/{rid}/{verb}", "POST"), "完成", undo)


def act_app(rid):
    if rid not in ("blender", "unity"):
        return {"ok": False, "msg": "这条线路没有可以打开的应用"}, 400
    return background("app:" + rid, "launching", lambda: ENV.agent(f"/app/{rid}/start", "POST"), "正在打开")


def check_routes():
    """一次检测全部线路：从外网访问各个域名，结合本机状态指出断在哪一段。"""
    if CHECK["running"]:
        return {"ok": False, "msg": "正在检测"}, 409
    CHECK["running"] = True
    kick()
    try:
        with STATE_LOCK:
            snap = snapshot()
        results = {}

        def one(r):
            code = ENV.probe(r["host"])
            if code in (None, 502, 530) and snap["tunnel"]["state"] == "on":
                time.sleep(2)   # 刚开启时 Cloudflare 可能还没就绪，再试一次
                code = ENV.probe(r["host"])
            if snap["tunnel"]["state"] != "on" or code == 530:
                brk, msg = "tunnel", "外网访问未开启"
            elif code is None:
                brk, msg = "domain", "连不上外网域名"
            elif code == 502 or r["service"]["state"] != "running":
                brk, msg = "service", "服务未运行"
            elif code != 401:
                brk, msg = "service", f"服务返回 {code}，没带密钥却{'被放行' if code == 200 else '没被拒绝'}"
            elif r["id"] == "browser" and r["app"]["state"] != "connected":
                brk, msg = "exit", "浏览器出口不经过节点，外网网站会被墙挡住"
            elif r["app"] is not None and r["app"]["state"] != "connected":
                brk, msg = "app", f"{r['app']['label']}未连接"
            else:
                brk, msg = None, "正常"
            results[r["id"]] = {"ok": brk is None, "break": brk, "where": BREAKS.get(brk), "msg": msg, "code": code,
                                "at": time.strftime("%H:%M:%S"), "stale": False, "live_sig": json.dumps(r["live"])}

        threads = [threading.Thread(target=one, args=(r,)) for r in snap["routes"] if r["live"]["break"] != "undeployed"]
        for t in threads:
            t.start()
        refresh_clash(measure=True)
        if EXIT.get("port"):
            refresh_exit(EXIT["port"], measure=True)
        for t in threads:
            t.join()
        CHECK["routes"] = results
        CHECK["at"] = time.strftime("%H:%M:%S")
    finally:
        CHECK["running"] = False
        kick()
    ok = sum(1 for v in results.values() if v["ok"])
    return {"ok": True, "at": CHECK["at"], "online": ok, "routes": results}, 200


def act_proxy(body):
    """开启：找到 Clash 的代理端口，确认能上网（不行就换最快的节点再试），再让 blender 账号走它。"""
    on = bool(body.get("on"))
    if BUSY.get("proxy"):
        return {"ok": False, "msg": "上一个操作还没完成"}, 409
    BUSY["proxy"] = "starting" if on else "stopping"
    kick()
    try:
        if not on:
            res = ENV.agent("/net/direct", "POST")
            return {"ok": bool(res.get("ok")), "msg": res.get("msg", "")}, 200
        refresh_clash()
        if not CLASH["running"]:
            return {"ok": False, "msg": "Clash 没在运行，请先打开 Clash Verge"}, 200
        port = CLASH.get("port") or 7897
        if CLASH.get("mode") == "direct":
            res = ENV.agent(f"/net/clash/{port}", "POST")
            return {"ok": bool(res.get("ok")), "msg": "已经走 Clash，但 Clash 现在是直连模式，实际不经过节点；"
                    "要翻墙请在 Clash 里切到规则模式"}, 200
        switched = None
        if not ENV.proxy_works(port):
            switched = clash_best()
            if not switched or not ENV.proxy_works(port):
                return {"ok": False, "msg": "Clash 的节点都连不上外网"}, 200
        res = ENV.agent(f"/net/clash/{port}", "POST")
        msg = res.get("msg", "")
        if switched:
            msg += f"；原节点不通，已换到 {switched}"
        return {"ok": bool(res.get("ok")), "msg": msg, "node": CLASH.get("node")}, 200
    finally:
        BUSY.pop("proxy", None)
        kick()


def act_clash_best():
    if not CLASH.get("running"):
        refresh_clash()
    if not CLASH.get("running"):
        return {"ok": False, "msg": "Clash 没在运行"}, 200
    node = clash_best()
    kick()
    return ({"ok": True, "node": node, "delay": CLASH.get("delay"), "msg": f"已换到 {node}"} if node
            else {"ok": False, "msg": "没有能连上的节点"}), 200


NOT_YET = ({"ok": False, "msg": "临时授权尚未部署"}, 501)


def route(method, path, body):
    parts = [p for p in path.split("/") if p][1:]
    key = "/".join(parts)
    if method == "GET" and key == "status":
        with STATE_LOCK:
            snap = snapshot()
            mark_stale(snap)
        return snap, 200
    if method == "POST" and key == "tunnel":
        return act_tunnel(body)
    if method == "POST" and key == "routes/check":
        return check_routes()
    if method == "POST" and key == "proxy":
        return act_proxy(body)
    if method == "POST" and key == "proxy/best":
        return act_clash_best()
    if method == "GET" and key == "log/tunnel":
        return {"ok": True, "log": tail(TUNNEL_LOG)}, 200
    if len(parts) == 3 and parts[0] == "routes" and parts[1] in BY_ID and method == "POST":
        if parts[2] == "service":
            return act_service(parts[1], body)
    if len(parts) == 4 and parts[0] == "routes" and parts[1] in BY_ID and parts[2:] == ["app", "launch"] and method == "POST":
        return act_app(parts[1])
    if len(parts) == 3 and parts[0] == "routes" and parts[1] in BY_ID and parts[2] == "log" and method == "GET":
        return ENV.agent(f"/log/{parts[1]}"), 200
    if parts and parts[0] in ("grants", "approvals", "logs", "rules", "fs", "sandbox"):
        return NOT_YET
    return {"ok": False, "msg": "not found"}, 404


# ======================================================================== HTTP

STATIC = Path(__file__).resolve().parent / "static"
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
        ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml"}


def static_file(rel):
    p = (STATIC / rel).resolve()
    if STATIC not in p.parents or not p.is_file():
        return None
    return p


class Handler(BaseHTTPRequestHandler):
    server_version = "bmcp-console"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def _events(self):
        q = HUB.add()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            snap = LAST["snapshot"]
            if snap:
                self.wfile.write(f"event: status.changed\ndata: {json.dumps(snap, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=15)
                except queue.Empty:
                    msg = b": ping\n\n"
                self.wfile.write(msg)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            HUB.remove(q)

    def _handle(self, method, body):
        if not self._host_ok():
            return self._send(403, {"ok": False, "msg": "bad host"})
        url = urllib.parse.urlsplit(self.path)
        path = url.path
        if method == "GET" and (path == "/" or path.startswith("/static/")):
            rel = "index.html" if path == "/" else path[len("/static/"):]
            f = static_file(urllib.parse.unquote(rel))
            if not f:
                return self._send(404, {"ok": False, "msg": "not found"})
            return self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
        if method == "GET" and path == "/api/events":
            t = urllib.parse.parse_qs(url.query).get("t", [""])[0]
            if not secrets.compare_digest(t, TOKEN):
                return self._send(401, {"ok": False, "msg": "bad token"})
            return self._events()
        if not secrets.compare_digest(self.headers.get("X-Panel-Token", ""), TOKEN):
            return self._send(401, {"ok": False, "msg": "bad token"})
        if not path.startswith("/api/"):
            return self._send(404, {"ok": False, "msg": "not found"})
        try:
            data, code = route(method, path, body)
            self._send(code, data)
        except Exception as e:
            self._send(500, {"ok": False, "msg": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._handle("GET", {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return self._send(400, {"ok": False, "msg": "bad json"})
        self._handle("POST", body if isinstance(body, dict) else {})


class ExclusiveServer(ThreadingHTTPServer):
    """Windows 上独占端口：默认的 SO_REUSEADDR 允许第二个进程绑定同一端口。"""
    allow_reuse_address = not IS_WIN
    daemon_threads = True

    def server_bind(self):
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def open_browser(token):
    webbrowser.open(f"http://127.0.0.1:{PORT}/?t={token}")


def main():
    global TOKEN
    no_browser = "--no-browser" in sys.argv
    if os.environ.get("BMCP_PANEL_TOKEN"):       # 测试用：固定令牌
        TOKEN = os.environ["BMCP_PANEL_TOKEN"]
    try:
        srv = ExclusiveServer(("127.0.0.1", PORT), Handler)
    except OSError:
        try:
            if not no_browser:
                open_browser(TOKEN_FILE.read_text(encoding="utf-8").strip())
        except OSError:
            pass
        sys.exit(0)
    if not DEMO:
        DATA.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(TOKEN, encoding="utf-8")
    threading.Thread(target=poller, daemon=True).start()
    if not no_browser:
        threading.Timer(0.5, open_browser, args=(TOKEN,)).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
