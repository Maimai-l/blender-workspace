"""S04 - behind the chest: deep forest interior at low height (1920 x 1040),
ferns and ground mist, cool and dark with warm glints. The chest fills most of
the frame (only the left strip and the top show)."""
import numpy as np

from ..color import C, mix, aerial, jitter
from ..noise import rng_for
from ..canvas import dabs
from ..layers import Painting
from ..sky import sky
from ..atmos import mist, glow
from ..forest import far_trunks, leafy_mass, undergrowth, forest_row
from ..ground import fern
from ..foliage import Blobs

W, H, M = 1920, 1040, 40
HZ = 140.0
L3 = (0.5, -0.8, -0.4)
SUN2 = (0.53, -0.85)
HAZE = C(120, 128, 150)
HAZE_W = C(196, 186, 176)


def build(outdir, quick=False):
    P = Painting('S04', W, H, M, outdir)
    rng = rng_for('S04')

    cv = P.layer('far', 0.2)
    stops = [C(84, 96, 120), C(120, 126, 148), C(150, 148, 160), C(108, 116, 130), C(64, 76, 92)]
    sky(cv, rng, stops, [0, 0.12, 0.2, 0.5, 1.0], sun=(260, 120), glow=(500, C(236, 210, 170), 0.5), n_strokes=0.6)
    xs = np.sort(rng.uniform(-40, 1960, 16))
    for (dd, n_, wr, lf) in [(0.55, 12, (16, 50), 5.0), (0.3, 8, (40, 120), 7.0)]:
        forest_row(cv, rng, -80, 2000, H + 80, -200, n_, dd, HAZE, L3, SUN2, width=wr, leaf=lf, branches=(1, 3),
                   saplings=0.0, vines=0.4, fade_p=0.2, top_jitter=20, leaf_size=40 if dd > 0.5 else 56)
        mist(cv, rng, -100, 2020, 60, 700, HAZE_W, HAZE, density=0.5, opacity=(0.04, 0.1), size=(200, 560),
             aspect=(0.1, 0.22), profile='mid')
    mist(cv, rng, -100, 2020, 60, 520, HAZE_W, HAZE, density=0.9, opacity=(0.04, 0.1), size=(200, 560),
         aspect=(0.1, 0.22), profile='mid')
    P.add('far', 0.2, cv, 'deep cool forest interior at low height, ground mist; opaque')

    cv = P.layer('mid', 0.6)
    pal = dict(dark=C(14, 26, 36), mid=C(28, 52, 54), lit=C(70, 100, 70), tip=C(236, 196, 120))
    for (x, y, s_, lean) in [(80, 1100, 420, 0.3), (300, 1060, 300, 0.1), (60, 700, 260, 0.4), (220, 520, 200, 0.2),
                             (120, 330, 180, 0.3)]:
        fern(cv, rng, x, y, s_, pal=pal, sun2=SUN2, light=0.8, lean=lean, spread=0.9)
    # warm glints: tiny sunlit leaf edges in the dark
    n = 160
    gx = rng.uniform(0, 560, n)
    gy = rng.uniform(0, 1040, n)
    dabs(cv, gx, gy, rng.uniform(3, 9, n), jitter(C(255, 214, 140), rng, n, dl=0.05), aspect=0.5, shape='leaf',
         angle=rng.uniform(0, 6.28, n), opacity=rng.uniform(0.5, 1.0, n), edge=0.3, rng=rng)
    P.add('mid', 0.6, cv, 'dark ferns at the left strip with warm glints')

    P.save(note_robot='the chest covers x > ~0.07 of the frame; paint visible on the left strip and top')
    return P
