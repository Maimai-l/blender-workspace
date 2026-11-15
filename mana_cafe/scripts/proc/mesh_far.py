"""Mountain mesh beyond the seam radius: the composed landscape (composite.py) on a polar grid around the camera, so
the mesh density is uniform on screen. Inside the seam the rows sink below the near mesh (the two cross at the seam).

    mesh_far.py     -> dem/mesh_far.npz, mesh_far.json
"""
import os, sys, math, time, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_lib as tl
from far_build import OUT
from composite import Composite, CAM, KEYS

AZ0, AZ1, DAZ = -182.0, -76.0, 0.036  # degrees (math convention), grid columns
R1, DR = 46000.0, 0.0014              # metres; rows are geometric: r *= 1 + DR


def main(log=print):
    t0 = time.time()
    comp = Composite()
    seam = comp.L['seam']
    r0 = seam - 80.0
    az = np.radians(np.arange(AZ1, AZ0 - 1e-9, -DAZ))                 # left to right on screen
    nr = int(math.log(R1 / r0) / math.log(1 + DR)) + 1
    rr = r0 * (1 + DR) ** np.arange(nr)
    ncol = az.size
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
    np.savez(os.path.join(OUT, 'mesh_far.npz'), co=co.reshape(-1, 3), nr=nr, ncol=ncol,
             **{'a_' + k: v.ravel() for k, v in att.items()})
    json.dump(dict(comp.info(), nr=nr, ncol=ncol), open(os.path.join(OUT, 'mesh_far.json'), 'w'))
    log('saved mesh_far', co.shape, 'z', float(co[..., 2].min()), float(co[..., 2].max()), '%.1fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
