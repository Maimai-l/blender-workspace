"""S11 / S15 - POV looking straight up: trunks converge to a ragged canopy gap with a
glowing golden sky. Round 5: the canopy is painted as big leafy masses in flat
light/shadow planes (lit and rim-lit on the side facing the gap, dark undersides),
with a few silhouetted branches and twigs; the flare is a soft painted glow.
1920 x 1040.
"""
import numpy as np

from ..color import C, mix, ramp, jitter, aerial, shade, smoothstep
from ..noise import rng_for, fbm, noise1d
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass, spray
from ..trees import species, paint_tube, trunk_path
from ..sky import sky, sun_disc, paint_planes
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


LP = ((VP[0] + 2 * SUN[0]) / 3, (VP[1] + 2 * SUN[1]) / 3)     # where the light comes from (gap, sun side)
PLANE = (C(28, 36, 56), C(46, 66, 66), C(126, 140, 72), C(236, 208, 124))


def radial_shade(cv, G, lp=LP, gain=1.0):
    """Each cluster is lit on the side facing the light point (the gap), dark elsewhere."""
    cid = G['cid']
    bx, by, brx = G['b']['x'], G['b']['y'], G['b']['rx']
    X, Y = cv.coords()
    valid = cid >= 0
    k = np.maximum(cid, 0)
    cx, cy = np.where(valid, bx[k], X), np.where(valid, by[k], Y)
    tx, ty = lp[0] - cx, lp[1] - cy
    tn = np.hypot(tx, ty) + 1e-6
    facing = ((X - cx) * tx / tn + (Y - cy) * ty / tn) / np.maximum(brx[k], 1)
    lt = G['b']['light'][k]
    sh = (0.1 + 0.8 * smoothstep(-0.15, 0.95, facing) * (0.35 + 0.65 * G['rad'])) * lt * gain
    G['shade'] = np.where(valid, np.clip(sh, 0, 1), G['shade']).astype(np.float32)
    return G


CANOPY_HAZE = C(198, 176, 196)


def masses(cv, rng, centres, d, leaf_px, rim_amt=1.0, cols=PLANE, strokes=0.25, leafy=0.6, gain=1.0, falloff=0.3,
           haze=CANOPY_HAZE, th=(0.3, 0.6, 0.88)):
    """Big leafy masses: each centre (x, y, R) becomes 3-6 overlapping lumpy blobs; painted
    as flat planes with leafy, rim-lit edges toward the gap."""
    b = Blobs()
    items = []
    for (x, y, R) in centres:
        ang = np.arctan2(y - VP[1], x - VP[0])
        for j in range(int(rng.integers(3, 7))):
            u, v = rng.normal(0, 0.55, 2)
            rr = R * rng.uniform(0.45, 0.8)
            # masses extend tangentially around the gap (like the canopy rim)
            ox = -np.sin(ang) * u * R + np.cos(ang) * v * R * 0.5
            oy = np.cos(ang) * u * R + np.sin(ang) * v * R * 0.5
            kk = float(gapk(x + ox, y + oy))
            items.append((-kk, x + ox, y + oy, rr, rr * rng.uniform(0.65, 0.9), ang + np.pi / 2 + rng.normal(0, 0.4),
                          float(np.clip(1.5 - falloff * kk, 0.22, 1.05)) * rng.uniform(0.85, 1.1)))
    items.sort(key=lambda t: t[0])
    for _, x, y, rx, ry, rot, lt in items:
        b.add(x, y, rx, ry, rot=rot, light=lt, hue=rng.normal(0, 0.05), val=rng.normal(0, 0.04), rng=rng, lumpy=0.24)
    G = render_gbuffer(cv, b, light3=(0.0, 0.0, -1.0), wrap=0.5, under=0.0)
    radial_shade(cv, G, gain=gain)
    hc = tuple(aerial(c, d, haze) for c in cols)
    paint_planes(cv, rng, b, hc, G=G, glob=0.0, th=th, noise_amt=0.07, strokes=strokes,
                 rim=aerial(C(255, 220, 146), d * 0.3, HAZE), rim_amt=rim_amt, rim_point=LP, leafy_edge=leafy,
                 leaf_px=leaf_px, leaf_cols=[hc[0], hc[1], hc[2]])


def ring_centres(rng, k_in, k_out, n, R, rag=0.18):
    xs = rng.uniform(-300, W + 300, n * 8)
    ys = rng.uniform(-300, H + 300, n * 8)
    th = np.arctan2(ys - VP[1], xs - VP[0])
    rr = 1 + rag * (0.5 * np.sin(th * 4 + 0.7) + 0.3 * np.sin(th * 7 + 2.2) + 0.2 * np.sin(th * 13 + 4.1))
    k = gapk(xs, ys) / rr
    ok = (k > k_in) & (k < k_out)
    xs, ys, k = xs[ok][:n], ys[ok][:n], k[ok][:n]
    return [(x, y, R * rng.uniform(0.7, 1.3) * (0.75 + 0.25 * min(kk, 2.5))) for x, y, kk in zip(xs, ys, k)]


def branch(cv, rng, p0, p1, w0, d, twigs=3, leaves=None):
    """A silhouetted branch reaching toward the gap: dark, rim-lit on the gap side; thin
    twigs at the end carry small leaf masses (collected into `leaves` as centres)."""
    bark = species('camphor')
    bark.dark, bark.mid = C(30, 26, 44), C(46, 40, 58)
    bark.lit, bark.rim = C(120, 96, 90), C(255, 216, 150)
    p0 = np.asarray(p0, np.float32)
    p1 = np.asarray(p1, np.float32)
    L = float(np.hypot(*(p1 - p0)))
    pm = p0 + (p1 - p0) * 0.5 + rng.normal(0, L * 0.06, 2)
    pts = catmull(np.array([p0, pm, p1]), n=24)
    mid = pts[12]
    l2 = np.array(LP) - mid
    l2 = l2 / (np.hypot(*l2) + 1e-6)
    paint_tube(cv, pts, np.linspace(w0, w0 * 0.3, 24), rng, bark, (float(l2[0]), float(l2[1]), -0.8), moss=0.3,
               detail=0.4, rim_amt=1.4, refl_amt=0.1, flecks=0.0, end_fade=0.1)
    a0 = float(np.arctan2(*(p1 - p0)[::-1]))
    for k in range(twigs):
        q0 = pts[int(rng.integers(10, 24))]
        a = a0 + rng.normal(0, 0.6)
        tl = L * rng.uniform(0.2, 0.4)
        q1 = q0 + tl * np.array([np.cos(a), np.sin(a)])
        qm = (q0 + q1) / 2 + rng.normal(0, tl * 0.08, 2)
        stroke(cv, [q0, qm, q1], taper(3, 1.0, 0.2, max(w0 * 0.22, 2.5)), C(30, 26, 42), bristle=0.2, rag=0.2,
               rng=rng)
        if leaves is not None:
            leaves.append((q1[0], q1[1], tl * rng.uniform(0.3, 0.5)))


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
    # dark outer ceiling (the underside of the canopy all around), lit only near the gap
    masses(cv, rng, ring_centres(rng, 1.55, 7.0, 120, 160), 0.1, 11, rim_amt=0.6, strokes=0.3, leafy=0.4,
           cols=(C(30, 38, 62), C(46, 62, 72), C(104, 120, 72), C(222, 196, 120)), falloff=0.55)
    # sky holes through the outer ceiling (small, clustered, leaf-edged)
    hx, hy = [], []
    for i in range(46):
        a = rng.uniform(0, 2 * np.pi)
        kk = rng.uniform(1.8, 4.5)
        cx, cy = VP[0] + np.cos(a) * GAP_R[0] * kk, VP[1] + np.sin(a) * GAP_R[1] * kk
        m = int(rng.integers(3, 9))
        hx.append(cx + rng.normal(0, 26, m))
        hy.append(cy + rng.normal(0, 18, m))
    hx, hy = np.concatenate(hx), np.concatenate(hy)
    dabs(cv, hx, hy, rng.uniform(10, 34, len(hx)), C(0, 0, 0), aspect=rng.uniform(0.45, 0.9, len(hx)), shape='leaf',
         angle=rng.uniform(0, np.pi, len(hx)), edge=0.3, rag=0.5, bristle=0.0, mode='erase', rng=rng)
    # the lit inner ring around the gap
    masses(cv, rng, ring_centres(rng, 0.95, 1.75, 70, 110), 0.25, 9, rim_amt=1.0, strokes=0.2, leafy=0.6,
           falloff=0.35)
    P.add('canopy_far', 0.3, cv, 'the highest canopy rimming the gap: big leafy masses in flat planes, lit and '
          'rim-lit on the gap side')

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
    leaves = []
    # a few silhouetted branches reaching from the trunk tops into the bright gap
    for (e, a, wb) in ends[::2]:
        tip = np.array([VP[0] + np.cos(a) * GAP_R[0] * rng.uniform(0.55, 0.8),
                        VP[1] + np.sin(a) * GAP_R[1] * rng.uniform(0.55, 0.8)])
        tip += rng.normal(0, 40, 2)
        branch(cv, rng, e, tip, wb * 0.16, 0.1, twigs=int(rng.integers(2, 4)), leaves=leaves)
    centres = list(leaves)
    for (e, a, wb) in ends:
        px, py = -np.sin(a), np.cos(a)
        for k in range(3):
            u = rng.normal(0, 0.8)
            centres.append((e[0] + px * u * 140 - np.cos(a) * 40, e[1] + py * u * 140 - np.sin(a) * 40,
                            rng.uniform(70, 120)))
    masses(cv, rng, centres, 0.06, 14, rim_amt=1.0, strokes=0.25, leafy=0.6, falloff=0.4)
    P.add('canopy_mid', 0.75, cv, 'crowns of the converging trees and silhouetted branches/twigs into the gap')

    # ---------------------------------------------------------------- near leaves silhouetted at the corners
    cv = P.layer('canopy_near', 0.9)
    masses(cv, rng, ring_centres(rng, 3.2, 6.0, 26, 220), 0.0, 24, rim_amt=1.1, strokes=0.3, leafy=0.7,
           cols=(C(20, 24, 40), C(34, 48, 56), C(108, 118, 66), C(232, 200, 118)), gain=0.9, falloff=0.25)
    for i in range(6):
        a = rng.uniform(0, 2 * np.pi)
        x = VP[0] + np.cos(a) * 1150
        y = VP[1] + np.sin(a) * 640
        aa = np.arctan2(VP[1] - y, VP[0] - x) + rng.normal(0, 0.35)
        spray(cv, x, y, aa, rng.uniform(260, 420), rng.uniform(34, 50), C(18, 22, 36), C(70, 80, 56), rng,
              stem_col=C(24, 22, 34), droop=0.0, sun2=(np.cos(aa), np.sin(aa)), curl=rng.normal(0, 0.5),
              rim=C(255, 214, 140))
    P.add('canopy_near', 0.9, cv, 'near leaves and twigs silhouetted with warm rims')

    # ---------------------------------------------------------------- flare: a soft painted sun glow
    cv = P.layer('flare', 1.0)
    glow(cv, SUN[0], SUN[1], 120, C(255, 252, 236), 0.8)
    glow(cv, SUN[0], SUN[1], 360, C(255, 236, 182), 0.35)
    # a soft, slightly irregular halo painted with large low-opacity round dabs (no streaks)
    n = 40
    a = rng.uniform(0, 2 * np.pi, n)
    r = rng.uniform(60, 260, n)
    dabs(cv, SUN[0] + np.cos(a) * r, SUN[1] + np.sin(a) * r * 0.9, rng.uniform(120, 260, n),
         jitter(np.broadcast_to(C(255, 240, 200), (n, 3)), rng, dl=0.02), aspect=rng.uniform(0.6, 1.0, n),
         opacity=rng.uniform(0.04, 0.09, n), edge=0.95, rag=0.3, bristle=0.4, rng=rng)
    P.add('flare', 1.0, cv, 'soft painted sun glow at the gap edge (animate opacity); no starburst', grain_amt=0.0)

    P.save(sun=list(SUN), zenith=list(VP))
    return P
