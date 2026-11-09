"""S10 - RISE C, low-angle front: canopy high above with the gap of golden sky
directly above the robot's head; sunbeams down through the gap. 1920 x 1600: the
camera tilts up ~500 px (frames: start = rows 560-1600, end = rows 0-1040).
"""
import numpy as np

from ..color import C, mix, aerial, jitter, smoothstep
from ..noise import rng_for
from ..canvas import stroke, taper
from ..layers import Painting
from ..foliage import Blobs, vine
from ..sky import sky, cumulus_blobs, paint_clouds, sculpted_cloud
from ..atmos import beams, glow, mist
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, far_trunks, forest_row, layered_mass

W, H, M = 1920, 1600, 48
GAP = (780.0, 330.0, 560.0, 300.0)      # above the robot's head (robot ~x 0.12-0.62)
SUN = (980.0, 210.0)
L3 = (0.3, -0.85, -0.4)
SUN2 = (0.33, -0.94)
HAZE = C(240, 222, 210)
HAZE_W = C(255, 234, 200)
VP = (800.0, -2400.0)
TOPS = []


def gapk(x, y):
    cx, cy, rx, ry = GAP
    return np.sqrt(((np.asarray(x) - cx) / rx) ** 2 + ((np.asarray(y) - cy) / ry) ** 2)


def ring(cv, rng, d, n, rad, leaf, k_in, k_out, ymax, light_k=1.0):
    xs = rng.uniform(-150, W + 150, n * 5)
    ys = rng.uniform(-200, ymax, n * 5)
    # ragged, drooping lower edge (no shelf): the allowed depth varies along x
    edge = ymax * (0.55 + 0.45 * (0.5 + 0.5 * np.sin(xs / 170 + 1.3) * np.sin(xs / 61 + 0.4)))
    keep = ys < edge
    xs, ys = xs[keep], ys[keep]
    th = np.arctan2(ys - GAP[1], xs - GAP[0])
    rr = 1 + 0.16 * (np.sin(th * 5 + 0.7) * 0.6 + np.sin(th * 11 + 2.1) * 0.4)
    k = gapk(xs, ys) / rr
    ok = (k > k_in) & (k < k_out)
    xs, ys = xs[ok][:n], ys[ok][:n]
    # drop stragglers: every cluster must overlap a cluster above it (no hanging balls)
    o = np.argsort(ys)
    xs, ys = xs[o], ys[o]
    keep = np.ones(len(xs), bool)
    for i in range(len(xs)):
        if ys[i] < 120:
            continue
        above = (ys[:i] < ys[i]) & keep[:i]
        if not above.any() or np.min(np.hypot(xs[:i][above] - xs[i], ys[:i][above] - ys[i])) > rad * 1.3:
            keep[i] = False
    xs, ys = xs[keep], ys[keep]
    b = Blobs()
    for i in np.argsort(ys):
        r = rad * rng.uniform(0.6, 1.3)
        b.add(xs[i], ys[i], r, r * rng.uniform(0.65, 0.85), rot=rng.normal(0, 0.3),
              light=light_k * rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng,
              lumpy=0.18)
    leafy_mass(cv, rng, b, d, HAZE, L3, SUN2, leaf, density=0.9, trans_amt=0.65, rim_amt=0.85, lz=-0.45)


def up_trunk(cv, rng, xb, wb, d, sp, top_y, moss=1.0, ivy=0.3):
    yb = H + 100
    f = (yb - top_y) / (yb - VP[1])
    top = (xb + (VP[0] - xb) * f, top_y)
    TOPS.append((top[0], top_y, wb))
    pts, ww = trunk_path(rng, (xb, yb), top, wb, wb * 0.55, sway=0.012, bulge=0.07)
    paint_tube(cv, pts, ww, rng, species(sp, depth=d, haze=HAZE), L3, depth=d, haze=HAZE, moss=moss, ivy=ivy,
               detail=0.8, twist=0.15 if sp == 'camphor' else 0.0, flecks=0.3, end_fade=0.15, sky_side=0.2)


def build(outdir, quick=False):
    P = Painting('S10', W, H, M, outdir)
    rng = rng_for('S10')

    cv = P.layer('sky', 0.0)
    stops = [C(250, 222, 170), C(255, 214, 150), C(250, 200, 160), C(236, 214, 200), C(226, 214, 214)]
    sky(cv, rng, stops, [0, 0.15, 0.35, 0.65, 1.0], sun=SUN, glow=(700, C(255, 244, 210), 1.0), n_strokes=0.7)
    sculpted_cloud(cv, rng, 620, 380, 560, 140, [C(186, 140, 160), C(232, 176, 160), C(255, 212, 160),
                                                 C(255, 236, 196), C(255, 248, 224)], kind='cumulus',
                   light3=(0.4, -0.6, 0.1), rim=C(255, 242, 210), rim_amt=0.8)
    glow(cv, SUN[0], SUN[1], 150, C(255, 252, 236), 0.85)
    P.add('sky', 0.0, cv, 'golden sky in the gap above the robot; opaque')

    cv = P.layer('far', 0.25)
    xs = np.sort(rng.uniform(-40, 1960, 16))
    for (dd, n_, wr, lf) in [(0.76, 12, (14, 40), 5.0), (0.6, 8, (24, 70), 6.0)]:
        forest_row(cv, rng, -80, 2000, H + 60, 640, n_, dd, HAZE, L3, SUN2, mist_col=HAZE_W,
                   mist_band=(H - 500, H + 60), width=wr, leaf=lf, branches=(1, 2), saplings=0.0, vines=0.4,
                   fade_p=0.4, top_jitter=80, leaf_size=34 if dd > 0.7 else 44)
    ring(cv, rng, 0.55, 300, 44, 7, 0.95, 1.8, 900)
    mist(cv, rng, -100, 2020, 900, H + 40, HAZE_W, HAZE, density=0.8, opacity=(0.04, 0.12), size=(180, 560),
         aspect=(0.1, 0.25), profile='bottom')
    P.add('far', 0.25, cv, 'far trunks converging up into the high canopy around the gap')

    cv = P.layer('canopy', 0.6)
    TOPS.clear()
    for (xb, wb, sp, ty) in [(-120, 360, 'camphor', 200), (300, 160, 'beech', 560), (1500, 220, 'cedar', 420),
                             (1880, 380, 'camphor', 120)]:
        up_trunk(cv, rng, xb, wb, 0.1, sp, ty)
    # crowns where the trunks enter the canopy (no cut-off trunk tops)
    cb = Blobs()
    for (tx, ty, wb) in TOPS:
        if ty < 300:
            continue                      # these tops are already inside the canopy ring
        side = -1.0 if tx < W / 2 else 1.0
        for k in range(2):
            layered_mass(cb, rng, tx + side * wb * 0.3 + rng.normal(0, wb * 0.2), ty - k * wb * 0.45,
                         wb * rng.uniform(0.5, 0.7), flat=0.6, droop=0.4)
    leafy_mass(cv, rng, cb, 0.05, HAZE, L3, SUN2, 14, density=0.9, trans_amt=0.65, rim_amt=0.85, lz=-0.45)
    ring(cv, rng, 0.05, 300, 80, 14, 1.4, 4.0, 820, light_k=0.95)
    for i in range(10):
        x = rng.choice([rng.uniform(100, 420), rng.uniform(1300, 1750)])
        vine(cv, x, rng.uniform(300, 560), rng.uniform(400, 900), rng, C(40, 44, 50), C(26, 50, 52), C(128, 154, 78),
             leaf=rng.uniform(12, 17), width=2.5, sun2=SUN2)
    P.add('canopy', 0.6, cv, 'giant trunks rising at the sides into the dark canopy around the gap')

    cv = P.layer('beams', 0.75)
    angs = np.radians([92, 97, 102, 108, 114])
    beams(cv, rng, SUN, angs, 1700, [80, 130, 90, 150, 70], C(255, 240, 196), opacity=0.36, spread_w=1.6,
          streak=0.6, start_fade=0.1)
    P.add('beams', 0.75, cv, 'sunbeams down through the gap onto the face (robot goes above or below: '
          'above for silhouette, below for light on the face)')

    P.save(sun=list(SUN), frames=dict(start=[0, 560, 1920, 1040], end=[0, 0, 1920, 1040]), gap=list(GAP))
    return P
