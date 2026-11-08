"""ground.py - forest floor: seamless ground tile, moss patches, grass/fern clumps,
wildflower clusters.

paint_ground_tile(cv, rng)      2048x2048 RGB, wrap canvas: moss, leaf litter, roots,
                                stones, tiny wildflowers.
paint_moss_patch(cv, rng, i)    RGBA soft-edged moss patch.
paint_grass_clump(cv, rng, i)   RGBA grass (i=1,3) or fern (i=2) clump, 512x512.
paint_flower(cv, rng, i)        RGBA wildflower cluster, 256x256.
"""
import numpy as np
from brush import (Canvas, col, mix, mix_many, shade, jitter, smooth_path, wobble, taper,
                   stroke, dabs, leaf_fans, dab_stroke, fbm, value_noise, smoothstep)

LIGHT = (0.62, -0.78)

MOSS_DARK = col(44, 72, 42)
MOSS_MID = col(84, 118, 54)
MOSS_LIT = col(138, 160, 70)
SOIL_DARK = col(58, 44, 40)
SOIL_MID = col(96, 74, 56)
LITTER = [col(132, 96, 52), col(108, 72, 44), col(150, 112, 60), col(90, 64, 50),
          col(168, 128, 70), col(120, 86, 60)]
STONE_DARK = col(78, 76, 86)
STONE_MID = col(118, 116, 118)
STONE_LIT = col(170, 164, 150)
FLOWER_COLS = [col(246, 240, 226), col(244, 226, 150), col(206, 186, 226), col(236, 232, 240)]


def _stones(cv, rng, xs, ys, sizes, moss=True):
    """Rounded stones: shadow under, body, lit top-right, optional moss on top."""
    n = len(xs)
    # cast shadow (down-left of the light)
    dabs(cv, xs - sizes * 0.15, ys + sizes * 0.22, sizes * 1.1, jitter(SOIL_DARK, rng, n, dl=0.02),
         aspect=0.5, angle=0.0, rng=rng, edge=0.5, rag=0.3, bristle=0.2, opacity=0.8)
    body = jitter(mix(STONE_MID, STONE_DARK, rng.uniform(0.1, 0.6, n)[:, None]), rng,
                  dl=0.03, dc=0.2, dh=0.2)
    ang = rng.normal(0, 0.3, n)
    dabs(cv, xs, ys, sizes, body, aspect=rng.uniform(0.6, 0.85, n), angle=ang, rng=rng,
         edge=0.15, rag=0.25, bristle=0.15)
    lit = jitter(mix(STONE_LIT, STONE_MID, rng.uniform(0.0, 0.5, n)[:, None]), rng, dl=0.03, dc=0.2)
    dabs(cv, xs + sizes * 0.12, ys - sizes * 0.14, sizes * 0.55, lit, aspect=0.55, angle=ang,
         rng=rng, edge=0.3, rag=0.3, bristle=0.4, opacity=0.9)
    if moss:
        sel = rng.random(n) < 0.5
        m = int(sel.sum())
        if m:
            dabs(cv, xs[sel] - sizes[sel] * 0.1, ys[sel] - sizes[sel] * 0.2, sizes[sel] * 0.4,
                 jitter(MOSS_MID, rng, m, dl=0.03), aspect=0.6, rng=rng, edge=0.5, rag=0.5,
                 bristle=0.4, opacity=0.85)


def _flowers(cv, rng, xs, ys, size, cols=None):
    """Tiny flower heads: a dark centre dot under 4-6 petal dabs, a pale centre."""
    n = len(xs)
    if n == 0:
        return
    if cols is None:
        cols = np.stack([FLOWER_COLS[i] for i in rng.integers(0, len(FLOWER_COLS), n)])
    npet = 5
    rep = np.repeat(np.arange(n), npet)
    ang = np.tile(np.linspace(0, 2 * np.pi, npet, endpoint=False), n) + rng.normal(0, 0.2, n * npet)
    s = np.repeat(size, npet) if np.ndim(size) else np.full(n * npet, size, np.float32)
    px = xs[rep] + np.cos(ang) * s * 0.28
    py = ys[rep] + np.sin(ang) * s * 0.28
    pc = jitter(cols[rep], rng, dl=0.03, dc=0.15)
    # shadowed petals on the lower-left
    shadow = np.clip(-(np.cos(ang) * LIGHT[0] + np.sin(ang) * LIGHT[1]), 0, 1)
    pc = mix(pc, shade(pc, dl=-0.12, dc=1.2), shadow[:, None] * 0.5)
    dabs(cv, px, py, s * 0.5, pc, aspect=0.75, angle=ang, rng=rng, edge=0.3, rag=0.3, bristle=0.15)
    cen = jitter(col(220, 180, 90), rng, n, dl=0.05)
    dabs(cv, xs, ys, np.broadcast_to(size, (n,)) * 0.22, cen, aspect=0.9, rng=rng, edge=0.4, rag=0.3)


def paint_ground_tile(cv, rng):
    W, H = cv.w, cv.h
    cv.wrap = True
    # 1. base: dark soil with soft colour drift, then moss in soft big dabs
    big = fbm(H, W, 700, rng, octaves=3, tile=True)
    cv.img[..., :3] = mix(SOIL_DARK, mix(MOSS_DARK, SOIL_MID, 0.5), big[..., None])
    cv.img[..., 3] = 1
    n = 2600
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    k = big[ys.astype(int) % H, xs.astype(int) % W]
    t = np.clip(k * 0.8 + rng.normal(0, 0.15, n), 0, 1)
    cols = jitter(mix_many([MOSS_DARK, MOSS_MID, mix(MOSS_MID, SOIL_MID, 0.4)], t), rng,
                  dl=0.02, dc=0.1, dh=0.08)
    dabs(cv, xs, ys, rng.uniform(90, 190, n), cols, aspect=rng.uniform(0.5, 0.8, n), rng=rng,
         edge=0.45, rag=0.4, bristle=0.5, opacity=rng.uniform(0.6, 0.95, n))
    # moss texture: many small dabs, lit ones toward the upper-right of lumps
    n = 14000
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    k = big[ys.astype(int) % H, xs.astype(int) % W]
    fine = fbm(H, W, 160, rng, octaves=3, tile=True)
    f = fine[ys.astype(int) % H, xs.astype(int) % W]
    t = np.clip(0.2 + 0.5 * k + 0.6 * (f - 0.5) + rng.normal(0, 0.12, n), 0, 1)
    cols = jitter(mix_many([MOSS_DARK, MOSS_MID, MOSS_LIT], t), rng, dl=0.02, dc=0.1, dh=0.1)
    dabs(cv, xs, ys, rng.uniform(14, 34, n), cols, aspect=rng.uniform(0.55, 0.9, n), rng=rng,
         edge=0.3, rag=0.5, bristle=0.4, opacity=rng.uniform(0.7, 1.0, n))
    # 2. roots crossing the tile (tile-safe strokes)
    for _ in range(5):
        p0 = np.array([rng.uniform(0, W), rng.uniform(0, H)])
        ang = rng.uniform(0, 2 * np.pi)
        L = rng.uniform(0.5, 1.1) * W
        pts = [p0]
        a = ang
        for i in range(10):
            a += rng.normal(0, 0.25)
            pts.append(pts[-1] + (L / 10) * np.array([np.cos(a), np.sin(a)]))
        pts = smooth_path(np.array(pts), 60)
        w = rng.uniform(22, 48) * (0.6 + 0.4 * np.sin(np.linspace(0.3, 2.8, 60)))
        stroke(cv, pts, w, mix(SOIL_MID, col(110, 90, 70), 0.5), color_lit=col(150, 126, 96),
               color_dark=SOIL_DARK, light=LIGHT, edge=0.15, bristle=0.3, rag=0.2, rng=rng, core=0.4)
        # shadow on the ground along the root's lower-left side
        stroke(cv, pts + [-8, 12], w * 0.8, SOIL_DARK, opacity=0.35, edge=0.8, bristle=0.3, rng=rng)
        # moss creeping on the root
        m = 40
        s = rng.uniform(0, 1, m)
        idx = (s * 59).astype(int)
        dabs(cv, pts[idx, 0] + rng.normal(0, 6, m), pts[idx, 1] + rng.normal(0, 6, m),
             rng.uniform(10, 22, m), jitter(MOSS_MID, rng, m, dl=0.04), aspect=0.7, rng=rng,
             edge=0.5, rag=0.5, opacity=0.8)
    # 3. leaf litter: elongated small dabs with a dark offset shadow
    n = 2200
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    sz = rng.uniform(16, 40, n)
    ang = rng.uniform(0, np.pi, n)
    cols = np.stack([LITTER[i] for i in rng.integers(0, len(LITTER), n)])
    cols = jitter(cols, rng, dl=0.04, dc=0.15, dh=0.1)
    dabs(cv, xs - 3, ys + 4, sz, jitter(SOIL_DARK, rng, n, dl=0.02), aspect=0.45, angle=ang,
         rng=rng, edge=0.4, rag=0.3, opacity=0.7)
    dabs(cv, xs, ys, sz, cols, aspect=rng.uniform(0.35, 0.55, n), angle=ang, rng=rng,
         edge=0.18, rag=0.35, bristle=0.3)
    # lighter edge on the lit side of some leaves
    sel = rng.random(n) < 0.4
    m = int(sel.sum())
    dabs(cv, xs[sel] + 3, ys[sel] - 3, sz[sel] * 0.6, shade(cols[sel], dl=0.1), aspect=0.3,
         angle=ang[sel], rng=rng, edge=0.3, rag=0.3, opacity=0.8)
    # 4. stones
    n = 70
    _stones(cv, rng, rng.uniform(0, W, n), rng.uniform(0, H, n), rng.uniform(24, 70, n))
    # 5. small grass tufts
    n = 320
    xs, ys = rng.uniform(0, W, n), rng.uniform(0, H, n)
    cols = jitter(mix(MOSS_MID, MOSS_LIT, rng.uniform(0.2, 0.9, n)[:, None]), rng, dl=0.03, dc=0.1, dh=0.08)
    leaf_fans(cv, xs, ys, rng.uniform(30, 60, n), cols, rng, n_leaves=5, spread=1.6,
              direction=np.full(n, -np.pi / 2) + rng.normal(0, 0.3, n), aspect=0.18, rag=0.2,
              bristle=0.4, edge=0.25)
    # 6. wildflowers in small groups
    ng = 36
    gx, gy = rng.uniform(0, W, ng), rng.uniform(0, H, ng)
    gc = rng.integers(0, len(FLOWER_COLS), ng)
    cnt = rng.integers(3, 8, ng)
    rep = np.repeat(np.arange(ng), cnt)
    fx = gx[rep] + rng.normal(0, 28, len(rep))
    fy = gy[rep] + rng.normal(0, 22, len(rep))
    # leaves under the flowers
    leaf_fans(cv, fx, fy + 6, 22, jitter(MOSS_MID, rng, len(rep), dl=0.03), rng, n_leaves=3,
              spread=1.5, direction=rng.uniform(0, 2 * np.pi, len(rep)), aspect=0.5, rag=0.3)
    _flowers(cv, rng, fx, fy, rng.uniform(14, 22, len(rep)),
             cols=np.stack([FLOWER_COLS[i] for i in gc[rep]]))
    cv.wrap = False


def paint_moss_patch(cv, rng, i):
    """Soft-edged moss patch, RGBA: velvety mounds built from thousands of tiny
    soft dabs; each mound is lit on its upper-right, the patch thins outward."""
    W, H = cv.w, cv.h
    cx, cy = W / 2, H / 2
    nphi = 64
    phi = np.linspace(0, 2 * np.pi, nphi, endpoint=False)
    rad = 1 + 0.22 * np.cos(phi * 3 + rng.uniform(0, 6)) + 0.1 * np.cos(phi * 7 + rng.uniform(0, 6))
    R = W * 0.36
    pals = [[MOSS_DARK, MOSS_MID, MOSS_LIT],
            [shade(MOSS_DARK, dh=0.2), shade(MOSS_MID, dh=0.15, dc=0.9), shade(MOSS_LIT, dh=0.1)],
            [mix(MOSS_DARK, SOIL_DARK, 0.3), shade(MOSS_MID, dh=-0.1), shade(MOSS_LIT, dh=-0.15, dl=0.03)]]
    ramp = pals[(i - 1) % 3]
    # mounds
    nm = int(rng.integers(4, 8))
    mx = cx + rng.normal(0, R * 0.4, nm)
    my = cy + rng.normal(0, R * 0.3, nm)
    mr = R * rng.uniform(0.3, 0.55, nm)
    n = 26000
    u = rng.random(n)
    ang = rng.uniform(0, 2 * np.pi, n)
    rr = np.sqrt(u) * 1.12
    idx = ((ang / (2 * np.pi) * nphi) % nphi).astype(int)
    k = rr / rad[idx]
    xs = cx + np.cos(ang) * rr * R
    ys = cy + np.sin(ang) * rr * R * 0.8
    keep = (k < 1.0) & (rng.random(n) < smoothstep(1.0, 0.6, k) + 0.12)
    xs, ys, k = xs[keep], ys[keep], k[keep]
    m = len(xs)
    # height field from the mounds -> lit value from its gradient toward the sun
    dx = (xs[:, None] - mx[None, :]) / mr[None, :]
    dy = (ys[:, None] - my[None, :]) / mr[None, :]
    hgt = np.exp(-(dx * dx + dy * dy) * 1.6)
    gxs = np.sum(-2 * 1.6 * dx * hgt / mr[None, :], 1)
    gys = np.sum(-2 * 1.6 * dy * hgt / mr[None, :], 1)
    hsum = hgt.sum(1)
    slope = (gxs * LIGHT[0] + gys * LIGHT[1]) * R * 0.3
    t = np.clip(0.35 + 0.15 * hsum + slope + rng.normal(0, 0.12, m), 0, 0.9)
    cols = jitter(mix_many(ramp, t), rng, dl=0.02, dc=0.1, dh=0.08)
    op = smoothstep(1.05, 0.65, k) * 0.9 + 0.1
    order = np.argsort(t)                       # dark first, lit dabs on top
    dabs(cv, xs[order], ys[order], W * rng.uniform(0.006, 0.016, m), cols[order],
         aspect=rng.uniform(0.6, 1.0, m), rng=rng, edge=0.5, rag=0.4, bristle=0.3, opacity=op[order])
    # sparse tiny sprouts and specks for texture
    sel = rng.random(m) < 0.05
    q = int(sel.sum())
    dabs(cv, xs[sel] + rng.normal(0, 2, q), ys[sel] - 3, W * rng.uniform(0.005, 0.009, q),
         shade(cols[sel], dl=0.1, dh=-0.08), aspect=0.45, angle=-np.pi / 2 + rng.normal(0, 0.5, q),
         rng=rng, edge=0.4, rag=0.3, opacity=0.9)


def paint_grass_clump(cv, rng, i):
    """Grass (i odd) or fern (i even) clump from the bottom centre, RGBA 512x512."""
    W, H = cv.w, cv.h
    bx, by = W / 2, H * 0.96
    if i % 2 == 1:
        nb = int(rng.integers(26, 40))
        angs = np.sort(rng.uniform(-1.25, 1.25, nb))
        order = np.argsort(np.abs(angs))[::-1]       # outer blades first, centre ones on top
        for j in order:
            a = angs[j]
            L = H * rng.uniform(0.45, 0.9) * (1 - 0.3 * abs(a) / 1.25)
            curl = a * rng.uniform(0.6, 1.1)
            pts = [np.array([bx + rng.normal(0, W * 0.02), by])]
            ang = -np.pi / 2 + a * 0.35
            for k in range(8):
                ang += curl / 8 + rng.normal(0, 0.05)
                pts.append(pts[-1] + (L / 8) * np.array([np.cos(ang), np.sin(ang)]))
            pts = smooth_path(np.array(pts), 40)
            lit = np.clip(0.5 + 0.5 * np.sin(a) * LIGHT[0] * 2 + rng.normal(0, 0.15), 0, 1)
            c = jitter(mix_many([MOSS_DARK, MOSS_MID, MOSS_LIT], 0.25 + 0.7 * lit), rng, 1, dl=0.03, dh=0.1)[0]
            stroke(cv, pts, taper(40, 0.9, 0.0, W * rng.uniform(0.018, 0.03)), c, edge=0.25,
                   bristle=0.3, rag=0.15, rng=rng)
    else:
        # fern: fronds with paired leaflets
        nf = int(rng.integers(5, 8))
        angs = np.sort(rng.uniform(-1.3, 1.3, nf))
        for j in np.argsort(np.abs(angs))[::-1]:
            a = angs[j]
            L = H * rng.uniform(0.5, 0.85) * (1 - 0.25 * abs(a) / 1.3)
            pts = [np.array([bx, by])]
            ang = -np.pi / 2 + a * 0.5
            for k in range(8):
                ang += a * 0.09 + rng.normal(0, 0.04)
                pts.append(pts[-1] + (L / 8) * np.array([np.cos(ang), np.sin(ang)]))
            pts = smooth_path(np.array(pts), 40)
            lit = np.clip(0.5 + np.sin(a) * 0.5 + rng.normal(0, 0.1), 0, 1)
            base_c = mix_many([MOSS_DARK, MOSS_MID, MOSS_LIT], 0.2 + 0.6 * lit)
            stroke(cv, pts, taper(40, 1.0, 0.1, W * 0.012), mix(base_c, SOIL_DARK, 0.4), edge=0.3,
                   bristle=0.3, rng=rng)
            # leaflets: pairs along the frond, shrinking to the tip
            m = 14
            s = np.linspace(0.12, 0.97, m)
            idx = (s * 39).astype(int)
            d = np.gradient(pts, axis=0)
            dirs = np.arctan2(d[idx, 1], d[idx, 0])
            for side in (-1, 1):
                la = dirs + side * rng.uniform(1.0, 1.3, m)
                Ls = W * 0.11 * (1 - s) ** 0.7 * rng.uniform(0.85, 1.15, m) + 4
                cols = jitter(mix(base_c, MOSS_LIT, np.clip(s + rng.normal(0, 0.2, m), 0, 1)[:, None] * 0.5),
                              rng, dl=0.03, dc=0.1, dh=0.08)
                dabs(cv, pts[idx, 0] + np.cos(la) * Ls * 0.45, pts[idx, 1] + np.sin(la) * Ls * 0.45,
                     Ls, cols, aspect=0.32, angle=la, rng=rng, edge=0.25, rag=0.3, bristle=0.3)


def paint_flower(cv, rng, i):
    """Small wildflower cluster, RGBA 256x256: stems, leaves, 4-8 heads."""
    W, H = cv.w, cv.h
    bx, by = W / 2, H * 0.95
    nh = int(rng.integers(4, 9))
    colour = FLOWER_COLS[(i - 1) % len(FLOWER_COLS)]
    heads = []
    for j in range(nh):
        a = rng.uniform(-0.9, 0.9)
        L = H * rng.uniform(0.4, 0.75)
        top = np.array([bx + np.sin(a) * L * 0.8, by - np.cos(a) * L])
        pts = smooth_path([np.array([bx + a * 10, by]), (np.array([bx, by]) + top) / 2 + [a * 12, 0], top], 20)
        stroke(cv, pts, taper(20, 1.0, 0.5, W * 0.012), mix(MOSS_MID, MOSS_DARK, 0.4), edge=0.3,
               bristle=0.3, rng=rng)
        heads.append(top)
        # a leaf or two on the stem
        if rng.random() < 0.7:
            k = int(rng.integers(5, 14))
            la = -np.pi / 2 + rng.choice([-1, 1]) * rng.uniform(0.7, 1.2)
            Ls = W * rng.uniform(0.1, 0.16)
            dabs(cv, pts[k, 0] + np.cos(la) * Ls * 0.45, pts[k, 1] + np.sin(la) * Ls * 0.45, Ls,
                 jitter(MOSS_MID, rng, 1, dl=0.04)[0], aspect=0.38, angle=la, rng=rng, edge=0.25, rag=0.3)
    heads = np.array(heads)
    _flowers(cv, rng, heads[:, 0], heads[:, 1], W * rng.uniform(0.16, 0.24, nh),
             cols=np.broadcast_to(colour, (nh, 3)).copy())
