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
from ..sky import sky, cumulus_blobs, paint_clouds
from ..atmos import mist, beams, glow, dapple
from ..ground import ground, fern, grass, stone, flowers

W, H, M = 1920, 2900, 48
SUN = (1530.0, 200.0)
L3 = (0.55, -0.78, -0.32)
SUN2 = (0.55, -0.83)
FE = 1860                                   # top of the final framing
ROBOT = (0.22 * W, FE + 0.28 * 1040, 0.70 * W, FE + 0.97 * 1040)
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
                density=1.0, trans_amt=0.55, rim_amt=0.7, haze=HAZE):
    """Crowns seen from below. anchors: list of (x, y, angles, lengths, width)."""
    bark = species('camphor', depth=d, haze=haze)
    blobs = Blobs()
    for (x, y, angs, lens, w) in anchors:
        limbs, tips, tw = limb_fan(rng, (x, y), angs, lens, [w] * len(angs), levels=levels, split=(1, 3),
                                   curl=0.3)
        for pts, ww, lvl in limbs:
            if ww[0] > 3:
                paint_tube(cv, pts, ww, rng, bark, L3, detail=0.5, moss=0.4 if lvl == 0 else 0.0,
                           depth=d, haze=haze, end_fade=0.2)
        keep = ~in_gap(tips[:, 0], tips[:, 1], gap_k)
        tips = tips[keep]
        if len(tips) == 0:
            continue
        sizes = rad * rng.uniform(0.7, 1.25, len(tips))
        crown_blobs(rng, tips, sizes, blobs=blobs, sun2=SUN2, light=light_k, per_tip=(2, 5), spread=0.7,
                    flatten=0.8, lumpy=0.16)
    if extra:
        blobs.extend(extra)
    G = render_gbuffer(cv, blobs, light3=(L3[0], L3[1], -0.4), wrap=0.5, under=0.3)
    # remove clusters that fall into the gap centre
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
    for (cx, cy, w_, h_) in [(640, 470, 430, 110), (1190, 600, 560, 140), (820, 210, 330, 70),
                             (1380, 420, 260, 60)]:
        b = cumulus_blobs(rng, cx, cy, w_, h_, lumpy=0.1, puff=(0.15, 0.32))
        paint_clouds(cv, rng, b, cl_stops, light3=(0.5, -0.65, 0.15), leaf=11, rim=C(255, 236, 196),
                     rim_amt=0.7, edge=0.42, vnoise=0.12)
    glow(cv, SUN[0], SUN[1], 170, C(255, 248, 226), 0.85)
    P.add('sky', 0.0, cv, 'dawn sky through the canopy gap; opaque')

    # ------------------------------------------------------------------ far
    cv = P.layer('far', 0.15)
    d = 0.72
    # far crowns ring the gap (pale, hazy)
    anchors = []
    for x in np.linspace(-80, 2000, 11):
        if in_gap(x, 760, 1.0):
            continue
        anchors.append((x + rng.normal(0, 40), 820 + rng.normal(0, 60),
                        [-np.pi / 2 + rng.uniform(-0.9, -0.3), -np.pi / 2 + rng.uniform(-0.2, 0.2),
                         -np.pi / 2 + rng.uniform(0.3, 0.9)], [380, 420, 380], 18))
    crown_layer(cv, rng, anchors, d, leaf=6.5, rad=30, gap_k=0.86, levels=2, density=0.8,
                trans_amt=0.4, rim_amt=0.5)
    # far trunks
    xs = np.sort(rng.uniform(-40, 1960, 17))
    for x in xs:
        dd = 0.82 if 480 < x < 1360 else 0.7
        wb = rng.uniform(18, 46)
        top = (x + rng.normal(0, 30), rng.uniform(560, 900))
        pts, w_ = trunk_path(rng, (x, 2560 + rng.uniform(-30, 20)), top, wb, wb * 0.7, sway=0.012, bulge=0.05,
                             flare=0.3, flare_h=0.04)
        paint_tube(cv, pts, w_, rng, species(['camphor', 'beech', 'cedar'][int(rng.integers(0, 3))], depth=dd,
                   haze=HAZE), L3, detail=0.3, depth=dd, haze=HAZE, moss=0.3, end_fade=0.12,
                   mist_fade=(2150, 2560), mist_col=HAZE_W)
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
    mids = [(300, 2610, 118, 'camphor', 400, 0.18), (536, 2585, 58, 'beech', 640, 0.0),
            (1345, 2600, 80, 'cedar', 1250, 0.06), (1500, 2625, 150, 'camphor', 1380, -0.15),
            (60, 2600, 90, 'beech', 110, 0.0)]
    # mid crowns first (behind trunks' upper parts? no: crowns hang in front of trunk tops)
    for (x, y, w_, sp, xt, tw) in mids:
        pts, ww = trunk_path(rng, (x, y), (xt, -60), w_, w_ * 0.62, sway=0.02, bulge=0.07,
                             flare=0.5 if sp == 'camphor' else 0.2, flare_h=0.05)
        bark = species(sp, depth=d, haze=HAZE)
        paint_tube(cv, pts, ww, rng, bark, L3, depth=d, haze=HAZE, moss=0.7, ivy=0.3 if sp == 'camphor' else 0,
                   twist=tw, detail=0.7, flecks=0.4, mist_fade=(2250, 2640), mist_col=mix(HAZE_W, HAZE, 0.5))
    anchors = [(400, 330, [-2.4, -1.9, -1.2], [520, 460, 420], 34),
               (640, 420, [-2.2, -1.5], [380, 320], 22),
               (1250, 380, [-1.6, -0.9, -0.4], [380, 460, 420], 26),
               (1380, 480, [-1.9, -0.6, -0.2], [460, 520, 380], 38),
               (110, 520, [-2.0, -1.2], [300, 380], 26)]
    crown_layer(cv, rng, anchors, d, leaf=10, rad=46, gap_k=0.93, levels=2, density=0.9)
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
    ground(cv, rng, 2545, 2905, -60, 1980, aerial(C(150, 160, 120), 0.45, HAZE_W), C(92, 118, 84),
           C(44, 64, 78), light=lambda x, y: warmth(x, y) * (1 - smoothstep(2700, 2880, y)),
           lit_col=C(214, 200, 120), size_far=5, size_near=34)
    # cool shadow in front (bottom) and sun patches in the clearing behind the robot
    yy = cv.ys()[:, None]
    shade_k = (smoothstep(2760, 2905, yy) * 0.5 * np.ones((1, cv.shape[1]))).astype(np.float32)
    cv.lock_tint(C(38, 50, 78), shade_k)
    xs = rng.uniform(300, 1500, 26)
    ys = rng.uniform(2560, 2720, 26)
    dapple(cv, rng, xs, ys, rng.uniform(18, 46, 26) * (0.5 + (ys - 2545) / 360), C(236, 222, 140), flatten=0.25,
           opacity=(0.35, 0.75), cluster=6, mode='lock')
    # ferns, grass, stones at the sides of the clearing (keep robot zone clear)
    for (x, y, s) in [(140, 2700, 130), (300, 2660, 100), (420, 2610, 70), (1420, 2640, 90),
                      (1560, 2690, 120), (1720, 2650, 100), (230, 2600, 70), (1300, 2585, 55)]:
        fern(cv, rng, x, y, s, depth=0.25, haze=HAZE_W, sun2=SUN2, light=0.9)
    for (x, y, r) in [(1380, 2700, 34), (470, 2655, 26), (1240, 2620, 18)]:
        stone(cv, rng, x, y, r, sun2=SUN2)
    fx = rng.uniform(380, 1450, 90)
    fy = rng.uniform(2570, 2700, 90)
    flowers(cv, rng, fx, fy, 2.5 + (fy - 2545) / 60)
    P.add('mid', 0.45, cv, 'mid trunks + crowns rimming the gap, perch branches, clearing floor (robot kneels on it)')

    # ------------------------------------------------------------------ mist_mid
    cv = P.layer('mist_mid', 0.55)
    mist(cv, rng, -100, 2020, 2300, 2760, HAZE_W, HAZE_C, light=warmth, density=1.0, opacity=(0.04, 0.12),
         size=(140, 420), aspect=(0.1, 0.24), profile='bottom')
    mist(cv, rng, -100, 2020, 1100, 2300, HAZE_W, HAZE_C, light=warmth, density=0.35, opacity=(0.02, 0.06),
         size=(220, 640), aspect=(0.1, 0.22), profile='flat')
    glow(cv, 880, 2380, 520, C(255, 238, 204), 0.22, squash=0.7)
    P.add('mist_mid', 0.55, cv, 'warm glowing mist behind the robot; the robot goes above this layer')

    # ------------------------------------------------------------------ beams
    cv = P.layer('beams', 0.6)
    angs = np.radians([97, 101.5, 105, 109.5, 113, 118])
    beams(cv, rng, SUN, angs, 2900, [70, 120, 60, 150, 80, 60], C(255, 236, 186), opacity=0.16,
          spread_w=1.8, streak=0.65)
    P.add('beams', 0.6, cv, 'sunbeams through the gap (could be animated: opacity shimmer)')

    # ------------------------------------------------------------------ near
    cv = P.layer('near', 0.8)
    d = 0.0
    # left giant camphor (twisting, buttressed, ivy) and right giant beech
    giants = [dict(sp='camphor', base=(150, 2915), top=(330, -70), wb=500, wt=280, flare=0.55, tw=0.22,
                   roots=6, ivy=0.9, moss=1.3),
              dict(sp='beech', base=(1765, 2915), top=(1640, -70), wb=430, wt=270, flare=0.45, tw=0.0,
                   roots=5, ivy=0.3, moss=1.0)]
    bark_near = {}
    for g in giants:
        pts, ww = trunk_path(rng, g['base'], g['top'], g['wb'], g['wt'], sway=0.025, bulge=0.08,
                             flare=g['flare'], flare_h=0.045)
        bark = species(g['sp'])
        if g['sp'] == 'beech':
            bark.blotch = C(96, 122, 92)
            bark.lichen = 0.6
        bark_near[g['sp']] = bark
        sp_ = catmull(pts, spacing=3.0)
        fr = Frame(sp_, np.interp(np.linspace(0, 1, len(sp_)), np.linspace(0, 1, len(ww)), ww))
        roots = buttress_roots(rng, fr, g['roots'], g['base'][1] - 25, g['wb'], spread=1.5)
        for rp, rw, sd in roots:
            # keep roots out of the robot zone
            if np.any((rp[:, 0] > ROBOT[0] + 40) & (rp[:, 0] < ROBOT[2] - 40)):
                continue
            paint_tube(cv, rp, rw, rng, bark, L3, moss=1.6, detail=0.8, start_fade=0.25)
        paint_tube(cv, pts, ww, rng, bark, L3, moss=g['moss'], ivy=g['ivy'], twist=g['tw'], flecks=0.7,
                   detail=1.0, moss_base=0.5, sky_side=0.3)
    # near crowns at the top corners with big limbs reaching over the gap
    anchors = [(330, 120, [-2.5, -1.7, -0.75, -0.25], [560, 420, 520, 640], 70),
               (1640, 140, [-2.9, -2.35, -1.5, -0.8], [640, 560, 420, 380], 66)]
    crown_layer(cv, rng, anchors, 0.0, leaf=15, rad=78, gap_k=1.0, levels=2, density=0.9,
                trans_amt=0.6, rim_amt=0.8)
    # stones and a fallen log at the sides of the clearing floor
    for (x, y, r) in [(330, 2860, 70), (1540, 2875, 60), (470, 2890, 40)]:
        stone(cv, rng, x, y, r, sun2=SUN2, moss=0.9)
    P.add('near', 0.8, cv, 'giant framing trunks (camphor left, beech right), roots, near crowns at the top')

    # ------------------------------------------------------------------ fg
    cv = P.layer('fg', 1.0)
    # overhanging leaf sprays from the top edge (dark, warm rims)
    for i in range(16):
        x = rng.choice([rng.uniform(-60, 520), rng.uniform(1400, 1980)])
        a = np.pi / 2 + rng.normal(0, 0.5)
        spray(cv, x, rng.uniform(-60, 40), a, rng.uniform(160, 320), rng.uniform(26, 40), C(22, 34, 46),
              C(120, 128, 66), rng, stem_col=C(30, 28, 40), droop=0.6, sun2=SUN2)
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
