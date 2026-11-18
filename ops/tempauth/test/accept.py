"""临时授权验收测试：装好授权助手和网关之后，在 blender 账号里运行。

    "C:\\Program Files\\BlenderMCP\\python\\cpython-3.14.6-windows-x86_64-none\\python.exe" accept.py

经三条路径测：网关的管理接口（签发、吊销、确认），网关的 MCP 接口（对方 AI 看到的样子），授权助手的命名管道
（绕过执行前检查，直接测沙盒账号本身的边界）。报告写到 D:\\Projects\\aitemp-test\\accept-report.md。
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BlenderMCP\tempauth")
import gateway  # noqa: E402  只用它的 PipeHelper

ROOT = Path(r"D:\Projects\aitemp-test")
A, B, C = ROOT / "a", ROOT / "b", ROOT / "c"
TOK = Path(r"C:\ProgramData\BlenderMCP\tempauth.token").read_text().strip()
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
H = gateway.PipeHelper()
RESULTS = []


def rec(group, name, ok, detail=""):
    RESULTS.append((group, name, bool(ok), str(detail).replace("\n", " / ")[:300]))
    print(("PASS " if ok else "FAIL ") + group + " | " + name + " | " + str(detail)[:160].replace("\n", " / "), flush=True)


def adm(method, path, body=None):
    r = urllib.request.Request("http://127.0.0.1:8087/admin/" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"X-Tempauth-Token": TOK, "Content-Type": "application/json"})
    try:
        return json.loads(OP.open(r, timeout=200).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def mcp(url, method, params=None):
    url = url.replace("https://tmcp.maimaiqiu.work", "http://127.0.0.1:8086")
    r = urllib.request.Request(url, method="POST", headers={"Content-Type": "application/json"},
                               data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode())
    try:
        return json.loads(OP.open(r, timeout=120).read())
    except urllib.error.HTTPError as e:
        return {"http": e.code}


def tool(url, name, **a):
    r = mcp(url, "tools/call", {"name": name, "arguments": a})
    if "result" not in r:
        return True, json.dumps(r)
    return r["result"]["isError"], r["result"]["content"][0]["text"]


def run_wait(url, command, shell="cmd", timeout=600, **kw):
    err, text = tool(url, "run_command", command=command, shell=shell, timeout_seconds=timeout, **kw)
    while "get_command_result" in text and ("仍在运行" in text or "等待" in text):
        tid = text.split("任务 ")[1].split("，")[0].split("）")[0]
        err, text = tool(url, "get_command_result", task_id=tid, wait_seconds=60)
    return err, text


def hrun(gid, command, shell="cmd", timeout=60, cwd=None):
    """经助手直接运行（不过执行前检查），返回 (退出码, 状态, 输出)。"""
    q = {"op": "run", "grant": gid, "command": command, "shell": shell, "timeout": timeout, "online": False}
    if cwd:
        q["cwd"] = cwd
    for _ in range(100):
        try:
            j = H.call(q)["job"]
            break
        except gateway.HelperError as e:
            if e.code != "busy":
                raise
            time.sleep(1)
    while True:
        p = H.call({"op": "poll", "job": j, "wait": 30000})
        if p["state"] != "running":
            return p["exit"], p["state"], p["output"]


def main():
    t0 = time.time()
    for d in (A, B, C):
        d.mkdir(parents=True, exist_ok=True)
    st = H.call({"op": "status"})
    rec("助手", "服务就绪", st.get("ready"), f"{st.get('version')} {st.get('error') or ''}")
    v = H.call({"op": "verify"})
    bad = [c for c in v["checks"] if not c[1]]
    rec("助手", f"沙盒自检（{len(v['checks'])} 项）", v["passed"], "; ".join(f"{c[0]}: {c[2]}" for c in bad) or ("补上：" + "；".join(v["fixed"]) if v["fixed"] else ""))

    ga = adm("POST", "grants", {"folders": [str(A)], "name": "验收 A 断网", "minutes": 60, "limit": 100, "net": False, "confirm": False})
    gb = adm("POST", "grants", {"folders": [str(B)], "name": "验收 B 联网", "minutes": 60, "limit": 100, "net": True, "confirm": False})
    gc = adm("POST", "grants", {"folders": [str(C)], "name": "验收 C 确认", "minutes": 60, "limit": 5, "net": False, "confirm": True})
    rec("签发", "三条授权", all(g.get("ok") for g in (ga, gb, gc)), [g.get("msg") for g in (ga, gb, gc) if not g.get("ok")])
    UA, UB, UC = ga["url"], gb["url"], gc["url"]
    ida, idb, idc = ga["grant"]["id"], gb["grant"]["id"], gc["grant"]["id"]
    init = mcp(UA, "initialize", {"protocolVersion": "2025-06-18"})
    rec("MCP", "initialize + tools/list", "result" in init and len(mcp(UA, "tools/list")["result"]["tools"]) == 7)

    # ---- 程序（经 MCP）
    err, out = run_wait(UA, "whoami")
    rec("程序", "whoami 是 aitemp", not err and "aitemp" in out.lower(), out)
    err, out = run_wait(UA, 'python -c "import ssl, sqlite3, json; print(\'py ok\')"')
    rec("程序", "conda python", not err and "py ok" in out, out)
    err, out = run_wait(UA, "python -m venv .venv", timeout=300)
    rec("程序", "python -m venv", not err and (A / ".venv" / "Scripts" / "python.exe").exists(), out[-200:])
    err, out = run_wait(UA, "node -v && npm -v && git --version")
    rec("程序", "node、npm、git", not err and "git version" in out, out)
    err, out = run_wait(UA, 'blender -b --factory-startup --python-expr "import bpy; print(\'bl\', bpy.app.version_string)"', timeout=180)
    rec("程序", "blender -b", not err and "bl 5." in out, out[-200:])
    err, out = run_wait(UA, 'echo "home=$HOME"; pwd; uname -s', shell="bash")
    rec("程序", "bash", not err and ("MINGW" in out.upper() or "MSYS" in out.upper()), out)
    err, out = run_wait(UA, "$PSVersionTable.PSVersion.ToString(); [Environment]::UserName", shell="powershell")
    rec("程序", "powershell", not err and "aitemp" in out.lower(), out)
    err, out = run_wait(UA, "echo 中文输出测试 && dir /b")
    rec("程序", "中文输出不乱码", not err and "中文输出测试" in out, out[:120])

    # ---- 沙盒边界（经助手，绕过执行前检查）
    code, _, out = hrun(ida, f'dir "{B}"')
    rec("隔离", "授权 A 的命令读不到授权 B 的文件夹", code != 0, out)
    for cmd, what in ((r"type C:\ProgramData\BlenderMCP\agent.token", "agent.token"), (r"dir C:\Users\blender", "C:\\Users\\blender"),
                      (r"dir D:\Projects", "D:\\Projects"), (r"dir D:\Projects\maa-cli", "maa-cli"), (r"echo x > D:\Program Files\x.txt", "写 D:\\Program Files")):
        code, _, out = hrun(ida, cmd)
        rec("隔离", f"读写 {what} 被拒绝", code != 0, out)
    probe = ("import socket\nfor h,p in [('127.0.0.1',8766),('127.0.0.1',9876),('127.0.0.1',8087),('127.0.0.1',7899),('1.1.1.1',443)]:\n"
             "    try:\n        socket.create_connection((h,p),timeout=3).close(); print('OPEN',h,p)\n"
             "    except Exception as e: print('blocked',h,p,type(e).__name__)\n")
    (A / "probe.py").write_text(probe, encoding="utf-8")
    code, _, out = hrun(ida, "python probe.py")
    rec("联网", "断网时本机端口、7899、外网全拦", code == 0 and "OPEN" not in out and out.count("blocked") == 5, out)

    # ---- 联网装包（授权 B）
    err, out = run_wait(UB, "python -m venv .venv && .venv\\Scripts\\python -m pip install six", timeout=300)
    rec("装包", "联网：venv 里 pip install six", not err and ("Successfully installed six" in out or "already satisfied" in out), out[-200:])
    err, out = run_wait(UB, 'python -m pip install --user --no-warn-script-location cowsay && python -c "import cowsay; print(cowsay.__file__)"', timeout=300)
    rec("装包", "联网：pip --user 装进 .aitemp\\pyuser", not err and ".aitemp\\pyuser" in out.lower().replace("/", "\\"), out[-200:])
    err, out = run_wait(UB, "npm install --no-fund --no-audit is-number", timeout=300)
    rec("装包", "联网：npm install", not err and (B / "node_modules" / "is-number").exists(), out[-200:])
    err, out = run_wait(UB, "git clone --depth 1 https://github.com/octocat/Hello-World.git hw", timeout=180)
    rec("装包", "联网：git clone", not err and (B / "hw" / "README").exists(), out[-200:])
    err, out = run_wait(UA, "python -m pip install six")
    rec("装包", "断网：pip install 被执行前检查拦下", err and "拦截" in out, out)
    code, _, out = hrun(ida, ".venv\\Scripts\\python -m pip install --retries 0 --timeout 5 six", timeout=120)
    rec("装包", "断网：绕过检查直接装也失败", code != 0, out[-200:])

    # ---- 文件工具
    err, out = tool(UA, "write_file", path="sub/hello.txt", content="你好，aitemp")
    rec("文件", "write_file", not err, out)
    err, out = tool(UA, "read_file", path="sub/hello.txt")
    rec("文件", "read_file", not err and out == "你好，aitemp", out)
    err, out = tool(UA, "list_directory", depth=2)
    rec("文件", "list_directory", not err and "sub\\hello.txt" in out, out[:200])
    err, out = tool(UA, "read_file", path=r"C:\ProgramData\BlenderMCP\agent.token")
    rec("文件", "read_file 授权外被拦", err and "拦截" in out, out)
    code, _, out = hrun(ida, f'mklink /J lnk "{B}"')
    err, out2 = tool(UA, "list_directory", path="lnk")
    rec("文件", "经联接指到授权外被拒绝", err, out2)

    # ---- 超时、后台进程
    t1 = time.time()
    code, state, out = hrun(ida, "ping -n 30 127.0.0.1", timeout=5)
    rec("执行", "超时结束", state == "timeout" and time.time() - t1 < 15, f"{state} {time.time() - t1:.1f}s")
    before = subprocess.run(["tasklist", "/fi", "imagename eq PING.EXE"], capture_output=True, text=True, errors="replace").stdout.count("PING.EXE")
    code, state, out = hrun(ida, "start /b ping -n 60 127.0.0.1 >nul & echo started")
    time.sleep(1)
    after = subprocess.run(["tasklist", "/fi", "imagename eq PING.EXE"], capture_output=True, text=True, errors="replace").stdout.count("PING.EXE")
    rec("执行", "命令结束后留在后台的进程一并结束", after <= before, f"ping 进程 {before} → {after}")

    # ---- 吊销
    res = {}
    th = threading.Thread(target=lambda: res.update(r=tool(UA, "run_command", command="ping -n 60 127.0.0.1")))
    th.start()
    time.sleep(4)
    t1 = time.time()
    r = adm("POST", f"grants/{ida}/revoke")
    th.join(30)
    rec("吊销", "吊销接口 1 秒内返回", r.get("ok") and time.time() - t1 < 1.5, f"{r.get('ms')} ms")
    rec("吊销", "正在跑的命令被中止", "中止" in res.get("r", (0, ""))[1], res.get("r"))
    err, out = tool(UA, "list_directory")
    rec("吊销", "吊销后再调用被拒绝", err and "收回" in out, out)
    r = adm("POST", f"grants/{ida}/restore")
    err, out = tool(UA, "list_directory")
    rec("吊销", "恢复后能用", r.get("ok") and not err, out[:80])

    # ---- 执行前确认
    res = {}
    th = threading.Thread(target=lambda: res.update(r=tool(UC, "run_command", command="echo approved-ok")))
    th.start()
    time.sleep(2)
    ap = adm("GET", "approvals")["approvals"]
    mine = [a for a in ap if a["grant_id"] == idc]
    if mine:
        adm("POST", "approvals/" + mine[0]["id"], {"allow": True})
    th.join(90)
    rec("确认", "允许后执行", bool(mine) and "approved-ok" in res.get("r", (0, ""))[1], res.get("r"))
    th = threading.Thread(target=lambda: res.update(r=tool(UC, "run_command", command="echo should-not-run")))
    th.start()
    time.sleep(2)
    mine = [a for a in adm("GET", "approvals")["approvals"] if a["grant_id"] == idc]
    if mine:
        adm("POST", "approvals/" + mine[0]["id"], {"allow": False})
    th.join(90)
    rec("确认", "拒绝后不执行", bool(mine) and "主人拒绝" in res.get("r", (0, ""))[1], res.get("r"))

    # ---- 记录
    logs = adm("GET", "logs?limit=500")["logs"]
    mine = [l for l in logs if l["grant_id"] in (ida, idb, idc)]
    rec("记录", "每次调用都有记录（含拦截、拒绝）", any(l["result"] == "blocked" for l in mine) and any(l["result"] == "denied" for l in mine),
        f"{len(mine)} 条")

    # ---- 撤权（释放）
    for g in (ida, idb, idc):
        adm("POST", f"grants/{g}/revoke")
    H.call({"op": "release", "grant": idb})
    acl = subprocess.run(["icacls", str(B)], capture_output=True, text=True, errors="replace").stdout
    grp = subprocess.run(["net", "localgroup", "AITemp-" + idb], capture_output=True, text=True, errors="replace").returncode
    rec("撤权", "释放后组和文件夹权限都删掉", "AITemp-" not in acl and grp != 0, acl.splitlines()[1:3])

    lines = [f"# 临时授权验收报告", "", f"{time.strftime('%Y-%m-%d %H:%M')}，用时 {int(time.time() - t0)} 秒；"
             f"{len(RESULTS)} 项，未通过 {sum(1 for r in RESULTS if not r[2])} 项。", "",
             "| 类别 | 检查 | 结果 | 说明 |", "| --- | --- | --- | --- |"]
    for g, n, ok, d in RESULTS:
        lines.append(f"| {g} | {n} | {'通过' if ok else '**未通过**'} | {d.replace('|', '/')} |")
    (ROOT / "accept-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(RESULTS)} checks, {sum(1 for r in RESULTS if not r[2])} failed; report: {ROOT / 'accept-report.md'}")


if __name__ == "__main__":
    main()
