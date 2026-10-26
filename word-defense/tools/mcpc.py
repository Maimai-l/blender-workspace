#!/usr/bin/env python3
"""Tiny MCP (streamable HTTP) client used during development of Word Defense.

The three MCP services (exec on Windows, Unity, Blender) are reachable from the sandbox; this lets scripts here
push source files to the Windows machine and run Blender / Unity code from local files.

Usage:
  mcpc.py exec  "<powershell command>" [--stdin FILE] [--timeout MS]
  mcpc.py push  LOCAL_DIR REMOTE_DIR [--all]     # sync changed files (hash cache in LOCAL_DIR/.sync-state.json)
  mcpc.py blender FILE.py [--prompt TEXT]        # run a Blender Python file
  mcpc.py unity FILE.cs                          # run C# method body with Unity execute_code
  mcpc.py tool SERVER NAME JSON_ARGS             # raw tool call
"""
import base64, hashlib, json, os, sys, time, urllib.request

SERVERS = {"exec": "EXEC_MCP_URL", "unity": "UNITY_MCP_URL", "blender": "BLENDER_MCP_URL"}
_sessions = {}


def _post(url, payload, session=None, timeout=600):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("User-Agent", "curl/8.5.0")
    if session:
        req.add_header("Mcp-Session-Id", session)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        sid = resp.headers.get("Mcp-Session-Id")
        ctype = resp.headers.get("Content-Type", "")
        body = resp.read().decode("utf-8", "replace")
    if not body.strip():
        return sid, None
    if "text/event-stream" in ctype:
        result = None
        for line in body.splitlines():
            if line.startswith("data:"):
                try:
                    msg = json.loads(line[5:].strip())
                except Exception:
                    continue
                if "result" in msg or "error" in msg:
                    result = msg
        return sid, result
    return sid, json.loads(body)


def _session(server):
    if server in _sessions:
        return _sessions[server]
    url = os.environ[SERVERS[server]]
    sid, _ = _post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                         "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                    "clientInfo": {"name": "wd-sync", "version": "1.0"}}})
    _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    _sessions[server] = (url, sid)
    return url, sid


def call(server, name, args, timeout=600):
    url, sid = _session(server)
    _, res = _post(url, {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 1000000000, "method": "tools/call",
                         "params": {"name": name, "arguments": args}}, sid, timeout)
    if res is None:
        return ""
    if "error" in res:
        return "MCP ERROR: " + json.dumps(res["error"], ensure_ascii=False)
    out = []
    for c in res.get("result", {}).get("content", []):
        if c.get("type") == "text":
            out.append(c["text"])
    if res.get("result", {}).get("isError"):
        out.insert(0, "[tool reported error]")
    return "\n".join(out)


def run_exec(cmd, stdin_text=None, timeout_ms=85000):
    args = {"command_line": cmd, "timeout_ms": timeout_ms}
    if stdin_text is not None:
        args["stdin_text"] = stdin_text
    return call("exec", "run_process", args, timeout=timeout_ms / 1000 + 60)


WRITER_JS = r"""
const fs=require('fs'),path=require('path');
let s='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{
 const j=JSON.parse(s);let n=0;
 for(const [rel,b64] of Object.entries(j.files)){const p=path.join(j.root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});
  fs.writeFileSync(p,Buffer.from(b64,'base64'));n++;}
 for(const rel of (j.remove||[])){const p=path.join(j.root,rel);try{fs.unlinkSync(p);try{fs.unlinkSync(p+'.meta')}catch(e){}}catch(e){}}
 console.log('wrote '+n+' files to '+j.root+((j.remove||[]).length?(', removed '+j.remove.length):''));});
"""


def push(local_dir, remote_dir, all_files=False):
    state_path = os.path.join(local_dir, ".sync-state.json")
    state = {}
    if os.path.exists(state_path) and not all_files:
        state = json.load(open(state_path))
    files, new_state = {}, {}
    for root, dirs, names in os.walk(local_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for n in names:
            if n.startswith(".") or n.endswith(".pyc"):
                continue
            p = os.path.join(root, n)
            rel = os.path.relpath(p, local_dir).replace(os.sep, "/")
            data = open(p, "rb").read()
            h = hashlib.sha1(data).hexdigest()
            new_state[rel] = h
            if state.get(rel) != h:
                files[rel] = base64.b64encode(data).decode()
    removed = [r for r in state if r not in new_state]
    if not files and not removed:
        print("nothing to push")
        return
    payload = json.dumps({"root": remote_dir, "files": files, "remove": removed})
    js = WRITER_JS.replace("\n", " ")
    out = run_exec("& 'D:\\Program Files\\node.EXE' -e \"" + js.replace('"', '\\"') + "\"", stdin_text=payload)
    print(out)
    if "wrote" in out:
        json.dump(new_state, open(state_path, "w"), indent=0)
        for r in sorted(files):
            print("  +", r)
        for r in removed:
            print("  -", r)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd == "exec":
        stdin = None
        timeout = 85000
        rest = a[1:]
        if "--stdin" in rest:
            i = rest.index("--stdin"); stdin = open(rest[i + 1], encoding="utf-8").read(); del rest[i:i + 2]
        if "--timeout" in rest:
            i = rest.index("--timeout"); timeout = int(rest[i + 1]); del rest[i:i + 2]
        print(run_exec(rest[0], stdin, timeout))
    elif cmd == "push":
        push(a[1], a[2], "--all" in a)
    elif cmd == "blender":
        code = open(a[1], encoding="utf-8").read()
        prompt = "单词守城：在 Blender 中制作原创模型，再导入 Unity。建模和 HUD 都要现代、不过时、有设计感。"
        if "--prompt" in a:
            prompt = a[a.index("--prompt") + 1]
        print(call("blender", "execute_blender_code", {"code": code, "user_prompt": prompt}, timeout=900))
    elif cmd == "unity":
        code = open(a[1], encoding="utf-8").read()
        print(call("unity", "execute_code", {"action": "execute", "code": code}, timeout=900))
    elif cmd == "tool":
        print(call(a[1], a[2], json.loads(a[3])))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
