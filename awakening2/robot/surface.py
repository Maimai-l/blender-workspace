"""surface.py - what grew on the Warden while it knelt: moss cushions, soil,
an old tree on its roof, flowers; plus designed chipped-paint and rust decals.

Everything is placed ONCE from the kneeling pose (upward faces, gravity for
rust streaks) and stored in each part's local frame, so it stays on-model in
every later pose.
"""
import os, sys, zlib, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
import numpy as np
import cv2
import r3d
from r3d import sd_sphere, sd_capsule, sd_round_cone, sd_ellipsoid, U, SU, SUB, rot_matrix
import rig as R
import warden as WD

MOSS, SOIL, WOOD = R.MOSS, R.SOIL, R.WOOD
FOLIAGE = 13
CACHE = os.environ.get('AW2_MESH_CACHE', '/home/user/aw2_cache/meshes')
SURF_VERSION = '9'


def rng_for(name):
    return np.random.default_rng(zlib.crc32(name.encode()))


# how much moss each part carries (clump count, radius range)
MOSS_PLAN = {
    'roof_L': (40, (0.5, 1.4)), 'roof_R': (30, (0.45, 1.3)),
    'pauldron_L': (26, (0.45, 1.1)), 'pauldron_R': (20, (0.4, 1.0)),
    'head': (10, (0.3, 0.6)), 'torso': (22, (0.4, 0.95)),
    'forearm_L': (16, (0.4, 0.85)), 'forearm_R': (10, (0.35, 0.7)),
    'thigh_L': (14, (0.45, 0.9)), 'shin_L': (13, (0.35, 0.75)), 'shin_R': (15, (0.35, 0.75)),
    'foot_L': (14, (0.35, 0.75)), 'foot_R': (12, (0.3, 0.7)), 'hand_R': (8, (0.3, 0.6)),
    'hand_L': (4, (0.3, 0.5)), 'pelvis': (10, (0.35, 0.75)), 'upperarm_L': (5, (0.3, 0.55)),
    'upperarm_R': (4, (0.3, 0.5)), 'thigh_R': (6, (0.35, 0.7)),
}


def kneel_mats(rig):
    import poses as PZ
    return rig.world_mats(PZ.grounded(rig, PZ.KNEEL_DORMANT))


def plan_moss(rig):
    """Return {part: list of lobes (cx, cy, cz, r) in part-local coords} and flower anchors."""
    mats = kneel_mats(rig)
    lobes = {}
    flowers = {}
    for part, (n, (r0, r1)) in MOSS_PLAN.items():
        p = rig.parts[part]
        V = p.mesh.V; N = p.mesh.N
        M = mats[part]
        Nw = N @ M[:3, :3].T
        up = Nw[:, 2]
        cand = np.where(up > 0.62)[0]
        if part == 'head':
            # keep moss off the face: only the dome top and the brow top
            cand = cand[(V[cand, 2] > 1.9)]
        if part == 'torso':
            cand = cand[(V[cand, 2] > 6.2)]
        if len(cand) == 0:
            continue
        rng = rng_for('moss/' + part)
        chosen = []
        tries = 0
        while len(chosen) < n and tries < 4000:
            tries += 1
            i = cand[rng.integers(len(cand))]
            c = V[i]
            r = rng.uniform(r0, r1)
            if all(np.linalg.norm(c - cc) > (r + rr) * 0.55 for cc, rr, _ in chosen):
                chosen.append((c, r, N[i]))
        L = []
        F = []
        for c, r, nrm in chosen:
            # tangent frame
            t1 = np.cross(nrm, [0.0, 0.0, 1.0])
            if np.linalg.norm(t1) < 1e-3:
                t1 = np.cross(nrm, [1.0, 0.0, 0.0])
            t1 /= np.linalg.norm(t1); t2 = np.cross(nrm, t1)
            k = rng.integers(8, 15)
            for j in range(k):
                a = rng.uniform(0, 2 * np.pi); d = rng.uniform(0, 0.8) * r
                lr = r * rng.uniform(0.36, 0.62) * (1.15 - 0.4 * d / r)
                pc = c + t1 * np.cos(a) * d + t2 * np.sin(a) * d + nrm * (-0.35 * lr)
                L.append((*pc, lr))
            # flowers sit on top of the cushion
            if rng.random() < 0.35:
                kind = int(rng.choice([0, 0, 1, 2]))
                for j in range(rng.integers(1, 4)):          # small clusters of one kind
                    a = rng.uniform(0, 2 * np.pi); d = rng.uniform(0, 0.5) * r
                    fp = c + t1 * np.cos(a) * d + t2 * np.sin(a) * d + nrm * (r * 0.42)
                    F.append((*fp, rng.uniform(0.09, 0.17), kind, float(rng.uniform(0, 6.28))))
        lobes[part] = np.array(L, np.float32)
        flowers[part] = np.array(F, np.float32) if F else np.zeros((0, 6), np.float32)
    return lobes, flowers


def _lobe_sdf(L):
    def f(p):
        d = None
        for cx, cy, cz, r in L:
            q = np.sqrt((p[..., 0] - cx) ** 2 + (p[..., 1] - cy) ** 2 + (p[..., 2] - cz) ** 2) - r
            d = q if d is None else np.minimum(d, q)
        return d
    return f


TREE_BASE = np.array([2.6, -0.6, 0.15], np.float32)
TREE_SCALE = 0.62


def tree_sdf(p):
    """Scaled-down old tree (see _tree_sdf_full)."""
    q = TREE_BASE + (p - TREE_BASE) / TREE_SCALE
    return _tree_sdf_full(q) * TREE_SCALE


def _tree_sdf_full(p):
    """The old tree on the left roof half (roof_L local frame = mirrored roof frame).
    Built in roof-half local coords for the RIGHT half and mirrored by the rig, so x is
    measured outward from the ridge."""
    # trunk: a leaning, twisting tapered tube from the roof surface up
    base = np.array([2.6, -0.6, 0.15], np.float32)
    pts = [base, base + (0.25, 0.1, 1.6), base + (0.75, -0.15, 3.0), base + (0.55, 0.3, 4.4), base + (1.1, 0.1, 5.6)]
    rads = [0.55, 0.42, 0.34, 0.26, 0.2]
    d = None
    for i in range(len(pts) - 1):
        s = sd_round_cone(p, pts[i], pts[i + 1], rads[i], rads[i + 1])
        d = s if d is None else SU(d, s, 0.15)
    # branches
    br = [(pts[2], pts[2] + (-1.4, 0.4, 1.3), 0.2, 0.08), (pts[3], pts[3] + (1.5, -0.5, 0.9), 0.17, 0.07),
          (pts[3], pts[3] + (-0.8, -0.9, 1.4), 0.15, 0.06), (pts[4], pts[4] + (0.6, 0.6, 1.0), 0.13, 0.05)]
    for a, b, r1, r2 in br:
        d = SU(d, sd_round_cone(p, a, b, r1, r2), 0.1)
    # roots gripping the roof and spilling over the eave
    roots = [((2.6, -0.6, 0.1), (4.4, -1.2, -0.4), 0.22, 0.1), ((2.6, -0.6, 0.1), (4.9, 0.4, -0.75), 0.2, 0.08),
             ((2.6, -0.6, 0.1), (1.0, -1.6, 0.2), 0.18, 0.08), ((4.4, -1.2, -0.4), (5.9, -1.5, -0.6), 0.1, 0.06),
             ((4.9, 0.4, -0.75), (6.0, 0.6, -1.5), 0.09, 0.05)]
    for a, b, r1, r2 in roots:
        d = SU(d, sd_round_cone(p, a, b, r1, r2), 0.08)
    return d


TREE_CANOPY = [  # foliage clumps (x, y, z, r) in roof-half local coords
    (3.7, -0.4, 6.0, 1.3), (2.6, 0.2, 6.4, 1.1), (4.6, 0.3, 6.3, 1.0), (3.5, 0.9, 6.9, 0.95),
    (1.5, 0.2, 5.5, 0.95), (4.9, -0.8, 5.5, 0.85), (3.0, -1.0, 6.8, 0.9), (2.2, 1.0, 5.6, 0.8),
    (4.1, 0.0, 7.3, 0.85), (5.6, 0.5, 5.8, 0.7), (1.3, -0.7, 6.3, 0.75),
]


def foliage_lobes(rng):
    L = []
    for cx, cy, cz, r in TREE_CANOPY:
        cx, cy, cz = TREE_BASE + (np.array([cx, cy, cz], np.float32) - TREE_BASE) * TREE_SCALE
        r = r * TREE_SCALE * 1.15
        for j in range(7):
            a = rng.uniform(0, 2 * np.pi); e = rng.uniform(-0.3, 0.9)
            d = r * rng.uniform(0.3, 0.75)
            L.append((cx + np.cos(a) * d, cy + np.sin(a) * d, cz + e * r * 0.5, r * rng.uniform(0.38, 0.62)))
    return np.array(L, np.float32)


def soil_lobes(rng):
    L = []
    for j in range(14):
        a = rng.uniform(0, 2 * np.pi); d = rng.uniform(0, 1.5)
        L.append((2.6 + np.cos(a) * d, -0.6 + np.sin(a) * d * 0.8, -0.05 + rng.uniform(-0.1, 0.15), rng.uniform(0.35, 0.65)))
    return np.array(L, np.float32)


def _mesh_cached(name, fn, lo, hi, voxel):
    import hashlib
    key = hashlib.md5(f'{name}/{SURF_VERSION}/{voxel}/{np.round(lo, 2)}/{np.round(hi, 2)}'.encode()).hexdigest()[:10]
    path = os.path.join(CACHE, f'surf_{name}_{key}.npz')
    if os.path.exists(path):
        return r3d.Mesh.load(path)
    V, F, N = r3d.mesh_sdf(fn, lo, hi, voxel)
    m = r3d.Mesh(V, F, N, name=name)
    m.save(path)
    return m


def add_growth(rig, voxel=0.035):
    """Add moss / soil / tree / foliage parts to the rig. Returns flower anchors."""
    os.makedirs(CACHE, exist_ok=True)
    lobes, flowers = plan_moss(rig)
    for part, L in lobes.items():
        if len(L) == 0:
            continue
        lo = L[:, :3].min(0) - L[:, 3].max() - 0.1
        hi = L[:, :3].max(0) + L[:, 3].max() + 0.1
        m = _mesh_cached('moss_' + part, _lobe_sdf(L), lo, hi, voxel)
        p = rig.add(R.Part('moss_' + part, part, (0, 0, 0), None, lo, hi, voxel, MOSS))
        p.mesh = r3d.Mesh(m.V, m.F, m.N, part=p.index, mat=MOSS, name=p.name)
        p.lobes = L
    rng = rng_for('tree')
    # tree lives on the LEFT roof half: model in right-half coords, mirror x
    def mir(m):
        return r3d.Mesh(m.V * np.array([-1, 1, 1], np.float32), m.F[:, [0, 2, 1]].copy(),
                        m.N * np.array([-1, 1, 1], np.float32))
    t = _mesh_cached('tree', tree_sdf, (-0.2, -2.6, -1.9), (7.3, 1.9, 5.6), 0.035)
    p = rig.add(R.Part('tree', 'roof_L', (0, 0, 0), None, None, None, 0.04, WOOD))
    mm = mir(t); p.mesh = r3d.Mesh(mm.V, mm.F, mm.N, part=p.index, mat=WOOD, name='tree')
    FL = foliage_lobes(rng)
    lo = FL[:, :3].min(0) - FL[:, 3].max() - 0.1; hi = FL[:, :3].max(0) + FL[:, 3].max() + 0.1
    f = _mesh_cached('foliage', _lobe_sdf(FL), lo, hi, 0.05)
    p = rig.add(R.Part('foliage', 'roof_L', (0, 0, 0), None, None, None, 0.05, FOLIAGE))
    mm = mir(f); p.mesh = r3d.Mesh(mm.V, mm.F, mm.N, part=p.index, mat=FOLIAGE, name='foliage')
    p.lobes = FL * np.array([-1, 1, 1, 1], np.float32)
    SL = soil_lobes(rng)
    lo = SL[:, :3].min(0) - 0.8; hi = SL[:, :3].max(0) + 0.8
    s = _mesh_cached('soil', _lobe_sdf(SL), lo, hi, 0.04)
    p = rig.add(R.Part('soil', 'roof_L', (0, 0, 0), None, None, None, 0.04, SOIL))
    mm = mir(s); p.mesh = r3d.Mesh(mm.V, mm.F, mm.N, part=p.index, mat=SOIL, name='soil')
    return flowers


# ----------------------------------------------------------------------------
# decals: designed chipped paint and rust, box-projected in part space
# ----------------------------------------------------------------------------

CHIP, RUST, STREAK, PRIMER, FADE, LICHEN = 1, 2, 3, 4, 5, 6
TEXEL = 0.012    # metres per decal texel


def _chip_poly(rng, cx, cy, size):
    n = rng.integers(7, 13)
    ang = np.sort(rng.uniform(0, 2 * np.pi, n))
    rad = size * rng.uniform(0.45, 1.0, n)
    # chips are flaky: some deep notches
    rad[rng.random(n) < 0.25] *= 0.45
    return np.stack([cx + np.cos(ang) * rad * rng.uniform(0.8, 1.3), cy + np.sin(ang) * rad], -1)


def _streak_poly(rng, x0, y0, dx, dy, length, width):
    n = 9
    t = np.linspace(0, 1, n)
    wob = np.cumsum(rng.normal(0, 0.08, n)) * width
    w = width * (1 - t) ** 0.7 * rng.uniform(0.7, 1.1, n)
    px, py = -dy, dx
    cx = x0 + dx * t * length + px * wob
    cy = y0 + dy * t * length + py * wob
    left = np.stack([cx + px * w, cy + py * w], -1)
    right = np.stack([cx - px * w, cy - py * w], -1)[::-1]
    return np.concatenate([left, right])


PRIORITY = (FADE, PRIMER, RUST, STREAK, CHIP, LICHEN)    # later wins


class Decals:
    """Per part, three projections (along X, Y, Z); per projection one anti-aliased
    coverage map per decal label, sampled bilinearly so edges stay smooth when magnified."""
    def __init__(self, rig, parts, mats_kneel):
        self.maps = {}
        for name, dens in parts.items():
            p = rig.parts[name]
            V = p.mesh.V
            lo = V.min(0) - 0.05; hi = V.max(0) + 0.05
            down = mats_kneel[name][:3, :3].T @ np.array([0, 0, -1.0])
            rng = rng_for('decal/' + name)
            maps = []
            for ax in range(3):
                u, v = [i for i in range(3) if i != ax]
                Wt = int(np.ceil((hi[u] - lo[u]) / TEXEL)) + 1
                Ht = int(np.ceil((hi[v] - lo[v]) / TEXEL)) + 1
                cov = {k: np.zeros((Ht, Wt), np.uint8) for k in PRIORITY}
                fp = np.zeros((Ht, Wt), np.uint8)
                pu = ((V[:, u] - lo[u]) / TEXEL).astype(int); pv = ((V[:, v] - lo[v]) / TEXEL).astype(int)
                fp[np.clip(pv, 0, Ht - 1), np.clip(pu, 0, Wt - 1)] = 255
                fp = cv2.dilate(fp, np.ones((9, 9), np.uint8))
                edge = cv2.morphologyEx(fp, cv2.MORPH_GRADIENT, np.ones((25, 25), np.uint8))
                ey, ex = np.nonzero(edge)
                area = (hi[u] - lo[u]) * (hi[v] - lo[v])
                nclust = int(dens * area * 1.1) + 3
                ddx, ddy = down[u], down[v]
                nd = math.hypot(ddx, ddy)

                def fill(k, poly):
                    cv2.fillPoly(cov[k], [np.round(poly * 16).astype(np.int32)], 255, lineType=cv2.LINE_AA, shift=4)
                # sun-faded paint: a few big soft-cornered blotches (drawn first, everything sits on top)
                for c in range(int(dens * area * 0.08) + 1):
                    cx, cy = rng.uniform(0, Wt), rng.uniform(0, Ht)
                    sz = rng.uniform(0.5, 1.4) / TEXEL
                    fill(FADE, _chip_poly(rng, cx, cy, sz))
                    fill(FADE, _chip_poly(rng, cx + rng.normal(0, sz * 0.5), cy + rng.normal(0, sz * 0.5), sz * 0.6))
                # lichen: clusters of small pale rosettes
                for c in range(int(dens * area * 0.12) + 1):
                    cx, cy = rng.uniform(0, Wt), rng.uniform(0, Ht)
                    for j in range(rng.integers(4, 14)):
                        r = rng.uniform(0.025, 0.075) / TEXEL
                        ox, oy = rng.normal(0, 0.16 / TEXEL, 2)
                        ang = np.linspace(0, 2 * np.pi, 9, endpoint=False)
                        rr = r * rng.uniform(0.75, 1.0, 9)
                        fill(LICHEN, np.stack([cx + ox + np.cos(ang) * rr, cy + oy + np.sin(ang) * rr], -1))
                for c in range(nclust):
                    if len(ex) and rng.random() < 0.7:
                        kk = rng.integers(len(ex)); cx, cy = ex[kk], ey[kk]
                    else:
                        cx, cy = rng.uniform(0, Wt), rng.uniform(0, Ht)
                    kind = rng.random()
                    if kind < 0.62:
                        for j in range(rng.integers(2, 7)):
                            sz = rng.uniform(0.05, 0.22) / TEXEL
                            ox, oy = rng.normal(0, 0.18 / TEXEL, 2)
                            fill(PRIMER, _chip_poly(rng, cx + ox, cy + oy, sz * 1.35))
                            fill(CHIP, _chip_poly(rng, cx + ox, cy + oy, sz))
                        if nd > 0.35 and rng.random() < 0.85:
                            L = rng.uniform(0.9, 3.2) / TEXEL
                            fill(STREAK, _streak_poly(rng, cx, cy, ddx / nd, ddy / nd, L, rng.uniform(0.03, 0.08) / TEXEL))
                    elif kind < 0.85:
                        sz = rng.uniform(0.12, 0.4) / TEXEL
                        fill(RUST, _chip_poly(rng, cx, cy, sz))
                        for j in range(rng.integers(2, 5)):
                            fill(CHIP, _chip_poly(rng, cx + rng.normal(0, sz * 0.6), cy + rng.normal(0, sz * 0.6), sz * 0.3))
                    elif nd > 0.35:
                        L = rng.uniform(1.0, 3.0) / TEXEL
                        fill(STREAK, _streak_poly(rng, cx, cy, ddx / nd, ddy / nd, L, rng.uniform(0.04, 0.1) / TEXEL))
                maps.append((cov, lo[u], lo[v], u, v))
            self.maps[p.index] = maps

    @staticmethod
    def _bilinear(img, x, y):
        H, W = img.shape
        x = np.clip(x - 0.5, 0, W - 1.001); y = np.clip(y - 0.5, 0, H - 1.001)
        x0 = x.astype(int); y0 = y.astype(int); fx = x - x0; fy = y - y0
        a = img[y0, x0].astype(np.float32); b = img[y0, x0 + 1].astype(np.float32)
        c = img[y0 + 1, x0].astype(np.float32); d = img[y0 + 1, x0 + 1].astype(np.float32)
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

    def lookup(self, part_idx, o, n_local):
        maps = self.maps.get(part_idx)
        out = np.zeros(len(o), np.uint8)
        if maps is None:
            return out
        ax = np.argmax(np.abs(n_local), axis=1)
        for a in range(3):
            sel = np.where(ax == a)[0]
            if len(sel) == 0:
                continue
            cov, lu, lv, u, v = maps[a]
            xu = (o[sel, u] - lu) / TEXEL; yv = (o[sel, v] - lv) / TEXEL
            res = np.zeros(len(sel), np.uint8)
            for k in PRIORITY:
                c = self._bilinear(cov[k], xu, yv)
                res[c > 127] = k
            out[sel] = res
        return out


DECAL_PARTS = {'torso': 1.0, 'pelvis': 1.0, 'head': 0.7, 'pauldron_R': 1.1, 'pauldron_L': 1.1,
               'forearm_R': 1.0, 'forearm_L': 1.0, 'thigh_R': 0.9, 'thigh_L': 0.9, 'shin_R': 1.0,
               'shin_L': 1.0, 'foot_R': 0.9, 'foot_L': 0.9, 'roof_R': 0.7, 'roof_L': 0.7}

DECAL_COLS = {   # (light, shadow) by decal label, for PAINT parts
    FADE: (WD.hexc('b77a63'), WD.hexc('6c4240')),     # sun-faded paint: lighter, greyer, same hue
    LICHEN: (WD.hexc('b9c19a'), WD.hexc('6a7466')),
    CHIP: (WD.hexc('5e5a57'), WD.hexc('34303c')),     # bare iron
    RUST: (WD.hexc('8c4a28'), WD.hexc('4c2a24')),     # rust: browner and more orange than the paint
    STREAK: (WD.hexc('7a3f27'), WD.hexc('472624')),
    PRIMER: (WD.hexc('8b4436'), WD.hexc('512a2c')),
}
ROOF_DECAL_COLS = {  # verdigris roof: chips show dark bronze, "rust" is pale green patina
    FADE: (WD.hexc('a6cbb9'), WD.hexc('5b8189')),
    LICHEN: (WD.hexc('d2d6b0'), WD.hexc('7c8577')),
    CHIP: (WD.hexc('6e5640'), WD.hexc('3c3238')),
    RUST: (WD.hexc('9cc7b3'), WD.hexc('5a8088')),
    STREAK: (WD.hexc('8fbfae'), WD.hexc('557a85')),
    PRIMER: (WD.hexc('5b8b86'), WD.hexc('35525f')),
}
