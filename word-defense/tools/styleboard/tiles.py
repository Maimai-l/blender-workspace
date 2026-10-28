# tiles.py - close-up motif tiles rendered from the same scenes with closer cameras.
import sys, math, json, subprocess
import numpy as np
from eng import Cam
from util import smooth, at
import scene_a, scene_b, scene_c

TW, TH = 632, 400


def road_pt(mod, s, path_name='ROAD'):
    P = smooth(getattr(mod, path_name), 8)
    p, d = at(P, s)
    return p, d


def views_a():
    v = {}
    v['cheng'] = ((7.9, -1.5, 3.0), (5.35, 2.85, 0.7), 34)
    v['yuan'] = ((-0.2, 3.6, 3.0), (-1.9, 8.9, 1.5), 34)
    p, d = road_pt(scene_a, 0.255)
    v['di'] = ((p[0] - 0.8, p[1] - 2.6, 1.25), (p[0], p[1], 0.45), 40)
    p, d = road_pt(scene_a, 0.18)
    v['lu'] = ((p[0] - 1.2, p[1] - 3.4, 2.6), (p[0] - 0.1, p[1] + 0.6, 0.2), 32)
    v['mu'] = ((1.5, 3.3, 1.5), (2.6, 6.55, 0.85), 38)
    p, d = road_pt(scene_a, 0.38)
    v['ji'] = ((p[0] + 0.4, p[1] - 3.6, 2.4), (p[0] + 1.2, p[1] - 0.2, 0.9), 30)
    return v


def views_b():
    v = {}
    v['cheng'] = ((7.8, -1.3, 2.9), (5.2, 2.9, 0.8), 34)
    v['yuan'] = ((-0.9, 4.2, 2.6), (-1.9, 9.6, 1.5), 34)
    p, d = road_pt(scene_b, 0.19)
    v['di'] = ((p[0] - 0.4, p[1] - 2.3, 1.15), (p[0] + 0.1, p[1], 0.35), 40)
    p, d = road_pt(scene_b, 0.6)
    v['lu'] = ((p[0] - 1.6, p[1] - 3.2, 2.4), (p[0], p[1] + 0.3, 0.2), 32)
    v['mu'] = ((-6.9, 2.5, 1.45), (-5.15, 5.9, 0.85), 36)
    p, d = road_pt(scene_b, 0.41)
    v['ji'] = ((p[0] + 0.3, p[1] - 3.2, 2.0), (p[0] + 0.8, p[1], 0.8), 32)
    return v


def views_c():
    v = {}
    v['cheng'] = ((7.9, -0.9, 2.5), (5.35, 3.2, 0.7), 34)
    v['yuan'] = ((-0.9, 4.6, 2.4), (-1.9, 8.9, 0.8), 32)
    p, d = road_pt(scene_c, 0.21, 'CANAL')
    nrm = np.array([-d[1], d[0]])
    side = -1 if nrm[1] > 0 else 1   # stand on the near (front) bank
    cpos = p + nrm * side * 1.9
    v['di'] = ((cpos[0] - 0.3, cpos[1], 0.85), (p[0], p[1], 0.25), 40)
    p, d = road_pt(scene_c, 0.62, 'CANAL')
    v['lu'] = ((p[0] - 1.4, p[1] - 3.0, 2.2), (p[0], p[1] + 0.2, 0.3), 32)
    v['mu'] = ((-7.7, -1.5, 1.35), (-6.0, 1.6, 0.6), 34)
    p, d = road_pt(scene_c, 0.46, 'CANAL')
    v['ji'] = ((p[0] - 0.6, p[1] - 3.4, 2.0), (p[0], p[1], 1.3), 32)
    return v


MODS = {'a': (scene_a, views_a), 'b': (scene_b, views_b), 'c': (scene_c, views_c)}

if __name__ == '__main__':
    import os
    os.makedirs('out', exist_ok=True)
    which = sys.argv[1]
    only = sys.argv[2:] or None
    mod, vf = MODS[which]
    jobs = []
    for name, (pos, tgt, lens) in vf().items():
        if only and name not in only:
            continue
        cam = Cam(pos, tgt, lens, TW, TH)
        cv, bk = mod.build(cam=cam, W=TW, H=TH)
        out = 'out/tile_%s_%s' % (which, name)
        mod.render(cv, out, TW, TH)
        jobs += [out + '.svg', out + '.png']
    subprocess.run(['node', 'render.js', str(TW), str(TH), '1'] + jobs, check=True, capture_output=True)
    print('rendered', len(jobs) // 2)
