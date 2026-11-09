"""S16A - flight background, 4096 x 1040, tileable horizontally (x wraps exactly).

Three scrolling layers for a tracking shot beside the flying robot (scroll each at its
own speed): `sky` (gold sky with high clouds, slow), `cloud_bank` (a bank of sculpted
cumulus, medium), `wisps` (near fast streaks). Plus `sun_glow`, a screen-fixed
1920 x 1040 overlay (the sun is off-frame upper right) that should NOT scroll.
Tiling: every element is painted once on its own canvas and pasted at x and x +- W.
"""
import json
import os
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, noise1d
from ..canvas import Canvas, dabs, stroke, taper, grain, save_rgba, save_rgb
from ..layers import Painting
from ..sky import sky, plane_cloud, gradient_field
from ..atmos import glow

W, H, M = 4096, 1040, 0
HAZE = C(255, 222, 168)
PLANES = (C(150, 112, 162), C(238, 168, 132), C(255, 214, 148), C(255, 244, 212))


def planes(d):
    return tuple(aerial(c, d, HAZE) for c in PLANES)


def paste_wrap(dst, src, x0, y0):
    """Composite a premultiplied canvas `src` at (x0, y0) and at x0 +- W (wrap in x)."""
    h, w = src.img.shape[:2]
    for ox in (x0 - W, x0, x0 + W):
        X0, X1 = max(ox, 0), min(ox + w, W)
        Y0, Y1 = max(y0, 0), min(y0 + h, H)
        if X1 <= X0 or Y1 <= Y0:
            continue
        s = src.img[Y0 - y0:Y1 - y0, X0 - ox:X1 - ox]
        d = dst.img[Y0:Y1, X0:X1]
        d *= (1 - s[..., 3:4])
        d += s


def element(seed, w, h, fn):
    """Paint fn(cv, rng, lx, ly) on a private canvas (w x h) with its own rng."""
    cv = Canvas(w, h, 0)
    fn(cv, np.random.default_rng(seed))
    return cv


def build(outdir, quick=False):
    P = Painting('S16A', W, H, M, outdir)
    rng = rng_for('S16A')

    # ---------------------------------------------------------------- sky: x-independent gradient + wrapped elements
    cv = P.layer('sky', 0.1)
    stops = [C(196, 164, 194), C(236, 180, 162), C(250, 198, 136), C(255, 212, 132), C(255, 226, 160),
             C(255, 236, 190)]
    pos = [0.0, 0.12, 0.28, 0.45, 0.62, 1.0]
    Y = cv.ys()[:, None]
    cv.img[..., :3] = ramp(stops, np.clip(Y / H, 0, 1), pos) * np.ones((1, W, 1), np.float32)
    cv.img[..., 3] = 1.0
    # brushed strokes as wrapped elements
    for k in range(260):
        L = rng.uniform(300, 900)
        wd = rng.uniform(24, 70)
        y = rng.uniform(0, H)
        x = rng.uniform(0, W)
        col = jitter(ramp(stops, np.array([y / H]), pos)[0], rng, 1, dl=0.018, dc=0.1, dh=0.04)[0]
        seed = int(rng.integers(1 << 30))
        op = rng.uniform(0.25, 0.5)
        ew, eh = int(L + 2 * wd + 20), int(wd * 3 + 40)

        def fn(c, r, L=L, wd=wd, col=col, op=op, eh=eh):
            p = np.array([[wd + 10, eh / 2], [wd + 10 + L / 2, eh / 2 + r.normal(0, 5)], [wd + 10 + L, eh / 2]])
            stroke(c, p, taper(12, 0.35, 0.25, wd), col, opacity=op, edge=0.55, bristle=0.6, rag=0.25, spacing=6.0,
                   rng=r)
        paste_wrap(cv, element(seed, ew, eh, fn), int(x - ew / 2), int(y - eh / 2))
    # high clouds: a few strato forms and long lenses (slow layer)
    for (cx, by, w_, h_, kind) in [(500, 300, 820, 110, 'strato'), (1700, 220, 600, 90, 'strato'),
                                   (2700, 340, 900, 140, 'cumulus'), (3600, 200, 520, 80, 'strato')]:
        seed = int(rng.integers(1 << 30))
        ew, eh = int(w_ * 1.5 + 200), int(h_ * 3 + 200)

        def fn(c, r, w_=w_, h_=h_, kind=kind, ew=ew, eh=eh):
            plane_cloud(c, r, ew / 2, eh - 120, w_, h_, planes(0.3), kind=kind, light3=(0.6, -0.7, 0.3),
                        rim=C(255, 246, 214), wisps=0.6)
        paste_wrap(cv, element(seed, ew, eh, fn), int(cx - ew / 2), int(by - (eh - 120)))
    P.add('sky', 0.1, cv, 'gold sky with high clouds; tileable in x (scroll slowest)')

    # ---------------------------------------------------------------- cloud bank (medium)
    cv = P.layer('cloud_bank', 0.5)
    xs = np.arange(0, W, 330) + rng.normal(0, 60, len(np.arange(0, W, 330)))
    for cx in xs:
        w_ = rng.uniform(420, 900)
        h_ = rng.uniform(140, 280)
        by = rng.uniform(880, 960)
        kind = 'cumulus' if rng.random() < 0.7 else 'strato'
        seed = int(rng.integers(1 << 30))
        ew, eh = int(w_ * 1.5 + 200), int(h_ * 2.6 + 240)

        def fn(c, r, w_=w_, h_=h_, kind=kind, ew=ew, eh=eh):
            plane_cloud(c, r, ew / 2, eh - 140, w_, h_, planes(0.12), kind=kind, light3=(0.6, -0.7, 0.3),
                        rim=C(255, 246, 214), wisps=0.5)
        paste_wrap(cv, element(seed, ew, eh, fn), int(cx - ew / 2), int(by - (eh - 140)))
    # a continuous base under the bank so it reads as one sea of cloud
    base = element(int(rng.integers(1 << 30)), 10, 10, lambda c, r: None)
    yy = cv.ys()[:, None]
    k = smoothstep(900, 980, yy) * np.ones((1, W), np.float32)
    cv.img *= (1 - k[..., None])
    cv.img[..., :3] += k[..., None] * aerial(C(196, 150, 170), 0.15, HAZE)
    cv.img[..., 3:4] += k[..., None]
    P.add('cloud_bank', 0.5, cv, 'bank of sculpted cumulus along the bottom; tileable in x (scroll medium)')

    # ---------------------------------------------------------------- near wisps (fast)
    cv = P.layer('wisps', 1.0)
    for k in range(70):
        y = rng.uniform(80, H - 40)
        x = rng.uniform(0, W)
        L = rng.uniform(500, 1600)
        th = rng.uniform(16, 60)
        litk = float(np.clip(1.0 - y / H + rng.normal(0, 0.15), 0, 1))
        col = mix(C(226, 172, 176), C(255, 240, 212), litk)
        seed = int(rng.integers(1 << 30))
        ew, eh = int(L + 4 * th + 40), int(th * 4 + 60)

        def fn(c, r, L=L, th=th, col=col, eh=eh):
            n = 10
            t = np.linspace(0, 1, n)
            xs_ = 2 * th + 20 + t * L
            ys_ = eh / 2 + np.cumsum(r.normal(0, 2.5, n))
            prof = np.sin(np.pi * t) ** 0.8
            for j in range(4):
                cc = mix(col, C(255, 250, 232), j / 3 * 0.6)
                stroke(c, np.stack([xs_, ys_ + (j - 1.5) * th * 0.25], 1), th * (0.2 + 0.8 * prof) * r.uniform(0.5, 1.0),
                       jitter(cc, r, 1, dl=0.02)[0], opacity=r.uniform(0.18, 0.4), edge=0.85, bristle=0.7, rag=0.3,
                       spacing=8.0, rng=r)
        paste_wrap(cv, element(seed, ew, eh, fn), int(x - ew / 2), int(y - eh / 2))
    P.add('wisps', 1.0, cv, 'fast near cloud wisps (speed lines of vapour); tileable in x (scroll fastest)',
          grain_amt=0.0)

    # ---------------------------------------------------------------- screen-fixed sun glow (not tiled)
    gl = Canvas(1920, 1040, 0)
    glow(gl, 2050, -80, 900, C(255, 236, 186), 0.55)
    glow(gl, 2050, -80, 420, C(255, 250, 230), 0.5)
    save_rgba(os.path.join(outdir, '03_sun_glow.png'), gl.img)
    P.meta.append(dict(name='sun_glow', file='03_sun_glow.png', depth=0.0, size=[1920, 1040], offset=[0, 0],
                       blend='screen', coverage=1.0, note='SCREEN-FIXED overlay (do not scroll): the off-frame sun '
                                                       'at the upper right; use screen or add blending'))
    P.save(tileable_x=True, tile_width=W, scroll_note='scroll sky slowest, cloud_bank medium, wisps fastest; '
           'sun_glow fixed to the camera', sun='off-frame upper right')
    return P
