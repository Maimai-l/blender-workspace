"""S05 - ground-level close-up by the knee (1920 x 1040; the ground fills the lower ~60 %).

Moss, clover, leaf litter, roots, small stones, ferns with dew-tipped fronds and a crack
in the soil near the robot's fingers (left-centre); blurred trunks and mist above.
Pebbles and dew drops are separate sprite layers (positions in layers.json) so they can
jump/sparkle during the tremor.
"""
import numpy as np
import cv2

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, fbm
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass
from ..sky import sky
from ..atmos import mist, glow, dapple
from ..forest import leafy_mass, surface_roots, forest_row, LEAF
from ..ground import fern, grass, stone, flowers

W, H, M = 1920, 1040, 40
HZ = 420.0
SUN = (1480.0, 160.0)
L3 = (0.5, -0.8, -0.3)
SUN2 = (0.53, -0.85)
HAZE = C(236, 222, 214)
HAZE_W = C(255, 234, 200)
HAZE_C = C(214, 206, 224)
CRACK = [(420, 905), (500, 893), (560, 900), (620, 880), (690, 874), (760, 858), (830, 852), (890, 836)]
FERN_TIPS = []


def scale_at(y):
    """Perspective size factor: 0 at the horizon -> 1 at the bottom edge."""
    return np.clip((np.asarray(y, np.float32) - HZ) / (H - HZ), 0, 1.2)


def blur_layer(cv, sigma):
    cv.img[:] = cv2.GaussianBlur(cv.img, (0, 0), sigma)


def fern_with_tips(cv, rng, x, y, s_, **kw):
    """Paint a fern and remember a few frond-tip positions for dew."""
    fern(cv, rng, x, y, s_, **kw)
    lean = kw.get('lean', 0.0)
    spread = kw.get('spread', 1.0)
    for a in -np.pi / 2 + lean + np.linspace(-1.1, 1.1, 5) * spread:
        L = s_ * 0.9
        FERN_TIPS.append((x + np.cos(a) * L * 0.85 + rng.normal(0, 6), y + np.sin(a) * L * 0.75 + L * 0.12))


def build(outdir, quick=False):
    FERN_TIPS.clear()
    P = Painting('S05', W, H, M, outdir)
    rng = rng_for('S05')

    # ---------------------------------------------------------------- far: blurred trunks and mist
    cv = P.layer('far', 0.2)
    stops = [C(204, 196, 214), C(238, 220, 206), C(255, 236, 206), C(250, 230, 202)]
    sky(cv, rng, stops, [0, 0.2, 0.42, 1.0], sun=SUN, glow=(800, C(255, 242, 210), 0.9), n_strokes=0.6)
    for (dd, n_, wr, lf) in [(0.74, 12, (20, 60), 5.0), (0.52, 7, (60, 160), 7.0)]:
        forest_row(cv, rng, -80, 2000, HZ + 10, -200, n_, dd, HAZE, L3, SUN2, mist_col=HAZE_W,
                   mist_band=(HZ - 220, HZ + 10), width=wr, leaf=lf, branches=(0, 1), saplings=0.0, vines=0.3,
                   fade_p=0.3, top_jitter=20, leaf_size=46 if dd > 0.7 else 64)
        mist(cv, rng, -100, 2020, HZ - 380, HZ + 20, HAZE_W, HAZE_C, density=0.6, opacity=(0.04, 0.11),
             size=(200, 600), aspect=(0.1, 0.25), profile='bottom')
    blur_layer(cv, 4.0)
    P.add('far', 0.2, cv, 'out-of-focus trunks and glowing mist; opaque')

    # ---------------------------------------------------------------- mid: the far ground band (soft)
    cv = P.layer('mid', 0.45)
    X, Y = cv.coords()
    t = scale_at(Y)
    base = ramp([aerial(C(130, 150, 104), 0.45, HAZE_W), C(96, 124, 82), C(70, 100, 74)], np.clip(t * 3, 0, 1))
    cv.over(base, smoothstep(HZ - 4, HZ + 10, Y) * (Y < HZ + 260))
    from ..forest import undergrowth
    undergrowth(cv, rng, HZ + 12, -80, 2000, 0.4, HAZE_W, L3, SUN2, leaf=5, height=(10, 90), centre=(900, 1000), n=70)
    for x in rng.uniform(-40, 1960, 16):
        fern(cv, rng, x, HZ + rng.uniform(10, 40), rng.uniform(30, 60), depth=0.35, haze=HAZE_W, sun2=SUN2, light=0.9)
    mist(cv, rng, -100, 2020, HZ - 40, HZ + 60, HAZE_W, HAZE_C, density=1.2, opacity=(0.05, 0.13),
         size=(120, 360), aspect=(0.07, 0.14), profile='mid')
    blur_layer(cv, 1.5)
    P.add('mid', 0.45, cv, 'far ground band and low mist at the horizon (slightly soft)')

    # ---------------------------------------------------------------- ground: the close floor
    cv = P.layer('ground', 0.8)
    X, Y = cv.coords()
    t = scale_at(Y)
    n1 = fbm(cv.shape[0], cv.shape[1], 360, rng, octaves=4)
    n2 = fbm(cv.shape[0], cv.shape[1], 140, rng, octaves=3)
    v = np.clip(0.62 - 0.32 * t + 0.28 * (n1 - 0.5), 0, 1)
    base = ramp([C(30, 42, 60), C(52, 82, 68), C(104, 132, 78), C(186, 184, 108)], v, [0, 0.35, 0.7, 1])
    soil = smoothstep(0.66, 0.82, n2)
    base = mix(base, C(104, 82, 68), (soil * 0.55)[..., None])
    cv.over(base, smoothstep(HZ + 30, HZ + 70, Y))
    # moss texture in perspective rows (dabs grow toward the camera)
    for r_ in range(56):
        tt = (r_ + rng.random()) / 56
        y = HZ + 40 + (H + 40 - HZ - 40) * tt ** 1.35
        sz = 5 + 46 * tt ** 1.5
        n = int(W / (sz * 0.45) * 1.6)
        xs = rng.uniform(-30, W + 30, n)
        ys = y + rng.normal(0, sz * 0.25, n)
        ix = np.clip((xs + cv.m).astype(int), 0, cv.shape[1] - 1)
        iy = np.clip((ys + cv.m).astype(int), 0, cv.shape[0] - 1)
        cols = jitter(base[iy, ix], rng, dl=0.07, dc=0.2, dh=0.1)
        dabs(cv, xs, ys, sz * rng.uniform(0.6, 1.3, n), cols, aspect=rng.uniform(0.35, 0.8, n), edge=0.3, rag=0.6,
             bristle=0.3, rng=rng)
    # fallen leaves lying flat (ochre, rust, brown), foreshortened
    centres = np.array([[300, 700], [560, 860], [820, 640], [1150, 900], [1420, 700], [1700, 860], [980, 1010],
                        [200, 960]], np.float32)
    nl = 240
    ci = rng.integers(0, len(centres), nl)
    ly = centres[ci, 1] + rng.normal(0, 40, nl)
    lx = centres[ci, 0] + rng.normal(0, 130, nl)
    s_ = 8 + 46 * scale_at(ly) ** 1.3
    lc = jitter(np.array([[(150, 118, 76), (138, 92, 66), (112, 84, 70), (168, 142, 88), (124, 108, 70)][i]
                          for i in rng.integers(0, 5, nl)], np.float32) / 255, rng, dl=0.04, dc=0.12, dh=0.05)
    order = np.argsort(ly)
    dabs(cv, lx[order], ly[order], s_[order], lc[order], aspect=rng.uniform(0.18, 0.32, nl)[order],
         angle=rng.normal(0, 0.35, nl)[order], shape='leaf', edge=0.25, rag=0.15, bristle=0.2, split=0.14, rng=rng)
    # roots crossing the floor
    surface_roots(cv, rng, [((-40, 640), (560, 700), 44), ((1180, 600), (1960, 660), 40),
                            ((960, 560), (1320, 760), 26), ((-60, 960), (420, 1060), 70)], L3)
    # the crack in the soil near the fingers (left-centre)
    P_ = np.array(CRACK, np.float32)
    m_ = 300
    t_ = rng.uniform(0, 1, m_)
    i_ = np.minimum((t_ * (len(P_) - 1)).astype(int), len(P_) - 2)
    q_ = P_[i_] + (P_[i_ + 1] - P_[i_]) * (t_ * (len(P_) - 1) - i_)[:, None]
    dabs(cv, q_[:, 0] + rng.normal(0, 28, m_), q_[:, 1] + rng.normal(0, 9, m_), rng.uniform(10, 24, m_),
         jitter(mix(C(92, 72, 62), C(150, 120, 90), rng.random(m_)[:, None]), rng, dl=0.03), aspect=0.45,
         angle=rng.normal(0, 0.2, m_), shape='flat', edge=0.3, rag=0.6, rng=rng)
    zz = [P_[0]]
    for i in range(len(P_) - 1):
        for f in np.linspace(0.25, 1.0, 4):
            zz.append(P_[i] + (P_[i + 1] - P_[i]) * f + np.array([0, rng.normal(0, 5)]))
    zz = np.array(zz, np.float32)
    wz = (4 + 10 * np.sin(np.linspace(0, np.pi, len(zz))) ** 0.7) * rng.uniform(0.6, 1.3, len(zz))
    stroke(cv, zz + [0, -3], wz * 1.25, C(214, 182, 128), opacity=0.85, bristle=0.4, rag=0.5, rng=rng, smooth=False)
    stroke(cv, zz, wz, C(26, 20, 28), bristle=0.2, rag=0.7, rng=rng, smooth=False)
    for k in range(6):
        i = int(rng.integers(1, len(zz) - 1))
        a_ = rng.uniform(0, 2 * np.pi)
        q = zz[i] + np.array([np.cos(a_), 0.35 * np.sin(a_)]) * rng.uniform(25, 60)
        stroke(cv, [zz[i], (zz[i] + q) / 2 + rng.normal(0, 5, 2), q], taper(3, 1.0, 0.1, 5), C(36, 28, 34), rng=rng)
    # small embedded mossy stones
    for i in range(14):
        y = HZ + 80 + (H - HZ - 60) * rng.random() ** 0.8
        x = rng.uniform(0, W)
        r = 6 + 34 * scale_at(y)
        stone(cv, rng, x, y, r, col_dark=C(46, 44, 54), col_mid=C(104, 98, 92), col_lit=C(196, 182, 150),
              sun2=SUN2, moss=1.0, flatten=0.55)
    # clover patches (trefoils) in perspective
    for (cx, cy, nn) in [(260, 760, 70), (1450, 820, 70), (980, 620, 40), (1760, 700, 50), (620, 560, 30),
                         (120, 980, 40), (1240, 980, 40)]:
        sc = 0.35 + scale_at(cy)
        xs = cx + rng.normal(0, 120 * sc, nn)
        ys = cy + rng.normal(0, 34 * sc, nn)
        lsz = 14 * sc * rng.uniform(0.8, 1.3, nn)
        for j in range(3):
            ang = j * 2.09 + rng.uniform(0, 2.09, nn)
            cols = jitter(mix(C(56, 104, 68), C(156, 194, 104), rng.random(nn)[:, None]), rng, dl=0.03)
            dabs(cv, xs + np.cos(ang) * lsz * 0.5, ys + np.sin(ang) * lsz * 0.32, lsz, cols, aspect=0.85, angle=ang,
                 shape='petal', edge=0.25, rag=0.1, split=0.12, rng=rng)
        FERN_TIPS.extend([(float(a), float(b_)) for a, b_ in zip(xs[::12], ys[::12] - lsz[::12] * 0.3)])
    # ferns (tips carry dew)
    for (x, y, s_, lean) in [(70, 1080, 340, 0.3), (1860, 1080, 360, -0.3), (1250, 1060, 240, -0.1),
                             (360, 700, 150, 0.1), (1620, 640, 140, -0.1), (900, 560, 90, 0.0), (1100, 600, 110, 0.1)]:
        fern_with_tips(cv, rng, x, y, s_, sun2=SUN2, light=0.85, lean=lean, spread=0.85)
    xs = rng.uniform(100, 1800, 14)
    ys = rng.uniform(560, 960, 14)
    dapple(cv, rng, xs, ys, 30 + 70 * scale_at(ys), C(222, 210, 122), flatten=0.3, opacity=(0.35, 0.7), cluster=6,
           mode='lock')
    flowers(cv, rng, rng.uniform(0, W, 40), rng.uniform(520, 1000, 40), rng.uniform(5, 11, 40))
    yy = cv.ys()[:, None]
    xx = cv.xs()[None, :]
    cv.lock_tint(C(30, 40, 66), (smoothstep(820, 1060, yy) * 0.45 * np.ones_like(xx)).astype(np.float32))
    warm_band = np.exp(-((yy - 560) / 90) ** 2) * (0.4 + 0.6 * smoothstep(400, 1700, xx))
    cv.lock_tint(C(232, 214, 140), (warm_band * 0.28).astype(np.float32))
    P.add('ground', 0.8, cv, 'close mossy floor (lower 60 %): litter, roots, clover, ferns, crack near the fingers')

    # ---------------------------------------------------------------- pebbles (sprites)
    cv = P.layer('pebbles', 0.85)
    peb = []
    for i in range(18):
        x = rng.uniform(380, 1150)
        y = rng.uniform(760, 1000)
        r = (7 + 16 * scale_at(y)) * rng.uniform(0.7, 1.3)
        stone(cv, rng, x, y, r, col_dark=C(46, 44, 54), col_mid=C(110, 102, 96), col_lit=C(204, 190, 158),
              sun2=SUN2, moss=0.3 if rng.random() < 0.3 else 0.0, flatten=0.62)
        peb.append([round(float(x), 1), round(float(y), 1), round(float(r), 1)])
    P.add('pebbles', 0.85, cv, 'loose pebble sprites (layers.json "pebbles": x, y, r) - make them jump',
          grain_amt=0.02)

    # ---------------------------------------------------------------- dew drops (sprites)
    cv = P.layer('dew', 0.9)
    tips = np.array(FERN_TIPS, np.float32)
    tips = tips[(tips[:, 1] > HZ + 40) & (tips[:, 0] > -10) & (tips[:, 0] < W + 10)]
    r = 2.0 + 4 * scale_at(tips[:, 1])
    dabs(cv, tips[:, 0], tips[:, 1] + r * 0.2, r * 2.2, C(36, 64, 66), aspect=0.95, edge=0.3, rag=0.05, bristle=0.0,
         rng=rng, opacity=0.6)
    dabs(cv, tips[:, 0], tips[:, 1], r * 1.9, C(200, 226, 206), aspect=0.95, edge=0.35, rag=0.05, bristle=0.0, rng=rng,
         opacity=0.8)
    dabs(cv, tips[:, 0] + r * 0.3, tips[:, 1] - r * 0.35, r * 0.7, C(255, 252, 236), aspect=0.9, edge=0.4, rag=0.0,
         bristle=0.0, rng=rng)
    P.add('dew', 0.9, cv, 'dew drops on fern tips and clover (layers.json "dew": x, y) - sparkle/shake them',
          grain_amt=0.0)

    P.save(sun=list(SUN), horizon_y=HZ, pebbles=peb, crack=CRACK,
           dew=[[round(float(a), 1), round(float(b_), 1)] for a, b_ in tips],
           robot_between=['ground', 'pebbles'], note_robot='fingers/knee go above `ground`; pebbles and dew in front')
    return P
