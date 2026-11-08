"""sky.py - dawn sky, 4096x2048 RGB.

paint_sky(cv, rng)  Oklab gradient (deep violet-blue -> dusty rose -> golden peach at
                    the horizon) with streaky horizontal brush texture, a few long
                    cloud wisps lit from below, and a warm glow around the sun side.
"""
import numpy as np
import cv2
from brush import (Canvas, col, mix, mix_many, shade, jitter, smooth_path, wobble, taper,
                   stroke, dabs, smoothstep, noise1d, value_noise, fbm)

LIGHT = (0.62, -0.78)

STOPS = [col(44, 40, 92), col(78, 64, 120), col(128, 96, 142), col(182, 136, 152),
         col(222, 170, 150), col(246, 196, 146), col(255, 220, 166), col(255, 232, 196)]
# gradient coordinate: 0 at the top, 1 at the bottom of the canvas; the horizon
# (brightest) is at ~0.82; below it we stay in the pale warm mist colour.


def paint_sky(cv, rng):
    W, H = cv.w, cv.h
    hz = 0.82
    yy = np.linspace(0, 1, H).astype(np.float32)
    t = np.clip(yy / hz, 0, 1) ** 0.85
    # streaky horizontal variation of the gradient coordinate (brushed look)
    streak = (value_noise(H, 1, 90, rng)[:, 0] - 0.5) * 0.06
    streak += (value_noise(H, 1, 400, rng)[:, 0] - 0.5) * 0.03
    cv.fill_vgradient(STOPS, 0, H, noise=np.interp(np.linspace(0, 1, H), np.linspace(0, 1, H),
                                                   streak) * (t ** 0.5))
    # recompute with the horizon warp: rows below the horizon keep the last stops
    # (fill_vgradient covered 0..1 over the whole height, so pull the lower part)
    cols = mix_many(STOPS, np.clip(t + streak * np.sqrt(t), 0, 1))
    cv.img[..., :3] = cols[:, None, :]
    cv.img[..., 3] = 1
    # 2-D warmth: the sun is low on the upper right; a glow toward that corner
    xx = np.linspace(0, 1, W).astype(np.float32)
    gx = np.exp(-((xx[None, :] - 0.82) ** 2) / 0.18 - ((yy[:, None] - hz + 0.02) ** 2) / 0.05)
    cv.tint(col(255, 226, 176), gx * 0.55)
    gx2 = np.exp(-((xx[None, :] - 0.75) ** 2) / 0.6) * smoothstep(0.2, hz, yy)[:, None]
    cv.tint(col(250, 200, 160), gx2 * 0.18)
    # painted texture: long, thin horizontal strokes with low opacity
    n = 2600
    ys = rng.uniform(0, H, n) ** 1.0
    ys = (rng.beta(1.6, 1.2, n) * H).astype(np.float32)        # more strokes low
    xs = rng.uniform(-0.1, 1.1, n) * W
    L = rng.uniform(250, 1400, n) * (0.5 + 0.5 * (ys / H))
    wd = rng.uniform(18, 70, n)
    base = cv.img[np.clip(ys.astype(int), 0, H - 1), np.clip(xs.astype(int), 0, W - 1), :3]
    cols = jitter(base, rng, dl=0.022, dc=0.12, dh=0.08)
    for k in range(n):
        p0 = np.array([xs[k] - L[k] / 2, ys[k]])
        p1 = np.array([xs[k] + L[k] / 2, ys[k] + rng.normal(0, 8)])
        pts = smooth_path([p0, (p0 + p1) / 2 + [0, rng.normal(0, 10)], p1], 12)
        stroke(cv, pts, taper(12, 0.4, 0.3, wd[k]), cols[k], opacity=rng.uniform(0.12, 0.3),
               edge=0.6, bristle=0.7, rag=0.2, rng=rng)
    # cloud wisps: each cloud is a lens-shaped envelope whose thickness varies
    # along its length; it is filled with many thin horizontal dabs. Colour comes
    # from the height inside the lens: lavender-rose at the top, lavender-grey in
    # the core, warm gold along the underside (the sun is below the cloud).
    nw = int(rng.integers(5, 8))
    for k in range(nw):
        big = k < 2
        y0 = rng.uniform(0.28, 0.7) * H
        x0 = rng.uniform(0.0, 0.5) * W
        length = rng.uniform(0.3, 0.7 if big else 0.5) * W
        thick = rng.uniform(0.04, 0.085 if big else 0.06) * H * (0.6 + 0.6 * y0 / H)
        hy = y0 / H
        sky_here = mix_many(STOPS, np.clip(hy / hz, 0, 1))
        top_c = shade(mix(sky_here, col(234, 196, 196), 0.55), dl=0.05, dc=0.8)
        core_c = shade(mix(sky_here, col(150, 124, 160), 0.4), dl=-0.01, dc=0.85)
        under_c = mix(col(255, 216, 158), col(250, 184, 126), rng.uniform(0.2, 0.8))
        gold_c = col(255, 234, 180)
        # thickness profile along the lens
        ns = 400
        s = np.linspace(0, 1, ns)
        prof = np.sin(np.pi * s) ** 0.6 * (0.35 + 0.65 * noise1d(ns, int(3 + length / thick * 0.3), rng, periodic=False))
        prof *= 0.7 + 0.3 * noise1d(ns, 3, rng, periodic=False)
        centre = (noise1d(ns, 3, rng, periodic=False) - 0.5) * thick * 1.6 + s * thick * rng.uniform(-1.2, 1.2)
        n = int(length * thick / 180) + 200
        u = rng.random(n)
        i = (u * (ns - 1)).astype(int)
        v = rng.uniform(-1, 1, n)                       # -1 top .. 1 bottom of the lens
        th = thick * prof[i]
        xs = x0 + u * length + rng.normal(0, thick * 0.1, n)
        ys = y0 + centre[i] + v * th * 0.5
        keep = th > thick * 0.08
        xs, ys, v, th, u = xs[keep], ys[keep], v[keep], th[keep], u[keep]
        m = len(xs)
        # colour by height: top rose, core lavender-grey, underside gold
        t = (v + 1) / 2
        cols = mix_many([top_c, core_c, under_c, gold_c], np.clip(t * 1.05 + rng.normal(0, 0.06, m), 0, 1))
        cols = jitter(cols, rng, dl=0.012, dc=0.08, dh=0.04)
        # dab length follows the local thickness; thin ends get thin, streaky dabs
        L = th * rng.uniform(1.2, 3.0, m) + 8
        asp = np.clip(th / L * rng.uniform(0.5, 0.9, m), 0.08, 0.5)
        op = np.clip(0.35 + 0.65 * (th / thick), 0, 1) * rng.uniform(0.5, 1.0, m)
        order = np.argsort(np.abs(v))[::-1]            # edges first, core on top
        order = np.argsort(-t)                          # paint bottom (gold) first, then up
        # upper part first, so the gold underside ends on top of the body
        order = np.argsort(t)
        dabs(cv, xs[order], ys[order], L[order], cols[order], aspect=asp[order],
             angle=rng.normal(0, 0.05, m), rng=rng, edge=0.45, rag=0.3, bristle=0.5, opacity=op[order])
        # a few crisp bright gold touches on the lowest bumps
        low = (t > 0.8) & (th > thick * 0.5)
        q = int(low.sum() * 0.12)
        if q:
            sel = np.nonzero(low)[0][rng.permutation(int(low.sum()))[:q]]
            dabs(cv, xs[sel], ys[sel] + th[sel] * 0.1, th[sel] * 0.9 + 4, jitter(gold_c, rng, q, dl=0.01),
                 aspect=0.25, angle=0.0, rng=rng, edge=0.3, rag=0.3, bristle=0.4, opacity=0.85)
    # fine horizontal haze bands near the horizon
    for k in range(5):
        y = (hz - 0.02 - 0.05 * k * rng.uniform(0.7, 1.2)) * H
        pts = np.stack([np.linspace(-50, W + 50, 30), y + np.sin(np.linspace(0, 3, 30)) * 10], 1)
        stroke(cv, pts, rng.uniform(25, 60), col(255, 226, 186), opacity=0.14, edge=0.9, bristle=0.6, rng=rng)
