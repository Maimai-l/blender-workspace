"""S01 - tilt-down reveal, 1920 x 2900 (final framing = bottom 1040 px).

Top: giant crowns silhouetted around a canopy gap, dawn sky, sun upper right,
beams slanting down-left, bare perch branches. Middle: unique mossy trunks in
three depths with mist between. Bottom: misty clearing for the kneeling robot
(x 0.22-0.70, y 0.28-0.97 of the final frame), framed by two giant trunks.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, shade, smoothstep
from ..noise import rng_for, fbm
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass, spray, vine
from ..trees import (species, paint_tube, trunk_path, buttress_roots, crown_blobs, limb_fan, Frame,
                     MOSS, IVY)
from ..sky import sky, cumulus_blobs, paint_clouds, sculpted_cloud, plane_cloud
from ..atmos import mist, beams, glow, dapple
from ..ground import ground, fern, grass, stone, flowers
from ..forest import broadleaf, far_trunks, surface_roots

W, H, M = 1920, 2900, 48
SUN = (1330.0, 175.0)
L3 = (0.55, -0.78, -0.32)
SUN2 = (0.55, -0.83)
FE = 1860                                   # top of the final framing
ROBOT = (0.37 * W, FE + 0.18 * 1040, 0.73 * W, FE + 0.95 * 1040)
GAP = (1010.0, 300.0, 640.0, 420.0)         # canopy gap ellipse (cx, cy, rx, ry)
HAZE_W = C(255, 234, 202)
HAZE_C = C(216, 208, 226)
HAZE = C(236, 222, 216)

LEAF_NEAR = [C(20, 30, 48), C(28, 48, 62), C(44, 78, 72), C(98, 130, 72), C(170, 176, 86)]
TRANS = C(200, 204, 92)
RIM = C(255, 214, 140)


def in_gap(x, y, k=1.0):
    cx, cy, rx, ry = GAP
    return ((np.asarray(x) - cx) / (rx * k)) ** 2 + ((np.asarray(y) - cy) / (ry * k)) ** 2 < 1


def beam_light(x, y):
    a = np.arctan2(np.asarray(y) - SUN[1], np.asarray(x) - SUN[0])
    deg = np.degrees(a)
    return smoothstep(94, 100, deg) * (1 - smoothstep(118, 126, deg))


def warmth(x, y):
    x = np.asarray(x, np.float32)
    y = np.asarray(y, np.float32)
    clear = np.exp(-(((x - 920) / 760) ** 2 + ((y - 2430) / 420) ** 2))
    up = np.exp(-(((x - SUN[0]) / 900) ** 2 + ((y - SUN[1]) / 900) ** 2))
    return np.clip(0.15 + 0.7 * clear + 0.45 * beam_light(x, y) + 0.4 * up, 0, 1)


def pal_depth(stops, d, haze=HAZE):
    return [aerial(c, d, haze) for c in stops]


def crown_layer(cv, rng, anchors, d, leaf, rad, light_k=1.0, gap_k=0.92, levels=2, extra=None,
                density=1.0, trans_amt=0.55, rim_amt=0.7, haze=HAZE, along=True, limb_detail=0.5):
    """Crowns seen from below. anchors: list of (x, y, angles, lengths, width).
    Clusters sit at limb tips and along the outer half of the smaller limbs."""
    bark = species('camphor', depth=d, haze=haze)
    blobs = Blobs()
    sites, sizes = [], []
    for (x, y, angs, lens, w) in anchors:
        limbs, tips, tw = limb_fan(rng, (x, y), angs, lens, [w] * len(angs), levels=levels, split=(1, 3),
                                   curl=0.3)
        for pts, ww, lvl in sorted(limbs, key=lambda l: -l[1][0]):
            paint_tube(cv, pts, ww, rng, bark, L3, detail=limb_detail, moss=0.5 if lvl == 0 else 0.0,
                       depth=d, haze=haze, end_fade=0.1)
            if along and lvl >= 1:
                k = len(pts)
                idx = np.arange(int(k * 0.45), k, 2)
                sites.append(pts[idx])
                sizes.append(rad * rng.uniform(0.45, 0.8, len(idx)))
        sites.append(tips)
        sizes.append(rad * rng.uniform(0.75, 1.25, len(tips)))
    if sites:
        S = np.concatenate(sites)
        Z = np.concatenate(sizes)
        keep = ~in_gap(S[:, 0], S[:, 1], gap_k) & (S[:, 1] < 1500)
        S, Z = S[keep], Z[keep]
        crown_blobs(rng, S, Z, blobs=blobs, sun2=SUN2, light=light_k, per_tip=(2, 4), spread=0.6,
                    flatten=0.8, lumpy=0.17)
    if extra:
        blobs.extend(extra)
    G = render_gbuffer(cv, blobs, light3=(L3[0], L3[1], -0.4), wrap=0.5, under=0.3)
    stops = pal_depth(LEAF_NEAR, d, haze)
    paint_mass(cv, G, rng, stops, leaf=leaf, density=density, trans=aerial(TRANS, d * 0.6, haze),
               trans_amt=trans_amt, rim=aerial(RIM, d * 0.4, haze), rim_amt=rim_amt,
               tip=aerial(C(255, 226, 150), d * 0.5, haze), tip_amt=0.12, sun2=SUN2, droop=0.4,
               vnoise=0.16)
    return G


def understory(cv, rng, x, y_base, h, d, leaf, sp='beech'):
    """A small hazy tree in the middle distance: thin trunk + 2-3 tiers of foliage."""
    bark = species(sp, depth=d, haze=HAZE)
    top = (x + rng.normal(0, h * 0.06), y_base - h)
    pts, ww = trunk_path(rng, (x, y_base), top, h * 0.035, h * 0.02, sway=0.04, bulge=0.05)
    paint_tube(cv, pts, ww, rng, bark, L3, detail=0.4, depth=d, haze=HAZE, moss=0.3,
               mist_fade=(y_base - h * 0.3, y_base), mist_col=HAZE_W)
    b = Blobs()
    for tier in range(int(rng.integers(2, 4))):
        ty = y_base - h * (0.55 + 0.17 * tier) + rng.normal(0, h * 0.03)
        span = h * (0.32 - 0.07 * tier)
        for k in range(int(rng.integers(3, 6))):
            b.add(top[0] + rng.uniform(-span, span) * 0.8, ty + rng.normal(0, h * 0.03), span * rng.uniform(0.3, 0.5),
                  span * rng.uniform(0.18, 0.28), light=rng.uniform(0.8, 1.05), rng=rng, lumpy=0.2)
    G = render_gbuffer(cv, b, light3=(L3[0], L3[1], 0.1), wrap=0.5, under=0.4)
    paint_mass(cv, G, rng, pal_depth(LEAF_NEAR, d), leaf=leaf, density=0.9,
               trans=aerial(TRANS, d * 0.6, HAZE), trans_amt=0.6, rim=aerial(RIM, d * 0.5, HAZE), rim_amt=0.6,
               sun2=SUN2, droop=0.6, vnoise=0.14)


def gap_k(x, y):
    cx, cy, rx, ry = GAP
    return np.sqrt(((np.asarray(x) - cx) / rx) ** 2 + ((np.asarray(y) - cy) / ry) ** 2)


def canopy_ring(cv, rng, d, rad, leaf, k_in, k_out, y_max, n, light_k=1.0, density=1.0, trans_amt=0.55,
                rim_amt=0.7, haze=HAZE, limbs=(), limb_w=30, rag_amp=0.12, extra_blobs=None):
    """Canopy seen from below: clusters fill the band k_in..k_out of the gap ellipse
    (ragged by angle), above y_max(x). limbs: list of (start, end) to paint first."""
    bark = species('camphor', depth=d, haze=haze)
    for (p0, p1, w0) in limbs:
        p0 = np.asarray(p0, np.float32)
        p1 = np.asarray(p1, np.float32)
        mid_ = (p0 + p1) / 2 + rng.normal(0, 0.08, 2) * np.hypot(*(p1 - p0))
        pts = catmull(np.array([p0, mid_, p1]), n=24)
        paint_tube(cv, pts, np.linspace(w0, w0 * 0.45, 24), rng, bark, L3, detail=0.6, moss=0.6, depth=d,
                   haze=haze, end_fade=0.15)
    xs = rng.uniform(-150, W + 150, n * 4)
    ys = rng.uniform(-200, 1700, n * 4)
    th = np.arctan2(ys - GAP[1], xs - GAP[0])
    ragk = 1 + rag_amp * (np.sin(th * 5 + rng.uniform(0, 6)) * 0.6 + np.sin(th * 11 + rng.uniform(0, 6)) * 0.4)
    k = gap_k(xs, ys) / ragk
    ok = (k > k_in) & (k < k_out) & (ys < y_max(xs))
    xs, ys = xs[ok][:n], ys[ok][:n]
    # lower clusters in front (painter's order: top/back first)
    order = np.argsort(ys)
    blobs = Blobs()
    for i in order:
        r = rad * rng.uniform(0.6, 1.3)
        lt = light_k * rng.uniform(0.75, 1.1)
        blobs.add(xs[i], ys[i], r, r * rng.uniform(0.65, 0.85), rot=rng.normal(0, 0.3), light=lt,
                  hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng, lumpy=0.17)
    if extra_blobs is not None:
        blobs.extend(extra_blobs)
    G = render_gbuffer(cv, blobs, light3=(L3[0], L3[1], -0.4), wrap=0.5, under=0.3)
    stops = pal_depth(LEAF_NEAR, d, haze)
    paint_mass(cv, G, rng, stops, leaf=leaf, density=density, trans=aerial(TRANS, d * 0.6, haze),
               trans_amt=trans_amt, rim=aerial(RIM, d * 0.4, haze), rim_amt=rim_amt,
               tip=aerial(C(255, 226, 150), d * 0.5, haze), tip_amt=0.12, sun2=SUN2, droop=0.4,
               vnoise=0.16)
    return G


def build(outdir, quick=False):
    P = Painting('S01', W, H, M, outdir)
    rng = rng_for('S01')

    # ------------------------------------------------------------------ sky
    cv = P.layer('sky', 0.0)
    stops = [C(104, 112, 182), C(146, 138, 198), C(212, 168, 192), C(246, 198, 168), C(255, 218, 168),
             C(252, 232, 202), C(240, 226, 210)]
    pos = [0.0, 0.06, 0.13, 0.21, 0.33, 0.6, 1.0]
    sky(cv, rng, stops, pos, sun=SUN, glow=(620, C(255, 238, 198), 0.95), tilt=-0.04, n_strokes=0.7,
        stroke_w=(26, 90), stroke_len=(200, 700), angle=-0.1)
    cl_stops = [C(140, 126, 180), C(192, 154, 184), C(236, 182, 172), C(255, 214, 168), C(255, 238, 206)]
    for (cx, by, w_, h_, kind) in [(700, 560, 760, 150, 'strato'), (1240, 470, 520, 190, 'cumulus')]:
        plane_cloud(cv, rng, cx, by, w_, h_, (cl_stops[0], cl_stops[2], cl_stops[3], cl_stops[4]), kind=kind,
                    light3=(0.5, -0.75, 0.3), rim=C(255, 244, 214), wisps=0.4)
    glow(cv, SUN[0], SUN[1], 170, C(255, 248, 226), 0.85)
    P.add('sky', 0.0, cv, 'dawn sky through the canopy gap; opaque')

    # ------------------------------------------------------------------ far
    cv = P.layer('far', 0.15)
    d = 0.72
    # far crowns ring the gap (pale, hazy)
    anchors = []
    for x in np.linspace(-80, 2000, 12):
        anchors.append((x + rng.normal(0, 40), 900 + rng.normal(0, 70),
                        [-np.pi / 2 + rng.uniform(-1.2, -0.6), -np.pi / 2 + rng.uniform(-0.25, 0.25),
                         -np.pi / 2 + rng.uniform(0.6, 1.2)], [300, 360, 300], 16))
    canopy_ring(cv, rng, d, 34, 6.5, 0.86, 1.25, lambda x: 980 + 0 * x, 420, density=0.8, trans_amt=0.45,
                rim_amt=0.5)
    # far trunks: varied width, lean, forks, side branches; some dissolve into the mist
    xs = np.sort(np.concatenate([rng.uniform(-40, 1960, 16), rng.uniform(560, 1360, 6)]))
    far_trunks(cv, rng, xs, 2560, (700, 900), d, HAZE, L3, HAZE_W, (2150, 2560), width=(12, 70), fade_p=0.45,
               fork_p=0.45, branch_p=0.55, sun2=SUN2)
    # far understorey wall fading into mist
    b = Blobs()
    for x in np.linspace(-60, 1980, 34):
        y = 2470 + rng.normal(0, 30)
        b.add(x, y, rng.uniform(50, 110), rng.uniform(40, 80), light=rng.uniform(0.7, 1.0), rng=rng, lumpy=0.18)
    G = render_gbuffer(cv, b, light3=L3, wrap=0.5)
    paint_mass(cv, G, rng, pal_depth(LEAF_NEAR, 0.8), leaf=6, density=0.7, trans=aerial(TRANS, 0.6, HAZE),
               trans_amt=0.4, sun2=SUN2, vnoise=0.12)
    yy = cv.ys()[:, None]
    cv.lock_tint(HAZE_W, (smoothstep(2300, 2600, yy) * 0.8 * np.ones((1, cv.shape[1]))).astype(np.float32))
    P.add('far', 0.15, cv, 'far crowns around the gap, pale far trunks, far understorey in mist')

    # ------------------------------------------------------------------ mist_far
    cv = P.layer('mist_far', 0.25)
    mist(cv, rng, -100, 2020, 2060, 2640, HAZE_W, HAZE_C, light=warmth, density=1.4, opacity=(0.05, 0.14),
         size=(160, 520), aspect=(0.12, 0.28), profile='bottom')
    mist(cv, rng, -100, 2020, 950, 2150, HAZE_W, HAZE_C, light=warmth, density=0.55, opacity=(0.03, 0.08),
         size=(200, 600), aspect=(0.1, 0.25), profile='flat')
    glow(cv, 900, 2440, 640, C(255, 236, 200), 0.38, squash=0.55)
    P.add('mist_far', 0.25, cv, 'mist between far and mid trees; glow behind the robot')

    # ------------------------------------------------------------------ mid
    cv = P.layer('mid', 0.45)
    d = 0.38
    # hazier back row first
    for (x, w_, sp, xt) in [(760, 40, 'beech', 820), (1180, 46, 'camphor', 1120), (230, 50, 'cedar', 260),
                            (1650, 54, 'beech', 1600)]:
        pts, ww = trunk_path(rng, (x, 2575), (xt, 820 if 400 < xt < 1600 else 300), w_, w_ * 0.65, sway=0.02,
                             bulge=0.06, flare=0.3)
        paint_tube(cv, pts, ww, rng, species(sp, depth=0.55, haze=HAZE), L3, depth=0.55, haze=HAZE, moss=0.4,
                   detail=0.5, mist_fade=(2100, 2600), mist_col=HAZE_W)
    for (x, yb, h_, wb) in [(170, 2560, 1050, 46), (560, 2552, 760, 30), (1580, 2570, 980, 44),
                            (1830, 2560, 820, 36)]:
        broadleaf(cv, rng, (x, yb), h_, wb, 0.5, HAZE, L3, SUN2, leaf=7, mist_fade=(yb - 380, yb),
                  mist_col=HAZE_W, lz=-0.15)
    mids = [(300, 2610, 118, 'camphor', 400, 0.18), (536, 2585, 58, 'beech', 640, 0.0),
            (1345, 2600, 80, 'cedar', 1250, 0.06), (1500, 2625, 150, 'camphor', 1380, -0.15),
            (60, 2600, 90, 'beech', 110, 0.0)]
    for (x, y, w_, sp, xt, tw) in mids:
        yt = 840 if 450 < xt < 1550 else (420 if 250 < xt < 1750 else -60)
        pts, ww = trunk_path(rng, (x, y), (xt, yt), w_, w_ * 0.62, sway=0.02, bulge=0.07,
                             flare=0.5 if sp == 'camphor' else 0.2, flare_h=0.05)
        bark = species(sp, depth=d, haze=HAZE)
        paint_tube(cv, pts, ww, rng, bark, L3, depth=d, haze=HAZE, moss=0.8, ivy=0.25 if sp == 'camphor' else 0,
                   twist=tw, detail=0.7, flecks=0.4, mist_fade=(2250, 2640), mist_col=mix(HAZE_W, HAZE, 0.5))
    anchors = [(392, 760, [-0.55, -0.95], [520, 420], 30), (380, 380, [-0.3, -0.8, -2.6], [560, 440, 360], 26),
               (630, 560, [-0.5, -1.1], [380, 300], 18),
               (1270, 600, [np.pi + 0.5, np.pi + 1.0], [420, 380], 22),
               (1400, 760, [np.pi + 0.45, np.pi + 0.9], [560, 420], 34),
               (1385, 330, [np.pi + 0.25, np.pi + 0.7, -0.5], [560, 460, 320], 28),
               (100, 600, [-0.4, -1.2], [380, 300], 22)]
    limbs = [((392, 900), (620, 600), 28), ((380, 560), (560, 330), 24), ((630, 700), (760, 560), 16),
             ((1270, 760), (1120, 600), 20), ((1400, 900), (1210, 700), 30), ((1385, 520), (1560, 330), 24),
             ((100, 700), (300, 520), 20)]
    canopy_ring(cv, rng, d, 50, 10, 1.02, 1.5, lambda x: 860 + 380 * np.abs(x - 1000) / 1000, 360,
                density=0.9, limbs=limbs)
    # vines from the mid limbs
    for i in range(10):
        x = rng.choice([rng.uniform(380, 700), rng.uniform(1200, 1500)])
        vine(cv, x, rng.uniform(450, 800), rng.uniform(500, 1200), rng, aerial(C(44, 46, 52), d, HAZE),
             aerial(C(30, 56, 58), d, HAZE), aerial(C(128, 156, 80), d * 0.7, HAZE), leaf=rng.uniform(8, 12),
             width=2.0, sun2=SUN2)
    # bare perch branches reaching into the gap
    for (p0, a0, L0) in [((560, 620), -0.55, 420), ((1460, 520), -2.55, 380)]:
        bark = species('camphor', depth=d, haze=HAZE)
        pts = [np.array(p0, np.float32)]
        a = a0
        for i in range(7):
            a += rng.normal(0, 0.14)
            pts.append(pts[-1] + L0 / 7 * np.array([np.cos(a), np.sin(a)], np.float32))
        pts = np.array(pts)
        paint_tube(cv, pts, np.linspace(16, 4, len(pts)), rng, bark, L3, detail=0.4, depth=d, haze=HAZE,
                   end_fade=0.15)
        for k in range(5):
            i = int(rng.integers(2, len(pts) - 1))
            b0 = pts[i]
            aa = a0 + rng.choice([-1, 1]) * rng.uniform(0.4, 1.0)
            tw_ = [b0]
            for j in range(4):
                aa += rng.normal(0, 0.25)
                tw_.append(tw_[-1] + rng.uniform(18, 34) * np.array([np.cos(aa), np.sin(aa)]))
            stroke(cv, np.array(tw_), taper(5, 1.0, 0.2, 3.2), aerial(C(46, 40, 60), d, HAZE), bristle=0.2,
                   rag=0.2, rng=rng)
    # mid ground: the clearing floor
    ground(cv, rng, 2545, 2905, -60, 1980, aerial(C(150, 158, 124), 0.55, HAZE_W), C(74, 98, 78),
           C(34, 48, 70), light=lambda x, y: warmth(x, y) * (1 - smoothstep(2660, 2860, y)) * 0.8,
           lit_col=C(200, 190, 118), size_far=5, size_near=26)
    # moss / litter patches (lighter moss, ochre litter, dark hollows)
    for (c0, n0, a0) in [(C(126, 150, 84), 22, 0.7), (C(150, 118, 92), 30, 0.65), (C(34, 48, 66), 24, 0.75),
                         (C(98, 84, 96), 14, 0.5)]:
        px = np.where(rng.random(n0) < 0.6, rng.choice([rng.uniform(0, 520), rng.uniform(1300, 1920)], n0),
                      rng.uniform(-40, 1960, n0))
        py = rng.uniform(2570, 2890, n0)
        sc = 0.4 + (py - 2545) / 360
        for i in range(n0):
            m = int(60 * sc[i])
            xx = px[i] + rng.normal(0, 70 * sc[i], m)
            yy = py[i] + rng.normal(0, 14 * sc[i], m)
            cc = jitter(mix(c0, C(88, 116, 82), 0.3), rng, m, dl=0.04, dc=0.15, dh=0.08)
            dabs(cv, xx, yy, rng.uniform(8, 22, m) * sc[i], cc, aspect=rng.uniform(0.2, 0.45, m),
                 angle=rng.normal(0, 0.15, m), opacity=a0 * rng.uniform(0.5, 1, m), shape='flat', rag=0.5,
                 edge=0.3, bristle=0.4, rng=rng)
    # ferns and grass hugging the trunks' feet at the sides of the clearing
    for (x, y, s_) in [(330, 2700, 120), (420, 2660, 90), (250, 2640, 80), (1560, 2690, 120), (1470, 2650, 90),
                       (1650, 2640, 80), (560, 2615, 60), (1360, 2615, 60)]:
        fern(cv, rng, x, y, s_, depth=0.2, haze=HAZE_W, sun2=SUN2, light=0.9)
    for x in list(rng.uniform(200, 640, 10)) + list(rng.uniform(1300, 1720, 10)):
        grass(cv, rng, x, rng.uniform(2600, 2760), rng.uniform(30, 70), light=0.85, sun2=SUN2)
    # far shrub band softening the floor line
    b = Blobs()
    xs_ = np.sort(rng.uniform(-80, 2000, 46))
    for x in xs_:
        side = np.clip(np.abs(x - 900) / 800, 0, 1)
        if side < 0.35 and rng.random() < 0.55:
            continue
        hgt = 30 + 150 * side ** 1.5 * rng.uniform(0.5, 1.2)
        for k in range(int(1 + 3 * side)):
            r = hgt * rng.uniform(0.45, 0.8)
            b.add(x + rng.normal(0, 30), 2555 - k * r * 0.6 - rng.uniform(0, 0.3) * hgt, r, r * rng.uniform(0.55, 0.8),
                  light=rng.uniform(0.8, 1.1), hue=rng.normal(0, 0.05), rng=rng, lumpy=0.24)
    G = render_gbuffer(cv, b, light3=(L3[0], L3[1], 0.15), wrap=0.5, under=0.4)
    paint_mass(cv, G, rng, pal_depth(LEAF_NEAR, 0.45, HAZE_W), leaf=6, density=0.9,
               trans=aerial(TRANS, 0.3, HAZE_W), trans_amt=0.7, rim=aerial(RIM, 0.2, HAZE_W), rim_amt=0.6,
               sun2=SUN2, vnoise=0.14)
    # cool shadow in front (bottom) and sun patches in the clearing behind the robot
    yy = cv.ys()[:, None]
    shade_k = (smoothstep(2760, 2905, yy) * 0.5 * np.ones((1, cv.shape[1]))).astype(np.float32)
    cv.lock_tint(C(38, 50, 78), shade_k)
    surface_roots(cv, rng, [((300, 2612), (520, 2680), 26), ((330, 2620), (190, 2700), 22),
                            ((1500, 2628), (1680, 2700), 28), ((1480, 2632), (1360, 2690), 20),
                            ((560, 2590), (660, 2625), 14)], L3, d=0.3, haze=HAZE_W)
    xs = np.concatenate([rng.uniform(250, 700, 9), rng.uniform(1380, 1700, 8), rng.uniform(700, 1400, 7)])
    ys = rng.uniform(2575, 2840, len(xs))
    dapple(cv, rng, xs, ys, rng.uniform(50, 100, len(xs)) * (0.5 + (ys - 2545) / 360), C(214, 204, 116),
           flatten=0.24, opacity=(0.3, 0.6), cluster=6, mode='lock')
    # ferns, grass, stones at the sides of the clearing (keep robot zone clear)
    for (x, y, s) in [(140, 2700, 130), (300, 2660, 100), (420, 2610, 70), (1420, 2640, 90),
                      (1560, 2690, 120), (1720, 2650, 100), (230, 2600, 70), (1300, 2585, 55)]:
        fern(cv, rng, x, y, s, depth=0.25, haze=HAZE_W, sun2=SUN2, light=0.9)
    for (x, y, r) in [(1400, 2705, 30), (480, 2660, 22)]:
        stone(cv, rng, x, y, r, sun2=SUN2, moss=1.4)
    fx = rng.uniform(380, 1450, 90)
    fy = rng.uniform(2570, 2700, 90)
    flowers(cv, rng, fx, fy, 2.5 + (fy - 2545) / 60)
    P.add('mid', 0.45, cv, 'mid trunks + crowns rimming the gap, perch branches, clearing floor (robot kneels on it)')

    # ------------------------------------------------------------------ mist_mid
    cv = P.layer('mist_mid', 0.55)
    mist(cv, rng, -100, 2020, 2300, 2760, HAZE_W, HAZE_C, light=warmth, density=1.0, opacity=(0.04, 0.12),
         size=(140, 420), aspect=(0.1, 0.24), profile='bottom')
    # low ground mist hugging the far floor
    mist(cv, rng, -100, 2020, 2520, 2680, HAZE_W, HAZE_C, light=warmth, density=1.2, opacity=(0.05, 0.13),
         size=(120, 380), aspect=(0.08, 0.16), profile='mid')
    mist(cv, rng, -100, 2020, 1100, 2300, HAZE_W, HAZE_C, light=warmth, density=0.35, opacity=(0.02, 0.06),
         size=(220, 640), aspect=(0.1, 0.22), profile='flat')
    glow(cv, 880, 2380, 520, C(255, 238, 204), 0.22, squash=0.7)
    P.add('mist_mid', 0.55, cv, 'warm glowing mist behind the robot; the robot goes above this layer')

    # ------------------------------------------------------------------ beams
    cv = P.layer('beams', 0.6)
    angs = np.radians([97, 101.5, 105, 109.5, 113, 118])
    beams(cv, rng, SUN, angs, 2900, [80, 140, 70, 170, 90, 70], C(255, 238, 190), opacity=0.42,
          spread_w=1.8, streak=0.6)
    P.add('beams', 0.6, cv, 'sunbeams through the gap (could be animated: opacity shimmer)')

    # ------------------------------------------------------------------ near
    cv = P.layer('near', 0.8)
    d = 0.0
    # left giant camphor (twisting, buttressed, ivy) and right giant beech
    giants = [dict(sp='camphor', base=(150, 2915), top=(330, -70), wb=500, wt=280, flare=0.55, tw=0.22,
                   roots=6, ivy=0.6, moss=1.3),
              dict(sp='beech', base=(1765, 2915), top=(1640, -70), wb=430, wt=270, flare=0.45, tw=0.0,
                   roots=5, ivy=0.12, moss=1.0)]
    bark_near = {}
    for g in giants:
        pts, ww = trunk_path(rng, g['base'], g['top'], g['wb'], g['wt'], sway=0.025, bulge=0.08,
                             flare=g['flare'], flare_h=0.045)
        bark = species(g['sp'])
        if g['sp'] == 'beech':
            bark.blotch = C(96, 122, 92)
            bark.lichen = 0.2
        bark_near[g['sp']] = bark
        sp_ = catmull(pts, spacing=3.0)
        fr = Frame(sp_, np.interp(np.linspace(0, 1, len(sp_)), np.linspace(0, 1, len(ww)), ww))
        roots = buttress_roots(rng, fr, g['roots'], g['base'][1] - 25, g['wb'], spread=1.5)
        for rp, rw, sd in roots:
            # keep roots out of the robot zone
            if np.any((rp[:, 0] > ROBOT[0] + 40) & (rp[:, 0] < ROBOT[2] - 40)):
                continue
            paint_tube(cv, rp, rw, rng, bark, L3, moss=1.6, detail=0.8, start_fade=0.25)
        paint_tube(cv, pts, ww, rng, bark, L3, moss=g['moss'], ivy=g['ivy'], twist=g['tw'], flecks=0.3,
                   detail=1.0, moss_base=0.5, sky_side=0.3)
    # near crowns at the top corners with big limbs reaching over the gap
    anchors = [(300, 720, [-0.35, -0.8], [640, 520], 64), (320, 400, [-0.15, -0.55, -1.25], [600, 620, 380], 56),
               (330, 80, [-0.3, 0.12, -2.6], [520, 440, 300], 48),
               (1665, 650, [np.pi + 0.35, np.pi + 0.8], [580, 480], 60),
               (1652, 330, [np.pi + 0.2, np.pi + 0.6, np.pi + 1.3], [600, 560, 360], 52),
               (1645, 50, [np.pi + 0.3, np.pi - 0.1, -0.4], [520, 420, 300], 44)]
    limbs = [((300, 760), (700, 330), 64), ((320, 420), (640, 120), 52), ((300, 240), (60, -60), 40),
             ((1665, 700), (1320, 330), 60), ((1652, 380), (1380, 90), 52), ((1650, 200), (1900, -40), 40)]
    top = Blobs()
    for x in np.linspace(300, 1700, 16):
        if rng.random() < 0.25:
            continue
        yb = rng.uniform(-40, 90) - 60 * np.exp(-((x - SUN[0]) / 160) ** 2)
        for k in range(int(rng.integers(2, 4))):
            r = rng.uniform(50, 95)
            top.add(x + rng.normal(0, 50), yb - k * 50 + rng.normal(0, 20), r, r * 0.75, light=rng.uniform(0.75, 1.1),
                    hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng, lumpy=0.18)
    canopy_ring(cv, rng, 0.0, 80, 15, 1.35, 3.5, lambda x: 520 + 900 * np.clip(np.abs(x - 1000) / 900, 0, 1) ** 1.5,
                420, density=0.9, limbs=limbs, trans_amt=0.6, rim_amt=0.8, rag_amp=0.16, extra_blobs=top)
    # surface roots snaking over the floor from the giants (outside the robot zone)
    for (p0, p1, w0) in [((330, 2840), (560, 2900), 46), ((380, 2800), (470, 2760), 30),
                         ((1560, 2850), (1380, 2905), 44), ((1600, 2790), (1470, 2740), 28)]:
        mid_ = ((p0[0] + p1[0]) / 2 + rng.normal(0, 20), (p0[1] + p1[1]) / 2 + rng.normal(0, 10))
        pts = catmull(np.array([p0, mid_, p1], np.float32), n=20)
        paint_tube(cv, pts, np.linspace(w0, w0 * 0.3, 20), rng, species('camphor'), L3, moss=2.0, detail=0.7,
                   start_fade=0.2)
    # stones and a fallen log at the sides of the clearing floor
    for (x, y, r) in [(360, 2885, 52)]:
        stone(cv, rng, x, y, r, sun2=SUN2, moss=1.6)
    P.add('near', 0.8, cv, 'giant framing trunks (camphor left, beech right), roots, near crowns at the top')

    # ------------------------------------------------------------------ fg
    cv = P.layer('fg', 1.0)
    # overhanging leaf sprays from the top edge (dark, warm rims)
    for i in range(16):
        x = rng.choice([rng.uniform(-60, 520), rng.uniform(1400, 1980)])
        a = np.pi / 2 + rng.normal(0, 0.5)
        spray(cv, x, rng.uniform(-60, 40), a, rng.uniform(160, 320), rng.uniform(26, 40), C(20, 30, 44),
              C(90, 104, 60), rng, stem_col=C(30, 28, 40), droop=0.6, sun2=SUN2, rim=C(255, 214, 140))
    # hanging vines down the sides
    for i in range(9):
        x = rng.choice([rng.uniform(150, 520), rng.uniform(1380, 1720)])
        vine(cv, x, rng.uniform(80, 400), rng.uniform(700, 1600), rng, C(40, 44, 50), C(26, 50, 52),
             C(120, 150, 76), leaf=rng.uniform(13, 20), width=3.0, sun2=SUN2)
    # bottom corners: big ferns and leafy undergrowth (outside the robot zone)
    for (x, y, s, lean) in [(60, 2960, 300, 0.25), (250, 2990, 260, 0.1), (-40, 2860, 220, 0.5),
                            (1880, 2960, 290, -0.25), (1700, 3000, 260, -0.1), (1980, 2850, 220, -0.5)]:
        fern(cv, rng, x, y, s, sun2=SUN2, light=0.65, lean=lean, spread=0.9)
    for x in list(rng.uniform(-40, 380, 8)) + list(rng.uniform(1480, 1960, 8)):
        grass(cv, rng, x, 2915, rng.uniform(70, 140), light=0.7, sun2=SUN2)
    P.add('fg', 1.0, cv, 'foreground: overhanging leaves at the top, vines, ferns in the bottom corners')

    P.save(sun=list(SUN), light_dir=list(L3), frames=dict(start=[0, 0, 1920, 1040], end=[0, FE, 1920, 1040]),
           robot_zone=[ROBOT[0], ROBOT[1], ROBOT[2], ROBOT[3]],
           robot_between=['beams', 'near'],
           camera='tilt down from frames.start to frames.end; anchor parallax at the end frame')
    return P
