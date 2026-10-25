
# kit_props.py - props and gameplay set pieces
import bpy, math, random
from mathutils import Vector, Matrix
import dlib, kit_env
from dlib import MB, cbox, box_mm, hexa, lathe, cyl, sphere, torus, quad_strip, limb, trs, rot_m
from kit_env import pick, STONE_MIX, FLOOR_MIX, arch_inner_z

def set_origin(ob, world_pt):
    """Move object origin to world_pt keeping geometry in place."""
    off = Vector(world_pt)
    ob.data.transform(Matrix.Translation(-off))
    ob.location = off

# ---------------- great door ----------------
def door_leaf(name, sign, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    n = 7; x_in, x_out = 0.006, 1.68
    w = (x_out - x_in) / n
    t = 0.065
    for i in range(n):
        a = x_in + i * w + 0.003; b = x_in + (i + 1) * w - 0.003
        xa, xb = sign * a, sign * b
        za, zb = arch_inner_z(xa) - 0.03, arch_inner_z(xb) - 0.03
        jt = rng.uniform(-0.004, 0.004)
        pts = [(xa, -t + jt, 0.03), (xb, -t + jt, 0.03), (xb, t, 0.03), (xa, t, 0.03),
               (xa, -t + jt, za), (xb, -t + jt, zb), (xb, t, zb), (xa, t, za)]
        hexa(mb, pts, "M_Wood")
    for zc in (0.55, 1.65, 2.75):
        for yy in (-1, 1):
            x0, x1 = sign * 0.05, sign * 1.73
            box_mm(mb, (min(x0, x1), yy * t + (-0.022 if yy < 0 else 0), zc - 0.065), (max(x0, x1), yy * t + (0 if yy < 0 else 0.022), zc + 0.065), "M_Iron", 0.006)
        for k in range(n):
            xc = sign * (x_in + (k + 0.5) * w)
            cbox(mb, (xc, -t - 0.034, zc), (0.045, 0.026, 0.045), "M_Iron", 0.008)
        cyl(mb, (sign * 1.70, 0, zc), 0.045, 0.2, 10, "M_Iron")
    lathe(mb, [(0.0, 0), (0.08, 0), (0.08, 0.012), (0.0, 0.016)], 16, "M_Iron", trs((sign * 0.32, -t, 1.25), (90, 0, 0)))
    torus(mb, (sign * 0.32, -t - 0.03, 1.17), 0.09, 0.015, "M_Iron", 16, 6, (90, 0, 0))
    for dx in (-0.075, 0.075):
        cbox(mb, (sign * 0.9 + dx, -t - 0.07, 1.93), (0.035, 0.14, 0.22), "M_Iron", 0.006)
    cbox(mb, (sign * 0.9, -t - 0.07, 1.835), (0.19, 0.14, 0.03), "M_Iron", 0.006)
    ob = mb.finish()
    set_origin(ob, (sign * 1.70, 0, 0))
    return ob

def door_bar():
    mb = MB("Door_Bar", seed=5)
    cbox(mb, (0, -0.165, 1.93), (2.6, 0.07, 0.15), "M_Iron", 0.012)
    for x in (-1.25, 1.25):
        cbox(mb, (x, -0.165, 1.93), (0.06, 0.09, 0.19), "M_Iron", 0.01)
    ob = mb.finish(); set_origin(ob, (0, -0.165, 1.93)); return ob

def door_lock():
    mb = MB("Door_Lock", seed=6)
    torus(mb, (0, -0.165, 1.93), 0.075, 0.016, "M_Iron", 16, 6, (90, 0, 0), arc=0.55)
    cyl(mb, (-0.072, -0.165, 1.86), 0.016, 0.12, 8, "M_Iron")
    cyl(mb, (0.072, -0.165, 1.86), 0.016, 0.12, 8, "M_Iron")
    cbox(mb, (0, -0.165, 1.69), (0.27, 0.11, 0.28), "M_Iron", 0.03)
    lathe(mb, [(0.0, 0), (0.095, 0), (0.095, 0.014), (0.0, 0.018)], 20, "M_Gold", trs((0, -0.22, 1.69), (90, 0, 0)))
    torus(mb, (0, -0.24, 1.69), 0.075, 0.009, "M_RuneLock", 24, 5, (90, 0, 0))
    for k in range(6):
        a = k * math.pi / 3
        cbox(mb, (0.06 * math.cos(a), -0.242, 1.69 + 0.06 * math.sin(a)), (0.018, 0.01, 0.018), "M_RuneLock", 0.0, (0, -math.degrees(a), 0))
    cyl(mb, (0, -0.238, 1.705), 0.018, 0.012, 10, "M_Socket", (90, 0, 0))
    cbox(mb, (0, -0.238, 1.67), (0.014, 0.012, 0.045), "M_Socket", 0.0)
    ob = mb.finish(); set_origin(ob, (0, -0.165, 1.93)); return ob

def door_sigil():
    mb = MB("Door_Sigil", seed=8)
    torus(mb, (0, 0, 0), 0.26, 0.018, "M_RuneLock", 32, 6, (90, 0, 0))
    torus(mb, (0, 0, 0), 0.19, 0.01, "M_RuneLock", 32, 5, (90, 0, 0))
    # key glyph
    torus(mb, (0, 0, 0.07), 0.045, 0.012, "M_RuneLock", 16, 5, (90, 0, 0))
    cbox(mb, (0, 0, -0.04), (0.024, 0.02, 0.16), "M_RuneLock", 0.0)
    cbox(mb, (0.028, 0, -0.1), (0.04, 0.02, 0.022), "M_RuneLock", 0.0)
    cbox(mb, (0.022, 0, -0.06), (0.03, 0.02, 0.02), "M_RuneLock", 0.0)
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        cbox(mb, (0.225 * math.cos(a), 0, 0.225 * math.sin(a)), (0.05, 0.02, 0.014), "M_RuneLock", 0.0, (0, -math.degrees(a) + 90, 0))
    ob = mb.finish(); ob.location = (0, -0.48, 4.62); return ob

# ---------------- gates ----------------
def portcullis(name="Gate_Portcullis"):
    mb = MB(name, seed=9)
    for i in range(11):
        x = -1.5 + i * 0.3
        cyl(mb, (x, 0, 2.43), 0.035, 4.56, 8, "M_Iron")
        lathe(mb, [(0.0, 0.0), (0.035, 0.2)], 8, "M_Iron", trs((x, 0, 0), (0, 0, 0)), cap_bottom=False)
    for z in (0.6, 1.5, 2.4, 3.3, 4.2):
        box_mm(mb, (-1.66, -0.05, z - 0.045), (1.66, 0.05, z + 0.045), "M_Iron", 0.01)
        for i in range(11):
            cbox(mb, (-1.5 + i * 0.3, -0.055, z), (0.06, 0.03, 0.06), "M_Iron", 0.01)
    return mb.finish()

def cell_bars(name="CellBars_2"):
    mb = MB(name, seed=10)
    box_mm(mb, (-1, -0.04, 0), (1, 0.04, 0.08), "M_Iron", 0.008)
    box_mm(mb, (-1, -0.05, 2.5), (1, 0.05, 2.62), "M_Iron", 0.01)
    box_mm(mb, (-1, -0.035, 1.25), (1, 0.035, 1.31), "M_Iron", 0.006)
    for i in range(10):
        cyl(mb, (-0.9 + i * 0.2, 0, 1.3), 0.02, 2.5, 8, "M_Iron")
    return mb.finish()

def cell_gate(name="CellGate"):
    mb = MB(name, seed=12)
    W = 1.9
    box_mm(mb, (0, -0.035, 0.08), (W, 0.035, 0.14), "M_Iron", 0.006)
    box_mm(mb, (0, -0.035, 2.36), (W, 0.035, 2.42), "M_Iron", 0.006)
    box_mm(mb, (0, -0.035, 1.22), (W, 0.035, 1.28), "M_Iron", 0.006)
    box_mm(mb, (0, -0.04, 0.08), (0.06, 0.04, 2.42), "M_Iron", 0.006)
    box_mm(mb, (W - 0.06, -0.04, 0.08), (W, 0.04, 2.42), "M_Iron", 0.006)
    for i in range(1, 9):
        cyl(mb, (i * W / 9, 0, 1.25), 0.018, 2.3, 8, "M_Iron")
    torus(mb, (W - 0.15, -0.06, 1.25), 0.06, 0.012, "M_Iron", 12, 5, (90, 0, 0))
    return mb.finish()

# ---------------- key & altar ----------------
def key_gold(name="Key_Gold"):
    mb = MB(name, seed=13)
    G = "M_Gold"
    torus(mb, (0, 0, 0.40), 0.075, 0.018, G, 24, 8, (90, 0, 0))
    for a in (0, 90):
        cbox(mb, (0, 0, 0.40), (0.012, 0.016, 0.13), G, 0.0, (0, a + 45, 0))
    sphere(mb, (0, -0.004, 0.40), 0.026, "M_Ember", 10, 6)
    lathe(mb, [(0.0, 0.296), (0.028, 0.296), (0.03, 0.31), (0.022, 0.318), (0.026, 0.33), (0.0, 0.333)], 14, G)
    cyl(mb, (0, 0, 0.18), 0.016, 0.24, 12, G)
    cbox(mb, (0.042, 0, 0.115), (0.07, 0.022, 0.1), G, 0.004)
    cbox(mb, (0.08, 0, 0.085), (0.03, 0.022, 0.04), G, 0.004)
    cbox(mb, (0.08, 0, 0.145), (0.03, 0.022, 0.035), G, 0.004)
    sphere(mb, (0, 0, 0.06), 0.02, G, 10, 6)
    ob = mb.finish(smooth_angle=40)
    set_origin(ob, (0, 0, 0.24))
    ob.location = (0, 0, 0)
    return ob

def pedestal(name="Pedestal"):
    mb = MB(name, seed=14); rng = random.Random(14)
    cbox(mb, (0, 0, 0.1), (1.4, 1.4, 0.2), "M_StoneB", 0.03)
    cbox(mb, (0, 0, 0.3), (1.05, 1.05, 0.2), "M_StoneA", 0.03)
    lathe(mb, [(0.34, 0.4), (0.3, 0.46), (0.27, 0.5), (0.25, 0.85), (0.3, 0.9), (0.36, 0.95)], 8, "M_StoneB", phase=math.pi / 8)
    cbox(mb, (0, 0, 1.01), (0.8, 0.8, 0.12), "M_StoneB", 0.025)
    box_mm(mb, (-0.405, -0.405, 0.955), (0.405, 0.405, 0.985), "M_Gold", 0.004)
    cbox(mb, (0, 0, 1.11), (0.44, 0.44, 0.09), "M_Velvet", 0.035)
    for sx in (-1, 1):
        for sy in (-1, 1):
            sphere(mb, (sx * 0.21, sy * 0.21, 1.07), 0.022, "M_Gold", 8, 5)
            # candles on the lower step
            h = rng.uniform(0.12, 0.25)
            cyl(mb, (sx * 0.6, sy * 0.6, 0.2 + h / 2), 0.035, h, 10, "M_Wax")
            sphere(mb, (sx * 0.6, sy * 0.6, 0.2 + h + 0.035), 0.016, "M_Flame", 8, 6, (1, 1, 2.0))
    return mb.finish()

def healing_font(name="HealingFont"):
    mb = MB(name, seed=15)
    lathe(mb, [(0.55, 0), (0.55, 0.12), (0.42, 0.18), (0.3, 0.3), (0.26, 0.55), (0.34, 0.68), (0.62, 0.8), (0.82, 0.88), (0.86, 0.98), (0.78, 1.0), (0.72, 0.92)],
          8, "M_StoneB", phase=math.pi / 8, cap_top=False)
    lathe(mb, [(0.0, 0.9), (0.73, 0.9)], 8, "M_HealWater", phase=math.pi / 8, cap_bottom=False, cap_top=False)
    # water surface as a disc (single face up)
    pts = [(0.73 * math.cos(math.pi / 8 + k * math.pi / 4), 0.73 * math.sin(math.pi / 8 + k * math.pi / 4), 0.9) for k in range(8)]
    mb.add(pts, [list(range(8))], "M_HealWater", recalc=False)
    for k in range(8):
        a = k * math.pi / 4
        cbox(mb, (0.85 * math.cos(a), 0.85 * math.sin(a), 0.87), (0.05, 0.05, 0.08), "M_HealWater", 0.0, (0, 0, math.degrees(a)))
    return mb.finish(smooth_angle=30)

def rune_circle(name="RuneCircle", seed=16):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    lathe(mb, [(3.95, 0.0), (3.95, 0.022), (4.25, 0.022), (4.25, 0.0)], 72, "M_StoneB", cap_bottom=False, cap_top=False)
    lathe(mb, [(3.95, 0.022), (4.25, 0.022)], 72, "M_StoneB", cap_bottom=False, cap_top=False)
    def flat_ring(r0, r1, z, segs, m):
        verts = []; faces = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            verts.append((r0 * math.cos(a), r0 * math.sin(a), z)); verts.append((r1 * math.cos(a), r1 * math.sin(a), z))
        for i in range(segs):
            j = (i + 1) % segs
            faces.append([2 * i, 2 * i + 1, 2 * j + 1, 2 * j])
        mb.add(verts, faces, m, recalc=False)
    flat_ring(3.86, 3.92, 0.012, 96, "M_Rune")
    flat_ring(3.28, 3.34, 0.012, 96, "M_Rune")
    flat_ring(0.62, 0.68, 0.012, 48, "M_Rune")
    flat_ring(1.25, 1.29, 0.012, 64, "M_Rune")
    def stroke(x0, y0, x1, y1, wdt=0.045):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dy, dx))
        cbox(mb, ((x0 + x1) / 2, (y0 + y1) / 2, 0.013), (L + wdt * 0.6, wdt, 0.01), "M_Rune", 0.0, (0, 0, ang))
    pts = [(3.31 * math.cos(math.pi / 2 + k * 2 * math.pi / 5), 3.31 * math.sin(math.pi / 2 + k * 2 * math.pi / 5)) for k in range(5)]
    for k in range(5):
        a = pts[k]; b = pts[(k + 2) % 5]
        stroke(a[0], a[1], b[0], b[1], 0.05)
    N = 30
    for g in range(N):
        a = 2 * math.pi * (g + 0.5) / N
        cx, cy = 3.6 * math.cos(a), 3.6 * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)   # tangent
        rx, ry = math.cos(a), math.sin(a)    # radial
        for s in range(rng.randint(2, 4)):
            u0, v0 = rng.uniform(-0.12, 0.12), rng.uniform(-0.17, 0.17)
            u1, v1 = rng.uniform(-0.12, 0.12), rng.uniform(-0.17, 0.17)
            if math.hypot(u1 - u0, v1 - v0) < 0.1:
                v1 = -v0 if abs(v0) > 0.05 else 0.17
            stroke(cx + tx * u0 + rx * v0, cy + ty * u0 + ry * v0, cx + tx * u1 + rx * v1, cy + ty * u1 + ry * v1, 0.035)
    for k in range(6):
        a = k * math.pi / 3
        stroke(0.68 * math.cos(a), 0.68 * math.sin(a), 1.25 * math.cos(a), 1.25 * math.sin(a), 0.04)
    return mb.finish()

# ---------------- lighting props ----------------
def torch_sconce(name="TorchSconce"):
    mb = MB(name, seed=17)
    cbox(mb, (0, -0.015, 0), (0.12, 0.03, 0.24), "M_Iron", 0.008)
    for dz in (-0.07, 0.07):
        cbox(mb, (0, -0.032, dz), (0.03, 0.012, 0.03), "M_Iron", 0.004)
    limb(mb, (0, -0.03, -0.05), (0, -0.17, -0.02), 0.012, 0.012, 6, "M_Iron")
    torus(mb, (0, -0.2, 0.0), 0.04, 0.009, "M_Iron", 12, 5, (0, 0, 0))
    q = trs((0, -0.2, 0.0), (14, 0, 0))
    limb(mb, q @ Vector((0, 0, -0.16)), q @ Vector((0, 0, 0.22)), 0.022, 0.028, 8, "M_WoodDark")
    lathe(mb, [(0.026, 0.0), (0.044, 0.03), (0.048, 0.08), (0.04, 0.12), (0.0, 0.135)], 10, "M_ClothDark", q @ Matrix.Translation((0, 0, 0.2)))
    sphere(mb, q @ Vector((0, 0, 0.32)), 0.03, "M_Ember", 8, 5, (1.2, 1.2, 0.6))
    return mb.finish()

def brazier(name="Brazier", seed=18):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for k in range(3):
        a = k * 2 * math.pi / 3
        foot = (0.42 * math.cos(a), 0.42 * math.sin(a), 0.0)
        knee = (0.28 * math.cos(a), 0.28 * math.sin(a), 0.45)
        top = (0.2 * math.cos(a), 0.2 * math.sin(a), 0.78)
        limb(mb, foot, knee, 0.03, 0.026, 6, "M_Iron")
        limb(mb, knee, top, 0.026, 0.024, 6, "M_Iron")
        sphere(mb, foot, 0.04, "M_Iron", 8, 5, (1, 1, 0.6))
    torus(mb, (0, 0, 0.45), 0.29, 0.015, "M_Iron", 18, 5)
    lathe(mb, [(0.06, 0.74), (0.22, 0.8), (0.38, 0.92), (0.44, 1.0), (0.46, 1.03), (0.42, 1.03), (0.36, 0.96), (0.2, 0.86), (0.0, 0.84)], 16, "M_Iron")
    for i in range(16):
        r = rng.uniform(0.0, 0.3); a = rng.uniform(0, 2 * math.pi)
        s = rng.uniform(0.07, 0.14)
        cbox(mb, (r * math.cos(a), r * math.sin(a), 0.92 + rng.uniform(0, 0.05)), (s, s * 0.8, s * 0.6),
             "M_Ember" if rng.random() < 0.55 else "M_StoneDark", 0.015, (rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 90)))
    return mb.finish(smooth_angle=40)

def candles(name="Candles", seed=19):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    lathe(mb, [(0.0, 0), (0.17, 0), (0.18, 0.015), (0.15, 0.025), (0.0, 0.025)], 16, "M_Iron")
    spots = [(0, 0), (0.08, 0.05), (-0.07, 0.06), (0.03, -0.09), (-0.08, -0.05)]
    for (x, y) in spots:
        h = rng.uniform(0.07, 0.24); r = rng.uniform(0.022, 0.034)
        cyl(mb, (x, y, 0.025 + h / 2), r, h, 10, "M_Wax")
        for d in range(2):
            a = rng.uniform(0, 2 * math.pi)
            sphere(mb, (x + r * math.cos(a), y + r * math.sin(a), 0.025 + h - rng.uniform(0.01, 0.05)), 0.008, "M_Wax", 6, 4, (1, 1, 2.5))
        sphere(mb, (x, y, 0.025 + h + 0.03), 0.012, "M_Flame", 8, 6, (1, 1, 2.2))
    return mb.finish(smooth_angle=40)

def chandelier(name="Chandelier", seed=20):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    R = 0.8; zr = -1.7
    torus(mb, (0, 0, zr), R, 0.03, "M_Iron", 32, 6)
    torus(mb, (0, 0, zr - 0.08), 0.18, 0.025, "M_Iron", 16, 6)
    for k in range(4):
        a = k * math.pi / 2
        limb(mb, (0.18 * math.cos(a), 0.18 * math.sin(a), zr - 0.08), (R * math.cos(a), R * math.sin(a), zr), 0.015, 0.015, 6, "M_Iron")
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.3
        p0 = Vector((R * math.cos(a), R * math.sin(a), zr)); p1 = Vector((0, 0, -0.05))
        n = 14
        for i in range(n):
            t = (i + 0.5) / n
            c = p0.lerp(p1, t)
            d = (p1 - p0).normalized()
            rot = d.to_track_quat('Z', 'Y').to_euler()
            torus(mb, (0, 0, 0), 0.035, 0.008, "M_Iron", 10, 4, M=Matrix.Translation(c) @ rot.to_matrix().to_4x4() @ rot_m((90, 0, 90 * (i % 2))))
    torus(mb, (0, 0, 0), 0.06, 0.014, "M_Iron", 12, 5, (90, 0, 0))
    for k in range(8):
        a = k * math.pi / 4 + math.pi / 8
        x, y = R * math.cos(a), R * math.sin(a)
        lathe(mb, [(0.0, 0), (0.06, 0), (0.06, 0.015), (0.0, 0.015)], 10, "M_Iron", Matrix.Translation((x, y, zr + 0.02)))
        h = rng.uniform(0.1, 0.18)
        cyl(mb, (x, y, zr + 0.035 + h / 2), 0.028, h, 10, "M_Wax")
        sphere(mb, (x, y, zr + 0.035 + h + 0.03), 0.014, "M_Flame", 8, 6, (1, 1, 2.2))
    return mb.finish(smooth_angle=40)

# ---------------- decor ----------------
def barrel(name="Barrel", seed=21):
    mb = MB(name, seed=seed)
    prof = [(0.27, 0.0), (0.31, 0.15), (0.335, 0.45), (0.31, 0.75), (0.27, 0.9)]
    lathe(mb, prof, 18, "M_Wood", cap_bottom=True, cap_top=False)
    lathe(mb, [(0.255, 0.86), (0.255, 0.88)], 18, "M_WoodDark", cap_bottom=False, cap_top=True)
    lathe(mb, [(0.27, 0.9), (0.255, 0.9), (0.255, 0.86)], 18, "M_Wood", cap_bottom=False, cap_top=False)
    for (z0, z1, r) in ((0.06, 0.12, 0.294), (0.3, 0.36, 0.33), (0.54, 0.6, 0.33), (0.78, 0.84, 0.294)):
        lathe(mb, [(r + 0.004, z0), (r + 0.012, z0 + 0.01), (r + 0.012, z1 - 0.01), (r + 0.004, z1)], 18, "M_Iron", cap_bottom=False, cap_top=False)
    return mb.finish(smooth_angle=30)

def crate(name="Crate", s=0.8, seed=22):
    mb = MB(name, seed=seed)
    h = s / 2; f = 0.075 * s / 0.8
    cbox(mb, (0, 0, h), (s - 0.04, s - 0.04, s - 0.04), "M_Wood", 0.01)
    for a in (-1, 1):
        for b in (-1, 1):
            cbox(mb, (a * (h - f / 2), b * (h - f / 2), h), (f, f, s), "M_WoodDark", 0.012)
            cbox(mb, (0, a * (h - f / 2), h + b * (h - f / 2)), (s - 2 * f, f, f), "M_WoodDark", 0.012)
            cbox(mb, (a * (h - f / 2), 0, h + b * (h - f / 2)), (f, s - 2 * f, f), "M_WoodDark", 0.012)
    for yy in (-1, 1):
        L = math.hypot(s - 2 * f, s - 2 * f)
        cbox(mb, (0, yy * (h - f * 0.3), h), (L - 0.02, f * 0.6, f * 0.9), "M_WoodDark", 0.01, (0, 45, 0))
    return mb.finish()

def bone(mb, p0, p1, r=0.022):
    limb(mb, p0, p1, r, r * 0.85, 8, "M_Bone")
    d = (Vector(p1) - Vector(p0)).normalized()
    for p, s in ((Vector(p0), -1), (Vector(p1), 1)):
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 0.1:
            side = Vector((1, 0, 0))
        side.normalize()
        sphere(mb, p + side * r * 0.9, r * 1.35, "M_Bone", 8, 5)
        sphere(mb, p - side * r * 0.9, r * 1.35, "M_Bone", 8, 5)

def skull_geo(mb, c, s=1.0, rot=(0, 0, 0)):
    M = Matrix.Translation(Vector(c)) @ rot_m(rot) @ Matrix.Diagonal((s, s, s, 1))
    sphere(mb, (0, 0.01, 0.1), 0.1, "M_Bone", 14, 9, (0.92, 1.08, 1.0), M=M)
    cbox(mb, (0, -0.07, 0.035), (0.11, 0.07, 0.07), "M_Bone", 0.02, M=M)
    for sx in (-1, 1):
        sphere(mb, (sx * 0.038, -0.085, 0.1), 0.028, "M_Socket", 8, 6, (1, 0.6, 1), M=M)
    cbox(mb, (0, -0.1, 0.06), (0.02, 0.02, 0.03), "M_Socket", 0.004, M=M)
    for i in range(6):
        cbox(mb, (-0.035 + i * 0.014, -0.103, 0.012), (0.01, 0.01, 0.018), "M_Bone", 0.002, M=M)

def skull(name="Skull"):
    mb = MB(name, seed=23)
    skull_geo(mb, (0, 0, 0), 1.0, (8, 0, 0))
    return mb.finish(smooth_angle=45)

def bone_pile(name="BonePile", seed=24):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for i in range(9):
        c = Vector((rng.uniform(-0.45, 0.45), rng.uniform(-0.35, 0.35), 0.03 + i * 0.006))
        a = rng.uniform(0, math.pi)
        L = rng.uniform(0.25, 0.42)
        d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.1, 0.12))) * (L / 2)
        bone(mb, c - d, c + d, rng.uniform(0.016, 0.024))
    skull_geo(mb, (0.15, -0.05, 0.02), 1.0, (rng.uniform(-10, 10), rng.uniform(-30, 30), rng.uniform(-40, 40)))
    for k in range(4):
        torus(mb, (-0.2, 0.15, 0.03 + k * 0.012), 0.14 - k * 0.015, 0.012, "M_Bone", 16, 5, (90, 0, 20 + k * 6), arc=0.45)
    return mb.finish(smooth_angle=45)

def chain_hanging(name="Chain_Hanging", n=16):
    mb = MB(name, seed=25)
    torus(mb, (0, 0, -0.03), 0.04, 0.01, "M_Iron", 12, 5, (90, 0, 0))
    for i in range(n):
        torus(mb, (0, 0, -0.09 - i * 0.065), 0.036, 0.009, "M_Iron", 12, 5, (90, 0, 90 * (i % 2)), M=Matrix.Diagonal((1, 1, 1.35, 1)))
    torus(mb, (0, 0, -0.12 - n * 0.065), 0.06, 0.014, "M_Iron", 14, 5, (90, 0, 0))
    return mb.finish(smooth_angle=50)

def banner(name, cloth_mat, seed):
    mb = MB(name, seed=seed)
    cyl(mb, (0, 0, 0), 0.025, 1.05, 10, "M_WoodDark", (0, 90, 0))
    for sx in (-1, 1):
        sphere(mb, (sx * 0.55, 0, 0), 0.04, "M_Gold", 10, 6)
    w, h, nx, ny = 0.86, 2.1, 8, 18
    def P(i, j, back):
        u = i / nx; v = j / ny
        x = (u - 0.5) * w
        z = -0.04 - v * h + (v ** 6) * 0.32 * (1 - abs(2 * u - 1))
        y = 0.035 * math.sin(u * 6.28 + v * 2.5) * v + 0.04 * v + (0.007 if back else 0.0)
        return (x, y, z)
    for back in (False, True):
        verts = [P(i, j, back) for j in range(ny + 1) for i in range(nx + 1)]
        faces = []
        for j in range(ny):
            for i in range(nx):
                a = j * (nx + 1) + i
                faces.append([a, a + 1, a + nx + 2, a + nx + 1] if back else [a, a + nx + 1, a + nx + 2, a + 1])
        mb.add(verts, faces, cloth_mat, recalc=False)
    torus(mb, (0, -0.025, -0.8), 0.17, 0.016, "M_Gold", 24, 5, (90, 0, 0))
    cbox(mb, (0, -0.022, -0.8), (0.16, 0.012, 0.16), "M_Gold", 0.0, (0, 45, 0))
    cbox(mb, (0, -0.02, -0.25), (0.6, 0.012, 0.035), "M_Gold", 0.0)
    return mb.finish(smooth_angle=60)

def rubble(name, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for i in range(14):
        r = rng.uniform(0, 0.6) * (1 - i / 20)
        a = rng.uniform(0, 2 * math.pi)
        s = rng.uniform(0.12, 0.42) * (1.2 - i / 20)
        z = s * 0.3 + (0.25 * (1 - r / 0.6) if i > 5 else 0)
        cbox(mb, (r * math.cos(a), r * math.sin(a), z), (s * rng.uniform(0.8, 1.4), s * rng.uniform(0.7, 1.1), s * rng.uniform(0.5, 0.8)),
             pick(rng, STONE_MIX), rng.uniform(0.02, 0.05), (rng.uniform(-30, 30), rng.uniform(-30, 30), rng.uniform(0, 360)))
    return mb.finish()

def pebbles(name="Pebbles", seed=27):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for i in range(16):
        r = rng.uniform(0, 0.8); a = rng.uniform(0, 2 * math.pi); s = rng.uniform(0.04, 0.12)
        cbox(mb, (r * math.cos(a), r * math.sin(a), s * 0.25), (s, s * 0.8, s * 0.55), pick(rng, STONE_MIX), s * 0.2,
             (rng.uniform(-20, 20), rng.uniform(-20, 20), rng.uniform(0, 360)))
    return mb.finish()

def sarcophagus(name="Sarcophagus", seed=28):
    mb = MB(name, seed=seed)
    cbox(mb, (0, 0, 0.06), (1.12, 2.3, 0.12), "M_StoneC", 0.02)
    cbox(mb, (0, 0, 0.42), (1.0, 2.18, 0.62), "M_StoneB", 0.03)
    for sx in (-1, 1):
        for k in range(3):
            cbox(mb, (sx * 0.505, -0.7 + k * 0.7, 0.42), (0.02, 0.5, 0.4), "M_StoneA", 0.008)
    cbox(mb, (0, 0, 0.8), (1.1, 2.28, 0.14), "M_StoneC", 0.03)
    cbox(mb, (0, 0, 0.92), (0.86, 2.0, 0.12), "M_StoneB", 0.04)
    cbox(mb, (0, 0.05, 1.0), (0.3, 1.5, 0.08), "M_StoneB", 0.035)
    skull_geo(mb, (0, -0.78, 0.96), 1.15, (-90, 0, 180))
    return mb.finish()

def urn(name="Urn", seed=29):
    mb = MB(name, seed=seed)
    lathe(mb, [(0.0, 0), (0.1, 0), (0.13, 0.04), (0.21, 0.16), (0.24, 0.3), (0.2, 0.45), (0.11, 0.55), (0.1, 0.6), (0.135, 0.65), (0.115, 0.67), (0.0, 0.64)], 16, "M_Clay")
    lathe(mb, [(0.243, 0.26), (0.25, 0.28), (0.25, 0.32), (0.243, 0.34)], 16, "M_Gold", cap_bottom=False, cap_top=False)
    return mb.finish(smooth_angle=40)

def table(name="Table", seed=30):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for k in range(4):
        cbox(mb, (0, -0.3 + k * 0.2, 0.78), (1.7, 0.195, 0.06), "M_WoodDark", 0.008, (0, rng.uniform(-0.6, 0.6), 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            cbox(mb, (sx * 0.72, sy * 0.3, 0.375), (0.08, 0.08, 0.75), "M_WoodDark", 0.01)
        cbox(mb, (sx * 0.72, 0, 0.2), (0.06, 0.56, 0.06), "M_WoodDark", 0.008)
    cbox(mb, (0, 0, 0.2), (1.38, 0.06, 0.06), "M_WoodDark", 0.008)
    return mb.finish()

def build():
    dlib.reset()
    out = []
    out += [portcullis(), cell_bars(), cell_gate(), key_gold(), pedestal(), healing_font(), rune_circle(),
            torch_sconce(), brazier(), candles(), chandelier(), barrel(), crate("Crate", 0.8, 22), crate("Crate_Small", 0.55, 23),
            skull(), bone_pile(), chain_hanging(), banner("Banner_Red", "M_ClothRed", 31), banner("Banner_Blue", "M_ClothBlue", 32),
            rubble("Rubble_A", 33), rubble("Rubble_B", 34), pebbles(), sarcophagus(), urn(), table()]
    return out

def build_door():
    dlib.reset()
    return [door_leaf("Door_LeafA", -1, 41), door_leaf("Door_LeafB", 1, 42), door_bar(), door_lock(), door_sigil()]
