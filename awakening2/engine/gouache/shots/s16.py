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
from ..sky import sky, cumulus_blobs, paint_clouds, sun_disc, sculpted_blobs, sculpted_cloud, plane_cloud, paint_planes
from ..atmos import mist, glow

W, H, M = 2400, 1040, 160
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


PLANES = (C(150, 112, 162), C(238, 168, 132), C(255, 214, 148), C(255, 244, 212))


def planes(d):
    return tuple(aerial(c, d, HAZE) for c in PLANES)


def build(outdir, quick=False):
    P = Painting('S16', W, H, M, outdir)
    rng = rng_for('S16')

    # ---------------------------------------------------------------- sky
    cv = P.layer('sky', 0.0)
    # an amber-to-blue dawn: clear blue-violet high up (strongest at the upper left, away from the sun),
    # lilac-rose, peach, then amber and gold down to the cloud sea; the whole sky warms toward the sun
    stops = [C(70, 92, 168), C(104, 118, 186), C(160, 146, 196), C(222, 168, 172), C(248, 184, 132),
             C(255, 198, 112), C(255, 214, 136), C(255, 226, 168)]
    pos = [0.0, 0.08, 0.2, 0.32, 0.44, 0.54, 0.64, 1.0]
    X, Y = cv.coords()
    dsun = np.hypot(X - SUN[0], (Y - SUN[1]) * 1.15)
    warp = (fbm(cv.shape[0], cv.shape[1], 700, rng, octaves=3) - 0.5) * 0.04
    t = Y / float(H) + 0.1 * (X / float(W) - 0.5) + 0.14 * np.exp(-(dsun / 900.0) ** 2) + warp
    base = ramp(stops, np.clip(t, 0, 1), pos)
    # warm glow around the sun: amber far out, gold nearer, pale cream at the core
    for (r_, col_, k_) in [(1300, C(255, 196, 120), 0.45), (650, C(255, 214, 140), 0.55), (260, C(255, 238, 196), 0.7)]:
        g_ = np.exp(-(dsun / r_) ** 2) * k_
        base = mix(base, col_, g_[..., None])
    cv.img[..., :3] = base
    cv.img[..., 3] = 1.0
    # brushed over with broad strokes that sample the sky (paint, not a gradient)
    n = 900
    xs = rng.uniform(-0.05, 1.05, n) * W
    ys = rng.uniform(-0.05, 0.75, n) * H
    ix = np.clip((xs + cv.m).astype(int), 0, cv.shape[1] - 1)
    iy = np.clip((ys + cv.m).astype(int), 0, cv.shape[0] - 1)
    cols = jitter(base[iy, ix], rng, dl=0.02, dc=0.1, dh=0.04)
    for k in range(n):
        L = rng.uniform(260, 900)
        a_ = -0.06 + rng.normal(0, 0.05)
        dx_, dy_ = np.cos(a_) * L / 2, np.sin(a_) * L / 2
        stroke(cv, [[xs[k] - dx_, ys[k] - dy_], [xs[k], ys[k] + rng.normal(0, 8)], [xs[k] + dx_, ys[k] + dy_]],
               taper(12, 0.35, 0.25, rng.uniform(24, 80)), cols[k], opacity=rng.uniform(0.25, 0.55), edge=0.55,
               bristle=0.6, rag=0.25, spacing=6.0, rng=rng)
    # long thin high cloud streaks in the upper left (cool lilac bodies, warm undersides)
    for k in range(7):
        y0 = rng.uniform(60, 330)
        x0 = rng.uniform(-100, 1100)
        L = rng.uniform(500, 1100)
        if trail_dist(x0 + L / 2, y0) < 140:
            continue
        n_ = 10
        xs_ = np.linspace(x0, x0 + L, n_)
        ys_ = y0 + np.cumsum(rng.normal(0, 6, n_)) - np.linspace(0, L * 0.06, n_)
        th = rng.uniform(8, 22)
        base_c = mix(C(150, 140, 196), C(222, 172, 176), (y0 / 330))
        for j in range(5):
            off = (j - 2) * th * 0.35
            c = mix(base_c, C(255, 214, 170), np.clip(j / 4, 0, 1) * 0.8)
            stroke(cv, np.stack([xs_ + rng.normal(0, 10, n_), ys_ + off], 1), taper(n_, 0.2, 0.1, th * rng.uniform(0.5, 1.0)),
                   jitter(c, rng, 1, dl=0.02)[0], opacity=rng.uniform(0.25, 0.55), edge=0.6, bristle=0.7, rag=0.3,
                   rng=rng)
    # the sun: a painted halo (soft concentric bands of warm light, brushed), a bright disc with a hot core
    for (rr_, col_, op_, n_) in [(300, C(255, 222, 160), 0.1, 50), (190, C(255, 234, 184), 0.16, 40),
                                 (120, C(255, 244, 214), 0.24, 30)]:
        aa = rng.uniform(0, 2 * np.pi, n_)
        rd = rr_ * np.sqrt(rng.uniform(0.3, 1.0, n_))
        dabs(cv, SUN[0] + np.cos(aa) * rd * 0.6, SUN[1] + np.sin(aa) * rd * 0.6, rng.uniform(rr_ * 0.6, rr_ * 1.1, n_),
             jitter(np.broadcast_to(col_, (n_, 3)), rng, dl=0.02, dc=0.06), aspect=rng.uniform(0.7, 1.0, n_),
             angle=rng.uniform(0, np.pi, n_), opacity=op_, edge=0.95, rag=0.35, bristle=0.4, rng=rng)
    glow(cv, SUN[0], SUN[1], 150, C(255, 246, 220), 0.55)
    sun_disc(cv, SUN[0], SUN[1], 52, col=C(255, 252, 238), halo=C(255, 236, 190), rng=rng)
    dabs(cv, [SUN[0]], [SUN[1]], [72], C(255, 255, 248), aspect=1.0, edge=0.35, rag=0.0, bristle=0.0, rng=rng)
    P.add('sky', 0.0, cv, 'amber-to-blue dawn sky; bright sun disc with a painted halo at upper right '
          '(where the trail ends); opaque')

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
        plane_cloud(cv, rng, cx, by, w_, h_, planes(0.2), kind=kind, light3=(0.7, -0.6, 0.3), rim=C(255, 246, 214),
                    wisps=0.5)
    P.add('high_clouds', 0.08, cv, 'large sculpted cloud forms + soft lenses, upper left (clear of the trail)')

    # ---------------------------------------------------------------- far ridge
    cv = P.layer('ridge', 0.15)
    xs = np.linspace(1060, 2460, 300)
    ridge = 590 - 200 * np.exp(-((xs - 1700) / 230) ** 2) - 120 * np.exp(-((xs - 2200) / 170) ** 2) \
        - 40 * np.exp(-((xs - 1380) / 140) ** 2) + (noise1d(300, 26, rng) - 0.5) * 34 + (noise1d(300, 90, rng) - 0.5) * 10
    ridge += 60 * smoothstep(1300, 1060, xs)
    col_sh = C(150, 138, 186)
    col_lit = C(246, 196, 170)
    # broad planes: a flat lilac body, lit facets on the sun-facing slopes cut by gullies, a crisp crest
    X, Y = cv.coords()
    rx = np.interp(X[0], xs, ridge, left=900, right=900)[None, :]
    inside = (Y >= rx) & (Y < 760) & (X >= xs[0])
    a_ = np.clip((Y - rx) / 1.2, 0, 1) * inside
    tt = np.clip((Y - rx) / 170, 0, 1)
    body = aerial(col_sh, 0.1, HAZE)
    cv.over(mix(body, HAZE, (tt * 0.55)[..., None]), a_)
    slope = np.gradient(np.convolve(ridge, np.ones(9) / 9, mode='same'))
    face = np.clip(slope / 2.0, 0, 1)                                   # right-facing slopes face the sun
    litc0 = aerial(col_lit, 0.05, HAZE)
    # the sunlit faces: many curved, irregular brush strokes running down the fall lines
    for i in range(0, 300, 2):
        if face[i] < 0.12 or rng.random() < 0.25:
            continue
        x0, y0 = xs[i] + rng.normal(0, 3), ridge[i] + rng.uniform(2, 10)
        L = (40 + 150 * rng.random() ** 0.7) * (0.5 + face[i])
        n = 5
        t = np.linspace(0, 1, n)
        bend = rng.normal(0, 0.25)
        px = x0 - L * (0.55 + bend) * t + np.cumsum(rng.normal(0, 4, n))
        py = y0 + L * t + np.cumsum(rng.normal(0, 3, n))
        k = float(np.clip(0.3 + 0.7 * face[i] - 0.25 * rng.random(), 0, 1))
        col = jitter(mix(body, litc0, k), rng, 1, dl=0.025, dc=0.08, dh=0.03)[0]
        stroke(cv, np.stack([px, py], 1), taper(n, 0.7, 0.15, rng.uniform(9, 24)), col,
               opacity=rng.uniform(0.45, 0.85), edge=0.35, bristle=0.55, rag=0.4, mode='lock', rng=rng)
    # shadow-side texture: cooler strokes on the left-facing slopes
    for i in range(0, 300, 3):
        if face[i] > 0.05 or rng.random() < 0.4:
            continue
        x0, y0 = xs[i], ridge[i] + rng.uniform(4, 30)
        L = rng.uniform(40, 140)
        n = 4
        t = np.linspace(0, 1, n)
        px = x0 + L * 0.45 * t + np.cumsum(rng.normal(0, 4, n))
        py = y0 + L * t
        stroke(cv, np.stack([px, py], 1), taper(n, 0.6, 0.2, rng.uniform(8, 18)),
               jitter(mix(body, aerial(C(118, 104, 164), 0.1, HAZE), 0.5), rng, 1, dl=0.02)[0],
               opacity=rng.uniform(0.3, 0.6), edge=0.4, bristle=0.55, rag=0.4, mode='lock', rng=rng)
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
    # a continuous painted cloud deck first (so gaps between mounds show cloud, not sky)
    from ..soft import mist_strokes
    Yd = cv.ys()[:, None] * np.ones((1, cv.shape[1]), np.float32)
    deck = smoothstep(628, 660, Yd)
    tdeck = np.clip((Yd - 640) / 400, 0, 1)
    dcol = mix(mix(np.broadcast_to(planes(0.3)[2], Yd.shape + (3,)), planes(0.2)[1], (tdeck * 0.6)[..., None]),
               planes(0.2)[0], (tdeck ** 2 * 0.5)[..., None])
    cv.over(dcol, deck.astype(np.float32))
    for (y0d, y1d, n_, wdt) in [(632, 700, 120, (14, 40)), (690, 830, 120, (24, 70)), (820, 1060, 110, (40, 110))]:
        mist_strokes(cv, rng, -200, W + 200, y0d, y1d, planes(0.2)[3], planes(0.2)[0], n_,
                     light=lambda x, y: np.clip(0.25 + 0.6 * (x / W) - 0.3 * ((y - 640) / 400), 0, 1), width=wdt,
                     length=(300, 900), opacity=(0.25, 0.55), profile='flat')
    # irregular cumulus mounds of varied scale, receding in perspective (not rows of blocks)
    for band, (y0b, y1b, s0, s1, dd) in enumerate([(615, 690, 0.25, 0.55, 0.36), (680, 800, 0.45, 1.0, 0.28),
                                                   (780, 960, 0.8, 1.7, 0.2)]):
        b = Blobs()
        x = -200.0
        items = []
        while x < W + 200:
            sc = float(np.exp(rng.uniform(np.log(s0), np.log(s1))))
            w_ = 260 * sc * rng.uniform(0.6, 1.4)
            h_ = w_ * rng.uniform(0.18, 0.42)
            yb = rng.uniform(y0b, y1b)
            items.append((yb, x + w_ / 2, w_, h_))
            x += w_ * rng.uniform(0.45, 0.85)
        items.sort(key=lambda t: t[0])
        for yb, cx, w_, h_ in items:
            sculpted_blobs(rng, cx, yb, w_, h_, kind='cumulus' if rng.random() < 0.65 else 'strato', blobs=b)
        paint_planes(cv, rng, b, planes(dd), light3=(0.6, -0.7, 0.35), th=(0.3, 0.52, 0.8), soft=0.09, wrap=0.6,
                     rim=C(255, 246, 214), rim_amt=0.6, strokes=0.6, stroke_size=10 + 8 * band, noise_amt=0.05,
                     wisps=0.4, form=0.0)
    yy = cv.ys()[:, None]
    cv.lock_tint(HAZE, (smoothstep(760, 600, yy) * 0.45 * np.ones((1, cv.shape[1]))).astype(np.float32))
    P.add('cloud_sea', 0.3, cv, 'the far sea of clouds: irregular cumulus of varied scale in perspective')

    # ---------------------------------------------------------------- mid cumulus (right, below the diagonal)
    cv = P.layer('clouds_mid', 0.5)
    for (cx, by, w_, h_, kind) in [(1300, 830, 520, 170, 'cumulus'), (2120, 800, 640, 200, 'cumulus'),
                                   (850, 880, 520, 90, 'strato')]:
        plane_cloud(cv, rng, cx, by, w_, h_, planes(0.1), kind=kind, light3=(0.65, -0.7, 0.3), rim=C(255, 246, 214),
                    wisps=0.4, soft=0.08, wrap=0.6, form=0.0)
    P.add('clouds_mid', 0.5, cv, 'sculpted cumulus banks rising from the sea (right half)')

    # ---------------------------------------------------------------- near cumulus (bottom right)
    cv = P.layer('clouds_near', 0.75)
    for (cx, by, w_, h_, kind) in [(1760, 1120, 900, 330, 'cumulus'), (2330, 1080, 520, 360, 'cumulus'),
                                   (1120, 1110, 520, 170, 'strato')]:
        plane_cloud(cv, rng, cx, by, w_, h_, planes(0.0), kind=kind, light3=(0.65, -0.7, 0.3), rim=C(255, 248, 222),
                    wisps=0.5, soft=0.08, wrap=0.6, form=0.0)
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
    paint_planes(cv, rng, b, (C(58, 42, 78), C(84, 92, 82), C(184, 166, 84), C(255, 222, 130)),
                 light3=(0.75, -0.55, 0.3), th=(0.4, 0.62, 0.86), strokes=0.4, rim=C(255, 226, 150), rim_amt=1.2,
                 sun2=SUN2, leafy_edge=0.7, leaf_cols=[C(58, 42, 78), C(110, 110, 76), C(230, 200, 110)],
                 noise_amt=0.08)
    mist(cv, rng, -60, 900, 940, 1080, C(255, 230, 196), C(214, 196, 214), density=0.8, opacity=(0.05, 0.14),
         size=(120, 360), aspect=(0.12, 0.25), profile='bottom')
    P.add('fg', 1.0, cv, 'forest canopy tops at the bottom-left edge (the launch point of the trail)')

    P.save(sun=list(SUN), trail_diagonal=[list(TRAIL[0]), list(TRAIL[1])],
           camera='slow pan across 2400 px; any 1920-wide window is composed')
    return P
