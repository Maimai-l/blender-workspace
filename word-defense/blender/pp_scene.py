# pp_scene.py - Word Defense pop-up book spread (scene prototype). Runs inside WD_Popup.blend and rebuilds it.
# The book is open at 90 degrees: the floor page is the battlefield, the back page is the sky.
# Enemies come out of a tear in the back page and walk the path down to the castle at the front right.
import sys, importlib, math, random
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import pp_lib; importlib.reload(pp_lib)
import pp_shapes; importlib.reload(pp_shapes)
import pp_castle; importlib.reload(pp_castle)
from pp_lib import *
from pp_shapes import *
import bpy
import numpy as np
from mathutils import Vector, Matrix

assert bpy.data.filepath.replace('\\', '/').endswith('/popup/WD_Popup.blend'), "open WD_Popup.blend first"
wipe()
scn = bpy.context.scene

# ------------------------------------------------------------------ layout (metres; Z up, the reader at -Y)
HW = 8.2          # half width of the pages
D = 10.4          # depth of the floor page, front edge y=0 to the back page's printed face
RG = 0.35         # gutter radius where the two pages bend into the spine
H = 9.0           # height of the back page
TX, TZ = -0.9, RG + 0.02     # the tear: centre x, bottom z
NSHEET = 9        # sheets visible inside the tear

PATH = [(-0.9, 9.98), (-0.88, 9.45), (-0.8, 9.0), (0.2, 8.74), (2.6, 8.64), (4.9, 8.47), (6.05, 7.97), (6.15, 7.15), (5.2, 6.56),
        (2.8, 6.32), (-0.2, 6.22), (-3.2, 6.07), (-5.5, 5.77), (-6.45, 5.07), (-6.2, 4.22), (-4.9, 3.77), (-2.4, 3.64),
        (0.2, 3.52), (1.6, 3.25), (2.3, 2.62), (2.75, 2.27), (3.1, 2.16)]
CASTLE = (5.6, 2.15)
MOAT = (CASTLE[0], CASTLE[1], 2.45, 1.75, 0.26)          # cx, cy, rx, ry, half width
RIVER = [(6.7, 9.55), (7.05, 8.45), (7.2, 7.05), (7.0, 5.65), (7.25, 4.6), (7.1, 3.75)]
PATHS = catmull(PATH, 10)
RIVS = catmull(RIVER, 10)

C = {k: coll(k) for k in ("Book", "Backdrop", "Floor", "Rows", "Castle", "Lights", "Rig")}

# ------------------------------------------------------------------ palette and materials
# depth reads as value and temperature: dark saturated indigo in front, light warm lavender at the back
M = {}
M['sky'] = sky('P_Sky', [(0.0, '#EDBB9C'), (0.17, '#CC9DAA'), (0.42, '#8273AE'), (0.74, '#424689'), (1.0, '#262B5D')],
               RG, 5.0, '#9A8AC4', emit=0.2)
M['mtn_far'] = washi('P_MtnFar', '#A39BCB', '#B1A6D2', haze='#E7BDAF', haze_h=2.2, haze_amt=0.45, transl=0.05, mscale=0.35)
M['mtn_near'] = washi('P_MtnNear', '#8580BA', '#918AC1', haze='#DDB2B0', haze_h=1.8, haze_amt=0.4, transl=0.05, mscale=0.35)
M['moon'] = washi('P_Moon', '#F7E4B4', '#C5ACCF', mscale=3.0, transl=0.0, emit='#F8E3B2', emit_strength=0.8, mottle=1.0,
                  grad='#E39A5E', grad_z=(3.35, 4.5), grad_amt=0.72)
M['star'] = washi('P_Star', '#F0D38E', '#F6DDA0', transl=0.0, emit='#F3D690', emit_strength=0.7)
M['reed'] = washi('P_Reed', '#2C3C70', '#36487A', mscale=0.9, haze='#6E7AA8', haze_h=0.5, haze_amt=0.3)
M['lily'] = washi('P_Lily', '#3B6A84', '#4A7B90', transl=0.0, spec=0.1, sheen=0.0)
M['foam'] = washi('P_Foam', '#E9F0FB', '#FFFFFF', transl=0.3, emit='#E9F0FB', emit_strength=0.2)
M['cloud'] = washi('P_Cloud', '#8B86BC', '#9890C3', grad='#ECBDA8', grad_z=(-0.05, 0.42), grad_amt=0.6, transl=0.08)
M['row4b'] = washi('P_Row4Back', '#7C78B5', '#9089C1', mscale=0.9, haze='#E4BCBA', haze_h=1.5, haze_amt=0.62)
M['row4'] = washi('P_Row4', '#6A69AA', '#7C77B6', mscale=0.9, haze='#D9B2B9', haze_h=1.35, haze_amt=0.58)
M['row3b'] = washi('P_Row3Back', '#5A5EA2', '#6B6BAC', mscale=0.9, haze='#C7A9C4', haze_h=1.15, haze_amt=0.55)
M['row3'] = washi('P_Row3', '#4B5398', '#5C60A3', mscale=0.9, haze='#B19CC2', haze_h=1.0, haze_amt=0.5)
M['row2b'] = washi('P_Row2Back', '#454F94', '#575C9E', mscale=0.9, haze='#9F90C0', haze_h=0.85, haze_amt=0.48)
M['row2'] = washi('P_Row2', '#38448A', '#4A5194', mscale=0.9, haze='#8F84BA', haze_h=0.75, haze_amt=0.42)
M['row1b'] = washi('P_Row1Back', '#34408A', '#444D90', mscale=0.9, haze='#8279B3', haze_h=0.65, haze_amt=0.38)
M['row1'] = washi('P_Row1', '#2B3679', '#3A4384', mscale=0.9, haze='#776FAC', haze_h=0.6, haze_amt=0.34)
M['wing'] = washi('P_Wing', '#232C66', '#323A72', mscale=0.9, haze='#6A63A2', haze_h=0.8, haze_amt=0.3)
M['floor'] = washi('P_Floor', '#3F4580', '#474C86', mscale=0.22, transl=0.0, mottle=0.9, spec=0.05, sheen=0.0,
                   wgrad=('#2A3270', 'Y', 0.0, 7.0, 0.55))
M['patch_l'] = washi('P_PatchLight', '#4D548E', '#565C94', mscale=0.3, transl=0.0, spec=0.05, sheen=0.0, wgrad=('#353E7C', 'Y', 0.0, 7.0, 0.5))
M['patch_d'] = washi('P_PatchDark', '#363C74', '#3D437A', mscale=0.3, transl=0.0, spec=0.05, sheen=0.0, wgrad=('#262E69', 'Y', 0.0, 7.0, 0.5))
M['path'] = washi('P_Path', '#C6BFDA', '#D2CAE1', mscale=0.6, transl=0.0, fiber=0.04, spec=0.08, sheen=0.05)
M['path_u'] = washi('P_PathUnder', '#8E89BA', '#9893BF', mscale=0.6, transl=0.0, spec=0.05, sheen=0.0)
M['print_a'] = washi('P_PrintGrass', '#58619D', '#5F68A2', transl=0.0, spec=0.05, sheen=0.0, wgrad=('#3C4683', 'Y', 0.0, 7.0, 0.5))
M['print_b'] = washi('P_PrintFlower', '#7D7BB6', '#8784BC', transl=0.0, spec=0.05, sheen=0.0)
M['print_c'] = washi('P_PrintFlowerWarm', '#B48FA6', '#BE99AE', transl=0.0, spec=0.05, sheen=0.0)
M['water'] = water('P_Water', '#4A70B6', '#6589CC', '#B8CFF0')
M['bank'] = washi('P_Bank', '#A9A6D0', '#B6B2D7', mscale=0.6, transl=0.0, spec=0.05, sheen=0.0)
M['sheet'] = washi('P_Sheet', '#E6DECD', '#D9D0BD', mscale=0.5, transl=0.1, rough=0.9)
M['tear'] = washi('P_TearEdge', '#F4EFE6', '#FFFFFF', mscale=1.0, transl=0.2, fiber=0.12)
M['flapback'] = washi('P_FlapBack', '#EAE4D8', '#DED7C9', mscale=0.8, transl=0.1, fiber=0.06)
M['rampback'] = washi('P_RampBack', '#B9B2C6', '#C4BDCF', mscale=0.8, transl=0.0, fiber=0.05)
M['edge'] = page_edges('P_PageEdge', '#E9E1CE', '#C3B8A1')
M['cover'] = cloth('P_Cover', '#1F2143', '#2D305C')
M['desk'] = wood('P_Desk', '#0A0706', '#16100C', rough=0.8, coat=0.0)
M['verge'] = washi('P_Verge', '#484F88', '#50568D', mscale=0.4, transl=0.0, wgrad=('#323B78', 'Y', 0.0, 7.0, 0.5))
M['lantern'] = glow('P_Lantern', '#FFB867', 7.0)
M['post'] = wood('P_Post', '#3B2A20', '#56402F')
M['dark'] = washi('P_DarkTrim', '#2E3163', '#363A6B', transl=0.0)
M['void'] = None

# ------------------------------------------------------------------ the book
def slab(name, x0, x1, y0, y1, z0, z1, mat, collection):
    mb = MB().box(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), (x1 - x0, y1 - y0, z1 - z0))
    return obj(name, mb, collection, [mat])

obj("FloorPage", MB().add([(-HW, 0, 0), (HW, 0, 0), (HW, D - RG, 0), (-HW, D - RG, 0)], [(0, 1, 2, 3)]), C['Book'], [M['floor']])
slab("FloorPages", -HW, HW, 0.0, D - RG, -0.30, -0.002, M['edge'], C['Book'])
slab("FloorCover", -HW - 0.22, HW + 0.22, -0.22, D + 0.42, -0.39, -0.30, M['cover'], C['Book'])
obj("Desk", MB().add([(-60, -50, -0.39), (60, -50, -0.39), (60, 60, -0.39), (-60, 60, -0.39)], [(0, 1, 2, 3)]), C['Book'], [M['desk']])

mb = MB()
prof = [(D - RG + RG * math.sin(a), RG - RG * math.cos(a)) for a in np.linspace(0, math.pi / 2, 10)]
for k in range(len(prof) - 1):
    (y0, z0), (y1, z1) = prof[k], prof[k + 1]
    mb.add([(-HW, y0, z0), (HW, y0, z0), (HW, y1, z1), (-HW, y1, z1)], [(0, 1, 2, 3)])
obj("Gutter", mb, C['Book'], [M['floor']])


def tear_fn(scale=1.0, seed=7):
    def fn(X, Y):
        cz = TZ + 1.15 * scale
        d = sd_ellipse(X, Y, TX, cz, 1.02 * scale, 1.2 * scale)
        d = smin(d, sd_box(X, Y, TX, TZ + 0.45 * scale, 0.86 * scale, 0.45 * scale), 0.25)
        d = d + 0.085 * scale * fbm(X * 1.7, Y * 1.7, seed, 3) + 0.03 * fbm(X * 6.5, Y * 6.5, seed + 9, 3) \
            + 0.011 * fbm(X * 28.0, Y * 28.0, seed + 21, 2)
        return d
    return fn


def sheet_fn(scale, seed):
    t = tear_fn(scale, seed)

    def fn(X, Y):
        rect = sd_box(X, Y, 0.0, (RG + H) / 2, HW, (H - RG) / 2)
        return np.maximum(rect, -t(X, Y))
    return fn


card("BackPage", sheet_fn(1.0, 7), (-HW, RG, HW, H), 0.03, C['Backdrop'], [M['sky'], M['flapback'], M['tear']],
     M=frame((0, D, 0), (1, 0, 0), (0, 0, 1)), t=0.02, shell=1, rim=2)
for k in range(1, NSHEET + 1):
    card("Sheet%02d" % k, sheet_fn(1.0 - 0.009 * k, 7 + k), (-HW, RG, HW, H), 0.03, C['Backdrop'], [M['sheet']],
         M=frame((0, D + k * 0.03, 0), (1, 0, 0), (0, 0, 1)), t=0.02)

def cover_fn(X, Y):
    rect = sd_box(X, Y, 0.0, (H + 0.2 - 0.39) / 2, HW + 0.22, (H + 0.2 + 0.39) / 2)
    return np.maximum(rect, -tear_fn(0.9, 30)(X, Y))
card("BackCover", cover_fn, (-HW - 0.22, -0.39, HW + 0.22, H + 0.2), 0.04, C['Book'], [M['cover']],
     M=frame((0, D + NSHEET * 0.03 + 0.04, 0), (1, 0, 0), (0, 0, 1)), t=0.09)

t0 = tear_fn(1.0, 7)
def rim_fn(X, Y):
    d = t0(X, Y)
    w = 0.035 + 0.03 * (fbm(X * 9.0, Y * 9.0, 77, 2) * 0.5 + 0.5) + 0.01 * fbm(X * 40, Y * 40, 78, 2)
    return np.maximum(-d, d - w)
card("TearRim", rim_fn, (TX - 1.5, TZ - 0.1, TX + 1.5, TZ + 2.8), 0.008, C['Backdrop'], [M['tear']],
     M=frame((0, D - 0.003, 0), (1, 0, 0), (0, 0, 1)), t=0.003)

# the torn flap that fell outward: a white tongue curling from the hole down onto the floor (the enemies' ramp)
def ramp_flap():
    rng = random.Random(5)
    prof = catmull([(D, TZ + 0.01), (D - 0.035, TZ * 0.62), (D - 0.1, 0.07), (D - 0.28, 0.016), (D - 0.6, 0.013)], 8)
    nt, nu = len(prof) - 1, 18
    mb = MB()
    jag_l = [rng.uniform(-0.05, 0.05) for _ in range(nt + 1)]
    jag_r = [rng.uniform(-0.05, 0.05) for _ in range(nt + 1)]
    tip = [rng.uniform(0.78, 1.0) for _ in range(nu + 1)]
    V, F = [], []
    for j in range(nu + 1):
        for i in range(nt + 1):
            s = i / nt * tip[j]
            k = s * nt
            i0 = min(int(k), nt - 1); f = k - i0
            y = prof[i0][0] + (prof[i0 + 1][0] - prof[i0][0]) * f
            z = prof[i0][1] + (prof[i0 + 1][1] - prof[i0][1]) * f
            w = 1.25 * (1.0 - 0.5 * s)
            u = j / nu - 0.5
            jag = jag_l[i] if j == 0 else (jag_r[i] if j == nu else 0.0)
            V.append((TX + u * w + jag + 0.04 * math.sin(7 * s), y, z + 0.004))
    for j in range(nu):
        for i in range(nt):
            a = j * (nt + 1) + i
            F.append((a, a + 1, a + nt + 2, a + nt + 1))
    mb.add(V, F)
    ob = obj("RampFlap", mb, C['Backdrop'], [M['rampback'], M['sky'], M['tear']])
    solidify(ob, 0.012, -1.0, 1, 2)
    return ob


# small torn pieces round the rim, bent out toward the reader
def tear_flaps():
    tf = tear_fn(1.0, 7)
    rim = max(shape_loops(tf, (TX - 1.6, TZ - 0.2, TX + 1.6, TZ + 3.0), 0.02), key=len)
    P = np.asarray(rim)
    ctr = P.mean(axis=0)
    out = []
    for k, (ang, L, w0, curl, seed) in enumerate(((172, 0.42, 0.42, 1.9, 1), (12, 0.36, 0.38, 1.7, 2), (118, 0.32, 0.34, 2.1, 3), (62, 0.3, 0.3, 1.5, 4))):
        a = math.radians(ang)
        dirs = P - ctr
        i = int(np.argmax(dirs[:, 0] * math.cos(a) + dirs[:, 1] * math.sin(a)))
        p = P[i]; t = P[(i + 3) % len(P)] - P[(i - 3) % len(P)]
        t = t / np.linalg.norm(t)
        nin = ctr - p; nin = nin / np.linalg.norm(nin)
        T = Vector((t[0], 0.0, t[1])); NIN = Vector((nin[0], 0.0, nin[1])); OUT = Vector((0.0, -1.0, 0.0))
        rng = random.Random(seed)
        nt, nu = 12, 10
        tip = [rng.uniform(0.55, 1.0) for _ in range(nu + 1)]
        V, F = [], []
        for j in range(nu + 1):
            u = j / nu - 0.5
            pos = Vector((p[0], D - 0.004, p[1]))
            prev_s = 0.0
            col = []
            for i2 in range(nt + 1):
                s_ = i2 / nt * tip[j]
                phi = curl * (s_ ** 0.85)
                if i2 > 0:
                    ds = (s_ - prev_s) * L
                    pos = pos + (NIN * math.cos(phi) + OUT * math.sin(phi)) * ds
                prev_s = s_
                w = w0 * (1.0 - 0.85 * s_)
                jag = rng.uniform(-0.02, 0.02) if j in (0, nu) else 0.0
                col.append(tuple(pos + T * (u * w + jag)))
            V.extend(col)
        for j in range(nu):
            for i2 in range(nt):
                a0 = j * (nt + 1) + i2
                F.append((a0, a0 + nt + 1, a0 + nt + 2, a0 + 1))
        ob = obj("TearFlap%d" % k, MB().add(V, F), C['Backdrop'], [M['sky'], M['flapback'], M['tear']])
        solidify(ob, 0.01, 0.0, 1, 2)
        out.append(ob)
    return out


# inside the hole: darkness with a faint indigo depth far behind, and a cold light on the receding page edges
vm, VN, VL = pp_lib._new_mat('P_Void')
gt = VN.new('ShaderNodeTexGradient'); gt.gradient_type = 'SPHERICAL'
tc_ = VN.new('ShaderNodeTexCoord'); mp_ = VN.new('ShaderNodeMapping')
mp_.inputs['Scale'].default_value = (0.4, 0.4, 0.4)
VL.new(tc_.outputs['Object'], mp_.inputs['Vector']); VL.new(mp_.outputs['Vector'], gt.inputs['Vector'])
rp = VN.new('ShaderNodeValToRGB')
rp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
rp.color_ramp.elements[1].position = 1.0
rp.color_ramp.elements[1].color = rgba('#2A2C78')
VL.new(gt.outputs['Fac'], rp.inputs['Fac'])
em = VN.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = 0.9
VL.new(rp.outputs['Color'], em.inputs['Color'])
vo = VN.new('ShaderNodeOutputMaterial'); VL.new(em.outputs[0], vo.inputs['Surface'])
obj("VoidDepth", MB().add([(-2.5, 0, -2.5), (2.5, 0, -2.5), (2.5, 0, 2.5), (-2.5, 0, 2.5)], [(0, 1, 2, 3)]), C['Backdrop'], [vm],
    loc=(TX, D + 2.4, TZ + 0.4))
light("TearInner", 'POINT', C['Lights'], (TX, D + 0.14, TZ + 1.05), energy=22.0, color=(0.55, 0.62, 1.0), size=0.25)

# ------------------------------------------------------------------ backdrop collage (raised a little off the sky page)
card("Moon", lambda X, Y: cut_edge(sd_circle(X, Y, 0.0, 0.0, 0.62), X, Y, 5, 0.01, 4.0, 0.004),
     (-0.7, -0.7, 0.7, 0.7), 0.01, C['Backdrop'], [M['moon']], M=frame((-5.0, D - 0.008, 3.95), (1, 0, 0), (0, 0, 1)), t=0.006)
def torn(fn_b, scale=1.0):
    fn, b = fn_b
    tf = tear_fn(scale, 7)
    return (lambda X, Y: np.maximum(fn(X, Y), -tf(X, Y))), b

card("MountainsFar", *torn(mountains(11, -HW, HW, RG, 1.8, 3.3, 8), 1.0), 0.03, C['Backdrop'], [M['mtn_far'], M['flapback'], M['tear']],
     M=frame((0, D - 0.03, 0), (1, 0, 0), (0, 0, 1)), t=0.008, shell=1, rim=2)
card("MountainsNear", *torn(mountains(12, -HW, HW, RG, 1.0, 2.2, 6), 1.03), 0.03, C['Backdrop'], [M['mtn_near'], M['flapback'], M['tear']],
     M=frame((0, D - 0.08, 0), (1, 0, 0), (0, 0, 1)), t=0.008, shell=1, rim=2)
for i, (cx, cz, cw, ch, cy) in enumerate([(-2.3, 4.5, 3.2, 0.5, 0.16), (3.5, 4.1, 3.9, 0.55, 0.13), (-7.0, 3.4, 2.2, 0.42, 0.2), (6.6, 4.7, 2.2, 0.4, 0.18)]):
    fn, b = cloud(30 + i, cw, ch)
    card("Cloud%d" % i, fn, b, 0.015, C['Backdrop'], [M['cloud']], M=frame((cx, D - cy, cz), (1, 0, 0), (0, 0, 1)), t=0.01)

# ------------------------------------------------------------------ floor print: patches, path, river, moat
def floor_layer(name, fn, bounds, step, mats, z, t=0.006):
    return card(name, fn, bounds, step, C['Floor'], mats, M=frame((0, 0, z), (1, 0, 0), (0, 1, 0)), t=t)

FB = (-HW + 0.02, 0.02, HW - 0.02, D - RG - 0.02)

def patch_fn(blobs, seed):
    def fn(X, Y):
        d = None
        for (x, y, rx, ry) in blobs:
            e = sd_ellipse(X, Y, x, y, rx, ry)
            d = e if d is None else smin(d, e, 0.5)
        return cut_edge(d, X, Y, seed, 0.06, 1.2, 0.012, 10.0)
    return fn

floor_layer("PatchLight", patch_fn([(-3.0, 6.1, 3.6, 0.9), (1.6, 6.3, 3.4, 0.8), (-1.0, 3.6, 3.8, 0.85), (2.0, 8.7, 3.2, 0.7), (-3.8, 1.2, 2.4, 0.6)], 41),
            FB, 0.04, [M['patch_l']], 0.001, 0.003)
floor_layer("PatchDark", patch_fn([(-5.5, 2.0, 2.2, 1.0), (0.5, 1.3, 2.6, 0.8), (-4.8, 8.6, 2.2, 0.6), (3.6, 4.9, 2.0, 0.5)], 42),
            FB, 0.04, [M['patch_d']], 0.001, 0.003)

def path_fn(r, seed):
    def fn(X, Y):
        return cut_edge(sd_polyline(X, Y, PATHS, r), X, Y, seed, 0.014, 3.0, 0.005, 18.0)
    return fn

floor_layer("Verge", path_fn(1.05, 53), FB, 0.03, [M['verge']], 0.002, 0.012)
floor_layer("PathUnder", path_fn(0.43, 51), FB, 0.025, [M['path_u']], 0.004, 0.006)
floor_layer("Path", path_fn(0.36, 52), FB, 0.025, [M['path']], 0.011, 0.006)

def water_fn(extra, seed):
    cx, cy, rx, ry, hw = MOAT

    def fn(X, Y):
        river = sd_polyline(X, Y, RIVS, 0.28 + extra)
        moat = np.abs(sd_ellipse(X, Y, cx, cy, rx, ry)) - (hw + extra)
        pool = sd_ellipse(X, Y, RIVER[0][0], RIVER[0][1] + 0.1, 0.7 + extra, 0.42 + extra)
        d = smin(smin(river, moat, 0.3), pool, 0.3)
        return cut_edge(d, X, Y, seed, 0.02, 2.0, 0.006, 16.0)
    return fn

floor_layer("Bank", water_fn(0.09, 61), FB, 0.025, [M['bank']], 0.004, 0.006)
floor_layer("Water", water_fn(0.0, 62), FB, 0.025, [M['water']], 0.008, 0.004)

# ------------------------------------------------------------------ printed motifs on the floor (flat, like an illustrated page)
def motif_geom(kind, seed):
    rng = random.Random(seed)
    if kind == 'flower':
        r = 0.045
        fn = lambda X, Y: np.minimum.reduce([sd_circle(X, Y, r * math.cos(a), r * math.sin(a), r * 0.62) for a in np.linspace(0, 2 * math.pi, 6)[:-1]])
        return shape2d(fn, (-0.1, -0.1, 0.1, 0.1), 0.006)
    blades = []
    for k in range(3):
        a = math.radians(rng.uniform(-28, 28) + (k - 1) * 22)
        L_ = rng.uniform(0.09, 0.16)
        blades.append([(-0.012 + k * 0.012, 0.0), (0.0 + k * 0.012, 0.0), (L_ * math.sin(a) + k * 0.012, L_ * math.cos(a))])
    fn = lambda X, Y: np.minimum.reduce([sd_poly(X, Y, b) for b in blades])
    return shape2d(fn, (-0.15, -0.02, 0.17, 0.18), 0.005)

def floor_prints():
    rng = random.Random(77)
    gtemp = [motif_geom('grass', 700 + i) for i in range(4)]
    ftemp = motif_geom('flower', 710)
    wf_ = water_fn(0.25, 62)
    g_mb, f_mb, w_mb = MB(), MB(), MB()
    n_ok = 0
    for i in range(2600):
        x = rng.uniform(-HW + 0.2, HW - 0.2); y = rng.uniform(0.15, D - RG - 0.3)
        X = np.array([[x]]); Y = np.array([[y]])
        if sd_polyline(X, Y, PATHS, 0.55)[0, 0] < 0 or wf_(X, Y)[0, 0] < 0 or ((x + 4.0) / 2.6) ** 2 + ((y - 1.45) / 0.85) ** 2 < 1:
            continue
        if (x - CASTLE[0]) ** 2 / 2.7 ** 2 + (y - CASTLE[1]) ** 2 / 2.0 ** 2 < 1.0:
            continue
        a = rng.uniform(0, 2 * math.pi); sc = rng.uniform(0.75, 1.3)
        Mx = Matrix.Translation((x, y, 0.0026)) @ Matrix.Rotation(a, 4, 'Z') @ Matrix.Diagonal((sc, sc, 1, 1))
        r = rng.random()
        if r < 0.035:
            f_mb.add2d(ftemp, Mx)
        elif r < 0.045:
            w_mb.add2d(ftemp, Mx)
        elif r < 0.36:
            g_mb.add2d(gtemp[i % 4], Mx)
        else:
            continue
        n_ok += 1
    for name, mb, m in (("PrintGrass", g_mb, M['print_a']), ("PrintFlowers", f_mb, M['print_b']), ("PrintFlowersWarm", w_mb, M['print_c'])):
        if mb.v:
            obj(name, mb, C['Floor'], [m])
    print("printed motifs", n_ok)

floor_prints()

# ------------------------------------------------------------------ lanterns along the path
def path_point(frac):
    P = np.asarray(PATHS); seg = np.hypot(*np.diff(P, axis=0).T); s = np.concatenate([[0], np.cumsum(seg)])
    t = frac * s[-1]; i = min(int(np.searchsorted(s, t)) - 1, len(P) - 2); i = max(i, 0)
    f = (t - s[i]) / max(seg[i], 1e-9); p = P[i] + (P[i + 1] - P[i]) * f
    d = (P[i + 1] - P[i]) / max(seg[i], 1e-9)
    return p, np.array([-d[1], d[0]])

def lantern(x, y, k):
    mb = MB()
    mb.box((x, y, 0.33), (0.045, 0.045, 0.66), 0)
    mb.box((x, y, 0.645), (0.17, 0.035, 0.03), 0)
    mb.lathe([(0.105, 0.0), (0.0, 0.085)], 4, 1, Matrix.Translation((x, y, 0.83)), phase=math.pi / 4)
    mb.box((x, y, 0.035), (0.14, 0.14, 0.07), 0)
    obj("LanternPost%d" % k, mb, C['Floor'], [M['post'], M['dark']])
    g = MB().box((x, y, 0.745), (0.11, 0.11, 0.16))
    obj("LanternGlow%d" % k, g, C['Floor'], [M['lantern']])
    light("LanternLight%d" % k, 'POINT', C['Lights'], (x, y, 0.74), energy=7.0, color=(1.0, 0.6, 0.3), size=0.05)

wf = water_fn(0.0, 62)
for k, (frac, side) in enumerate(((0.075, -1), (0.255, -1), (0.6, 1), (0.93, 1))):
    p, n = path_point(frac)
    q = p + n * side * 0.72
    wd = float(wf(np.array([[q[0]]]), np.array([[q[1]]]))[0, 0])
    pd = float(sd_polyline(np.array([[q[0]]]), np.array([[q[1]]]), PATHS, 0.0)[0, 0])
    print("lantern", k, "at", round(q[0], 2), round(q[1], 2), "path dist", round(pd, 2), "water dist", round(wd, 2))
    lantern(q[0], q[1], k)

# ------------------------------------------------------------------ rows of pop-up cards
pieces = []

LIGHTER = {}

def piece(kind, mat, x, y, seed, rot=0.0, **kw):
    gen = {'tree': tree_round, 'fir': tree_fir, 'bush': bush, 'hill': hill, 'rock': rock, 'grass': grass,
           'tuft': tuft, 'flowers': flowers, 'shrub': shrub}[kind]
    fn, b = gen(seed, **kw)
    span = b[2] - b[0]
    step = 0.008 if span < 0.6 else (0.01 if span < 0.9 else (0.014 if span < 1.6 else (0.02 if span < 3.2 else 0.03)))
    ob = card("%s_%d" % (kind, len(pieces)), fn, b, step, C['Rows'], [mat], loc=(x, y, 0.0),
              rot=(0.0, 0.0, math.radians(rot)), t=0.02)
    pieces.append(ob)
    if kind in ('tree', 'shrub') and mat.name in LIGHTER:
        # a second, lighter crown just behind and a little up-right: the layered paper look of the references
        kw2 = dict(kw)
        if kind == 'shrub':
            kw2 = {'h': kw.get('h', 0.75), 'w': kw.get('w', 0.9), 'trunk': 0.06, 'lobes': 7}
        fn2, b2 = tree_round(seed, part='crown', grow=0.035, **kw2)
        ob2 = card("%s_%d_back" % (kind, len(pieces)), fn2, b2, step, C['Rows'], [LIGHTER[mat.name]],
                   loc=(x + 0.06 * math.cos(math.radians(rot)), y + 0.07, 0.04), rot=(0.0, 0.0, math.radians(rot)), t=0.015)
        pieces.append(ob2)
    return ob


def ground_row(y, x0, x1, hmax, front, back, seed, gaps=(), dy=0.3, wave=0.14):
    """Two staggered layers of low cut-outs (mounds, tufts, flowers, shrubs, rocks, grass) between x0 and x1,
    nothing in `gaps`. Heights stay under hmax so the path behind the row stays in view from the game camera."""
    rng = random.Random(seed)
    ph = rng.uniform(0, 6.28)
    for layer, (mat, yy, hk) in enumerate(((back, y + dy, 1.12), (front, y, 0.86))):
        x = x0 + (0.0 if layer == 0 else rng.uniform(0.3, 0.6))
        while x < x1:
            w = rng.uniform(0.8, 1.6)
            cxp = x + w / 2
            if any(g0 - 0.2 < cxp < g1 + 0.2 for g0, g1 in gaps):
                x += 0.5
                continue
            h = hmax * hk * rng.uniform(0.62, 1.0)
            r = rng.random()
            s_ = rng.randint(0, 99999)
            yj = yy + wave * math.sin(cxp * 0.8 + ph) + rng.uniform(-0.05, 0.05)
            rot = rng.uniform(-6, 6)
            if layer == 1 and r < 0.12:
                piece('rock', mat, cxp, yj, s_, rot, w=w * 0.5, h=h * 0.7)
                step_w = w * 0.6
            elif r < 0.27:
                piece('tuft', mat, cxp, yj, s_, rot, w=min(0.7, w * 0.5), h=h * 0.95, blades=rng.randint(7, 11))
                step_w = w * 0.55
            elif r < 0.37:
                piece('flowers', mat, cxp, yj, s_, rot, w=min(0.75, w * 0.55), h=h * 0.85, n=rng.randint(4, 6))
                step_w = w * 0.6
            elif r < 0.47 and hmax >= 0.5:
                hs = h * 1.02
                piece('shrub', mat, cxp, yj, s_, rot, h=hs, w=hs * rng.uniform(0.95, 1.25))
                step_w = hs * 1.1
            elif layer == 1 and r < 0.53:
                piece('grass', mat, cxp, yj, s_, rot, w=w * 0.45, h=h * 0.65, blades=rng.randint(5, 8))
                step_w = w * 0.5
            else:
                piece('bush', mat, cxp, yj, s_, rot, w=w, h=h)
                step_w = w
            x += step_w * rng.uniform(0.6, 0.95) if layer == 0 else step_w * rng.uniform(0.9, 1.5)

LIGHTER.update({M['row4'].name: M['row4b'], M['row3'].name: M['row3b'], M['row2'].name: M['row2b'], M['row1'].name: M['row1b'],
                M['wing'].name: M['row1'], M['row4b'].name: M['row4b'], M['row3b'].name: M['row4'], M['row2b'].name: M['row3'],
                M['row1b'].name: M['row2']})

# row 4: low hills and trees in front of the sky page, open around the tear
piece('hill', M['row4b'], -5.3, 10.02, 401, w=5.8, h=1.6)
piece('hill', M['row4b'], 3.5, 10.02, 402, w=4.4, h=1.45)
for x, h, s in ((-7.55, 2.3, 411), (-6.8, 1.9, 412), (-3.55, 1.8, 413), (-2.85, 1.5, 414), (1.25, 1.6, 415), (1.95, 2.1, 416),
                (5.05, 2.2, 417), (5.8, 1.7, 418), (7.7, 2.4, 419)):
    piece('fir', M['row4'], x, 9.8 + (s % 3) * 0.05, s, rot=(s % 5 - 2) * 2.0, h=h, w=h * 0.44)
piece('tree', M['row4'], -4.75, 9.72, 421, h=2.0, w=1.6)
piece('tree', M['row4'], 3.35, 9.74, 422, h=1.9, w=1.5)
ground_row(9.35, -6.4, -2.2, 0.55, M['row4'], M['row4b'], 431, dy=0.25)
ground_row(9.35, 0.4, 6.2, 0.55, M['row4'], M['row4b'], 432, dy=0.25)

# row 3: tall on the left where nothing walks behind it, low in the middle, open on the right for path and river
for x, h, w, s in ((-7.4, 2.7, 1.9, 441), (-6.0, 2.2, 1.6, 442), (-4.5, 2.5, 1.7, 443)):
    piece('tree', M['row3'], max(x, -7.15), 7.48 + (s % 2) * 0.14, s, rot=(s % 5 - 2) * 2.0, h=h, w=min(w, 1.8))
piece('fir', M['row3b'], -3.15, 7.72, 444, h=2.0, w=0.9)
piece('fir', M['row3b'], -5.25, 7.78, 445, h=2.3, w=1.0)
ground_row(7.45, -2.6, 5.3, 0.72, M['row3'], M['row3b'], 446)
piece('tree', M['row3'], 7.55, 7.4, 447, h=2.8, w=1.35)

# row 2: low everywhere in front of the long middle channel; wings at both edges
ground_row(4.92, -5.7, 6.4, 0.8, M['row2'], M['row2b'], 451)
piece('tree', M['wing'], -7.45, 4.85, 461, h=3.0, w=1.35)
piece('fir', M['wing'], 7.6, 4.95, 462, h=3.2, w=1.25)

# row 1: ground row in front of the last channel; a tall tree frames the left edge
ground_row(2.38, -6.4, 2.5, 0.56, M['row1'], M['row1b'], 471)
piece('tree', M['wing'], -7.4, 2.15, 481, h=3.2, w=1.45)

# foreground strip along the front edge of the page
ground_row(0.36, -7.9, 2.7, 0.62, M['wing'], M['row1'], 491, dy=0.22, gaps=((-6.0, -2.7),))

# ------------------------------------------------------------------ pond at the front left, with reeds and lily pads
POND = (-4.35, 1.42, 1.65, 0.5)
def pond_fn(extra, seed):
    px, py, rx, ry = POND
    def fn(X, Y):
        d = sd_ellipse(X, Y, px, py, rx + extra, ry + extra)
        d = smin(d, sd_ellipse(X, Y, px + 0.9, py + 0.12, 0.7 + extra, 0.38 + extra), 0.3)
        return cut_edge(d, X, Y, seed, 0.03, 1.6, 0.008, 14.0)
    return fn
floor_layer("PondBank", pond_fn(0.1, 63), (POND[0] - 2.2, POND[1] - 1.0, POND[0] + 2.4, POND[1] + 1.0), 0.02, [M['bank']], 0.004, 0.006)
floor_layer("Pond", pond_fn(0.0, 64), (POND[0] - 2.2, POND[1] - 1.0, POND[0] + 2.4, POND[1] + 1.0), 0.02, [M['water']], 0.008, 0.004)
for k, (lx, ly, lr) in enumerate(((-5.0, 1.35, 0.13), (-4.7, 1.62, 0.1), (-3.6, 1.3, 0.12), (-3.25, 1.55, 0.09), (-4.15, 1.2, 0.08))):
    def lily(X, Y, lx=lx, ly=ly, lr=lr, k=k):
        d = sd_circle(X, Y, lx, ly, lr)
        a = 1.3 + k
        notch = sd_poly(X, Y, [(lx, ly), (lx + math.cos(a) * lr * 1.6, ly + math.sin(a) * lr * 1.6), (lx + math.cos(a + 0.5) * lr * 1.6, ly + math.sin(a + 0.5) * lr * 1.6)])
        return np.maximum(d, -notch)
    floor_layer("Lily%d" % k, lily, (lx - lr - 0.05, ly - lr - 0.05, lx + lr + 0.05, ly + lr + 0.05), 0.006, [M['lily']], 0.013, 0.004)
for k, (rx_, ry_, rh) in enumerate(((-6.05, 1.5, 0.62), (-5.8, 1.78, 0.5), (-2.55, 1.32, 0.58), (-2.35, 1.6, 0.46), (-3.05, 1.92, 0.4))):
    piece('tuft', M['reed'], rx_, ry_, 900 + k, rot=(k - 2) * 7, w=0.42, h=rh, blades=8)

# ------------------------------------------------------------------ waterfall from the mountains into the river's pool
def waterfall(wx=6.6):
    for k, (w, yy, col) in enumerate(((0.62, D - 0.11, '#9DB7E6'), (0.42, D - 0.15, '#C6D7F2'), (0.22, D - 0.19, '#F0F5FD'))):
        mat = washi('P_Fall%d' % k, col, col, transl=0.25, mscale=1.4, emit=col, emit_strength=0.12)
        def fn(X, Y, w=w, k=k):
            top = 2.25 - k * 0.1
            taper = np.clip((top - Y) / 0.35, 0.35, 1.0)
            half = w / 2 * taper * (1 + 0.12 * np.sin(Y * 6 + k * 1.7)) + 0.015 * fbm(X * 8, Y * 3, 90 + k, 2)
            d = np.abs(X) - half
            return np.maximum(d, np.maximum(0.28 - Y, Y - top))
        card("Waterfall%d" % k, fn, (-w, 0.25, w, 2.4), 0.012, C['Backdrop'], [mat], M=frame((wx, yy, 0), (1, 0, 0), (0, 0, 1)), t=0.004)
    # the falls pour out from under a dark rock ledge
    def ledge(X, Y):
        d = smin(sd_ellipse(X, Y, 0.0, 0.08, 0.8, 0.34), sd_ellipse(X, Y, -0.38, 0.24, 0.42, 0.3), 0.15)
        d = smin(d, sd_ellipse(X, Y, 0.42, 0.16, 0.36, 0.26), 0.12)
        d = np.maximum(d, -(Y + 0.1))
        return cut_edge(d, X, Y, 97, 0.025, 3.5, 0.008, 18.0)
    card("FallLedge", ledge, (-0.95, -0.15, 0.95, 0.6), 0.008, C['Backdrop'], [M['mtn_near']], M=frame((wx - 0.02, D - 0.24, 2.12), (1, 0, 0), (0, 0, 1)), t=0.01)
    for k, (fx, fz, fw) in enumerate(((wx - 0.28, 0.3, 0.55), (wx + 0.22, 0.28, 0.5), (wx, 0.38, 0.7))):
        fn, b = cloud(95 + k, fw, 0.24)
        card("Foam%d" % k, fn, b, 0.008, C['Backdrop'], [M['foam']], M=frame((fx, D - 0.26 - k * 0.02, fz - 0.08), (1, 0, 0), (0, 0, 1)), t=0.004)

waterfall()

# ------------------------------------------------------------------ stars on the sky page
def star_pts(r, inner=0.38):
    pts = []
    for k in range(8):
        a = math.pi / 2 + k * math.pi / 4
        rr = r if k % 2 == 0 else r * inner
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    return pts
rs = random.Random(12)
for k, (sx, sz) in enumerate(((-6.6, 4.6), (-3.6, 4.85), (-1.2, 5.05), (0.9, 4.75), (2.2, 5.1), (4.9, 4.65), (7.3, 5.0),
                              (-7.4, 3.9), (-4.1, 4.15), (1.6, 4.3), (6.1, 4.15), (-2.7, 3.75), (3.0, 3.6))):
    r = rs.uniform(0.06, 0.12)
    card("Star%d" % k, lambda X, Y, r=r: sd_poly(X, Y, star_pts(r)), (-r - 0.02, -r - 0.02, r + 0.02, r + 0.02), 0.004,
         C['Backdrop'], [M['star']], M=frame((sx, D - 0.012, sz), (1, 0, 0), (0, 0, 1)), t=0.004)

# ------------------------------------------------------------------ castle
bridge_end = pp_castle.build(C['Castle'], CASTLE, M)
print("drawbridge end", tuple(round(v, 2) for v in bridge_end), "path end", PATH[-1])

# ------------------------------------------------------------------ lights
LIGHTING = 'mixed'
if LIGHTING == 'back':
    # moonlight from behind-left (where the moon hangs): rims on every card, soft shadows falling toward the reader
    sun = light("Moonlight", 'SUN', C['Lights'], (0, 0, 20), energy=2.6, color=(0.76, 0.82, 1.0), size=math.radians(7.0))
    sun.rotation_euler = Vector((0.42, -0.52, -0.74)).to_track_quat('-Z', 'Y').to_euler()
    fill = light("FrontFill", 'AREA', C['Lights'], (0.3, -14.0, 16.0), energy=2100.0, color=(0.72, 0.76, 1.0), size=18.0, shadow=False)
    aim(fill, (0.3, 5.0, 0.5))
elif LIGHTING == 'mixed':
    # high soft key from the front-left shows the paper; a shadowless rim from behind-left outlines every card
    sun = light("Moonlight", 'SUN', C['Lights'], (0, 0, 20), energy=1.5, color=(0.76, 0.82, 1.0), size=math.radians(9.0))
    sun.rotation_euler = Vector((0.36, 0.42, -0.83)).to_track_quat('-Z', 'Y').to_euler()
    rim = light("MoonRim", 'SUN', C['Lights'], (0, 0, 21), energy=1.3, color=(0.8, 0.84, 1.0), size=math.radians(6.0), shadow=False)
    rim.rotation_euler = Vector((0.5, -0.55, -0.67)).to_track_quat('-Z', 'Y').to_euler()
    fill = light("FrontFill", 'AREA', C['Lights'], (0.3, -14.0, 16.0), energy=1500.0, color=(0.72, 0.76, 1.0), size=18.0, shadow=False)
    aim(fill, (0.3, 5.0, 0.5))
else:
    sun = light("Moonlight", 'SUN', C['Lights'], (0, 0, 20), energy=1.6, color=(0.74, 0.8, 1.0), size=math.radians(6.0))
    sun.rotation_euler = Vector((0.32, 0.5, -0.8)).to_track_quat('-Z', 'Y').to_euler()
cyc = light("HorizonGlow", 'AREA', C['Lights'], (0.0, D - 0.55, 0.15), energy=650.0, color=(1.0, 0.66, 0.46), size=16.0, size_y=0.5)
aim(cyc, (0.0, D + 0.5, 2.2))
for i, (yy, e) in enumerate(((9.55, 120.0), (7.75, 150.0), (5.2, 110.0), (2.65, 70.0))):
    l = light("RowGlow%d" % i, 'AREA', C['Lights'], (0.0, yy, 0.06), energy=e, color=(1.0, 0.68, 0.6), size=15.0, size_y=0.35)
    aim(l, (0.0, yy + 1.6, 1.0))
tl = light("TearLight", 'SPOT', C['Lights'], (TX, D + 1.6, 1.15), energy=2500.0, color=(0.64, 0.74, 1.0), size=0.4, spot=math.radians(50), blend=0.6)
aim(tl, (TX - 0.1, D - 3.2, 0.0))

world = scn.world or bpy.data.worlds.new("World")
scn.world = world
try:
    world.use_nodes = True
except Exception:
    pass
bg = next(n for n in world.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs['Color'].default_value = rgba('#1B2044')
bg.inputs['Strength'].default_value = 0.6

# ------------------------------------------------------------------ camera (the game view)
cam_data = bpy.data.cameras.new("GameCam")
cam_data.lens = 55.0
cam_data.sensor_width = 36.0
cam_data.clip_end = 300.0
cam = bpy.data.objects.new("GameCam", cam_data)
C['Rig'].objects.link(cam)
cam.location = (0.3, -19.41, 18.75)
aim(cam, (0.3, 6.8, 0.4))
scn.camera = cam

# ------------------------------------------------------------------ render settings
r = scn.render
r.engine = 'BLENDER_EEVEE'
r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
ee = scn.eevee
for attr, val in (("taa_render_samples", 48), ("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("shadow_step_count", 8)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
try:
    scn.view_settings.view_transform = 'AgX'
    scn.view_settings.look = 'AgX - Base Contrast'
except Exception:
    pass

bpy.ops.wm.save_mainfile()
print("built:", len(bpy.data.objects), "objects,", len(pieces), "row pieces,", sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH'), "polygons")
