# Xingyuan - garden structures outside the complex (positions from the calibrated aerial):
# three stone frames over the pink path, two lamp posts at the gate plaza, the corten wheel-and-cage sculpture,
# raised planters and granite benches on the terrace, the pond railing, stepping stones, fountains.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import xy_core as C, xy_geo2d as G, xy_env_data as ED, xy_terrain as TR

ZP = ED.ZP
WL = ED.WL
Z = Vector((0, 0, 1))

def _axes(ang_deg):
    a = math.radians(ang_deg)
    d = Vector((math.cos(a), math.sin(a), 0))
    n = Vector((-math.sin(a), math.cos(a), 0))
    return d, n

def ring(mb, c, R, z, r, m, nu=72, nv=8):
    """Torus ring (horizontal), centre c (x, y), radius R at height z, tube radius r."""
    rows = []
    for i in range(nu + 1):
        a = 2 * math.pi * i / nu
        ca, sa = math.cos(a), math.sin(a)
        row = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            rr = R + r * math.cos(b)
            row.append(Vector((c[0] + rr * ca, c[1] + rr * sa, z + r * math.sin(b))))
        rows.append(row)
    mb.quad_strip(rows, m, smooth=True, closed_u=True)

def tube_path(mb, pts, r, m, segs=8):
    import xy_plants as P
    P.tube_r(mb, pts, [r] * len(pts), m, segs=segs)

# ------------------------------------------------------------------ stone frames (石坊)
def frames(coll):
    mb = C.MB()
    span, H = 4.0, 4.3
    for (c, ang) in ED.FRAMES:
        d, n = _axes(ang)
        base = Vector((c[0], c[1], 0))
        for s in (-1, 1):
            p = base + d * s * span / 2
            zg = TR.height(p.x, p.y)
            zg = min(zg, ZP)
            mb.obox(Vector((p.x, p.y, zg + 0.08)), (d, n, Z), (0.27, 0.27, 0.26), 'M_GraniteOut')          # plinth
            z0, z1 = zg - 0.3, ZP + H - 0.15
            mb.obox(Vector((p.x, p.y, (z0 + z1) / 2)), (d, n, Z), (0.16, 0.16, (z1 - z0) / 2), 'M_GraniteOut')
        # lintel with overhangs, slightly thicker in the middle; small cap blocks over the posts
        mb.obox(Vector((base.x, base.y, ZP + H - 0.12)), (d, n, Z), (span / 2 + 0.8, 0.16, 0.18), 'M_GraniteOut')
        for s in (-1, 1):
            p = base + d * s * span / 2
            mb.obox(Vector((p.x, p.y, ZP + H + 0.1)), (d, n, Z), (0.2, 0.19, 0.04), 'M_GraniteOut')
    return mb.finish('环境_石坊', coll, recalc=True)

# ------------------------------------------------------------------ lamp posts
def lamps(coll):
    mb = C.MB()
    for (x, y) in ED.LAMPS:
        z0 = ZP
        top = z0 + 4.48
        mb.cyl((x, y, z0 - 0.02), (x, y, z0 + 0.06), 0.16, 16, 'M_Iron')                   # base plate
        mb.cyl((x, y, z0 + 0.06), (x, y, z0 + 0.55), 0.085, 16, 'M_Iron', r1=0.07)          # base sleeve
        mb.cyl((x, y, z0 + 0.55), (x, y, top - 0.62), 0.055, 12, 'M_Iron', r1=0.042)        # pole
        mb.cyl((x, y, top - 0.62), (x, y, top - 0.56), 0.07, 12, 'M_Iron')                  # collar
        # square lantern: frosted panels in a black frame, pyramid cap with a finial
        h0, h1 = top - 0.56, top - 0.08
        w = 0.17
        mb.box((x - 0.21, y - 0.21, h0), (x + 0.21, y + 0.21, h0 + 0.04), 'M_Iron')
        mb.box((x - w, y - w, h0 + 0.04), (x + w, y + w, h1), 'M_LampGlass')
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((x + sx * w - 0.02, y + sy * w - 0.02, h0 + 0.04), (x + sx * w + 0.02, y + sy * w + 0.02, h1), 'M_Iron')
        mb.box((x - 0.22, y - 0.22, h1), (x + 0.22, y + 0.22, h1 + 0.03), 'M_Iron')
        apex = Vector((x, y, top + 0.1))
        q = [Vector((x - 0.2, y - 0.2, h1 + 0.03)), Vector((x + 0.2, y - 0.2, h1 + 0.03)), Vector((x + 0.2, y + 0.2, h1 + 0.03)),
             Vector((x - 0.2, y + 0.2, h1 + 0.03))]
        for i in range(4):
            mb.face([q[i], q[(i + 1) % 4], apex], 'M_Iron')
        mb.cyl((x, y, top + 0.08), (x, y, top + 0.2), 0.015, 8, 'M_Iron')
    return mb.finish('环境_灯柱', coll, recalc=True)

# ------------------------------------------------------------------ corten sculpture
def sculpture(coll):
    (cx, cy), H, R = ED.SCULPTURE
    mb = C.MB()
    z0, zt = ZP, ZP + H
    n = 30
    for k in range(n):
        a = 2 * math.pi * k / n
        p = (cx + R * math.cos(a), cy + R * math.sin(a))
        mb.cyl((p[0], p[1], z0 + 0.02), (p[0], p[1], zt - 0.03), 0.014, 6, 'M_Corten')
    ring(mb, (cx, cy), R, z0 + 0.05, 0.03, 'M_Corten')
    ring(mb, (cx, cy), R, z0 + 1.55, 0.022, 'M_Corten')
    ring(mb, (cx, cy), R, zt, 0.055, 'M_Corten', nv=10)                  # wheel rim
    ring(mb, (cx, cy), R * 0.55, zt, 0.025, 'M_Corten')
    mb.cyl((cx, cy, zt - 0.1), (cx, cy, zt + 0.1), 0.17, 16, 'M_Corten')    # hub
    for k in range(18):
        a = 2 * math.pi * k / 18 + 0.1
        mb.cyl((cx + 0.15 * math.cos(a), cy + 0.15 * math.sin(a), zt), (cx + (R - 0.04) * math.cos(a), cy + (R - 0.04) * math.sin(a), zt),
               0.022, 6, 'M_Corten')
    mb.cyl((cx, cy, z0), (cx, cy, zt - 0.1), 0.05, 10, 'M_Corten')        # central mast
    return mb.finish('环境_钢雕塑', coll, recalc=False)

# ------------------------------------------------------------------ planters, benches
PLANTER_H = 0.42
SOIL_Z = ZP + 0.34

def planters(coll):
    mb = C.MB()
    out = []
    items = [(c, ang, size, PLANTER_H) for (c, ang, size) in ED.PLANTERS]
    (lc, lsize) = ED.LAWN_PLANTER
    items.append((lc, 0.0, lsize, 0.30))
    for (c, ang, (w, dpt), h) in items:
        d, n = _axes(ang)
        p = Vector((c[0], c[1], 0))
        t = 0.1
        zc = ZP + h / 2 - 0.02
        hh = h / 2 + 0.02
        mb.obox(Vector((p.x, p.y, zc)) + n * (dpt / 2 - t / 2), (d, n, Z), (w / 2, t / 2, hh), 'M_DarkGranite')
        mb.obox(Vector((p.x, p.y, zc)) - n * (dpt / 2 - t / 2), (d, n, Z), (w / 2, t / 2, hh), 'M_DarkGranite')
        mb.obox(Vector((p.x, p.y, zc)) + d * (w / 2 - t / 2), (d, n, Z), (t / 2 - 0.001, dpt / 2 - t - 0.001, hh - 0.001), 'M_DarkGranite')
        mb.obox(Vector((p.x, p.y, zc)) - d * (w / 2 - t / 2), (d, n, Z), (t / 2 - 0.001, dpt / 2 - t - 0.001, hh - 0.001), 'M_DarkGranite')
        # soil surface inside
        zs = ZP + h - 0.08
        q = [p + d * s1 * (w / 2 - t) + n * s2 * (dpt / 2 - t) for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        mb.face([Vector((v.x, v.y, zs)) for v in q], 'M_Soil')
        out.append((c, ang, (w, dpt), zs))
    mb.finish('环境_花池', coll, recalc=False)
    return out

def planters_info():
    out = []
    for (c, ang, size) in ED.PLANTERS:
        out.append((c, ang, size, ZP + PLANTER_H - 0.08))
    (lc, lsize) = ED.LAWN_PLANTER
    out.append((lc, 0.0, lsize, ZP + 0.30 - 0.08))
    return out

def benches(coll):
    mb = C.MB()
    for ((x, y), ang) in ED.BENCHES:
        d, n = _axes(ang)
        zg = TR.height(x, y)
        z0 = ZP if abs(zg - ZP) < 0.1 or zg < ZP else zg
        z0 = ZP if _on_paving(x, y) else max(z0, zg)
        p = Vector((x, y, 0))
        for s in (-1, 1):
            q = p + d * s * 0.6
            mb.obox(Vector((q.x, q.y, z0 + 0.17)), (d, n, Z), (0.08, 0.2, 0.19), 'M_GraniteOut')
        mb.obox(Vector((p.x, p.y, z0 + 0.405)), (d, n, Z), (0.82, 0.23, 0.045), 'M_GraniteOut')
    return mb.finish('环境_石凳', coll, recalc=True)

_MASK = None
def set_mask(M):
    global _MASK
    _MASK = M

def _on_paving(x, y):
    return _MASK is not None and _MASK.test(x, y)

# ------------------------------------------------------------------ railing along the terrace edge
def railing(coll, spacing=2.4):
    P = G.Path(ED.RAIL)
    L = P.length
    n = max(2, int(round(L / spacing)))
    mb = C.MB()
    off = -0.18                  # the terrace is on the right of the RAIL direction
    zk = ZP + 0.03
    posts = []
    for k in range(n + 1):
        u = L * k / n
        x, y = P.at(u, off)
        posts.append((x, y))
        mb.cyl((x, y, zk - 0.01), (x, y, ZP + 0.88), 0.085, 14, 'M_Granite', cap=False)
        # rounded cap
        bm_cap(mb, (x, y, ZP + 0.88), 0.085)
    for zr in (ZP + 0.80, ZP + 0.42):
        pts = [Vector((p[0], p[1], zr)) for p in (P.at(L * k / (n * 6), off) for k in range(n * 6 + 1))]
        tube_path(mb, pts, 0.022, 'M_Steel', segs=10)
    return mb.finish('环境_栏杆', coll, recalc=False)

def bm_cap(mb, c, r, m='M_Granite', nu=14, nv=5):
    rows = []
    for j in range(nv + 1):
        b = (math.pi / 2) * j / nv
        rr = r * math.cos(b)
        z = c[2] + r * 0.8 * math.sin(b)
        rows.append([Vector((c[0] + rr * math.cos(2 * math.pi * i / nu), c[1] + rr * math.sin(2 * math.pi * i / nu), z)) for i in range(nu)])
    mb.quad_strip(rows, m, smooth=True, closed_u=True)

# ------------------------------------------------------------------ stepping stones, fountains
def stepping_stones(coll):
    mb = C.MB()
    r = random.Random(4)
    for (x, y) in ED.STONES:
        rad = r.uniform(0.30, 0.36)
        top = WL + r.uniform(0.10, 0.15)
        bot = TR.height(x, y) - 0.2
        mb.cyl((x, y, bot), (x, y, top - 0.03), rad, 20, 'M_StepStone', r1=rad * 0.98, cap=False)
        # softened top edge
        mb.cyl((x, y, top - 0.03), (x, y, top), rad * 0.98, 20, 'M_StepStone', r1=rad * 0.9, cap=False)
        mb.face([Vector((x + rad * 0.9 * math.cos(2 * math.pi * i / 20), y + rad * 0.9 * math.sin(2 * math.pi * i / 20), top))
                 for i in range(20)], 'M_StepStone')
    return mb.finish('环境_汀步', coll, recalc=False)

def _droplet(mb, p, r, m='M_Foam', stretch=1.0, axis=None):
    """A small faceted droplet (octahedron), optionally stretched along `axis` (a streak)."""
    ax = axis.normalized() if axis is not None else Vector((0, 0, 1))
    a1 = ax.orthogonal().normalized(); a2 = ax.cross(a1).normalized()
    q = [p + a1 * r, p + a2 * r, p - a1 * r, p - a2 * r]
    top, bot = p + ax * r * stretch, p - ax * r * stretch
    for k in range(4):
        mb.face([q[k], q[(k + 1) % 4], top], m)
        mb.face([q[(k + 1) % 4], q[k], bot], m)

def _spray(mb, rng, c, z0, n, v0=(2.2, 3.4), spread=0.55):
    """Spray along ballistic arcs from a jet at c: droplets and short streaks (falling water)."""
    g = 9.81
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        el = math.radians(rng.uniform(62, 88))
        v = rng.uniform(*v0)
        vh, vz = v * math.cos(el) * spread * 2, v * math.sin(el)
        t = rng.uniform(0.05, 2 * vz / g)
        pos = Vector((c[0] + math.cos(a) * vh * t, c[1] + math.sin(a) * vh * t, z0 + vz * t - 0.5 * g * t * t))
        if pos.z < z0:
            continue
        vel = Vector((math.cos(a) * vh, math.sin(a) * vh, vz - g * t))
        r = rng.uniform(0.008, 0.026)
        _droplet(mb, pos, r, stretch=rng.uniform(1.0, 3.5), axis=vel)

def _foam_blob(bm_list, c, rad, h, seed, sub=3, amp=0.28):
    import mathutils.noise as MN
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    off = Vector((seed * 3.1, seed * 1.7, 0.4))
    for v in bm.verts:
        p = v.co.copy()
        nz = MN.noise(p * 2.5 + off) + 0.6 * MN.noise(p * 6.0 + off) + 0.3 * MN.noise(p * 13.0 + off)
        zz = max(p.z, -0.1)
        rr = 1.0 + amp * nz
        v.co = Vector((c[0] + p.x * rad * rr, c[1] + p.y * rad * rr, WL - 0.04 + zz * h * (1 + 1.6 * amp * nz)))
    bm_list.append(bm)

def _join(name, coll, bms, mat):
    me = bpy.data.meshes.new(name)
    big = bmesh.new()
    for bm in bms:
        tmp = bpy.data.meshes.new('_tmp')
        bm.to_mesh(tmp); bm.free()
        big.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    big.to_mesh(me); big.free()
    me.materials.append(C.mat(mat))
    for pl in me.polygons:
        pl.use_smooth = True
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o

def _foam_flecks(mb, rng, c, r0, r1, n):
    """Foam and bubbles floating on the surface: small flat irregular patches, thinning outward."""
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        d = r0 + (r1 - r0) * (rng.random() ** 1.6)
        p = Vector((c[0] + d * math.cos(a), c[1] + d * math.sin(a), WL + 0.004 + rng.uniform(0, 0.006)))
        rr = rng.uniform(0.010, 0.040) * (1.25 - 0.6 * (d - r0) / max(r1 - r0, 1e-3))
        k = rng.randint(5, 7)
        pts = [p + Vector((math.cos(2 * math.pi * j / k) * rr * rng.uniform(0.6, 1.2),
                           math.sin(2 * math.pi * j / k) * rr * rng.uniform(0.6, 1.2), 0)) for j in range(k)]
        mb.face(pts, 'M_FoamFleck')

def fountains(coll):
    """Main pond: an aerated bubbler - a glassy water dome, white churn at its foot, spray falling back
    (the foam on the pond surface is painted by M_PondWater). NW pond: a ring of twelve small jets."""
    objs = []
    rng = random.Random(8)
    (x, y, r) = ED.FOUNTAINS[0]
    bms = []
    _foam_blob(bms, (x, y), 0.40, 0.48, 1, sub=4, amp=0.12)
    objs.append(_join('环境_喷泉_涌泉', coll, bms, 'M_Foam'))
    bms = []
    for k in range(9):
        a = 2 * math.pi * k / 9 + rng.uniform(-0.25, 0.25)
        d = rng.uniform(0.36, 0.55)
        _foam_blob(bms, (x + d * math.cos(a), y + d * math.sin(a)), rng.uniform(0.16, 0.26), rng.uniform(0.10, 0.2), 10 + k, sub=3)
    objs.append(_join('环境_喷泉_翻花', coll, bms, 'M_Foam'))
    mb = C.MB()
    for i in range(260):
        a = rng.uniform(0, 2 * math.pi); d = 0.25 + 0.75 * rng.random() ** 1.5
        _droplet(mb, Vector((x + d * math.cos(a), y + d * math.sin(a), WL + rng.uniform(0.02, 0.5) * (1.1 - d))), rng.uniform(0.006, 0.016))
    objs.append(mb.finish('环境_喷泉_水花', coll, recalc=False))
    (x, y, r) = ED.FOUNTAINS[1]
    mb = C.MB()
    for k in range(12):
        a = 2 * math.pi * k / 12
        p = (x + r * math.cos(a), y + r * math.sin(a))
        h = rng.uniform(0.55, 0.7)
        mb.cyl((p[0], p[1], WL - 0.02), (p[0], p[1], WL + h), 0.03, 8, 'M_FountainWater', r1=0.014)
        for i in range(14):
            _droplet(mb, Vector((p[0] + rng.gauss(0, 0.06), p[1] + rng.gauss(0, 0.06), WL + h * rng.uniform(0.6, 1.08))), rng.uniform(0.006, 0.014))
    objs.append(mb.finish('环境_喷泉_环形', coll, recalc=False))
    return objs

def build(coll, mask=None):
    for nm in [o.name for o in coll.objects]:
        o = bpy.data.objects[nm]
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and getattr(me, 'users', 1) == 0:
            bpy.data.meshes.remove(me)
    set_mask(mask)
    frames(coll)
    lamps(coll)
    sculpture(coll)
    pl = planters(coll)
    benches(coll)
    railing(coll)
    stepping_stones(coll)
    fountains(coll)
    return pl
