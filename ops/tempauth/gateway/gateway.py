"""临时授权网关（blender 账号运行，只用 Python 标准库）。

- 127.0.0.1:8086：对外的 MCP（经隧道 tmcp.maimaiqiu.work），地址 /t/<令牌>/mcp。工具：执行命令、查结果、取消、
  读文件、写文件、列目录、查看授权。校验令牌、有效期、次数、执行前检查、执行前确认，每次调用写一条执行记录。
- 127.0.0.1:8087：控制台用的管理接口（不经隧道），凭 C:\\ProgramData\\BlenderMCP\\tempauth.token 里的令牌调用。
- 命令和读写都交给授权助手（SYSTEM 服务，命名管道 \\\\.\\pipe\\aitemp-helper），以沙盒账号 aitemp 的身份执行。

设计见《MCP 控制台需求》第 5 节。测试：python gateway.py --demo（假助手，直接在本机跑命令，没有隔离）。
"""
import base64
import hashlib
import ipaddress
import json
import os
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

IS_WIN = os.name == "nt"
DEMO = "--demo" in sys.argv
PUBLIC_PORT = int(os.environ.get("TMCP_PORT", "8086"))
ADMIN_PORT = int(os.environ.get("TMCP_ADMIN_PORT", "8087"))
PUBLIC_BASE = os.environ.get("TMCP_BASE", "https://tmcp.maimaiqiu.work")
DATA = Path(os.environ.get("TMCP_DATA", str(Path.home() / "TempAuth")))
ADMIN_TOKEN_FILE = Path(os.environ.get("TMCP_ADMIN_TOKEN_FILE",
                                       r"C:\ProgramData\BlenderMCP\tempauth.token" if IS_WIN else str(DATA / "tempauth.token")))
PIPE = r"\\.\pipe\aitemp-helper"
VERSION = "1.1.0"

WAIT_BUDGET = 75          # Cloudflare 约 100 秒断开；一次调用最多等这么久
OUTPUT_KEEP = 64 * 1024   # 执行记录里只存输出的前 64 KB
RESTORE_WINDOW = 600      # 吊销后 10 分钟内可以恢复
MAX_BODY = 12 * 1024 * 1024

PROTECTED = [r"C:\Users\Administrator", r"C:\Users\blender", r"C:\ProgramData\BlenderMCP",
             r"D:\Projects\maa-cli", r"D:\Projects\skland"]
SYSTEM_ROOTS = [r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)", r"C:\ProgramData", r"C:\Users",
                r"C:\Recovery", r"D:\Program Files", r"D:\Program Files (x86)", r"D:\ProgramData",
                r"D:\$RECYCLE.BIN", r"D:\System Volume Information"]
READ_ONLY_OK = [r"C:\Windows", r"C:\Program Files", r"C:\Program Files (x86)", r"D:\Program Files",
                r"D:\Program Files (x86)", r"D:\ProgramData"]

ADMIN_TOKEN = secrets.token_hex(32)


def now():
    return time.time()


def hms(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S") if t else ""


SEP = "\\" if IS_WIN else "/"


def wpath(p):
    """Windows 风格的规范路径（去掉多余的 \\ 和 ..），不访问磁盘。非 Windows（--demo 测试）用 POSIX 路径。"""
    if not IS_WIN:
        return os.path.normpath(p)
    s = str(PureWindowsPath(p))
    parts = []
    for x in s.replace("/", "\\").split("\\"):
        if x in ("", "."):
            continue
        if x == "..":
            if len(parts) > 1:
                parts.pop()
            continue
        parts.append(x)
    if not parts:
        return s
    if re.fullmatch(r"[A-Za-z]:", parts[0]):
        return parts[0].upper() + "\\" + "\\".join(parts[1:])
    return "\\".join(parts)


def under(p, root):
    p, root = p.rstrip(SEP).lower(), root.rstrip(SEP).lower()
    return p == root or p.startswith(root + SEP)


def folder_problem(p):
    """不能授权的原因；能授权返回 None。助手会再按真实路径核一遍。"""
    p = wpath(p)
    if p.startswith("\\\\"):
        return "网络路径不能授权"
    if not re.match(r"^[A-Za-z]:\\", p):
        return "请填写完整路径，例如 D:\\Projects\\xxx"
    rest = [x for x in p[3:].split("\\") if x]
    if len(rest) < 2:
        return "盘符和顶层目录不能授权，请选择其下的文件夹"
    for s in PROTECTED:
        if under(p, s) or under(s, p):
            return "受保护位置"
    for s in SYSTEM_ROOTS:
        if under(p, s):
            return "系统和程序目录"
    return None


# ====================================================================== 执行前检查（只作提醒和记录；边界是沙盒账号）
RULES = [
    ("path", "路径范围", "命令和读写只能落在授权的文件夹里；出现授权文件夹以外的盘符路径、网络路径，或用 .. 走出授权文件夹，就拦截。"
     "程序目录（C:\\Windows、Program Files、D:\\ProgramData）可以读和运行。", []),
    ("protected", "受保护位置", "、".join(PROTECTED) + " 一律不可访问。", []),
    ("tasks", "计划任务与服务", "schtasks、sc create/config/start/stop、New-Service、Register-ScheduledTask 等", [
        r"\bschtasks\b", r"\bsc(\.exe)?\s+(create|config|start|stop|delete|failure|sdset|privs)\b",
        r"(?i)\b(Register|New|Set|Unregister)-ScheduledTask\b", r"(?i)\b(New|Set|Start|Stop|Remove)-Service\b"]),
    ("registry", "注册表", "reg add/delete/query/import、regedit、HKLM:/HKCU: 路径", [
        r"(?i)\breg(\.exe)?\s+(add|delete|import|export|load|unload|save|restore|copy|query)\b", r"(?i)\bregedit\b",
        r"(?i)\b(HKLM|HKCU|HKU|HKCR):", r"(?i)\bHKEY_[A-Z_]+", r"(?i)Registry::"]),
    ("account", "账号与权限", "net user/localgroup、icacls、takeown、runas、Set-Acl、*-LocalUser", [
        r"(?i)\bnet1?(\.exe)?\s+(user|localgroup|group|accounts|share|use)\b", r"(?i)\b(icacls|cacls|xcacls|takeown|runas)\b",
        r"(?i)\bSet-Acl\b", r"(?i)\b(New|Set|Remove|Enable|Disable)-LocalUser\b", r"(?i)\b(Add|Remove)-LocalGroupMember\b"]),
    ("system", "系统与防火墙", "netsh、防火墙命令、bcdedit、shutdown、wmic、Defender 设置、WMI 建进程", [
        r"(?i)\b(netsh|bcdedit|shutdown|wmic|wevtutil|vssadmin|diskpart|bcdboot|mountvol)\b",
        r"(?i)\b(Set|New|Remove|Disable|Enable)-NetFirewall\w*", r"(?i)\b(Stop|Restart)-Computer\b",
        r"(?i)\b(Set|Add|Remove)-MpPreference\b", r"(?i)\bInvoke-(WmiMethod|CimMethod)\b", r"(?i)\bWin32_Process\b",
        r"(?i)\bformat(\.com)?\s+[a-z]:"]),
    ("encoding", "编码与混淆", "powershell -EncodedCommand、certutil -decode、FromBase64String、Invoke-Expression/iex、mshta 等", [
        r"(?i)\s-e(c|nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{16,}", r"(?i)\bcertutil(\.exe)?\b.*-(decode|urlcache|decodehex)",
        r"(?i)FromBase64String", r"(?i)\bInvoke-Expression\b", r"(?i)(^|[;|&(\s])iex(\s|\(|$)", r"(?i)\b(mshta|rundll32|regsvr32|cscript|wscript)\b"]),
    ("network", "联网", "授权不允许联网时，pip/npm/yarn/conda 安装、git clone/fetch/pull/push、curl、wget、Invoke-WebRequest 等一律拦截。", [
        r"(?i)\bpip3?(\.exe)?\s+(install|download|wheel)\b", r"(?i)-m\s+pip\s+(install|download|wheel)\b",
        r"(?i)\b(npm|pnpm|yarn)(\.cmd)?\s+(install|i|ci|add|update|upgrade|dlx|create)\b", r"(?i)\bnpx(\.cmd)?\s",
        r"(?i)\bgit(\.exe)?\s+(clone|fetch|pull|push|ls-remote)\b", r"(?i)\bgit(\.exe)?\s+submodule\s+update\b",
        r"(?i)\b(curl|wget)(\.exe)?\b", r"(?i)\b(Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|bitsadmin)\b",
        r"(?i)(^|[;|&(\s])(iwr|irm)\s", r"(?i)\bconda\s+(install|create|update)\b", r"(?i)\buv\s+(pip\s+install|add|sync)\b"]),
]
RULE_RE = {k: [re.compile(x) for x in pats] for k, _, _, pats in RULES}
RULE_NAME = {k: n for k, n, _, _ in RULES}


def check_path_text(grant, text, cwd):
    """命令里出现的路径：盘符路径、/c/ 形式、网络路径、..。返回 (规则, 说明) 或 None。"""
    folders = grant["folders"]
    cands = []
    for m in re.finditer(r"(?i)(?<![\w/\\])([a-z]):[\\/][^\s\"'|&<>;,()]*", text):
        cands.append(m.group(0))
    for m in re.finditer(r"(?i)(?<![\w.~/-])/([a-z])/([^\s\"'|&<>;,()]*)", text):
        cands.append(m.group(1) + ":\\" + m.group(2))
    if re.search(r"(?<![\w])\\\\[A-Za-z0-9.$-]+\\", text):
        return ("path", "网络路径")
    for c in cands:
        p = wpath(c)
        for s in PROTECTED:
            if under(p, s):
                return ("protected", s)
        if any(under(p, f) for f in folders) or any(under(p, s) for s in READ_ONLY_OK):
            continue
        return ("path", p)
    for tok in re.split(r"[\s\"'|&<>;,()=]+", text):
        if ".." in tok and re.search(r"(^|[\\/])\.\.([\\/]|$)", tok):
            p = wpath(cwd + SEP + (tok.replace("/", "\\") if IS_WIN else tok))
            if not any(under(p, f) for f in folders):
                return ("path", "上级目录 " + tok)
    return None


def check_command(grant, command, cwd):
    hit = check_path_text(grant, command, cwd)
    if hit:
        return hit
    for key in ("tasks", "registry", "account", "system", "encoding"):
        for r in RULE_RE[key]:
            if r.search(command):
                return (key, r.pattern)
    if not grant["net"]:
        for r in RULE_RE["network"]:
            if r.search(command):
                return ("network", "授权不允许联网")
    return None


# ====================================================================== 授权助手（命名管道）
class HelperDown(Exception):
    pass


class HelperError(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


class PipeHelper:
    def call(self, req, timeout=None):
        data = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")
        f = None
        for _ in range(200):
            try:
                f = open(PIPE, "r+b", buffering=0)
                break
            except FileNotFoundError:
                raise HelperDown("授权助手没有运行（服务 AITempHelper）")
            except OSError as e:
                if getattr(e, "winerror", None) in (231, 2):   # 管道忙
                    time.sleep(0.05)
                    continue
                raise HelperDown(f"连不上授权助手：{e}")
        if f is None:
            raise HelperDown("授权助手一直忙")
        with f:
            f.write(data)
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = f.read(65536)
                if not chunk:
                    break
                buf += chunk
        if not buf:
            raise HelperDown("授权助手没有回应")
        r = json.loads(buf.decode("utf-8"))
        if not r.get("ok"):
            raise HelperError(r.get("error", "error"), r.get("msg", "助手报错"))
        return r


class FakeHelper:
    """--demo 和非 Windows 上用：直接在本机跑命令，没有隔离，只为测试网关和界面。"""

    def __init__(self):
        self.jobs, self.grants, self.lock = {}, {}, threading.Lock()

    def call(self, req, timeout=None):
        op = req["op"]
        if op == "status":
            return {"ok": True, "version": "demo", "ready": True, "error": None, "online": False, "running": None,
                    "grants": list(self.grants)}
        if op == "check_folder":
            p = folder_problem(req["folder"]) if IS_WIN else None
            if p:
                raise HelperError("folder", p)
            if not os.path.isdir(req["folder"]):
                raise HelperError("folder", "文件夹不存在：" + req["folder"])
            return {"ok": True, "real": req["folder"]}
        if op == "prepare":
            self.grants[req["grant"]] = req["folders"]
            return {"ok": True, "folders": req["folders"], "ms": 3}
        if op == "release":
            self.grants.pop(req["grant"], None)
            return {"ok": True, "errors": []}
        if op in ("reconcile", "clean", "sweep", "kill_grant"):
            if op == "kill_grant":
                for j in self.jobs.values():
                    if j["grant"] == req["grant"] and j["p"].poll() is None:
                        j["p"].kill(); j["reason"] = "revoked"
            return {"ok": True, "released": [], "killed": 0}
        if req.get("grant") not in self.grants and op in ("run", "fs"):
            raise HelperError("unknown_grant", "unknown")
        if op == "run":
            with self.lock:
                if any(j["p"].poll() is None for j in self.jobs.values()):
                    raise HelperError("busy", "上一条命令还在运行")
                sh = req.get("shell", "cmd")
                args = ["bash", "-c", req["command"]] if (sh == "bash" or not IS_WIN) else \
                    (["powershell", "-NoProfile", "-Command", req["command"]] if sh == "powershell" else ["cmd", "/d", "/c", req["command"]])
                p = subprocess.Popen(args, cwd=req.get("cwd") or self.grants[req["grant"]][0], stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                jid = "j" + uuid.uuid4().hex[:12]
                job = {"p": p, "grant": req["grant"], "out": b"", "t0": now(), "t1": None, "reason": ""}

                def rd():
                    for chunk in iter(lambda: p.stdout.read1(4096), b""):
                        job["out"] += chunk
                    p.wait()
                    job["t1"] = now()

                threading.Thread(target=rd, daemon=True).start()
                timer = threading.Timer(req.get("timeout", 600), lambda: (p.poll() is None) and (p.kill(), job.update(reason="timeout")))
                timer.daemon = True
                timer.start()
                self.jobs[jid] = job
                return {"ok": True, "job": jid, "pid": p.pid}
        if op == "poll":
            j = self.jobs.get(req["job"])
            if not j:
                raise HelperError("unknown_job", "没有这个任务")
            t_end = now() + req.get("wait", 0) / 1000
            while j["t1"] is None and now() < t_end:
                time.sleep(0.1)
            st = "running" if j["t1"] is None else ("done" if not j["reason"] else ("timeout" if j["reason"] == "timeout" else "killed"))
            return {"ok": True, "state": st, "exit": j["p"].returncode if j["t1"] else -1, "reason": j["reason"],
                    "seconds": round((j["t1"] or now()) - j["t0"], 1), "output": j["out"].decode("utf-8", "replace"),
                    "bytes": len(j["out"])}
        if op == "kill":
            j = self.jobs.get(req["job"])
            if j and j["p"].poll() is None:
                j["p"].kill(); j["reason"] = req.get("reason", "killed")
            return {"ok": True}
        if op == "fs":
            import base64
            path = req["path"]
            a = req["action"]
            if a == "list":
                if os.path.isfile(path):
                    st = os.stat(path)
                    return {"ok": True, "file": {"p": os.path.basename(path), "s": st.st_size, "m": hms(st.st_mtime)}}
                if not os.path.isdir(path):
                    raise HelperError("not_found", "不存在：" + path)
                items = []
                for root, dirs, files in os.walk(path):
                    depth = os.path.relpath(root, path).count(os.sep) + (0 if root == path else 1)
                    for d in sorted(dirs):
                        items.append({"p": os.path.relpath(os.path.join(root, d), path) + "\\", "d": True, "link": False})
                    for f in sorted(files):
                        st = os.stat(os.path.join(root, f))
                        items.append({"p": os.path.relpath(os.path.join(root, f), path), "s": st.st_size, "m": hms(st.st_mtime)})
                    if depth + 1 >= req.get("depth", 1):
                        dirs[:] = []
                return {"ok": True, "items": items[:1000], "more": len(items) > 1000}
            if a == "read":
                if not os.path.isfile(path):
                    raise HelperError("not_found", "文件不存在：" + path)
                with open(path, "rb") as f:
                    f.seek(req.get("offset", 0))
                    b = f.read(req.get("length", 1 << 20))
                    size = os.path.getsize(path)
                    return {"ok": True, "data": base64.b64encode(b).decode(), "size": size, "eof": f.tell() >= size}
            if a == "write":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                b = base64.b64decode(req["data"])
                with open(path, "ab" if req.get("append") else "wb") as f:
                    f.write(b)
                return {"ok": True, "bytes": len(b)}
        if op == "verify":
            return {"ok": True, "passed": True, "checks": [["（演示）沙盒自检", True, "demo"]], "fixed": [], "ms": 5}
        raise HelperError("op", "不支持：" + op)


HELPER = FakeHelper() if (DEMO or not IS_WIN) else PipeHelper()


# ====================================================================== 事件
class Hub:
    def __init__(self):
        self.qs, self.lock = [], threading.Lock()

    def add(self):
        q = queue.Queue(maxsize=500)
        with self.lock:
            self.qs.append(q)
        return q

    def remove(self, q):
        with self.lock:
            if q in self.qs:
                self.qs.remove(q)

    def publish(self, event, data):
        with self.lock:
            for q in list(self.qs):
                try:
                    q.put_nowait((event, data))
                except queue.Full:
                    pass


HUB = Hub()


# ====================================================================== 存储
class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS grants (
            id TEXT PRIMARY KEY, name TEXT, folders TEXT, token_hash TEXT UNIQUE, created REAL, expires REAL,
            lim INTEGER, used INTEGER DEFAULT 0, net INTEGER, confirm INTEGER, revoked_at REAL, released INTEGER DEFAULT 0,
            minutes INTEGER);
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, grant_id TEXT, at REAL, op TEXT, target TEXT, result TEXT, note TEXT,
            seconds REAL, cwd TEXT, shell TEXT, exit INTEGER, output TEXT, task TEXT);
        CREATE INDEX IF NOT EXISTS logs_grant ON logs(grant_id, id);
        CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(grants)").fetchall()}
        if "browser" not in cols:
            self.db.execute("ALTER TABLE grants ADD COLUMN browser INTEGER DEFAULT 0")
        if "logins" not in cols:
            self.db.execute("ALTER TABLE grants ADD COLUMN logins TEXT DEFAULT '[]'")

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            return cur.lastrowid

    def meta(self, k, v=None):
        if v is None:
            r = self.q("SELECT v FROM meta WHERE k=?", (k,))
            return json.loads(r[0]["v"]) if r else None
        self.x("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (k, json.dumps(v, ensure_ascii=False)))


STORE = Store(DATA / ("tempauth-demo.db" if DEMO else "tempauth.db"))


def grant_state(g, t=None):
    t = t or now()
    if g["revoked_at"]:
        return "revoked"
    if g["lim"] >= 0 and g["used"] >= g["lim"]:
        return "used"
    if g["expires"] <= t:
        return "expired"
    return "active"


def grant_view(g):
    t = now()
    st = grant_state(g, t)
    v = {"id": g["id"], "name": g["name"], "folders": json.loads(g["folders"]), "created": g["created"],
         "expires": g["expires"], "minutes": g["minutes"], "limit": g["lim"], "used": g["used"], "net": bool(g["net"]),
         "confirm": bool(g["confirm"]), "state": st, "remaining": max(0, int(g["expires"] - t)),
         "restorable": st == "revoked" and not g["released"] and g["expires"] > t and t - g["revoked_at"] < RESTORE_WINDOW}
    v["created_hm"], v["expires_at"] = hms(g["created"]), datetime.fromtimestamp(g["expires"]).strftime("%m-%d %H:%M")
    v["browser"] = bool(g["browser"])
    v["logins"] = json.loads(g["logins"] or "[]")
    v["browser_ops"] = STORE.q("SELECT COUNT(*) n FROM logs WHERE grant_id=? AND op NOT IN ('run','read','write','list')",
                               (g["id"],))[0]["n"] if g["browser"] else 0
    return v


def get_grant(gid):
    r = STORE.q("SELECT * FROM grants WHERE id=?", (gid,))
    return r[0] if r else None


def grant_by_token(token):
    h = hashlib.sha256(token.encode()).hexdigest()
    r = STORE.q("SELECT * FROM grants WHERE token_hash=?", (h,))
    return r[0] if r else None


def gdict(g):
    d = dict(g)
    d["folders"] = json.loads(g["folders"])
    d["net"] = bool(g["net"])
    return d


def log_view(r, full=False):
    v = {k: r[k] for k in ("id", "grant_id", "op", "target", "result", "note", "seconds", "cwd", "shell", "exit", "task")}
    v["at"], v["time"] = r["at"], hms(r["at"])
    v["full_time"] = datetime.fromtimestamp(r["at"]).strftime("%Y-%m-%d %H:%M:%S")
    if full:
        v["output"] = r["output"] or ""
    return v


def add_log(grant_id, op, target, result, note="", seconds=0.0, cwd="", shell="", exit_code=None, output="", task=""):
    lid = STORE.x("INSERT INTO logs (grant_id, at, op, target, result, note, seconds, cwd, shell, exit, output, task) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (grant_id, now(), op, target[:4000], result, note, round(seconds, 2), cwd, shell, exit_code,
                   (output or "")[:OUTPUT_KEEP], task))
    row = STORE.q("SELECT * FROM logs WHERE id=?", (lid,))[0]
    HUB.publish("log.created", log_view(row))
    return lid


def update_log(lid, **kw):
    if "output" in kw:
        kw["output"] = (kw["output"] or "")[:OUTPUT_KEEP]
    if "seconds" in kw:
        kw["seconds"] = round(kw["seconds"], 2)
    sets = ", ".join(f"{k}=?" for k in kw)
    STORE.x(f"UPDATE logs SET {sets} WHERE id=?", (*kw.values(), lid))
    row = STORE.q("SELECT * FROM logs WHERE id=?", (lid,))[0]
    HUB.publish("log.updated", log_view(row))


def blocked_today():
    t0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    return STORE.q("SELECT COUNT(*) n FROM logs WHERE result='blocked' AND at>=?", (t0,))[0]["n"]


def counts():
    active = sum(1 for g in STORE.q("SELECT * FROM grants WHERE released=0") if grant_state(g) == "active")
    with TASK_LOCK:
        pending = sum(1 for t in TASKS.values() if t["state"] == "approval")
    with LOGIN_LOCK:
        pending += sum(1 for r in LOGINREQ.values() if r["state"] in ("pending", "active"))
    return {"active": active, "pending": pending, "blocked_today": blocked_today()}


def publish_counts():
    HUB.publish("counts", counts())


def publish_grant(gid):
    g = get_grant(gid)
    if g:
        HUB.publish("grant.changed", grant_view(g))
    publish_counts()


# ====================================================================== 助手调用（助手重启后自动重新准备授权）
def helper_for(g, req, timeout=None):
    try:
        return HELPER.call(req, timeout)
    except HelperError as e:
        if e.code != "unknown_grant":
            raise
    HELPER.call({"op": "prepare", "grant": g["id"], "folders": json.loads(g["folders"])})
    return HELPER.call(req, timeout)


def helper_status():
    try:
        r = HELPER.call({"op": "status"})
        return {"ok": bool(r.get("ready")), "version": r.get("version"), "msg": r.get("error") or ""}
    except (HelperDown, HelperError, OSError) as e:
        return {"ok": False, "version": None, "msg": str(e)}


# ====================================================================== 任务：执行前确认 → 排队 → 执行
TASKS = {}
TASK_LOCK = threading.Lock()
RUNQ = queue.Queue()
CURRENT = {"task": None}


def new_task(g, command, shell, cwd, timeout):
    t = {"id": "t" + uuid.uuid4().hex[:10], "grant": g["id"], "command": command, "shell": shell, "cwd": cwd,
         "timeout": timeout, "state": "new", "created": now(), "job": None, "exit": None, "output": "", "note": "",
         "seconds": 0.0, "log": None, "done": threading.Event(), "started": None}
    with TASK_LOCK:
        TASKS[t["id"]] = t
        if len(TASKS) > 500:
            for k in sorted(TASKS, key=lambda k: TASKS[k]["created"])[:100]:
                if TASKS[k]["done"].is_set():
                    TASKS.pop(k, None)
    return t


def approval_view(t):
    g = get_grant(t["grant"])
    return {"id": t["id"], "grant_id": t["grant"], "grant": g["name"] if g else "", "command": t["command"],
            "shell": t["shell"], "cwd": t["cwd"], "at": t["created"], "time": hms(t["created"])}


def finish(t, state, note="", exit_code=None, output="", seconds=0.0, result=None):
    t.update(state=state, note=note, exit=exit_code, output=output, seconds=seconds)
    if t["log"]:
        update_log(t["log"], result=result or state, note=note, exit=exit_code, output=output, seconds=seconds)
    t["done"].set()


def take_count(gid):
    """原子地占一次次数；授权不可用或次数用完时返回原因。"""
    with STORE.lock:
        g = get_grant(gid)
        st = grant_state(g)
        if st != "active":
            return {"revoked": "授权已被收回", "expired": "授权已到期", "used": "次数已用完"}[st]
        STORE.x("UPDATE grants SET used=used+1 WHERE id=?", (gid,))
    publish_grant(gid)
    return None


def refund(gid):
    STORE.x("UPDATE grants SET used=MAX(used-1, 0) WHERE id=?", (gid,))
    publish_grant(gid)


def enqueue(t):
    reason = take_count(t["grant"])
    if reason:
        t["log"] = t["log"] or add_log(t["grant"], "run", t["command"], "denied", reason, cwd=t["cwd"], shell=t["shell"], task=t["id"])
        finish(t, "denied", reason, result="denied")
        return
    t["state"] = "queued"
    if not t["log"]:
        t["log"] = add_log(t["grant"], "run", t["command"], "running", "排队中", cwd=t["cwd"], shell=t["shell"], task=t["id"])
    else:
        update_log(t["log"], result="running", note="排队中")
    RUNQ.put(t)


def worker():
    while True:
        t = RUNQ.get()
        if t["state"] != "queued":
            continue
        g = get_grant(t["grant"])
        if grant_state(g) in ("revoked", "expired"):   # 用完的照样执行：这条已经占了次数
            refund(t["grant"])
            finish(t, "cancelled", "授权已失效，没有执行", result="denied")
            continue
        CURRENT["task"] = t
        t["state"], t["started"] = "running", now()
        update_log(t["log"], result="running", note="执行中")
        try:
            r = helper_for(g, {"op": "run", "grant": g["id"], "command": t["command"], "shell": t["shell"], "cwd": t["cwd"],
                               "online": bool(g["net"]), "timeout": t["timeout"]})
            t["job"] = r["job"]
            while True:
                p = HELPER.call({"op": "poll", "job": t["job"], "wait": 30000})
                t["output"] = p.get("output", "")
                if p["state"] != "running":
                    break
            reason = p.get("reason") or ""
            if p["state"] == "done":
                finish(t, "done", f"退出码 {p['exit']}", p["exit"], p.get("output", ""), p.get("seconds", 0), result="ok")
            elif p["state"] == "timeout":
                finish(t, "timeout", f"超过 {t['timeout']} 秒，已结束", p["exit"], p.get("output", ""), p.get("seconds", 0), result="timeout")
            else:
                why = {"revoked": "授权被收回，已中止", "expired": "授权到期，已中止", "cancelled": "对方取消",
                       "stopped": "助手停止"}.get(reason, "已中止")
                finish(t, "killed", why, p["exit"], p.get("output", ""), p.get("seconds", 0), result="cancelled")
        except (HelperDown, HelperError, OSError) as e:
            if not t["job"]:
                refund(t["grant"])
            finish(t, "error", f"没能执行：{e}", result="error")
        finally:
            CURRENT["task"] = None


def wait_task(t, budget):
    t["done"].wait(max(0.0, budget))


def task_text(t):
    st = t["state"]
    if st == "approval":
        return (f"等待电脑主人确认（任务 {t['id']}）。主人允许后命令会自动执行；稍后用 get_command_result 查结果。", False)
    if st in ("queued", "running"):
        return (f"命令仍在运行（任务 {t['id']}，已运行 {int(now() - (t['started'] or now()))} 秒）。"
                f"用 get_command_result 取结果。\n--- 目前的输出 ---\n{tail_text(t['output'])}", False)
    if st == "done":
        return (f"退出码 {t['exit']}，用时 {t['seconds']} 秒\n{t['output']}", t["exit"] != 0)
    if st == "timeout":
        return (f"超时，已结束（{t['note']}）\n{t['output']}", True)
    if st == "killed":
        return (f"已中止：{t['note']}\n{t['output']}", True)
    if st == "denied":
        return (f"没有执行：{t['note']}", True)
    if st == "cancelled":
        return (f"没有执行：{t['note']}", True)
    return (f"出错：{t['note']}", True)


def tail_text(s, n=8000):
    return s if len(s) <= n else "…\n" + s[-n:]


# ====================================================================== 授权：签发、吊销、恢复、到期
def make_prompt(g, url):
    folders = json.loads(g["folders"])
    if not folders:
        return make_browser_prompt(g, url)
    lim = "不限" if g["lim"] < 0 else f"{g['lim']} 次"
    exp = datetime.fromtimestamp(g["expires"]).strftime("%Y-%m-%d %H:%M")
    lines = [
        "我给你开了一个临时 MCP 连接，可以在我电脑（Windows）的指定文件夹里执行命令、读写文件"
        + ("，并使用一个浏览器。" if g["browser"] else "。"),
        f"连接地址：{url}",
        "把它添加为自定义连接器（远程 MCP 服务，不需要登录）。地址里带着令牌，请不要转给别人。",
        "",
        "这次授权的边界：",
        f"- 用途：{g['name']}",
        "- 文件夹：" + "、".join(folders) + "（只能在这里面读写；命令默认在第一个文件夹里执行）",
        f"- 到期：{exp}，之后地址失效",
        f"- 次数：{lim}（执行命令和写文件计次；读文件、列目录、被拦截或被拒绝的调用不计）",
        "- 联网：" + ("允许，经代理出网，pip、npm、git 都能用" if g["net"] else "不允许，下载和安装都会失败"),
        "- 执行前确认：" + ("需要，每条命令要我在电脑上点允许，可能要等一会" if g["confirm"] else "不需要"),
        "- 会被拦截：访问授权文件夹以外的位置、计划任务和服务、注册表、账号和权限、系统和防火墙设置、编码混淆的命令"
        + ("" if g["net"] else "、下载安装"),
        "",
        "环境：命令默认用 cmd，也可以选 powershell 或 bash（Git Bash）。Python 是只读的 conda base，"
        "要装包请先在文件夹里建虚拟环境：python -m venv .venv，再用 .venv\\Scripts\\python -m pip install …。"
        "Node 和 npm、git、Blender（blender -b）都能用。命令最长等 75 秒返回，没跑完会给任务编号，用 get_command_result 取结果。",
    ]
    if g["browser"]:
        lines += ["", *browser_prompt_lines(g)]
    return "\n".join(lines)


def browser_prompt_lines(g):
    logins = json.loads(g["logins"] or "[]")
    return [
        "浏览器：",
        "- 允许，经代理访问外网；浏览器操作不计次数，不需要我确认",
        "- 已带登录：" + ("、".join(logins) if logins else "无"),
        "- 不能打开本机或局域网地址、本地文件，不能上传本地文件",
        "- 需要登录其他网站，或遇到验证码、邮件验证时，调用 request_login，由我在电脑上登录；不要向我索要密码或验证码",
    ]


def make_browser_prompt(g, url):
    exp = datetime.fromtimestamp(g["expires"]).strftime("%Y-%m-%d %H:%M")
    return "\n".join([
        "我给你开了一个临时 MCP 连接，可以使用我电脑上的一个浏览器。",
        f"连接地址：{url}",
        "把它添加为自定义连接器（远程 MCP 服务，不需要登录）。地址里带着令牌，请不要转给别人。",
        "",
        f"用途：{g['name']}",
        f"到期：{exp}，之后地址失效",
        "",
        *browser_prompt_lines(g),
    ])


def issue(body):
    folders = body.get("folders") or []
    if isinstance(folders, str):
        folders = [folders]
    folders = [wpath(f.strip().strip('"')) for f in folders if f and f.strip()]
    browser = bool(body.get("browser"))
    if not folders and not browser:
        return {"ok": False, "msg": "请选择文件夹或浏览器"}, 400
    logins = [d for d in (body.get("logins") or []) if isinstance(d, str)] if browser else []
    saved = {x["domain"] for x in saved_logins()}
    missing = [d for d in logins if d not in saved]
    if missing:
        return {"ok": False, "msg": "以下网站没有保存的登录：" + "、".join(missing)}, 400
    seen, reals = set(), []
    for f in folders:
        p = folder_problem(f) if IS_WIN else None
        if p:
            return {"ok": False, "msg": f"{f}：{p}"}, 400
        try:
            real = HELPER.call({"op": "check_folder", "folder": f})["real"]
        except HelperError as e:
            return {"ok": False, "msg": str(e)}, 400
        except HelperDown as e:
            return {"ok": False, "msg": str(e)}, 503
        if real.lower() not in seen:
            seen.add(real.lower())
            reals.append(real)
    minutes = int(body.get("minutes") or 60)
    if minutes not in (30, 60, 240, 1440):
        minutes = max(5, min(minutes, 7 * 1440))
    lim = int(body.get("limit") if body.get("limit") is not None else 20)
    lim = -1 if lim < 0 else max(1, min(lim, 100000))
    name = (body.get("name") or "").strip()[:60] or (Path(reals[0].replace("\\", "/")).name or reals[0] if reals else "浏览器")
    names = {r["name"] for r in STORE.q("SELECT name FROM grants")}
    base, i = name, 2
    while name in names:
        name, i = f"{base} {i}", i + 1
    gid = "g" + secrets.token_hex(5)
    token = secrets.token_urlsafe(32)
    t = now()
    if reals:
        try:
            HELPER.call({"op": "prepare", "grant": gid, "folders": reals})
        except HelperError as e:
            return {"ok": False, "msg": str(e)}, 400
        except HelperDown as e:
            return {"ok": False, "msg": str(e)}, 503
    STORE.x("INSERT INTO grants (id, name, folders, token_hash, created, expires, lim, used, net, confirm, minutes, browser, logins) "
            "VALUES (?,?,?,?,?,?,?,0,?,?,?,?,?)",
            (gid, name, json.dumps(reals, ensure_ascii=False), hashlib.sha256(token.encode()).hexdigest(), t,
             t + minutes * 60, lim, 1 if body.get("net") else 0, 1 if body.get("confirm") else 0, minutes,
             1 if browser else 0, json.dumps(logins)))
    STORE.meta("last_issue", {"folders": reals, "minutes": minutes, "limit": lim, "net": bool(body.get("net")),
                              "confirm": bool(body.get("confirm")), "browser": browser, "logins": logins})
    g = get_grant(gid)
    url = f"{PUBLIC_BASE}/t/{token}/mcp"
    publish_grant(gid)
    return {"ok": True, "grant": grant_view(g), "url": url, "prompt": make_prompt(g, url)}, 200


def cancel_tasks(gid, why, states=("approval", "queued")):
    with TASK_LOCK:
        ts = [t for t in TASKS.values() if t["grant"] == gid and t["state"] in states]
    for t in ts:
        was_approval = t["state"] == "approval"
        t["state"] = "cancelled"
        if t["log"]:
            update_log(t["log"], result="denied", note=why)
        else:
            t["log"] = add_log(gid, "run", t["command"], "denied", why, cwd=t["cwd"], shell=t["shell"], task=t["id"])
        t["note"] = why
        t["done"].set()
        ev = APPROVED.pop(t["id"], None)
        if ev:
            ev.set()
        if was_approval:
            HUB.publish("approval.resolved", {"id": t["id"], "decision": "cancelled"})
            publish_counts()


def revoke(gid):
    g = get_grant(gid)
    if not g:
        return {"ok": False, "msg": "授权不存在"}, 404
    t0 = now()
    if not g["revoked_at"]:
        STORE.x("UPDATE grants SET revoked_at=? WHERE id=?", (t0, gid))
    try:
        HELPER.call({"op": "kill_grant", "grant": gid, "reason": "revoked"})
    except (HelperDown, HelperError) as e:
        print("kill_grant:", e, file=sys.stderr)
    cancel_tasks(gid, "授权已被收回")
    close_browser(gid)
    cancel_logins(gid, "授权已被收回")
    publish_grant(gid)
    return {"ok": True, "grant": grant_view(get_grant(gid)), "ms": int((now() - t0) * 1000)}, 200


def restore(gid):
    g = get_grant(gid)
    if not g:
        return {"ok": False, "msg": "授权不存在"}, 404
    v = grant_view(g)
    if v["state"] != "revoked":
        return {"ok": False, "msg": "该授权未被吊销"}, 400
    if not v["restorable"]:
        return {"ok": False, "msg": "已超过恢复期限：仅可在吊销后 10 分钟内且未到期时恢复"}, 400
    STORE.x("UPDATE grants SET revoked_at=NULL WHERE id=?", (gid,))
    publish_grant(gid)
    return {"ok": True, "grant": grant_view(get_grant(gid))}, 200


def ticker():
    """每 3 秒：到期或用完的授权中止命令；不再可恢复的授权撤掉文件夹权限、删组。"""
    last_states = {}
    while True:
        time.sleep(3)
        try:
            t = now()
            any_live = False
            for g in STORE.q("SELECT * FROM grants WHERE released=0"):
                st = grant_state(g, t)
                if st == "active":
                    any_live = True
                if last_states.get(g["id"]) not in (None, st):
                    publish_grant(g["id"])
                last_states[g["id"]] = st
                if st == "expired":
                    try:
                        HELPER.call({"op": "kill_grant", "grant": g["id"], "reason": "expired"})
                    except Exception:
                        pass
                    cancel_tasks(g["id"], "授权已到期")
                if st in ("expired", "revoked"):
                    close_browser(g["id"])
                    cancel_logins(g["id"], "授权已失效")
                if st == "used":
                    cancel_tasks(g["id"], "次数已用完", ("approval",))
                with TASK_LOCK:
                    busy = any(x["grant"] == g["id"] and x["state"] in ("queued", "running") for x in TASKS.values())
                done_running = not busy
                release = (st == "expired") or (st == "used" and done_running) or \
                          (st == "revoked" and (t - g["revoked_at"] >= RESTORE_WINDOW or g["expires"] <= t))
                if st == "revoked" and g["expires"] > t and t - g["revoked_at"] < RESTORE_WINDOW:
                    any_live = True
                if release:
                    try:
                        HELPER.call({"op": "release", "grant": g["id"], "folders": json.loads(g["folders"])})
                        STORE.x("UPDATE grants SET released=1 WHERE id=?", (g["id"],))
                        publish_grant(g["id"])
                        # 仅浏览器的授权：截图、PDF 等输出放在 TempAuth\browser\<id>，授权结束后删掉
                        shutil.rmtree(BROWSER_DIR / g["id"], ignore_errors=True)
                    except (HelperDown, HelperError, OSError) as e:
                        print("release:", e, file=sys.stderr)
            expire_logins()
            if not any_live and STORE.meta("cleaned") is not True:
                try:
                    HELPER.call({"op": "clean"})
                    STORE.meta("cleaned", True)
                except Exception:
                    pass
            elif any_live:
                STORE.meta("cleaned", False)
        except Exception as e:
            print("ticker:", e, file=sys.stderr)


def reconcile():
    keep = [g["id"] for g in STORE.q("SELECT id FROM grants WHERE released=0")]
    try:
        HELPER.call({"op": "reconcile", "keep": keep})
    except Exception as e:
        print("reconcile:", e, file=sys.stderr)


# ====================================================================== MCP 工具
TOOL_NAMES = {"run_command", "get_command_result", "cancel_command", "read_file", "write_file", "list_directory"}
TOOLS = [
    {"name": "run_command",
     "description": "Run a shell command as the sandbox user, inside the granted folder on the owner's Windows PC. "
                    "Waits up to 75 s; if the command is still running (or waiting for the owner's approval) you get a task id - "
                    "call get_command_result with it. Counts against the grant's call limit.",
     "inputSchema": {"type": "object", "properties": {
         "command": {"type": "string", "description": "The command line."},
         "shell": {"type": "string", "enum": ["cmd", "powershell", "bash"], "description": "Default cmd. bash is Git Bash."},
         "cwd": {"type": "string", "description": "Working directory: a path inside the granted folder, absolute or relative to it. Default: the granted folder."},
         "timeout_seconds": {"type": "integer", "description": "Kill the command after this many seconds (default 600, max 3600)."}},
         "required": ["command"]}},
    {"name": "get_command_result",
     "description": "Get the output of a command started with run_command. Waits up to wait_seconds (default 60, max 75) for it to finish.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "wait_seconds": {"type": "integer"}},
                     "required": ["task_id"]}},
    {"name": "cancel_command", "description": "Stop a running or queued command.",
     "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "read_file",
     "description": "Read a file inside the granted folder. Text is returned as UTF-8 (default); use encoding=base64 for binary files. "
                    "Reads at most 1 MB per call; use offset to continue.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Absolute, or relative to the granted folder."},
         "offset": {"type": "integer", "description": "Byte offset (default 0)."},
         "length": {"type": "integer", "description": "Bytes to read (default 262144, max 1048576)."},
         "encoding": {"type": "string", "enum": ["text", "base64"]}}, "required": ["path"]}},
    {"name": "write_file",
     "description": "Create or overwrite a file inside the granted folder (parent folders are created). Counts against the call limit.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string"}, "content": {"type": "string"},
         "encoding": {"type": "string", "enum": ["text", "base64"], "description": "text = UTF-8 (default)."},
         "append": {"type": "boolean"}}, "required": ["path", "content"]}},
    {"name": "list_directory",
     "description": "List a folder inside the granted folder (default: the granted folder). depth 1-3.",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}, "depth": {"type": "integer"}}}},
    {"name": "grant_info", "description": "Show this grant's folder, expiry, remaining calls, network and approval settings.",
     "inputSchema": {"type": "object", "properties": {}}},
]
OP_OF = {"run_command": "run", "write_file": "write", "read_file": "read", "list_directory": "list"}


def resolve(g, p):
    folders = json.loads(g["folders"])
    p = (p or "").strip().strip('"')
    if not p or p == ".":
        return folders[0]
    if not IS_WIN:
        return wpath(p if p.startswith("/") else folders[0] + "/" + p)
    if re.match(r"^[A-Za-z]:[\\/]", p) or p.startswith("\\\\"):
        return wpath(p)
    if re.match(r"^/[a-zA-Z]/", p):
        return wpath(p[1] + ":\\" + p[3:])
    return wpath(folders[0] + "\\" + p)


def path_problem(g, p):
    for s in PROTECTED:
        if under(p, s):
            return ("protected", s)
    if not any(under(p, f) for f in json.loads(g["folders"])):
        return ("path", p)
    return None


def text_result(s, err=False):
    return {"content": [{"type": "text", "text": s}], "isError": bool(err)}


def tools_for(g):
    out = []
    if json.loads(g["folders"]):
        out += [t for t in TOOLS if t["name"] != "grant_info"]
    if g["browser"]:
        out += browser_tools(g) + LOGIN_TOOLS
    out.append(next(t for t in TOOLS if t["name"] == "grant_info"))
    return out


def call_tool(g, name, args):
    """返回 MCP tools/call 的 result。每次调用一条执行记录。"""
    gid = g["id"]
    st = grant_state(g)
    if name.startswith("browser_") or name in ("request_login", "check_login"):
        if not g["browser"]:
            return text_result("这次授权不包含浏览器。", True)
        if st != "active" and name != "check_login":
            why = {"revoked": "授权已被主人收回", "expired": "授权已到期", "used": "次数已用完"}[st]
            add_log(gid, WEB_OPS.get(name, name), str(args.get("url") or ""), "denied", why)
            return text_result(why + "，这个地址不能再用了。", True)
        if name == "request_login":
            return tool_request_login(g, args)
        if name == "check_login":
            return tool_check_login(g, args)
        return call_browser(g, name, args)
    if name in TOOL_NAMES and not json.loads(g["folders"]):
        return text_result("这次授权不包含文件夹。", True)
    op = OP_OF.get(name)
    if name == "grant_info":
        v = grant_view(g)
        lim = "不限" if v["limit"] < 0 else f"{v['used']}/{v['limit']}"
        return text_result(f"用途：{v['name']}\n文件夹：{'、'.join(v['folders'])}\n状态：{v['state']}\n到期：{v['expires_at']}"
                           f"（剩 {v['remaining'] // 60} 分钟）\n已用次数：{lim}\n联网：{'允许' if v['net'] else '不允许'}\n"
                           f"执行前确认：{'需要' if v['confirm'] else '不需要'}")
    if name in ("get_command_result", "cancel_command"):
        with TASK_LOCK:
            t = TASKS.get(str(args.get("task_id", "")))
        if not t or t["grant"] != gid:
            return text_result("没有这个任务编号", True)
        if name == "cancel_command":
            if t["state"] in ("approval", "queued"):
                was = t["state"] == "approval"
                t["state"], t["note"] = "cancelled", "对方取消"
                if t["log"]:
                    update_log(t["log"], result="cancelled", note="对方取消")
                t["done"].set()
                if was:
                    HUB.publish("approval.resolved", {"id": t["id"], "decision": "cancelled"}); publish_counts()
            elif t["state"] == "running" and t["job"]:
                HELPER.call({"op": "kill", "job": t["job"], "reason": "cancelled"})
                wait_task(t, 10)
            s, err = task_text(t)
            return text_result(s, err)
        wait_task(t, min(max(int(args.get("wait_seconds") or 60), 0), WAIT_BUDGET))
        s, err = task_text(t)
        return text_result(s, err)
    if not op:
        return text_result("没有这个工具：" + name, True)
    target = str(args.get("command") if op == "run" else args.get("path") or ".")
    if st != "active":
        why = {"revoked": "授权已被主人收回", "expired": "授权已到期", "used": "次数已用完"}[st]
        add_log(gid, op, target, "denied", why)
        return text_result(why + "，这个地址不能再用了。", True)

    if op == "run":
        command = str(args.get("command") or "").strip()
        shell = args.get("shell") or "cmd"
        if shell not in ("cmd", "powershell", "bash"):
            return text_result("shell 只能是 cmd、powershell 或 bash", True)
        if not command:
            return text_result("命令是空的", True)
        cwd = resolve(g, args.get("cwd"))
        pp = path_problem(g, cwd)
        if pp:
            add_log(gid, "run", command, "blocked", f"{RULE_NAME[pp[0]]}：工作目录 {cwd}", cwd=cwd, shell=shell)
            publish_counts()
            return text_result(f"已拦截（{RULE_NAME[pp[0]]}）：工作目录必须在授权文件夹里。", True)
        hit = check_command(gdict(g), command, cwd)
        if hit:
            add_log(gid, "run", command, "blocked", f"{RULE_NAME[hit[0]]}" + (f"：{hit[1]}" if hit[0] in ("path", "protected") else ""),
                    cwd=cwd, shell=shell)
            publish_counts()
            return text_result(f"已拦截（执行前检查：{RULE_NAME[hit[0]]}），不计次数。", True)
        timeout = max(5, min(int(args.get("timeout_seconds") or 600), 3600))
        t = new_task(g, command, shell, cwd, timeout)
        t0 = now()
        if g["confirm"]:
            t["state"] = "approval"
            ev = APPROVED[t["id"]] = threading.Event()
            t["log"] = add_log(gid, "run", command, "pending", "等待确认", cwd=cwd, shell=shell, task=t["id"])
            HUB.publish("approval.created", approval_view(t))
            publish_counts()
            ev.wait(WAIT_BUDGET)
            if t["state"] == "approval":
                s, err = task_text(t)
                return text_result(s, err)
        else:
            enqueue(t)
        wait_task(t, WAIT_BUDGET - (now() - t0))
        s, err = task_text(t)
        return text_result(s, err)

    path = resolve(g, args.get("path"))
    pp = path_problem(g, path)
    if pp:
        add_log(gid, op, path, "blocked", f"{RULE_NAME[pp[0]]}" + (f"：{pp[1]}" if pp[0] == "protected" else ""))
        publish_counts()
        return text_result(f"已拦截（{RULE_NAME[pp[0]]}）：只能访问授权的文件夹。", True)
    t0 = now()
    try:
        if op == "list":
            depth = max(1, min(int(args.get("depth") or 1), 3))
            r = helper_for(g, {"op": "fs", "grant": gid, "action": "list", "path": path, "depth": depth})
            if "file" in r:
                f = r["file"]
                text = f"{f['p']}  {f['s']} 字节  {f['m']}"
                n = 1
            else:
                lines = [it["p"] + ("" if it.get("d") else f"  {it['s']}") for it in r["items"]]
                n = len(lines)
                text = "\n".join(lines) + ("\n…（超过 1000 项，没列完）" if r.get("more") else "") if lines else "（空文件夹）"
            add_log(gid, "list", path, "ok", f"{n} 项", now() - t0)
            return text_result(text)
        if op == "read":
            import base64
            length = max(1, min(int(args.get("length") or 262144), 1 << 20))
            r = helper_for(g, {"op": "fs", "grant": gid, "action": "read", "path": path, "offset": int(args.get("offset") or 0), "length": length})
            data = base64.b64decode(r["data"])
            add_log(gid, "read", path, "ok", size_text(len(data)), now() - t0)
            more = "" if r["eof"] else f"\n…（文件共 {r['size']} 字节，还没读完；用 offset={int(args.get('offset') or 0) + len(data)} 继续）"
            if args.get("encoding") == "base64":
                return text_result(r["data"] + more)
            try:
                return text_result(data.decode("utf-8") + more)
            except UnicodeDecodeError:
                return text_result("这个文件不是 UTF-8 文本。用 encoding=base64 读取，或用命令查看。", True)
        if op == "write":
            import base64
            content = args.get("content")
            if not isinstance(content, str):
                return text_result("content 要是字符串", True)
            data = content if args.get("encoding") == "base64" else base64.b64encode(content.encode("utf-8")).decode()
            if len(data) > 8 * 1024 * 1024:
                return text_result("一次最多写 6 MB", True)
            reason = take_count(gid)
            if reason:
                add_log(gid, "write", path, "denied", reason)
                return text_result(reason, True)
            try:
                r = helper_for(g, {"op": "fs", "grant": gid, "action": "write", "path": path, "data": data, "append": bool(args.get("append"))})
            except (HelperError, HelperDown):
                refund(gid)
                raise
            add_log(gid, "write", path, "ok", size_text(r["bytes"]), now() - t0)
            return text_result(f"已写入 {r['bytes']} 字节：{path}")
    except HelperError as e:
        result = "blocked" if e.code in ("denied", "path") else "error"
        add_log(gid, op, path, result, ("沙盒拒绝：" if e.code == "denied" else "") + str(e)[:200], now() - t0)
        publish_counts()
        return text_result(str(e), True)
    except HelperDown as e:
        add_log(gid, op, path, "error", str(e), now() - t0)
        return text_result(str(e), True)
    return text_result("没有这个工具", True)


APPROVED = {}


def size_text(n):
    return f"{n} B" if n < 1024 else (f"{n / 1024:.1f} KB" if n < 1 << 20 else f"{n / (1 << 20):.1f} MB")


def decide(tid, allow):
    with TASK_LOCK:
        t = TASKS.get(tid)
    if not t or t["state"] != "approval":
        return {"ok": False, "msg": "该请求已处理"}, 409
    HUB.publish("approval.resolved", {"id": tid, "decision": "allow" if allow else "deny"})
    if allow:
        enqueue(t)
    else:
        t["state"], t["note"] = "denied", "主人拒绝"
        update_log(t["log"], result="denied", note="")
        t["done"].set()
    ev = APPROVED.pop(tid, None)
    if ev:
        ev.set()
    publish_counts()
    return {"ok": True}, 200



# ====================================================================== 浏览器授权
# 每条带浏览器的授权一个 Playwright MCP（stdio，无界面 Edge，配置只在内存里）。网关是它的客户端：
# 只把下面允许的工具转给对方 AI；写入登录信息时网关自己调用 browser_run_code_unsafe，这个工具不给对方。
PLAYWRIGHT_CLI = Path(os.environ.get("TMCP_PLAYWRIGHT", r"C:\Program Files\BlenderMCP\node\node_modules\@playwright\mcp\cli.js"))
NODE = os.environ.get("TMCP_NODE", r"D:\Program Files\node.EXE")
BROWSER_PROXY = os.environ.get("TMCP_BROWSER_PROXY", "http://127.0.0.1:7899")
BLOCKED_ORIGINS = ";".join(f"{s}://{h}" for s in ("http", "https") for h in ("127.0.0.1", "localhost", "[::1]", "0.0.0.0"))
LOGIN_DIR = DATA / "logins"
BROWSER_DIR = DATA / "browser"
LOGIN_TIMEOUT = 600        # 登录请求 10 分钟没处理就取消
WEB_OPS = {
    "browser_navigate": "打开网页", "browser_navigate_back": "返回", "browser_tabs": "标签页", "browser_find": "查找",
    "browser_snapshot": "读取页面", "browser_take_screenshot": "截图", "browser_click": "点击", "browser_type": "输入",
    "browser_fill_form": "填写表单", "browser_select_option": "选择", "browser_press_key": "按键", "browser_hover": "悬停",
    "browser_wait_for": "等待", "browser_drag": "拖动", "browser_handle_dialog": "对话框", "browser_console_messages": "控制台",
    "browser_close": "关闭页面", "browser_resize": "调整窗口", "browser_pdf_save": "保存 PDF",
    "request_login": "登录", "check_login": "登录",
}
NO_WINDOW = 0x08000000 if IS_WIN else 0
NEW_GROUP = 0x00000200 if IS_WIN else 0


class StdioMCP:
    """一个 stdio 上的 MCP 服务端子进程（换行分隔的 JSON-RPC）。"""

    def __init__(self, args, cwd=None, log=None):
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log or subprocess.DEVNULL,
                                  cwd=cwd, creationflags=NO_WINDOW | NEW_GROUP)
        self.lock, self.pending, self.next_id = threading.Lock(), {}, 1
        threading.Thread(target=self._read, daemon=True).start()
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "tempauth", "version": VERSION}}, 60)
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, msg):
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        with self.lock:
            self.p.stdin.write(data)
            self.p.stdin.flush()

    def _read(self):
        for line in self.p.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if "method" in msg and "id" in msg:      # 服务端发来的请求（如 roots/list）：不支持
                try:
                    self._send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "not supported"}})
                except OSError:
                    pass
                continue
            q = self.pending.pop(msg.get("id"), None)
            if q:
                q.put(msg)
        for q in list(self.pending.values()):
            q.put({"error": {"message": "浏览器进程已退出"}})

    def call(self, method, params, timeout=80):
        with self.lock:
            mid = self.next_id
            self.next_id += 1
        q = queue.Queue()
        self.pending[mid] = q
        self._send({"jsonrpc": "2.0", "id": mid, "method": method, "params": params})
        try:
            r = q.get(timeout=timeout)
        except queue.Empty:
            self.pending.pop(mid, None)
            raise TimeoutError("浏览器 %d 秒没有响应" % timeout)
        if "error" in r:
            raise RuntimeError(r["error"].get("message", "浏览器出错"))
        return r["result"]

    def alive(self):
        return self.p.poll() is None

    def close(self):
        if self.p.poll() is None:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", str(self.p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
            else:
                self.p.kill()


BROWSERS = {}
BROWSER_LOCK = threading.Lock()
TOOL_SCHEMAS = {}


def browser_args(gid, state_file, outdir, headless=True, proxy=True):
    args = [NODE, str(PLAYWRIGHT_CLI), "--browser", "msedge", "--isolated", "--output-dir", str(outdir), "--ignore-roots",
            "--codegen", "none", "--no-webmcp", "--caps", "pdf", "--idle-timeout", "0", "--blocked-origins", BLOCKED_ORIGINS]
    if headless:
        args.append("--headless")
    if proxy:
        # 回环地址也走代理：请求到了代理节点上，碰不到这台电脑的本机服务
        args += ["--proxy-server", BROWSER_PROXY, "--proxy-bypass", "<-loopback>"]
    if state_file:
        args += ["--storage-state", str(state_file)]
    return args


def grant_outdir(g):
    folders = json.loads(g["folders"])
    d = Path(folders[0]) / "downloads" if folders else BROWSER_DIR / g["id"] / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def browser_for(g):
    gid = g["id"]
    with BROWSER_LOCK:
        b = BROWSERS.get(gid)
        if b and b.alive():
            return b
        state = merged_state(json.loads(g["logins"] or "[]"))
        state_file = None
        if state["cookies"] or state["origins"]:
            d = BROWSER_DIR / gid
            d.mkdir(parents=True, exist_ok=True)
            state_file = d / "state.json"
            state_file.write_text(json.dumps(state), encoding="utf-8")
        BROWSER_DIR.mkdir(parents=True, exist_ok=True)
        log = open(BROWSER_DIR / f"{gid}.log", "ab")
        b = StdioMCP(browser_args(gid, state_file, grant_outdir(g)), cwd=str(grant_outdir(g)), log=log)
        if state_file:
            try:
                state_file.unlink()          # Playwright 启动时已读入；不在磁盘上留登录信息
            except OSError:
                pass
        if not TOOL_SCHEMAS:
            for t in b.call("tools/list", {}, 60)["tools"]:
                TOOL_SCHEMAS[t["name"]] = t
        BROWSERS[gid] = b
        return b


def close_browser(gid):
    with BROWSER_LOCK:
        b = BROWSERS.pop(gid, None)
    if b:
        b.close()


def browser_tools(g):
    if not TOOL_SCHEMAS:
        try:
            browser_for(g)
        except Exception as e:
            print("browser_tools:", e, file=sys.stderr)
    return [TOOL_SCHEMAS[n] for n in WEB_OPS if n in TOOL_SCHEMAS]


def url_problem(url):
    """本机、局域网和本地文件拦下；返回原因或 None。"""
    try:
        u = urlsplit(url.strip())
    except ValueError:
        return "网址无效"
    if u.scheme not in ("http", "https", ""):
        return "仅支持 http、https 网址"
    host = (u.hostname or "").strip("[]").lower()
    if not host and u.scheme:
        return "网址无效"
    if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost") or host.endswith(".local"):
        return "本机地址"
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_unspecified or ip.is_reserved:
            return "本机或局域网地址"
    except ValueError:
        pass
    return None


def web_target(name, args):
    if name == "browser_navigate":
        return str(args.get("url", ""))
    if name in ("browser_click", "browser_hover", "browser_select_option"):
        return str(args.get("element") or args.get("ref") or "")
    if name == "browser_type":
        return f"{args.get('element') or args.get('ref') or ''}（{len(str(args.get('text', '')))} 个字符）"
    if name == "browser_fill_form":
        return f"{len(args.get('fields') or [])} 个字段"
    if name == "browser_press_key":
        return str(args.get("key", ""))
    if name == "browser_find":
        return str(args.get("text") or args.get("query") or "")
    if name in ("browser_take_screenshot", "browser_pdf_save"):
        return str(args.get("filename") or "")
    return ""


def call_browser(g, name, args):
    gid = g["id"]
    if name not in WEB_OPS:
        return text_result("这个浏览器工具不提供：" + name, True)
    op, target, t0 = WEB_OPS[name], web_target(name, args), now()
    if name == "browser_navigate":
        why = url_problem(str(args.get("url", "")))
        if why:
            add_log(gid, op, target, "blocked", why)
            publish_counts()
            return text_result(f"已拦截：{why}。", True)
    try:
        b = browser_for(g)
        r = b.call("tools/call", {"name": name, "arguments": args}, WAIT_BUDGET)
    except Exception as e:
        add_log(gid, op, target, "error", str(e)[:200], now() - t0)
        if isinstance(e, TimeoutError):
            return text_result("浏览器在 75 秒内没有完成这一步，页面可能还在加载；稍后用 browser_snapshot 查看。", True)
        return text_result("浏览器出错：" + str(e), True)
    err = bool(r.get("isError"))
    note = ""
    if err:
        texts = [c.get("text", "") for c in r.get("content", []) if c.get("type") == "text"]
        note = (texts[0] if texts else "")[:200]
    add_log(gid, op, target, "error" if err else "ok", note, now() - t0)
    return r


# ---------------------------------------------------------------------- 保存的登录（按网站域名）
SLD2 = {"com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn", "ac.cn", "co.uk", "org.uk", "ac.uk", "co.jp", "ne.jp", "or.jp",
        "com.hk", "com.tw", "com.au", "net.au", "co.kr", "com.sg", "com.br", "co.in"}


def site_of(host):
    host = (host or "").lstrip(".").lower().strip("[]")
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    return ".".join(parts[-3:]) if ".".join(parts[-2:]) in SLD2 else ".".join(parts[-2:])


def login_file(domain):
    if not re.fullmatch(r"[a-z0-9.-]{1,120}", domain or ""):
        raise ValueError("域名不对")
    return LOGIN_DIR / f"{domain}.json"


def saved_logins(with_use=False):
    out = []
    if LOGIN_DIR.exists():
        for f in sorted(LOGIN_DIR.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            v = {"domain": d["domain"], "title": d.get("title", ""), "saved": d.get("saved", 0),
                 "saved_at": datetime.fromtimestamp(d.get("saved", 0)).strftime("%m-%d %H:%M"),
                 "stale": now() - d.get("saved", 0) > 7 * 86400}
            if with_use:
                v["in_use"] = sum(1 for g in STORE.q("SELECT * FROM grants WHERE released=0 AND browser=1")
                                  if grant_state(g) == "active" and d["domain"] in json.loads(g["logins"] or "[]"))
            out.append(v)
    return out


def merged_state(domains):
    cookies, origins = [], []
    for d in domains:
        try:
            x = json.loads(login_file(d).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cookies += x.get("cookies", [])
        origins += x.get("origins", [])
    return {"cookies": cookies, "origins": origins}


def filter_state(state, domain):
    def ok(host):
        return site_of(host) == domain
    cookies = [c for c in state.get("cookies", []) if ok(c.get("domain", ""))]
    origins = [o for o in state.get("origins", []) if ok(urlsplit(o.get("origin", "")).hostname or "")]
    return {"cookies": cookies, "origins": origins}


def delete_login(domain):
    try:
        f = login_file(domain)
    except ValueError as e:
        return {"ok": False, "msg": str(e)}, 400
    if f.exists():
        f.unlink()
    HUB.publish("logins.changed", {})
    return {"ok": True}, 200


def save_login(body):
    """控制台在用户点“完成”或“保存登录”后调用：state 是登录窗口的 storageState，domains 是用户选中的网站。"""
    state = body.get("state") or {}
    domains = [d for d in (body.get("domains") or []) if isinstance(d, str)]
    titles = body.get("titles") or {}
    if not domains:
        return {"ok": False, "msg": "未选择网站"}, 400
    LOGIN_DIR.mkdir(parents=True, exist_ok=True)
    picked = {"cookies": [], "origins": []}
    for d in domains:
        part = filter_state(state, d)
        picked["cookies"] += part["cookies"]
        picked["origins"] += part["origins"]
        if body.get("save", True):
            try:
                f = login_file(d)
            except ValueError:
                continue
            f.write_text(json.dumps({"domain": d, "title": titles.get(d, ""), "saved": now(), **part}, ensure_ascii=False),
                         encoding="utf-8")
    HUB.publish("logins.changed", {})
    rid = body.get("request")
    if rid:
        with LOGIN_LOCK:
            r = LOGINREQ.get(rid)
        if not r or r["state"] not in ("pending", "active"):
            return {"ok": False, "msg": "该登录请求已结束"}, 409
        g = get_grant(r["grant"])
        if body.get("save", True):          # 授权的浏览器重启时也带上
            have = json.loads(g["logins"] or "[]")
            STORE.x("UPDATE grants SET logins=? WHERE id=?", (json.dumps(sorted(set(have) | set(domains))), g["id"]))
            g = get_grant(g["id"])
            publish_grant(g["id"])
        try:
            if not DEMO:
                inject_state(g, picked)
        except Exception as e:
            return {"ok": False, "msg": "写入浏览器失败：" + str(e)}, 500
        finish_login(r, "logged_in", "已保存" if body.get("save", True) else "未保存")
    return {"ok": True, "domains": domains}, 200


def run_code_arg():
    t = TOOL_SCHEMAS.get("browser_run_code_unsafe") or {}
    props = (t.get("inputSchema") or {}).get("properties") or {}
    return "code" if "code" in props or not props else next(iter(props))


def inject_state(g, state):
    b = browser_for(g)
    code = ("async (page) => { const s = %s; if (s.cookies.length) await page.context().addCookies(s.cookies); "
            "try { await page.reload({ waitUntil: 'domcontentloaded', timeout: 20000 }); } catch (e) {} return page.url(); }"
            % json.dumps(state))
    r = b.call("tools/call", {"name": "browser_run_code_unsafe", "arguments": {run_code_arg(): code}}, 60)
    if r.get("isError"):
        raise RuntimeError(" ".join(c.get("text", "") for c in r.get("content", []))[:200])


def current_url(g):
    b = browser_for(g)
    r = b.call("tools/call", {"name": "browser_run_code_unsafe", "arguments": {run_code_arg(): "async (page) => page.url()"}}, 20)
    for c in r.get("content", []):
        m = re.search(r"https?://[^\s\"'`]+", c.get("text", ""))
        if m:
            return m.group(0)
    return ""


# ---------------------------------------------------------------------- 登录请求（request_login）
LOGINREQ = {}
LOGIN_LOCK = threading.Lock()

LOGIN_TOOLS = [
    {"name": "request_login",
     "description": "Ask the PC owner to sign in to a website for this browser. Use it when a page asks for a login, a "
                    "verification code or an email link. Do not ask for or type passwords or codes yourself. The owner signs "
                    "in in a window on their own desktop; the login is then added to this browser and the page is reloaded. "
                    "Waits up to 75 s. Returns status: logged_in | pending (with request_id; call check_login) | declined | cancelled.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string", "description": "The login page. Default: the current page."},
         "reason": {"type": "string", "description": "One sentence shown to the owner, e.g. why the login is needed."}},
         "required": ["reason"]}},
    {"name": "check_login", "description": "Wait for a login request started with request_login.",
     "inputSchema": {"type": "object", "properties": {
         "request_id": {"type": "string"},
         "wait_seconds": {"type": "integer", "description": "Default 60, max 75."}}, "required": ["request_id"]}},
]


def login_view(r):
    g = get_grant(r["grant"])
    return {"id": r["id"], "grant_id": r["grant"], "grant": g["name"] if g else "", "url": r["url"], "domain": r["domain"],
            "reason": r["reason"], "state": r["state"], "at": r["created"], "time": hms(r["created"])}


def login_result(r):
    st = r["state"]
    if st in ("pending", "active"):
        return text_result(json.dumps({"status": "pending", "request_id": r["id"],
                                       "message": "等待电脑主人登录；用 check_login 继续等待。"}, ensure_ascii=False))
    msg = {"logged_in": "已登录，浏览器已带上登录状态并刷新了页面，继续原来的步骤。",
           "declined": "电脑主人拒绝了这次登录。告诉用户这一步需要登录。",
           "cancelled": "登录请求已取消（主人取消、超时或授权失效）。"}[st]
    return text_result(json.dumps({"status": st, "request_id": r["id"], "message": msg}, ensure_ascii=False), st != "logged_in")


def tool_request_login(g, args):
    url = str(args.get("url") or "").strip()
    if not url:
        try:
            url = current_url(g)
        except Exception:
            url = ""
    if not url:
        return text_result("没有给登录页地址，当前也没有打开的页面。", True)
    why = url_problem(url)
    if why:
        add_log(g["id"], "登录", url, "blocked", why)
        return text_result(f"已拦截：{why}。", True)
    r = {"id": "l" + uuid.uuid4().hex[:10], "grant": g["id"], "url": url, "domain": site_of(urlsplit(url).hostname or ""),
         "reason": str(args.get("reason") or "")[:200], "state": "pending", "created": now(), "done": threading.Event()}
    r["log"] = add_log(g["id"], "登录", r["domain"], "pending", r["reason"][:100])
    with LOGIN_LOCK:
        LOGINREQ[r["id"]] = r
    HUB.publish("login.created", login_view(r))
    publish_counts()
    r["done"].wait(WAIT_BUDGET)
    return login_result(r)


def tool_check_login(g, args):
    with LOGIN_LOCK:
        r = LOGINREQ.get(str(args.get("request_id", "")))
    if not r or r["grant"] != g["id"]:
        return text_result("没有这个登录请求", True)
    r["done"].wait(min(max(int(args.get("wait_seconds") or 60), 0), WAIT_BUDGET))
    return login_result(r)


def finish_login(r, state, note=""):
    with LOGIN_LOCK:
        if r["state"] not in ("pending", "active"):
            return
        r["state"] = state
    update_log(r["log"], result={"logged_in": "done", "declined": "denied", "cancelled": "cancelled"}[state],
               note=note, seconds=now() - r["created"])
    r["done"].set()
    HUB.publish("login.resolved", {"id": r["id"], "state": state})
    publish_counts()


def login_action(rid, action):
    with LOGIN_LOCK:
        r = LOGINREQ.get(rid)
    if not r or r["state"] not in ("pending", "active"):
        return {"ok": False, "msg": "该登录请求已结束"}, 409
    if action == "start":
        r["state"] = "active"
        HUB.publish("login.changed", login_view(r))
    elif action == "decline":
        finish_login(r, "declined")
    elif action == "cancel":
        finish_login(r, "cancelled", "")
    else:
        return {"ok": False, "msg": "不支持的操作"}, 400
    return {"ok": True, "request": login_view(r)}, 200


def cancel_logins(gid, why):
    with LOGIN_LOCK:
        rs = [r for r in LOGINREQ.values() if r["grant"] == gid and r["state"] in ("pending", "active")]
    for r in rs:
        finish_login(r, "cancelled", why)


def expire_logins():
    with LOGIN_LOCK:
        rs = [r for r in LOGINREQ.values() if r["state"] in ("pending", "active") and now() - r["created"] > LOGIN_TIMEOUT]
    for r in rs:
        finish_login(r, "cancelled", "等待超过 10 分钟")


def mcp_instructions(g):
    v = grant_view(g)
    text = f"这是电脑主人给你的临时授权（{v['name']}），{v['expires_at']} 到期。"
    if v["folders"]:
        text += (f"只能在 {'、'.join(v['folders'])} 里执行命令和读写文件。Windows；命令默认 cmd，可选 powershell、bash。"
                 "Python 是只读的 conda，装包先建 venv。" + ("命令可以联网（经代理）。" if v["net"] else "命令不能联网。")
                 + ("每条命令要主人确认。" if v["confirm"] else ""))
    if v["browser"]:
        text += ("本授权包含浏览器，经代理访问外网，不能打开本机或局域网地址、本地文件。"
                 "遇到登录页、验证码或邮件验证时，调用 request_login，由电脑主人在自己的窗口中完成登录；不要索要或输入密码、验证码。"
                 "返回 logged_in 后，浏览器已带上登录状态并回到原页面。"
                 + ("本次授权已带上以下网站的登录状态：" + "、".join(v["logins"]) + "。" if v["logins"] else ""))
    return text


def handle_rpc(g, msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if mid is None:
        return None   # 通知
    if method == "initialize":
        pv = params.get("protocolVersion") or "2025-06-18"
        res = {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}},
               "serverInfo": {"name": "tempauth", "version": VERSION}, "instructions": mcp_instructions(g)}
    elif method == "ping":
        res = {}
    elif method == "tools/list":
        res = {"tools": tools_for(get_grant(g["id"]))}
    elif method == "tools/call":
        try:
            res = call_tool(get_grant(g["id"]), params.get("name", ""), params.get("arguments") or {})
        except Exception as e:
            res = text_result(f"网关出错：{type(e).__name__}: {e}", True)
    elif method in ("resources/list", "prompts/list"):
        res = {method.split("/")[0]: []}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


# ====================================================================== 管理接口
def fs_list(path):
    if not path:
        drives = [f"{d}:\\" for d in "CDEFGH" if os.path.isdir(f"{d}:\\")] if IS_WIN else [str(Path.home())]
        return {"ok": True, "path": "", "parent": None, "dirs": [{"name": d, "path": d, "ok": False, "reason": "盘符", "enter": True} for d in drives]}, 200
    p = wpath(path) if IS_WIN else path
    try:
        names = sorted(os.listdir(p), key=str.lower)
    except OSError as e:
        return {"ok": False, "msg": f"打不开：{e.strerror or e}"}, 400
    dirs = []
    for n in names:
        full = os.path.join(p, n)
        if not os.path.isdir(full) or n.startswith("$") or n == "System Volume Information":
            continue
        why = folder_problem(full) if IS_WIN else None
        dirs.append({"name": n, "path": full, "ok": why is None, "reason": why or "",
                     "enter": why in (None, "盘符和顶层目录不能授权，请选择其下的文件夹")})
    parent = str(Path(p).parent) if Path(p).parent != Path(p) else ""
    return {"ok": True, "path": p, "parent": parent, "dirs": dirs[:500]}, 200


def admin_route(method, path, query, body):
    parts = [x for x in path.split("/") if x][1:]   # 去掉 admin
    key = "/".join(parts)
    if method == "GET" and key == "state":
        c = counts()
        return {"ok": True, "version": VERSION, "helper": helper_status(), "public_base": PUBLIC_BASE, **c,
                "last_issue": STORE.meta("last_issue")}, 200
    if key == "grants":
        if method == "POST":
            return issue(body)
        rows = STORE.q("SELECT * FROM grants ORDER BY created DESC LIMIT 200")
        vs = [grant_view(r) for r in rows]
        if query.get("status", "active") == "active":
            vs = [v for v in vs if v["state"] == "active" or v["restorable"]]
        return {"ok": True, "grants": vs, "last_issue": STORE.meta("last_issue")}, 200
    if len(parts) == 3 and parts[0] == "grants" and method == "POST":
        if parts[2] == "revoke":
            return revoke(parts[1])
        if parts[2] == "restore":
            return restore(parts[1])
    if key == "approvals" and method == "GET":
        with TASK_LOCK:
            ts = sorted([t for t in TASKS.values() if t["state"] == "approval"], key=lambda t: t["created"])
        return {"ok": True, "approvals": [approval_view(t) for t in ts]}, 200
    if len(parts) == 2 and parts[0] == "approvals" and method == "POST":
        return decide(parts[1], bool(body.get("allow")))
    if key == "logs" and method == "GET":
        lim = max(1, min(int(query.get("limit") or 100), 500))
        sql, args = "SELECT * FROM logs", []
        conds = []
        if query.get("grant"):
            conds.append("grant_id=?"); args.append(query["grant"])
        if query.get("before"):
            conds.append("id<?"); args.append(int(query["before"]))
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        rows = STORE.q(sql + " ORDER BY id DESC LIMIT ?", (*args, lim))
        names = {r["id"]: r["name"] for r in STORE.q("SELECT id, name FROM grants")}
        out = []
        for r in rows:
            v = log_view(r)
            v["grant"] = names.get(r["grant_id"], "")
            out.append(v)
        return {"ok": True, "logs": out}, 200
    if len(parts) == 2 and parts[0] == "logs" and method == "GET":
        rows = STORE.q("SELECT * FROM logs WHERE id=?", (int(parts[1]),))
        if not rows:
            return {"ok": False, "msg": "记录不存在"}, 404
        return {"ok": True, "log": log_view(rows[0], True)}, 200
    if key == "rules" and method == "GET":
        return {"ok": True, "rules": [{"key": k, "name": n, "desc": d} for k, n, d, _ in RULES],
                "blocked_today": blocked_today(), "protected": PROTECTED}, 200
    if key == "sandbox/verify" and method == "POST":
        try:
            r = HELPER.call({"op": "verify"})
            return {"ok": True, "passed": r["passed"], "checks": r["checks"], "fixed": r.get("fixed", []), "ms": r.get("ms")}, 200
        except (HelperDown, HelperError) as e:
            return {"ok": False, "msg": str(e)}, 503
    if key == "logins" and method == "GET":
        return {"ok": True, "logins": saved_logins(with_use=True)}, 200
    if len(parts) == 3 and parts[0] == "logins" and parts[2] == "delete" and method == "POST":
        return delete_login(parts[1])
    if key == "logins/save" and method == "POST":
        return save_login(body)
    if key == "logins/requests" and method == "GET":
        with LOGIN_LOCK:
            rs = sorted([r for r in LOGINREQ.values() if r["state"] in ("pending", "active")], key=lambda r: r["created"])
        return {"ok": True, "requests": [login_view(r) for r in rs]}, 200
    if len(parts) == 3 and parts[:2] == ["logins", "requests"] and method == "POST":
        return login_action(parts[2], body.get("action", ""))
    if key == "fs" and method == "GET":
        return fs_list(query.get("path", ""))
    if key == "fs/check" and method == "POST":
        p = folder_problem(body.get("folder", "")) if IS_WIN else None
        if p:
            return {"ok": False, "msg": p}, 400
        try:
            return {"ok": True, "real": HELPER.call({"op": "check_folder", "folder": body.get("folder", "")})["real"]}, 200
        except HelperError as e:
            return {"ok": False, "msg": str(e)}, 400
        except HelperDown as e:
            return {"ok": False, "msg": str(e)}, 503
    return {"ok": False, "msg": "not found"}, 404


# ====================================================================== HTTP
class Base(BaseHTTPRequestHandler):
    server_version = "tempauth"
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def send_json(self, code, obj, extra=None):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("请求太大")
        return self.rfile.read(n) if n else b""


class PublicHandler(Base):
    def _bare(self):
        """控制台的连通检测 POST /mcp：没有令牌，回 401（和其他线路一样，401 表示服务在）。"""
        if self.path.split("?")[0].rstrip("/") == "/mcp":
            self.send_json(401, {"error": "this endpoint needs a grant token: /t/<token>/mcp"})
            return True
        return False

    def _grant(self):
        m = re.fullmatch(r"/t/([A-Za-z0-9_-]{20,80})/mcp/?", self.path.split("?")[0])
        if not m:
            return None
        return grant_by_token(m.group(1))

    def do_POST(self):
        try:
            raw = self.body()
        except ValueError as e:
            return self.send_json(413, {"error": str(e)})
        if self._bare():
            return
        g = self._grant()
        if not g:
            return self.send_json(404, {"error": "not found"})
        try:
            msg = json.loads(raw or b"null")
        except json.JSONDecodeError:
            return self.send_json(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        if isinstance(msg, list):
            out = [r for r in (handle_rpc(g, m) for m in msg if isinstance(m, dict)) if r]
        elif isinstance(msg, dict):
            out = handle_rpc(g, msg)
        else:
            out = None
        if out is None or out == []:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_json(200, out)

    def do_GET(self):
        if self._grant():
            self.send_response(405)
            self.send_header("Allow", "POST, DELETE")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        self.send_json(200 if self._grant() else 404, {})


class AdminHandler(Base):
    def _ok(self):
        if self.headers.get("Host", "") not in (f"127.0.0.1:{ADMIN_PORT}", f"localhost:{ADMIN_PORT}"):
            self.send_json(403, {"ok": False, "msg": "bad host"})
            return False
        if not secrets.compare_digest(self.headers.get("X-Tempauth-Token", ""), ADMIN_TOKEN):
            self.send_json(401, {"ok": False, "msg": "bad token"})
            return False
        return True

    def _query(self):
        from urllib.parse import parse_qs, urlsplit
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def _events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        q = HUB.add()
        try:
            self.wfile.write(f"event: counts\ndata: {json.dumps(counts())}\n\n".encode())
            self.wfile.flush()
            while True:
                try:
                    ev, data = q.get(timeout=15)
                    self.wfile.write(f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except OSError:
            pass
        finally:
            HUB.remove(q)

    def _handle(self, method):
        if not self._ok():
            return
        path = self.path.split("?")[0]
        if not path.startswith("/admin/"):
            return self.send_json(404, {"ok": False, "msg": "not found"})
        if method == "GET" and path == "/admin/events":
            return self._events()
        try:
            body = json.loads(self.body() or b"{}") if method == "POST" else {}
            data, code = admin_route(method, path, self._query(), body if isinstance(body, dict) else {})
        except Exception as e:
            data, code = {"ok": False, "msg": f"{type(e).__name__}: {e}"}, 500
        self.send_json(code, data)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


class Server(ThreadingHTTPServer):
    allow_reuse_address = not IS_WIN
    daemon_threads = True

    def server_bind(self):
        if IS_WIN and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main():
    try:
        pub = Server(("127.0.0.1", PUBLIC_PORT), PublicHandler)
        adm = Server(("127.0.0.1", ADMIN_PORT), AdminHandler)
    except OSError as e:
        print("端口被占用：", e, file=sys.stderr)
        sys.exit(1)
    ADMIN_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    ADMIN_TOKEN_FILE.write_text(ADMIN_TOKEN, encoding="utf-8")
    reconcile()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=ticker, daemon=True).start()
    threading.Thread(target=adm.serve_forever, daemon=True).start()
    print(f"tempauth gateway {VERSION}: MCP 127.0.0.1:{PUBLIC_PORT}, admin 127.0.0.1:{ADMIN_PORT}, demo={DEMO}", flush=True)
    pub.serve_forever()


if __name__ == "__main__":
    main()
