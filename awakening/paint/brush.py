"""brush.py - gouache-style painting primitives on float RGBA canvases.

Everything here works on a premultiplied float32 RGBA canvas (H, W, 4) in sRGB
0..1.  Colour maths (mixing, jitter, atmosphere) happens in Oklab so blends stay
clean instead of going muddy.

Main entry points
-----------------
Canvas(w, h, bg=None, wrap=False)   canvas object; wrap=True makes stamps tile.
dabs(cv, x, y, size, ...)           stamp many elliptical bristle dabs at once.
stroke(cv, pts, width, color, ...)  one continuous bristle stroke along a polyline.
dab_stroke(cv, pts, ...)            a stroke made of individual dabs (leafy lines).
clump(cv, cx, cy, r, pal, ...)      a foliage clump: dark base, mid body, lit dabs.
paper_grain(cv, rng, amount)        subtle gouache/paper grain over the colour.
save_rgba(path, cv) / save_rgb      write PNG; RGBA gets colour bleed under alpha.
mix, jitter, atmos, shade           colour helpers (Oklab).
fbm(h, w, ...)                      cheap band-limited noise field.

All randomness goes through numpy Generators that the caller passes in, so every
asset is deterministic given its seed (see rng_for()).
"""
import zlib
import numpy as np
import cv2
from PIL import Image

# ----------------------------------------------------------------------------
# random / colour utilities
# ----------------------------------------------------------------------------

def rng_for(name):
    """Deterministic Generator for an asset name (crc32, stable across sessions)."""
    return np.random.default_rng(zlib.crc32(name.encode()))


def col(*v):
    """Colour from 0..255 ints or 0..1 floats -> float32 array (3,)."""
    a = np.array(v, np.float32).reshape(-1)[:3]
    if a.max() > 1.0:
        a = a / 255.0
    return a


_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]], np.float32)
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]], np.float32)
_M1i = np.linalg.inv(_M1)
_M2i = np.linalg.inv(_M2)


def _srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def oklab(rgb):
    """sRGB (...,3) -> Oklab (...,3)."""
    lin = _srgb_to_lin(rgb)
    lms = lin @ _M1.T
    lms = np.cbrt(lms)
    return lms @ _M2.T


def rgb_from_oklab(lab):
    """Oklab (...,3) -> sRGB (...,3), clipped."""
    lms = np.asarray(lab, np.float32) @ _M2i.T
    lin = (lms ** 3) @ _M1i.T
    return _lin_to_srgb(lin).astype(np.float32)


def mix(c1, c2, t):
    """Mix two sRGB colours in Oklab. t may be scalar or array (...,1)/(...)."""
    a, b = oklab(c1), oklab(c2)
    t = np.asarray(t, np.float32)
    if t.ndim and t.shape[-1] != 1:
        t = t[..., None]
    return rgb_from_oklab(a + (b - a) * t)


def mix_many(colors, t):
    """Piecewise mix along a list of sRGB colours, t in 0..1 (array ok)."""
    colors = [oklab(c) for c in colors]
    t = np.clip(np.asarray(t, np.float32), 0, 1) * (len(colors) - 1)
    i = np.minimum(t.astype(int), len(colors) - 2)
    f = (t - i)[..., None]
    labs = np.stack(colors)
    return rgb_from_oklab(labs[i] * (1 - f) + labs[i + 1] * f)


def shade(c, dl=0.0, dc=1.0, dh=0.0):
    """Shift an sRGB colour in Oklab: lightness +dl, chroma *dc, hue +dh radians."""
    lab = oklab(c)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    C = np.hypot(a, b) * dc
    h = np.arctan2(b, a) + dh
    return rgb_from_oklab(np.stack([L + dl, C * np.cos(h), C * np.sin(h)], -1))


def jitter(c, rng, n=None, dl=0.03, dc=0.08, dh=0.05):
    """Per-dab colour variation: Oklab lightness +-dl, chroma scale +-dc, hue +-dh.
    c may be one colour (then n copies) or an (n,3) array."""
    c = np.asarray(c, np.float32)
    if c.ndim == 1:
        c = np.broadcast_to(c, (n, 3))
    n = c.shape[0]
    lab = oklab(c)
    L = lab[:, 0] + rng.uniform(-dl, dl, n)
    a, b = lab[:, 1], lab[:, 2]
    C = np.hypot(a, b) * (1 + rng.uniform(-dc, dc, n))
    h = np.arctan2(b, a) + rng.uniform(-dh, dh, n)
    return rgb_from_oklab(np.stack([L, C * np.cos(h), C * np.sin(h)], -1))


def smoothstep(a, b, x):
    """Hermite step: 0 below a, 1 above b (array ok)."""
    t = np.clip((np.asarray(x, np.float32) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


MIST = col(255, 228, 196)
MIST_COOL = col(214, 206, 222)   # lavender-grey mist for upper/farther areas


def atmos(c, depth, mist=MIST, cool=0.5):
    """Atmospheric perspective: depth 0..1 pushes colour toward mist, loses chroma.
    cool mixes the mist between warm MIST (0) and lavender MIST_COOL (1)."""
    m = mix(mist, MIST_COOL, cool)
    lab = oklab(np.asarray(c, np.float32))
    ml = oklab(m)
    d = np.asarray(depth, np.float32)
    if d.ndim and d.shape[-1] != 1:
        d = d[..., None]
    out = lab + (ml - lab) * d
    # extra chroma loss, so far colours go grey-lavender rather than pastel
    out[..., 1:] *= (1 - 0.35 * d)
    return rgb_from_oklab(out)


# ----------------------------------------------------------------------------
# noise
# ----------------------------------------------------------------------------

def value_noise(h, w, cells, rng, tile=False):
    """Smooth random field (h, w) in 0..1 from a cells x cells grid, cubic upsample.
    tile=True makes it periodic."""
    cells = max(2, int(cells))
    g = rng.random((cells, cells)).astype(np.float32)
    if tile:
        g3 = np.tile(g, (3, 3))
        big = cv2.resize(g3, (3 * w, 3 * h), interpolation=cv2.INTER_CUBIC)
        return big[h:2 * h, w:2 * w]
    return cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)


def fbm(h, w, scale, rng, octaves=4, gain=0.5, tile=False):
    """Fractal sum of value_noise. scale = size in px of the largest feature.
    Returns roughly 0..1 (normalised)."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    cells = max(w, h) / scale
    for _ in range(octaves):
        out += amp * value_noise(h, w, cells, rng, tile)
        tot += amp
        amp *= gain
        cells *= 2
    out /= tot
    lo, hi = np.percentile(out, [1, 99])
    return np.clip((out - lo) / max(hi - lo, 1e-6), 0, 1)


def noise1d(n, cells, rng, periodic=True):
    """Smooth 1-D noise 0..1 of length n."""
    g = rng.random(int(cells) + 3).astype(np.float32)
    if periodic:
        g[-3:] = g[:3]
    x = np.linspace(0, len(g) - 3, n)
    i = x.astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return g[i] * (1 - f) + g[i + 1] * f


# ----------------------------------------------------------------------------
# bristle / edge textures (shared, deterministic)
# ----------------------------------------------------------------------------
_TEX_RNG = np.random.default_rng(1234)
N_TEX = 32
# 1-D bristle transparency profiles across the stroke width (periodic, 256)
BRISTLE = np.stack([
    0.55 * noise1d(256, 40, _TEX_RNG) + 0.45 * noise1d(256, 14, _TEX_RNG)
    for _ in range(N_TEX)]).astype(np.float32)
BRISTLE = (BRISTLE - BRISTLE.min(1, keepdims=True)) / np.ptp(BRISTLE, 1)[:, None]
# 2-D ragged-edge noise, 64x64, used to wobble the dab radius
EDGE2D = np.stack([value_noise(64, 64, 6, _TEX_RNG, tile=True) for _ in range(N_TEX)])
EDGE2D = (EDGE2D - 0.5).astype(np.float32)

# ----------------------------------------------------------------------------
# canvas
# ----------------------------------------------------------------------------


class Canvas:
    """Premultiplied float RGBA canvas. img[..., :3] is colour*alpha."""

    def __init__(self, w, h, bg=None, wrap=False):
        self.w, self.h, self.wrap = int(w), int(h), wrap
        self.img = np.zeros((self.h, self.w, 4), np.float32)
        if bg is not None:
            self.img[..., :3] = np.asarray(bg, np.float32)
            self.img[..., 3] = 1.0

    @property
    def alpha(self):
        return self.img[..., 3]

    def rgb(self):
        """Straight (un-premultiplied) colour."""
        a = np.maximum(self.img[..., 3:4], 1e-4)
        return np.clip(self.img[..., :3] / a, 0, 1)

    def composite(self, other, x=0, y=0, opacity=1.0):
        """Paint another canvas (premultiplied) over this one at offset (x, y)."""
        src = other.img if isinstance(other, Canvas) else other
        h, w = src.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        s = src[y0 - y:y1 - y, x0 - x:x1 - x] * opacity
        d = self.img[y0:y1, x0:x1]
        d *= (1 - s[..., 3:4])
        d += s

    def fill_mask(self, mask, color, opacity=1.0):
        """Flat colour through a (H, W) alpha mask."""
        a = (np.asarray(mask, np.float32) * opacity)[..., None]
        self.img *= (1 - a)
        self.img[..., :3] += a * np.asarray(color, np.float32)
        self.img[..., 3:4] += a

    def fill_vgradient(self, stops, y0=0, y1=None, opacity=1.0, noise=None):
        """Fill rows y0..y1 with a vertical Oklab gradient through sRGB `stops`.
        noise: optional (H,) array added to the gradient coordinate (streaks)."""
        y1 = self.h if y1 is None else y1
        t = np.linspace(0, 1, y1 - y0).astype(np.float32)
        if noise is not None:
            t = np.clip(t + noise, 0, 1)
        cols = mix_many(stops, t)                          # (rows, 3)
        a = opacity
        d = self.img[y0:y1]
        d *= (1 - a)
        d[..., :3] += cols[:, None, :] * a
        d[..., 3] += a

    def multiply_rgb(self, factor):
        """Multiply colour (keeps alpha). factor: scalar, (H,W) or (H,W,3)."""
        f = np.asarray(factor, np.float32)
        if f.ndim == 2:
            f = f[..., None]
        self.img[..., :3] *= f
        np.minimum(self.img[..., :3], self.img[..., 3:4], out=self.img[..., :3])

    def tint(self, color, amount):
        """Mix the colour toward `color` by amount (scalar or (H,W)), keeps alpha."""
        amt = np.asarray(amount, np.float32)
        if amt.ndim == 2:
            amt = amt[..., None]
        c = np.asarray(color, np.float32) * self.img[..., 3:4]
        self.img[..., :3] += (c - self.img[..., :3]) * amt


# ----------------------------------------------------------------------------
# dabs
# ----------------------------------------------------------------------------
_GRIDS = {}


def _grid(P):
    g = _GRIDS.get(P)
    if g is None:
        c = np.arange(P, dtype=np.float32) - (P - 1) / 2
        g = np.meshgrid(c, c)  # xx, yy
        _GRIDS[P] = g
    return g


def _dab_alphas(P, a, b, ang, tex, edge, rag, bristle, opacity):
    """Batch of dab alpha stamps (N, P, P). a, b: semi-axes (N,), ang radians (N,).
    edge: softness as a fraction of radius (0.1 crisp .. 0.6 soft).
    rag: ragged edge amount. bristle: streak transparency strength."""
    xx, yy = _grid(P)
    ca, sa = np.cos(ang)[:, None, None], np.sin(ang)[:, None, None]
    u = xx * ca + yy * sa
    v = -xx * sa + yy * ca
    ru = u / a[:, None, None]
    rv = v / b[:, None, None]
    r = np.sqrt(ru * ru + rv * rv)
    if np.any(rag > 0):
        iu = ((ru * 20 + 32).astype(np.int32)) & 63
        iv = ((rv * 20 + 32).astype(np.int32)) & 63
        n = EDGE2D[tex[:, None, None], iv, iu]
        r = r * (1 + (rag[:, None, None] * 0.9) * n)
    e = edge[:, None, None]
    alpha = np.clip((1 - r) / e, 0, 1)
    # slight squaring keeps the body opaque and the ramp short (gouache edge)
    alpha = alpha * alpha * (3 - 2 * alpha)
    if np.any(bristle > 0):
        iv = ((rv * 100 + 128 + tex[:, None, None] * 37).astype(np.int32)) & 255
        bt = BRISTLE[tex[:, None, None], iv]
        alpha = alpha * (1 - bristle[:, None, None] * bt)
    return alpha * opacity[:, None, None]


def dabs(cv, x, y, size, color, aspect=0.7, angle=None, opacity=1.0,
         edge=0.18, rag=0.5, bristle=0.35, rng=None, chunk=2048):
    """Stamp N elliptical bristle dabs.  All parameters may be scalars or (N,) arrays.

    x, y      centres (px).  size: full length of the dab's long axis (px).
    color     (3,) or (N,3) sRGB.  aspect: short/long axis ratio.
    angle     radians (None -> random).  opacity 0..1.
    edge      edge softness fraction.  rag: ragged-edge amount.  bristle: streakiness.
    Dabs in one call are stamped in random order (grouped by size for speed).
    """
    x = np.atleast_1d(np.asarray(x, np.float32))
    n = x.shape[0]
    if n == 0:
        return
    y = np.broadcast_to(np.asarray(y, np.float32), (n,))
    size = np.broadcast_to(np.asarray(size, np.float32), (n,))
    aspect = np.broadcast_to(np.asarray(aspect, np.float32), (n,))
    color = np.asarray(color, np.float32)
    color = np.broadcast_to(color, (n, 3)) if color.ndim == 1 else color
    opacity = np.broadcast_to(np.asarray(opacity, np.float32), (n,))
    edge = np.broadcast_to(np.asarray(edge, np.float32), (n,))
    rag = np.broadcast_to(np.asarray(rag, np.float32), (n,))
    bristle = np.broadcast_to(np.asarray(bristle, np.float32), (n,))
    if rng is None:
        rng = np.random.default_rng(int(abs(float(x[0]) * 7 + float(y[0]) * 13)) & 0xffff)
    if angle is None:
        angle = rng.uniform(0, np.pi, n).astype(np.float32)
    else:
        angle = np.broadcast_to(np.asarray(angle, np.float32), (n,))
    tex = rng.integers(0, N_TEX, n)

    if cv.wrap:
        # duplicate dabs that cross the border on the other side(s)
        W, H = cv.w, cv.h
        half = size * 0.5 * (1 + rag) + 2
        xs, ys, idx = [x], [y], [np.arange(n)]
        for dx in (-W, 0, W):
            for dy in (-H, 0, H):
                if dx == 0 and dy == 0:
                    continue
                m = ((x + dx + half > 0) & (x + dx - half < W) &
                     (y + dy + half > 0) & (y + dy - half < H))
                if m.any():
                    xs.append(x[m] + dx)
                    ys.append(y[m] + dy)
                    idx.append(np.nonzero(m)[0])
        idx = np.concatenate(idx)
        x, y = np.concatenate(xs), np.concatenate(ys)
        size, aspect, color = size[idx], aspect[idx], color[idx]
        opacity, edge, rag, bristle = opacity[idx], edge[idx], rag[idx], bristle[idx]
        angle, tex = angle[idx], tex[idx]
        n = x.shape[0]

    a = size * 0.5
    b = a * aspect
    # patch size: enough for the ragged ellipse
    P = np.ceil(size * (1 + 0.6 * rag) + 3).astype(np.int32)
    P = np.maximum(P, 3)
    img = cv.img
    H, W = cv.h, cv.w
    order = rng.permutation(n)
    Ps = P[order]
    # group by P, keep groups' internal order random
    uniq = np.unique(Ps)
    for p in uniq:
        sel = order[Ps == p]
        p = int(p)
        for c0 in range(0, len(sel), max(1, chunk * 400 // (p * p))):
            s = sel[c0:c0 + max(1, chunk * 400 // (p * p))]
            al = _dab_alphas(p, a[s], b[s], angle[s], tex[s], edge[s], rag[s],
                             bristle[s], opacity[s])
            xi = np.round(x[s] - (p - 1) / 2).astype(np.int32)
            yi = np.round(y[s] - (p - 1) / 2).astype(np.int32)
            cols = color[s]
            for k in range(len(s)):
                x0, y0 = xi[k], yi[k]
                x1, y1 = x0 + p, y0 + p
                A = al[k]
                if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
                    cx0, cy0 = max(x0, 0), max(y0, 0)
                    cx1, cy1 = min(x1, W), min(y1, H)
                    if cx1 <= cx0 or cy1 <= cy0:
                        continue
                    A = A[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
                    x0, y0, x1, y1 = cx0, cy0, cx1, cy1
                d = img[y0:y1, x0:x1]
                A3 = A[..., None]
                d *= (1 - A3)
                d[..., :3] += A3 * cols[k]
                d[..., 3] += A


# ----------------------------------------------------------------------------
# strokes
# ----------------------------------------------------------------------------

def smooth_path(pts, n=None, tension=0.5):
    """Catmull-Rom resample of a polyline (M,2) -> (n,2)."""
    pts = np.asarray(pts, np.float32)
    if len(pts) < 3:
        if n is None:
            return pts
        t = np.linspace(0, 1, n)[:, None]
        return pts[0] * (1 - t) + pts[-1] * t
    if n is None:
        n = int(np.sum(np.hypot(*np.diff(pts, axis=0).T)) / 3) + 2
    ext = np.vstack([pts[0] * 2 - pts[1], pts, pts[-1] * 2 - pts[-2]])
    seg = len(pts) - 1
    t = np.linspace(0, seg - 1e-6, n)
    i = t.astype(int)
    f = (t - i)[:, None]
    p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
    return 0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f ** 2 +
                  (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)


def wobble(pts, rng, amp, freq=3):
    """Displace a polyline sideways with smooth noise (hand tremor / bark lines)."""
    pts = np.asarray(pts, np.float32)
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.maximum(np.hypot(*nrm.T)[:, None], 1e-6)
    w = (noise1d(len(pts), freq, rng, periodic=False) - 0.5) * 2 * amp
    return pts + nrm * w[:, None]


def taper(n, start=0.3, end=0.0, body=1.0):
    """Width profile (n,) for a stroke: eases from start*body to body to end*body."""
    t = np.linspace(0, 1, n)
    w = np.ones(n, np.float32) * body
    k = 0.25
    w *= np.where(t < k, start + (1 - start) * np.sin(t / k * np.pi / 2), 1)
    w *= np.where(t > 1 - k, end + (1 - end) * np.sin((1 - t) / k * np.pi / 2), 1)
    return w


def stroke(cv, pts, width, color, opacity=1.0, edge=0.25, bristle=0.45, rag=0.3,
           color2=None, shade_side=0.0, tex=None, rng=None, color_along=None,
           light=None, color_lit=None, color_dark=None, core=0.0):
    """One continuous stroke along polyline pts (M,2) with per-point width (M,) or scalar.

    color     body colour; color2 (optional) is the colour on the +normal side
              (shade_side>0 blends from color at -side to color2 at +side).
    color_along  optional (M,3) colour per polyline point (varies along the stroke).
    light + color_lit (+ color_dark)  cylinder shading: the side whose outward
              normal faces the light vector (lx, ly) blends to color_lit, the far
              side blends to color_dark (default: body colour); core>0 darkens a
              core-shadow band just past the terminator.
    bristle   streak transparency across the width; rag: ragged edge noise.
    The stroke is rendered in one vectorised pass over its bounding box.
    """
    pts = np.asarray(pts, np.float32)
    m = len(pts)
    if m < 2:
        return
    width = np.broadcast_to(np.asarray(width, np.float32), (m,))
    if rng is None:
        rng = np.random.default_rng(int(abs(pts[0, 0] * 3 + pts[0, 1] * 5)) & 0xffff)
    if tex is None:
        tex = int(rng.integers(0, N_TEX))
    wmax = float(width.max()) * (1 + rag) + 2
    if cv.wrap:
        # tile: repeat the stroke at every offset whose bounding box touches the canvas
        cv.wrap = False
        try:
            for dx in (-cv.w, 0, cv.w):
                for dy in (-cv.h, 0, cv.h):
                    q = pts + [dx, dy]
                    if (q[:, 0].max() + wmax < 0 or q[:, 0].min() - wmax > cv.w or
                            q[:, 1].max() + wmax < 0 or q[:, 1].min() - wmax > cv.h):
                        continue
                    stroke(cv, q, width, color, opacity, edge, bristle, rag, color2, shade_side,
                           tex, rng, color_along, light, color_lit, color_dark, core)
        finally:
            cv.wrap = True
        return
    x0 = int(max(0, np.floor(pts[:, 0].min() - wmax)))
    y0 = int(max(0, np.floor(pts[:, 1].min() - wmax)))
    x1 = int(min(cv.w, np.ceil(pts[:, 0].max() + wmax) + 1))
    y1 = int(min(cv.h, np.ceil(pts[:, 1].max() + wmax) + 1))
    if x1 <= x0 or y1 <= y0:
        return
    hh, ww = y1 - y0, x1 - x0
    best_d = np.full((hh, ww), 1e9, np.float32)      # squared distance to polyline
    best_s = np.zeros((hh, ww), np.float32)          # arclength param 0..1
    best_t = np.zeros((hh, ww), np.float32)          # signed perpendicular distance
    best_w = np.ones((hh, ww), np.float32)
    best_nl = np.zeros((hh, ww), np.float32)         # normal . light (signed by side)
    seg = np.diff(pts, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(seglen)])
    total = max(cum[-1], 1e-6)
    for i in range(m - 1):
        L = seglen[i]
        if L < 1e-3:
            continue
        wseg = max(width[i], width[i + 1]) * (1 + rag) + 2
        sx0 = int(max(0, np.floor(min(pts[i, 0], pts[i + 1, 0]) - wseg))) - x0
        sy0 = int(max(0, np.floor(min(pts[i, 1], pts[i + 1, 1]) - wseg))) - y0
        sx1 = int(min(cv.w, np.ceil(max(pts[i, 0], pts[i + 1, 0]) + wseg) + 1)) - x0
        sy1 = int(min(cv.h, np.ceil(max(pts[i, 1], pts[i + 1, 1]) + wseg) + 1)) - y0
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        xs = np.arange(sx0, sx1, dtype=np.float32) + x0 - pts[i, 0]
        ys = np.arange(sy0, sy1, dtype=np.float32) + y0 - pts[i, 1]
        X, Y = np.meshgrid(xs, ys)
        dx, dy = seg[i] / L
        t = np.clip((X * dx + Y * dy) / L, 0, 1)
        px = X - t * L * dx
        py = Y - t * L * dy
        d2 = px * px + py * py
        side = -X * dy + Y * dx
        sub = (slice(sy0, sy1), slice(sx0, sx1))
        better = d2 < best_d[sub]
        best_d[sub] = np.where(better, d2, best_d[sub])
        s_here = (cum[i] + t * L) / total
        best_s[sub] = np.where(better, s_here, best_s[sub])
        best_t[sub] = np.where(better, side, best_t[sub])
        w_here = width[i] + (width[i + 1] - width[i]) * t
        best_w[sub] = np.where(better, w_here, best_w[sub])
        if light is not None:
            nl = -dy * light[0] + dx * light[1]
            best_nl[sub] = np.where(better, nl, best_nl[sub])
    dist = np.sqrt(best_d)
    half = np.maximum(best_w * 0.5, 0.3)
    rr = dist / half
    if rag > 0:
        iu = ((best_s * total / 6).astype(np.int32)) & 63
        iv = ((best_t / np.maximum(half, 1) * 20 + 32).astype(np.int32)) & 63
        rr = rr * (1 + rag * 1.5 * EDGE2D[tex, iv, iu])
    alpha = np.clip((1 - rr) / edge, 0, 1)
    alpha = alpha * alpha * (3 - 2 * alpha)
    if bristle > 0:
        iv = ((best_t / np.maximum(half, 1) * 100 + 128).astype(np.int32)) & 255
        alpha *= (1 - bristle * BRISTLE[tex, iv])
    alpha *= opacity
    alpha = alpha.astype(np.float32)
    color = np.asarray(color, np.float32)
    if color_along is not None:
        ca = np.asarray(color_along, np.float32)
        idx = np.clip((best_s * (len(ca) - 1)).astype(int), 0, len(ca) - 1)
        colimg = ca[idx]
    else:
        colimg = np.broadcast_to(color, (hh, ww, 3))
    if color2 is not None:
        k = np.clip(best_t / np.maximum(half, 1) * 0.5 + 0.5 + shade_side, 0, 1)
        c2 = np.asarray(color2, np.float32)
        colimg = colimg * (1 - k[..., None]) + c2 * k[..., None]
    if light is not None and color_lit is not None:
        # position across the cylinder in -1..1, times which side faces the light
        # which side faces the light; magnitude eased so a trunk lit from 40 deg
        # above still gets a fully lit and a fully dark edge
        fac = np.sign(best_nl) * (0.55 + 0.45 * np.abs(best_nl))
        tn = np.clip(best_t / np.maximum(half, 1), -1, 1) * fac
        k = smoothstep(0.05, 0.9, tn)
        cl = np.asarray(color_lit, np.float32)
        colimg = colimg * (1 - k[..., None]) + cl * k[..., None]
        if color_dark is not None:
            kd = smoothstep(0.0, -0.85, tn)
            cd = np.asarray(color_dark, np.float32)
            colimg = colimg * (1 - kd[..., None]) + cd * kd[..., None]
        if core > 0:
            band = np.exp(-((tn + 0.2) / 0.3) ** 2) * core
            colimg = colimg * (1 - band[..., None] * 0.3)
    d = cv.img[y0:y1, x0:x1]
    A3 = alpha[..., None]
    d *= (1 - A3)
    d[..., :3] += A3 * colimg
    d[..., 3] += alpha


def dab_stroke(cv, pts, size, color, spacing=0.35, jitter_pos=0.3, aspect=0.6,
               along=True, rng=None, **kw):
    """Stroke built from dabs along the polyline (good for leafy twigs and grass).
    spacing is a fraction of dab size; dabs are aligned to the path if along."""
    pts = np.asarray(pts, np.float32)
    if rng is None:
        rng = np.random.default_rng(1)
    seg = np.diff(pts, axis=0)
    L = np.hypot(seg[:, 0], seg[:, 1])
    cum = np.concatenate([[0], np.cumsum(L)])
    total = cum[-1]
    size = np.broadcast_to(np.asarray(size, np.float32), (len(pts),))
    n = int(total / (float(size.mean()) * spacing)) + 1
    s = np.linspace(0, total, n)
    xs = np.interp(s, cum, pts[:, 0])
    ys = np.interp(s, cum, pts[:, 1])
    sz = np.interp(s, cum, size)
    i = np.clip(np.searchsorted(cum, s) - 1, 0, len(seg) - 1)
    ang = np.arctan2(seg[i, 1], seg[i, 0]) if along else None
    if ang is not None:
        ang = ang + rng.normal(0, 0.25, n)
    xs = xs + rng.normal(0, 1, n) * sz * jitter_pos
    ys = ys + rng.normal(0, 1, n) * sz * jitter_pos
    dabs(cv, xs, ys, sz, color, aspect=aspect, angle=ang, rng=rng, **kw)


# ----------------------------------------------------------------------------
# foliage clump
# ----------------------------------------------------------------------------

def make_palette(shadow, mid, lit, tip=None, depth=0.0, cool=0.5):
    """Foliage palette dict. depth>0 applies atmospheric perspective to all."""
    tip = lit if tip is None else tip
    pal = {'shadow': col(*shadow), 'mid': col(*mid), 'lit': col(*lit), 'tip': col(*tip)}
    if depth > 0:
        pal = {k: atmos(v, depth, cool=cool) for k, v in pal.items()}
    return pal


def lumpy_radius(phi, rng, lobes=4, amp=0.16):
    """Radius multiplier for angle phi (array) giving a lumpy, leafy silhouette."""
    r = np.ones_like(phi)
    for k in range(1, 4):
        ph = rng.uniform(0, 2 * np.pi)
        r += amp / k * np.cos(phi * (lobes + k - 1) + ph)
    return r


def leaf_fans(cv, x, y, size, color, rng, n_leaves=5, spread=1.3, direction=None,
              aspect=0.42, **kw):
    """Groups of leaves fanning out from points (x, y) (arrays, one fan per point).
    size: leaf length. direction: angle the fan opens toward (array, radians);
    None -> random. Leaf dabs are elongated and their far end sits at the point
    plus the leaf direction, like a cluster of leaves on a twig tip."""
    x = np.atleast_1d(np.asarray(x, np.float32))
    m = len(x)
    if m == 0:
        return
    y = np.broadcast_to(np.asarray(y, np.float32), (m,))
    size = np.broadcast_to(np.asarray(size, np.float32), (m,))
    color = np.asarray(color, np.float32)
    color = np.broadcast_to(color, (m, 3)) if color.ndim == 1 else color
    if direction is None:
        direction = rng.uniform(0, 2 * np.pi, m)
    nl = rng.integers(max(2, n_leaves - 2), n_leaves + 2, m)
    tot = int(nl.sum())
    rep = np.repeat(np.arange(m), nl)
    # angle of each leaf within its fan
    frac = np.concatenate([np.linspace(-0.5, 0.5, k) for k in nl]) if tot else np.zeros(0)
    ang = direction[rep] + frac * spread + rng.normal(0, 0.12, tot)
    # leaf sizes: mostly near the nominal size, a few clearly bigger (skewed)
    L = size[rep] * (0.7 + 0.5 * rng.random(tot) ** 1.6 + 0.6 * (rng.random(tot) < 0.12))
    px = x[rep] + np.cos(ang) * L * 0.45
    py = y[rep] + np.sin(ang) * L * 0.45
    cols = jitter(color[rep], rng, dl=0.025, dc=0.08, dh=0.06)
    dabs(cv, px, py, L, cols, aspect=aspect * rng.uniform(0.8, 1.25, tot), angle=ang,
         rng=rng, **kw)


def clump(cv, cx, cy, r, pal, rng, light=(0.62, -0.78), detail=1.0, density=1.0,
          lit_amount=1.0, shadow_bias=0.0, base=True, mid=True, rag=0.3,
          bristle=0.3, edge=0.2, flatten=1.0, rim=0.0, lobes=None, leaf_scale=1.0,
          terminator=0.0):
    """Paint a foliage clump at (cx, cy), radius r (px).

    pal         dict from make_palette: shadow / mid / lit / tip.
    light       unit vector toward the sun in image space (x right, y down).
    detail      1 = foreground (small dabs, leaf fans), 0.4 = mid, 0.15 = far.
    density     texture density multiplier (base mass is always solid).
    lit_amount  how many lit dabs (0 = none, e.g. deep shadow / backlit clump).
    shadow_bias -1..1 shifts the whole clump darker (<0) or lighter (>0).
    flatten     vertical squash of the clump (<1 flatter).
    rim         0..1 strength of a warm rim-light line on the sun-side edge
                (used for backlit canopies).
    leaf_scale  multiplies the leaf dab size.
    terminator  shifts the light/shadow boundary (-0.5 more lit .. 0.5 more shadow).
    Every layer is driven by one 'lit value' v in 0..1 across the clump (0 = shadow
    side, 1 = sun-facing edge): base mass -> shadow texture -> mid leaf clusters
    (dense where v is high) -> lit clusters -> pale tips (-> rim light).
    """
    lx, ly = light
    nphi = 64
    phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
    rad = lumpy_radius(phi, rng, lobes=int(rng.integers(3, 6)) if lobes is None else lobes)

    def inside(px, py):
        ang = np.arctan2((py - cy) / flatten, px - cx)
        idx = ((ang / (2 * np.pi) * nphi) % nphi).astype(int)
        rr = np.hypot(px - cx, (py - cy) / flatten)
        return rr / (r * rad[idx])

    def litval(px, py):
        lit = ((px - cx) * lx + (py - cy) / flatten * ly) / r
        return smoothstep(-0.25 + terminator, 0.85 + terminator, lit)

    def scatter(n, rmax=1.0, shift=0.0):
        u = rng.random(n)
        ang = rng.uniform(0, 2 * np.pi, n)
        rr = np.sqrt(u) * rmax
        px = cx + np.cos(ang) * rr * r + lx * r * shift
        py = cy + (np.sin(ang) * rr * r + ly * r * shift) * flatten
        return px, py

    sh, md, lt, tp = pal['shadow'], pal['mid'], pal['lit'], pal['tip']
    if shadow_bias != 0:
        t = abs(shadow_bias)
        if shadow_bias > 0:
            sh, md, lt = (mix(c, lt, t * 0.5) for c in (sh, md, lt))
        else:
            dk = shade(sh, dl=-0.05, dc=0.85)
            sh, md, lt = (mix(c, dk, t * 0.6) for c in (sh, md, lt))
            tp = mix(tp, lt, t * 0.7)
    ramp = [sh, md, lt]

    dab_sz = r * (0.42 - 0.22 * detail)                      # base dab long axis
    leaf = r * (0.19 - 0.09 * detail) * (0.9 + 0.3 * (1 - detail)) * leaf_scale
    nl = 4 if detail > 0.5 else 3
    kw = dict(rag=rag, bristle=bristle, edge=edge)

    # --- 1. base mass: dark cool, solid fill of the lumpy silhouette
    if base:
        n = int(24 * (r / dab_sz) ** 2) + 12
        px, py = scatter(n, 1.0)
        k = inside(px, py)
        keep = k < 0.97
        px, py, k = px[keep], py[keep], k[keep]
        sz = dab_sz * (1.1 - 0.45 * k) * rng.uniform(0.85, 1.15, len(px))
        v = litval(px, py)
        t = np.clip(0.1 + 0.45 * v + rng.normal(0, 0.05, len(px)), 0, 0.7)
        cols = jitter(mix(sh, md, t[:, None]), rng, dl=0.012, dc=0.06, dh=0.05)
        ang_d = np.arctan2(py - cy, px - cx) + rng.normal(0, 0.6, len(px)) + np.pi / 2
        dabs(cv, px, py, sz, cols, aspect=rng.uniform(0.7, 0.95, len(px)),
             angle=ang_d, rng=rng, rag=rag, bristle=bristle * 0.4, edge=edge)
        # edge leaves: small clusters along the silhouette, pointing outward
        ne = int((40 + 60 * detail) * (r / 80) ** 0.95) + 8
        ang = rng.uniform(0, 2 * np.pi, ne)
        idx = ((ang / (2 * np.pi) * nphi) % nphi).astype(int)
        rr = r * rad[idx] * rng.uniform(0.86, 1.0, ne)
        px = cx + np.cos(ang) * rr
        py = cy + np.sin(ang) * rr * flatten
        v = litval(px, py)
        t = np.clip(0.15 + 0.75 * v + rng.normal(0, 0.08, ne), 0, 1)
        cols = mix_many(ramp, t * 0.75)
        leaf_fans(cv, px, py, leaf * rng.uniform(0.8, 1.15, ne), cols, rng,
                  n_leaves=nl, spread=0.9, aspect=0.6,
                  direction=ang + rng.normal(0, 0.3, ne), **kw)

    # --- 2. shadow-side texture: sparse, low contrast
    if mid:
        n = int(density * (r * r) / (leaf * leaf) * 0.14 * (0.5 + 0.5 * detail)) + 2
        px, py = scatter(n, 0.9, -0.1)
        k = inside(px, py)
        v = litval(px, py)
        keep = (k < 0.9) & (v < 0.35)
        px, py = px[keep], py[keep]
        m = len(px)
        cols = jitter(mix(sh, md, rng.uniform(0.3, 0.55, m)[:, None]), rng, dl=0.015, dc=0.08)
        d = np.arctan2(py - cy, px - cx) + rng.normal(0, 0.5, m)
        leaf_fans(cv, px, py, leaf * rng.uniform(0.8, 1.1, m), cols, rng, n_leaves=3,
                  spread=0.8, aspect=0.62, direction=d, **kw)

    # --- 3. mid body: leaf clusters, dense where the clump is lit, grouped in
    #        patches (a few patch centres on the lit side) so light reads as
    #        clusters rather than an even dusting
    if mid:
        n = int(density * (r * r) / (leaf * leaf) * 1.6 * (0.55 + 0.45 * detail)) + 6
        npatch = int(3 + 4 * detail)
        pcx, pcy = scatter(npatch, 0.75, 0.3)
        pid = rng.integers(0, npatch, n)
        prad = r * rng.uniform(0.28, 0.45, npatch)
        px = pcx[pid] + rng.normal(0, 1, n) * prad[pid]
        py = pcy[pid] + rng.normal(0, 1, n) * prad[pid] * flatten
        k = inside(px, py)
        v = litval(px, py)
        keep = (k < 0.97) & (rng.random(n) < 0.1 + 0.9 * v ** 1.5)
        px, py, v, k = px[keep], py[keep], v[keep], k[keep]
        m = len(px)
        t = np.clip(0.3 + 0.6 * v + rng.normal(0, 0.1, m), 0, 1)
        cols = mix_many(ramp, t)
        d = np.arctan2(py - cy, px - cx)
        d = d + np.angle(np.exp(1j * (-np.pi / 2 - d))) * 0.4 + rng.normal(0, 0.4, m)
        leaf_fans(cv, px, py, leaf * rng.uniform(0.75, 1.3, m), cols, rng,
                  n_leaves=nl, spread=1.0, aspect=0.55, direction=d, **kw)

    # --- 4. lit leaves: sun side only, warm
    if lit_amount > 0:
        n = int(lit_amount * density * (r * r) / (leaf * leaf) * 0.9 * (0.5 + 0.5 * detail)) + 2
        npatch = int(2 + 3 * detail)
        pcx, pcy = scatter(npatch, 0.6, 0.45)
        pid = rng.integers(0, npatch, n)
        prad = r * rng.uniform(0.2, 0.35, npatch)
        px = pcx[pid] + rng.normal(0, 1, n) * prad[pid]
        py = pcy[pid] + rng.normal(0, 1, n) * prad[pid] * flatten
        k = inside(px, py)
        v = litval(px, py)
        prob = smoothstep(0.4, 1.0, v) ** 1.2
        keep = (k < 1.0) & (rng.random(n) < prob)
        px, py, v, k = px[keep], py[keep], v[keep], k[keep]
        m = len(px)
        t = np.clip(0.4 + 0.6 * smoothstep(0.45, 1.0, v) + rng.normal(0, 0.12, m), 0, 1)
        cols = mix(md, lt, t[:, None])
        d = np.arctan2(py - cy, px - cx)
        d = d + np.angle(np.exp(1j * (np.arctan2(ly, lx) - d))) * 0.4 + rng.normal(0, 0.35, m)
        leaf_fans(cv, px, py, leaf * rng.uniform(0.7, 1.0, m), cols, rng,
                  n_leaves=3, spread=0.9, aspect=0.6, direction=d,
                  rag=rag * 0.8, bristle=bristle, edge=edge)
        # tips: pale gold on the most sun-facing leaves
        if m > 0:
            nt = max(1, int(m * 0.2 * lit_amount))
            sel = np.argsort(-(v + 0.2 * k))[:nt]
            cols = jitter(mix(lt, tp, rng.uniform(0.4, 1.0, nt)[:, None]), rng,
                          dl=0.02, dc=0.1, dh=0.06)
            dabs(cv, px[sel] + lx * leaf * 0.5, py[sel] + ly * leaf * 0.5,
                 leaf * rng.uniform(0.5, 0.8, nt), cols,
                 aspect=rng.uniform(0.45, 0.65, nt), angle=d[sel] + rng.normal(0, 0.3, nt),
                 rng=rng, rag=rag * 0.7, bristle=bristle * 0.6, edge=edge)

    # --- 5. rim light (backlit clumps): warm thin dabs along the sun-side edge
    if rim > 0:
        nr = int(rim * (20 + 40 * detail) * (r / 80) ** 0.9) + 4
        a0 = np.arctan2(ly, lx)
        ang = a0 + rng.normal(0, 0.8, nr)
        idx = ((ang / (2 * np.pi) * nphi) % nphi).astype(int)
        rr = r * rad[idx] * rng.uniform(0.9, 1.0, nr)
        px = cx + np.cos(ang) * rr
        py = cy + np.sin(ang) * rr * flatten
        cols = jitter(mix(lt, tp, rng.uniform(0.3, 1.0, nr)[:, None]), rng, dl=0.03, dc=0.1)
        dabs(cv, px, py, leaf * rng.uniform(0.5, 0.9, nr), cols, aspect=0.35,
             angle=ang + rng.normal(0, 0.4, nr), rng=rng, rag=rag * 0.6,
             bristle=bristle, edge=edge, opacity=rim)


def clump_cluster(cv, cx, cy, r, pal, rng, n=5, spread=0.55, light=(0.62, -0.78),
                  detail=1.0, shadow_bias=0.0, bounds=None, **kw):
    """A lump of n overlapping clumps forming a bigger mass; back ones darker,
    front/sun-side ones brighter. Painted back-to-front. shadow_bias applies to
    the whole cluster on top of the per-clump variation. bounds=(x0, y0, x1, y1)
    keeps every clump (plus its leafy fringe) inside that box."""
    lx, ly = light
    offs = np.clip(rng.normal(0, 1, (n, 2)), -1.8, 1.8)
    offs[:, 1] *= 0.7
    offs = offs * spread * r
    key = offs[:, 0] * lx + offs[:, 1] * ly
    order = np.argsort(key)
    for j, i in enumerate(order):
        ox, oy = offs[i]
        rr = r * rng.uniform(0.55, 0.85)
        x, y = cx + ox, cy + oy
        if bounds is not None:
            m = rr * 1.35
            x = float(np.clip(x, bounds[0] + m, bounds[2] - m))
            y = float(np.clip(y, bounds[1] + m, bounds[3] - m))
        bias = (key[i] / (spread * r + 1e-6)) * 0.35 + shadow_bias
        clump(cv, x, y, rr, pal, rng, light=light, detail=detail,
              shadow_bias=float(np.clip(bias, -0.8, 0.6)), **kw)


# ----------------------------------------------------------------------------
# finishing
# ----------------------------------------------------------------------------

def paper_grain(cv, rng, amount=0.02, fibre=0.012):
    """Multiply colour by subtle paper grain (fine speckle + soft fibre bands).
    amount ~0.01-0.03 luminance.  Alpha untouched."""
    h, w = cv.h, cv.w
    fine = rng.normal(0, 1, (h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(fine, (0, 0), 0.7)
    fine /= fine.std() + 1e-6
    fib = value_noise(h, w, max(2, w // 7), rng) - 0.5
    fib += 0.5 * (value_noise(h, w, max(2, w // 40), rng) - 0.5)
    g = 1 + amount * fine + fibre * fib * 4
    cv.multiply_rgb(g)


def _bleed(rgb, alpha, passes=(2, 4, 8, 16, 32, 64)):
    """Fill transparent pixels with nearby colour so texture filtering has no dark
    fringe.  Pull-push style: blur premultiplied colour and alpha, divide, fill holes."""
    out = rgb.copy()
    filled = alpha > 1e-3
    prem = rgb * alpha[..., None]
    a = alpha.copy()
    for s in passes:
        if filled.all():
            break
        bp = cv2.blur(prem, (s * 2 + 1, s * 2 + 1))
        ba = cv2.blur(a, (s * 2 + 1, s * 2 + 1))
        ok = (~filled) & (ba > 1e-4)
        out[ok] = (bp[ok] / ba[ok][:, None])
        filled |= ok
    if not filled.all():
        # whole-image average for anything still empty
        m = alpha > 1e-3
        avg = rgb[m].mean(0) if m.any() else np.array([0.5, 0.5, 0.5])
        out[~filled] = avg
    return np.clip(out, 0, 1)


def save_rgba(path, cv, bleed=True):
    """Write straight-alpha 8-bit PNG with colour bleed under transparent areas."""
    a = np.clip(cv.img[..., 3], 0, 1)
    rgb = cv.rgb()
    if bleed:
        rgb = _bleed(rgb, a)
    out = np.dstack([rgb, a])
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), 'RGBA').save(path, compress_level=6)


def save_rgb(path, cv, dither=True):
    """Write 8-bit RGB PNG (flattened over nothing: assumes opaque canvas).
    Tiny ordered dither prevents banding in smooth gradients."""
    rgb = cv.rgb()
    if dither:
        rng = np.random.default_rng(7)
        rgb = rgb + (rng.random(rgb.shape).astype(np.float32) - 0.5) / 255
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB').save(
        path, compress_level=6)


def alpha_extent(cv, thresh=0.02):
    """Bounding box (x0, y0, x1, y1) of painted pixels."""
    m = cv.img[..., 3] > thresh
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return 0, 0, 0, 0
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
