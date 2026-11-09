"""sky.py - painted dawn skies and sculpted clouds.

sky(cv, ...)        Oklab gradient (blue-violet -> rose -> peach -> gold near the
                    sun) with a sun glow, then brushed over with broad, slightly
                    tilted gouache strokes that sample the gradient with colour
                    jitter, so it reads as paint, never as a digital gradient.
cumulus(...)        a cloud built from puffs (Blobs): G-buffer lit by the sun,
                    painted with rounded strokes that wrap around the puffs:
                    gold-lit tops, rose mid-tones, lilac-violet undersides.
cloud_sea(...)      rows of flattened puffs shrinking toward the horizon.
"""
import numpy as np
import cv2

from .canvas import dabs, stroke, catmull, taper
from .color import C, mix, ramp, jitter, oklab, from_oklab, smoothstep, ramp_lab, jitter_lab
from .noise import fbm, noise1d
from .foliage import Blobs, render_gbuffer, paint_mass


def gradient_field(cv, stops, pos, sun=None, glow=None, tilt=0.0, warp=None):
    """Straight sky colour (H, W, 3) over the canvas buffer. glow = (radius, colour,
    strength). tilt: gradient coordinate shifts with x (sky brighter toward the sun)."""
    X, Y = cv.coords()
    t = Y / float(cv.H) + tilt * (X / float(cv.W) - 0.5)
    if warp is not None:
        t = t + warp
    rgb = ramp(stops, np.clip(t, pos[0], pos[-1]), pos)
    if sun is not None and glow is not None:
        r, gc, st = glow
        d = np.hypot(X - sun[0], (Y - sun[1]) * 1.15) / r
        k = (np.exp(-d * d * 1.6) * 0.75 + np.exp(-d * 3.2) * 0.45) * st
        lab = oklab(rgb)
        lab = lab + (oklab(gc) - lab) * np.clip(k, 0, 1)[..., None]
        rgb = from_oklab(lab)
    return np.clip(rgb, 0, 1).astype(np.float32)


def sky(cv, rng, stops, pos, sun=None, glow=None, tilt=0.0, n_strokes=1.0, stroke_w=(30, 110),
        stroke_len=(250, 900), angle=0.0, opacity=(0.25, 0.6), warp_amt=0.02):
    """Fill the whole canvas with a brushed sky. Returns the base gradient field."""
    h, w = cv.shape
    warp = (fbm(h, w, max(w, h) * 0.35, rng, octaves=3) - 0.5) * warp_amt
    base = gradient_field(cv, stops, pos, sun, glow, tilt, warp)
    cv.img[..., :3] = base
    cv.img[..., 3] = 1.0
    # broad brushed strokes sampling the gradient
    n = int(n_strokes * w * h / (np.mean(stroke_w) * np.mean(stroke_len)) * 2.2)
    xs = rng.uniform(-0.05, 1.05, n) * cv.W
    ys = rng.uniform(-0.05, 1.05, n) * cv.H
    ix = np.clip((xs + cv.m).astype(int), 0, w - 1)
    iy = np.clip((ys + cv.m).astype(int), 0, h - 1)
    cols = jitter(base[iy, ix], rng, dl=0.018, dc=0.1, dh=0.05)
    L = rng.uniform(*stroke_len, n)
    Wd = rng.uniform(*stroke_w, n)
    for k in range(n):
        a = angle + rng.normal(0, 0.05)
        dx, dy = np.cos(a) * L[k] / 2, np.sin(a) * L[k] / 2
        bend = rng.normal(0, 0.08) * L[k]
        p = np.array([[xs[k] - dx, ys[k] - dy], [xs[k] - dy * 0 + 0, ys[k] + bend * 0.2],
                      [xs[k] + dx, ys[k] + dy]], np.float32)
        p[1] = [xs[k], ys[k] + bend * 0.15]
        stroke(cv, p, taper(12, 0.35, 0.25, Wd[k]), cols[k], opacity=rng.uniform(*opacity),
               edge=0.55, bristle=0.6, rag=0.25, spacing=6.0, rng=rng)
    return base


def sun_disc(cv, x, y, r, col=C(255, 250, 232), halo=C(255, 232, 170), rng=None):
    """Soft painted sun: bright disc + halo of soft dabs."""
    rng = rng or np.random.default_rng(3)
    X, Y = cv.coords()
    d = np.hypot(X - x, Y - y)
    a = np.clip((r * 1.0 - d) / (r * 0.35) + 0.5, 0, 1)
    halo_a = np.exp(-(d / (r * 2.6)) ** 2) * 0.55
    cv.over(halo, halo_a)
    cv.over(col, a)


def cumulus_blobs(rng, x, y, w, h, n=None, flat_base=True, lumpy=0.12, rows=3, light=1.0, hue=0.0,
                  blobs=None, puff=(0.12, 0.3)):
    """Puffs for one cumulus mass spanning (x-w/2..x+w/2), base at y, height h.
    Piles of puffs: big ones at the bottom middle, smaller toward the top/edges."""
    if blobs is None:
        blobs = Blobs()
    n = n or int(8 + w / max(h, 1) * 6)
    items = []
    for i in range(n):
        u = rng.uniform(-0.5, 0.5)
        env = np.sqrt(max(1 - (2 * u) ** 2, 0.02))           # dome envelope
        top = h * env * rng.uniform(0.55, 1.0)
        yy = y - rng.uniform(0.15, 1.0) * top
        r = (puff[0] + (puff[1] - puff[0]) * rng.random() ** 1.3) * min(w, h * 2.2) * (0.6 + 0.6 * env)
        r = min(r, h * 0.6)
        ry = r * rng.uniform(0.7, 0.95)
        if flat_base:
            yy = min(yy, y - ry * 0.55)
        z = yy + rng.normal(0, h * 0.05)
        items.append((-z, x + u * w, yy, r, ry))
    items.sort(key=lambda it: it[0])
    for _, px, py, r, ry in items:
        blobs.add(px, py, r, ry, rot=rng.normal(0, 0.1), light=light * rng.uniform(0.9, 1.05),
                  hue=hue + rng.normal(0, 0.03), val=rng.normal(0, 0.03), rng=rng, lumpy=lumpy)
    return blobs


def paint_clouds(cv, rng, blobs, stops, pos=None, light3=(0.6, -0.5, 0.25), leaf=16, density=1.0,
                 rim=None, rim_amt=0.0, vnoise=0.07, edge=0.45, opacity=1.0, wrap=0.6, under=0.45,
                 bands=4, aspect=0.55, trans=None, trans_amt=0.0, sun2=None, fringe=0.3, tip=None,
                 edge_leaves=0.35, size_dark=1.7, size_lit=0.9, bristle=0.3):
    G = render_gbuffer(cv, blobs, light3=light3, wrap=wrap, under=under)
    if sun2 is None:
        sun2 = (light3[0], light3[1])
    paint_mass(cv, G, rng, stops, pos, leaf=leaf, density=density, aspect=aspect, shape='round',
               vnoise=vnoise, hue_var=0.03, sun2=sun2, trans=trans, trans_amt=trans_amt, rim=rim,
               rim_amt=rim_amt, tip=tip, tip_amt=0.12 if tip is not None else 0, edge_leaves=edge_leaves,
               droop=0.0, size_dark=size_dark, size_lit=size_lit, bristle=bristle, rag=0.3, edge=edge,
               split=0.0, bands=bands, opacity=opacity, fringe=fringe, orient='tangent')
    return G


def sculpted_blobs(rng, cx, base_y, w, h, kind='cumulus', blobs=None, light=1.0, hue=0.0, lobes=None):
    """A large sculpted cloud form: a flat base slab, a few big crown lobes following a
    dome (cumulus) or an undulating band (strato), and small satellite lobes on the
    crown so the painted edge breaks up. Painter's order: base, then lobes back->front."""
    if blobs is None:
        blobs = Blobs()
    items = []
    # flat base slab (a row of wide, thin ellipses)
    nb = max(3, int(w / max(h * 0.9, 1)))
    for i in range(nb):
        u = (i + 0.5) / nb - 0.5
        items.append((0.0, cx + u * w * 0.95, base_y - h * 0.16, w / nb * 0.9, h * 0.2, 0.0, 0.9))
    nl = lobes or (int(rng.integers(3, 6)) if kind == 'cumulus' else int(rng.integers(5, 9)))
    us = np.sort(rng.uniform(-0.42, 0.42, nl))
    for u in us:
        if kind == 'cumulus':
            env = np.sqrt(max(1 - (2 * u) ** 2, 0.05))
            r = h * rng.uniform(0.32, 0.5) * (0.6 + 0.5 * env)
            y = base_y - h * env * rng.uniform(0.55, 0.85) + r * 0.25
        else:
            env = 1.0 - abs(2 * u) ** 3
            r = h * rng.uniform(0.35, 0.6)
            y = base_y - h * rng.uniform(0.35, 0.7) * env
        x = cx + u * w
        y = min(y, base_y - r * 0.5)
        items.append((1.0 + rng.random(), x, y, r * rng.uniform(1.05, 1.5), r * rng.uniform(0.75, 0.95),
                      rng.normal(0, 0.12), 1.0))
        # satellites on the upper edge of each lobe
        for k in range(int(rng.integers(1, 3))):
            a = rng.uniform(-np.pi * 0.9, -np.pi * 0.1)
            rr = r * rng.uniform(0.32, 0.5)
            items.append((2.0 + rng.random(), x + np.cos(a) * r * 1.05, y + np.sin(a) * r * 0.85, rr * 1.2, rr,
                          rng.normal(0, 0.2), 1.05))
    items.sort(key=lambda it: it[0])
    for _, x, y, rx, ry, rot, lt in items:
        blobs.add(x, y, rx, ry, rot=rot, light=light * lt * rng.uniform(0.95, 1.05), hue=hue + rng.normal(0, 0.02),
                  val=rng.normal(0, 0.025), rng=rng, lumpy=0.08)
    return blobs


def sculpted_cloud(cv, rng, cx, base_y, w, h, stops, pos=None, kind='cumulus', light3=(0.6, -0.6, 0.18),
                   rim=None, rim_amt=0.8, tip=None, opacity=1.0, under=0.95, leaf=None, density=0.45):
    b = sculpted_blobs(rng, cx, base_y, w, h, kind=kind)
    leaf = leaf or max(h / 9.0, 7.0)
    return paint_clouds(cv, rng, b, stops, pos, light3=light3, leaf=leaf, density=density, rim=rim,
                        rim_amt=rim_amt, edge=0.45, opacity=opacity, wrap=0.5, under=under, bands=4,
                        edge_leaves=0.5, size_dark=1.8, size_lit=1.0, tip=tip, fringe=0.35)
