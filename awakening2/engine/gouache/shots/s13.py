"""S13 - high angle down on the clearing (2200 x 1200, room for shake).

Forest floor: moss, litter, roots, fallen logs, stones, shrub tops; giant trunk bases
on the rim of the clearing lean out under the canopy; a band of dense treetops seen
from above frames the clearing (layer `canopy`, nearest). The clearing centre is where
the robot crouches in the shot (painting ~(950, 560); shotfx uses window (0, 0)).
Ferns are their own layer (the wind ring flattens them radially): opaque, two-tone
fronds of four species with soft cast shadows. Light from the bottom of the frame.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, fbm
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs
from ..atmos import mist, dapple, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, surface_roots, giant, layered_mass
from ..sky import paint_planes
from ..foliage import render_gbuffer
from ..ground import fern, grass, stone, flowers, FERN_KINDS

W, H, M = 2200, 1200, 40
L3 = (0.15, 0.6, 0.55)          # sun toward the bottom of the frame, raised
SUN2 = (0.24, 0.97)
CENTRE = (950.0, 560.0)         # where the robot crouches (as composited in the shot)
OPEN = (980.0, 560.0, 760.0, 420.0)   # the canopy opening ellipse (cx, cy, rx, ry)
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
    Xg, Yg = cv.coords()
    cx_, cy_, rx_, ry_ = OPEN
    kk = np.hypot((Xg - cx_) / rx_, (Yg + 70 - cy_) / ry_)
    cv.lock_tint(C(30, 44, 58), (smoothstep(0.82, 1.02, kk) * 0.55).astype(np.float32))
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
    kinds = []
    for (x, y) in pts:
        kind = str(rng.choice(('sword', 'lady', 'bracken', 'hart'), p=[0.35, 0.25, 0.25, 0.15]))
        s_ = {'sword': rng.uniform(80, 160), 'lady': rng.uniform(70, 140), 'bracken': rng.uniform(110, 190),
              'hart': rng.uniform(50, 100)}[kind]
        nf = None if kind != 'sword' else int(rng.integers(7, 13))
        # soft cast shadow on the ground, away from the light (light comes from the bottom)
        ns = 14
        dabs(cv, x + rng.normal(0, s_ * 0.25, ns) - SUN2[0] * s_ * 0.18, y + rng.normal(0, s_ * 0.2, ns) - SUN2[1] * s_ * 0.18,
             rng.uniform(s_ * 0.5, s_ * 0.9, ns), C(18, 30, 30), aspect=0.75, edge=0.85, rag=0.4, bristle=0.3,
             opacity=0.18, rng=rng)
        fern(cv, rng, x, y, s_, sun2=SUN2, light=rng.uniform(0.85, 1.05), spread=2.5, n_fronds=nf,
             droop=rng.uniform(0.3, 0.6), kind=kind, lean=rng.uniform(-0.6, 0.6), body=1.0)
        kinds.append(kind)
    P.add('ferns', 0.6, cv, 'fern rosettes (centres listed in layers.json: flatten radially from the robot)')

    # ---------------------------------------------------------------- trunks leaning toward the camera
    cv = P.layer('trunks', 1.0)
    cx_, cy_, rx_, ry_ = OPEN
    for (a_deg, w, sp) in [(205, 200, 'camphor'), (322, 170, 'beech'), (30, 210, 'camphor')]:
        a = np.radians(a_deg)
        bx, by = cx_ + np.cos(a) * rx_ * 0.92, cy_ + np.sin(a) * ry_ * 0.92
        tx, ty = cx_ + np.cos(a) * rx_ * 1.6, cy_ + np.sin(a) * ry_ * 1.7
        pts, ww = trunk_path(rng, (bx, by), (tx, ty), w, w * 1.7, sway=0.02, bulge=0.06, flare=0.5, flare_h=0.12)
        bark = species(sp)
        bark.mid = mix(bark.dark, bark.mid, 0.5)
        bark.lit = mix(bark.mid, bark.lit, 0.5)
        paint_tube(cv, pts, ww, rng, bark, (L3[0], L3[1], -0.3), moss=1.4, ivy=0.0, detail=0.9, twist=0.1, flecks=0.0)
    P.add('trunks', 1.0, cv, 'giant trunk bases on the rim of the clearing, leaning out under the canopy')

    # ---------------------------------------------------------------- canopy: treetops seen from above
    cv = P.layer('canopy', 1.0)
    crowns = []
    for i in range(900):
        x = rng.uniform(-260, W + 260)
        y = rng.uniform(-260, H + 260)
        th = np.arctan2(y - cy_, x - cx_)
        rag = 1 + 0.12 * np.sin(th * 5 + 0.8) + 0.07 * np.sin(th * 11 + 2.0)
        k = np.hypot((x - cx_) / rx_, (y - cy_) / ry_) / rag
        if k < 1.08:
            continue
        crowns.append((k, x, y))
        if len(crowns) >= 120:
            break
    crowns.sort(key=lambda t: -t[0])                 # farthest-out (nearest the camera at the edges) first? no:
    crowns.sort(key=lambda t: t[0])                  # rim crowns first, the big outer ones on top
    b = Blobs()
    kinds_c = []
    for k, x, y in crowns:
        R = rng.uniform(90, 170) * (0.8 + 0.25 * min(k - 1.0, 1.5))
        kind = rng.choice(['broad', 'broad', 'conifer', 'flat'], p=[0.35, 0.3, 0.2, 0.15])
        if kind == 'conifer':
            # from above: a dark-centred star of radiating branch tiers
            for j in range(7):
                aa = j / 7 * 2 * np.pi + rng.normal(0, 0.2)
                b.add(x + np.cos(aa) * R * 0.45, y + np.sin(aa) * R * 0.45, R * 0.55, R * 0.22, rot=aa,
                      light=rng.uniform(0.85, 1.05), hue=0.12 + rng.normal(0, 0.03), val=-0.04, rng=rng, lumpy=0.3)
            b.add(x, y, R * 0.35, R * 0.35, light=0.9, hue=0.12, val=-0.02, rng=rng, lumpy=0.3)
        elif kind == 'flat':
            for j in range(int(rng.integers(5, 9))):
                b.add(x + rng.normal(0, R * 0.5), y + rng.normal(0, R * 0.5), R * rng.uniform(0.35, 0.55),
                      R * rng.uniform(0.3, 0.45), rot=rng.uniform(0, np.pi), light=rng.uniform(0.9, 1.1),
                      hue=-0.06 + rng.normal(0, 0.03), val=0.03, rng=rng, lumpy=0.22)
        else:
            # a broadleaf crown from above: many small domed clusters (each with a lit and a shadow side)
            for j in range(int(rng.integers(8, 14))):
                rr = R * rng.uniform(0.22, 0.42)
                rd = R * 0.6 * np.sqrt(rng.random())
                aa = rng.uniform(0, 2 * np.pi)
                b.add(x + np.cos(aa) * rd, y + np.sin(aa) * rd, rr, rr * rng.uniform(0.8, 0.95),
                      rot=rng.uniform(0, np.pi), light=rng.uniform(0.85, 1.1) * (1.05 - 0.25 * rd / R),
                      hue=rng.normal(0, 0.05), val=rng.normal(0, 0.04), rng=rng, lumpy=0.24)
        kinds_c.append(str(kind))
    G = render_gbuffer(cv, b, light3=(0.25, 0.8, 0.45), wrap=0.25, under=0.0)
    paint_planes(cv, rng, b, (C(20, 32, 44), C(38, 64, 58), C(96, 130, 72), C(184, 190, 104)), G=G, glob=0.0,
                 th=(0.36, 0.6, 0.88), noise_amt=0.08, strokes=0.6, leafy_edge=0.9, leaf_px=14,
                 leaf_cols=[C(20, 32, 44), C(52, 86, 64), C(124, 152, 80)], rim=C(232, 220, 146), rim_amt=0.5,
                 sun2=SUN2)
    P.add('canopy', 1.0, cv, 'band of dense treetops seen from above framing the clearing (nearest layer; the '
          'wind ring can cross it)')

    P.save(robot_centre=list(CENTRE), fern_centres=[list(map(float, p)) for p in pts], fern_kinds=kinds,
           light_dir=list(L3))
    return P
