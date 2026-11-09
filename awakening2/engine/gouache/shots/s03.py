"""S03 / S07 - looking up past the bowed face toward the canopy (2100 x 1140, slow push).

Dark mossy trunks converge upward; a bright gap of dawn sky at the upper left;
a strong warm sunbeam (the first ray) enters from the upper left; floating motes.
The face covers the right two thirds (composited above `beam`... see layers.json).
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, vine, spray
from ..sky import sky, cumulus_blobs, paint_clouds, sculpted_cloud
from ..atmos import mist, beams, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, layered_mass

W, H, M = 2100, 1140, 48
VP = (1000.0, -1500.0)
SUN = (300.0, 70.0)
GAP = (600.0, 190.0, 560.0, 270.0)
L3 = (-0.6, -0.7, -0.3)
SUN2 = (-0.65, -0.76)
HAZE = C(232, 216, 214)
HAZE_W = C(255, 232, 196)


def gapk(x, y):
    cx, cy, rx, ry = GAP
    return np.sqrt(((np.asarray(x) - cx) / rx) ** 2 + ((np.asarray(y) - cy) / ry) ** 2)


def converging(cv, rng, xb, wb, d, top_k=1.2, sp='camphor', moss=0.9, ivy=0.3, detail=0.8):
    """Trunk from below the frame toward VP; stops where it enters the canopy."""
    yb = H + 120
    dx, dy = VP[0] - xb, VP[1] - yb
    L = np.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    # walk up until the canopy (outside the gap) or the top
    t_end = L * rng.uniform(0.55, 0.7)
    top = (xb + ux * t_end, yb + uy * t_end)
    pts, ww = trunk_path(rng, (xb, yb), top, wb, wb * 0.45, sway=0.02, bulge=0.07)
    bark = species(sp, depth=d, haze=HAZE)
    paint_tube(cv, pts, ww, rng, bark, L3, depth=d, haze=HAZE, moss=moss, ivy=ivy, detail=detail,
               twist=0.18 if sp == 'camphor' else 0.0, end_fade=0.2, flecks=0.25, sky_side=0.2)


def canopy(cv, rng, d, n, rad, leaf, k_in, k_out, light_k=1.0, ymax=380):
    xs = rng.uniform(-150, W + 150, n * 4)
    ys = rng.uniform(-200, ymax, n * 4)
    th = np.arctan2(ys - GAP[1], xs - GAP[0])
    rr = 1 + 0.15 * (np.sin(th * 5 + 1.3) * 0.6 + np.sin(th * 9 + 0.4) * 0.4)
    k = gapk(xs, ys) / rr
    ok = (k > k_in) & (k < k_out) & (ys < ymax - 0.1 * np.abs(xs - 1300) + rng.normal(0, 30, len(xs)))
    xs, ys = xs[ok][:n], ys[ok][:n]
    b = Blobs()
    for i in np.argsort(ys):
        r = rad * rng.uniform(0.6, 1.3)
        b.add(xs[i], ys[i], r, r * rng.uniform(0.65, 0.85), rot=rng.normal(0, 0.3),
              light=light_k * rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.05), val=rng.normal(0, 0.05), rng=rng,
              lumpy=0.18)
    leafy_mass(cv, rng, b, d, HAZE, L3, SUN2, leaf, density=0.9, trans_amt=0.65, rim_amt=0.85, lz=-0.45)


def build(outdir, quick=False):
    P = Painting('S03', W, H, M, outdir)
    rng = rng_for('S03')

    # ---------------------------------------------------------------- sky
    cv = P.layer('sky', 0.0)
    stops = [C(250, 226, 186), C(250, 208, 170), C(232, 186, 186), C(200, 176, 204), C(184, 180, 210)]
    pos = [0.0, 0.2, 0.42, 0.7, 1.0]
    sky(cv, rng, stops, pos, sun=SUN, glow=(760, C(255, 242, 206), 1.0), tilt=0.25, n_strokes=0.7,
        stroke_w=(24, 80), stroke_len=(200, 600), angle=0.2)
    sculpted_cloud(cv, rng, 860, 330, 680, 120, [C(176, 140, 180), C(222, 172, 176), C(255, 210, 170),
                                                 C(255, 234, 198), C(255, 248, 226)], kind='strato',
                   light3=(-0.6, -0.5, 0.1), rim=C(255, 240, 204), rim_amt=0.8)
    glow(cv, SUN[0], SUN[1], 150, C(255, 250, 232), 0.85)
    P.add('sky', 0.0, cv, 'dawn sky; the gap is upper left, sun near the top-left corner; opaque')

    # ---------------------------------------------------------------- far: high canopy + far trunks
    cv = P.layer('far', 0.2)
    for xb in [-40, 330, 760, 1180, 1500, 1820, 2150]:
        converging(cv, rng, xb + rng.normal(0, 40), rng.uniform(60, 120), 0.62, sp=['beech', 'camphor', 'cedar'][
            int(rng.integers(0, 3))], moss=0.4, ivy=0.0, detail=0.4)
    canopy(cv, rng, 0.55, 300, 46, 7, 0.95, 2.2, ymax=430)
    # distant crowns and understorey filling the depth below the canopy
    b = Blobs()
    for i in range(18):
        layered_mass(b, rng, rng.uniform(-100, W + 100), rng.uniform(560, 1150), rng.uniform(90, 170), flat=0.6,
                     droop=0.35)
    leafy_mass(cv, rng, b, 0.7, HAZE, L3, SUN2, 6, density=0.8, trans_amt=0.45, rim_amt=0.5, lz=-0.2)
    for xb in [80, 560, 980, 1400, 1700]:
        converging(cv, rng, xb + rng.normal(0, 40), rng.uniform(40, 80), 0.72, sp='beech', moss=0.3, ivy=0.0,
                   detail=0.3)
    mist(cv, rng, -100, W + 100, 450, H, HAZE_W, HAZE, density=1.0, opacity=(0.05, 0.13), size=(160, 520),
         aspect=(0.1, 0.25), profile='bottom')
    P.add('far', 0.2, cv, 'far trunks converging upward, high canopy rimming the gap')

    # ---------------------------------------------------------------- mid: dark mossy trunks + near canopy
    cv = P.layer('mid', 0.55)
    for (xb, wb, sp) in [(-160, 520, 'camphor'), (240, 300, 'beech'), (1320, 420, 'camphor'), (1960, 380, 'cedar')]:
        converging(cv, rng, xb, wb, 0.0, sp=sp, moss=1.2, ivy=0.5 if sp == 'camphor' else 0.1, detail=0.9)
    canopy(cv, rng, 0.0, 260, 80, 13, 1.45, 4.0, light_k=0.95, ymax=300)
    for i in range(8):
        x = rng.uniform(900, 1900)
        vine(cv, x, rng.uniform(250, 420), rng.uniform(300, 700), rng, C(40, 44, 50), C(26, 50, 52),
             C(130, 150, 76), leaf=rng.uniform(12, 18), width=2.5, sun2=SUN2)
    P.add('mid', 0.55, cv, 'dark mossy trunks converging upward and the near canopy; the face goes above this')

    # ---------------------------------------------------------------- beam (the first ray)
    cv = P.layer('beam', 0.7)
    ang = np.arctan2(720 - SUN[1], 1450 - SUN[0])
    beams(cv, rng, SUN, [ang - 0.05, ang, ang + 0.06], 2300, [120, 220, 90], C(255, 236, 186), opacity=0.5,
          spread_w=1.3, streak=0.55, start_fade=0.04, end_len=0.95)
    P.add('beam', 0.7, cv, 'the first ray: soft warm beam from the upper left (animate: slide/opacity)',
          grain_amt=0.0)

    # ---------------------------------------------------------------- motes
    cv = P.layer('motes', 0.75)
    n = 260
    t = rng.uniform(0.05, 0.9, n)
    across = rng.normal(0, 1, n)
    L = 2000
    cx = SUN[0] + np.cos(ang) * L * t - np.sin(ang) * across * (60 + 200 * t)
    cy = SUN[1] + np.sin(ang) * L * t + np.cos(ang) * across * (60 + 200 * t)
    sz = rng.uniform(2, 7, n) * (0.6 + rng.random(n) ** 3 * 1.8)
    inb = np.exp(-across ** 2 / 2)
    cols = jitter(mix(C(255, 236, 190), C(255, 252, 236), rng.random(n)[:, None]), rng, dl=0.02)
    dabs(cv, cx, cy, sz, cols, aspect=rng.uniform(0.6, 1.0, n), opacity=np.clip(0.3 + 0.7 * inb, 0, 1), edge=0.8,
         rag=0.2, bristle=0.0, rng=rng)
    P.add('motes', 0.75, cv, 'floating dust motes in the beam (drift them slowly)', grain_amt=0.0)

    P.save(sun=list(SUN), light_dir=list(L3), beam_angle_deg=float(np.degrees(ang)),
           note_shots='S07 reuses this painting', face_between=['mid', 'beam'])
    return P
