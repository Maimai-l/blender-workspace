"""vines.py - vines hanging from the robot: verlet chains in world space, drawn as
inked, tapered strokes with leaves (cel shading, 2 tones), held on 2s.

Each vine is anchored to a robot part (part-local point) and optionally rooted in
the ground; a rooted vine tears loose when the robot pulls it beyond its slack,
then swings free - overlapping action for the rise.
"""
import math, zlib
import numpy as np
import cv2
import r3d
import ink


class Vine:
    def __init__(self, part, local, length, seg=0.35, root=None, snap=1.18, name='v', width=0.07,
                 leaf_every=0.32, leaf_size=0.2):
        self.part = part; self.local = np.asarray(local, np.float32)
        self.n = max(3, int(length / seg) + 1); self.seg = length / (self.n - 1)
        self.root = None if root is None else np.asarray(root, np.float32)
        self.snap = snap; self.name = name; self.width = width
        self.leaf_every = leaf_every; self.leaf_size = leaf_size
        self.rng = np.random.default_rng(zlib.crc32(name.encode()))


class VineSet:
    def __init__(self, rig, vines, pose_fn, fps=24, gravity=9.8, damping=0.04, iters=12, wind=None):
        self.rig = rig; self.vines = vines; self.pose_fn = pose_fn
        self.fps = fps; self.g = gravity; self.damp = damping; self.iters = iters
        self.wind = wind
        self.frames = {}
        self.state = None
        self.f_done = -1
        self.snapped = [False] * len(vines)

    def _anchor(self, v, mats):
        return r3d.xform_points(mats[v.part], v.local[None])[0]

    def _init(self, mats):
        st = []
        for v in self.vines:
            a = self._anchor(v, mats)
            if v.root is not None:
                pts = np.linspace(a, v.root, v.n).astype(np.float32)
                # some sag
                sag = np.sin(np.linspace(0, np.pi, v.n))[:, None] * np.array([0, 0, -0.25], np.float32)
                pts += sag
            else:
                pts = np.array([a + np.array([0, 0, -v.seg * i], np.float32) for i in range(v.n)], np.float32)
            st.append([pts.copy(), pts.copy()])
        self.state = st

    def step_to(self, f):
        """Simulate up to frame f (inclusive); positions per frame are stored."""
        dt = 1.0 / self.fps
        while self.f_done < f:
            k = self.f_done + 1
            pose = self.pose_fn(k / self.fps)
            mats = self.rig.world_mats(pose)
            if self.state is None:
                self._init(mats)
                # settle the chains before the shot starts
                for _ in range(60):
                    self._sub(mats, dt, settle=True)
            self._sub(mats, dt)
            self.frames[k] = [s[0].copy() for s in self.state]
            self.f_done = k
        return self.frames[f]

    def _sub(self, mats, dt, settle=False):
        for vi, (v, (p, pp)) in enumerate(zip(self.vines, self.state)):
            a = self._anchor(v, mats)
            vel = (p - pp) * (1 - self.damp)
            acc = np.array([0, 0, -self.g], np.float32)
            if self.wind is not None:
                w = self.wind(self.f_done / self.fps) if callable(self.wind) else self.wind
                acc = acc + np.asarray(w, np.float32)
            new = p + vel + acc * dt * dt
            new[0] = a
            rooted = v.root is not None and not self.snapped[vi]
            if rooted:
                new[-1] = v.root
            for _ in range(self.iters):
                d = new[1:] - new[:-1]
                L = np.linalg.norm(d, axis=1, keepdims=True) + 1e-6
                corr = (L - v.seg) / L * d * 0.5
                new[:-1] += corr
                new[1:] -= corr
                new[0] = a
                if rooted:
                    new[-1] = v.root
                # stay above the ground
                new[:, 2] = np.maximum(new[:, 2], 0.05)
            if rooted and not settle:
                total = np.sum(np.linalg.norm(np.diff(new, axis=0), axis=1))
                if total > v.seg * (v.n - 1) * v.snap:
                    self.snapped[vi] = True
            pp[:] = p; p[:] = new

    def draw(self, canvas, f, cam, depth=None, light=(0.6, -0.8), colours=None, on=2, scale=1.0):
        """Draw onto a straight-alpha RGBA canvas. depth: (H, W) robot depth for occlusion.
        All stems go through two batched stroke passes (ink, then fill); leaves are local patches."""
        fh = (f // on) * on
        pts_all = self.step_to(fh)
        H, W = canvas.shape[:2]
        cols = colours or dict(stem=(0.24, 0.33, 0.20), leaf=(0.46, 0.60, 0.30), leaf_sh=(0.22, 0.36, 0.26),
                              leaf_hi=(0.72, 0.78, 0.42), ink=(0.16, 0.14, 0.11))
        lx, ly = light
        ink_strokes, stem_strokes, leaves = [], [], []
        for v, P in zip(self.vines, pts_all):
            q = cam.project(P)
            if np.all(q[:, 2] < 0.5):
                continue
            vis = (q[:, 2] > 0.5) & (q[:, 0] > -200) & (q[:, 0] < W + 200) & (q[:, 1] > -200) & (q[:, 1] < H + 200)
            if depth is not None:
                ix = np.clip(q[:, 0].astype(int), 0, W - 1); iy = np.clip(q[:, 1].astype(int), 0, H - 1)
                vis &= q[:, 2] <= depth[iy, ix] + 0.6
            runs, cur = [], []
            for i in range(len(q)):
                if vis[i]:
                    cur.append(i)
                elif cur:
                    runs.append(cur); cur = []
            if cur:
                runs.append(cur)
            for run in runs:
                if len(run) < 2:
                    continue
                pts = q[run, :2].astype(np.float32)
                pts = ink.resample(ink.smooth_chain(pts, 1.0), 3.0)
                if len(pts) < 2:
                    continue
                wpx = float(np.clip(cam.fpx * v.width / np.mean(q[run, 2]) * scale, 1.0, 9.0))
                tpr = np.linspace(1.0, 0.45, len(pts)).astype(np.float32)
                ink_strokes.append((pts, (tpr * (wpx + 1.6)).astype(np.float32)))
                stem_strokes.append((pts, (tpr * wpx).astype(np.float32)))
            L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
            nleaf = int(L[-1] / v.leaf_every)
            rng = np.random.default_rng(zlib.crc32(v.name.encode()))
            for j in range(1, nleaf):
                s_ = j * v.leaf_every + rng.uniform(-0.05, 0.05)
                i = int(np.searchsorted(L, s_)) - 1
                i = min(max(i, 0), len(P) - 2)
                r1, r2, r3, r4 = rng.uniform(-0.7, 0.7), rng.uniform(0.55, 1.3), rng.random(), rng.random()
                if r4 < 0.22 or not (vis[i] and vis[i + 1]):      # gaps: not every node has a leaf
                    continue
                u = (s_ - L[i]) / max(L[i + 1] - L[i], 1e-6)
                c = q[i, :2] * (1 - u) + q[i + 1, :2] * u
                z = q[i, 2]
                d = q[i + 1, :2] - q[i, :2]; nd = np.linalg.norm(d) + 1e-6; d = d / nd
                side = 1 if j % 2 else -1
                perp = np.array([-d[1], d[0]]) * side
                ang = math.atan2(perp[1] + d[1] * 0.6, perp[0] + d[0] * 0.6) + r1
                size = cam.fpx * v.leaf_size / max(z, 0.5) * r2 * scale
                if size < 2.0:
                    continue
                lit = (math.cos(ang) * lx + math.sin(ang) * ly) > -0.1
                leaves.append((c, ang, size, cols['leaf'] if lit else cols['leaf_sh'],
                               cols['leaf_hi'] if lit and r3 < 0.35 else None))
        if ink_strokes:
            _over(canvas, ink.draw_strokes((H, W), ink_strokes), cols['ink'])
            _over(canvas, ink.draw_strokes((H, W), stem_strokes), cols['stem'])
        for c, ang, size, fill, hi in leaves:
            _leaf(canvas, c, ang, size, fill, cols['ink'], hi)


def _over(canvas, cov, col):
    a = cov[..., None]
    canvas[..., :3] = canvas[..., :3] * (1 - a) * canvas[..., 3:4] + np.asarray(col, np.float32) * a
    na = a[..., 0] + canvas[..., 3] * (1 - a[..., 0])
    canvas[..., :3] /= np.maximum(na[..., None], 1e-6)
    canvas[..., 3] = na


def _leaf(canvas, c, ang, size, fill, inkc, hi=None):
    t = np.linspace(0, 1, 9)
    w = np.sin(np.pi * t) ** 0.8 * 0.36
    xs = t * size;
    up = np.stack([xs, w * size], -1); dn = np.stack([xs[::-1], -w[::-1] * size], -1)
    poly = np.concatenate([up, dn])
    R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    poly = poly @ R.T + np.asarray(c)
    H, W = canvas.shape[:2]
    x0, y0 = np.floor(poly.min(0)).astype(int) - 3
    x1, y1 = np.ceil(poly.max(0)).astype(int) + 3
    if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H:
        return
    x0 = max(x0, 0); y0 = max(y0, 0); x1 = min(x1, W); y1 = min(y1, H)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    m = np.zeros((y1 - y0, x1 - x0), np.float32)
    pp = np.round((poly - [x0, y0]) * 16).astype(np.int32)
    cv2.fillPoly(m, [pp], 1.0, cv2.LINE_AA, shift=4)
    mi = np.zeros_like(m)
    cv2.polylines(mi, [pp], True, 1.0, max(1, int(size * 0.06) + 1), cv2.LINE_AA, shift=4)
    sub = canvas[y0:y1, x0:x1]
    fc = np.ones_like(m)[..., None] * np.asarray(fill, np.float32)
    if hi is not None:
        # a lit half
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        side = (xx - c[0]) * -math.sin(ang) + (yy - c[1]) * math.cos(ang)
        fc = np.where((side < 0)[..., None], np.asarray(hi, np.float32), fc)
    a = m[..., None]
    rgb = sub[..., :3] * sub[..., 3:4] * (1 - a) + fc * a
    al = a[..., 0] + sub[..., 3] * (1 - a[..., 0])
    ai = mi[..., None]
    rgb = rgb * (1 - ai) + np.asarray(inkc, np.float32) * ai
    al = np.maximum(al, mi)
    sub[..., :3] = rgb / np.maximum(al[..., None], 1e-6)
    sub[..., 3] = al
