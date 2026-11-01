# Qiting - pavilion frame: columns and bases, architrave and lattice frieze, plaster bracket bands with bracket
# sets (instanced), the upper drum with its window band, the interior (inner columns, ceiling ring, painted
# caisson), the plaque and the couplet boards.
import bpy, math
from mathutils import Vector, Matrix
import xy_core as C, xy_parts as PT, xy_props as PR
import qt_dims as D


def _get(name):
    return bpy.data.objects.get(name)


def _ring_xf(r, az, z, extra_rz=0.0, s=1.0):
    """transform for a part whose local +Y points radially outward at azimuth az (radians)."""
    return ((r * math.cos(az), r * math.sin(az), z), (0.0, 0.0, az - math.pi / 2 + extra_rz), s)


def annulus(mb, r0, r1, z0, z1, m, segs=160, a0=0.0, a1=2 * math.pi):
    """solid ring section (rectangle r0..r1 x z0..z1) revolved over a0..a1 (closed if full)."""
    full = abs((a1 - a0) - 2 * math.pi) < 1e-6
    n = segs if full else max(2, int(segs * (a1 - a0) / (2 * math.pi)) + 1)
    sec = [(r0, z0), (r1, z0), (r1, z1), (r0, z1)]
    rows = []
    for k in range(n if full else n):
        a = a0 + (a1 - a0) * k / (n if full else (n - 1))
        c, s = math.cos(a), math.sin(a)
        rows.append([(r * c, r * s, z) for (r, z) in sec])
    vrows, faces = mb.quad_strip(rows, m, closed_u=True) if not full else mb.quad_strip(rows + [rows[0]], m, closed_u=True)
    if not full:
        mb.face([Vector(p) for p in reversed(rows[0])], m)
        mb.face([Vector(p) for p in rows[-1]], m)


# ------------------------------------------------------------------ sources
def column_src(name, H, d0, d1, m='M_Red'):
    """round column with slight entasis, rounded top; origin at its foot."""
    if _get(name):
        return _get(name)
    return PT.column_src(name, H, r0=d0 / 2, r1=d1 / 2, segs=24, m=m)


def base_src(name='SRC_qt_base', R=0.31):
    """柱础: plain round stone base, a low drum with a convex top (photos never show the bases clearly)."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    prof = [(0.0, 0.0), (R, 0.0), (R, 0.05), (R * 0.97, 0.075), (R * 0.86, 0.10), (R * 0.72, 0.115), (0.0, 0.12)]
    mb.lathe(prof, 32, 'M_Marble', cap_bot=False, cap_top=False, smooth=True)
    o = mb.finish(name, C.lib_coll(), recalc=True)
    o.data.set_sharp_from_angle(angle=math.radians(45))
    return o


def _cloud_arm(L, H, lobes=3, lift=0.30):
    """outline (x, z) of a bracket arm with cloud-shaped ends (W01 / af3b): flat top, lower edge rising toward
    each end in cusped lobes. Counter-clockwise seen from -y."""
    pts = []
    n_end = 6 * lobes
    half = L / 2
    end_len = L * 0.28
    # lower edge, left end -> right end
    for i in range(n_end + 1):          # left end region, from the tip inward
        t = i / n_end
        x = -half + end_len * t
        base = H * lift * (1 - t) ** 1.3
        cusp = 0.035 * abs(math.sin(math.pi * lobes * t))
        pts.append((x, base + cusp))
    pts.append((-half + end_len, 0.0))
    pts.append((half - end_len, 0.0))
    for i in range(n_end + 1):
        t = 1 - i / n_end
        x = half - end_len * t
        base = H * lift * (1 - t) ** 1.3
        cusp = 0.035 * abs(math.sin(math.pi * lobes * t))
        pts.append((x, base + cusp))
    # dedupe
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-5 or abs(p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    out.append((half, H))
    out.append((-half, H))
    return out


def bracket_src(name, reach, scale=1.0):
    """斗栱 on a column top. Local: X along the wall (tangent), +Y outward, Z up, origin at the column top centre.
    栌斗, a cloud-ended 泥道栱 and a longer 慢栱 along the wall, a projecting 华栱 carrying a 替木 under the
    purlin at y = reach. Height to the top of the 慢栱 blocks ~0.70 m (bands of W01 / af3b)."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    R = 'M_RedDark'
    s = scale
    PT.dou(mb, 0, 0, 0.0, 0.44 * s, 0.44 * s, 0.24 * s, R, taper=0.72, ear=0.58)
    # tier 1: 泥道栱 along X (cloud ends), 华栱 along +Y
    ol = _cloud_arm(1.30 * s, 0.20 * s)
    PT._extrude_xz(mb, ol, -0.065 * s, 0.065 * s, R, Matrix.Translation((0, 0, 0.14 * s)))
    PT.arm_y(mb, 0, -0.30 * s, reach + 0.10 * s, 0.14 * s, H=0.20 * s, W=0.13 * s, m=R, k=0.12 * s)
    for x in (-0.53 * s, 0.53 * s, 0.0):
        PT.dou(mb, x, 0, 0.34 * s, 0.20 * s, 0.18 * s, 0.11 * s, R)
    PT.dou(mb, 0, reach, 0.34 * s, 0.22 * s, 0.22 * s, 0.12 * s, R)
    # tier 2: 慢栱 along X (longer cloud arm)
    ol2 = _cloud_arm(1.90 * s, 0.20 * s, lobes=4, lift=0.35)
    PT._extrude_xz(mb, ol2, -0.065 * s, 0.065 * s, R, Matrix.Translation((0, 0, 0.45 * s)))
    for x in (-0.85 * s, 0.85 * s, -0.30 * s, 0.30 * s):
        PT.dou(mb, x, 0, 0.65 * s, 0.20 * s, 0.18 * s, 0.10 * s, R)
    # 替木 under the purlin
    mb.box((-0.55 * s, reach - 0.06 * s, 0.46 * s), (0.55 * s, reach + 0.06 * s, 0.52 * s), R)
    # 耍头: beam end projecting past the purlin, bevelled nose
    nose = [(-0.40 * s, 0.0), (reach + 0.18 * s, 0.0), (reach + 0.26 * s, 0.07 * s), (reach + 0.26 * s, 0.16 * s), (-0.40 * s, 0.16 * s)]
    Mz = Matrix.Translation((0, 0, 0.46 * s)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
    PT._extrude_xz(mb, nose, -0.06 * s, 0.06 * s, R, Mz)
    return mb.finish(name, C.lib_coll(), recalc=True)


# ------------------------------------------------------------------ lower storey
def lower_storey(c_cols, c_eave):
    out = []
    H = D.Z_ARCH[1] - 0.12
    col = column_src('SRC_qt_col', H, D.COL_D0, D.COL_D1)
    colin = column_src('SRC_qt_colin', 5.80 - 0.12, D.COL_IN_D, D.COL_IN_D * 0.92)
    base = base_src()
    xf_c, xf_ci, xf_b = [], [], []
    for k in range(D.N_COL):
        az = D.col_az(k)
        xf_c.append(((D.R_COL * math.cos(az), D.R_COL * math.sin(az), 0.12), (0, 0, az), 1.0))
        xf_b.append(((D.R_COL * math.cos(az), D.R_COL * math.sin(az), 0.0), (0, 0, az), 1.0))
        xf_ci.append(((D.R_COL_IN * math.cos(az), D.R_COL_IN * math.sin(az), 0.12), (0, 0, az), 1.0))
        xf_b.append(((D.R_COL_IN * math.cos(az), D.R_COL_IN * math.sin(az), 0.0), (0, 0, az), 0.9))
    out.append(C.instancer('QT_columns_outer', col, xf_c, c_cols))
    out.append(C.instancer('QT_columns_inner', colin, xf_ci, c_cols))
    out.append(C.instancer('QT_column_bases', base, xf_b, c_cols))
    # architrave, frieze, lower beam (rings through the columns), plaster band
    mb = C.MB()
    R = D.R_COL
    annulus(mb, R - 0.10, R + 0.10, D.Z_ARCH[0], D.Z_ARCH[1], 'M_Red', segs=192)
    annulus(mb, R - 0.08, R + 0.08, D.Z_LOWBEAM[0], D.Z_LOWBEAM[1], 'M_Red', segs=192)
    # frieze posts: 2 per bay -> 3 openings
    for k in range(D.N_COL):
        a0 = D.col_az(k)
        for f in (1 / 3, 2 / 3):
            a = a0 + math.radians(45) * f
            c, s = math.cos(a), math.sin(a)
            Mx = Matrix.Translation((R * c, R * s, D.Z_FRIEZE[0])) @ Matrix.Rotation(a, 4, 'Z')
            for (lo, hi) in (((-0.06, -0.05, 0.0), (0.06, 0.05, D.Z_FRIEZE[1] - D.Z_FRIEZE[0])),):
                P = [Mx @ Vector(v) for v in ((lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2]),
                                              (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2]))]
                for f4 in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
                    mb.face([P[i] for i in f4], 'M_Red')
    out.append(mb.finish('QT_beams_lower', c_cols, recalc=True))
    # plaster bracket band (栱眼壁) up to the wall beam under the rafters
    z_top = 4.11
    mb = C.MB()
    annulus(mb, R - 0.05, R + 0.04, D.Z_ARCH[1], z_top, 'M_Plaster', segs=192)
    out.append(mb.finish('QT_band_lower', c_eave, recalc=True))
    # bracket sets on the column tops
    brk = bracket_src('SRC_qt_brk1', reach=0.50)
    xf = []
    for k in range(D.N_COL):
        az = D.col_az(k)
        xf.append(((R * math.cos(az), R * math.sin(az), D.Z_ARCH[1]), (0, 0, az - math.pi / 2), 1.0))
    out.append(C.instancer('QT_brackets_lower', brk, xf, c_eave))
    return out


# ------------------------------------------------------------------ interior
def interior(c_cols, c_eave):
    out = []
    mb = C.MB()
    # inner ring beam on the inner columns, radial beams from outer to inner columns
    annulus(mb, D.R_COL_IN - 0.10, D.R_COL_IN + 0.10, D.Z_ARCH[0], D.Z_ARCH[1], 'M_Red', segs=128)
    for k in range(D.N_COL):
        az = D.col_az(k)
        c, s = math.cos(az), math.sin(az)
        p0 = Vector((D.R_COL_IN * c, D.R_COL_IN * s, (D.Z_ARCH[0] + D.Z_ARCH[1]) / 2))
        p1 = Vector((D.R_COL * c, D.R_COL * s, (D.Z_ARCH[0] + D.Z_ARCH[1]) / 2))
        d = (p1 - p0).normalized()
        sd = Vector((-s, c, 0))
        mb.obox((p0 + p1) / 2, (d, sd, Vector((0, 0, 1))), ((p1 - p0).length / 2, 0.09, (D.Z_ARCH[1] - D.Z_ARCH[0]) / 2), 'M_Red')
    out.append(mb.finish('QT_beams_inner', c_cols, recalc=True))
    # flat painted ceiling ring between the rings, at the architrave top
    mb = C.MB()
    annulus(mb, D.R_COL_IN + 0.10, D.R_COL - 0.06, D.Z_ARCH[1], D.Z_ARCH[1] + 0.06, 'M_PaintedPanel', segs=160)
    out.append(mb.finish('QT_ceiling_ring', c_eave, recalc=True))
    # inner drum (white inside) from the ring beam up to the caisson, red posts are the inner columns above
    mb = C.MB()
    annulus(mb, D.R_COL_IN - 0.08, D.R_COL_IN + 0.04, D.Z_ARCH[1], D.Z_SILL2[0], 'M_PlasterIn', segs=128)
    out.append(mb.finish('QT_inner_wall', c_cols, recalc=True))
    # painted caisson (藻井): shallow dome inside the upper drum (W08)
    mb = C.MB()
    Rd = D.R_COL_IN - 0.08
    z0 = 6.60
    prof = [(Rd, z0 - 0.06), (Rd, z0)]
    for i in range(1, 13):
        t = i / 12.0
        prof.append((Rd * (1 - t), z0 + 0.55 * math.sin(math.pi / 2 * t) ** 1.2))
    prof = [(max(r, 0.0), z) for r, z in prof]
    mb.lathe(prof, 96, 'M_CeilingLotus', cap_bot=False, cap_top=False, smooth=True)
    o = mb.finish('QT_caisson', c_eave, recalc=False)
    for p in o.data.polygons:
        p.use_smooth = True
    # faces must look down: flip if the first face normal points up
    if o.data.polygons[len(o.data.polygons) // 2].normal.z > 0:
        o.data.flip_normals()
    out.append(o)
    return out


# ------------------------------------------------------------------ upper storey
def upper_storey(c_cols, c_eave):
    out = []
    R = D.R_DRUM2
    mb = C.MB()
    annulus(mb, R - 0.12, R + 0.07, D.Z_SILL2[0], D.Z_SILL2[1], 'M_Red', segs=160)      # sill
    annulus(mb, R - 0.12, R + 0.07, D.Z_BEAM2[0], D.Z_BEAM2[1], 'M_Red', segs=160)      # beam over windows
    annulus(mb, R - 0.12, R - 0.035, D.Z_WIN2[0] - 0.005, D.Z_WIN2[1] + 0.005, 'M_WindowPanel', segs=160)   # panels (set back)
    # window frames: 2 mullions per bay + the posts, and a thin head/sill strip
    for k in range(D.N_COL):
        a0 = D.col_az(k)
        for f in (1 / 3, 2 / 3):
            a = a0 + math.radians(45) * f
            c, s = math.cos(a), math.sin(a)
            p = Vector((R * c, R * s, (D.Z_WIN2[0] + D.Z_WIN2[1]) / 2))
            mb.obox(p, (Vector((-s, c, 0)), Vector((c, s, 0)), Vector((0, 0, 1))),
                    (0.045, 0.055, (D.Z_WIN2[1] - D.Z_WIN2[0]) / 2 + 0.012), 'M_Red')
    annulus(mb, R - 0.025, R + 0.045, D.Z_WIN2[0] - 0.012, D.Z_WIN2[0] + 0.04, 'M_Red', segs=160)
    annulus(mb, R - 0.025, R + 0.045, D.Z_WIN2[1] - 0.04, D.Z_WIN2[1] + 0.012, 'M_Red', segs=160)
    out.append(mb.finish('QT_upper_windows', c_cols, recalc=True))
    # plaster band up to the wall beam (7.38)
    mb = C.MB()
    annulus(mb, R - 0.12, R + 0.03, D.Z_BEAM2[1], 7.38, 'M_Plaster', segs=160)
    out.append(mb.finish('QT_band_upper', c_eave, recalc=True))
    # engaged posts (the inner columns continuing) on the drum
    post = column_src('SRC_qt_post2', D.Z_BEAM2[1] - D.Z_SILL2[1], 0.30, 0.28)
    xf = []
    for k in range(D.N_COL):
        az = D.col_az(k)
        xf.append((((R + 0.03) * math.cos(az), (R + 0.03) * math.sin(az), D.Z_SILL2[1]), (0, 0, az), 1.0))
    out.append(C.instancer('QT_posts_upper', post, xf, c_cols))
    brk = bracket_src('SRC_qt_brk2', reach=0.48, scale=0.92)
    xf = []
    for k in range(D.N_COL):
        az = D.col_az(k)
        xf.append((((R + 0.03) * math.cos(az), (R + 0.03) * math.sin(az), D.Z_BEAM2[1]), (0, 0, az - math.pi / 2), 1.0))
    out.append(C.instancer('QT_brackets_upper', brk, xf, c_eave))
    return out


# ------------------------------------------------------------------ plaque and couplets
def _gold_hui(mb, cx, cz, y, s, m='M_GoldPaint'):
    """small 回-pattern ornament (af3b, under the plaque characters): a square spiral of thin strips."""
    w = 0.012 * s / 0.06
    pts = [(-1, -1), (1, -1), (1, 1), (-0.5, 1), (-0.5, -0.4), (0.45, -0.4), (0.45, 0.45), (0.0, 0.45)]
    for (a, b) in zip(pts, pts[1:]):
        x0, z0 = cx + a[0] * s / 2, cz + a[1] * s / 2
        x1, z1 = cx + b[0] * s / 2, cz + b[1] * s / 2
        mb.box((min(x0, x1) - w, y - 0.006, min(z0, z1) - w), (max(x0, x1) + w, y, max(z0, z1) + w), m)


def boards(c_boards):
    out = []
    # plaque on the north face of the lower bracket band, centred on the entrance bay
    w, h = D.PLAQUE_W, D.PLAQUE_H
    mb = C.MB()
    t = 0.06
    mb.box((-w / 2, -t / 2, -h / 2), (w / 2, t / 2, h / 2), 'M_BlackLacquer')
    fw = 0.035
    for (x0, x1, z0, z1) in ((-w / 2, w / 2, h / 2 - fw, h / 2), (-w / 2, w / 2, -h / 2, -h / 2 + fw),
                             (-w / 2, -w / 2 + fw, -h / 2 + fw, h / 2 - fw), (w / 2 - fw, w / 2, -h / 2 + fw, h / 2 - fw)):
        mb.box((x0, -t / 2 - 0.012, z0), (x1, t / 2 - 0.003, z1), 'M_BlackLacquer')
    for sx in (-1, 1):
        _gold_hui(mb, sx * 0.13, -h / 2 + 0.07, -t / 2, 0.055)
    plq = mb.finish('QT_plaque', c_boards, recalc=True)
    txt = PR.text_mesh('QT_plaque_text', D.PLAQUE_TEXT[::-1], 0.32, c_boards, 'M_GoldPaint', extrude=0.008, spacing=1.25)
    txt.data.transform(Matrix.Translation((0.0, -t / 2 - 0.006, 0.03)))
    az = math.pi / 2
    r = D.R_COL + 0.12
    zc = D.Z_ARCH[1] + 0.06 + h / 2
    M = Matrix.Translation((0, r, zc)) @ Matrix.Rotation(math.pi, 4, 'Z')
    for o in (plq, txt):
        o.matrix_world = M
    out += [plq, txt]
    # couplets on the two entrance columns, hung in front of them, facing outward
    entr = [(D.col_az(1), D.COUPLET_TEXT[0]), (D.col_az(0), D.COUPLET_TEXT[1])]
    # col_az(0) = 67.5 deg (east of north), col_az(1) = 112.5 deg (west of north). Seen from the stair the right
    # (west) column carries the upper line 時有落花, the left (east) column 遠聞流水 (af3b).
    for i, (az, text) in enumerate(entr):
        cw, cl = D.COUPLET_W, D.COUPLET_L
        mb = C.MB()
        t = 0.035
        mb.box((-cw / 2, -t / 2, -cl), (cw / 2, t / 2, 0.0), 'M_BlackLacquer')
        for sx in (-1, 1):       # two small gold hooks at the top
            mb.box((sx * 0.07 - 0.008, -0.004, -0.004), (sx * 0.07 + 0.008, 0.004, 0.07), 'M_GoldPaint')
        brd = mb.finish('QT_couplet_%d' % i, c_boards, recalc=True)
        ch = 0.20
        tx = PR.text_mesh('QT_couplet_%d_text' % i, text, ch, c_boards, 'M_GoldPaint', extrude=0.006, vertical=True, spacing=1.0)
        # stack of 4 characters from the top; the 5th position (bottom) stays blank
        bb = [v.co for v in tx.data.vertices]
        ztop = max(v.z for v in bb)
        tx.data.transform(Matrix.Translation((0.0, -t / 2 - 0.004, -0.17 - ztop)))
        r = D.R_COL + D.COL_D1 / 2 + 0.035
        M = Matrix.Translation((r * math.cos(az), r * math.sin(az), D.Z_FRIEZE[0] - 0.08)) @ Matrix.Rotation(az + math.pi / 2, 4, 'Z')
        for o in (brd, tx):
            o.matrix_world = M
        out += [brd, tx]
    return out
