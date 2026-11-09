"""atmos.py - mist, sunbeams, glows, dappled light, aerial perspective passes.

mist(cv, ...)        a mist bank built from many soft, low-opacity horizontal
                     strokes (visible brushwork), warm cream where lit and
                     lilac-grey in shade, density from a vertical profile and noise.
beams(cv, ...)       painted sunbeams: long soft streaky strokes fanning from a
                     source, fading along their length.
glow(cv, ...)        soft light bloom (used sparingly: sun, mist glow).
dapple(cv, ...)      sunlight patches on the ground (perspective-flattened).
haze_pass(cv, ...)   alpha-locked tint toward a haze colour by a (H, W) amount.
"""
import numpy as np

from .canvas import dabs, stroke, catmull, taper
from .color import C, mix, jitter, ramp, smoothstep
from .noise import fbm


def mist(cv, rng, x0, x1, y0, y1, col_lit, col_shade, light=None, density=1.0, opacity=(0.04, 0.12),
         size=(120, 420), aspect=(0.12, 0.3), profile='bottom', angle=0.0, noise_scale=500,
         bristle=0.5, n_mult=1.0):
    """Mist bank in the box. light: callable (x, y) -> 0..1 warmth/brightness.
    profile: 'bottom' (denser at y1), 'top', 'mid' or 'flat'."""
    W = x1 - x0
    H = y1 - y0
    n = int(n_mult * density * W * H / (np.mean(size) ** 2 * np.mean(aspect)) * 3.0)
    xs = rng.uniform(x0 - size[1] * 0.3, x1 + size[1] * 0.3, n)
    u = rng.random(n)
    if profile == 'bottom':
        ys = y0 + H * (1 - u ** 1.8)
    elif profile == 'top':
        ys = y0 + H * u ** 1.8
    elif profile == 'mid':
        ys = y0 + H * (0.5 + (rng.beta(2.2, 2.2, n) - 0.5))
    else:
        ys = y0 + H * u
    # horizontal density modulation (banks and gaps)
    nz = fbm(64, 256, 40, rng, octaves=3)
    ix = np.clip(((xs - x0) / max(W, 1) * 255).astype(int), 0, 255)
    iy = np.clip(((ys - y0) / max(H, 1) * 63).astype(int), 0, 63)
    keep = rng.random(n) < (0.25 + 0.75 * nz[iy, ix])
    xs, ys = xs[keep], ys[keep]
    n = len(xs)
    lt = light(xs, ys) if light is not None else np.full(n, 0.5, np.float32)
    cols = jitter(mix(col_shade, col_lit, np.clip(lt, 0, 1)[:, None]), rng, dl=0.02, dc=0.08, dh=0.04)
    sz = rng.uniform(*size, n)
    dabs(cv, xs, ys, sz, cols, aspect=rng.uniform(*aspect, n), angle=angle + rng.normal(0, 0.04, n),
         opacity=rng.uniform(*opacity, n) * (0.6 + 0.6 * np.clip(lt, 0, 1)), edge=0.95, rag=0.4,
         bristle=bristle, shape='round', rng=rng)


def beams(cv, rng, src, angles, length, widths, col, opacity=0.18, spread_w=1.6, streak=0.6,
          start_fade=0.08, end_len=0.85, edge=0.9):
    """Sunbeams from src (x, y) at the given angles (radians, image coords)."""
    for a, w in zip(angles, widths):
        L = length * rng.uniform(0.8, 1.1)
        k = 24
        t = np.linspace(0, 1, k)
        pts = np.stack([src[0] + np.cos(a) * L * t, src[1] + np.sin(a) * L * t], 1)
        wd = w * (0.6 + spread_w * t)
        op = opacity * smoothstep(0, start_fade, t) * (1 - smoothstep(end_len * 0.6, 1.0, t)) * rng.uniform(0.6, 1.1)
        c = jitter(np.broadcast_to(col, (k, 3)), rng, dl=0.01, dc=0.05, dh=0.02)
        stroke(cv, pts, wd, c, opacity=op, edge=edge, bristle=streak, rag=0.1, smooth=True,
               spacing=8.0, rng=rng)


def glow(cv, x, y, r, col, strength=0.5, squash=1.0):
    X, Y = cv.coords()
    d = np.hypot(X - x, (Y - y) / squash) / r
    a = np.exp(-d * d) * strength
    cv.over(col, np.clip(a, 0, 1))


def dapple(cv, rng, xs, ys, size, col, flatten=0.35, opacity=(0.5, 0.9), cluster=5, angle=0.0,
           mode='over', edge=0.6):
    """Sun patches: clusters of soft ellipses flattened by perspective."""
    xs = np.asarray(xs, np.float32)
    ys = np.asarray(ys, np.float32)
    size = np.broadcast_to(np.asarray(size, np.float32), xs.shape)
    cluster = cluster * 2
    m = len(xs) * cluster
    rep = np.repeat(np.arange(len(xs)), cluster)
    px = xs[rep] + rng.normal(0, 0.45, m) * size[rep]
    py = ys[rep] + rng.normal(0, 0.45, m) * size[rep] * flatten
    sz = size[rep] * rng.uniform(0.45, 0.95, m)
    edge = max(edge, 0.75)
    cols = jitter(np.broadcast_to(col, (m, 3)), rng, dl=0.03, dc=0.1, dh=0.04)
    dabs(cv, px, py, sz, cols, aspect=flatten * rng.uniform(0.8, 1.3, m), angle=angle + rng.normal(0, 0.1, m),
         opacity=rng.uniform(*opacity, m), edge=edge, rag=0.6, bristle=0.2, rng=rng, mode=mode)


def haze_pass(cv, col, amount):
    """Alpha-locked tint of the whole layer toward col by amount (scalar/(H,W))."""
    cv.lock_tint(col, amount)
