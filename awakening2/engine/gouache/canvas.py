"""canvas.py - Canvas, brush API (dabs, strokes, tube fields), paper, saving.

A Canvas holds premultiplied float32 RGBA with an optional margin (overscan) so
multiplane layers can be shifted for parallax without showing an edge. Every
drawing call takes *flat* painting coordinates (0..W, 0..H of the finished
painting); the margin is handled here.
"""
import numpy as np
import cv2
from PIL import Image
from scipy.ndimage import gaussian_filter

from . import kernels as K
from .noise import value_noise, noise1d

# ----------------------------------------------------------------------------
# shared textures (deterministic)
# ----------------------------------------------------------------------------
_TR = np.random.default_rng(20261109)
N_TEX = 32
BR = np.stack([0.6 * noise1d(256, 46, _TR, periodic=True) + 0.4 * noise1d(256, 15, _TR, periodic=True)
               for _ in range(N_TEX)]).astype(np.float32)
BR = (BR - BR.min(1, keepdims=True)) / np.ptp(BR, 1)[:, None]
BR = np.ascontiguousarray(BR ** 1.3, dtype=np.float32)
E2 = np.stack([value_noise(64, 64, 7, _TR, tile=True) for _ in range(N_TEX)]).astype(np.float32)
E2 = np.ascontiguousarray(E2 - 0.5, dtype=np.float32)


def _make_paper(n=512):
    """Tileable paper height field 0..1: cold-press tooth + faint fibres."""
    r = np.random.default_rng(77)
    tooth = np.zeros((n, n), np.float32)
    for cells, amp in ((n / 3, 1.0), (n / 6, 0.6), (n / 14, 0.35), (n / 40, 0.25)):
        tooth += amp * value_noise(n, n, cells, r, tile=True)
    fine = r.normal(0, 1, (n, n)).astype(np.float32)
    fine = gaussian_filter(fine, 0.8, mode='wrap')
    tooth = tooth / tooth.std() + 0.35 * fine / fine.std()
    # fibres: short streaks
    fib = r.normal(0, 1, (n, n)).astype(np.float32)
    fib = gaussian_filter(fib, (0.7, 6.0), mode='wrap')
    tooth += 0.4 * fib / fib.std()
    lo, hi = np.percentile(tooth, [1, 99])
    return np.ascontiguousarray(np.clip((tooth - lo) / (hi - lo), 0, 1), dtype=np.float32)


PAPER = _make_paper()

SHAPES = {'round': 0, 'leaf': 1, 'flat': 2, 'petal': 3}
MODES = {'over': 0, 'lock': 1, 'erase': 2, 'behind': 3}


class Canvas:
    """Premultiplied float RGBA. Flat size W x H, buffer (H+2m) x (W+2m)."""

    def __init__(self, W, H, margin=0, bg=None):
        self.W, self.H, self.m = int(W), int(H), int(margin)
        self.img = np.zeros((self.H + 2 * self.m, self.W + 2 * self.m, 4), np.float32)
        if bg is not None:
            self.img[..., :3] = np.asarray(bg, np.float32)
            self.img[..., 3] = 1.0

    @property
    def shape(self):
        return self.img.shape[:2]

    @property
    def alpha(self):
        return self.img[..., 3]

    def rgb(self):
        a = np.maximum(self.img[..., 3:4], 1e-5)
        return np.clip(self.img[..., :3] / a, 0, 1)

    def coords(self):
        """Flat coordinate grids (X, Y) covering the whole buffer (incl. margin)."""
        h, w = self.shape
        X = np.arange(w, dtype=np.float32) - self.m
        Y = np.arange(h, dtype=np.float32) - self.m
        return np.meshgrid(X, Y)

    def ys(self):
        return np.arange(self.shape[0], dtype=np.float32) - self.m

    def xs(self):
        return np.arange(self.shape[1], dtype=np.float32) - self.m

    def over(self, rgb, a):
        """Composite a full-buffer straight colour (H,W,3)/(3,) with alpha (H,W)."""
        a = np.asarray(a, np.float32)[..., None]
        self.img *= (1 - a)
        self.img[..., :3] += a * np.asarray(rgb, np.float32)
        self.img[..., 3:4] += a

    def over_region(self, x0, y0, rgb, a):
        """Composite straight colour+alpha arrays at pixel offset (x0, y0)."""
        h, w = a.shape
        d = self.img[y0:y0 + h, x0:x0 + w]
        A = a[..., None]
        d *= (1 - A)
        d[..., :3] += A * rgb
        d[..., 3:4] += A

    def lock_tint(self, rgb, amount):
        """Alpha-locked tint toward colour(s) rgb by amount (H,W) / scalar."""
        amt = np.asarray(amount, np.float32)
        if amt.ndim == 2:
            amt = amt[..., None]
        c = np.asarray(rgb, np.float32) * self.img[..., 3:4]
        self.img[..., :3] += (c - self.img[..., :3]) * amt

    def multiply(self, f):
        f = np.asarray(f, np.float32)
        if f.ndim == 2:
            f = f[..., None]
        self.img[..., :3] *= f
        np.minimum(self.img[..., :3], self.img[..., 3:4], out=self.img[..., :3])

    def paste(self, other, opacity=1.0):
        """Composite another Canvas of the same size over this one."""
        s = other.img * opacity
        self.img *= (1 - s[..., 3:4])
        self.img += s

    def crop(self):
        m = self.m
        return self.img[m:m + self.H, m:m + self.W]


def _arr(v, n, dt=np.float32):
    return np.ascontiguousarray(np.broadcast_to(np.asarray(v, dt), (n,)), dtype=dt)


def dabs(cv, x, y, size, color, aspect=0.6, angle=None, opacity=1.0, edge=0.25, rag=0.35,
         bristle=0.25, shape='round', pool=0.0, dry=0.0, split=0.0, mode='over', rng=None):
    """Stamp many dabs (in the given order). size = long-axis length (px).
    color (3,) or (N,3); every other parameter scalar or (N,)."""
    x = np.atleast_1d(np.asarray(x, np.float32))
    n = x.shape[0]
    if n == 0:
        return
    if rng is None:
        rng = np.random.default_rng(int(abs(float(x[0])) * 7 + n) & 0xffffff)
    y = _arr(y, n)
    size = _arr(size, n)
    a = size * 0.5
    b = a * _arr(aspect, n)
    if angle is None:
        angle = rng.uniform(0, np.pi, n)
    col = np.asarray(color, np.float32)
    col = np.ascontiguousarray(np.broadcast_to(col, (n, 3)) if col.ndim == 1 else col, dtype=np.float32)
    shp = SHAPES[shape] if isinstance(shape, str) else shape
    K.k_dabs(cv.img, float(cv.m), float(cv.m), np.ascontiguousarray(x), y, a, b, _arr(angle, n), col,
             _arr(opacity, n), _arr(edge, n), _arr(rag, n), _arr(bristle, n),
             rng.integers(0, N_TEX, n).astype(np.int32), _arr(shp, n, np.int32),
             _arr(pool, n), _arr(dry, n), _arr(split, n), MODES[mode], PAPER, BR, E2)


def catmull(pts, n=None, spacing=3.0):
    """Catmull-Rom resample of a polyline (M,2) -> (n,2)."""
    pts = np.asarray(pts, np.float32)
    if len(pts) < 2:
        return pts
    if n is None:
        L = float(np.sum(np.hypot(*np.diff(pts, axis=0).T)))
        n = max(int(L / spacing) + 2, 3)
    if len(pts) == 2:
        t = np.linspace(0, 1, n, dtype=np.float32)[:, None]
        return pts[0] * (1 - t) + pts[1] * t
    ext = np.vstack([pts[0] * 2 - pts[1], pts, pts[-1] * 2 - pts[-2]])
    seg = len(pts) - 1
    t = np.linspace(0, seg - 1e-5, n)
    i = t.astype(int)
    f = (t - i)[:, None]
    p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
    return (0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f ** 2 +
                   (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)).astype(np.float32)


def normals(pts):
    d = np.gradient(np.asarray(pts, np.float32), axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    return nrm / np.maximum(np.hypot(*nrm.T)[:, None], 1e-6)


def wobble(pts, rng, amp, cells=4):
    """Sideways smooth noise displacement (hand tremor)."""
    pts = np.asarray(pts, np.float32)
    w = (noise1d(len(pts), cells, rng) - 0.5) * 2 * amp
    return pts + normals(pts) * w[:, None]


def taper(n, start=0.3, end=0.05, body=1.0, k=0.25):
    t = np.linspace(0, 1, n)
    w = np.ones(n, np.float32) * body
    w *= np.where(t < k, start + (1 - start) * np.sin(np.minimum(t / k, 1) * np.pi / 2), 1)
    w *= np.where(t > 1 - k, end + (1 - end) * np.sin(np.minimum((1 - t) / k, 1) * np.pi / 2), 1)
    return w.astype(np.float32)


def _along(v, n, dim=None):
    v = np.asarray(v, np.float32)
    if dim is None:
        if v.ndim == 0:
            return np.full(n, float(v), np.float32)
        src = np.linspace(0, 1, len(v))
        return np.interp(np.linspace(0, 1, n), src, v).astype(np.float32)
    if v.ndim == 1:
        return np.ascontiguousarray(np.broadcast_to(v, (n, dim)), dtype=np.float32)
    src = np.linspace(0, 1, len(v))
    dst = np.linspace(0, 1, n)
    return np.ascontiguousarray(np.stack([np.interp(dst, src, v[:, c]) for c in range(dim)], 1),
                                dtype=np.float32)


def stroke(cv, pts, width, color, opacity=1.0, color2=None, load2=0.0, edge=0.2, rag=0.25,
           bristle=0.4, pool=0.0, dry=0.0, drytail=0.0, mode='over', rng=None, smooth=True,
           spacing=None, tex=None):
    """One continuous brush stroke along pts. width/opacity scalar or per-point;
    color (3,) or per-point (M,3)."""
    pts = np.asarray(pts, np.float32)
    if len(pts) < 2:
        return
    wmax = float(np.max(width))
    if smooth:
        pts = catmull(pts, spacing=spacing or max(1.5, min(wmax * 0.25, 8.0)))
    n = len(pts)
    if rng is None:
        rng = np.random.default_rng(int(abs(float(pts[0, 0])) * 3 + abs(float(pts[0, 1]))) & 0xffffff)
    tex = int(rng.integers(0, N_TEX)) if tex is None else int(tex)
    c2 = np.zeros(3, np.float32) if color2 is None else np.asarray(color2, np.float32)
    K.k_stroke(cv.img, float(cv.m), float(cv.m), np.ascontiguousarray(pts), _along(width, n),
               _along(color, n, 3), _along(opacity, n), c2, float(load2 if color2 is not None else 0.0),
               float(edge), float(rag), float(bristle), tex, float(pool), float(dry), float(drytail),
               MODES[mode], PAPER, BR, E2)


def tube_fields(cv, pts, widths, rag=0.0, tex=0, caps=False):
    """Form fields of a tube along pts with full widths: returns dict with x0, y0
    (pixel offset of the arrays), R, TN, S, HW, L (length) and the resampled path."""
    pts = np.asarray(pts, np.float32)
    h, w = cv.shape
    x0, y0, R, TN, S, HW, L = K.k_sweep(np.ascontiguousarray(pts), _along(widths, len(pts)),
                                        float(cv.m), float(cv.m), h, w, float(rag), E2, int(tex), bool(caps))
    return dict(x0=x0, y0=y0, R=R, TN=TN, S=S, HW=HW, L=L)


# ----------------------------------------------------------------------------
# finishing / io
# ----------------------------------------------------------------------------

def grain(cv, amount=0.035, mode='multiply'):
    """Paper grain in the paint: modulate colour by the paper tooth (alpha kept)."""
    h, w = cv.shape
    ph, pw = PAPER.shape
    ry = (np.arange(h) - cv.m) % ph
    rx = (np.arange(w) - cv.m) % pw
    p = PAPER[ry[:, None], rx[None, :]]
    cv.multiply(1.0 + amount * (p - 0.5) * 2.0)


def bleed(rgb, alpha, passes=(2, 4, 8, 16, 32, 64, 128)):
    """Fill transparent pixels with nearby colour (no dark fringes when filtered)."""
    out = rgb.copy()
    filled = alpha > 2e-3
    prem = rgb * alpha[..., None]
    for s in passes:
        if filled.all():
            break
        k = (s * 2 + 1, s * 2 + 1)
        bp = cv2.blur(prem, k)
        ba = cv2.blur(alpha, k)
        ok = (~filled) & (ba > 1e-4)
        out[ok] = bp[ok] / ba[ok][:, None]
        filled |= ok
    if not filled.all():
        m = alpha > 2e-3
        out[~filled] = rgb[m].mean(0) if m.any() else 0.5
    return np.clip(out, 0, 1)


def to_u8(rgb, rng=None):
    if rng is None:
        rng = np.random.default_rng(5)
    noise = (rng.random(rgb.shape[:2], dtype=np.float32) - 0.5)[..., None] / 255.0
    return (np.clip(rgb + noise, 0, 1) * 255 + 0.5).astype(np.uint8)


def save_rgba(path, prem):
    """Straight-alpha 8-bit PNG from a premultiplied float RGBA array."""
    a = np.clip(prem[..., 3], 0, 1)
    rgb = np.clip(prem[..., :3] / np.maximum(a[..., None], 1e-5), 0, 1)
    rgb = bleed(rgb, a)
    out = np.dstack([to_u8(rgb), (a * 255 + 0.5).astype(np.uint8)])
    Image.fromarray(out, 'RGBA').save(path, compress_level=4)


def save_rgb(path, rgb, quality=None):
    im = Image.fromarray(to_u8(np.asarray(rgb, np.float32)), 'RGB')
    if quality:
        im.save(path, quality=quality)
    else:
        im.save(path, compress_level=4)
