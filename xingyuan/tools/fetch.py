#!/usr/bin/env python3
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""fetch.py <remote_path> <local_path> : copy a file from the Blender machine via base64 over MCP."""
import sys, os, base64, json
sys.path.insert(0, os.path.dirname(__file__))
import bmcp
remote, local = sys.argv[1], sys.argv[2]
code = r'''
import base64, os
p = %r
data = open(p, 'rb').read()
print('B64BEGIN' + base64.b64encode(data).decode('ascii') + 'B64END', len(data))
''' % remote
m = bmcp.call('execute_blender_code', {'code': code, 'user_prompt': 'fetch render'})
txt = bmcp.text_of(m)
i = txt.find('B64BEGIN'); j = txt.find('B64END')
if i < 0 or j < 0:
    print('FAILED:', txt[:500]); sys.exit(1)
data = base64.b64decode(txt[i + 8:j])
os.makedirs(os.path.dirname(os.path.abspath(local)), exist_ok=True)
open(local, 'wb').write(data)
print('fetched', len(data), 'bytes ->', local)
