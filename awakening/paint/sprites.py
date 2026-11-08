"""sprites.py - small RGBA sprites: single leaves and cel-style dust puffs.

paint_leaf(cv, rng, i)   256x256 leaf; i selects the shape family:
                         1,4 broadleaf, 2,5 maple-like, 3,6 elongated.
paint_dust(cv, rng, i)   512x512 soil/dust puff: overlapping rounded lumps with a
                         darker underside, like anime smoke.
"""
import numpy as np
import cv2
from brush import (Canvas, col, mix, mix_many, shade, jitter, smooth_path, wobble, taper,
                   stroke, dabs, smoothstep, noise1d)

LIGHT = (0.62, -0.78)

LEAF_PALS = [((84, 112, 52), (44, 70, 46), (170, 176, 84)),      # green
             ((150, 110, 48), (96, 62, 40), (214, 176, 92)),     # ochre/autumn
             ((108, 124, 54), (58, 78, 50), (186, 184, 96)),     # yellow-green
             ((120, 84, 50), (72, 50, 44), (190, 146, 94)),      # brown
             ((96, 118, 60), (50, 76, 56), (178, 180, 96)),
             ((160, 96, 52), (100, 56, 44), (222, 164, 100))]    # rust


def leaf_outline(kind, rng, n=180):
    """Leaf outline in a unit frame: returns (n,2) points, midrib from (0,-1) tip
    to (0, 1) stem, width about 1."""
    t = np.linspace(0, 1, n)                       # 0 = tip, 1 = stem
    if kind == 'broad':
        w = np.sin(np.pi * t ** 0.85) ** 0.9 * 0.55
        w *= 1 + 0.06 * np.sin(t * 40 + rng.uniform(0, 6))      # slightly wavy margin
    elif kind == 'long':
        w = np.sin(np.pi * t ** 0.9) ** 1.4 * 0.26
    else:                                          # maple-like: lobed
        lobes = 5
        base = np.sin(np.pi * t ** 0.8) ** 0.8 * 0.55
        phase = np.clip((t - 0.05) / 0.75, 0, 1)
        w = base * (0.55 + 0.45 * np.abs(np.cos(phase * np.pi * lobes / 2)) ** 0.6)
        w = np.where(t > 0.85, base * 0.8, w)
    y = -1 + 2 * t
    left = np.stack([-w, y], 1)
    right = np.stack([w, y], 1)[::-1]
    return np.vstack([left, right])


def paint_leaf(cv, rng, i):
    W, H = cv.w, cv.h
    kind = ['broad', 'maple', 'long'][(i - 1) % 3]
    midc, darkc, litc = (col(*c) for c in LEAF_PALS[(i - 1) % len(LEAF_PALS)])
    midc = shade(midc, dh=rng.uniform(-0.1, 0.1))
    S = W * 0.42
    ang = rng.uniform(-0.5, 0.5)
    ca, sa = np.cos(ang), np.sin(ang)

    def tx(p):
        p = np.asarray(p, np.float32) * S
        return np.stack([W / 2 + p[..., 0] * ca - p[..., 1] * sa,
                         H / 2 + p[..., 0] * sa + p[..., 1] * ca], -1)

    out = leaf_outline(kind, rng)
    # mask from the outline, slightly roughened
    mask = np.zeros((H, W), np.float32)
    poly = tx(out).astype(np.int32)
    cv2.fillPoly(mask, [poly], 1.0)
    # paint: fill the mask with short strokes running from the midrib outward
    # (dark half on the left of the midrib, lit edge on the right / sun side)
    n = 900
    t = rng.uniform(0.02, 0.98, n)
    side = rng.choice([-1, 1], n)
    u = rng.uniform(0.0, 1.0, n) ** 0.8
    # width of the outline at t: sample
    idx = (t * (len(out) // 2 - 1)).astype(int)
    wt = -out[idx, 0]
    px = side * u * wt
    py = -1 + 2 * t
    pts = tx(np.stack([px, py], 1))
    # value: left half darker, lit toward the right margin, darker near the midrib base
    v = np.clip(0.5 + 0.5 * side * u + rng.normal(0, 0.12, n), 0, 1)
    v = v * (0.8 + 0.2 * (1 - t))
    cols = jitter(mix_many([darkc, midc, litc], v), rng, dl=0.02, dc=0.1, dh=0.06)
    # stroke direction: veins run from midrib toward the margin, tilted to the tip
    dirs = ang + side * rng.uniform(0.5, 0.9, n) - np.pi / 2 + np.pi / 2
    dirs = np.where(side > 0, ang - 0.6 + rng.normal(0, 0.15, n), ang + 0.6 + np.pi + rng.normal(0, 0.15, n))
    sz = S * rng.uniform(0.12, 0.26, n)
    tmp = Canvas(W, H)
    dabs(tmp, pts[:, 0], pts[:, 1], sz, cols, aspect=0.35, angle=dirs, rng=rng, edge=0.3, rag=0.3, bristle=0.4)
    # clip to the (softened) mask, then paint margin strokes along the outline
    m = cv2.GaussianBlur(mask, (0, 0), 1.2)
    tmp.img *= m[..., None]
    cv.composite(tmp)
    # underlying flat fill so no holes remain inside
    fill = Canvas(W, H)
    fill.fill_mask(mask, mix(darkc, midc, 0.5))
    fill.img *= (1 - cv.img[..., 3:4])
    cv.img += fill.img
    # margin: dabs following the outline, lit colour on the sun side, dark elsewhere
    m2 = len(out)
    sel = np.arange(0, m2, 3)
    op = out[sel]
    lit = np.clip(op[:, 0] * LIGHT[0] * 1.6 - op[:, 1] * 0.3 + 0.4, 0, 1)
    cols = jitter(mix_many([darkc, midc, litc], lit), rng, dl=0.03, dc=0.1)
    d = np.gradient(out, axis=0)[sel]
    a = np.arctan2(d[:, 1], d[:, 0]) + ang
    q = tx(op * 0.97)
    dabs(cv, q[:, 0], q[:, 1], S * 0.11, cols, aspect=0.4, angle=a, rng=rng, edge=0.3, rag=0.35, bristle=0.3)
    # midrib and a few side veins
    rib = tx(np.stack([np.zeros(30), np.linspace(-0.95, 1.0, 30)], 1))
    stroke(cv, rib, taper(30, 0.3, 1.0, S * 0.045), mix(darkc, litc, 0.55), edge=0.35, bristle=0.4, rng=rng, opacity=0.9)
    for k in range(5):
        tt = 0.2 + 0.14 * k
        for sd in (-1, 1):
            vpts = tx(np.stack([[0, sd * 0.45 * wt.max() * 0.9], [-1 + 2 * tt, -1 + 2 * tt - 0.25]], 1))
            stroke(cv, vpts, taper(2, 1.0, 0.3, S * 0.02), mix(midc, litc, 0.5), edge=0.4, opacity=0.55, rng=rng)
    # stem
    stem = tx(np.array([[0, 0.98], [rng.uniform(-0.1, 0.1), 1.18]]))
    stroke(cv, stem, S * 0.04, mix(darkc, col(120, 90, 60), 0.5), edge=0.3, rng=rng)


def paint_dust(cv, rng, i):
    """Anime-style dust puff: cluster of rounded lumps, flat warm grey-beige with a
    crisp darker underside crescent and a lighter top on every lump."""
    W, H = cv.w, cv.h
    base = col(178, 164, 142) if i == 1 else col(168, 158, 146)
    dark = shade(base, dl=-0.16, dc=1.15, dh=0.2)
    lit = shade(base, dl=0.1, dc=0.8, dh=-0.1)
    cx, cy = W / 2, H * 0.55
    nl = int(rng.integers(6, 10))
    lumps = []
    for k in range(nl):
        a = rng.uniform(0, 2 * np.pi)
        d = rng.uniform(0, 0.2) * W
        r = W * rng.uniform(0.1, 0.19) * (1 - d / (0.3 * W) * 0.4)
        lumps.append((cx + np.cos(a) * d, cy + np.sin(a) * d * 0.6, r))
    lumps.sort(key=lambda l: -l[1])           # lower lumps first (back), upper on top
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for (x, y, r) in lumps:
        nphi = 48
        phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
        rad = r * (1 + 0.09 * np.cos(phi * 3 + rng.uniform(0, 6)) + 0.05 * np.cos(phi * 6 + rng.uniform(0, 6)))
        poly = np.stack([x + np.cos(phi) * rad, y + np.sin(phi) * rad * 0.88], 1)
        mask = np.zeros((H, W), np.float32)
        cv2.fillPoly(mask, [poly.astype(np.int32)], 1.0)
        mask = cv2.GaussianBlur(mask, (0, 0), 0.8)
        body = Canvas(W, H)
        bc = jitter(base, rng, 1, dl=0.02, dc=0.1)[0]
        body.fill_mask(mask, bc)
        nx, ny = (xx - x) / r, (yy - y) / (r * 0.88)
        # crisp shadow crescent: lower-left, hugging the edge
        rr = np.hypot(nx, ny)
        lighting = -(nx * LIGHT[0] + ny * LIGHT[1])           # 1 away from the light
        term = smoothstep(0.08, 0.22, lighting * 0.6 + rr * rr * 0.55 - 0.25)
        body.tint(dark, term * 0.95 * mask)
        # lighter cap toward the light
        cap = smoothstep(0.55, 0.9, (nx * LIGHT[0] + ny * LIGHT[1]) * 0.6 + (1 - rr) * 0.6) * (1 - term)
        body.tint(lit, cap * 0.85 * mask)
        # outline: thin darker rim where the lump overlaps the ones behind
        rim = mask - cv2.erode(mask, np.ones((5, 5), np.uint8))
        body.tint(shade(bc, dl=-0.08), np.clip(rim, 0, 1) * 0.5 * (cv.img[..., 3] > 0.5))
        cv.composite(body)
    # ragged dabs around the upper edges in the body colour (brushy, not vector)
    for (x, y, r) in lumps:
        n = 12
        a = rng.uniform(-np.pi, 0.2, n)
        q = np.stack([x + np.cos(a) * r * 1.02, y + np.sin(a) * r * 0.9], 1)
        dabs(cv, q[:, 0], q[:, 1], r * rng.uniform(0.16, 0.26, n), jitter(base, rng, n, dl=0.02),
             aspect=0.75, rng=rng, edge=0.3, rag=0.4, bristle=0.2, opacity=0.9)
    # detached specks drifting away
    n = 12
    a = rng.uniform(0, 2 * np.pi, n)
    d = rng.uniform(0.3, 0.46, n) * W
    dabs(cv, cx + np.cos(a) * d, cy + np.sin(a) * d * 0.7, rng.uniform(10, 28, n),
         jitter(base, rng, n, dl=0.03), aspect=0.8, rng=rng, edge=0.35, rag=0.4, opacity=0.85)
