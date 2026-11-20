#!/usr/bin/env python3
"""upload_mcp.py <local> <remote> [chunk_kB]: copy a file to the PC through Blender's Python (execute_blender_code),
appending base64 chunks. About 200 kB/s. Skips files whose size and md5 already match on the PC."""
import base64, hashlib, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmcp

def remote_md5(remote):
    out = bmcp.text_of(bmcp.call('execute_blender_code', {'code':
        "import hashlib, os\np = %r\nprint(hashlib.md5(open(p,'rb').read()).hexdigest() if os.path.exists(p) else 'none')" % remote}))
    return out.strip().split()[-1]

def put(local, remote, chunk=700_000, quiet=False):
    data = open(local, 'rb').read()
    md5 = hashlib.md5(data).hexdigest()
    if remote_md5(remote) == md5:
        if not quiet:
            print('up to date', remote)
        return 0
    t0 = time.time()
    code = "import os\np = %r\nos.makedirs(os.path.dirname(p), exist_ok=True)\nopen(p, 'wb').close()\nprint('new')" % remote
    bmcp.text_of(bmcp.call('execute_blender_code', {'code': code}))
    for i in range(0, len(data), chunk):
        b64 = base64.b64encode(data[i:i + chunk]).decode('ascii')
        code = "import base64\nopen(%r, 'ab').write(base64.b64decode('%s'))\nprint('ok')" % (remote, b64)
        for attempt in range(3):
            out = bmcp.text_of(bmcp.call('execute_blender_code', {'code': code}))
            if 'ok' in out:
                break
            time.sleep(2)
        else:
            raise RuntimeError('chunk %d failed: %s' % (i, out[:200]))
    if remote_md5(remote) != md5:
        raise RuntimeError('md5 mismatch after upload of ' + local)
    if not quiet:
        print('put %d bytes -> %s in %.1fs' % (len(data), remote, time.time() - t0))
    return len(data)

if __name__ == '__main__':
    put(sys.argv[1], sys.argv[2], int(sys.argv[3]) * 1000 if len(sys.argv) > 3 else 700_000)
