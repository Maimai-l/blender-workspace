"""S16 - golden sky for the climax, 2400 x 1040 (slow pan).

Warm gold sunrise sky, sun upper right; a sea of sculpted cumulus below (gold
tops, lilac-violet undersides); a far ridge breaking through the sea under the
sun; forest canopy tops at the bottom-left edge. The diagonal from the lower
left to the upper right is kept calm for the light trail.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, shade, smoothstep
from ..noise import rng_for, fbm, noise1d
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass
from ..sky import sky, cumulus_blobs, paint_clouds, sun_disc, sculpted_blobs, sculpted_cloud
from ..atmos import mist, glow

W, H, M = 2400, 1040, 40
SUN = (2010.0, 205.0)
SUN2 = (0.75, -0.66)
TRAIL = ((140.0, 1010.0), (2080.0, 160.0))     # calm diagonal (lower-left -> upper-right)
HAZE = C(255, 222, 168)

CLOUD = [C(122, 94, 150), C(170, 118, 148), C(228, 156, 128), C(252, 198, 126), C(255, 224, 150),
         C(255, 246, 210)]
CLOUD_POS = [0.0, 0.2, 0.42, 0.66, 0.86, 1.0]


def trail_dist(x, y):
    (x0, y0), (x1, y1) = TRAIL
    dx, dy = x1 - x0, y1 - y0
    L = np.hypot(dx, dy)
    return np.abs((np.asarray(x) - x0) * dy - (np.asarray(y) - y0) * dx) / L


def below_trail(x, y):
    (x0, y0), (x1, y1) = TRAIL
    yl = y0 + (np.asarray(x) - x0) * (y1 - y0) / (x1 - x0)
    return np.asarray(y) > yl


def cloud_pal(d):
    return [aerial(c, d, HAZE) for c in CLOUD]


def build(outdir, quick=False):
    P = Painting('S16', W, H, M, outdir)
    rng = rng_for('S16')

    # ---------------------------------------------------------------- sky
    cv = P.layer('sky', 0.0)
    stops = [C(196, 164, 194), C(236, 180, 162), C(250, 198, 136), C(255, 210, 128), C(255, 222, 146),
             C(255, 232, 172), C(255, 236, 190)]
    pos = [0.0, 0.1, 0.24, 0.4, 0.55, 0.68, 1.0]
    sky(cv, rng, stops, pos, sun=SUN, glow=(1000, C(255, 238, 186), 1.0), tilt=0.12, n_strokes=0.8,
        stroke_w=(24, 80), stroke_len=(260, 900), angle=-0.06)
    glow(cv, SUN[0], SUN[1], 520, C(255, 236, 170), 0.35)
    # long thin high cloud streaks in the upper left (lilac tops, gold undersides)
    for k in range(7):
        y0 = rng.uniform(60, 330)
        x0 = rng.uniform(-100, 1100)
        L = rng.uniform(500, 1100)
        if trail_dist(x0 + L / 2, y0) < 140:
            continue
        n = 10
        xs = np.linspace(x0, x0 + L, n)
        ys = y0 + np.cumsum(rng.normal(0, 6, n)) - np.linspace(0, L * 0.06, n)
        th = rng.uniform(8, 22)
        base = mix(C(214, 170, 180), C(246, 196, 160), (y0 / 330))
        for j in range(5):
            off = (j - 2) * th * 0.35
            c = mix(base, C(255, 224, 180), np.clip(j / 4, 0, 1) * 0.8)
            stroke(cv, np.stack([xs + rng.normal(0, 10, n), ys + off], 1), taper(n, 0.2, 0.1, th * rng.uniform(0.5, 1.0)),
                   jitter(c, rng, 1, dl=0.02)[0], opacity=rng.uniform(0.25, 0.55), edge=0.6, bristle=0.7, rag=0.3,
                   rng=rng)
    sun_disc(cv, SUN[0], SUN[1], 46, rng=rng)
    glow(cv, SUN[0], SUN[1], 260, C(255, 244, 214), 0.6)
    P.add('sky', 0.0, cv, 'gold sunrise sky, sun at upper right; opaque')

    # ---------------------------------------------------------------- high clouds (upper left, calm)
    cv = P.layer('high_clouds', 0.08)
    # long soft lenses of altostratus: lilac bodies, gold sun-side edges, low contrast
    for k in range(9):
        cx = rng.uniform(-100, 1500)
        cy = rng.uniform(70, 400)
        if below_trail(cx, cy) or trail_dist(cx, cy) < 160:
            continue
        L = rng.uniform(300, 760)
        th = rng.uniform(14, 34) * (0.7 + cy / 400)
        n = 12
        t = np.linspace(-0.5, 0.5, n)
        xs = cx + t * L
        ys = cy + np.cumsum(rng.normal(0, 3, n)) - t * L * 0.05
        prof = np.sin(np.pi * (t + 0.5)) ** 0.7
        body = mix(C(214, 172, 190), C(246, 200, 168), cy / 400)
        for j in range(6):
            f = j / 5
            col = mix(body, C(255, 226, 186), f ** 1.5 * 0.85)
            off = (f - 0.4) * th * 0.9
            stroke(cv, np.stack([xs + rng.normal(0, 8, n), ys + off], 1), th * (0.25 + 0.75 * prof) * rng.uniform(0.6, 1.0),
                   jitter(col, rng, 1, dl=0.02)[0], opacity=rng.uniform(0.35, 0.6), edge=0.7, bristle=0.6, rag=0.35,
                   rng=rng)
    # a few large sculpted forms above the diagonal (flat bases, lit crowns)
    for (cx, by, w_, h_, kind) in [(420, 360, 900, 170, 'strato'), (980, 220, 520, 120, 'cumulus'),
                                   (120, 170, 420, 90, 'strato')]:
        sculpted_cloud(cv, rng, cx, by, w_, h_, cloud_pal(0.2), CLOUD_POS, kind=kind, light3=(0.75, -0.5, 0.12),
                       rim=C(255, 236, 190), rim_amt=0.8, tip=C(255, 248, 220))
    P.add('high_clouds', 0.08, cv, 'large sculpted cloud forms + soft lenses, upper left (clear of the trail)')

    # ---------------------------------------------------------------- far ridge
    cv = P.layer('ridge', 0.15)
    xs = np.linspace(1060, 2460, 300)
    ridge = 590 - 200 * np.exp(-((xs - 1700) / 230) ** 2) - 120 * np.exp(-((xs - 2200) / 170) ** 2) \
        - 40 * np.exp(-((xs - 1380) / 140) ** 2) + (noise1d(300, 26, rng) - 0.5) * 34 + (noise1d(300, 90, rng) - 0.5) * 10
    ridge += 60 * smoothstep(1300, 1060, xs)
    col_sh = C(150, 138, 186)
    col_lit = C(246, 196, 170)
    # block-in below the crest line, then strokes that follow the slopes (lit right-facing slopes)
    X, Y = cv.coords()
    rx = np.interp(X[0], xs, ridge, left=900, right=900)
    inside = (Y >= rx[None, :]) & (Y < 720) & (X >= xs[0])
    a_ = np.clip((Y - rx[None, :]) / 2.0, 0, 1) * inside
    tt = np.clip((Y - rx[None, :]) / 150, 0, 1)
    cv.over(mix(col_sh, HAZE, (tt * 0.5)[..., None]), a_)
    slope = np.gradient(ridge)
    for i in range(0, 300, 1):
        x = xs[i]
        top = ridge[i]
        lit = float(np.clip(slope[i] / 4.0, 0, 1))
        ang = float(np.arctan2(slope[i], xs[1] - xs[0]))
        n = int(rng.integers(3, 7))
        dy = rng.uniform(4, 120, n) ** 1.0
        t = np.clip(dy / 150, 0, 1)
        c = mix(mix(col_sh, col_lit, lit * (1 - t)[:, None] * 0.9), HAZE, (t * 0.5)[:, None])
        c = jitter(c, rng, dl=0.015, dc=0.08, dh=0.04)
        dabs(cv, x + rng.normal(0, 3, n), top + dy, rng.uniform(16, 34, n), c, aspect=0.28,
             angle=ang + np.pi / 2 * 0 + rng.normal(0, 0.15, n) + (np.pi / 2 if rng.random() < 0.3 else 0.0),
             edge=0.35, rag=0.35, bristle=0.5, shape='flat', rng=rng, mode='lock')
    # warm rim along the sunlit crest
    crest = np.stack([xs, ridge + 2], 1)
    seg = np.arange(0, 300, 2)
    for i in seg:
        j = min(i + 2, 299)
        if ridge[j] > ridge[i] - 1:      # descending toward the right = faces the sun
            stroke(cv, crest[i:j + 1], 3.0, C(255, 230, 186), opacity=0.8, bristle=0.3, rag=0.2, rng=rng, smooth=False)
    P.add('ridge', 0.15, cv, 'distant ridge breaking through the cloud sea under the sun')

    # ---------------------------------------------------------------- cloud sea (far)
    cv = P.layer('cloud_sea', 0.3)
    for (r0, r1, lf, dd) in [(0, 8, 9, 0.38), (8, 16, 17, 0.22)]:
        b = Blobs()
        for row in range(r0, r1):
            t = row / 15
            y = 615 + 430 * t ** 1.4
            r = 24 + 130 * t ** 1.6
            n = int(W / (r * 1.5)) + 3
            for x in np.linspace(-r, W + r, n) + rng.normal(0, r * 0.4, n):
                # gaps in the sea show the shadowed lower layer
                if rng.random() < 0.12:
                    continue
                b.add(x, y + rng.normal(0, r * 0.2), r * rng.uniform(1.2, 2.2), r * rng.uniform(0.42, 0.62),
                      rot=rng.normal(0, 0.05), light=rng.uniform(0.8, 1.05), val=rng.normal(0, 0.05), rng=rng,
                      lumpy=0.12)
        paint_clouds(cv, rng, b, cloud_pal(dd), CLOUD_POS, light3=(0.7, -0.6, 0.25), leaf=lf, density=0.4,
                     rim=C(255, 236, 196), rim_amt=0.6, edge=0.5, bands=5)
    yy = cv.ys()[:, None]
    cv.lock_tint(HAZE, (smoothstep(760, 600, yy) * 0.45 * np.ones((1, cv.shape[1]))).astype(np.float32))
    P.add('cloud_sea', 0.3, cv, 'the far sea of clouds')

    # ---------------------------------------------------------------- mid cumulus (right, below the diagonal)
    cv = P.layer('clouds_mid', 0.5)
    for (cx, by, w_, h_, kind) in [(1300, 830, 520, 170, 'cumulus'), (2120, 800, 640, 200, 'cumulus'),
                                   (850, 880, 520, 90, 'strato')]:
        sculpted_cloud(cv, rng, cx, by, w_, h_, cloud_pal(0.1), CLOUD_POS, kind=kind, light3=(0.7, -0.6, 0.15),
                       rim=C(255, 238, 200), rim_amt=0.9, tip=C(255, 248, 224))
    P.add('clouds_mid', 0.5, cv, 'sculpted cumulus banks rising from the sea (right half)')

    # ---------------------------------------------------------------- near cumulus (bottom right)
    cv = P.layer('clouds_near', 0.75)
    for (cx, by, w_, h_, kind) in [(1760, 1120, 900, 330, 'cumulus'), (2330, 1080, 520, 360, 'cumulus'),
                                   (1120, 1110, 520, 170, 'strato')]:
        sculpted_cloud(cv, rng, cx, by, w_, h_, cloud_pal(0.0), CLOUD_POS, kind=kind, light3=(0.7, -0.6, 0.18),
                       rim=C(255, 240, 204), rim_amt=1.0, tip=C(255, 250, 230))
    P.add('clouds_near', 0.75, cv, 'big near cumulus at the bottom right')

    # ---------------------------------------------------------------- canopy tops (bottom left)
    cv = P.layer('fg', 1.0)
    b = Blobs()
    for x in np.linspace(-80, 760, 15):
        yb = 900 + 160 * (x / 760) ** 1.6 + rng.normal(0, 18)
        for k in range(3):
            r = rng.uniform(55, 110) * (1.2 - 0.4 * x / 760)
            b.add(x + rng.normal(0, 40), yb + k * 55 + rng.normal(0, 15), r, r * 0.72, light=rng.uniform(0.85, 1.1),
                  hue=rng.normal(0, 0.06), val=rng.normal(0, 0.04), rng=rng, lumpy=0.2)
    G = render_gbuffer(cv, b, light3=(0.75, -0.55, 0.35), wrap=0.4, under=0.45)
    stops = [C(60, 40, 76), C(78, 66, 92), C(106, 108, 80), C(196, 170, 80), C(252, 210, 112)]
    paint_mass(cv, G, rng, stops, leaf=13, density=1.0, trans=C(230, 206, 96), trans_amt=0.4,
               rim=C(255, 214, 130), rim_amt=1.0, tip=C(255, 230, 150), tip_amt=0.25, sun2=SUN2, droop=0.3)
    mist(cv, rng, -60, 900, 940, 1080, C(255, 230, 196), C(214, 196, 214), density=0.8, opacity=(0.05, 0.14),
         size=(120, 360), aspect=(0.12, 0.25), profile='bottom')
    P.add('fg', 1.0, cv, 'forest canopy tops at the bottom-left edge (the launch point of the trail)')

    P.save(sun=list(SUN), trail_diagonal=[list(TRAIL[0]), list(TRAIL[1])],
           camera='slow pan across 2400 px; any 1920-wide window is composed')
    return P
