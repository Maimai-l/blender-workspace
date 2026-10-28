# pp_lib.py - paper pop-up toolkit for the Word Defense scene prototype (Blender 5.2)
# Shapes are 2D signed-distance fields (numpy, negative inside). They are traced with marching squares,
# filled (holes allowed), placed in 3D and given paper thickness with a Solidify modifier.
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix

ROOT = r"C:/Users/blender/Documents/WordDefense/popup"


# ------------------------------------------------------------------ colour
def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(h, a=1.0):
    return lin(h) + (a,)


# ------------------------------------------------------------------ noise (value noise, numpy)
_GRIDS = {}


def _grid(seed):
    g = _GRIDS.get(seed)
    if g is None:
        g = np.random.default_rng(seed).random((256, 256))
        _GRIDS[seed] = g
    return g


def vnoise(x, y, seed=0):
    g = _grid(seed)
    xf0 = np.floor(x); yf0 = np.floor(y)
    xf = x - xf0; yf = y - yf0
    xi = xf0.astype(np.int64) & 255; yi = yf0.astype(np.int64) & 255
    x1 = (xi + 1) & 255; y1 = (yi + 1) & 255
    u = xf * xf * (3 - 2 * xf); v = yf * yf * (3 - 2 * yf)
    a = g[yi, xi]; b = g[yi, x1]; c = g[y1, xi]; d = g[y1, x1]
    return (a + (b - a) * u) * (1 - v) + (c + (d - c) * u) * v


def fbm(x, y, seed=0, octaves=4, lac=2.03, gain=0.5):
    s = np.zeros_like(x, dtype=float); amp = 1.0; f = 1.0; norm = 0.0
    for o in range(octaves):
        s = s + amp * (vnoise(x * f + o * 31.7, y * f - o * 17.3, seed + o) * 2 - 1)
        norm += amp; amp *= gain; f *= lac
    return s / norm


def cut_edge(F, X, Y, seed, amp=0.012, freq=9.0, fine=0.004, fine_freq=40.0):
    """Hand-cut irregularity: a slow wobble plus fine tremor along every edge."""
    return F + amp * fbm(X * freq, Y * freq, seed, 3) + fine * fbm(X * fine_freq, Y * fine_freq, seed + 50, 2)


# ------------------------------------------------------------------ 2D signed distances
def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_ellipse(X, Y, cx, cy, rx, ry):
    return (np.hypot((X - cx) / rx, (Y - cy) / ry) - 1.0) * min(rx, ry)


def sd_capsule(X, Y, ax, ay, bx, by, ra, rb=None):
    rb = ra if rb is None else rb
    pax = X - ax; pay = Y - ay; bax = bx - ax; bay = by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay + 1e-12), 0, 1)
    return np.hypot(pax - bax * h, pay - bay * h) - (ra + (rb - ra) * h)


def sd_box(X, Y, cx, cy, hx, hy, r=0.0):
    qx = np.abs(X - cx) - hx + r; qy = np.abs(Y - cy) - hy + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_poly(X, Y, pts):
    v = np.asarray(pts, float); n = len(v)
    d = (X - v[0, 0]) ** 2 + (Y - v[0, 1]) ** 2
    s = np.ones_like(X, dtype=float)
    j = n - 1
    for i in range(n):
        ex = v[j, 0] - v[i, 0]; ey = v[j, 1] - v[i, 1]
        wx = X - v[i, 0]; wy = Y - v[i, 1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-12), 0, 1)
        bx = wx - ex * t; by = wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = Y >= v[i, 1]; c2 = Y < v[j, 1]; c3 = ex * wy > ey * wx
        s = np.where((c1 & c2 & c3) | (~c1 & ~c2 & ~c3), -s, s)
        j = i
    return s * np.sqrt(d)


def sd_polyline(X, Y, pts, r):
    d = np.full(X.shape, np.inf)
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        bax = bx - ax; bay = by - ay
        L2 = bax * bax + bay * bay
        if L2 < 1e-12:
            continue
        pax = X - ax; pay = Y - ay
        h = np.clip((pax * bax + pay * bay) / L2, 0, 1)
        d = np.minimum(d, np.hypot(pax - bax * h, pay - bay * h))
    return d - r


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def umin(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def catmull(pts, n=12):
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (np.array(P[i - 1], float), np.array(P[i], float), np.array(P[i + 1], float), np.array(P[i + 2], float))
        for k in range(n):
            t = k / n; t2 = t * t; t3 = t2 * t
            out.append(tuple(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)))
    out.append(tuple(map(float, pts[-1])))
    return out


# ------------------------------------------------------------------ marching squares
_SEG = {1: ((3, 0),), 2: ((0, 1),), 3: ((3, 1),), 4: ((1, 2),), 6: ((0, 2),), 7: ((3, 2),),
        8: ((2, 3),), 9: ((0, 2),), 11: ((1, 2),), 12: ((1, 3),), 13: ((0, 1),), 14: ((3, 0),)}


def trace(F, x0, y0, step):
    """Closed zero-contours of F (inside < 0) as lists of (x, y). F's border must be outside."""
    ny, nx = F.shape
    a = (F < 0).astype(np.int16)
    idx = a[:-1, :-1] + 2 * a[:-1, 1:] + 4 * a[1:, 1:] + 8 * a[1:, :-1]
    H = ny * nx
    adj = {}

    def key(e, i, j):
        if e == 0: return i * nx + j
        if e == 1: return H + i * nx + j + 1
        if e == 2: return (i + 1) * nx + j
        return H + i * nx + j

    for i, j in np.argwhere((idx != 0) & (idx != 15)):
        c = int(idx[i, j])
        if c in (5, 10):
            centre = (F[i, j] + F[i, j + 1] + F[i + 1, j + 1] + F[i + 1, j]) * 0.25
            if c == 5:
                segs = ((0, 1), (2, 3)) if centre < 0 else ((3, 0), (1, 2))
            else:
                segs = ((3, 0), (1, 2)) if centre < 0 else ((0, 1), (2, 3))
        else:
            segs = _SEG[c]
        for ea, eb in segs:
            ka = key(ea, i, j); kb = key(eb, i, j)
            adj.setdefault(ka, []).append(kb)
            adj.setdefault(kb, []).append(ka)

    def pos(k):
        if k < H:
            i, j = divmod(k, nx)
            f0, f1 = F[i, j], F[i, j + 1]
            t = f0 / (f0 - f1)
            return (x0 + (j + t) * step, y0 + i * step)
        i, j = divmod(k - H, nx)
        f0, f1 = F[i, j], F[i + 1, j]
        t = f0 / (f0 - f1)
        return (x0 + j * step, y0 + (i + t) * step)

    loops, seen = [], set()
    for start in adj:
        if start in seen:
            continue
        loop = [start]; seen.add(start)
        prev, cur = None, start
        while True:
            nb = adj[cur]
            nxt = nb[0] if nb[0] != prev else (nb[1] if len(nb) > 1 else None)
            if nxt is None or nxt == start or nxt in seen:
                break
            loop.append(nxt); seen.add(nxt)
            prev, cur = cur, nxt
        if len(loop) > 3:
            loops.append([pos(k) for k in loop])
    return loops


def loop_area(lp):
    P = np.asarray(lp)
    x, y = P[:, 0], P[:, 1]
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def resample(lp, seg):
    P = np.asarray(list(lp) + [lp[0]], float)
    d = np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1]))
    L = float(d.sum())
    n = max(8, int(L / seg))
    s = np.concatenate([[0.0], np.cumsum(d)])
    t = np.linspace(0, L, n, endpoint=False)
    return list(zip(np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])))


def shape_loops(fn, bounds, step, seg=None, min_area=None):
    """Sample fn(U, V) over bounds = (u0, v0, u1, v1) and return the traced outline loops."""
    u0, v0, u1, v1 = bounds
    us = np.arange(u0 - step, u1 + 2 * step, step)
    vs = np.arange(v0 - step, v1 + 2 * step, step)
    U, V = np.meshgrid(us, vs)
    F = np.asarray(fn(U, V), float)
    F[0, :] = F[-1, :] = 1.0
    F[:, 0] = F[:, -1] = 1.0
    F = np.where(np.abs(F) < 1e-9, 1e-9, F)
    min_area = (step * step * 6) if min_area is None else min_area
    out = []
    for lp in trace(F, us[0], vs[0], step):
        if abs(loop_area(lp)) >= min_area:
            out.append(resample(lp, seg or step * 0.85))
    return out


def fill2d(loops):
    """Triangulate outline loops (holes allowed) -> (verts2d, faces) with faces pointing +Z."""
    bm = bmesh.new()
    for lp in loops:
        vs = [bm.verts.new((float(x), float(y), 0.0)) for x, y in lp]
        for k in range(len(vs)):
            try:
                bm.edges.new((vs[k], vs[(k + 1) % len(vs)]))
            except ValueError:
                pass
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=bm.edges[:])
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.verts.index_update()
    verts = [(v.co.x, v.co.y) for v in bm.verts]
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return verts, faces


def shape2d(fn, bounds, step, seg=None, min_area=None):
    return fill2d(shape_loops(fn, bounds, step, seg, min_area))


# ------------------------------------------------------------------ placing 2D shapes in 3D
def frame(origin=(0, 0, 0), u=(1, 0, 0), v=(0, 0, 1)):
    """Matrix taking 2D (x, y) to origin + x*u + y*v; the 2D +Z normal becomes u x v."""
    U = Vector(u).normalized(); V = Vector(v).normalized(); N = U.cross(V)
    M = Matrix(((U.x, V.x, N.x, 0), (U.y, V.y, N.y, 0), (U.z, V.z, N.z, 0), (0, 0, 0, 1)))
    return Matrix.Translation(Vector(origin)) @ M


def facing(rot_z=0.0, origin=(0, 0, 0)):
    """Upright card whose printed side faces -Y rotated by rot_z (radians) about Z."""
    c, s = math.cos(rot_z), math.sin(rot_z)
    return frame(origin, (c, s, 0), (0, 0, 1))


FLOOR = frame((0, 0, 0), (1, 0, 0), (0, 1, 0))


class MB:
    """Mesh builder: accumulate polygons with material slots, then make one mesh."""

    def __init__(self):
        self.v, self.f, self.m, self.sm = [], [], [], []

    def add(self, verts, faces, mat=0, M=None, smooth=False):
        base = len(self.v)
        for p in verts:
            p = Vector((p[0], p[1], p[2] if len(p) > 2 else 0.0))
            self.v.append(tuple(M @ p) if M is not None else tuple(p))
        for fc in faces:
            self.f.append(tuple(base + i for i in fc)); self.m.append(mat); self.sm.append(smooth)
        return self

    def add2d(self, geom, M, mat=0):
        verts2d, faces = geom
        return self.add([(x, y, 0.0) for x, y in verts2d], faces, mat, M)

    def box(self, c, s, mat=0, M=None):
        x, y, z = c; a, b, h = s[0] / 2, s[1] / 2, s[2] / 2
        V = [(x - a, y - b, z - h), (x + a, y - b, z - h), (x + a, y + b, z - h), (x - a, y + b, z - h),
             (x - a, y - b, z + h), (x + a, y - b, z + h), (x + a, y + b, z + h), (x - a, y + b, z + h)]
        F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return self.add(V, F, mat, M)

    def lathe(self, prof, segs, mat=0, M=None, smooth=False, cap_bottom=True, cap_top=True, phase=0.0):
        """prof: [(radius, z), ...] bottom to top."""
        base = len(self.v)
        ring = []
        for r, z in prof:
            ring.append([(r * math.cos(phase + 2 * math.pi * k / segs), r * math.sin(phase + 2 * math.pi * k / segs), z) for k in range(segs)])
        V = [p for rr in ring for p in rr]
        F = []
        for a in range(len(prof) - 1):
            for k in range(segs):
                k1 = (k + 1) % segs
                F.append((a * segs + k, a * segs + k1, (a + 1) * segs + k1, (a + 1) * segs + k))
        if cap_bottom and prof[0][0] > 1e-6:
            F.append(tuple(reversed(range(segs))))
        if cap_top and prof[-1][0] > 1e-6:
            F.append(tuple((len(prof) - 1) * segs + k for k in range(segs)))
        return self.add(V, F, mat, M, smooth)

    def mesh(self, name):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        for poly, mi, sm in zip(me.polygons, self.m, self.sm):
            poly.material_index = mi
            poly.use_smooth = sm
        return me


# ------------------------------------------------------------------ objects
def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in [x.name for x in p.children]:
        p.children.link(c)
    return c


def obj(name, data, collection, mats=(), loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    if isinstance(data, MB):
        data = data.mesh(name)
    ob = bpy.data.objects.new(name, data)
    collection.objects.link(ob)
    if data is not None and hasattr(data, "materials"):
        for m in mats:
            data.materials.append(m)
    ob.location = loc
    ob.rotation_euler = rot
    if parent is not None:
        ob.parent = parent
    return ob


def solidify(ob, t=0.02, offset=-1.0, shell=0, rim=0):
    m = ob.modifiers.new("Paper", 'SOLIDIFY')
    m.thickness = t
    m.offset = offset
    m.use_even_offset = True
    m.use_rim = True
    m.material_offset = shell
    m.material_offset_rim = rim
    return m


def card(name, fn, bounds, step, collection, mats, M=None, loc=(0, 0, 0), rot=(0, 0, 0), t=0.02,
         shell=0, rim=0, parent=None, seg=None):
    """One cut-out piece of paper: 2D shape in local XZ (base at z=0, printed side facing -Y)."""
    geom = shape2d(fn, bounds, step, seg)
    mb = MB().add2d(geom, M if M is not None else facing(0.0))
    ob = obj(name, mb, collection, mats, loc, rot, parent)
    if t > 0:
        solidify(ob, t, -1.0, shell, rim)
    return ob


# ------------------------------------------------------------------ materials
def _sock(node, name):
    for s in node.inputs:
        if s.name == name or s.identifier == name:
            return s
    return None


def _set(node, **kw):
    for k, v in kw.items():
        s = _sock(node, k.replace('_', ' '))
        if s is not None:
            s.default_value = v


def _new_mat(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    return mat, nt.nodes, nt.links


def _mix_rgb(N, L, fac, a, b, blend='MIX'):
    m = N.new('ShaderNodeMix')
    m.data_type = 'RGBA'
    m.blend_type = blend
    fi = [s for s in m.inputs if s.identifier == 'Factor_Float'][0]
    ai = [s for s in m.inputs if s.identifier == 'A_Color'][0]
    bi = [s for s in m.inputs if s.identifier == 'B_Color'][0]
    for sock, val in ((fi, fac), (ai, a), (bi, b)):
        if isinstance(val, (int, float)):
            sock.default_value = val
        elif isinstance(val, tuple):
            sock.default_value = val
        else:
            L.new(val, sock)
    return [s for s in m.outputs if s.identifier == 'Result_Color'][0]


def _math(N, L, op, a, b=None, clamp=False):
    m = N.new('ShaderNodeMath')
    m.operation = op
    m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            m.inputs[i].default_value = v
        else:
            L.new(v, m.inputs[i])
    return m.outputs[0]


def _map_range(N, L, val, a0, a1, b0, b1, clamp=True):
    m = N.new('ShaderNodeMapRange')
    m.clamp = clamp
    L.new(val, m.inputs['Value'])
    m.inputs['From Min'].default_value = a0
    m.inputs['From Max'].default_value = a1
    m.inputs['To Min'].default_value = b0
    m.inputs['To Max'].default_value = b1
    return m.outputs['Result']


def _coords(N, L, seed=0.0):
    """Object coordinates offset by the object's location and a random number, so every piece differs."""
    tc = N.new('ShaderNodeTexCoord')
    oi = N.new('ShaderNodeObjectInfo')
    add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    L.new(tc.outputs['Object'], add.inputs[0])
    L.new(oi.outputs['Location'], add.inputs[1])
    rnd = N.new('ShaderNodeVectorMath'); rnd.operation = 'SCALE'
    comb = N.new('ShaderNodeCombineXYZ')
    comb.inputs[0].default_value = 13.7 + seed; comb.inputs[1].default_value = 7.3 + seed; comb.inputs[2].default_value = 21.1 + seed
    L.new(comb.outputs[0], rnd.inputs[0])
    L.new(oi.outputs['Random'], rnd.inputs['Scale'])
    add2 = N.new('ShaderNodeVectorMath'); add2.operation = 'ADD'
    L.new(add.outputs[0], add2.inputs[0]); L.new(rnd.outputs[0], add2.inputs[1])
    return add2.outputs[0], oi


def _noise(N, L, vec, scale, detail=2.0, rough=0.5, distort=0.0, dims='3D'):
    n = N.new('ShaderNodeTexNoise')
    try:
        n.noise_dimensions = dims
    except Exception:
        pass
    L.new(vec, n.inputs['Vector'])
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    _set(n, Distortion=distort)
    return n.outputs['Fac']


def _scale_vec(N, L, vec, s):
    m = N.new('ShaderNodeVectorMath'); m.operation = 'MULTIPLY'
    L.new(vec, m.inputs[0]); m.inputs[1].default_value = s
    return m.outputs[0]


def washi(name, base, var=None, *, rough=0.86, transl=0.12, mottle=1.0, mscale=0.45, fiber=0.0, grain=0.25,
          jitter=0.05, haze=None, haze_h=0.9, haze_amt=0.0, emit=None, emit_strength=0.0, sheen=0.25,
          spec=0.22, thickness=0.02, grad=None, grad_z=(0.0, 1.0), grad_amt=0.0, wgrad=None):
    """Washi-like paper: watercolour mottling, fibres, fine grain, a little translucency, optional
    ground haze (world height) and a vertical shade (object height) towards `grad`."""
    mat, N, L = _new_mat(name)
    var = var or base
    vec, oi = _coords(N, L)
    m1 = _noise(N, L, vec, mscale, 3.0, 0.55, 0.35)
    ramp = N.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[1].position = 0.68
    L.new(m1, ramp.inputs['Fac'])
    fac = _math(N, L, 'MULTIPLY', ramp.outputs['Color'], mottle)
    col = _mix_rgb(N, L, fac, rgba(base), rgba(var))
    if fiber > 0:
        # sparse, slightly curly fibres
        fa = _noise(N, L, _scale_vec(N, L, vec, (7.0, 7.0, 22.0)), 1.0, 3.0, 0.65, 1.5)
        fb = _noise(N, L, _scale_vec(N, L, vec, (22.0, 7.0, 7.0)), 1.0, 3.0, 0.65, 1.5)
        fmax = _math(N, L, 'MAXIMUM', fa, fb)
        fsharp = _map_range(N, L, fmax, 0.66, 0.86, 0.0, 1.0)
        col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', fsharp, fiber), col, (1.0, 1.0, 1.0, 1.0), 'SCREEN')
    # slow light/dark breathing like watercolour pooling
    m2 = _noise(N, L, vec, mscale * 4.0, 4.0, 0.6)
    pool = _map_range(N, L, m2, 0.42, 0.58, 0.88, 1.1)
    # pigment gathers along the edge of each wash: thin darker rims where the slow noise crosses its midpoint
    rimd = _math(N, L, 'ABSOLUTE', _math(N, L, 'SUBTRACT', m1, 0.5))
    rims = _map_range(N, L, rimd, 0.0, 0.025, 0.93, 1.0)
    pool = _math(N, L, 'MULTIPLY', pool, rims)
    hsv = N.new('ShaderNodeHueSaturation')
    L.new(col, hsv.inputs['Color'])
    jit = _map_range(N, L, oi.outputs['Random'], 0.0, 1.0, 1.0 - jitter, 1.0 + jitter)
    L.new(_math(N, L, 'MULTIPLY', pool, jit), hsv.inputs['Value'])
    col = hsv.outputs['Color']
    if grad is not None and grad_amt > 0:
        tc = N.new('ShaderNodeTexCoord')
        sep = N.new('ShaderNodeSeparateXYZ')
        L.new(tc.outputs['Object'], sep.inputs[0])
        g = _map_range(N, L, sep.outputs['Z'], grad_z[0], grad_z[1], 1.0, 0.0)
        col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', g, grad_amt), col, rgba(grad))
    if wgrad is not None:
        # world-space gradient: (hex, axis, from, to, amount) -> full colour at `from`, none at `to`
        gh, gax, g0, g1, gamt = wgrad
        geo = N.new('ShaderNodeNewGeometry')
        sep = N.new('ShaderNodeSeparateXYZ')
        L.new(geo.outputs['Position'], sep.inputs[0])
        g = _map_range(N, L, sep.outputs[gax], g0, g1, 1.0, 0.0)
        g = _math(N, L, 'POWER', g, 1.3)
        col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', g, gamt), col, rgba(gh))
    if haze is not None and haze_amt > 0:
        geo = N.new('ShaderNodeNewGeometry')
        sep = N.new('ShaderNodeSeparateXYZ')
        L.new(geo.outputs['Position'], sep.inputs[0])
        hz = _map_range(N, L, sep.outputs['Z'], 0.0, haze_h, 1.0, 0.0)
        hz = _math(N, L, 'POWER', hz, 1.6)
        col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', hz, haze_amt), col, rgba(haze))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=rough)
    _set(bsdf, **{'Specular IOR Level': spec, 'Sheen Weight': sheen, 'Sheen Roughness': 0.6})
    gn = _noise(N, L, vec, 160.0, 2.0, 0.5)
    bump = N.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = grain * 0.32
    bump.inputs['Distance'].default_value = 0.002
    L.new(gn, bump.inputs['Height'])
    L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    if emit is not None and emit_strength > 0:
        bsdf.inputs['Emission Color'].default_value = rgba(emit)
        bsdf.inputs['Emission Strength'].default_value = emit_strength
    out = N.new('ShaderNodeOutputMaterial')
    if transl > 0:
        tr = N.new('ShaderNodeBsdfTranslucent')
        L.new(col, tr.inputs['Color'])
        mix = N.new('ShaderNodeMixShader')
        mix.inputs['Fac'].default_value = transl
        L.new(bsdf.outputs[0], mix.inputs[1]); L.new(tr.outputs[0], mix.inputs[2])
        L.new(mix.outputs[0], out.inputs['Surface'])
    else:
        L.new(bsdf.outputs[0], out.inputs['Surface'])
    if 'Thickness' in out.inputs:
        out.inputs['Thickness'].default_value = thickness
    return mat


def sky(name, stops, z0, z1, mottle_col, emit=0.25, mscale=0.18):
    """Back-page print: vertical colour ramp over world height with soft watercolour clouds."""
    mat, N, L = _new_mat(name)
    geo = N.new('ShaderNodeNewGeometry')
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(geo.outputs['Position'], sep.inputs[0])
    t = _map_range(N, L, sep.outputs['Z'], z0, z1, 0.0, 1.0)
    vec, oi = _coords(N, L)
    wob = _noise(N, L, vec, 0.35, 2.0, 0.5)
    t = _math(N, L, 'ADD', t, _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', wob, 0.5), 0.12))
    ramp = N.new('ShaderNodeValToRGB')
    cr = ramp.color_ramp
    cr.interpolation = 'EASE'
    while len(cr.elements) < len(stops):
        cr.elements.new(0.5)
    for el, (p, h) in zip(cr.elements, stops):
        el.position = p
        el.color = rgba(h)
    L.new(t, ramp.inputs['Fac'])
    m1 = _noise(N, L, vec, mscale, 4.0, 0.62, 0.5)
    mf = _map_range(N, L, m1, 0.45, 0.75, 0.0, 0.45)
    col = _mix_rgb(N, L, mf, ramp.outputs['Color'], rgba(mottle_col), 'SOFT_LIGHT')
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.92)
    _set(bsdf, **{'Specular IOR Level': 0.15, 'Sheen Weight': 0.2})
    L.new(col, bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = emit
    gn = _noise(N, L, vec, 160.0, 2.0, 0.5)
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.04; bump.inputs['Distance'].default_value = 0.002
    L.new(gn, bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def glow(name, col, strength=4.0, transl_col=None):
    """Lit vellum: warm emission plus a translucent layer."""
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    n = _noise(N, L, vec, 6.0, 3.0, 0.55)
    s = _map_range(N, L, n, 0.3, 0.7, strength * 0.8, strength * 1.15)
    em = N.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = rgba(col)
    L.new(s, em.inputs['Strength'])
    out = N.new('ShaderNodeOutputMaterial')
    L.new(em.outputs[0], out.inputs['Surface'])
    return mat


def water(name, base, light, line):
    """Glossy printed water: soft banding and fine wave lines."""
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    w = N.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'X'
    L.new(_scale_vec(N, L, vec, (1.0, 1.6, 1.0)), w.inputs['Vector'])
    w.inputs['Scale'].default_value = 1.7
    w.inputs['Distortion'].default_value = 7.5
    w.inputs['Detail'].default_value = 2.0
    _set(w, **{'Detail Scale': 1.2})
    lines = _map_range(N, L, w.outputs['Fac'], 0.9, 0.975, 0.0, 1.0)
    m = _noise(N, L, vec, 0.7, 3.0, 0.55)
    mf = _map_range(N, L, m, 0.35, 0.7, 0.0, 1.0)
    col = _mix_rgb(N, L, mf, rgba(base), rgba(light))
    col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', lines, 0.32), col, rgba(line))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.28)
    _set(bsdf, **{'Specular IOR Level': 0.55, 'Coat Weight': 0.35, 'Coat Roughness': 0.15})
    gn = _noise(N, L, vec, 120.0, 2.0, 0.5)
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.05; bump.inputs['Distance'].default_value = 0.002
    L.new(gn, bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def page_edges(name, paper, line, scale=95.0):
    """Side of a stack of pages: fine horizontal lines."""
    mat, N, L = _new_mat(name)
    tc = N.new('ShaderNodeTexCoord')
    w = N.new('ShaderNodeTexWave')
    w.wave_type = 'BANDS'
    w.bands_direction = 'Z'
    L.new(tc.outputs['Object'], w.inputs['Vector'])
    w.inputs['Scale'].default_value = scale
    w.inputs['Distortion'].default_value = 0.6
    w.inputs['Detail'].default_value = 1.0
    lines = _map_range(N, L, w.outputs['Fac'], 0.7, 1.0, 0.0, 1.0)
    vec, oi = _coords(N, L)
    m = _noise(N, L, vec, 3.0, 2.0, 0.5)
    col = _mix_rgb(N, L, lines, rgba(paper), rgba(line))
    col = _mix_rgb(N, L, _map_range(N, L, m, 0.3, 0.7, 0.0, 0.25), col, rgba(line))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.9)
    _set(bsdf, **{'Specular IOR Level': 0.2})
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def cloth(name, base, thread):
    """Book cloth on the cover boards."""
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    wa = N.new('ShaderNodeTexWave'); wa.wave_type = 'BANDS'; wa.bands_direction = 'X'
    wb = N.new('ShaderNodeTexWave'); wb.wave_type = 'BANDS'; wb.bands_direction = 'Y'
    for w in (wa, wb):
        L.new(vec, w.inputs['Vector']); w.inputs['Scale'].default_value = 140.0; w.inputs['Distortion'].default_value = 0.4
    weave = _math(N, L, 'MULTIPLY', wa.outputs['Fac'], wb.outputs['Fac'])
    m = _noise(N, L, vec, 2.0, 3.0, 0.5)
    col = _mix_rgb(N, L, _map_range(N, L, m, 0.3, 0.7, 0.0, 0.5), rgba(base), rgba(thread))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.8)
    _set(bsdf, **{'Sheen Weight': 0.6, 'Specular IOR Level': 0.2})
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.25; bump.inputs['Distance'].default_value = 0.003
    L.new(weave, bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def wood(name, dark, light, rough=0.45, coat=0.3):
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    w = N.new('ShaderNodeTexWave'); w.wave_type = 'RINGS'
    L.new(_scale_vec(N, L, vec, (0.25, 4.0, 0.25)), w.inputs['Vector'])
    w.inputs['Scale'].default_value = 1.6; w.inputs['Distortion'].default_value = 8.0; w.inputs['Detail'].default_value = 3.0
    col = _mix_rgb(N, L, _map_range(N, L, w.outputs['Fac'], 0.2, 0.9, 0.0, 1.0), rgba(dark), rgba(light))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=rough)
    _set(bsdf, **{'Specular IOR Level': 0.3, 'Coat Weight': coat})
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


# ------------------------------------------------------------------ lights
def light(name, kind, collection, loc, rot=(0, 0, 0), energy=10.0, color=(1, 1, 1), size=0.1, size_y=None,
          shadow=True, spot=None, blend=0.3, soft=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == 'AREA':
        ld.shape = 'RECTANGLE' if size_y is not None else 'SQUARE'
        ld.size = size
        if size_y is not None:
            ld.size_y = size_y
    elif kind == 'SUN':
        ld.angle = size
    else:
        ld.shadow_soft_size = size
    if kind == 'SPOT' and spot is not None:
        ld.spot_size = spot
        ld.spot_blend = blend
    try:
        ld.use_shadow = shadow
    except Exception:
        pass
    ob = bpy.data.objects.new(name, ld)
    collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def aim(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


# ------------------------------------------------------------------ housekeeping
def wipe():
    """Remove everything this file holds so a rebuild starts clean (only used in WD_Popup.blend)."""
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll_ in list(bpy.data.collections):
        bpy.data.collections.remove(coll_)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.node_groups):
        for item in list(block):
            try:
                block.remove(item)
            except Exception:
                pass
    for img in list(bpy.data.images):
        if img.name not in ("Render Result", "Viewer Node"):
            bpy.data.images.remove(img)
