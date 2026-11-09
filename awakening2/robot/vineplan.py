"""vineplan.py - where vines hang from the Warden (planned from the kneeling pose)."""
import os, sys, zlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
import numpy as np
import r3d
import vines as VN

# part: (count, length range m, rooted fraction)
PLAN = {
    'forearm_L': (4, (2.5, 5.0), 0.0),
    'forearm_R': (3, (2.0, 4.5), 0.75),
    'roof_L': (5, (2.5, 6.0), 0.0),
    'roof_R': (4, (2.5, 5.5), 0.0),
    'pauldron_L': (3, (2.0, 4.0), 0.0),
    'pauldron_R': (3, (2.0, 4.0), 0.0),
    'torso': (3, (2.0, 4.5), 0.4),
    'thigh_L': (2, (1.8, 3.5), 0.66),
    'shin_R': (2, (1.0, 2.5), 1.0),
    'pelvis': (2, (1.5, 3.0), 0.66),
}


def plan(rig, kneel_pose):
    mats = rig.world_mats(kneel_pose)
    out = []
    for part, (n, (l0, l1), rooted) in PLAN.items():
        p = rig.parts[part]
        V = p.mesh.V; N = p.mesh.N
        M = mats[part]
        Vw = r3d.xform_points(M, V); Nw = r3d.xform_dirs(M, N)
        cand = np.where((Nw[:, 2] < -0.25) & (Vw[:, 2] > 0.8))[0]
        if part.startswith('roof'):
            # the eave edges: the outermost vertices of the half, underside
            cand = cand[np.abs(V[cand, 0]) > 4.6]
        if len(cand) == 0:
            continue
        rng = np.random.default_rng(zlib.crc32(('vine/' + part).encode()))
        chosen = []
        for _ in range(400):
            if len(chosen) >= n:
                break
            i = cand[rng.integers(len(cand))]
            if all(np.linalg.norm(Vw[i] - Vw[j]) > 0.9 for j in chosen):
                chosen.append(i)
        for k, i in enumerate(chosen):
            length = float(rng.uniform(l0, l1))
            root = None
            if rng.random() < rooted:
                h = float(Vw[i, 2])
                off = rng.normal(0, 0.6, 2)
                root = np.array([Vw[i, 0] + off[0], Vw[i, 1] + off[1], 0.0], np.float32)
                length = max(length, h * 1.12)
            out.append(VN.Vine(part, V[i], length, seg=0.3, root=root, name=f'{part}_{k}',
                               width=float(rng.uniform(0.07, 0.12)), leaf_every=float(rng.uniform(0.18, 0.3)),
                               leaf_size=float(rng.uniform(0.24, 0.36))))
    return out
