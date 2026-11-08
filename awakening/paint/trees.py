"""trees.py - procedural painted trees (foreground and middle distance).

paint_tree(cv, rng, spec)   paints one tree into a Canvas: roots, trunk with bark
                            and moss, limbs, back/front foliage masses, vines.
TreeSpec                    all the knobs; fg_spec()/mid_spec() give the presets.

Construction is canopy-first: an envelope ellipse that fits the canvas gets a set of
big foliage "lumps" (each a cluster of clumps); limbs are grown from the trunk top
toward the lumps, so the branching reads as the structure holding the masses.
The trunk base sits at the bottom centre of the canvas.
"""
from dataclasses import dataclass
import numpy as np
from brush import (Canvas, col, mix, mix_many, shade, jitter, atmos, smooth_path, wobble,
                   taper, stroke, dabs, dab_stroke, clump, clump_cluster, leaf_fans,
                   make_palette, smoothstep, noise1d)

LIGHT = (0.62, -0.78)        # toward the sun (upper right), image coords


@dataclass
class TreeSpec:
    W: int = 2048
    H: int = 3072
    trunk_h: float = 0.36          # fraction of H from the base to the first fork
    trunk_w: float = 0.10          # base trunk width as a fraction of W
    lean: float = 0.0              # horizontal drift of the trunk top (fraction of W)
    canopy_w: float = 0.92         # envelope width as a fraction of W
    canopy_top: float = 0.03       # top margin as a fraction of H
    n_top: int = 6                 # lumps along the upper silhouette
    n_inner: int = 4               # lumps inside
    n_low: int = 3                 # lumps along the lower edge (front, shadowed)
    lump_r: float = 0.15           # lump radius as a fraction of W
    cluster_n: int = 5             # clumps per lump
    detail: float = 1.0
    depth: float = 0.0             # atmospheric depth of the whole tree
    cool: float = 0.5
    moss: float = 1.0
    vines: int = 3
    twigs: int = 10                # thin twigs out of lumps
    pal_shadow: tuple = (28, 58, 64)
    pal_mid: tuple = (74, 114, 66)
    pal_lit: tuple = (152, 172, 70)
    pal_tip: tuple = (236, 212, 130)
    bark_dark: tuple = (52, 44, 54)
    bark_mid: tuple = (96, 82, 70)
    bark_lit: tuple = (150, 128, 100)
    moss_col: tuple = (80, 114, 56)


def fg_spec(variant, rng):
    """Foreground preset with per-variant differences."""
    s = TreeSpec()
    s.lean = float(rng.uniform(-0.05, 0.05))
    s.trunk_h = float(rng.uniform(0.40, 0.47))
    s.canopy_top = 0.05
    s.trunk_w = float(rng.uniform(0.13, 0.16))
    s.n_top = int(rng.integers(5, 8))
    s.n_inner = int(rng.integers(3, 6))
    s.n_low = int(rng.integers(2, 4))
    s.lump_r = float(rng.uniform(0.14, 0.165))
    s.n_inner = int(rng.integers(4, 7))
    hues = [((26, 54, 64), (72, 112, 64), (158, 172, 66), (244, 214, 124)),    # classic
            ((28, 50, 70), (60, 102, 78), (138, 168, 82), (236, 216, 146)),    # bluer
            ((32, 58, 52), (90, 118, 56), (172, 170, 62), (246, 210, 112))]    # olive/golden
    s.pal_shadow, s.pal_mid, s.pal_lit, s.pal_tip = hues[variant % 3]
    s.vines = int(rng.integers(2, 5))
    return s


def mid_spec(variant, rng):
    s = TreeSpec(W=1024, H=1536)
    s.lean = float(rng.uniform(-0.05, 0.05))
    s.trunk_h = float(rng.uniform(0.33, 0.42))
    s.trunk_w = float(rng.uniform(0.095, 0.115))
    s.n_top = int(rng.integers(4, 7))
    s.n_inner = int(rng.integers(2, 4))
    s.n_low = int(rng.integers(1, 3))
    s.lump_r = float(rng.uniform(0.15, 0.18))
    s.cluster_n = 4
    s.detail = 0.45
    s.depth = 0.22
    s.cool = 0.6
    s.moss = 0.5
    s.vines = int(rng.integers(0, 2))
    s.twigs = 5
    hues = [((28, 56, 66), (70, 110, 68), (152, 170, 72), (240, 214, 130)),
            ((32, 52, 72), (64, 102, 82), (140, 166, 88), (234, 214, 146)),
            ((28, 58, 56), (84, 116, 58), (166, 170, 66), (244, 212, 120)),
            ((24, 54, 70), (62, 108, 76), (146, 170, 78), (238, 214, 136))]
    s.pal_shadow, s.pal_mid, s.pal_lit, s.pal_tip = hues[variant % 4]
    s.bark_dark, s.bark_mid, s.bark_lit = (46, 42, 54), (84, 76, 72), (132, 118, 100)
    return s


# ----------------------------------------------------------------------------
# skeleton
# ----------------------------------------------------------------------------

def branch_path(p0, ang, length, rng, curl=0.0, n=9, wob=0.07):
    """Polyline from p0 heading at angle ang (image coords: -pi/2 is up), bending
    by a total of `curl` radians with per-step noise."""
    pts = [np.array(p0, np.float32)]
    a = ang
    seg = length / (n - 1)
    for i in range(n - 1):
        a += curl / (n - 1) + rng.normal(0, wob)
        pts.append(pts[-1] + seg * np.array([np.cos(a), np.sin(a)], np.float32))
    return np.array(pts)


def limb_curve(p0, target, rng, n=10, out_angle=0.9, wob=0.03):
    """Quadratic-Bezier-like limb: leaves p0 heading outward/up at out_angle
    (radians from vertical, sign = side of the target), then bends to target."""
    p0, target = np.asarray(p0, np.float32), np.asarray(target, np.float32)
    side = np.sign(target[0] - p0[0]) or 1.0
    L = np.hypot(*(target - p0))
    a = -np.pi / 2 + side * out_angle
    c = p0 + np.array([np.cos(a), np.sin(a)], np.float32) * L * rng.uniform(0.35, 0.5)
    t = np.linspace(0, 1, n)[:, None]
    pts = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * c + t ** 2 * target
    return wobble(pts, rng, L * wob, 3)


def path_to(p0, p1, rng, n=10, bulge=0.25, wob=0.05):
    """Curved polyline from p0 to p1 bowing sideways by bulge*length (hand-drawn)."""
    p0, p1 = np.asarray(p0, np.float32), np.asarray(p1, np.float32)
    d = p1 - p0
    L = np.hypot(*d) + 1e-6
    nrm = np.array([-d[1], d[0]]) / L
    t = np.linspace(0, 1, n)[:, None]
    pts = p0 + d * t + nrm * (np.sin(np.pi * t) * bulge * L)
    return wobble(pts, rng, L * wob, 3)


def build_skeleton(spec, rng):
    """Return trunk, limbs, lumps, envelope.
    trunk: dict(pts, w).  limbs: list of dict(pts, w, level).
    lumps: list of dict(x, y, r, z, kind) foliage masses, z 0 (front) .. 1 (back)."""
    W, H = spec.W, spec.H
    base = np.array([W / 2, H], np.float32)
    th = spec.trunk_h * H
    top = np.array([W / 2 + spec.lean * W, H - th], np.float32)
    ctrl = [base, base + (top - base) * 0.35 + [rng.normal(0, 0.015) * W, 0],
            base + (top - base) * 0.7 + [rng.normal(0, 0.015) * W, 0], top]
    tpts = smooth_path(ctrl, 40)
    tw0 = spec.trunk_w * W
    tw = tw0 * (1 - 0.4 * np.linspace(0, 1, 40) ** 0.8)
    trunk = dict(pts=tpts, w=tw)

    lr = spec.lump_r * W
    # envelope: fits the canvas horizontally, from the canopy top down to just
    # below the trunk top
    rx = spec.canopy_w * W / 2 - lr * 1.5
    y_top = spec.canopy_top * H + lr * 0.9
    y_bot = H - th + lr * 0.6
    ry = (y_bot - y_top) / 2
    cx = W / 2 + spec.lean * W * 0.5
    cy = (y_top + y_bot) / 2
    lumps = []
    # upper silhouette lumps
    n = spec.n_top
    angs = np.linspace(-np.pi * 0.92, -np.pi * 0.08, n) + rng.normal(0, 0.08, n)
    for a in angs:
        k = rng.uniform(0.78, 0.95)
        lumps.append(dict(x=cx + np.cos(a) * rx * k, y=cy + np.sin(a) * ry * k,
                          r=lr * rng.uniform(0.9, 1.15), z=rng.uniform(0.25, 0.7), kind='top'))
    # inner lumps
    for _ in range(spec.n_inner):
        a = rng.uniform(-np.pi, 0)
        k = np.sqrt(rng.random()) * 0.6
        lumps.append(dict(x=cx + np.cos(a) * rx * k, y=cy + np.sin(a) * ry * k * 0.9,
                          r=lr * rng.uniform(0.95, 1.25), z=rng.uniform(0.0, 1.0), kind='inner'))
    # lower edge lumps (front, hanging, shadowed)
    n = spec.n_low
    xs_low = np.linspace(-0.55, 0.55, n) + rng.normal(0, 0.08, n)
    for xl in xs_low:
        yy = cy + ry * rng.uniform(0.55, 0.8) - lr * 0.3
        yy = min(yy, H - th - lr * 0.45)
        lumps.append(dict(x=cx + xl * rx, y=yy, r=lr * rng.uniform(0.75, 0.95),
                          z=rng.uniform(0.0, 0.3), kind='low'))

    for lp in lumps:
        # a cluster reaches ~1.8 lump radii from its centre: keep that inside
        lp['x'] = float(np.clip(lp['x'], lr * 1.3, W - lr * 1.3))
        lp['y'] = float(max(lp['y'], lr * 1.2))
    # limbs: hierarchical. Lumps are grouped by direction into K main limbs; each
    # main limb goes from the trunk (at a different height) to a hub, then
    # sub-limbs run from the hub to each lump.
    limbs = []
    K = int(np.clip(rng.integers(3, 6), 2, len(lumps)))
    heights = np.sort(rng.uniform(0.55, 0.97, K))[::-1]
    # the trunk stops just above the highest attachment, hidden by foliage
    cut = int(min(39, (heights[0] + 0.05) * 39)) + 1
    trunk['pts'], trunk['w'] = tpts[:cut], tw[:cut]
    lumps.append(dict(x=float(tpts[cut - 1, 0]), y=float(tpts[cut - 1, 1]) - lr * 0.3,
                      r=lr * rng.uniform(0.9, 1.1), z=rng.uniform(0.1, 0.4), kind='inner'))
    P = np.array([[lp['x'], lp['y']] for lp in lumps], np.float32)
    ang = np.arctan2(P[:, 1] - top[1], P[:, 0] - top[0])
    order = np.argsort(ang)
    groups = np.array_split(order, K)
    # the most sideways groups attach lower on the trunk
    gorder = np.argsort([abs(np.mean(ang[g]) + np.pi / 2) for g in groups])[::-1]
    for gi, g in zip(gorder, groups):
        if len(g) == 0:
            continue
        s = heights[list(gorder).index(gi)]
        i = int(s * 39)
        p0 = tpts[i]
        centre = P[g].mean(0)
        hub = p0 + (centre - p0) * rng.uniform(0.4, 0.6)
        hub[1] = min(hub[1], p0[1] - 0.05 * H)          # hubs always above the fork
        side = np.sign(hub[0] - p0[0]) or 1.0
        p0 = p0 + np.array([side * tw[i] * 0.25, 0], np.float32)
        n = max(6, int(np.hypot(*(hub - p0)) / (W * 0.05)))
        out = abs(np.arctan2(hub[0] - p0[0], -(hub[1] - p0[1])))   # angle from vertical
        pts = limb_curve(p0, hub, rng, n=n, out_angle=min(1.2, out + rng.uniform(0.2, 0.5)))
        w0 = tw[i] * np.sqrt(len(g) / len(lumps)) * 1.15
        wprof = w0 * (1 - 0.35 * np.linspace(0, 1, n))
        zg = float(np.mean([lumps[j]['z'] for j in g]))
        limbs.append(dict(pts=pts, w=wprof, level=0, z=zg))
        for j in g:
            lp = lumps[j]
            target = np.array([lp['x'], lp['y']]) + rng.normal(0, 0.12, 2) * lp['r']
            n2 = max(5, int(np.hypot(*(target - hub)) / (W * 0.05)))
            p2 = path_to(hub, target, rng, n=n2, bulge=rng.uniform(-0.2, 0.2), wob=0.04)
            w1 = wprof[-1] / np.sqrt(len(g)) * rng.uniform(0.9, 1.1)
            limbs.append(dict(pts=p2, w=w1 * (1 - 0.6 * np.linspace(0, 1, n2) ** 0.9),
                              level=1, z=lp['z']))
            # occasional side twig off the sub-limb
            if rng.random() < 0.5 and n2 > 4:
                m = int(rng.integers(2, n2 - 1))
                side = rng.choice([-1, 1])
                a2 = np.arctan2(*(p2[m + 1] - p2[m - 1])[::-1]) + side * rng.uniform(0.5, 1.0)
                p3 = branch_path(p2[m], a2, lp['r'] * rng.uniform(0.5, 0.9), rng,
                                 curl=-side * 0.4, n=5, wob=0.1)
                limbs.append(dict(pts=p3, w=w1 * 0.5 * (1 - 0.6 * np.linspace(0, 1, 5)),
                                  level=2, z=lp['z']))
    # twigs poking out of lumps (thin, drawn after back foliage, before front)
    twigs = []
    for _ in range(spec.twigs):
        lp = lumps[int(rng.integers(0, len(lumps)))]
        a = rng.uniform(-np.pi, np.pi)
        p0 = np.array([lp['x'], lp['y']]) + np.array([np.cos(a), np.sin(a)]) * lp['r'] * 0.4
        L = lp['r'] * rng.uniform(0.5, 0.8)
        pts = branch_path(p0, a, L, rng, curl=rng.normal(0, 0.9), n=6, wob=0.15)
        pts[:, 0] = np.clip(pts[:, 0], W * 0.02, W * 0.98)
        pts[:, 1] = np.clip(pts[:, 1], H * 0.02, H)
        twigs.append(dict(pts=pts, w=W * 0.006 * (1 - 0.7 * np.linspace(0, 1, 6)), level=2, z=lp['z']))
    return trunk, limbs, twigs, lumps, (cx, cy, rx, ry)


# ----------------------------------------------------------------------------
# painting parts
# ----------------------------------------------------------------------------

def paint_limb(cv, pts, w, rng, dark, mid, lit, moss=None, moss_amt=0.0, detail=1.0,
               streaks=True):
    """Trunk or branch: shaded cylinder stroke + bark streaks (+ moss on the shade side)."""
    pts = np.asarray(pts, np.float32)
    w = np.asarray(w, np.float32)
    if len(pts) < 2:
        return
    sp = smooth_path(pts, max(len(pts) * 4, 12))
    ws = np.interp(np.linspace(0, 1, len(sp)), np.linspace(0, 1, len(w)), w)
    drift = noise1d(len(sp), 4, rng, periodic=False) - 0.5
    body = shade(np.broadcast_to(mid, (len(sp), 3)), dl=drift * 0.05, dh=drift * 0.35)
    stroke(cv, sp, ws, mid, color_along=body, color_lit=lit, color_dark=dark, light=LIGHT,
           bristle=0.2, rag=0.12, edge=0.1, rng=rng, core=0.5)
    d = np.gradient(sp, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.maximum(np.hypot(*nrm.T)[:, None], 1e-6)
    sgn = np.sign(nrm[:, 0] * LIGHT[0] + nrm[:, 1] * LIGHT[1])     # +1 if nrm faces light
    sgn[sgn == 0] = 1
    L = np.sum(np.hypot(*np.diff(sp, axis=0).T))
    wm = float(ws.mean())
    if streaks and wm > 6:
        nb = int(L * wm / 420 * (0.4 + 0.6 * detail)) + 4
        for _ in range(nb):
            s0 = rng.uniform(0, 0.85)
            s1 = min(1.0, s0 + rng.uniform(0.08, 0.4))
            i0, i1 = int(s0 * (len(sp) - 1)), int(s1 * (len(sp) - 1)) + 1
            if i1 - i0 < 2:
                continue
            t = rng.uniform(-0.92, 0.92)
            seg = sp[i0:i1] + nrm[i0:i1] * (t * ws[i0:i1, None] * 0.5)
            seg = wobble(seg, rng, wm * 0.02, 4)
            facing = t * sgn[i0:i1].mean()           # >0 on the lit side
            kind = rng.random()
            if kind < 0.4:                            # dark crack / fissure
                c = shade(mix(dark, mid, rng.uniform(0.0, 0.3)), dl=rng.uniform(-0.05, 0.0),
                          dh=rng.uniform(-0.1, 0.3), dc=1.15)
                wd = wm * rng.uniform(0.012, 0.03) + 1.2
                op = rng.uniform(0.6, 0.95)
            elif facing > 0.1:                        # lit ridge
                c = shade(mix(lit, mid, rng.uniform(0.0, 0.5)), dl=rng.uniform(0.0, 0.08),
                          dh=rng.uniform(-0.15, 0.1))
                wd = wm * rng.uniform(0.02, 0.06) + 1.5
                op = rng.uniform(0.5, 0.9)
            else:                                     # cool mid ridge on the shade side
                c = shade(mix(mid, dark, rng.uniform(0.2, 0.6)), dl=rng.uniform(-0.03, 0.04),
                          dh=rng.uniform(0.0, 0.35), dc=1.1)
                wd = wm * rng.uniform(0.02, 0.06) + 1.5
                op = rng.uniform(0.5, 0.9)
            stroke(cv, seg, taper(len(seg), 0.3, 0.1, wd), c, opacity=op,
                   bristle=0.6, rag=0.2, edge=0.22, rng=rng)
    # moss: patches of small green dabs on the shaded side, more toward the base
    if moss is not None and moss_amt > 0 and wm > 6:
        npatch = int(L / (wm * 1.6) * moss_amt) + 1
        for _ in range(npatch):
            s = rng.uniform(0, 1) ** 1.5 * 0.9                 # toward the start (base)
            i = int(s * (len(sp) - 1))
            tcen = rng.uniform(-0.95, 0.1) * sgn[i]            # shade side
            prad = wm * rng.uniform(0.25, 0.6)
            nm = int(prad * prad / (wm * wm) * 260 * moss_amt) + 12
            # continuous position along the limb (interpolated, no index banding)
            sc = np.clip(s + rng.normal(0, prad / L, nm), 0, 1) * (len(sp) - 1)
            si = np.minimum(sc.astype(int), len(sp) - 2)
            f = (sc - si)[:, None]
            cpt = sp[si] * (1 - f) + sp[si + 1] * f
            cn = nrm[si] * (1 - f) + nrm[si + 1] * f
            cw = ws[si] * (1 - f[:, 0]) + ws[si + 1] * f[:, 0]
            tt = np.clip(tcen + rng.normal(0, 0.22, nm), -1.08, 1.0)
            px = cpt[:, 0] + cn[:, 0] * tt * cw * 0.5
            py = cpt[:, 1] + cn[:, 1] * tt * cw * 0.5
            sz = wm * rng.uniform(0.035, 0.09, nm) + 2
            # lit moss is yellow-green, shaded moss deep blue-green
            litm = np.clip(tt * sgn[si] * 0.5 + 0.5 + rng.normal(0, 0.15, nm), 0, 1)
            cols = mix_many([mix(moss, dark, 0.55), moss, shade(moss, dl=0.08, dh=-0.15)], litm)
            cols = jitter(cols, rng, dl=0.02, dc=0.1, dh=0.06)
            dabs(cv, px, py, sz, cols, aspect=rng.uniform(0.65, 1.0, nm), rng=rng, rag=0.4,
                 bristle=0.3, edge=0.45, opacity=rng.uniform(0.7, 1.0, nm))


def paint_roots(cv, base, w0, rng, dark, mid, lit, moss, n=5, detail=1.0):
    """Root flare painted over the trunk base: ridges that start on the trunk and
    curve outward and down to the bottom edge."""
    angs = np.linspace(-1, 1, n) + rng.normal(0, 0.08, n)
    for a in angs:
        x0 = base[0] + a * w0 * 0.28
        y0 = base[1] - w0 * rng.uniform(1.1, 1.8) * (1.2 - 0.5 * abs(a))
        x1 = base[0] + a * w0 * rng.uniform(0.7, 1.05) + rng.normal(0, 0.05) * w0
        y1 = base[1] + w0 * 0.05
        pts = path_to([x0, y0], [x1, y1], rng, n=8, bulge=a * rng.uniform(0.08, 0.2), wob=0.015)
        tt = np.linspace(0, 1, len(pts))
        wprof = w0 * rng.uniform(0.18, 0.28) * (0.25 + 0.95 * tt ** 1.5)
        paint_limb(cv, pts, wprof, rng, dark, mid, lit, moss, moss_amt=1.5, detail=detail)


def paint_vine(cv, p0, length, rng, dark, leafcol, w=4.0):
    """Hanging vine: olive-brown stem drooping down with pairs of leaf dabs."""
    n = 14
    xs = p0[0] + np.cumsum(rng.normal(0, length * 0.035, n))
    ys = p0[1] + np.linspace(0, length, n) + np.sin(np.linspace(0, 2.5, n)) * length * 0.02
    pts = smooth_path(np.stack([xs, ys], 1), 60)
    stem = mix(dark, leafcol, 0.3)
    stroke(cv, pts, taper(60, 1.0, 0.4, w * 1.6), stem, bristle=0.4, rag=0.2, edge=0.3, rng=rng)
    k = int(length / (w * 7)) + 3
    s = np.linspace(0.05, 1, k)
    idx = (s * 59).astype(int)
    px, py = np.repeat(pts[idx, 0], 2), np.repeat(pts[idx, 1], 2)
    side = np.tile([1, -1], k)
    ang = np.pi / 2 + side * rng.uniform(0.7, 1.3, 2 * k)
    cols = jitter(mix(leafcol, dark, rng.uniform(0, 0.4, 2 * k)[:, None]), rng, dl=0.04, dc=0.1, dh=0.08)
    L = w * rng.uniform(4.0, 6.5, 2 * k)
    dabs(cv, px + np.cos(ang) * L * 0.45, py + np.sin(ang) * L * 0.45, L, cols,
         aspect=0.45, angle=ang, rng=rng, rag=0.25, bristle=0.3)


# ----------------------------------------------------------------------------
# whole tree
# ----------------------------------------------------------------------------

def paint_tree(cv, rng, spec):
    W, H = spec.W, spec.H
    d = spec.depth
    pal = make_palette(spec.pal_shadow, spec.pal_mid, spec.pal_lit, spec.pal_tip,
                       depth=d, cool=spec.cool)
    bark_dark = atmos(col(*spec.bark_dark), d, cool=spec.cool)
    bark_mid = atmos(col(*spec.bark_mid), d, cool=spec.cool)
    bark_lit = atmos(col(*spec.bark_lit), d, cool=spec.cool)
    moss = atmos(col(*spec.moss_col), d, cool=spec.cool)
    trunk, limbs, twigs, lumps, env = build_skeleton(spec, rng)
    cx, cy, rx, ry = env

    def lump_light(lp):
        """(shadow_bias, lit_amount, terminator) from the lump's position and depth:
        big-form light, top-right of the canopy lit, lower-left in shadow."""
        nx, ny = (lp['x'] - cx) / rx, (lp['y'] - cy) / ry
        big = smoothstep(-1.1, 1.1, nx * LIGHT[0] - ny * -LIGHT[1])   # 0 lower-left .. 1 upper-right
        z = lp['z']
        bias = (big - 0.55) * 1.1 - 0.5 * z
        lit = np.clip(0.05 + 1.3 * big ** 1.3 - 0.6 * z, 0.0, 1.4)
        term = 0.25 - 0.5 * big                        # lit area grows toward the sun side
        if lp['kind'] == 'low':
            bias -= 0.25
            lit *= 0.5
            term += 0.15
        return float(np.clip(bias, -0.85, 0.5)), float(lit), float(term)

    bounds = (W * 0.01, H * 0.01, W * 0.99, H)
    back = [lp for lp in lumps if lp['z'] > 0.55]
    front = [lp for lp in lumps if lp['z'] <= 0.55]
    back_pal = {k: shade(v, dl=-0.02, dc=0.85, dh=0.1) for k, v in pal.items()}

    # 1. back foliage (darker, cooler, coarser)
    def lump_pal(base_pal):
        # per-lump colour variation: hue and lightness drift so no two masses match
        dh, dl = rng.uniform(-0.09, 0.09), rng.uniform(-0.025, 0.025)
        return {k: shade(v, dl=dl, dh=dh, dc=rng.uniform(0.9, 1.1)) for k, v in base_pal.items()}

    for lp in sorted(back, key=lambda s: -s['z']):
        bias, lit, term = lump_light(lp)
        clump_cluster(cv, lp['x'], lp['y'], lp['r'] * 1.05, lump_pal(back_pal), rng,
                      n=max(3, spec.cluster_n - 1), spread=0.55, detail=spec.detail * 0.8,
                      lit_amount=lit * 0.5, shadow_bias=max(bias - 0.15, -0.6), density=0.7,
                      terminator=term + 0.1, bounds=bounds)

    # 2. roots, trunk, limbs (thick first), twigs
    base = np.array([W / 2, H], np.float32)
    paint_limb(cv, trunk['pts'], trunk['w'], rng, bark_dark, bark_mid, bark_lit, moss,
               moss_amt=spec.moss, detail=spec.detail)
    paint_roots(cv, base, spec.trunk_w * W, rng, bark_dark, bark_mid, bark_lit, moss,
                n=int(rng.integers(4, 7)), detail=spec.detail)
    for b in sorted(limbs, key=lambda b: (b['level'], -b['z'])):
        # limbs deep in the canopy are darker (in the foliage's shadow)
        k = 0.45 + 0.45 * b['z']
        paint_limb(cv, b['pts'], b['w'], rng, bark_dark, mix(bark_mid, bark_dark, k * 0.85),
                   mix(bark_lit, bark_mid, k), moss,
                   moss_amt=spec.moss * 0.5 if b['level'] == 0 else 0.0, detail=spec.detail)
    for t in twigs:
        paint_limb(cv, t['pts'], t['w'], rng, bark_dark, mix(bark_mid, bark_dark, 0.5),
                   bark_mid, None, streaks=False)

    # 3. front foliage, back-to-front (lower hanging lumps last)
    for lp in sorted(front, key=lambda s: -s['z']):
        bias, lit, term = lump_light(lp)
        clump_cluster(cv, lp['x'], lp['y'], lp['r'], lump_pal(pal), rng,
                      n=spec.cluster_n, spread=0.5, detail=spec.detail,
                      lit_amount=lit, shadow_bias=bias, terminator=term, bounds=bounds)

    # 4. vines from limbs
    for _ in range(spec.vines):
        if not limbs:
            break
        b = limbs[int(rng.integers(0, len(limbs)))]
        i = int(rng.integers(1, len(b['pts'])))
        p0 = b['pts'][i] + [0, b['w'][i] * 0.3]
        paint_vine(cv, p0, spec.trunk_h * H * rng.uniform(0.35, 0.8), rng,
                   mix(bark_dark, pal['shadow'], 0.5), pal['mid'], w=W / 500)
    return env
