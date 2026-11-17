"""Mountain mesh beyond the seam radius: the composed landscape (composite.py) on a polar grid around the camera, so
the mesh density is uniform on screen. Inside the seam the rows sink below the near mesh (the two cross at the seam).
Faces the camera cannot see (behind ridges) are left out, with a margin; faces that look at the sun are kept as
shadow casters.

    mesh_far.py     -> dem/mesh_far.npz, mesh_far.json
"""
import os, sys, math, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_lib as tl
from far_build import OUT
from composite import Composite, CAM, KEYS

AZ0, AZ1, DAZ = -182.0, -76.0, 0.036  # degrees (math convention), grid columns
R1 = 46000.0
# rows are geometric, r *= 1 + dr; finer between 5.5 and 20 km, where the snow peaks stand
BANDS = ((5500.0, 0.0014), (20000.0, 0.00065), (R1, 0.0013))
SUN = (-26.0, 28.6)                   # azimuth, elevation of the sun (deg)
CAM_Z_RANGE = (8.0, 22.0)             # the final camera may sit a little lower or higher than the sketch camera


def rows(r0):
    out = [r0]
    for lim, dr in BANDS:
        while out[-1] < lim:
            out.append(out[-1] * (1 + dr))
    return np.array(out)


def main(log=print):
    t0 = time.time()
    comp = Composite()
    seam = comp.L['seam']
    az = np.radians(np.arange(AZ1, AZ0 - 1e-9, -DAZ))                 # left to right on screen
    rr = rows(seam - 80.0)
    nr, ncol = rr.size, az.size
    log('polar grid rows %d cols %d = %.1f M verts' % (nr, ncol, nr * ncol / 1e6))
    co = np.empty((nr, ncol, 3), np.float32)
    att = {k: np.empty((nr, ncol), np.float32) for k in KEYS + ('alt', 'wfar')}
    ca, sa = np.cos(az), np.sin(az)
    CH = 64
    for s in range(0, nr, CH):
        r = rr[s:s + CH, None]
        qx = CAM[0] + r * ca[None, :]
        qy = CAM[1] + r * sa[None, :]
        o = comp.sample(qx, qy)
        drop = (qx * qx + qy * qy) / (2.0 * tl.R_EARTH) * 0.87      # earth curvature and refraction
        co[s:s + CH, :, 0] = qx
        co[s:s + CH, :, 1] = qy
        co[s:s + CH, :, 2] = o['z'] - drop - np.maximum(0.0, seam - r)
        for k in KEYS:
            att[k][s:s + CH] = o[k]
        att['alt'][s:s + CH] = o['z']
        att['wfar'][s:s + CH] = o['wfar']
    # --- visibility from the camera (lowest and highest camera height), per column outwards
    # horizon of the near ground first (inside the seam)
    rn = 30.0 * (1.004 ** np.arange(int(math.log(seam / 30.0) / math.log(1.004)) + 1))
    qx = CAM[0] + rn[:, None] * ca[None, :]
    qy = CAM[1] + rn[:, None] * sa[None, :]
    zn = comp.sample(qx, qy)['z'] - (qx * qx + qy * qy) / (2.0 * tl.R_EARTH) * 0.87
    vis = np.zeros((nr, ncol), bool)
    for cz in CAM_Z_RANGE:
        h0 = np.degrees(np.arctan2(zn - cz, rn[:, None])).max(0)
        el = np.degrees(np.arctan2(co[..., 2] - cz, rr[:, None]))
        run = np.maximum.accumulate(np.vstack([h0[None, :], el]), axis=0)[:-1]
        vis |= el >= run - 0.25
    # dilate: 3 rows, 2 columns
    v2 = vis.copy()
    for d in (1, 2, 3):
        v2[d:] |= vis[:-d]
        v2[:-d] |= vis[d:]
    v3 = v2.copy()
    for d in (1, 2):
        v3[:, d:] |= v2[:, :-d]
        v3[:, :-d] |= v2[:, d:]
    # faces that look at the sun stay (they cast the shadows)
    gz_r = np.gradient(co[..., 2], axis=0) / np.gradient(rr)[:, None]
    gz_a = np.gradient(co[..., 2], axis=1) / (rr[:, None] * math.radians(DAZ)) * -1.0   # columns run clockwise
    nx = -(gz_r * ca[None, :] - gz_a * sa[None, :])
    ny = -(gz_r * sa[None, :] + gz_a * ca[None, :])
    sa_, se_ = math.radians(SUN[0]), math.radians(SUN[1])
    lit = (nx * math.cos(se_) * math.cos(sa_) + ny * math.cos(se_) * math.sin(sa_) + math.sin(se_)) > 0.02
    high = att['alt'] > 250.0
    keepv = v3 | (lit & high)
    keep = keepv[:-1, :-1] | keepv[1:, :-1] | keepv[:-1, 1:] | keepv[1:, 1:]
    log('faces kept %.1f%% (visible %.1f%%)' % (100 * keep.mean(), 100 * vis.mean()))
    np.savez(os.path.join(OUT, 'mesh_far.npz'), co=co.reshape(-1, 3), nr=nr, ncol=ncol, keep=keep,
             **{'a_' + k: v.ravel() for k, v in att.items()})
    json.dump(dict(comp.info(), nr=nr, ncol=ncol), open(os.path.join(OUT, 'mesh_far.json'), 'w'))
    log('saved mesh_far', co.shape, 'quads %.2f M' % (keep.sum() / 1e6), '%.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
