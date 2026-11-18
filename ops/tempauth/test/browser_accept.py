# 浏览器授权验收（正式网关 8086/8087，blender 账号运行）。报告直接打印；签发一条仅浏览器授权，测完吊销。
import json, threading, time, urllib.request, urllib.error, subprocess, os
from pathlib import Path
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOK = Path(r"C:\ProgramData\BlenderMCP\tempauth.token").read_text().strip()
res = []
def rec(name, ok, detail=""):
    res.append((name, ok)); print(("PASS " if ok else "FAIL ") + name + " | " + str(detail)[:200], flush=True)
def adm(m, p, b=None):
    r = urllib.request.Request("http://127.0.0.1:8087/admin/" + p, method=m, data=json.dumps(b).encode() if b is not None else None,
                               headers={"X-Tempauth-Token": TOK, "Content-Type": "application/json"})
    try:
        return json.loads(OP.open(r, timeout=100).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())
def mcp(U, method, params=None):
    U = U.replace("https://tmcp.maimaiqiu.work", "http://127.0.0.1:8086")
    r = urllib.request.Request(U, method="POST", headers={"Content-Type": "application/json"},
                               data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode())
    try:
        return json.loads(OP.open(r, timeout=120).read())
    except urllib.error.HTTPError as e:
        return {"http": e.code}
def tool(U, name, **a):
    r = mcp(U, "tools/call", {"name": name, "arguments": a})
    if "result" not in r:
        return True, json.dumps(r), []
    c = r["result"]["content"]
    return r["result"].get("isError"), " ".join(x.get("text", "") for x in c if x.get("type") == "text"), [x["type"] for x in c]

g = adm("POST", "grants", {"browser": True, "minutes": 30, "name": "浏览器验收"})
U, gid = g["url"], g["grant"]["id"]
rec("签发仅浏览器授权", g.get("ok") and g["grant"]["folders"] == [] and g["grant"]["browser"], g["grant"].get("logins"))
init = mcp(U, "initialize", {"protocolVersion": "2025-06-18"})
names = [t["name"] for t in mcp(U, "tools/list")["result"]["tools"]]
rec("工具列表", "browser_navigate" in names and "request_login" in names and "browser_run_code_unsafe" not in names
    and "browser_file_upload" not in names and "run_command" not in names, ",".join(names))
rec("说明含 request_login", "request_login" in json.dumps(init, ensure_ascii=False))
t0 = time.time(); e, txt, _ = tool(U, "browser_navigate", url="https://example.com")
rec("打开 example.com", not e and "Example Domain" in txt, "%.1fs" % (time.time() - t0))
e, txt, types = tool(U, "browser_take_screenshot")
rec("截图返回图片", not e and "image" in types, types)
for u in ["http://127.0.0.1:8087/admin/state", "http://localhost:8766/status", "http://192.168.1.1/", "file:///C:/Windows/win.ini"]:
    e, txt, _ = tool(U, "browser_navigate", url=u)
    rec("拦截 " + u, e and "拦截" in txt, txt[:80])
e, txt, _ = tool(U, "browser_run_code_unsafe", code="async (page) => 1")
rec("任意代码被拒", e, txt[:80])

# 登录请求：完成（不保存）
out = {}
th = threading.Thread(target=lambda: out.update(r=tool(U, "request_login", url="https://example.com/", reason="验收测试")))
th.start(); time.sleep(2)
reqs = adm("GET", "logins/requests")["requests"]
mine = [r for r in reqs if r["grant_id"] == gid] if reqs and "grant_id" in reqs[0] else reqs
rec("请求出现在列表", len(mine) == 1, mine)
rid = mine[0]["id"]
adm("POST", "logins/requests/" + rid, {"action": "start"})
state = {"cookies": [{"name": "aitemp_accept", "value": "1", "domain": ".example.com", "path": "/", "expires": -1,
                      "httpOnly": False, "secure": True, "sameSite": "Lax"}], "origins": []}
t0 = time.time()
sv = adm("POST", "logins/save", {"state": state, "domains": ["example.com"], "request": rid, "titles": {}, "save": False})
th.join(30)
rec("完成登录：logged_in", sv.get("ok") and '"logged_in"' in out.get("r", (0, ""))[1], "%s %.1fs" % (out.get("r"), time.time() - t0))
e, txt, _ = tool(U, "browser_navigate", url="https://example.com/?check")
rec("登录后浏览器仍可用", not e, txt[:60])
rec("未保存到浏览器登录", not Path(r"C:\Users\blender\TempAuth\logins\example.com.json").exists())

# 登录请求：拒绝
out = {}
th = threading.Thread(target=lambda: out.update(r=tool(U, "request_login", url="https://example.org/", reason="验收测试：拒绝")))
th.start(); time.sleep(2)
reqs = [r for r in adm("GET", "logins/requests")["requests"] if r.get("state") == "pending"]
adm("POST", "logins/requests/" + reqs[0]["id"], {"action": "decline"})
th.join(30)
rec("拒绝：declined", '"declined"' in out.get("r", (0, ""))[1], out.get("r"))

logs = adm("GET", "logs?limit=50&grant=" + gid)["logs"]
ops = {}
for l in logs:
    ops[l["op"]] = ops.get(l["op"], 0) + 1
rec("执行记录", ops.get("登录") == 2 and ops.get("打开网页", 0) >= 5, ops)
gv = [x for x in adm("GET", "grants?status=all")["grants"] if x["id"] == gid][0]
rec("浏览器操作计数", gv.get("browser_ops", 0) >= 3 and gv["used"] == 0, (gv.get("browser_ops"), gv["used"]))

t0 = time.time(); r = adm("POST", "grants/%s/revoke" % gid)
rec("吊销", r.get("ok"), "%d ms" % r.get("ms", -1))
time.sleep(2)
e, txt, _ = tool(U, "browser_navigate", url="https://example.com")
rec("吊销后调用被拒", e and "收回" in txt, txt[:60])
ps = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Process | ? { $_.CommandLine -match '%s' }).Count" % gid],
                    capture_output=True, text=True).stdout.strip()
rec("浏览器进程已结束", ps in ("0", ""), ps)
print("OUTDIR", gid, os.path.exists(r"C:\Users\blender\TempAuth\browser\%s" % gid))
print("RESULT %d/%d" % (sum(1 for _, ok in res if ok), len(res)))
