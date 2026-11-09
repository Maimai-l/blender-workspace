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
from ..foliage import Blobs
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
    for row in range(9):
        y = 575 + row * 40 + rng.normal(0, 8)
        r0 = 26 + row * 8
        for x in np.arange(-80, W + 80, r0 * 0.85):
            xx = x + rng.normal(0, r0 * 0.35)
            yy = y + rng.normal(0, r0 * 0.3) + 18 * np.sin(xx / 210 + row)
            e = ((xx - gx) / 175) ** 2 + ((yy - gy) / 72) ** 2
            if e < 1.0:
                continue                                          # the gap
            kind = str(rng.choice(KINDS, p=[0.68, 0.12, 0.1, 0.1]))
            r = r0 * rng.uniform(0.75, 1.3) * (1.3 if kind == 'emergent' else 1.0)
            lt = rng.uniform(0.85, 1.1) * (0.75 if e < 2.2 and yy > gy else 1.0)   # the gap's far wall in shade
            rows.append((yy, xx, r, lt, kind, rng.normal(0, 0.06)))
    rows.sort(key=lambda t: t[0])
    for yy, xx, r, lt, kind, hue in rows:
        add_crown(b, rng, xx, yy, r, kind, lt, hue)
    d = 0.35
    ccols = (aerial(C(34, 46, 70), d, HAZE), aerial(C(52, 80, 80), d, HAZE), aerial(C(120, 140, 96), d * 0.6, HAZE),
             aerial(C(236, 210, 140), d * 0.3, HAZE))
    paint_planes(cv, rng, b, ccols, light3=(0.8, -0.5, 0.25), th=(0.42, 0.64, 0.86), strokes=1.2, stroke_size=9,
                 rim=C(255, 222, 156), rim_amt=1.0, sun2=(0.85, -0.5), leafy_edge=0.45, noise_amt=0.08, leaf_px=7,
                 glob=0.0, form=0.0, soft=0.015, wrap=0.3, stroke_dl=0.06, stroke_op=(0.35, 0.7))
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
    b = Blobs()
    for x in np.arange(-120, W + 160, 115):
        top = 950 + 70 * np.sin(x / 300 + 1.4) + rng.normal(0, 25)
        kind = str(rng.choice(KINDS, p=[0.55, 0.25, 0.1, 0.1]))
        add_crown(b, rng, x + rng.normal(0, 30), top + 40, rng.uniform(90, 150), kind, rng.uniform(0.85, 1.1),
                  rng.normal(0, 0.05))
        add_crown(b, rng, x + rng.normal(0, 60) + 75, top + 130, rng.uniform(100, 160), 'round', 1.0,
                  rng.normal(0, 0.05))
        add_crown(b, rng, x + rng.normal(0, 40), top + 230, rng.uniform(120, 170), 'round', 0.9, rng.normal(0, 0.05))
    ncols = (C(26, 30, 50), C(38, 52, 64), C(70, 92, 74), C(220, 190, 120))
    paint_planes(cv, rng, b, ncols, light3=(0.7, -0.6, -0.1), th=(0.5, 0.72, 0.9), strokes=1.0, stroke_size=16,
                 rim=C(255, 214, 140), rim_amt=1.0, sun2=(0.8, -0.6), leafy_edge=0.6, noise_amt=0.06, leaf_px=16,
                 glob=0.0, form=0.0, soft=0.015, wrap=0.3, stroke_dl=0.05, stroke_op=(0.35, 0.7))
    P.add('near', 0.85, cv, 'dark backlit treetops along the bottom edge with warm rims')

    P.save(sun=list(SUN), gap=list(GAP), camera='slow pan left -> right over 4.5 s (any 1920-wide window)')
    return P
