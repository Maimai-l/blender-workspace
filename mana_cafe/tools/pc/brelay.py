"""Run a Python file inside the live Blender through the Blender MCP add-on's local socket (127.0.0.1:9876).

Used when the cloud MCP endpoint for Blender is down: the cloud session reaches this PC through the exec
server, writes the code to a file and runs
    python brelay.py <code.py> [<out.txt>] [<timeout_s>]
with Blender's bundled Python. The add-on runs the code on Blender's main thread and returns what it printed.
The full output goes to <out.txt> (default: <code>.out); up to 25,000 characters are also printed.
"""
import json
import os
import socket
import sys
import time

code_path = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != '-' else os.path.splitext(code_path)[0] + '.out'
timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 3600.0
code = open(code_path, encoding='utf-8').read()

t0 = time.time()
s = socket.create_connection(('127.0.0.1', 9876), timeout=10)
s.settimeout(timeout)
s.sendall(json.dumps({'type': 'execute_code', 'params': {'code': code}}).encode('utf-8'))
buf = b''
resp = None
while True:
    d = s.recv(1 << 20)
    if not d:
        break
    buf += d
    try:
        resp = json.loads(buf.decode('utf-8'))
        break
    except (ValueError, UnicodeDecodeError):
        continue
s.close()

if resp is None:
    text = 'RELAY ERROR: no complete response (%d bytes)' % len(buf)
elif resp.get('status') != 'success':
    text = 'BLENDER ERROR: ' + str(resp.get('message', resp))
else:
    r = resp.get('result', {})
    text = r.get('result', '') if isinstance(r, dict) else str(r)
    if isinstance(r, dict) and not r.get('executed', True):
        text = 'NOT EXECUTED: ' + json.dumps(r)
text += '\n[relay %.1fs]' % (time.time() - t0)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(text)
with open(out_path + '.done', 'w') as f:
    f.write('1')
sys.stdout.reconfigure(encoding='utf-8')
if len(text) > 25000:
    print(text[:12000] + '\n...[%d chars, full output in %s]...\n' % (len(text), out_path) + text[-12000:])
else:
    print(text)
