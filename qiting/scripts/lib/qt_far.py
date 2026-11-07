# Qiting round 2 - the far scene seen across the lake in the aerials A1/A2: the far shores and their tree belts,
# the island with its red pavilion, 紫云楼 on the south shore (waterfront terrace, podium, main tower, side towers,
# galleries), the red boat-stage, small boats, the western dragon-boat dock, far hall complexes and the city.
# Positions: master plan (lake, island, 紫云楼) checked with the calibrated A2 camera. Detail is kept to what reads at
# 200-3000 m; the haze comes from the compositor (qt_haze).
import bpy, bmesh, math, random, zlib
import numpy as np
from mathutils import Vector, Matrix
import xy_core as C, xy_roof as XR
import qt_env as QE

ZW = 426.5 - 441.4          # water level (model Z)
ZL = ZW + 1.6               # general ground level round the lake (428.1)

# lake outline beyond the near grid (model X, Y), counter-clockwise; the near shore is the DWG lakeside walk
LAKE = [(-310, -72), (-125, -69.5), (0, -71.0), (125, -84.0), (150, -150), (212, -166), (285, -171), (313, -189), (331, -226),
        (340, -290), (300, -302), (272, -278), (201, -278), (120, -264), (55, -262), (-71, -283), (-140, -302), (-210, -303),
        (-262, -282), (-300, -240), (-318, -150)]
ISLAND = [(-63, -213), (-80, -201), (-100, -198), (-124, -206), (-141, -232), (-136, -258), (-118, -272), (-95, -268), (-76, -246)]
ZIYUN = dict(x=-3.5, y_front=-270.0)                    # axis x (plan -7, A1 -8, A2 0: the middle) and the terrace front
RED_BOAT = (62.1, -206.6)
BOATS = [(-6.8, -148.2, 0.4), (117.5, -255.5, 1.2), (-38.3, -229.1, -0.6), (-166.8, -255.4, 2.0)]
DOCK = dict(x0=-100.0, x1=-170.0, y=-104.0)
BOATHOUSE = (-220.0, -199.0)

# far districts, placed by ray-casting the calibrated A2 aerial onto the ground (see docs/dimensions.md):
# Tang-style hall groups on the far shores, the grey-roofed housing west of 紫云楼, long white buildings to the
# south-east, mid-rise blocks, and the high-rise city from about 1.2 km out.
HALL_SITES = [(330, -330, 0.15, 5), (250, -360, 0.05, 4), (-260, -335, -0.1, 5), (-345, -262, 0.6, 4),
              (120, -322, 0.0, 3), (-150, -345, 0.0, 3), (420, -250, 0.4, 4), (-420, -180, -0.4, 4)]
VILLA_POLY = [(-110, -350), (-210, -340), (-330, -335), (-470, -300), (-1150, -300), (-1150, -1500), (-110, -1500)]
OFFICES = [(400, -880, 140, 32, 16), (250, -960, 180, 40, 22), (110, -1050, 160, 36, 18), (480, -1010, 90, 30, 14)]
_HALLS = []


def hall_list():
    """the individual halls of HALL_SITES: (x, y, length, depth, wall height, rotation), fixed by seed"""
    if not _HALLS:
        rng = random.Random(zlib.crc32(b'farhalls'))
        for (cx, cy, rot, n) in HALL_SITES:
            for k in range(n):
                w = rng.uniform(14, 28); d = rng.uniform(9, 14)
                hx = cx + (k - n / 2) * 30 * math.cos(rot) + rng.uniform(-4, 4)
                hy = cy + (k - n / 2) * 30 * math.sin(rot) + rng.uniform(-8, 8)
                _HALLS.append((hx, hy, w, d, rng.uniform(4, 7), rot))
    return _HALLS


def _seed(s):
    return zlib.crc32(s.encode())


def _inside(poly, x, y):
    n = len(poly); c = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def in_near_grid(x, y, m=0.0):
    import qt_env_grid as EG
    x0, x1 = EG.GX0, EG.GX0 + (EG.GNX - 1) * EG.GRES
    y1, y0 = EG.GY1, EG.GY1 - (EG.GNY - 1) * EG.GRES
    return (x0 + m) <= x <= (x1 - m) and (y0 + m) <= y <= (y1 - m)


# ------------------------------------------------------------------ far land
def ground_z(x, y):
    """far ground height: shore level, the land behind the hill higher, rising gently towards the south (少陵原)"""
    base = ZL + 0.6 * math.sin(x * 0.013) * math.sin(y * 0.011)
    t = min(1.0, max(0.0, (y + 95.0) / 55.0))           # land behind the hill sits higher (-10.8)
    base = base + (-10.8 - base) * t * t * (3 - 2 * t)
    if y < -700.0:
        base += min(-700.0 - y, 3300.0) * 0.008
    return base


def in_ziyun(x, y, m=0.0):
    return abs(x - ZIYUN['x']) < 75.0 + m and -365.0 - m < y < -230.0 + m


def far_land(coll, step=8.0):
    """land round the lake beyond the near grid: a coarse grid at the shore level (forest floor), rising gently away
    from the water, with the lake and the near grid cut out and lowered under 紫云楼's terrace; an outer plain at
    40 m steps out to the horizon; the island as its own patch."""
    import qt_env_grid as EG
    xs = np.arange(-1600, 1600 + 1e-6, step); ys = np.arange(400, -2600 - 1e-6, -step)
    nx, ny = len(xs), len(ys)
    verts = []
    gx0, gx1 = EG.GX0, EG.GX0 + (EG.GNX - 1) * EG.GRES
    gy1, gy0 = EG.GY1, EG.GY1 - (EG.GNY - 1) * EG.GRES
    zt = ZW + 1.2
    for y in ys:
        for x in xs:
            base = ground_z(x, y)
            if in_ziyun(x, y, 4.0):
                base = min(base, zt - 0.3)
            # within 40 m of the near grid: blend to the grid's edge height (no seam)
            cxg = min(max(x, gx0), gx1); cyg = min(max(y, gy0), gy1)
            dg = math.hypot(x - cxg, y - cyg)
            if dg < 40.0:
                ze = QE.height(cxg, cyg)
                w = 1.0 - dg / 40.0
                base = base + (ze - base) * w * w * (3 - 2 * w)
            verts.append((x, y, base))
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            cx, cy = xs[i] + step / 2, ys[j] - step / 2
            if in_near_grid(cx, cy, -step * 0.5):
                continue
            if _inside(LAKE, cx, cy):
                continue
            a = j * nx + i
            faces.append((a + nx, a + nx + 1, a + 1, a))
    # outer plain (40 m) round the inner grid, out to 6 km south and 4 km east and west
    S = 40.0
    oxs = np.arange(-4000, 4000 + 1e-6, S); oys = np.arange(1200, -6000 - 1e-6, -S)
    o0 = len(verts)
    onx = len(oxs)
    for y in oys:
        for x in oxs:
            verts.append((x, y, ground_z(x, y) - 0.4))
    for j in range(len(oys) - 1):
        for i in range(onx - 1):
            cx, cy = oxs[i] + S / 2, oys[j] - S / 2
            if -1600 + S < cx < 1600 - S and -2600 + S < cy < 400 - S:
                continue
            a = o0 + j * onx + i
            faces.append((a + onx, a + onx + 1, a + 1, a))
    me = bpy.data.meshes.new('QT_far_land')
    me.from_pydata(verts, [], faces)
    me.update()
    me.validate()
    for nm, v in (('w_forest', 0.85), ('lawn', 0.15), ('w_mud', 0.0), ('w_bank', 0.0), ('w_bare', 0.0)):
        a = me.attributes.new(nm, 'FLOAT', 'POINT'); a.data.foreach_set('value', [v] * len(verts))
    o = QE._obj('QT_far_land', me, coll, ['M_Terrain'])
    # island
    mb = C.MB()
    P = ISLAND
    cxy = (sum(p[0] for p in P) / len(P), sum(p[1] for p in P) / len(P))
    rows = []
    for k, s_ in enumerate((1.0, 0.85, 0.55, 0.0)):
        z = ZW + (-1.5 if k == 0 else 1.0 + 0.6 * k)
        rows.append([(cxy[0] + (x - cxy[0]) * s_, cxy[1] + (y - cxy[1]) * s_, z) for x, y in P])
    rows[0] = [(cxy[0] + (x - cxy[0]) * 1.06, cxy[1] + (y - cxy[1]) * 1.06, ZW - 1.5) for x, y in P]
    mb.quad_strip(rows[:3], 'M_Terrain', closed_u=True)
    mb.face([Vector(p) for p in rows[2]], 'M_Terrain')
    isl = mb.finish('QT_island', coll, recalc=True)
    for nm, v in (('w_forest', 0.8), ('lawn', 0.2), ('w_mud', 0.0), ('w_bank', 0.0), ('w_bare', 0.0)):
        a = isl.data.attributes.new(nm, 'FLOAT', 'POINT'); a.data.foreach_set('value', [v] * len(isl.data.vertices))
    return [o, isl]


def _seg_dist(px, py, poly):
    d = 1e9
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x1 - x0, y1 - y0
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy + 1e-12)))
        d = min(d, math.hypot(px - x0 - t * dx, py - y0 - t * dy))
    return d


def far_blocked(x, y):
    """places the far planting avoids: the near grid, water, 紫云楼, buildings, the dock"""
    if in_near_grid(x, y, -4) or _inside(LAKE, x, y) or in_ziyun(x, y, -6) or _inside(ISLAND, x, y):
        return True
    if any(abs(x - ox) < w / 2 + 6 and abs(y - oy) < d / 2 + 6 for ox, oy, w, d, h in OFFICES):
        return True
    for (hx, hy, w, d, h, rot) in hall_list():
        c, s_ = math.cos(rot), math.sin(rot)
        lx, ly = (x - hx) * c + (y - hy) * s_, -(x - hx) * s_ + (y - hy) * c
        if abs(lx) < w / 2 + 4.5 and abs(ly) < d / 2 + 4.5:
            return True
    if -196 < x < -95 and -137 < y < -95:              # the dock and its halls
        return True
    return False


def _realize_group():
    ng = bpy.data.node_groups.get('XY_RealizeAll')
    if ng is None:
        ng = bpy.data.node_groups.new('XY_RealizeAll', 'GeometryNodeTree')
        ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        gi = ng.nodes.new('NodeGroupInput'); go = ng.nodes.new('NodeGroupOutput')
        rz = ng.nodes.new('GeometryNodeRealizeInstances')
        ng.links.new(gi.outputs[0], rz.inputs[0]); ng.links.new(rz.outputs[0], go.inputs[0])
    return ng


def far_templates(T):
    """single-mesh copies (TREEF_*) of the tree templates for the far planting. The templates scatter their leaves
    as instances (XY_Foliage); instancing those again tens of thousands of times overflows the GPU's acceleration
    structure (OptiX ran out of memory at 28,000 trees), so each far tree is one instance of one realized mesh."""
    ng = _realize_group()
    lib = C.lib_coll()
    F = {}
    for kind, lst in T.items():
        F[kind] = []
        for o in lst:
            name = 'TREEF_' + o.name[5:]
            old = bpy.data.objects.get(name)
            if old is not None:
                me_old = old.data
                bpy.data.objects.remove(old, do_unlink=True)
                if me_old is not None and me_old.users == 0:
                    bpy.data.meshes.remove(me_old)
            # XY_Foliage shows 6 % proxy leaves in the viewport depsgraph (the one Python evaluates): point its viewport
            # branch at the real leaves, 40 % of them enlarged 1.5x (18 % at 2.1x for the leaf-heavy cedars and willows),
            # about the same canopy cover seen from afar
            fm = next((md for md in o.modifiers if md.type == 'NODES' and md.node_group and md.node_group.name == 'XY_Foliage'), None)
            saved = None
            if fm is not None:
                props = fm.properties.inputs
                ids = {it.name: it.identifier for it in fm.node_group.interface.items_tree if getattr(it, 'in_out', None) == 'INPUT'}
                saved = {k: getattr(props, ids[k]).value for k in ('Proxy', 'Proxy Fraction', 'Proxy Scale')}
                frac, scl = (0.18, 2.1) if kind in ('cedar', 'willow') else (0.40, 1.5)    # cedars and willows are leaf-heavy
                C.set_mod_input(fm, 'Proxy', getattr(props, ids['Leaves']).value)
                C.set_mod_input(fm, 'Proxy Fraction', frac)
                C.set_mod_input(fm, 'Proxy Scale', scl)
            m = o.modifiers.new('realize_tmp', 'NODES')
            m.node_group = ng
            try:
                dg = bpy.context.evaluated_depsgraph_get()
                dg.update()
                me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            finally:
                o.modifiers.remove(m)
                if saved is not None:
                    for k, v in saved.items():
                        C.set_mod_input(fm, k, v)
            me.name = name
            fo = bpy.data.objects.new(name, me)
            C.link(fo, lib)
            F[kind].append(fo)
    return F


def tree_proxy(kind):
    """low-poly crown (TREEP_<kind>) shown in the viewport instead of the far trees"""
    name = 'TREEP_' + kind
    o = bpy.data.objects.get(name)
    if o is not None:
        return o
    mb = C.MB()
    m = {'cedar': 'M_LeafCedar', 'willow': 'M_LeafWillow'}.get(kind, 'M_LeafCamphor')
    if kind in ('cedar', 'column'):
        h, r = (12.0, 3.6) if kind == 'cedar' else (13.0, 1.8)
        mb.lathe([(r, 1.2), (r * 0.75, h * 0.45), (0.05, h)], 6, m, smooth=False)
    else:
        h, r = {'broad': (9.0, 4.2), 'willow': (8.0, 4.0), 'small': (5.0, 2.4)}.get(kind, (8.0, 3.5))
        prof = [(0.05, h * 0.25)] + [(r * math.sin(math.pi * t), h * 0.25 + (h * 0.75) * (1 - math.cos(math.pi * t)) / 2)
                                     for t in (0.2, 0.4, 0.6, 0.8)] + [(0.05, h)]
        mb.lathe(prof, 6, m, smooth=False)
    return mb.finish(name, C.lib_coll(), recalc=True)


def far_trees(coll, T):
    """the far planting: shore belts (willows at the water, broadleaf behind), the island, dense park woodland round
    the lake thinning with distance, the thick wood behind 紫云楼, street trees in the housing; all instanced from the
    round-2 templates. Ground height from ground_z."""
    rng = random.Random(_seed('fartrees'))
    T = far_templates(T)
    pts = []

    def add(x, y, kind, sc=(0.9, 1.3)):
        lst = T[kind]
        o = lst[rng.randrange(len(lst))]
        pts.append((o, ((x, y, ground_z(x, y) - 0.2), (0, 0, rng.uniform(0, 6.28)), rng.uniform(*sc))))
    # shore belts along the lake outline (except the near shore, which is the planted DWG area)
    P = LAKE + [LAKE[0]]
    for (x0, y0), (x1, y1) in zip(P[:-1], P[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        tx, ty = (x1 - x0) / L, (y1 - y0) / L
        nx_, ny_ = ty, -tx                         # outward (land side) for a CCW polygon
        n = int(L / 3.2)
        for k in range(n):
            sp = (k + rng.random()) / max(n, 1)
            bx, by = x0 + (x1 - x0) * sp, y0 + (y1 - y0) * sp
            if by > -95 and abs(bx) < 140:
                continue
            for d, kind, prob in ((rng.uniform(2.5, 6), 'willow', 0.8), (rng.uniform(8, 16), 'broad', 1.0),
                                  (rng.uniform(16, 28), 'broad', 1.0), (rng.uniform(28, 45), 'broad' if rng.random() < 0.75 else 'cedar', 0.9),
                                  (rng.uniform(45, 70), 'broad', 0.8), (rng.uniform(70, 100), 'broad' if rng.random() < 0.8 else 'cedar', 0.6)):
                if rng.random() > prob:
                    continue
                x, y = bx + nx_ * d, by + ny_ * d
                if far_blocked(x, y):
                    continue
                add(x, y, kind)
    # woodland and planting further back
    nvil = 0
    # uniform samples (about one per 47 m2) thinned per zone to the canopy density seen in A1/A2
    for _ in range(90000):
        x = rng.uniform(-1150, 1150); y = rng.uniform(-1500, 330)
        if far_blocked(x, y):
            continue
        dl = _seg_dist(x, y, LAKE)
        if 120 < x < 240 and -70 < y < 130:
            # east of the surveyed site, between it and the W02 viewpoint (206.5, 54.6, +6.3): the photo looks over
            # low planting to the pavilion, so only scattered small trees here, none right by the viewpoint
            if math.hypot(x - 206.5, y - 54.6) < 30 or rng.random() > 0.15:
                continue
            add(x, y, 'small' if rng.random() < 0.6 else 'broad', (0.7, 1.0))
            continue
        if _inside(VILLA_POLY, x, y):
            keep = 0.13                                    # street and garden trees between the houses
        elif abs(x - ZIYUN['x']) < 130 and -800 < y < -330:
            keep = 0.95                                    # the thick wood round and behind 紫云楼
        elif y > -330 and abs(x) < 700:
            keep = 0.85                                    # the park round the lake
        else:
            keep = max(0.07, 0.85 * math.exp(-max(0.0, dl - 150.0) / 400.0))
        if rng.random() > keep:
            continue
        r = rng.random()
        kind = 'broad' if r < 0.72 else ('cedar' if r < 0.88 else ('column' if r < 0.95 else 'small'))
        add(x, y, kind, (1.0, 1.45) if kind == 'broad' else (0.9, 1.3))
    # island
    for _ in range(60):
        x = rng.uniform(-141, -63); y = rng.uniform(-272, -198)
        if _inside(ISLAND, x, y):
            add(x, y, 'willow' if rng.random() < 0.6 else 'broad')
    by = {}
    for o, item in pts:
        by.setdefault(o.name, (o, []))[1].append(item)
    out = [C.instancer('QT_far_trees_' + nm[6:], o, lst, coll, proxy=tree_proxy(nm[6:].split('_')[0])) for nm, (o, lst) in by.items()]
    return out, len(pts)


# ------------------------------------------------------------------ simple Tang-style halls
def roof(name, coll, cx, cy, A, B, z_eave, z_ridge, rot=0.0, kind='xieshan', lift=0.35):
    """a hall roof (deck only, tile top + dark soffit) on the xy_roof profile; A, B = half length / depth."""
    prof = XR.Profile(B, z_eave, z_ridge)
    shape = XR.RoofShape(kind, A, B, prof, xg=max(0.5, A - B * 0.75), lift=lift, lift_len=max(1.5, B * 0.35))
    M = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(rot, 4, 'Z')
    return XR.deck(name, shape, M, coll, t_top=0.12, t_sof=0.45, res=0.8, mat_top='M_TileFar', mat_sof='M_RedDark')


def hall(mb, cx, cy, w, d, z0, h, rot=0.0, body='M_Plaster', cols='M_Red', plat=0.9):
    """platform + body with red columns (boxes only)."""
    c, s = math.cos(rot), math.sin(rot)
    def bx(x0, y0, z_0, x1, y1, z_1, m):
        P = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        P = [(cx + x * c - y * s, cy + x * s + y * c) for x, y in P]
        B = [Vector((x, y, z_0)) for x, y in P]; T = [Vector((x, y, z_1)) for x, y in P]
        mb.face(list(reversed(B)), m); mb.face(T, m)
        for i in range(4):
            j = (i + 1) % 4
            mb.face([B[i], B[j], T[j], T[i]], m)
    bx(-w / 2 - 1.2, -d / 2 - 1.2, z0, w / 2 + 1.2, d / 2 + 1.2, z0 + plat, 'M_Kerb')
    bx(-w / 2 + 0.6, -d / 2 + 0.6, z0 + plat, w / 2 - 0.6, d / 2 - 0.6, z0 + plat + h, body)
    n = max(2, int(w / 4.5))
    for k in range(n + 1):
        x = -w / 2 + 0.6 + (w - 1.2) * k / n
        for y in (-d / 2 + 0.45, d / 2 - 0.45):
            bx(x - 0.25, y - 0.25, z0 + plat, x + 0.25, y + 0.25, z0 + plat + h, cols)


# ---- building blocks for the far halls (kept coarse: they are seen from 250 m and more)
def frustum(mb, x0, x1, y0, y1, z0, z1, m, inset=(0.0, 0.0, 0.0, 0.0), top=True):
    """battered block: bottom rectangle x0..x1, y0..y1 at z0, top inset by (west, east, south, north) at z1"""
    iw, ie, isth, inth = inset
    B = [Vector(v) for v in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))]
    T = [Vector(v) for v in ((x0 + iw, y0 + isth, z1), (x1 - ie, y0 + isth, z1), (x1 - ie, y1 - inth, z1), (x0 + iw, y1 - inth, z1))]
    for i in range(4):
        j = (i + 1) % 4
        mb.face([B[i], B[j], T[j], T[i]], m)
    if top:
        mb.face(T, m)


def rail(mb, pts, z, h=1.0, step=1.8, m='M_Marble', zfun=None):
    """balustrade along a 2D polyline: top and bottom rails with posts (reads as a light lattice band far off)"""
    zf = zfun or (lambda x, y: z)
    for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
        L = math.hypot(xb - xa, yb - ya)
        if L < 1e-6:
            continue
        n = max(1, int(round(L / step)))
        tx, ty = (xb - xa) / L, (yb - ya) / L
        nx_, ny_ = -ty * 0.13, tx * 0.13
        for k in range(n):
            s0, s1 = k / n, (k + 1) / n
            p0 = (xa + (xb - xa) * s0, ya + (yb - ya) * s0); p1 = (xa + (xb - xa) * s1, ya + (yb - ya) * s1)
            z0, z1 = zf(*p0), zf(*p1)
            for zz, th in ((h - 0.16, 0.16), (0.12, 0.14)):
                Q = [Vector((p0[0] - nx_, p0[1] - ny_, z0 + zz)), Vector((p1[0] - nx_, p1[1] - ny_, z1 + zz)),
                     Vector((p1[0] + nx_, p1[1] + ny_, z1 + zz)), Vector((p0[0] + nx_, p0[1] + ny_, z0 + zz))]
                U = [q + Vector((0, 0, th)) for q in Q]
                mb.face(U, m); mb.face(list(reversed(Q)), m)
                for i in range(4):
                    j = (i + 1) % 4
                    mb.face([Q[i], Q[j], U[j], U[i]], m)
            mb.box((p0[0] - 0.13, p0[1] - 0.13, z0), (p0[0] + 0.13, p0[1] + 0.13, z0 + h), m)
        mb.box((xb - 0.13, yb - 0.13, zf(xb, yb)), (xb + 0.13, yb + 0.13, zf(xb, yb) + h), m)


def rect_pts(x0, x1, y0, y1, open_side=None, gap=None):
    """closed rectangle as a polyline; open_side 'N'/'S' leaves a centred gap of width gap (for a stair)"""
    if open_side == 'N':
        xm = (x0 + x1) / 2
        return [[(xm - gap / 2, y1), (x0, y1), (x0, y0), (x1, y0), (x1, y1), (xm + gap / 2, y1)]]
    return [[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]]


def columns(mb, x0, x1, y0, y1, z0, z1, step, m='M_Red', r=0.38):
    """square columns round a rectangle (corners included), about `step` apart"""
    pts = set()
    for (xa, ya), (xb, yb) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        n = max(1, int(round(math.hypot(xb - xa, yb - ya) / step)))
        for k in range(n):
            pts.add((round(xa + (xb - xa) * k / n, 3), round(ya + (yb - ya) * k / n, 3)))
    for (x, y) in pts:
        mb.box((x - r, y - r, z0), (x + r, y + r, z1), m)


def walls(mb, x0, x1, y0, y1, z0, z1, m_wall='M_Plaster', m_win='M_WindowPanel', bay=4.5, sill=0.9, head=0.8):
    """storey body: plaster walls with a lattice-window band on all four sides"""
    mb.box((x0, y0, z0), (x1, y1, z0 + sill), m_wall)
    mb.box((x0, y0, z1 - head), (x1, y1, z1), m_wall)
    mb.box((x0 + 0.05, y0 + 0.05, z0 + sill), (x1 - 0.05, y1 - 0.05, z1 - head), m_win)


def skirt(name, coll, cx, cy, A, B, z_eave, rise, depth, lift=0.5, rot=0.0):
    """pent roof ring (腰檐 / lower eave of a double roof): only `depth` metres in from the eave"""
    prof = XR.Profile(depth, z_eave, z_eave + rise)
    shape = XR.RoofShape('pyramid', A, B, prof, lift=lift, lift_len=max(2.0, min(A, B) * 0.3), d_cap=depth)
    M = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(rot, 4, 'Z')
    return XR.deck(name, shape, M, coll, t_top=0.12, t_sof=0.40, res=0.7, mat_top='M_TileFar', mat_sof='M_RedDark')


def hip_gable(name, coll, cx, cy, A, B, z_eave, z_ridge, xg, lift=0.9, rot=0.0, ridge_h=1.2, gold=True):
    """歇山 roof with its gable triangles, a ridge and gilded ridge ends (one object)"""
    prof = XR.Profile(B, z_eave, z_ridge)
    shape = XR.RoofShape('xieshan', A, B, prof, xg=xg, lift=lift, lift_len=max(2.0, B * 0.4))
    M = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(rot, 4, 'Z')
    deck = XR.deck(name, shape, M, coll, t_top=0.14, t_sof=0.50, res=0.7, mat_top='M_TileFar', mat_sof='M_RedDark')
    mb = C.MB()
    zg = shape.zg()
    yg = B - (A - xg)                         # half width of the gable triangle at its base
    for sx in (-1, 1):
        pts = [Vector((sx * xg, y, max(zg, shape.z(sx * xg * 0.999, y) - 0.1))) for y in np.linspace(-yg, yg, 9)]
        mb.face(pts if sx > 0 else list(reversed(pts)), 'M_RedDark')
    zr = shape.z(0.0, 0.0)
    mb.box((-xg - 0.4, -0.45, zr - 0.3), (xg + 0.4, 0.45, zr + ridge_h), 'M_TileFar')
    for sx in (-1, 1):
        mb.box((sx * xg - 0.55, -0.35, zr), (sx * xg + 0.55, 0.35, zr + ridge_h + 1.3), 'M_Gold' if gold else 'M_TileFar')
    mb.transform(M)
    o = mb.finish(name + '_ridge', coll, recalc=True)
    return [deck, o]


def arch_bridge(mb, xa, xb, y0, y1, z_end, z_mid, z_spring, z_crown, m='M_GraniteLight', n=16):
    """flying gallery: an arched bridge between two piers (deck, spandrels, arch soffit) with balustrades"""
    def zt_(t): return z_end + (z_mid - z_end) * math.sin(math.pi * t)
    def za_(t): return z_spring + (z_crown - z_spring) * math.sqrt(max(0.0, 1.0 - (2 * t - 1) ** 2))
    ts = np.linspace(0.0, 1.0, n + 1)
    xs = [xa + (xb - xa) * t for t in ts]
    for yy, flip in ((y0, False), (y1, True)):
        for i in range(n):
            q = [Vector((xs[i], yy, za_(ts[i]))), Vector((xs[i + 1], yy, za_(ts[i + 1]))),
                 Vector((xs[i + 1], yy, zt_(ts[i + 1]))), Vector((xs[i], yy, zt_(ts[i])))]
            mb.face(list(reversed(q)) if flip else q, m)
    for i in range(n):
        mb.face([Vector((xs[i], y0, zt_(ts[i]))), Vector((xs[i + 1], y0, zt_(ts[i + 1]))),
                 Vector((xs[i + 1], y1, zt_(ts[i + 1]))), Vector((xs[i], y1, zt_(ts[i])))], 'M_WalkSlabs')
        mb.face([Vector((xs[i], y1, za_(ts[i]))), Vector((xs[i + 1], y1, za_(ts[i + 1]))),
                 Vector((xs[i + 1], y0, za_(ts[i + 1]))), Vector((xs[i], y0, za_(ts[i])))], m)
    zf = lambda x, y: zt_((x - xa) / (xb - xa))
    for yy in (y0 + 0.2, y1 - 0.2):
        rail(mb, [(xa, yy), (xb, yy)], 0.0, h=1.0, step=1.2, zfun=zf)


def ziyun(coll):
    """紫云楼 (A1/A2, master plan item 6), measured by ray-casting the calibrated aerials (see docs): a waterfront
    terrace with a rimmed pool in front, broad steps, a forecourt, the main tower on a battered stone podium with a
    central stair and three doors, two que towers on bastions joined to the podium by arched flying galleries.
    Main tower: two storeys with balconies, a pent roof between them, a double-eaved hip-gable top roof; ridge about
    35 m above the terrace. Axis x = -7 (plan; A1 agrees within 2 m), terrace front y = -270."""
    out = []
    X0, YF = ZIYUN['x'], ZIYUN['y_front']
    zt = ZW + 1.2
    zf = zt + 1.5                     # forecourt
    zp = zt + 9.4                     # podium top
    zq = zt + 9.2                     # que bastion top
    yc = -328.0                       # main tower centre
    mb = C.MB()
    X = lambda x: X0 + x
    # waterfront terrace, its front lip, the rimmed pool in the lake
    mb.box((X(-72.5), -300.0, ZW - 1.0), (X(72.5), YF, zt), 'M_WalkSlabs')
    for (x0, x1, y0, y1) in ((-55.0, 55.0, -236.8, -236.0), (-55.0, -54.2, -270.0, -236.0), (54.2, 55.0, -270.0, -236.0)):
        mb.box((X(x0), y0, ZW - 1.0), (X(x1), y1, ZW + 0.25), 'M_Marble')
    rail(mb, [(X(-72.0), YF - 0.4), (X(72.0), YF - 0.4)], zt, h=0.9, step=2.4)
    # broad steps up to the forecourt, the forecourt
    for k in range(6):
        y = -294.0 - k * 1.0
        mb.box((X(-50.0), y - 1.0, zt), (X(50.0), y, zt + (k + 1) * 0.25), 'M_GraniteStep')
    mb.box((X(-50.0), -362.0, zt), (X(50.0), -300.0, zf), 'M_WalkSlabs')
    # lamp posts on the terrace (white globes)
    for xl in (-42.0, -32.5, -23.0, -13.5, 13.5, 23.0, 32.5, 42.0):
        mb.box((X(xl) - 0.16, -293.4, zt), (X(xl) + 0.16, -293.1, zt + 5.6), 'M_LampPost')
        mb.box((X(xl) - 0.35, -293.6, zt + 5.5), (X(xl) + 0.35, -292.9, zt + 6.2), 'M_LampGlass')
    # main stair with cheek walls, landing
    nst = 30
    for k in range(nst):
        y = -300.0 - k * 0.4
        mb.box((X(-9.5), y - 0.4, zf), (X(9.5), y, zf + (k + 1) * (zt + 6.8 - zf) / nst), 'M_GraniteStep')
    mb.box((X(-9.5), -315.0, zf), (X(9.5), -312.0, zt + 6.8), 'M_GraniteStep')
    for sx in (-1, 1):
        xa, xb = (X(9.5), X(12.0)) if sx > 0 else (X(-12.0), X(-9.5))
        P = [Vector((xa, -300.0, zf)), Vector((xb, -300.0, zf)), Vector((xb, -300.0, zf + 1.0)), Vector((xa, -300.0, zf + 1.0))]
        Q = [Vector((xa, -315.0, zf)), Vector((xb, -315.0, zf)), Vector((xb, -315.0, zp)), Vector((xa, -315.0, zp))]
        R = [Vector((xa, -312.0, zt + 7.8)), Vector((xb, -312.0, zt + 7.8))]
        mb.face([P[0], P[1], P[2], P[3]], 'M_GraniteLight')
        mb.face([P[3], P[2], R[1], Q[2], Q[3], R[0]], 'M_GraniteLight')
        mb.face([P[0], P[3], R[0], Q[3], Q[0]], 'M_GraniteLight')
        mb.face([P[1], Q[1], Q[2], R[1], P[2]], 'M_GraniteLight')
    # podium: battered wings either side of the stair, the central block behind the landing with three doors
    for sx in (-1, 1):
        if sx > 0:
            frustum(mb, X(12.0), X(23.5), -360.0, -303.0, zf, zp, 'M_GraniteLight', inset=(0.0, 1.0, 1.0, 0.0))
        else:
            frustum(mb, X(-23.5), X(-12.0), -360.0, -303.0, zf, zp, 'M_GraniteLight', inset=(1.0, 0.0, 1.0, 0.0))
    mb.box((X(-12.0), -360.0, zt + 6.8), (X(12.0), -315.0, zp), 'M_GraniteLight')
    for xd in (-5.5, 0.0, 5.5):
        mb.box((X(xd - 1.6), -315.15, zt + 6.8), (X(xd + 1.6), -314.95, zt + 9.0), 'M_Dark')
    rail(mb, [(X(-12.0), -304.2), (X(-22.3), -304.2), (X(-22.3), -359.0)], zp, h=1.0)
    rail(mb, [(X(12.0), -304.2), (X(22.3), -304.2), (X(22.3), -359.0)], zp, h=1.0)
    rail(mb, [(X(-12.0), -315.3), (X(12.0), -315.3)], zp, h=1.0)
    # que bastions and the flying galleries
    for sx in (-1, 1):
        cx = sx * 35.0
        frustum(mb, X(cx - 5.5), X(cx + 5.5), -320.0, -306.0, zf, zq, 'M_GraniteLight', inset=(0.9, 0.9, 0.9, 0.9))
        rail(mb, rect_pts(X(cx - 4.4), X(cx + 4.4), -318.9, -307.1)[0], zq, h=1.0)
        xa, xb = (X(22.5), X(cx - 4.6)) if sx > 0 else (X(cx + 4.6), X(-22.5))
        arch_bridge(mb, xa, xb, -316.0, -310.0, zq, zq + 1.2, zf, zt + 7.4)
    out.append(mb.finish('QT_ziyun_base', coll, recalc=True))
    # main tower bodies, balconies and columns; que pavilions
    mb = C.MB()
    mb.box((X(-19.5), -347.0, zp), (X(19.5), -309.0, zp + 0.3), 'M_WalkSlabs')
    rail(mb, rect_pts(X(-19.3), X(19.3), -346.8, -309.2)[0], zp + 0.3, h=1.0)
    walls(mb, X(-15.0), X(15.0), -343.0, -313.0, zp + 0.3, zt + 15.6)
    columns(mb, X(-18.6), X(18.6), -346.1, -309.9, zp + 0.3, zt + 15.6, 4.6)
    z2 = zt + 19.4
    mb.box((X(-15.0), -342.0, z2 - 0.4), (X(15.0), -314.0, z2), 'M_WalkSlabs')
    rail(mb, rect_pts(X(-14.8), X(14.8), -341.8, -314.2)[0], z2, h=1.1)
    walls(mb, X(-12.5), X(12.5), -340.0, -316.0, z2, zt + 24.4)
    columns(mb, X(-14.2), X(14.2), -341.2, -314.8, z2, zt + 24.4, 4.2, r=0.34)
    mb.box((X(-12.6), -340.1, zt + 26.3), (X(12.6), -315.9, zt + 28.7), 'M_RedDark')         # bracket band between the eaves
    for sx in (-1, 1):
        cx = X(sx * 35.0)
        walls(mb, cx - 3.25, cx + 3.25, -316.25, -309.75, zq, zt + 14.2, bay=3.0)
        columns(mb, cx - 3.5, cx + 3.5, -316.5, -309.5, zq, zt + 14.2, 3.5, r=0.3)
        mb.box((cx - 3.0, -316.0, zt + 15.5), (cx + 3.0, -310.0, zt + 16.7), 'M_RedDark')
        mb.box((cx - 0.25, -313.25, zt + 18.4), (cx + 0.25, -312.75, zt + 19.6), 'M_Gold')
    out.append(mb.finish('QT_ziyun_halls', coll, recalc=True))
    # roofs: the pent roof, the double-eaved hip-gable top; the que pavilions' double pyramid roofs
    out.append(skirt('QT_ziyun_roof1', coll, X(0.0), yc, 21.0, 20.0, zt + 15.8, 3.6, 6.0, lift=0.7))
    out.append(skirt('QT_ziyun_roof2', coll, X(0.0), yc, 19.5, 18.5, zt + 24.6, 2.2, 6.5, lift=0.8))
    out += hip_gable('QT_ziyun_roof3', coll, X(0.0), yc, 17.0, 13.5, zt + 28.9, zt + 33.8, 7.0, lift=1.0)
    for sx in (-1, 1):
        cx = X(sx * 35.0)
        out.append(skirt('QT_ziyun_queroof1%+d' % sx, coll, cx, -313.0, 6.5, 6.5, zt + 14.6, 1.3, 2.6, lift=0.45))
        out.append(roof('QT_ziyun_queroof2%+d' % sx, coll, cx, -313.0, 3.8, 3.8, zt + 16.4, zt + 18.9, kind='pyramid', lift=0.4))
    return out


def boats(coll):
    out = []
    mb = C.MB()
    # red boat-stage: barge with a two-storey red pavilion (A1/A2)
    x, y = RED_BOAT
    mb.box((x - 9, y - 4, ZW - 0.6), (x + 9, y + 4, ZW + 0.9), 'M_RedDark')
    hall(mb, x, y, 11, 5.5, ZW + 0.9, 3.2, body='M_RedLacquerB', cols='M_Red', plat=0.2)
    hall(mb, x, y, 7, 4.0, ZW + 5.3, 2.6, body='M_RedLacquerB', cols='M_Red', plat=0.2)
    # small paddle boats
    for (bx, by, r) in BOATS:
        M = Matrix.Translation((bx, by, ZW)) @ Matrix.Rotation(r, 4, 'Z')
        P = [M @ Vector(v) for v in ((-1.6, -0.8, -0.2), (1.6, -0.8, -0.2), (1.6, 0.8, -0.2), (-1.6, 0.8, -0.2),
                                     (-1.6, -0.8, 0.5), (1.6, -0.8, 0.5), (1.6, 0.8, 0.5), (-1.6, 0.8, 0.5))]
        for f4 in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
            mb.face([P[i] for i in f4], 'M_RedLacquerB')
        Q = [M @ Vector(v) for v in ((-0.8, -0.7, 0.5), (0.8, -0.7, 0.5), (0.8, 0.7, 0.5), (-0.8, 0.7, 0.5),
                                     (-0.8, -0.7, 1.4), (0.8, -0.7, 1.4), (0.8, 0.7, 1.4), (-0.8, 0.7, 1.4))]
        for f4 in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
            mb.face([Q[i] for i in f4], 'M_PostWhite')
    out.append(mb.finish('QT_boats', coll, recalc=True))
    out.append(roof('QT_boatstage_roof1', coll, x, y, 7.2, 3.6, ZW + 4.8, ZW + 5.6, kind='xieshan', lift=0.3))
    out.append(roof('QT_boatstage_roof2', coll, x, y, 4.8, 2.8, ZW + 8.3, ZW + 9.6, kind='xieshan', lift=0.4))
    # western dock: pier on posts, dragon boats with red cabins, two hall buildings
    mb = C.MB()
    d = DOCK
    mb.box((d['x1'], d['y'] - 2.5, ZW + 0.6), (d['x0'], d['y'] + 2.5, ZW + 1.0), 'M_WalkSlabs')
    rng = random.Random(_seed('dock'))
    for k in range(9):
        bx = d['x0'] - 5 - k * 7.2
        for side in (-1, 1):
            by = d['y'] + side * 6.5
            mb.box((bx - 1.8, by - 4.5, ZW - 0.3), (bx + 1.8, by + 4.5, ZW + 0.6), 'M_RedDark')
            mb.box((bx - 1.6, by - 3.0, ZW + 0.6), (bx + 1.6, by + 3.0, ZW + 2.2), 'M_RedLacquerB')
            mb.box((bx - 0.06, by - 0.06, ZW + 2.2), (bx + 0.06, by + 0.06, ZW + 6.5), 'M_Iron')
            mb.box((bx - 0.03, by - 1.4, ZW + 3.0), (bx + 0.03, by + 1.4, ZW + 6.0), 'M_LanternRed')
    for (hx, hy) in ((-150.0, -126.0), (-182.0, -122.0)):
        hall(mb, hx, hy, 22, 10, ZW + 1.0, 4.5, plat=0.8)
    out.append(mb.finish('QT_dock', coll, recalc=True))
    for (hx, hy) in ((-150.0, -126.0), (-182.0, -122.0)):
        out.append(roof('QT_dock_roof_%d' % int(-hx), coll, hx, hy, 13.0, 6.5, ZW + 6.3, ZW + 9.2, kind='xieshan', lift=0.4))
    # white boathouse (石舫-like) at the west end
    mb = C.MB()
    x, y = BOATHOUSE
    mb.box((x - 9, y - 3.5, ZW - 0.4), (x + 9, y + 3.5, ZW + 1.4), 'M_PostWhite')
    hall(mb, x, y, 12, 5.5, ZW + 1.4, 3.0, body='M_PostWhite', cols='M_PostWhite', plat=0.1)
    out.append(mb.finish('QT_boathouse', coll, recalc=True))
    out.append(roof('QT_boathouse_roof', coll, x, y, 7.5, 3.6, ZW + 4.6, ZW + 6.4, kind='xieshan', lift=0.3))
    # island pavilion (red, two storeys) at the island's east tip
    mb = C.MB()
    hall(mb, -70.0, -218.0, 7, 7, ZW + 1.6, 3.4, body='M_RedLacquerB', plat=0.6)
    hall(mb, -70.0, -218.0, 5, 5, ZW + 7.0, 2.6, body='M_RedLacquerB', plat=0.3)
    out.append(mb.finish('QT_island_pavilion', coll, recalc=True))
    out.append(roof('QT_island_pav_roof1', coll, -70.0, -218.0, 5.2, 5.2, ZW + 6.4, ZW + 7.2, kind='pyramid', lift=0.3))
    out.append(roof('QT_island_pav_roof2', coll, -70.0, -218.0, 3.8, 3.8, ZW + 10.4, ZW + 12.6, kind='pyramid', lift=0.3))
    return out


def far_halls(coll):
    """Tang-style hall groups on the far shores (A2 left: a long complex on the east shore; right: halls by the lake)"""
    out = []
    mb = C.MB()
    roofs = []
    for (hx, hy, w, d, h, rot) in hall_list():
        z0 = ground_z(hx, hy)
        hall(mb, hx, hy, w, d, z0, h, rot=rot, plat=1.0)
        roofs.append((hx, hy, w / 2 + 1.5, d / 2 + 1.5, z0 + 1.0 + h, z0 + 1.0 + h + d * 0.42, rot))
    out.append(mb.finish('QT_far_halls', coll, recalc=True))
    for k, (hx, hy, A, B, ze, zr, rot) in enumerate(roofs):
        out.append(roof('QT_far_hall_roof_%02d' % k, coll, hx, hy, A, B, ze, zr, rot=rot, kind='xieshan', lift=0.3))
    return out


def hip_house(mb, cx, cy, w, d, z0, h, rot, rh, m_wall, m_roof, over=0.7):
    """a house: wall box and a hipped roof with eaves (coarse; seen from 400 m and more)"""
    c, s_ = math.cos(rot), math.sin(rot)
    T = lambda x, y, z: Vector((cx + x * c - y * s_, cy + x * s_ + y * c, z))
    a, b = w / 2, d / 2
    B = [T(-a, -b, z0), T(a, -b, z0), T(a, b, z0), T(-a, b, z0)]
    U = [T(-a, -b, z0 + h), T(a, -b, z0 + h), T(a, b, z0 + h), T(-a, b, z0 + h)]
    for i in range(4):
        j = (i + 1) % 4
        mb.face([B[i], B[j], U[j], U[i]], m_wall)
    A2, B2 = a + over, b + over
    ze = z0 + h - 0.15
    E = [T(-A2, -B2, ze), T(A2, -B2, ze), T(A2, B2, ze), T(-A2, B2, ze)]
    rx = max(0.0, A2 - B2)
    R = [T(-rx, 0, ze + rh), T(rx, 0, ze + rh)]
    mb.face([E[0], E[1], R[1], R[0]], m_roof)
    mb.face([E[2], E[3], R[0], R[1]], m_roof)
    mb.face([E[1], E[2], R[1]], m_roof)
    mb.face([E[3], E[0], R[0]], m_roof)
    mb.face(list(reversed(E)), m_roof)


def villas(coll):
    """the grey-roofed low-rise housing west of 紫云楼 (A1/A2 right): streets of two- and three-storey houses"""
    rng = random.Random(_seed('villas'))
    mb = C.MB()
    n = 0
    y = -345.0
    while y > -1500:
        x = -110.0
        dy = rng.uniform(16, 20)
        while x > -1150:
            dx = rng.uniform(16, 21)
            if rng.random() < 0.12:                      # gardens and small squares
                x -= dx
                continue
            hx, hy = x - dx / 2 + rng.uniform(-2, 2), y - dy / 2 + rng.uniform(-2, 2)
            if (_inside(VILLA_POLY, hx, hy) and not in_ziyun(hx, hy, 15) and not _inside(LAKE, hx, hy)
                    and _seg_dist(hx, hy, LAKE) > 25 and not any(math.hypot(hx - a, hy - b) < 40 + 9 * k for a, b, r, k in HALL_SITES)):
                w = rng.uniform(9, 14); d = rng.uniform(8, 11)
                h = rng.choice((6.2, 6.6, 7.0, 9.2, 9.6))
                rot = 0.02 * rng.uniform(-1, 1)
                hip_house(mb, hx, hy, w, d, ground_z(hx, hy) - 0.1, h, rot, rng.uniform(2.8, 3.8),
                          rng.choice(('M_CityA', 'M_CityA', 'M_CityC', 'M_Plaster')), 'M_TileBrown', over=0.9)
                n += 1
            x -= dx
        y -= dy + (9.0 if rng.random() < 0.25 else 0.0)  # every few rows a street
    o = mb.finish('QT_villas', coll, recalc=False)
    return o, n


def offices(coll):
    """long white buildings south-east of the lake (A2 left, behind the woods)"""
    mb = C.MB()
    for (cx, cy, w, d, h) in OFFICES:
        z0 = ground_z(cx, cy)
        mb.box((cx - w / 2, cy - d / 2, z0 - 0.5), (cx + w / 2, cy + d / 2, z0 + h), 'M_CityC')
        mb.box((cx - w / 2 - 1.5, cy - d / 2 - 1.5, z0 + h), (cx + w / 2 + 1.5, cy + d / 2 + 1.5, z0 + h + 1.2), 'M_TileFar')
    return mb.finish('QT_offices', coll, recalc=True)


def city(coll):
    """Xi'an south of the park: mid-rise blocks from about 1 km out, then high-rise residential compounds (slab and
    point towers, mostly 60-110 m, a few landmarks to 160 m) from 1.3 to 3.8 km, on ground rising to the south."""
    rng = random.Random(_seed('city'))
    mb = C.MB()
    n = 0
    mats_ = ('M_CityA', 'M_CityB', 'M_CityC')
    # mid-rise belt
    for _ in range(420):
        x = rng.uniform(-2600, 2600); y = rng.uniform(-1500, -950)
        if _inside(VILLA_POLY, x, y) or any(abs(x - ox) < w / 2 + 25 and abs(y - oy) < d / 2 + 25 for ox, oy, w, d, h in OFFICES):
            continue
        if abs(x) < 900 and y > -1150:
            continue
        w = rng.uniform(30, 80); d = rng.uniform(13, 18); h = rng.uniform(15, 30)
        z0 = ground_z(x, y)
        mb.box((x - w / 2, y - d / 2, z0 - 1), (x + w / 2, y + d / 2, z0 + h), rng.choice(mats_))
        n += 1
    # high-rise compounds
    for _ in range(130):
        cx = rng.uniform(-3400, 3400); cy = rng.uniform(-3900, -1250)
        if cy > -1600 and abs(cx) < 500:
            continue
        slab = rng.random() < 0.55
        rows, cols = rng.randint(2, 3), rng.randint(2, 5)
        hbase = rng.uniform(40, 75) * (1.3 if rng.random() < 0.08 else 1.0)
        m = rng.choice(mats_)
        for i in range(cols):
            for j in range(rows):
                if rng.random() < 0.12:
                    continue
                x = cx + (i - cols / 2) * (62 if slab else 48) + rng.uniform(-4, 4)
                y = cy + (j - rows / 2) * 70 + rng.uniform(-6, 6)
                w, d = (rng.uniform(30, 40), rng.uniform(12, 15)) if slab else (rng.uniform(16, 23), rng.uniform(16, 23))
                h = hbase * rng.uniform(0.85, 1.12)
                z0 = ground_z(x, y)
                mb.box((x - w / 2, y - d / 2, z0 - 1), (x + w / 2, y + d / 2, z0 + h), m)
                n += 1
    o = mb.finish('QT_city', coll, recalc=True)
    return o, n


def mats():
    import xy_mats as XM
    import qt_mats as QM
    QM.lacquer('M_RedLacquerB', (0.20, 0.025, 0.018), rough=0.55, coat=0.05)
    m = XM.simple('M_TileFar', (0.050, 0.053, 0.057), rough=0.65, spec=0.3)
    XM.simple('M_TileBrown', (0.068, 0.058, 0.050), rough=0.7, spec=0.25)
    for name, col in (('M_CityA', (0.48, 0.45, 0.40)), ('M_CityB', (0.42, 0.44, 0.46)), ('M_CityC', (0.60, 0.59, 0.56))):
        mm, nt, bs, out = XM._new(name)
        L = nt.links
        # facade: window rows from object coordinates (horizontal bands) over a wall colour
        pos = XM._world_pos(nt)
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); L.new(pos, sep.inputs[0])
        wave = nt.nodes.new('ShaderNodeTexWave'); wave.wave_type = 'BANDS'; wave.bands_direction = 'Z'
        wave.inputs['Scale'].default_value = 0.33; L.new(pos, wave.inputs['Vector'])
        c = XM._ramp(nt, wave.outputs['Fac'], [(0.0, tuple(v * 0.45 for v in col)), (0.35, col), (1.0, col)], (-300, 0))
        L.new(c, bs.inputs['Base Color'])
        bs.inputs['Roughness'].default_value = 0.6
