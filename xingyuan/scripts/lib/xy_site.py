# Xingyuan build library - ground, platforms (台基), paving slabs, curbs, stairs.
# Paving is real geometry: every slab is its own bevelled quad with a per-slab random attribute
# ('slab') that the stone materials use for tone variation.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix
import xy_core as C

class Paver:
    """Accumulates slabs into one mesh (with the 'slab' face attribute)."""
    def __init__(self, seed=1):
        self.mb = C.MB()
        self.rand = []           # per face value
        self.rng = random.Random(seed)

    def slab(self, x0, y0, x1, y1, z, m, gap=0.005, bev=0.007, drop=0.012, jitter=0.0018, M=None):
        mb = self.mb
        g = gap / 2
        a0, b0, a1, b1 = x0 + g, y0 + g, x1 - g, y1 - g
        if a1 - a0 < 0.03 or b1 - b0 < 0.03:
            return
        r = self.rng.random()
        dz = (self.rng.random() - 0.5) * 2 * jitter
        tx = (self.rng.random() - 0.5) * jitter * 0.8
        ty = (self.rng.random() - 0.5) * jitter * 0.8
        cx, cy = (a0 + a1) / 2, (b0 + b1) / 2
        def zt(x, y):
            return z + dz + tx * (x - cx) / max(0.3, a1 - a0) + ty * (y - cy) / max(0.3, b1 - b0)
        top = [(a0 + bev, b0 + bev), (a1 - bev, b0 + bev), (a1 - bev, b1 - bev), (a0 + bev, b1 - bev)]
        bot = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
        T = [Vector((x, y, zt(x, y))) for x, y in top]
        B = [Vector((x, y, z - drop)) for x, y in bot]
        if M is not None:
            T = [M @ p for p in T]
            B = [M @ p for p in B]
        f = mb.face(T, m)
        if f is not None:
            self.rand.append((f, r))
        for i in range(4):
            j = (i + 1) % 4
            f = mb.face([B[i], B[j], T[j], T[i]], m)
            if f is not None:
                self.rand.append((f, r))

    def poly(self, P2, z, m, gap=0.005, bev=0.007, drop=0.012, jitter=0.0018, rnd=None):
        """A slab with an arbitrary (small, roughly convex, CCW) outline P2 [(x, y), ...]: bevelled top + sides."""
        n = len(P2)
        if n < 3:
            return
        A = 0.0
        cx = cy = 0.0
        for i in range(n):
            x1, y1 = P2[i]; x2, y2 = P2[(i + 1) % n]
            c = x1 * y2 - x2 * y1
            A += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c
        if A <= 1e-6:
            return
        cx /= 3 * A; cy /= 3 * A
        def ins(p, d):
            vx, vy = p[0] - cx, p[1] - cy
            L = math.hypot(vx, vy)
            k = 0.0 if L < 1e-9 else max(0.0, (L - d) / L)
            return (cx + vx * k, cy + vy * k)
        r = self.rng.random() if rnd is None else rnd
        dz = (self.rng.random() - 0.5) * 2 * jitter
        tx = (self.rng.random() - 0.5) * jitter * 0.8
        ty = (self.rng.random() - 0.5) * jitter * 0.8
        T = [Vector((q[0], q[1], z + dz + tx * (q[0] - cx) + ty * (q[1] - cy))) for q in (ins(p, gap / 2 + bev) for p in P2)]
        B = [Vector((q[0], q[1], z - drop)) for q in (ins(p, gap / 2) for p in P2)]
        f = self.mb.face(T, m)
        if f is not None:
            self.rand.append((f, r))
        for i in range(n):
            j = (i + 1) % n
            f = self.mb.face([B[i], B[j], T[j], T[i]], m)
            if f is not None:
                self.rand.append((f, r))

    def field(self, x0, y0, x1, y1, z, m, sw=0.6, sl=0.9, along='y', stagger=0.5, gap=0.005, M=None,
              border=None, clip=None):
        """Fill a rectangle with running-bond slabs. along: direction of the long side ('x' or 'y').
        clip: optional function (x,y)->bool, slab kept if its centre passes."""
        if along == 'y':
            # columns of width sw along x, slabs of length sl along y, staggered per column
            nx = max(1, int(round((x1 - x0) / sw)))
            w = (x1 - x0) / nx
            for i in range(nx):
                xa, xb = x0 + i * w, x0 + (i + 1) * w
                off = (i % 2) * stagger * sl
                y = y0 - off
                while y < y1:
                    ya, yb = max(y0, y), min(y1, y + sl)
                    if yb - ya > 0.05 and (clip is None or clip((xa + xb) / 2, (ya + yb) / 2)):
                        self.slab(xa, ya, xb, yb, z, m, gap=gap, M=M)
                    y += sl
        else:
            ny = max(1, int(round((y1 - y0) / sw)))
            w = (y1 - y0) / ny
            for i in range(ny):
                ya, yb = y0 + i * w, y0 + (i + 1) * w
                off = (i % 2) * stagger * sl
                x = x0 - off
                while x < x1:
                    xa, xb = max(x0, x), min(x1, x + sl)
                    if xb - xa > 0.05 and (clip is None or clip((xa + xb) / 2, (ya + yb) / 2)):
                        self.slab(xa, ya, xb, yb, z, m, gap=gap, M=M)
                    x += sl

    def grout(self, x0, y0, x1, y1, z, m='M_Gravel', M=None):
        P = [Vector((x0, y0, z - 0.011)), Vector((x1, y0, z - 0.011)), Vector((x1, y1, z - 0.011)), Vector((x0, y1, z - 0.011))]
        if M is not None:
            P = [M @ p for p in P]
        self.mb.face(P, m)

    def finish(self, name, collection):
        mb = self.mb
        lay = mb.bm.faces.layers.float.new('slab')
        for f, r in self.rand:
            if f.is_valid:
                f[lay] = r
        o = mb.finish(name, collection, recalc=False)
        # make sure faces point up / out: recalc on the bmesh happened? (skipped to keep caps up)
        return o

def recalc_up(o):
    """Flip faces whose normal points down (for paving made of open quads)."""
    me = o.data
    bm = bmesh.new(); bm.from_mesh(me)
    for f in bm.faces:
        if f.normal.z < -0.5:
            f.normal_flip()
    bm.to_mesh(me); bm.free()

# ------------------------------------------------------------------ platform (台基)
def platform(mb, x0, y0, x1, y1, z_top, z_bot, m_side='M_Granite', m_curb='M_Granite', curb_w=0.42, curb_l=1.1,
             sides=('-x', '+x', '-y', '+y'), rng=None):
    """Retaining body of a raised platform: side faces + edge curb stones (阶条石) along chosen sides.
    The top inside the curbs is left for paving."""
    rng = rng or random.Random(7)
    h = z_top - z_bot
    # body (sides) as separate stone courses for realism
    courses = max(1, int(round(h / 0.32)))
    ch = h / courses
    def side_stones(p0, p1, z0, z1, outward):
        L = (p1 - p0).length
        d = (p1 - p0).normalized()
        n = max(1, int(round(L / 0.9)))
        for k in range(n):
            a = p0 + d * (L * k / n) + outward * 0.0
            b = p0 + d * (L * (k + 1) / n)
            e = 0.004
            pa = a + d * e; pb = b - d * e
            mb.face([Vector((pa.x, pa.y, z0 + e)), Vector((pb.x, pb.y, z0 + e)), Vector((pb.x, pb.y, z1 - e)), Vector((pa.x, pa.y, z1 - e))], m_side)
    corners = {'-y': (Vector((x0, y0, 0)), Vector((x1, y0, 0)), Vector((0, -1, 0))),
               '+x': (Vector((x1, y0, 0)), Vector((x1, y1, 0)), Vector((1, 0, 0))),
               '+y': (Vector((x1, y1, 0)), Vector((x0, y1, 0)), Vector((0, 1, 0))),
               '-x': (Vector((x0, y1, 0)), Vector((x0, y0, 0)), Vector((-1, 0, 0)))}
    for s in sides:
        p0, p1, out = corners[s]
        for c in range(courses - 1):
            za = z_bot + c * ch
            side_stones(p0 + out * 0.001, p1 + out * 0.001, za, za + ch, out)
        # top course is the curb (阶条石) as blocks
        L = (p1 - p0).length
        d = (p1 - p0).normalized()
        n = max(1, int(round(L / curb_l)))
        for k in range(n):
            a = p0 + d * (L * k / n)
            b = p0 + d * (L * (k + 1) / n)
            inward = -out
            e = 0.003
            q0 = a + d * e; q1 = b - d * e
            zc0 = z_top - ch if courses > 1 else z_bot
            z1 = z_top + (rng.random() - 0.5) * 0.002
            P = [q0, q1, q1 + inward * curb_w, q0 + inward * curb_w]
            top = [Vector((p.x, p.y, z1)) for p in P]
            bot = [Vector((p.x, p.y, zc0)) for p in P]
            mb.face(top, m_curb)
            mb.face([bot[0], bot[1], top[1], top[0]], m_curb)
            # small chamfer face on the outer top edge is approximated by the bevel modifier later
    # inner fill under the curbs (hidden) not needed

def stairs(mb, center, direction, width, z_top, z_bot, n, run=0.36, m='M_Granite', side_w=0.32, sides=True,
           m_side='M_Granite'):
    """Straight flight going DOWN along `direction` (unit 2D vector) starting at `center` (top edge mid point).
    Treads are separate blocks. Optional 垂带 (sloped side curbs) and 象眼 side walls."""
    cx, cy = center
    d = Vector((direction[0], direction[1], 0)).normalized()
    s = Vector((-d.y, d.x, 0))
    rise = (z_top - z_bot) / n
    W = width
    for k in range(n - 1):            # n risers, n-1 treads (the last step lands on the ground)
        zt = z_top - rise * (k + 1)
        a = k * run
        b = (k + 1) * run + 0.03
        base = Vector((cx, cy, 0))
        hw = W / 2 - 0.003           # treads stop 3 mm short of the side curbs
        p = [base + d * a - s * hw, base + d * b - s * hw, base + d * b + s * hw, base + d * a + s * hw]
        top = [Vector((q.x, q.y, zt)) for q in p]
        bot = [Vector((q.x, q.y, zt - rise - 0.02)) for q in p]
        # tread block (5 faces)
        mb.face(top, m)
        mb.face([bot[0], bot[3], top[3], top[0]], m)   # riser (front edge is at 'a' side -> back)
        mb.face([bot[1], bot[2], top[2], top[1]], m)   # nose face
        mb.face([bot[0], bot[1], top[1], top[0]], m)
        mb.face([bot[2], bot[3], top[3], top[2]], m)
    if sides:
        Lrun = (n - 1) * run + 0.03
        for sg in (-1, 1):
            o = Vector((cx, cy, 0)) + s * sg * (W / 2 + side_w / 2)
            # sloped curb: from top (z_top) at a=0 to bottom (z_bot+rise*0.5) at a=Lrun
            pts_top = [o + d * 0.0 + Vector((0, 0, z_top + 0.0)), o + d * Lrun + Vector((0, 0, z_bot + 0.05))]
            hw = side_w / 2
            P = []
            for (pp, zz) in ((o, z_top), (o + d * Lrun, z_bot + 0.06)):
                P.append((pp - s * hw, zz)); P.append((pp + s * hw, zz))
            (a0, za), (a1, _), (b0, zb), (b1, _) = P
            top = [Vector((a0.x, a0.y, za)), Vector((a1.x, a1.y, za)), Vector((b1.x, b1.y, zb)), Vector((b0.x, b0.y, zb))]
            mb.face(top, m_side)
            # outer and inner side faces down to z_bot
            for (p0, p1, zz0, zz1) in ((a0, b0, za, zb), (a1, b1, za, zb)):
                mb.face([Vector((p0.x, p0.y, z_bot)), Vector((p1.x, p1.y, z_bot)), Vector((p1.x, p1.y, zz1)), Vector((p0.x, p0.y, zz0))], m_side)
            # end face at bottom
            mb.face([Vector((b0.x, b0.y, z_bot)), Vector((b1.x, b1.y, z_bot)), Vector((b1.x, b1.y, zb)), Vector((b0.x, b0.y, zb))], m_side)

# ================================================================== raster-based floor system
import numpy as np

class Raster:
    """Coverage raster for unions of axis-aligned rectangles (cell = res metres)."""
    def __init__(self, x0, y0, x1, y1, res=0.05):
        self.x0, self.y0, self.res = x0, y0, res
        self.nx = int(round((x1 - x0) / res)); self.ny = int(round((y1 - y0) / res))
        self.m = np.zeros((self.ny, self.nx), dtype=np.int16)   # 0 = none, else label id
    def ij(self, x, y):
        return int(round((x - self.x0) / self.res)), int(round((y - self.y0) / self.res))
    def add(self, rect, label=1):
        x0, y0, x1, y1 = rect
        i0, j0 = self.ij(x0, y0); i1, j1 = self.ij(x1, y1)
        i0 = max(0, i0); j0 = max(0, j0); i1 = min(self.nx, i1); j1 = min(self.ny, j1)
        self.m[j0:j1, i0:i1] = label
    def sub(self, rect):
        self.add(rect, 0)
    def xy(self, i, j):
        return self.x0 + i * self.res, self.y0 + j * self.res

def rects_from_mask(mask):
    """Greedy decomposition of a boolean mask into axis-aligned rectangles (cell units)."""
    m = mask.copy()
    ny, nx = m.shape
    out = []
    for j in range(ny):
        i = 0
        row = m[j]
        while i < nx:
            if not row[i]:
                i += 1
                continue
            i2 = i
            while i2 < nx and row[i2]:
                i2 += 1
            # extend downwards while the whole span is filled
            j2 = j + 1
            while j2 < ny and m[j2, i:i2].all():
                j2 += 1
            out.append((i, j, i2, j2))
            m[j:j2, i:i2] = False
            i = i2
    return out

def boundary_runs(mask):
    """Edges between True and False cells. Returns list of (x-or-y axis, fixed index, start, end, outward_dir)
    in cell units: ('h', j, i0, i1, +1) means a horizontal edge at row line j from i0 to i1 with outside at +y."""
    runs = []
    ny, nx = mask.shape
    pad = np.zeros((ny + 2, nx + 2), dtype=bool); pad[1:-1, 1:-1] = mask
    # horizontal edges: between row j-1 and j (line j)
    for j in range(ny + 1):
        a = pad[j, 1:-1]; b = pad[j + 1, 1:-1]       # a = cell below line (j-1), b = cell above (j)
        for kind, cond in (('down', a & ~b), ('up', ~a & b)):
            # 'down': inside below, outside above -> outward +y ; 'up': inside above, outward -y
            idx = np.nonzero(cond)[0]
            if len(idx) == 0:
                continue
            s = idx[0]; p = idx[0]
            for q in list(idx[1:]) + [None]:
                if q is not None and q == p + 1:
                    p = q; continue
                runs.append(('h', j, s, p + 1, +1 if kind == 'down' else -1))
                if q is not None:
                    s = q; p = q
    for i in range(nx + 1):
        a = pad[1:-1, i]; b = pad[1:-1, i + 1]
        for kind, cond in (('left', a & ~b), ('right', ~a & b)):
            idx = np.nonzero(cond)[0]
            if len(idx) == 0:
                continue
            s = idx[0]; p = idx[0]
            for q in list(idx[1:]) + [None]:
                if q is not None and q == p + 1:
                    p = q; continue
                runs.append(('v', i, s, p + 1, +1 if kind == 'left' else -1))
                if q is not None:
                    s = q; p = q
    return runs

def pave_rects(pv, R, rects, z, m, sw, sl, along='y', origin=(0.0, 0.0), stagger=0.5, inset=0.0):
    """Pave rectangles (cell units of raster R) with a global slab grid clipped to each rectangle."""
    ox, oy = origin
    for (i0, j0, i1, j1) in rects:
        x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
        x0 += inset; y0 += inset; x1 -= inset; y1 -= inset
        if x1 - x0 < 0.05 or y1 - y0 < 0.05:
            continue
        if along == 'y':
            ka = int(math.floor((x0 - ox) / sw)); kb = int(math.ceil((x1 - ox) / sw))
            for k in range(ka, kb):
                xa = max(x0, ox + k * sw); xb = min(x1, ox + (k + 1) * sw)
                if xb - xa < 0.04:
                    continue
                off = (k % 2) * stagger * sl
                la = int(math.floor((y0 - oy - off) / sl)); lb = int(math.ceil((y1 - oy - off) / sl))
                for l in range(la, lb):
                    ya = max(y0, oy + off + l * sl); yb = min(y1, oy + off + (l + 1) * sl)
                    if yb - ya < 0.04:
                        continue
                    pv.slab(xa, ya, xb, yb, z, m)
        else:
            ka = int(math.floor((y0 - oy) / sw)); kb = int(math.ceil((y1 - oy) / sw))
            for k in range(ka, kb):
                ya = max(y0, oy + k * sw); yb = min(y1, oy + (k + 1) * sw)
                if yb - ya < 0.04:
                    continue
                off = (k % 2) * stagger * sl
                la = int(math.floor((x0 - ox - off) / sl)); lb = int(math.ceil((x1 - ox - off) / sl))
                for l in range(la, lb):
                    xa = max(x0, ox + off + l * sl); xb = min(x1, ox + off + (l + 1) * sl)
                    if xb - xa < 0.04:
                        continue
                    pv.slab(xa, ya, xb, yb, z, m)

def edge_walls(mb, R, mask, z_top, z_low_fn, style_fn, curb_w=0.40, curb_len=1.0, rng=None, skip_fn=None):
    """Retaining faces + curb stones along the boundary of `mask` (raised area at z_top).
    z_low_fn(x, y) -> ground height just outside; style_fn(x, y) -> (side material, curb material)."""
    rng = rng or random.Random(3)
    runs = boundary_runs(mask)
    for (ax, fix, s, e, out) in runs:
        if ax == 'h':
            y = R.y0 + fix * R.res
            xa = R.x0 + s * R.res; xb = R.x0 + e * R.res
            L = xb - xa
            mid = ((xa + xb) / 2, y + out * 0.1)
            zl = z_low_fn(mid[0], mid[1])
            if zl is None or zl >= z_top - 0.02:
                continue
            if skip_fn and skip_fn(mid[0], mid[1]):
                continue
            ms, mc = style_fn((xa + xb) / 2, y - out * 0.2)
            n = max(1, int(round(L / curb_len)))
            for k in range(n):
                a = xa + L * k / n; b = xa + L * (k + 1) / n
                e2 = 0.003
                # curb top
                y_in = y - out * curb_w
                zt = z_top + 0.003 + (rng.random() - 0.5) * 0.001
                P = [Vector((a + e2, y_in, zt)), Vector((b - e2, y_in, zt)), Vector((b - e2, y, zt)), Vector((a + e2, y, zt))]
                if out < 0:
                    P = list(reversed(P))
                mb.face(P, mc)
                # outward face of the curb (0.16 tall) and the retaining face below
                zc = z_top - 0.16
                if zc - 0.004 <= zl:
                    F1 = [Vector((a + e2, y, zl - 0.02)), Vector((b - e2, y, zl - 0.02)), Vector((b - e2, y, zt)), Vector((a + e2, y, zt))]
                    if out > 0:
                        F1 = list(reversed(F1))
                    mb.face(F1, mc)
                    continue
                F1 = [Vector((a + e2, y, zc)), Vector((b - e2, y, zc)), Vector((b - e2, y, zt)), Vector((a + e2, y, zt))]
                F2 = [Vector((a + e2, y, zl - 0.02)), Vector((b - e2, y, zl - 0.02)), Vector((b - e2, y, zc - 0.004)), Vector((a + e2, y, zc - 0.004))]
                if out > 0:
                    F1 = list(reversed(F1)); F2 = list(reversed(F2))
                mb.face(F1, mc)
                mb.face(F2, ms)
        else:
            x = R.x0 + fix * R.res
            ya = R.y0 + s * R.res; yb = R.y0 + e * R.res
            L = yb - ya
            mid = (x + out * 0.1, (ya + yb) / 2)
            zl = z_low_fn(mid[0], mid[1])
            if zl is None or zl >= z_top - 0.02:
                continue
            if skip_fn and skip_fn(mid[0], mid[1]):
                continue
            ms, mc = style_fn(x - out * 0.2, (ya + yb) / 2)
            n = max(1, int(round(L / curb_len)))
            for k in range(n):
                a = ya + L * k / n; b = ya + L * (k + 1) / n
                e2 = 0.003
                x_in = x - out * curb_w
                zt = z_top + (rng.random() - 0.5) * 0.001
                P = [Vector((x_in, a + e2, zt)), Vector((x, a + e2, zt)), Vector((x, b - e2, zt)), Vector((x_in, b - e2, zt))]
                if out < 0:
                    P = list(reversed(P))
                mb.face(P, mc)
                zc = z_top - 0.16
                if zc - 0.004 <= zl:
                    F1 = [Vector((x, a + e2, zl - 0.02)), Vector((x, b - e2, zl - 0.02)), Vector((x, b - e2, zt)), Vector((x, a + e2, zt))]
                    if out < 0:
                        F1 = list(reversed(F1))
                    mb.face(F1, mc)
                    continue
                F1 = [Vector((x, a + e2, zc)), Vector((x, b - e2, zc)), Vector((x, b - e2, zt)), Vector((x, a + e2, zt))]
                F2 = [Vector((x, a + e2, zl - 0.02)), Vector((x, b - e2, zl - 0.02)), Vector((x, b - e2, zc - 0.004)), Vector((x, a + e2, zc - 0.004))]
                if out < 0:
                    F1 = list(reversed(F1)); F2 = list(reversed(F2))
                mb.face(F1, mc)
                mb.face(F2, ms)
