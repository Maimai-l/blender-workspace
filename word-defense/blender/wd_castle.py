# wd_castle.py - castle (gate faces Unity +x) and cannon (barrel along Unity +z) -> WD_Castle.fbx, WD_Cannon.fbx
import sys, importlib, math, random
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import wdlib; importlib.reload(wdlib)
from wdlib import *
from mathutils import Vector, Matrix
import bpy

reset()
rng = random.Random(21)
P = lambda x, z, y: tuple(U(x, z, y))          # Unity-local (x, z, y) -> Blender tuple

def merlons(mb, x0, z0, x1, z1, y, mat_name="M_Stone", skip=None):
    a, b = Vector((x0, z0)), Vector((x1, z1))
    L = (b - a).length
    n = max(1, int(L / 0.78))
    d = (b - a) / L
    ang = math.degrees(math.atan2(d.y, d.x))
    for k in range(n):
        t = (k + 0.5) / n
        c = a + (b - a) * t
        if skip and skip(c):
            continue
        cbox(mb, P(c.x, c.y, y + 0.24), (0.44, 0.34, 0.48), mat_name, b=0.04, rot=(0, 0, ang + 180))

root = empty("WD_Castle")
# ---------------- base platform + ramp
mb = MB("Base", seed=1)
cbox(mb, P(0, 0, 0.0), (9.4, 9.4, 1.0), "M_StoneShade", b=0.14)
cbox(mb, P(0, 0, 0.42), (8.6, 8.6, 0.2), "M_StoneDark", b=0.06)
# ramp toward the road (+x)
v = [P(4.6, -1.25, 0.5), P(4.6, 1.25, 0.5), P(6.4, 1.25, 0.02), P(6.4, -1.25, 0.02),
     P(4.6, -1.25, -0.3), P(4.6, 1.25, -0.3), P(6.4, 1.25, -0.3), P(6.4, -1.25, -0.3)]
hexa(mb, v, "M_StoneShade")
for s in (-1, 1):
    cbox(mb, P(5.5, s * 1.38, 0.28), (1.9, 0.26, 0.5), "M_StoneDark", b=0.05)
base = mb.finish(smooth_angle=30); base.parent = root

# ---------------- curtain walls with a gate in the +x wall
H0, H1, R = 0.5, 3.0, 3.3
mb = MB("Walls", seed=2)
T = 0.62
cbox(mb, P(-R, 0, (H0 + H1) / 2), (T, 2 * R, H1 - H0), "M_Stone", b=0.05)
cbox(mb, P(0, -R, (H0 + H1) / 2), (2 * R, T, H1 - H0), "M_Stone", b=0.05)
cbox(mb, P(0, R, (H0 + H1) / 2), (2 * R, T, H1 - H0), "M_Stone", b=0.05)
GW, GH = 1.7, 2.1
for s in (-1, 1):
    zc = s * (GW / 2 + (R - GW / 2) / 2)
    cbox(mb, P(R, zc, (H0 + H1) / 2), (T, R - GW / 2, H1 - H0), "M_Stone", b=0.05)
cbox(mb, P(R, 0, (H0 + GH + H1) / 2 + 0.0), (T, GW + 0.02, H1 - (H0 + GH)), "M_Stone", b=0.03)
# walkway trim
for (x0, z0, x1, z1) in ((-R, -R, -R, R), (-R, -R, R, -R), (-R, R, R, R), (R, -R, R, R)):
    c = ((x0 + x1) / 2, (z0 + z1) / 2)
    sx = abs(x1 - x0) + T + 0.12; sz = abs(z1 - z0) + T + 0.12
    cbox(mb, P(c[0], c[1], H1 - 0.06), (max(sx, T + 0.12), max(sz, T + 0.12), 0.14), "M_StoneShade", b=0.03)
merlons(mb, -R - 0.2, -R + 1.0, -R - 0.2, R - 1.0, H1)
merlons(mb, -R + 1.0, -R - 0.2, R - 1.0, -R - 0.2, H1)
merlons(mb, -R + 1.0, R + 0.2, R - 1.0, R + 0.2, H1)
merlons(mb, R + 0.2, -R + 1.0, R + 0.2, R - 1.0, H1, skip=lambda c: abs(c.y) < 1.35)
# gate arch, door and studs
for s in (-1, 1):
    cbox(mb, P(R + 0.34, s * (GW / 2 + 0.16), H0 + GH / 2), (0.2, 0.32, GH + 0.05), "M_StoneShade", b=0.04)
cbox(mb, P(R + 0.34, 0, H0 + GH + 0.16), (0.22, GW + 0.64, 0.34), "M_StoneShade", b=0.04)
cbox(mb, P(R - 0.05, 0, H0 + GH / 2 - 0.02), (0.12, GW, GH), "M_Door", b=0.02)
for zz in (-0.45, 0.45):
    for yy in (0.6, 1.2, 1.8):
        sphere(mb, P(R + 0.03, zz, H0 + yy), 0.05, "M_Gold", segs=6, rings=4)
cbox(mb, P(R + 0.02, 0, H0 + GH * 0.55), (0.06, 0.06, GH * 0.95), "M_Gold", b=0.01)
walls = mb.finish(smooth_angle=30); walls.parent = root

# ---------------- gate banners (separate for wind)
flags = []
def banner(name, x, z, y_top, h, w, facing_x=True):
    mb = MB(name, seed=rng.randint(0, 999))
    v = [P(x, z - w / 2, y_top), P(x, z + w / 2, y_top), P(x, z + w / 2, y_top - h + 0.25), P(x, z, y_top - h), P(x, z - w / 2, y_top - h + 0.25)]
    vv = v + [tuple(Vector(q) + Vector(U(0.04, 0, 0))) for q in v]
    f = [[0, 1, 2, 3, 4], [9, 8, 7, 6, 5], [0, 5, 6, 1], [1, 6, 7, 2], [2, 7, 8, 3], [3, 8, 9, 4], [4, 9, 5, 0]]
    mb.add(vv, f, "M_Flag")
    sphere(mb, P(x + 0.02, z, y_top - h * 0.45), w * 0.18, "M_Gold", segs=8, rings=4, scl=(0.3, 1, 1))
    cyl(mb, P(x + 0.0, z, y_top + 0.02), 0.03, w + 0.2, 6, "M_WoodDark", rot=(90, 0, 0))
    ob = mb.finish(smooth_angle=30)
    set_origin(ob, U(x, z, y_top))
    ob.parent = root
    flags.append(ob)
banner("Banner_L", R + 0.36, -1.75, 2.85, 1.5, 0.62)
banner("Banner_R", R + 0.36, 1.75, 2.85, 1.5, 0.62)

# ---------------- towers
def tower(name, x, z):
    mb = MB(name, seed=rng.randint(0, 999))
    M = Matrix.Translation(U(x, z, 0))
    lathe(mb, [(1.12, H0 - 0.02), (1.06, 3.95)], 12, "M_Stone", M, phase=0.13)
    lathe(mb, [(1.06, 3.95), (1.26, 4.12), (1.26, 4.48), (1.18, 4.5)], 12, "M_StoneShade", M, phase=0.13)
    for k in range(8):
        a = 2 * math.pi * (k + 0.5) / 8
        cbox(mb, P(x + 1.18 * math.cos(a), z + 1.18 * math.sin(a), 4.72), (0.32, 0.26, 0.46), "M_Stone", b=0.04, rot=(0, 0, -math.degrees(a)))
    lathe(mb, [(1.42, 4.7), (1.28, 4.86), (0.0, 6.9)], 12, "M_Roof", M, cap_bottom=True, cap_top=False, phase=0.13)
    sphere(mb, P(x, z, 7.0), 0.13, "M_Gold", segs=8, rings=5)
    for k in range(3):
        a = 2 * math.pi * k / 3 + 0.4
        cbox(mb, P(x + 1.1 * math.cos(a), z + 1.1 * math.sin(a), 2.6), (0.12, 0.22, 0.55), "M_Door", b=0.02, rot=(0, 0, -math.degrees(a)))
    ob = mb.finish(smooth_angle=40)
    set_origin(ob, U(x, z, H0))
    ob.parent = root
    # pennant on a pole
    pm = MB(name + "_Flag", seed=rng.randint(0, 999))
    cyl(pm, P(x, z, 7.45), 0.025, 0.95, 6, "M_WoodDark")
    v = [P(x, z, 7.85), P(x + 0.0, z + 0.75, 7.72), P(x, z, 7.55)]
    vv = v + [tuple(Vector(q) + Vector(U(0.03, 0, 0))) for q in v]
    pm.add(vv, [[0, 1, 2], [5, 4, 3], [0, 3, 4, 1], [1, 4, 5, 2], [2, 5, 3, 0]], "M_Flag")
    fo = pm.finish(smooth_angle=30)
    set_origin(fo, U(x, z, 7.0))
    parent_keep(fo, ob)
    flags.append(fo)
    return ob
towers = [tower("Tower_NE", R, R), tower("Tower_NW", -R, R), tower("Tower_SE", R, -R), tower("Tower_SW", -R, -R)]

# ---------------- keep
mb = MB("Keep", seed=5)
KX, KZ, KS = -0.7, 0.0, 3.3
cbox(mb, P(KX, KZ, (H0 + 6.0) / 2), (KS, KS, 6.0 - H0), "M_Stone", b=0.06)
cbox(mb, P(KX, KZ, 5.95), (KS + 0.4, KS + 0.4, 0.4), "M_StoneShade", b=0.05)
for sx in (-1, 1):
    for sz in (-1, 1):
        cbox(mb, P(KX + sx * (KS / 2 + 0.02), KZ + sz * (KS / 2 + 0.02), 3.2), (0.42, 0.42, 5.4), "M_StoneShade", b=0.05)
v = [P(KX - KS / 2 - 0.35, KZ - KS / 2 - 0.35, 6.12), P(KX + KS / 2 + 0.35, KZ - KS / 2 - 0.35, 6.12),
     P(KX + KS / 2 + 0.35, KZ + KS / 2 + 0.35, 6.12), P(KX - KS / 2 - 0.35, KZ + KS / 2 + 0.35, 6.12), P(KX, KZ, 8.7)]
mb.add(v, [[0, 1, 4], [1, 2, 4], [2, 3, 4], [3, 0, 4], [3, 2, 1, 0]], "M_RoofDark")
sphere(mb, P(KX, KZ, 8.8), 0.16, "M_Gold", segs=8, rings=5)
cyl(mb, P(KX, KZ, 9.4), 0.03, 1.2, 6, "M_WoodDark")
for (fx, fz, rot) in ((KX + KS / 2 + 0.01, KZ, 0), (KX - KS / 2 - 0.01, KZ, 180), (KX, KZ + KS / 2 + 0.01, 90), (KX, KZ - KS / 2 - 0.01, -90)):
    for yy in (3.4, 4.9):
        for off in (-0.55, 0.55):
            ox = 0 if rot in (0, 180) else off
            oz = off if rot in (0, 180) else 0
            sz = (0.06, 0.34, 0.62) if rot in (0, 180) else (0.34, 0.06, 0.62)
            cbox(mb, P(fx + ox, fz + oz, yy), (sz[0], sz[1], sz[2]), "M_WindowLit", b=0.02)
keep = mb.finish(smooth_angle=30)
set_origin(keep, U(KX, KZ, H0)); keep.parent = root
# keep flag
pm = MB("Keep_Flag", seed=8)
v = [P(KX, KZ, 9.95), P(KX, KZ + 1.25, 9.75), P(KX, KZ + 1.25, 9.25), P(KX, KZ, 9.35)]
vv = v + [tuple(Vector(q) + Vector(U(0.04, 0, 0))) for q in v]
pm.add(vv, [[0, 1, 2, 3], [7, 6, 5, 4], [0, 4, 5, 1], [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0]], "M_Flag")
kf = pm.finish(smooth_angle=30); set_origin(kf, U(KX, KZ, 9.6)); parent_keep(kf, keep); flags.append(kf)

# ---------------- bastion above the gate for the cannon
mb = MB("Bastion", seed=9)
BX = R + 0.55
lathe(mb, [(0.55, 1.9), (1.18, 2.9), (1.25, 3.05)], 14, "M_StoneShade", Matrix.Translation(U(BX, 0, 0)))
lathe(mb, [(1.25, 3.05), (1.25, 3.12), (0.0, 3.12)], 14, "M_StoneDark", Matrix.Translation(U(BX, 0, 0)))
for k in range(9):
    a = -math.pi * 0.62 + (math.pi * 1.24) * k / 8
    cbox(mb, P(BX + 1.14 * math.cos(a), 1.14 * math.sin(a), 3.3), (0.26, 0.36, 0.38), "M_Stone", b=0.04, rot=(0, 0, -math.degrees(a)))
torus(mb, P(BX, 0, 3.13), 0.95, 0.04, "M_Gold", segs=24, csegs=5)
bastion = mb.finish(smooth_angle=35); bastion.parent = root
cannon_mount = empty("CannonMount", U(BX, 0, 3.12), parent=None)
cannon_mount.parent = root
export_fbx(collect(root), MODELS + "/WD_Castle.fbx")
save_blend("WD_Castle")

# ---------------- cannon (separate file), origin at the mount
reset()
croot = empty("WD_Cannon")
mb = MB("CannonBase", seed=11)
lathe(mb, [(0.78, 0.0), (0.8, 0.1), (0.72, 0.18), (0.0, 0.18)], 18, "M_Steel")
torus(mb, (0, 0, 0.12), 0.79, 0.035, "M_Gold", segs=28, csegs=5)
cb = mb.finish(smooth_angle=40); parent_keep(cb, croot)
mb = MB("CannonYaw", seed=12)
for s in (-1, 1):
    v = []
    prof = [(-0.5, 0.18), (0.45, 0.18), (0.42, 0.55), (0.12, 0.84), (-0.2, 0.84), (-0.5, 0.45)]
    for (zz, yy) in prof:
        v.append(P(s * 0.38 - 0.08, zz, yy))
    for (zz, yy) in prof:
        v.append(P(s * 0.38 + 0.08, zz, yy))
    n = len(prof)
    f = [list(range(n)), list(reversed(range(n, 2 * n)))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    mb.add(v, f, "M_SteelLight")
    sphere(mb, P(s * 0.47, 0.0, 0.62), 0.07, "M_Gold", segs=8, rings=4)
cbox(mb, P(0, -0.05, 0.3), (0.66, 0.8, 0.22), "M_Steel", b=0.05)
cy = mb.finish(smooth_angle=35)
set_origin(cy, U(0, 0, 0.18)); parent_keep(cy, croot)
mb = MB("CannonBarrel", seed=13)
R90 = Matrix.Translation(U(0, 0, 0.62)) @ rot_m((90, 0, 0))   # lathe Z -> Unity +z
lathe(mb, [(0.0, -0.66), (0.1, -0.64), (0.12, -0.56), (0.05, -0.5), (0.27, -0.48), (0.29, -0.3), (0.25, 0.1), (0.2, 0.72),
           (0.25, 0.78), (0.26, 0.92), (0.15, 0.94), (0.15, 0.6)], 16, "M_Steel", R90, cap_bottom=False, cap_top=True)
for zz, rr in ((-0.32, 0.3), (0.12, 0.26), (0.8, 0.27)):
    torus(mb, (0, 0, 0), rr, 0.035, "M_Gold", segs=20, csegs=5, M=Matrix.Translation(U(0, zz, 0.62)) @ rot_m((90, 0, 0)))
lathe(mb, [(0.14, 0.86), (0.0, 0.86)], 12, "M_Door", R90, cap_bottom=False, cap_top=False)
cyl(mb, P(0, 0.0, 0.62), 0.07, 0.86, 8, "M_Gold", rot=(0, 90, 0))
cbar = mb.finish(smooth_angle=45)
set_origin(cbar, U(0, 0, 0.62))
parent_keep(cbar, cy)
muzzle = empty("Muzzle", U(0, 0.98, 0.62)); parent_keep(muzzle, cbar)
export_fbx(collect(croot), MODELS + "/WD_Cannon.fbx")
save_blend("WD_Cannon")
print("castle + cannon ok")
