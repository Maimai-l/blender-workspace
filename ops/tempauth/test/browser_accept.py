# 浏览器授权验收（正式网关 8086/8087，blender 账号运行）。结果直接打印；签发一条仅浏览器授权，测完吊销。
# 网关 2.2：结果格式见《MCP 控制台需求》第 6 节。用到外网（example.com、维基百科、arxiv、httpbin），本机起一个 18099 的测试页。
import base64, http.server, json, re, subprocess, threading, time, urllib.request, urllib.error
from pathlib import Path
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
TOK = Path(r"C:\ProgramData\BlenderMCP\tempauth.token").read_text().strip()
res = []
PAGE = b"""<!doctype html><html><head><title>Local Test</title></head><body>
<main><h1>Local test page</h1><p>Hello from <b>18099</b>.</p>
<table><tr><th>k</th><th>v</th></tr><tr><td>a</td><td>1</td></tr></table></main>
<nav>menu item</nav>
<input type=file id=f onchange="document.getElementById('o').textContent=this.files[0].name+':'+this.files[0].size">
<div id=o>none</div><a href="/report.csv" download>report</a>
<div style="height:3000px">tall</div></body></html>"""


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        csv = self.path.startswith("/report.csv")
        b = b"a,b\n1,2\n" if csv else PAGE
        self.send_response(200)
        self.send_header("Content-Type", "text/csv" if csv else "text/html")
        if csv:
            self.send_header("Content-Disposition", "attachment; filename=report.csv")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


def rec(name, ok, detail=""):
    res.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + " | " + json.dumps(detail, ensure_ascii=False, default=str)[:240], flush=True)


def adm(m, p, b=None):
    r = urllib.request.Request("http://127.0.0.1:8087/admin/" + p, method=m, data=json.dumps(b).encode() if b is not None else None,
                               headers={"X-Tempauth-Token": TOK, "Content-Type": "application/json"})
    try:
        return json.loads(OP.open(r, timeout=100).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


class Sess:
    """一个 MCP 会话：initialize 拿到 Mcp-Session-Id，之后都带着。"""

    def __init__(self, url):
        self.url, self.sid = url.replace("https://tmcp.maimaiqiu.work", "http://127.0.0.1:8086"), None
        r = self.rpc("initialize", {"protocolVersion": "2025-06-18"}, raw=True)
        self.sid = r.headers.get("Mcp-Session-Id")
        self.init = json.loads(r.read())["result"]

    def rpc(self, method, params=None, raw=False):
        h = {"Content-Type": "application/json"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        try:
            r = OP.open(urllib.request.Request(self.url, method="POST", headers=h, data=json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()), timeout=120)
        except urllib.error.HTTPError as e:
            return {"http": e.code}
        return r if raw else json.loads(r.read()).get("result", {})

    def call(self, tool, **a):
        """返回 (isError, structuredContent, 文本, 内容块类型)。"""
        r = self.rpc("tools/call", {"name": tool, "arguments": a})
        c = r.get("content", [])
        return (r.get("isError"), r.get("structuredContent") or {}, "\n".join(x.get("text", "") for x in c if x.get("type") == "text"),
                [x["type"] for x in c])


def code_of(sc):
    return ((sc or {}).get("error") or {}).get("code")


def num(s):
    return int(re.sub(r"\D", "", str(s)) or 0)


LOCAL = re.compile(r"\]\(\.?/?[^)\s]*\.(yml|png|jpe?g|pdf|log)\)")
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 18099), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

g = adm("POST", "grants", {"browser": True, "minutes": 30, "name": "浏览器验收", "allow_hosts": ["127.0.0.1:18099"]})
U, gid = g["url"], g["grant"]["id"]
rec("签发仅浏览器授权（允许 127.0.0.1:18099）", g.get("ok") and g["grant"]["folders"] == [] and g["grant"]["allow_hosts"] == ["127.0.0.1:18099"])
rec("提示词按能力分组、时间 UTC", "浏览器：" in g["prompt"] and "文件夹：" not in g["prompt"] and "（UTC）" in g["prompt"]
    and "127.0.0.1:18099" in g["prompt"])
A, B = Sess(U), Sess(U)
rec("每个 MCP 会话一个编号", A.sid and B.sid and A.sid != B.sid)
tools = A.rpc("tools/list")["tools"]
names = {t["name"] for t in tools}
rec("工具：读内容、坐标、滚轮、前进刷新、下载、重置、网络、录制", {"browser_get_text", "browser_evaluate", "browser_mouse_click_xy",
    "browser_mouse_wheel", "browser_navigate_forward", "browser_reload", "browser_read_download", "browser_reset",
    "browser_network_requests", "browser_cookie_list", "browser_start_tracing", "request_login"} <= names
    and not names & {"browser_run_code_unsafe", "browser_storage_state", "run_command"}, len(names))
rec("没有 filename 参数", not [t["name"] for t in tools if "filename" in (t.get("inputSchema", {}).get("properties") or {})])
rec("说明含 request_login 和 UTC", "request_login" in A.init["instructions"] and "UTC" in A.init["instructions"])

t0 = time.time(); e, sc, txt, _ = A.call("browser_navigate", url="https://example.com")
rec("打开 example.com：page 和 snapshot", not e and sc["page"]["title"] == "Example Domain" and "[ref=" in sc["snapshot"]["text"]
    and not LOCAL.search(txt) and json.loads(txt) == sc, "%.1fs" % (time.time() - t0))
e, sc, _, _ = A.call("browser_navigate", url="https://example.com", snapshot="none")
rec("snapshot=none 不带快照", not e and sc["snapshot"].get("omitted") and "text" not in sc["snapshot"], sc.get("snapshot"))
e, sc, _, types = A.call("browser_take_screenshot")
rec("截图：image 内容块", not e and "image" in types and sc["attachments"][0]["type"] == "image", types)
e, sc, txt, types = A.call("browser_pdf_save")
rec("PDF 作为嵌入资源返回", not e and "resource" in types and not LOCAL.search(txt), types)
e, sc, _, _ = A.call("browser_navigate")
rec("缺参数：invalid_argument", e and code_of(sc) == "invalid_argument" and sc["error"]["details"]["field"] == "url", sc)
e, sc, _, _ = A.call("browser_navigate", url="https://this-domain-does-not-exist-zz9q.com/")
rec("不存在的域名：ERR_NAME_NOT_RESOLVED，没有颜色码和内部函数名", e and code_of(sc) == "navigation_failed"
    and sc["error"]["details"]["net_error"] == "ERR_NAME_NOT_RESOLVED" and "\\u001b" not in json.dumps(sc) and "callTool" not in json.dumps(sc), sc)
e, sc, _, _ = A.call("browser_click", target="e99999", element="nothing")
rec("找不到元素：ref_not_found、可重试", e and code_of(sc) == "ref_not_found" and sc["error"]["retryable"] is True, sc)
for u, why in [("http://127.0.0.1:8087/admin/state", "loopback"), ("http://localhost:8766/status", "loopback"),
               ("http://192.168.1.1/", "private"), ("file:///C:/Windows/win.ini", "scheme")]:
    e, sc, _, _ = A.call("browser_navigate", url=u)
    rec("拦截 " + u, e and code_of(sc) == "url_blocked" and sc["error"]["details"]["reason"] == why, sc)
e, sc, _, _ = A.call("browser_run_code_unsafe", code="async (page) => 1")
rec("Node 里的任意代码不提供", e and code_of(sc) == "tool_unavailable", sc)

e, sc, _, _ = A.call("browser_navigate", url="http://127.0.0.1:18099/")
rec("允许的本机地址可访问", not e and sc["page"]["title"] == "Local Test", sc.get("page") or sc)
e, sc, _, _ = A.call("browser_evaluate", function="async () => { try { const r = await fetch('http://127.0.0.1:8087/admin/state'); return 'open ' + r.status; } catch (e) { return 'blocked'; } }")
rec("页面脚本连不到其他本机端口", not e and "open 200" not in sc.get("result", ""), sc.get("result"))
e, sc, _, _ = A.call("browser_evaluate", function="() => navigator.userAgent")
rec("UA 不带 Headless", not e and "Headless" not in sc["result"] and "Edg/" in sc["result"], sc.get("result"))
e, sc, _, _ = A.call("browser_get_text")
rec("browser_get_text：正文（main）转 markdown", not e and sc["scope"] == "main" and "# Local test page" in sc["text"]
    and "| a | 1 |" in sc["text"] and "menu item" not in sc["text"], sc.get("text"))
e, sc, _, _ = A.call("browser_get_text", scope="page", format="text")
rec("browser_get_text：整页纯文本", not e and "menu item" in sc["text"], sc.get("scope"))
A.call("browser_mouse_move_xy", x=400, y=300)
e, sc, _, _ = A.call("browser_mouse_wheel", deltaX=0, deltaY=2500)
time.sleep(0.8)
e2, sc2, _, _ = A.call("browser_evaluate", function="() => window.scrollY")
rec("滚轮", not e and num(sc2.get("result")) > 1000, sc2.get("result"))
A.call("browser_evaluate", function="() => window.scrollTo(0, 0)")
snap = A.call("browser_snapshot")[1]["snapshot"]["text"]
fref = (re.search(r'button "Choose File" \[ref=(\w+)\]', snap) or re.search(r'\[ref=(\w+)\][^\n]*Choose', snap) or [None, "e5"])[1]
A.call("browser_click", target=fref, element="file input")
e, sc, _, _ = A.call("browser_file_upload", files=[{"name": "hello.txt", "content_base64": base64.b64encode(b"hello world").decode()}])
e2, sc2, _, _ = A.call("browser_evaluate", function="() => document.getElementById('o').textContent")
rec("上传：调用方给内容（base64）", not e and "hello.txt:11" in sc2.get("result", ""), [sc.get("error"), sc2.get("result")])
snap = A.call("browser_snapshot")[1]["snapshot"]["text"]
lref = (re.search(r'link "report" \[ref=(\w+)\]', snap) or [None, "e9"])[1]
A.call("browser_click", target=lref, element="report")
time.sleep(1)
e, scl, _, _ = A.call("browser_read_download")
e2, scr, _, _ = A.call("browser_read_download", name="report.csv")
rec("下载后读取内容", any(d["name"] == "report.csv" for d in scl.get("downloads", [])) and scr.get("content") == "a,b\n1,2\n", [scl, scr])

e, sc, _, _ = B.call("browser_navigate", url="https://example.com")
e, sca, _, _ = A.call("browser_tabs", action="list")
e, scb, _, _ = B.call("browser_tabs", action="list")
rec("两个会话各用各的浏览器", "18099" in sca["tabs"][0]["url"] and "example.com" in scb["tabs"][0]["url"], [sca.get("tabs"), scb.get("tabs")])

e, sc, _, _ = B.call("browser_navigate", url="https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)")
sn = sc.get("snapshot", {})
rec("大页面快照默认截到 2 万字", sn.get("truncated") and len(sn["text"]) <= 20000 and sn.get("next_offset") == len(sn["text"]),
    {k: v for k, v in sn.items() if k != "text"})
e, sc2, _, _ = B.call("browser_snapshot", offset=sn.get("next_offset", 1), limit=5000)
rec("快照翻页（不重抓）", not e and sc2["snapshot"]["offset"] == sn.get("next_offset") and len(sc2["snapshot"]["text"]) == 5000)
e, sc, _, _ = B.call("browser_get_text", limit=3000)
e2, sc2, _, _ = B.call("browser_get_text", offset=3000, limit=3000)
rec("正文分页", not e and sc["next_offset"] == 3000 and sc2["offset"] == 3000 and sc["text"] != sc2["text"], sc.get("total_chars"))
t0 = time.time()
B.call("browser_navigate", url="https://arxiv.org/pdf/1706.03762")
e, sc, _, _ = B.call("browser_get_text", limit=1500)
rec("在线 PDF：提取文字", not e and sc.get("source") == "pdf" and sc.get("pages", 0) > 5 and "Attention" in sc.get("text", ""),
    [sc.get("pages"), sc.get("total_chars"), round(time.time() - t0, 1), sc.get("error")])
B.call("browser_navigate_back")
e, sc, _, _ = B.call("browser_navigate_forward")
rec("前进", not e and "arxiv.org/pdf" in sc.get("page", {}).get("url", ""), sc.get("page") or sc)
e, sc, _, _ = B.call("browser_reload", wait_until="load")
rec("刷新", not e and sc.get("page"), sc.get("page") or sc)
e, sc, _, _ = B.call("browser_navigate", url="https://www.bing.com/search?q=playwright+mcp", wait_until="networkidle")
rec("wait_until=networkidle", not e and sc.get("snapshot", {}).get("total_chars", 0) > 6000, sc.get("snapshot", {}).get("total_chars"))

B.call("browser_navigate", url="https://httpbin.org/cookies/set?sid=SECRET123")
B.call("browser_evaluate", function="async () => (await fetch('/headers', {headers: {Authorization: 'Bearer TOKEN456'}})).status")
e, sc, _, _ = B.call("browser_network_requests")
idx = re.findall(r"(\d+)\. \[GET\] https://httpbin.org/headers", sc.get("result", ""))
e, sc, _, _ = B.call("browser_network_request", index=int(idx[-1]) if idx else 1, part="request-headers")
rec("网络记录里 Cookie、Authorization 打码", not e and "cookie: [redacted]" in sc.get("result", "") and "SECRET123" not in sc.get("result", "")
    and "TOKEN456" not in sc.get("result", ""), sc.get("result", "")[:200])
B.call("browser_start_tracing")
B.call("browser_navigate", url="https://example.com")
e, sc, _, _ = B.call("browser_stop_tracing")
tr = [d for d in sc.get("downloads", []) if d["name"].endswith(".trace")]
e2, sc2, _, _ = B.call("browser_read_download", name=tr[0]["name"], encoding="base64", limit=1000) if tr else (True, {}, "", [])
rec("录制 trace 并读取", tr and not e2 and sc2.get("length_bytes", 0) > 0, sc.get("downloads"))
e, sc, _, _ = B.call("browser_reset", locale="en-US", timezone_id="America/New_York")
B.call("browser_navigate", url="https://example.com")
e, sc2, _, _ = B.call("browser_evaluate", function="() => [navigator.language, Intl.DateTimeFormat().resolvedOptions().timeZone]")
rec("browser_reset：语言和时区", "en-US" in sc2.get("result", "") and "America/New_York" in sc2.get("result", ""), sc2.get("result"))
e, sc, _, _ = B.call("grant_info")
rec("grant_info：浏览器设置", sc["browser"]["locale"] == "en-US" and sc["browser"]["allowed_local_hosts"] == ["127.0.0.1:18099"]
    and sc["browser"]["sessions_open"] == 2 and "folders" not in sc, sc.get("browser"))

# 登录请求：完成（不保存）
out = {}
th = threading.Thread(target=lambda: out.update(r=A.call("request_login", url="https://example.com/", reason="验收测试")))
th.start(); time.sleep(2)
mine = [r for r in adm("GET", "logins/requests")["requests"] if r["grant_id"] == gid]
rec("登录请求出现在列表", len(mine) == 1, mine)
rid = mine[0]["id"]
adm("POST", "logins/requests/" + rid, {"action": "start"})
e, sc, _, _ = A.call("check_login", request_id=rid, wait_seconds=0)
rec("登录中：in_progress，next 指向 check_login", not e and sc["status"] == "in_progress" and sc["next"]["tool"] == "check_login", sc)
state = {"cookies": [{"name": "aitemp_accept", "value": "1", "domain": ".example.com", "path": "/", "expires": -1,
                      "httpOnly": False, "secure": True, "sameSite": "Lax"}], "origins": []}
sv = adm("POST", "logins/save", {"state": state, "domains": ["example.com"], "request": rid, "titles": {}, "save": False})
th.join(30)
e, sc, _, _ = out.get("r", (True, {}, "", []))
rec("完成登录：logged_in，带刷新后的页面", sv.get("ok") and not e and sc["status"] == "logged_in" and sc["saved"] is False
    and sc.get("page", {}).get("url"), sc)       # 写入登录后刷新当前页面（这个会话当时在本机测试页）
e, sc, _, _ = A.call("browser_cookie_list", domain="example.com")
rec("登录网站的 Cookie 值不给", not e and "aitemp_accept=[redacted" in sc.get("result", "") and "aitemp_accept=1" not in sc.get("result", ""), sc.get("result"))
rec("未保存到浏览器登录", not Path(r"C:\Users\blender\TempAuth\logins\example.com.json").exists())
out = {}
th = threading.Thread(target=lambda: out.update(r=A.call("request_login", url="https://example.org/", reason="验收测试：拒绝")))
th.start(); time.sleep(2)
reqs = [r for r in adm("GET", "logins/requests")["requests"] if r.get("state") == "pending"]
adm("POST", "logins/requests/" + reqs[0]["id"], {"action": "decline"})
th.join(30)
e, sc, _, _ = out.get("r", (False, {}, "", []))
rec("拒绝：declined、isError", e and sc["status"] == "declined", sc)

gv = [x for x in adm("GET", "grants?status=all")["grants"] if x["id"] == gid][0]
rec("浏览器操作计数，不占次数", gv.get("browser_ops", 0) >= 30 and gv["used"] == 0, (gv.get("browser_ops"), gv["used"]))
r = adm("POST", "grants/%s/revoke" % gid)
rec("吊销", r.get("ok"), "%d ms" % r.get("ms", -1))
time.sleep(2)
outdir = Path(r"C:\Users\blender\TempAuth\browser\%s\output" % gid)
left = sorted(f.name for f in outdir.iterdir() if f.is_file()) if outdir.exists() else []
rec("快照、截图、PDF、控制台日志、上传的临时文件不留下（下载的文件保留）", left == ["report.csv"], left)
e, sc, _, _ = A.call("browser_navigate", url="https://example.com")
rec("吊销后调用被拒：grant_revoked", e and code_of(sc) == "grant_revoked", sc)
ps = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Process | ? { $_.CommandLine -match '%s' }).Count" % gid],
                    capture_output=True, text=True).stdout.strip()
rec("浏览器进程都已结束", ps in ("0", ""), ps)
srv.shutdown()
print("RESULT %d/%d" % (sum(1 for _, ok in res if ok), len(res)))
