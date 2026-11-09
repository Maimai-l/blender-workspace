"""pc_worker.py - runs ON THE PC: render a share of the frame chunks listed in a jobs file.

  python pc_worker.py jobs.json WORKER_ID N_WORKERS

jobs.json: {"chunks": [[sid, start, end], ...], "ss": 2, "out": "<frames dir>"}
Writes <out>/<sid>/<sid>_<frame>.png and <out>/_done/<jobname>_<id>.done when finished.
"""
import os, sys, json, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('engine', 'robot', 'shots'):
    sys.path.insert(0, os.path.join(HERE, '..', p))


def main():
    jobs_path, wid, nw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    jobs = json.load(open(jobs_path))
    out = jobs['out']
    os.environ['AW2_FRAMES'] = out
    import render_shot as RS
    import cv2, comp
    name = os.path.splitext(os.path.basename(jobs_path))[0]
    done_dir = os.path.join(out, '_done'); os.makedirs(done_dir, exist_ok=True)
    log = open(os.path.join(done_dir, f'{name}_{wid}.log'), 'a')
    n = len(jobs['chunks'])
    if jobs.get('contiguous', True):
        mine = [c for i, c in enumerate(jobs['chunks']) if i * nw // n == wid]
    else:
        mine = [c for i, c in enumerate(jobs['chunks']) if i % nw == wid]
    shots = {}
    for sid, a, b in mine:
        try:
            if sid not in shots:
                shots.clear()           # keep memory bounded: one shot at a time per worker
                shots[sid] = RS.Shot(sid, ss=jobs.get('ss', 2))
            S = shots[sid]
            od = os.path.join(out, sid); os.makedirs(od, exist_ok=True)
            for f in range(a, min(b, S.nf)):
                p = os.path.join(od, f'{sid}_{f:04d}.png')
                if jobs.get('skip_existing') and os.path.exists(p):
                    continue
                t0 = time.time()
                rgb = S.frame(f)
                tmp = p + '.tmp.png'
                cv2.imwrite(tmp, comp.to_u8(rgb)[..., ::-1])
                os.replace(tmp, p)
                log.write(f'{sid} {f} {time.time() - t0:.1f}\n'); log.flush()
        except Exception:
            log.write(f'FAILED {sid} {a}-{b}\n{traceback.format_exc()}\n'); log.flush()
    open(os.path.join(done_dir, f'{name}_{wid}.done'), 'w').write('ok')


if __name__ == '__main__':
    main()
