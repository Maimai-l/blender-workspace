"""The Warden - final robot design (refined from concept A).

A hunched furnace giant, ~21 m tall standing, with a curved shrine-roof
carapace on its back (two halves that swing open over the engine bells),
a small domed head under a heavy V brow, two lamp eyes with lid shutters,
a furnace door with louvres on the chest, layered shoulder domes, barrel
forearms, three-finger mitts, a skirt of tassets and short elephant legs.

Local frames: X = robot's right, Y = forward, Z = up. Every part is modelled
around its pivot. Materials: PAINT (vermilion lacquer), ROOF (verdigris),
METAL (dark iron), BRASS, LENS, GLOW, LIDS, DARK.
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
import numpy as np
from r3d import (sd_sphere, sd_ellipsoid, sd_box, sd_capsule, sd_round_cone, sd_cyl,
                 sd_torus, U, SU, SUB, SSUB, INT, SINT, CHAMF, rot_matrix)
import rig as R
from rig import Rig, Part

PAINT, METAL, LENS, GLOW, MOSS, WOOD, CABLE, DARK, LIDS, SOIL = R.PAINT, R.METAL, R.LENS, R.GLOW, R.MOSS, R.WOOD, R.CABLE, R.DARK, R.LIDS, R.SOIL
ROOF, BRASS = 11, 12

VERSION = '12'


def _len2(x, y):
    return np.sqrt(x * x + y * y)


# ----------------------------------------------------------------------------
# part SDFs (local coordinates around each pivot)
# ----------------------------------------------------------------------------

def sdf_pelvis(p):
    hip = sd_box(p, (0, 0, 0.2), (2.3, 1.75, 1.05), r=0.55)
    # tassets: front, sides, back (thick armour plates hanging like a skirt)
    front = sd_box(p, (0, 1.72, -0.75), (1.35, 0.26, 1.15), r=0.22, R=rot_matrix(-10, 0, 0))
    sideR = sd_box(p, (2.35, 0.25, -0.65), (0.26, 1.45, 1.1), r=0.22, R=rot_matrix(0, 14, 0))
    sideL = sd_box(p, (-2.35, 0.25, -0.65), (0.26, 1.45, 1.1), r=0.22, R=rot_matrix(0, -14, 0))
    back = sd_box(p, (0, -1.75, -0.6), (1.5, 0.26, 1.05), r=0.22, R=rot_matrix(10, 0, 0))
    return U(hip, front, sideR, sideL, back)


def sdf_torso(p):
    belly = sd_round_cone(p, (0, 0.25, 0.3), (0, 0.45, 3.7), 2.35, 3.55)
    chest = sd_ellipsoid(p, (0, 0.35, 5.0), (4.0, 3.15, 3.15))
    d = SU(belly, chest, 0.9)
    # chest armour plate (the furnace door housing), slightly proud of the body
    door = sd_box(p, (0, 3.18, 4.45), (1.95, 0.42, 1.75), r=0.42)
    d = SU(d, door, 0.18)
    # louvre window recessed into the door
    win = sd_box(p, (0, 3.75, 4.35), (1.32, 0.55, 1.12), r=0.16)
    d = SUB(d, win)
    # neck collar
    collar = sd_torus(p, (0, 1.0, 7.55), 1.62, 0.5, rot_matrix(-14, 0, 0))
    d = SU(d, collar, 0.35)
    # engine housing on the back (under the roof)
    house = sd_box(p, (0, -2.35, 5.35), (2.55, 1.45, 2.05), r=0.6)
    d = SU(d, house, 0.5)
    spine = sd_box(p, (0, -2.3, 8.2), (0.75, 1.5, 1.7), r=0.4)
    d = SU(d, spine, 0.4)
    # belt band at the waist
    belt = sd_cyl(p, (0, 0.3, 0.55), (0, 0.3, 1.25), 2.62, 0.18)
    d = SU(d, belt, 0.08)
    return d


def sdf_core(p):
    return sd_box(p, (0, 3.42, 4.35), (1.2, 0.14, 1.0), r=0.1)


def sdf_grille(p):
    slats = U(*[sd_box(p, (0, 3.62, 3.55 + i * 0.4), (1.3, 0.07, 0.15), r=0.04, R=rot_matrix(28, 0, 0))
                for i in range(5)])
    frame = SUB(sd_box(p, (0, 3.6, 4.35), (1.36, 0.1, 1.16), r=0.12), sd_box(p, (0, 3.6, 4.35), (1.24, 0.3, 1.04), r=0.08))
    return U(slats, frame)


ROOF_PIVOT = (0.0, -2.0, 9.9)   # ridge hinge, torso coordinates


def _ridge_z(y):
    """Ridge height along the spine: a hood peak behind the head, sweeping down the back."""
    t = np.clip((-0.1 - y) / 4.9, 0.0, 1.0)          # 0 at the front edge, 1 at the back
    return 10.55 - 3.0 * t ** 1.6


def _roof_z(x, y):
    ax = np.abs(x)
    z = _ridge_z(y) - 0.78 * ax + 0.085 * ax * ax
    # corners curl up a little more at the eave ends (front and back)
    t = np.clip((-0.1 - y) / 4.9, 0.0, 1.0)
    curl = (np.maximum(ax - 3.8, 0.0) ** 2) * 0.12 * (1.0 + 0.8 * np.abs(2 * t - 1))
    return z + curl


def sdf_roof_half(p):
    """Right half of the roof carapace; local origin = ROOF_PIVOT on the ridge."""
    x = p[..., 0]
    y = p[..., 1] + ROOF_PIVOT[1]
    z = p[..., 2] + ROOF_PIVOT[2]
    zr = _roof_z(x, y)
    shell = np.abs(z - zr + 0.12) - 0.3
    span_x = np.maximum(-x, x - 5.9)
    span_y = np.abs(y + 2.55) - 2.45                 # y in [-5.0, -0.1]
    d = np.maximum(np.maximum(shell * 0.7, span_x), span_y)
    q = np.stack([x, y, z], -1)
    # eave beam all round the outer edge (polyline of capsules), and the ridge cap
    ys = np.linspace(-4.95, -0.15, 9)
    pts = [(5.85, yy, float(_roof_z(5.85, yy)) - 0.12) for yy in ys]
    beams = [sd_capsule(q, pts[i], pts[i + 1], 0.34) for i in range(len(pts) - 1)]
    xs = np.linspace(0.0, 5.85, 7)
    for yy in (-0.15, -4.95):
        pf = [(xx, yy, float(_roof_z(xx, yy)) - 0.12) for xx in xs]
        beams += [sd_capsule(q, pf[i], pf[i + 1], 0.27) for i in range(len(pf) - 1)]
    rp = [(0.0, yy, float(_ridge_z(yy)) + 0.2) for yy in ys]
    beams += [sd_capsule(q, rp[i], rp[i + 1], 0.36) for i in range(len(rp) - 1)]
    d = U(d, *beams)
    return d.astype(np.float32)


def sdf_bells(p):
    out = []
    for s in (1, -1):
        a = (1.25 * s, -3.45, 5.5); b = (1.4 * s, -3.75, 3.55)       # pointing almost straight down
        outer = sd_round_cone(p, a, b, 0.55, 1.0)
        inner = sd_round_cone(p, (a[0], a[1] - 0.05, a[2] - 0.15), (b[0] * 1.01, b[1] - 0.1, b[2] - 0.22), 0.42, 0.88)
        bell = SUB(outer, inner)
        ring = sd_torus(p, (1.36 * s, -3.68, 4.0), 0.88, 0.09, rot_matrix(-10, 0, 0))
        out.append(U(bell, ring))
    return U(*out)


EYE_C = (0.74, 2.1, 1.1)    # right eye centre, head coordinates
EYE_R = 0.52


def sdf_head(p):
    dome = sd_ellipsoid(p, (0, 0.3, 1.5), (1.92, 1.82, 1.62))
    face = sd_box(p, (0, 1.25, 0.86), (1.52, 0.88, 1.08), r=0.62)
    d = SU(dome, face, 0.5)
    # heavy V brow: two plates meeting low in the middle
    # heavy, level brow whose outer ends dip a little (old and gentle, not angry)
    browR = sd_box(p, (0.98, 1.9, 1.86), (1.12, 0.8, 0.33), r=0.25, R=rot_matrix(-8, 0, -4) @ rot_matrix(0, 7, 0))
    browL = sd_box(p, (-0.98, 1.9, 1.86), (1.12, 0.8, 0.33), r=0.25, R=rot_matrix(-8, 0, 4) @ rot_matrix(0, -7, 0))
    d = SU(d, U(browR, browL), 0.18)
    # deep round eye sockets
    ex, ey, ez = EYE_C
    sockets = U(sd_sphere(p, (ex, ey + 0.16, ez), 0.58), sd_sphere(p, (-ex, ey + 0.16, ez), 0.58))
    d = SSUB(d, sockets, 0.07)
    # snout with furnace-grille vents
    snout = sd_box(p, (0, 1.95, 0.36), (0.9, 0.48, 0.5), r=0.4)
    d = SU(d, snout, 0.3)
    # a framed furnace grille on the snout: a recess with four upright slats
    rec = sd_box(p, (0, 2.42, 0.34), (0.56, 0.2, 0.26), r=0.12)
    d = SUB(d, rec)
    slats = U(*[sd_box(p, (x, 2.3, 0.34), (0.045, 0.12, 0.25), r=0.02) for x in (-0.33, -0.11, 0.11, 0.33)])
    d = U(d, slats)
    # lamp-housing ears
    ears = U(sd_cyl(p, (1.62, 0.45, 1.2), (2.12, 0.45, 1.2), 0.66, 0.12),
             sd_cyl(p, (-1.62, 0.45, 1.2), (-2.12, 0.45, 1.2), 0.66, 0.12))
    d = SU(d, ears, 0.1)
    hatch = sd_cyl(p, (0, 0.25, 2.95), (0, 0.25, 3.3), 0.48, 0.09)
    d = SU(d, hatch, 0.14)
    return d


def sdf_earhubs(p):
    return U(sd_cyl(p, (2.08, 0.45, 1.2), (2.3, 0.45, 1.2), 0.36, 0.07),
             sd_cyl(p, (-2.08, 0.45, 1.2), (-2.3, 0.45, 1.2), 0.36, 0.07))


def sdf_eyes(p):
    ex, ey, ez = EYE_C
    return U(sd_sphere(p, (ex, ey, ez), EYE_R), sd_sphere(p, (-ex, ey, ez), EYE_R))


def sdf_lid(p):
    """Right eye lid shutter around the eye centre (local origin = eye centre).
    Rest (0): open, tucked under the brow. rx = -70: closed."""
    shell = SUB(sd_sphere(p, (0, 0, 0), 0.6), sd_sphere(p, (0, 0, 0), 0.535))
    cap = INT(shell, sd_plane_z(p, 0.06))
    front = INT(cap, -(p[..., 1] + 0.38))     # keep the front part (y > -0.38)
    return front


def sd_plane_z(p, z0):
    return z0 - p[..., 2]     # negative above z0


def sdf_upperarm(p):
    arm = sd_round_cone(p, (0, 0, -0.3), (0, 0, -3.85), 1.02, 0.9)
    sleeve = sd_cyl(p, (0, 0, -0.9), (0, 0, -2.2), 1.12, 0.1)
    return SU(arm, sleeve, 0.05)


def sdf_elbow(p):
    return sd_sphere(p, (0, 0, 0.0), 1.0)


def sdf_pauldron(p):
    dome = sd_ellipsoid(p, (0.45, 0.0, 0.5), (2.25, 2.45, 1.75))
    dome = SUB(dome, sd_box(p, (0.45, 0, -1.55), (3.0, 3.0, 1.3)))
    rim = sd_torus(p, (0.45, 0.0, -0.18), 2.05, 0.26)
    d = SU(dome, rim, 0.08)
    top = sd_ellipsoid(p, (0.55, -0.05, 1.05), (1.55, 1.75, 1.25))
    top = SUB(top, sd_box(p, (0.55, 0, 0.2), (3, 3, 0.55)))
    return U(d, top)


def sdf_forearm(p):
    a = sd_round_cone(p, (0, 0, -0.45), (0, 0.1, -4.3), 1.2, 1.58)
    b1 = sd_cyl(p, (0, 0.03, -1.35), (0, 0.03, -1.7), 1.4, 0.08)
    b2 = sd_cyl(p, (0, 0.07, -2.95), (0, 0.07, -3.3), 1.57, 0.08)
    cuff = sd_cyl(p, (0, 0.1, -4.15), (0, 0.1, -4.65), 1.75, 0.12)
    return SU(a, U(b1, b2, cuff), 0.04)


HAND_VERSION = '2'


def _finger(p, base, d1, d2, w):
    """A two-segment mechanical finger: capsule segments with a groove at the joint, a joint pin,
    and an armour plate on the back of each segment."""
    a = np.asarray(base, np.float32); b = a + np.asarray(d1, np.float32); c = b + np.asarray(d2, np.float32)
    seg1 = sd_capsule(p, a, a + (b - a) * 0.86, w)
    seg2 = sd_capsule(p, b + (c - b) * 0.14, c, w * 0.88)
    joint = sd_sphere(p, b, w * 0.7)
    d = U(seg1, seg2, joint)
    # plates on the back (-Y side) of each segment
    for p0, p1, ww in ((a, b, w), (b, c, w * 0.88)):
        mid = (p0 + p1) * 0.5 + np.array([0, -ww * 0.55, 0], np.float32)
        ln = float(np.linalg.norm(p1 - p0)) * 0.42
        plate = sd_box(p, tuple(mid), (ww * 1.02, ww * 0.42, ln), r=ww * 0.25)
        d = SU(d, plate, 0.05)
    return d


def sdf_hand(p):
    palm = sd_box(p, (0, 0.15, -0.85), (1.08, 0.8, 0.95), r=0.36)
    back = sd_box(p, (0, -0.55, -0.9), (0.95, 0.22, 0.78), r=0.15)      # an armour plate on the back of the hand
    knuck = sd_capsule(p, (-0.75, 0.5, -1.62), (0.75, 0.5, -1.62), 0.42)
    f1 = _finger(p, (0.66, 0.62, -1.78), (0.04, 0.24, -0.62), (0.02, 0.22, -0.52), 0.36)
    f2 = _finger(p, (0.0, 0.66, -1.82), (0.0, 0.25, -0.68), (0.0, 0.22, -0.56), 0.37)
    f3 = _finger(p, (-0.66, 0.6, -1.78), (-0.05, 0.22, -0.6), (-0.03, 0.2, -0.48), 0.34)
    th = _finger(p, (0.95, 0.42, -0.62), (0.26, 0.32, -0.44), (0.18, 0.26, -0.34), 0.34)
    d = SU(palm, knuck, 0.2)
    d = SU(d, back, 0.08)
    d = U(d, f1, f2, f3)
    return SU(d, th, 0.12)


def mat_hand(o, m):
    # the back of the hand and the finger plates carry the body's paint; joints and palm stay iron
    out = m.copy()
    out[o[:, 1] < 0.18] = PAINT
    return out


def panel_hand(o):
    # segment lines across the fingers and the back plate outline
    seg = np.digitize(o[:, 2], [-2.36, -2.0, -1.55]).astype(np.int32)
    return seg + (o[:, 1] < -0.33).astype(np.int32) * 10


def sdf_thigh(p):
    a = sd_round_cone(p, (0, 0, 0), (0, 0.1, -2.9), 1.32, 1.2)
    plate = sd_box(p, (0, 0.85, -1.35), (1.0, 0.5, 1.3), r=0.35)
    return SU(a, plate, 0.25)


def sdf_shin(p):
    knee = sd_ellipsoid(p, (0, 0.95, 0.05), (1.02, 0.78, 0.98))
    a = sd_round_cone(p, (0, 0, -0.2), (0, -0.05, -2.75), 1.18, 1.62)
    ridge = sd_box(p, (0, 0.95, -1.6), (0.62, 0.55, 1.35), r=0.4)
    d = SU(SU(a, ridge, 0.4), knee, 0.15)
    hem = sd_cyl(p, (0, -0.05, -2.75), (0, -0.05, -3.05), 1.72, 0.1)
    return SU(d, hem, 0.05)


def sdf_foot(p):
    a = sd_box(p, (0, 0.6, -0.72), (1.55, 1.95, 0.62), r=0.42)
    heel = sd_ellipsoid(p, (0, -0.35, -0.42), (1.35, 1.15, 0.8))
    toes = U(*[sd_box(p, (x, 2.55, -0.98), (0.44, 0.55, 0.38), r=0.26) for x in (-0.95, 0.0, 0.95)])
    return U(SU(a, heel, 0.4), toes)


def sdf_anklejoint(p):
    return sd_sphere(p, (0, 0, 0), 1.05)


# ----------------------------------------------------------------------------
# rig
# ----------------------------------------------------------------------------

def build(voxel=0.06, head_voxel=0.03):
    r = Rig('warden')
    v, hv = voxel, head_voxel
    r.add(Part('pelvis', None, (0, 0, 8.45), sdf_pelvis, (-3.0, -2.4, -2.2), (3.0, 2.4, 1.4), v, PAINT, version=VERSION))
    r.add(Part('torso', 'pelvis', (0, 0, 0.9), sdf_torso, (-4.4, -4.2, -0.3), (4.4, 4.2, 10.1), v, PAINT, version=VERSION))
    r.add(Part('core', 'torso', (0, 0, 0), sdf_core, (-1.4, 3.1, 3.2), (1.4, 3.7, 5.5), v * 0.5, GLOW, version=VERSION))
    r.add(Part('grille', 'torso', (0, 0, 0), sdf_grille, (-1.6, 3.3, 3.0), (1.6, 3.9, 5.7), v * 0.4, METAL, version=VERSION))
    r.add(Part('bells', 'torso', (0, 0, 0), sdf_bells, (-3.0, -6.0, 2.0), (3.0, -2.8, 6.2), v, METAL, version=VERSION))
    r.add_pair('roof', 'torso', ROOF_PIVOT, sdf_roof_half, (-0.5, -3.4, -4.2), (6.4, 2.3, 1.4), v * 0.8, ROOF, version=VERSION)
    r.add(Part('head', 'torso', (0, 1.2, 7.35), sdf_head, (-2.5, -1.7, -0.6), (2.5, 3.0, 3.5), hv, PAINT, version=VERSION))
    r.add(Part('earhubs', 'head', (0, 0, 0), sdf_earhubs, (-2.5, -0.1, 0.6), (2.5, 1.0, 1.8), hv, BRASS, version=VERSION))
    r.add(Part('eyes', 'head', (0, 0, 0), sdf_eyes, (-1.3, 1.4, 0.6), (1.3, 2.6, 1.8), hv * 0.6, LENS, version=VERSION))
    r.add_pair('lid', 'head', EYE_C, sdf_lid, (-0.7, -0.7, -0.7), (0.7, 0.7, 0.7), hv * 0.5, LIDS, version=VERSION)
    r.add_pair('upperarm', 'torso', (3.85, 0.35, 6.55), sdf_upperarm, (-1.4, -1.4, -4.5), (1.4, 1.4, 0.8), v, METAL, version=VERSION)
    r.add_pair('pauldron', 'upperarm_R', (0.15, 0, 0.35), sdf_pauldron, (-2.0, -2.8, -0.8), (3.0, 2.8, 2.6), v, PAINT, version=VERSION)
    r.add_pair('elbow', 'upperarm_R', (0, 0, -4.2), sdf_elbow, (-1.2, -1.2, -1.2), (1.2, 1.2, 1.2), v, METAL, version=VERSION)
    r.add_pair('forearm', 'upperarm_R', (0, 0, -4.2), sdf_forearm, (-2.0, -2.0, -5.0), (2.0, 2.0, 0.9), v, PAINT, version=VERSION)
    r.add_pair('hand', 'forearm_R', (0, 0.1, -4.75), sdf_hand, (-1.6, -1.1, -3.6), (2.0, 1.8, 0.3), v * 0.7, METAL, version=VERSION + HAND_VERSION)
    r.add_pair('thigh', 'pelvis', (1.62, 0, -0.65), sdf_thigh, (-1.7, -1.7, -3.5), (1.7, 1.7, 1.5), v, PAINT, version=VERSION)
    r.add_pair('shin', 'thigh_R', (0, 0.1, -3.05), sdf_shin, (-2.0, -2.0, -3.3), (2.0, 2.0, 1.3), v, PAINT, version=VERSION)
    r.add_pair('ankle', 'shin_R', (0, -0.05, -3.0), sdf_anklejoint, (-1.2, -1.2, -1.2), (1.2, 1.2, 1.2), v, METAL, version=VERSION)
    r.add_pair('foot', 'shin_R', (0, -0.05, -3.0), sdf_foot, (-1.9, -1.8, -1.5), (1.9, 3.3, 0.6), v, PAINT, version=VERSION)
    return r


# ----------------------------------------------------------------------------
# palette (dawn key light) and poses
# ----------------------------------------------------------------------------

def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


PALETTE = {
    PAINT: (hexc('c9644a'), hexc('7d3c4c')),      # vermilion lacquer / violet-red shade
    ROOF: (hexc('6fa39a'), hexc('3c5e6c')),       # verdigris copper / blue shade
    METAL: (hexc('6c6762'), hexc('3a3644')),      # dark iron
    BRASS: (hexc('c9a160'), hexc('7a5a48')),
    LENS: (hexc('3f4650'), hexc('262a36')),       # dormant glass (overridden when lit)
    GLOW: (hexc('ffdc8c'), hexc('ffdc8c')),
    LIDS: (hexc('c9644a'), hexc('7d3c4c')),
    DARK: (hexc('3a2e36'), hexc('241c26')),
}

STAND = {'torso': (-12, 0, 0), 'head': (10, 0, 0), 'upperarm_R': (6, 10, 0), 'forearm_R': (12, 0, 0),
         'thigh_R': (0, 3, 0), 'lid_R': (-25, 10, 0)}

KNEEL = {'_root': None,
         'thigh_R': (6, 0, 0), 'shin_R': (-100, 0, 0), 'foot_R': (45, 0, 0),
         'thigh_L': (80, 5, 0), 'shin_L': (-84, 0, 0), 'foot_L': (4, 0, 0),
         'torso': (-26, 0, 0), 'head': (-32, 0, 0),
         'upperarm_R': (14, 8, 0), 'forearm_R': (8, 0, 0), 'hand_R': (20, 0, 0),
         'upperarm_L': (44, -2, 0), 'forearm_L': (52, 0, 0), 'hand_L': (10, 0, 0),
         'lid_R': (-62, 0, 0)}


# ----------------------------------------------------------------------------
# per-pixel material / panel functions (part-space positions -> ids)
# ----------------------------------------------------------------------------

def mat_head(o, m):
    ex, ey, ez = EYE_C
    out = m.copy()
    for sx in (1, -1):
        d = np.sqrt((o[:, 0] - sx * ex) ** 2 + (o[:, 1] - (ey + 0.16)) ** 2 + (o[:, 2] - ez) ** 2)
        out[(d < 0.62) & (o[:, 1] < ey + 0.12)] = DARK
    # the grille recess (not the slats) is dark
    inrec = (np.abs(o[:, 0]) < 0.55) & (np.abs(o[:, 2] - 0.34) < 0.25) & (o[:, 1] > 2.1) & (o[:, 1] < 2.405)
    slat = np.min(np.abs(o[:, 0:1] - np.array([[-0.33, -0.11, 0.11, 0.33]])), axis=1) < 0.05
    out[inrec & ~slat] = DARK
    return out


def mat_torso(o, m):
    out = m.copy()
    win = (np.abs(o[:, 0]) < 1.3) & (o[:, 2] > 3.25) & (o[:, 2] < 5.45) & (o[:, 1] > 3.0) & (o[:, 1] < 3.62)
    out[win] = DARK
    return out


def panel_torso(o):
    x, y, z = o[:, 0], o[:, 1], o[:, 2]
    band = np.digitize(z, [1.3, 2.6, 6.55])
    door = (np.abs(x) < 1.92) & (z > 2.75) & (z < 6.15) & (y > 2.6)
    side = (x > 0).astype(np.int32)
    back = (y < -1.0) & (z > 3.4)
    # riveted armour plates: the flanks are separate plates in two rows, the back plate splits down the spine
    mid = (z > 2.6) & (z < 6.55)
    flank = (np.abs(x) > 2.75) & mid & (y > -1.0)
    row = (z > 4.5) & mid & (flank | back)
    split = back & (x > 0)
    return (band + 4 * door + 8 * (side * (z < 2.6)) + 16 * back + 32 * (flank * (1 + side))
            + 96 * row + 192 * split).astype(np.int32)


def panel_head(o):
    # a helmet cap above the brow, split down the back of the skull
    x, y, z = o[:, 0], o[:, 1], o[:, 2]
    cap = z > 2.45
    back = (y < -0.3) & (x > 0) & (z > 0.9)
    return (cap.astype(np.int32) + 2 * back).astype(np.int32)


def panel_upperarm(o):
    return (o[:, 2] < -3.0).astype(np.int32)


def panel_roof(o):
    y = o[:, 1] + ROOF_PIVOT[1]
    x = o[:, 0]
    seam = np.floor((y + 5.2) / 0.82).astype(np.int32)
    outer = (np.abs(x) > 3.6).astype(np.int32)
    return seam * 2 + outer


def panel_pauldron(o):
    # three rings of plate; the lower ring is cut into four lames
    z = o[:, 2]
    ring = np.digitize(z, [0.15, 0.95]).astype(np.int32)
    sector = np.floor((np.arctan2(o[:, 1], o[:, 0] - 0.45) + np.pi) / (np.pi / 2)).astype(np.int32) % 4
    return ring + 3 * sector * (ring == 1)


def panel_shin(o):
    return (np.digitize(o[:, 2], [-1.25]).astype(np.int32) + (o[:, 1] > 0.55) * 10
            + ((o[:, 1] < -0.55) & (o[:, 0] > 0)) * 20)


def panel_thigh(o):
    return (o[:, 1] > 0.5).astype(np.int32) + 2 * (o[:, 2] < -1.9)


def panel_lid(o):
    # an eyelid crease across the shutter (reads as a closed eye, not a goggle)
    return (o[:, 2] > 0.33).astype(np.int32)


def panel_forearm(o):
    ang = np.arctan2(o[:, 0], o[:, 1])
    return (np.floor((ang + np.pi) / (2 * np.pi / 5))).astype(np.int32) * (o[:, 2] < -1.75) * (o[:, 2] > -2.9)


def style_fns(rig):
    """matfn / panelfn dicts keyed by part index for cel.render."""
    P = rig.parts
    mf = {P['head'].index: mat_head, P['torso'].index: mat_torso,
          P['hand_R'].index: mat_hand, P['hand_L'].index: mat_hand}
    pf = {P['torso'].index: panel_torso, P['head'].index: panel_head}
    for side in ('R', 'L'):
        pf[P['upperarm_' + side].index] = panel_upperarm
        pf[P['roof_' + side].index] = panel_roof
        pf[P['pauldron_' + side].index] = panel_pauldron
        pf[P['shin_' + side].index] = panel_shin
        pf[P['thigh_' + side].index] = panel_thigh
        pf[P['forearm_' + side].index] = panel_forearm
        pf[P['lid_' + side].index] = panel_lid
        pf[P['hand_' + side].index] = panel_hand
    return mf, pf


# ----------------------------------------------------------------------------
# eyes: designed cel eyes evaluated in head space (works from every angle)
# ----------------------------------------------------------------------------

EYE_DORMANT = (hexc('3b4250'), hexc('252935'))


def eye_colour(o, glow, lit):
    """Colour LENS pixels. o: head-space positions (n,3); glow 0..1; lit bool (n,)."""
    ex, ey, ez = EYE_C
    sx = np.sign(o[:, 0])
    dx = o[:, 0] - sx * ex
    dz = o[:, 2] - ez
    r = np.sqrt(dx * dx + dz * dz) / EYE_R          # 0 centre .. 1 rim (seen from the front)
    n = len(o)
    out = np.zeros((n, 3), np.float32)
    # dormant glass: dark blue-grey with a cool shade band at the bottom
    base = np.where(lit[:, None], EYE_DORMANT[0], EYE_DORMANT[1])
    out[:] = base
    # reflected sky crescent (upper-left) on dormant glass
    refl = (dz > 0.12) & (dx < -0.02) & (r < 0.8) & (r > 0.45)
    out[refl] = hexc('8d9cb0')
    if glow > 0.04:
        # a lamp warming up: ember red -> orange -> white-gold, never a blend with the dark glass
        g = float(np.clip(glow, 0, 1))
        e_rim, e_mid, e_core = hexc('6e2a22'), hexc('a9442a'), hexc('d9702f')
        b_rim, b_mid, b_core = hexc('e08436'), hexc('ffb552'), hexc('fff3c8')
        rim = e_rim * (1 - g) + b_rim * g; mid = e_mid * (1 - g) + b_mid * g; core = e_core * (1 - g) + b_core * g
        col = np.where((r < 0.36)[:, None], core, np.where((r < 0.7)[:, None], mid, rim))
        out = col.astype(np.float32)
    return out.astype(np.float32)
