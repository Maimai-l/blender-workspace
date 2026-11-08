"""forest.py - far forest strips and the overhanging foreground canopy.

paint_far_strip(cv, rng, level)   4096x1024 band: rows of rounded canopies with a
                                   few tall silhouettes, misted by distance; the
                                   bottom edge is fully opaque.
paint_canopy_fg(cv, rng, variant)  2048x1024 backlit foliage hanging from the top
                                   edge with warm rim light on the sun side.
"""
import numpy as np
from brush import (Canvas, col, mix, mix_many, shade, jitter, atmos, smooth_path, wobble,
                   taper, stroke, dabs, clump, clump_cluster, leaf_fans, make_palette,
                   smoothstep, noise1d, MIST, MIST_COOL)

LIGHT = (0.62, -0.78)


def paint_far_strip(cv, rng, level):
    """level 1 = nearest, 3 = farthest (nearly mist-coloured)."""
    W, H = cv.w, cv.h
    depth = {1: 0.42, 2: 0.62, 3: 0.80}[level]
    cool = {1: 0.45, 2: 0.6, 3: 0.7}[level]
    detail = {1: 0.3, 2: 0.2, 3: 0.12}[level]
    pal = make_palette((26, 54, 66), (66, 106, 70), (150, 168, 76), (240, 212, 130),
                       depth=depth, cool=cool)
    mist = mix(MIST, MIST_COOL, cool * 0.35)
    base_top = {1: 0.42, 2: 0.47, 3: 0.52}[level] * H     # where the solid fill starts
    # 1. solid lower fill, fading into mist toward the bottom edge
    fill_c = mix(pal['shadow'], pal['mid'], 0.35)
    cv.fill_vgradient([fill_c, mix(fill_c, mist, 0.35), mix(fill_c, mist, 0.75)],
                      y0=int(base_top), y1=H)
    # 2. back row of canopies (lighter, smaller, higher), then the front row
    rows = [dict(y=base_top - 0.03 * H, r=0.12 * H, n=int(W / (0.13 * H)) + 2, bias=0.22, lit=0.5),
            dict(y=base_top + 0.08 * H, r=0.15 * H, n=int(W / (0.14 * H)) + 2, bias=0.0, lit=1.0)]
    for row in rows:
        xs = np.linspace(-row['r'], W + row['r'], row['n']) + rng.normal(0, row['r'] * 0.35, row['n'])
        for x in xs:
            r = row['r'] * rng.uniform(0.7, 1.25)
            y = row['y'] + rng.normal(0, row['r'] * 0.25)
            p = {k: atmos(v, 0.0) for k, v in pal.items()}
            dh = rng.uniform(-0.08, 0.08)
            p = {k: shade(v, dh=dh, dl=rng.uniform(-0.02, 0.02)) for k, v in p.items()}
            clump_cluster(cv, x, y, r, p, rng, n=3, spread=0.45, detail=detail,
                          lit_amount=row['lit'] * (0.7 - 0.3 * (level - 1)),
                          shadow_bias=row['bias'] + rng.uniform(-0.1, 0.1), flatten=0.8,
                          edge=0.35, rag=0.25, bristle=0.2, density=0.7)
    # a lower, darker third row so the texture runs down into the fill
    n3 = int(W / (0.16 * H)) + 2
    xs = np.linspace(0, W, n3) + rng.normal(0, 0.05 * H, n3)
    for x in xs:
        r = 0.14 * H * rng.uniform(0.8, 1.2)
        p = {k: shade(v, dh=rng.uniform(-0.06, 0.06)) for k, v in pal.items()}
        clump(cv, x, base_top + 0.26 * H + rng.normal(0, 0.03 * H), r, p, rng, detail=detail,
              lit_amount=0.25 * (3 - level) / 2, shadow_bias=-0.2, flatten=0.8, edge=0.35,
              rag=0.25, bristle=0.2, density=0.6)
    # 3. tall tree silhouettes sticking up: stacked shrinking clumps on a spire
    nt = int(rng.integers(4, 8))
    xs = rng.uniform(0.02, 0.98, nt) * W
    for x in xs:
        base_y = base_top + 0.02 * H
        lean = rng.normal(0, 0.06)
        if rng.random() < 0.55:
            # conifer-like spire: irregular side tufts shrinking upward
            h = rng.uniform(0.26, 0.4) * H
            r0 = h * rng.uniform(0.16, 0.22)
            h = min(h, base_y - 0.1 * H - r0 * 0.6)          # keep clear of the top edge
            k = int(7 + h / r0 * 1.5)
            for i in range(k):
                t = i / (k - 1)
                yy = base_y - t * h
                rr = r0 * (1 - 0.85 * t) ** 0.8 * rng.uniform(0.7, 1.3)
                xx = x + lean * t * h + rng.normal(0, r0 * 0.35 * (1 - t))
                p = {kk: shade(v, dh=rng.uniform(-0.05, 0.05)) for kk, v in pal.items()}
                clump(cv, xx, yy, max(rr, 6), p, rng, detail=detail,
                      lit_amount=0.5 * (1 - level * 0.2), shadow_bias=-0.05 + 0.1 * t,
                      flatten=0.7, edge=0.35, rag=0.25, bristle=0.2, density=0.6)
            c = mix(pal['shadow'], mist, 0.2)
            stroke(cv, np.array([[x, base_y + 0.1 * H], [x + lean * h * 0.3, base_y - 0.3 * h]]),
                   r0 * 0.1, c, opacity=0.8, edge=0.4, bristle=0.3, rng=rng)
        else:
            # broadleaf emergent: tall thin trunk with a rounded crown
            h = rng.uniform(0.2, 0.32) * H
            r0 = h * rng.uniform(0.32, 0.45)
            h = min(h, base_y - 0.1 * H - r0 * 1.9)          # crown clear of the top edge
            c = mix(pal['shadow'], mist, 0.15)
            stroke(cv, np.array([[x, base_y + 0.1 * H], [x + lean * h, base_y - h + r0 * 0.5]]),
                   r0 * 0.08, c, opacity=0.9, edge=0.3, bristle=0.3, rng=rng)
            p = {kk: shade(v, dh=rng.uniform(-0.05, 0.05)) for kk, v in pal.items()}
            clump_cluster(cv, x + lean * h, base_y - h, r0 * 1.25, p, rng, n=5, spread=0.7,
                          detail=detail, lit_amount=0.6 * (1 - level * 0.2), shadow_bias=0.05,
                          flatten=0.7, edge=0.35, rag=0.25, bristle=0.2, density=0.7)
    # 4. ground mist: the lowest part dissolves toward the mist colour
    yy = np.arange(H, dtype=np.float32) / H
    fade = smoothstep(0.62, 1.0, yy) ** 1.4 * 0.85
    cv.tint(mist, fade[:, None] * np.ones((1, W), np.float32))
    # 5. a touch of warm light haze from the sun side on the canopy tops
    haze = np.clip((np.arange(W, dtype=np.float32) / W - 0.3) / 0.7, 0, 1)[None, :] * \
        np.clip(1 - np.abs(yy[:, None] - base_top / H) / 0.25, 0, 1)
    cv.tint(mix(MIST, pal['tip'], 0.3), haze * 0.12 * (level - 1))


def paint_canopy_fg(cv, rng, variant):
    """Overhanging foliage seen from below, hanging from the top edge."""
    W, H = cv.w, cv.h
    pal = make_palette((24, 50, 58), (44, 84, 72), (92, 124, 66), (238, 206, 128))
    if variant == 2:
        pal = make_palette((24, 46, 62), (42, 80, 78), (88, 118, 74), (242, 212, 138))
    rim_c = col(246, 214, 140)
    bark_dark, bark_mid = col(36, 30, 38), col(70, 58, 56)
    # branches from the upper corners sweeping across
    nb = int(rng.integers(2, 4))
    branches = []
    for i in range(nb):
        side = -1 if (i % 2 == 0) else 1
        x0 = W * (0.1 + 0.15 * rng.random()) if side < 0 else W * (0.75 + 0.15 * rng.random())
        p0 = np.array([x0, -0.02 * H])
        L = W * rng.uniform(0.35, 0.6)
        ang = np.pi / 2 - side * rng.uniform(0.9, 1.3)          # down and inward
        pts = [p0]
        a = ang
        for k in range(8):
            a += rng.normal(0, 0.12) + 0.03 * side              # droop slightly
            pts.append(pts[-1] + (L / 8) * np.array([np.cos(a), np.sin(a)]))
        pts = np.array(pts)
        pts = pts[pts[:, 1] < H * 0.9]
        if len(pts) < 3:
            continue
        w = W * rng.uniform(0.02, 0.03) * (1 - 0.6 * np.linspace(0, 1, len(pts)))
        branches.append((pts, w))
        # sub twigs
        for _ in range(3):
            m = int(rng.integers(1, len(pts) - 1))
            a2 = np.arctan2(*(pts[m + 1] - pts[m - 1])[::-1]) + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2)
            L2 = L * rng.uniform(0.2, 0.4)
            q = [pts[m]]
            for k in range(5):
                a2 += rng.normal(0, 0.15) + 0.08
                q.append(q[-1] + (L2 / 5) * np.array([np.cos(a2), np.sin(a2)]))
            q = np.array(q)
            branches.append((q, w[m] * 0.5 * (1 - 0.6 * np.linspace(0, 1, 6))))
    # solid dark band along the top edge so the card joins the frame edge
    band = smoothstep(0.07, 0.0, np.linspace(0, 1, H))[:, None] * np.ones((1, W), np.float32)
    cv.fill_mask(band, pal['shadow'])
    # back layer of foliage along the top edge (very dark, soft)
    n = int(W / 110) + 4
    xs = np.linspace(0, W, n) + rng.normal(0, 40, n)
    for x in xs:
        r = H * rng.uniform(0.12, 0.2)
        y = rng.uniform(-0.1, 0.12) * H
        clump(cv, x, y, r, pal, rng, detail=0.6, lit_amount=0.0, shadow_bias=-0.4,
              flatten=0.85, edge=0.3)
    for pts, w in branches:
        sp = smooth_path(pts, 40)
        ws = np.interp(np.linspace(0, 1, 40), np.linspace(0, 1, len(w)), w)
        stroke(cv, sp, ws, bark_mid, color_lit=mix(bark_mid, rim_c, 0.5), color_dark=bark_dark,
               light=LIGHT, edge=0.15, bristle=0.3, rag=0.15, rng=rng, core=0.3)
    # foliage clusters hanging along the branches, backlit with rim light
    for pts, w in branches:
        sp = smooth_path(pts, 12)
        for i in range(1, 12):
            if rng.random() < 0.45:
                continue
            r = H * rng.uniform(0.06, 0.11) * (1 if w[0] > W * 0.02 else 0.7)
            p = {k: shade(v, dh=rng.uniform(-0.08, 0.08)) for k, v in pal.items()}
            clump_cluster(cv, sp[i, 0], sp[i, 1] + r * 0.5, r, p, rng, n=3, spread=0.5,
                          detail=1.0, lit_amount=0.4, shadow_bias=-0.1, rim=1.0,
                          terminator=0.15, edge=0.22)
    # thin twigs drawn over the foliage so the branch structure stays readable
    for pts, w in branches:
        if w[0] < W * 0.02:
            sp = smooth_path(pts, 30)
            ws = np.interp(np.linspace(0, 1, 30), np.linspace(0, 1, len(w)), w) * 0.6
            stroke(cv, sp, ws, bark_dark, edge=0.2, bristle=0.3, rag=0.15, rng=rng, opacity=0.9)
    # rim light along the lower silhouette: the sun is behind the canopy, so the
    # thin leafy edge glows warm, strongest toward the right (sun side)
    import cv2
    a = (cv.img[..., 3] > 0.5).astype(np.uint8)
    edge = a - cv2.erode(a, np.ones((9, 9), np.uint8))
    ys, xs = np.nonzero(edge)
    if len(xs):
        below = ys < H - 2
        # keep edge pixels that have open sky below them (undersides)
        open_below = np.zeros_like(xs, bool)
        open_below[below] = cv.img[np.minimum(ys[below] + 6, H - 1), xs[below], 3] < 0.3
        xs, ys = xs[open_below], ys[open_below]
        if len(xs):
            # translucent glow: edge zone tinted toward lit green, stronger to the right
            glow = cv2.GaussianBlur(edge.astype(np.float32), (0, 0), 14) * 3.0
            glow = np.clip(glow, 0, 1) * smoothstep(0.25, 1.0, np.linspace(0, 1, W))[None, :]
            cv.tint(mix(pal['lit'], rim_c, 0.3), glow * 0.3)
            p = np.clip(0.02 + 0.6 * smoothstep(0.3, 1.0, xs / W), 0, 1)
            sel = rng.random(len(xs)) < p * 0.16
            xs, ys = xs[sel], ys[sel]
            cols = jitter(mix(pal['lit'], rim_c, rng.uniform(0.3, 0.95, len(xs))[:, None]), rng, dl=0.03, dc=0.1)
            dabs(cv, xs + rng.normal(0, 3, len(xs)), ys + rng.normal(0, 3, len(xs)),
                 rng.uniform(9, 24, len(xs)), cols, aspect=0.4, angle=rng.uniform(0, np.pi, len(xs)),
                 rng=rng, edge=0.3, rag=0.3, bristle=0.3, opacity=rng.uniform(0.6, 1.0, len(xs)))
    # scattered single leaf clusters at the fringe, catching the light
    nf = 60
    for pts, w in branches[:nb]:
        sp = smooth_path(pts, nf)
        sel = rng.random(nf) < 0.25
        q = sp[sel] + rng.normal(0, H * 0.03, (sel.sum(), 2))
        cols = jitter(mix(pal['lit'], rim_c, rng.uniform(0.2, 0.7, len(q))[:, None]), rng, dl=0.03)
        leaf_fans(cv, q[:, 0], q[:, 1], H * 0.018, cols, rng, n_leaves=4, spread=1.2,
                  direction=rng.uniform(0, 2 * np.pi, len(q)), aspect=0.5, rag=0.25, bristle=0.3)
