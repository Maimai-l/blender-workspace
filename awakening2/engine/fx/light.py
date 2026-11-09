"""light.py - photography helpers: sunbeams, motes and sparkles, glows, bloom, lens flare.

These are the only soft (airbrushed) elements of the package.  They draw into the additive
light buffer (H, W, 3); apply it last with `core.apply_light` (screen).  `sunbeams` also
returns a beam-strength mask (H, W) so motes, leaves (`sunlit=`) and other effects can
light up only inside the shafts.
"""
import math

import numpy as np
from numba import njit

from . import core, palettes, raster
from .core import PolyBatch, held

TAU = 2 * math.pi


@njit(cache=True, fastmath=True)
def _beams(mask, sx, sy, B):
    """B columns: angle, half-width at source (px), spread (rad), length, intensity, softness,
    fade-in length.  Writes the summed beam strength into mask."""
    H, W = mask.shape
    nb = B.shape[0]
    for y in range(H):
        dy = y + 0.5 - sy
        for x in range(W):
            dx = x + 0.5 - sx
            r = math.sqrt(dx * dx + dy * dy) + 1e-6
            th = math.atan2(dy, dx)
            v = 0.0
            for b in range(nb):
                d = th - B[b, 0]
                if d > math.pi:
                    d -= 2 * math.pi
                elif d < -math.pi:
                    d += 2 * math.pi
                hw = B[b, 1] + r * math.tan(B[b, 2])
                across = abs(d) * r / hw
                if across >= 1.0:
                    continue
                L = B[b, 3]
                if r > L:
                    continue
                soft = B[b, 5]
                e = 1.0 - across
                if e < soft:
                    t = e / soft
                    prof = t * t * (3 - 2 * t)
                else:
                    prof = 1.0
                along = 1.0 - (r / L) ** 1.5
                fi = B[b, 6]
                if fi > 0 and r < fi:
                    t = r / fi
                    along *= t * t * (3 - 2 * t)
                v += prof * along * B[b, 4]
            mask[y, x] = v


def sunbeams(light, src, angles, widths=None, spread=0.04, length=None, colour=None,
             intensity=0.35, softness=0.6, frame=0, name='beams', shimmer=0.15, fade_in=0.0,
             scale=1.0):
    """Light shafts from `src` (may be off-screen) at `angles` (radians, screen; pi/2 = down).

    widths: half-widths at the source (px, list or scalar); spread: widening (rad);
    length: px (default: past the frame); shimmer: slow intensity breathing (on 1s).
    Adds colour * mask to `light` (if not None) and returns the mask (H, W) float32.
    `scale` < 1 computes the mask at lower resolution (fast) and upsamples it."""
    H, W = (light.shape[:2] if light is not None else (int(src[2]), int(src[3])))
    n = len(angles)
    widths = np.broadcast_to(np.asarray(60.0 if widths is None else widths, np.float64), (n,))
    L = math.hypot(W, H) * 1.6 if length is None else length
    g = core.rng('beams', name)
    ph = g.uniform(0, TAU, n)
    fr = g.uniform(0.04, 0.09, n)
    B = np.zeros((n, 7), np.float64)
    for i, a in enumerate(angles):
        sh = 1 + shimmer * math.sin(frame * fr[i] + ph[i]) * math.sin(frame * fr[i] * 0.37 + 2 * ph[i])
        B[i] = (a, widths[i] * scale, spread, L * scale, intensity * sh, softness, fade_in * scale)
    hs, ws = max(1, int(round(H * scale))), max(1, int(round(W * scale)))
    mask = np.zeros((hs, ws), np.float32)
    _beams(mask, src[0] * scale, src[1] * scale, B)
    if scale != 1.0:
        import cv2
        mask = cv2.resize(mask, (W, H), interpolation=cv2.INTER_LINEAR)
    if light is not None:
        col = palettes.LIGHT_GOLD if colour is None else np.asarray(colour, np.float32)
        light += mask[..., None] * col[None, None, :]
    return mask


def glow(light, xy, radius, colour=None, intensity=0.5, core_r=0.0, hardness=1.5):
    """Soft airbrush glow (photography) at xy."""
    col = palettes.LIGHT_GOLD if colour is None else np.asarray(colour, np.float32)
    raster.add_soft_discs(light, np.array([[xy[0], xy[1], core_r, radius, col[0], col[1], col[2],
                                            intensity, hardness]], np.float64))
    return light


def bloom(rgb, threshold=0.78, radius=24.0, strength=0.5, colour=None):
    """Bloom for a finished frame: bright parts blurred at three scales and screened back."""
    import cv2
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    k = np.clip((lum - threshold) / max(1 - threshold, 1e-3), 0, 1)[..., None]
    src = (rgb * k).astype(np.float32)
    if colour is not None:
        src = src * np.asarray(colour, np.float32)
    acc = np.zeros_like(src)
    for m, wgt in ((0.35, 0.5), (1.0, 0.35), (2.6, 0.25)):
        acc += cv2.GaussianBlur(src, (0, 0), radius * m) * wgt
    return core.apply_light(rgb, acc * strength)


class Motes:
    """Dust motes and sparkles drifting in the light (drawn into the light buffer).

    region: (x0, y0, x1, y1); mask: optional (H, W) beam strength (from `sunbeams`) - motes
    only show where the light is; sparkle: fraction that flash into 4-point stars."""

    def __init__(self, name, region, count=120, size=(1.0, 3.0), drift=(0.25, -0.15),
                 wander=6.0, sparkle=0.12, colour=None, intensity=0.9, on=1):
        g = core.rng('motes', name)
        x0, y0, x1, y1 = region
        self.n = count
        self.x = g.uniform(x0, x1, count)
        self.y = g.uniform(y0, y1, count)
        self.w, self.h = x1 - x0, y1 - y0
        self.x0, self.y0 = x0, y0
        self.sz = g.uniform(size[0], size[1], count)
        self.ph = g.uniform(0, TAU, (count, 3))
        self.fq = g.uniform(0.02, 0.06, (count, 3))
        self.tw = g.uniform(0.08, 0.25, count)
        self.drift = np.asarray(drift, np.float64) * g.uniform(0.6, 1.4, (count, 1))
        self.wander = wander
        self.sp = g.random(count) < sparkle
        self.col = palettes.LIGHT_GOLD if colour is None else np.asarray(colour, np.float32)
        self.intensity = intensity
        self.on = on
        self.name = name

    def draw(self, light, frame, mask=None):
        f = held(frame, self.on)
        H, W = light.shape[:2]
        x = self.x + self.drift[:, 0] * f + self.wander * (np.sin(f * self.fq[:, 0] + self.ph[:, 0])
                                                           + 0.5 * np.sin(f * self.fq[:, 1] * 2.3 + self.ph[:, 1]))
        y = self.y + self.drift[:, 1] * f + self.wander * np.sin(f * self.fq[:, 2] + self.ph[:, 2])
        x = self.x0 + np.mod(x - self.x0, self.w)
        y = self.y0 + np.mod(y - self.y0, self.h)
        tw = 0.55 + 0.45 * np.sin(f * self.tw + self.ph[:, 0] * 3)
        rows = []
        stars = PolyBatch()
        for i in range(self.n):
            xi, yi = x[i], y[i]
            if not (0 <= xi < W and 0 <= yi < H):
                continue
            m = 1.0 if mask is None else float(mask[int(yi), int(xi)])
            v = m * tw[i] * self.intensity
            if v < 0.03:
                continue
            s = self.sz[i]
            rows.append((xi, yi, s * 0.5, s * 2.5, *self.col, v, 2.0))
            if self.sp[i] and tw[i] > 0.85:
                ln = s * 7 * (tw[i] - 0.85) / 0.15
                for a in (0.0, math.pi / 2):
                    ca, sa = math.cos(a + 0.3), math.sin(a + 0.3)
                    P = np.array([(xi - ca * ln, yi - sa * ln), (xi + ca * ln, yi + sa * ln)])
                    stars.add(core.stroke_poly(np.array([P[0], (xi, yi), P[1]]), [0.2, max(1.0, s * 0.7), 0.2]),
                              self.col, alpha=min(1.0, v))
        if rows:
            raster.add_soft_discs(light, np.asarray(rows, np.float64))
        if len(stars):
            lay = core.Layer(light.shape, *stars.bbox())
            stars.paint(lay)
            lay.onto_light(light, 1.0)
        return light


def lens_flare(light, src, strength=0.35, colour=None, frame=0, ghosts=6, streak=True, rays=8,
               name='flare'):
    """A subtle lens flare: ghost discs along the line from `src` through the frame centre, a
    soft horizontal streak and faint rays at the source."""
    H, W = light.shape[:2]
    c = np.array([W / 2, H / 2])
    s = np.asarray(src, np.float64)
    d = c - s
    g = core.rng('flare', name)
    cols = [palettes.LIGHT_GOLD, core.hexc('#9fd6c8'), core.hexc('#c9a6e8'), core.hexc('#ffb38a')]
    diag = math.hypot(W, H)
    rows = []
    for i in range(ghosts):
        t = g.uniform(0.4, 2.0)
        p = s + d * t
        r = diag * g.uniform(0.012, 0.05)
        col = cols[i % len(cols)]
        rows.append((p[0], p[1], r * 0.6, r * 0.5, *col, strength * g.uniform(0.05, 0.12), 0.6))
    rows.append((s[0], s[1], 0, diag * 0.12, *(palettes.LIGHT_GOLD if colour is None else colour),
                 strength * 0.35, 1.2))
    raster.add_soft_discs(light, np.asarray(rows, np.float64))
    b = PolyBatch()
    if streak:
        L = W * 0.45
        q = np.linspace(-1, 1, 9)
        P = np.stack([s[0] + q * L, s[1] + q * 0], 1)
        b.add(core.stroke_poly(P, 3.0 * (1 - np.abs(q)) ** 2 + 0.2), core.hexc('#ffe9b8'), alpha=strength * 0.6)
    for k in range(rays):
        a = k * TAU / rays + 0.2 + 0.03 * math.sin(frame * 0.05 + k)
        L = diag * 0.06 * (1.2 if k % 2 == 0 else 0.7)
        P = np.array([s, s + np.array([math.cos(a), math.sin(a)]) * L])
        b.add(core.stroke_poly(P, [2.2, 0.2]), core.hexc('#fff3d6'), alpha=strength * 0.5)
    if len(b):
        lay = core.Layer(light.shape, *b.bbox())
        b.paint(lay)
        lay.onto_light(light, 1.0)
    return light
