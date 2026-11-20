#!/usr/bin/env python3
"""Push <project>/scripts/lib/*.py to <PC project>\\lib and <project>/scripts/proc/*.py (if any) to <PC project>\\proc,
in one Blender call. With file arguments, push only those: a bare name means scripts/lib/<name>, and the file's
folder (lib or proc) decides the target. The project comes from xyp (XY_PROJECT, the calling script or the cwd)."""
import os, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmcp, xyp
xyp.need_project('push.py')
PROC = os.path.join(xyp.SCRIPTS, 'proc')
files = sys.argv[1:] or sorted(glob.glob(xyp.LIB + '/*.py')) + sorted(glob.glob(PROC + '/*.py'))
srcs = {}
for f in files:
    f = os.path.abspath(f) if os.path.isabs(f) or os.path.exists(f) else os.path.join(xyp.LIB, f)
    sub = 'proc' if os.path.basename(os.path.dirname(f)) == 'proc' else 'lib'
    srcs[sub + '\\' + os.path.basename(f)] = open(f, encoding='utf-8').read()
code = ('import os\nR = %r\nS = %r\n'
        'for k, v in S.items():\n    p = os.path.join(R, k); os.makedirs(os.path.dirname(p), exist_ok=True)\n'
        '    open(p, "w", encoding="utf-8", newline="\\n").write(v)\n'
        'print("pushed", len(S), "files", sum(len(v) for v in S.values()), "chars")') % (xyp.PC_ROOT, srcs)
print(bmcp.text_of(bmcp.call('execute_blender_code', {'code': code})))
