# 浏览器授权验收（网关 3.0，blender 账号运行）。结果直接打印；签发浏览器授权，测完吊销。
# 用到外网（example.com、维基百科、arxiv、Bing、httpbin），本机起一个 18099 的测试页。
# 备用网关上跑：TA_ADMIN=18087 TA_MCP=18086 TA_DATA=<数据目录> TA_TOKEN=<令牌文件>
import base64, http.server, json, os, re, subprocess, threading, time, urllib.request, urllib.error
from pathlib import Path
ADMIN, MCP = os.environ.get("TA_ADMIN", "8087"), os.environ.get("TA_MCP", "8086")
DATA = Path(os.environ.get("TA_DATA", r"C:\Users\blender\TempAuth"))
TOK = Path(os.environ.get("TA_TOKEN", r"C:\ProgramData\BlenderMCP\tempauth.token")).read_text().strip()
DEMO = os.environ.get("TA_DEMO") == "1"          # 备用网关是 --demo：登录不写进浏览器
OP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
res = []
PAGE = b"""<!doctype html><html><head><title>Local Test</title></head><body>
<main><h1>Local test page</h1><p>Hello from <b>18099</b>. The quick brown fox jumps over the lazy dog in this paragraph,
which is long enough for article extraction to keep it as the main content of the page and not a fragment.</p>
<p>Second paragraph mentions the magic number 4242 so that find can locate it in the extracted text easily.</p>
<table><tr><th>k</th><th>v</th></tr><tr><td>a</td><td>1</td></tr></table></main>
<nav>menu item</nav>
<label>Name <input id=n></label><button onclick="document.getElementById('o').textContent='hi '+document.getElementById('n').value">Greet</button>
<select id=s><option>red</option><option>blue</option></select>
<label><input type=checkbox id=c> agree</label>
<input type=file id=f onchange="document.getElementById('u').textContent=this.files[0].name+':'+this.files[0].size">
<div id=o>none</div><div id=u>none</div><a href="/report.csv" download>report</a>
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
    print(("PASS " if ok else "FAIL ") + name + " | " + json.dumps(detail, ensure_ascii=False, default=str)[:260], flush=True)


def adm(m, p, b=None):
    r = urllib.request.Request(f"http://127.0.0.1:{ADMIN}/admin/" + p, method=m, data=json.dumps(b).encode() if b is not None else None,
                               headers={"X-Tempauth-Token": TOK, "Content-Type": "application/json"})
    try:
        return json.loads(OP.open(r, timeout=100).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


class Sess:
    def __init__(self, url):
        self.url, self.sid = url.replace("https://tmcp.maimaiqiu.work", f"http://127.0.0.1:{MCP}"), None
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
        r = self.rpc("tools/call", {"name": tool, "arguments": a})
        c = r.get("content", [])
        return r.get("isError"), r.get("structuredContent") or {}, [x["type"] for x in c]


def code_of(sc):
    return ((sc or {}).get("error") or {}).get("code")


def ref(els, pattern):
    m = re.search(r"^(\w+) " + pattern, els, re.M)        # ref 可能带框架前缀，如 f4e16
    return m.group(1) if m else None


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 18099), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
g = adm("POST", "grants", {"browser": True, "minutes": 30, "name": "浏览器验收", "allow_hosts": ["127.0.0.1:18099"]})
U, gid = g["url"], g["grant"]["id"]
rec("签发（允许 127.0.0.1:18099）", g.get("ok") and g["grant"]["allow_hosts"] == ["127.0.0.1:18099"] and "web_search" in g["prompt"])
A, B = Sess(U), Sess(U)
rec("每个 MCP 会话一个编号", A.sid and B.sid and A.sid != B.sid)
tools = A.rpc("tools/list")["tools"]
names = [t["name"] for t in tools]
rec("默认工具精简（≤ 15 个），定义小", len(names) <= 15 and {"web_search", "web_read", "browser_open", "browser_act", "browser_eval"} <= set(names)
    and len(json.dumps(tools)) < 20000, [len(names), len(json.dumps(tools))])
gf = adm("POST", "grants", {"browser": True, "minutes": 10, "name": "完整工具", "browser_full": True})
nf = [t["name"] for t in Sess(gf["url"]).rpc("tools/list")["tools"]]
rec("勾了完整浏览器工具时列出原始工具", len(nf) > 50 and "browser_click" in nf and "browser_run_code_unsafe" not in nf, len(nf))
adm("POST", "grants/%s/revoke" % gf["grant"]["id"])
e, sc, _ = A.call("grant_info")
rec("语言时区跟随出口", sc["browser"]["locale"] and sc["browser"]["timezone_id"] and sc["browser"]["blocklist_size"] > 1000, sc.get("browser"))

# 查资料
t0 = time.time(); e, sc, _ = A.call("web_search", query="attention is all you need arxiv")
rec("web_search（Bing）", not e and len(sc.get("results", [])) >= 5 and all(r["url"].startswith("http") for r in sc["results"]),
    [round(time.time() - t0, 1), [r["url"] for r in sc.get("results", [])[:3]]])
e, sc, _ = A.call("web_read", url="https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)", limit=4000)
rec("web_read 维基百科：article，没有侧栏", not e and sc["scope"] == "article" and "[checkbox" not in sc["text"] and sc["total_chars"] > 20000
    and sc["next_offset"] == 4000, [sc.get("scope"), sc.get("total_chars"), sc.get("text", "")[:120]])
e, sc, _ = A.call("web_read", find='"self-attention" encoder', limit=3000)
rec("web_read find：只给相关段落", not e and sc["matches"] and all(("attention" in m["text"].lower() or "encoder" in m["text"].lower()) for m in sc["matches"]),
    [sc.get("match_lines"), len(sc.get("matches", []))])
t0 = time.time(); e, sc, _ = A.call("web_read", url="https://arxiv.org/pdf/1706.03762", limit=1500)
rec("web_read 在线 PDF", not e and sc["source"] == "pdf" and sc["pages"] >= 10 and "Attention" in sc["text"], [sc.get("pages"), round(time.time() - t0, 1)])
e, sc, _ = A.call("web_read", url="https://www.bing.com/search?q=playwright", limit=2000)
rec("web_read 搜索结果页：正文为空时退回整页", not e and sc["total_chars"] > 500, [sc.get("scope"), sc.get("total_chars"), sc.get("note")])
e, sc, _ = A.call("browser_open", url="https://www.codenong.com/")
rec("屏蔽列表里的网站打不开", e and code_of(sc) == "url_blocked" and sc["error"]["details"]["reason"] == "blocklist", sc)

# 操作网页
e, sc, _ = A.call("browser_open", url="http://127.0.0.1:18099/")
els = sc.get("elements", {}).get("text", "")
rec("browser_open：元素列表", not e and sc["page"]["title"] == "Local Test" and ref(els, "textbox") and ref(els, r'button "Greet"')
    and sc["elements"]["total_chars"] < sc["elements"]["snapshot_chars"], els[:300])
tb, bt, cb, sel, fi = ref(els, "textbox"), ref(els, r'button "Greet"'), ref(els, "checkbox"), ref(els, "combobox"), ref(els, r'button "Choose File"')
e, sc, _ = A.call("browser_act", actions=[{"type": {"ref": tb, "text": "Ada"}}, {"click": bt}, {"check": cb}, {"select": {"ref": sel, "values": ["blue"]}},
                                          {"upload": {"ref": fi, "files": [{"name": "hello.txt", "content_base64": base64.b64encode(b"hello world").decode()}]}},
                                          {"scroll": {"dy": 1500}}])
rec("browser_act：一次执行 6 个操作，返回滚动位置", not e and sc.get("completed") == 6 and sc["scroll"]["y"] > 1000, [sc.get("completed"), sc.get("scroll"), sc.get("error")])
e, sc, _ = A.call("browser_eval", function="() => [document.getElementById('o').textContent, document.getElementById('u').textContent, document.getElementById('c').checked, document.getElementById('s').value, document.querySelectorAll('p').length]")
rec("browser_eval：原始 JSON；操作都生效", not e and sc.get("value") == ["hi Ada", "hello.txt:11", True, "blue", 2], sc)
e, sc, _ = A.call("browser_act", actions=[{"click": "e99999"}])
rec("browser_act 出错：指出第几个操作", e and code_of(sc) == "ref_not_found" and sc["error"]["details"]["index"] == 0, sc)
e, sc, _ = A.call("browser_act", actions=[{"upload": {"files": [{"name": "x.txt", "content_base64": "eA=="}]}}])
rec("没打开文件选择框就上传：no_file_chooser", e and code_of(sc) == "no_file_chooser", sc)
e, sc, _ = A.call("browser_act", actions=[{"scroll": {"to": "top"}}, {"click": ref(els, r'link "report"')}], observe="none")
time.sleep(1)
e, sc2, _ = A.call("browser_tabs")
rec("下载：报告文件名，不留下载页标签", not e and any(d["name"] == "report.csv" for d in sc.get("downloads", []))
    and not any("downloads" in t["url"] for t in sc2.get("tabs", [])), [sc.get("downloads"), sc2.get("tabs")])
e, sc, _ = A.call("browser_files", action="read", name="report.csv")
rec("browser_files 读下载", not e and sc.get("content") == "a,b\n1,2\n", sc)
e, sc, _ = A.call("browser_observe", mode="full", limit=500)
e2, sc2, _ = A.call("browser_observe", mode="full", offset=500, limit=500)
rec("browser_observe full：分页", not e and sc["snapshot"]["next_offset"] == 500 and sc2["snapshot"]["offset"] == 500)
e, sc, types = A.call("browser_screenshot")
rec("截图", not e and "image" in types, types)
B.call("browser_open", url="https://example.com", observe="none")
e, sa, _ = A.call("browser_tabs")
e, sb, _ = B.call("browser_tabs")
rec("两个会话各用各的浏览器", "18099" in sa["tabs"][0]["url"] and "example.com" in sb["tabs"][0]["url"])

# 状态和评测
B.call("browser_open", url="https://httpbin.org/cookies/set?sid=SECRET123", observe="none")
B.call("browser_eval", function="async () => (await fetch('/headers', {headers: {Authorization: 'Bearer TOKEN456'}})).status")
e, sc, _ = B.call("browser_inspect", kind="network", filter="httpbin", limit=3)
idx = [i["index"] for i in sc.get("items", []) if i["url"].endswith("/headers")]
rec("browser_inspect network：分页", not e and len(sc["items"]) <= 3 and sc["total"] >= 1, [sc.get("total"), sc.get("items")])
if not idx:
    e, scall, _ = B.call("browser_inspect", kind="network", filter="headers")
    idx = [i["index"] for i in scall.get("items", [])]
e, sc, _ = B.call("browser_inspect", kind="network", index=idx[-1] if idx else 1, part="request-headers")
rec("请求头里的 Cookie、Authorization 打码", not e and "SECRET123" not in sc.get("text", "") and "TOKEN456" not in sc.get("text", "")
    and "[redacted]" in sc.get("text", ""), sc.get("text", "")[:200])
e, sc, _ = B.call("browser_inspect", kind="cookies", filter="httpbin.org")
rec("browser_inspect cookies", not e and any(c["name"] == "sid" for c in sc.get("items", [])), sc.get("items"))
e, sc, _ = B.call("browser_reset", locale="en-GB", timezone_id="Europe/London")
B.call("browser_open", url="https://example.com", observe="none")
e, sc2, _ = B.call("browser_eval", function="() => [navigator.language, Intl.DateTimeFormat().resolvedOptions().timeZone]")
rec("browser_reset：语言和时区", sc2.get("value") == ["en-GB", "Europe/London"], sc2)

# 登录请求
out = {}
th = threading.Thread(target=lambda: out.update(r=A.call("request_login", url="https://example.com/", reason="验收测试")))
th.start(); time.sleep(2)
mine = [r for r in adm("GET", "logins/requests")["requests"] if r["grant_id"] == gid]
rid = mine[0]["id"] if mine else ""
adm("POST", "logins/requests/" + rid, {"action": "start"})
state = {"cookies": [{"name": "aitemp_accept", "value": "1", "domain": ".example.com", "path": "/", "expires": -1,
                      "httpOnly": False, "secure": True, "sameSite": "Lax"}], "origins": []}
sv = adm("POST", "logins/save", {"state": state, "domains": ["example.com"], "request": rid, "titles": {}, "save": False})
th.join(30)
e, sc, _ = out.get("r", (True, {}, []))
rec("登录请求：logged_in", sv.get("ok") and not e and sc["status"] == "logged_in" and (DEMO or sc.get("page")), sc)
if not DEMO:
    e, sc, _ = A.call("browser_inspect", kind="cookies", filter="example.com")
    rec("登录网站的 Cookie 值不给", not e and any(c["name"] == "aitemp_accept" and "redacted" in c["value"] for c in sc.get("items", [])), sc.get("items"))

gv = [x for x in adm("GET", "grants?status=all")["grants"] if x["id"] == gid][0]
rec("浏览器操作计数，不占次数", gv.get("browser_ops", 0) >= 20 and gv["used"] == 0, (gv.get("browser_ops"), gv["used"]))
r = adm("POST", "grants/%s/revoke" % gid)
rec("吊销", r.get("ok"), "%d ms" % r.get("ms", -1))
time.sleep(2)
outdir = DATA / "browser" / gid / "output"
left = sorted(f.name for f in outdir.iterdir() if f.is_file()) if outdir.exists() else []
rec("临时文件不留下（下载的文件保留）", left == ["report.csv"], left)
e, sc, _ = A.call("web_read", url="https://example.com")
rec("吊销后调用被拒：grant_revoked", e and code_of(sc) == "grant_revoked", sc)
ps = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Process | ? { $_.CommandLine -match '%s' }).Count" % gid], capture_output=True, text=True).stdout.strip()
rec("浏览器进程都已结束", ps in ("0", ""), ps)
srv.shutdown()
print("RESULT %d/%d" % (sum(1 for _, ok in res if ok), len(res)))
