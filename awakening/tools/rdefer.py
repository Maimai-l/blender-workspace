#!/usr/bin/env python3
"""Run a long Blender script without holding the MCP reply open.

    rdefer.py <script.py> ["PRE = 1; OTHER = 'x'"] [--timeout 3600]

The script runs from a Blender timer (so the MCP call returns at once; the tunnel in front of the Blender endpoint
cuts replies at about 100 s); what it prints is written to renders/job_<id>.txt on the PC, which this waits for
through exec and then prints."""
import argparse, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xyp, bmcp, pcx

ap = argparse.ArgumentParser()
ap.add_argument('script')
ap.add_argument('pre', nargs='?', default='')
ap.add_argument('--timeout', type=int, default=3600)
a = ap.parse_args()
code = (a.pre + '\n' if a.pre else '') + open(a.script, encoding='utf-8').read()
job = xyp.PC_ROOT + '\\renders\\job_%s.txt' % uuid.uuid4().hex[:8]
wrapper = '''
import bpy, io, os, contextlib, traceback
_JOB = %r
_CODE = %r
def _run_job():
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(_CODE, 'deferred_job', 'exec'), {'__name__': '__main__', 'bpy': bpy})
    except BaseException:
        buf.write('\\nFAILED\\n' + traceback.format_exc())
    with open(_JOB + '.tmp', 'w', encoding='utf-8') as fh:
        fh.write(buf.getvalue())
    os.replace(_JOB + '.tmp', _JOB)
    return None
bpy.app.timers.register(_run_job, first_interval=0.3)
print('deferred', _JOB)
''' % (job, code)
out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': wrapper}))
if 'deferred' not in out:
    sys.exit(out)
print(pcx.wait_file(job, timeout_s=a.timeout))
