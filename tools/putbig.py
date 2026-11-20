#!/usr/bin/env python3
"""putbig.py <local> <remote> : copy a large file to the PC through exec, as parallel base64 chunks joined there."""
import base64, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcx
from concurrent.futures import ThreadPoolExecutor

def put(local, remote, chunk=900_000, workers=4):
    data = open(local, 'rb').read()
    b64 = base64.b64encode(data).decode('ascii')
    tag = uuid.uuid4().hex[:8]
    parts = [b64[i:i + chunk] for i in range(0, len(b64), chunk)]
    tmpd = pcx.TMP + '\\big_' + tag
    pcx.bash('mkdir -p "%s"' % pcx._unix(tmpd))
    def w(i):
        txt = '\n'.join(parts[i][j:j + 76] for j in range(0, len(parts[i]), 76))
        for attempt in range(3):
            try:
                pcx.write_text('%s\\%03d.b64' % (tmpd, i), txt)
                return
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(w, range(len(parts))))
    u = pcx._unix(tmpd)
    out = pcx.bash('mkdir -p "$(dirname "%s")" && cat "%s"/*.b64 | base64 -d > "%s" && rm -rf "%s" && wc -c < "%s"'
                   % (pcx._unix(remote), u, pcx._unix(remote), u, pcx._unix(remote)))
    n = int(out.strip().split()[-1])
    if n != len(data):
        raise RuntimeError('size mismatch %d != %d' % (n, len(data)))
    return n

if __name__ == '__main__':
    t0 = time.time()
    n = put(sys.argv[1], sys.argv[2])
    print('put %d bytes -> %s in %.1fs' % (n, sys.argv[2], time.time() - t0))
