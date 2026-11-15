"""Near layer mesh: the real ground around the cafe (surveyed TIN + Copernicus with synthesised detail), with the
site grading from lib/mc_site.py, on a tensor-product grid: 0.25 m cells at the site, growing to 2.5 m.

    mesh_near.py     -> dem/mesh_near.npz
"""
import os, sys, math, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'lib'))
import terrain_lib as tl
from far_build import OUT
from composite import Composite, CAM, KEYS
import mc_site

AZ_KEEP = (-180.0, -76.0)       # view wedge kept (degrees, math convention), plus everything within R_KEEP
R_KEEP = 320.0
SKIRT = 80.0                    # the mesh runs this far past the seam radius, sinking below the polar mesh
FINE, GROW, COARSE = 0.25, 0.0045, 2.5


def lines(lo, hi):
    out = [0.0]
    for sgn, lim in ((1, hi), (-1, lo)):
        x = 0.0
        while abs(x) < abs(lim):
            x += sgn * min(max(FINE, GROW * abs(x)), COARSE)
            out.append(x)
    return np.array(sorted(set(out)))


def main(log=print):
    t0 = time.time()
    comp = Composite()
    seam = comp.L['seam']
    R_MAX = seam + SKIRT
    x0, y0, x1, y1 = CAM[0] - R_MAX - 5, CAM[1] - R_MAX - 5, CAM[0] + R_KEEP + 5, CAM[1] + R_KEEP + 5
    xs = lines(x0, x1)
    ys = lines(y0, y1)
    nx, ny = xs.size, ys.size
    log('tensor grid', nx, 'x', ny, '= %.1f M' % (nx * ny / 1e6))
    cx = 0.5 * (xs[:-1] + xs[1:])
    cy = 0.5 * (ys[:-1] + ys[1:])
    CX, CY = np.meshgrid(cx.astype(np.float32), cy.astype(np.float32))
    az = np.degrees(np.arctan2(CY - CAM[1], CX - CAM[0]))
    az = np.where(az > 60, az - 360, az)
    rc = np.hypot(CX - CAM[0], CY - CAM[1])
    keep = (((az > AZ_KEEP[0]) & (az < AZ_KEEP[1])) & (rc < R_MAX)) | (rc < R_KEEP)
    del rc
    del CX, CY, az
    used = np.zeros((ny, nx), bool)
    used[:-1, :-1] |= keep
    used[1:, :-1] |= keep
    used[:-1, 1:] |= keep
    used[1:, 1:] |= keep
    idx = np.full((ny, nx), -1, np.int32)
    nv = int(used.sum())
    idx[used] = np.arange(nv, dtype=np.int32)
    jj, ii = np.nonzero(keep)
    quads = np.stack([idx[jj, ii], idx[jj, ii + 1], idx[jj + 1, ii + 1], idx[jj + 1, ii]], 1)
    del keep
    vj, vi = np.nonzero(used)
    X = xs[vi]
    Y = ys[vj]
    log('verts %.2f M, quads %.2f M' % (nv / 1e6, len(quads) / 1e6), '%.1fs' % (time.time() - t0))

    def nat(x, y):
        return comp.sample(x, y)['z']
    site = mc_site.Site(nat)
    Z = np.empty(nv, np.float32)
    att = {k: np.empty(nv, np.float32) for k in KEYS + ('alt', 'wfar', 'track', 'terrace', 'sdf')}
    CH = 400000
    for s in range(0, nv, CH):
        x = X[s:s + CH]
        y = Y[s:s + CH]
        z, mt, mp, sdf = site.height(x, y)
        o = comp.sample(x, y)
        Z[s:s + CH] = z - np.maximum(0.0, np.hypot(x - CAM[0], y - CAM[1]) - seam)
        att['alt'][s:s + CH] = z
        att['track'][s:s + CH] = mt
        att['terrace'][s:s + CH] = mp
        att['sdf'][s:s + CH] = sdf
        att['wfar'][s:s + CH] = o['wfar']
        for k in KEYS:
            att[k][s:s + CH] = o[k]
    d2 = X * X + Y * Y
    co = np.stack([X, Y, Z - d2 / (2.0 * tl.R_EARTH) * 0.87], 1).astype(np.float32)
    np.savez(os.path.join(OUT, 'mesh_near.npz'), co=co, quads=quads, **{'a_' + k: v for k, v in att.items()})
    log('saved mesh_near', co.shape, quads.shape, '%.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
