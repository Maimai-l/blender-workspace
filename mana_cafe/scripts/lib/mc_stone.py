"""Dry-stone walls and flagstone paving as real geometry: every stone is its own rounded, chipped block.

Built with numpy from the site design (mc_site) and the graded ground (dem/site_h.npz)."""
import bpy, os, math, zlib
import numpy as np
import mc_core as C
import mc_site
from mc_core import NT


class Ground:
    """Graded site ground on a 0.1 m grid (written by proc/mesh_near.py)."""

    def __init__(self):
        d = np.load(os.path.join(C.DEM, 'site_h.npz'))
        self.zg = d['z']
        self.tg = d['track'].astype(np.float32)
        self.sg = d['sdf'].astype(np.float32)
        self.x0, self.y0, self.cell = float(d['x0']), float(d['y0']), float(d['cell'])

    def _s(self, a, x, y):
        c = (np.asarray(x, float) - self.x0) / self.cell
        r = (np.asarray(y, float) - self.y0) / self.cell
        H, W = a.shape
        c = np.clip(c, 0, W - 1.001)
        r = np.clip(r, 0, H - 1.001)
        c0 = c.astype(int)
        r0 = r.astype(int)
        fc = c - c0
        fr = r - r0
        return (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0 + 1, c0] * fr * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc +
                a[r0 + 1, c0 + 1] * fr * fc)

    def z(self, x, y):
        return self._s(self.zg, x, y)

    def track(self, x, y):
        return self._s(self.tg, x, y)

    def sdf(self, x, y):
        return self._s(self.sg, x, y)


# ------------------------------------------------------------------ one stone = one rounded, chipped block
def _axis(n):
    return {6: np.array([-1, -0.86, -0.3, 0.3, 0.86, 1.0]), 5: np.array([-1, -0.86, 0.0, 0.86, 1.0]),
            4: np.array([-1, -0.8, 0.8, 1.0])}[n]


def _template(nx=6, ny=5, nz=4):
    """Surface grid of a box: returns (params [Nv,3] in -1..1 with 'edge band' coordinates, quads [Nq,4])."""
    ax, ay, az = _axis(nx), _axis(ny), _axis(nz)
    idx = -np.ones((nx, ny, nz), int)
    pts = []
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if i in (0, nx - 1) or j in (0, ny - 1) or k in (0, nz - 1):
                    idx[i, j, k] = len(pts)
                    pts.append((ax[i], ay[j], az[k]))
    q = []
    for i in range(nx - 1):
        for j in range(ny - 1):
            q.append((idx[i, j, 0], idx[i, j + 1, 0], idx[i + 1, j + 1, 0], idx[i + 1, j, 0]))
            q.append((idx[i, j, nz - 1], idx[i + 1, j, nz - 1], idx[i + 1, j + 1, nz - 1], idx[i, j + 1, nz - 1]))
    for i in range(nx - 1):
        for k in range(nz - 1):
            q.append((idx[i, 0, k], idx[i + 1, 0, k], idx[i + 1, 0, k + 1], idx[i, 0, k + 1]))
            q.append((idx[i, ny - 1, k], idx[i, ny - 1, k + 1], idx[i + 1, ny - 1, k + 1], idx[i + 1, ny - 1, k]))
    for j in range(ny - 1):
        for k in range(nz - 1):
            q.append((idx[0, j, k], idx[0, j, k + 1], idx[0, j + 1, k + 1], idx[0, j + 1, k]))
            q.append((idx[nx - 1, j, k], idx[nx - 1, j + 1, k], idx[nx - 1, j + 1, k + 1], idx[nx - 1, j, k + 1]))
    return np.array(pts), np.array(q)


def stones_mesh(name, centre, half, frame, seed, round_r=0.014, chip=0.02, warp=0.006, flat_top=0.0):
    """N stones. centre [N,3]; half [N,3] half-sizes along the stone's own axes; frame [N,3,3] rows = axes in world.
    Returns a mesh with per-vertex attributes sid (random per stone) and up (1 on faces of the stone that look up)."""
    T, Q = _template()
    N = len(centre)
    rng = np.random.default_rng(seed)
    nv = len(T)
    # the template's band coordinate 0.86 / 0.8 marks where the rounding starts: place it at (half - r)
    r = np.minimum(round_r * rng.uniform(0.6, 1.5, (N, 1)), half.min(1, keepdims=True) * 0.45)       # [N,1]
    P = np.empty((N, nv, 3))
    for a in range(3):
        t = T[:, a][None, :]
        h = half[:, a][:, None]
        at = np.abs(t)
        x = np.where(at > 0.999, h, np.where(at > 0.75, h - r, at / 0.86 * (h - r)))
        P[:, :, a] = np.sign(t) * x
    # round: clamp to the inner box, push out by r
    inner = np.clip(P, -(half[:, None, :] - r[:, None, :]), half[:, None, :] - r[:, None, :])
    d = P - inner
    L = np.linalg.norm(d, axis=2, keepdims=True)
    P = inner + np.where(L > 1e-9, d / np.maximum(L, 1e-9), 0.0) * r[:, None, :]
    # chipped corners: each of the 8 corners loses a random amount
    sg = np.sign(T)                                                              # [nv,3]
    for cx in (-1, 1):
        for cy in (-1, 1):
            for cz in (-1, 1):
                amt = chip * rng.uniform(0.0, 1.0, (N, 1)) ** 2.2 * 2.2
                c = np.array([cx, cy, cz])
                w = np.clip((T * c).min(1) - 0.25, 0, 1) / 0.75                 # 1 at that corner, 0 away from it
                w = (w ** 1.5)[None, :, None]
                P -= w * c[None, None, :] * np.minimum(amt[:, :, None], 0.6 * half[:, None, :])
    # gentle warp of the faces (three sines with random phases per stone), fades towards the top if flat_top
    k = rng.uniform(6.0, 22.0, (N, 3, 3))
    ph = rng.uniform(0, 6.28, (N, 3))
    amp = warp * rng.uniform(0.5, 1.6, (N, 1))
    for i in range(3):
        s = np.sin((P * k[:, i][:, None, :]).sum(2) + ph[:, i][:, None])
        P += (s * amp)[:, :, None] * (T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-6))[None, :, :] * \
            (1.0 - flat_top * np.clip(T[:, 2], 0, 1))[None, :, None]
    # to world
    Wd = np.einsum('nvi,nij->nvj', P, frame) + centre[:, None, :]
    co = Wd.reshape(-1, 3)
    quads = (Q[None, :, :] + (np.arange(N) * nv)[:, None, None]).reshape(-1, 4)
    sid = np.repeat(rng.uniform(0, 1, N), nv)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.loops.add(len(quads) * 4)
    me.loops.foreach_set('vertex_index', quads.astype(np.int32).ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set('loop_start', np.arange(0, len(quads) * 4, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    me.attributes.new('sid', 'FLOAT', 'POINT').data.foreach_set('value', sid.astype(np.float32))
    return me


# ------------------------------------------------------------------ walls
def _runs(mask):
    """Index ranges of consecutive True values in a closed loop mask."""
    n = len(mask)
    if mask.all():
        return [(0, n)]
    start = next(i for i in range(n) if mask[i] and not mask[i - 1])
    out = []
    i = start
    cnt = 0
    while cnt < n:
        if mask[i % n]:
            j = i
            while mask[j % n] and (j - i) < n:
                j += 1
            out.append((i, j))
            cnt += j - i
            i = j
        else:
            i += 1
            cnt += 1
    return out


def wall_paths(g):
    """Wall centre lines round the terrace: list of dicts with world xy [n,2], outward normal [n,2], top [n],
    foot_out [n], foot_in [n]."""
    step = 0.05
    P = np.vstack([mc_site.TERRACE, mc_site.TERRACE[:1]])
    pl, _ = mc_site.polyline_resample(P, step)
    u, v = pl[:, 0], pl[:, 1]
    on = ~((u < -5.0) & (v > -11.3) & (v < 9.62)) & ~((u > 7.4) & (v > 1.62) & (v < 4.40))
    out = []
    n = len(pl)
    for a, b in _runs(on):
        ii = np.arange(a, b) % n
        if len(ii) < 12:
            continue
        uu, vv = u[ii], v[ii]
        # smooth the line a little so the wall flows
        k = 9
        w = np.hanning(2 * k + 1)
        w /= w.sum()
        up = np.r_[np.repeat(uu[:1], k), uu, np.repeat(uu[-1:], k)]
        vp = np.r_[np.repeat(vv[:1], k), vv, np.repeat(vv[-1:], k)]
        uu, vv = np.convolve(up, w, 'valid'), np.convolve(vp, w, 'valid')
        tu, tv = np.gradient(uu), np.gradient(vv)
        L = np.hypot(tu, tv)
        tu, tv = tu / L, tv / L
        nu, nv = tv, -tu                                                    # one of the two normals
        x, y = mc_site.to_world(uu, vv)
        nx_, ny_ = mc_site.to_world(nu, nv)
        if np.mean(g.sdf(x + nx_ * 0.6, y + ny_ * 0.6)) < np.mean(g.sdf(x - nx_ * 0.6, y - ny_ * 0.6)):
            nx_, ny_ = -nx_, -ny_
        z_out = g.z(x + nx_ * (mc_site.WALL_T / 2 + 0.12), y + ny_ * (mc_site.WALL_T / 2 + 0.12))
        kk = 30
        ww = np.hanning(2 * kk + 1)
        ww /= ww.sum()
        zs = np.convolve(np.r_[np.repeat(z_out[:1], kk), z_out, np.repeat(z_out[-1:], kk)], ww, 'valid')
        top = np.maximum(mc_site.Z_T + mc_site.PARAPET, zs + 0.80)
        s = np.arange(len(x)) * step
        top = top + 0.02 * np.sin(s * 0.9 + a) + 0.012 * np.sin(s * 2.7 + 1.3 * a)
        out.append(dict(xy=np.c_[x, y], n=np.c_[nx_, ny_], top=top, foot_out=z_out - 0.14,
                        foot_in=np.full(len(x), mc_site.Z_T - 0.06), s=s))
    return out


def build_walls(name='MC_walls', seed=11):
    g = Ground()
    rng = np.random.default_rng(seed)
    C_, H_, F_ = [], [], []
    T = mc_site.WALL_T

    def add(c, h, f):
        C_.append(c)
        H_.append(h)
        F_.append(f)

    def frame_at(tx, ty, yaw=0.0, tilt=0.0, roll=0.0):
        """Rows: stone x axis (along the wall), y (through the wall), z (up), with small random rotations."""
        t = np.array([tx, ty, 0.0])
        nrm = np.array([ty, -tx, 0.0])
        up = np.array([0.0, 0.0, 1.0])
        cy, sy = math.cos(yaw), math.sin(yaw)
        t2 = t * cy + nrm * sy
        n2 = -t * sy + nrm * cy
        ct, st = math.cos(tilt), math.sin(tilt)
        t3 = t2 * ct + up * st
        u3 = -t2 * st + up * ct
        cr, sr = math.cos(roll), math.sin(roll)
        n4 = n2 * cr + u3 * sr
        u4 = -n2 * sr + u3 * cr
        return np.stack([t3, n4, u4])

    for W in wall_paths(g):
        xy, nrm, top, s = W['xy'], W['n'], W['top'], W['s']
        tan = np.c_[-nrm[:, 1], nrm[:, 0]]
        Ltot = s[-1]
        for side, foot in ((1.0, W['foot_out']), (-1.0, W['foot_in'])):
            z0 = float(foot.min())
            zc = z0
            while zc < float(top.max()) - 0.05:
                hc = rng.uniform(0.055, 0.135)
                sc = rng.uniform(0.0, 0.25)
                while sc < Ltot - 0.06:
                    Ls = float(np.clip(rng.lognormal(math.log(0.30), 0.42), 0.13, 0.62))
                    Ls = min(Ls, Ltot - sc)
                    i = int(np.clip(np.searchsorted(s, sc + Ls / 2), 0, len(s) - 1))
                    hh = hc * rng.uniform(0.82, 1.12)
                    zb = zc + rng.uniform(-0.006, 0.006)
                    cap_z = top[i] - 0.075
                    if zb + hh > foot[i] and zb < cap_z - 0.02 and Ls > 0.07:
                        hh2 = min(hh, cap_z - zb + 0.01)
                        depth = rng.uniform(0.17, 0.30)
                        face = T / 2 + rng.normal(0, 0.011)
                        c = np.array([xy[i, 0] + nrm[i, 0] * side * (face - depth / 2),
                                      xy[i, 1] + nrm[i, 1] * side * (face - depth / 2), zb + hh2 / 2])
                        add(c, np.array([Ls / 2 - rng.uniform(0.002, 0.012), depth / 2, hh2 / 2 - rng.uniform(0.001, 0.006)]),
                            frame_at(tan[i, 0], tan[i, 1], rng.normal(0, 0.035), rng.normal(0, 0.02), rng.normal(0, 0.03)))
                    sc += Ls
                zc += hc
        # hearting: a core block so that no light passes through the joints
        sc = 0.0
        while sc < Ltot:
            Ls = min(0.5, Ltot - sc)
            i = int(np.clip(np.searchsorted(s, sc + Ls / 2), 0, len(s) - 1))
            zb = min(W['foot_out'][i], W['foot_in'][i])
            zt = top[i] - 0.09
            if zt - zb > 0.05 and Ls > 0.05:
                add(np.array([xy[i, 0], xy[i, 1], (zb + zt) / 2]), np.array([Ls / 2 + 0.02, T / 2 - 0.10, (zt - zb) / 2]),
                    frame_at(tan[i, 0], tan[i, 1]))
            sc += Ls
        # cope stones: broad slabs across the full width, uneven
        sc = rng.uniform(0, 0.1)
        while sc < Ltot - 0.1:
            Ls = float(np.clip(rng.lognormal(math.log(0.46), 0.3), 0.26, 0.85))
            Ls = min(Ls, Ltot - sc)
            i = int(np.clip(np.searchsorted(s, sc + Ls / 2), 0, len(s) - 1))
            th = rng.uniform(0.045, 0.085)
            wd = T / 2 + rng.uniform(0.01, 0.05)
            off = rng.normal(0, 0.015)
            add(np.array([xy[i, 0] + nrm[i, 0] * off, xy[i, 1] + nrm[i, 1] * off, top[i] - 0.075 + th / 2 + rng.uniform(-0.004, 0.01)]),
                np.array([Ls / 2 - rng.uniform(0.003, 0.012), wd, th / 2]),
                frame_at(tan[i, 0], tan[i, 1], rng.normal(0, 0.03), rng.normal(0, 0.018), rng.normal(0, 0.025)))
            sc += Ls
        # wall ends: stacked through-stones
        for i in (0, len(s) - 1):
            zb = min(W['foot_out'][i], W['foot_in'][i])
            zc = zb
            while zc < top[i] - 0.08:
                hh = rng.uniform(0.07, 0.14)
                hh = min(hh, top[i] - 0.075 - zc + 0.01)
                add(np.array([xy[i, 0], xy[i, 1], zc + hh / 2]), np.array([rng.uniform(0.10, 0.17), T / 2 + rng.normal(0, 0.01), hh / 2 - 0.003]),
                    frame_at(tan[i, 0], tan[i, 1], rng.normal(0, 0.03), 0.0, rng.normal(0, 0.02)))
                zc += hh
    centre, half, frame = np.array(C_), np.array(H_), np.array(F_)
    me = stones_mesh(name, centre, half, frame, seed)
    o = C.obj(name, me, C.coll('MC_site'), stone_material())
    return o, len(centre)


# ------------------------------------------------------------------ paving
def build_paving(name='MC_paving', seed=5):
    """Flagstones from the Voronoi cells written by proc/paving.py; each stone a low slab with worn edges."""
    d = np.load(os.path.join(C.DEM, 'paving.npz'))
    P, off = d['pts'], d['off']
    rng = np.random.default_rng(seed)
    verts, faces, sid, top = [], [], [], []
    nv = 0
    for i in range(len(off) - 1):
        poly = P[off[i]:off[i + 1]]
        n = len(poly)
        if n < 3:
            continue
        cen = poly.mean(0)
        # worn edges: a few millimetres of wander along each side, corners knocked off
        pts = []
        for j in range(n):
            a, b = poly[j], poly[(j + 1) % n]
            e = b - a
            L = np.linalg.norm(e)
            if L < 1e-4:
                continue
            nr = np.array([e[1], -e[0]]) / L
            prev = poly[j] - poly[j - 1]
            turn = abs(np.cross(prev / max(np.linalg.norm(prev), 1e-9), e / L))
            if turn > 0.5:                                    # a real corner: cut it
                cut = min(0.03, L * 0.3) * rng.uniform(0.3, 1.4)
                pts.append(a + e * (cut / L) + nr * rng.normal(0, 0.002))
            else:
                pts.append(a + nr * rng.normal(0, 0.0025))
            if turn <= 0.5 or L > 0.1:
                nxt = poly[(j + 2) % n] - b
                turn2 = abs(np.cross(e / L, nxt / max(np.linalg.norm(nxt), 1e-9)))
                if turn2 > 0.5:
                    cut = min(0.03, L * 0.3) * rng.uniform(0.3, 1.4)
                    pts.append(b - e * (cut / L) + nr * rng.normal(0, 0.002))
        pts = np.array(pts)
        m = len(pts)
        z0 = mc_site.Z_T + 0.016 + rng.normal(0, 0.004)
        tilt = rng.normal(0, 0.006, 2)
        zt = z0 + (pts - cen) @ tilt
        zc = z0 + 0.001
        wx, wy = mc_site.to_world(pts[:, 0], pts[:, 1])
        cx, cy = mc_site.to_world(cen[0], cen[1])
        # ring 0: top edge; ring 1: shoulder (2 cm in, slightly lower edge -> worn arris); ring 2: skirt bottom
        inner = cen + (pts - cen) * (1 - 0.02 / max(np.linalg.norm(pts - cen, axis=1).mean(), 0.05))
        ix, iy = mc_site.to_world(inner[:, 0], inner[:, 1])
        base = nv
        for k in range(m):
            verts.append((ix[k], iy[k], zt[k] + 0.001))
        for k in range(m):
            verts.append((wx[k], wy[k], zt[k] - 0.006))
        for k in range(m):
            verts.append((wx[k] + (wx[k] - cx) * 0.01, wy[k] + (wy[k] - cy) * 0.01, zt[k] - 0.05))
        verts.append((cx, cy, zc))
        cidx = base + 3 * m
        for k in range(m):
            k2 = (k + 1) % m
            faces.append((cidx, base + k, base + k2, -1))
            faces.append((base + k, base + m + k, base + m + k2, base + k2))
            faces.append((base + m + k, base + 2 * m + k, base + 2 * m + k2, base + m + k2))
        r = rng.uniform()
        sid += [r] * (3 * m + 1)
        nv += 3 * m + 1
    co = np.array(verts, np.float32)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    loops, starts = [], []
    for f in faces:
        starts.append(len(loops))
        loops += [v for v in f if v >= 0]
    me.loops.add(len(loops))
    me.loops.foreach_set('vertex_index', np.array(loops, np.int32))
    me.polygons.add(len(starts))
    me.polygons.foreach_set('loop_start', np.array(starts, np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    me.shade_flat()
    me.attributes.new('sid', 'FLOAT', 'POINT').data.foreach_set('value', np.array(sid, np.float32))
    o = C.obj(name, me, C.coll('MC_site'), stone_material('MC_flagstone', paving=True))
    return o, len(off) - 1


def build_paving_bed(name='MC_paving_bed'):
    """Grit between and under the flagstones: the terrace outline as one n-gon fan, 3 cm below the stone tops."""
    P = mc_site.TERRACE
    x, y = mc_site.to_world(P[:, 0], P[:, 1])
    n = len(P)
    # triangulate with Blender (the outline is concave)
    from mathutils.geometry import tessellate_polygon
    from mathutils import Vector
    tris = tessellate_polygon([[Vector((x[i], y[i], 0.0)) for i in range(n)]])
    co = np.c_[x, y, np.full(n, mc_site.Z_T + 0.005)]
    me = C.tri_mesh(name, co, np.array(tris, np.int32))
    o = C.obj(name, me, C.coll('MC_site'), grit_material())
    return o


# ------------------------------------------------------------------ materials
def stone_material(name='MC_drystone', paving=False):
    """Local slate and schist: grey to brown per stone, bedding lines on the broken edges, pale and ochre lichen on
    the weather sides, earth in the lowest courses."""
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    geo = n.node('ShaderNodeNewGeometry')
    P = geo.outputs['Position']
    sid = n.attr('sid').outputs['Fac']
    Nz = n.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Normal']}).outputs['Z']
    z = n.node('ShaderNodeSeparateXYZ', inputs={0: P}).outputs['Z']
    if paving:
        tone = n.ramp(sid, [(0.0, (0.105, 0.100, 0.096, 1)), (0.35, (0.150, 0.140, 0.128, 1)), (0.7, (0.185, 0.165, 0.140, 1)),
                            (0.9, (0.125, 0.122, 0.122, 1)), (1.0, (0.21, 0.185, 0.15, 1))])
    else:
        tone = n.ramp(sid, [(0.0, (0.038, 0.040, 0.044, 1)), (0.25, (0.085, 0.083, 0.082, 1)), (0.5, (0.13, 0.118, 0.105, 1)),
                            (0.72, (0.165, 0.135, 0.10, 1)), (0.88, (0.10, 0.098, 0.10, 1)), (1.0, (0.21, 0.18, 0.14, 1))])
    n1 = n.noise(P, 9.0, 5, 0.65, dist=0.5).outputs['Fac']
    n2 = n.noise(P, 55.0, 4, 0.7).outputs['Fac']
    n3 = n.noise(P, 240.0, 3, 0.6).outputs['Fac']
    col = n.mix(1.0, tone, n.ramp(n1, [(0.2, (0.62, 0.62, 0.62, 1)), (0.8, (1.35, 1.33, 1.3, 1))]), 'MULTIPLY')
    col = n.mix(1.0, col, n.ramp(n2, [(0.25, (0.8, 0.8, 0.8, 1)), (0.75, (1.2, 1.2, 1.2, 1))]), 'MULTIPLY')
    # iron staining
    col = n.mix(n.math('MULTIPLY', n.smooth(n1, 0.6, 0.85), n.smooth(sid, 0.3, 0.7)), col, (0.20, 0.105, 0.05, 1))
    # bedding: fine horizontal lines on the steep (broken) faces
    side = n.smooth(n.math('ABSOLUTE', Nz), 0.75, 0.35)
    bed = n.node('ShaderNodeTexNoise', noise_dimensions='1D',
                 inputs={'W': n.math('ADD', n.math('MULTIPLY', z, 260.0), n.math('MULTIPLY', n1, 6.0)), 'Scale': 1.0, 'Detail': 2.0})
    col = n.mix(n.math('MULTIPLY', side, n.math('MULTIPLY', n.smooth(bed.outputs['Fac'], 0.55, 0.75), 0.45)), col, (0.03, 0.03, 0.032, 1))
    # lichen: crusts on the upward and outward faces, where the rain and light reach
    expo = n.smooth(Nz, -0.2, 0.7)
    lpos = n.noise(P, 14.0, 5, 0.7, dist=1.2).outputs['Fac']
    lich = n.math('MULTIPLY', n.smooth(lpos, 0.58, 0.68), n.math('ADD', 0.35, n.math('MULTIPLY', expo, 0.65)))
    lcol = n.ramp(n3, [(0.3, (0.36, 0.38, 0.33, 1)), (0.7, (0.52, 0.53, 0.47, 1))])
    col = n.mix(n.math('MULTIPLY', lich, 0.0 if paving else 0.75), col, lcol)
    olich = n.math('MULTIPLY', n.smooth(n.noise(P, 23.0, 4, 0.6, dist=0.8, dims='4D', w=7.7).outputs['Fac'], 0.70, 0.76), expo)
    col = n.mix(n.math('MULTIPLY', olich, 0.0 if paving else 0.8), col, (0.46, 0.27, 0.035, 1))
    if paving:
        # foot-worn: paler and smoother in the middle of each slab, dust in the low spots
        dustn = n.noise(P, 2.2, 5, 0.6).outputs['Fac']
        col = n.mix(n.math('MULTIPLY', n.smooth(dustn, 0.45, 0.75), 0.35), col, (0.20, 0.175, 0.14, 1))
    else:
        # earth and damp in the lowest courses
        ao = n.node('ShaderNodeAmbientOcclusion', inputs={'Distance': 0.25}, samples=4)
        col = n.mix(n.math('MULTIPLY', n.smooth(ao.outputs['AO'], 0.75, 0.25), 0.55), col, (0.045, 0.036, 0.028, 1))
    bh = n.math('ADD', n.math('MULTIPLY', n2, 0.004), n.math('ADD', n.math('MULTIPLY', n3, 0.0012),
                                                           n.math('MULTIPLY', n.math('MULTIPLY', side, bed.outputs['Fac']), 0.004)))
    bh = n.math('ADD', bh, n.math('MULTIPLY', lich, 0.0015))
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 1.0, 'Height': bh})
    rough = n.mixf(lich, n.math('ADD', 0.62 if paving else 0.72, n.math('MULTIPLY', n2, 0.2)), 0.95)
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': rough, 'Normal': bump.outputs[0],
                                                      'Specular IOR Level': 0.35})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


def grit_material(name='MC_grit'):
    """Compacted grit and earth in the joints of the paving."""
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    geo = n.node('ShaderNodeNewGeometry')
    P = geo.outputs['Position']
    a = n.noise(P, 6.0, 5, 0.6).outputs['Fac']
    b = n.noise(P, 180.0, 4, 0.7).outputs['Fac']
    c = n.noise(P, 700.0, 2, 0.5).outputs['Fac']
    col = n.ramp(b, [(0.2, (0.060, 0.050, 0.040, 1)), (0.5, (0.115, 0.098, 0.078, 1)), (0.8, (0.20, 0.18, 0.15, 1))])
    col = n.mix(n.math('MULTIPLY', n.smooth(a, 0.5, 0.75), 0.5), col, (0.075, 0.062, 0.045, 1))
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 1.0,
                                            'Height': n.math('ADD', n.math('MULTIPLY', b, 0.006), n.math('MULTIPLY', c, 0.003))})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': 0.9, 'Normal': bump.outputs[0]})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


# ------------------------------------------------------------------ retaining walls from the Megascans wall scan
def _mesh_arrays(me):
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    nl = len(me.loops)
    li = np.empty(nl, np.int32)
    me.loops.foreach_get('vertex_index', li)
    ls = np.empty(len(me.polygons), np.int32)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    uv = np.empty(nl * 2, np.float32)
    me.uv_layers[0].uv.foreach_get('vector', uv)
    return co.reshape(-1, 3), li, ls, lt, uv.reshape(-1, 2)


def wall_module(key='mossy_wall', budget=110000):
    """Decimated copy of the wall scan (cached as mesh 'FAB_<key>_module')."""
    import mc_fab
    name = 'FAB_%s_module' % key
    me = bpy.data.meshes.get(name)
    if me is not None:
        return me
    src = mc_fab.objects(key)[0]
    tmp = bpy.data.objects.new('tmp_wall', src.data)
    bpy.context.scene.collection.objects.link(tmp)
    md = tmp.modifiers.new('dec', 'DECIMATE')
    md.ratio = min(1.0, budget / len(src.data.polygons))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    me.name = name
    me.use_fake_user = True
    bpy.data.objects.remove(tmp, do_unlink=True)
    return me


def build_walls_scan(name='MC_walls', key='mossy_wall', seed=11, overlap=0.07):
    """Dry-stone retaining walls: the scanned wall module repeated along the terrace outline and bent to it. Each
    repeat shows another side of the scan (turned, mirrored), is stretched a little differently and sits at its own
    height in the ground, so the 3.5 m scan does not read as a repeat."""
    import mc_fab
    g = Ground()
    rng = np.random.default_rng(seed)
    co, li, ls, lt, uv = _mesh_arrays(wall_module(key))
    x0, x1 = co[:, 0].min(), co[:, 0].max()
    y0, y1 = co[:, 1].min(), co[:, 1].max()
    z0, z1 = co[:, 2].min(), co[:, 2].max()
    Lm, Hm = x1 - x0, z1 - z0
    yc = 0.5 * (y0 + y1)
    V, LI, LS, LT, UV = [], [], [], [], []
    nv = nl = 0
    count = 0
    for W in wall_paths(g):
        xy, nrm, top, s = W['xy'], W['n'], W['top'], W['s']
        Ltot = float(s[-1])
        if Ltot < 0.8:
            continue
        nmod = max(1, int(round(Ltot / (Lm * 0.96))))
        seg = Ltot / nmod
        foot = np.minimum(W['foot_out'], W['foot_in'] - 0.3)
        for k in range(nmod):
            flip = rng.uniform() < 0.5                      # show the other face of the scan
            mirror = rng.uniform() < 0.5
            xm = (co[:, 0] - x0) / Lm                       # 0..1 along the module
            ym = co[:, 1] - yc
            if flip:
                xm, ym = 1.0 - xm, -ym
            if mirror:
                xm = 1.0 - xm
            sm = k * seg - overlap + xm * (seg + 2 * overlap)
            sm = np.clip(sm, 0.0, Ltot)
            px = np.interp(sm, s, xy[:, 0])
            py = np.interp(sm, s, xy[:, 1])
            nx_ = np.interp(sm, s, nrm[:, 0])
            ny_ = np.interp(sm, s, nrm[:, 1])
            tp = np.interp(sm, s, top)
            ft = np.interp(sm, s, foot)
            need = float(np.percentile(tp - ft, 85)) + 0.10          # wall height here, with 10 cm in the ground
            zs = np.clip(need / Hm, 0.92, 1.45)
            dz = rng.uniform(-0.025, 0.02)
            P = np.stack([px + nx_ * ym * 0.97, py + ny_ * ym * 0.97, tp + dz - (z1 - co[:, 2]) * zs], 1)
            V.append(P.astype(np.float32))
            if mirror:                                      # a mirrored copy needs its faces turned back
                idx = li.reshape(-1, 3)[:, ::-1].ravel()
                uvm = uv.reshape(-1, 3, 2)[:, ::-1].reshape(-1, 2)
            else:
                idx, uvm = li, uv
            LI.append(idx + nv)
            UV.append(uvm)
            LS.append(ls + nl)
            LT.append(lt)
            nv += len(co)
            nl += len(li)
            count += 1
    co2 = np.concatenate(V)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co2))
    me.vertices.foreach_set('co', co2.ravel())
    lic = np.concatenate(LI).astype(np.int32)
    me.loops.add(len(lic))
    me.loops.foreach_set('vertex_index', lic)
    lsc = np.concatenate(LS).astype(np.int32)
    me.polygons.add(len(lsc))
    me.polygons.foreach_set('loop_start', lsc)
    me.polygons.foreach_set('loop_total', np.concatenate(LT).astype(np.int32))
    me.update(calc_edges=True)
    uvl = me.uv_layers.new(name='UVMap')
    uvl.uv.foreach_set('vector', np.concatenate(UV).astype(np.float32).ravel())
    me.shade_smooth()
    mat = mc_fab.rock_material(key, sat=0.65, val=0.66)
    o = C.obj(name, me, C.coll('MC_site'), mat)
    return o, count
