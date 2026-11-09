"""S09 - RISE B, low camera near the ground from the robot's side (1920 x 1040,
horizon y ~990). Ferns and grass in the extreme foreground, trunks rising up the
frame edges (converging a little upward), canopy and a patch of sky at the top.
The robot rises at the left-centre (x ~0.15-0.42); it goes between `mid` and `near`.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for
from ..canvas import dabs, stroke
from ..layers import Painting
from ..foliage import Blobs, vine, spray
from ..sky import sky, cumulus_blobs, paint_clouds
from ..atmos import mist, beams, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, far_trunks, broadleaf, undergrowth, forest_row
from ..ground import fern, grass

W, H, M = 1920, 1040, 48
HZ = 990.0
VPY = -6000.0                  # trunks converge slightly upward
SUN = (1500.0, 120.0)
L3 = (0.5, -0.8, -0.35)
SUN2 = (0.53, -0.85)
HAZE = C(236, 222, 216)
HAZE_W = C(255, 234, 200)
HAZE_C = C(214, 206, 224)


def up_trunk(cv, rng, xb, wb, d, sp, moss=0.8, ivy=0.2, yb=None, detail=0.7, flecks=0.3):
    yb = HZ + 20 if yb is None else yb
    vx = 960.0
    t = 0.75
    top = (xb + (vx - xb) * (yb + 150) / (yb - VPY) * 1.0, -150)
    pts, ww = trunk_path(rng, (xb, yb), top, wb, wb * 0.7, sway=0.012, bulge=0.07, flare=0.4, flare_h=0.05)
    paint_tube(cv, pts, ww, rng, species(sp, depth=d, haze=HAZE), L3, depth=d, haze=HAZE, moss=moss, ivy=ivy,
               detail=detail, twist=0.15 if sp == 'camphor' else 0.0, flecks=flecks, sky_side=0.2)


def build(outdir, quick=False):
    P = Painting('S09', W, H, M, outdir)
    rng = rng_for('S09')

    # ---------------------------------------------------------------- sky
    cv = P.layer('sky', 0.0)
    stops = [C(150, 150, 204), C(222, 180, 192), C(250, 210, 172), C(255, 230, 190), C(250, 232, 206)]
    sky(cv, rng, stops, [0, 0.2, 0.45, 0.75, 1.0], sun=SUN, glow=(700, C(255, 238, 200), 0.9), n_strokes=0.8,
        stroke_w=(24, 80), stroke_len=(200, 600), angle=-0.08)
    b = cumulus_blobs(rng, 1250, 170, 520, 90, lumpy=0.1, puff=(0.15, 0.3))
    paint_clouds(cv, rng, b, [C(150, 128, 178), C(200, 158, 184), C(244, 190, 170), C(255, 222, 176),
                              C(255, 242, 210)], light3=(0.6, -0.6, 0.2), leaf=11, rim=C(255, 238, 200), rim_amt=0.7)
    P.add('sky', 0.0, cv, 'dawn sky (patch visible at the top) and glowing horizon mist; opaque')

    # ---------------------------------------------------------------- far
    cv = P.layer('far', 0.25)
    for (dd, n_, wr, lf) in [(0.8, 14, (10, 32), 4.5), (0.66, 10, (16, 56), 5.5)]:
        forest_row(cv, rng, -80, 2000, HZ + 5, -150, n_, dd, HAZE, L3, SUN2, mist_col=HAZE_W,
                   mist_band=(HZ - 400, HZ + 5), width=wr, leaf=lf, branches=(1, 3), saplings=0.5, vines=0.35,
                   fade_p=0.4, top_jitter=60, leaf_size=30 if dd > 0.75 else 40)
        mist(cv, rng, -100, 2020, HZ - 600, HZ + 20, HAZE_W, HAZE_C, density=0.45, opacity=(0.04, 0.1),
             size=(200, 600), aspect=(0.1, 0.25), profile='bottom')
    b = Blobs()
    for x in np.linspace(-80, 2000, 20):
        r = rng.uniform(70, 130)
        b.add(x + rng.normal(0, 40), rng.uniform(-60, 140), r, r * 0.72, light=rng.uniform(0.8, 1.05),
              hue=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.62, HAZE, L3, SUN2, 7, density=0.8, trans_amt=0.5, rim_amt=0.6, lz=-0.3)
    undergrowth(cv, rng, HZ + 4, -60, 1980, 0.6, HAZE, L3, SUN2, leaf=5, height=(20, 90))
    mist(cv, rng, -100, 2020, HZ - 420, HZ + 20, HAZE_W, HAZE_C, density=1.2, opacity=(0.05, 0.14),
         size=(160, 480), aspect=(0.1, 0.24), profile='bottom')
    P.add('far', 0.25, cv, 'far trunks rising from the low horizon into mist; hazy canopy')

    # ---------------------------------------------------------------- mid
    cv = P.layer('mid', 0.5)
    for (x, wb, sp) in [(700, 70, 'beech'), (1180, 90, 'camphor'), (1460, 60, 'cedar')]:
        up_trunk(cv, rng, x, wb, 0.35, sp, moss=0.8, ivy=0.2, yb=HZ + 25, detail=0.6)
    b = Blobs()
    for (cx, cy, n_) in [(300, 10, 14), (1150, -20, 10), (1750, 30, 14)]:
        for k in range(n_):
            r = rng.uniform(60, 110)
            b.add(cx + rng.normal(0, 200), cy + abs(rng.normal(0, 80)), r, r * 0.75, light=rng.uniform(0.8, 1.1),
                  hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.2, HAZE, L3, SUN2, 11, density=0.9, trans_amt=0.6, rim_amt=0.8, lz=-0.4)
    for i in range(8):
        x = rng.uniform(400, 1800)
        vine(cv, x, rng.uniform(40, 140), rng.uniform(300, 650), rng, C(44, 46, 52), C(30, 56, 58), C(128, 156, 80),
             leaf=rng.uniform(11, 15), width=2.3, sun2=SUN2)
    beams(cv, rng, (SUN[0], -60), np.radians([104, 110, 117, 125]), 1300, [80, 120, 60, 100], C(255, 238, 192),
          opacity=0.28, spread_w=1.5, streak=0.6)
    P.add('mid', 0.5, cv, 'mid trunks, canopy and vines at the top, beams (robot goes above this layer)')

    # ---------------------------------------------------------------- near: trunks rising up the frame edges
    cv = P.layer('near', 0.8)
    up_trunk(cv, rng, -40, 330, 0.0, 'camphor', moss=1.3, ivy=0.5, yb=H + 80, detail=0.9)
    up_trunk(cv, rng, 1900, 300, 0.0, 'beech', moss=1.1, ivy=0.1, yb=H + 80, detail=0.9)
    P.add('near', 0.8, cv, 'huge trunks rising up both frame edges')

    # ---------------------------------------------------------------- fg: extreme foreground ferns and grass
    cv = P.layer('fg', 1.0)
    for (x, s_, lean) in [(120, 420, 0.25), (420, 330, 0.0), (900, 260, 0.1), (1300, 340, -0.1), (1700, 420, -0.25),
                          (1960, 380, -0.4)]:
        fern(cv, rng, x, H + 120, s_, sun2=SUN2, light=0.7, lean=lean, spread=0.85)
    for x in rng.uniform(-40, 1960, 30):
        grass(cv, rng, x, H + 30, rng.uniform(120, 260), light=0.7, sun2=SUN2, n=int(rng.integers(6, 12)))
    P.add('fg', 1.0, cv, 'extreme foreground ferns and grass along the bottom')

    P.save(sun=list(SUN), horizon_y=HZ, robot_between=['mid', 'near'])
    return P
