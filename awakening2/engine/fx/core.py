"""core.py - canvases, compositing, seeds, timing and small geometry helpers.

Conventions (shared by every effect in the package)
  * canvas  : straight-alpha RGBA float32 (H, W, 4), sRGB 0..1.  Cel effects are
              composited into it with "over".
  * light   : additive "photography" buffer, float32 (H, W, 3), sRGB 0..1.  Glows,
              beams and flares go here; apply it last with `apply_light` (screen).
  * frame   : integer frame number at 24 fps.  Drawings are held on 2s unless an
              effect says otherwise (`held(frame, on, start)`).
  * seeds   : `seed(name, ...)` = zlib.crc32 of the joined parts -> deterministic.
  * sizes and positions are screen pixels of the canvas you pass in; nothing
    assumes 1920x1040.
"""
import math
import zlib

import numpy as np

from . import raster

FPS = 24


# ----------------------------------------------------------------------------- seeds / timing
def seed(*parts):
    return zlib.crc32("/".join(str(p) for p in parts).encode()) & 0xFFFFFFFF


def rng(*parts):
    return np.random.default_rng(seed(*parts))


def held(frame, on=2, start=0):
    """Frame whose drawing is on screen at `frame` when animating on `on`s from `start`."""
    if on <= 1:
        return int(frame)
    return int(start + ((int(frame) - start) // on) * on)


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / max(b - a, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ease_out(x, p=2.0):
    x = np.clip(x, 0.0, 1.0)
    return 1 - (1 - x) ** p


def ease_in(x, p=2.0):
    return np.clip(x, 0.0, 1.0) ** p


# ----------------------------------------------------------------------------- colour
def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def pal(*hexes):
    return np.stack([hexc(h) for h in hexes]).astype(np.float32)


def mix(a, b, t):
    return (np.asarray(a, np.float32) * (1 - t) + np.asarray(b, np.float32) * t).astype(np.float32)


# ----------------------------------------------------------------------------- canvases
def new_canvas(h, w):
    return np.zeros((h, w, 4), np.float32)


def new_light(h, w):
    return np.zeros((h, w, 3), np.float32)


class Layer:
    """A premultiplied local cel buffer placed at (ox, oy) on a canvas.

    Effects paint shapes into a Layer (so a group can be faded or cut as one cel)
    and then `layer.onto(canvas, opacity)`."""

    def __init__(self, canvas_shape, x0, y0, x1, y1, pad=4):
        H, W = canvas_shape[:2]
        self.ox = int(max(0, math.floor(x0) - pad))
        self.oy = int(max(0, math.floor(y0) - pad))
        x1 = int(min(W, math.ceil(x1) + pad))
        y1 = int(min(H, math.ceil(y1) + pad))
        self.w = max(0, x1 - self.ox)
        self.h = max(0, y1 - self.oy)
        self.buf = np.zeros((max(self.h, 1), max(self.w, 1), 4), np.float32)
        self.empty = self.w == 0 or self.h == 0

    @classmethod
    def full(cls, canvas_shape):
        return cls(canvas_shape, 0, 0, canvas_shape[1], canvas_shape[0], pad=0)

    def onto(self, canvas, opacity=1.0):
        if self.empty or opacity <= 0:
            return canvas
        raster.over_premul(canvas, self.buf, self.ox, self.oy, float(opacity))
        return canvas

    def onto_light(self, light, gain=1.0):
        """Add this layer's premultiplied colour to an additive light buffer."""
        if self.empty or gain <= 0:
            return light
        sl = light[self.oy:self.oy + self.h, self.ox:self.ox + self.w]
        sl += self.buf[:self.h, :self.w, :3] * gain
        return light


def over(canvas, rgba, x0=0, y0=0, opacity=1.0):
    """Straight-alpha `rgba` patch over the straight-alpha canvas at (x0, y0)."""
    pm = np.empty_like(rgba, dtype=np.float32)
    pm[..., :3] = rgba[..., :3] * rgba[..., 3:4]
    pm[..., 3] = rgba[..., 3]
    raster.over_premul(canvas, pm, int(x0), int(y0), float(opacity))
    return canvas


def to_premul(canvas):
    out = canvas.copy()
    out[..., :3] *= out[..., 3:4]
    return out


def from_premul(pm):
    out = pm.copy()
    a = out[..., 3:4]
    np.divide(out[..., :3], a, out=out[..., :3], where=a > 1e-6)
    return out


def apply_light(rgb, light, mode='screen'):
    """Apply the additive photography buffer to an RGB image (returns new array)."""
    L = np.clip(light, 0, None)
    if mode == 'add':
        return np.clip(rgb + L, 0, 1)
    return 1 - (1 - np.clip(rgb, 0, 1)) * (1 - np.clip(L, 0, 1))


def composite(bg_rgb, canvas=None, light=None):
    """bg (H,W,3) <- canvas (straight RGBA, over) <- light (screen).  For tests and the lead."""
    out = bg_rgb[..., :3].astype(np.float32).copy()
    if canvas is not None:
        a = canvas[..., 3:4]
        out = canvas[..., :3] * a + out * (1 - a)
    if light is not None:
        out = apply_light(out, light)
    return out


# ----------------------------------------------------------------------------- geometry
def rot(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    p = np.asarray(pts, np.float64)
    return np.stack([p[:, 0] * c - p[:, 1] * s, p[:, 0] * s + p[:, 1] * c], 1)


def unit(v):
    v = np.asarray(v, np.float64)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.array([0.0, -1.0])


def polyline_normals(p):
    p = np.asarray(p, np.float64)
    d = np.zeros_like(p)
    if len(p) < 2:
        d[:] = (1, 0)
    else:
        d[1:-1] = p[2:] - p[:-2]
        d[0] = p[1] - p[0]
        d[-1] = p[-1] - p[-2]
    ln = np.linalg.norm(d, axis=1, keepdims=True)
    d = d / np.maximum(ln, 1e-9)
    return np.stack([-d[:, 1], d[:, 0]], 1), d


def stroke_poly(p, widths, cap_pts=0):
    """Outline polygon of a variable-width stroke along polyline p (N,2)."""
    p = np.asarray(p, np.float64)
    w = np.broadcast_to(np.asarray(widths, np.float64), (len(p),))
    n, d = polyline_normals(p)
    left = p + n * (w[:, None] * 0.5)
    right = p - n * (w[:, None] * 0.5)
    parts = [left]
    if cap_pts and w[-1] > 0.5:
        a0 = math.atan2(n[-1, 1], n[-1, 0])
        ang = a0 - np.linspace(0, math.pi, cap_pts + 2)[1:-1]
        parts.append(p[-1] + np.stack([np.cos(ang), np.sin(ang)], 1) * w[-1] * 0.5)
    parts.append(right[::-1])
    if cap_pts and w[0] > 0.5:
        a0 = math.atan2(-n[0, 1], -n[0, 0])
        ang = a0 - np.linspace(0, math.pi, cap_pts + 2)[1:-1]
        parts.append(p[0] + np.stack([np.cos(ang), np.sin(ang)], 1) * w[0] * 0.5)
    return np.concatenate(parts, 0)


def resample_polyline(p, step):
    p = np.asarray(p, np.float64)
    if len(p) < 2:
        return p.copy()
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    L = s[-1]
    if L < 1e-9:
        return p[:1].copy()
    m = max(2, int(math.ceil(L / step)) + 1)
    t = np.linspace(0, L, m)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def chaikin(p, it=2, closed=True):
    p = np.asarray(p, np.float64)
    for _ in range(it):
        if closed:
            q = np.roll(p, -1, 0)
        else:
            q = p[1:]
            p = p[:-1]
        a = 0.75 * p + 0.25 * q
        b = 0.25 * p + 0.75 * q
        r = np.empty((2 * len(p), 2))
        r[0::2] = a
        r[1::2] = b
        if not closed:
            r = np.concatenate([p[:1], r, q[-1:]], 0)
        p = r
    return p


class PolyBatch:
    """Collects cel polygons (fill / shade / ink) and paints them in one numba call.

    shade: points outside the "terminator disc" (tx, ty, tr) take the shade colour
           (tr <= 0: no shading).  This gives curved, designed shadow shapes.
    ink_w: line width in px drawn centred on the outline (0 = no line).
    """

    def __init__(self):
        self.verts = []
        self.fill = []
        self.shade = []
        self.ink = []
        self.par = []          # ink_w, tx, ty, tr, alpha

    def add(self, pts, fill, shade=None, ink=None, ink_w=0.0, term=None, alpha=1.0):
        pts = np.asarray(pts, np.float64)
        if len(pts) < 3 or alpha <= 0:
            return
        self.verts.append(pts)
        self.fill.append(fill)
        self.shade.append(fill if shade is None else shade)
        self.ink.append(fill if ink is None else ink)
        if term is None:
            term = (0.0, 0.0, 0.0)
        self.par.append((float(ink_w), float(term[0]), float(term[1]), float(term[2]), float(alpha)))

    def __len__(self):
        return len(self.verts)

    def bbox(self):
        if not self.verts:
            return None
        allp = np.concatenate(self.verts, 0)
        m = max(p[0] for p in self.par) + 2
        return allp[:, 0].min() - m, allp[:, 1].min() - m, allp[:, 0].max() + m, allp[:, 1].max() + m

    def paint(self, layer):
        if not self.verts or layer.empty:
            return layer
        starts = np.zeros(len(self.verts) + 1, np.int64)
        starts[1:] = np.cumsum([len(v) for v in self.verts])
        V = np.concatenate(self.verts, 0).astype(np.float64)
        raster.paint_polys(layer.buf, layer.ox, layer.oy, V, starts,
                           np.asarray(self.fill, np.float32), np.asarray(self.shade, np.float32),
                           np.asarray(self.ink, np.float32), np.asarray(self.par, np.float64))
        return layer

    def draw(self, canvas, opacity=1.0, layer=None):
        """Paint into a fresh layer sized to the batch and composite it onto the canvas."""
        bb = self.bbox()
        if bb is None:
            return canvas
        if layer is None:
            layer = Layer(canvas.shape, *bb)
        self.paint(layer)
        layer.onto(canvas, opacity)
        return canvas


class LobeBatch:
    """Cel-shaded round lobes (dust, mist, smoke).  Painted back to front in the order added.

    Each lobe: centre, radius, lit crescent size `ls` (fraction of r, on the side facing the
    light), shadow crescent size `ss`, shadow-side line width `lw` (px), edge wobble amplitude
    `wa` and phase `wp`, opacity `al`, and `lk` (radius factor of the lit offset disc)."""

    COLS = 15

    def __init__(self):
        self.rows = []

    def add(self, cx, cy, r, ls=0.3, ss=0.4, lw=0.0, wa=0.04, wp=0.0, al=1.0, lk=1.0, sk=1.0,
            tone=None, li=0.0):
        tc = (0.0, 0.0, 0.0) if tone is None else tone
        self.rows.append((cx, cy, r, ls, ss, lw, wa, wp, lk, al, sk, tc[0], tc[1], tc[2], li))

    def add_arrays(self, cx, cy, r, ls, ss, lw, wa, wp, al=1.0, lk=1.0, sk=1.0, tcx=0.0, tcy=0.0,
                   tr=0.0, li=0.0):
        n = len(np.atleast_1d(cx))
        cols = [np.broadcast_to(np.asarray(v, np.float64), (n,)) for v in
                (cx, cy, r, ls, ss, lw, wa, wp, lk, al, sk, tcx, tcy, tr, li)]
        self.rows.extend(map(tuple, np.stack(cols, 1)))

    def __len__(self):
        return len(self.rows)

    def array(self):
        if not self.rows:
            return np.zeros((0, self.COLS), np.float64)
        return np.asarray(self.rows, np.float64)

    def bbox(self):
        L = self.array()
        if len(L) == 0:
            return None
        R = L[:, 2] * (1 + np.abs(L[:, 6])) + L[:, 5] + 2
        return (L[:, 0] - R).min(), (L[:, 1] - R).min(), (L[:, 0] + R).max(), (L[:, 1] + R).max()

    def paint(self, layer, palette, light_dir):
        L = self.array()
        if len(L) == 0 or layer.empty:
            return layer
        l = unit(light_dir)
        raster.paint_lobes(layer.buf, layer.ox, layer.oy, L, np.asarray(palette, np.float32),
                           float(l[0]), float(l[1]))
        return layer


def cut_holes(layer, holes):
    """Erase discs from a layer (holes: iterable of (cx, cy, r, wobble_amp, wobble_phase))."""
    H = np.asarray(list(holes), np.float64).reshape(-1, 5)
    if len(H) and not layer.empty:
        raster.cut_discs(layer.buf, layer.ox, layer.oy, H)
    return layer


class BillowBatch:
    """Groups of discs ("billows") painted back to front in the order added.

    Within a group the lit cap and the shadow boundary are unions of shifted discs, so the
    tone shapes are scalloped by the bumps (see raster.paint_billows).  A silhouette colour
    line (shadow side) is painted under all groups so only the outer edge shows it."""

    def __init__(self):
        self.groups = []      # (discs (n, 7), alpha, inner_line, line_widths (n,))

    def add(self, discs, alpha=1.0, inner=0.0, line=None):
        D = np.asarray(discs, np.float64).reshape(-1, 7)
        if len(D) == 0:
            return
        lw = np.zeros(len(D)) if line is None else np.broadcast_to(np.asarray(line, np.float64), (len(D),))
        self.groups.append((D, float(alpha), float(inner), np.asarray(lw, np.float64)))

    def __len__(self):
        return len(self.groups)

    def bbox(self):
        if not self.groups:
            return None
        D = np.concatenate([g[0] for g in self.groups], 0)
        LW = np.concatenate([g[3] for g in self.groups], 0)
        R = D[:, 2] * (1 + np.abs(D[:, 3])) + LW + 2
        return (D[:, 0] - R).min(), (D[:, 1] - R).min(), (D[:, 0] + R).max(), (D[:, 1] + R).max()

    def paint(self, layer, palette, light_dir):
        if not self.groups or layer.empty:
            return layer
        l = unit(light_dir)
        P = np.asarray(palette, np.float32)
        D = np.ascontiguousarray(np.concatenate([g[0] for g in self.groups], 0))
        LW = np.ascontiguousarray(np.concatenate([g[3] for g in self.groups], 0))
        if LW.max() > 0.05:
            raster.paint_disc_lines(layer.buf, layer.ox, layer.oy, D[:, :5].copy(), LW, P[3].copy(),
                                    float(l[0]), float(l[1]))
        starts = np.zeros(len(self.groups) + 1, np.int64)
        starts[1:] = np.cumsum([len(g[0]) for g in self.groups])
        GP = np.asarray([(g[1], g[2]) for g in self.groups], np.float64)
        raster.paint_billows(layer.buf, layer.ox, layer.oy, starts, D, GP, P, float(l[0]), float(l[1]))
        return layer


_GRAIN = {}


def _grain_tex(n=512):
    """Tileable dry-brush grain: soft streaks along x at a few scales (0..1, mean 0.5)."""
    if n in _GRAIN:
        return _GRAIN[n]
    import cv2
    g = np.random.default_rng(seed('fx_grain'))
    acc = np.zeros((n, n), np.float32)
    for sx, sy, wgt in ((30.0, 12.0, 0.6), (60.0, 30.0, 0.4), (10.0, 5.0, 0.2)):
        z = g.standard_normal((n, n)).astype(np.float32)
        z = np.tile(z, (3, 3))
        z = cv2.GaussianBlur(z, (0, 0), sigmaX=sx, sigmaY=sy)[n:2 * n, n:2 * n]
        acc += wgt * z / (z.std() + 1e-6)
    acc = (acc - acc.mean()) / (acc.std() + 1e-6)
    tex = np.clip(0.5 + 0.18 * acc, 0, 1).astype(np.float32)
    _GRAIN[n] = tex
    return tex


def brush_grain(layer, amount=0.06, anchor=(0.0, 0.0), scale=1.0, light=(0.6, -0.8)):
    """Low-contrast dry-brush grain inside a layer's fills (multiplies its colour by 1 +/- amount),
    streaked across the light direction and anchored at `anchor` so it travels with the effect."""
    if layer.empty or amount <= 0:
        return layer
    import cv2
    tex = _grain_tex()
    n = tex.shape[0]
    h, w = layer.buf.shape[:2]
    l = unit(light)
    ang = math.atan2(l[1], l[0]) + math.pi / 2
    s = max(scale, 0.05)
    ca, sa = math.cos(ang) / s, math.sin(ang) / s
    ox = layer.ox - anchor[0]
    oy = layer.oy - anchor[1]
    # affine map from layer pixels to texture pixels (rotation + scale), wrapped
    M = np.array([[ca, sa, ca * ox + sa * oy], [-sa, ca, -sa * ox + ca * oy]], np.float32)
    M[:, 2] = np.mod(M[:, 2], n)
    big = np.tile(tex, (3, 3))
    M2 = M.copy()
    M2[:, 2] += n
    T = cv2.warpAffine(big, M2, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                       borderMode=cv2.BORDER_WRAP)
    k = 1.0 + amount * 2.0 * (T - 0.5)
    layer.buf[..., :3] *= k[..., None]
    return layer
