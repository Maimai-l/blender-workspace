"""S06 - treetops against the dawn sky, seen from below (1920 x 1040).

The canopy edge of huge trees rises along the bottom and the sides, silhouetted
with warm rims; branches reach into a peach-gold sky; the upper middle stays open
for the flock that bursts out of the canopy.
"""
import numpy as np

from ..color import C, mix, aerial, jitter
from ..noise import rng_for
from ..canvas import stroke, taper
from ..layers import Painting
from ..foliage import Blobs, spray
from ..sky import sky, cumulus_blobs, paint_clouds, sculpted_cloud
from ..atmos import glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, layered_mass

W, H, M = 1920, 1040, 48
SUN = (1180.0, 760.0)          # low, behind the canopy (glow through it)
L3 = (0.1, 0.4, -0.85)
SUN2 = (0.0, 1.0)
HAZE = C(255, 222, 186)
OPEN = (960.0, 300.0, 640.0, 260.0)   # sky kept clear for the flock


def build(outdir, quick=False):
    P = Painting('S06', W, H, M, outdir)
    rng = rng_for('S06')

    cv = P.layer('sky', 0.0)
    stops = [C(132, 132, 196), C(186, 160, 200), C(236, 186, 182), C(252, 210, 166), C(255, 226, 170),
             C(255, 238, 196)]
    sky(cv, rng, stops, [0, 0.2, 0.42, 0.62, 0.8, 1.0], sun=SUN, glow=(800, C(255, 236, 190), 0.9),
        n_strokes=0.9, stroke_w=(26, 90), stroke_len=(240, 800), angle=-0.06)
    cpal = [C(140, 118, 176), C(194, 150, 182), C(242, 186, 168), C(255, 220, 176), C(255, 242, 212)]
    for (cx, by, w_, h_, kind) in [(150, 330, 760, 200, 'cumulus'), (1780, 250, 620, 110, 'strato')]:
        sculpted_cloud(cv, rng, cx, by, w_, h_, cpal, kind=kind, light3=(0.1, 0.6, 0.15), rim=C(255, 238, 200),
                       rim_amt=0.8, under=0.3)
    P.add('sky', 0.0, cv, 'peach-gold dawn sky; upper middle kept open for the flock; opaque')

    # ---------------------------------------------------------------- far crowns (hazier, lower)
    cv = P.layer('canopy_far', 0.4)
    b = Blobs()
    for x in np.linspace(-120, 2040, 16):
        top = 690 + 110 * np.sin(x / 260 + 1.0) + rng.normal(0, 40)
        layered_mass(b, rng, x + rng.normal(0, 40), top + 60, rng.uniform(90, 140), flat=0.8, droop=0.2)
    leafy_mass(cv, rng, b, 0.3, C(255, 214, 180), (0.0, -0.3, -0.9), (0.0, -1.0), 8, density=0.9, trans_amt=1.0,
               rim_amt=1.0, lz=-0.8,
               stops=[C(76, 66, 102), C(96, 94, 116), C(124, 128, 108), C(206, 182, 112), C(255, 216, 142)])
    P.add('canopy_far', 0.4, cv, 'distant crowns along the bottom, glowing edges')

    # ---------------------------------------------------------------- near canopy edge + branches
    cv = P.layer('canopy', 0.85)
    bark = species('camphor')
    bark.mid = mix(bark.dark, bark.mid, 0.5)
    # branches reaching up into the sky from the canopy (left and right, clear of the flock)
    for (p0, p1, w) in [((-60, 1100), (520, 520), 70), ((260, 1100), (700, 700), 40), ((1980, 1080), (1400, 520), 66),
                        ((1650, 1100), (1240, 760), 36), ((420, 720), (560, 380), 16), ((1500, 700), (1380, 360), 14),
                        ((150, 760), (60, 420), 14)]:
        p0 = np.asarray(p0, np.float32)
        p1 = np.asarray(p1, np.float32)
        pts = np.array([p0, (p0 + p1) / 2 + rng.normal(0, 25, 2), p1])
        paint_tube(cv, pts, np.linspace(w, w * 0.35, 3), rng, bark, (0.0, -0.3, -0.85), moss=0.5, detail=0.6,
                   end_fade=0.05, rim_amt=1.4)
    b = Blobs()
    for (cx, cy, R, n_) in [(200, 860, 150, 7), (1720, 840, 150, 7), (960, 1000, 160, 6), (560, 560, 60, 3),
                            (1380, 540, 60, 3), (90, 470, 55, 2), (520, 700, 90, 3), (1420, 690, 90, 3)]:
        for k in range(n_):
            x = cx + rng.normal(0, R * 1.2)
            y = cy + rng.normal(0, R * 0.7)
            if ((x - OPEN[0]) / OPEN[2]) ** 2 + ((y - OPEN[1]) / OPEN[3]) ** 2 < 1:
                continue
            layered_mass(b, rng, x, y, R * rng.uniform(0.6, 1.0), flat=0.7, droop=0.25)
    leafy_mass(cv, rng, b, 0.0, HAZE, (0.0, -0.3, -0.85), (0.0, -1.0), 13, density=0.9, trans_amt=1.0, rim_amt=1.2,
               lz=-0.8, stops=[C(30, 34, 56), C(42, 58, 70), C(64, 92, 76), C(150, 150, 82), C(236, 204, 112)])
    for i in range(8):
        x = rng.choice([rng.uniform(250, 650), rng.uniform(1280, 1680)])
        y = rng.uniform(520, 720)
        a = -np.pi / 2 + rng.normal(0, 0.5)
        spray(cv, x, y, a, rng.uniform(150, 260), rng.uniform(22, 32), C(26, 32, 48), C(96, 100, 66), rng,
              stem_col=C(30, 26, 40), droop=0.0, sun2=(0.0, -1.0), curl=rng.normal(0, 0.4), rim=C(255, 214, 140))
    P.add('canopy', 0.85, cv, 'near canopy: readable leaf clumps with warm rims, branches reaching into the sky')

    P.save(sun=list(SUN), open_sky=list(OPEN))
    return P
