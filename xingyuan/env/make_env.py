# Xingyuan environment - data generator (runs locally, NOT in Blender).
# Reads the shapes measured on the calibrated aerial photo (plan metres, X east, Y north, Z: courtyard -0.6),
# builds: terrain height grid + ground-material grid, water / lotus / open-water masks, and all placements
# (trees, shrubs, bank plants, lotus, rocks). Writes xy_env_data.py and xy_env_grid.py into scripts/lib.
import sys, os, math, json, random, base64, zlib
import numpy as np
import cv2
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, '..', 'scripts', 'lib')
sys.path.insert(0, LIB)
import xy_layout as LY

WL = -1.45          # water level
ZG = -0.66          # natural ground next to paving
ZP = -0.60          # paving / courtyard level

# ------------------------------------------------------------------ measured shapes (plan metres)
RAIL = [(27.0, -24.9), (25.6, -24.4), (22.4, -23.8), (20.4, -23.2), (17.0, -21.6), (14.0, -19.7), (11.5, -18.3), (9.0, -15.9),
        (7.1, -13.1), (5.4, -10.1), (3.8, -7.2), (3.2, -3.4), (3.0, -0.3), (3.4, 3.2), (4.0, 6.3), (5.2, 9.4), (6.2, 11.6), (7.4, 13.6)]
RED_TERRACE = RAIL + [(10.08, 13.6), (13.08, 13.6), (13.08, -1.09), (23.37, -1.09), (23.37, -9.1), (27.0, -9.1)]
CRAZY = [(-4.48, 27.34), (-4.8, 24.0), (-3.8, 20.5), (-1.5, 17.6), (2.0, 15.9), (6.5, 15.0), (7.4, 13.6), (10.08, 13.6),
         (10.08, 22.67), (7.2, 22.67), (7.2, 27.34)]
GRAY_PLAZA = [[(27.0, -33.0), (43.3, -33.0), (43.3, -9.1), (27.0, -9.1)],
              [(43.3, -25.6), (47.5, -25.6), (47.5, -14.4), (43.3, -14.4)]]
SCULPT_PLAZA = ((47.5, -20.0), 5.6)
SW_PLAZA = [(-24.0, -31.0), (-4.6, -31.0), (-4.6, -27.0), (-6.8, -23.6), (-9.2, -21.4), (-13.0, -20.6), (-16.5, -20.8),
            (-21.0, -21.8), (-24.0, -23.0)]
PINK_PATH = [(-13.5, -21.0), (-15.6, -16.5), (-17.3, -12.2), (-18.8, -8.2), (-20.0, -4.6), (-21.3, -0.4), (-22.6, 3.9),
             (-24.0, 8.0), (-25.7, 12.2), (-27.4, 16.2), (-28.9, 20.2)]
PINK_W = 1.9
SLAB_BRIDGE = ((-29.2, 21.6), (-25.4, 26.8), 1.6)
GRAY_PATH_N = [(-25.0, 27.4), (-21.0, 29.6), (-15.5, 30.8), (-10.0, 31.2), (-4.48, 31.4)]
GRAY_N_W = 1.8
EAST_PATH = [(93.2, -40.0), (92.6, -22.0), (91.6, -15.0), (91.2, -9.0), (91.3, -4.0), (90.6, 1.0), (89.6, 6.0), (89.4, 11.0),
             (90.2, 16.0), (91.6, 21.0), (93.2, 25.5), (95.5, 29.0), (99.0, 34.0), (103.0, 40.0)]
EAST_W = 1.8

# main lotus pond + stream (west, south of A5): west bank = rock line, east bank = terrace railing
POND_MAIN = [(-3.5, -42.0), (-3.0, -30.0), (-4.0, -26.0), (-6.5, -23.0), (-9.0, -20.5), (-11.5, -17.5), (-13.0, -14.5),
             (-14.6, -11.5), (-16.0, -8.0), (-17.2, -4.5), (-18.4, -1.0), (-19.6, 2.5), (-20.6, 6.0), (-21.0, 9.5),
             (-20.8, 13.0), (-21.5, 16.5), (-23.3, 19.2), (-27.0, 22.2), (-30.4, 24.4), (-32.8, 25.6), (-37.0, 25.0),
             (-40.0, 27.5), (-40.6, 31.5), (-38.6, 34.6), (-35.0, 35.6), (-31.6, 34.0), (-29.6, 31.0), (-28.6, 28.2),
             (-26.6, 26.4), (-23.6, 24.2), (-19.6, 21.6), (-15.8, 20.6), (-12.0, 20.0), (-8.8, 18.6), (-4.5, 17.0),
             (1.5, 15.0), (6.0, 14.2), (7.0, 13.2), (5.7, 11.4), (4.7, 9.3), (3.5, 6.2), (2.9, 3.1), (2.5, -0.3),
             (2.7, -3.5), (3.3, -7.3), (4.8, -10.2), (6.3, -13.2), (7.6, -15.3), (8.0, -17.5), (7.5, -20.5),
             (7.0, -23.5), (7.0, -27.0), (7.5, -31.0), (8.0, -42.0)]
# open water (no lotus) inside the main pond, from the water/vegetation profile of the aerial
OPEN_W = [(-24, 1.0), (-22, -0.5), (-20, -3.0), (-18, -4.0), (-16, -5.5), (-14, -5.5), (-12, -5.0), (-10, -6.5), (-8, -7.5),
          (-6, -9.5), (-4, -12.0), (-2, -16.5), (0, -17.5), (2, -18.5), (4, -18.5), (6, -20.5), (8, -21.0), (10, -21.5),
          (12, -20.5), (14, -20.0), (16, -20.0)]
OPEN_E = [(-24, 6.0), (-22, 6.0), (-20, 6.0), (-18, 6.5), (-16, 5.5), (-14, 3.5), (-12, 2.0), (-10, -0.5), (-8, -2.0),
          (-6, -3.0), (-4, -4.5), (-2, -6.5), (0, -6.5), (2, -6.5), (4, -8.5), (6, -10.0), (8, -11.0), (10, -11.0),
          (12, -11.0), (14, -8.5), (16, -8.0)]
POND_N = [(-19.0, 56.0), (-8.0, 55.5), (2.0, 56.0), (6.5, 57.2), (8.0, 60.8), (14.0, 61.6), (17.0, 64.0), (15.0, 70.0),
          (8.0, 75.0), (-2.0, 77.0), (-12.0, 76.0), (-19.0, 71.0), (-21.0, 63.0)]
CHANNEL_NW = ([(-36.5, 33.5), (-33.5, 40.0), (-29.5, 46.0), (-25.0, 52.0), (-19.5, 58.0)], 2.1)

FOUNTAINS = [(-9.36, 0.20, 1.6), (-35.0, 29.3, 1.2)]
STONES = [(-16.19, 7.10), (-15.01, 6.95), (-13.95, 6.35), (-13.30, 5.85), (-12.85, 6.45), (-12.20, 6.75), (-11.55, 6.95),
          (-10.85, 7.15)]
FRAMES = [((-19.52, -4.32), 11.7), ((-23.20, 4.35), 13.1), ((-26.60, 13.10), 15.0)]
LAMPS = [(26.43, -11.25), (44.65, -11.95)]
SCULPTURE = ((47.91, -18.29), 3.53, 1.70)
PLANTERS = [((6.8, 6.4), -25.0, (2.0, 1.4)), ((5.5, -1.1), -5.0, (2.0, 1.4)), ((7.0, -8.5), 25.0, (2.0, 1.4)),
            ((10.6, -15.0), 40.0, (2.0, 1.4))]
LAWN_PLANTER = ((24.1, -22.5), (2.4, 2.0))
BENCHES = [((12.9, -18.0), 33.0), ((17.3, -20.2), 22.0), ((20.8, -21.9), 14.0), ((6.0, 2.6), -80.0), ((-18.0, -24.5), 0.0),
           ((-11.0, -24.0), 0.0), ((-26.4, 6.2), 72.0), ((-23.0, -2.8), 70.0)]

# ------------------------------------------------------------------ grids
X0, X1, Y0, Y1 = -90.0, 125.0, -65.0, 105.0
RES = 0.25
NX, NY = int(round((X1 - X0) / RES)), int(round((Y1 - Y0) / RES))
xs = X0 + (np.arange(NX) + 0.5) * RES
ys = Y1 - (np.arange(NY) + 0.5) * RES         # row 0 = north
XX, YY = np.meshgrid(xs, ys)

def to_px(pts):
    return np.array([[(x - X0) / RES, (Y1 - y) / RES] for x, y in pts], dtype=np.float32)

def poly_mask(pts):
    m = np.zeros((NY, NX), np.uint8)
    cv2.fillPoly(m, [np.round(to_px(pts) * 16).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)

def poly_line_mask(pts, width):
    m = np.zeros((NY, NX), np.uint8)
    p = np.round(to_px(pts) * 16).astype(np.int32)
    cv2.polylines(m, [p], False, 1, thickness=max(1, int(round(width / RES))), lineType=cv2.LINE_8, shift=4)
    return m.astype(bool)

def circle_mask(c, r):
    return (XX - c[0]) ** 2 + (YY - c[1]) ** 2 <= r * r

def rect_mask(x0, y0, x1, y1):
    return (XX >= x0) & (XX <= x1) & (YY >= y0) & (YY <= y1)

def dist_outside(mask):
    """distance (m) from each cell outside the mask to the mask"""
    return cv2.distanceTransform((~mask).astype(np.uint8), cv2.DIST_L2, 5) * RES

def dist_inside(mask):
    return cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5) * RES

def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)

# ---- complex footprint (as in xy_build_site): raised floors, courtyards, pool, 3 m apron
raised = np.zeros((NY, NX), bool)
for (rect, l, name) in LY.RAISED:
    raised |= rect_mask(*rect)
courts = np.zeros((NY, NX), bool)
for k, cd in LY.COURTS.items():
    courts |= rect_mask(*cd['rect'])
complex_core = raised | courts
apron = (dist_outside(complex_core) <= 3.0)

# ---- paved environment
red = poly_mask(RED_TERRACE)
crazy = poly_mask(CRAZY)
gray = np.zeros((NY, NX), bool)
for g in GRAY_PLAZA:
    gray |= poly_mask(g)
gray |= circle_mask(*SCULPT_PLAZA)
pink = poly_line_mask(PINK_PATH, PINK_W) | poly_mask(SW_PLAZA)
grayn = poly_line_mask(GRAY_PATH_N, GRAY_N_W)
eastp = poly_line_mask(EAST_PATH, EAST_W)
paved = apron | complex_core | red | crazy | gray | pink | grayn | eastp

# ---- water
pond_main = poly_mask(POND_MAIN)
pond_n = poly_mask(POND_N)
chan = poly_line_mask(CHANNEL_NW[0], CHANNEL_NW[1] * 2)
water = (pond_main | pond_n | chan) & ~paved
water = cv2.morphologyEx(water.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
# along the terrace railing the pond runs right up to the stone retaining wall (no exposed bank; lotus to the wall)
rail_strip = (~paved) & (dist_outside(red) < 1.2) & (dist_outside(water) < 1.4)
water |= rail_strip
open_band = np.zeros((NY, NX), bool)
oy = [p[0] for p in OPEN_W]
for j in range(NY):
    y = ys[j]
    if y < oy[0] or y > oy[-1]:
        continue
    xw = np.interp(y, oy, [p[1] for p in OPEN_W]); xe = np.interp(y, oy, [p[1] for p in OPEN_E])
    open_band[j] = (xs >= xw) & (xs <= xe)
# in the main pond: lotus = pond minus open band (only y -26..16); elsewhere open
lotus_zone = (pond_main | rail_strip) & water & ~open_band & (YY > -30) & (YY < 15.5)
# lotus also in shallow margins of the north lake (patches)
din_w = dist_inside(water)
rng = np.random.default_rng(7)
noise = cv2.GaussianBlur(rng.random((NY, NX)).astype(np.float32), (0, 0), 14)
noise = (noise - noise.min()) / (noise.max() - noise.min())
lotus_zone |= pond_n & water & (din_w < 3.2) & (noise > 0.55)
lotus_zone &= din_w > 0.35

# ---- terrain heights
dpav = dist_outside(paved)
dwat = dist_outside(water)
# gentle mounds away from paving/water
fbm = np.zeros((NY, NX), np.float32)
for sc, amp in ((90, 1.0), (45, 0.5), (22, 0.25)):
    n = cv2.GaussianBlur(rng.random((NY, NX)).astype(np.float32), (0, 0), sc / RES / 6)
    n = (n - n.mean()) / (n.std() + 1e-6)
    fbm += amp * n
fbm = fbm / 1.75
mound = np.clip(fbm, -0.4, 1.6) * 0.35 + 0.12
wm = smooth((dpav - 1.5) / 7.0) * smooth((dwat - 2.5) / 6.0)
H = ZG + mound * wm
# water banks: slope from the shore (WL-0.12) up to the land height over b metres (steep next to paving)
b = np.where(dpav < 2.5, 0.6, 2.8)
tb = smooth(dwat / b)
bank = (WL - 0.12) + (H - (WL - 0.12)) * (tb ** 0.85)
H = np.where(water, H, np.where(dwat < b, bank, H))
# water bed
depth = 0.30 + 0.55 * smooth(din_w / 3.0)
H = np.where(water, WL - 0.12 - depth, H)
# under paving / complex: hidden below the paving
H = np.where(paved, -0.69, H)

# ------------------------------------------------------------------ placements
random.seed(11)
def inside_poly(pt, poly):
    x, y = pt; inside = False; n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside

def cell(x, y):
    i = int((x - X0) / RES); j = int((Y1 - y) / RES)
    return min(max(j, 0), NY - 1), min(max(i, 0), NX - 1)

def poisson(region_fn, bbox, spacing, n_try=30, existing=None, seed=1):
    """Bridson-like dart throwing: points inside region_fn with min distance spacing (and to existing points)."""
    r = random.Random(seed)
    x0, y0, x1, y1 = bbox
    pts = []
    others = list(existing) if existing else []
    tree = cKDTree(others) if others else None
    tries = int((x1 - x0) * (y1 - y0) / (spacing * spacing) * n_try)
    for _ in range(tries):
        p = (r.uniform(x0, x1), r.uniform(y0, y1))
        if not region_fn(p):
            continue
        if tree is not None and tree.query(p)[0] < spacing * 0.92:
            continue
        if any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < spacing * spacing for q in pts[-400:]):
            continue
        if pts:
            dd, _ = cKDTree(pts).query(p) if len(pts) % 50 == 0 else (None, None)
        pts.append(p)
    # final cleanup with a KD-tree (dart throwing above checks only recent points)
    keep = []
    for p in pts:
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= spacing * spacing for q in keep):
            keep.append(p)
    return keep

block_trunk = paved | water
dblock = dist_outside(block_trunk)
def free(p, clear=1.2):
    j, i = cell(*p)
    return dblock[j, i] >= clear

ZONES = [
    # name, species, polygon, spacing, size range, clearance
    ('W_main', 'mix:willow=0.45,light=0.35,broad=0.2', [(-88, 14), (-6, 14), (-6, 104), (-88, 104)], 8.2, (0.85, 1.15), 1.4),
    ('W_strip', 'willow', [(-62, -42), (-23.5, -42), (-23.5, -24), (-26, -12), (-29, 0), (-31.5, 14), (-62, 14)], 8.4, (0.8, 1.1), 1.6),
    ('W_northlake', 'mix:willow=0.6,light=0.25,broad=0.15', [(-6, 62), (22, 62), (22, 104), (-6, 104)], 8.8, (0.9, 1.15), 1.2),
    ('Broad_N', 'broad', [(16, 66.5), (76, 66.5), (76, 104), (16, 104)], 8.6, (0.85, 1.25), 1.5),
    ('Broad_N2', 'broad', [(16, 58), (38, 58), (38, 66.5), (16, 66.5)], 7.8, (0.8, 1.1), 1.5),
    ('Broad_N3', 'broad', [(64, 56), (76, 56), (76, 66.5), (64, 66.5)], 7.8, (0.8, 1.1), 1.5),
    ('Broad_N4', 'broad', [(38, 58), (64, 58), (64, 66.5), (38, 66.5)], 7.4, (0.85, 1.15), 1.5),
    ('Broad_NE', 'broad', [(76, 38), (124, 38), (124, 104), (76, 104)], 8.8, (0.9, 1.25), 1.5),
    ('Purple_E', 'purple', [(61, -2.5), (84, -2.5), (84, 19), (78, 25.5), (69.6, 25.5), (69.6, 19.4), (61, 19.4)], 4.7, (0.85, 1.25), 1.3),
    ('Light_E', 'light', [(69.6, 26), (84, 26), (84, 37.5), (76, 37.5), (69.6, 35.2)], 6.8, (0.85, 1.15), 1.2),
    ('Broad_Eedge', 'broad', [(98, -64), (124, -64), (124, 38), (98, 38)], 8.6, (0.9, 1.25), 1.5),
    ('Broad_SE', 'broad', [(58, -64), (98, -64), (98, -3.5), (84, -3.5), (64, -4.0), (58, -8.0), (58, -30)], 8.4, (0.85, 1.25), 1.5),
    ('Light_SE', 'light', [(51, -13.5), (58, -13.5), (58, -2.5), (51, -2.5)], 6.0, (0.8, 1.0), 1.2),
    ('Light_SE2', 'light', [(48, -64), (58, -64), (58, -32), (52, -29), (48, -34)], 7.0, (0.85, 1.1), 1.4),
    ('South_W', 'broad', [(-24, -64), (26, -64), (26, -34), (8, -34), (8, -44), (-24, -44)], 8.4, (0.85, 1.2), 1.5),
    ('South_W2', 'light', [(9.5, -33), (26.5, -33), (26.5, -25.5), (20, -24.6), (14, -22.0), (10.5, -19.5)], 6.0, (0.7, 0.95), 1.2),
    ('South_E', 'broad', [(44, -64), (58, -64), (58, -36), (44, -36)], 8.4, (0.85, 1.2), 1.5),
    ('Axis_S', 'light', [(26, -64), (44, -64), (44, -50), (26, -50)], 9.0, (0.9, 1.1), 1.5),
]
SPECIMENS = [('willow', (-16.5, -15.0), 1.15, 0.6), ('light', (16.5, -21.6), 0.95, 2.1), ('willow', (-8.0, 22.5), 1.05, 4.0),
             ('willow', (-24.5, 18.0), 1.0, 5.0)]
for (c, rot, sz) in PLANTERS:
    SPECIMENS.append(('small', c, 1.0, random.uniform(0, 6.28)))

def zone_fn(poly, clear):
    def f(p):
        if not inside_poly(p, poly):
            return False
        return free(p, clear)
    return f

trees = []
existing = [s[1] for s in SPECIMENS]
for k, (name, sp, poly, spacing, srange, clear) in enumerate(ZONES):
    xsP = [p[0] for p in poly]; ysP = [p[1] for p in poly]
    pts = poisson(zone_fn(poly, clear), (min(xsP), min(ysP), max(xsP), max(ysP)), spacing, existing=existing, seed=100 + k)
    for p in pts:
        spp = sp
        if sp.startswith('mix:'):
            opts = [(a.split('=')[0], float(a.split('=')[1])) for a in sp[4:].split(',')]
            t = random.random(); acc = 0.0
            for nm, w in opts:
                acc += w
                if t <= acc:
                    spp = nm
                    break
        trees.append((spp, round(p[0], 2), round(p[1], 2), round(random.uniform(*srange), 3), round(random.uniform(0, 6.283), 3)))
    existing += pts
for sp, c, s, r in SPECIMENS:
    trees.append((sp, c[0], c[1], s, r))

# keep crowns clear of the eaves: push trees out from the buildings' eave outlines (raised rect + 1.6 m)
# crown radius = measured horizontal extent of the widest template of each kind (foliage points + branchlet size)
CROWN_R = {'willow': 6.1, 'broad': 6.9, 'purple': 4.35, 'light': 5.15, 'small': 2.15}
EAVE = [(r[0] - 1.6, r[1] - 1.6, r[2] + 1.6, r[3] + 1.6) for (r, l, n) in LY.RAISED]
moved = []
for k, (sp, x, y, s_, rot) in enumerate(trees):
    if sp == 'small':
        continue
    R = CROWN_R[sp] * s_
    for _ in range(6):
        worst = None
        for (x0, y0, x1, y1) in EAVE:
            dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
            d = math.hypot(dx, dy)
            if d < R and (worst is None or d < worst[0]):
                cxr = min(max(x, x0), x1); cyr = min(max(y, y0), y1)
                worst = (d, cxr, cyr)
        if worst is None:
            break
        d, cxr, cyr = worst
        vx, vy = x - cxr, y - cyr
        L = math.hypot(vx, vy) or 1.0
        step = R - d + 0.3
        x, y = x + vx / L * step, y + vy / L * step
    if (x, y) != (trees[k][1], trees[k][2]):
        if free((x, y), 1.2):
            moved.append((sp, round(x - trees[k][1], 2), round(y - trees[k][2], 2)))
            trees[k] = (sp, round(x, 2), round(y, 2), s_, rot)
        else:
            moved.append((sp, 'dropped'))
            trees[k] = None
trees = [t for t in trees if t is not None]
print('trees moved off eaves', moved)

# far ring (simplified trees closing the horizon), outside the detailed grid
far = []
r = random.Random(5)
for k in range(5000):
    a = r.uniform(0, 2 * math.pi); d = r.uniform(108, 240)
    x = 30 + math.cos(a) * d * 1.05; y = 22 + math.sin(a) * d * 0.95
    if X0 + 2 < x < X1 - 2 and Y0 + 2 < y < Y1 - 2:
        continue
    if any((x - q[0]) ** 2 + (y - q[1]) ** 2 < 9.0 ** 2 for q in far):
        continue
    far.append((x, y))
far_trees = [('far_' + r.choice(['broad', 'broad', 'willow', 'light']), round(x, 1), round(y, 1), round(r.uniform(0.9, 1.35), 3),
              round(r.uniform(0, 6.283), 3)) for (x, y) in far]

# canopy mask -> ground material
canopy = np.zeros((NY, NX), bool)
CROWN = {'willow': 6.0, 'broad': 5.8, 'purple': 3.6, 'light': 4.4, 'small': 1.6}
for (sp, x, y, s, rot) in trees:
    rr = CROWN.get(sp, 4.0) * s * 0.9
    canopy |= circle_mask((x, y), rr)

# ---- ground materials (codes): 0 lawn, 1 forest floor, 2 bare soil, 3 planting bed, 4 water bed
MAT = np.zeros((NY, NX), np.uint8)
MAT[canopy] = 1
# east yard: lawn with bare patches
yard = poly_mask([(84, -3), (97, -3), (97, 36), (84, 36)])
bare = yard & (noise > 0.62)
MAT[bare] = 2
MAT[water | (dwat < 0.8)] = 4
bankbed = (~water) & (dwat < 2.6) & (~paved) & (dpav > 0.3)
MAT[bankbed] = 3
MAT[paved] = 0

# ------------------------------------------------------------------ smaller plants
def scatter(mask, density, seed, jitter=1.0, min_d=None):
    rr = np.random.default_rng(seed)
    cnt = int(mask.sum() * RES * RES * density)
    jj, ii = np.nonzero(mask)
    if cnt == 0 or len(jj) == 0:
        return []
    pick = rr.integers(0, len(jj), cnt)
    out = []
    for q in pick:
        x = xs[ii[q]] + rr.uniform(-RES / 2, RES / 2); y = ys[jj[q]] + rr.uniform(-RES / 2, RES / 2)
        out.append((round(float(x), 2), round(float(y), 2), round(float(rr.uniform(0.75, 1.3)), 2), round(float(rr.uniform(0, 6.283)), 2)))
    if min_d:
        t = []
        for p in out:
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= min_d * min_d for q in t[-300:]):
                t.append(p)
        out = t
    return out

lotus_pts = scatter(lotus_zone, 2.3, 21)
bank_zone = bankbed & (dwat > 0.15) & (dwat < 2.4) & ~canopy
bank_pts = scatter(bank_zone, 2.2, 22)
# shrub masses: hedge ring at the sculpture plaza, edges of tree zones next to lawns / paths
cx, cy = SCULPT_PLAZA[0]
ang = np.degrees(np.arctan2(YY - cy, XX - cx))
rad = np.hypot(XX - cx, YY - cy)
hedge = (rad > 5.75) & (rad < 7.2) & (np.abs(ang) < 112)
edge_shrub = (~paved) & (~water) & canopy & (dpav > 0.6) & (dpav < 3.5) & (noise > 0.45)
planted_bank_s = poly_mask([(8.0, -16.5), (11.0, -19.0), (14.5, -21.0), (20.0, -24.4), (27.5, -25.4), (27.5, -33), (8.5, -33), (7.6, -20)]) & ~water & ~paved
shrub_pts = scatter(hedge, 3.2, 31) + scatter(edge_shrub, 0.22, 32, min_d=1.1) + scatter(planted_bank_s, 0.35, 33, min_d=1.0)
hedge_pts = scatter(hedge, 3.0, 34)
# rocks along the west bank of the main pond, the NW pond and the channel
shore = water & (din_w < 0.55)
rock_zone = shore & ((XX < -10) | (YY > 50)) & ~lotus_zone
rock_pts = scatter(rock_zone, 1.4, 41, min_d=0.55)
rock_land = (~water) & (dwat < 0.9) & (XX < -12) & (YY < 40) & (~paved)
rock_pts += scatter(rock_land, 0.6, 42, min_d=0.7)

# ------------------------------------------------------------------ write
def b64(a):
    return base64.b64encode(zlib.compress(a.tobytes(), 9)).decode('ascii')

grid_py = os.path.join(LIB, 'xy_env_grid.py')
# terrain at 0.5 m (vertex grid), heights in mm (int16); smooth material weights (uint8) per vertex
G = 2
H2 = cv2.resize(H, (NX // G, NY // G), interpolation=cv2.INTER_AREA)
def wmap(code_mask, blur):
    w = cv2.resize(code_mask.astype(np.float32), (NX // G, NY // G), interpolation=cv2.INTER_AREA)
    return np.clip(cv2.GaussianBlur(w, (0, 0), blur) * 255, 0, 255).astype(np.uint8)
W_FOREST = wmap(MAT == 1, 2.2)
W_BARE = wmap(MAT == 2, 1.2)
W_BANK = wmap(MAT == 3, 1.0)
W_MUD = wmap(MAT == 4, 0.8)
WATER2 = cv2.resize(water.astype(np.uint8), (NX // G, NY // G), interpolation=cv2.INTER_NEAREST)
PAVED2 = cv2.resize(paved.astype(np.uint8), (NX // G, NY // G), interpolation=cv2.INTER_NEAREST)
with open(grid_py, 'w', encoding='utf-8') as f:
    f.write('# Generated by xingyuan/env/make_env.py - terrain grid (do not edit by hand)\n')
    f.write('GX0, GY1, GRES, GNX, GNY = %r, %r, %r, %r, %r\n' % (X0, Y1, RES * G, NX // G, NY // G))
    f.write('H_MM_B64 = %r\n' % b64(np.round(H2 * 1000).astype(np.int16)))
    for nm, arr in (('W_FOREST', W_FOREST), ('W_BARE', W_BARE), ('W_BANK', W_BANK), ('W_MUD', W_MUD),
                    ('WATER', WATER2), ('PAVED', PAVED2)):
        f.write('%s_B64 = %r\n' % (nm, b64(arr.astype(np.uint8))))

data = dict(WL=WL, ZG=ZG, ZP=ZP, RAIL=RAIL, RED_TERRACE=RED_TERRACE, CRAZY=CRAZY, GRAY_PLAZA=GRAY_PLAZA,
            SCULPT_PLAZA=SCULPT_PLAZA, SW_PLAZA=SW_PLAZA, PINK_PATH=PINK_PATH, PINK_W=PINK_W, SLAB_BRIDGE=SLAB_BRIDGE,
            GRAY_PATH_N=GRAY_PATH_N, GRAY_N_W=GRAY_N_W, EAST_PATH=EAST_PATH, EAST_W=EAST_W, POND_MAIN=POND_MAIN,
            POND_N=POND_N, CHANNEL_NW=CHANNEL_NW, FOUNTAINS=FOUNTAINS, STONES=STONES, FRAMES=FRAMES, LAMPS=LAMPS,
            SCULPTURE=SCULPTURE, PLANTERS=PLANTERS, LAWN_PLANTER=LAWN_PLANTER, BENCHES=BENCHES,
            TREES=trees, FAR_TREES=far_trees, LOTUS=lotus_pts, BANK=bank_pts, SHRUBS=shrub_pts, HEDGE=hedge_pts,
            ROCKS=rock_pts)
with open(os.path.join(LIB, 'xy_env_data.py'), 'w', encoding='utf-8') as f:
    f.write('# Generated by xingyuan/env/make_env.py - environment shapes and placements (plan metres)\n')
    for k, v in data.items():
        f.write('%s = %s\n' % (k, json.dumps(v)))

from collections import Counter
print('grid', NX, NY, 'trees', len(trees), Counter(t[0] for t in trees), 'far', len(far_trees))
print('lotus', len(lotus_pts), 'bank', len(bank_pts), 'shrubs', len(shrub_pts), 'hedge', len(hedge_pts), 'rocks', len(rock_pts))
print('water m2 %.0f, lotus m2 %.0f, lawn cells %.0f m2' % (water.sum() * RES * RES, lotus_zone.sum() * RES * RES,
      ((MAT == 0) & ~paved & ~water).sum() * RES * RES))
print('H range', float(H.min()), float(H.max()))

# preview image
prev = np.zeros((NY, NX, 3), np.uint8)
prev[:] = (60, 140, 60)
prev[MAT == 1] = (35, 85, 35)
prev[MAT == 2] = (120, 100, 70)
prev[MAT == 3] = (70, 110, 50)
prev[water] = (60, 90, 140)
prev[lotus_zone] = (80, 150, 100)
prev[paved] = (190, 190, 185)
prev[red] = (190, 120, 110)
prev[pink & ~apron] = (210, 160, 160)
prev[complex_core] = (110, 110, 110)
for (sp, x, y, s, rot) in trees:
    col = {'willow': (170, 220, 120), 'broad': (20, 60, 20), 'purple': (120, 30, 70), 'light': (200, 230, 90), 'small': (240, 240, 0)}[sp]
    j, i = cell(x, y)
    cv2.circle(prev, (i, j), max(2, int(CROWN[sp] * s * 0.9 / RES)), col, 2)
cv2.imwrite(os.path.join(HERE, 'env_preview.png'), cv2.cvtColor(cv2.resize(prev, (NX // 2, NY // 2)), cv2.COLOR_RGB2BGR))
