#!/usr/bin/env python3
"""Qiting round 2 - site data for the surroundings, computed in the cloud session (numpy / SciPy / OpenCV) and
written as plain Python modules that Blender only reads:
  scripts/lib/qt_env_data.py   shapes and placements (plaza outline, paths, stairs, sculptures, lamps, trees ...)
  scripts/lib/qt_env_grid.py   terrain heights and masks on a 0.5 m grid (zlib + base64)

Sources: the DWG screenshot (plan, 0.245 m/px, registered on the pavilion axis), its spot heights, the master plan
(lake), the calibrated aerials A1/A2 (layout checks, tree positions). Model frame: X east, Y north, Z = 0 at the
podium floor; absolute height = Z + ABS0.

    python3 make_env.py [--preview]
"""
import math, os, sys, json, zlib, base64
import numpy as np
import cv2
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
LIB = os.path.join(PROJ, 'scripts', 'lib')
WORK = os.path.expanduser('~/.cache/qiting')
DWG = os.path.join(WORK, 'ref', 'photos', '2390cc8d040e61ce45ed5e0b64655b0b.jpg')
CX, CY, S = 596.26, 597.08, 0.245            # DWG pixel of the pavilion axis, metres per DWG pixel
ABS0 = 441.40                                # absolute height of Z = 0 (plaza -4.80 <-> 436.6 from the DWG spot heights)


def to_m(x, y):
    return (np.asarray(x) - CX) * S, (CY - np.asarray(y)) * S


def to_px(X, Y):
    return CX + np.asarray(X) / S, CY - np.asarray(Y) / S


def load_dwg():
    img = cv2.imread(DWG)
    b, g, r = [img[..., i].astype(int) for i in range(3)]
    white = (np.minimum(np.minimum(r, g), b) > 125)
    blue = (b > 140) & (r < 110) & (g < 130)
    purple = (r > 70) & (b > 90) & (g < 80) & (r < 200) & ~white
    green = (g > 120) & (r < 140) & (b < 140) & (g > r + 30)
    red = (r > 150) & (g < 120) & (b < 120)
    return img, white, blue, purple, green, red


def radial_first(white, r0, r1, az_deg, skip=None, step=0.05):
    """first white crossing beyond r0 (metres) along each azimuth (model, CCW from east)."""
    out = []
    for a in az_deg:
        if skip and skip(a):
            out.append(np.nan); continue
        th = math.radians(a)
        hit = np.nan
        for r in np.arange(r0, r1, step):
            x, y = to_px(r * math.cos(th), r * math.sin(th))
            xi, yi = int(round(float(x))), int(round(float(y)))
            if 0 <= yi < white.shape[0] and 0 <= xi < white.shape[1] and white[yi, xi]:
                hit = r; break
        out.append(hit)
    return np.array(out)


def plaza_outline(white):
    """the paved plaza edge: first DWG line beyond the terraces, stair corridors bridged by interpolation."""
    az = np.arange(0, 360, 0.5)
    stair = lambda a: (84 <= a <= 96) or (264 <= a <= 276)
    r = radial_first(white, 12.6, 32.0, az, skip=stair)
    ok = ~np.isnan(r)
    rr = np.interp(az, az[ok], r[ok], period=360)
    # small symbols touching the line give spikes: median filter (wrap)
    k = 5
    ext = np.concatenate([rr[-k:], rr, rr[:k]])
    med = np.array([np.median(ext[i:i + 2 * k + 1]) for i in range(len(rr))])
    # fill notches: DWG symbols and two planting pockets that the aerial A2 shows paved (a stone table stands in one)
    K = 18                                          # +-9 deg
    ext = np.concatenate([med[-K:], med, med[:K]])
    hi = np.array([np.percentile(ext[i:i + 2 * K + 1], 80) for i in range(len(med))])
    bad = med < hi - 2.0
    good = ~bad
    med = np.interp(az, az[good], med[good], period=360)
    return az, med


def path_mask(white, w_min=4.0, w_max=30.0, min_len=45):
    """interiors of double-line paths: medial axis of the open (non-line) area, kept where the local width is in
    [w_min, w_max] px and the axis branch is long; the path is the union of disks along the kept axis."""
    from skimage.morphology import medial_axis, skeletonize
    W = cv2.dilate(white.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    free = ~W
    skel, dist = medial_axis(free, return_distance=True)
    w = 2.0 * dist
    keep = skel & (w >= w_min) & (w <= w_max)
    # drop short pieces and pieces whose width varies wildly (symbol gaps)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(keep.astype(np.uint8), 8)
    good = np.zeros_like(keep)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_len:
            continue
        ws = w[lab == i]
        if np.std(ws) > 0.45 * np.mean(ws):
            continue
        good |= (lab == i)
    # rebuild the path area: disks of radius dist along the axis
    ys, xs = np.nonzero(good)
    area = np.zeros_like(W, dtype=np.uint8)
    for y, x in zip(ys, xs):
        cv2.circle(area, (int(x), int(y)), int(round(dist[y, x] + 0.5)), 1, -1)
    return (area > 0) & free, good, dist


# ------------------------------------------------------------------ hand-digitised layout (model metres)
# ring path round the plaza: centre radius and width by azimuth (DWG polar plots, checked on the rectified A2)
RING = [(0, 39.5, 3.2), (15, 33.3, 2.6), (30, 31.3, 2.6), (45, 30.1, 2.5), (60, 29.6, 2.7), (75, 29.0, 2.5),
        (90, 28.9, 2.5), (105, 29.2, 2.6), (120, 29.6, 2.8), (135, 30.2, 2.7), (150, 31.6, 3.0), (165, 32.9, 2.8),
        (180, 32.8, 2.7), (195, 31.9, 3.2), (210, 29.4, 2.7), (225, 26.9, 2.8), (240, 25.6, 2.8), (255, 24.9, 2.8),
        (270, 24.8, 2.9), (285, 26.1, 2.8), (300, 28.8, 2.6), (315, 33.5, 2.6), (330, 42.3, 2.6), (345, 41.5, 2.8)]
# park paths: centreline, width, surface ('pave' grey granite pavers, 'pink' promenade, 'walk' lakeside walk)
PATHS = {
    'north':  dict(w=2.8, kind='pave', pts=[(-57, 22.5), (-45, 26.5), (-30, 33.5), (-15, 38.5), (0, 41.5), (15, 40.6),
                                            (30, 37.0), (42, 31.5), (52, 24.0), (62, 16.5), (73, 11.5)]),
    'nw':     dict(w=2.8, kind='pave', pts=[(-95, 58), (-80, 48), (-70, 39), (-62, 29.5), (-57, 22.5)]),
    'west':   dict(w=2.6, kind='pave', pts=[(-57, 22.5), (-55, 11), (-51, 1), (-48, -10), (-46.5, -22), (-47.5, -38.5)]),
    'w_spur': dict(w=2.4, kind='pave', pts=[(-34.0, 1.5), (-43, 2.0), (-51, 1.0)]),
    'e_spur': dict(w=2.4, kind='pave', pts=[(38.5, 4.5), (48, 5.8), (60, 7.2), (73, 9.5), (95, 12.5)]),
    'east':   dict(w=2.8, kind='pave', pts=[(73, 11.5), (80, 2), (84, -12), (86, -28), (86, -44)]),
    'prom':   dict(w=5.2, kind='pink', pts=[(-125, -33), (-95, -34), (-70, -36.5), (-50, -39.5), (-30, -43.5), (-10, -47.5),
                                            (0, -49.0), (15, -51.0), (30, -51.6), (45, -51.0), (60, -49.0), (75, -46.0),
                                            (95, -42.0), (125, -38.0)]),
    'walk':   dict(w=6.0, kind='walk', pts=[(-125, -69.5), (-95, -70.0), (-60, -70.3), (-30, -70.8), (0, -71.0), (30, -71.2),
                                            (60, -73.0), (95, -78.0), (125, -84.0)]),
    'x_w':    dict(w=2.6, kind='pave', pts=[(-62, -38.5), (-60, -50), (-57, -62), (-55, -68)]),
    'x_e':    dict(w=2.6, kind='pave', pts=[(42, -51.2), (44, -60), (47, -71.5)]),
}
# garden stairs: axis polyline (x, y) from top to bottom, width, top and bottom heights resolved from the terrain
STAIRS = {
    'n_garden': dict(w=3.0, pts=[(0, 30.6), (0, 39.8)]),
    's_garden': dict(w=3.0, pts=[(0, -26.4), (0, -46.6)]),
    'e_curved': dict(w=2.6, pts=[(40.5, -16.5), (46.5, -20.0), (50.5, -26.5), (52.5, -34.0), (53.5, -41.5)]),
}
# plaza objects (projected from A2 onto the plaza plane)
PLAZA_TABLES = [(19.4, -1.5), (19.8, 7.0), (14.9, 16.6), (-19.0, -1.9), (-20.7, 6.4), (-13.8, 15.4)]
PLAZA_EGGS = [(20.3, 9.3), (-7.8, 18.4), (-19.6, 8.9)]
PLAZA_STATUES = [(-9.4, 19.9), (-7.3, 20.6), (-5.3, 20.8)]
PLAZA_SIGN = (-11.1, 18.2)
# lakeside: pointed waterside platform (DWG triangle), its level, the water level
PLATFORM = [(-7.0, -73.6), (7.0, -73.6), (0.0, -82.0)]
Z_PLATFORM = 427.30 - ABS0
Z_WATER = 426.50 - ABS0
# spot heights read on the DWG (x, y, absolute), outside the plaza
SPOTS = [(0, 43, 432.80), (5.7, 30, 434.60), (-14, 50.6, 433.16), (-26.7, 39, 432.42), (-35.2, 31.7, 431.81),
         (-28.6, 21.8, 433.52), (-31.4, 10.3, 434.14), (-44.6, 8.8, 430.88), (-67.7, 7.4, 430.66), (-64.9, 18.5, 431.12),
         (-57.4, 47.9, 431.88), (-71.5, 44.7, 431.35), (-69.6, -2.7, 432.27), (-55.5, -6.3, 430.60), (12.3, 22, 435.39),
         (24, 16.9, 434.96), (29.2, 30, 435.01), (38.2, 38, 435.14), (46.5, 45.2, 434.04), (42, 20.4, 435.04),
         (59.4, 21.3, 432.97), (74, 11.9, 432.73), (74.5, 0.4, 433.59), (70.8, 30, 434.10), (74, 46, 430.14),
         (58.5, 4.8, 433.58), (34.9, -5.3, 434.17), (15.6, 54.2, 430.43), (0.6, -14.2, 435.28), (-17.8, -12.9, 434.87),
         (16.4, -14.4, 434.81), (33.8, -17.1, 434.27), (-39.2, -11.3, 432.72), (-33.6, -21, 431.38), (-5, -36.5, 431.94),
         (21.5, -43, 430.93), (3.7, -26.1, 434.54), (40, -38, 430.14), (-40, -60, 429.47), (-10, -60, 429.68),
         (20, -62, 429.46), (-60, -52, 429.65), (60, -60, 429.30), (0, -71, 429.22), (-60, -70, 429.20), (60, -72, 429.18),
         (-90, -30, 429.74), (-90, 10, 430.50), (-95, 50, 430.50), (0, 62, 430.45), (60, 58, 430.10), (95, 30, 431.50),
         (95, -10, 430.60), (95, -50, 429.50)]


def ring_xy():
    az = np.array([a for a, r, w in RING] + [360.0])
    rc = np.array([r for a, r, w in RING] + [RING[0][1]])
    w = np.array([w for a, r, w in RING] + [RING[0][2]])
    A = np.arange(0, 360, 1.0)
    R = np.interp(A, az, rc); Wd = np.interp(A, az, w)
    # light smoothing (wrap)
    k = np.ones(7) / 7
    R = np.convolve(np.concatenate([R[-3:], R, R[:3]]), k, 'valid')
    return np.stack([R * np.cos(np.radians(A)), R * np.sin(np.radians(A))], 1), Wd


def polyline_dense(pts, step=0.5):
    P = np.array(pts, float)
    out = [P[0]]
    for a, b in zip(P[:-1], P[1:]):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        for t in np.linspace(0, 1, n + 1)[1:]:
            out.append(a + (b - a) * t)
    return np.array(out)


def chaikin(pts, it=3, closed=False):
    P = np.array(pts, float)
    for _ in range(it):
        Q = []
        n = len(P)
        rng = range(n) if closed else range(n - 1)
        if not closed:
            Q.append(P[0])
        for i in rng:
            a, b = P[i], P[(i + 1) % n]
            Q += [0.75 * a + 0.25 * b, 0.25 * a + 0.75 * b]
        if not closed:
            Q.append(P[-1])
        P = np.array(Q)
    return P


GX0, GY0, GX1, GY1, GRES = -130.0, -120.0, 130.0, 85.0, 0.5


def terrain(plaza_poly):
    """terrain heights on the GRES grid: thin-plate fit of the spot heights plus path and plaza levels, then the
    flat areas imposed and blended. Returns H (ny, nx) in model Z, masks."""
    from scipy.interpolate import RBFInterpolator
    xs = np.arange(GX0, GX1 + 1e-6, GRES); ys = np.arange(GY1, GY0 - 1e-6, -GRES)
    X, Y = np.meshgrid(xs, ys)
    P = [(x, y, z - ABS0) for x, y, z in SPOTS]
    # plaza rim and the hill top
    for a in range(0, 360, 10):
        t = math.radians(a)
        r = 26.0
        P.append((r * math.cos(t), r * math.sin(t), -5.15 if math.sin(t) > -0.3 else -5.9))
    for a in range(0, 360, 30):
        t = math.radians(a)
        P.append((14 * math.cos(t), 14 * math.sin(t), -4.8))
    # lake bottom (keeps the fit from bulging under the water)
    for x in range(-120, 121, 20):
        for y in (-95, -110):
            P.append((x, y, Z_WATER - 1.2))
    P = np.array(P)
    rbf = RBFInterpolator(P[:, :2], P[:, 2], kernel='thin_plate_spline', smoothing=2.0)
    H = rbf(np.stack([X.ravel(), Y.ravel()], 1)).reshape(X.shape)
    return xs, ys, X, Y, H


PATHS['n_road'] = dict(w=6.0, kind='pave', pts=[(-130, 60), (-80, 58), (-40, 57.5), (0, 57), (40, 54), (80, 47), (130, 40)])
STAIRS['n_link'] = dict(w=3.0, pts=[(0, 24.7), (0, 28.2)])


def plaza_z(x, y):
    """plaza: -4.80, falling toward the north edge (-5.0 at the pavilion stair foot, -5.45 at the edge, A2/W02)."""
    if y <= 12.0:
        return -4.80
    t = min(1.0, (y - 12.0) / 12.5)
    w = max(0.0, 1.0 - abs(x) / 16.0)
    return -4.80 - 0.65 * (t ** 1.3) * w


def poly_mask(poly, X, Y):
    """cells of the grid (X, Y from meshgrid on GX0/GY1/GRES) inside a polygon, via cv2.fillPoly."""
    m = np.zeros(X.shape, np.uint8)
    P = np.asarray(poly, float)
    px = np.stack([(P[:, 0] - GX0) / GRES, (GY1 - P[:, 1]) / GRES], 1)
    cv2.fillPoly(m, [np.round(px * 16).astype(np.int32).reshape(-1, 1, 2)], 1, lineType=cv2.LINE_8, shift=4)
    return m > 0


def corridor(pts_dense, half, X, Y):
    """mask of cells within `half` of a dense polyline, and the index of the nearest centreline point."""
    from scipy.spatial import cKDTree
    t = cKDTree(pts_dense[:, :2])
    d, i = t.query(np.stack([X.ravel(), Y.ravel()], 1), distance_upper_bound=half + 6.0)
    d = d.reshape(X.shape); i = i.reshape(X.shape)
    return d, i


def smooth_along(z, win):
    k = max(1, int(win))
    pad = np.concatenate([np.full(k, z[0]), z, np.full(k, z[-1])])
    c = np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), 'valid')
    return c


def relax(H0, fixed, T, lam=0.05, iters=600):
    """screened-Poisson relaxation: fixed cells hold T, free cells smooth toward their neighbours and H0."""
    H = np.where(fixed, T, H0).astype(np.float64)
    for _ in range(iters):
        nb = np.zeros_like(H)
        nb[1:-1, 1:-1] = H[:-2, 1:-1] + H[2:, 1:-1] + H[1:-1, :-2] + H[1:-1, 2:]
        Hn = (nb + lam * H0) / (4.0 + lam)
        Hn[0, :] = H0[0, :]; Hn[-1, :] = H0[-1, :]; Hn[:, 0] = H0[:, 0]; Hn[:, -1] = H0[:, -1]
        H = np.where(fixed, T, Hn)
    return H


def poisson_disc(rng, cand, r):
    """greedy Poisson-disc thinning of candidate points (shuffled)."""
    from scipy.spatial import cKDTree
    idx = rng.permutation(len(cand))
    keep = []
    grid = {}
    cs = r / math.sqrt(2)
    for i in idx:
        x, y = cand[i]
        gi, gj = int(x // cs), int(y // cs)
        ok = True
        for di in (-2, -1, 0, 1, 2):
            for dj in (-2, -1, 0, 1, 2):
                for k in grid.get((gi + di, gj + dj), ()):
                    if (cand[k][0] - x) ** 2 + (cand[k][1] - y) ** 2 < r * r:
                        ok = False; break
                if not ok: break
            if not ok: break
        if ok:
            keep.append(i)
            grid.setdefault((gi, gj), []).append(i)
    return [cand[i] for i in keep]


def build_all():
    rng = np.random.default_rng(zlib.crc32(b'qiting-env'))
    img, white, blue, purple, green, red = load_dwg()
    az, pr = plaza_outline(white)
    plaza = np.stack([pr * np.cos(np.radians(az)), pr * np.sin(np.radians(az))], 1)
    ring_c, ring_w = ring_xy()
    xs, ys, X, Y, H0 = terrain(plaza)
    fixed = np.zeros(X.shape, bool); T = np.zeros(X.shape)
    paved = np.zeros(X.shape, bool)
    # --- plaza
    pm = poly_mask(plaza, X, Y)
    pz = np.vectorize(plaza_z)(X, Y)
    fixed |= pm; T[pm] = pz[pm]; paved |= pm
    # --- paths: heights from the fit along the centreline, smoothed; the ring path closed
    path_out = {}
    def add_path(name, P, w, kind, closed=False, zfix=None):
        Pd = polyline_dense(np.vstack([P, P[:1]]) if closed else P, 0.5)
        zc = H0[np.clip(((GY1 - Pd[:, 1]) / GRES).astype(int), 0, X.shape[0] - 1),
                np.clip(((Pd[:, 0] - GX0) / GRES).astype(int), 0, X.shape[1] - 1)]
        if zfix is not None:
            zc = np.array([zfix(x, y) for x, y in Pd])
        zc = smooth_along(zc, 16)
        d, i = corridor(np.c_[Pd, zc], w / 2, X, Y)
        m = d <= w / 2 + 0.35
        ok = m & (i < len(Pd))
        fixed[ok] = True; T[ok] = zc[i[ok]]
        paved[d <= w / 2] = True
        path_out[name] = dict(kind=kind, w=w, closed=closed, pts=[(round(float(x), 3), round(float(y), 3), round(float(z), 3)) for (x, y), z in zip(Pd, zc)])
    # ring path: width varies, use the mean
    add_path('ring', ring_c, float(np.mean(ring_w)), 'pave', closed=True)
    walk_y = lambda x: float(np.interp(x, [p[0] for p in PATHS['walk']['pts']], [p[1] for p in PATHS['walk']['pts']]))
    for k, d in PATHS.items():
        P = chaikin(d['pts'], 3)
        zf = None
        if k == 'walk':
            zf = lambda x, y: 429.20 - ABS0
        if k == 'prom':
            zf = lambda x, y: 429.90 - ABS0 + 0.004 * abs(x)
        add_path(k, P, d['w'], d['kind'], zfix=zf)
    # --- stairs: straight ramps between their end heights (steps are built in Blender)
    stair_out = {}
    for k, d in STAIRS.items():
        P = chaikin(d['pts'], 3) if len(d['pts']) > 2 else np.array(d['pts'], float)
        Pd = polyline_dense(P, 0.25)
        def hz(x, y):
            j = int(np.clip((GY1 - y) / GRES, 0, X.shape[0] - 1)); i = int(np.clip((x - GX0) / GRES, 0, X.shape[1] - 1))
            return T[j, i] if fixed[j, i] else H0[j, i]
        z0, z1 = hz(*Pd[0]), hz(*Pd[-1])
        if k == 'n_link':
            z0 = plaza_z(0, 24.7)
        zc = np.linspace(z0, z1, len(Pd))
        dd, ii = corridor(np.c_[Pd, zc], d['w'] / 2, X, Y)
        m = (dd <= d['w'] / 2 + 0.4) & (ii < len(Pd))
        fixed[m] = True; T[m] = zc[ii[m]]
        paved[dd <= d['w'] / 2] = True
        stair_out[k] = dict(w=d['w'], pts=[(round(float(x), 3), round(float(y), 3)) for x, y in P], z0=round(float(z0), 3), z1=round(float(z1), 3))
    # --- lake: everything south of the walk's southern edge (and the platform is its own object)
    wy = np.vectorize(walk_y)(X)
    water = Y < wy - PATHS['walk']['w'] / 2 - 0.02
    fixed |= water; T[water] = Z_WATER - 1.4
    # --- relax
    H = relax(H0, fixed, T)
    print('terrain relaxed: Z %.2f .. %.2f' % (H.min(), H.max()))
    # --- cover weights: bank (between the plaza and the ring path), forest floor (under the tree zones)
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    ring_mask = np.zeros(X.shape, bool)
    d_r, i_r = corridor(np.c_[polyline_dense(np.vstack([ring_c, ring_c[:1]]), 0.5), np.zeros(len(polyline_dense(np.vstack([ring_c, ring_c[:1]]), 0.5)))], 1.5, X, Y)
    rr = np.hypot(X, Y)
    ring_r = np.interp(np.degrees(np.arctan2(Y, X)) % 360, np.arange(0, 360, 1.0), np.hypot(ring_c[:, 0], ring_c[:, 1]))
    plaza_r = np.interp(np.degrees(np.arctan2(Y, X)) % 360, az, pr, period=360)
    bank = (~pm) & (rr < ring_r - 1.3) & (rr > plaza_r - 0.2)
    # --- trees
    trees = []
    def zone(x, y):
        """species mix and Poisson-disc spacing per area, read off the aerials A1/A2."""
        r = math.hypot(x, y)
        if y < -47 and y > -66:                 # lakeside lawn strip: open lawn, a few round trees (willows by the edge)
            return dict(broad=0.55, willow=0.30, small=0.15), 14.0
        if r < 48 and y > 18:                   # north slope band (aerial foreground): big deodars
            return dict(cedar=0.60, broad=0.30, column=0.10), 6.0
        if x > 6 and y > 14 and r < 66:         # north-east wood (A2 lower left, y 16-33): deodars and broadleaf, closed canopy
            return dict(cedar=0.42, broad=0.48, column=0.10), 6.0
        if x < -6 and y > 8 and r < 62:         # north-west wood (A2 lower right)
            return dict(cedar=0.42, broad=0.53, column=0.05), 6.5
        if 12 < x < 45 and -20 < y <= 0:        # grove of small round-headed trees east of the plaza (A2 centre left)
            return dict(small=0.55, broad=0.45), 5.0
        if x > 35 and y > -45:                  # east slope: lawn with groups of round trees and some deodars
            return dict(broad=0.75, cedar=0.25), 14.0
        if x < -35 and y > -36:                 # west slope: lawn with round trees
            return dict(broad=0.85, cedar=0.15), 11.5
        if -47 <= y <= -24 and abs(x) <= 40:    # south slope below the plaza: round broadleaf trees, lawn between
            return dict(broad=0.65, small=0.35), 8.5
        if y >= 48:                              # beyond the north path / road
            return dict(cedar=0.55, broad=0.30, column=0.15), 6.5
        return dict(broad=0.7, cedar=0.3), 9.0
    cand = []
    for x in np.arange(GX0 + 2, GX1 - 2, 1.3):
        for y in np.arange(-66, GY1 - 2, 1.3):
            cand.append((x + rng.uniform(-0.6, 0.6), y + rng.uniform(-0.6, 0.6)))
    cand = np.array(cand)
    # exclusions: paved (with clearance), bank band, inside the ring path, water
    from scipy.spatial import cKDTree
    pv_idx = np.argwhere(paved)
    pv_xy = np.c_[GX0 + pv_idx[:, 1] * GRES, GY1 - pv_idx[:, 0] * GRES]
    tp = cKDTree(pv_xy)
    dpv, _ = tp.query(cand, distance_upper_bound=4.0)
    rc = np.hypot(cand[:, 0], cand[:, 1])
    ring_rc = np.interp(np.degrees(np.arctan2(cand[:, 1], cand[:, 0])) % 360, np.arange(0, 360, 1.0), np.hypot(ring_c[:, 0], ring_c[:, 1]))
    grove = (cand[:, 0] > 12) & (cand[:, 0] < 45) & (cand[:, 1] > -20) & (cand[:, 1] <= 0)   # A2: trees inside the ring here
    ok = (dpv > 2.2) & ((rc > ring_rc + 2.0) | grove)
    cand = cand[ok]
    # density per zone: thin with zone-specific disc radius
    by_r = {}
    for c in cand:
        sp, rad = zone(*c)
        by_r.setdefault(rad, []).append(c)
    for rad, cs in by_r.items():
        for (x, y) in poisson_disc(rng, cs, rad):
            sp, _ = zone(x, y)
            names = list(sp); w = np.array([sp[n] for n in names]); w = w / w.sum()
            kind = names[rng.choice(len(names), p=w)]
            j = int(np.clip((GY1 - y) / GRES, 0, X.shape[0] - 1)); i = int(np.clip((x - GX0) / GRES, 0, X.shape[1] - 1))
            trees.append((round(float(x), 2), round(float(y), 2), round(float(H[j, i]), 3), kind, int(rng.integers(0, 5)),
                          round(float(rng.uniform(0.75, 1.25)), 3), round(float(rng.uniform(0, 6.283)), 3)))
    # the two planting pockets on the north side of the plaza: one cedar each (A2)
    for (x, y) in ((-16.8, 19.6), (16.8, 19.6)):
        j = int((GY1 - y) / GRES); i = int((x - GX0) / GRES)
        trees.append((x, y, round(float(H[j, i]), 3), 'cedar', 2, 1.05, 0.7))
    # willows along the lake edge of the walk's land side
    for x in np.arange(-120, 121, 8.5):
        y = walk_y(x) + PATHS['walk']['w'] / 2 + 2.2 + rng.uniform(-0.6, 0.8)
        if abs(x) < 10:
            continue
        j = int(np.clip((GY1 - y) / GRES, 0, X.shape[0] - 1)); i = int(np.clip((x - GX0) / GRES, 0, X.shape[1] - 1))
        trees.append((round(float(x + rng.uniform(-1.5, 1.5)), 2), round(float(y), 2), round(float(H[j, i]), 3), 'willow',
                      int(rng.integers(0, 5)), round(float(rng.uniform(0.9, 1.15)), 3), round(float(rng.uniform(0, 6.283)), 3)))
    print('trees', len(trees), {k: sum(1 for t in trees if t[3] == k) for k in ('cedar', 'broad', 'column', 'small', 'willow')})
    # --- hedges: a clipped band in the bank just outside the plaza edge, broken at the stairs and pockets
    hedge = []
    seg = []
    for a, r in zip(az, pr):
        if (85 <= a <= 95) or (265 <= a <= 275) or (34 <= a <= 50) or (130 <= a <= 146):
            if len(seg) > 3: hedge.append(seg)
            seg = []
            continue
        rh = r + 1.15
        x, y = rh * math.cos(math.radians(a)), rh * math.sin(math.radians(a))
        j = int(np.clip((GY1 - y) / GRES, 0, X.shape[0] - 1)); i = int(np.clip((x - GX0) / GRES, 0, X.shape[1] - 1))
        seg.append((round(float(x), 3), round(float(y), 3), round(float(H[j, i]), 3)))
    if len(seg) > 3: hedge.append(seg)
    # --- lamps
    lamps = []
    def along(P, step, off, kind, z_of):
        Pd = polyline_dense(P, 0.25)
        L = np.r_[0, np.cumsum(np.hypot(*np.diff(Pd, axis=0).T))]
        for s_ in np.arange(step / 2, L[-1], step):
            k = np.searchsorted(L, s_)
            k = min(max(k, 1), len(Pd) - 1)
            t = Pd[k] - Pd[k - 1]; t /= (np.linalg.norm(t) + 1e-9)
            n = np.array([-t[1], t[0]])
            for sd in (off if isinstance(off, (list, tuple)) else [off]):
                q = Pd[k] + n * sd
                lamps.append((round(float(q[0]), 2), round(float(q[1]), 2), round(float(z_of(q[0], q[1])), 3), kind,
                              round(float(math.atan2(t[1], t[0])), 3)))
    def hz(x, y):
        j = int(np.clip((GY1 - y) / GRES, 0, X.shape[0] - 1)); i = int(np.clip((x - GX0) / GRES, 0, X.shape[1] - 1))
        return H[j, i]
    along(np.vstack([ring_c, ring_c[:1]]), 15.0, [-(float(np.mean(ring_w)) / 2 + 0.45)], 'park', hz)
    along(chaikin(PATHS['prom']['pts']), 18.0, [PATHS['prom']['w'] / 2 + 0.5, -(PATHS['prom']['w'] / 2 + 0.5)], 'lantern', hz)
    along(chaikin(PATHS['walk']['pts']), 24.0, [PATHS['walk']['w'] / 2 - 0.4], 'walk', hz)
    for k in ('north', 'west', 'e_spur', 'east', 'n_road'):
        along(chaikin(PATHS[k]['pts']), 20.0, [PATHS[k]['w'] / 2 + 0.45], 'park', hz)
    lamps.append((-9.5, -68.6, round(float(hz(-9.5, -68.6)), 3), 'mast', 0.0))
    # --- sculptures (丽人行, white figure groups on plinths): between the promenade and the walk (DWG symbols, A1/A2)
    sculpt = []
    for (x, y, rot) in ((-40, -60.5, 0.3), (-33, -64, -0.2), (-25.5, -60, 0.1), (-17.5, -63.5, 0.4), (-10.5, -60.5, -0.3),
                        (12, -61, 0.2), (21, -64, -0.1), (30, -60.5, 0.35)):
        sculpt.append((x, y, round(float(hz(x, y)), 3), rot))
    out = dict(plaza=[(round(float(x), 3), round(float(y), 3)) for x, y in plaza], plaza_az_r=[(float(a), round(float(r), 3)) for a, r in zip(az, pr)],
               paths=path_out, stairs=stair_out, trees=trees, hedges=hedge, lamps=lamps, sculptures=sculpt,
               tables=PLAZA_TABLES, eggs=PLAZA_EGGS, statues=PLAZA_STATUES, sign=PLAZA_SIGN,
               platform=PLATFORM, z_platform=Z_PLATFORM, z_water=Z_WATER, abs0=ABS0,
               walk=dict(pts=PATHS['walk']['pts'], w=PATHS['walk']['w']))
    with open(os.path.join(LIB, 'qt_env_data.py'), 'w') as f:
        f.write('# generated by qiting/env/make_env.py - site layout of the surroundings (model metres)\n')
        f.write('ENV = ' + repr(out) + '\n')
    # --- grid module
    def enc(a, dt):
        return base64.b64encode(zlib.compress(np.ascontiguousarray(a.astype(dt)).tobytes(), 9)).decode('ascii')
    Hmm = np.round(H * 1000).astype(np.int32)
    w_bank = gaussian_filter(bank.astype(float), 1.5)
    with open(os.path.join(LIB, 'qt_env_grid.py'), 'w') as f:
        f.write('# generated by qiting/env/make_env.py - terrain grid (Z in mm, int32) and cover weights (uint8)\n')
        f.write('GX0, GY1, GRES, GNX, GNY = %r, %r, %r, %d, %d\n' % (GX0, GY1, GRES, X.shape[1], X.shape[0]))
        f.write('H_MM_B64 = %r\n' % enc(Hmm, np.int32))
        f.write('PAVED_B64 = %r\n' % enc(paved.astype(np.uint8), np.uint8))
        f.write('WATER_B64 = %r\n' % enc(water.astype(np.uint8), np.uint8))
        f.write('BANK_B64 = %r\n' % enc(np.clip(w_bank * 255, 0, 255), np.uint8))
        f.write('PLAZA_B64 = %r\n' % enc(pm.astype(np.uint8), np.uint8))
    np.savez_compressed(os.path.join(WORK, 'terrain_final.npz'), H=H, paved=paved, water=water, bank=bank, pm=pm)
    # preview
    gy, gx = np.gradient(H, GRES)
    shade = np.clip(0.62 + (-gx * 0.7 + gy * 0.7), 0, 1)
    vis = (np.stack([shade] * 3, 2) * 210).astype(np.uint8)
    vis[paved] = (vis[paved] * 0.5 + np.array([60, 60, 160])).astype(np.uint8)
    vis[water] = (140, 90, 40)
    vis[bank] = (vis[bank] * 0.6 + np.array([0, 70, 0])).astype(np.uint8)
    for t in trees:
        c = {'cedar': (40, 90, 20), 'broad': (40, 160, 60), 'column': (90, 200, 120), 'small': (100, 200, 160), 'willow': (60, 200, 200)}[t[3]]
        cv2.circle(vis, (int((t[0] - GX0) / GRES), int((GY1 - t[1]) / GRES)), 3, c, -1)
    for l in lamps:
        cv2.circle(vis, (int((l[0] - GX0) / GRES), int((GY1 - l[1]) / GRES)), 1, (0, 0, 255), -1)
    cv2.imwrite(os.path.join(WORK, 'view', 'env_final.png'), vis)
    print('lamps', len(lamps), 'hedge segments', len(hedge), 'sculptures', len(sculpt))


if __name__ == '__main__' and '--preview' not in sys.argv:
    build_all()
    sys.exit(0)

if __name__ == '__main__':
    import json
    img, white, blue, purple, green, red = load_dwg()
    az, pr = plaza_outline(white)
    plaza = np.stack([pr * np.cos(np.radians(az)), pr * np.sin(np.radians(az))], 1)
    ring, ring_w = ring_xy()
    xs, ys, X, Y, H = terrain(plaza)
    print('terrain', H.shape, 'Z range %.2f .. %.2f' % (H.min(), H.max()))
    np.savez_compressed(os.path.join(WORK, 'terrain_raw.npz'), H=H, xs=xs, ys=ys)
    # preview: hillshade with layout
    gy, gx = np.gradient(H, GRES)
    shade = np.clip(0.6 + (-gx * 0.6 + gy * 0.6), 0, 1)
    vis = (np.stack([shade] * 3, 2) * 200).astype(np.uint8)
    def px(x, y):
        return int((x - GX0) / GRES), int((GY1 - y) / GRES)
    cv2.polylines(vis, [np.array([px(*p) for p in plaza]).reshape(-1, 1, 2)], True, (0, 200, 255), 1)
    cv2.polylines(vis, [np.array([px(*p) for p in ring]).reshape(-1, 1, 2)], True, (0, 120, 255), 2)
    for k, d in PATHS.items():
        cv2.polylines(vis, [np.array([px(*p) for p in chaikin(d['pts'])]).reshape(-1, 1, 2)], False,
                      (255, 80, 200) if d['kind'] == 'pink' else (255, 200, 0), 2)
    for x, y, z in SPOTS:
        cv2.circle(vis, px(x, y), 2, (0, 0, 255), -1)
    lv = np.clip((H - H.min()) / (H.max() - H.min()), 0, 1)
    cont = (np.abs(((H * 2) % 1) - 0.5) < 0.06)
    vis[cont] = (90, 160, 90)
    cv2.imwrite(os.path.join(WORK, 'view', 'env_layout.png'), vis)
    print('wrote env_layout.png')
