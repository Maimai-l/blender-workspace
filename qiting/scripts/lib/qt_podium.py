# Qiting - the round podium (台基): top paving, coping, carved drum, plinth, three notched terraces, the
# balustrade on the coping, and the north stair (three flights between solid ashlar side walls, small doors near the
# drum, balustrades on both parapets).
import bpy, bmesh, math, random, zlib
from mathutils import Vector, Matrix
import xy_core as C, xy_parts as PT
import qt_dims as D


def _seed(name):
    return zlib.crc32(name.encode())


class SMB(C.MB):
    """MB that records face ranges per slab/block so each one can get its own tone ('slab' face attribute)."""
    def __init__(self, seed=1):
        super().__init__()
        self.ranges = []
        self.rng = random.Random(seed)
        self._f0 = None

    def begin(self):
        self._f0 = len(self.bm.faces)

    def end(self):
        self.ranges.append((self._f0, len(self.bm.faces), self.rng.random()))

    def finish_slabs(self, name, coll, recalc=True):
        o = self.finish(name, coll, recalc=recalc)
        me = o.data
        vals = [0.0] * len(me.polygons)
        for (a, b, v) in self.ranges:
            for i in range(a, min(b, len(vals))):
                vals[i] = v
        at = me.attributes.new('slab', 'FLOAT', 'FACE')
        at.data.foreach_set('value', vals)
        return o


def slab(mb, poly, z0, z1, m, bevel=0.005, m_side=None):
    """closed prism of a convex-ish polygon [(x, y)] (CCW), top edges chamfered by `bevel`."""
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cy = sum(p[1] for p in poly) / n
    ins = []
    for (x, y) in poly:
        dx, dy = cx - x, cy - y
        L = math.hypot(dx, dy) or 1.0
        k = min(bevel / L, 0.4)
        ins.append((x + dx * k, y + dy * k))
    B = [Vector((x, y, z0)) for x, y in poly]
    M = [Vector((x, y, z1 - bevel)) for x, y in poly]
    T = [Vector((x, y, z1)) for x, y in ins]
    ms = m_side or m
    mb.face(list(reversed(B)), ms)
    mb.face(T, m)
    for i in range(n):
        j = (i + 1) % n
        mb.face([B[i], B[j], M[j], M[i]], ms)
        mb.face([M[i], M[j], T[j], T[i]], m)


def sector(r0, r1, a0, a1, gap=0.004, step=0.25):
    """polygon of an annular sector with half-gaps trimmed off all sides (CCW)."""
    g = gap / 2
    ra, rb = r0 + g, r1 - g
    da0, da1 = a0 + g / max(ra, 0.05), a1 - g / max(ra, 0.05)
    db0, db1 = a0 + g / rb, a1 - g / rb
    n = max(1, int(abs(a1 - a0) * r1 / step))
    out = []
    for i in range(n + 1):
        a = db0 + (db1 - db0) * i / n
        out.append((rb * math.cos(a), rb * math.sin(a)))
    for i in range(n + 1):
        a = da1 - (da1 - da0) * i / n
        out.append((ra * math.cos(a), ra * math.sin(a)))
    return out


def ring_slabs(mb, r0, r1, z0, z1, m, n_seg, a_off=0.0, gap=0.005, skip=None, bevel=0.005):
    for k in range(n_seg):
        a0 = a_off + 2 * math.pi * k / n_seg
        a1 = a_off + 2 * math.pi * (k + 1) / n_seg
        if skip and skip(0.5 * (a0 + a1), r0, r1):
            continue
        mb.begin()
        slab(mb, sector(r0, r1, a0, a1, gap), z0, z1, m, bevel=bevel)
        mb.end()


def _in_stair(a, r0=0.0, r1=99.0, half=None):
    """True if the arc centre at angle a (radians) lies under the north stair footprint."""
    hw = (D.STAIR_W_CLEAR / 2 + D.STAIR_PARAPET) if half is None else half
    x = abs(((r0 + r1) / 2) * math.cos(a))
    return math.sin(a) > 0 and x < hw + 0.05


# ------------------------------------------------------------------ podium top and coping
R_FLOOR = 4.50          # floor paving out to the coping's inner edge


def floor(c):
    mb = SMB(_seed('floor'))
    # centre disc + rings of slabs
    mb.begin(); slab(mb, [(0.45 * math.cos(2 * math.pi * k / 24), 0.45 * math.sin(2 * math.pi * k / 24)) for k in range(24)],
                     -0.10, 0.0, 'M_GraniteFloor'); mb.end()
    r = 0.45
    k = 0
    while r < R_FLOOR - 0.01:
        r1 = min(R_FLOOR, r + 0.60)
        n = max(8, int(round(2 * math.pi * (r + r1) / 2 / 0.90)))
        ring_slabs(mb, r, r1, -0.10, 0.0, 'M_GraniteFloor', n, a_off=(k % 2) * math.pi / n)
        r = r1
        k += 1
    o = mb.finish_slabs('QT_floor', c)
    # bedding under the joints
    mb = C.MB()
    mb.lathe([(0.0, -0.105), (R_FLOOR, -0.105)], 64, 'M_Dark', cap_top=False, cap_bot=False)
    o2 = mb.finish('QT_floor_bed', c, recalc=False)
    return [o, o2]


def coping(c):
    """marble coping ring under the balustrade, 32 blocks, rounded outer edge; opening for the stair."""
    mb = SMB(_seed('coping'))
    r0, r1 = R_FLOOR, D.R_COPING
    z0, z1 = -D.COPING_T, 0.0
    n = 32
    for k in range(n):
        a0 = 2 * math.pi * k / n + math.pi / n
        a1 = a0 + 2 * math.pi / n
        mb.begin()
        g = 0.003
        steps = 6
        prof = [(r0, z0), (r1 - 0.06, z0), (r1 - 0.02, z0 + 0.03), (r1, z0 + 0.08), (r1, z1 - 0.05), (r1 - 0.015, z1 - 0.012), (r1 - 0.05, z1), (r0, z1)]
        rows = []
        for i in range(steps + 1):
            a = a0 + g / r1 + (a1 - a0 - 2 * g / r1) * i / steps
            rows.append([(rr * math.cos(a), rr * math.sin(a), zz) for (rr, zz) in prof])
        mb.quad_strip(rows, 'M_Marble', closed_u=True)
        mb.face(list(reversed(rows[0])), 'M_Marble')
        mb.face(rows[-1], 'M_Marble')
        mb.end()
    return mb.finish_slabs('QT_coping', c)


# ------------------------------------------------------------------ carved drum
REL_Z0 = -(D.COPING_T + D.RELIEF_H)          # -2.51
REL_Z1 = -D.COPING_T                          # -0.26
SOUTH = 1.5 * math.pi


def _relief_features():
    """placed features of the carved band: (kind, angle, z centre, width, height). Located with the calibrated
    cameras: south panel and its flanking cartouche / medallion (W04), the two small windows (340d, W01, 419; W02),
    the carved gate building, the round medallion on the upper edge and the lettered cartouche (W01)."""
    return [
        ('panel', SOUTH, -1.32, 1.60, 0.95),                       # dark inscription panel on the south axis (W04)
        ('window', math.radians(225), -1.05, 0.52, 0.58),          # small openings either side of the south panel:
        ('window', math.radians(315), -1.05, 0.52, 0.58),          #   SW (340d, W01, 419) and SE (W02)
        ('cartouche', math.radians(246), -1.10, 0.42, 0.95),       # vertical cartouche left of the panel (W04)
        ('medallion', math.radians(293), -1.75, 0.30, 0.30),       # round medallion right of the panel (W04)
        ('gate', math.radians(161), -0.78, 1.55, 0.86),            # carved gate building (W01, 153-170 deg)
        ('medallion', math.radians(174), -0.50, 0.30, 0.30),       # round medallion at the top of the field (W01)
        ('cartouche', math.radians(199), -0.85, 0.32, 0.78),       # lettered vertical cartouche (W01)
    ]


def _figures():
    """relief figures round the band: (angle, foot z, height, robe width, lean, phase, arms). The photos show
    groups of standing and dancing figures in long robes with flying ribbons, 1.3-1.9 m tall (W01, W04, W07, 419);
    poses and faces cannot be read, so they are robed masses with heads, arms and ribbons, not invented scenes."""
    rng = random.Random(_seed('figures'))
    R = D.R_DRUM
    keep_out = [(SOUTH, 1.10), (math.pi / 2, 1.95), (math.radians(161), 0.95), (math.radians(199), 0.30),
                (math.radians(246), 0.32), (math.radians(225), 0.45), (math.radians(315), 0.45)]
    out = []
    a = 0.0
    while a < 2 * math.pi:
        a += rng.uniform(0.55, 0.95) / R
        if any(abs(((a - c + math.pi) % (2 * math.pi)) - math.pi) * R < w for (c, w) in keep_out):
            continue
        H = rng.uniform(1.30, 1.80)
        out.append((a, REL_Z0 + 0.18 + rng.uniform(0.0, 0.12), H, rng.uniform(0.22, 0.34), rng.uniform(-0.35, 0.35),
                    rng.uniform(0, 2 * math.pi), rng.random() < 0.6))
    for side in (-1, 1):                     # the two large figures flanking the south panel (W04)
        out.append((SOUTH + side * 1.45 / R, REL_Z0 + 0.16, 1.95, 0.34, 0.0, 0.0, False))
    return out


def _plateau(q, a, b):
    """1 for q <= a, 0 for q >= b, smooth but steep in between: carved forms with crisp edges."""
    if q <= a:
        return 1.0
    if q >= b:
        return 0.0
    t = (q - a) / (b - a)
    return 1.0 - t * t * (3 - 2 * t)


def _fig_h(dx, z, f):
    a, z0, H, w, lean, ph, arms = f
    t = (z - z0) / H
    if t < -0.03 or t > 1.06:
        return 0.0
    h = 0.0
    # body axis sways in an S-curve (dancing figures), hem flares and trails to one side
    sway = w * (lean * t + 0.55 * math.sin(math.pi * 1.3 * t + ph) * (1.0 - t) * 0.6)
    xc = sway
    if t < 0.84:
        width = w * (0.42 + 1.35 * max(0.0, 0.48 - t) ** 1.05 + 0.10 * math.sin(t * 9.0 + ph))
        trail = 0.35 * w * max(0.0, 0.35 - t) * math.copysign(1.0, math.sin(ph))     # hem swept to one side
        q = (dx - xc - trail) / width
        if abs(q) < 1.2:
            body = _plateau(abs(q), 0.78, 1.05)
            fold = 0.22 * math.sin((dx - xc) * 34.0 + t * 11.0 + ph) * (1 - t) + 0.07 * math.sin((dx - xc) * 85.0 + ph)
            s_edge = min(1.0, max(0.0, t / 0.04))
            h = 0.11 * body * (1.0 + fold) * s_edge
    # head
    rh = 0.08 * H / 1.6
    hx = w * (lean * 0.93 + 0.55 * math.sin(math.pi * 1.3 * 0.93 + ph) * 0.07 * 0.6)
    hz = z0 + H * 0.93
    d2 = (dx - hx) ** 2 + ((z - hz) / 1.15) ** 2
    if d2 < (1.3 * rh) ** 2:
        h = max(h, 0.12 * _plateau(math.sqrt(d2) / rh, 0.75, 1.1) * (0.85 + 0.15 * (1 - d2 / (rh * rh * 1.7))))
    # arms with long sleeves: raised in a dance, or folded in front
    for sgn in (-1, 1):
        if arms:
            pts = [(hx + sgn * 0.08, z0 + H * 0.80), (hx + sgn * (0.28 + 0.06 * math.sin(ph)), z0 + H * (0.92 + 0.05 * sgn * math.cos(ph))),
                   (hx + sgn * (0.45 + 0.10 * math.cos(ph)), z0 + H * (0.80 + 0.12 * math.sin(ph + sgn)))]
        else:
            pts = [(hx + sgn * 0.10, z0 + H * 0.78), (hx + sgn * 0.06, z0 + H * 0.60), (hx + sgn * 0.16, z0 + H * 0.48)]
        for (ax0, az0), (ax1, az1) in zip(pts, pts[1:]):
            vx, vz = ax1 - ax0, az1 - az0
            L2 = vx * vx + vz * vz
            tt = max(0.0, min(1.0, ((dx - ax0) * vx + (z - az0) * vz) / L2))
            dd = math.hypot(dx - ax0 - vx * tt, z - az0 - vz * tt)
            rr = 0.035 + 0.02 * tt          # sleeve widens toward the cuff
            if dd < rr * 1.6:
                h = max(h, 0.075 * _plateau(dd / rr, 0.7, 1.15))
    # flying ribbons: two long arcs from the shoulders, curling up at the ends
    for k in (0, 1):
        sk = 1 if k == 0 else -1
        u = (dx - hx) * sk
        if -0.05 < u < 1.05:
            zr = z0 + H * (0.74 - 0.20 * k) + 0.22 * math.sin(u * 3.3 + ph + k) * u - 0.10 * u
            h = max(h, 0.05 * _plateau(abs(z - zr) / (0.022 + 0.015 * u), 0.6, 1.1) * min(1.0, 3.0 * (1.05 - u)))
    return h


def _gate_h(dx, z, fz, w, hh):
    """carved gate building (W01): podium, four columns, eave beam, hipped roof with a ridge."""
    zb, zt = fz - hh / 2, fz + hh / 2
    if abs(dx) > w / 2 + 0.05 or z < zb - 0.03 or z > zt + 0.05:
        return None
    h = 0.008                                                       # recessed ground inside the scene
    if z < zb + 0.08 and abs(dx) < w / 2 - 0.05:
        h = 0.05                                                    # platform
    zr0 = zt - 0.26                                                 # roof from here up
    if zr0 <= z <= zt:
        t = (z - zr0) / 0.26
        half = (w / 2) * (1.0 - 0.45 * t) + 0.05 * (1 - t) ** 3     # curved hip roof outline, upturned eaves
        if abs(dx) < half:
            h = 0.065 - 0.012 * abs(math.sin(dx * 55.0))              # tile ribs
        if abs(z - zt + 0.02) < 0.02 and abs(dx) < half:
            h = 0.075                                                # ridge
    if zr0 - 0.07 <= z < zr0 and abs(dx) < w / 2 - 0.08:
        h = 0.06                                                    # eave beam
    for cx in (-0.62, -0.22, 0.22, 0.62):
        if abs(dx - cx * w / 1.55) < 0.035 and zb + 0.08 <= z < zr0 - 0.07:
            h = 0.055                                               # columns
    return h


_FIGS = None


def _relief_height(a, z, feats, rng_noise):
    """outward displacement (m) of the carved band at angle a, height z (0 = relief ground R_DRUM)."""
    global _FIGS
    if _FIGS is None:
        _FIGS = _figures()
    fz0, fz1 = REL_Z0 + 0.14, REL_Z1 - 0.14
    if z < fz0 - 0.015 or z > fz1 + 0.015:
        return 0.05                       # plain raised border above and below the carved field
    if z < fz0 or z > fz1:
        return 0.05 * (1.0 - min(z - (fz0 - 0.015), (fz1 + 0.015) - z) / 0.015)
    R = D.R_DRUM
    h = 0.006 + 0.0025 * math.sin(a * R * 23.0 + z * 31.0) * math.sin(a * R * 7.0 - z * 13.0)    # chiselled ground
    for f in _FIGS:
        da = (a - f[0] + math.pi) % (2 * math.pi) - math.pi
        dx = da * R
        if abs(dx) < 1.3:
            h = max(h, _fig_h(dx, z, f))
    # cloud scrolls drifting along the upper part of the field
    cl = math.sin(a * R * 2.2) * math.sin(z * 9.0 + a * R * 1.1)
    if z > fz1 - 0.45 and cl > 0.25:
        h = max(h, 0.04 * min(1.0, (cl - 0.25) / 0.12))
    for (kind, fa, fz, w, hh) in feats:
        da = (a - fa + math.pi) % (2 * math.pi) - math.pi
        dx = da * R
        dz = z - fz
        if kind in ('panel', 'window') and abs(dx) < w / 2 + 0.12 and abs(dz) < hh / 2 + 0.12:
            h = 0.05 if (abs(dx) > w / 2 + 0.02 or abs(dz) > hh / 2 + 0.02) else 0.02
        elif kind == 'cartouche':
            q = (dx / (w / 2)) ** 2 + (dz / (hh / 2)) ** 2
            if q < 1.0:
                h = 0.055 if q > 0.78 else 0.025          # characters not legible in any photo: left plain
        elif kind == 'medallion':
            q = (dx ** 2 + dz ** 2) ** 0.5 / (w / 2)
            if q < 1.0:
                h = 0.06 if q > 0.80 else 0.03
        elif kind == 'gate':
            g = _gate_h(dx, z, fz, w, hh)
            if g is not None:
                h = g
    return max(0.0, h)


def drum(c):
    """carved drum: a displaced cylinder mesh (real relief, ~3 cm grid), plain borders, openings cut as
    recesses (dark), the south panel recessed dark stone."""
    feats = _relief_features()
    R = D.R_DRUM
    da = 0.021 / R
    na = int(2 * math.pi / da)
    zs = []
    z = REL_Z0
    while z < REL_Z1 - 1e-6:
        zs.append(z)
        z += 0.02
    zs.append(REL_Z1)
    me = bpy.data.meshes.new('QT_relief')
    bm = bmesh.new()
    rows = []
    rngn = random.Random(3)
    for z in zs:
        row = []
        for i in range(na):
            a = 2 * math.pi * i / na
            h = _relief_height(a, z, feats, rngn)
            r = R + h
            row.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rows.append(row)
    for j in range(len(rows) - 1):
        for i in range(na):
            i2 = (i + 1) % na
            bm.faces.new((rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]))
    # inner closing surface (keeps it a closed shell for the normal checks)
    inner = []
    for z in (REL_Z0, REL_Z1):
        inner.append([bm.verts.new(((R - 0.4) * math.cos(2 * math.pi * i / na), (R - 0.4) * math.sin(2 * math.pi * i / na), z)) for i in range(na)])
    for i in range(na):
        i2 = (i + 1) % na
        bm.faces.new((inner[0][i2], inner[0][i], inner[1][i], inner[1][i2]))
        bm.faces.new((rows[0][i2], rows[0][i], inner[0][i], inner[0][i2]))
        bm.faces.new((rows[-1][i], rows[-1][i2], inner[1][i2], inner[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    C.orient_closed_shells(bm)
    uvl = bm.loops.layers.uv.new('UVMap')
    C.box_uv(bm, uvl, 1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.mat('M_MarbleRelief'))
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new('QT_relief', me)
    C.link(o, c)
    # openings and the panel: dark recessed boxes set into the band
    mb = C.MB()
    for (kind, fa, fz, w, hh) in feats:
        if kind not in ('panel', 'window'):
            continue
        cx, cy = math.cos(fa), math.sin(fa)
        p = Vector(((R + 0.012) * cx, (R + 0.012) * cy, fz))
        mb.obox(p, (Vector((-cy, cx, 0)), Vector((cx, cy, 0)), Vector((0, 0, 1))), (w / 2, 0.012, hh / 2),
                'M_BlackLacquer' if kind == 'panel' else 'M_Dark')
    o2 = mb.finish('QT_relief_openings', c, recalc=True)
    # plinth (moulded base course)
    mb = C.MB()
    z0, z1 = D.Z_TIER_TOP, REL_Z0
    prof = [(R - 0.3, z0), (R + 0.12, z0), (R + 0.12, z0 + 0.10), (R + 0.07, z0 + 0.13), (R + 0.04, z1 - 0.03),
            (R + 0.01, z1), (R - 0.3, z1), (R - 0.3, z0)]
    mb.lathe(prof, 192, 'M_Marble', cap_top=False, cap_bot=False, smooth=False)
    o3 = mb.finish('QT_plinth', c, recalc=True)
    return [o, o2, o3]


# ------------------------------------------------------------------ terraces
def _notched_outline(R, n_notch=8, w=None, d=None, step=0.20):
    """circle of radius R with n_notch rectangular notches (width w, depth d) at the column azimuths."""
    w = D.TIER_NOTCH_W if w is None else w
    d = D.TIER_NOTCH_D if d is None else d
    pts = []
    half = (w / 2) / R
    centers = [D.col_az(k) for k in range(n_notch)]
    n = int(2 * math.pi * R / step)
    angs = [2 * math.pi * i / n for i in range(n)]
    for c in centers:
        angs += [c - half, c + half]
    angs = sorted(a % (2 * math.pi) for a in angs)
    for a in angs:
        inside = any(abs(((a - c + math.pi) % (2 * math.pi)) - math.pi) < half - 1e-6 for c in centers)
        if inside:
            continue
        on_edge = [c for c in centers if abs(abs(((a - c + math.pi) % (2 * math.pi)) - math.pi) - half) < 1e-6]
        if on_edge:
            cc = on_edge[0]
            dlt = ((a - cc + math.pi) % (2 * math.pi)) - math.pi
            # outer corner, then the notch corner (rectangular, radial walls)
            p_out = (R * math.cos(a), R * math.sin(a))
            ux, uy = math.cos(cc), math.sin(cc)
            px, py = -uy, ux
            off = (w / 2) * (1 if dlt > 0 else -1)
            rin = R * math.cos(half) - d
            p_in = (ux * rin + px * off, uy * rin + py * off)
            if dlt < 0:
                pts += [p_out, p_in]
            else:
                pts += [p_in, p_out]
        else:
            pts.append((R * math.cos(a), R * math.sin(a)))
    return pts


def _prism_uv(name, coll, outline, z0, z1, m, R_uv):
    """closed prism of a 2D outline; UVs: u = arc length (angle * R_uv), v = z (for the ashlar joints)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    B = [bm.verts.new((x, y, z0)) for x, y in outline]
    T = [bm.verts.new((x, y, z1)) for x, y in outline]
    n = len(outline)
    fb = bm.faces.new(list(reversed(B)))
    ft = bm.faces.new(T)
    side = []
    for i in range(n):
        j = (i + 1) % n
        side.append(bm.faces.new((B[i], B[j], T[j], T[i])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        for l in f.loops:
            co = l.vert.co
            if f in side:
                a = math.atan2(co.y, co.x)
                l[uvl].uv = (a * R_uv, co.z)
            else:
                l[uvl].uv = (co.x, co.y)
    # fix the wrap seam on side faces (u jumps by 2 pi R)
    for f in side:
        us = [l[uvl].uv[0] for l in f.loops]
        if max(us) - min(us) > math.pi * R_uv:
            for l in f.loops:
                if l[uvl].uv[0] < 0:
                    l[uvl].uv = (l[uvl].uv[0] + 2 * math.pi * R_uv, l[uvl].uv[1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.mat(m))
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o


def terraces(c):
    """three terraces (W03, 340d, 419; plan from the DWG): solid notched prisms of ashlar (joints from the
    material), paved tops of granite slabs."""
    out = []
    for k in range(3):
        R = D.TIER_R[k]
        zt = D.Z_TIER_TOP - k * D.TIER_H
        zb = zt - D.TIER_H
        ol = _notched_outline(R)
        out.append(_prism_uv('QT_terrace_%d' % (k + 1), c, ol, zb, zt - 0.06, 'M_Ashlar', R))
    mb = SMB(_seed('tiertops'))
    for k in range(3):
        R = D.TIER_R[k]
        r_in = (D.R_DRUM + 0.12) if k == 0 else D.TIER_R[k - 1]
        zt = D.Z_TIER_TOP - k * D.TIER_H
        r = r_in
        kk = 0
        while r < R - 0.01:
            r1 = min(R + 0.03, r + 0.60)
            n = max(8, int(round(2 * math.pi * r1 / 0.95)))
            ring_slabs(mb, r, r1, zt - 0.065, zt - 0.003, 'M_GraniteFloor', n, a_off=kk * 0.21,
                       skip=lambda a, r0, r1_, R=R: _notch_hit(a, r0, r1_, R))
            r = r1
            kk += 1
    out.append(mb.finish_slabs('QT_terrace_tops', c))
    return out


def _notch_hit(a, r0, r1, R):
    """skip top slabs that would roof over a notch."""
    if r1 < R - D.TIER_NOTCH_D - 0.02:
        return False
    for j in range(8):
        cc = D.col_az(j)
        da = abs(((a - cc + math.pi) % (2 * math.pi)) - math.pi)
        if da * R < D.TIER_NOTCH_W / 2 + 0.45:
            return True
    return False


# ------------------------------------------------------------------ balustrades
POST_W = D.BAL_POST_W


def post_src(name='SRC_qt_post'):
    """望柱 (W02, af3b): square shaft with a moulded collar, a necked round head with a bud on top."""
    if bpy.data.objects.get(name):
        return bpy.data.objects[name]
    mb = C.MB()
    w = POST_W / 2
    H = D.BAL_POST_H
    hs = H - 0.40
    mb.box((-w, -w, 0.0), (w, w, hs), 'M_Marble')
    # collars and head (lathe)
    prof = [(0.0, hs), (w * 1.18, hs), (w * 1.18, hs + 0.035), (w * 0.95, hs + 0.05), (w * 1.08, hs + 0.08),
            (w * 1.08, hs + 0.11), (w * 0.78, hs + 0.13), (w * 0.82, hs + 0.16)]
    rb = w * 1.05
    zc = hs + 0.16 + rb * 0.95
    for i in range(1, 12):
        t = i / 11.0
        ang = -math.pi / 2 + math.pi * t
        prof.append((rb * math.cos(ang) * (1.0 - 0.18 * max(0.0, t - 0.6)), zc + rb * 1.05 * math.sin(ang)))
    prof[-1] = (0.0, zc + rb * 1.05 + 0.03)
    prof = [(max(0.0, r), z) for r, z in prof]
    mb.lathe(prof, 20, 'M_Marble', cap_bot=False, cap_top=False, smooth=True)
    o = mb.finish(name, C.lib_coll(), recalc=True)
    o.data.set_sharp_from_angle(angle=math.radians(40))
    return o


def _fret(mb, x0, x1, z0, z1, y, m, sign=-1, t=0.012, strip=0.022):
    """卍-type fret as raised strips on a panel face at y, protruding toward sign*Y (local XZ)."""
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    s = min((x1 - x0) * 0.42, (z1 - z0) * 0.42)
    ya, yb = (y - t, y) if sign < 0 else (y, y + t)
    def bx(xa, za, xb, zb):
        mb.box((min(xa, xb) - strip / 2, ya, min(za, zb) - strip / 2), (max(xa, xb) + strip / 2, yb, max(za, zb) + strip / 2), m)
    for (a, b) in (((-1, 0), (1, 0)), ((0, -1), (0, 1)), ((1, 0), (1, 1)), ((-1, 0), (-1, -1)), ((0, 1), (-1, 1)), ((0, -1), (1, -1))):
        bx(cx + a[0] * s, cz + a[1] * s, cx + b[0] * s, cz + b[1] * s)
    for sx in (-1, 1):
        xa = cx + sx * (s + 0.06)
        xb = x0 + 0.05 if sx < 0 else x1 - 0.05
        if abs(xb - xa) < 0.08:
            continue
        bx(xa, cz - s, xb, cz - s)
        bx(xa, cz + s, xb, cz + s)
        bx(xb, cz - s, xb, cz + s * 0.3)


def bay_src(name, L, H=D.BAL_RAIL_H):
    """one straight bay between posts (local X from -L/2 to L/2, centred, +Y outward, base at z=0):
    sill, fret panel, two vase supports, hand rail."""
    if bpy.data.objects.get(name):
        return bpy.data.objects[name]
    mb = C.MB()
    m = 'M_Marble'
    hl = L / 2 - POST_W / 2 + 0.01
    mb.box((-hl, -0.11, 0.0), (hl, 0.11, 0.12), m)                     # 地栿 sill
    mb.box((-hl, -0.045, 0.12), (hl, 0.045, 0.58), m)                  # 华板 panel
    mb.box((-hl, -0.06, 0.58), (hl, 0.06, 0.63), m)                    # panel cap
    for y in (-0.045, 0.045):
        sgn = -1 if y < 0 else 1
        for (xa, xb, za, zb) in ((-hl + 0.03, hl - 0.03, 0.16, 0.185), (-hl + 0.03, hl - 0.03, 0.52, 0.545),
                                 (-hl + 0.03, -hl + 0.055, 0.16, 0.545), (hl - 0.055, hl - 0.03, 0.16, 0.545)):
            if sgn < 0:
                mb.box((xa, y - 0.010, za), (xb, y, zb), m)
            else:
                mb.box((xa, y, za), (xb, y + 0.010, zb), m)
    _fret(mb, -hl + 0.08, hl - 0.08, 0.20, 0.50, -0.045, m, sign=-1)
    _fret(mb, -hl + 0.08, hl - 0.08, 0.20, 0.50, 0.045, m, sign=1)
    for x in (-L / 4, L / 4):                                           # 净瓶 vase supports
        mb.lathe([(0.0, 0.63), (0.045, 0.63), (0.05, 0.66), (0.032, 0.70), (0.055, 0.76), (0.04, 0.80), (0.0, 0.80)], 12, m,
                 center=(x, 0.0, 0.0), cap_bot=False, cap_top=False)
    # hand rail 寻杖
    mb.box((-hl, -0.05, 0.80), (hl, 0.05, H), m)
    o = mb.finish(name, C.lib_coll(), recalc=True)
    return o


def podium_balustrade(c):
    """24 posts on R_BAL (3 per column bay); bays between, except across the stair opening."""
    out = []
    n = D.BAL_N
    post = post_src()
    xf_p, xf_b = [], []
    hw = D.STAIR_W_CLEAR / 2 + D.STAIR_PARAPET / 2
    # post angles: evenly spaced, but the two posts at the stair edges sit on the parapet centre lines
    a_stair = math.asin(hw / D.R_BAL)
    angs = []
    for i in range(n):
        a = math.pi / 2 + a_stair + (2 * math.pi - 2 * a_stair) * i / n
        angs.append(a)
    angs.append(math.pi / 2 - a_stair)
    angs = sorted(a % (2 * math.pi) for a in angs)
    pts = [(D.R_BAL * math.cos(a), D.R_BAL * math.sin(a)) for a in angs]
    for (x, y), a in zip(pts, angs):
        xf_p.append(((x, y, 0.0), (0, 0, a - math.pi / 2), 1.0))
    L = None
    for i in range(len(pts)):
        p, q = Vector(pts[i] + (0.0,)), Vector(pts[(i + 1) % len(pts)] + (0.0,))
        mid = (p + q) / 2
        if mid.y > 0 and abs(mid.x) < hw:            # stair opening
            continue
        d = q - p
        L = d.length
        a = math.atan2(d.y, d.x)
        xf_b.append(((mid.x, mid.y, 0.0), (0, 0, a), 1.0))
    bay = bay_src('SRC_qt_bay', L)
    out.append(C.instancer('QT_balustrade_posts', post, xf_p, c))
    out.append(C.instancer('QT_balustrade_bays', bay, xf_b, c))
    return out


# ------------------------------------------------------------------ stair
def stair_profile():
    """[(r_start, r_end, z, kind)] treads and landings from the top (podium floor) down to the plaza; the riser
    height; the radius of the last riser (stair foot)."""
    rise = -D.Z_PLAZA / D.STAIR_RISERS
    out = []
    r = D.STAIR_R0
    z = 0.0
    for f, (nr, tread) in enumerate(D.STAIR_FLIGHTS):
        for i in range(nr - 1):
            z -= rise
            out.append((r, r + tread, z, 'tread'))
            r += tread
        z -= rise
        if f < len(D.STAIR_LANDINGS):
            out.append((r, r + D.STAIR_LANDINGS[f], z, 'landing'))
            r += D.STAIR_LANDINGS[f]
    return out, rise, r


def nose_z(r):
    """line through the step nosings (flat on landings): parapets and rails follow it."""
    prof, rise, r_foot = stair_profile()
    if r <= D.STAIR_R0:
        return 0.0
    if r >= r_foot:
        return D.Z_PLAZA
    for (r0, r1, z, kind) in prof:
        if r0 <= r < r1:
            if kind == 'tread':
                return z + rise * (1 - (r - r0) / (r1 - r0))
            return z
    return D.Z_PLAZA


def rail_base(r):
    """parapet / balustrade base line: nosing line smoothed over a tread, 0.10 above, easing to the floor."""
    T = D.STAIR_TREAD
    z = 0.5 * (nose_z(r - T / 2) + nose_z(r + T / 2))
    k = max(0.0, min(1.0, (r - D.STAIR_R0) / 0.4))
    return z + 0.10 * k


def _wall_mesh(name, coll, x0, x1, r0, r1, m='M_Ashlar'):
    """one stair side wall (solid ashlar): bottom on the plaza, top along the parapet base line; UV u = r, v = z."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    n = 160
    top = [(r0 + (r1 - r0) * i / n, rail_base(r0 + (r1 - r0) * i / n) - 0.12) for i in range(n + 1)]
    poly = [(r0, D.Z_PLAZA - 0.05), (r1, D.Z_PLAZA - 0.05)] + list(reversed(top))
    A = [bm.verts.new((x0, y, z)) for (y, z) in poly]
    B = [bm.verts.new((x1, y, z)) for (y, z) in poly]
    k = len(poly)
    bm.faces.new(A)
    bm.faces.new(list(reversed(B)))
    for i in range(k):
        j = (i + 1) % k
        bm.faces.new((A[j], A[i], B[i], B[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    C.orient_closed_shells(bm)
    for f in bm.faces:
        for l in f.loops:
            co = l.vert.co
            if abs(f.normal.x) > 0.7:
                l[uvl].uv = (co.y, co.z)
            elif abs(f.normal.z) > 0.7:
                l[uvl].uv = (co.x, co.y)
            else:
                l[uvl].uv = (co.x, co.z)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(C.mat(m))
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o


def stair(c_st, c_bal):
    out = []
    prof, rise, r_foot = stair_profile()
    hw = D.STAIR_W_CLEAR / 2
    pw = D.STAIR_PARAPET
    # steps: one granite block per tread across the width, nosing over the step below; landings in slabs
    mb = SMB(_seed('steps'))
    for (r0, r1, z, kind) in prof:
        mb.begin()
        if kind == 'tread':
            slab(mb, [(-hw - 0.01, r0), (hw + 0.01, r0), (hw + 0.01, r1 + 0.025), (-hw - 0.01, r1 + 0.025)],
                 z - rise - 0.04, z, 'M_GraniteStep', bevel=0.008)
        else:
            n = max(1, int(round((r1 - r0) / 0.58)))
            for i in range(n):
                ya = r0 + (r1 - r0 + 0.025) * i / n
                yb = r0 + (r1 - r0 + 0.025) * (i + 1) / n
                slab(mb, [(-hw - 0.01, ya + 0.003), (hw + 0.01, ya + 0.003), (hw + 0.01, yb - 0.003), (-hw - 0.01, yb - 0.003)],
                     z - 0.14, z, 'M_GraniteStep', bevel=0.006)
        mb.end()
    out.append(mb.finish_slabs('QT_stair_steps', c_st))
    # core under the steps (between the walls)
    mb = C.MB()
    n = 120
    ra, rb = D.R_DRUM - 0.1, r_foot
    top = [(ra + (rb - ra) * i / n, nose_z(ra + (rb - ra) * i / n) - rise - 0.10) for i in range(n + 1)]
    _extrude_yz(mb, [(ra, D.Z_PLAZA - 0.05), (rb, D.Z_PLAZA - 0.05)] + list(reversed(top)), -hw - 0.005, hw + 0.005, 'M_GraniteLight')
    out.append(mb.finish('QT_stair_core', c_st, recalc=True))
    for side in (-1, 1):
        x0, x1 = (hw, hw + pw) if side > 0 else (-hw - pw, -hw)
        out.append(_wall_mesh('QT_stair_wall_%s' % ('E' if side > 0 else 'W'), c_st, x0, x1, D.R_DRUM - 0.1, r_foot + 0.30))
    # small access doors in both side walls near the drum (W02 east face, 419 west face: ~0.6 x 0.86 m)
    mb = C.MB()
    for side in (-1, 1):
        x = side * (hw + pw)
        rcd, wd, z0, z1 = D.STAIR_DOOR
        mb.box((x - 0.02, rcd - wd / 2, z0), (x + 0.02, rcd + wd / 2, z1), 'M_DoorMetal')
        for (ya, yb, za, zb) in ((rcd - wd / 2 - 0.10, rcd - wd / 2, z0, z1 + 0.10), (rcd + wd / 2, rcd + wd / 2 + 0.10, z0, z1 + 0.10),
                                 (rcd - wd / 2 - 0.10, rcd + wd / 2 + 0.10, z1, z1 + 0.10)):
            mb.box((x - 0.03, ya, za), (x + 0.03, yb, zb), 'M_Marble')
    out.append(mb.finish('QT_stair_doors', c_st, recalc=True))
    out += stair_balustrades(c_bal, r_foot)
    return out


def _extrude_yz(mb, poly, x0, x1, m):
    """closed prism of a polygon given in (y, z), between x = x0 and x = x1."""
    A = [Vector((x0, y, z)) for (y, z) in poly]
    B = [Vector((x1, y, z)) for (y, z) in poly]
    n = len(poly)
    mb.face(A, m)
    mb.face(list(reversed(B)), m)
    for i in range(n):
        j = (i + 1) % n
        mb.face([A[j], A[i], B[i], B[j]], m)


def stair_balustrades(c, r_foot):
    """balustrades on both parapets: sloped marble coping, posts every ~1.25 m and at flight ends, sloped bays
    (sill, panel, cap, vase supports, hand rail); they start at the podium balustrade's stair-edge posts."""
    out = []
    hw = D.STAIR_W_CLEAR / 2
    pw = D.STAIR_PARAPET
    prof, rise, _ = stair_profile()
    post = post_src()
    xf_p = []
    mb = C.MB()
    m = 'M_Marble'
    xc = hw + pw / 2
    y_join = math.sqrt(max(0.0, D.R_BAL ** 2 - xc ** 2))      # podium post on the parapet line
    stations = [y_join]
    fl = []
    start = D.STAIR_R0 + 0.12
    for (r0, r1, z, kind) in prof:
        if kind == 'landing':
            fl.append((start, r0 + 0.12))
            stations += [r0 + 0.12, r1 - 0.12]
            start = r1 - 0.12
    fl.append((start, r_foot - 0.15))
    stations += [D.STAIR_R0 + 0.12, r_foot - 0.15]
    for (a, b) in fl:
        n = max(1, int(round((b - a) / 1.25)))
        for i in range(1, n):
            stations.append(a + (b - a) * i / n)
    stations = sorted(set(round(v, 3) for v in stations))
    for side in (-1, 1):
        x = side * xc
        # parapet coping
        n = 180
        ys = [D.R_DRUM - 0.05 + (r_foot + 0.30 - (D.R_DRUM - 0.05)) * i / n for i in range(n + 1)]
        top = [(y, rail_base(y)) for y in ys]
        for i in range(n):
            (ya, za), (yb, zb) = top[i], top[i + 1]
            P = [Vector((x - 0.19, ya, za)), Vector((x + 0.19, ya, za)), Vector((x + 0.19, yb, zb)), Vector((x - 0.19, yb, zb))]
            Q = [p - Vector((0, 0, 0.12)) for p in P]
            mb.face(P, m); mb.face(list(reversed(Q)), m)
            mb.face([Q[1], Q[2], P[2], P[1]], m)
            mb.face([Q[3], Q[0], P[0], P[3]], m)
            if i == 0:
                mb.face([Q[0], Q[1], P[1], P[0]], m)
            if i == n - 1:
                mb.face([P[3], P[2], Q[2], Q[3]], m)
        for sy in stations[1:]:
            xf_p.append(((x, sy, rail_base(sy)), (0, 0, 0), 1.0))
        for a, b in zip(stations, stations[1:]):
            za, zb = rail_base(a), rail_base(b)
            ya, yb = a + POST_W / 2, b - POST_W / 2
            if yb - ya < 0.12:
                continue
            for (z0, z1, w) in ((0.0, 0.10, 0.20), (0.10, 0.56, 0.08), (0.56, 0.61, 0.11), (0.80, D.BAL_RAIL_H, 0.10)):
                P = [Vector((x - w / 2, ya, za + z0)), Vector((x + w / 2, ya, za + z0)), Vector((x + w / 2, yb, zb + z0)), Vector((x - w / 2, yb, zb + z0))]
                Q = [Vector((p.x, p.y, p.z + (z1 - z0))) for p in P]
                mb.face(list(reversed(P)), m); mb.face(Q, m)
                for k in range(4):
                    j = (k + 1) % 4
                    mb.face([P[k], P[j], Q[j], Q[k]], m)
            # raised frame on both panel faces (follows the slope): thin solid strips standing on the panel
            for sgn in (-1, 1):
                for (u0, u1, v0, v1) in ((0.03, 0.97, 0.14, 0.165), (0.03, 0.97, 0.50, 0.525)):
                    xa, xb = x + sgn * 0.038, x + sgn * 0.052
                    P0 = [Vector((xx, ya + (yb - ya) * u, za + (zb - za) * u + v)) for xx in (xa, xb) for (u, v) in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
                    A, B = P0[:4], P0[4:]
                    mb.face(list(reversed(A)), m); mb.face(B, m)
                    for k in range(4):
                        j = (k + 1) % 4
                        mb.face([A[k], A[j], B[j], B[k]], m)
            for f in (1 / 3, 2 / 3):
                y = ya + (yb - ya) * f
                z = za + (zb - za) * f
                mb.lathe([(0.0, z + 0.61), (0.04, z + 0.61), (0.045, z + 0.64), (0.03, z + 0.68), (0.05, z + 0.74), (0.036, z + 0.80), (0.0, z + 0.80)],
                         10, m, center=(x, y, 0.0), cap_bot=False, cap_top=False)
    out.append(mb.finish('QT_stair_balustrade', c, recalc=True))
    out.append(C.instancer('QT_stair_posts', post, xf_p, c))
    return out
