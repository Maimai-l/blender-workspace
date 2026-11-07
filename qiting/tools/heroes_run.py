#!/usr/bin/env python3
"""Render beauty shots (scripts/render_heroes.py with lib/heroes.py) and fetch them.

    heroes_run.py [names ...] [--samples 64] [--scale 0.5]

The shots render one by one from Blender timers; this waits for each renders/<name>.jpg.done marker through exec
(not through the busy Blender) and copies renders/<name>.jpg into the sandbox's renders folder."""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, bmcp, pcx

ap = argparse.ArgumentParser()
ap.add_argument('names', nargs='*')
ap.add_argument('--samples', type=int, default=64)
ap.add_argument('--scale', type=float, default=0.5)
a = ap.parse_args()
pre = 'NAMES = %r\nSAMPLES = %d\nSCALE = %r\n' % (a.names, a.samples, a.scale)
code = pre + open(os.path.join(xyp.PROJ, 'scripts', 'render_heroes.py'), encoding='utf-8').read()
out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': code}))
print(out.strip().splitlines()[-1] if out.strip() else out)
names = a.names
if not names:
    import re
    m = re.search(r"heroes deferred (\[.*\])", out)
    names = eval(m.group(1)) if m else []
for n in names:
    remote = xyp.PC_ROOT + '\\renders\\' + n + '.jpg'
    msg = pcx.wait_file(remote + '.done')
    print(msg)
    if not msg.startswith('FAILED'):
        pcx.fetch(remote, os.path.join(xyp.S, 'renders', n + '.jpg'))
print(pcx.wait_file(xyp.PC_ROOT + '\\renders\\heroes.done'))
