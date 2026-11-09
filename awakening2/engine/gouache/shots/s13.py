"""S13 - high angle down on the clearing (2200 x 1200, room for shake).

Forest floor: moss, litter, roots, fallen logs, stones, shrub tops; the bases of
the giant trunks lean out of frame toward the camera; the clearing centre (robot
crouches right of centre) is open. Ferns are their own layer (the wind ring
flattens them radially). Light from the bottom of the frame (layout arrow).
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, fbm
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs
from ..atmos import mist, dapple, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, surface_roots, giant
from ..ground import fern, grass, stone, flowers

W, H, M = 2200, 1200, 40
L3 = (0.15, 0.6, 0.55)          # sun toward the bottom of the frame, raised
SUN2 = (0.24, 0.97)
CENTRE = (1330.0, 380.0)        # where the robot crouches
HAZE = C(236, 224, 210)


def build(outdir, quick=False):
    P = Painting('S13', W, H, M, outdir)
    rng = rng_for('S13')

    # ---------------------------------------------------------------- ground
    cv = P.layer('ground', 0.3)
    X, Y = cv.coords()
    n1 = fbm(cv.shape[0], cv.shape[1], 420, rng, octaves=4)
    n2 = fbm(cv.shape[0], cv.shape[1], 120, rng, octaves=3)
    clear = np.exp(-(((X - CENTRE[0]) / 650) ** 2 + ((Y - CENTRE[1]) / 480) ** 2))
    v = np.clip(0.25 + 0.45 * n1 + 0.15 * (n2 - 0.5) + 0.25 * clear, 0, 1)
    base = ramp([C(32, 48, 60), C(58, 86, 70), C(104, 128, 78), C(176, 176, 102)], v, [0, 0.35, 0.7, 1.0])
    litter = smoothstep(0.62, 0.8, n2) * (1 - clear)
    base = mix(base, C(132, 104, 84), (litter * 0.6)[..., None])
    cv.img[..., :3] = base
    cv.img[..., 3] = 1
    # moss / litter texture dabs over everything
    n = 90000
    xs = rng.uniform(-40, W + 40, n)
    ys = rng.uniform(-40, H + 40, n)
    ix = np.clip((xs + cv.m).astype(int), 0, cv.shape[1] - 1)
    iy = np.clip((ys + cv.m).astype(int), 0, cv.shape[0] - 1)
    cols = jitter(base[iy, ix], rng, dl=0.06, dc=0.18, dh=0.1)
    dabs(cv, xs, ys, rng.uniform(6, 20, n), cols, aspect=rng.uniform(0.3, 0.8, n), shape='flat', edge=0.3, rag=0.5,
         bristle=0.4, rng=rng)
    # roots radiating from the trunk bases
    bases = [(260, 200, 300), (2000, 260, 280), (180, 1060, 260)]
    specs = []
    for (bx, by, w) in bases:
        for k in range(7):
            a = rng.uniform(0, 2 * np.pi)
            L = rng.uniform(250, 650)
            specs.append(((bx + np.cos(a) * w * 0.3, by + np.sin(a) * w * 0.3),
                          (bx + np.cos(a) * L, by + np.sin(a) * L * 0.8), rng.uniform(26, 50)))
    surface_roots(cv, rng, specs, L3)
    # fallen logs
    bark = species('camphor')
    for (p0, p1, w) in [((420, 760), (1080, 980), 90), ((1650, 900), (2150, 700), 70)]:
        p0 = np.asarray(p0, np.float32)
        p1 = np.asarray(p1, np.float32)
        pts = catmull(np.array([p0, (p0 + p1) / 2 + rng.normal(0, 20, 2), p1]), n=30)
        paint_tube(cv, pts, np.linspace(w, w * 0.8, 30), rng, bark, L3, moss=2.5, detail=0.8)
    # stones
    for (x, y, r) in [(820, 560, 50), (1960, 560, 44), (640, 1060, 60), (1180, 820, 34), (300, 640, 40)]:
        stone(cv, rng, x, y, r, sun2=SUN2, moss=1.6, flatten=0.8)
    # dappled light, flowers
    xs = rng.uniform(100, W - 100, 14)
    ys = rng.uniform(80, H - 80, 14)
    dapple(cv, rng, xs, ys, rng.uniform(70, 130, 14), C(206, 200, 116), flatten=0.7, opacity=(0.25, 0.5), cluster=6,
           mode='lock', edge=0.8)
    fx = rng.uniform(0, W, 160)
    fy = rng.uniform(0, H, 160)
    flowers(cv, rng, fx, fy, rng.uniform(4, 8, 160))
    P.add('ground', 0.3, cv, 'forest floor seen from above: moss, litter, roots, logs, stones; opaque')

    # ---------------------------------------------------------------- shrubs (tops seen from above)
    cv = P.layer('shrubs', 0.45)
    b = Blobs()
    for (cx, cy, n_) in [(520, 420, 9), (1900, 1000, 10), (980, 1120, 7), (120, 520, 6), (2120, 420, 7),
                         (1500, 1150, 5)]:
        for k in range(n_):
            r = rng.uniform(45, 90)
            b.add(cx + rng.normal(0, 90), cy + rng.normal(0, 70), r, r * 0.85, light=rng.uniform(0.85, 1.1),
                  hue=rng.normal(0, 0.06), val=rng.normal(0, 0.05), rng=rng, lumpy=0.22)
    leafy_mass(cv, rng, b, 0.0, HAZE, L3, SUN2, 12, density=0.9, trans_amt=0.3, rim_amt=0.6, lz=0.6, droop=0.0,
               under=0.0)
    P.add('shrubs', 0.45, cv, 'shrub tops')

    # ---------------------------------------------------------------- ferns (separate: flattened by the wind ring)
    cv = P.layer('ferns', 0.6)
    pts = []
    for i in range(70):
        x = rng.uniform(-40, W + 40)
        y = rng.uniform(-40, H + 40)
        if np.hypot((x - CENTRE[0]) / 520, (y - CENTRE[1]) / 400) < 1.0:
            continue
        pts.append((x, y))
    for (x, y) in pts:
        s_ = rng.uniform(70, 150)
        fern(cv, rng, x, y, s_, sun2=SUN2, light=0.95, spread=2.5, n_fronds=int(rng.integers(8, 13)), droop=0.4)
    P.add('ferns', 0.6, cv, 'fern rosettes (centres listed in layers.json: flatten radially from the robot)')

    # ---------------------------------------------------------------- trunks leaning toward the camera
    cv = P.layer('trunks', 1.0)
    for (bx, by, w, tx, ty, sp) in [(260, 200, 300, -260, -300, 'camphor'), (2000, 260, 280, 2500, -260, 'beech'),
                                    (180, 1060, 260, -300, 1500, 'camphor')]:
        pts, ww = trunk_path(rng, (bx, by), (tx, ty), w, w * 1.9, sway=0.02, bulge=0.06, flare=0.4, flare_h=0.1)
        paint_tube(cv, pts, ww, rng, species(sp), L3, moss=1.4, ivy=0.4 if sp == 'camphor' else 0.1, detail=0.9,
                   twist=0.1, flecks=0.2)
    P.add('trunks', 1.0, cv, 'giant trunk bases leaning out of frame toward the camera')

    P.save(robot_centre=list(CENTRE), fern_centres=[list(map(float, p)) for p in pts], light_dir=list(L3))
    return P
