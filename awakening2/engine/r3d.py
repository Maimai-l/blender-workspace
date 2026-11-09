"""r3d.py - the 3D helper of the Awakening II look engine.

The robot is modelled as signed-distance-field (SDF) parts, meshed once with
marching cubes, posed as rigid parts, and rasterised by our own numba
rasteriser into *passes* (never final pixels):

    depth   camera-space depth (inf = empty)
    tri     global triangle index (-1 = empty)
    part    part index per pixel (-1 = empty)
    mat     material class per pixel
    nrm     world-space normal (unit)
    wpos    world-space position
    opos    object(part)-space position (for decals that must stay on-model)

`look.py` turns these passes into drawn frames.

Conventions: world Z up, metres. Robot local frame: X = robot's right,
Y = forward, Z = up. Cameras: lens in mm on a 36 mm wide sensor.
"""
import os
import math
import numpy as np
from numba import njit, prange

# ----------------------------------------------------------------------------
# SDF primitives (numpy, vectorised over (..., 3) point arrays)
# ----------------------------------------------------------------------------

def _len(v):
    return np.sqrt(np.sum(v * v, axis=-1))


def sd_sphere(p, c, r):
    return _len(p - np.asarray(c, np.float32)) - r


def sd_ellipsoid(p, c, rad):
    rad = np.asarray(rad, np.float32)
    q = (p - np.asarray(c, np.float32))
    k0 = _len(q / rad)
    k1 = _len(q / (rad * rad))
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def rot_matrix(rx=0.0, ry=0.0, rz=0.0):
    """Rotation matrix from Euler angles in degrees (applied X then Y then Z)."""
    rx, ry, rz = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], np.float32)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], np.float32)
    return (Rz @ Ry @ Rx).astype(np.float32)


def to_local(p, c, R=None):
    """Point in a primitive's local frame (centre c, rotation R local->world)."""
    q = p - np.asarray(c, np.float32)
    if R is not None:
        q = q @ np.asarray(R, np.float32)   # q_local = R^T q  (row vectors)
    return q


def sd_box(p, c, half, r=0.0, R=None):
    """Rounded box: half extents `half` (the rounding is inside them)."""
    q = np.abs(to_local(p, c, R)) - (np.asarray(half, np.float32) - r)
    return _len(np.maximum(q, 0.0)) + np.minimum(np.max(q, axis=-1), 0.0) - r


def sd_capsule(p, a, b, r):
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32)
    pa = p - a; ba = b - a
    h = np.clip(np.sum(pa * ba, -1) / np.dot(ba, ba), 0.0, 1.0)
    return _len(pa - h[..., None] * ba) - r


def sd_round_cone(p, a, b, r1, r2):
    """Capsule whose radius goes from r1 at a to r2 at b (iq's round cone)."""
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32)
    ba = b - a
    l2 = float(np.dot(ba, ba)); rr = r1 - r2
    a2 = l2 - rr * rr; il2 = 1.0 / l2
    pa = p - a
    y = np.sum(pa * ba, -1)
    z = y - l2
    xv = pa * l2 - y[..., None] * ba
    x2 = np.sum(xv * xv, -1)
    y2 = y * y * l2
    z2 = z * z * l2
    k = np.sign(rr) * rr * rr * x2
    out = np.where(np.sign(z) * a2 * z2 > k, np.sqrt(x2 + z2) * il2 - r2,
                   np.where(np.sign(y) * a2 * y2 < k, np.sqrt(x2 + y2) * il2 - r1,
                            (np.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1))
    return out.astype(np.float32)


def sd_cyl(p, a, b, r, rr=0.0):
    """Capped cylinder between a and b with radius r and edge rounding rr."""
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32)
    ba = b - a; L = float(np.linalg.norm(ba)); ax = ba / L
    pa = p - a
    y = np.sum(pa * ax, -1) - L * 0.5
    x = _len(pa - (np.sum(pa * ax, -1))[..., None] * ax)
    dx = x - (r - rr); dy = np.abs(y) - (L * 0.5 - rr)
    return (np.minimum(np.maximum(dx, dy), 0.0) + np.sqrt(np.maximum(dx, 0) ** 2 + np.maximum(dy, 0) ** 2) - rr).astype(np.float32)


def sd_torus(p, c, R_, r, Rm=None):
    q = to_local(p, c, Rm)
    qx = np.sqrt(q[..., 0] ** 2 + q[..., 1] ** 2) - R_
    return np.sqrt(qx * qx + q[..., 2] ** 2) - r


def sd_plane(p, n, d):
    n = np.asarray(n, np.float32); n = n / np.linalg.norm(n)
    return np.sum(p * n, -1) - d


def U(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def SU(a, b, k):
    """Polynomial smooth union."""
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def SUB(a, b):
    return np.maximum(a, -b)


def SSUB(a, b, k):
    h = np.clip(0.5 - 0.5 * (a + b) / k, 0.0, 1.0)
    return a * (1 - h) + (-b) * h + k * h * (1 - h)


def INT(a, b):
    return np.maximum(a, b)


def SINT(a, b, k):
    h = np.clip(0.5 - 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h + k * h * (1 - h)


def CHAMF(a, b, k):
    """Chamfered union (a 45-degree fillet of size k)."""
    return np.minimum(np.minimum(a, b), (a + b - k) * 0.70710678)


# ----------------------------------------------------------------------------
# meshing
# ----------------------------------------------------------------------------

def mesh_sdf(fn, lo, hi, voxel, pad=2):
    """Marching cubes of fn over the box lo..hi. Returns V (n,3) f32, F (m,3) i32, N (n,3) f32.

    Normals are the SDF gradient at the vertices (smooth, exact), faces are wound
    counter-clockwise seen from outside.
    """
    from skimage.measure import marching_cubes
    lo = np.asarray(lo, np.float32) - pad * voxel
    hi = np.asarray(hi, np.float32) + pad * voxel
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    xs = lo[0] + np.arange(n[0], dtype=np.float32) * voxel
    ys = lo[1] + np.arange(n[1], dtype=np.float32) * voxel
    zs = lo[2] + np.arange(n[2], dtype=np.float32) * voxel
    vol = np.empty((n[0], n[1], n[2]), np.float32)
    # evaluate in x-slabs to bound memory
    Y, Z = np.meshgrid(ys, zs, indexing='ij')
    for i in range(n[0]):
        P = np.stack([np.full_like(Y, xs[i]), Y, Z], -1)
        vol[i] = fn(P)
    if vol.min() > 0 or vol.max() < 0:
        raise ValueError('surface not inside the meshing box')
    V, F, _, _ = marching_cubes(vol, level=0.0, spacing=(voxel, voxel, voxel))
    V = (V + lo).astype(np.float32)
    F = F.astype(np.int32)
    N = sdf_normals(fn, V, voxel * 0.5)
    # fix winding: geometric normal should agree with the gradient
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    gn = np.cross(b - a, c - a)
    agree = np.sum(gn * (N[F[:, 0]] + N[F[:, 1]] + N[F[:, 2]]), -1)
    if np.mean(agree < 0) > 0.5:
        F = F[:, [0, 2, 1]].copy()
    return V, F, N


def sdf_normals(fn, V, h):
    e = np.float32(h)
    dx = fn(V + [e, 0, 0]) - fn(V - [e, 0, 0])
    dy = fn(V + [0, e, 0]) - fn(V - [0, e, 0])
    dz = fn(V + [0, 0, e]) - fn(V - [0, 0, e])
    N = np.stack([dx, dy, dz], -1).astype(np.float32)
    N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-9)
    return N


# ----------------------------------------------------------------------------
# transforms
# ----------------------------------------------------------------------------

def mat4(R=None, t=(0, 0, 0)):
    M = np.eye(4, dtype=np.float32)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def xform_points(M, P):
    return (P @ M[:3, :3].T + M[:3, 3]).astype(np.float32)


def xform_dirs(M, D):
    D = D @ M[:3, :3].T
    return (D / np.maximum(np.linalg.norm(D, axis=-1, keepdims=True), 1e-9)).astype(np.float32)


# ----------------------------------------------------------------------------
# camera
# ----------------------------------------------------------------------------

class Camera:
    def __init__(self, pos, target, lens=50.0, W=1920, H=1040, roll=0.0,
                 shift=(0.0, 0.0), up=(0, 0, 1), near=0.05):
        self.pos = np.asarray(pos, np.float32)
        self.target = np.asarray(target, np.float32)
        self.lens = float(lens); self.W = int(W); self.H = int(H)
        self.near = near
        f = self.target - self.pos; f /= np.linalg.norm(f)
        upw = np.asarray(up, np.float32)
        r = np.cross(f, upw); r /= np.linalg.norm(r)
        u = np.cross(r, f)
        if roll:
            a = math.radians(roll)
            r, u = r * math.cos(a) + u * math.sin(a), -r * math.sin(a) + u * math.cos(a)
        self.f, self.r, self.u = f.astype(np.float32), r.astype(np.float32), u.astype(np.float32)
        self.fpx = self.lens / 36.0 * self.W
        # shift in fractions of the width (like Blender's shift_x/shift_y)
        self.cx = self.W * 0.5 - shift[0] * self.W
        self.cy = self.H * 0.5 + shift[1] * self.W

    def scaled(self, s):
        c = Camera.__new__(Camera)
        c.__dict__.update(self.__dict__)
        c.W = int(round(self.W * s)); c.H = int(round(self.H * s))
        c.fpx = self.fpx * s; c.cx = self.cx * s; c.cy = self.cy * s
        return c

    def to_cam(self, P):
        d = P - self.pos
        return np.stack([d @ self.r, d @ self.u, d @ self.f], -1).astype(np.float32)

    def project(self, P):
        """World points -> (sx, sy, depth)."""
        c = self.to_cam(np.asarray(P, np.float32))
        z = c[..., 2]
        zz = np.where(z > 1e-6, z, 1e-6)
        sx = self.cx + self.fpx * c[..., 0] / zz
        sy = self.cy - self.fpx * c[..., 1] / zz
        return np.stack([sx, sy, z], -1).astype(np.float32)

    def ray_dirs(self):
        """World-space view ray direction per pixel (H, W, 3)."""
        xs = (np.arange(self.W, dtype=np.float32) + 0.5 - self.cx) / self.fpx
        ys = -(np.arange(self.H, dtype=np.float32) + 0.5 - self.cy) / self.fpx
        X, Y = np.meshgrid(xs, ys)
        D = X[..., None] * self.r + Y[..., None] * self.u + self.f
        return D / np.linalg.norm(D, axis=-1, keepdims=True)


# ----------------------------------------------------------------------------
# numba rasteriser (visibility buffer)
# ----------------------------------------------------------------------------

@njit(cache=True, fastmath=True)
def _raster(sx, sy, sz, F, W, H, near, cull, zbuf, tbuf, b1buf, b2buf):
    nt = F.shape[0]
    for t in range(nt):
        i0 = F[t, 0]; i1 = F[t, 1]; i2 = F[t, 2]
        z0 = sz[i0]; z1 = sz[i1]; z2 = sz[i2]
        if z0 < near or z1 < near or z2 < near:
            continue
        x0 = sx[i0]; y0 = sy[i0]; x1 = sx[i1]; y1 = sy[i1]; x2 = sx[i2]; y2 = sy[i2]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area == 0.0:
            continue
        if cull[t] and area > 0.0:   # screen y points down: CCW-from-outside -> negative area
            continue
        minx = max(int(math.floor(min(x0, min(x1, x2)))), 0)
        maxx = min(int(math.ceil(max(x0, max(x1, x2)))), W - 1)
        miny = max(int(math.floor(min(y0, min(y1, y2)))), 0)
        maxy = min(int(math.ceil(max(y0, max(y1, y2)))), H - 1)
        if minx > maxx or miny > maxy:
            continue
        inv = 1.0 / area
        iz0 = 1.0 / z0; iz1 = 1.0 / z1; iz2 = 1.0 / z2
        for py in range(miny, maxy + 1):
            fy = py + 0.5
            for px in range(minx, maxx + 1):
                fx = px + 0.5
                w0 = ((x1 - fx) * (y2 - fy) - (x2 - fx) * (y1 - fy)) * inv
                w1 = ((x2 - fx) * (y0 - fy) - (x0 - fx) * (y2 - fy)) * inv
                w2 = 1.0 - w0 - w1
                if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                    continue
                izp = w0 * iz0 + w1 * iz1 + w2 * iz2
                z = 1.0 / izp
                if z < zbuf[py, px]:
                    zbuf[py, px] = z
                    tbuf[py, px] = t
                    # perspective-correct barycentrics
                    b1buf[py, px] = w1 * iz1 * z
                    b2buf[py, px] = w2 * iz2 * z


@njit(cache=True, fastmath=True)
def _raster_depth_ortho(sx, sy, sz, F, W, H, zbuf):
    nt = F.shape[0]
    for t in range(nt):
        i0 = F[t, 0]; i1 = F[t, 1]; i2 = F[t, 2]
        x0 = sx[i0]; y0 = sy[i0]; x1 = sx[i1]; y1 = sy[i1]; x2 = sx[i2]; y2 = sy[i2]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area == 0.0:
            continue
        minx = max(int(math.floor(min(x0, min(x1, x2)))), 0)
        maxx = min(int(math.ceil(max(x0, max(x1, x2)))), W - 1)
        miny = max(int(math.floor(min(y0, min(y1, y2)))), 0)
        maxy = min(int(math.ceil(max(y0, max(y1, y2)))), H - 1)
        if minx > maxx or miny > maxy:
            continue
        inv = 1.0 / area
        for py in range(miny, maxy + 1):
            fy = py + 0.5
            for px in range(minx, maxx + 1):
                fx = px + 0.5
                w0 = ((x1 - fx) * (y2 - fy) - (x2 - fx) * (y1 - fy)) * inv
                w1 = ((x2 - fx) * (y0 - fy) - (x0 - fx) * (y2 - fy)) * inv
                w2 = 1.0 - w0 - w1
                if w0 < 0.0 or w1 < 0.0 or w2 < 0.0:
                    continue
                z = w0 * sz[i0] + w1 * sz[i1] + w2 * sz[i2]
                if z < zbuf[py, px]:
                    zbuf[py, px] = z


class Mesh:
    """A rigid part: local vertices, faces, normals, a part id, a material class."""
    def __init__(self, V, F, N, part=0, mat=0, cull=True, name=''):
        self.V = np.ascontiguousarray(V, np.float32)
        self.F = np.ascontiguousarray(F, np.int32)
        self.N = np.ascontiguousarray(N, np.float32)
        self.part = int(part); self.mat = int(mat); self.cull = bool(cull)
        self.name = name

    def save(self, path):
        tmp = path + f'.tmp{os.getpid()}.npz'
        np.savez_compressed(tmp, V=self.V, F=self.F, N=self.N,
                            meta=np.array([self.part, self.mat, int(self.cull)]),
                            name=np.array(self.name))
        try:
            os.replace(tmp, path)      # atomic: parallel renderers never read a half-written mesh
        except OSError:                # Windows: another process wrote/holds it already
            try:
                os.remove(tmp)
            except OSError:
                pass

    @staticmethod
    def load(path):
        d = np.load(path)
        m = d['meta']
        return Mesh(d['V'], d['F'], d['N'], int(m[0]), int(m[1]), bool(m[2]), str(d['name']))


class Scene:
    """A list of (mesh, world matrix) for one frame."""
    def __init__(self):
        self.items = []

    def add(self, mesh, M):
        self.items.append((mesh, np.asarray(M, np.float32)))

    def gather(self):
        Vs, Ns, Fs, Os, parts, mats, culls = [], [], [], [], [], [], []
        ONs = []
        off = 0
        for mesh, M in self.items:
            Vs.append(xform_points(M, mesh.V))
            Ns.append(xform_dirs(M, mesh.N))
            Os.append(mesh.V)
            ONs.append(mesh.N)
            Fs.append(mesh.F + off)
            nf = len(mesh.F)
            parts.append(np.full(nf, mesh.part, np.int16))
            mats.append(np.full(nf, mesh.mat, np.int16))
            culls.append(np.full(nf, mesh.cull, np.bool_))
            off += len(mesh.V)
        self._onrm = np.concatenate(ONs)
        return (np.concatenate(Vs), np.concatenate(Ns), np.concatenate(Os),
                np.concatenate(Fs), np.concatenate(parts), np.concatenate(mats),
                np.concatenate(culls))


def render_passes(scene, cam, want_opos=True):
    """Rasterise a scene. Returns a dict of passes (H, W)."""
    V, N, O, F, fpart, fmat, fcull = scene.gather()
    P = cam.project(V)
    W, H = cam.W, cam.H
    zbuf = np.full((H, W), np.inf, np.float32)
    tbuf = np.full((H, W), -1, np.int32)
    b1 = np.zeros((H, W), np.float32)
    b2 = np.zeros((H, W), np.float32)
    _raster(P[:, 0].copy(), P[:, 1].copy(), P[:, 2].copy(), F, W, H, np.float32(cam.near),
            fcull, zbuf, tbuf, b1, b2)
    m = tbuf >= 0
    out = {'depth': zbuf, 'tri': tbuf, 'mask': m}
    part = np.full((H, W), -1, np.int16)
    mat = np.full((H, W), -1, np.int16)
    t = tbuf[m]
    part[m] = fpart[t]
    mat[m] = fmat[t]
    out['part'] = part; out['mat'] = mat
    w1 = b1[m]; w2 = b2[m]; w0 = 1.0 - w1 - w2
    f = F[t]
    def interp(A):
        return (A[f[:, 0]] * w0[:, None] + A[f[:, 1]] * w1[:, None] + A[f[:, 2]] * w2[:, None])
    nrm = np.zeros((H, W, 3), np.float32)
    nn = interp(N)
    nn /= np.maximum(np.linalg.norm(nn, axis=-1, keepdims=True), 1e-9)
    nrm[m] = nn
    out['nrm'] = nrm
    wpos = np.zeros((H, W, 3), np.float32)
    wpos[m] = interp(V)
    out['wpos'] = wpos
    if want_opos:
        opos = np.zeros((H, W, 3), np.float32)
        opos[m] = interp(O)
        out['opos'] = opos
        onrm = np.zeros((H, W, 3), np.float32)
        onrm[m] = interp(scene._onrm)
        out['onrm'] = onrm
    return out


class ShadowMap:
    """Orthographic depth map from a directional light."""
    def __init__(self, scene, light_dir, center, extent, res=2048):
        L = np.asarray(light_dir, np.float32); L /= np.linalg.norm(L)  # direction TO the light
        self.L = L
        f = -L
        up = np.array([0, 0, 1], np.float32) if abs(f[2]) < 0.95 else np.array([0, 1, 0], np.float32)
        r = np.cross(f, up); r /= np.linalg.norm(r)
        u = np.cross(r, f)
        self.f, self.r, self.u = f, r, u
        self.c = np.asarray(center, np.float32)
        self.ext = float(extent); self.res = int(res)
        V, N, O, F, *_ = scene.gather()
        sx, sy, sz = self._proj(V)
        self.z = np.full((self.res, self.res), np.inf, np.float32)
        _raster_depth_ortho(sx, sy, sz, F, self.res, self.res, self.z)

    def _proj(self, P):
        d = P - self.c
        x = d @ self.r; y = d @ self.u; z = d @ self.f
        s = self.res / (2 * self.ext)
        return ((x * s + self.res / 2).astype(np.float32), (-y * s + self.res / 2).astype(np.float32),
                (z + 1000.0).astype(np.float32))

    def lit(self, P, bias=0.04):
        """1 where world points P (..., 3) are lit, 0 where shadowed (PCF 3x3)."""
        sh = P.shape[:-1]
        Q = P.reshape(-1, 3)
        sx, sy, sz = self._proj(Q)
        res = self.res
        acc = np.zeros(len(Q), np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ix = np.clip((sx + dx).astype(int), 0, res - 1)
                iy = np.clip((sy + dy).astype(int), 0, res - 1)
                acc += (sz - bias <= self.z[iy, ix]).astype(np.float32)
        return (acc / 9.0).reshape(sh)
