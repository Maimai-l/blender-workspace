#!/usr/bin/env python3
"""Run a data-processing script on the PC with Blender's bundled Python (outside Blender).

    pyrun.py <scripts/proc/name.py> [args...] [--timeout 3600]

Pushes scripts/proc and scripts/lib first. The script runs in the background with PYTHONPATH = <PC project>\\pylib
(numba, scipy, pillow, rasterio) and <PC project>\\proc; its output goes to tmp\\<name>.log, which this polls
through exec and prints when the process has ended."""
import os, sys, time, subprocess
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__)), os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools')]  # this folder, then the shared <repo>/tools
import xyp, pcx
a = sys.argv[1:]
timeout = 3600
if '--timeout' in a:
    i = a.index('--timeout'); timeout = int(a[i + 1]); del a[i:i + 2]
name = os.path.splitext(os.path.basename(a[0]))[0]
subprocess.run([sys.executable, '-I', os.path.join(xyp.TOOLS, 'push.py')], check=True, stdout=subprocess.DEVNULL,
               env=dict(os.environ, XY_PROJECT=xyp.PROJ))
root = pcx._unix(xyp.PC_ROOT)
tag = '%s_%s' % (name, time.strftime('%H%M%S'))
args = ' '.join('"%s"' % x for x in a[1:])
cmd = ('cd "%s" && rm -f tmp/%s.done && export PYTHONPATH="%s\\pylib;%s\\proc" && export PYTHONUNBUFFERED=1 && '
       '(nohup sh -c \'"%s" proc/%s.py %s > tmp/%s.log 2>&1; echo $? > tmp/%s.done\' > /dev/null 2>&1 &) ; echo started'
       % (root, tag, xyp.PC_ROOT, xyp.PC_ROOT, pcx._unix(pcx.PY), name, args, tag, tag))
print(pcx.bash(cmd), tag, file=sys.stderr)
t0 = time.time()
while time.time() - t0 < timeout:
    out = pcx.bash('cd "%s" && for i in $(seq 1 70); do [ -f tmp/%s.done ] && break; sleep 1; done; '
                   'if [ -f tmp/%s.done ]; then echo __EXIT__ $(cat tmp/%s.done); fi; tail -c 6000 tmp/%s.log'
                   % (root, tag, tag, tag, tag), timeout_ms=85000)
    if '__EXIT__' in out:
        print(out)
        sys.exit(0)
    print('  ... running %.0fs: %s' % (time.time() - t0, out.strip().splitlines()[-1][:150] if out.strip() else ''), file=sys.stderr)
sys.exit('timeout')
