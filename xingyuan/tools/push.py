#!/usr/bin/env python3
# Push local library modules into Blender's lib folder.
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
import bmcp
import xyp
LOCAL = xyp.LIB
REMOTE = xyp.PC_ROOT + r'\lib'
files = sys.argv[1:] or sorted(glob.glob(LOCAL + '/*.py'))
parts = []
for f in files:
    f = f if os.path.isabs(f) else os.path.join(LOCAL, f)
    src = open(f, encoding='utf-8').read()
    name = os.path.basename(f)
    parts.append('open(os.path.join(%r, %r), "w", encoding="utf-8").write(%r)\nprint("pushed", %r, %d)' % (REMOTE, name, src, name, len(src)))
code = 'import os\nos.makedirs(%r, exist_ok=True)\n' % REMOTE + '\n'.join(parts)
m = bmcp.call('execute_blender_code', {'code': code, 'user_prompt': 'push library'})
print(bmcp.text_of(m))
