#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""upload.py <local file> <remote path> : copy a local file to the Blender machine in base64 chunks."""
import sys, os, base64
sys.path.insert(0, os.path.dirname(__file__))
import bmcp
local, remote = sys.argv[1], sys.argv[2]
data = base64.b64encode(open(local, 'rb').read()).decode('ascii')
CH = 300000
parts = [data[i:i + CH] for i in range(0, len(data), CH)]
for k, part in enumerate(parts):
    code = ("import base64, os\np = %r\nos.makedirs(os.path.dirname(p), exist_ok=True)\n"
            "open(p, %r).write(base64.b64decode(%r))\nprint('ok', os.path.getsize(p))") % (remote, 'wb' if k == 0 else 'ab', part)
    m = bmcp.call('execute_blender_code', {'code': code, 'user_prompt': 'upload deliverable'})
    t = bmcp.text_of(m)
    if 'ok' not in t:
        print('FAILED', t[:300]); sys.exit(1)
print('uploaded', local, '->', remote, t.strip().split()[-1], 'bytes')
