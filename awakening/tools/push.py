#!/usr/bin/env python3
"""Push every ../scripts/lib/*.py (or the given files) to <PC project>\\lib in one Blender call."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmcp, xyp
REMOTE = xyp.PC_ROOT + r'\lib'
files = sys.argv[1:] or sorted(glob.glob(xyp.LIB + '/*.py'))
srcs = {}
for f in files:
    f = f if os.path.isabs(f) else os.path.join(xyp.LIB, f)
    srcs[os.path.basename(f)] = open(f, encoding='utf-8').read()
code = ('import os\nR = %r\nos.makedirs(R, exist_ok=True)\nS = %r\n'
        'for k, v in S.items():\n    open(os.path.join(R, k), "w", encoding="utf-8").write(v)\n'
        'print("pushed", len(S), "files", sum(len(v) for v in S.values()), "chars")') % (REMOTE, srcs)
print(bmcp.text_of(bmcp.call('execute_blender_code', {'code': code})))
