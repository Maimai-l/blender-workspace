#!/usr/bin/env python3
"""Tiny MCP (streamable HTTP) client used during development of Word Defense.

The three MCP services (exec on Windows, Unity, Blender) are reachable from the sandbox; this lets scripts here
push source files to the Windows machine and run Blender / Unity code from local files.

Usage:
  mcpc.py bash  "<git bash command>" [--timeout MS]
  mcpc.py ps    "<powershell code>" [--timeout MS]
  mcpc.py push  LOCAL_DIR REMOTE_DIR [--all]     # sync changed text files (hash cache in LOCAL_DIR/.sync-state.json)
  mcpc.py pull  REMOTE_FILE LOCAL_FILE           # copy one file back (any type)
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


def _bash_json(res):
    try:
        j = json.loads(res)
    except Exception:
        return res
    out = j.get("stdout", "") or ""
    if j.get("stderr"):
        out += ("\n" if out else "") + "STDERR: " + j["stderr"]
    return out


def run_bash(cmd, timeout_ms=110000):
    """Runs a Git Bash command on the Windows machine (exec = Claude Code served over MCP)."""
    res = call("exec", "Bash", {"command": cmd, "timeout": timeout_ms, "description": "wd tools"}, timeout=timeout_ms / 1000 + 60)
    return _bash_json(res)


def run_ps(code, timeout_ms=110000):
    """Runs Windows PowerShell 5.1 code (passed inline with -Command; no script files)."""
    import shlex
    return run_bash("MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -NonInteractive -Command " + shlex.quote(code), timeout_ms)


# kept for older helper scripts: they passed PowerShell code
def run_exec(cmd, stdin_text=None, timeout_ms=85000):
    if stdin_text is not None:
        raise SystemExit("stdin is not supported by the exec service any more")
    return run_ps(cmd, timeout_ms)


def win_path(remote_dir, rel):
    return remote_dir.rstrip("\\/") + "\\" + rel.replace("/", "\\")


def write_remote(path, text):
    call("exec", "Read", {"file_path": path, "limit": 1})          # the Write tool requires a read of existing files
    res = call("exec", "Write", {"file_path": path, "content": text})
    return '"type":"create"' in res or '"type":"update"' in res, res[:300]


def push(local_dir, remote_dir, all_files=False):
    state_path = os.path.join(local_dir, ".sync-state.json")
    state = {}
    if os.path.exists(state_path) and not all_files:
        state = json.load(open(state_path))
    changed, new_state = [], {}
    for root, dirs, names in os.walk(local_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for n in names:
            if n.startswith(".") or n.endswith(".pyc"):
                continue
            p = os.path.join(root, n)
            rel = os.path.relpath(p, local_dir).replace(os.sep, "/")
            data = open(p, "rb").read()
            h = hashlib.sha1(data).hexdigest()
            new_state[rel] = state.get(rel)
            if state.get(rel) != h:
                changed.append((rel, data, h))
            else:
                new_state[rel] = h
    removed = [r for r in state if r not in new_state]
    if not changed and not removed:
        print("nothing to push")
        return
    for rel, data, h in changed:
        ok, info = write_remote(win_path(remote_dir, rel), data.decode("utf-8"))
        if ok:
            new_state[rel] = h
            print("  +", rel)
        else:
            print("  ! FAILED", rel, info)
    for rel in removed:
        wp = win_path(remote_dir, rel).replace("\\", "/")
        print(run_bash('rm -f "%s" "%s.meta" && echo "  - %s"' % (wp, wp, rel)))
        new_state.pop(rel, None)
    json.dump({k: v for k, v in new_state.items() if v}, open(state_path, "w"), indent=0)
    print("pushed %d, removed %d" % (len(changed), len(removed)))


def pull(remote_path, local_path):
    """Copies one remote file (any type) into the sandbox, 20 KB per call."""
    rp = remote_path.replace("\\", "/")
    size = int(run_bash('stat -c %%s "%s"' % rp).strip().split()[0])
    chunks = []
    for i in range(0, size, 20000):
        out = run_bash('dd if="%s" bs=20000 skip=%d count=1 2>/dev/null | base64 -w0' % (rp, i // 20000))
        chunks.append(base64.b64decode(out.strip()))
    data = b"".join(chunks)
    if len(data) != size:
        raise SystemExit("pull size mismatch for %s: %d != %d" % (remote_path, len(data), size))
    os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
    open(local_path, "wb").write(data)
    print(local_path, size)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd = a[0]
    if cmd in ("bash", "exec", "ps"):
        timeout = 110000
        rest = a[1:]
        if "--timeout" in rest:
            i = rest.index("--timeout"); timeout = int(rest[i + 1]); del rest[i:i + 2]
        print(run_ps(rest[0], timeout) if cmd in ("exec", "ps") else run_bash(rest[0], timeout))
    elif cmd == "push":
        push(a[1], a[2], "--all" in a)
    elif cmd == "pull":
        pull(a[1], a[2])
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
