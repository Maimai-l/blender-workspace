# Xingyuan build library - generic timber-frame pieces in world coordinates (axis-aligned layouts):
# columns, beams, brackets, railings, wall bays, generic roofs for corridors and pavilions.
import bpy, math, random
from mathutils import Vector, Matrix
import xy_core as C, xy_roof as RF, xy_parts as PT

RED = 'M_RedLacquer'

def inst_xf(x, y, z, rz=0.0, s=1.0):
    return ((x, y, z), (0.0, 0.0, rz), s)

class Frame:
    """Collects instance transforms + one MB for unique geometry, then finishes into a collection."""
    def __init__(self, name, coll):
        self.name, self.coll = name, coll
        self.mb = C.MB()
        self.inst = {}            # src name -> list of transforms
    def add(self, src, xf):
        self.inst.setdefault(src.name, (src, []))[1].append(xf)
    def box(self, x0, y0, z0, x1, y1, z1, m=RED):
        self.mb.box((x0, y0, z0), (x1, y1, z1), m)
    def beam(self, p, q, z0, z1, w, m=RED):
        (x0, y0), (x1, y1) = p, q
        if abs(y1 - y0) < 1e-6:
            self.box(min(x0, x1), y0 - w / 2, z0, max(x0, x1), y0 + w / 2, z1, m)
        else:
            # y-beams 3 mm shallower/narrower so crossings never share a face plane
            self.box(x0 - w / 2 + 0.003, min(y0, y1), z0 + 0.003, x0 + w / 2 - 0.003, max(y0, y1), z1 - 0.003, m)
    def finish(self):
        objs = []
        if len(self.mb.bm.faces):
            objs.append(self.mb.finish(self.name + '_构件', self.coll))
        else:
            self.mb.bm.free()
        for key, (src, lst) in self.inst.items():
            short = key.replace('SRC_', '')
            objs.append(C.instancer('%s_%s' % (self.name, short), src, lst, self.coll))
        return objs

# ------------------------------------------------------------------ columns etc.
def columns(fr, pts, H, src_name, r0=0.15, r1=0.135, base='SRC_base_plain', base_r=0.27):
    src = PT.column_src(src_name, H, r0, r1, segs=16)
    bsrc = PT.base_plain_src(base, base_r) if base == 'SRC_base_plain' else PT.base_src()
    for (x, y) in pts:
        fr.add(src, inst_xf(x, y, 0.0))
        fr.add(bsrc, inst_xf(x, y, 0.0))

def bracket(fr, src, x, y, z, out_dir):
    """out_dir: (dx, dy) unit-ish vector the bracket projects toward (local +Y)."""
    ang = math.atan2(out_dir[1], out_dir[0]) - math.pi / 2
    fr.add(src, inst_xf(x, y, z, ang))

# ------------------------------------------------------------------ railing (寻杖栏杆)
def railing(fr, p, q, z=0.0, h=0.82, post_h=1.0, posts=True, m=RED):
    """Railing from p to q (axis aligned) standing on z."""
    (x0, y0), (x1, y1) = p, q
    L = math.hypot(x1 - x0, y1 - y0)
    if L < 0.2:
        return
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    def seg_box(a, b, z0, z1, w):
        xa, ya = x0 + ux * a, y0 + uy * a
        xb, yb = x0 + ux * b, y0 + uy * b
        fr.beam((xa, ya), (xb, yb), z + z0, z + z1, w, m)
    seg_box(0.0, L, 0.0, 0.10, 0.10)          # 地栿
    seg_box(0.0, L, 0.42, 0.48, 0.09)         # 盆唇
    seg_box(0.0, L, h - 0.06, h, 0.075)       # 寻杖
    # dense balusters between 地栿 and 盆唇
    bal = PT.baluster_src('SRC_baluster', h=0.32)
    n = max(2, int(L / 0.075))
    for k in range(1, n):
        a = L * k / n
        fr.add(bal, inst_xf(x0 + ux * a, y0 + uy * a, z + 0.10, math.atan2(uy, ux)))
    # small posts (蜀柱) between 盆唇 and 寻杖
    n2 = max(1, int(round(L / 0.65)))
    for k in range(1, n2):
        a = L * k / n2
        xa, ya = x0 + ux * a, y0 + uy * a
        fr.box(xa - 0.03, ya - 0.03, z + 0.48, xa + 0.03, ya + 0.03, z + h - 0.06, m)
    if posts:
        ps = PT.post_src('SRC_rail_post', h=post_h)
        fr.add(ps, inst_xf(x0 + ux * 0.06, y0 + uy * 0.06, z))
        fr.add(ps, inst_xf(x1 - ux * 0.06, y1 - uy * 0.06, z))

# ------------------------------------------------------------------ wall bay (generic, world)
def wall_bay(fr, p, q, kind, out, z_top=2.0, dado=0.75, win=(0.95, 1.75), ww=None, door_w=1.2, door_h=2.3,
             open_door=False, plaster='M_Plaster', brick='M_Brick', t=0.24):
    """Infill between columns at p and q (axis aligned). out: (nx, ny) exterior normal.
    kind: 'window' | 'door' | 'plain' | 'opening'"""
    (x0, y0), (x1, y1) = p, q
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    a, b = 0.15, L - 0.15
    def span(a_, b_, z0, z1, d0, d1, m):
        # d measured along the outward normal from the wall axis
        xa, ya = x0 + ux * a_ + out[0] * d0, y0 + uy * a_ + out[1] * d0
        xb, yb = x0 + ux * b_ + out[0] * d1, y0 + uy * b_ + out[1] * d1
        fr.box(min(xa, xb), min(ya, yb), z0, max(xa, xb), max(ya, yb), z1, m)
    h = t / 2
    # posts (抱框) and head beam
    span(a, a + 0.1, 0.0, z_top, -0.08, 0.08, RED)
    span(b - 0.1, b, 0.0, z_top, -0.08, 0.08, RED)
    c = L / 2
    if kind == 'plain':
        span(a + 0.1, b - 0.1, 0.0, dado - 0.03, -h, h, brick)
        span(a + 0.1, b - 0.1, dado + 0.03, z_top, -h + 0.02, h - 0.02, plaster)
        span(a + 0.1, b - 0.1, dado - 0.04, dado + 0.04, -h - 0.01, h + 0.01, RED)
        return
    if kind == 'window':
        w = ww if ww is not None else min(1.4, (b - a) - 0.6)
        w0, w1 = c - w / 2, c + w / 2
        span(a + 0.1, b - 0.1, 0.0, win[0] - 0.03, -h, h, brick)
        span(a + 0.1, b - 0.1, win[0] - 0.06, win[0], -h - 0.02, h + 0.02, RED)
        span(a + 0.1, w0 - 0.08, win[0] + 0.003, z_top, -h + 0.02, h - 0.02, plaster)
        span(w1 + 0.08, b - 0.1, win[0] + 0.003, z_top, -h + 0.02, h - 0.02, plaster)
        span(w0, w1, win[1] + 0.084, z_top, -h + 0.02, h - 0.02, plaster)
        span(w0 - 0.08, w0, win[0], win[1] + 0.08, -0.07, 0.07, RED)
        span(w1, w1 + 0.08, win[0], win[1] + 0.08, -0.07, 0.07, RED)
        span(w0 - 0.08, w1 + 0.08, win[1], win[1] + 0.08, -0.07, 0.07, RED)
        nb = max(3, int(round(w / 0.11)))
        for k in range(1, nb):
            s = w0 + w * k / nb
            span(s - 0.022, s + 0.022, win[0], win[1], 0.01, 0.055, RED)
        span(w0, w1, win[0], win[1], -0.03, -0.018, 'M_Glass')
        return
    if kind in ('door', 'opening'):
        d0, d1 = c - door_w / 2, c + door_w / 2
        span(a + 0.1, d0 - 0.08, 0.35, z_top, -h, h, plaster)
        span(d1 + 0.08, b - 0.1, 0.35, z_top, -h, h, plaster)
        span(a + 0.1, d0 - 0.08, 0.0, 0.35, -h - 0.01, h + 0.01, brick)
        span(d1 + 0.08, b - 0.1, 0.0, 0.35, -h - 0.01, h + 0.01, brick)
        span(d0, d1, door_h + 0.104, z_top, -h + 0.02, h - 0.02, plaster)
        span(d0 - 0.08, d0, 0.0, door_h + 0.08, -0.09, 0.09, RED)
        span(d1, d1 + 0.08, 0.0, door_h + 0.08, -0.09, 0.09, RED)
        span(d0 - 0.08, d1 + 0.08, door_h, door_h + 0.1, -0.09, 0.09, RED)
        if kind == 'door':
            lw = door_w / 2
            for li, (s0, s1) in enumerate(((d0, d0 + lw), (d0 + lw, d1))):
                if open_door:
                    continue
                span(s0 + 0.004, s1 - 0.004, 0.06, door_h, -0.035, 0.035, 'M_DoorRed')
                for zz in (0.5, 1.3, 2.0):
                    span(s0 + 0.06, s1 - 0.06, zz, zz + 0.06, 0.03, 0.05, 'M_DoorRed')
        return

# ------------------------------------------------------------------ generic roof (corridor / pavilion)
def roof(name, coll, kind, cx, cy, A, B, z_eave, z_ridge, along='x', xg=None, lift=0.0, lift_len=1.6,
         ridge='main', horn=0.25, horn_len=0.55, gables=(True, True), rafters=True, d_in=None,
         barge=True, xuanyu=True, fins=None, ridge_scale=0.75, finial=None, deck_sof=0.205, d_cap=None, tympanum=False):
    """Build a roof (tiles, deck, rafters, eave boards, ridges, bargeboards) and return the RoofShape and M."""
    P = RF.Profile(B, z_eave, z_ridge)
    shape = RF.RoofShape(kind, A, B, P, xg=xg, lift=lift, lift_len=lift_len, d_cap=d_cap)
    M = Matrix.Translation((cx, cy, 0.0))
    if along == 'y':
        M = M @ Matrix.Rotation(math.radians(90), 4, 'Z')
    faces = ['S', 'N'] if kind == 'gable' else ['S', 'N', 'E', 'W']
    RF.place_tiles(name + '_瓦', shape, M, faces, coll)
    RF.deck(name + '_望板', shape, M, coll, t_top=0.055, t_sof=deck_sof, soffit_step=(0.9, 0.075) if B > 2.5 else None)
    if rafters:
        rafters_inst(name, coll, shape, M, P, faces, d_in=d_in)
    RF.eave_boards(name + '_连檐', shape, M, coll, faces)
    zr = P.f(B)
    if kind == 'gable':
        RF.main_ridge(name + '_正脊', M, -A + 0.1, A - 0.1, zr - 0.05, coll, horn=horn, horn_len=horn_len, scale=ridge_scale)
        for i, xs in enumerate((-A + 0.06, A - 0.06)):
            if gables[i]:
                RF.verge_ridge(name + '_排山', M, shape, xs, coll, r=0.08)
                if barge:
                    RF.bargeboard(name + '_博风', M, shape, xs + (0.03 if xs < 0 else -0.03), coll, depth=min(0.45, 0.16 * B + 0.1),
                                  thick=0.06, top_off=-0.02, flare=0.25 if B > 2 else 0.12)
                if tympanum:
                    gable_board(name, coll, shape, M, xs - (0.10 if xs > 0 else -0.10), z_floor=tympanum)
                if xuanyu:
                    pw = M @ Vector((xs + (0.03 if xs < 0 else -0.03), 0, zr - 0.30))
                    RF.xuanyu(name + '_悬鱼', tuple(pw), 'x' if along == 'x' else 'y', coll, w=0.6 * min(1.0, B / 3), h=0.75 * min(1.0, B / 3), thick=0.05)
    elif kind == 'xieshan':
        RF.main_ridge(name + '_正脊', M, -xg - 0.15, xg + 0.15, zr - 0.05, coll, horn=horn, horn_len=horn_len, scale=ridge_scale)
        zg = P.f(A - xg)
        for sx in (-1, 1):
            gable_triangle(name, coll, shape, M, P, sx * xg, B, zg, zr)
            for sy in (-1, 1):
                RF.hip_ridge(name + '_戗脊', M, shape, (sx, sy), coll, A - xg - 0.05)
    else:
        # hip / pyramid
        dtop = (shape.d_cap - 0.1) if shape.d_cap else (B - 0.05)
        for sx in (-1, 1):
            for sy in (-1, 1):
                RF.hip_ridge(name + '_戗脊', M, shape, (sx, sy), coll, dtop)
        if shape.d_cap:
            return shape, M, P
        if A - B > 0.2:
            RF.main_ridge(name + '_正脊', M, -(A - B) - 0.1, (A - B) + 0.1, zr - 0.05, coll, horn=horn * 0.6, horn_len=0.4, scale=ridge_scale)
        if finial:
            RF.finial(name + '_宝顶', tuple(M @ Vector((0, 0, zr - 0.08))), coll, scale=finial)
    return shape, M, P

def gable_triangle(name, coll, shape, M, P, xg_signed, B, zg, zr):
    """歇山 gable (山花) at local x = xg_signed: plaster triangle + 博风 + 悬鱼."""
    mb = C.MB()
    N = 16
    sx = 1 if xg_signed > 0 else -1
    pts = []
    for i in range(N + 1):
        y = -B + 2 * B * i / N
        z = shape.P.f(B - abs(y))
        pts.append((y, max(z, zg)))
    # plaster triangle slightly inside the gable plane
    xin = xg_signed - sx * 0.05
    poly = [(y, z - 0.08) for (y, z) in pts if z - 0.08 > zg]
    if len(poly) >= 2:
        base = [M @ Vector((xin, poly[0][0], zg)), M @ Vector((xin, poly[-1][0], zg))]
        for i in range(len(poly) - 1):
            (y0, z0), (y1, z1) = poly[i], poly[i + 1]
            mb.face([M @ Vector((xin, y0, zg)), M @ Vector((xin, y1, zg)), M @ Vector((xin, y1, z1)), M @ Vector((xin, y0, z0))], 'M_RedPaint')
    mb.finish(name + '_山花', coll)
    dg = _d_at(shape, zg)
    RF.bargeboard(name + '_博风', M, shape, xg_signed + sx * 0.02, coll, depth=0.30, thick=0.05, top_off=-0.02, flare=0.0,
                  d_min=dg, d_max=B)
    RF.verge_ridge(name + '_垂脊', M, shape, xg_signed - sx * 0.05, coll, d0=dg, d1=B, r=0.075)
    pw = M @ Vector((xg_signed + sx * 0.04, 0, zr - 0.2))
    RF.xuanyu(name + '_悬鱼', tuple(pw), 'x' if abs(M[0][0]) > 0.5 else 'y', coll, w=0.42, h=0.55, thick=0.05)

def _d_at(shape, z):
    """distance from eave where the profile reaches height z"""
    lo, hi = 0.0, shape.B
    for _ in range(30):
        mid = (lo + hi) / 2
        if shape.P.f(mid) < z:
            lo = mid
        else:
            hi = mid
    return lo

def rafters_inst(name, coll, shape, M, P, faces, d_in=None, spacing=0.30, src_name=None, fly_back=None, fly_len=None,
                 r_round=0.05, sq=(0.085, 0.10)):
    """Rafter-pair instances along the eaves (straight parts), tilted to follow the eave lift."""
    A, B = shape.A, shape.B
    d_in = d_in if d_in is not None else min(B - 0.1, 1.6)
    src_name = src_name or ('SRC_rafter_%s' % name)
    src = bpy.data.objects.get(src_name)
    if src is None:
        src = PT.rafter_pair_src(src_name, lambda d: P.f(d) - P.f(0), d_in=d_in,
                                 fly_back=fly_back if fly_back else min(0.9, d_in * 0.6),
                                 fly_len=fly_len if fly_len else min(0.55, d_in * 0.4), r_round=r_round, sq=sq)
    R3 = M.to_3x3()
    tr = []
    for face in faces:
        half = A if face in 'SN' else B
        if shape.kind == 'gable':
            lim = half - 0.12
        else:
            lim = half - 0.35
        n = int(2 * lim / spacing)
        for k in range(n + 1):
            c = -lim + 2 * lim * k / n
            if shape.kind != 'gable':
                # keep away from the hip lines: rafters near corners get shorter fans
                other = B if face in 'SN' else A
                if half - abs(c) < 0.25:
                    continue
            pts = RF._row_points(shape, face, c, 0.0, 0.0, 1)
            p0 = pts[0][0]
            dn = RF._downhill(face)
            # tilt to follow the corner lift
            p1 = RF._row_points(shape, face, c, d_in, d_in, 1)[0][0]
            extra = (p1.z - p0.z) - (P.f(d_in) - P.f(0))
            tilt = math.atan2(extra, d_in)
            # local frame: rafter +Y must point along downhill (outward)
            ang = math.atan2(dn.y, dn.x) - math.pi / 2
            Ml = Matrix.Translation(p0) @ Matrix.Rotation(ang, 4, 'Z') @ Matrix.Rotation(-tilt, 4, 'X')
            # skip rafters that would cross the hip line near the corners
            if shape.kind != 'gable' and (half - abs(c)) < d_in + 0.1:
                continue
            W = M @ Ml
            loc, q, s = W.decompose()
            tr.append((tuple(loc), tuple(q.to_euler('XYZ')), tuple(s)))
    C.instancer(name + '_椽', src, tr, coll)


def gable_board(name, coll, shape, M, xg, z_floor, mat='M_RedPaint', bottom=None):
    """Painted gable board (山花板) filling the gable under the roof soffit at local x = xg.
    The bottom edge is z_floor, or follows bottom(y) when given (e.g. the skirt surface below)."""
    mb = C.MB()
    B = shape.B
    N = 24
    for i in range(N):
        y0 = -B + 2 * B * i / N; y1 = -B + 2 * B * (i + 1) / N
        z0 = shape.z(xg, y0) - 0.20; z1 = shape.z(xg, y1) - 0.20
        b0 = bottom(y0) if bottom else z_floor
        b1 = bottom(y1) if bottom else z_floor
        if z0 <= b0 and z1 <= b1:
            continue
        mb.face([M @ Vector((xg, y0, b0)), M @ Vector((xg, y1, b1)), M @ Vector((xg, y1, max(z1, b1))),
                 M @ Vector((xg, y0, max(z0, b0)))], mat)
    o = mb.finish(name + '_山花板', coll)
    return o

def stepped_roof(name, coll, cx, cy, A, B, z_eave, z_step, z_ridge, d_cap, along='x', lift=0.45, lift_len=2.2,
                 upper_end_inset=0.55, upper_over=0.32, step_gap=0.14, horn=0.30, horn_len=0.6, d_in=1.4):
    """Stepped 歇山 (B3 south pavilion): a hipped skirt (tiled up to d_cap from the eave, reaching z_step there)
    with a separate gable roof (eave just above the skirt top, ridge at z_ridge) sitting on it.
    The upper roof has its own tiled eaves, bargeboards, 悬鱼 and red gable boards down to the skirt."""
    # skirt profile: choose the virtual ridge so that the concave profile reaches z_step at d_cap
    t = C.interp(RF.NPROF, d_cap / B)
    z_rv = z_eave + (z_step - z_eave) / max(0.05, t)
    skirt, M, P = roof(name + '_下檐', coll, 'pyramid', cx, cy, A, B, z_eave, z_rv, along=along, lift=lift,
                       lift_len=lift_len, d_in=d_in, ridge_scale=0.7, d_cap=d_cap)
    Au = A - upper_end_inset
    Bu = B - d_cap + upper_over
    zue = P.f(d_cap - upper_over) + step_gap
    up_shape, Mu, Pu = roof(name + '_上檐', coll, 'gable', cx, cy, Au, Bu, zue, z_ridge, along=along, horn=horn,
                            horn_len=horn_len, gables=(True, True), d_in=min(1.2, Bu - 0.2), ridge_scale=0.78, xuanyu=True)
    for sx in (-1, 1):
        xg = sx * (Au - 0.12)
        gable_board(name + '_上檐', coll, up_shape, Mu, xg, 0.0, bottom=lambda y, xg=xg: skirt.z(xg, y) - 0.06)
    return skirt, up_shape
