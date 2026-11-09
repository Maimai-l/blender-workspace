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


def paint_planes(cv, rng, blobs, cols, light3=(0.55, -0.75, 0.3), wrap=0.45, under=0.6, th=(0.3, 0.52, 0.8),
                 soft=0.035, noise_amt=0.1, rag=0.6, strokes=1.0, stroke_size=None, rim=None, rim_amt=1.0,
                 wisps=0.0, wisp_col=None, opacity=1.0, edge_px=1.2, sun2=None, leafy_edge=0.0, leaf_cols=None,
                 soft_base=0.0, region=None):
    """Ghibli-style masses painted as big flat value planes (not dabs): the dome shading of
    the blobs is cut into 3-4 planes with hard-ish, noise-meandering terminators (shadow ->
    mid -> lit -> crown highlight), the silhouette is a crisp painted edge, a few broad
    form-following strokes add brushwork, a thin bright rim runs along the sun-facing edge
    and optional soft wisps trail off. cols = (shadow, mid, lit, highlight)."""
    from .color import oklab, from_oklab
    import cv2 as _cv2
    G = render_gbuffer(cv, blobs, light3=light3, wrap=wrap, under=under)
    cov, sh, cid = G['cov'], G['shade'], G['cid']
    ys, xs = np.nonzero(cov > 0.02)
    if len(xs) == 0:
        return G
    pad = 8
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + pad, cov.shape[1]), min(int(ys.max()) + pad, cov.shape[0])
    c = cov[y0:y1, x0:x1]
    hh, ww = c.shape
    size = float(np.sqrt(max((c > 0.5).sum(), 1)))
    n1 = fbm(hh, ww, max(size * 0.35, 30), rng, octaves=3) - 0.5
    n2 = fbm(hh, ww, max(size * 0.08, 8), rng, octaves=2) - 0.5
    # whole-mass shading (lit crown and sun side, shadowed base) blended with the per-lobe domes,
    # so lobes read as bumps on one form rather than separate boulders
    yy = (np.arange(hh, dtype=np.float32)[:, None] + 0.5)
    xx = (np.arange(ww, dtype=np.float32)[None, :] + 0.5)
    colsum = np.maximum((c > 0.5).sum(0, keepdims=True), 1)
    ytop = np.argmax(c > 0.5, axis=0)[None, :].astype(np.float32)
    ybot = (hh - np.argmax((c > 0.5)[::-1], axis=0))[None, :].astype(np.float32)
    gv = np.clip((ybot - yy) / np.maximum(ybot - ytop, 1), 0, 1)          # 1 at the top .. 0 at the base
    s2x = light3[0] / (np.hypot(light3[0], light3[1]) + 1e-6)
    gx = (xx / ww - 0.5) * s2x
    vglob = np.clip(0.15 + 0.85 * gv ** 0.8 + 0.25 * gx, 0, 1)
    v = np.clip(0.45 * sh[y0:y1, x0:x1] + 0.55 * vglob + noise_amt * n1 + noise_amt * 0.4 * n2, 0, 1)
    L = [oklab(np.asarray(k, np.float32)) for k in cols]
    m1 = smoothstep(th[0] - soft, th[0] + soft, v)
    m2 = smoothstep(th[1] - soft, th[1] + soft, v)
    m3 = smoothstep(th[2] - soft * 0.7, th[2] + soft * 0.7, v)
    lab = L[0] + (L[1] - L[0]) * m1[..., None]
    lab = lab + (L[2] - lab) * m2[..., None]
    lab = lab + (L[3] - lab) * (m3 * 0.85)[..., None]
    # keep a little form inside each plane
    lab[..., 0] += (v - 0.5) * 0.05
    rgb = np.clip(from_oklab(lab), 0, 1)
    # crisp, slightly ragged silhouette
    cr = _cv2.GaussianBlur(c, (0, 0), 1.0)
    edge_noise = (fbm(hh, ww, 14, rng, octaves=2) - 0.5) * rag * 0.35
    a = np.clip((cr - 0.5 + edge_noise) / max(edge_px * 0.08, 1e-3) * 0.5 + 0.5, 0, 1)
    if soft_base > 0:
        # soften the underside edge (flat bases dissolve a little)
        gy = _cv2.Sobel(_cv2.GaussianBlur(c, (0, 0), 6), _cv2.CV_32F, 0, 1, ksize=3)
        base = np.clip(-gy * 8, 0, 1) * soft_base
        a = a * (1 - base) + _cv2.GaussianBlur(c, (0, 0), 10) * base
    a = (a * opacity).astype(np.float32)
    cv.over_region(x0, y0, rgb.astype(np.float32), a)
    # broad form-following strokes, sampling the plane colour (alpha-locked)
    if strokes > 0:
        ss = stroke_size or max(size * 0.07, 10)
        n = int(strokes * (c > 0.5).sum() / (ss * ss * 0.35) * 0.6)
        if n > 0:
            sel = np.flatnonzero((c > 0.97).ravel())
            pick = rng.choice(sel, min(n, len(sel)), replace=False)
            py, px = np.unravel_index(pick, c.shape)
            cidp = cid[y0:y1, x0:x1][py, px]
            bx = np.where(cidp >= 0, G['b']['x'][np.maximum(cidp, 0)] + cv.m - x0, px)
            by = np.where(cidp >= 0, G['b']['y'][np.maximum(cidp, 0)] + cv.m - y0, py)
            ang = np.arctan2(py - by, px - bx) + np.pi / 2 + rng.normal(0, 0.25, len(px))
            colp = jitter(rgb[py, px], rng, dl=0.025, dc=0.08, dh=0.03)
            dabs(cv, px + x0 - cv.m, py + y0 - cv.m, ss * rng.uniform(0.6, 1.5, len(px)), colp,
                 aspect=rng.uniform(0.25, 0.45, len(px)), angle=ang, shape='flat', edge=0.45, rag=0.3,
                 bristle=0.35, opacity=rng.uniform(0.2, 0.45, len(px)) * opacity, mode='lock', rng=rng)
    # leafy edge (for foliage masses painted in planes): sparse leaf marks along the silhouette
    if leafy_edge > 0:
        band = (cr > 0.25) & (cr < 0.7)
        ne = int(leafy_edge * band.sum() / 6)
        if ne > 0:
            sel = np.flatnonzero(band.ravel())
            pick = rng.choice(sel, min(ne, len(sel)), replace=False)
            py, px = np.unravel_index(pick, c.shape)
            gx = _cv2.Sobel(cr, _cv2.CV_32F, 1, 0, ksize=3)
            gy = _cv2.Sobel(cr, _cv2.CV_32F, 0, 1, ksize=3)
            nx, ny = -gx[py, px], -gy[py, px]
            nn = np.hypot(nx, ny) + 1e-6
            ang = np.arctan2(ny / nn, nx / nn) + rng.normal(0, 0.6, len(px))
            lc = leaf_cols if leaf_cols is not None else cols[:3]
            colp = jitter(ramp(lc, np.clip(v[py, px] + rng.normal(0, 0.1, len(px)), 0, 1)), rng, dl=0.03)
            L_ = max(size * 0.03, 6)
            dabs(cv, px + x0 - cv.m + nx / nn * L_ * 0.3, py + y0 - cv.m + ny / nn * L_ * 0.3,
                 L_ * rng.uniform(0.7, 1.3, len(px)), colp, aspect=0.45, angle=ang, shape='leaf', edge=0.25,
                 rag=0.2, bristle=0.2, split=0.1, opacity=opacity, rng=rng)
    # thin bright rim along the sun-facing edge
    if rim is not None and rim_amt > 0:
        s2 = sun2 if sun2 is not None else (light3[0], light3[1])
        s2 = np.asarray(s2, np.float32) / (np.hypot(*s2) + 1e-6)
        gx = _cv2.Sobel(cr, _cv2.CV_32F, 1, 0, ksize=3)
        gy = _cv2.Sobel(cr, _cv2.CV_32F, 0, 1, ksize=3)
        gn = np.hypot(gx, gy) + 1e-6
        nx, ny = -gx / gn, -gy / gn
        face = nx * s2[0] + ny * s2[1]
        band = (cr > 0.45) & (cr < 0.85) & (face > 0.25)
        nr = int(rim_amt * band.sum() / 3)
        if nr > 0:
            sel = np.flatnonzero(band.ravel())
            pick = rng.choice(sel, min(nr, len(sel)), replace=False)
            py, px = np.unravel_index(pick, c.shape)
            ang = np.arctan2(ny[py, px], nx[py, px]) + np.pi / 2
            f = face[py, px]
            colp = jitter(np.broadcast_to(np.asarray(rim, np.float32), (len(px), 3)), rng, dl=0.02)
            dabs(cv, px + x0 - cv.m, py + y0 - cv.m, rng.uniform(6, 16, len(px)), colp, aspect=0.22, angle=ang,
                 edge=0.4, rag=0.2, bristle=0.2, opacity=np.clip(0.4 + 0.6 * f, 0, 1) * opacity, rng=rng)
    # soft wisps trailing from the sides / base
    if wisps > 0:
        wc = wisp_col if wisp_col is not None else cols[1]
        band = (cr > 0.2) & (cr < 0.6)
        nw = int(wisps * 40)
        sel = np.flatnonzero(band.ravel())
        if len(sel) and nw:
            pick = rng.choice(sel, min(nw, len(sel)), replace=False)
            py, px = np.unravel_index(pick, c.shape)
            colp = jitter(np.broadcast_to(np.asarray(wc, np.float32), (len(px), 3)), rng, dl=0.03)
            dabs(cv, px + x0 - cv.m + rng.normal(0, size * 0.05, len(px)), py + y0 - cv.m + rng.normal(0, 4, len(px)),
                 rng.uniform(size * 0.15, size * 0.4, len(px)), colp, aspect=rng.uniform(0.06, 0.14, len(px)),
                 angle=rng.normal(0, 0.06, len(px)), edge=0.95, rag=0.3, bristle=0.5,
                 opacity=rng.uniform(0.15, 0.35, len(px)) * opacity, rng=rng)
    return G


def plane_cloud(cv, rng, cx, base_y, w, h, cols, kind='cumulus', light3=(0.55, -0.75, 0.3), rim=None, wisps=0.3,
                opacity=1.0, strokes=0.6, lobes=None, soft_base=0.0):
    b = sculpted_blobs(rng, cx, base_y, w, h, kind=kind, lobes=lobes)
    return paint_planes(cv, rng, b, cols, light3=light3, rim=rim, wisps=wisps, opacity=opacity, strokes=strokes,
                        soft_base=soft_base)
