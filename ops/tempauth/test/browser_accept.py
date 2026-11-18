# 浏览器授权验收（正式网关 8086/8087，blender 账号运行）。报告直接打印；签发一条仅浏览器授权，测完吊销。
# 网关 2.0：结果格式见《MCP 控制台需求》第 6 节。
import json, re, threading, time, urllib.request, urllib.error, subprocess, os
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
    """返回 (isError, structuredContent 或 None, 文本, 内容块类型)。"""
    r = mcp(U, "tools/call", {"name": name, "arguments": a})
    if "result" not in r:
        return True, {"error": {"code": "transport"}}, json.dumps(r), []
    c = r["result"]["content"]
    return (r["result"].get("isError"), r["result"].get("structuredContent"),
            "\n".join(x.get("text", "") for x in c if x.get("type") == "text"), [x["type"] for x in c])


def code_of(sc):
    return ((sc or {}).get("error") or {}).get("code")


LOCAL = re.compile(r"\]\(\.?/?[^)\s]*\.(yml|png|jpe?g|pdf|log)\)")

g = adm("POST", "grants", {"browser": True, "minutes": 30, "name": "浏览器验收"})
U, gid = g["url"], g["grant"]["id"]
rec("签发仅浏览器授权", g.get("ok") and g["grant"]["folders"] == [] and g["grant"]["browser"], g["grant"].get("logins"))
rec("提示词按能力分组、时间 UTC", "浏览器：" in g["prompt"] and "文件夹：" not in g["prompt"] and "（UTC）" in g["prompt"])
init = mcp(U, "initialize", {"protocolVersion": "2025-06-18"})
tools = mcp(U, "tools/list")["result"]["tools"]
names = [t["name"] for t in tools]
rec("工具列表", "browser_navigate" in names and "request_login" in names and "browser_run_code_unsafe" not in names
    and "browser_file_upload" not in names and "run_command" not in names, ",".join(names))
rec("没有 filename 参数", not [t["name"] for t in tools if "filename" in (t.get("inputSchema", {}).get("properties") or {})])
rec("说明含 request_login 和 UTC", "request_login" in init["result"]["instructions"] and "UTC" in init["result"]["instructions"])
e, sc, _, _ = tool(U, "grant_info")
rec("grant_info 只有浏览器一组", not e and "folders" not in sc and sc["browser"]["counted"] is False and sc["expires_at"].endswith("Z"), sc)

t0 = time.time(); e, sc, txt, _ = tool(U, "browser_navigate", url="https://example.com")
rec("打开 example.com：JSON 里有 page 和 snapshot", not e and sc["page"]["title"] == "Example Domain" and "[ref=" in sc["snapshot"]["text"]
    and not LOCAL.search(txt) and json.loads(txt) == sc, "%.1fs" % (time.time() - t0))
ref = (re.search(r'link "Learn more" \[ref=(\w+)\]', sc["snapshot"]["text"]) or [None, "e6"])[1]
e, sc, _, _ = tool(U, "browser_tabs", action="list")
rec("标签页：tabs 数组", not e and sc["tabs"][0]["current"] and sc["tabs"][0]["url"].startswith("https://example.com"), sc)
e, sc, txt, types = tool(U, "browser_take_screenshot", filename="ignored.png")
rec("截图：image 内容块，JSON 里列出附件", not e and "image" in types and sc["attachments"][0]["type"] == "image" and not LOCAL.search(txt), types)
e, sc, txt, types = tool(U, "browser_pdf_save")
rec("PDF 作为嵌入资源返回", not e and "resource" in types and not LOCAL.search(txt), types)
e, sc, _, _ = tool(U, "browser_navigate")
rec("缺参数：invalid_argument", e and code_of(sc) == "invalid_argument" and sc["error"]["details"]["field"] == "url", sc)
e, sc, _, _ = tool(U, "browser_navigate", url="https://this-domain-does-not-exist-zz9q.com/")
rec("不存在的域名：navigation_failed、ERR_NAME_NOT_RESOLVED", e and code_of(sc) == "navigation_failed"
    and sc["error"]["details"]["net_error"] == "ERR_NAME_NOT_RESOLVED" and "\\u001b" not in json.dumps(sc) and "callTool" not in json.dumps(sc), sc)
e, sc, _, _ = tool(U, "browser_navigate", url="https://example.com")
for u, why in [("http://127.0.0.1:8087/admin/state", "loopback"), ("http://localhost:8766/status", "loopback"),
               ("http://192.168.1.1/", "private"), ("file:///C:/Windows/win.ini", "scheme")]:
    e, sc, _, _ = tool(U, "browser_navigate", url=u)
    rec("拦截 " + u, e and code_of(sc) == "url_blocked" and sc["error"]["details"]["reason"] == why, sc)
e, sc, _, _ = tool(U, "browser_run_code_unsafe", code="async (page) => 1")
rec("任意代码被拒", e and code_of(sc) == "tool_unavailable", sc)
e, sc, _, _ = tool(U, "browser_click", target="e99999", element="nothing")
rec("找不到元素：ref_not_found、可重试", e and code_of(sc) == "ref_not_found" and sc["error"]["retryable"] is True, sc)

# 登录请求：完成（不保存）
out = {}
th = threading.Thread(target=lambda: out.update(r=tool(U, "request_login", url="https://example.com/", reason="验收测试")))
th.start(); time.sleep(2)
mine = [r for r in adm("GET", "logins/requests")["requests"] if r["grant_id"] == gid]
rec("请求出现在列表", len(mine) == 1, mine)
rid = mine[0]["id"]
adm("POST", "logins/requests/" + rid, {"action": "start"})
e, sc, _, _ = tool(U, "check_login", request_id=rid, wait_seconds=0)
rec("登录中：in_progress，next 指向 check_login", not e and sc["status"] == "in_progress" and sc["next"]["tool"] == "check_login", sc)
state = {"cookies": [{"name": "aitemp_accept", "value": "1", "domain": ".example.com", "path": "/", "expires": -1,
                      "httpOnly": False, "secure": True, "sameSite": "Lax"}], "origins": []}
t0 = time.time()
sv = adm("POST", "logins/save", {"state": state, "domains": ["example.com"], "request": rid, "titles": {}, "save": False})
th.join(30)
e, sc, _, _ = out.get("r", (True, {}, "", []))
rec("完成登录：logged_in，带刷新后的页面", sv.get("ok") and not e and sc["status"] == "logged_in" and sc["saved"] is False
    and sc["page"]["url"].startswith("https://example.com"), "%s %.1fs" % (sc, time.time() - t0))
e, _, txt, _ = tool(U, "browser_navigate", url="https://example.com/?check")
rec("登录后浏览器仍可用", not e, txt[:60])
rec("未保存到浏览器登录", not Path(r"C:\Users\blender\TempAuth\logins\example.com.json").exists())

# 登录请求：拒绝
out = {}
th = threading.Thread(target=lambda: out.update(r=tool(U, "request_login", url="https://example.org/", reason="验收测试：拒绝")))
th.start(); time.sleep(2)
reqs = [r for r in adm("GET", "logins/requests")["requests"] if r.get("state") == "pending"]
adm("POST", "logins/requests/" + reqs[0]["id"], {"action": "decline"})
th.join(30)
e, sc, _, _ = out.get("r", (False, {}, "", []))
rec("拒绝：declined、isError", e and sc["status"] == "declined", sc)

logs = adm("GET", "logs?limit=50&grant=" + gid)["logs"]
ops = {}
for l in logs:
    ops[l["op"]] = ops.get(l["op"], 0) + 1
rec("执行记录", ops.get("登录") == 2 and ops.get("打开网页", 0) >= 7, ops)
gv = [x for x in adm("GET", "grants?status=all")["grants"] if x["id"] == gid][0]
rec("浏览器操作计数，不占次数", gv.get("browser_ops", 0) >= 6 and gv["used"] == 0, (gv.get("browser_ops"), gv["used"]))
outdir = Path(r"C:\Users\blender\TempAuth\browser\%s\output" % gid)
left = [f.name for f in outdir.iterdir()] if outdir.exists() else []
rec("快照、截图、PDF 文件不留在电脑上", not left, left)

r = adm("POST", "grants/%s/revoke" % gid)
rec("吊销", r.get("ok"), "%d ms" % r.get("ms", -1))
time.sleep(2)
e, sc, _, _ = tool(U, "browser_navigate", url="https://example.com")
rec("吊销后调用被拒：grant_revoked", e and code_of(sc) == "grant_revoked", sc)
ps = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Process | ? { $_.CommandLine -match '%s' }).Count" % gid],
                    capture_output=True, text=True).stdout.strip()
rec("浏览器进程已结束", ps in ("0", ""), ps)
print("RESULT %d/%d" % (sum(1 for _, ok in res if ok), len(res)))
