"""S12 - behind the robot looking toward the sun (1920 x 1040, horizon y ~600).

Backlit forest interior: the sun glows through the mist between trunks; trunks
are dark silhouettes with gold rims; their shadows and the light rays between
them run toward the camera. The robot (back 3/4, x ~0.22-0.62) goes between
`beams` and `fg`.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, vine
from ..atmos import mist, beams, glow, clean_shaft, light_stripes
from ..trees import species, paint_tube, trunk_path, buttress_roots, Frame
from ..canvas import catmull
from ..forest import leafy_mass, far_trunks, broadleaf, floor, undergrowth, layered_mass
from ..ground import fern, grass

W, H, M = 1920, 1040, 48
HZ = 600.0
SUN = (1250.0, 455.0)
HAZE = C(255, 226, 180)
HAZE_W = C(255, 236, 200)
HAZE_C = C(200, 178, 196)


def sunward(x, y):
    """Unit 2-D vectors from points toward the sun."""
    dx, dy = SUN[0] - np.asarray(x, np.float32), SUN[1] - np.asarray(y, np.float32)
    n = np.hypot(dx, dy) + 1e-6
    return dx / n, dy / n


def warm(x, y):
    d = np.hypot((np.asarray(x) - SUN[0]) / 900, (np.asarray(y) - SUN[1]) / 500)
    return np.clip(1.1 - d, 0, 1)


def backlit_trunk(cv, rng, x, wb, d, top=-120, base=None, sp='camphor', moss=0.6, roots=0, branches=0,
                  leaves=None):
    """Backlit silhouette trunk with real taper, lean, root flare, optional buttress
    roots and a few branches (with small leaf masses collected into `leaves`)."""
    base = HZ + 30 + (1 - d) * 300 if base is None else base
    Ht = base - top
    lean = rng.normal(0, 0.06)
    pts, ww = trunk_path(rng, (x, base), (x + lean * Ht, top), wb, wb * rng.uniform(0.32, 0.55),
                         sway=rng.uniform(0.01, 0.03), bulge=0.09, flare=rng.uniform(0.5, 0.95), flare_h=0.05,
                         lean_curve=rng.normal(0, 0.03))
    mid = pts[len(pts) // 2]
    ux, uy = sunward(mid[0], mid[1])
    bark = species(sp)
    dk = aerial(C(40, 34, 62), d, HAZE)
    bark.dark = dk
    bark.mid = aerial(C(62, 52, 76), d, HAZE)
    bark.lit = aerial(C(150, 110, 96), d * 0.7, HAZE)
    bark.rim = C(255, 220, 150)
    bark.refl = aerial(C(90, 80, 110), d, HAZE)
    bark.blotch = aerial(C(60, 70, 72), d, HAZE)
    L3 = (float(ux), float(uy), -0.75)
    mp = dict(dark=aerial(C(30, 44, 54), d, HAZE), mid=aerial(C(50, 70, 60), d, HAZE), lit=C(190, 180, 90),
              tip=C(255, 220, 140))
    sp_ = catmull(pts, spacing=3.0)
    fr = Frame(sp_, np.interp(np.linspace(0, 1, len(sp_)), np.linspace(0, 1, len(ww)), ww))
    if roots:
        for rp, rw, sd in buttress_roots(rng, fr, roots, base - 8, wb, spread=1.3):
            paint_tube(cv, rp, rw, rng, bark, L3, moss=0.8 * (1 - d), detail=0.5, start_fade=0.25, rim_amt=1.2,
                       refl_amt=0.2, flecks=0.0, moss_pal=mp)
    paint_tube(cv, pts, ww, rng, bark, L3, moss=moss * (1 - d), detail=0.6, rim_amt=1.4, refl_amt=0.2, flecks=0.0,
               moss_pal=mp)
    for k in range(branches):
        s0 = rng.uniform(0.35, 0.8)
        p0, w0, _ = fr.at(s0, 0)
        if p0[1] < 0:
            continue
        sgn = rng.choice([-1, 1])
        a = -np.pi / 2 + sgn * rng.uniform(0.6, 1.2)
        L = Ht * rng.uniform(0.12, 0.25)
        p1 = p0 + L * np.array([np.cos(a), np.sin(a)])
        pm = (p0 + p1) / 2 + np.array([0, -L * 0.08]) + rng.normal(0, L * 0.05, 2)
        q = catmull(np.array([p0, pm, p1], np.float32), n=16)
        paint_tube(cv, q, np.linspace(float(w0) * 0.42, float(w0) * 0.12, 16), rng, bark, L3, detail=0.4,
                   rim_amt=1.4, refl_amt=0.2, flecks=0.0, end_fade=0.15)
        if leaves is not None:
            layered_mass(leaves, rng, p1[0], p1[1] - L * 0.05, L * rng.uniform(0.25, 0.4), flat=0.6, droop=0.3)


def build(outdir, quick=False):
    P = Painting('S12', W, H, M, outdir)
    rng = rng_for('S12')

    # ---------------------------------------------------------------- sky / glow
    cv = P.layer('sky', 0.0)
    X, Y = cv.coords()
    dist = np.hypot(X - SUN[0], (Y - SUN[1]) * 1.25)
    t = np.clip(dist / 1300, 0, 1)
    stops = [C(255, 254, 240), C(255, 240, 196), C(255, 216, 156), C(246, 194, 156), C(222, 180, 178),
             C(196, 172, 190)]
    base = ramp(stops, t ** 0.8, [0, 0.08, 0.28, 0.55, 0.82, 1.0])
    cv.img[..., :3] = base
    cv.img[..., 3] = 1
    n = 700
    ang = rng.uniform(0, 2 * np.pi, n)
    rr = rng.uniform(80, 1400, n)
    xs = SUN[0] + np.cos(ang) * rr
    ys = SUN[1] + np.sin(ang) * rr * 0.8
    ix = np.clip((xs + cv.m).astype(int), 0, cv.shape[1] - 1)
    iy = np.clip((ys + cv.m).astype(int), 0, cv.shape[0] - 1)
    cols = jitter(base[iy, ix], rng, dl=0.02, dc=0.1, dh=0.04)
    for k in range(n):
        a = ang[k] + np.pi / 2 + rng.normal(0, 0.1)
        L = rng.uniform(150, 500)
        p = np.array([[xs[k] - np.cos(a) * L / 2, ys[k] - np.sin(a) * L / 2], [xs[k], ys[k]],
                      [xs[k] + np.cos(a) * L / 2, ys[k] + np.sin(a) * L / 2]], np.float32)
        stroke(cv, p, taper(8, 0.4, 0.3, rng.uniform(24, 70)), cols[k], opacity=rng.uniform(0.2, 0.45), edge=0.6,
               bristle=0.6, rag=0.2, rng=rng)
    P.add('sky', 0.0, cv, 'the sun glowing through the mist (in frame); opaque')

    # ---------------------------------------------------------------- far
    cv = P.layer('far', 0.2)
    far_leaves = Blobs()
    for x in np.sort(rng.uniform(-60, 1980, 16)):
        backlit_trunk(cv, rng, x, float(np.exp(rng.uniform(np.log(12), np.log(52)))), rng.uniform(0.55, 0.78),
                      sp=['beech', 'camphor', 'cedar'][int(rng.integers(0, 3))], moss=0.2,
                      branches=int(rng.integers(0, 3)), leaves=far_leaves)
    if len(far_leaves):
        leafy_mass(cv, rng, far_leaves, 0.6, HAZE, (0.0, 0.5, -0.85), (0.0, 1.0), 6, density=0.8, trans_amt=0.8,
                   rim_amt=0.8, lz=-0.8)
    undergrowth(cv, rng, HZ + 10, -60, 1980, 0.6, HAZE, (0.0, -0.3, -0.9), (0.0, -1.0), leaf=5, height=(20, 80))
    mist(cv, rng, -100, 2020, HZ - 300, HZ + 80, HAZE_W, HAZE_C, light=warm, density=1.2, opacity=(0.05, 0.15),
         size=(180, 520), aspect=(0.1, 0.24), profile='bottom')
    P.add('far', 0.2, cv, 'far trunks dissolving in the glowing mist')

    # ---------------------------------------------------------------- mid
    cv = P.layer('mid', 0.5)
    mid_leaves = Blobs()
    for (x, wb, sp, nr, nb) in [(120, 150, 'camphor', 4, 2), (420, 64, 'cedar', 0, 1), (930, 48, 'beech', 0, 2),
                                (1560, 104, 'camphor', 3, 2), (1800, 180, 'beech', 4, 1)]:
        backlit_trunk(cv, rng, x, wb, 0.12, sp=sp, moss=0.7, base=HZ + 140, roots=nr, branches=nb,
                      leaves=mid_leaves)
    if len(mid_leaves):
        leafy_mass(cv, rng, mid_leaves, 0.1, HAZE, (0.0, 0.5, -0.85), (0.0, 1.0), 9, density=0.85, trans_amt=0.8,
                   rim_amt=0.9, lz=-0.8)
    # canopy at the top, backlit
    b = Blobs()
    for x in np.linspace(-80, 2000, 20):
        for k in range(2):
            r = rng.uniform(70, 130)
            b.add(x + rng.normal(0, 50), rng.uniform(-90, 60), r, r * 0.72, light=rng.uniform(0.8, 1.1),
                  hue=rng.normal(0, 0.05), rng=rng, lumpy=0.2)
    leafy_mass(cv, rng, b, 0.1, HAZE, (0.0, 0.6, -0.8), (0.0, 1.0), 11, density=0.9, trans_amt=0.6, rim_amt=0.45,
               lz=-0.8)
    # ground: dark, backlit
    floor(cv, rng, HZ, H + 40, -60, W + 60, HAZE_W, (0.0, -0.3, -0.9), (0.0, -1.0),
          lambda x, y: warm(x, y) * 0.35,
          near=C(28, 32, 54), mid=C(54, 62, 72), lit=C(255, 214, 140), patches=0, flowers_n=30, litter=True)
    # the sun sits on the treeline, so the floor is in shade except where it shines through gaps between
    # the far trunks: a few long sunlit stripes radiating toward the camera from the point under the sun,
    # kept out of the near trunks' shadows; hard, dry-brush edges, broken by small shadows
    VPG = (SUN[0], HZ - 4)
    occ = []
    for (x, wb) in [(120, 150), (420, 64), (930, 48), (1560, 104), (1800, 180)]:
        a_c = np.arctan2(HZ + 140 - VPG[1], x - VPG[0])
        a_w = np.arctan2(wb * 0.5, np.hypot(x - VPG[0], 140.0))
        occ.append((a_c - a_w, a_c + a_w, float(np.hypot(x - VPG[0], 140.0))))
    stripes = []
    for a_deg, w_deg in [(38, 3.0), (55, 1.2), (68, 5.0), (104, 3.6), (121, 1.1), (133, 5.5)]:
        a_c = np.radians(a_deg + rng.normal(0, 1.5))
        a_w = np.radians(w_deg * rng.uniform(0.8, 1.2))
        stripes.append((float(a_c), float(a_w), float(rng.uniform(70, 180)), float(rng.uniform(1100, 2200))))
    # the shaded floor: cool violet in front, warmer near the glowing far edge
    Xf, Yf = cv.coords()
    tf = np.clip((Yf - HZ) / (H - HZ), 0, 1)
    cv.lock_tint(C(232, 196, 156), (np.clip(1 - tf * 3, 0, 1) * 0.22 * (Yf > HZ)).astype(np.float32))
    cv.lock_tint(C(46, 44, 86), (smoothstep(0.35, 1.0, tf) * 0.25 * (Yf > HZ)).astype(np.float32))
    LT = light_stripes(cv, rng, VPG, stripes, C(214, 170, 112), HZ + 4, warm_amt=0.28, lift=0.035,
                       cool_col=C(52, 50, 92), cool_amt=0.12, occluders=occ)
    # backlit grass and fern clumps across the floor (rims glow), low glowing mist on the floor
    for i in range(26):
        y = HZ + 30 + (H - HZ) * rng.random() ** 1.4
        x = rng.uniform(-40, 1960)
        sc = 0.3 + (y - HZ) / (H - HZ)
        if rng.random() < 0.5:
            grass(cv, rng, x, y, 60 * sc, light=0.5, sun2=(0.0, -1.0), n=int(8 + 10 * sc),
                  pal=dict(dark=C(24, 28, 46), mid=C(44, 56, 60), lit=C(170, 150, 90), tip=C(255, 222, 150)))
        else:
            fern(cv, rng, x, y, 70 * sc, sun2=(0.0, -1.0), light=0.5,
                 pal=dict(dark=C(24, 28, 46), mid=C(40, 54, 58), lit=C(150, 140, 80), tip=C(255, 214, 140)))
    mist(cv, rng, -100, 2020, HZ - 40, HZ + 160, HAZE_W, HAZE_C, light=warm, density=1.1, opacity=(0.05, 0.14),
         size=(140, 420), aspect=(0.08, 0.18), profile='mid')
    P.add('mid', 0.5, cv, 'mid trunks as dark silhouettes with gold rims; floor in cool shade crossed by hard-edged '
          'sunlit stripes between the trunk shadows')

    # ---------------------------------------------------------------- beams toward the camera
    cv = P.layer('beams', 0.6)
    # three translucent shafts with clean edges, each continuing one of the ground stripes up to the sun
    # pick the widest lit gaps along a ground arc and send a shaft from the sun to each
    Xs, Ys = cv.coords()
    th_s = np.linspace(np.radians(20), np.radians(160), 600)
    rr_s = 330.0
    gx_ = np.clip((VPG[0] + np.cos(th_s) * rr_s + cv.m).astype(int), 0, cv.shape[1] - 1)
    gy_ = np.clip((VPG[1] + np.sin(th_s) * rr_s + cv.m).astype(int), 0, cv.shape[0] - 1)
    lit = LT[gy_, gx_] > 0.5
    runs, i = [], 0
    while i < len(lit):
        if lit[i]:
            j = i
            while j < len(lit) and lit[j]:
                j += 1
            runs.append((j - i, th_s[i], th_s[j - 1]))
            i = j
        else:
            i += 1
    for (n_, t0, t1) in sorted(runs, reverse=True)[:3]:
        tc = (t0 + t1) / 2
        p_ground = (VPG[0] + np.cos(tc) * rr_s * 1.5, VPG[1] + np.sin(tc) * rr_s * 1.5)
        ang = float(np.arctan2(p_ground[1] - SUN[1], p_ground[0] - SUN[0]))
        L = float(np.hypot(p_ground[0] - SUN[0], p_ground[1] - SUN[1]))
        hw = float(np.arctan2(rr_s * 1.5 * (t1 - t0) / 2, L)) * 0.9
        clean_shaft(cv, rng, SUN, ang, max(hw, np.radians(1.5)), 110, L, C(255, 236, 194),
                    opacity=float(rng.uniform(0.09, 0.14)), fade_in=0.35, fade_out=0.25, streaks=4)
    glow(cv, SUN[0], SUN[1], 150, C(255, 250, 230), 0.5)
    P.add('beams', 0.6, cv, 'three translucent light shafts with clean edges, continuing the ground stripes; small '
          'sun bloom (robot goes above this)', grain_amt=0.0)

    # ---------------------------------------------------------------- fg
    cv = P.layer('fg', 1.0)
    backlit_trunk(cv, rng, 1930, 260, 0.0, sp='camphor', moss=1.0, base=H + 80, top=-140)
    for (x, s_, lean) in [(60, 260, 0.3), (300, 200, 0.1), (1500, 200, -0.1), (1720, 260, -0.3)]:
        fern(cv, rng, x, H + 70, s_, sun2=(0.0, -1.0), light=0.45, lean=lean, spread=0.9,
             pal=dict(dark=C(20, 24, 40), mid=C(36, 50, 56), lit=C(120, 120, 70), tip=C(255, 214, 140)))
    for x in rng.uniform(-20, 1940, 22):
        grass(cv, rng, x, H + 25, rng.uniform(50, 110), light=0.5, sun2=(0.0, -1.0),
              pal=dict(dark=C(20, 24, 40), mid=C(40, 52, 56), lit=C(150, 140, 80), tip=C(255, 220, 150)))
    P.add('fg', 1.0, cv, 'dark backlit ferns/grass at the bottom, a near trunk at the right edge')

    P.save(sun=list(SUN), horizon_y=HZ, robot_between=['beams', 'fg'])
    return P
