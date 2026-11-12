#!/usr/bin/env python3
"""tidy.py [scan|clean] [--min-age MIN] : end-of-session cleanup of the PC work area, through exec.

Sends ops/pc_tidy.sh to the PC's Git Bash and prints its report. "scan" (default) only lists; "clean" deletes the
tool by-products and appends each removal to D:\\Blender\\Projects\\_迁移日志\\cleanup_<date>.log.
Nothing is deleted while a background Blender job, render worker or ffmpeg is running. See ops/README.md."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'qiting', 'tools'))
import pcx

a = sys.argv[1:]
mode = a[0] if a and a[0] in ('scan', 'clean') else 'scan'
age = a[a.index('--min-age') + 1] if '--min-age' in a else '60'
script = open(os.path.join(HERE, 'pc_tidy.sh'), encoding='utf-8').read()
print(pcx.bash("MIN_AGE_MIN=%s bash -s %s <<'__TIDY__'\n%s\n__TIDY__" % (int(age), mode, script), timeout_ms=85000))
