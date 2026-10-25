
# chars.py - rig + character meshes
import bpy, math, random
from mathutils import Vector, Matrix
import dlib
from dlib import MB, cbox, box_mm, hexa, lathe, cyl, sphere, torus, limb, trs, rot_m

BONES = [
    ("root", (0, 0, 0), (0, 0, 0.2), None),
    ("hips", (0, 0, 0.98), (0, 0, 1.08), "root"),
    ("spine", (0, 0, 1.08), (0, 0, 1.26), "hips"),
    ("chest", (0, 0, 1.26), (0, 0, 1.46), "spine"),
    ("neck", (0, 0, 1.46), (0, 0, 1.56), "chest"),
    ("head", (0, 0, 1.56), (0, 0, 1.80), "neck"),
    ("jaw", (0, -0.03, 1.63), (0, -0.10, 1.585), "head"),
    ("cape1", (0, 0.16, 1.44), (0, 0.20, 1.03), "chest"),
    ("cape2", (0, 0.20, 1.03), (0, 0.23, 0.62), "cape1"),
]
for side, s in (("L", 1), ("R", -1)):
    BONES += [
        ("shoulder." + side, (s * 0.05, 0, 1.42), (s * 0.18, 0, 1.43), "chest"),
        ("upperarm." + side, (s * 0.19, 0, 1.42), (s * 0.25, 0.0, 1.15), "shoulder." + side),
        ("forearm." + side, (s * 0.25, 0.0, 1.15), (s * 0.28, -0.03, 0.89), "upperarm." + side),
        ("hand." + side, (s * 0.28, -0.03, 0.89), (s * 0.29, -0.04, 0.79), "forearm." + side),
        ("thigh." + side, (s * 0.10, 0, 0.96), (s * 0.11, 0, 0.53), "hips"),
        ("shin." + side, (s * 0.11, 0, 0.53), (s * 0.11, 0.03, 0.10), "thigh." + side),
        ("foot." + side, (s * 0.11, 0.03, 0.10), (s * 0.11, -0.12, 0.02), "shin." + side),
    ]

def build_rig(name="Rig"):
    arm = bpy.data.armatures.new(name + "_Data")
    rig = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    ebs = {}
    for n, h, t, p in BONES:
        eb = arm.edit_bones.new(n)
        eb.head = h; eb.tail = t
        y = (Vector(t) - Vector(h)).normalized()
        if abs(y.x) > 0.7:
            eb.align_roll(Vector((0, 0, 1)))
        else:
            eb.align_roll(Vector((1, 0, 0)).cross(y))
        ebs[n] = eb
    for n, h, t, p in BONES:
        if p:
            ebs[n].parent = ebs[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_mode = 'XYZ'
    return rig

def attach(ob, rig):
    ob.parent = rig
    m = ob.modifiers.new("Armature", 'ARMATURE')
    m.object = rig
    return ob

def zblend(lo_bone, hi_bone, z0, z1):
    def f(co):
        t = min(1.0, max(0.0, (co.z - z0) / (z1 - z0)))
        out = []
        if t < 1: out.append((lo_bone, 1 - t))
        if t > 0: out.append((hi_bone, t))
        return out
    return f

def flap_weights(side_bone, ztop, zbot, amt=0.85):
    def f(co):
        t = min(1.0, max(0.0, (ztop - co.z) / (ztop - zbot)))
        w = amt * t
        out = [("hips", 1 - w)]
        if w > 0: out.append((side_bone, w))
        return out
    return f

def flap(mb, x0, x1, ztop, zbot, y, th, mat, group, nz=4, rag=None):
    # thick strip of quads subdivided along z
    verts = []
    for j in range(nz + 1):
        z = ztop + (zbot - ztop) * j / nz
        for xx in (x0, x1):
            zz = z
            if rag and j == nz:
                zz += rag()
            verts.append((xx, y - th / 2, zz)); verts.append((xx, y + th / 2, zz))
    faces = []
    for j in range(nz):
        a = j * 4; b = (j + 1) * 4
        faces += [[a, a + 2, b + 2, b], [a + 1, b + 1, b + 3, a + 3], [a, b, b + 1, a + 1], [a + 2, a + 3, b + 3, b + 2]]
    faces += [[0, 1, 3, 2], [nz * 4, nz * 4 + 2, nz * 4 + 3, nz * 4 + 1]]
    return mb.add(verts, faces, mat, group=group)

def cape_sheet(mb, outer_mat, inner_mat, ztop=1.45, zbot=0.6, wtop=0.46, wbot=0.62, nx=6, ny=12, rag=0.0, seed=3):
    rng = random.Random(seed)
    def W(co):
        t = (ztop - co.z) / (ztop - zbot)
        c = max(0.0, 1 - t / 0.12)
        c2 = min(1.0, max(0.0, (t - 0.42) / 0.3))
        c1 = max(0.0, 1 - c - c2)
        return [(n, w) for n, w in (("chest", c), ("cape1", c1), ("cape2", c2)) if w > 0]
    ragv = [rng.uniform(0, rag) for _ in range(nx + 1)]
    for layer, mat in ((0, outer_mat), (1, inner_mat)):
        verts = []
        for j in range(ny + 1):
            v = j / ny
            for i in range(nx + 1):
                u = i / nx
                hw = (wtop + (wbot - wtop) * v) / 2
                x = (u - 0.5) * 2 * hw
                z = ztop + (zbot - ztop) * v + (ragv[i] if j == ny else 0)
                y = 0.165 + 0.07 * v - 0.085 * (x / hw) ** 2 + (0.008 if layer == 0 else 0.0)
                verts.append((x, y, z))
        faces = []
        for j in range(ny):
            for i in range(nx):
                a = j * (nx + 1) + i
                q = [a, a + 1, a + nx + 2, a + nx + 1]
                faces.append(list(reversed(q)) if layer == 1 else q)
        mb.add(verts, faces, mat, recalc=False, group=W)

# ------------------------------------------------------------------ knight
def knight_mesh(name="Knight_Body"):
    mb = MB(name, seed=5)
    for side, s in (("L", 1), ("R", -1)):
        F, S, T, U, A, H = "foot." + side, "shin." + side, "thigh." + side, "upperarm." + side, "forearm." + side, "hand." + side
        cbox(mb, (s * 0.11, -0.04, 0.05), (0.11, 0.24, 0.1), "M_Leather", 0.035, group=F)
        sphere(mb, (s * 0.11, -0.15, 0.048), 0.056, "M_Leather", 12, 6, (1.0, 1.15, 0.85), group=F)
        box_mm(mb, (s * 0.11 - 0.06, -0.16, 0.0), (s * 0.11 + 0.06, 0.08, 0.025), "M_WoodDark", 0.0, group=F)
        limb(mb, (s * 0.11, 0.02, 0.06), (s * 0.11, 0.015, 0.31), 0.064, 0.061, 12, "M_Leather", group=S)
        torus(mb, (s * 0.11, 0.012, 0.3), 0.066, 0.014, "M_Leather", 14, 5, group=S)
        limb(mb, (s * 0.11, -0.004, 0.28), (s * 0.11, 0.0, 0.5), 0.06, 0.069, 12, "M_Steel", group=S)
        sphere(mb, (s * 0.11, -0.028, 0.53), 0.07, "M_Steel", 12, 8, (1.0, 0.92, 1.0), group=S)
        sphere(mb, (s * 0.11, -0.095, 0.53), 0.018, "M_Gold", 8, 5, group=S)
        limb(mb, (s * 0.103, 0, 0.95), (s * 0.11, 0, 0.56), 0.086, 0.07, 12, "M_Leather", group=T)
        box_mm(mb, (s * 0.11 - 0.07, -0.1, 0.62), (s * 0.11 + 0.07, -0.06, 0.82), "M_SteelDark", 0.02, group=T)
        sphere(mb, (s * 0.205, 0.0, 1.425), 0.108, "M_Steel", 14, 8, (1.0, 1.05, 0.85), group=U)
        torus(mb, (s * 0.205, 0.0, 1.39), 0.1, 0.012, "M_Gold", 18, 5, (0, s * 18, 0), group=U)
        torus(mb, (s * 0.215, 0.0, 1.33), 0.075, 0.02, "M_Steel", 16, 6, (0, s * 15, 0), group=U)
        limb(mb, (s * 0.19, 0, 1.4), (s * 0.25, 0, 1.15), 0.053, 0.047, 10, "M_ClothDark", group=U)
        sphere(mb, (s * 0.25, 0.008, 1.15), 0.052, "M_Steel", 10, 7, group=A)
        cbox(mb, (s * 0.255, 0.05, 1.15), (0.06, 0.03, 0.07), "M_Steel", 0.012, group=A)
        limb(mb, (s * 0.25, 0, 1.13), (s * 0.279, -0.028, 0.92), 0.048, 0.043, 12, "M_Steel", group=A)
        limb(mb, (s * 0.278, -0.027, 0.935), (s * 0.282, -0.032, 0.895), 0.048, 0.058, 12, "M_Steel", group=A)
        cbox(mb, (s * 0.287, -0.04, 0.84), (0.075, 0.095, 0.11), "M_Leather", 0.025, group=H)
        cbox(mb, (s * 0.32, -0.04, 0.85), (0.02, 0.07, 0.07), "M_SteelDark", 0.008, group=H)
        cbox(mb, (s * 0.262, -0.085, 0.86), (0.03, 0.035, 0.06), "M_Leather", 0.01, group=H)
        flap(mb, s * 0.005, s * 0.165, 0.985, 0.6, -0.135, 0.016, "M_ClothBlue", flap_weights(T, 0.985, 0.6))
        flap(mb, s * 0.005, s * 0.165, 0.985, 0.6, 0.13, 0.016, "M_ClothBlue", flap_weights(T, 0.985, 0.6))
        flap(mb, s * 0.005, s * 0.165, 0.63, 0.6, -0.145, 0.012, "M_Gold", flap_weights(T, 0.985, 0.6), nz=1)
    lathe(mb, [(0.15, 0.86), (0.165, 0.95), (0.165, 1.0)], 14, "M_Leather", group="hips")
    lathe(mb, [(0.168, 0.965), (0.172, 0.975), (0.172, 1.045), (0.168, 1.055)], 16, "M_Leather", Matrix.Diagonal((1, 0.82, 1, 1)), group="hips")
    cbox(mb, (0, -0.145, 1.01), (0.07, 0.02, 0.06), "M_Gold", 0.008, group="hips")
    lathe(mb, [(0.15, 0.98), (0.155, 1.1), (0.165, 1.22), (0.17, 1.3)], 14, "M_ClothBlue", Matrix.Diagonal((1, 0.78, 1, 1)), group=zblend("hips", "spine", 1.0, 1.1))
    lathe(mb, [(0.16, 1.13), (0.186, 1.2), (0.207, 1.3), (0.207, 1.38), (0.19, 1.44), (0.14, 1.48), (0.085, 1.5)], 16, "M_Steel",
          Matrix.Diagonal((1, 0.8, 1, 1)), group=zblend("spine", "chest", 1.17, 1.27))
    lathe(mb, [(0.162, 1.125), (0.17, 1.14), (0.172, 1.16), (0.165, 1.17)], 16, "M_Gold", Matrix.Diagonal((1, 0.8, 1, 1)), group="spine")
    box_mm(mb, (-0.012, -0.172, 1.2), (0.012, -0.15, 1.44), "M_Steel", 0.008, group="chest")
    torus(mb, (0, -0.168, 1.34), 0.05, 0.009, "M_Gold", 18, 5, (90, 0, 0), group="chest")
    cbox(mb, (0, -0.17, 1.34), (0.016, 0.01, 0.12), "M_Gold", 0.0, group="chest")
    cbox(mb, (0, -0.17, 1.35), (0.09, 0.01, 0.016), "M_Gold", 0.0, group="chest")
    lathe(mb, [(0.125, 1.44), (0.11, 1.5), (0.088, 1.545)], 14, "M_Steel", group="chest")
    limb(mb, (0, 0, 1.47), (0, 0, 1.585), 0.056, 0.052, 10, "M_ClothDark", group="neck")
    helm = [(0.0, 1.88), (0.05, 1.877), (0.095, 1.855), (0.122, 1.815), (0.132, 1.745), (0.132, 1.665), (0.126, 1.6), (0.112, 1.56), (0.096, 1.545)]
    lathe(mb, helm, 18, "M_Steel", Matrix.Diagonal((1, 1.12, 1, 1)), group="head")
    cbox(mb, (0, -0.142, 1.705), (0.17, 0.03, 0.022), "M_Socket", 0.004, group="head")
    for k in range(5):
        cbox(mb, (-0.04 + k * 0.02, -0.142, 1.64), (0.008, 0.025, 0.03), "M_Socket", 0.0, group="head")
    box_mm(mb, (-0.013, -0.152, 1.6), (0.013, -0.13, 1.84), "M_Steel", 0.008, group="head")
    torus(mb, (0, 0, 1.775), 0.13, 0.009, "M_Gold", 24, 5, M=Matrix.Diagonal((1, 1.12, 1, 1)), group="head")
    for k in range(8):
        t = k / 7.0
        y = -0.1 + 0.27 * t
        z = 1.87 + 0.035 * math.sin(t * math.pi) - 0.06 * t * t
        sphere(mb, (0, y, z), 0.04 - 0.012 * t, "M_ClothRed", 10, 6, (0.55, 1.0, 1.6), group="head")
    limb(mb, (0, 0.17, 1.8), (0, 0.24, 1.6), 0.03, 0.012, 8, "M_ClothRed", group="head")
    # sword in right hand (grip along Y, blade forward -Y)
    sx, sz = -0.29, 0.835
    W = "hand.R"
    sphere(mb, (sx, 0.08, sz), 0.03, "M_Gold", 10, 6, group=W)
    limb(mb, (sx, 0.06, sz), (sx, -0.088, sz), 0.019, 0.019, 10, "M_Leather", group=W)
    cbox(mb, (sx, -0.1, sz), (0.03, 0.032, 0.23), "M_Gold", 0.008, group=W)
    for dz in (-0.115, 0.115):
        sphere(mb, (sx, -0.1, sz + dz), 0.022, "M_Gold", 8, 5, group=W)
    hexa(mb, [(sx - 0.007, -0.116, sz - 0.028), (sx + 0.007, -0.116, sz - 0.028), (sx + 0.007, -0.116, sz + 0.028), (sx - 0.007, -0.116, sz + 0.028),
              (sx - 0.005, -0.9, sz - 0.02), (sx + 0.005, -0.9, sz - 0.02), (sx + 0.005, -0.9, sz + 0.02), (sx - 0.005, -0.9, sz + 0.02)], "M_Steel", group=W)
    hexa(mb, [(sx - 0.005, -0.9, sz - 0.02), (sx + 0.005, -0.9, sz - 0.02), (sx + 0.005, -0.9, sz + 0.02), (sx - 0.005, -0.9, sz + 0.02),
              (sx - 0.0005, -0.99, sz - 0.001), (sx + 0.0005, -0.99, sz - 0.001), (sx + 0.0005, -0.99, sz + 0.001), (sx - 0.0005, -0.99, sz + 0.001)], "M_Steel", group=W)
    box_mm(mb, (sx - 0.0075, -0.6, sz - 0.004), (sx + 0.0075, -0.12, sz + 0.004), "M_SteelDark", 0.0, group=W)
    cape_sheet(mb, "M_ClothBlue", "M_ClothRed")
    return mb.finish(smooth_angle=42)

# ------------------------------------------------------------------ skeleton
def skull_parts(mb, scale=1.0, eye=0.016, M=None):
    c = Vector((0, 0.0, 1.69))
    sphere(mb, c + Vector((0, 0.01, 0.0)), 0.11 * scale, "M_Bone", 16, 10, (0.92, 1.1, 1.0), group="head")
    cbox(mb, (0, -0.085, 1.632), (0.1, 0.06, 0.05), "M_Bone", 0.02, group="head")
    for sx in (-1, 1):
        sphere(mb, (sx * 0.04, -0.097, 1.69), 0.031, "M_Socket", 10, 6, (1, 0.6, 1), group="head")
        sphere(mb, (sx * 0.04, -0.105, 1.69), eye, "M_EyeGlow", 8, 6, (1, 0.6, 1), group="head")
        cbox(mb, (sx * 0.075, -0.05, 1.64), (0.03, 0.06, 0.05), "M_Bone", 0.012, group="head")
    cbox(mb, (0, -0.112, 1.655), (0.02, 0.02, 0.03), "M_Socket", 0.004, group="head")
    for i in range(6):
        cbox(mb, (-0.035 + i * 0.014, -0.112, 1.612), (0.01, 0.012, 0.018), "M_Bone", 0.002, group="head")
    cbox(mb, (0, -0.07, 1.585), (0.095, 0.075, 0.028), "M_Bone", 0.01, group="jaw")
    for sx in (-1, 1):
        cbox(mb, (sx * 0.045, -0.035, 1.61), (0.015, 0.04, 0.05), "M_Bone", 0.006, group="jaw")
    for i in range(6):
        cbox(mb, (-0.035 + i * 0.014, -0.105, 1.6), (0.01, 0.012, 0.016), "M_Bone", 0.002, group="jaw")

def skeleton_mesh(name="Skeleton_Body", warden=False):
    mb = MB(name, seed=9 if not warden else 19)
    rng = random.Random(4)
    skull_parts(mb, 1.0, 0.02 if warden else 0.016)
    for i in range(3):
        cyl(mb, (0, 0.01, 1.48 + i * 0.035), 0.024, 0.026, 8, "M_Bone", group="neck")
    for i in range(8):
        z = 0.99 + i * 0.06
        g = "spine" if z < 1.25 else "chest"
        cyl(mb, (0, 0.04, z), 0.028, 0.04, 8, "M_Bone", group=g)
        cbox(mb, (0, 0.075, z), (0.02, 0.04, 0.025), "M_Bone", 0.006, group=g)
    for i in range(5):
        z = 1.42 - i * 0.045
        R = 0.15 - abs(i - 1.2) * 0.01
        for sgn in (1, -1):
            start = -70 if sgn > 0 else 90
            torus(mb, (0, 0.0, z), R, 0.011, "M_Bone", 16, 5, (0, 0, start), arc=0.44,
                  M=Matrix.Translation((0, 0.02, 0)) @ Matrix.Diagonal((1, 0.78, 1, 1)) @ rot_m((-10, 0, 0)), group="chest")
    cbox(mb, (0, -0.115, 1.34), (0.03, 0.016, 0.17), "M_Bone", 0.006, group="chest")
    for sx in (-1, 1):
        limb(mb, (sx * 0.02, -0.08, 1.45), (sx * 0.17, -0.0, 1.44), 0.012, 0.011, 6, "M_Bone", group="chest")
        cbox(mb, (sx * 0.085, 0.1, 1.37), (0.085, 0.016, 0.12), "M_Bone", 0.01, (0, sx * 10, sx * 15), group="chest")
        cbox(mb, (sx * 0.08, 0.0, 0.99), (0.12, 0.05, 0.1), "M_Bone", 0.02, (0, sx * 25, 0), group="hips")
    cbox(mb, (0, 0.05, 0.96), (0.06, 0.04, 0.1), "M_Bone", 0.015, group="hips")
    torus(mb, (0, -0.03, 0.9), 0.065, 0.016, "M_Bone", 12, 5, (90, 0, 0), arc=0.5, group="hips")
    for side, s in (("L", 1), ("R", -1)):
        F, S, T, U, A, H = "foot." + side, "shin." + side, "thigh." + side, "upperarm." + side, "forearm." + side, "hand." + side
        limb(mb, (s * 0.1, 0, 0.94), (s * 0.11, 0, 0.56), 0.026, 0.024, 8, "M_Bone", group=T)
        sphere(mb, (s * 0.1, 0, 0.95), 0.036, "M_Bone", 8, 6, group=T)
        sphere(mb, (s * 0.11, 0, 0.56), 0.034, "M_Bone", 8, 6, group=T)
        sphere(mb, (s * 0.11, -0.035, 0.53), 0.026, "M_Bone", 8, 5, group=S)
        limb(mb, (s * 0.11, 0.0, 0.52), (s * 0.11, 0.025, 0.12), 0.022, 0.018, 8, "M_Bone", group=S)
        limb(mb, (s * 0.135, 0.01, 0.5), (s * 0.135, 0.03, 0.14), 0.011, 0.01, 6, "M_Bone", group=S)
        sphere(mb, (s * 0.11, 0.03, 0.1), 0.03, "M_Bone", 8, 5, group=S)
        cbox(mb, (s * 0.11, 0.03, 0.045), (0.05, 0.07, 0.05), "M_Bone", 0.015, group=F)
        for k in range(3):
            limb(mb, (s * (0.09 + k * 0.02), -0.0, 0.035), (s * (0.085 + k * 0.025), -0.13, 0.015), 0.009, 0.008, 6, "M_Bone", group=F)
        limb(mb, (s * 0.19, 0, 1.41), (s * 0.25, 0, 1.16), 0.02, 0.018, 8, "M_Bone", group=U)
        sphere(mb, (s * 0.19, 0, 1.415), 0.032, "M_Bone", 8, 6, group=U)
        sphere(mb, (s * 0.25, 0, 1.155), 0.027, "M_Bone", 8, 5, group=A)
        for dy in (-0.012, 0.012):
            limb(mb, (s * 0.25, dy, 1.14), (s * 0.28, -0.03 + dy, 0.9), 0.012, 0.011, 6, "M_Bone", group=A)
        cbox(mb, (s * 0.285, -0.035, 0.86), (0.025, 0.06, 0.05), "M_Bone", 0.008, group=H)
        for k in range(4):
            limb(mb, (s * 0.285, -0.06 + k * 0.016, 0.84), (s * 0.29, -0.07 + k * 0.018, 0.775), 0.007, 0.006, 5, "M_Bone", group=H)
        limb(mb, (s * 0.27, -0.06, 0.85), (s * 0.26, -0.095, 0.81), 0.008, 0.006, 5, "M_Bone", group=H)
    # loincloth
    rag = lambda: rng.uniform(-0.04, 0.06)
    flap(mb, -0.11, 0.11, 0.97, 0.68, -0.07, 0.012, "M_ClothDark", flap_weights("thigh.L", 0.97, 0.68, 0.0), nz=3, rag=rag)
    flap(mb, -0.12, 0.12, 0.97, 0.7, 0.08, 0.012, "M_ClothDark", flap_weights("thigh.R", 0.97, 0.7, 0.0), nz=3, rag=rag)
    lathe(mb, [(0.13, 0.95), (0.135, 0.99)], 12, "M_Leather", Matrix.Diagonal((1, 0.75, 1, 1)), group="hips")
    sx, sz = -0.29, 0.835
    W = "hand.R"
    if not warden:
        limb(mb, (sx, 0.06, sz), (sx, -0.085, sz), 0.017, 0.017, 8, "M_Leather", group=W)
        sphere(mb, (sx, 0.07, sz), 0.024, "M_RustIron", 8, 5, group=W)
        cbox(mb, (sx, -0.095, sz), (0.026, 0.028, 0.18), "M_RustIron", 0.006, group=W)
        hexa(mb, [(sx - 0.007, -0.108, sz - 0.03), (sx + 0.007, -0.108, sz - 0.03), (sx + 0.007, -0.108, sz + 0.03), (sx - 0.007, -0.108, sz + 0.03),
                  (sx - 0.005, -0.72, sz - 0.022), (sx + 0.005, -0.72, sz - 0.022), (sx + 0.005, -0.72, sz + 0.03), (sx - 0.005, -0.72, sz + 0.03)], "M_RustIron", group=W)
        hexa(mb, [(sx - 0.005, -0.72, sz - 0.022), (sx + 0.005, -0.72, sz - 0.022), (sx + 0.005, -0.72, sz + 0.03), (sx - 0.005, -0.72, sz + 0.03),
                  (sx - 0.001, -0.8, sz + 0.02), (sx + 0.001, -0.8, sz + 0.02), (sx + 0.001, -0.8, sz + 0.024), (sx - 0.001, -0.8, sz + 0.024)], "M_RustIron", group=W)
        # round shield on left forearm
        Ms = Matrix.Translation((0.335, -0.05, 1.0)) @ rot_m((0, 90, -30))
        lathe(mb, [(0.0, -0.015), (0.27, -0.015), (0.27, 0.015), (0.0, 0.02)], 18, "M_Wood", Ms, group="forearm.L")
        torus(mb, (0, 0, 0), 0.27, 0.016, "M_RustIron", 24, 5, M=Ms, group="forearm.L")
        sphere(mb, (0, 0, 0.02), 0.06, "M_RustIron", 10, 6, (1, 1, 0.6), M=Ms, group="forearm.L")
        for k in range(2):
            cbox(mb, (0, (k - 0.5) * 0.24, 0.018), (0.5, 0.04, 0.008), "M_RustIron", 0.0, M=Ms, group="forearm.L")
    else:
        # warden armour
        helm = [(0.0, 1.835), (0.075, 1.83), (0.112, 1.785), (0.125, 1.72), (0.124, 1.68), (0.118, 1.665)]
        lathe(mb, helm, 16, "M_Iron", Matrix.Diagonal((1, 1.12, 1, 1)), cap_bottom=False, group="head")
        torus(mb, (0, 0, 1.675), 0.122, 0.012, "M_RustIron", 20, 5, M=Matrix.Diagonal((1, 1.12, 1, 1)), group="head")
        for sxx in (-1, 1):
            pts = [(sxx * 0.11, 0.0, 1.75), (sxx * 0.17, -0.02, 1.79), (sxx * 0.22, -0.04, 1.86), (sxx * 0.245, -0.055, 1.95), (sxx * 0.235, -0.07, 2.03)]
            rads = [0.04, 0.033, 0.025, 0.016, 0.006]
            for k in range(len(pts) - 1):
                limb(mb, pts[k], pts[k + 1], rads[k], rads[k + 1], 8, "M_Bone", group="head")
            sxx2 = sxx
            sphere(mb, (sxx2 * 0.215, 0.0, 1.43), 0.13, "M_Iron", 14, 8, (1.0, 1.05, 0.8), group="upperarm.L" if sxx > 0 else "upperarm.R")
            for k in range(3):
                lathe(mb, [(0.025, 0), (0.0, 0.1)], 8, "M_Bone", trs((sxx * (0.2 + k * 0.035), -0.04 + k * 0.04, 1.52), (0, sxx * 25, 0)), cap_top=False,
                      group="upperarm.L" if sxx > 0 else "upperarm.R")
        lathe(mb, [(0.14, 1.28), (0.17, 1.34), (0.168, 1.43), (0.11, 1.48)], 16, "M_Iron", Matrix.Diagonal((1, 0.78, 1, 1)), group="chest")
        box_mm(mb, (-0.015, -0.142, 1.29), (0.015, -0.12, 1.46), "M_RustIron", 0.006, group="chest")
        lathe(mb, [(0.14, 0.95), (0.145, 1.02)], 14, "M_Leather", Matrix.Diagonal((1, 0.8, 1, 1)), group="hips")
        sphere(mb, (0, -0.125, 0.985), 0.035, "M_Bone", 8, 6, (1, 0.8, 1.1), group="hips")
        cape_sheet(mb, "M_ClothRed", "M_ClothDark", ztop=1.46, zbot=0.42, wtop=0.5, wbot=0.7, rag=0.12, seed=7)
        # great axe: haft along Y
        limb(mb, (sx, 0.36, sz), (sx, -0.78, sz), 0.022, 0.022, 8, "M_WoodDark", group=W)
        for yy in (-0.05, 0.05, 0.2):
            torus(mb, (sx, yy, sz), 0.024, 0.006, "M_Leather", 10, 4, (90, 0, 0), group=W)
        lathe(mb, [(0.0, 0.0), (0.03, 0.0), (0.0, 0.1)], 8, "M_RustIron", trs((sx, 0.36, sz), (-90, 0, 0)), group=W)
        for dz in (1, -1):
            hexa(mb, [(sx - 0.012, -0.6, sz + dz * 0.02), (sx + 0.012, -0.6, sz + dz * 0.02), (sx + 0.012, -0.76, sz + dz * 0.02), (sx - 0.012, -0.76, sz + dz * 0.02),
                      (sx - 0.004, -0.53, sz + dz * 0.25), (sx + 0.004, -0.53, sz + dz * 0.25), (sx + 0.004, -0.83, sz + dz * 0.25), (sx - 0.004, -0.83, sz + dz * 0.25)], "M_RustIron", group=W)
        lathe(mb, [(0.0, 0.0), (0.028, 0.0), (0.0, 0.14)], 8, "M_RustIron", trs((sx, -0.78, sz), (90, 0, 0)), group=W)
    return mb.finish(smooth_angle=45)
