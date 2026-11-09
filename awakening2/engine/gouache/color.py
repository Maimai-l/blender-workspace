"""color.py - sRGB <-> Oklab, clean mixing, ramps, jitter, aerial perspective.

All colours are float32 sRGB in 0..1 (shape (3,) or (..., 3)). Mixing happens in
Oklab so blends between complementary hues stay clean instead of going muddy.
"""
import numpy as np

_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]], np.float32)
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]], np.float32)
_M1i = np.linalg.inv(_M1).astype(np.float32)
_M2i = np.linalg.inv(_M2).astype(np.float32)


def C(*v):
    """Colour from '#rrggbb', 0..255 ints (any component > 1) or 0..1 floats."""
    if len(v) == 1 and isinstance(v[0], str):
        h = v[0].lstrip('#')
        return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0
    a = np.array(v, np.float32).reshape(-1)[:3]
    if a.max() > 1.0:
        a = a / 255.0
    return a


def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((np.maximum(c, 0) + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def oklab(rgb):
    lms = srgb_to_lin(rgb) @ _M1.T
    return np.cbrt(lms) @ _M2.T


def from_oklab(lab):
    lms = np.asarray(lab, np.float32) @ _M2i.T
    return lin_to_srgb((lms ** 3) @ _M1i.T).astype(np.float32)


def mix(c1, c2, t):
    """Oklab mix; t scalar or array broadcastable to (..., 1)."""
    a, b = oklab(c1), oklab(c2)
    t = np.asarray(t, np.float32)
    if t.ndim and t.shape[-1] != 1:
        t = t[..., None]
    return from_oklab(a + (b - a) * t)


def ramp(stops, t, pos=None):
    """Piecewise Oklab ramp through `stops` (list of colours) at t (array) 0..1.
    pos: optional increasing stop positions (default evenly spaced)."""
    labs = np.stack([oklab(c) for c in stops]).astype(np.float32)
    k = len(stops)
    pos = np.linspace(0, 1, k) if pos is None else np.asarray(pos, np.float32)
    t = np.clip(np.asarray(t, np.float32), pos[0], pos[-1])
    i = np.clip(np.searchsorted(pos, t, side='right') - 1, 0, k - 2)
    f = ((t - pos[i]) / np.maximum(pos[i + 1] - pos[i], 1e-6))[..., None]
    return from_oklab(labs[i] * (1 - f) + labs[i + 1] * f)


def ramp_lab(stops, t, pos=None):
    """Like ramp() but returns Oklab (for further edits before converting)."""
    labs = np.stack([oklab(c) for c in stops]).astype(np.float32)
    k = len(stops)
    pos = np.linspace(0, 1, k) if pos is None else np.asarray(pos, np.float32)
    t = np.clip(np.asarray(t, np.float32), pos[0], pos[-1])
    i = np.clip(np.searchsorted(pos, t, side='right') - 1, 0, k - 2)
    f = ((t - pos[i]) / np.maximum(pos[i + 1] - pos[i], 1e-6))[..., None]
    return labs[i] * (1 - f) + labs[i + 1] * f


def shade(c, dl=0.0, dc=1.0, dh=0.0):
    """Shift colour(s) in Oklab: lightness +dl, chroma *dc, hue +dh (radians)."""
    lab = oklab(c)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    Cc = np.hypot(a, b) * dc
    h = np.arctan2(b, a) + dh
    return from_oklab(np.stack([L + dl, Cc * np.cos(h), Cc * np.sin(h)], -1))


def jitter(c, rng, n=None, dl=0.03, dc=0.08, dh=0.05):
    """Per-dab colour variation in Oklab (lightness +-dl, chroma *(1+-dc), hue +-dh)."""
    c = np.asarray(c, np.float32)
    if c.ndim == 1:
        c = np.broadcast_to(c, (n, 3))
    n = c.shape[0]
    lab = oklab(c)
    L = lab[:, 0] + rng.uniform(-dl, dl, n)
    Cc = np.hypot(lab[:, 1], lab[:, 2]) * (1 + rng.uniform(-dc, dc, n))
    h = np.arctan2(lab[:, 2], lab[:, 1]) + rng.uniform(-dh, dh, n)
    return from_oklab(np.stack([L, Cc * np.cos(h), Cc * np.sin(h)], -1))


def jitter_lab(lab, rng, dl=0.03, dc=0.08, dh=0.05):
    lab = np.asarray(lab, np.float32)
    n = lab.shape[0]
    L = lab[:, 0] + rng.uniform(-dl, dl, n)
    Cc = np.hypot(lab[:, 1], lab[:, 2]) * (1 + rng.uniform(-dc, dc, n))
    h = np.arctan2(lab[:, 2], lab[:, 1]) + rng.uniform(-dh, dh, n)
    return np.stack([L, Cc * np.cos(h), Cc * np.sin(h)], -1)


def lab_shift(lab, dl=0.0, dc=1.0, dh=0.0):
    lab = np.asarray(lab, np.float32)
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    Cc = np.hypot(a, b) * dc
    h = np.arctan2(b, a) + dh
    return np.stack([L + dl, Cc * np.cos(h), Cc * np.sin(h)], -1)


def aerial(c, depth, haze, chroma_loss=0.35):
    """Aerial perspective: depth 0..1 pulls colour toward `haze` in Oklab and drops
    chroma, so far things get lighter, cooler (if haze is cool), lower contrast."""
    lab = oklab(np.asarray(c, np.float32))
    hl = oklab(np.asarray(haze, np.float32))
    d = np.asarray(depth, np.float32)
    if d.ndim and d.shape[-1] != 1:
        d = d[..., None]
    out = lab + (hl - lab) * d
    out[..., 1:] *= (1 - chroma_loss * d * (1 - d))
    return from_oklab(out)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float32) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


# --- dawn palette ------------------------------------------------------------
DAWN = dict(
    sky_top=C(104, 112, 178), sky_violet=C(150, 140, 196), sky_rose=C(214, 168, 186),
    sky_peach=C(246, 196, 164), sky_gold=C(255, 214, 146), sky_cream=C(255, 236, 200),
    sun=C(255, 248, 226),
    mist_lit=C(255, 236, 202), mist_warm=C(250, 216, 170), mist_shade=C(190, 184, 210),
    mist_cool=C(168, 172, 200),
    leaf_deep=C(28, 42, 64), leaf_shadow=C(36, 64, 76), leaf_mid=C(62, 104, 84),
    leaf_lit=C(126, 162, 82), leaf_bright=C(190, 200, 98), leaf_tip=C(250, 224, 140),
    rim=C(255, 214, 140), rim_hot=C(255, 238, 190),
    moss_dark=C(40, 74, 70), moss=C(86, 128, 70), moss_lit=C(168, 192, 88),
    bark_dark=C(52, 48, 76), bark_mid=C(96, 86, 96), bark_lit=C(176, 150, 128),
    ground_shade=C(46, 62, 84), ground_mid=C(84, 108, 80), ground_lit=C(196, 188, 110),
)
