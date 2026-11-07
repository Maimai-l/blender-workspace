# Qiting round 2 - the surroundings: hill terrain, plaza paving on the DWG outline, park paths, garden stairs,
# promenade, lakeside walk with its revetment and railing, the waterside platform, the lake, planting (cedars,
# broadleaf trees, willows, columnar trees, clipped hedges, lawn), lamps, the plaza furniture and the white
# sculptures. All placements come from qt_env_data / qt_env_grid (made by qiting/env/make_env.py).
import bpy, bmesh, math, random, zlib, base64
import numpy as np
from mathutils import Vector, Matrix
import xy_core as C, xy_plants as PL
import qt_dims as D
import qt_env_data as ED
import qt_env_grid as EG

E = ED.ENV
_G = {}


def _seed(s):
    return zlib.crc32(s.encode())


def grid():
    if _G:
        return _G
    def dec(b, dt):
        return np.frombuffer(zlib.decompress(base64.b64decode(b)), dtype=dt).reshape(EG.GNY, EG.GNX)
    _G['H'] = dec(EG.H_MM_B64, np.int32).astype(np.float64) / 1000.0
    _G['paved'] = dec(EG.PAVED_B64, np.uint8) > 0
    _G['water'] = dec(EG.WATER_B64, np.uint8) > 0
    _G['bank'] = dec(EG.BANK_B64, np.uint8) / 255.0
    _G['plaza'] = dec(EG.PLAZA_B64, np.uint8) > 0
    return _G


def height(x, y):
    H = grid()['H']
    fi = (x - EG.GX0) / EG.GRES; fj = (EG.GY1 - y) / EG.GRES
    i0 = int(np.clip(fi, 0, EG.GNX - 2)); j0 = int(np.clip(fj, 0, EG.GNY - 2))
    a = min(max(fi - i0, 0.0), 1.0); b = min(max(fj - j0, 0.0), 1.0)
    return float(H[j0, i0] * (1 - a) * (1 - b) + H[j0, i0 + 1] * a * (1 - b) + H[j0 + 1, i0] * (1 - a) * b + H[j0 + 1, i0 + 1] * a * b)


def _obj(name, me, coll, mats):
    o = bpy.data.objects.get(name)
    if o is not None:
        old = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    for m in mats:
        me.materials.append(C.mat(m))
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o


# ------------------------------------------------------------------ terrain
def terrain(coll):
    """0.5 m grid mesh; cells fully inside the plaza are left out (paved there); under paths the ground sits 6 cm
    lower so the paving never fights with it. Cover attributes for M_Terrain: lawn, forest floor, bank, mud."""
    g = grid()
    H = g['H'].copy()
    ny, nx = H.shape
    H[g['paved']] -= 0.06
    jj, ii = np.mgrid[0:ny, 0:nx]
    X = EG.GX0 + ii * EG.GRES
    Y = EG.GY1 - jj * EG.GRES
    pl = g['plaza']
    deep = pl.copy()
    for _ in range(2):
        d2 = deep.copy()
        d2[1:, :] &= deep[:-1, :]; d2[:-1, :] &= deep[1:, :]; d2[:, 1:] &= deep[:, :-1]; d2[:, :-1] &= deep[:, 1:]
        deep = d2
    keep = ~(deep[:-1, :-1] & deep[:-1, 1:] & deep[1:, :-1] & deep[1:, 1:])
    cj, ci = np.nonzero(keep)
    v00 = cj * nx + ci
    faces = np.stack([v00 + nx, v00 + nx + 1, v00 + 1, v00], 1)
    verts = np.stack([X.ravel(), Y.ravel(), H.ravel()], 1)
    me = bpy.data.meshes.new('QT_terrain')
    me.vertices.add(len(verts)); me.vertices.foreach_set('co', verts.astype(np.float32).ravel())
    me.loops.add(len(faces) * 4); me.loops.foreach_set('vertex_index', faces.astype(np.int32).ravel())
    me.polygons.add(len(faces)); me.polygons.foreach_set('loop_start', np.arange(0, len(faces) * 4, 4, dtype=np.int32))
    me.update(); me.validate()
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
    # cover weights
    water = g['water'].astype(np.float32)
    try:
        from scipy.ndimage import gaussian_filter
        forest = gaussian_filter(_forest_mask(X, Y), 3.0)
    except Exception:
        forest = _forest_mask(X, Y)
    bank = g['bank'].astype(np.float32)
    lawn = np.clip(1.0 - forest - bank, 0, 1) * (1 - water)
    for nm, arr in (('w_forest', np.clip(forest, 0, 1) * 0.85), ('w_bare', np.zeros_like(lawn)), ('w_bank', bank),
                    ('w_mud', water), ('lawn', lawn)):
        a = me.attributes.new(nm, 'FLOAT', 'POINT')
        a.data.foreach_set('value', np.asarray(arr, np.float32).ravel())
    return _obj('QT_terrain', me, coll, ['M_Terrain'])


def _forest_mask(X, Y):
    """leaf litter under the dense conifer stands (north and east slopes), from the tree list."""
    F = np.zeros(X.shape, np.float32)
    for (x, y, z, kind, var, s, rot) in E['trees']:
        if kind != 'cedar':
            continue
        r = 3.2 * s
        i0 = int((x - r - EG.GX0) / EG.GRES); i1 = int((x + r - EG.GX0) / EG.GRES) + 1
        j0 = int((EG.GY1 - (y + r)) / EG.GRES); j1 = int((EG.GY1 - (y - r)) / EG.GRES) + 1
        i0, j0 = max(i0, 0), max(j0, 0)
        sub = (X[j0:j1, i0:i1] - x) ** 2 + (Y[j0:j1, i0:i1] - y) ** 2 < r * r
        F[j0:j1, i0:i1][sub] = 1.0
    return F


def far_ground(coll):
    """flat ground beyond the grid on the land side (north, east, west); the lake takes the south."""
    x0, x1 = EG.GX0, EG.GX0 + (EG.GNX - 1) * EG.GRES
    y1, y0 = EG.GY1, EG.GY1 - (EG.GNY - 1) * EG.GRES
    z = height(0, y1)
    R = 1500.0
    V = [(-R, -R), (R, -R), (R, R), (-R, R), (x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    zz = [E['z_water'] - 3.0] * 2 + [-10.8] * 2 + [height(x0, y0), height(x1, y0), height(x1, y1), height(x0, y1)]
    verts = [(x, y, z_) for (x, y), z_ in zip(V, zz)]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new('QT_far_ground')
    me.from_pydata(verts, [], faces); me.update()
    for nm, v in (('w_forest', 0.7), ('lawn', 0.3), ('w_mud', 0.0), ('w_bank', 0.0), ('w_bare', 0.0)):
        a = me.attributes.new(nm, 'FLOAT', 'POINT'); a.data.foreach_set('value', [v] * 8)
    return _obj('QT_far_ground', me, coll, ['M_Terrain'])


# ------------------------------------------------------------------ paved ribbons
def _offset(pts, off, closed=False):
    P = np.array([(p[0], p[1]) for p in pts])
    n = len(P)
    out = []
    for i in range(n):
        a = P[i - 1] if (i > 0 or closed) else P[i]
        b = P[(i + 1) % n] if (i < n - 1 or closed) else P[i]
        t = b - a
        t = t / (np.linalg.norm(t) + 1e-9)
        nrm = np.array([-t[1], t[0]])
        out.append(P[i] + nrm * off)
    return np.array(out)


def ribbon(mb, pts, w, m, dz=0.03, closed=False, th=0.12, kerb=None):
    """paved strip along a centreline with heights: top at z + dz, with side faces down th; optional kerbs
    (width, height above the paving, material) along both edges. UV u = length, v = across (for joints)."""
    P = [(p[0], p[1], p[2]) for p in pts]
    L = [0.0]
    for a, b in zip(P[:-1], P[1:]):
        L.append(L[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    left = _offset(P, w / 2, closed); right = _offset(P, -w / 2, closed)
    n = len(P)
    rng = range(n if closed else n - 1)
    uvl = mb.uv
    for i in rng:
        j = (i + 1) % n
        za, zb = P[i][2] + dz, P[j][2] + dz
        q = [Vector((right[i][0], right[i][1], za)), Vector((right[j][0], right[j][1], zb)),
             Vector((left[j][0], left[j][1], zb)), Vector((left[i][0], left[i][1], za))]
        f = mb.face(q, m)
        if f is not None:
            uu = [L[i], L[j] if j > i else L[i] + math.hypot(P[j][0] - P[i][0], P[j][1] - P[i][1])]
            for l, (u, v) in zip(f.loops, ((uu[0], 0.0), (uu[1], 0.0), (uu[1], w), (uu[0], w))):
                l[uvl].uv = (u, v)
        if kerb:
            continue                     # the kerb's inner face closes the edge (a side face here would lie in its plane)
        for side, e in ((1, left), (-1, right)):
            # side faces facing outward (round 2 fix: they were wound inward)
            a = Vector((e[i][0], e[i][1], za)); b = Vector((e[j][0], e[j][1], zb))
            if side > 0:
                mb.face([a, b, b - Vector((0, 0, th)), a - Vector((0, 0, th))], m)
            else:
                mb.face([b, a, a - Vector((0, 0, th)), b - Vector((0, 0, th))], m)
    if kerb:
        kw, kh, km = kerb
        for side in (1, -1):
            e_out = _offset(P, side * (w / 2 + kw), closed)
            e_in = _offset(P, side * w / 2, closed)
            for i in rng:
                j = (i + 1) % n
                za, zb = P[i][2] + dz + kh, P[j][2] + dz + kh
                a0 = Vector((e_in[i][0], e_in[i][1], za)); b0 = Vector((e_in[j][0], e_in[j][1], zb))
                a1 = Vector((e_out[i][0], e_out[i][1], za)); b1 = Vector((e_out[j][0], e_out[j][1], zb))
                top = [a0, b0, b1, a1] if side > 0 else [a1, b1, b0, a0]
                mb.face(top, km)
                lo = Vector((0, 0, kh + 0.10))
                mb.face([b0, a0, a0 - lo, b0 - lo] if side > 0 else [a0, b0, b0 - lo, a0 - lo], km)
                mb.face([a1, b1, b1 - lo, a1 - lo] if side > 0 else [b1, a1, a1 - lo, b1 - lo], km)


def paths(coll):
    out = []
    groups = {'pave': ('QT_paths', 'M_PathPavers', (0.12, 0.03, 'M_Kerb')), 'pink': ('QT_promenade', 'M_PinkPavers', (0.25, 0.02, 'M_Kerb')),
              'walk': ('QT_lakewalk', 'M_WalkSlabs', None)}
    mbs = {k: C.MB() for k in groups}
    for name, d in E['paths'].items():
        g = groups[d['kind']]
        ribbon(mbs[d['kind']], d['pts'], d['w'], g[1], closed=d['closed'], kerb=g[2])
    for k, (nm, m, kb) in groups.items():
        o = mbs[k].finish(nm, coll, recalc=False, keep_uv=True)
        out.append(o)
    return out


# ------------------------------------------------------------------ plaza paving (DWG outline) and kerb
def plaza(coll, src):
    """setts in running bond on circular courses inside the DWG outline, outside the terraces; light kerb on the
    outline. Sett heights follow the plaza surface (falling toward the north edge)."""
    out = []
    import qt_ground as QG
    rng = random.Random(_seed('plaza2'))
    azr = E['plaza_az_r']
    A = [a for a, r in azr]; R = [r for a, r in azr]
    def r_edge(a_deg):
        return float(np.interp(a_deg % 360.0, A, R, period=360))
    r0 = D.TIER_R[2] + 0.02
    pts = []
    r = r0 + QG.SETT_W / 2
    k = 0
    while r < 26.0:
        n = int(2 * math.pi * r / (QG.SETT_L + QG.JOINT))
        off = (k % 2) * 0.5
        for i in range(n):
            a = 2 * math.pi * (i + off) / n
            if r > r_edge(math.degrees(a)) - 0.20 - QG.SETT_W / 2:
                continue
            x, y = r * math.cos(a), r * math.sin(a)
            hw = D.STAIR_W_CLEAR / 2 + D.STAIR_PARAPET
            if y > 0 and abs(x) < hw + 0.05 and y < 22.6:
                continue
            z = D.plaza_z(x, y) + rng.uniform(-0.0025, 0.0015) if hasattr(D, 'plaza_z') else -4.8
            pts.append(((x, y, z), (rng.uniform(-0.004, 0.004), rng.uniform(-0.004, 0.004), a + math.pi / 2 + rng.uniform(-0.01, 0.01)), 1.0))
        r += QG.SETT_W + QG.JOINT
        k += 1
    out.append(C.instancer('QT_plaza_setts', src, pts, coll, proxy=QG.sett_proxy('SRC_qt_sett_px', 'M_Setts')))
    # bed under the setts (dark joints) and the kerb on the outline
    mb = C.MB()
    N = 720
    ring_in = [((r0) * math.cos(2 * math.pi * i / N), r0 * math.sin(2 * math.pi * i / N)) for i in range(N)]
    ring_out = [(r_edge(360.0 * i / N) * math.cos(2 * math.pi * i / N), r_edge(360.0 * i / N) * math.sin(2 * math.pi * i / N)) for i in range(N)]
    rows = [[(x, y, D.plaza_z(x, y) - 0.075) for x, y in ring_in], [(x, y, D.plaza_z(x, y) - 0.075) for x, y in ring_out]]
    mb.quad_strip(rows, 'M_Dark', closed_u=True)
    bed = mb.finish('QT_plaza_bed', coll, recalc=False)
    if bed.data.polygons[0].normal.z < 0:
        bed.data.flip_normals()
    out.append(bed)
    mb = C.MB()
    rows = []
    for i in range(N):
        a = 2 * math.pi * i / N
        re = r_edge(360.0 * i / N)
        cx, cy = math.cos(a), math.sin(a)
        z = D.plaza_z(re * cx, re * cy)
        rows.append([((re + dr) * cx, (re + dr) * cy, z + dz) for dr, dz in ((-0.20, -0.10), (-0.20, 0.012), (-0.06, 0.03), (0.0, 0.0), (0.0, -0.45))])
    mb.quad_strip(rows + [rows[0]], 'M_Kerb', closed_u=False)
    out.append(mb.finish('QT_plaza_kerb', coll, recalc=True))
    return out


# ------------------------------------------------------------------ garden stairs
def stairs(coll):
    mb = C.MB()
    for name, d in E['stairs'].items():
        P = np.array(d['pts'])
        L = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
        tot = L[-1]
        dz = d['z1'] - d['z0']
        n = max(1, int(round(abs(dz) / 0.15)))
        tread = tot / n
        w = d['w']
        for k in range(n):
            s0, s1 = k * tread, (k + 1) * tread
            def at(s):
                i = min(max(np.searchsorted(L, s), 1), len(P) - 1)
                t = (s - L[i - 1]) / max(1e-9, L[i] - L[i - 1])
                p = P[i - 1] + (P[i] - P[i - 1]) * t
                tg = (P[i] - P[i - 1]) / max(1e-9, L[i] - L[i - 1])
                return p, np.array([-tg[1], tg[0]])
            pa, na = at(s0); pb, nb = at(min(s1 + 0.03, tot))
            z = d['z0'] + dz * (k + 1) / n + 0.03
            zb = z - 0.15 - 0.10
            hw = w / 2 - 0.01                # 1 cm clear of the cheek walls (no faces in their plane)
            q = [pa - na * hw, pb - nb * hw, pb + nb * hw, pa + na * hw]
            B = [Vector((p[0], p[1], zb)) for p in q]
            T = [Vector((p[0], p[1], z)) for p in q]
            mb.face(list(reversed(B)), 'M_GraniteStep'); mb.face(T, 'M_GraniteStep')
            for i in range(4):
                j = (i + 1) % 4
                mb.face([B[i], B[j], T[j], T[i]], 'M_GraniteStep')
        # cheek walls along both sides (light stone), following the flight
        for side in (-1, 1):
            rows = []
            for k in range(n + 1):
                s = min(k * tread, tot)
                i = min(max(np.searchsorted(L, s), 1), len(P) - 1)
                t = (s - L[i - 1]) / max(1e-9, L[i] - L[i - 1])
                p = P[i - 1] + (P[i] - P[i - 1]) * t
                tg = (P[i] - P[i - 1]) / max(1e-9, L[i] - L[i - 1])
                nr = np.array([-tg[1], tg[0]])
                z = d['z0'] + dz * k / n + 0.20
                e0 = p + nr * side * (w / 2); e1 = p + nr * side * (w / 2 + 0.25)
                rows.append([(e0[0], e0[1], z - 0.6), (e0[0], e0[1], z), (e1[0], e1[1], z), (e1[0], e1[1], z - 0.6)])
            mb.quad_strip(rows, 'M_Kerb', closed_u=True)
    return mb.finish('QT_garden_stairs', coll, recalc=True)


# ------------------------------------------------------------------ lake, revetment, railing, platform
def lake(coll):
    out = []
    zw = E['z_water']
    walk = E['walk']
    WP = np.array(walk['pts'], float)
    xs = np.arange(-1400, 1401, 10.0)
    def wy(x):
        return float(np.interp(x, WP[:, 0], WP[:, 1])) - walk['w'] / 2
    # water surface: from the walk's edge to 1400 m south; a thin closed slab (volume shading)
    mb = C.MB()
    top = [(x, min(wy(x), -60.0) if -130 <= x <= 130 else wy(np.clip(x, -125, 125)) - 0.0, zw) for x in xs]
    far = [(x, -1400.0, zw) for x in xs]
    bot = [(x, y, zw - 2.0) for x, y, _ in top]
    bfar = [(x, y, zw - 2.0) for x, y, _ in far]
    mb.quad_strip([far, top], 'M_Lake')
    mb.quad_strip([top, bot], 'M_Lake')
    mb.quad_strip([bot, bfar], 'M_Lake')
    o = mb.finish('QT_lake', coll, recalc=True)
    out.append(o)
    # revetment: dressed stone wall from the walk down into the water, coping slab on top
    mb = C.MB()
    xr = np.arange(-125, 125.1, 1.0)
    rows = []
    for x in xr:
        y = wy(x)
        rows.append([(x, y - 0.35, zw - 0.6), (x, y - 0.35, -12.2 - 0.05), (x, y + 0.05, -12.2 + 0.02)])
    mb.quad_strip([[r[0] for r in rows], [r[1] for r in rows]], 'M_Revetment')
    mb.quad_strip([[r[1] for r in rows], [r[2] for r in rows]], 'M_Kerb')
    out.append(mb.finish('QT_revetment', coll, recalc=False))
    # railing: square stone posts every 2.4 m with two iron rails, along the water edge (A1/A2)
    mb = C.MB()
    xr = np.arange(-124, 124.1, 2.4)
    plat = E['platform']
    for x in xr:
        if abs(x) < 7.2:
            continue
        y = wy(x) + 0.15
        mb.box((x - 0.09, y - 0.09, -12.2), (x + 0.09, y + 0.09, -11.15), 'M_Kerb')
    for zr, r in ((-11.25, 0.025), (-11.65, 0.018)):
        seg = []
        for x in np.arange(-124, 124.1, 1.0):
            if abs(x) < 7.2:
                if len(seg) > 1:
                    mb.sweep([Vector(p) for p in seg], [(r * math.cos(2 * math.pi * k / 6), r * math.sin(2 * math.pi * k / 6)) for k in range(6)], 'M_Iron')
                seg = []
                continue
            seg.append((x, wy(x) + 0.15, zr))
        if len(seg) > 1:
            mb.sweep([Vector(p) for p in seg], [(r * math.cos(2 * math.pi * k / 6), r * math.sin(2 * math.pi * k / 6)) for k in range(6)], 'M_Iron')
    out.append(mb.finish('QT_lake_railing', coll, recalc=True))      # recalc: swept rails come out inside out westward
    # waterside platform: pointed slab 2 m below the walk, steps down from the walk, railing round the point
    mb = C.MB()
    zp = E['z_platform']
    (ax, ay), (bx, by), (cx, cy) = plat
    y_edge = wy(0.0)
    poly = [(ax, y_edge), (bx, y_edge), (cx, cy)]
    B = [Vector((x, y, zw - 0.8)) for x, y in poly]; T = [Vector((x, y, zp)) for x, y in poly]
    mb.face(list(reversed(B)), 'M_WalkSlabs'); mb.face(T, 'M_WalkSlabs')
    for i in range(3):
        j = (i + 1) % 3
        mb.face([B[i], B[j], T[j], T[i]], 'M_Revetment')
    nst = int(round((-12.2 - zp) / 0.16))
    run = 0.32
    for k in range(nst):
        z = -12.2 - (k + 1) * (-12.2 - zp) / nst
        y0 = y_edge - k * run
        hx = 6.8 - k * run * (7.0 / max(1e-6, (y_edge - cy)))
        mb.box((-hx, y0 - run - 0.02, z - 0.2), (hx, y0, z), 'M_GraniteStep')
    for (p, q) in ((poly[1], poly[2]), (poly[2], poly[0])):
        n = 8
        for k in range(n + 1):
            x = p[0] + (q[0] - p[0]) * k / n; y = p[1] + (q[1] - p[1]) * k / n
            mb.box((x - 0.07, y - 0.07, zp), (x + 0.07, y + 0.07, zp + 1.0), 'M_Kerb')
        for zr in (zp + 0.95, zp + 0.55):
            mb.sweep([Vector((p[0], p[1], zr)), Vector((q[0], q[1], zr))], [(0.02 * math.cos(2 * math.pi * k / 6), 0.02 * math.sin(2 * math.pi * k / 6)) for k in range(6)], 'M_Iron')
    out.append(mb.finish('QT_platform', coll, recalc=True))
    return out


# ------------------------------------------------------------------ hedges
def hedges(coll):
    """clipped hedges in the bank just outside the plaza edge (A1/A2): a rounded box section swept along the
    outline, with a slightly irregular top; the foliage look comes from M_Hedge (displaced leaves shader)."""
    mb = C.MB()
    rng = random.Random(_seed('hedge'))
    for seg in E['hedges']:
        P = [Vector((x, y, z)) for x, y, z in seg]
        if len(P) < 3:
            continue
        rows = []
        for i, p in enumerate(P):
            a = P[max(i - 1, 0)]; b = P[min(i + 1, len(P) - 1)]
            t = (b - a); t.z = 0; t.normalize()
            nrm = Vector((-t.y, t.x, 0))
            h = 0.95 + 0.12 * math.sin(i * 0.37) + rng.uniform(-0.03, 0.03)
            w = 0.85
            sec = [(-w, -0.3), (-w, h * 0.55), (-w * 0.9, h * 0.85), (-w * 0.55, h), (w * 0.55, h), (w * 0.9, h * 0.85), (w, h * 0.55), (w, -0.3)]
            rows.append([p + nrm * u + Vector((0, 0, v)) for u, v in sec])
        mb.quad_strip(rows, 'M_Hedge', closed_u=True)
    o = mb.finish('QT_hedges', coll, recalc=False)
    for f in o.data.polygons:
        f.use_smooth = True
    return o


# ------------------------------------------------------------------ plants
def cedar_sources():
    """needle sprays for the cedars: flat fans of short needle tufts (M_LeafCedar)."""
    c = PL.src_coll('XY_SRC_cedar')
    for o in list(c.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for k in range(3):
        PL.branchlet('SRC_cedar_%d' % k, c, 'M_LeafCedar', seed=41 * k + 3, twig='M_Twig', n_twigs=9, tw_len=(0.26, 0.42),
                     L=0.032, W=0.0045, step=0.011, tip_n=6, tw_r=0.003)
    cp = PL.src_coll('XY_PX_cedar')
    for o in list(cp.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    mb = C.MB()
    for a in range(3):
        ang = a * math.pi / 3
        d = Vector((math.cos(ang), math.sin(ang), 0)) * 0.5
        mb.face([-d + Vector((0, 0, -0.08)), d + Vector((0, 0, -0.08)), d + Vector((0, 0, 0.12)), -d + Vector((0, 0, 0.12))], 'M_LeafCedar')
    PL._finish_src(mb, 'PX_cedar_0', cp)
    return c, cp


def cedar_template(name, coll, sets, seed, H=13.0, R=4.2, base=1.4):
    """deodar cedar (A1/A2 foreground): straight trunk; tiers of near-horizontal branches about a metre apart whose
    length falls with height to a narrow drooping leader; flat needle sprays along each branch so the crown reads as
    layered shelves with gaps between them, the branch tips hanging down."""
    rng = random.Random(seed)
    T = PL.Template(name)
    trunk = [Vector((0, 0, -0.2)), Vector((0, 0, H * 0.5)), Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), H))]
    PL.tube(T.mb, PL.bez(trunk[0], trunk[1], trunk[2], 8), 0.22 + 0.012 * H, 0.03, 9, 'M_Bark')
    z = base
    while z < H - 0.4:
        t = (z - base) / (H - base)
        Lb = R * (1.0 - t) ** 0.85 + 0.30
        nb = rng.randint(7, 9)
        a0 = rng.uniform(0, 2 * math.pi)
        droop = 0.10 + 0.22 * (1.0 - t)                    # lower tiers sweep down more
        for b in range(nb):
            a = a0 + 2 * math.pi * b / nb + rng.uniform(-0.3, 0.3)
            d = Vector((math.cos(a), math.sin(a), 0))
            L = Lb * rng.uniform(0.6, 1.15)
            p0 = Vector((0, 0, z))
            p1 = p0 + d * L * 0.5 + Vector((0, 0, 0.10 * L))
            p2 = p0 + d * L + Vector((0, 0, -droop * L))
            pts = PL.bez(p0, p1, p2, 5)
            PL.tube(T.mb, pts, 0.035 + 0.02 * L / R, 0.01, 5, 'M_Bark')
            # flat sprays along the outer 80 % of the branch, lying in the tier's plane
            s_ = 0.20
            while s_ <= 1.0:
                p = pts[0] * ((1 - s_) ** 2) + p1 * (2 * (1 - s_) * s_) + p2 * (s_ * s_)
                for k in range(3):
                    off = Vector((rng.gauss(0, 0.20), rng.gauss(0, 0.20), rng.gauss(-0.07, 0.12)))
                    rot = (rng.uniform(-0.30, 0.30) + 0.15, rng.uniform(-0.30, 0.30), a + rng.uniform(-0.9, 0.9))
                    T.add_point(p + off, rot, rng.uniform(1.8, 2.5), rng.randrange(3))
                s_ += 0.12
        z += rng.uniform(0.55, 0.85)
    # leader tuft
    for k in range(8):
        T.add_point(Vector((0, 0, H - 0.3 + 0.1 * k)), (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(0, 6.28)), 1.4, rng.randrange(3))
    c, cp = sets['cedar']
    return T.finish(coll, c, cp, proxy_frac=0.06, proxy_scale=2.2)


def plant_mats():
    import xy_mats as XM
    XM.leaf2('M_LeafWillow', (0.090, 0.140, 0.045), (0.190, 0.250, 0.090), back=(0.22, 0.25, 0.17), back_mix=0.55, trans=0.32,
             rough=0.45, var_tree=0.30, dry=(0.17, 0.17, 0.06), dry_frac=0.06)
    XM.leaf2('M_LeafCamphor', (0.045, 0.095, 0.018), (0.115, 0.185, 0.036), back=(0.11, 0.14, 0.06), back_mix=0.45, trans=0.28,
             rough=0.42, spec=0.5, var_tree=0.40, dry=(0.16, 0.12, 0.03), dry_frac=0.05)
    XM.leaf2('M_LeafLight', (0.085, 0.160, 0.030), (0.190, 0.270, 0.060), back=(0.17, 0.21, 0.10), back_mix=0.45, trans=0.35,
             rough=0.45, var_tree=0.35, dry=(0.20, 0.19, 0.05), dry_frac=0.06)
    XM.leaf2('M_LeafPurple', (0.060, 0.016, 0.024), (0.17, 0.048, 0.055), back=(0.11, 0.05, 0.05), back_mix=0.4, trans=0.30)
    XM.leaf2('M_LeafRed', (0.085, 0.014, 0.018), (0.18, 0.030, 0.030), back=(0.14, 0.05, 0.045), back_mix=0.4, trans=0.3)
    XM.leaf2('M_LeafBox', (0.020, 0.048, 0.010), (0.055, 0.100, 0.020), back=(0.07, 0.09, 0.04), back_mix=0.4, trans=0.2,
             rough=0.35, spec=0.6, var_tree=0.25, dry=(0.10, 0.10, 0.03), dry_frac=0.04)
    XM.leaf2('M_LeafCedar', (0.055, 0.100, 0.030), (0.140, 0.215, 0.060), back=(0.14, 0.18, 0.08), back_mix=0.35, trans=0.20,
             rough=0.55, spec=0.35, var_tree=0.25, dry=(0.12, 0.11, 0.05), dry_frac=0.04)
    XM.leaf2('M_Lotus', (0.045, 0.092, 0.026), (0.100, 0.170, 0.050))
    XM.leaf2('M_BankLeaf', (0.030, 0.075, 0.014), (0.085, 0.160, 0.030))
    XM.simple('M_LotusStalk', (0.06, 0.10, 0.03), rough=0.5)
    XM.grass_blade()
    XM.bark2('M_Bark', (0.040, 0.034, 0.028), (0.105, 0.090, 0.075), furrow=0.5, scale=7.0, stretch=3.0, moss=0.3)
    XM.bark2('M_BarkWillow', (0.038, 0.034, 0.030), (0.12, 0.11, 0.095), furrow=0.8, scale=6.0, stretch=5.0, moss=0.4)
    XM.bark2('M_Twig', (0.045, 0.040, 0.034), (0.10, 0.090, 0.075), furrow=0.3, scale=12.0, stretch=2.0, moss=0.0)
    XM.boulder()
    XM.terrain()


def templates():
    """all tree / shrub templates: xy_plants sources plus the cedar."""
    sets = PL.make_sources()
    sets['cedar'] = cedar_sources()
    c = PL.src_coll('XY_TREES')
    T = {}
    T['cedar'] = []
    for k in range(5):
        nm = 'TREE_cedar_%d' % k
        PL._clear_obj(nm)
        T['cedar'].append(cedar_template(nm, c, sets, seed=1200 + k, H=10.5 + 0.9 * k, R=4.8 + 0.45 * (k % 3), base=0.7))
    T['broad'] = []
    for k in range(5):
        nm = 'TREE_broad_%d' % k
        PL._clear_obj(nm)
        T['broad'].append(PL.broadleaf_template(nm, c, sets, 'light' if k % 2 else 'broad', seed=1300 + k, H=8.5 + 0.9 * k,
                                                R=3.2 + 0.5 * (k % 3), base=2.4 + 0.4 * (k % 2), trunk_r=0.17 + 0.02 * k,
                                                n_attr=1600, per_tip=4, spread=0.28))
    T['column'] = []
    for k in range(3):
        nm = 'TREE_column_%d' % k
        PL._clear_obj(nm)
        T['column'].append(PL.broadleaf_template(nm, c, sets, 'light', seed=1400 + k, H=14.0 + 1.5 * k, R=1.7 + 0.2 * k, base=2.2,
                                                 trunk_r=0.2, n_attr=1300, D=0.28, di=1.8, dk=0.5, per_tip=4, spread=0.22,
                                                 lump=0.10, shell=0.2))
    T['small'] = []
    for k in range(3):
        nm = 'TREE_small_%d' % k
        PL._clear_obj(nm)
        T['small'].append(PL.broadleaf_template(nm, c, sets, 'light', seed=1500 + k, H=5.0 + 0.6 * k, R=1.8 + 0.3 * k, base=1.6,
                                                trunk_r=0.09, n_attr=600, D=0.22, di=1.4, dk=0.38, per_tip=3, spread=0.22,
                                                spray_scale=(0.7, 1.0)))
    T['willow'] = []
    for k in range(5):
        nm = 'TREE_willow_%d' % k
        PL._clear_obj(nm)
        T['willow'].append(PL.willow_template(nm, c, sets, seed=1600 + k, H=9.5 + 0.7 * k, R=4.0 + 0.4 * (k % 3), fork=2.3 + 0.4 * (k % 2)))
    sh = []
    for k in range(4):
        nm = 'SHRUB_qt_%d' % k
        PL._clear_obj(nm)
        sh.append(PL.shrub_template(nm, c, sets, 'shrub', seed=1700 + k, R=0.7 + 0.25 * k, Hs=0.8 + 0.25 * k))
    T['shrub'] = sh
    for lst in T.values():
        for o in lst:
            o.hide_render = False
    return T, sets


def trees(coll, T):
    """one XY_Instancer per template, placing it at the tree list positions."""
    by = {}
    for (x, y, z, kind, var, s, rot) in E['trees']:
        lst = T[kind]
        o = lst[var % len(lst)]
        by.setdefault(o.name, (o, []))[1].append(((x, y, z - 0.05), (0, 0, rot), s))
    out = []
    for nm, (o, lst) in by.items():
        out.append(C.instancer('QT_trees_' + nm[5:], o, lst, coll))
    return out


def shrubs_and_grass(coll, T, sets):
    """shrubs on the banks and at path edges; lawn grass clumps within 70 m of the pavilion (viewport 1 %)."""
    g = grid()
    rng = np.random.default_rng(_seed('lawn'))
    H = g['H']
    ny, nx = H.shape
    out = []
    # shrubs: scattered on the bank band and at the plaza pockets
    pts = {o.name: (o, []) for o in T['shrub']}
    bj, bi = np.nonzero(g['bank'] > 0.6)
    sel = rng.choice(len(bj), size=min(len(bj), 160), replace=False)
    for k in sel:
        x = EG.GX0 + bi[k] * EG.GRES + rng.uniform(-0.25, 0.25); y = EG.GY1 - bj[k] * EG.GRES + rng.uniform(-0.25, 0.25)
        o = T['shrub'][int(rng.integers(0, len(T['shrub'])))]
        pts[o.name][1].append(((x, y, height(x, y) - 0.05), (0, 0, float(rng.uniform(0, 6.28))), float(rng.uniform(0.8, 1.3))))
    for nm, (o, lst) in pts.items():
        if lst:
            out.append(C.instancer('QT_shrubs_' + nm[6:], o, lst, coll))
    # grass: lawn cells (not paved, not water, not bank), within 70 m, density 26 per m2
    jj, ii = np.mgrid[0:ny, 0:nx]
    X = EG.GX0 + ii * EG.GRES; Y = EG.GY1 - jj * EG.GRES
    lawn = (~g['paved']) & (~g['water']) & (g['bank'] < 0.3) & (np.hypot(X, Y) < 70) & (Y > -66)
    F = _forest_mask(X, Y) > 0.5
    lawn &= ~F
    cj, ci = np.nonzero(lawn)
    cnt = rng.poisson(26 * EG.GRES ** 2, len(cj))
    rep = np.repeat(np.arange(len(cj)), cnt)
    gx = EG.GX0 + (ci[rep] + rng.uniform(-0.5, 0.5, len(rep))) * EG.GRES
    gy = EG.GY1 - (cj[rep] + rng.uniform(-0.5, 0.5, len(rep))) * EG.GRES
    gz = np.array([height(x, y) for x, y in zip(gx, gy)]) - 0.01
    rot = rng.uniform(0, 6.283, len(gx)); scl = rng.uniform(0.8, 1.3, len(gx)); kind = rng.integers(0, 4, len(gx))
    P = [((float(gx[i]), float(gy[i]), float(gz[i])), (0.0, 0.0, float(rot[i])), float(scl[i]), int(kind[i])) for i in range(len(gx))]
    out.append(PL.scatter('QT_lawn_grass', coll, P, 'grass', sets, frac=0.01))
    return out, len(P)


# ------------------------------------------------------------------ lamps
def lamp_sources():
    lib = C.lib_coll()
    out = {}
    if bpy.data.objects.get('SRC_lamp_park') is None:
        # park lamp (A1/A2 at the plaza edge and along the paths): dark grey post, white lantern box with a cap
        mb = C.MB()
        mb.cyl((0, 0, 0), (0, 0, 0.35), 0.11, 12, 'M_DarkGranite', r1=0.10)
        mb.cyl((0, 0, 0.35), (0, 0, 3.1), 0.055, 10, 'M_LampPost', r1=0.045)
        mb.box((-0.16, -0.16, 3.1), (0.16, 0.16, 3.16), 'M_LampPost')
        mb.box((-0.13, -0.13, 3.16), (0.13, 0.13, 3.52), 'M_LampGlow')
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.13 - 0.018, sy * 0.13 - 0.018, 3.16), (sx * 0.13 + 0.018, sy * 0.13 + 0.018, 3.52), 'M_LampPost')
        mb.lathe([(0.0, 3.52), (0.24, 3.52), (0.25, 3.55), (0.12, 3.68), (0.03, 3.74), (0.0, 3.80)], 4, 'M_LampPost', smooth=False)
        mb.finish('SRC_lamp_park', lib, recalc=True)
        # promenade lantern post (A1/A2: red lanterns on white posts along the pink road)
        mb = C.MB()
        mb.cyl((0, 0, 0), (0, 0, 3.8), 0.07, 10, 'M_PostWhite', r1=0.055)
        mb.box((-0.55, -0.04, 3.55), (0.55, 0.04, 3.63), 'M_PostWhite')
        for sx in (-1, 1):
            x = sx * 0.48
            mb.cyl((x, 0, 3.55), (x, 0, 3.40), 0.008, 4, 'M_Iron')
            prof = [(0.0, 2.86), (0.05, 2.86), (0.17, 2.94), (0.21, 3.08), (0.20, 3.22), (0.15, 3.33), (0.05, 3.38), (0.0, 3.40)]
            mb.lathe(prof, 12, 'M_LanternRed', center=(x, 0, 0), smooth=True)
            mb.cyl((x, 0, 2.86), (x, 0, 2.70), 0.012, 4, 'M_Gold')
        mb.lathe([(0.0, 3.8), (0.09, 3.8), (0.07, 3.92), (0.0, 4.0)], 8, 'M_PostWhite')
        mb.finish('SRC_lamp_lantern', lib, recalc=True)
        # lakeside lamp: tall grey pole with a single cylinder head
        mb = C.MB()
        mb.cyl((0, 0, 0), (0, 0, 4.6), 0.075, 10, 'M_LampPost', r1=0.05)
        mb.cyl((0, 0, 4.6), (0, 0, 5.05), 0.17, 12, 'M_LampGlow', r1=0.17)
        mb.lathe([(0.0, 5.05), (0.22, 5.05), (0.10, 5.2), (0.0, 5.25)], 12, 'M_LampPost')
        mb.finish('SRC_lamp_walk', lib, recalc=True)
        # floodlight mast at the waterside (A1 far crop): 10 m pole with four heads
        mb = C.MB()
        mb.cyl((0, 0, 0), (0, 0, 10.0), 0.16, 12, 'M_LampPost', r1=0.09)
        mb.box((-0.9, -0.06, 9.4), (0.9, 0.06, 9.52), 'M_LampPost')
        mb.box((-0.06, -0.9, 9.6), (0.06, 0.9, 9.72), 'M_LampPost')
        for (x, y) in ((-0.8, 0), (0.8, 0), (0, -0.8), (0, 0.8)):
            mb.box((x - 0.2, y - 0.14, 9.0), (x + 0.2, y + 0.14, 9.35), 'M_LampPost')
        mb.finish('SRC_lamp_mast', lib, recalc=True)
    for k in ('park', 'lantern', 'walk', 'mast'):
        out[k] = bpy.data.objects['SRC_lamp_' + k]
    return out


def lamps(coll):
    src = lamp_sources()
    by = {}
    for (x, y, z, kind, rot) in E['lamps']:
        by.setdefault(kind, []).append(((x, y, z - 0.02), (0, 0, rot), 1.0))
    return [C.instancer('QT_lamps_' + k, src[k], lst, coll) for k, lst in by.items()]


# ------------------------------------------------------------------ plaza furniture, sculptures
def furniture(coll):
    mb = C.MB()
    rng = random.Random(_seed('furn'))
    for (x, y) in E['tables']:
        z = D.plaza_z(x, y)
        mb.lathe([(0.0, z), (0.30, z), (0.30, z + 0.05), (0.16, z + 0.12), (0.13, z + 0.55), (0.18, z + 0.62), (0.45, z + 0.66),
                  (0.47, z + 0.72), (0.44, z + 0.76), (0.0, z + 0.76)], 24, 'M_StoneTable', center=(x, y, 0), smooth=True)
        for k in range(4):
            a = rng.uniform(0, 0.4) + k * math.pi / 2
            sx, sy = x + 0.85 * math.cos(a), y + 0.85 * math.sin(a)
            mb.lathe([(0.0, z), (0.17, z), (0.19, z + 0.06), (0.15, z + 0.22), (0.17, z + 0.40), (0.15, z + 0.44), (0.0, z + 0.44)],
                     16, 'M_StoneTable', center=(sx, sy, 0), smooth=True)
    for (x, y) in E['eggs']:
        z = D.plaza_z(x, y)
        prof = [(0.0, z - 0.02)]
        for k in range(1, 16):
            t = k / 15.0
            prof.append((0.42 * math.sin(math.pi * t) ** 0.8 * (1.0 - 0.25 * t), z - 0.02 + 1.55 * (1 - math.cos(math.pi * t)) / 2))
        prof.append((0.0, z + 1.53))
        mb.lathe(prof, 24, 'M_EggStone', center=(x, y, 0), smooth=True)
        mb.cyl((x, y, z), (x, y, z + 0.06), 0.65, 24, 'M_Kerb')
    for (x, y) in E['statues']:
        z = D.plaza_z(x, y)
        mb.box((x - 0.35, y - 0.35, z), (x + 0.35, y + 0.35, z + 0.45), 'M_DarkGranite')
        prof = [(0.0, z + 0.45), (0.17, z + 0.45), (0.21, z + 0.70), (0.15, z + 1.25), (0.11, z + 1.45), (0.07, z + 1.50),
                (0.09, z + 1.60), (0.085, z + 1.72), (0.0, z + 1.76)]
        mb.lathe(prof, 14, 'M_Bronze', center=(x, y, 0), smooth=True)
    x, y = E['sign']
    z = D.plaza_z(x, y)
    mb.box((x - 0.06, y - 0.06, z), (x + 0.06, y + 0.06, z + 0.9), 'M_Iron')
    M = Matrix.Translation((x, y, z + 0.95)) @ Matrix.Rotation(math.radians(-25), 4, 'X')
    q = [M @ Vector(v) for v in ((-0.45, -0.02, -0.28), (0.45, -0.02, -0.28), (0.45, 0.02, -0.28), (-0.45, 0.02, -0.28),
                                 (-0.45, -0.02, 0.28), (0.45, -0.02, 0.28), (0.45, 0.02, 0.28), (-0.45, 0.02, 0.28))]
    for f4 in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
        mb.face([q[i] for i in f4], 'M_SignBoard')
    return mb.finish('QT_plaza_furniture', coll, recalc=True)


def sculptures(coll):
    """丽人行: white figure groups on low plinths in the lawn by the lake (A1/A2 show them small and white). Kept as
    soft draped masses (heads, robes, a sleeve) like the softened relief - the photos give no detail to copy."""
    import mathutils.noise as MN
    mb = C.MB()
    for k, (x, y, z, rot) in enumerate(E['sculptures']):
        rng = random.Random(_seed('sc%d' % k))
        M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rot, 4, 'Z')
        mb.box((x - 1.3, y - 0.8, z - 0.1), (x + 1.3, y + 0.8, z + 0.45), 'M_Kerb')
        nf = rng.randint(2, 3)
        for f in range(nf):
            fx = (f - (nf - 1) / 2) * 0.75 + rng.uniform(-0.1, 0.1)
            Hf = rng.uniform(1.6, 1.85)
            prof = []
            for i in range(14):
                t = i / 13.0
                rr = 0.30 * (1.0 - t) ** 0.6 * (1.0 + 0.25 * math.sin(t * 9 + f)) + 0.08
                if t > 0.82:
                    rr = 0.10 * math.sin(math.pi * (t - 0.82) / 0.18 * 0.5 + 0.6) + 0.02
                prof.append((rr, 0.45 + Hf * t))
            prof[-1] = (0.0, 0.45 + Hf + 0.02)
            vs0 = len(mb.bm.verts)
            mb.lathe(prof, 18, 'M_MarbleRelief', center=(0, 0, 0), smooth=True, cap_top=False)
            # lean and sway, and move into place
            for v in list(mb.bm.verts)[vs0:]:
                h = v.co.z - 0.45
                v.co.x += fx + 0.12 * math.sin(h * 1.7 + f) + 0.04 * MN.noise(v.co * 3.0)
                v.co.y += 0.04 * MN.noise(v.co * 3.0 + Vector((5, 5, 5)))
                v.co = M @ v.co
    o = mb.finish('QT_sculptures', coll, recalc=True)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


# golden timber gate at the dock compound's entrance and the white sightseeing cart on the promenade (A2), placed
# by ray-casting A2 onto the terrain: posts at (-41.9, -41.7) and (-48.2, -41.9), beams at 4.7 and 6.6 m,
# hanging slats down to 2.8 m, red lanterns; the cart at (-33.4 .. -38.4, -37), heading west.
GATE = dict(x=-45.05, y=-41.8, half=3.15)
CART = dict(x=-35.9, y=-37.0, rot=math.pi)


def gate_and_cart(coll):
    import xy_mats as XM
    XM.simple('M_OchreWood', (0.42, 0.25, 0.055), rough=0.55, coat=0.1)
    XM.simple('M_CartWhite', (0.80, 0.80, 0.78), rough=0.35, coat=0.3)
    XM.simple('M_CartSeat', (0.03, 0.03, 0.035), rough=0.6)
    XM.simple('M_Tyre', (0.015, 0.015, 0.015), rough=0.8)
    out = []
    mb = C.MB()
    g = GATE
    z0 = height(g['x'], g['y'])
    for sx in (-1, 1):
        px = g['x'] + sx * g['half']
        mb.box((px - 0.2, g['y'] - 0.2, z0 - 0.2), (px + 0.2, g['y'] + 0.2, z0 + 7.2), 'M_OchreWood')
        mb.box((px - 0.28, g['y'] - 0.28, z0 + 7.2), (px + 0.28, g['y'] + 0.28, z0 + 7.45), 'M_OchreWood')
        mb.box((px - 0.32, g['y'] - 0.32, z0 - 0.05), (px + 0.32, g['y'] + 0.32, z0 + 0.6), 'M_Kerb')
        for dy in (-0.42, 0.42):
            mb.cyl((px, g['y'] + dy, z0 + 2.45), (px, g['y'] + dy, z0 + 3.25), 0.26, 12, 'M_LanternRed', r1=0.22)
    for zb, th in ((4.55, 0.32), (6.45, 0.38)):
        mb.box((g['x'] - g['half'] - 1.0, g['y'] - 0.18, z0 + zb), (g['x'] + g['half'] + 1.0, g['y'] + 0.18, z0 + zb + th), 'M_OchreWood')
    n = 26
    for k in range(n):
        x = g['x'] - g['half'] + 0.35 + (2 * g['half'] - 0.7) * (k + 0.5) / n
        mb.box((x - 0.025, g['y'] - 0.03, z0 + 2.8), (x + 0.025, g['y'] + 0.03, z0 + 6.45), 'M_OchreWood')
    out.append(mb.finish('QT_gate', coll, recalc=True))
    # cart: chassis, three bench rows, roof on four posts, wheels
    mb = C.MB()
    c = CART
    zc = height(c['x'], c['y'])
    M = Matrix.Translation((c['x'], c['y'], zc)) @ Matrix.Rotation(c['rot'], 4, 'Z')
    def bx(a, b, m):
        q = [M @ Vector(v) for v in ((a[0], a[1], a[2]), (b[0], a[1], a[2]), (b[0], b[1], a[2]), (a[0], b[1], a[2]),
                                     (a[0], a[1], b[2]), (b[0], a[1], b[2]), (b[0], b[1], b[2]), (a[0], b[1], b[2]))]
        for f4 in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
            mb.face([q[i] for i in f4], m)
    bx((-2.5, -0.72, 0.30), (2.5, 0.72, 0.62), 'M_CartWhite')
    bx((1.75, -0.72, 0.62), (2.5, 0.72, 1.15), 'M_CartWhite')                 # bonnet and dash
    for xr in (-1.9, -0.75, 0.4):
        bx((xr, -0.68, 0.62), (xr + 0.75, 0.68, 0.98), 'M_CartSeat')
        bx((xr - 0.08, -0.68, 0.62), (xr + 0.02, 0.68, 1.45), 'M_CartSeat')
    for xp in (-2.4, 2.25):
        for yp in (-0.66, 0.66):
            bx((xp - 0.04, yp - 0.04, 0.62), (xp + 0.04, yp + 0.04, 2.0), 'M_CartWhite')
    bx((-2.6, -0.8, 2.0), (2.55, 0.8, 2.1), 'M_CartWhite')
    for xw in (-1.7, 1.75):
        for yw in (-0.62, 0.62):
            p0 = M @ Vector((xw, yw - 0.1, 0.27)); p1 = M @ Vector((xw, yw + 0.1, 0.27))
            mb.cyl(p0, p1, 0.27, 14, 'M_Tyre')
    out.append(mb.finish('QT_cart', coll, recalc=True))
    return out


def get_templates():
    """the tree templates already in the file (built by templates()), grouped by kind."""
    T = {}
    for o in bpy.data.objects:
        if o.name.startswith('TREE_') and o.type == 'MESH':
            kind = o.name.split('_')[1]
            T.setdefault(kind, []).append(o)
    for k in T:
        T[k].sort(key=lambda o: o.name)
    return T
