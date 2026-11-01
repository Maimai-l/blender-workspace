#!/usr/bin/env python3
"""fetch.py <remote_path> <local_path> [chunk_MB] : copy a file from the Blender PC to this session.
The file is read by Blender's Python and sent back as base64 in pieces of chunk_MB (default 2), so large files
(videos, archives, .blend files) work too. Do not raise the piece size: on 2026-11-01 one 8 MB piece (an 11 MB
reply) made the Blender MCP server exit until it was restarted from the console."""
import os, sys, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmcp

remote, local = sys.argv[1], sys.argv[2]
chunk = int(float(sys.argv[3]) * 1024 * 1024) if len(sys.argv) > 3 else 2 * 1024 * 1024
CODE = r'''
import base64, os
p = %r
size = os.path.getsize(p)
with open(p, 'rb') as f:
    f.seek(%d)
    data = f.read(%d)
print('SIZE', size, 'B64BEGIN' + base64.b64encode(data).decode('ascii') + 'B64END')
'''
os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)
off, total = 0, None
with open(local, 'wb') as out:
    while total is None or off < total:
        m = bmcp.call('execute_blender_code', {'code': CODE % (remote, off, chunk), 'user_prompt': 'fetch file'})
        txt = bmcp.text_of(m)
        i = txt.find('B64BEGIN'); j = txt.find('B64END'); k = txt.find('SIZE ')
        if i < 0 or j < 0 or k < 0:
            print('FAILED:', txt[:500]); sys.exit(1)
        total = int(txt[k + 5:i].split()[0])
        data = base64.b64decode(txt[i + 8:j])
        if not data and off < total:
            print('FAILED: empty piece at', off); sys.exit(1)
        out.write(data)
        off += len(data)
        if total > chunk:
            print('  %d / %d bytes' % (off, total), file=sys.stderr)
print('fetched', off, 'bytes ->', local)
