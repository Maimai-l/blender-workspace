# wd_units.py - ink enemies, boss, shell and portal -> WD_Scout/WD_Soldier/WD_Brute/WD_Boss/WD_Shell/WD_Portal.fbx
# Units face Unity +z. Limbs are separate objects with their origin at the joint, for procedural animation.
import sys, importlib, math, random
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import wdlib; importlib.reload(wdlib)
from wdlib import *
from mathutils import Vector, Matrix
import bpy

reset()
rng = random.Random(33)
P = lambda x, z, y: tuple(U(x, z, y))

def piece(name, build, pivot, parent, smooth=60):
    mb = MB(name, seed=rng.randint(0, 9999))
    build(mb)
    ob = mb.finish(smooth_angle=smooth)
    set_origin(ob, U(*pivot))
    parent_keep(ob, parent)
    return ob

def Mt(x, z, y, rot=(0, 0, 0), scl=(1, 1, 1)):
    return Matrix.Translation(U(x, z, y)) @ rot_m(rot) @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1))

def eye(mb, x, z, y, r, pupil=0.45, mat_w="M_EyeWhite"):
    sphere(mb, P(x, z, y), r, mat_w, segs=14, rings=8, scl=(1.0, 0.62, 1.05))
    sphere(mb, P(x, z + r * 0.5, y), r * pupil, "M_InkGlow", segs=12, rings=6, scl=(1.0, 0.55, 1.0))

# ======================================================================= scout
root = empty("WD_Scout")
def scout_body(mb):
    lathe(mb, [(0.0, 0.1), (0.24, 0.12), (0.35, 0.24), (0.38, 0.4), (0.34, 0.57), (0.24, 0.7), (0.1, 0.79), (0.0, 0.81)], 18, "M_Ink", Mt(0, 0, 0))
    # ink-drop tip leaning back
    lathe(mb, [(0.11, 0.0), (0.06, 0.12), (0.0, 0.24)], 10, "M_Ink", Mt(0, -0.05, 0.74, rot=(-28, 0, 0)), cap_top=False)
    eye(mb, 0.0, 0.25, 0.47, 0.205, pupil=0.5)
    cbox(mb, P(0, 0.3, 0.7), (0.3, 0.06, 0.05), "M_InkLight", b=0.02, rot=(-10, 0, 0))
    for s in (-1, 1):
        sphere(mb, P(s * 0.37, 0.02, 0.36), 0.08, "M_InkLight", segs=10, rings=6, scl=(0.8, 1.0, 1.2))
    torus(mb, P(0, 0, 0.17), 0.3, 0.035, "M_InkGlow", segs=24, csegs=6)
piece("Body", scout_body, (0, 0, 0.12), root)
for s, nm in ((-1, "FootL"), (1, "FootR")):
    piece(nm, lambda mb, s=s: sphere(mb, P(s * 0.15, 0.06, 0.07), 0.11, "M_InkLight", segs=12, rings=6, scl=(1.0, 1.35, 0.7)), (s * 0.15, 0, 0.14), root)
export_fbx(collect(root), MODELS + "/WD_Scout.fbx")

# ======================================================================= soldier
root = empty("WD_Soldier")
def soldier_body(mb):
    lathe(mb, [(0.0, 0.2), (0.33, 0.22), (0.41, 0.42), (0.42, 0.68), (0.37, 0.9), (0.0, 0.95)], 18, "M_Ink", Mt(0, 0, 0))
    torus(mb, P(0, 0, 0.44), 0.42, 0.05, "M_InkArmor", segs=24, csegs=6)
    sphere(mb, P(0, 0.36, 0.44), 0.06, "M_InkGlow", segs=10, rings=5)
    # helmet with visor slit and crest
    sphere(mb, P(0, 0.02, 1.08), 0.33, "M_InkArmor", segs=18, rings=10, scl=(1.0, 1.05, 0.92))
    cbox(mb, P(0, 0.31, 1.06), (0.4, 0.08, 0.075), "M_InkGlow", b=0.02)
    cbox(mb, P(0, 0.33, 0.94), (0.06, 0.06, 0.22), "M_InkArmor", b=0.02)
    for k in range(3):
        cbox(mb, P(0, 0.12 - k * 0.17, 1.42 - k * 0.04), (0.06, 0.16, 0.2 - k * 0.04), "M_InkGlow", b=0.02, rot=(-15, 0, 0))
    for s in (-1, 1):
        sphere(mb, P(s * 0.4, 0, 0.84), 0.17, "M_InkArmor", segs=14, rings=7, scl=(1.0, 1.0, 0.72))
piece("Body", soldier_body, (0, 0, 0.2), root)
def arm_shield(mb):
    limb(mb, P(-0.44, 0, 0.8), P(-0.5, 0.06, 0.48), 0.09, 0.08, 10, "M_Ink")
    M = Mt(-0.58, 0.16, 0.56, rot=(90, 0, 20))
    lathe(mb, [(0.0, -0.04), (0.33, -0.04), (0.35, 0.0), (0.3, 0.05), (0.0, 0.07)], 20, "M_InkArmor", M)
    torus(mb, (0, 0, 0.07), 0.19, 0.03, "M_InkGlow", segs=20, csegs=5, M=M)
    sphere(mb, (0, 0, 0.08), 0.06, "M_InkGlow", segs=10, rings=5, M=M)
piece("ArmL", arm_shield, (-0.44, 0, 0.8), root)
def arm_spear(mb):
    limb(mb, P(0.44, 0, 0.8), P(0.5, 0.1, 0.5), 0.09, 0.08, 10, "M_Ink")
    sphere(mb, P(0.5, 0.12, 0.48), 0.09, "M_Ink", segs=10, rings=6)
    limb(mb, P(0.5, 0.16, -0.1), P(0.5, 0.16, 1.45), 0.028, 0.028, 6, "M_WoodDark")
    lathe(mb, [(0.07, 0.0), (0.0, 0.3)], 4, "M_InkGlow", Mt(0.5, 0.16, 1.45))
    torus(mb, P(0.5, 0.16, 1.42), 0.05, 0.02, "M_InkArmor", segs=10, csegs=4)
piece("ArmR", arm_spear, (0.44, 0, 0.8), root)
for s, nm in ((-1, "FootL"), (1, "FootR")):
    piece(nm, lambda mb, s=s: sphere(mb, P(s * 0.17, 0.05, 0.09), 0.13, "M_InkArmor", segs=12, rings=6, scl=(1.0, 1.4, 0.75)), (s * 0.17, 0, 0.2), root)
export_fbx(collect(root), MODELS + "/WD_Soldier.fbx")

# ======================================================================= brute
root = empty("WD_Brute")
def brute_body(mb):
    M = Mt(0, 0, 0.0, rot=(-12, 0, 0))
    lathe(mb, [(0.0, 0.5), (0.5, 0.52), (0.68, 0.82), (0.7, 1.2), (0.56, 1.52), (0.0, 1.62)], 20, "M_Ink", M)
    sphere(mb, P(0, 0.42, 1.42), 0.26, "M_InkLight", segs=14, rings=8, scl=(1.1, 1.0, 0.9))
    for s in (-1, 1):
        cbox(mb, P(s * 0.11, 0.66, 1.46), (0.13, 0.05, 0.05), "M_InkGlow", b=0.015, rot=(0, 0, s * 12))
        lathe(mb, [(0.08, 0.0), (0.0, 0.34)], 8, "M_InkArmor", Mt(s * 0.24, 0.34, 1.6, rot=(-30, s * 35, 0)))
        cbox(mb, P(s * 0.66, 0.0, 1.42), (0.56, 0.7, 0.3), "M_InkArmor", b=0.09, rot=(0, s * 22, 0))
        for k in range(2):
            lathe(mb, [(0.07, 0.0), (0.0, 0.26)], 6, "M_InkGlow", Mt(s * (0.66 + 0.06 * s), -0.15 + k * 0.3, 1.58, rot=(0, s * 22, 0)))
    v = [P(0, 0.72, 1.18), P(0.16, 0.7, 1.0), P(0, 0.68, 0.82), P(-0.16, 0.7, 1.0)]
    vv = v + [tuple(Vector(q) + Vector(U(0, -0.06, 0))) for q in v]
    mb.add(vv, [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]], "M_InkGlow")
    torus(mb, P(0, 0.04, 0.62), 0.6, 0.06, "M_InkArmor", segs=26, csegs=6)
piece("Body", brute_body, (0, 0, 0.55), root, smooth=50)
for s, nm in ((-1, "ArmL"), (1, "ArmR")):
    def arm(mb, s=s):
        limb(mb, P(s * 0.74, 0.0, 1.3), P(s * 0.88, 0.16, 0.78), 0.18, 0.15, 12, "M_Ink", bulge=0.03)
        sphere(mb, P(s * 0.9, 0.22, 0.6), 0.25, "M_InkLight", segs=14, rings=8, scl=(1, 1.1, 0.95))
        torus(mb, P(s * 0.88, 0.16, 0.82), 0.16, 0.045, "M_InkArmor", segs=16, csegs=5)
    piece(nm, arm, (s * 0.74, 0, 1.3), root)
for s, nm in ((-1, "LegL"), (1, "LegR")):
    def leg(mb, s=s):
        limb(mb, P(s * 0.3, 0.0, 0.6), P(s * 0.33, 0.04, 0.2), 0.17, 0.15, 12, "M_Ink")
        cbox(mb, P(s * 0.33, 0.1, 0.1), (0.32, 0.46, 0.2), "M_InkArmor", b=0.07)
    piece(nm, leg, (s * 0.3, 0, 0.6), root)
export_fbx(collect(root), MODELS + "/WD_Brute.fbx")

# ======================================================================= boss
root = empty("WD_Boss")
def boss_body(mb):
    M = Mt(0, 0, 0, rot=(-8, 0, 0))
    lathe(mb, [(0.0, 1.2), (0.9, 1.25), (1.18, 1.7), (1.26, 2.35), (1.08, 2.95), (0.6, 3.2), (0.0, 3.25)], 24, "M_Ink", M)
    torus(mb, P(0, 0.02, 1.32), 0.95, 0.09, "M_InkArmor", segs=30, csegs=6)
    # glowing core behind the chest plates
    sphere(mb, P(0, 0.72, 2.2), 0.5, "M_InkGlow", segs=16, rings=8, scl=(1.25, 0.6, 1.1))
    for s in (-1, 1):
        cbox(mb, P(s * 1.2, -0.05, 2.95), (0.95, 1.1, 0.5), "M_InkArmor", b=0.16, rot=(0, s * 24, 0))
        torus(mb, P(s * 1.2, -0.05, 2.95), 0.5, 0.05, "M_Gold", segs=20, csegs=5, rot=(0, s * 24, 0))
        for k in range(3):
            lathe(mb, [(0.1, 0.0), (0.0, 0.45 - k * 0.08)], 6, "M_InkGlow", Mt(s * (1.25 + 0.05 * k), -0.4 + 0.4 * k, 3.15, rot=(0, s * 30, 0)))
    # scroll poles
    for s in (-1, 1):
        limb(mb, P(s * 0.85, -0.55, 2.6), P(s * 1.25, -0.75, 4.75), 0.05, 0.04, 6, "M_Gold")
piece("Body", boss_body, (0, 0, 1.25), root, smooth=50)
def head(mb):
    sphere(mb, P(0, 0.32, 3.45), 0.46, "M_Ink", segs=18, rings=10, scl=(1.05, 1.0, 0.95))
    for s in (-1, 1):
        cbox(mb, P(s * 0.17, 0.76, 3.48), (0.2, 0.05, 0.07), "M_InkGlow", b=0.02, rot=(0, 0, s * 10))
    for k in range(5):
        a = math.radians(-60 + 30 * k)
        lathe(mb, [(0.1, 0.0), (0.0, 0.42 + (0.18 if k == 2 else 0))], 6, "M_Gold" if k == 2 else "M_InkArmor",
              Mt(0.36 * math.sin(a), 0.32 + 0.12 * math.cos(a), 3.8, rot=(-15 * math.cos(a), 25 * math.sin(a), 0)))
    torus(mb, P(0, 0.32, 3.72), 0.38, 0.05, "M_Gold", segs=22, csegs=5)
piece("Head", head, (0, 0.3, 3.15), root)
# chest plates in reading order: 0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right
for i, (px, py) in enumerate(((-0.4, 2.52), (0.4, 2.52), (-0.4, 1.9), (0.4, 1.9))):
    def plate(mb, px=px, py=py):
        yaw = -14 if px < 0 else 14
        cbox(mb, P(px, 1.04, py), (0.66, 0.16, 0.54), "M_InkArmor", b=0.06, rot=(0, 0, yaw))
        cbox(mb, P(px, 1.1, py), (0.56, 0.06, 0.44), "M_Gold", b=0.03, rot=(0, 0, yaw))
        cbox(mb, P(px, 1.14, py), (0.48, 0.06, 0.36), "M_InkArmor", b=0.03, rot=(0, 0, yaw))
        v = [P(px, 1.19, py + 0.12), P(px + 0.09, 1.19, py), P(px, 1.19, py - 0.12), P(px - 0.09, 1.19, py)]
        vv = v + [tuple(Vector(q) + Vector(U(0, -0.05, 0))) for q in v]
        mb.add(vv, [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]], "M_InkGlow")
    piece("Plate%d" % i, plate, (px, 1.08, py), root, smooth=30)
for s, nm in ((-1, "ArmL"), (1, "ArmR")):
    def arm(mb, s=s):
        limb(mb, P(s * 1.22, 0, 2.75), P(s * 1.55, 0.22, 2.0), 0.3, 0.26, 14, "M_Ink", bulge=0.05)
        limb(mb, P(s * 1.55, 0.22, 2.0), P(s * 1.62, 0.5, 1.45), 0.26, 0.24, 14, "M_Ink")
        sphere(mb, P(s * 1.64, 0.56, 1.25), 0.42, "M_InkLight", segs=16, rings=8)
        torus(mb, P(s * 1.56, 0.28, 1.92), 0.28, 0.07, "M_Gold", segs=18, csegs=5, rot=(30, 0, 0))
    piece(nm, arm, (s * 1.22, 0, 2.75), root)
for s, nm in ((-1, "LegL"), (1, "LegR")):
    def leg(mb, s=s):
        limb(mb, P(s * 0.55, 0, 1.35), P(s * 0.62, 0.06, 0.4), 0.3, 0.27, 14, "M_Ink")
        cbox(mb, P(s * 0.62, 0.16, 0.2), (0.62, 0.86, 0.4), "M_InkArmor", b=0.12)
        torus(mb, P(s * 0.6, 0.04, 0.55), 0.3, 0.05, "M_Gold", segs=18, csegs=5)
    piece(nm, leg, (s * 0.55, 0, 1.35), root)
def scroll(mb):
    for s in (-1, 1):
        cyl(mb, P(s * 1.3, -0.78, 4.6), 0.11, 0.62, 12, "M_Gold")
    cyl(mb, P(0, -0.78, 4.95), 0.07, 2.9, 10, "M_Gold", rot=(0, 90, 0))
    cyl(mb, P(0, -0.78, 4.22), 0.07, 2.9, 10, "M_Gold", rot=(0, 90, 0))
    cbox(mb, P(0, -0.74, 4.58), (2.6, 0.04, 0.72), "M_Parchment", b=0.01)
piece("Scroll", scroll, (0, -0.72, 4.58), root, smooth=40)
export_fbx(collect(root), MODELS + "/WD_Boss.fbx")

# ======================================================================= shell
root = empty("WD_Shell")
def shell(mb):
    sphere(mb, P(0, 0, 0), 0.2, "M_ShellGold", segs=16, rings=10, scl=(1, 1.18, 1))
    torus(mb, P(0, 0, 0), 0.205, 0.028, "M_ShellCore", segs=24, csegs=6, rot=(90, 0, 0))
    sphere(mb, P(0, 0.2, 0), 0.07, "M_ShellCore", segs=10, rings=6)
piece("Shell", shell, (0, 0, 0), root)
export_fbx(collect(root), MODELS + "/WD_Shell.fbx")

# ======================================================================= portal (opening faces Unity -x)
root = empty("WD_Portal")
def portal_stones(mb):
    for s in (-1, 1):
        y = 0.0
        for k, (w, h) in enumerate(((1.25, 0.9), (1.05, 0.95), (0.95, 0.9), (0.85, 0.85))):
            cbox(mb, P(rng.uniform(-0.06, 0.06), s * (1.75 + k * -0.05), y + h / 2), (w, w * 0.9, h - 0.05), "M_PortalStone", b=0.08,
                 rot=(rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-8, 8)))
            y += h
    # broken arch: two halves leaning in, keystone floats
    for s in (-1, 1):
        cbox(mb, P(0, s * 1.2, 3.95), (0.8, 1.3, 0.55), "M_PortalStone", b=0.08, rot=(s * 18, 0, 0))
    cbox(mb, P(0, 0, 4.55), (0.7, 0.6, 0.6), "M_PortalStone", b=0.08, rot=(0, 0, 12))
    lathe(mb, [(3.1, -0.3), (3.0, 0.08), (2.6, 0.16), (0.0, 0.18)], 16, "M_PortalStone", Mt(0, 0, 0))
    torus(mb, P(0, 0, 0.17), 2.35, 0.05, "M_Crystal", segs=32, csegs=5)
    for k in range(9):
        a = 2 * math.pi * k / 9 + 0.3
        r = rng.uniform(2.2, 2.9)
        h = rng.uniform(0.5, 1.3)
        lathe(mb, [(0.0, 0.0), (0.14 * h, h * 0.35), (0.0, h)], 5, "M_Crystal", Mt(r * math.cos(a), r * math.sin(a), 0.1, rot=(rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 90))))
piece("PortalStones", portal_stones, (0, 0, 0), root, smooth=30)
def core(mb):
    lathe(mb, [(0.0, -0.04), (1.45, -0.02), (1.45, 0.02), (0.0, 0.04)], 32, "M_PortalCore", Mt(0, 0, 1.95, rot=(0, 90, 0)))
piece("PortalCore", core, (0, 0, 1.95), root)
for k in range(5):
    def crys(mb, k=k):
        a = 2 * math.pi * k / 5
        h = 0.7 + 0.15 * k % 3
        lathe(mb, [(0.0, -h * 0.5), (0.16, 0.0), (0.0, h * 0.5)], 5, "M_Crystal", Mt(0.3 * math.cos(a), 2.4 * math.sin(a) * 0.9, 3.0 + 0.7 * math.cos(a), rot=(15, 10, 0)))
    a = 2 * math.pi * k / 5
    piece("Crystal%d" % k, crys, (0.3 * math.cos(a), 2.4 * math.sin(a) * 0.9, 3.0 + 0.7 * math.cos(a)), root)
export_fbx(collect(root), MODELS + "/WD_Portal.fbx")

# lay the units out for a look (not exported again)
for i, n in enumerate(("WD_Scout", "WD_Soldier", "WD_Brute", "WD_Boss", "WD_Shell", "WD_Portal")):
    ob = bpy.data.objects[n]
    ob.location = U(-6 + i * 3.2 if i < 4 else (8 if i == 4 else 14), 0, 0)
save_blend("WD_Units")
print("units ok")
