"""atmos.py - mist, sunbeams, glows, dappled light, aerial perspective passes.

mist(cv, ...)        a mist bank built from many soft, low-opacity horizontal
                     strokes (visible brushwork), warm cream where lit and
                     lilac-grey in shade, density from a vertical profile and noise.
beams(cv, ...)       painted sunbeams: long soft streaky strokes fanning from a
                     source, fading along their length.
glow(cv, ...)        soft light bloom (used sparingly: sun, mist glow).
dapple(cv, ...)      sunlight patches on the ground (perspective-flattened).
haze_pass(cv, ...)   alpha-locked tint toward a haze colour by a (H, W) amount.
"""
import numpy as np

from .canvas import dabs, stroke, catmull, taper
from .color import C, mix, jitter, ramp, smoothstep
from .noise import fbm


def mist(cv, rng, x0, x1, y0, y1, col_lit, col_shade, light=None, density=1.0, opacity=(0.04, 0.12),
         size=(120, 420), aspect=(0.12, 0.3), profile='bottom', angle=0.0, noise_scale=500,
         bristle=0.5, n_mult=1.0):
    """Mist bank in the box. light: callable (x, y) -> 0..1 warmth/brightness.
    profile: 'bottom' (denser at y1), 'top', 'mid' or 'flat'."""
    W = x1 - x0
    H = y1 - y0
    n = int(n_mult * density * W * H / (np.mean(size) ** 2 * np.mean(aspect)) * 3.0)
    xs = rng.uniform(x0 - size[1] * 0.3, x1 + size[1] * 0.3, n)
    u = rng.random(n)
    if profile == 'bottom':
        ys = y0 + H * (1 - u ** 1.8)
    elif profile == 'top':
        ys = y0 + H * u ** 1.8
    elif profile == 'mid':
        ys = y0 + H * (0.5 + (rng.beta(2.2, 2.2, n) - 0.5))
    else:
        ys = y0 + H * u
    # horizontal density modulation (banks and gaps)
    nz = fbm(64, 256, 40, rng, octaves=3)
    ix = np.clip(((xs - x0) / max(W, 1) * 255).astype(int), 0, 255)
    iy = np.clip(((ys - y0) / max(H, 1) * 63).astype(int), 0, 63)
    keep = rng.random(n) < (0.25 + 0.75 * nz[iy, ix])
    xs, ys = xs[keep], ys[keep]
    n = len(xs)
    lt = light(xs, ys) if light is not None else np.full(n, 0.5, np.float32)
    cols = jitter(mix(col_shade, col_lit, np.clip(lt, 0, 1)[:, None]), rng, dl=0.02, dc=0.08, dh=0.04)
    sz = rng.uniform(*size, n)
    dabs(cv, xs, ys, sz, cols, aspect=rng.uniform(*aspect, n), angle=angle + rng.normal(0, 0.04, n),
         opacity=rng.uniform(*opacity, n) * (0.6 + 0.6 * np.clip(lt, 0, 1)), edge=0.95, rag=0.4,
         bristle=bristle, shape='round', rng=rng)


def beams(cv, rng, src, angles, length, widths, col, opacity=0.18, spread_w=1.6, streak=0.6,
          start_fade=0.08, end_len=0.85, edge=0.9):
    """Sunbeams from src (x, y) at the given angles (radians, image coords)."""
    for a, w in zip(angles, widths):
        L = length * rng.uniform(0.8, 1.1)
        k = 24
        t = np.linspace(0, 1, k)
        pts = np.stack([src[0] + np.cos(a) * L * t, src[1] + np.sin(a) * L * t], 1)
        wd = w * (0.6 + spread_w * t)
        op = opacity * smoothstep(0, start_fade, t) * (1 - smoothstep(end_len * 0.6, 1.0, t)) * rng.uniform(0.6, 1.1)
        c = jitter(np.broadcast_to(col, (k, 3)), rng, dl=0.01, dc=0.05, dh=0.02)
        stroke(cv, pts, wd, c, opacity=op, edge=edge, bristle=streak, rag=0.1, smooth=True,
               spacing=8.0, rng=rng)


def glow(cv, x, y, r, col, strength=0.5, squash=1.0):
    X, Y = cv.coords()
    d = np.hypot(X - x, (Y - y) / squash) / r
    a = np.exp(-d * d) * strength
    cv.over(col, np.clip(a, 0, 1))


def dapple(cv, rng, xs, ys, size, col, flatten=0.35, opacity=(0.5, 0.9), cluster=5, angle=0.0,
           mode='over', edge=0.6):
    """Sun patches: clusters of soft ellipses flattened by perspective."""
    xs = np.asarray(xs, np.float32)
    ys = np.asarray(ys, np.float32)
    size = np.broadcast_to(np.asarray(size, np.float32), xs.shape)
    cluster = cluster * 2
    m = len(xs) * cluster
    rep = np.repeat(np.arange(len(xs)), cluster)
    px = xs[rep] + rng.normal(0, 0.45, m) * size[rep]
    py = ys[rep] + rng.normal(0, 0.45, m) * size[rep] * flatten
    sz = size[rep] * rng.uniform(0.45, 0.95, m)
    edge = max(edge, 0.75)
    cols = jitter(np.broadcast_to(col, (m, 3)), rng, dl=0.03, dc=0.1, dh=0.04)
    dabs(cv, px, py, sz, cols, aspect=flatten * rng.uniform(0.8, 1.3, m), angle=angle + rng.normal(0, 0.1, m),
         opacity=rng.uniform(*opacity, m), edge=edge, rag=0.6, bristle=0.2, rng=rng, mode=mode)


def haze_pass(cv, col, amount):
    """Alpha-locked tint of the whole layer toward col by amount (scalar/(H,W))."""
    cv.lock_tint(col, amount)


def _edge_alpha(dist_px, rng_noise, paper, soft=1.4, dry=0.6):
    """Hard painted edge: a short ramp (soft px) broken up by the paper tooth (dry brush)."""
    a = np.clip(dist_px / soft + 0.5, 0, 1)
    if dry > 0:
        # within ~6 px of the edge the paint catches only the raised tooth of the paper
        near = np.clip(1 - dist_px / 6.0, 0, 1)
        brk = np.clip((paper + rng_noise * 0.6 - 0.35 * near) * 3.0, 0, 1)
        a = a * (1 - dry * near * (1 - brk))
    return a


def ground_stripes(cv, rng, vp, stripes, col, y_min, opacity=0.9, texture=1.0, lock=True):
    """Sunlit stripes on the ground between cast shadows (backlit scene): each stripe is a wedge
    radiating from the vanishing point vp (the point on the horizon under the sun) toward the
    camera, given as (angle_centre, angle_width, r_start) in radians/px. Hard, dry-brush edges,
    a flat warm fill with brush strokes along the stripe; only where the layer already has paint
    (lock) and below y_min."""
    from .canvas import PAPER
    from .noise import fbm
    h, w = cv.shape
    X, Y = cv.coords()
    dx, dy = X - vp[0], Y - vp[1]
    r = np.hypot(dx, dy) + 1e-6
    th = np.arctan2(dy, dx)
    ph, pw = PAPER.shape
    pap = PAPER[(np.arange(h) - cv.m)[:, None] % ph, (np.arange(w) - cv.m)[None, :] % pw]
    nz = fbm(h, w, 60, rng, octaves=2) - 0.5
    A = np.zeros((h, w), np.float32)
    for (tc, tw, r0) in stripes:
        d_ang = tw / 2 - np.abs(np.angle(np.exp(1j * (th - tc))))
        dist = d_ang * r                                      # px inside the wedge's side edges
        dist = np.minimum(dist, (r - r0) * 0.6)               # soft start near the horizon
        a = _edge_alpha(dist, nz, pap)
        A = np.maximum(A, a)
    A *= (Y > y_min)
    if lock:
        A *= np.clip(cv.img[..., 3], 0, 1)
    A = (A * opacity).astype(np.float32)
    # fill: warm, slightly varied along the stripe (brighter in the middle distance)
    t = np.clip((r - 40) / 900, 0, 1)
    cc = mix(np.broadcast_to(col, (h, w, 3)), C(255, 236, 190), (np.sin(np.pi * np.clip(t * 1.3, 0, 1)) * 0.35)[..., None])
    cv.over(cc, A)
    if texture > 0:
        # strokes along the stripes (dry brush): sample points inside the light
        sel = np.flatnonzero((A > 0.4).ravel())
        if len(sel):
            n = min(len(sel), int(texture * len(sel) / 260))
            pick = rng.choice(sel, n, replace=False)
            py, px = np.unravel_index(pick, A.shape)
            ang = th[py, px] + rng.normal(0, 0.03, n)
            rr = r[py, px]
            cols = jitter(mix(np.broadcast_to(col, (n, 3)), C(255, 240, 200), rng.uniform(0, 0.6, n)[:, None]), rng,
                          dl=0.04, dc=0.12, dh=0.04)
            dabs(cv, px - cv.m, py - cv.m, 10 + rr * rng.uniform(0.03, 0.08, n), cols, aspect=rng.uniform(0.12, 0.25, n),
                 angle=ang, shape='flat', edge=0.4, rag=0.4, bristle=0.6, dry=0.35,
                 opacity=rng.uniform(0.25, 0.6, n), mode='lock', rng=rng)
    return A


def clean_shaft(cv, rng, apex, ang, half_w, r0, r1, col, opacity=0.18, fade_in=0.2, fade_out=0.25, streaks=6):
    """A painted translucent light shaft with clean edges: a wedge from apex (the sun or a gap)
    at angle ang with angular half width half_w, visible from r0 to r1 px; flat fill fading in
    at the top and out at the bottom, a few faint streaks along it, edges crisp (not a gradient)."""
    X, Y = cv.coords()
    dx, dy = X - apex[0], Y - apex[1]
    r = np.hypot(dx, dy) + 1e-6
    th = np.arctan2(dy, dx)
    d_ang = half_w - np.abs(np.angle(np.exp(1j * (th - ang))))
    dist = d_ang * r
    a = np.clip(dist / 1.5 + 0.5, 0, 1)
    t = np.clip((r - r0) / max(r1 - r0, 1), 0, 1)
    prof = np.clip(t / fade_in, 0, 1) * np.clip((1 - t) / fade_out, 0, 1) * (r > r0) * (r < r1)
    a = (a * prof * opacity).astype(np.float32)
    cv.over(np.asarray(col, np.float32), a)
    for k in range(streaks):
        u = rng.uniform(-0.8, 0.8)
        aa = ang + u * half_w
        L0 = r0 + (r1 - r0) * rng.uniform(0.15, 0.35)
        L1 = r0 + (r1 - r0) * rng.uniform(0.6, 0.85)
        p0 = (apex[0] + np.cos(aa) * L0, apex[1] + np.sin(aa) * L0)
        p1 = (apex[0] + np.cos(aa) * L1, apex[1] + np.sin(aa) * L1)
        stroke(cv, [p0, p1], max(half_w * (L0 + L1) * 0.12, 3), mix(col, C(255, 252, 236), 0.5),
               opacity=opacity * rng.uniform(0.35, 0.7), edge=0.6, bristle=0.7, rag=0.2, rng=rng)


def floor_light(cv, rng, vp, shadows, warm_col, cool_col, y_min, r_light=60.0, warm_amt=0.6, cool_amt=0.3,
                lift=0.12, texture=1.0):
    """Backlit floor light as light minus cast shadows. shadows: list of (angle_lo, angle_hi, r_start) wedges
    radiating from vp (shadows of trunks start at the trunk base, far ones at the horizon). The lit part is
    tinted warm and lifted (texture kept), the shadowed part tinted cool; every edge is hard with dry-brush
    breakup. Returns the light mask."""
    from .canvas import PAPER
    from .noise import fbm
    h, w = cv.shape
    X, Y = cv.coords()
    dx, dy = X - vp[0], Y - vp[1]
    r = np.hypot(dx, dy) + 1e-6
    th = np.arctan2(dy, dx)
    ph, pw = PAPER.shape
    pap = PAPER[(np.arange(h) - cv.m)[:, None] % ph, (np.arange(w) - cv.m)[None, :] % pw]
    nz = fbm(h, w, 60, rng, octaves=2) - 0.5
    Lt = np.clip((r - r_light) / 40.0, 0, 1) * (Y > y_min)
    for (lo, hi, r0) in shadows:
        tc, tw = (lo + hi) / 2, (hi - lo)
        d_ang = tw / 2 - np.abs(np.angle(np.exp(1j * (th - tc))))
        dist = np.minimum(d_ang * r, (r - r0) * 0.8)          # inside the shadow wedge (px)
        sa = _edge_alpha(dist, nz, pap, soft=1.4, dry=0.5)
        Lt = Lt * (1 - sa)
    Lt = (Lt * np.clip(cv.img[..., 3], 0, 1)).astype(np.float32)
    flo = (np.clip(cv.img[..., 3], 0, 1) * (Y > y_min)).astype(np.float32)
    cv.lock_tint(cool_col, (flo * (1 - Lt) * cool_amt).astype(np.float32))
    cv.lock_tint(warm_col, (Lt * warm_amt).astype(np.float32))
    if lift > 0:
        cv.img[..., :3] += (Lt * lift)[..., None] * cv.img[..., 3:4]
        np.minimum(cv.img[..., :3], cv.img[..., 3:4], out=cv.img[..., :3])
    if texture > 0:
        sel = np.flatnonzero((Lt > 0.5).ravel())
        if len(sel):
            n = min(len(sel), int(texture * len(sel) / 300))
            pick = rng.choice(sel, n, replace=False)
            py, px = np.unravel_index(pick, Lt.shape)
            ang = th[py, px] + rng.normal(0, 0.03, n)
            rr = r[py, px]
            cols = jitter(mix(np.broadcast_to(warm_col, (n, 3)), C(255, 238, 196), rng.uniform(0, 0.5, n)[:, None]),
                          rng, dl=0.04, dc=0.12, dh=0.04)
            dabs(cv, px - cv.m, py - cv.m, 8 + rr * rng.uniform(0.03, 0.07, n), cols, aspect=rng.uniform(0.12, 0.25, n),
                 angle=ang, shape='flat', edge=0.4, rag=0.4, bristle=0.6, dry=0.4,
                 opacity=rng.uniform(0.2, 0.5, n), mode='lock', rng=rng)
    return Lt


def light_stripes(cv, rng, vp, stripes, warm_col, y_min, warm_amt=0.6, lift=0.1, cool_col=None, cool_amt=0.0,
                  texture=1.0, blades=1.0, occluders=()):
    """Painterly sunlit stripes on a shaded floor (backlit). stripes: (angle_centre, angle_width, r_start, r_end).
    Each stripe's width wanders with the ground (low-frequency noise along it), it is broken into segments by
    small shadows (clumps, stones), its far end dissolves, and its edges are hard with dry-brush breakup. The
    floor texture is kept (warm tint + lift); grass blades standing in the light catch it."""
    from .canvas import PAPER
    from .noise import fbm, noise1d
    h, w = cv.shape
    X, Y = cv.coords()
    dx, dy = X - vp[0], Y - vp[1]
    r = np.hypot(dx, dy) + 1e-6
    th = np.arctan2(dy, dx)
    ph, pw = PAPER.shape
    pap = PAPER[(np.arange(h) - cv.m)[:, None] % ph, (np.arange(w) - cv.m)[None, :] % pw]
    nz = fbm(h, w, 50, rng, octaves=2) - 0.5
    A = np.zeros((h, w), np.float32)
    RMAX = 2400
    for (tc, tw, r0, r1) in stripes:
        wob = 1 + 0.35 * (noise1d(RMAX, 9, rng) - 0.5) * 2 + 0.18 * (noise1d(RMAX, 40, rng) - 0.5) * 2 \
            + 0.12 * (noise1d(RMAX, 160, rng) - 0.5) * 2
        cen = (noise1d(RMAX, 6, rng) - 0.5) * 2 * tw * 0.25
        ri = np.clip(r.astype(int), 0, RMAX - 1)
        half = tw / 2 * wob[ri]
        d_ang = half - np.abs(np.angle(np.exp(1j * (th - tc - cen[ri]))))
        dist = d_ang * r
        a = _edge_alpha(dist, nz, pap, soft=1.3, dry=0.65)
        # far end dissolves into the mist, near end may stop short
        a *= np.clip((r - r0) / 60.0, 0, 1) * np.clip((r1 - r) / 120.0, 0, 1)
        # small shadows break the stripe into segments
        for k in range(int(rng.integers(1, 4))):
            rc = rng.uniform(r0 + 80, r1 - 60)
            ln = rng.uniform(15, 60) * (rc / 400)
            gap = np.clip((np.abs(r - rc) - ln) / 4.0, 0, 1)
            side = rng.uniform(-0.6, 0.6)
            part = np.clip((np.angle(np.exp(1j * (th - tc))) / max(tw / 2, 1e-4) - side) * 4, 0, 1) \
                if rng.random() < 0.5 else 0.0
            a *= np.maximum(gap, part)
        A = np.maximum(A, a)
    # cast shadows of near objects cut the stripes beyond them: (angle_lo, angle_hi, r_start)
    for (lo, hi, r0s) in occluders:
        tc, tw = (lo + hi) / 2, (hi - lo)
        d_ang = tw / 2 - np.abs(np.angle(np.exp(1j * (th - tc))))
        dist = np.minimum(d_ang * r, (r - r0s) * 1.0)
        A = A * (1 - _edge_alpha(dist, nz, pap, soft=1.3, dry=0.5))
    A = (A * (Y > y_min) * np.clip(cv.img[..., 3], 0, 1)).astype(np.float32)
    # mottled light inside the stripes (litter, unevenness), brighter toward the sun
    mot = fbm(h, w, 26, rng, octaves=2)
    A = A * (0.72 + 0.28 * mot) * (0.85 + 0.15 * np.clip(1 - (r - 200) / 1400, 0, 1))
    if cool_col is not None and cool_amt > 0:
        flo = (np.clip(cv.img[..., 3], 0, 1) * (Y > y_min)).astype(np.float32)
        cv.lock_tint(cool_col, (flo * (1 - A) * cool_amt).astype(np.float32))
    cv.lock_tint(warm_col, (A * warm_amt).astype(np.float32))
    if lift > 0:
        cv.img[..., :3] += (A * lift)[..., None] * cv.img[..., 3:4]
        np.minimum(cv.img[..., :3], cv.img[..., 3:4], out=cv.img[..., :3])
    sel = np.flatnonzero((A > 0.5).ravel())
    if texture > 0 and len(sel):
        n = min(len(sel), int(texture * len(sel) / 320))
        pick = rng.choice(sel, n, replace=False)
        py, px = np.unravel_index(pick, A.shape)
        ang = th[py, px] + rng.normal(0, 0.04, n)
        rr = r[py, px]
        cols = jitter(mix(np.broadcast_to(warm_col, (n, 3)), C(255, 236, 190), rng.uniform(0, 0.5, n)[:, None]), rng,
                      dl=0.04, dc=0.12, dh=0.04)
        dabs(cv, px - cv.m, py - cv.m, 8 + rr * rng.uniform(0.025, 0.06, n), cols, aspect=rng.uniform(0.12, 0.25, n),
             angle=ang, shape='flat', edge=0.4, rag=0.45, bristle=0.6, dry=0.4, opacity=rng.uniform(0.2, 0.5, n),
             mode='lock', rng=rng)
    edge_band = np.flatnonzero(((A > 0.15) & (A < 0.6)).ravel())
    if blades > 0 and len(edge_band):
        n = min(len(edge_band), int(blades * len(edge_band) / 120))
        pick = rng.choice(edge_band, n, replace=False)
        py, px = np.unravel_index(pick, A.shape)
        sc = np.clip((py - cv.m - y_min) / 400.0, 0.2, 1.4)
        for i in range(n):
            x0, y0 = px[i] - cv.m, py[i] - cv.m
            hgt = rng.uniform(10, 26) * sc[i]
            lean = rng.normal(0, 0.4)
            stroke(cv, [[x0, y0], [x0 + lean * hgt * 0.5, y0 - hgt * 0.6], [x0 + lean * hgt, y0 - hgt]],
                   taper(3, 1.0, 0.0, max(2.0 * sc[i], 1.2)), jitter(C(40, 40, 62), rng, 1, dl=0.03)[0],
                   opacity=0.85, edge=0.3, bristle=0.2, rng=rng)
    if blades > 0 and len(sel):
        n = min(len(sel), int(blades * len(sel) / 900))
        pick = rng.choice(sel, n, replace=False)
        py, px = np.unravel_index(pick, A.shape)
        sc = np.clip((py - cv.m - y_min) / 400.0, 0.2, 1.4)
        for i in range(n):
            x0, y0 = px[i] - cv.m, py[i] - cv.m
            hgt = rng.uniform(8, 22) * sc[i]
            lean = rng.normal(0, 0.35)
            stroke(cv, [[x0, y0], [x0 + lean * hgt * 0.5, y0 - hgt * 0.6], [x0 + lean * hgt, y0 - hgt]],
                   taper(3, 1.0, 0.0, max(1.5 * sc[i], 1.0)), jitter(C(255, 226, 150), rng, 1, dl=0.04)[0],
                   opacity=0.85, edge=0.3, bristle=0.2, rng=rng)
    return A
