"""soft.py - painted soft focus (out-of-focus layers simplified by brushwork, no blur filter).

soft_trunk()    a trunk as 3 long bristle strokes: body, shadow side, lit side (no bark detail).
soft_mass()     a foliage mass in 2 flat planes with bristly painted edges and visible strokes.
soft_row()      a row of soft trunks with soft canopy masses on top.
mist_strokes()  mist as broad horizontal brush strokes with visible bristles (not airbrush).
soft_fern()     a fern as a few broad tapered strokes (fronds) with blocky leaflet strokes.
"""
import numpy as np

from .color import C, mix, jitter, aerial, shade, smoothstep
from .canvas import dabs, stroke, taper
from .foliage import Blobs
from .sky import paint_planes


def soft_trunk(cv, rng, x, y_base, y_top, w, body, lit, dark, lit_side=1.0, lean=0.0, opacity=1.0, glint=None):
    n = 7
    t = np.linspace(0, 1, n)
    H = y_base - y_top
    xs = x + lean * H * t + (rng.random(n) - 0.5) * w * 0.12
    ys = y_base - H * t
    pts = np.stack([xs, ys], 1)
    wd = w * (1.0 - 0.3 * t) * (1 + 0.5 * np.exp(-t / 0.05))          # flared foot
    stroke(cv, pts, wd, jitter(body, rng, 1, dl=0.015)[0], opacity=opacity, edge=0.3, bristle=0.5, rag=0.35,
           spacing=6.0, rng=rng)
    # shadow side and lit side: offset narrower strokes, alpha-locked so the silhouette stays one shape
    for side, col, k, op in ((-lit_side, dark, 0.45, 0.7), (lit_side, lit, 0.32, 0.75)):
        off = np.stack([side * wd * (0.5 - k * 0.5), np.zeros(n)], 1)
        stroke(cv, pts + off, wd * k, jitter(col, rng, 1, dl=0.02)[0], opacity=op * opacity, edge=0.5, bristle=0.7,
               rag=0.4, spacing=6.0, dry=0.15, mode='lock', rng=rng)
    if glint is not None:
        # a few warm light patches on the lit side
        for j in range(int(rng.integers(1, 4))):
            gy = y_base - H * rng.uniform(0.1, 0.8)
            gx = float(np.interp(gy, ys[::-1], xs[::-1])) + lit_side * w * 0.25
            L = rng.uniform(0.04, 0.1) * H
            stroke(cv, [[gx, gy - L / 2], [gx, gy + L / 2]], max(w * 0.25, 3), glint, opacity=rng.uniform(0.4, 0.7),
                   edge=0.6, bristle=0.6, rag=0.4, mode='lock', rng=rng)


def soft_mass(cv, rng, centres, cols, light3=(0.5, -0.8, 0.2), rim=None, strokes=0.9, brush_edge=1.0):
    """centres: list of (x, y, R). cols: (shadow, mid, lit, lit2). Two dominant planes."""
    b = Blobs()
    for (x, y, R) in centres:
        for j in range(int(rng.integers(2, 5))):
            r = R * rng.uniform(0.5, 0.85)
            b.add(x + rng.normal(0, R * 0.45), y + rng.normal(0, R * 0.3), r * 1.2, r * 0.8,
                  rot=rng.normal(0, 0.3), light=rng.uniform(0.85, 1.1), hue=rng.normal(0, 0.04), rng=rng, lumpy=0.22)
    if len(b) == 0:
        return
    paint_planes(cv, rng, b, cols, light3=light3, th=(0.42, 0.72, 0.97), soft=0.05, noise_amt=0.06,
                 strokes=strokes, stroke_size=None, rim=rim, rim_amt=0.5 if rim is not None else 0.0,
                 brush_edge=brush_edge, glob=0.45)


def mist_strokes(cv, rng, x0, x1, y0, y1, col_lit, col_shade, n, light=None, width=(30, 90), length=(300, 900),
                 opacity=(0.08, 0.2), profile='flat', angle=0.0):
    for k in range(n):
        u = rng.random()
        if profile == 'bottom':
            u = 1 - u ** 1.8
        elif profile == 'top':
            u = u ** 1.8
        y = y0 + (y1 - y0) * u
        x = rng.uniform(x0, x1)
        L = rng.uniform(*length)
        lt = float(light(x, y)) if light is not None else 0.5
        col = jitter(mix(col_shade, col_lit, lt), rng, 1, dl=0.02, dc=0.08)[0]
        a = angle + rng.normal(0, 0.03)
        dx, dy = np.cos(a) * L / 2, np.sin(a) * L / 2
        stroke(cv, [[x - dx, y - dy], [x, y + rng.normal(0, 4)], [x + dx, y + dy]],
               taper(10, 0.3, 0.3, rng.uniform(*width)), col, opacity=rng.uniform(*opacity) * (0.6 + 0.6 * lt),
               edge=0.6, bristle=0.65, rag=0.3, spacing=8.0, rng=rng)


def soft_row(cv, rng, x0, x1, y_base, y_top, n, d, haze, body, lit, dark, width=(12, 40), lit_side=1.0,
             canopy=True, canopy_cols=None, canopy_R=None, glint=None, lean_sd=0.02):
    xs = np.sort(rng.uniform(x0, x1, n))
    hb = aerial(body, d, haze)
    hl = aerial(lit, d * 0.85, haze)
    hd = aerial(dark, d, haze)
    for x in xs:
        w = float(np.exp(rng.uniform(np.log(width[0]), np.log(width[1]))))
        tb = y_top + rng.uniform(-40, 40)
        soft_trunk(cv, rng, x, y_base + rng.uniform(-10, 20), tb, w, jitter(hb, rng, 1, dl=0.03, dh=0.05)[0], hl, hd,
                   lit_side=lit_side, lean=rng.normal(0, lean_sd), glint=glint)
    if canopy:
        cols = canopy_cols or (C(36, 54, 66), C(60, 88, 78), C(128, 150, 92), C(150, 170, 104))
        hc = tuple(aerial(c, d, haze) for c in cols)
        R = canopy_R or (y_base - y_top) * 0.08
        cen = [(x, y_top + rng.uniform(0, R * 1.2), R * rng.uniform(0.8, 1.4))
               for x in np.arange(x0 - R, x1 + R, R * 1.4) + rng.normal(0, R * 0.3, len(np.arange(x0 - R, x1 + R, R * 1.4)))]
        soft_mass(cv, rng, cen, hc)


def soft_fern(cv, rng, x, y, size, cols, lean=0.0, n=None, spread=0.9, opacity=1.0, glint=None):
    """Simplified fern: fronds as broad tapered strokes, leaflets as a few blocky side strokes."""
    nf = n or int(rng.integers(5, 9))
    angs = -np.pi / 2 + lean + np.linspace(-1.2, 1.2, nf) * spread + rng.normal(0, 0.1, nf)
    for a0 in angs[np.argsort(np.abs(angs + np.pi / 2))[::-1]]:
        L = size * rng.uniform(0.7, 1.1)
        k = 8
        pts = [np.array([x, y], np.float32)]
        a = a0
        side = np.sign(np.cos(a0)) or 1.0
        for i in range(k):
            a += side * 0.1 * (i / k) * (1 + abs(np.cos(a0)))
            pts.append(pts[-1] + L / k * np.array([np.cos(a), np.sin(a)], np.float32))
        P = np.array(pts)
        v = rng.uniform(0.2, 0.8)
        col = jitter(mix(cols[0], cols[1], v), rng, 1, dl=0.02)[0]
        prof = np.sin(np.pi * np.clip(np.linspace(0, 1, len(P)) * 0.95 + 0.05, 0, 1)) ** 0.7
        stroke(cv, P, size * 0.22 * prof + 2, col, opacity=opacity, edge=0.4, bristle=0.6, rag=0.5, rng=rng)
        # blocky leaflet strokes across the frond (lighter on the upper side)
        for i in range(2, len(P) - 1):
            tg = P[i + 1] - P[i - 1]
            tg = tg / (np.hypot(*tg) + 1e-6)
            nrm = np.array([-tg[1], tg[0]])
            wl = size * 0.11 * prof[i]
            for sg in (-1, 1):
                q0 = P[i]
                q1 = P[i] + nrm * sg * wl + tg * wl * 0.6
                cc = jitter(mix(cols[1], cols[2], rng.uniform(0.2, 0.7)), rng, 1, dl=0.03)[0]
                stroke(cv, [q0, q1], max(wl * 0.5, 2), cc, opacity=0.6 * opacity, edge=0.4, bristle=0.6, rag=0.4,
                       mode='lock', rng=rng)
        if glint is not None and rng.random() < 0.6:
            g = P[int(rng.integers(3, len(P)))]
            dabs(cv, g[0] + rng.normal(0, 4, 3), g[1] + rng.normal(0, 4, 3), rng.uniform(4, 9, 3), glint,
                 aspect=0.5, shape='leaf', angle=rng.uniform(0, 6.28, 3), opacity=0.8, rng=rng)


def repaint(cv, rng, sizes=(36, 20), density=1.0, aspect=0.4, bristle=0.55, jit=(0.015, 0.06, 0.03), overlap=2.5,
            edge=0.45, rag=0.45, lowc=0.0, keep=0.0):
    """Painted soft focus: re-paint a finished layer with large flat-brush dabs that sample its
    colour and alpha and follow the local edge direction (structure-tensor orientation). Big
    brushes first, then smaller ones. Details dissolve into visible brush marks with soft,
    broken edges; the image itself is never blurred. lowc pulls colours toward the layer's
    mean (lower contrast); keep mixes back some of the original."""
    import cv2 as _cv2
    from .canvas import Canvas
    from .color import oklab, from_oklab
    img = cv.img
    h, w = img.shape[:2]
    a = np.clip(img[..., 3], 0, 1)
    rgb = img[..., :3] / np.maximum(a[..., None], 1e-4)
    lum = img[..., 0] * 0.3 + img[..., 1] * 0.59 + img[..., 2] * 0.11 + 0.5 * a
    gx = _cv2.Sobel(lum, _cv2.CV_32F, 1, 0, ksize=5)
    gy = _cv2.Sobel(lum, _cv2.CV_32F, 0, 1, ksize=5)
    sig = max(sizes[0] * 0.5, 4)
    jxx = _cv2.GaussianBlur(gx * gx, (0, 0), sig)
    jyy = _cv2.GaussianBlur(gy * gy, (0, 0), sig)
    jxy = _cv2.GaussianBlur(gx * gy, (0, 0), sig)
    ang_field = 0.5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
    mean = (rgb * a[..., None]).reshape(-1, 3).sum(0) / max(a.sum(), 1e-3)
    out = Canvas(cv.W, cv.H, cv.m)
    for s in sizes:
        step = s * 0.45 / np.sqrt(density)
        gy_, gx_ = np.mgrid[0:h:step, 0:w:step]
        px = (gx_.ravel() + rng.uniform(-0.5, 0.5, gx_.size) * step).astype(np.float32)
        py = (gy_.ravel() + rng.uniform(-0.5, 0.5, gy_.size) * step).astype(np.float32)
        ix = np.clip(px.astype(int), 0, w - 1)
        iy = np.clip(py.astype(int), 0, h - 1)
        ap = a[iy, ix]
        ok = ap > 0.01
        px, py, ix, iy, ap = px[ok], py[ok], ix[ok], iy[ok], ap[ok]
        order = rng.permutation(len(px))
        px, py, ix, iy, ap = px[order], py[order], ix[order], iy[order], ap[order]
        cols = rgb[iy, ix]
        if lowc > 0:
            cols = cols + (mean[None, :] - cols) * lowc
        cols = jitter(np.clip(cols, 0, 1), rng, dl=jit[0], dc=jit[1], dh=jit[2])
        o = 1 - (1 - np.clip(ap, 0, 0.999)) ** (1 / overlap)
        dabs(out, px - cv.m, py - cv.m, s * rng.uniform(0.8, 1.3, len(px)), cols,
             aspect=aspect * rng.uniform(0.8, 1.25, len(px)), angle=ang_field[iy, ix] + rng.normal(0, 0.2, len(px)),
             opacity=o, shape='flat', edge=edge, rag=rag, bristle=bristle, rng=rng)
    if keep > 0:
        cv.img[:] = out.img * (1 - keep) + cv.img * keep
    else:
        cv.img[:] = out.img
