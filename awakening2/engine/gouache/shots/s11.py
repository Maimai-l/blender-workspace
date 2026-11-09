"""S11 - POV looking straight up: trunks converge to a ragged canopy gap with a
glowing golden sky; leaves silhouetted with warm rims; sun flare at the gap edge.
1920 x 1040.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, shade, smoothstep
from ..noise import rng_for, fbm, noise1d
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass, spray
from ..trees import species, paint_tube, trunk_path
from ..sky import sky, sun_disc
from ..atmos import glow, beams

W, H, M = 1920, 1040, 40
VP = (975.0, 470.0)            # zenith / convergence point (centre of the gap)
SUN = (1225.0, 330.0)          # at the gap's upper-right edge
GAP_R = (430.0, 300.0)
HAZE = C(255, 228, 176)
LEAF = [C(22, 28, 46), C(30, 46, 58), C(46, 74, 64), C(104, 126, 64), C(196, 186, 86)]


def gapk(x, y):
    return np.sqrt(((np.asarray(x) - VP[0]) / GAP_R[0]) ** 2 + ((np.asarray(y) - VP[1]) / GAP_R[1]) ** 2)


def ring(cv, rng, k_in, k_out, n, rad, leaf, d, light_k=1.0, density=1.0, rag=0.18, trans_amt=0.7,
         rim_amt=0.9, extra=None):
    xs = rng.uniform(-200, W + 200, n * 5)
    ys = rng.uniform(-200, H + 200, n * 5)
    th = np.arctan2(ys - VP[1], xs - VP[0])
    ph = rng.uniform(0, 6, 3)
    rr = 1 + rag * (0.5 * np.sin(th * 4 + ph[0]) + 0.3 * np.sin(th * 7 + ph[1]) + 0.2 * np.sin(th * 13 + ph[2]))
    k = gapk(xs, ys) / rr
    ok = (k > k_in) & (k < k_out)
    xs, ys, k = xs[ok][:n], ys[ok][:n], k[ok][:n]
    order = np.argsort(-k)            # outer (nearer) clusters last
    b = Blobs()
    for i in order[::-1][::-1]:
        r = rad * rng.uniform(0.6, 1.3) * (0.7 + 0.3 * min(k[i], 2.0))
        ang = np.arctan2(ys[i] - VP[1], xs[i] - VP[0])
        fall = float(np.clip(1.45 - 0.3 * k[i], 0.45, 1.0))
        b.add(xs[i], ys[i], r, r * rng.uniform(0.6, 0.85), rot=ang + rng.normal(0, 0.3),
              light=light_k * fall * rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.05),
              val=rng.normal(0, 0.05) - 0.12 * (1 - fall), rng=rng, lumpy=0.18)
    if extra is not None:
        b.extend(extra)
    # light comes from the gap: each cluster is lit on its gap-facing side (sun2 toward VP/sun)
    G = render_gbuffer(cv, b, light3=(0.35, -0.3, -0.6), wrap=0.55, under=0.0)
    # replace the dome shading direction by a radial one: clusters glow on the side facing the gap
    cid = G['cid']
    bx, by = G['b']['x'], G['b']['y']
    X, Y = cv.coords()
    valid = cid >= 0
    cxp = np.where(valid, bx[np.maximum(cid, 0)], X)
    cyp = np.where(valid, by[np.maximum(cid, 0)], Y)
    tx, ty = SUN[0] - cxp, SUN[1] - cyp
    tn = np.hypot(tx, ty) + 1e-6
    dx, dy = X - cxp, Y - cyp
    rx = G['b']['rx'][np.maximum(cid, 0)]
    facing = (dx * tx / tn + dy * ty / tn) / np.maximum(rx, 1)
    lt = G['b']['light'][np.maximum(cid, 0)]
    G['shade'] = np.where(valid, np.clip((0.18 + 0.55 * smoothstep(0.1, 0.95, facing) * G['rad'] ** 1.5) * lt, 0, 1),
                          G['shade']).astype(np.float32)
    stops = [aerial(c, d, HAZE) for c in LEAF]
    # sun2 per painting: toward the sun from the frame centre-ish
    paint_mass(cv, G, rng, stops, leaf=leaf, density=density, trans=aerial(C(214, 206, 92), d * 0.5, HAZE),
               trans_amt=trans_amt, rim=aerial(C(255, 216, 140), d * 0.3, HAZE), rim_amt=rim_amt,
               tip=C(255, 232, 160), tip_amt=0.15, sun2=(0.0, -1.0), droop=0.0, vnoise=0.14)
    # rims: along each silhouette edge facing the sun (radial sun direction): extra pass
    return G


def build(outdir, quick=False):
    P = Painting('S11', W, H, M, outdir)
    rng = rng_for('S11')

    # ---------------------------------------------------------------- sky: golden glow
    cv = P.layer('sky', 0.0)
    X, Y = cv.coords()
    d = np.hypot(X - SUN[0], (Y - SUN[1]) * 1.1)
    t = np.clip(d / 1100, 0, 1)
    stops = [C(255, 252, 236), C(255, 238, 186), C(255, 214, 140), C(250, 188, 130), C(222, 160, 150)]
    base = ramp(stops, t ** 0.7, [0, 0.12, 0.35, 0.65, 1.0])
    cv.img[..., :3] = base
    cv.img[..., 3] = 1
    sky(cv, rng, stops, [0, 0.12, 0.35, 0.65, 1.0], n_strokes=0.0)     # (no-op strokes; keep api)
    cv.img[..., :3] = base
    # radial brushed strokes around the sun (painted glow)
    n = 900
    ang = rng.uniform(0, 2 * np.pi, n)
    rr = rng.uniform(60, 1100, n)
    xs = SUN[0] + np.cos(ang) * rr
    ys = SUN[1] + np.sin(ang) * rr * 0.9
    ix = np.clip((xs + cv.m).astype(int), 0, cv.shape[1] - 1)
    iy = np.clip((ys + cv.m).astype(int), 0, cv.shape[0] - 1)
    cols = jitter(base[iy, ix], rng, dl=0.02, dc=0.1, dh=0.04)
    for k in range(n):
        a = ang[k] + np.pi / 2 + rng.normal(0, 0.1)
        L = rng.uniform(120, 420)
        p = np.array([[xs[k] - np.cos(a) * L / 2, ys[k] - np.sin(a) * L / 2], [xs[k], ys[k]],
                      [xs[k] + np.cos(a) * L / 2, ys[k] + np.sin(a) * L / 2]], np.float32)
        stroke(cv, p, taper(8, 0.4, 0.3, rng.uniform(20, 60)), cols[k], opacity=rng.uniform(0.2, 0.5), edge=0.6,
               bristle=0.6, rag=0.2, rng=rng)
    # a few warm cloud wisps in the gap
    for k in range(4):
        y0 = VP[1] + rng.uniform(-180, 160)
        x0 = VP[0] + rng.uniform(-420, 200)
        L = rng.uniform(260, 520)
        xs_ = np.linspace(x0, x0 + L, 9)
        ys_ = y0 + np.cumsum(rng.normal(0, 5, 9))
        for j in range(4):
            c = mix(C(244, 186, 168), C(255, 234, 190), j / 3)
            stroke(cv, np.stack([xs_, ys_ + (j - 1.5) * 6], 1), taper(9, 0.2, 0.1, rng.uniform(10, 22)), c,
                   opacity=rng.uniform(0.3, 0.55), edge=0.6, bristle=0.7, rag=0.3, rng=rng)
    P.add('sky', 0.0, cv, 'golden sky in the gap; opaque')

    # ---------------------------------------------------------------- high canopy ring around the gap
    cv = P.layer('canopy_far', 0.3)
    ring(cv, rng, 0.92, 7.0, 720, 54, 8, 0.12, density=0.9)
    P.add('canopy_far', 0.3, cv, 'the highest canopy rimming the gap, backlit, translucent edges')

    # ---------------------------------------------------------------- trunks converging to the zenith
    cv = P.layer('trunks', 0.6)
    angs = np.radians([200, 236, 268, 300, 334, 18, 62, 112, 152]) + rng.normal(0, 0.06, 9)
    ends = []
    for i, a in enumerate(angs):
        far = np.array([VP[0] + np.cos(a) * 1500, VP[1] + np.sin(a) * 1200])
        stop_r = rng.uniform(1.12, 1.35)
        near_end = np.array([VP[0] + np.cos(a) * GAP_R[0] * stop_r, VP[1] + np.sin(a) * GAP_R[1] * stop_r])
        wb = rng.uniform(220, 380)
        pts, ww = trunk_path(rng, far, near_end, wb, wb * 0.22, sway=0.03, bulge=0.06)
        ends.append((near_end, a, wb))
        sp = ['camphor', 'beech', 'cedar'][i % 3]
        mid = pts[len(pts) // 2]
        L2 = np.array(SUN) - mid
        L2 = L2 / np.hypot(*L2)
        bark = species(sp)
        paint_tube(cv, pts, ww, rng, bark, (L2[0], L2[1], -0.45), moss=0.9, ivy=0.4 if sp == 'camphor' else 0.0,
                   twist=0.15 if sp == 'camphor' else 0.0, detail=0.8, flecks=0.3, end_fade=0.25, sky_side=0.2)
    P.add('trunks', 0.6, cv, 'trunks converging toward the zenith')

    # ---------------------------------------------------------------- crowns at the trunk tops
    cv = P.layer('canopy_mid', 0.75)
    crowns = Blobs()
    for (e, a, wb) in ends:
        # a crown around each trunk top, spreading sideways (perpendicular to the trunk)
        px, py = -np.sin(a), np.cos(a)
        for k in range(9):
            u = rng.normal(0, 1.0)
            v = rng.normal(0, 0.4) - 0.5
            x = e[0] + px * u * 150 + np.cos(a) * v * 120
            y = e[1] + py * u * 150 + np.sin(a) * v * 120
            r = rng.uniform(40, 75)
            crowns.add(x, y, r, r * 0.75, rot=a + np.pi / 2, light=rng.uniform(0.8, 1.1), hue=rng.normal(0, 0.05),
                       val=rng.normal(0, 0.05), rng=rng, lumpy=0.18)
    ring(cv, rng, 1.2, 1.5, 80, 56, 12, 0.12, density=0.95, extra=crowns)
    P.add('canopy_mid', 0.75, cv, 'crowns of the converging trees')

    # ---------------------------------------------------------------- near leaves silhouetted at the corners
    cv = P.layer('canopy_near', 0.9)
    ring(cv, rng, 3.4, 5.0, 50, 120, 20, 0.0, density=0.9, rim_amt=1.0)
    for i in range(10):
        a = rng.uniform(0, 2 * np.pi)
        x = VP[0] + np.cos(a) * 1150
        y = VP[1] + np.sin(a) * 640
        aa = np.arctan2(VP[1] - y, VP[0] - x) + rng.normal(0, 0.35)
        spray(cv, x, y, aa, rng.uniform(260, 420), rng.uniform(34, 50), C(18, 22, 36), C(70, 80, 56), rng,
              stem_col=C(24, 22, 34), droop=0.0, sun2=(np.cos(aa), np.sin(aa)), curl=rng.normal(0, 0.5),
              rim=C(255, 214, 140))
    P.add('canopy_near', 0.9, cv, 'near leaves and twigs silhouetted with warm rims')

    # ---------------------------------------------------------------- flare
    cv = P.layer('flare', 1.0)
    glow(cv, SUN[0], SUN[1], 150, C(255, 250, 230), 0.75)
    glow(cv, SUN[0], SUN[1], 420, C(255, 230, 170), 0.3)
    rays = np.radians(np.arange(0, 360, 360 / 14)) + rng.normal(0, 0.06, 14)
    beams(cv, rng, SUN, rays, 900, rng.uniform(10, 26, 14), C(255, 242, 206), opacity=0.25, spread_w=0.6,
          streak=0.5, start_fade=0.02, end_len=0.6, edge=0.85)
    # ghosts along the line sun -> centre -> beyond
    for f, r, a in [(0.55, 34, 0.12), (1.3, 60, 0.08), (1.75, 22, 0.14)]:
        gx = SUN[0] + (W / 2 - SUN[0]) * f
        gy = SUN[1] + (H / 2 - SUN[1]) * f
        glow(cv, gx, gy, r, C(255, 214, 160), a)
    P.add('flare', 1.0, cv, 'sun flare at the gap edge (animate opacity)')

    P.save(sun=list(SUN), zenith=list(VP))
    return P
