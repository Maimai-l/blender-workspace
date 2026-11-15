"""Paving layout for the terrace: local slate slabs laid in courses parallel to the cafe, random widths and
lengths, open joints, trimmed to the terrace outline.

    paving.py   -> dem/paving.npz  (pts [M,2] local coordinates, off [N+1] polygon offsets)
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'lib'))
from far_build import OUT
import mc_site


def main(seed=3):
    rng = np.random.default_rng(seed)
    T = mc_site.TERRACE
    lo, hi = T.min(0) - 1, T.max(0) + 1
    sh = mc_site.SHELL
    out, off = [], [0]
    u = lo[0]
    while u < hi[0]:
        w = float(rng.choice([0.32, 0.40, 0.48, 0.58, 0.70], p=[0.15, 0.3, 0.3, 0.18, 0.07]))   # course width
        v = lo[1] - rng.uniform(0, 0.8)
        skew = rng.normal(0, 0.004)
        while v < hi[1]:
            L = float(np.clip(rng.lognormal(np.log(0.72), 0.38), 0.34, 1.6))
            j = 0.011 + rng.uniform(0, 0.012)                       # joint
            p = np.array([[u + j, v + j], [u + w - j, v + j + skew * w], [u + w - j, v + L - j + skew * w], [u + j, v + L - j]])
            p += rng.normal(0, 0.004, p.shape)
            v += L
            cen = p.mean(0)
            if mc_site.terrace_sdf(cen[None, 0], cen[None, 1])[0] > -0.10:
                continue
            if sh[0] + 0.6 < cen[0] < sh[2] - 0.6 and sh[1] + 0.6 < cen[1] < sh[3] - 0.6:
                continue                                           # under the building
            # subdivide the edges so the trimming follows the curved wall line
            q = []
            for k in range(4):
                a, b = p[k], p[(k + 1) % 4]
                m = max(1, int(np.linalg.norm(b - a) / 0.2))
                for t in np.arange(m) / m:
                    q.append(a + (b - a) * t)
            q = np.array(q)
            for it in range(3):
                d = mc_site.terrace_sdf(q[:, 0], q[:, 1])
                bad = d > -0.22
                if not bad.any():
                    break
                e = 0.02
                gx = (mc_site.terrace_sdf(q[:, 0] + e, q[:, 1]) - mc_site.terrace_sdf(q[:, 0] - e, q[:, 1])) / (2 * e)
                gy = (mc_site.terrace_sdf(q[:, 0], q[:, 1] + e) - mc_site.terrace_sdf(q[:, 0], q[:, 1] - e)) / (2 * e)
                q[bad, 0] -= gx[bad] * (d[bad] + 0.22)
                q[bad, 1] -= gy[bad] * (d[bad] + 0.22)
            # drop duplicate points made by the trimming
            keep = np.r_[True, np.linalg.norm(np.diff(q, axis=0), axis=1) > 0.01]
            q = q[keep]
            area = 0.5 * np.abs(np.dot(q[:, 0], np.roll(q[:, 1], -1)) - np.dot(q[:, 1], np.roll(q[:, 0], -1)))
            if len(q) < 3 or area < 0.035:
                continue
            out.append(q)
            off.append(off[-1] + len(q))
        u += w
    np.savez(os.path.join(OUT, 'paving.npz'), pts=np.vstack(out), off=np.array(off))
    print('slabs', len(out))


if __name__ == '__main__':
    main()
