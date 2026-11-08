#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Minimal client for the exec MCP server (Claude Code served over MCP on the Blender PC, see CLAUDE.md).
usage: execc.py bash "<command>" ["<description>"]
Runs in Git Bash as the blender account; paths look like /c/Users/blender/... Only the 7 tools allowed in
.claude/settings.json can be called."""
import json, os, ssl, sys, urllib.request
import xyp
CTX = ssl.create_default_context(cafile=xyp.CA) if xyp.CA else ssl.create_default_context()
URL = os.environ['EXEC_MCP_URL']
def post(payload, sid=None, timeout=600):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), method='POST')
    req.add_header('Content-Type', 'application/json'); req.add_header('User-Agent', 'xy-mcp-client/1.0')
    req.add_header('Accept', 'application/json, text/event-stream')
    if sid: req.add_header('Mcp-Session-Id', sid)
    op = urllib.request.build_opener(urllib.request.ProxyHandler(), urllib.request.HTTPSHandler(context=CTX))
    with op.open(req, timeout=timeout) as r:
        return r.headers.get('Mcp-Session-Id'), r.read().decode('utf-8', 'replace')
def session():
    sid, _ = post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'xy-cli', 'version': '1.0'}}})
    post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, sid)
    return sid
# .claude/settings.json denies the other 13 exec tools for the harness; a direct client must honour that itself
ALLOWED = {'Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep', 'TaskStop'}

def call(name, args):
    if name not in ALLOWED:
        raise SystemExit('exec tool %r is not allowed in this repo (see .claude/settings.json)' % name)
    sid = session()
    _, body = post({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}}, sid)
    txt = ''.join(l[5:] for l in body.splitlines() if l.startswith('data:')) or body
    return json.loads(txt)
if __name__ == '__main__':
    if sys.argv[1] == 'bash':
        r = call('Bash', {'command': sys.argv[2], 'description': sys.argv[3] if len(sys.argv) > 3 else 'run command'})
        for c in r.get('result', {}).get('content', []):
            t = c.get('text', '')
            try:
                j = json.loads(t); print(j.get('stdout', '')); print(j.get('stderr', ''), file=sys.stderr)
            except Exception:
                print(t)
