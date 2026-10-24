# Xingyuan build library - the five halls (A1-A5).
# Hall-local frame: u = depth from the porch column line (u=0) toward the back wall (u=D),
# v = along the ridge (end column lines at v=0 and v=L), z up (floor = 0).
import bpy, math, random
from mathutils import Vector, Matrix
import xy_core as C, xy_roof as RF, xy_parts as PT, xy_site as S

HC = 3.80          # column height (hall)
UF = 2.05          # front wall line (porch depth)
B_ROOF = 8.60      # ridge to eave edge (horizontal)
H_EAVE = 4.905     # tile surface at the eave edge
H_RIDGE = 9.11     # tile surface at the ridge
OVER_V = 1.15      # roof overhang beyond the end column lines (gable ends)
LIFT, LIFT_LEN = 0.42, 5.5   # 生起: eave rise toward the gable ends (A5 photo: ~0.4 m over the end bays)
Z_COURT = -0.60

class Frame:
    def __init__(self, ox, oy, rot_deg, oz=0.0):
        self.rot = rot_deg
        self.M = Matrix.Translation((ox, oy, oz)) @ Matrix.Rotation(math.radians(rot_deg), 4, 'Z')
    def p(self, u, v, z):
        return self.M @ Vector((u, v, z))
    def xf(self, Ml):
        W = self.M @ Ml
        loc, q, s = W.decompose()
        return (tuple(loc), tuple(q.to_euler('XYZ')), tuple(s))
    def box(self, mb, u0, v0, z0, u1, v1, z1, m):
        a = self.p(u0, v0, z0); b = self.p(u1, v1, z1)
        mb.box(tuple(a), tuple(b), m)

def hall_profile():
    return RF.Profile(B_ROOF, H_EAVE, H_RIDGE)

def rafter_bottom(P, d):
    """underside of the round rafter at distance d from the eave edge"""
    return P.f(d) - 0.344

# ------------------------------------------------------------------ bay infill
def _bay(mb, F, u, va, vb, kind, side, rng, open_leaf=False, glass_bars=True):
    """Infill of one bay of a timber wall at depth u between column centres va < vb.
    side: +1 if the exterior (viewer) side is toward -u (front wall), -1 if toward +u.
    kind: 'door' | 'window'."""
    R = 'M_RedLacquer'; DR = 'M_DoorRed'; W = 'M_Plaster'; BR = 'M_Brick'; G = 'M_Glass'
    t = 0.16                      # timber depth
    a = va + 0.19; b = vb - 0.19  # clear opening between column faces
    c = (va + vb) / 2
    ua, ub = u - t / 2, u + t / 2
    ra, rb = ua + 0.004, ub - 0.004   # rails a little shallower than posts (no coplanar faces)
    # 抱框 at both column faces
    for (v0, v1) in ((a, a + 0.11), (b - 0.11, b)):
        F.box(mb, ua, v0, 0.0, ub, v1, 3.56, R)
    # 由额 + transom band + head rail
    F.box(mb, ra, a + 0.11, 3.36, rb, b - 0.11, 3.555, R)        # 由额
    F.box(mb, ra, a + 0.11, 2.72, rb, b - 0.11, 2.88, R)         # head rail (上槛)
    # transom: dark panels with red struts
    F.box(mb, u - 0.03, a + 0.11, 2.881, u + 0.03, b - 0.11, 3.359, DR)
    n = max(2, int(round((b - a) / 0.58)))
    for k in range(1, n):
        vv = a + (b - a) * k / n
        F.box(mb, ua + 0.01, vv - 0.04, 2.8805, ub - 0.01, vv + 0.04, 3.3595, R)
    if kind == 'door':
        dw = 0.86                  # leaf width
        d0, d1 = c - dw, c + dw
        # door frame posts
        F.box(mb, ra, d0 - 0.1, 0.0, rb, d0, 2.72, R)
        F.box(mb, ra, d1, 0.0, rb, d1 + 0.1, 2.72, R)
        # plaster panels between 抱框 and door frame (inset), with a low red base rail
        for (v0, v1) in ((a + 0.11, d0 - 0.1), (d1 + 0.1, b - 0.11)):
            F.box(mb, u - 0.05, v0, 0.12, u + 0.05, v1, 2.72, W)
            F.box(mb, ua + 0.01, v0, 0.0, ub - 0.01, v1, 0.12, R)
        # threshold
        F.box(mb, ra + 0.004, d0, 0.0, rb - 0.004, d1, 0.10, R)
        # leaves
        for li, (v0, v1) in enumerate(((d0 + 0.004, c - 0.002), (c + 0.002, d1 - 0.004))):
            hinge = v0 if li == 0 else v1
            ang = 0.0
            if open_leaf and li == 1:
                ang = -math.radians(72)
            _leaf(mb, F, u, v0, v1, 0.10, 2.72, hinge, ang, side)
    else:
        ww = 1.02
        w0, w1 = c - ww, c + ww
        # brick dado (槛墙) full width, slightly recessed
        F.box(mb, u - 0.12, a + 0.11, 0.0, u + 0.12, b - 0.11, 0.90, BR)
        F.box(mb, ua - 0.02, a + 0.11, 0.90, ub + 0.02, b - 0.11, 1.0, R)      # sill
        # window frame posts
        F.box(mb, ra, w0 - 0.1, 1.0, rb, w0, 2.72, R)
        F.box(mb, ra, w1, 1.0, rb, w1 + 0.1, 2.72, R)
        for (v0, v1) in ((a + 0.11, w0 - 0.1), (w1 + 0.1, b - 0.11)):
            F.box(mb, u - 0.05, v0, 1.0, u + 0.05, v1, 2.72, W)
        # 直棂: rails + square bars + glass behind
        F.box(mb, ua + 0.02, w0, 1.0, ub - 0.02, w1, 1.07, R)
        F.box(mb, ua + 0.02, w0, 2.64, ub - 0.02, w1, 2.715, R)
        nbar = int(round((w1 - w0) / 0.118))
        for k in range(1, nbar):
            vv = w0 + (w1 - w0) * k / nbar
            F.box(mb, u - 0.03 * side - 0.025, vv - 0.024, 1.07, u - 0.03 * side + 0.025, vv + 0.024, 2.64, R)
        F.box(mb, u + 0.03 * side - 0.006, w0, 1.07, u + 0.03 * side + 0.006, w1, 2.64, G)

def _leaf(mb, F, u, v0, v1, z0, z1, hinge, ang, side):
    """Door leaf (frame, lower panel, glazed upper part with bars) rotated about the hinge edge."""
    R = 'M_DoorRed'; G = 'M_Glass'
    th = 0.06
    parts = []
    w = v1 - v0
    # stiles / rails
    parts.append((0.0, 0.0, 0.085, z0, z1))
    parts.append((w - 0.085, 0.0, w, z0, z1))
    for (za, zb) in ((z0, z0 + 0.14), (0.92, 1.04), (z1 - 0.11, z1)):
        parts.append((0.085, 0.0, w - 0.085, za, zb))      # rails between the stiles
    # lower panel (thinner, recessed)
    lower = (0.085, w - 0.085, z0 + 0.14, 0.92)
    # glazing bars
    nb = 4
    bars = [0.085 + (w - 0.17) * k / nb for k in range(1, nb)]
    def place(vl, ul, z):
        # local (vl along leaf from the v0 edge, ul across thickness) -> hall (u, v)
        if ang == 0.0:
            return F.p(u + ul, v0 + vl, z)
        # rotate around hinge line
        hv = hinge - v0
        dv = vl - hv
        ca, sa = math.cos(ang), math.sin(ang)
        uu = ul * ca + dv * sa * side
        vv = -ul * sa * side + dv * ca
        return F.p(u + uu, hinge + vv, z)
    def blk(va_, vb_, ua_, ub_, za, zb, m):
        P = [place(va_, ua_, za), place(vb_, ua_, za), place(vb_, ub_, za), place(va_, ub_, za),
             place(va_, ua_, zb), place(vb_, ua_, zb), place(vb_, ub_, zb), place(va_, ub_, zb)]
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
            mb.face([P[i] for i in f], m)
    for k, (va_, ub0, vb_, za, zb) in enumerate(parts):
        e = 0.0 if k < 2 else 0.002                         # rails 2 mm thinner than stiles
        blk(va_, vb_, -th / 2 + e, th / 2 - e, za, zb, R)
    blk(lower[0], lower[1], -0.018, 0.018, lower[2] + 0.001, lower[3] - 0.001, R)
    blk(lower[0] + 0.07, lower[1] - 0.07, -0.025, 0.025, lower[2] + 0.08, lower[3] - 0.08, R)
    blk(0.086, w - 0.086, -0.006, 0.006, 1.041, z1 - 0.111, G)
    for bv in bars:
        blk(bv - 0.018, bv + 0.018, -0.022, 0.022, 1.0405, z1 - 0.1105, R)

# ------------------------------------------------------------------ gable end (山面)
def _gable(mb, F, P, D, v_face, out_sign, rng, roof_z=None):
    """Brick gable wall + timber gable frame with window band, tie beam, 叉手 and red tympanum.
    v_face: wall outer face; out_sign: -1 if the exterior is toward -v.
    roof_z(u, v): actual tile-surface height (incl. eave lift); everything stays under its soffit."""
    R = 'M_RedLacquer'; W = 'M_Plaster'; BR = 'M_Brick'; G = 'M_Paper'
    uc = D / 2
    def soffit(u):
        if roof_z is not None:
            return roof_z(u, v_face) - 0.225
        return P.f(B_ROOF - abs(u - uc)) - 0.225
    vin = v_face - out_sign * 0.60           # inner face of the wall
    va, vb = (v_face, vin) if out_sign < 0 else (vin, v_face)
    # brick wall from the porch column line to the back (stone plinth), with a stone-framed door at the porch end
    du0, du1, dh = 0.50, 1.62, 2.55        # porch-end doorway (u range, height)
    F.box(mb, du1 + 0.06, va, 0.0, D + 0.3, vb, 0.45, 'M_Granite')
    F.box(mb, du1 + 0.06, va + 0.02, 0.45, D + 0.25, vb - 0.02, 4.45, BR)
    F.box(mb, -0.28, va, 0.0, du0 - 0.06, vb, 0.45, 'M_Granite')
    F.box(mb, -0.28, va + 0.02, 0.45, du0 - 0.06, vb - 0.02, 4.45, BR)
    F.box(mb, du0, va + 0.02, dh + 0.18, du1, vb - 0.02, 4.45, BR)
    for (a0, a1, z0, z1) in ((du0 - 0.16, du0, 0.0, dh + 0.16), (du1, du1 + 0.16, 0.0, dh + 0.16), (du0 - 0.16, du1 + 0.16, dh, dh + 0.18)):
        F.box(mb, a0, va - 0.035, z0, a1, vb + 0.035, z1, 'M_Granite')
    F.box(mb, du0, va + 0.05, 0.0, du1, vb - 0.05, 0.06, 'M_Granite')       # threshold
    # timber gable frame in the outer plane
    vo = v_face + out_sign * 0.02            # slightly proud of the wall face
    vi = v_face - out_sign * 0.10
    v0, v1 = (vo, vi) if out_sign < 0 else (vi, vo)
    def clipped_band(u0, u1, z0, z1, vv0, vv1, m, n=8):
        """box from u0..u1, z0..z1 whose top follows min(z1, soffit(u)) (sampled in n slices)"""
        for k in range(n):
            a = u0 + (u1 - u0) * k / n; b = u0 + (u1 - u0) * (k + 1) / n
            top = min(z1, soffit(a), soffit(b))
            if top - z0 > 0.02:
                F.box(mb, a, vv0, z0, b, vv1, top, m)
    # sill beam across the whole gable at 4.45-4.62
    clipped_band(-0.15, D + 0.15, 4.45, 4.62, v0, v1, R, n=1)
    # window band 4.62-5.98 : panes between mullions (inner part only)
    ua, ub = UF - 0.05, D - UF + 0.05
    mull = [ua, ua + 1.35, ub - 1.35, ub]
    F.box(mb, ua - 0.06, v0, 5.98, ub + 0.06, v1, 6.12, R)   # band head
    for mu in mull:
        F.box(mb, mu - 0.07, v0, 4.62, mu + 0.07, v1, 5.98, R)
    pv0, pv1 = sorted((v_face - out_sign * 0.01, v_face - out_sign * 0.03))
    for (p0, p1) in ((mull[0], mull[1]), (mull[1], mull[2]), (mull[2], mull[3])):
        F.box(mb, p0 + 0.07, pv0, 4.62, p1 - 0.07, pv1, 5.98, G)
    # outer ends of the gable above the sill (porch end and back end): white plaster up to the roof
    vpw0, vpw1 = sorted((v_face - out_sign * 0.005, v_face - out_sign * 0.09))
    clipped_band(-0.15, mull[0] - 0.07, 4.62, 9.0, vpw0, vpw1, W, n=10)
    clipped_band(mull[3] + 0.07, D + 0.15, 4.62, 9.0, vpw0, vpw1, W, n=10)
    # tie beam (四椽栿 end) 6.12-6.5 only where it fits under the roof
    tb = [u for u in [k * 0.05 for k in range(int(D / 0.05) + 1)] if soffit(u) > 6.55]
    tb0, tb1 = (min(tb), max(tb)) if tb else (uc - 2.5, uc + 2.5)
    F.box(mb, tb0, v0, 6.12, tb1, v1, 6.50, R)
    # red tympanum: from the band head / tie beam up to the soffit, between the plaster ends
    N = 28
    us = [mull[0] - 0.07 + (mull[3] - mull[0] + 0.14) * i / N for i in range(N + 1)]
    vpl = v_face - out_sign * 0.03
    for i in range(N):
        u0_, u1_ = us[i], us[i + 1]
        zf = 6.5 if (u0_ >= tb0 - 1e-6 and u1_ <= tb1 + 1e-6) else 6.12
        z0_, z1_ = soffit(u0_), soffit(u1_)
        if max(z0_, z1_) <= zf + 0.01:
            continue
        mb.face([F.p(u0_, vpl, zf), F.p(u1_, vpl, zf), F.p(u1_, vpl, max(z1_, zf)), F.p(u0_, vpl, max(z0_, zf))], 'M_RedPaint')
    # 叉手 (inverted-V struts) from the tie beam ends up to under the ridge purlin
    zt = soffit(uc) - 0.05
    for su in (-1, 1):
        ub0 = uc + su * min(3.1, (tb1 - tb0) / 2 - 0.2)
        p0 = (ub0, 6.5); p1 = (uc + su * 0.18, zt - 0.1)
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        cu, cz = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        hu, hz = L / 2, 0.11
        du, dz = math.cos(ang), math.sin(ang)
        nu, nz = -dz, du
        corners = [(cu - du * hu - nu * hz, cz - dz * hu - nz * hz), (cu + du * hu - nu * hz, cz + dz * hu - nz * hz),
                   (cu + du * hu + nu * hz, cz + dz * hu + nz * hz), (cu - du * hu + nu * hz, cz - dz * hu + nz * hz)]
        A_ = [F.p(cc[0], v0, cc[1]) for cc in corners]
        B_ = [F.p(cc[0], v1, cc[1]) for cc in corners]
        mb.face(A_, R); mb.face(list(reversed(B_)), R)
        for i in range(4):
            j = (i + 1) % 4
            mb.face([A_[i], A_[j], B_[j], B_[i]], R)
    # short king post (蜀柱) under the ridge
    F.box(mb, uc - 0.12, v0, 6.5, uc + 0.12, v1, zt, R)

# ------------------------------------------------------------------ main builder
def build_hall(key, ox, oy, rot, D, L, nb, front_doors, back_doors=(), open_bay=None, seed=1):
    """Build one hall into collection `key`."""
    rng = random.Random(seed)
    C.clear_coll(key)
    top = C.coll(key)
    c_wood = C.coll(key + ' 木构', top)
    c_wall = C.coll(key + ' 墙体门窗', top)
    c_roof = C.coll(key + ' 屋面', top)
    F = Frame(ox, oy, rot)
    P = hall_profile()
    bay = L / nb
    vs = [i * bay for i in range(nb + 1)]

    # (platform, curbs and paving come from the site-wide floor in xy_build_site)

    # ---------- columns + bases + brackets (instances)
    col_src = PT.column_src('SRC_col_hall', HC + 0.02, r0=0.235, r1=0.21)
    base_src = PT.base_src()
    bo = PT.bracket_outer_src()
    bi = PT.bracket_inner_src()
    cols, bases, brk_o, brk_i = [], [], [], []
    rows = [(0.0, 'porch'), (UF, 'front'), (D, 'back')]
    for (u, kind) in rows:
        for j, v in enumerate(vs):
            Ml = Matrix.Translation((u, v, 0.0))
            bases.append(F.xf(Ml))
            Mc = Matrix.Translation((u, v, 0.15)) @ Matrix.Diagonal((1, 1, (HC - 0.15) / (HC + 0.02), 1))
            cols.append(F.xf(Mc))
            if kind == 'porch':
                # outward = -u : local +Y -> -u  => rotate +90 about Z
                brk_o.append(F.xf(Matrix.Translation((u, v, HC)) @ Matrix.Rotation(math.radians(90), 4, 'Z')))
            elif kind == 'back':
                brk_o.append(F.xf(Matrix.Translation((u, v, HC)) @ Matrix.Rotation(math.radians(-90), 4, 'Z')))
            else:
                brk_i.append(F.xf(Matrix.Translation((u, v, HC)) @ Matrix.Rotation(math.radians(90), 4, 'Z')))
    # intermediate (补间) sets at mid-bay on the porch and back lines: block on the 阑额 + simple bracket
    brk_m = []
    for (u, kind) in rows:
        if kind == 'front':
            continue
        for j in range(nb):
            vm = (vs[j] + vs[j + 1]) / 2
            rz = 90 if kind == 'porch' else -90
            brk_m.append(F.xf(Matrix.Translation((u, vm, HC + 0.17)) @ Matrix.Rotation(math.radians(rz), 4, 'Z')))
    C.instancer(key + '_柱', col_src, cols, c_wood)
    C.instancer(key + '_柱础', base_src, bases, c_wood)
    C.instancer(key + '_斗栱_外檐', bo, brk_o, c_wood)
    C.instancer(key + '_斗栱_内', bi, brk_i, c_wood)
    C.instancer(key + '_斗栱_补间', bi, brk_m, c_wood)

    # ---------- beams, purlins, porch ceiling, crescent beams
    mb = C.MB()
    R = 'M_RedLacquer'
    for (u, kind) in rows:
        F.box(mb, u - 0.09, vs[0] - 0.05, HC - 0.26, u + 0.09, vs[-1] + 0.05, HC - 0.02, R)          # 阑额
        if kind in ('porch', 'back'):
            # 驼峰 blocks under the intermediate brackets
            for j in range(nb):
                vm = (vs[j] + vs[j + 1]) / 2
                F.box(mb, u - 0.08, vm - 0.20, HC - 0.02, u + 0.08, vm + 0.20, HC + 0.17, R)
        if kind == 'porch':
            # 由额 0.5 m below the 阑额 with short struts between (open frieze, as in the photos)
            F.box(mb, u - 0.075, vs[0] + 0.2, HC - 0.70, u + 0.075, vs[-1] - 0.2, HC - 0.53, R)
            for j in range(nb):
                n_s = 4
                for k in range(1, n_s):
                    vv = vs[j] + (vs[j + 1] - vs[j]) * k / n_s
                    F.box(mb, u - 0.055, vv - 0.05, HC - 0.53, u + 0.055, vv + 0.05, HC - 0.26, R)
        if kind in ('porch', 'back'):
            F.box(mb, u - 0.065, vs[0] - 0.36, HC + 0.62, u + 0.065, vs[-1] + 0.36, HC + 0.80, R)  # 柱头方
            F.box(mb, u - 0.065, vs[0] - 0.36, HC + 0.86, u + 0.065, vs[-1] + 0.36, HC + 1.04, R)  # 2nd 方
        else:
            F.box(mb, u - 0.065, vs[0] - 0.3, HC + 0.38, u + 0.065, vs[-1] + 0.3, HC + 0.56, R)
    # eave purlins (撩檐槫) on the outer bracket ends
    for (u_line, sgn) in ((0.0, -1), (D, 1)):
        u_p = u_line + sgn * 0.93
        d_p = B_ROOF - abs(u_p - D / 2)
        zb = HC + 0.98
        zt = rafter_bottom(P, d_p)
        r = max(0.1, (zt - zb) / 2)
        pa = F.p(u_p, -OVER_V + 0.08, zb + r); pb = F.p(u_p, L + OVER_V - 0.08, zb + r)
        mb.cyl(pa, pb, r, 16, R)
        # 撩檐方 strip under the purlin between brackets (continuous)
    # porch: crescent beams (乳栿) and coffered ceiling
    zc = HC + 0.80
    for v in vs:
        # 月梁: 0.30 tall, arched underside, built as a closed strip of slices
        N = 10
        bot = []; tp = []
        for i in range(N + 1):
            t = i / N
            uu = -0.05 + (UF + 0.1) * t
            arch = 0.07 * math.sin(math.pi * t)
            bot.append((uu, HC + 0.16 + arch))
            tp.append((uu, HC + 0.46))
        for i in range(N):
            (ua_, za_), (ub_, zb_) = bot[i], bot[i + 1]
            (_, zta), (_, ztb) = tp[i], tp[i + 1]
            for vv in (v - 0.1, v + 0.1):
                mb.face([F.p(ua_, vv, za_), F.p(ub_, vv, zb_), F.p(ub_, vv, ztb), F.p(ua_, vv, zta)], R)
            mb.face([F.p(ua_, v - 0.1, za_), F.p(ua_, v + 0.1, za_), F.p(ub_, v + 0.1, zb_), F.p(ub_, v - 0.1, zb_)], R)
            mb.face([F.p(ua_, v - 0.1, zta), F.p(ub_, v - 0.1, ztb), F.p(ub_, v + 0.1, ztb), F.p(ua_, v + 0.1, zta)], R)
        for (uu, zb_, zt_) in ((bot[0][0], bot[0][1], tp[0][1]), (bot[-1][0], bot[-1][1], tp[-1][1])):
            mb.face([F.p(uu, v - 0.1, zb_), F.p(uu, v + 0.1, zb_), F.p(uu, v + 0.1, zt_), F.p(uu, v - 0.1, zt_)], R)
    mb.finish(key + '_梁枋', c_wood, merge=0.0005)

    # coffered ceiling of the porch (board + rib grid)
    mb = C.MB()
    F.box(mb, 0.10, vs[0] - 0.1, zc + 0.02, UF - 0.05, vs[-1] + 0.1, zc + 0.05, 'M_CeilRib')
    nu = 3
    ribs_u = [0.1 + (UF - 0.15) * k / nu for k in range(nu + 1)]
    for uu in ribs_u:
        F.box(mb, uu - 0.035, vs[0] - 0.1, zc - 0.06, uu + 0.035, vs[-1] + 0.1, zc + 0.02, 'M_CeilRib')
    ribs_v = []
    for i in range(nb):
        nvb = max(1, int(round((vs[i + 1] - vs[i]) / 0.56)))
        for k in range(nvb):
            ribs_v.append(vs[i] + (vs[i + 1] - vs[i]) * k / nvb)
    ribs_v.append(vs[-1])
    for vv in ribs_v:
        F.box(mb, 0.10, vv - 0.035, zc - 0.055, UF - 0.05, vv + 0.035, zc + 0.019, 'M_CeilRib')
    panels = []
    for a in range(nu):
        for b in range(len(ribs_v) - 1):
            u0_, u1_ = ribs_u[a] + 0.035, ribs_u[a + 1] - 0.035
            v0_, v1_ = ribs_v[b] + 0.035, ribs_v[b + 1] - 0.035
            f = mb.face([F.p(u0_, v0_, zc + 0.015), F.p(u0_, v1_, zc + 0.015), F.p(u1_, v1_, zc + 0.015), F.p(u1_, v0_, zc + 0.015)],
                        'M_CeilPanel')
            if f is not None:
                panels.append(f)
    uvl = mb.uv
    oc = mb.finish(key + '_平棊', c_wood)
    # per-panel 0..1 UVs (the box-projection done in finish() is overwritten for the panel faces)
    me = oc.data
    pidx = me.materials.find('M_CeilPanel')
    uvd = me.uv_layers['UVMap'].data
    for poly in me.polygons:
        if poly.material_index == pidx:
            for li, (uu, vv) in zip(poly.loop_indices, ((0, 0), (0, 1), (1, 1), (1, 0))):
                uvd[li].uv = (uu, vv)

    # ---------- walls: front (doors / windows), back (windows), gables
    mb = C.MB()
    for i in range(nb):
        kind = 'door' if i in front_doors else 'window'
        _bay(mb, F, UF, vs[i], vs[i + 1], kind, +1, rng, open_leaf=(open_bay == i))
        kind = 'door' if i in back_doors else 'window'
        _bay(mb, F, D, vs[i], vs[i + 1], kind, -1, rng)
    # plaster (栱眼壁) between brackets above the 阑额, in all three rows, up to the 柱头方 / roof
    for (u, kind) in rows:
        if kind == 'front':
            F.box(mb, u - 0.04, vs[0], HC - 0.02, u + 0.04, vs[-1], HC + 0.38, 'M_PanelDark')
        else:
            F.box(mb, u - 0.04, vs[0], HC - 0.02, u + 0.04, vs[-1], HC + 0.62, 'M_PanelDark')
    # back wall above the second 方 up to the roof soffit (closing the eave cavity)
    zt_back = P.f(B_ROOF - (D - D / 2)) - 0.22
    F.box(mb, D - 0.04, vs[0] - 0.3, HC + 1.04, D + 0.04, vs[-1] + 0.3, zt_back + 0.05, 'M_Plaster')
    # porch side: closing board above the ceiling up to the roof (hidden mostly)
    zt_front = P.f(B_ROOF - D / 2) - 0.22
    F.box(mb, -0.04, vs[0] - 0.3, HC + 1.04, 0.04, vs[-1] + 0.3, zt_front + 0.05, 'M_RedOrange')
    # gables (clipped to the real roof surface incl. the eave lift)
    shape_g = RF.RoofShape('gable', L / 2 + OVER_V, B_ROOF, P, lift=LIFT, lift_len=LIFT_LEN)
    roof_z = lambda u, v: shape_g.z(v - L / 2, D / 2 - u)
    _gable(mb, F, P, D, -0.30, -1, rng, roof_z)
    _gable(mb, F, P, D, L + 0.30, +1, rng, roof_z)
    # interior: dark ceiling and back faces so open doors read as a dim room
    F.box(mb, UF + 0.15, 0.3, 4.40, D - 0.15, L - 0.3, 4.45, 'M_Interior')
    mb.finish(key + '_墙体门窗', c_wall)

    # ---------- roof
    shape = RF.RoofShape('gable', L / 2 + OVER_V, B_ROOF, P, lift=LIFT, lift_len=LIFT_LEN)
    # roof local (x along ridge, y across) -> hall: u = -y + D/2, v = x + L/2
    M_hr = Matrix(((0, -1, 0, D / 2), (1, 0, 0, L / 2), (0, 0, 1, 0), (0, 0, 0, 1)))
    M = F.M @ M_hr
    RF.place_tiles(key + '_瓦', shape, M, ['S', 'N'], c_roof)
    RF.deck(key + '_望板', shape, M, c_roof, t_top=0.055, t_sof=0.22, soffit_step=(1.15, 0.075))
    # rafters as instances (follow the eave lift near the gable ends)
    import xy_frame as FRM
    A = L / 2 + OVER_V
    FRM.rafters_inst(key, c_roof, shape, M, P, ['S', 'N'], d_in=2.95, src_name='SRC_rafter_hall',
                     fly_back=1.15, fly_len=0.62, r_round=0.062, sq=(0.10, 0.115))
    RF.eave_boards(key + '_连檐', shape, M, c_roof, ['S', 'N'])
    zr = P.f(B_ROOF)
    RF.main_ridge(key + '_正脊', M, -A + 0.12, A - 0.12, zr - 0.06, c_roof, horn=0.85, horn_len=1.25, vscale=1.62)
    for xs in (-A + 0.07, A - 0.07):
        RF.verge_ridge(key + '_排山', M, shape, xs, c_roof)
    for xs in (-A + 0.03, A - 0.03):
        RF.bargeboard(key + '_博风', M, shape, xs, c_roof, depth=0.52, thick=0.07, top_off=-0.02, flare=0.30)
    # 悬鱼 at both gables
    for sgn in (-1, 1):
        pw = F.p(D / 2, (L / 2) + sgn * (A - 0.03), zr - 0.42)
        RF.xuanyu(key + '_悬鱼', tuple(pw), 'y' if F.rot in (0, 180) else 'x', c_roof, w=0.95, h=1.15, thick=0.06)
    return top
