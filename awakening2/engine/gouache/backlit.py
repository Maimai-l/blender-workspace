"""backlit.py - canopy undersides seen against the light (S11 / S15).

backlit_masses()  leaf masses painted as translucent, backlit foliage: a thickness field
                  (distance inside the silhouette, broken by clumping noise) and the light
                  reaching each mass (near the bright gap = warm and strong, far = weak)
                  give the transmitted light; it is cut into 4 painted bands with ragged
                  boundaries (deep cool green -> dark green -> warm green -> glowing yellow-
                  green), then textured with leaves: glowing translucent leaves, darker
                  overlapping leaf silhouettes inside the bright parts (the classic backlit
                  pattern), leaf shapes breaking the silhouette, and a rim that differs per
                  mass (none / thin hot / broad soft; cream, gold, lime or rose).
haze_veil()       soft warm light haze around the gap (a layer of glowing air).
light_shafts()    soft rays radiating from the gap through the gaps between masses.
"""
import numpy as np
import cv2

from .color import C, mix, ramp, jitter, smoothstep, oklab, from_oklab
from .noise import fbm
from .canvas import dabs, stroke, taper
from .foliage import render_gbuffer

GREENS = [C(22, 30, 46), C(34, 54, 54), C(70, 108, 60), C(160, 186, 76), C(236, 232, 132)]
GREENS_POS = [0.0, 0.16, 0.42, 0.74, 1.0]
RIMS = [C(255, 244, 206), C(255, 214, 128), C(214, 236, 120), C(255, 196, 160)]


def backlit_masses(cv, rng, blobs, mass_of_blob, lit_fn, thick_px, leaf=12.0, density=1.0, greens=None,
                   gpos=None, rim_amt=1.0, cool=0.0, dark_leaves=1.0, glow_leaves=1.0, band_noise=0.08,
                   lp=None):
    """blobs: Blobs; mass_of_blob: list, mass index per blob (same order); lit_fn(X, Y) -> light reaching
    the canopy there (0..1); thick_px: thickness scale (px) at which light is mostly absorbed;
    lp: light point (the gap / sun) for rim direction."""
    greens = greens or GREENS
    gpos = gpos or GREENS_POS
    G = render_gbuffer(cv, blobs, light3=(0.0, 0.0, -1.0), wrap=0.5, under=0.0)
    cov, cid = G['cov'], G['cid']
    ys, xs = np.nonzero(cov > 0.02)
    if len(xs) == 0:
        return
    pad = 6
    x0, y0 = max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0)
    x1, y1 = min(int(xs.max()) + pad, cov.shape[1]), min(int(ys.max()) + pad, cov.shape[0])
    c = cov[y0:y1, x0:x1]
    cidr = cid[y0:y1, x0:x1]
    hh, ww = c.shape
    X = (np.arange(ww, dtype=np.float32) + x0 - cv.m)[None, :] * np.ones((hh, 1), np.float32)
    Y = (np.arange(hh, dtype=np.float32) + y0 - cv.m)[:, None] * np.ones((1, ww), np.float32)
    inside = (c > 0.5).astype(np.uint8)
    # close hairline gaps where blobs meet (otherwise they glow like edges inside a mass)
    kr = max(int(leaf * 0.9), 3) | 1
    inside = cv2.morphologyEx(inside, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kr, kr)))
    c = np.maximum(c, cv2.GaussianBlur(inside.astype(np.float32), (0, 0), 0.8))
    dist = cv2.distanceTransform(inside, cv2.DIST_L2, 5).astype(np.float32)
    clump = fbm(hh, ww, max(thick_px * 0.6, 20), rng, octaves=3)
    T = dist / max(thick_px, 1.0) * (0.55 + 0.9 * clump)
    Lp = np.clip(lit_fn(X, Y), 0, 1).astype(np.float32)
    # per mass: how translucent it is (leaf density) and its hue (warm gold-green .. cool green)
    rr = np.random.default_rng(int(rng.integers(1 << 30)))
    mob = np.asarray(mass_of_blob, np.int64) if len(mass_of_blob) else np.zeros(1, np.int64)
    nm = int(mob.max() + 1)
    m_trans = rr.uniform(0.6, 1.3, nm)
    m_hue = rr.normal(0, 0.12, nm)
    mid = np.where(cidr >= 0, mob[np.clip(cidr, 0, len(mob) - 1)], -1)
    TM = np.where(mid >= 0, m_trans[np.maximum(mid, 0)], 1.0).astype(np.float32)
    HU = np.where(mid >= 0, m_hue[np.maximum(mid, 0)], 0.0).astype(np.float32)
    trans = Lp * (0.22 + 0.78 * np.exp(-3.0 * T)) * TM
    v = np.clip(trans + (fbm(hh, ww, max(leaf * 3, 10), rng, octaves=2) - 0.5) * band_noise, 0, 1)
    if cool > 0:
        v = v * (1 - cool * 0.3)
    # 1. painted bands with ragged boundaries
    labs = [oklab(g) for g in greens]
    pert = (fbm(hh, ww, max(leaf * 2.0, 8), rng, octaves=2) - 0.5) * 0.12
    vb = v + pert
    lab = labs[0] + 0 * vb[..., None]
    for i in range(1, len(labs)):
        t = smoothstep(gpos[i] - 0.03, gpos[i] + 0.03, vb * 0.97)
        lab = lab + (labs[i] - lab) * (t * (0.55 if i == len(labs) - 1 else 1.0))[..., None]
    Cc = np.hypot(lab[..., 1], lab[..., 2])
    hh_ = np.arctan2(lab[..., 2], lab[..., 1]) + HU
    lab = np.stack([lab[..., 0], Cc * np.cos(hh_), Cc * np.sin(hh_)], -1)
    rgb = np.clip(from_oklab(lab), 0, 1).astype(np.float32)
    a = np.clip((c - 0.5) * 6 + 0.5, 0, 1).astype(np.float32)
    cv.over_region(x0, y0, rgb, a)
    # 2. leaves: a body layer sampled from the band colour, then dark overlapping leaves in the
    #    bright parts and glowing leaves in the dim parts
    area = float(inside.sum())
    n = int(density * area / (leaf * leaf * 0.5) * 0.9)
    sel = np.flatnonzero(inside.ravel())
    if n > 0 and len(sel):
        pick = rng.choice(sel, min(n, len(sel)), replace=False)
        py, px = np.unravel_index(pick, inside.shape)
        vv = v[py, px]
        col = jitter(ramp(greens, np.clip(vv + rng.normal(0, 0.05, len(px)), 0, 1), gpos), rng, dl=0.03, dc=0.1,
                     dh=0.05)
        ang = rng.uniform(0, 2 * np.pi, len(px))
        order = np.argsort(vv)
        dabs(cv, (px + x0 - cv.m)[order], (py + y0 - cv.m)[order], (leaf * rng.uniform(0.7, 1.3, len(px)))[order],
             col[order], aspect=rng.uniform(0.4, 0.6, len(px))[order], angle=ang[order], shape='leaf', edge=0.25,
             rag=0.25, bristle=0.15, split=0.1, opacity=0.9, mode='lock', rng=rng)
        # dark overlapping leaves where the light is strong (leaves stacked against the light)
        m = int(len(px) * 0.35 * dark_leaves)
        if m:
            bright = np.flatnonzero(vv > 0.45)
            if len(bright):
                j = rng.choice(bright, min(m, len(bright)), replace=False)
                dv = np.clip(vv[j] - rng.uniform(0.25, 0.45, len(j)), 0, 1)
                dc = jitter(ramp(greens, dv, gpos), rng, dl=0.02, dc=0.08)
                dabs(cv, px[j] + x0 - cv.m + rng.normal(0, leaf * 0.3, len(j)),
                     py[j] + y0 - cv.m + rng.normal(0, leaf * 0.3, len(j)), leaf * rng.uniform(0.7, 1.2, len(j)), dc,
                     aspect=rng.uniform(0.38, 0.55, len(j)), angle=rng.uniform(0, 2 * np.pi, len(j)), shape='leaf',
                     edge=0.22, rag=0.2, bristle=0.1, opacity=0.9, mode='lock', rng=rng)
        # glowing translucent leaves scattered in dimmer parts near the light
        m = int(len(px) * 0.12 * glow_leaves)
        if m:
            cand = np.flatnonzero((vv > 0.12) & (vv < 0.6) & (Lp[py, px] > 0.35) & (dist[py, px] < leaf * 2.5))
            if len(cand):
                j = rng.choice(cand, min(m, len(cand)), replace=False)
                gc = jitter(ramp(greens, np.clip(vv[j] + rng.uniform(0.25, 0.45, len(j)), 0, 1), gpos), rng, dl=0.03)
                dabs(cv, px[j] + x0 - cv.m, py[j] + y0 - cv.m, leaf * rng.uniform(0.7, 1.15, len(j)), gc,
                     aspect=rng.uniform(0.4, 0.55, len(j)), angle=rng.uniform(0, 2 * np.pi, len(j)), shape='leaf',
                     edge=0.25, rag=0.2, bristle=0.1, split=0.12, opacity=0.95, mode='lock', rng=rng)
    # 3. leaves breaking the silhouette (outward), coloured by the local transmitted light
    cb = cv2.GaussianBlur(c, (0, 0), max(leaf * 0.5, 1.5))
    gx = cv2.Sobel(cb, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(cb, cv2.CV_32F, 0, 1, ksize=3)
    gn = np.hypot(gx, gy) + 1e-6
    nx, ny = -gx / gn, -gy / gn
    band = (cb > 0.15) & (cb < 0.7)
    sel = np.flatnonzero(band.ravel())
    ne = int(band.sum() / (leaf * 1.2))
    if ne and len(sel):
        pick = rng.choice(sel, min(ne, len(sel)), replace=False)
        py, px = np.unravel_index(pick, band.shape)
        onx, ony = nx[py, px], ny[py, px]
        ix = np.clip((px - onx * leaf).astype(int), 0, ww - 1)
        iy = np.clip((py - ony * leaf).astype(int), 0, hh - 1)
        vv = np.clip(v[iy, ix] * rng.uniform(0.8, 1.25, len(px)), 0, 1)
        col = jitter(ramp(greens, vv, gpos), rng, dl=0.03, dc=0.1, dh=0.05)
        out = leaf * rng.uniform(0.0, 0.6, len(px))
        ang = np.arctan2(ony, onx) + rng.normal(0, 0.6, len(px))
        order = np.argsort(vv)
        dabs(cv, (px + onx * out + x0 - cv.m)[order], (py + ony * out + y0 - cv.m)[order],
             (leaf * rng.uniform(0.75, 1.25, len(px)))[order], col[order],
             aspect=rng.uniform(0.38, 0.55, len(px))[order], angle=ang[order], shape='leaf', edge=0.25, rag=0.2,
             bristle=0.1, split=0.1, rng=rng)
    # 4. rim per mass: none, a few scattered hot leaves, or a soft glow - never a continuous line
    if rim_amt > 0 and lp is not None:
        style = rr.choice(3, nm, p=[0.4, 0.3, 0.3])             # 0 none, 1 sparse hot leaves, 2 soft glow
        rcol = rr.integers(0, len(RIMS), nm)
        tx, ty = lp[0] - X, lp[1] - Y
        tn = np.hypot(tx, ty) + 1e-6
        face = np.clip(nx * tx / tn + ny * ty / tn, 0, 1)
        sty = np.where(mid >= 0, style[np.maximum(mid, 0)], 0)
        hot = (sty == 1) & (cb > 0.3) & (cb < 0.7) & (face > 0.4)
        soft = (sty == 2) & (cb > 0.25) & (cb < 0.9) & (face > 0.2)
        for msk, sz, op, per in ((hot, (6, 12), (0.6, 1.0), 45), (soft, (24, 48), (0.1, 0.22), 60)):
            sel = np.flatnonzero(msk.ravel())
            k = int(rim_amt * len(sel) / per)
            if not k:
                continue
            pick = rng.choice(sel, min(k, len(sel)), replace=False)
            py, px = np.unravel_index(pick, msk.shape)
            ci = rcol[np.maximum(mid[py, px], 0)]
            col = jitter(np.array([RIMS[i] for i in ci], np.float32), rng, dl=0.03, dc=0.08)
            col = mix(col, ramp(greens, np.full(len(px), 0.85), gpos), rng.uniform(0.15, 0.5, len(px))[:, None])
            ang = rng.uniform(0, 2 * np.pi, len(px))
            dabs(cv, px + x0 - cv.m, py + y0 - cv.m, rng.uniform(*sz, len(px)), col,
                 aspect=rng.uniform(0.4, 0.6, len(px)) if sz[0] < 20 else rng.uniform(0.6, 1.0, len(px)), angle=ang,
                 shape='leaf' if sz[0] < 20 else 'round', edge=0.3 if sz[0] < 20 else 0.95, rag=0.3, bristle=0.2,
                 opacity=rng.uniform(*op, len(px)) * Lp[py, px] ** 0.5, mode='lock', rng=rng)
    return dict(v=v, box=(x0, y0, x1, y1))


def haze_veil(cv, rng, centre, radii, col, k_in=0.9, k_out=2.2, n=140, opacity=(0.04, 0.1), size=(120, 380)):
    """A layer of warm glowing air around the gap: soft round strokes, denser and brighter near the gap."""
    cx, cy = centre
    rx, ry = radii
    a = rng.uniform(0, 2 * np.pi, n)
    k = k_in + (k_out - k_in) * rng.random(n) ** 1.6
    xs = cx + np.cos(a) * rx * k
    ys = cy + np.sin(a) * ry * k
    fall = np.clip(1.3 - 0.45 * k, 0.15, 1)
    cols = jitter(np.broadcast_to(col, (n, 3)), rng, dl=0.02, dc=0.06)
    dabs(cv, xs, ys, rng.uniform(*size, n), cols, aspect=rng.uniform(0.35, 0.7, n), angle=a + np.pi / 2,
         opacity=rng.uniform(*opacity, n) * fall, edge=0.95, rag=0.4, bristle=0.45, rng=rng)


def light_shafts(cv, rng, centre, radii, col, n=9, length=(500, 1100), width=(40, 120), opacity=0.16):
    """Soft shafts radiating from the gap rim toward the frame edges (light through the canopy)."""
    cx, cy = centre
    rx, ry = radii
    for i in range(n):
        a = rng.uniform(0, 2 * np.pi)
        p0 = np.array([cx + np.cos(a) * rx * 0.8, cy + np.sin(a) * ry * 0.8])
        L = rng.uniform(*length)
        p1 = p0 + L * np.array([np.cos(a), np.sin(a)])
        t = np.linspace(0, 1, 10)
        P = p0[None] * (1 - t[:, None]) + p1[None] * t[:, None]
        w = rng.uniform(*width)
        stroke(cv, P, w * (0.5 + 1.2 * t), col, opacity=opacity * np.sin(np.pi * np.clip(t * 1.1, 0, 1)) ** 0.7,
               edge=0.9, bristle=0.6, rag=0.2, spacing=8.0, rng=rng)
