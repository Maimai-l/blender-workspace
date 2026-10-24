# Xingyuan build library - roofs.
# A roof is described in a local frame: x along the main ridge, y across, z up (absolute heights).
# Height of the tile surface is f(d) where d = horizontal distance from the eave edge (0 at eave).
# Roof kinds: 'gable' (悬山, x in [-A, A], two slopes), 'xieshan' (歇山: gable core |x|<=xg plus hipped
# ends), 'pyramid' (攒尖, square, A == B). The profile shape comes from the 3-3 section of A5.
import bpy, math
from mathutils import Vector, Matrix
import xy_core as C

# A5 roof (3-3 section): r = distance from ridge, h = height of tile top surface
PROF_A5 = [(0, 9.2), (0.24, 9.086), (0.44, 8.922), (0.64, 8.764), (0.84, 8.623), (1.04, 8.465), (1.24, 8.318),
           (1.44, 8.188), (1.64, 8.047), (1.84, 7.912), (2.04, 7.777), (2.44, 7.534), (2.84, 7.297), (3.04, 7.178),
           (3.44, 6.947), (3.84, 6.738), (4.04, 6.642), (4.44, 6.445), (4.84, 6.258), (5.04, 6.168), (5.44, 5.999),
           (5.84, 5.841), (6.04, 5.762), (6.44, 5.621), (6.84, 5.474), (7.24, 5.339), (7.64, 5.209), (8.04, 5.096),
           (8.44, 4.994), (8.64, 4.955)]
_R0 = 8.64
_H0, _H1 = 9.2, 4.955
# normalised: s = d / R (0 at eave .. 1 at ridge), t = (h - eave) / (ridge - eave)
NPROF = sorted(((_R0 - r) / _R0, (h - _H1) / (_H0 - _H1)) for r, h in PROF_A5)

class Profile:
    def __init__(self, R, h_eave, h_ridge, power=1.0):
        self.R, self.he, self.hr, self.p = R, h_eave, h_ridge, power
    def f(self, d):
        s = max(0.0, min(1.0, d / self.R))
        t = C.interp(NPROF, s)
        if self.p != 1.0:
            t = t ** self.p
        return self.he + (self.hr - self.he) * t
    def slope(self, d, e=0.02):
        return (self.f(d + e) - self.f(d - e)) / (2 * e)

# ------------------------------------------------------------------ roof shape
class RoofShape:
    """kind: gable / xieshan / pyramid.  A: half length along x (to eave/verge),
    B: half width along y (eave to ridge distance = B).  xg: gable plane |x| for xieshan.
    lift: corner upturn height (hipped kinds), lift_len: length along the eave over which it rises."""
    def __init__(self, kind, A, B, prof, xg=None, lift=0.0, lift_len=2.0, ridge_gap=0.12, d_cap=None):
        self.kind, self.A, self.B, self.P = kind, A, B, prof
        self.xg = xg
        self.lift, self.lift_len = lift, lift_len
        self.ridge_gap = ridge_gap
        self.d_cap = d_cap          # skirt roofs: tiles/deck only up to this distance from the eave

    def _lift(self, x, y):
        if self.lift <= 0:
            return 0.0
        A, B = self.A, self.B
        if self.kind == 'gable':
            # 生起: eave rises toward the gable ends, fading out toward the ridge
            dx = A - abs(x)
            if dx >= self.lift_len:
                return 0.0
            t = 1.0 - dx / self.lift_len
            dy = B - abs(y)
            fall = max(0.0, 1.0 - dy / (B * 0.85))
            return self.lift * (t ** 2.0) * (fall ** 1.4)
        # distance to the nearest corner measured along the eave, falloff by distance from eave
        dx, dy = A - abs(x), B - abs(y)
        d_edge = min(dx, dy)
        along = max(dx, dy)  # distance along the eave from the corner
        if along > self.lift_len:
            return 0.0
        t = 1.0 - along / self.lift_len
        fall = max(0.0, 1.0 - d_edge / (self.lift_len * 0.9))
        return self.lift * (t ** 2.2) * (fall ** 1.5)

    def face_of(self, x, y):
        A, B = self.A, self.B
        dy = B - abs(y)
        if self.kind == 'gable':
            return ('S' if y < 0 else 'N'), dy
        dx = A - abs(x)
        if self.kind == 'xieshan' and abs(x) <= self.xg:
            return ('S' if y < 0 else 'N'), dy
        if dy <= dx:
            return ('S' if y < 0 else 'N'), dy
        return ('W' if x < 0 else 'E'), dx

    def z(self, x, y):
        A, B = self.A, self.B
        dy = B - abs(y)
        if self.kind == 'gable':
            d = dy
        elif self.kind == 'xieshan':
            if abs(x) <= self.xg:
                d = dy
            else:
                d = min(dy, A - abs(x))
        else:
            d = min(dy, A - abs(x))
        if self.d_cap is not None:
            d = min(d, self.d_cap)
        return self.P.f(d) + self._lift(x, y)

    def zg(self):
        """height of the gable base line (xieshan)"""
        return self.P.f(self.A - self.xg)

# ------------------------------------------------------------------ geometry sources (tiles etc.)
TILE_L = 0.34       # exposed course length along slope
COVER_R = 0.088     # 筒瓦 radius
PAN_W = 0.30        # 板瓦 width
ROW_W = 0.30        # distance between cover rows

def tile_sources():
    lib = C.lib_coll()
    out = {}
    if bpy.data.objects.get('SRC_cover') is None:
        # cover tile: half-cylinder along +X, axis at z=0.025, radius COVER_R, small lip at lower end
        mb = C.MB()
        segs = 9
        L = TILE_L + 0.02
        def ring(x, r, zc):
            return [(x, -r * math.cos(math.pi * k / segs), zc + r * math.sin(math.pi * k / segs)) for k in range(segs + 1)]
        rows = [ring(0.0, COVER_R + 0.006, 0.0), ring(0.03, COVER_R + 0.006, 0.0), ring(0.035, COVER_R, 0.0), ring(L, COVER_R, 0.0)]
        mb.quad_strip(rows, 'M_Tile', smooth=True)
        # lower end face (thickness ring)
        inner = ring(0.0, COVER_R - 0.012, 0.0)
        mb.quad_strip([rows[0], inner], 'M_Tile')
        o = mb.finish('SRC_cover', lib)
        o.data.set_sharp_from_angle(angle=math.radians(50))
        # pan tile: shallow concave plate, lower edge thickness
        mb = C.MB()
        n = 6
        def prow(x, zoff):
            pts = []
            for k in range(n + 1):
                u = -PAN_W / 2 + PAN_W * k / n
                sag = 0.03 * (1 - (2 * u / PAN_W) ** 2)
                pts.append((x, u, 0.0 + zoff - sag + 0.03))
            return pts
        top0 = prow(0.0, 0.0); top1 = prow(L, 0.02)
        mb.quad_strip([top0, top1], 'M_Tile', smooth=True)
        bot0 = [(p[0], p[1], p[2] - 0.016) for p in top0]
        mb.quad_strip([bot0, top0], 'M_Tile')
        mb.finish('SRC_pan', lib)
        # eave cover tile with end disc (瓦当)
        mb = C.MB()
        rows = [ring(0.0, COVER_R, 0.0), ring(L, COVER_R, 0.0)]
        mb.quad_strip(rows, 'M_Tile', smooth=True)
        # disc: full circle slightly larger, facing -X, 0.025 thick
        dsegs = 16
        R = COVER_R + 0.012
        zc = 0.0
        front = [(-0.025, R * math.cos(2 * math.pi * k / dsegs), zc + R * math.sin(2 * math.pi * k / dsegs)) for k in range(dsegs)]
        back = [(0.0, p[1], p[2]) for p in front]
        mb.quad_strip([back, front], 'M_Tile', closed_u=True)
        f = mb.face(list(reversed(front)), 'M_Tile')
        # relief ring + boss on the disc face
        ring2 = [(-0.035, 0.55 * R * math.cos(2 * math.pi * k / dsegs), zc + 0.55 * R * math.sin(2 * math.pi * k / dsegs)) for k in range(dsegs)]
        ring2b = [(-0.025, p[1], p[2]) for p in ring2]
        mb.quad_strip([ring2b, ring2], 'M_Tile', closed_u=True)
        mb.face(list(reversed(ring2)), 'M_Tile')
        o = mb.finish('SRC_cover_eave', lib)
        # eave pan tile with drip (滴水): pendant lip hanging down at lower end
        mb = C.MB()
        top0 = prow(0.0, 0.0); top1 = prow(L, 0.02)
        mb.quad_strip([top0, top1], 'M_Tile', smooth=True)
        drip = []
        for p in top0:
            u = p[1]
            depth = 0.075 - 0.045 * abs(2 * u / PAN_W) ** 1.5
            drip.append((p[0] - 0.012, u, p[2] - depth))
        mb.quad_strip([drip, top0], 'M_Tile')
        mb.finish('SRC_pan_eave', lib)
    for k in ('SRC_cover', 'SRC_pan', 'SRC_cover_eave', 'SRC_pan_eave'):
        out[k] = bpy.data.objects[k]
    return out

# ------------------------------------------------------------------ row marching
def _row_points(shape, face, c, d0, d1, step=0.05):
    """3D points along a tile row on a face. c = row coordinate along the eave.
    returns list of (Vector point, d)."""
    A, B = shape.A, shape.B
    pts = []
    n = max(2, int((d1 - d0) / step) + 1)
    for i in range(n + 1):
        d = d0 + (d1 - d0) * i / n
        if face == 'S':
            x, y = c, -B + d
        elif face == 'N':
            x, y = c, B - d
        elif face == 'W':
            x, y = -A + d, c
        else:
            x, y = A - d, c
        pts.append((Vector((x, y, shape.z(x, y))), d))
    return pts

def _downhill(face):
    return {'S': Vector((0, -1, 0)), 'N': Vector((0, 1, 0)), 'W': Vector((-1, 0, 0)), 'E': Vector((1, 0, 0))}[face]

def row_extent(shape, face, c):
    d = _row_extent(shape, face, c)
    if d is not None and shape.d_cap is not None:
        d = min(d, shape.d_cap)
    return d

def _row_extent(shape, face, c):
    """returns (d_max) the uphill extent of a row on a face, or None if the row is outside."""
    A, B = shape.A, shape.B
    if face in 'SN':
        if abs(c) > A:
            return None
        if shape.kind == 'gable':
            return B - shape.ridge_gap
        if shape.kind == 'xieshan' and abs(c) <= shape.xg:
            return B - shape.ridge_gap
        dm = A - abs(c)  # hip line
        return min(dm, B - shape.ridge_gap)
    else:
        if abs(c) > B:
            return None
        dm = B - abs(c)
        if shape.kind == 'xieshan':
            dm = min(dm, A - shape.xg - 0.02)
        else:
            dm = min(dm, A - shape.ridge_gap)
        return dm

def tile_transforms(shape, M, faces, skip=None):
    """Compute world transforms for cover/pan/eave tiles on given faces.
    M: world matrix of the roof local frame. returns dict src->list of (loc, rot, scale)."""
    res = {'SRC_cover': [], 'SRC_pan': [], 'SRC_cover_eave': [], 'SRC_pan_eave': []}
    A, B = shape.A, shape.B
    R3 = M.to_3x3()
    for face in faces:
        half = A if face in 'SN' else B
        n = int((2 * half) / ROW_W)
        start = -n * ROW_W / 2
        for k in range(n * 2 + 1):
            c = start + k * ROW_W / 2
            is_cover = (k % 2 == 1)
            if abs(c) > half - (0.06 if is_cover else 0.15):
                continue
            dmax = row_extent(shape, face, c)
            if dmax is None or dmax < 0.15:
                continue
            if skip and skip(face, c):
                continue
            pts = _row_points(shape, face, c, -0.03, dmax)
            # arc-length parameterisation
            acc = [0.0]
            for i in range(1, len(pts)):
                acc.append(acc[-1] + (pts[i][0] - pts[i - 1][0]).length)
            total = acc[-1]
            s = 0.0
            first = True
            while s < total - 0.05:
                # locate
                i = 1
                while i < len(acc) - 1 and acc[i] < s:
                    i += 1
                t = (s - acc[i - 1]) / max(1e-6, acc[i] - acc[i - 1])
                p = pts[i - 1][0].lerp(pts[i][0], t)
                tang = (pts[i][0] - pts[i - 1][0]).normalized()   # uphill
                side = tang.cross(Vector((0, 0, 1)))
                if side.length < 1e-6:
                    side = Vector((0, 1, 0))
                side.normalize()
                nrm = side.cross(tang).normalized()
                if nrm.z < 0:
                    nrm = -nrm; side = -side
                tilt = 0.0 if is_cover else 0.035
                tw = (tang * math.cos(tilt) - nrm * math.sin(tilt)).normalized()
                nw = (nrm * math.cos(tilt) + tang * math.sin(tilt)).normalized()
                loc = M @ p
                rot = C.rot_from_axes(R3 @ tw, R3 @ side, R3 @ nw)
                key = ('SRC_cover_eave' if first else 'SRC_cover') if is_cover else ('SRC_pan_eave' if first else 'SRC_pan')
                res[key].append((tuple(loc), rot, 1.0))
                first = False
                s += TILE_L
    return res

def place_tiles(name, shape, M, faces, collection, skip=None):
    src = tile_sources()
    tr = tile_transforms(shape, M, faces, skip)
    objs = []
    for k, lst in tr.items():
        if lst:
            objs.append(C.instancer('%s_%s' % (name, k[4:]), src[k], lst, collection))
    return objs, sum(len(v) for v in tr.values())

# ------------------------------------------------------------------ deck / soffit
def deck(name, shape, M, collection, t_top=0.055, t_sof=0.20, res=0.3, mat_top='M_Tile', mat_sof='M_RedOrange',
         x_range=None, soffit_step=None):
    """Roof deck (under the tiles) as height-field patches. Soffit at z - t_sof.
    soffit_step: (d_step, t_outer) -> soffit rises to z - t_outer for d < d_step (flying rafter zone)."""
    mb = C.MB()
    A, B = shape.A, shape.B
    xr = x_range or (-A, A)

    def sof_t(x, y):
        if soffit_step is None:
            return t_sof
        face, d = shape.face_of(x, y)
        return soffit_step[1] if d < soffit_step[0] else t_sof

    def patch(x0, x1, y0, y1, zf):
        nx = max(1, int((x1 - x0) / res)); ny = max(2, int((y1 - y0) / res * 2))
        xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
        ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
        # insert extra y samples near eave for the soffit step
        top = [[M @ Vector((x, y, zf(x, y) - t_top)) for x in xs] for y in ys]
        bot = [[M @ Vector((x, y, zf(x, y) - sof_t(x, y))) for x in xs] for y in ys]
        if shape.d_cap is not None:
            # keep only cells that reach below the cap (skirt ring)
            dc = shape.d_cap + res * 1.01
            for j in range(len(ys) - 1):
                for i in range(len(xs) - 1):
                    if min(shape.face_of(xs[ii], ys[jj])[1] for ii in (i, i + 1) for jj in (j, j + 1)) > dc:
                        continue
                    mb.face([top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]], mat_top)
                    mb.face([bot[j][i + 1], bot[j][i], bot[j + 1][i], bot[j + 1][i + 1]], mat_sof)
            return
        mb.quad_strip(top, mat_top)
        # soffit faces (reverse orientation)
        rows = [list(reversed(r)) for r in bot]
        mb.quad_strip(rows, mat_sof)
        # edges: perimeter skirt
        for (a, b) in ((top[0], bot[0]), (top[-1], bot[-1])):
            mb.quad_strip([a, b], mat_sof)
        ca = [r[0] for r in top]; cb = [r[0] for r in bot]
        mb.quad_strip([cb, ca], mat_sof)
        ca = [r[-1] for r in top]; cb = [r[-1] for r in bot]
        mb.quad_strip([ca, cb], mat_sof)

    if shape.kind == 'gable':
        patch(xr[0], xr[1], -B, 0.0, shape.z)
        patch(xr[0], xr[1], 0.0, B, shape.z)
    elif shape.kind == 'xieshan':
        xg = shape.xg
        patch(-xg, xg, -B, 0.0, shape.z)
        patch(-xg, xg, 0.0, B, shape.z)
        for sgn in (-1, 1):
            xa, xb = (xg, A) if sgn > 0 else (-A, -xg)
            patch(xa, xb, -B, 0.0, shape.z)
            patch(xa, xb, 0.0, B, shape.z)
    else:
        for (xa, xb) in ((-A, 0.0), (0.0, A)):
            patch(xa, xb, -B, 0.0, shape.z)
            patch(xa, xb, 0.0, B, shape.z)
    o = mb.finish(name, collection, merge=0.001, recalc=False)     # winding is correct by construction
    for p in o.data.polygons:
        p.use_smooth = True
    try:
        o.data.set_sharp_from_angle(angle=math.radians(35))
    except Exception:
        pass
    return o

# ------------------------------------------------------------------ rafters
def rafters(name, shape, M, collection, d_in_by_face, faces, spacing=ROW_W, r_round=0.062, fly_len=0.62,
            fly_back=1.15, sq=(0.105, 0.115), with_round=True, skip=None):
    """Eave rafters (round 檐椽) and flying rafters (square 飞椽) on given faces.
    d_in_by_face: dict face -> d where rafters start (inside the wall/purlin)."""
    mb = C.MB()
    A, B = shape.A, shape.B
    for face in faces:
        half = A if face in 'SN' else B
        n = int(2 * half / spacing)
        dn = _downhill(face)
        for k in range(n + 1):
            c = -n * spacing / 2 + k * spacing
            if abs(c) > half - 0.12:
                continue
            if skip and skip(face, c):
                continue
            d_in = d_in_by_face[face]
            # for hipped faces limit rafters to not cross the hip line
            dmax_row = row_extent(shape, face, c)
            if dmax_row is None:
                continue
            if face in 'SN' and shape.kind != 'gable' and not (shape.kind == 'xieshan' and abs(c) <= shape.xg):
                d_in = min(d_in, A - abs(c) - 0.05)
            if face in 'EW':
                d_in = min(d_in, B - abs(c) - 0.05)
            if d_in < 0.3:
                continue
            # flying rafter (square), from d=0.02 to d=fly_len+fly_back
            pts = []
            for i in range(7):
                d = 0.02 + (min(fly_back, d_in) - 0.02) * i / 6
                p = _row_points(shape, face, c, d, d, 1)[0][0]
                pts.append(M @ (p - Vector((0, 0, 0.075 + sq[1] / 2))))
            mb.sweep(pts, [(-sq[0] / 2, -sq[1] / 2), (sq[0] / 2, -sq[1] / 2), (sq[0] / 2, sq[1] / 2), (-sq[0] / 2, sq[1] / 2)],
                     'M_RedLacquer')
            if with_round:
                pts = []
                d_start = fly_len
                for i in range(9):
                    d = d_start + (d_in - d_start) * i / 8
                    p = _row_points(shape, face, c, d, d, 1)[0][0]
                    pts.append(M @ (p - Vector((0, 0, 0.075 + sq[1] + 0.03 + r_round))))
                sec = [(r_round * math.cos(2 * math.pi * j / 10), r_round * math.sin(2 * math.pi * j / 10)) for j in range(10)]
                mb.sweep(pts, sec, 'M_RedLacquer', smooth=True)
    o = mb.finish(name, collection)
    try:
        o.data.set_sharp_from_angle(angle=math.radians(40))
    except Exception:
        pass
    return o

def eave_boards(name, shape, M, collection, faces, fly_len=0.62):
    """大连檐 along the flying rafter ends and 小连檐 at the round rafter ends."""
    mb = C.MB()
    A, B = shape.A, shape.B
    for face in faces:
        half = A if face in 'SN' else B
        for (d, sec, dz) in ((0.015, [(-0.05, -0.06), (0.03, -0.06), (0.03, 0.04), (-0.05, 0.0)], 0.07),
                             (fly_len - 0.02, [(-0.04, -0.035), (0.04, -0.035), (0.04, 0.035), (-0.04, 0.035)], 0.075 + 0.115 + 0.03)):
            pts = []
            N = 24
            for i in range(N + 1):
                c = -half + 2 * half * i / N
                # along-eave line at distance d (respect hip: for hipped roofs, eave lines meet at corners)
                if face == 'S':
                    x, y = c, -B + d
                elif face == 'N':
                    x, y = -c, B - d
                elif face == 'W':
                    x, y = -A + d, -c
                else:
                    x, y = A - d, c
                if shape.kind != 'gable':
                    # clip at the hip line (diagonal)
                    if face in 'SN':
                        lim = A - d
                        x = max(-lim, min(lim, x))
                    else:
                        lim = B - d
                        y = max(-lim, min(lim, y))
                pts.append(M @ Vector((x, y, shape.z(x, y) - dz)))
            # dedupe consecutive
            P = [pts[0]]
            for p in pts[1:]:
                if (p - P[-1]).length > 1e-4:
                    P.append(p)
            if len(P) >= 2:
                mb.sweep(P, sec, 'M_RedLacquer', ups=None)
    return mb.finish(name, collection)

# ------------------------------------------------------------------ ridges
RIDGE_SEC = [(-0.20, -0.16), (-0.20, 0.05), (-0.215, 0.05), (-0.215, 0.11), (-0.20, 0.11), (-0.20, 0.17),
             (-0.165, 0.17), (-0.165, 0.42), (-0.19, 0.42), (-0.19, 0.48)]
def _ridge_section(scale=1.0, cap_r=0.10, vscale=1.0):
    left = RIDGE_SEC
    cap = [(-cap_r * math.cos(math.pi * k / 8), 0.48 + 0.02 + cap_r * math.sin(math.pi * k / 8)) for k in range(9)]
    right = [(-u, v) for (u, v) in reversed(left)]
    sec = left + [(-0.11, 0.48), ] + cap[1:-1] + [(0.11, 0.48)] + right
    return [(u * scale, (v * vscale if v > 0 else v) * scale) for u, v in sec]

def main_ridge(name, M, x0, x1, z0, collection, horn=0.75, horn_len=1.0, scale=1.0, curl=True, mat='M_Tile', vscale=1.0):
    """正脊 along local x from x0 to x1 at height z0 (roof apex), ends sweep up into horns (鸱尾-like)."""
    mb = C.MB()
    sec = _ridge_section(scale, vscale=vscale)
    # central straight part
    xa, xb = x0 + horn_len, x1 - horn_len
    path = []
    ups = []
    # left horn (going from tip down to straight part), then straight, then right horn
    def horn_pts(xe, dirn):
        P = []
        U = []
        N = 10
        th_max = (math.pi / 2) * 0.93
        for i in range(N + 1):
            th = th_max * (i / N)
            x = xe + dirn * horn_len * math.sin(th) / math.sin(th_max)
            z = horn * (1 - math.cos(th)) / (1 - math.cos(th_max))
            tx = dirn * horn_len * math.cos(th) / math.sin(th_max)
            tz = horn * math.sin(th) / (1 - math.cos(th_max))
            L = math.hypot(tx, tz)
            tx, tz = tx / L, tz / L
            P.append((x, z))
            U.append((-tz * dirn, tx * dirn))
        return P, U
    lp, lu = horn_pts(xa, -1)
    rp, ru = horn_pts(xb, 1)
    pts = [(x, z) for (x, z) in reversed(lp)] + [(xa + (xb - xa) * i / 8, 0.0) for i in range(1, 8)] + rp
    upv = list(reversed(lu)) + [(0, 1)] * 7 + ru
    P3 = [M @ Vector((x, 0, z0 + z)) for (x, z) in pts]
    R3 = M.to_3x3()
    U3 = []
    for (ux, uz) in upv:
        v = Vector((ux, 0, uz))
        if v.length < 1e-6:
            v = Vector((0, 0, 1))
        U3.append(R3 @ v.normalized())
    # taper towards tips
    rows = []
    n = len(P3)
    for i in range(n):
        if i == 0:
            t = (P3[1] - P3[0])
        elif i == n - 1:
            t = (P3[-1] - P3[-2])
        else:
            t = (P3[i + 1] - P3[i - 1])
        t.normalize()
        up = U3[i]
        side = t.cross(up); side.normalize()
        upv2 = side.cross(t).normalized()
        if upv2.dot(up) < 0:
            upv2 = -upv2
        k = min(i, n - 1 - i)
        sc = 0.55 + 0.45 * min(1.0, k / 6.0)
        rows.append([P3[i] + side * (u * sc) + upv2 * (v * sc) for (u, v) in sec])
    vrows, faces = mb.quad_strip(rows, mat, smooth=False, closed_u=True)
    idx = mb.slot(mat)
    for vr in (vrows[0], vrows[-1]):
        try:
            f = mb.bm.faces.new(vr); f.material_index = idx
        except ValueError:
            pass
    o = mb.finish(name, collection)
    return o

def verge_ridge(name, M, shape, xside, collection, d0=0.0, d1=None, r=0.095, mat='M_Tile'):
    """Verge (排山) roll along the gable edge at local x = xside, both slopes, plus end caps."""
    mb = C.MB()
    B = shape.B
    d1 = B if d1 is None else d1
    for sgn in (-1, 1):
        pts = []
        N = 24
        for i in range(N + 1):
            d = d0 + (d1 - d0) * i / N
            y = sgn * (B - d)
            pts.append(M @ Vector((xside, y, shape.z(xside, y) + 0.03)))
        sec = [(-0.11, -0.05), (0.11, -0.05)] + [(r * math.cos(math.pi * k / 8), 0.02 + r * math.sin(math.pi * k / 8)) for k in range(9)]
        sec = [(-0.11, -0.05), (0.11, -0.05), (0.11, 0.02)] + [(r * math.cos(math.pi * k / 8), 0.02 + r * math.sin(math.pi * k / 8)) for k in range(1, 8)] + [(-0.11, 0.02)]
        mb.sweep(pts, sec, mat, smooth=False)
        # tile end disc at the eave end
        p0 = pts[0]
        mb.cyl(p0 + (pts[0] - pts[1]).normalized() * 0.02, p0, r + 0.01, 12, mat, smooth=True)
    return mb.finish(name, collection)

def hip_ridge(name, M, shape, corner, collection, d_top, mat='M_Tile', curl=0.35):
    """Hip ridge (戗脊/垂脊) from an eave corner up the diagonal to distance d_top from the eave.
    corner: (sx, sy) signs."""
    mb = C.MB()
    sx, sy = corner
    A, B = shape.A, shape.B
    pts = []
    N = 22
    for i in range(N + 1):
        d = 0.0 + d_top * i / N
        x = sx * (A - d); y = sy * (B - d)
        pts.append(Vector((x, y, shape.z(x, y) + 0.02)))
    # upturned tip beyond the corner
    tip_dir = Vector((sx, sy, 0)).normalized()
    p0 = pts[0]
    tip = [p0 + tip_dir * 0.16 + Vector((0, 0, curl * 0.45)), p0 + tip_dir * 0.28 + Vector((0, 0, curl))]
    P = list(reversed(tip)) + pts
    P = [M @ p for p in P]
    sec = [(-0.13, -0.08), (0.13, -0.08), (0.13, 0.12), (0.10, 0.12), (0.10, 0.2)] + \
          [(0.085 * math.cos(math.pi * k / 6), 0.22 + 0.085 * math.sin(math.pi * k / 6)) for k in range(1, 6)] + \
          [(-0.10, 0.2), (-0.10, 0.12), (-0.13, 0.12)]
    rows = []
    n = len(P)
    for i in range(n):
        t = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        side = t.cross(Vector((0, 0, 1)))
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        up = side.cross(t).normalized()
        if up.z < 0:
            up = -up
        sc = 0.6 + 0.4 * min(1.0, i / 3.0)
        rows.append([P[i] + side * u * sc + up * v * sc for (u, v) in sec])
    vrows, faces = mb.quad_strip(rows, mat, closed_u=True)
    idx = mb.slot(mat)
    for vr in (vrows[0], vrows[-1]):
        try:
            f = mb.bm.faces.new(vr); f.material_index = idx
        except ValueError:
            pass
    return mb.finish(name, collection)

# ------------------------------------------------------------------ bargeboard, 悬鱼
def bargeboard(name, M, shape, xside, collection, depth=0.42, thick=0.06, top_off=0.10, d_max=None, flare=0.16,
               mat='M_RedLacquer', ymin=None, d_min=0.0):
    """博风板 on a gable edge (local x = xside) following both slopes, lower ends flared."""
    mb = C.MB()
    B = shape.B
    dm = B if d_max is None else d_max
    for sgn in (-1, 1):
        top = []; bot = []
        N = 30
        for i in range(N + 1):
            d = d_min + (dm - d_min) * i / N
            y = sgn * (B - d)
            z = shape.z(xside, y) - top_off
            fl = flare * max(0.0, 1 - d / 0.9) ** 2
            top.append((y, z))
            bot.append((y, z - depth - fl))
        # end scroll: round the outer lower corner
        poly = top + list(reversed(bot))
        # extrude along x by thickness
        P0 = [M @ Vector((xside - thick / 2, y, z)) for (y, z) in poly]
        P1 = [M @ Vector((xside + thick / 2, y, z)) for (y, z) in poly]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            mb.face([P0[i], P0[j], P1[j], P1[i]], mat)
        # caps as strips (non-convex) -> triangulate via quad pairs between top and bottom
        for i in range(N):
            mb.face([M @ Vector((xside - thick / 2, top[i][0], top[i][1])), M @ Vector((xside - thick / 2, bot[i][0], bot[i][1])),
                     M @ Vector((xside - thick / 2, bot[i + 1][0], bot[i + 1][1])), M @ Vector((xside - thick / 2, top[i + 1][0], top[i + 1][1]))], mat)
            mb.face([M @ Vector((xside + thick / 2, top[i][0], top[i][1])), M @ Vector((xside + thick / 2, top[i + 1][0], top[i + 1][1])),
                     M @ Vector((xside + thick / 2, bot[i + 1][0], bot[i + 1][1])), M @ Vector((xside + thick / 2, bot[i][0], bot[i][1]))], mat)
    return mb.finish(name, collection)

def xuanyu_poly(w=0.9, h=1.05):
    """Outline of a 悬鱼 (hanging ornament): lobed cloud head + central stem + pointed tail. (y, z) with top at 0."""
    import math as m
    pts = []
    # build by sampling a polar-ish outline around a vertical axis
    N = 64
    for i in range(N + 1):
        t = i / N  # 0..1 around
        a = 2 * m.pi * t
        # base ellipse
        rx = w / 2 * (0.62 + 0.38 * abs(m.cos(3 * a)) ** 0.6)
        ry = h / 2 * (0.75 + 0.25 * abs(m.cos(2 * a)))
        y = rx * m.sin(a)
        z = -h / 2 + ry * m.cos(a)
        pts.append((y, z))
    return pts[:-1]

def xuanyu(name, center, normal_axis, collection, w=0.9, h=1.05, thick=0.05, mat='M_RedLacquer'):
    """Place a 悬鱼 plate. center: top point (world); normal_axis: 'x' or 'y' world axis the plate faces."""
    mb = C.MB()
    poly = xuanyu_poly(w, h)
    cx, cy, cz = center
    def P(u, v, s):
        if normal_axis == 'y':
            return Vector((cx + u, cy + s, cz + v))
        return Vector((cx + s, cy + u, cz + v))
    n = len(poly)
    f0 = [P(u, v, -thick / 2) for u, v in poly]
    f1 = [P(u, v, thick / 2) for u, v in poly]
    mb.face(f0, mat); mb.face(list(reversed(f1)), mat)
    for i in range(n):
        j = (i + 1) % n
        mb.face([f0[i], f1[i], f1[j], f0[j]], mat)
    # inner relief disc
    for k, (u, v, r) in enumerate(((0, -h * 0.42, w * 0.16),)):
        ring0 = [P(u + r * math.cos(2 * math.pi * q / 14), v + r * math.sin(2 * math.pi * q / 14), -thick / 2 - 0.02) for q in range(14)]
        ring1 = [P(u + r * math.cos(2 * math.pi * q / 14), v + r * math.sin(2 * math.pi * q / 14), thick / 2 + 0.02) for q in range(14)]
        mb.face(ring0, mat); mb.face(list(reversed(ring1)), mat)
        for i in range(14):
            j = (i + 1) % 14
            mb.face([ring0[i], ring1[i], ring1[j], ring0[j]], mat)
    return mb.finish(name, collection)

# ------------------------------------------------------------------ finial
def finial(name, base, collection, scale=1.0, mat='M_Tile'):
    """宝顶 for pyramid roofs: lathe vase shape."""
    mb = C.MB()
    prof = [(0.32, 0.0), (0.34, 0.06), (0.26, 0.12), (0.22, 0.2), (0.28, 0.32), (0.31, 0.45), (0.27, 0.6),
            (0.16, 0.72), (0.12, 0.8), (0.17, 0.88), (0.12, 0.98), (0.0, 1.02)]
    prof = [(r * scale, z * scale) for r, z in prof]
    mb.lathe(prof, 20, mat, center=base, cap_top=False)
    return mb.finish(name, collection)
