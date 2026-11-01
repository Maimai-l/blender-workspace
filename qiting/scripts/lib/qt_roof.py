# Qiting - round (conical) roofs on a surface-of-revolution profile, and the gilded finial.
# A roof is given by its tile-top profile z_top(r) (traced on W02). Built parts:
#   deck (mortar bed + boards, a solid of revolution whose underside is the visible board soffit),
#   tiles (instanced cover / pan rows, tapering with the radius, every other row dropped where they get too
#   narrow), eave tiles (round end discs and drip tiles), two layers of instanced rafters (square eave rafters and
#   flying rafters, two rows of red square ends under the eave as in W01 / af3b), the fascia boards, the purlin,
#   the collar where a roof meets a wall, and the finial.
import bpy, math
from mathutils import Vector, Matrix
import xy_core as C, xy_roof as XR
import qt_dims as D

TILE_L = 0.33          # exposed course length along the slope
TILE_P0 = 0.30         # pitch the tile sources are made for
DECK_T = 0.13          # tile top -> deck top
DECK_MIN = 0.10


class Eave:
    """Section of one eave. All z values absolute.
    prof: [(r, z_tile_top)], eave_r: tile edge, fascia_r: outer face of the fascia board (大连檐),
    dly_top: top of the fascia board, r_wall: wall line under the eave, r_in: inner end of the deck."""
    def __init__(self, tag, prof, eave_r, fascia_r, dly_top, r_wall, r_in, n_rows, n_rafters, r_purlin,
                 fly_len=0.95, fly_slope=10.0, er_slope=16.5, er_inset=0.30, levels=None):
        self.tag = tag
        self.pts = sorted(prof)
        self.eave_r, self.fascia_r, self.r_wall, self.r_in = eave_r, fascia_r, r_wall, r_in
        self.n_rows, self.n_rafters, self.r_purlin = n_rows, n_rafters, r_purlin
        self.dly = (dly_top - 0.10, dly_top)                  # fascia board z range
        self.fly_h, self.fly_w = 0.09, 0.085
        self.er_h, self.er_w = 0.10, 0.095
        self.fly_end = fascia_r - 0.006
        self.fly_top_end = self.dly[0]
        self.fly_len = fly_len
        self.fly_k = math.tan(math.radians(fly_slope))
        self.er_end = fascia_r - er_inset
        self.er_top_end = self.fly_top_end - self.fly_h - 0.025 - (self.fly_end - self.er_end) * self.fly_k
        self.er_k = math.tan(math.radians(er_slope))
        self.levels = levels       # [(r_outer, r_inner, n_rows)] tile levels; default computed

    def z_top(self, r):
        p = self.pts
        if r >= p[-1][0]:
            (r0, z0), (r1, z1) = p[-2], p[-1]
            return z1 + (r - r1) * (z1 - z0) / (r1 - r0)
        if r <= p[0][0]:
            (r0, z0), (r1, z1) = p[0], p[1]
            return z0 + (r - r0) * (z1 - z0) / (r1 - r0)
        return D.interp(p, r)

    def fly_top(self, r):
        return self.fly_top_end + (self.fly_end - r) * self.fly_k

    def er_top(self, r):
        return self.er_top_end + (self.er_end - r) * self.er_k

    def underside(self, r):
        """visible soffit (boards): on the flying rafters outboard of the eave-rafter ends, else on the eave rafters."""
        if r > self.er_end:
            return self.fly_top(r)
        return self.er_top(r)


def _ring(r, z, segs):
    return [(r * math.cos(2 * math.pi * k / segs), r * math.sin(2 * math.pi * k / segs), z) for k in range(segs)]


def deck(E, coll, segs=192):
    """Solid of revolution: top = tile top - DECK_T, underside = board soffit, outer edge at the fascia."""
    mb = C.MB()
    rs = []
    r = E.fascia_r - 0.02
    while r > E.r_in:
        rs.append(r)
        r -= 0.12
    rs.append(E.r_in)
    # extra samples around the eave-rafter end step
    rs = sorted(set([round(x, 4) for x in rs + [E.er_end + 0.001, E.er_end - 0.001]]), reverse=True)
    top = [(r, E.z_top(r) - DECK_T) for r in rs]
    bot = [(r, min(E.underside(r), E.z_top(r) - DECK_T - DECK_MIN)) for r in rs]
    # profile loop: outer edge down, along the underside inward, up the inner edge, along the top outward
    rows_top = [_ring(r, z, segs) for (r, z) in top]
    rows_bot = [_ring(r, z, segs) for (r, z) in bot]
    m_top, m_bot = 'M_Tile', 'M_RedDark'
    mb.quad_strip(list(reversed(rows_top)), m_top, closed_u=True)              # top (faces up: inner -> outer)
    mb.quad_strip(rows_bot, m_bot, closed_u=True)                              # underside (outer -> inner)
    mb.quad_strip([rows_top[0], rows_bot[0]], m_bot, closed_u=True)            # outer edge
    mb.quad_strip([rows_bot[-1], rows_top[-1]], m_bot, closed_u=True)          # inner edge
    o = mb.finish('%s_deck' % E.tag, coll, recalc=True)
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.set_sharp_from_angle(angle=math.radians(30))
    return o


def tile_levels(E):
    """[(r_outer, r_inner, n)]: halve the rows where they would get narrower than 57% of the source pitch."""
    if E.levels:
        return E.levels
    out = []
    n = E.n_rows
    r_out = E.eave_r
    while True:
        r_cut = 0.57 * TILE_P0 * n / (2 * math.pi)
        if r_cut <= E.r_in + 0.05 or n <= 8:
            out.append((r_out, E.r_in, n))
            break
        out.append((r_out, r_cut, n))
        r_out = r_cut
        n //= 2
    return out


def _row_stations(E, r_out, r_in, first):
    """tile positions along one row, walking up the profile from r_out to r_in in TILE_L steps.
    returns [(r, z, slope_angle, is_eave)]"""
    out = []
    # fine polyline of the profile
    N = 200
    rs = [r_out - (r_out - r_in) * i / N for i in range(N + 1)]
    P = [(r, E.z_top(r)) for r in rs]
    acc = [0.0]
    for i in range(1, len(P)):
        acc.append(acc[-1] + math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]))
    s = 0.0
    k = 0
    while s < acc[-1] - 0.08:
        i = 1
        while i < len(acc) - 1 and acc[i] < s:
            i += 1
        t = (s - acc[i - 1]) / max(1e-9, acc[i] - acc[i - 1])
        r = P[i - 1][0] + (P[i][0] - P[i - 1][0]) * t
        z = P[i - 1][1] + (P[i][1] - P[i - 1][1]) * t
        ang = math.atan2(P[i][1] - P[i - 1][1], P[i - 1][0] - P[i][0])     # rise going inward
        out.append((r, z, ang, first and k == 0))
        s += TILE_L
        k += 1
    return out


def tiles(E, coll):
    src = XR.tile_sources()
    res = {'SRC_cover': [], 'SRC_pan': [], 'SRC_cover_eave': [], 'SRC_pan_eave': []}
    levels = tile_levels(E)
    for li, (r_out, r_in, n) in enumerate(levels):
        first = (li == 0)
        start = r_out if first else r_out + 0.10           # overlap the course below the level change
        st = _row_stations(E, start, r_in, first)
        for kind in ('cover', 'pan'):
            for j in range(n):
                phi = 2 * math.pi * (j + (0.5 if kind == 'pan' else 0.0)) / n
                c, s_ = math.cos(phi), math.sin(phi)
                for (r, z, ang, is_eave) in st:
                    pitch = 2 * math.pi * r / n
                    sc = max(0.55, min(1.15, pitch / TILE_P0))
                    ca, sa = math.cos(ang), math.sin(ang)
                    X = Vector((-c * ca, -s_ * ca, sa))        # uphill
                    Y = Vector((s_, -c, 0.0))
                    Z = X.cross(Y)
                    nrm = Z.normalized()
                    if kind == 'cover':
                        base = Vector((c * r, s_ * r, z)) - nrm * (XR.COVER_R + 0.006) * sc
                        key = 'SRC_cover_eave' if is_eave else 'SRC_cover'
                        scl = (1.0, sc, sc)
                    else:
                        base = Vector((c * r, s_ * r, z)) - nrm * (XR.COVER_R + 0.035)
                        key = 'SRC_pan_eave' if is_eave else 'SRC_pan'
                        scl = (1.0, sc, 1.0)
                    res[key].append((tuple(base), C.rot_from_axes(X, Y, Z), scl))
    objs = []
    for k, lst in res.items():
        if lst:
            objs.append(C.instancer('%s_%s' % (E.tag, k[4:]), src[k], lst, coll))
    return objs, sum(len(v) for v in res.values())


def rafter_sources():
    lib = C.lib_coll()
    out = {}
    for name, w, h, L in (('SRC_fly', 0.085, 0.09, 1.0), ('SRC_eaverafter', 0.095, 0.10, 1.0)):
        if bpy.data.objects.get(name) is None:
            mb = C.MB()
            # unit length along -X from the end face at x = 0 (end face gets the lighter end material)
            x0, x1 = -L, 0.0
            y0, y1 = -w / 2, w / 2
            z0, z1 = -h, 0.0
            P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
            vs = P
            faces = [((0, 3, 2, 1), 'M_RedDark'), ((4, 5, 6, 7), 'M_RedDark'), ((0, 1, 5, 4), 'M_RedDark'),
                     ((2, 3, 7, 6), 'M_RedDark'), ((3, 0, 4, 7), 'M_RedDark'), ((1, 2, 6, 5), 'M_RafterEnd')]
            for f, m in faces:
                mb.face([vs[i] for i in f], m)
            mb.finish(name, lib, recalc=True)
        out[name] = bpy.data.objects[name]
    return out


def rafters(E, coll):
    """two layers of square rafters, instanced; local frame of a source: +X = outward along the rafter,
    scaled in X to the needed length."""
    src = rafter_sources()
    fly, er = [], []
    n = E.n_rafters
    fly_ang = math.atan(E.fly_k)
    er_ang = math.atan(E.er_k)
    er_len = E.er_end - (E.r_wall - 0.25)
    for j in range(n):
        phi = 2 * math.pi * (j + 0.5) / n
        c, s_ = math.cos(phi), math.sin(phi)
        for (r_end, z_end, ang, L, lst) in ((E.fly_end, E.fly_top_end, fly_ang, E.fly_len, fly),
                                            (E.er_end, E.er_top_end, er_ang, er_len / math.cos(er_ang), er)):
            X = Vector((c * math.cos(ang), s_ * math.cos(ang), -math.sin(ang)))   # outward, sloping down
            Y = Vector((-s_, c, 0.0))
            Z = X.cross(Y)
            lst.append(((c * r_end, s_ * r_end, z_end), C.rot_from_axes(X, Y, Z), (L, 1.0, 1.0)))
    o1 = C.instancer('%s_rafters_fly' % E.tag, src['SRC_fly'], fly, coll)
    o2 = C.instancer('%s_rafters_eave' % E.tag, src['SRC_eaverafter'], er, coll)
    return [o1, o2]


def fascia(E, coll, segs=240):
    """大连檐 on the flying-rafter ends, 小连檐 on the eave-rafter ends, purlin ring under the eave rafters."""
    mb = C.MB()
    # 大连檐: outer face at fascia_r, 0.08 deep
    z0, z1 = E.dly
    mb.lathe([(E.fascia_r - 0.08, z0), (E.fascia_r, z0), (E.fascia_r, z1), (E.fascia_r - 0.10, z1), (E.fascia_r - 0.08, z0)], segs, 'M_Red',
             cap_top=False, cap_bot=False, smooth=False)
    # 小连檐: thin strip on top of the eave-rafter ends
    zt = E.er_top_end
    mb.lathe([(E.er_end - 0.06, zt), (E.er_end, zt), (E.er_end, zt + 0.03), (E.er_end - 0.06, zt + 0.03), (E.er_end - 0.06, zt)], segs, 'M_Red',
             cap_top=False, cap_bot=False, smooth=False)
    o = mb.finish('%s_fascia' % E.tag, coll, recalc=True)
    mb = C.MB()
    rp = E.r_purlin
    zt = E.er_top(rp) - E.er_h
    mb.lathe([(rp - 0.09, zt - 0.24), (rp + 0.09, zt - 0.24), (rp + 0.09, zt), (rp - 0.09, zt), (rp - 0.09, zt - 0.24)], segs, 'M_RedDark',
             cap_top=False, cap_bot=False, smooth=False)
    # beam on the wall top carrying the rafters (柱头枋)
    rw = E.r_wall
    zt2 = E.er_top(rw) - E.er_h
    mb.lathe([(rw - 0.10, zt2 - 0.22), (rw + 0.10, zt2 - 0.22), (rw + 0.10, zt2), (rw - 0.10, zt2), (rw - 0.10, zt2 - 0.22)], segs, 'M_RedDark',
             cap_top=False, cap_bot=False, smooth=False)
    o2 = mb.finish('%s_purlins' % E.tag, coll, recalc=True)
    return [o, o2]


def collar(name, r_wall, z0, z1, coll, segs=160):
    """tiled ridge collar where a roof meets a wall (围脊): a rounded roll of tiles against the wall."""
    mb = C.MB()
    prof = [(r_wall - 0.01, z0), (r_wall + 0.20, z0), (r_wall + 0.22, z0 + 0.04), (r_wall + 0.18, z1 - 0.10),
            (r_wall + 0.14, z1 - 0.04), (r_wall + 0.08, z1), (r_wall - 0.01, z1), (r_wall - 0.01, z0)]
    mb.lathe(prof, segs, 'M_Tile', cap_top=False, cap_bot=False, smooth=True)
    return mb.finish(name, coll, recalc=True)


def finial(coll, segs=48):
    """宝顶 (W02): a flared base on the roof apex, six stacked rings tapering upward, a neck, an egg-shaped bulb and
    a thin rod (W01, af3b)."""
    mb = C.MB()
    z = D.FINIAL_Z0
    prof = [(0.0, z - 0.25), (D.FINIAL_R0 + 0.06, z - 0.25), (D.FINIAL_R0 + 0.08, z - 0.08), (D.FINIAL_R0, z + 0.02)]
    n = D.FINIAL_RINGS
    zt = D.FINIAL_Z_RINGS_TOP
    hh = (zt - z) / n
    for i in range(n):
        t = i / (n - 1)
        r = D.FINIAL_R0 + (D.FINIAL_R1 - D.FINIAL_R0) * (t ** 0.9)
        za = z + i * hh
        # each ring: a rounded band, pinched at its joints
        prof += [(r * 0.90, za + 0.02), (r * 1.0, za + hh * 0.25), (r * 1.02, za + hh * 0.5), (r * 0.98, za + hh * 0.78),
                 (r * 0.88, za + hh * 0.98)]
    zn = D.FINIAL_Z_NECK
    rb = D.FINIAL_BULB_R
    prof += [(0.27, zt + 0.02), (0.30, zt + 0.05), (0.27, zn - 0.03), (0.22, zn)]
    # bulb: widest at 40 % of its height, pointed top
    zb0, zb1 = zn, D.FINIAL_Z_TOP
    H = zb1 - zb0
    for i in range(1, 15):
        t = i / 14.0
        prof.append((rb * math.sin(math.pi * min(1.0, t ** 0.85)) ** 0.75 * (1.0 - 0.15 * t) + 0.0 * t, zb0 + H * t))
    prof[-1] = (0.03, zb1)
    prof.append((0.0, zb1 + 0.01))
    prof = [(max(0.0, r), zz) for r, zz in prof]
    mb.lathe(prof, segs, 'M_Gold', cap_top=False, cap_bot=True, smooth=True)
    o = mb.finish('QT_finial', coll, recalc=True)
    o.data.set_sharp_from_angle(angle=math.radians(50))
    mb = C.MB()
    mb.cyl((0, 0, D.FINIAL_Z_TOP - 0.05), (0, 0, D.FINIAL_ROD_TOP), 0.028, 12, 'M_Rod', r1=0.012)
    mb.lathe([(0.0, D.FINIAL_ROD_TOP - 0.02), (0.035, D.FINIAL_ROD_TOP + 0.02), (0.0, D.FINIAL_ROD_TOP + 0.07)], 12, 'M_Rod')
    o2 = mb.finish('QT_finial_rod', coll, recalc=True)
    return [o, o2]


def build_roof(E, c_roof, c_eave):
    objs = [deck(E, c_roof)]
    tl, n = tiles(E, c_roof)
    objs += tl
    objs += rafters(E, c_eave)
    objs += fascia(E, c_eave)
    return objs, n


def eaves():
    """the two eaves of the pavilion, from the dimension table."""
    E1 = Eave('QT_R1', D.ROOF1, D.EAVE1_R, D.EAVE1_FASCIA_R, D.EAVE1_FASCIA_Z[1], D.R_COL, D.R_DRUM2 + 0.06,
              n_rows=120, n_rafters=240, r_purlin=D.R_COL + 0.50)
    E2 = Eave('QT_R2', D.ROOF2 + [(0.70, D.FINIAL_Z0 + 0.05)], D.EAVE2_R, D.EAVE2_FASCIA_R, D.EAVE2_FASCIA_Z[1],
              D.R_DRUM2, 0.70, n_rows=96, n_rafters=176, r_purlin=D.R_DRUM2 + 0.48)
    return E1, E2
