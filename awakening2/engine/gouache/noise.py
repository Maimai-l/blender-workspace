"""noise.py - band-limited noise fields and 1-D noise (deterministic via Generators)."""
import zlib
import numpy as np
import cv2


def rng_for(name):
    """Deterministic Generator for a name (crc32 - stable across sessions)."""
    return np.random.default_rng(zlib.crc32(name.encode()))


def value_noise(h, w, cells_x, rng, cells_y=None, tile=False):
    """Smooth random field (h, w) in 0..1 from a coarse grid, cubic upsample."""
    cx = max(2, int(round(cells_x)))
    cy = max(2, int(round(cells_y if cells_y is not None else cells_x * h / max(w, 1))))
    g = rng.random((cy, cx)).astype(np.float32)
    if tile:
        g3 = np.tile(g, (3, 3))
        big = cv2.resize(g3, (3 * w, 3 * h), interpolation=cv2.INTER_CUBIC)
        return big[h:2 * h, w:2 * w]
    # pad by one cell so the border is not clamped
    g = np.pad(g, 1, mode='reflect')
    big = cv2.resize(g, ((cx + 2) * w // cx, (cy + 2) * h // cy), interpolation=cv2.INTER_CUBIC)
    oy = (big.shape[0] - h) // 2
    ox = (big.shape[1] - w) // 2
    return np.ascontiguousarray(big[oy:oy + h, ox:ox + w])


def fbm(h, w, scale, rng, octaves=4, gain=0.5, tile=False, normalize=True):
    """Fractal noise; `scale` = size in px of the largest feature. ~0..1."""
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    cells = max(w, h) / max(scale, 1)
    for _ in range(octaves):
        cx = cells * w / max(w, h)
        cy = cells * h / max(w, h)
        out += amp * value_noise(h, w, max(cx, 2), rng, cells_y=max(cy, 2), tile=tile)
        tot += amp
        amp *= gain
        cells *= 2
    out /= tot
    if normalize:
        lo, hi = np.percentile(out, [1, 99])
        out = np.clip((out - lo) / max(hi - lo, 1e-6), 0, 1)
    return out


def noise1d(n, cells, rng, periodic=False):
    """Smooth 1-D noise in 0..1, length n."""
    g = rng.random(int(max(cells, 1)) + 3).astype(np.float32)
    if periodic:
        g[-3:] = g[:3]
    x = np.linspace(0, len(g) - 3, n)
    i = x.astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return (g[i] * (1 - f) + g[i + 1] * f).astype(np.float32)


def sample(field, x, y, ox=0.0, oy=0.0):
    """Nearest sample of a (H, W) field at flat coords (x, y) (+offset), clamped."""
    H, W = field.shape[:2]
    xi = np.clip((np.asarray(x) + ox).astype(np.int32), 0, W - 1)
    yi = np.clip((np.asarray(y) + oy).astype(np.int32), 0, H - 1)
    return field[yi, xi]
