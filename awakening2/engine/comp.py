"""comp.py - the 'photography' stage: multiplane backgrounds, cels, atmosphere,
light, grade and grain. Owns the final pixels.

Conventions: layers are straight-alpha float32 RGBA in memory unless noted;
`over()` takes premultiplied. Frame 1920x1040.
"""
import os, json, math
import numpy as np
import cv2
from PIL import Image

W, H = 1920, 1040
_CACHE = {}


def load_rgba(path, u8=False):
    """Load a straight-alpha RGBA layer. Cached as uint8 (4x smaller than float32); u8=True
    returns the cached uint8 array, otherwise a float32 copy in 0..1."""
    if path in _CACHE:
        im = _CACHE.pop(path)
        _CACHE[path] = im          # most recently used last
    else:
        im = np.ascontiguousarray(np.asarray(Image.open(path).convert('RGBA'), np.uint8))
        _CACHE[path] = im
        while len(_CACHE) > 12:    # bounded
            _CACHE.pop(next(iter(_CACHE)))
    if u8:
        return im
    return im.astype(np.float32) / 255.0


class Painting:
    """A multiplane background painting from the gouache engine (bg/<shot>/layers.json)."""
    def __init__(self, folder):
        self.folder = folder
        meta = json.load(open(os.path.join(folder, 'layers.json')))
        self.meta = meta
        self.size = meta['size']
        self.layers = meta['layers']

    def layer(self, name_or_idx):
        L = self.layers[name_or_idx] if isinstance(name_or_idx, int) else next(l for l in self.layers if l['name'] == name_or_idx)
        return L, load_rgba(os.path.join(self.folder, L['file']))

    def window(self, L, img, x0, y0, w=W, h=H, scale=1.0):
        """Crop a w x h window whose top-left is at painting coords (x0, y0) (float, bilinear)."""
        ox, oy = L['offset']
        M = np.array([[1 / scale, 0, x0 - ox], [0, 1 / scale, y0 - oy]], np.float32)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                              borderMode=cv2.BORDER_REPLICATE)


def premul(rgba):
    out = rgba.copy()
    out[..., :3] *= out[..., 3:4]
    return out


def over(dst, src):
    """premultiplied src over premultiplied dst"""
    return src + dst * (1 - src[..., 3:4])


def over_straight(dst_rgb, src, opacity=1.0):
    a = src[..., 3:4] * opacity
    return dst_rgb * (1 - a) + src[..., :3] * a


def light_from_screen(cam, az_deg, el_deg):
    """Direction TO the light from a screen-relative azimuth (0 = from behind the camera,
    90 = from screen right, 180 = from behind the subject) and an elevation."""
    f = np.array([cam.f[0], cam.f[1], 0.0], np.float32)
    if np.linalg.norm(f) < 1e-3:
        f = np.array([cam.u[0], cam.u[1], 0.0], np.float32)
    f /= np.linalg.norm(f)
    r = np.array([cam.r[0], cam.r[1], 0.0], np.float32); r /= max(np.linalg.norm(r), 1e-6)
    a = math.radians(az_deg); e = math.radians(el_deg)
    d = math.cos(e) * (math.sin(a) * r - math.cos(a) * f) + math.sin(e) * np.array([0, 0, 1.0], np.float32)
    return (d / np.linalg.norm(d)).astype(np.float32)


def ground_shadow(cam, shadow_map, z=0.0, ss=1, clean=(3, 3, 300, 2.0)):
    """Hard-edged cel shadow of the robot on the ground plane z, as a (H, W) mask."""
    import look
    Wc, Hc = cam.W, cam.H
    D = cam.ray_dirs()
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (z - cam.pos[2]) / D[..., 2]
    valid = (t > 0) & np.isfinite(t)
    P = cam.pos + D * np.where(valid, t, 0)[..., None]
    lit = np.ones((Hc, Wc), np.float32)
    lit[valid] = shadow_map.lit(P[valid], bias=0.15)
    sh = (lit < 0.5) & valid
    cc, co, ca, cs = clean
    return look.clean_mask(sh, cc * ss, co * ss, ca * ss * ss, cs * ss)


def blur(img, sigma):
    return cv2.GaussianBlur(img, (0, 0), sigma)


def light_wrap(rgb_robot_pm, alpha, bg_rgb, radius=18, strength=0.55):
    """Background light bleeding over the cel's silhouette (integration glow)."""
    a = alpha
    edge = np.clip(blur(1 - a, radius * 0.5) * a * 2.0, 0, 1)
    glow = blur(bg_rgb * (1 - a[..., None]), radius) / np.maximum(blur(1 - a, radius), 1e-3)[..., None]
    lum = np.clip((glow.mean(-1) - 0.45) / 0.45, 0, 1)
    k = (edge * lum * strength)[..., None]
    return rgb_robot_pm * (1 - k) + glow * a[..., None] * k


def blur_small(img, sigma, k=4):
    """A wide Gaussian blur computed at 1/k resolution (same look, ~k^2 times faster)."""
    h, w = img.shape[:2]
    sm = cv2.resize(img, (w // k, h // k), interpolation=cv2.INTER_AREA)
    sm = cv2.GaussianBlur(sm, (0, 0), sigma / k)
    return cv2.resize(sm, (w, h), interpolation=cv2.INTER_LINEAR)


def bloom(rgb, thr=0.8, sigma=22, strength=0.2, tint=(1.0, 0.86, 0.62)):
    b = np.clip(rgb - thr, 0, None) / (1 - thr)
    g = blur_small(b, sigma) * 0.6 + blur_small(b, sigma * 3) * 0.4
    return rgb + g * np.asarray(tint, np.float32) * strength


def s_curve(x, c=1.12, pivot=0.48):
    x = np.clip(x, 0, 1)
    return np.where(x < pivot, pivot * (x / pivot) ** c, 1 - (1 - pivot) * ((1 - x) / (1 - pivot)) ** c)


def grade(rgb, lift=(0.015, 0.012, 0.035), gain=(1.03, 1.0, 0.95), gamma=1.0, sat=1.04, contrast=1.12,
          warm_hi=(1.03, 0.99, 0.92), cool_lo=(0.94, 0.97, 1.06)):
    x = np.clip(rgb, 0, 1.5)
    lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
    hi = np.clip((lum - 0.45) / 0.45, 0, 1)[..., None]
    x = x * (np.asarray(cool_lo, np.float32) * (1 - hi) + np.asarray(warm_hi, np.float32) * hi)
    x = x * np.asarray(gain, np.float32) + np.asarray(lift, np.float32) * (1 - x)
    if contrast != 1.0:
        x = s_curve(x, contrast)
    mean = x.mean(-1, keepdims=True)
    x = mean + (x - mean) * sat
    if gamma != 1.0:
        x = np.clip(x, 0, None) ** (1 / gamma)
    return x


def vignette(rgb, strength=0.22, roundness=1.6):
    h, w = rgb.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (x - w / 2) / (w / 2); ny = (y - h / 2) / (h / 2)
    r = np.sqrt((np.abs(nx) ** roundness + np.abs(ny) ** roundness))
    v = 1 - strength * np.clip(r - 0.35, 0, None) ** 1.6
    return rgb * v[..., None]


_GRAIN = {}


def grain(rgb, frame, amount=0.018, size=1.3):
    """Film/paper grain that changes on 2s (like re-shot cels)."""
    key = (rgb.shape[0], rgb.shape[1])
    if key not in _GRAIN:
        rng = np.random.default_rng(7)
        g = [blur(rng.normal(0, 1, (key[0], key[1])).astype(np.float32), size) for _ in range(4)]
        g = [x / x.std() for x in g]
        _GRAIN[key] = g
    g = _GRAIN[key][(frame // 2) % 4]
    lum = rgb.mean(-1, keepdims=True)
    return rgb + g[..., None] * amount * (0.6 + 0.8 * lum * (1 - lum) * 4)


_PAPER = None


def paper(rgb, amount=0.025):
    """A fixed paper/gouache tooth texture over everything (multiplied lightly)."""
    global _PAPER
    if _PAPER is None or _PAPER.shape[:2] != rgb.shape[:2]:
        rng = np.random.default_rng(11)
        h, w = rgb.shape[:2]
        n = rng.normal(0, 1, (h, w)).astype(np.float32)
        p = blur(n, 0.8) * 0.6 + blur(n, 3.0) * 1.2 + blur(n, 12.0) * 2.0
        _PAPER = (p / p.std()).astype(np.float32)
    return rgb * (1 + _PAPER[..., None] * amount)


def finish(rgb, frame, vig=0.2, grain_amt=0.0, paper_amt=0.008, do_bloom=True, **gk):
    if do_bloom:
        rgb = bloom(rgb)
    rgb = grade(rgb, **gk)
    rgb = vignette(rgb, vig)
    rgb = paper(rgb, paper_amt)
    rgb = grain(rgb, frame, grain_amt)
    return np.clip(rgb, 0, 1)


def to_u8(rgb):
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
