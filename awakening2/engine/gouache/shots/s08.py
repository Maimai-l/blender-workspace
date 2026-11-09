"""S08 - RISE A, wide front view of the clearing (1920 x 1040, horizon y 757).

Two giant trunks frame left and right, the forest beyond in mist layers, ferns
and roots in front. The robot kneels centre (x ~630-1230, y ~130-870) and heaves
up; it is composited between `beams` and `near`. Sun behind the robot, upper right.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, spray, vine
from ..sky import sky
from ..atmos import mist, beams, glow
from ..ground import fern, grass, stone
from ..forest import (broadleaf, far_trunks, giant, floor, undergrowth, leafy_mass, surface_roots, LEAF,
                      forest_row)

W, H, M = 1920, 1040, 48
HZ = 757.0
SUN = (1290.0, 300.0)
L3 = (0.45, -0.85, -0.35)
SUN2 = (0.5, -0.86)
ROBOT = (630, 130, 1230, 870)
HAZE = C(236, 222, 216)
HAZE_W = C(255, 234, 202)
HAZE_C = C(216, 208, 226)


def warmth(x, y):
    x = np.asarray(x, np.float32)
    y = np.asarray(y, np.float32)
    g = np.exp(-(((x - SUN[0]) / 700) ** 2 + ((y - 700) / 300) ** 2))
    return np.clip(0.2 + 0.8 * g, 0, 1)


def build(outdir, quick=False):
    P = Painting('S08', W, H, M, outdir)
    rng = rng_for('S08')

    # ---------------------------------------------------------------- sky / glow
    cv = P.layer('sky', 0.0)
    stops = [C(196, 186, 210), C(228, 210, 210), C(250, 228, 196), C(255, 238, 206), C(244, 228, 206)]
    pos = [0.0, 0.3, 0.6, 0.73, 1.0]
    sky(cv, rng, stops, pos, sun=SUN, glow=(700, C(255, 240, 204), 0.9), n_strokes=0.8, stroke_w=(24, 80),
        stroke_len=(200, 600), angle=-0.05)
    P.add('sky', 0.0, cv, 'misty dawn glow behind the forest; opaque')

    # ---------------------------------------------------------------- far forest
    cv = P.layer('far', 0.15)
    d = 0.72
    # hazy far canopy hanging from the top
    b = Blobs()
    for x in np.linspace(-80, 2000, 26):
        y = rng.uniform(-60, 120)
        r = rng.uniform(60, 120)
        b.add(x + rng.normal(0, 30), y, r, r * 0.7, light=rng.uniform(0.75, 1.05), hue=rng.normal(0, 0.05), rng=rng,
              lumpy=0.2)
    leafy_mass(cv, rng, b, 0.75, HAZE, L3, SUN2, 6, density=0.8, trans_amt=0.4, rim_amt=0.5)
    for (dd, n_, wr, lf, yg) in [(0.82, 16, (8, 26), 4.0, HZ + 4), (0.7, 12, (14, 44), 5.0, HZ + 14)]:
        forest_row(cv, rng, -80, 2000, yg, -120, n_, dd, HAZE, L3, SUN2, mist_col=HAZE_W,
                   mist_band=(HZ - 260, HZ + 10), width=wr, leaf=lf, branches=(1, 2), saplings=0.6, vines=0.3,
                   keep=(ROBOT[0], ROBOT[2]), fade_p=0.4, top_jitter=30, leaf_size=26 if dd > 0.75 else 34)
        mist(cv, rng, -100, 2020, HZ - 520, HZ + 20, HAZE_W, HAZE_C, light=warmth, density=0.4, opacity=(0.04, 0.1),
             size=(200, 600), aspect=(0.1, 0.25), profile='bottom')
    undergrowth(cv, rng, HZ + 6, -60, 1980, 0.72, HAZE, L3, SUN2, leaf=5, height=(16, 70), centre=(950, 900))
    yy = cv.ys()[:, None]
    cv.lock_tint(HAZE_W, (smoothstep(HZ - 220, HZ + 20, yy) * 0.75 * np.ones((1, cv.shape[1]))).astype(np.float32))
    P.add('far', 0.15, cv, 'far trunks dissolving into mist, far understorey on the horizon')

    # ---------------------------------------------------------------- mist far
    cv = P.layer('mist_far', 0.25)
    mist(cv, rng, -100, 2020, HZ - 330, HZ + 40, HAZE_W, HAZE_C, light=warmth, density=1.3, opacity=(0.05, 0.14),
         size=(160, 480), aspect=(0.12, 0.26), profile='bottom')
    glow(cv, SUN[0] - 200, HZ - 160, 600, C(255, 238, 204), 0.3, squash=0.6)
    P.add('mist_far', 0.25, cv, 'mist between far and mid trees; glow behind the robot')

    # ---------------------------------------------------------------- mid
    cv = P.layer('mid', 0.45)
    d = 0.4
    for (x, wb, hgt) in [(140, 70, 1400), (470, 44, 1150), (1420, 50, 1250), (1760, 64, 1350)]:
        broadleaf(cv, rng, (x, HZ + 40), hgt, wb, d, HAZE, L3, SUN2, leaf=9, mist_fade=(HZ - 200, HZ + 40),
                  mist_col=HAZE_W, lz=-0.2, fork_at=rng.uniform(0.62, 0.75))
    # floor: horizon -> bottom; open centre where the robot kneels
    floor(cv, rng, HZ, H + 40, -60, W + 60, HAZE_W, L3, SUN2, warmth,
          roots=[((400, HZ + 60), (620, HZ + 120), 22), ((1480, HZ + 70), (1300, HZ + 130), 22)],
          veg=[], patches=30, flowers_n=70, size_near=30)
    # irregular undergrowth on the far edge of the floor (open in the centre where the robot kneels)
    undergrowth(cv, rng, HZ + 8, -80, 2000, 0.45, HAZE_W, L3, SUN2, leaf=6, height=(14, 110), centre=(930, 700),
                gap=(ROBOT[0] + 40, ROBOT[2] - 40), n=60)
    yy = cv.ys()[:, None]
    cv.lock_tint(C(36, 48, 76), (smoothstep(HZ + 150, H + 40, yy) * 0.45 * np.ones((1, cv.shape[1]))).astype(np.float32))
    for (x, y, s_) in [(300, HZ + 60, 90), (1600, HZ + 70, 100), (520, HZ + 30, 60), (1380, HZ + 35, 60),
                       (420, HZ + 90, 120), (1500, HZ + 95, 120), (240, HZ + 40, 70), (1690, HZ + 45, 70)]:
        fern(cv, rng, x, y, s_, depth=0.2, haze=HAZE_W, sun2=SUN2, light=0.9)
    for x in list(rng.uniform(260, 600, 8)) + list(rng.uniform(1300, 1660, 8)):
        grass(cv, rng, x, HZ + rng.uniform(40, 120), rng.uniform(30, 60), light=0.85, sun2=SUN2)
    P.add('mid', 0.45, cv, 'mid broadleaf trees, the clearing floor (the robot kneels on it)')

    # ---------------------------------------------------------------- mist mid
    cv = P.layer('mist_mid', 0.55)
    mist(cv, rng, -100, 2020, HZ - 120, HZ + 140, HAZE_W, HAZE_C, light=warmth, density=1.1, opacity=(0.04, 0.12),
         size=(120, 400), aspect=(0.08, 0.18), profile='mid')
    mist(cv, rng, -100, 2020, HZ - 30, HZ + 50, HAZE_W, HAZE_C, light=warmth, density=1.4, opacity=(0.05, 0.14),
         size=(100, 320), aspect=(0.07, 0.14), profile='mid')
    P.add('mist_mid', 0.55, cv, 'ground mist; the robot goes above this layer')

    # ---------------------------------------------------------------- beams
    cv = P.layer('beams', 0.6)
    beams(cv, rng, (SUN[0] + 260, -120), np.radians([108, 113, 118, 124, 130]), 1500, [70, 110, 60, 130, 70],
          C(255, 238, 190), opacity=0.32, spread_w=1.6, streak=0.6)
    P.add('beams', 0.6, cv, 'sunbeams slanting down-left through the canopy')

    # ---------------------------------------------------------------- near: giant framing trunks
    cv = P.layer('near', 0.8)
    giant(cv, rng, (150, H - 40), (240, -80), 400, 290, L3, sp='camphor', roots=6, ivy=0.0, moss=1.1, twist=0.22,
          keep_out=(ROBOT[0] - 60, ROBOT[2] + 60), flecks=0.3, root_spread=1.6,
          traits=dict(knots=3, fungi=2, hollow=True, ivy_bands=2, moss_cushions=4))
    giant(cv, rng, (1790, H - 30), (1700, -80), 370, 270, L3, sp='beech', roots=5, ivy=0.0, moss=0.8, twist=0.0,
          keep_out=(ROBOT[0] - 60, ROBOT[2] + 60), lichen=0.2, blotch=C(96, 122, 92), flecks=0.3, root_spread=1.5,
          traits=dict(knots=4, fungi=3, hollow=False, ivy_bands=1, moss_cushions=3, side=-1.0))
    # near canopy at the top corners
    b = Blobs()
    for (cx, cy, n_) in [(220, -20, 16), (1720, -30, 16), (600, -70, 6), (1330, -80, 6)]:
        for k in range(n_):
            r = rng.uniform(55, 100)
            b.add(cx + rng.normal(0, 170), cy + abs(rng.normal(0, 70)), r, r * 0.75, light=rng.uniform(0.75, 1.1),
                  hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.0, HAZE, L3, SUN2, 14, density=0.9, trans_amt=0.6, rim_amt=0.8, lz=-0.4)
    P.add('near', 0.8, cv, 'giant framing trunks (camphor left, beech right) and their roots; canopy corners')

    # ---------------------------------------------------------------- fg
    cv = P.layer('fg', 1.0)
    for i in range(7):
        x = rng.choice([rng.uniform(260, 560), rng.uniform(1360, 1640)])
        vine(cv, x, rng.uniform(-40, 40), rng.uniform(260, 620), rng, C(40, 44, 50), C(26, 50, 52), C(120, 150, 76),
             leaf=rng.uniform(13, 18), width=2.6, sun2=SUN2)
    for (x, y, s_, lean) in [(40, H + 60, 280, 0.3), (230, H + 80, 230, 0.1), (520, H + 90, 170, 0.0),
                             (1880, H + 60, 280, -0.3), (1680, H + 80, 230, -0.1), (1400, H + 90, 170, 0.0)]:
        fern(cv, rng, x, y, s_, sun2=SUN2, light=0.6, lean=lean, spread=0.9)
    for x in list(rng.uniform(-20, 600, 9)) + list(rng.uniform(1320, 1940, 9)):
        grass(cv, rng, x, H + 20, rng.uniform(60, 120), light=0.65, sun2=SUN2)
    P.add('fg', 1.0, cv, 'ferns, grass and vines in front (bottom corners / sides only)')

    P.save(sun=list(SUN), light_dir=list(L3), horizon_y=HZ, robot_zone=list(ROBOT),
           robot_between=['beams', 'near'], reuse='S14 reuses these layers')
    return P
