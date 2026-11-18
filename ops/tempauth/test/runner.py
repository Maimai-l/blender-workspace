"""runner.py - runs AS aitemp (started by aitemp_test.ps1). Checks what the sandbox account can and cannot do and
writes one JSON line per check to the report file given as argv[2].

    python runner.py <phase: offline|online> <report.jsonl> <blender-owned pid>

Every check states what is expected ("allow" or "deny") and what happened; the admin script turns it into a table.
Standard library only (runs with C:\\Program Files\\BlenderMCP\\python).
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

PHASE, REPORT, OTHER_PID = sys.argv[1], sys.argv[2], sys.argv[3]
GRANT = os.getcwd()
AIT = os.path.join(GRANT, ".aitemp")
PY = r"D:\ProgramData\python.exe"
NODE = r"D:\Program Files\node.EXE"
NPM = r"D:\Program Files\npm.cmd"
GIT = r"C:\Program Files\Git\cmd\git.exe"
BLENDER = r"D:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
ONLINE = PHASE == "online"


def env():
    e = dict(os.environ)
    for k, sub in (("TEMP", "tmp"), ("TMP", "tmp"), ("PIP_CACHE_DIR", "pip-cache"), ("PYTHONUSERBASE", "pyuser"),
                   ("npm_config_cache", "npm-cache"), ("npm_config_prefix", "npm-global"), ("UV_CACHE_DIR", "uv-cache")):
        e[k] = os.path.join(AIT, sub)
        os.makedirs(e[k], exist_ok=True)
    e["PATH"] = os.pathsep.join([r"D:\ProgramData", r"D:\ProgramData\Scripts", r"D:\Program Files",
                                 r"C:\Program Files\Git\cmd", r"C:\Windows\System32", r"C:\Windows"])
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        e.pop(k, None)
    if ONLINE:
        e["HTTP_PROXY"] = e["HTTPS_PROXY"] = "http://127.0.0.1:7899"
        e["NO_PROXY"] = "localhost,127.0.0.1"
    return e


ENV = env()


def record(group, name, expect, ok, detail=""):
    got = "allow" if ok else "deny"
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(json.dumps({"phase": PHASE, "group": group, "check": name, "expect": expect, "got": got,
                            "pass": expect == got, "detail": str(detail)[:300]}, ensure_ascii=False) + "\n")


def attempt(fn):
    try:
        return True, fn()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def run(args, timeout=120, cwd=None):
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV,
                       cwd=cwd or GRANT, timeout=timeout)
    out = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, f"exit {r.returncode}, {time.time() - t0:.1f}s: " + " / ".join(out[-3:])


def check_cmd(group, name, expect, args, timeout=120):
    try:
        ok, detail = run(args, timeout)
    except Exception as e:
        ok, detail = False, f"{type(e).__name__}: {e}"
    record(group, name, expect, ok, detail)


# ---------------------------------------------------------------- files (offline phase only; same in both)
if not ONLINE:
    p = os.path.join(GRANT, "sub", "f.txt")
    ok, d = attempt(lambda: (os.makedirs(os.path.dirname(p), exist_ok=True), open(p, "w").write("x"),
                             open(p).read(), os.remove(p), os.rmdir(os.path.dirname(p))))
    record("文件", "授权文件夹里建、读、删文件和子文件夹", "allow", ok, d)
    for path in (r"D:\Projects", r"D:\Projects\maa-cli", r"D:\Projects\skland", r"D:\Archive_DO_NOT_DELETE",
                 r"D:\Blender", r"C:\Users\blender", r"C:\Users\Administrator", r"C:\ProgramData\BlenderMCP"):
        ok, d = attempt(lambda: len(os.listdir(path)))
        record("文件", f"列目录 {path}", "deny", ok, d)
    for path in (r"C:\ProgramData\BlenderMCP\agent.token", "D:\\密码.kdbx", r"D:\Projects\maa-cli\run.ps1"):
        ok, d = attempt(lambda: len(open(path, "rb").read(16)))
        record("文件", f"读文件 {path}", "deny", ok, d)
    for path in (r"D:\Program Files\aitemp_probe.txt", r"D:\ProgramData\aitemp_probe.txt", r"D:\aitemp_probe.txt",
                 r"C:\aitemp_probe.txt", r"D:\Projects\aitemp_probe.txt"):
        def w(path=path):
            open(path, "w").write("x")
            os.remove(path)
        ok, d = attempt(w)
        record("文件", f"写文件 {path}", "deny", ok, d)
    ok, d = attempt(lambda: len(os.listdir("D:\\")))
    record("文件", r"列 D:\ 根目录（只看到名字）", "allow", ok, d)

    # ------------------------------------------------------------ programs
    check_cmd("程序", "conda base 的 python", "allow", [PY, "-c", "import ssl, sqlite3, json; print('ok')"])
    check_cmd("程序", "python -m venv .venv（含 pip）", "allow", [PY, "-m", "venv", os.path.join(GRANT, ".venv")], 300)
    check_cmd("程序", "node -v", "allow", [NODE, "-v"])
    check_cmd("程序", "npm -v", "allow", ["cmd", "/c", NPM, "-v"])
    check_cmd("程序", "git --version", "allow", [GIT, "--version"])
    check_cmd("程序", "blender -b 运行一行 Python", "allow",
              [BLENDER, "-b", "--factory-startup", "--python-expr", "import bpy; print('blender', bpy.app.version_string)"], 180)
    def conda_write():
        q = r"D:\ProgramData\Lib\site-packages\aitemp_probe.txt"
        open(q, "w").write("x")
        os.remove(q)
    ok, d = attempt(conda_write)
    record("装包", "往 conda 的 site-packages 写文件（装包会失败）", "deny", ok, d)
    check_cmd("装包", "PYTHONUSERBASE 指向 .aitemp", "allow",
              [PY, "-c", "import site,sys; b=site.getuserbase(); print(b); sys.exit(0 if '.aitemp' in b else 1)"])
    try:
        ok, d = run(["cmd", "/c", NPM, "config", "get", "prefix"])
        ok = ok and ".aitemp" in d
    except Exception as e:
        ok, d = False, e
    record("装包", "npm 全局目录指向 .aitemp", "allow", ok, d)

    # ------------------------------------------------------------ accounts / processes
    check_cmd("账号", f"结束 blender 账号的进程 {OTHER_PID}", "deny", ["taskkill", "/PID", OTHER_PID], 30)

# ---------------------------------------------------------------- network
def tcp(host, port):
    with socket.create_connection((host, port), timeout=4):
        return "connected"


for port, label in ((9876, "Blender 插件"), (17860, "转写台"), (8765, "控制台"), (8766, "agent"), (7897, "Clash 主端口"),
                    (8084, "命令执行"), (8088, "浏览器")):
    ok, d = attempt(lambda port=port: tcp("127.0.0.1", port))
    # a port nobody listens on looks like "deny" too; the admin script records which ports were listening
    record("本机端口", f"连 127.0.0.1:{port}（{label}）", "deny", ok, d)
ok, d = attempt(lambda: tcp("127.0.0.1", 7899))
record("本机端口", "连 127.0.0.1:7899（Clash 浏览器入口）", "allow" if ONLINE else "deny", ok, d)
ok, d = attempt(lambda: tcp("1.1.1.1", 443))
record("联网", "直连外网 1.1.1.1:443", "allow" if ONLINE else "deny", ok, d)


def via_proxy(url):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({"https": "http://127.0.0.1:7899"}))
    with op.open(urllib.request.Request(url, headers={"User-Agent": "aitemp-test"}), timeout=15) as r:
        return r.status


ok, d = attempt(lambda: via_proxy("https://pypi.org/simple/six/"))
record("联网", "经 Clash 7899 访问 pypi.org", "allow" if ONLINE else "deny", ok, d)
ok, d = attempt(lambda: via_proxy("https://www.google.com/generate_204"))
record("联网", "经 Clash 7899 访问 google（翻墙）", "allow" if ONLINE else "deny", ok, d)

VPY = os.path.join(GRANT, ".venv", "Scripts", "python.exe")
expect = "allow" if ONLINE else "deny"
check_cmd("装包", "venv 里 pip install six", expect, [VPY, "-m", "pip", "install", "--disable-pip-version-check", "six"], 300)
check_cmd("装包", "npm install is-number（装在文件夹的 node_modules）", expect,
          ["cmd", "/c", NPM, "install", "--no-fund", "--no-audit", "is-number"], 300)
check_cmd("装包", "pip install --user（装进 .aitemp）", expect,
          [PY, "-m", "pip", "install", "--user", "--disable-pip-version-check", "--no-warn-script-location", "tomli"], 300)
check_cmd("装包", "git clone GitHub 仓库", expect,
          [GIT, "clone", "--depth", "1", "https://github.com/octocat/Hello-World.git", f"hello-{PHASE}"], 180)
