#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Minimal MCP (streamable HTTP) client for the Blender MCP server.
With XY_VIA_EXEC=1 (the default here) execute_blender_code goes through the exec server and the add-on socket
instead (pcx.py), because the cloud endpoint for Blender was down.
usage:
  bmcp.py run <script.py> [--out FILE]      run a local python file inside Blender (execute_blender_code)
  bmcp.py code "<python>" [--out FILE]      run inline code
  bmcp.py tools                             list tools
Output text is printed (or written to --out)."""
import json, os, sys, urllib.request, ssl, time

URL = os.environ['BLENDER_MCP_URL']
import xyp
SESS_FILE = os.path.join(xyp.S, '.bmcp_session')
CTX = ssl.create_default_context(cafile=xyp.CA) if xyp.CA else ssl.create_default_context()

def _post(payload, sid=None, timeout=600):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'xy-mcp-client/1.0')
    req.add_header('Accept', 'application/json, text/event-stream')
    if sid:
        req.add_header('Mcp-Session-Id', sid)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(), urllib.request.HTTPSHandler(context=CTX))
    with opener.open(req, timeout=timeout) as r:
        hdr_sid = r.headers.get('Mcp-Session-Id')
        ctype = r.headers.get('Content-Type', '')
        body = r.read().decode('utf-8', 'replace')
    msgs = []
    if 'text/event-stream' in ctype:
        for block in body.split('\n\n'):
            for line in block.split('\n'):
                if line.startswith('data:'):
                    try:
                        msgs.append(json.loads(line[5:].strip()))
                    except Exception:
                        pass
    elif body.strip():
        msgs.append(json.loads(body))
    return hdr_sid, msgs

def session(force=False):
    if not force and os.path.exists(SESS_FILE):
        return open(SESS_FILE).read().strip()
    sid, msgs = _post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                       'params': {'protocolVersion': '2025-03-26', 'capabilities': {},
                                  'clientInfo': {'name': 'xy-cli', 'version': '1.0'}}})
    _post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, sid)
    open(SESS_FILE, 'w').write(sid or '')
    return sid

VIA_EXEC = os.environ.get('XY_VIA_EXEC', '1') == '1'   # Blender MCP endpoint down since 2026-11-01: go through exec

def call(name, args, timeout=600):
    if VIA_EXEC and name == 'execute_blender_code':
        import pcx
        txt = pcx.blender(args['code'])
        return {'result': {'content': [{'type': 'text', 'text': txt}]}}
    return _call_http(name, args, timeout)

def _call_http(name, args, timeout=600):
    for attempt in range(2):
        sid = session(force=attempt > 0)
        try:
            _, msgs = _post({'jsonrpc': '2.0', 'id': int(time.time()*1000) % 100000000, 'method': 'tools/call',
                             'params': {'name': name, 'arguments': args}}, sid, timeout)
        except urllib.error.HTTPError as e:
            if attempt == 0 and e.code in (400, 404, 409):
                continue
            raise
        for m in msgs:
            if 'result' in m or 'error' in m:
                return m
        if attempt == 0:
            continue
    return None

def text_of(m):
    if m is None:
        return '<no response>'
    if 'error' in m:
        return 'JSONRPC ERROR: ' + json.dumps(m['error'])
    out = []
    for c in m['result'].get('content', []):
        if c.get('type') == 'text':
            t = c['text']
            try:
                j = json.loads(t)
                if isinstance(j, dict) and 'result' in j:
                    t = j['result']
            except Exception:
                pass
            out.append(t)
        else:
            out.append('<%s>' % c.get('type'))
    if m['result'].get('isError'):
        out.insert(0, 'TOOL ERROR:')
    return '\n'.join(out)

if __name__ == '__main__':
    a = sys.argv[1:]
    out = None
    if '--out' in a:
        i = a.index('--out'); out = a[i+1]; del a[i:i+2]
    if a[0] == 'tools':
        sid = session()
        _, msgs = _post({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}, sid)
        for m in msgs:
            for t in m.get('result', {}).get('tools', []):
                print(t['name'])
        sys.exit(0)
    if a[0] == 'run':
        code = open(a[1], encoding='utf-8').read()
        if len(a) > 2:
            code = a[2] + '\n' + code
    else:
        code = a[1]
    t0 = time.time()
    m = call('execute_blender_code', {'code': code, 'user_prompt': '旗亭 Blender 复刻（第一轮：建筑主体）：请在 Blender 中，根据我提供的参考资料，完成旗亭的写实复刻建模。'})
    txt = text_of(m)
    if out:
        open(out, 'w', encoding='utf-8').write(txt)
        print('[saved %d chars to %s in %.1fs]' % (len(txt), out, time.time()-t0))
    else:
        print(txt)
        print('[%.1fs]' % (time.time()-t0), file=sys.stderr)
