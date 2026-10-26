# wd_world.py - floating island, road, decor and clouds for Word Defense -> WD_World.fbx + Data/path.json
import sys, importlib, json, math, random
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import wdlib; importlib.reload(wdlib)
from wdlib import *
from mathutils import Vector, noise
import bpy, bmesh

reset()
rng = random.Random(7)

# ------------------------------------------------------------------ path (Unity x, z)
CTRL = [(16.5, 13.4), (13.0, 13.6), (8.5, 12.8), (4.0, 12.0), (0.2, 10.4), (-0.8, 7.4), (1.4, 5.0),
        (5.6, 4.0), (8.6, 2.4), (9.0, -0.4), (6.4, -2.3), (2.0, -2.9), (-2.6, -2.2), (-6.4, -1.4), (-9.6, -1.2)]

def catmull(pts, samples=16):
    out = []
    P = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = [Vector((a, b)) for a, b in P[i - 1:i + 3]]
        for k in range(samples):
            t = k / samples
            t2, t3 = t * t, t * t * t
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append(v)
    out.append(Vector(pts[-1]))
    return out

def resample(poly, step):
    out = [poly[0]]
    acc = 0.0
    for i in range(1, len(poly)):
        a, b = poly[i - 1], poly[i]
        seg = (b - a).length
        while acc + seg >= step:
            t = (step - acc) / seg
            a = a + (b - a) * t
            seg = (b - a).length
            out.append(a.copy())
            acc = 0.0
        acc += seg
    if (out[-1] - poly[-1]).length > 0.05:
        out.append(poly[-1])
    return out

PATH = resample(catmull(CTRL), 0.25)
length = sum((PATH[i] - PATH[i - 1]).length for i in range(1, len(PATH)))
print("path points", len(PATH), "length", round(length, 2))

def path_dist(x, z):
    best = 1e9
    for p in PATH[::2]:
        d = (p.x - x) ** 2 + (p.y - z) ** 2
        if d < best:
            best = d
    return math.sqrt(best)

CASTLE = Vector((-14.2, -1.2))
PORTAL = Vector((17.6, 13.4))
POND = Vector((12.6, -6.8))
HILLS = [(-12.5, 10.5, 1.3, 3.8), (16.5, 4.5, 0.9, 3.2), (-3.5, 15.5, 0.8, 4.0), (-19.5, 4.0, 0.7, 3.0), (6.0, 16.5, 0.6, 3.0)]

def height(x, z):
    h = 0.0
    for hx, hz, hh, hr in HILLS:
        d2 = ((x - hx) ** 2 + (z - hz) ** 2) / (hr * hr)
        h += hh * math.exp(-d2 * 1.6)
    h += 0.10 * noise.noise(Vector((x * 0.22, z * 0.22, 0.5)))
    d = path_dist(x, z)
    m = min(1.0, max(0.0, (d - 1.9) / 2.2))
    c = (Vector((x, z)) - CASTLE).length
    m *= min(1.0, max(0.0, (c - 5.4) / 2.0))
    pd = (Vector((x, z)) - PORTAL).length
    m *= min(1.0, max(0.0, (pd - 3.0) / 2.0))
    pn = (Vector((x, z)) - POND).length
    m *= min(1.0, max(0.0, (pn - 3.2) / 1.5))
    return h * m

# ------------------------------------------------------------------ island (one closed faceted mesh)
CX, CZ, RX, RZ = 0.0, 2.6, 24.0, 16.0
S = 112
def outline(th):
    r = 1.0 + 0.055 * noise.noise(Vector((math.cos(th) * 1.3, math.sin(th) * 1.3, 2.0))) \
        + 0.03 * noise.noise(Vector((math.cos(th) * 3.1, math.sin(th) * 3.1, 5.0)))
    # a few lobes so the silhouette is not an ellipse
    r += 0.05 * math.cos(3 * th + 0.6) + 0.025 * math.sin(5 * th + 1.1)
    return r

def ring_xz(th, scale):
    r = outline(th) * scale
    return CX + RX * r * math.cos(th), CZ + RZ * r * math.sin(th)

bm = bmesh.new()
mats = ["M_Grass", "M_GrassDark", "M_GrassLight", "M_Cliff", "M_CliffB", "M_CliffC", "M_CliffDark", "M_Dirt"]
K = 22
rings = []
center = bm.verts.new(U(CX, CZ, height(CX, CZ)))
for k in range(1, K + 1):
    t = k / K
    ring = []
    for j in range(S):
        th = 2 * math.pi * j / S
        x, z = ring_xz(th, t)
        y = height(x, z) if t < 0.97 else 0.0
        if t > 0.9:
            y *= (1.0 - (t - 0.9) / 0.1)
        ring.append(bm.verts.new(U(x, z, y)))
    rings.append(ring)
# cliff rings: (depth, scale, band material, rocky amplitude)
CLIFF = [(-0.32, 1.006, 0, 0.0), (-0.42, 0.988, 3, 0.10), (-2.0, 0.982, 3, 0.18), (-2.15, 0.962, 4, 0.12),
         (-3.7, 0.955, 4, 0.20), (-3.85, 0.93, 5, 0.12), (-5.4, 0.915, 5, 0.22), (-5.6, 0.87, 6, 0.15),
         (-7.6, 0.70, 6, 0.35), (-9.8, 0.46, 6, 0.40), (-11.8, 0.22, 6, 0.30), (-12.9, 0.07, 6, 0.10)]
cliff_rings = []
for depth, sc, band, amp in CLIFF:
    ring = []
    for j in range(S):
        th = 2 * math.pi * j / S
        x, z = ring_xz(th, sc)
        n = noise.noise(Vector((math.cos(th) * 4.0, math.sin(th) * 4.0, depth * 0.7)))
        dx, dz = x - CX, z - CZ
        L = math.hypot(dx, dz) or 1.0
        x += dx / L * amp * n * 1.5
        z += dz / L * amp * n * 1.5
        ring.append(bm.verts.new(U(x, z, depth + 0.12 * amp * noise.noise(Vector((x * 0.5, z * 0.5, 3.0))))))
    cliff_rings.append((ring, band))
tip = bm.verts.new(U(CX + 0.5, CZ - 0.4, -13.6))

def face(vs, mi):
    try:
        f = bm.faces.new(vs)
        f.material_index = mi
        return f
    except ValueError:
        return None

def grass_mi(vs):
    c = sum((v.co for v in vs), Vector()) / len(vs)
    n = noise.noise(Vector((c.x * 0.07, c.y * 0.07, 9.0)))
    return 2 if n > 0.32 else (1 if n < -0.34 else 0)

for j in range(S):
    j2 = (j + 1) % S
    a, b = rings[0][j], rings[0][j2]
    face([center, a, b], grass_mi([center, a, b]))
for k in range(K - 1):
    A, B = rings[k], rings[k + 1]
    for j in range(S):
        j2 = (j + 1) % S
        vs = [A[j], B[j], B[j2], A[j2]]
        face(vs, grass_mi(vs))
prev = rings[-1]
for ring, band in cliff_rings:
    for j in range(S):
        j2 = (j + 1) % S
        face([prev[j], ring[j], ring[j2], prev[j2]], band)
    prev = ring
for j in range(S):
    face([prev[j], tip, prev[(j + 1) % S]], 6)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
me = bpy.data.meshes.new("Island")
bm.to_mesh(me)
bm.free()
for m in mats:
    me.materials.append(mat(m))
for p in me.polygons:
    p.use_smooth = p.material_index <= 2   # soft rolling grass, faceted cliffs
island = bpy.data.objects.new("Island", me)
bpy.context.scene.collection.objects.link(island)

# ------------------------------------------------------------------ road slab + edge stones
mb = MB("Road", seed=3)
W = 1.25
left, right = [], []
for i, p in enumerate(PATH):
    a = PATH[max(0, i - 1)]; b = PATH[min(len(PATH) - 1, i + 1)]
    t = (b - a).normalized()
    nrm = Vector((-t.y, t.x))
    left.append(p + nrm * W); right.append(p - nrm * W)
n = len(PATH)
verts = []
for i in range(n):
    for (q, y) in ((left[i], 0.045), (right[i], 0.045), (right[i], -0.08), (left[i], -0.08)):
        verts.append(tuple(U(q.x, q.y, y)))
faces = []
for i in range(n - 1):
    a, b = 4 * i, 4 * (i + 1)
    faces += [[a, a + 1, b + 1, b], [a + 1, a + 2, b + 2, b + 1], [a + 2, a + 3, b + 3, b + 2], [a + 3, a, b, b + 3]]
faces += [[0, 3, 2, 1], [4 * (n - 1), 4 * (n - 1) + 1, 4 * (n - 1) + 2, 4 * (n - 1) + 3]]
mb.add(verts, faces, "M_Road")
road = mb.finish(smooth_angle=20)

mb = MB("RoadStones", seed=4)
acc = 0.0
for i in range(1, n - 1):
    acc += (PATH[i] - PATH[i - 1]).length
    if acc < 0.95:
        continue
    acc = 0.0
    for side, q in ((1, left[i]), (-1, right[i])):
        t = (PATH[i + 1] - PATH[i - 1]).normalized()
        nrm = Vector((-t.y, t.x)) * side
        c = q + nrm * 0.12
        if (Vector((c.x, c.y)) - CASTLE).length < 4.6 or (Vector((c.x, c.y)) - PORTAL).length < 2.6:
            continue
        sx = rng.uniform(0.34, 0.5); sz = rng.uniform(0.22, 0.3); sy = rng.uniform(0.12, 0.2)
        ang = math.degrees(math.atan2(t.y, t.x)) + rng.uniform(-12, 12)
        cbox(mb, tuple(U(c.x, c.y, sy / 2 - 0.02)), (sx, sz, sy), "M_RoadEdge", b=0.05, rot=(0, 0, ang + 180))
stones = mb.finish(smooth_angle=30)

# ------------------------------------------------------------------ decor helpers
def tree_round(mb, x, z, s, leaf="M_Leaf"):
    y = height(x, z)
    cyl(mb, tuple(U(x, z, y + 0.45 * s)), 0.13 * s, 0.9 * s, 6, "M_Trunk", r2=0.09 * s)
    for (ox, oz, oy, r) in ((0, 0, 1.25, 0.62), (0.28, 0.12, 1.05, 0.42), (-0.25, -0.18, 1.0, 0.45)):
        sphere(mb, tuple(U(x + ox * s, z + oz * s, y + oy * s)), r * s, leaf, segs=7, rings=5, scl=(1, 1, 0.92))

def tree_pine(mb, x, z, s):
    y = height(x, z)
    cyl(mb, tuple(U(x, z, y + 0.25 * s)), 0.11 * s, 0.5 * s, 6, "M_Trunk")
    for k, (h0, r, hh) in enumerate(((0.45, 0.62, 0.9), (0.95, 0.5, 0.8), (1.4, 0.36, 0.7))):
        lathe(mb, [(r * s, 0), (0.0, hh * s)], 7, "M_LeafDark", Matrix.Translation(U(x, z, y + h0 * s)), cap_bottom=True, cap_top=False, phase=k * 0.4)

def rock(mb, x, z, s, m="M_Rock"):
    y = height(x, z)
    bv = sphere(mb, tuple(U(x, z, y + 0.12 * s)), 0.45 * s, m, segs=6, rings=4, scl=(1.0 + rng.uniform(-0.2, 0.3), 1.0 + rng.uniform(-0.2, 0.2), 0.62), rot=(0, 0, rng.uniform(0, 360)))
    for v in bv:
        v.co += Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), rng.uniform(-0.04, 0.04))) * s

def bush(mb, x, z, s, leaf="M_LeafDark"):
    y = height(x, z)
    for (ox, oz, r) in ((0, 0, 0.42), (0.32, 0.1, 0.3), (-0.3, 0.05, 0.32)):
        sphere(mb, tuple(U(x + ox * s, z + oz * s, y + r * 0.55 * s)), r * s, leaf, segs=7, rings=4, scl=(1, 1, 0.8))

def house(mb, x, z, rotdeg, s=1.0, roof="M_Roof"):
    y = height(x, z)
    M = Matrix.Translation(U(x, z, y)) @ rot_m((0, 0, rotdeg)) @ Matrix.Diagonal((s, s, s, 1))
    cbox(mb, (0, 0, 0.7), (1.8, 1.4, 1.4), "M_Stone", b=0.05, M=M)
    cbox(mb, (0, 0, 0.08), (2.0, 1.6, 0.16), "M_StoneShade", b=0.04, M=M)
    # pitched roof (prism) with overhang
    v = [(-1.1, -0.95, 1.38), (1.1, -0.95, 1.38), (1.1, 0.95, 1.38), (-1.1, 0.95, 1.38), (-1.1, 0, 2.25), (1.1, 0, 2.25)]
    f = [[0, 1, 5, 4], [2, 3, 4, 5], [0, 4, 3], [1, 2, 5], [0, 3, 2, 1]]
    mb.add(v, f, roof, M)
    cbox(mb, (0.45, 0.35, 2.1), (0.26, 0.26, 0.7), "M_StoneShade", b=0.03, M=M)
    cbox(mb, (0, -0.71, 0.5), (0.42, 0.06, 0.8), "M_Door", b=0.02, M=M)
    cbox(mb, (-0.55, -0.71, 0.85), (0.3, 0.05, 0.3), "M_WindowLit", b=0.01, M=M)
    cbox(mb, (0.6, -0.71, 0.85), (0.3, 0.05, 0.3), "M_WindowLit", b=0.01, M=M)

def fence(mb, pts):
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        L = (b - a).length
        nseg = max(1, int(L / 1.1))
        for k in range(nseg + 1):
            p = a + (b - a) * (k / nseg)
            y = height(p.x, p.y)
            cbox(mb, tuple(U(p.x, p.y, y + 0.32)), (0.12, 0.12, 0.64), "M_Wood", b=0.02)
        for hgt in (0.26, 0.5):
            mid = (a + b) / 2
            ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
            y = height(mid.x, mid.y)
            cbox(mb, tuple(U(mid.x, mid.y, y + hgt)), (L, 0.06, 0.08), "M_WoodDark", b=0.01, rot=(0, 0, ang + 180))

def lantern(mb, x, z):
    y = height(x, z)
    cyl(mb, tuple(U(x, z, y + 0.7)), 0.06, 1.4, 6, "M_WoodDark")
    cbox(mb, tuple(U(x, z, y + 1.48)), (0.26, 0.26, 0.3), "M_WindowLit", b=0.03)
    lathe(mb, [(0.22, 0), (0.0, 0.18)], 4, "M_Roof", Matrix.Translation(U(x, z, y + 1.63)) @ rot_m((0, 0, 45)), cap_top=False)
    cbox(mb, tuple(U(x, z, y + 0.03)), (0.3, 0.3, 0.08), "M_StoneShade", b=0.02)

# ------------------------------------------------------------------ decor placement
decor = MB("Decor", seed=5)
trees = MB("Trees", seed=6)
occupied = []
def free(x, z, r):
    if path_dist(x, z) < 2.5 + r:
        return False
    if (Vector((x, z)) - CASTLE).length < 6.0 + r or (Vector((x, z)) - PORTAL).length < 3.6 + r:
        return False
    if (Vector((x, z)) - POND).length < 3.0 + r:
        return False
    th = math.atan2((z - CZ) / RZ, (x - CX) / RX)
    rr = math.hypot((x - CX) / RX, (z - CZ) / RZ)
    if rr > outline(th) * 0.9:
        return False
    for (ox, oz, orad) in occupied:
        if (ox - x) ** 2 + (oz - z) ** 2 < (orad + r) ** 2:
            return False
    return True

def place(x, z, r):
    occupied.append((x, z, r))

# landmarks
WIND = (-12.5, 10.5)
place(WIND[0], WIND[1], 1.6)
HOUSES = [(-8.2, -6.6, 15), (-5.2, -7.6, -10), (-19.0, 3.0, 80), (-17.2, 6.6, 60), (11.5, 8.8, -35)]
for hx, hz, ha in HOUSES:
    house(decor, hx, hz, ha, roof="M_Flag" if hx > 0 else "M_Roof")
    place(hx, hz, 1.5)
fence(decor, [(-10.6, -5.0), (-9.8, -8.4), (-4.0, -9.4), (-2.6, -6.6)])
fence(decor, [(-20.2, 1.2), (-19.6, 8.2), (-15.2, 9.0)])
# lanterns along the road
acc = 0.0; side = 1
for i in range(1, len(PATH) - 1):
    acc += (PATH[i] - PATH[i - 1]).length
    if acc < 8.5:
        continue
    t = (PATH[i + 1] - PATH[i - 1]).normalized()
    nrm = Vector((-t.y, t.x)) * side
    q = PATH[i] + nrm * 1.85
    if (q - CASTLE).length > 5.0 and (q - PORTAL).length > 3.0:
        lantern(decor, q.x, q.y)
        place(q.x, q.y, 0.4)
        acc = 0.0; side = -side
# pond
pond = MB("Pond", seed=8)
pr = []
for j in range(20):
    th = 2 * math.pi * j / 20
    r = 2.5 + 0.35 * noise.noise(Vector((math.cos(th), math.sin(th), 7.0)))
    pr.append((POND.x + r * math.cos(th), POND.y + 0.8 * r * math.sin(th)))
verts = [tuple(U(POND.x, POND.y, -0.12))] + [tuple(U(x, z, -0.12)) for x, z in pr]
faces = [[0, 1 + j, 1 + (j + 1) % 20] for j in range(20)]
pond.add(verts, faces, "M_Water", recalc=False)
for (x, z) in pr[::2]:
    rock(decor, x + rng.uniform(-0.2, 0.2), z + rng.uniform(-0.2, 0.2), rng.uniform(0.45, 0.8), "M_RockDark")
water = pond.finish(smooth_angle=5)
# groves
GROVES = [(-17.5, 11.5, 3.6, 9), (-7.0, 14.5, 3.0, 7), (12.0, 16.2, 2.8, 5), (19.5, 7.5, 2.6, 6), (-20.5, -3.5, 2.5, 6),
          (15.5, -3.0, 2.6, 6), (-1.0, -9.0, 2.6, 5), (5.0, 8.4, 1.8, 3), (-6.5, 5.8, 2.2, 5), (-12.0, 4.0, 1.6, 3),
          (20.0, -8.0, 2.2, 4), (-13.0, -9.5, 2.0, 4), (9.0, -9.5, 2.2, 4), (2.5, 17.0, 2.4, 4)]
for gx, gz, gr, cnt in GROVES:
    for k in range(cnt * 3):
        if cnt <= 0:
            break
        a = rng.uniform(0, 2 * math.pi); d = gr * math.sqrt(rng.random())
        x, z = gx + d * math.cos(a), gz + d * math.sin(a)
        s = rng.uniform(0.85, 1.35)
        if not free(x, z, 0.75 * s):
            continue
        kind = rng.random()
        if kind < 0.42:
            tree_round(trees, x, z, s, "M_Leaf")
        elif kind < 0.72:
            tree_pine(trees, x, z, s * 1.1)
        elif kind < 0.86:
            tree_round(trees, x, z, s, "M_LeafAutumn")
        else:
            tree_round(trees, x, z, s * 0.9, "M_LeafPink")
        place(x, z, 0.75 * s)
        cnt -= 1
# rocks and bushes everywhere else
for k in range(260):
    x = rng.uniform(-22, 22); z = rng.uniform(-12, 18)
    s = rng.uniform(0.5, 1.1)
    if not free(x, z, 0.5 * s):
        continue
    if rng.random() < 0.45:
        rock(decor, x, z, s)
    else:
        bush(decor, x, z, s * 0.8, "M_LeafDark" if rng.random() < 0.6 else "M_Leaf")
    place(x, z, 0.5 * s)
decor_ob = decor.finish(smooth_angle=25)
trees_ob = trees.finish(smooth_angle=25)

# windmill (blades separate so Unity can spin them)
wm = MB("Windmill", seed=9)
wy = height(*WIND)
lathe(wm, [(1.1, 0), (0.95, 2.2), (0.8, 3.6)], 8, "M_Stone", Matrix.Translation(U(WIND[0], WIND[1], wy - 0.1)))
lathe(wm, [(1.05, 0), (0.0, 1.4)], 8, "M_Roof", Matrix.Translation(U(WIND[0], WIND[1], wy + 3.5)), cap_top=False)
cbox(wm, tuple(U(WIND[0] + 0.0, WIND[1] - 0.86, wy + 0.55)), (0.5, 0.12, 0.9), "M_Door", b=0.03)
cbox(wm, tuple(U(WIND[0] + 0.0, WIND[1] - 0.82, wy + 2.4)), (0.35, 0.1, 0.4), "M_WindowLit", b=0.02)
windmill = wm.finish(smooth_angle=30)
hub = U(WIND[0], WIND[1] - 1.05, wy + 3.0)
bl = MB("WindmillBlades", seed=10)
cyl(bl, tuple(hub), 0.16, 0.3, 8, "M_WoodDark", rot=(90, 0, 0))
for k in range(4):
    a = k * 90
    M = Matrix.Translation(hub) @ rot_m((0, a, 0))
    cbox(bl, (0, 0, 1.25), (0.08, 0.06, 2.3), "M_WoodDark", b=0.01, M=M)
    cbox(bl, (0.22, 0.0, 1.45), (0.36, 0.03, 1.7), "M_Parchment", b=0.01, M=M)
blades = part(bl, hub)

# clouds around the island
cl = MB("Clouds", seed=11)
CLOUDS = [(-27, -6, -2.5, 1.5), (27, 0, -3.5, 1.8), (-25, 15, -1.5, 1.3), (25, 18, -2.0, 1.2), (-10, -17, -5.0, 1.6),
          (12, -16, -4.0, 1.4), (0, 22, -3.0, 1.5), (-30, 5, -7.0, 2.0), (30, 10, -8.0, 2.2)]
for (x, z, y, s) in CLOUDS:
    for k in range(5):
        ox = rng.uniform(-1.6, 1.6) * s; oz = rng.uniform(-0.8, 0.8) * s; r = rng.uniform(0.7, 1.2) * s
        sphere(cl, tuple(U(x + ox, z + oz, y + rng.uniform(0, 0.4) * s)), r, "M_Cloud", segs=8, rings=5, scl=(1.3, 1.0, 0.7))
clouds = cl.finish(smooth_angle=60)

root = empty("WD_World")
for o in (island, road, stones, decor_ob, trees_ob, water, windmill, blades, clouds):
    o.parent = root
export_fbx(collect(root), MODELS + "/WD_World.fbx")

# path for Unity (x, y, z)
data = {"points": [[round(p.x, 3), 0.05, round(p.y, 3)] for p in PATH], "length": round(length, 3),
        "castle": [CASTLE.x, 0.0, CASTLE.y], "portal": [PORTAL.x, 0.0, PORTAL.y], "windmillHub": [-hub.x, hub.z, -hub.y]}
import os
os.makedirs(UNITY + "/Data", exist_ok=True)
with open(UNITY + "/Data/path.json", "w") as f:
    json.dump(data, f)
save_blend("WD_World")
print("ok", len(island.data.polygons), "island faces")
