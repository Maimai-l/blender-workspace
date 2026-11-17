"""Forest: tree positions on the composed landscape (fir on shaded slopes below the tree line at about 4250 m,
larch gold towards the tree line), only where the camera can see them.

    trees.py   -> dem/trees.npz  (co [N,3], h, yaw, sp: 0-3 fir, 4-5 larch)
"""
import os, sys, math, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_lib as tl
from far_build import OUT
from composite import Composite, CAM_VIEW as CAM

AZ0, AZ1 = -176.0, -78.0
R0, R1 = 260.0, 10500.0


def vnoise(x, y, scale, seed, octaves=4):
    out = np.zeros(np.shape(x))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        tab = np.random.default_rng(seed + 31 * o).uniform(0, 1, (256, 256))
        u, v = np.asarray(x) / scale, np.asarray(y) / scale
        i, j = np.floor(u).astype(int), np.floor(v).astype(int)
        fu, fv = u - i, v - j
        fu, fv = fu * fu * (3 - 2 * fu), fv * fv * (3 - 2 * fv)
        a, b = tab[i % 256, j % 256], tab[(i + 1) % 256, j % 256]
        c, d = tab[i % 256, (j + 1) % 256], tab[(i + 1) % 256, (j + 1) % 256]
        out += amp * (a * (1 - fu) * (1 - fv) + b * fu * (1 - fv) + c * (1 - fu) * fv + d * fu * fv)
        tot += amp
        amp *= 0.5
        scale *= 0.5
    return out / tot


def smooth(x, lo, hi):
    t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def horizon(comp, daz=0.1, dr=0.006):
    """H[row, col]: highest elevation angle (deg) of the ground nearer than each (range, azimuth)."""
    az = np.arange(AZ0 - 1, AZ1 + 1 + 1e-6, daz)
    nr = int(math.log(46000.0 / 40.0) / math.log(1 + dr)) + 1
    rr = 40.0 * (1 + dr) ** np.arange(nr)
    A, Rr = np.meshgrid(np.radians(az), rr)
    qx, qy = CAM[0] + Rr * np.cos(A), CAM[1] + Rr * np.sin(A)
    z = comp.sample(qx, qy)['z'] - (qx * qx + qy * qy) / (2 * tl.R_EARTH) * 0.87
    el = np.degrees(np.arctan2(z - CAM[2], Rr))
    H = np.maximum.accumulate(el, axis=0)
    H = np.vstack([np.full((1, len(az)), -90.0), H[:-1]])
    return az, rr, H


def main(n_cand=9_000_000, seed=4, log=print):
    t0 = time.time()
    comp = Composite()
    rng = np.random.default_rng(seed)
    az_t, rr_t, H = horizon(comp)
    log('horizon table', H.shape, '%.1fs' % (time.time() - t0))
    out = {k: [] for k in ('co', 'h', 'yaw', 'sp')}
    CH = 500000
    for s in range(0, n_cand, CH):
        az = rng.uniform(AZ0, AZ1, CH)
        r = np.sqrt(rng.uniform(0, 1, CH) * (R1 * R1 - R0 * R0) + R0 * R0)
        qx, qy = CAM[0] + r * np.cos(np.radians(az)), CAM[1] + r * np.sin(np.radians(az))
        o = comp.sample(qx, qy)
        alt, slope, north, flow, rocky = o['z'], o['slope'], o['north'], o['flow'], o['rocky']
        big = vnoise(qx, qy, 700.0, 2)
        mid = vnoise(qx, qy, 110.0, 1)
        # the tree line (m above the cafe): higher on sunny slopes and spurs, pulled down in the avalanche gullies
        line = -150.0 - 120.0 * north + 180.0 * (big - 0.5) + 100.0 * (mid - 0.5) - 90.0 * smooth(flow, 3.0, 3.8)
        depth = line - alt                                              # metres below the tree line
        dens = smooth(depth, -30.0, 170.0)                              # stragglers at the line, closed forest below
        clear = smooth(vnoise(qx, qy, 260.0, 3) * 0.6 + vnoise(qx, qy, 85.0, 7) * 0.4, 0.50, 0.60) * (0.35 + 0.65 * smooth(depth, 500.0, 60.0))
        aval = smooth(flow, 3.25, 3.75) * smooth(slope, 0.42, 0.68)     # avalanche tracks stay open
        rockx = np.clip(smooth(slope, 0.95, 1.25) + smooth(rocky, 0.62, 0.86), 0, 1)
        p = dens * (1.0 - 0.92 * clear) * (1.0 - aval) * (1.0 - rockx) * (0.55 + 0.45 * smooth(north, -0.3, 0.3))
        p *= np.minimum(1.0, (4200.0 / r) ** 1.1)                               # thinner far away (a tree is a pixel there)
        keep = rng.uniform(0, 1, CH) < p
        h = (7.0 + 17.0 * smooth(depth, 0.0, 320.0)) * rng.uniform(0.7, 1.3, CH)   # small trees towards the line
        h *= 1.0 + 0.5 * smooth(r, 4200.0, 9000.0)                              # far "trees" stand for small groups
        drop = (qx * qx + qy * qy) / (2 * tl.R_EARTH) * 0.87
        el = np.degrees(np.arctan2(alt + h - drop - CAM[2], r))
        ci = np.clip(np.round((az - az_t[0]) / (az_t[1] - az_t[0])).astype(int), 0, len(az_t) - 1)
        ri = np.clip(np.searchsorted(rr_t, r), 0, len(rr_t) - 1)
        keep &= el >= H[ri, ci] - 0.15
        larch = rng.uniform(0, 1, CH) < (0.04 + 0.16 * smooth(depth, 220.0, 20.0))
        sp = np.where(larch, 4 + rng.integers(0, 2, CH), rng.integers(0, 4, CH))      # 0-3 fir shapes, 4-5 larch
        out['co'].append(np.c_[qx, qy, alt - drop - 0.3][keep])
        out['h'].append(h[keep])
        out['yaw'].append(rng.uniform(0, 6.283, CH)[keep])
        out['sp'].append(sp[keep])
    res = {k: np.concatenate(v) for k, v in out.items()}
    np.savez(os.path.join(OUT, 'trees.npz'), co=res['co'].astype(np.float32), h=res['h'].astype(np.float32),
             yaw=res['yaw'].astype(np.float32), sp=res['sp'].astype(np.int32))
    r = np.hypot(res['co'][:, 0] - CAM[0], res['co'][:, 1] - CAM[1])
    log('trees', len(r), 'larch %.0f%%' % (100 * (res['sp'] >= 4).mean()),
        'by range km', np.histogram(r, [0, 1000, 2000, 3000, 5000, 7000, 11000])[0].tolist(), '%.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
