"""S02 - over the robot's left shoulder, looking across the forest at mid-trunk
height (1920 x 1040). Far forest in soft depth: trunks fading into glowing mist,
light shafts; no ground plane (the shoulder fills the bottom). Sun upper right.
"""
import numpy as np

from ..color import C, mix, jitter, aerial, smoothstep
from ..noise import rng_for
from ..canvas import dabs, stroke
from ..layers import Painting
from ..foliage import Blobs, vine, spray
from ..sky import sky
from ..atmos import mist, beams, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, far_trunks, broadleaf, forest_row

W, H, M = 1920, 1040, 48
SUN = (1500.0, 120.0)
L3 = (0.5, -0.8, -0.35)
SUN2 = (0.53, -0.85)
HAZE = C(236, 222, 216)
HAZE_W = C(255, 234, 200)
HAZE_C = C(214, 206, 224)


def warmth(x, y):
    x = np.asarray(x, np.float32)
    y = np.asarray(y, np.float32)
    return np.clip(0.25 + 0.75 * np.exp(-(((x - 1250) / 700) ** 2 + ((y - 500) / 500) ** 2)), 0, 1)


def build(outdir, quick=False):
    P = Painting('S02', W, H, M, outdir)
    rng = rng_for('S02')

    # ---------------------------------------------------------------- glowing mist (sky)
    cv = P.layer('sky', 0.0)
    stops = [C(214, 200, 214), C(244, 222, 204), C(255, 236, 206), C(250, 230, 206), C(236, 220, 212)]
    sky(cv, rng, stops, [0, 0.25, 0.5, 0.75, 1.0], sun=SUN, glow=(900, C(255, 242, 210), 0.9), n_strokes=0.8,
        stroke_w=(30, 90), stroke_len=(200, 640), angle=-0.05)
    P.add('sky', 0.0, cv, 'glowing mist; opaque')

    # ---------------------------------------------------------------- far: rows of forest fading into mist
    cv = P.layer('far', 0.3)
    for (dd, n_, wr, lf, hue) in [(0.84, 16, (8, 26), 4.0, 0.05), (0.72, 12, (14, 40), 5.0, -0.03),
                                  (0.58, 8, (24, 62), 6.5, 0.0)]:
        forest_row(cv, rng, -80, 2000, H + 160, -160, n_, dd, HAZE, L3, SUN2, width=wr, leaf=lf, branches=(1, 3),
                   saplings=0.0, vines=0.35, fade_p=0.2, top_jitter=40, hue=hue, leaf_size=30 + 14 * (0.84 - dd) * 10)
        mist(cv, rng, -100, 2020, -50, H + 50, HAZE_W, HAZE_C, light=warmth, density=0.45, opacity=(0.04, 0.1),
             size=(200, 600), aspect=(0.1, 0.25), profile='flat')
    # hazy lower canopy at the top
    b = Blobs()
    for x in np.linspace(-80, 2000, 22):
        r = rng.uniform(70, 140)
        b.add(x + rng.normal(0, 40), rng.uniform(-80, 90), r, r * 0.72, light=rng.uniform(0.8, 1.05),
              hue=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.62, HAZE, L3, SUN2, 7, density=0.8, trans_amt=0.5, rim_amt=0.6, lz=-0.3)
    beams(cv, rng, (SUN[0], -100), np.radians([100, 106, 113, 121]), 1400, [90, 140, 70, 120], C(255, 240, 196),
          opacity=0.3, spread_w=1.5, streak=0.6)
    P.add('far', 0.3, cv, 'three misty rows of forest (trunks, leafy side sprays, vines), hazy canopy, light shafts')

    # ---------------------------------------------------------------- mid: a few nearer mossy trunks
    cv = P.layer('mid', 0.6)
    for (x, wb, sp) in [(140, 150, 'camphor'), (1660, 120, 'beech'), (1880, 210, 'camphor'), (560, 70, 'cedar')]:
        pts, ww = trunk_path(rng, (x, H + 200), (x + rng.normal(0, 30), -150), wb, wb * 0.85, sway=0.02, bulge=0.07)
        paint_tube(cv, pts, ww, rng, species(sp, depth=0.25, haze=HAZE), L3, depth=0.25, haze=HAZE, moss=1.0,
                   ivy=0.4 if sp == 'camphor' else 0.0, detail=0.8, twist=0.15 if sp == 'camphor' else 0.0,
                   flecks=0.3)
    b = Blobs()
    for (cx, cy, n_) in [(200, -20, 10), (1750, -30, 12)]:
        for k in range(n_):
            r = rng.uniform(50, 95)
            b.add(cx + rng.normal(0, 160), cy + abs(rng.normal(0, 60)), r, r * 0.75, light=rng.uniform(0.8, 1.1),
                  hue=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.15, HAZE, L3, SUN2, 12, density=0.9, trans_amt=0.6, rim_amt=0.8, lz=-0.4)
    for i in range(6):
        x = rng.choice([rng.uniform(100, 400), rng.uniform(1500, 1800)])
        vine(cv, x, rng.uniform(-20, 60), rng.uniform(300, 700), rng, C(44, 46, 52), C(30, 56, 58), C(128, 156, 80),
             leaf=rng.uniform(11, 15), width=2.3, sun2=SUN2)
    P.add('mid', 0.6, cv, 'nearer mossy trunks at the edges, canopy corners, vines; shoulder goes above')

    P.save(sun=list(SUN), light_dir=list(L3))
    return P
