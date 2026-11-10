"""S00 - establishing vista (2200 x 1040, slow pan left -> right).

The forest at sunrise seen from above the canopy: layered forested ridges fading with
aerial perspective, a sea of mist lying in the valleys, the sun just rising at the upper
right with a gold glow, a few sculpted clouds lit from below. In the middle distance
(x ~1100-1400, y ~620) a gap in the canopy where mist swirls up and a shaft of light falls
in: the clearing where the robot kneels (no robot). Painted in flat planes, not dabs.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, fbm, noise1d
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, spray
from ..sky import sky, plane_cloud, paint_planes, sculpted_blobs
from ..atmos import mist, beams, glow

W, H, M = 2200, 1040, 64
SUN = (1930.0, 300.0)
GAP = (1250.0, 640.0)
HAZE = C(244, 214, 200)
MIST_LIT = C(255, 236, 204)
MIST_SH = C(204, 184, 210)


def ridge_profile(rng, base, amp, n_peaks, x0=-100, x1=W + 100, rough=0.12):
    xs = np.linspace(x0, x1, 600)
    y = np.full_like(xs, base, dtype=np.float32)
    for k in range(n_peaks):
        cx = rng.uniform(x0, x1)
        wdt = rng.uniform(140, 420)
        y -= amp * rng.uniform(0.4, 1.0) * np.exp(-((xs - cx) / wdt) ** 2)
    y += (noise1d(600, 40, rng) - 0.5) * amp * rough * 2 + (noise1d(600, 140, rng) - 0.5) * amp * rough * 0.6
    return xs, y


def paint_ridge(cv, rng, xs, ys, bottom, body, lit, top_bumps, bump_r, d, crown_cols, rim=None):
    """A forested ridge: flat body plane, lit right-facing slopes, a crown-bumped top edge
    (tree crowns painted as planes), mist fading at its foot."""
    X, Y = cv.coords()
    yl = np.interp(X[0], xs, ys)[None, :]
    inside = (Y >= yl) & (Y <= bottom)
    slope = np.gradient(np.interp(X[0], xs, ys))
    litk = np.clip(slope / 2.5, 0, 1)[None, :] * smoothstep(80, 0, Y - yl)
    col = mix(np.broadcast_to(body, Y.shape + (3,)), lit, (litk * 0.7)[..., None])
    a = np.clip((Y - yl) / 1.5, 0, 1) * inside
    cv.over(col, a)
    # crowns along the crest
    b = Blobs()
    if top_bumps > 0:
        for x in np.arange(xs[0], xs[-1], bump_r * 1.3):
            xx = x + rng.normal(0, bump_r * 0.3)
            yy = float(np.interp(xx, xs, ys)) + rng.uniform(-0.2, 0.5) * bump_r
            r = bump_r * rng.uniform(0.7, 1.3)
            b.add(xx, yy, r, r * rng.uniform(0.7, 0.95), light=rng.uniform(0.9, 1.1), rng=rng, lumpy=0.18)
        paint_planes(cv, rng, b, crown_cols, light3=(0.75, -0.55, 0.2), th=(0.38, 0.62, 0.86), strokes=0.0,
                     rim=rim, rim_amt=0.8, sun2=(0.85, -0.5), noise_amt=0.06)


def add_crown(b, rng, x, y, r, kind, lt=1.0, hue=0.0):
    """One tree crown (seen slightly from above) of a given kind into Blobs b.
    round: a lumpy cluster of 5-9 domes; spire: a conifer of narrowing stacked tiers with
    a pointed top; flat: an umbrella crown (wide, flat top, few lobes); emergent: a tall
    two-storey crown above the rest."""
    if kind == 'spire':
        h = r * rng.uniform(2.2, 3.0)
        n = int(rng.integers(4, 7))
        for j in range(n):
            t = j / (n - 1)
            w = r * (0.75 - 0.6 * t) * rng.uniform(0.85, 1.1)
            b.add(x + rng.normal(0, r * 0.05), y - t * h * 0.62, w, w * 0.7, rot=rng.normal(0, 0.08),
                  light=lt * rng.uniform(0.9, 1.05), hue=hue + 0.1, val=-0.03, rng=rng, lumpy=0.3)
        b.add(x, y - h * 0.7, r * 0.14, r * 0.26, light=lt, hue=hue + 0.1, val=-0.03, rng=rng, lumpy=0.2)
    elif kind == 'flat':
        for j in range(int(rng.integers(2, 4))):
            b.add(x + rng.normal(0, r * 0.4), y - r * 0.2 + rng.normal(0, r * 0.08), r * rng.uniform(0.7, 1.0),
                  r * rng.uniform(0.28, 0.38), rot=rng.normal(0, 0.05), light=lt * rng.uniform(0.95, 1.1),
                  hue=hue - 0.05, val=0.02, rng=rng, lumpy=0.22)
    elif kind == 'emergent':
        add_crown(b, rng, x, y, r * 0.9, 'round', lt * 0.9, hue)
        add_crown(b, rng, x + rng.normal(0, r * 0.2), y - r * 1.1, r * 0.75, 'round', lt * 1.05, hue + 0.04)
    else:
        for j in range(int(rng.integers(7, 12))):
            rr = r * rng.uniform(0.38, 0.62)
            aa = rng.uniform(-np.pi, np.pi)
            rd = r * 0.5 * np.sqrt(rng.random())
            b.add(x + np.cos(aa) * rd, y + np.sin(aa) * rd * 0.8, rr, rr * rng.uniform(0.75, 0.95),
                  rot=rng.uniform(0, np.pi), light=lt * rng.uniform(0.85, 1.1), hue=hue + rng.normal(0, 0.04),
                  val=rng.normal(0, 0.04), rng=rng, lumpy=0.24)


KINDS = ['round', 'spire', 'flat', 'emergent']


def snag(cv, rng, x, y_base, h, col, rim_col=None, w0=None):
    """A dead tree in silhouette: a crooked, tapering trunk with a broken top, and a few branches that
    curve up and fork into thin twigs (recursive); a thin warm rim on the sun side (right)."""
    w0 = w0 or rng.uniform(12, 18)
    n = 9
    t = np.linspace(0, 1, n)
    xs = x + np.cumsum(rng.normal(0, 7, n)) + np.sin(t * rng.uniform(2, 4) + rng.uniform(0, 6)) * h * 0.05
    ys = y_base - t * h
    trunk = np.stack([xs, ys], 1)
    wd = w0 * (1 - 0.65 * t) * (1 + 0.35 * np.exp(-t / 0.08))
    stroke(cv, trunk, wd, col, edge=0.3, bristle=0.4, rag=0.5, rng=rng)
    # broken top: a jagged splinter
    tp = trunk[-1]
    stroke(cv, [tp, tp + [rng.normal(0, 4), -w0 * 0.9]], taper(2, 1.0, 0.0, wd[-1] * 0.9), col, rng=rng)
    if rim_col is not None:
        stroke(cv, trunk + [wd[:, None].mean() * 0.0 + 0, 0] + np.stack([wd * 0.38, np.zeros(n)], 1),
               wd * 0.22, rim_col, opacity=0.55, edge=0.5, bristle=0.5, rag=0.4, rng=rng)

    def branch(p0, ang, L, wb, depth):
        k = 5
        pts = [np.asarray(p0, np.float32)]
        a = ang
        for i in range(k):
            a += rng.normal(0, 0.22) - 0.12 * np.cos(a)            # branches curve upward (toward -y)
            pts.append(pts[-1] + L / k * np.array([np.cos(a), np.sin(a)], np.float32))
        pts = np.array(pts)
        stroke(cv, pts, taper(len(pts), 1.0, 0.15, wb), col, edge=0.3, bristle=0.3, rag=0.4, rng=rng)
        if depth < 2:
            for j in range(int(rng.integers(1, 3))):
                i = int(rng.integers(2, k + 1))
                branch(pts[i], a + rng.choice([-1, 1]) * rng.uniform(0.4, 0.9), L * rng.uniform(0.4, 0.65),
                       max(wb * 0.55, 1.2), depth + 1)

    for j in range(int(rng.integers(3, 6))):
        tt = rng.uniform(0.35, 0.92)
        i = int(tt * (n - 1))
        sd = rng.choice([-1, 1])
        ang = -np.pi / 2 + sd * rng.uniform(0.6, 1.25)
        branch(trunk[i], ang, h * rng.uniform(0.18, 0.35) * (1.1 - tt * 0.5), max(wd[i] * 0.45, 2.0), 0)


def shade_dark(c, dl):
    from ..color import shade
    return np.clip(shade(c, dl=dl), 0, 1)


def crest_trees(cv, rng, xs, ys, scale, kind_p, body, lit, edge_px=1.0):
    """Broken ridge silhouette: crowns of varied size along the crest (mostly rounded, some
    short tiered conifers), occasional dips and gaps; lit sliver on the sun side."""
    x = xs[0]
    while x < xs[-1]:
        r = scale * float(np.exp(rng.normal(0, 0.4)))
        kind = rng.choice(['round', 'spire', 'gap'], p=kind_p)
        y = float(np.interp(x, xs, ys)) + rng.uniform(0, 0.4) * r
        if kind == 'gap':
            x += r * rng.uniform(0.8, 2.0)
            continue
        col = jitter(body, rng, 1, dl=0.015, dc=0.06)[0]
        lc = jitter(lit, rng, 1, dl=0.02)[0]
        if kind == 'spire':
            nt = int(rng.integers(3, 5))
            for j in range(nt):
                t = j / (nt - 1)
                w = r * (1.0 - 0.75 * t)
                dabs(cv, [x + rng.normal(0, r * 0.05)], [y - t * r * 1.6], [w * 1.4], col, aspect=0.55,
                     angle=rng.normal(0, 0.05), edge=0.25, rag=0.6, bristle=0.3, rng=rng)
            dabs(cv, [x + r * 0.3], [y - r * 0.6], [r * 0.9], lc, aspect=0.3, angle=-1.2, edge=0.45, rag=0.5,
                 bristle=0.4, opacity=0.5, mode='lock', rng=rng)
        else:
            k = int(rng.integers(2, 5))
            dabs(cv, x + rng.normal(0, r * 0.4, k), y - r * 0.3 + rng.normal(0, r * 0.18, k),
                 r * rng.uniform(1.0, 1.6, k), col, aspect=rng.uniform(0.75, 0.95, k), edge=0.25, rag=0.65,
                 bristle=0.3, rng=rng)
            dabs(cv, [x + r * 0.4], [y - r * 0.45], [r * 0.9], lc, aspect=0.45, angle=-0.7, edge=0.45, rag=0.5,
                 bristle=0.4, opacity=0.5, mode='lock', rng=rng)
        x += r * rng.uniform(0.55, 1.1)


def build(outdir, quick=False):
    P = Painting('S00', W, H, M, outdir)
    rng = rng_for('S00')

    # ---------------------------------------------------------------- sky
    cv = P.layer('sky', 0.0)
    stops = [C(150, 140, 196), C(204, 162, 190), C(242, 186, 164), C(255, 208, 140), C(255, 226, 168),
             C(255, 236, 196)]
    sky(cv, rng, stops, [0.0, 0.14, 0.3, 0.44, 0.56, 1.0], sun=SUN, glow=(900, C(255, 232, 170), 1.0), tilt=0.1,
        n_strokes=0.8, stroke_w=(24, 80), stroke_len=(260, 900), angle=-0.04)
    glow(cv, SUN[0], SUN[1], 90, C(255, 252, 236), 0.95)
    glow(cv, SUN[0], SUN[1], 360, C(255, 236, 180), 0.45)
    # clouds lit from below by the low sun (gold undersides, rose-lilac tops)
    ccols = (C(170, 136, 182), C(226, 166, 160), C(255, 206, 150), C(255, 238, 200))
    for (cx, by, w_, h_, kind) in [(420, 250, 760, 130, 'strato'), (1050, 150, 520, 90, 'strato'),
                                   (260, 120, 380, 70, 'cumulus'), (1500, 260, 420, 80, 'strato')]:
        plane_cloud(cv, rng, cx, by, w_, h_, ccols, kind=kind, light3=(0.85, 0.35, 0.25),
                    rim=C(255, 240, 200), wisps=0.4, strokes=0.5)
    P.add('sky', 0.0, cv, 'sunrise sky, sun just rising upper right, clouds lit from below; opaque')

    # ---------------------------------------------------------------- far ridges (4 layers of aerial perspective)
    cv = P.layer('far', 0.15)
    specs = [(430, 120, 0.84, 13), (470, 150, 0.68, 16), (520, 140, 0.52, 19), (565, 110, 0.38, 23)]
    for i, (base, amp, d, br) in enumerate(specs):
        xs, ys = ridge_profile(rng, base, amp, 4, rough=0.08)
        body = aerial(C(60, 76, 104), d, HAZE)
        lit = aerial(C(214, 176, 146), d * 0.7, HAZE)
        crowns = (aerial(C(52, 68, 96), d, HAZE), aerial(C(74, 94, 106), d, HAZE),
                  aerial(C(150, 146, 128), d, HAZE), aerial(C(236, 204, 156), d * 0.7, HAZE))
        paint_ridge(cv, rng, xs, ys, base + 300, body, lit, 0, br, d, crowns, rim=None)
        mixes = [[0.8, 0.05, 0.15], [0.6, 0.3, 0.1], [0.75, 0.15, 0.1], [0.65, 0.25, 0.1]]
        crest_trees(cv, rng, xs, ys, br * 0.9, mixes[i], body, lit)
        # brush texture on the ridge body: slanted strokes along the slopes (alpha-locked)
        nst = 140
        sx_ = rng.uniform(-100, W + 100, nst)
        sy_ = np.interp(sx_, xs, ys) + rng.uniform(10, 160, nst)
        sl = np.gradient(ys)[np.clip(((sx_ - xs[0]) / (xs[-1] - xs[0]) * (len(xs) - 1)).astype(int), 0, len(xs) - 1)]
        tcol = jitter(mix(np.broadcast_to(body, (nst, 3)), lit, np.clip(sl / 3, 0, 0.6)[:, None]), rng, dl=0.02, dc=0.08)
        dabs(cv, sx_, sy_, rng.uniform(30, 80, nst), tcol, aspect=rng.uniform(0.15, 0.3, nst),
             angle=np.arctan(sl / 3.6) + rng.normal(0, 0.15, nst), shape='flat', edge=0.4, rag=0.4, bristle=0.6,
             opacity=rng.uniform(0.25, 0.5, nst), mode='lock', rng=rng)
        # bright mist lying in the valley at the foot of this ridge
        yy = cv.ys()[:, None]
        X = cv.xs()[None, :]
        k = smoothstep(base - 30, base + 40, yy) * np.ones_like(X)
        mc = mix(np.broadcast_to(MIST_SH, k.shape + (3,)), MIST_LIT, np.clip(0.2 + 0.8 * X / W, 0, 1)[..., None] *
                 np.ones_like(k)[..., None])
        cv.over(mc, (k * 0.85).astype(np.float32))
        mist(cv, rng, -100, W + 100, base - 40, base + 30, MIST_LIT, MIST_SH,
             light=lambda x, y: np.clip(0.3 + 0.7 * (x / W), 0, 1), density=1.4, opacity=(0.1, 0.25),
             size=(180, 520), aspect=(0.08, 0.16), profile='bottom')
    P.add('far', 0.15, cv, 'four forested ridges fading with aerial perspective, mist in each valley')

    # ---------------------------------------------------------------- mist sea + the light shaft into the gap
    cv = P.layer('mist', 0.3)
    mist(cv, rng, -100, W + 100, 520, 700, MIST_LIT, MIST_SH, light=lambda x, y: np.clip(0.25 + 0.75 * (x / W), 0, 1),
         density=1.8, opacity=(0.08, 0.2), size=(200, 620), aspect=(0.07, 0.14), profile='mid')
    glow(cv, GAP[0], GAP[1] + 10, 230, C(255, 240, 206), 0.75, squash=0.45)
    ang = np.arctan2(GAP[1] - SUN[1], GAP[0] - SUN[0])
    beams(cv, rng, (SUN[0] - 120, SUN[1] - 40), [ang - 0.03, ang, ang + 0.035], 760, [60, 110, 50],
          C(255, 240, 200), opacity=0.42, spread_w=1.2, streak=0.5, start_fade=0.25, end_len=0.98)
    P.add('mist', 0.3, cv, 'the sea of mist in the valleys; glow and a shaft of light falling into the gap')

    # ---------------------------------------------------------------- mid canopy (the forest below us), with the gap
    cv = P.layer('mid', 0.55)
    b = Blobs()
    gx, gy = GAP
    rows = []
    # big-form light over the rolling canopy: ridges catch the sun, troughs sit in shadow and mist
    BF = fbm(400, 1100, 160, rng, octaves=3)

    def bigform(x, y):
        ix = int(np.clip(x / W * 1099, 0, 1099))
        iy = int(np.clip((y - 540) / 500 * 399, 0, 399))
        return float(BF[iy, ix])
    troughs = []
    for row in range(9):
        y = 575 + row * 40 + rng.normal(0, 8)
        r0 = 26 + row * 8
        for x in np.arange(-80, W + 80, r0 * 0.85):
            xx = x + rng.normal(0, r0 * 0.35)
            yy = y + rng.normal(0, r0 * 0.3) + 18 * np.sin(xx / 210 + row)
            e = ((xx - gx) / 175) ** 2 + ((yy - gy) / 72) ** 2
            if e < 1.35:
                continue                                          # the gap
            kind = str(rng.choice(KINDS, p=[0.68, 0.12, 0.1, 0.1]))
            r = r0 * rng.uniform(0.75, 1.3) * (1.3 if kind == 'emergent' else 1.0)
            f = bigform(xx, yy)
            lt = (0.32 + 0.95 * f ** 1.4) * rng.uniform(0.9, 1.1) * (0.75 if e < 2.2 and yy > gy else 1.0)
            if kind == 'emergent':
                lt = max(lt, 1.0)                                   # tall crowns rise into the light
            # local colour by species: young yellow-green, deep blue-green, olive, plain green
            hue = float(rng.choice([-0.12, 0.1, -0.05, 0.0])) + rng.normal(0, 0.03)
            rows.append((yy, xx, r, lt, kind, hue))
            if f < 0.35 and rng.random() < 0.45:
                troughs.append((xx, yy))
    rows.sort(key=lambda t: t[0])
    for yy, xx, r, lt, kind, hue in rows:
        add_crown(b, rng, xx, yy, r, kind, lt, hue)
    d = 0.35
    ccols = (aerial(C(34, 46, 70), d, HAZE), aerial(C(52, 80, 80), d, HAZE), aerial(C(120, 140, 96), d * 0.6, HAZE),
             aerial(C(236, 210, 140), d * 0.3, HAZE))
    paint_planes(cv, rng, b, ccols, light3=(0.8, -0.5, 0.35), th=(0.38, 0.62, 0.88), strokes=1.2, stroke_size=9,
                 rim=C(255, 222, 156), rim_amt=0.6, sun2=(0.85, -0.5), leafy_edge=0.45, noise_amt=0.1, leaf_px=7,
                 glob=0.0, form=0.0, soft=0.015, wrap=0.75, stroke_dl=0.06, stroke_op=(0.35, 0.7))
    # mist lying in the troughs of the canopy
    for (tx_, ty_) in troughs:
        dabs(cv, tx_ + rng.normal(0, 40, 4), ty_ + rng.normal(0, 10, 4), rng.uniform(90, 200, 4),
             jitter(mix(MIST_SH, MIST_LIT, np.clip(tx_ / W, 0, 1)), rng, 4, dl=0.02), aspect=rng.uniform(0.15, 0.3, 4),
             angle=rng.normal(0, 0.05, 4), opacity=rng.uniform(0.12, 0.25, 4), edge=0.95, rag=0.4, bristle=0.5, rng=rng)
    # thin mist pockets between the crown rows (cool left, warm right)
    for yb in (650, 720, 800):
        mist(cv, rng, -100, W + 100, yb - 20, yb + 25, MIST_LIT, MIST_SH,
             light=lambda x, y: np.clip(0.15 + 0.85 * (x / W), 0, 1), density=0.6, opacity=(0.04, 0.1),
             size=(160, 420), aspect=(0.06, 0.12), profile='mid')
    # mist swirling up out of the gap, in front of the canopy rim
    for k in range(9):
        t = k / 8
        cx = gx + np.sin(t * 5.5 + 0.6) * 50 * (1 - t) + rng.normal(0, 10)
        cy = gy - t * 230
        dabs(cv, cx + rng.normal(0, 30, 6), cy + rng.normal(0, 14, 6), rng.uniform(80, 200, 6) * (1 - 0.4 * t),
             jitter(mix(MIST_LIT, C(255, 248, 230), t), rng, 6, dl=0.02), aspect=rng.uniform(0.2, 0.4, 6),
             angle=rng.normal(0.4 * np.sin(t * 6), 0.2, 6), opacity=rng.uniform(0.1, 0.22, 6) * (1 - 0.6 * t),
             edge=0.95, rag=0.3, bristle=0.4, rng=rng)
    mist(cv, rng, -100, W + 100, 780, 960, MIST_LIT, MIST_SH, light=lambda x, y: np.clip(0.2 + 0.8 * (x / W), 0, 1),
         density=0.7, opacity=(0.04, 0.12), size=(200, 560), aspect=(0.07, 0.14), profile='mid')
    P.add('mid', 0.55, cv, 'the forest canopy below with the gap of the clearing (x~1250, y~640) and rising mist')

    # ---------------------------------------------------------------- near canopy silhouettes at the bottom edge
    cv = P.layer('near', 0.85)
    sil_cols = [C(30, 40, 46), C(24, 34, 52), C(36, 34, 54), C(28, 44, 42)]
    for row, (ybase, rr_, dark_k, rim_p) in enumerate([(915, (60, 120), 0.0, 0.35)]):
        groups = [Blobs(), Blobs(), Blobs()]
        x = -140.0
        while x < W + 160:
            r = rng.uniform(*rr_)
            kind = str(rng.choice(['round', 'round', 'spire', 'flat', 'snag'], p=[0.45, 0.2, 0.15, 0.1, 0.1]))
            top = ybase + 45 * np.sin(x / 260 + row * 2.0) + rng.normal(0, 22)
            if row == 1:
                # the front row: a broken skyline - occasional big tall crowns, long low stretches
                if rng.random() < 0.22:
                    r = r * rng.uniform(1.5, 2.1)
                    top -= r * rng.uniform(0.5, 0.9)
                elif rng.random() < 0.35:
                    r = r * rng.uniform(0.5, 0.75)
                    top += rng.uniform(30, 70)
            if kind == 'snag':
                c0 = jitter(sil_cols[1], rng, 1, dl=0.02)[0]
                if row == 0:
                    c0 = mix(c0, MIST_SH, 0.25)
                snag(cv, rng, x, top + 140, rng.uniform(220, 330), c0,
                     rim_col=mix(C(236, 200, 150), MIST_LIT, 0.3) if rng.random() < 0.6 else None)
                x += r * rng.uniform(0.8, 1.4)
                continue
            b = groups[int(rng.integers(0, 3))]
            if kind == 'spire':
                add_crown(b, rng, x, top + r * 0.6, r * 0.7, 'spire', rng.uniform(0.8, 1.1), 0.1)
            elif kind == 'flat':
                add_crown(b, rng, x, top + r * 0.2, r, 'flat', rng.uniform(0.8, 1.1), -0.05)
            else:
                add_crown(b, rng, x, top + r * 0.5, r, 'round', rng.uniform(0.75, 1.15), rng.normal(0, 0.06))
            # the body below each crown reaches the bottom edge
            for yy in np.arange(top + r, H + 220, r * 0.9):
                b.add(x + rng.normal(0, r * 0.3), yy, r * rng.uniform(0.9, 1.3), r * 0.8, light=0.6, rng=rng, lumpy=0.2)
            x += r * rng.uniform(0.9, 1.6) * (0.75 if row == 1 else 1.0)
            if row == 1 and rng.random() < 0.45:
                # leafy twigs breaking the top line (silhouetted, a few lit leaves)
                for j in range(int(rng.integers(1, 3))):
                    aa = -np.pi / 2 + rng.normal(0, 0.6)
                    spray(cv, x - r * rng.uniform(0.3, 1.0), top + r * rng.uniform(0.0, 0.3), aa, rng.uniform(70, 140),
                          rng.uniform(14, 22), C(22, 30, 40), C(70, 84, 64), rng, stem_col=C(22, 28, 38), droop=0.3,
                          sun2=(0.8, -0.6), curl=rng.normal(0, 0.5), rim=C(236, 200, 140) if rng.random() < 0.4 else None)
        for gi, b in enumerate(groups):
            if len(b) == 0:
                continue
            base = [C(30, 46, 44), C(24, 36, 54), C(34, 42, 56)][gi]
            if row == 0:
                base = mix(base, MIST_SH, 0.28)                    # the back row sits in thin mist
            if row == 1:
                base = shade_dark(base, -0.035)
            ncols = (shade_dark(base, 0.0), shade_dark(base, 0.06), mix(base, C(104, 120, 80), 0.5 - 0.2 * dark_k),
                     C(214, 190, 130))
            paint_planes(cv, rng, b, ncols, light3=(0.7, -0.6, -0.1), th=(0.5, 0.74, 0.93), strokes=1.4,
                         stroke_size=18, rim=[C(255, 214, 140), None, C(236, 200, 160)][gi],
                         rim_amt=rim_p * 2.2, sun2=(0.8, -0.6), leafy_edge=0.7, noise_amt=0.12, leaf_px=17 + 4 * row,
                         glob=0.0, form=0.0, soft=0.03, wrap=0.35, stroke_dl=0.07, stroke_op=(0.4, 0.8))
        if row == 0:
            # mist in the dips between the two rows: the valley shows between the near crowns
            for k in range(26):
                mx = rng.uniform(-60, W + 60)
                my = 960 + rng.normal(0, 25)
                dabs(cv, mx + rng.normal(0, 60, 3), my + rng.normal(0, 10, 3), rng.uniform(120, 260, 3),
                     jitter(mix(MIST_SH, MIST_LIT, np.clip(mx / W, 0, 1)), rng, 3, dl=0.02),
                     aspect=rng.uniform(0.12, 0.25, 3), angle=rng.normal(0, 0.04, 3),
                     opacity=rng.uniform(0.15, 0.3, 3), edge=0.95, rag=0.4, bristle=0.5, rng=rng)
    # ---- the front band: a low dark band of treetops with a finely broken top line (leaves and twigs,
    # not lumps), two big framing crowns at the corners, two dead snags against the mist
    xs_ = cv.xs()
    nw = len(xs_)
    top = 984 + 18 * (noise1d(nw, 9, rng) - 0.5) * 2 + 8 * (noise1d(nw, 40, rng) - 0.5) * 2 \
        - 150 * np.exp(-((xs_ + 60) / 300) ** 2) - 170 * np.exp(-((xs_ - 2260) / 320) ** 2)
    Xb, Yb = cv.coords()
    band = np.clip(Yb - top[None, :] + 0.5, 0, 1).astype(np.float32)
    tb = np.clip((Yb - top[None, :]) / 60.0, 0, 1)
    bcol = mix(np.broadcast_to(C(42, 56, 60), Yb.shape + (3,)), C(20, 28, 40), tb[..., None])
    cv.over(bcol, band)
    # brush texture inside the band (alpha-locked flat strokes)
    nst = 260
    sx = rng.uniform(-60, W + 60, nst)
    sy = np.interp(sx, xs_, top) + rng.uniform(6, 120, nst)
    dabs(cv, sx, sy, rng.uniform(30, 70, nst), jitter(np.broadcast_to(C(30, 42, 50), (nst, 3)), rng, dl=0.03, dc=0.15),
         aspect=rng.uniform(0.2, 0.4, nst), angle=rng.normal(0, 0.3, nst), shape='flat', edge=0.4, rag=0.5,
         bristle=0.6, opacity=rng.uniform(0.3, 0.6, nst), mode='lock', rng=rng)
    # leaves along the top line (small, irregular), a few lit on the sun side
    xl = np.arange(-60, W + 60, 6.0) + rng.normal(0, 2, len(np.arange(-60, W + 60, 6.0)))
    yl = np.interp(xl, xs_, top) + rng.uniform(-8, 10, len(xl))
    nl = len(xl)
    lit = (rng.random(nl) < 0.12 + 0.18 * (xl / W))
    lc = np.where(lit[:, None], jitter(np.broadcast_to(C(150, 150, 96), (nl, 3)), rng, dl=0.04),
                  jitter(np.broadcast_to(C(30, 42, 48), (nl, 3)), rng, dl=0.03))
    la = -np.pi / 2 + rng.normal(0, 0.9, nl)
    Ls = rng.uniform(10, 22, nl)
    dabs(cv, xl + np.cos(la) * Ls * 0.4, yl + np.sin(la) * Ls * 0.4, Ls, lc, aspect=0.45, angle=la, shape='leaf',
         edge=0.25, rag=0.25, split=0.1, rng=rng)
    # leafy twigs sticking up out of the band here and there
    for i in range(16):
        x0 = rng.uniform(150, W - 150)
        spray(cv, x0, float(np.interp(x0, xs_, top)) + 6, -np.pi / 2 + rng.normal(0, 0.45), rng.uniform(60, 120),
              rng.uniform(12, 18), C(24, 34, 42), C(80, 92, 66), rng, stem_col=C(22, 28, 38), droop=0.3,
              sun2=(0.8, -0.6), curl=rng.normal(0, 0.5), rim=C(236, 200, 140) if rng.random() < 0.35 else None)
    # two framing crowns at the bottom corners (dark, painted planes, rim on the sun side)
    for (cx, cy, R, rimc) in [(70, 900, 210, None), (2170, 880, 240, C(236, 196, 132))]:
        b = Blobs()
        for k in range(int(rng.integers(14, 20))):
            ang = rng.uniform(-np.pi, 0.3)
            rd = R * np.sqrt(rng.random())
            rr = R * rng.uniform(0.22, 0.42)
            b.add(cx + np.cos(ang) * rd, cy + np.sin(ang) * rd * 0.75, rr, rr * rng.uniform(0.75, 0.95),
                  rot=rng.uniform(0, np.pi), light=rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.04), rng=rng, lumpy=0.26)
        for k in range(8):                                   # the crown's body runs down out of frame
            b.add(cx + rng.normal(0, R * 0.4), cy + R * 0.4 + k * 40, R * 0.5, R * 0.4, light=0.5, rng=rng, lumpy=0.2)
        paint_planes(cv, rng, b, (C(18, 26, 38), C(28, 40, 48), C(60, 78, 64), C(206, 184, 126)),
                     light3=(0.7, -0.6, -0.1), th=(0.55, 0.78, 0.94), strokes=1.4, stroke_size=22, rim=rimc,
                     rim_amt=0.8 if rimc is not None else 0.0, sun2=(0.8, -0.6), leafy_edge=0.9, leaf_px=20,
                     noise_amt=0.12, glob=0.0, form=0.0, soft=0.03, wrap=0.3, stroke_dl=0.06, stroke_op=(0.4, 0.8))
    # two gnarled dead snags rising out of the band, silhouetted against the misty valley
    for (sx0, hh_) in [(640.0, 300.0), (1560.0, 250.0)]:
        snag(cv, rng, sx0, float(np.interp(sx0, xs_, top)) + 40, hh_, C(26, 32, 44), rim_col=C(214, 186, 150))
    P.add('near', 0.85, cv, 'near canopy: a misty back row of varied crowns, a low dark front band with a broken '
          'leafy top line, two framing corner crowns and two gnarled snags; '
          'branches against the misty valley, mist in the dips, rims on some crowns only')

    P.save(sun=list(SUN), gap=list(GAP), camera='slow pan left -> right over 4.5 s (any 1920-wide window)')
    return P
