
# kit_env.py - modular dungeon architecture
import bpy, math, random
from mathutils import Vector, Matrix
import dlib
from dlib import MB, cbox, box_mm, hexa, lathe, cyl, sphere, torus, quad_strip, trs, rot_m

ROW = 0.25
GAP = 0.018
STONE_MIX = [("M_StoneA", 0.58), ("M_StoneB", 0.26), ("M_StoneC", 0.13), ("M_StoneDark", 0.03)]
FLOOR_MIX = [("M_FloorA", 0.5), ("M_FloorB", 0.35), ("M_FloorC", 0.15)]
CEIL_MIX = [("M_StoneC", 0.5), ("M_StoneDark", 0.3), ("M_StoneA", 0.2)]

def pick(rng, mix):
    r = rng.random(); acc = 0.0
    for m, w in mix:
        acc += w
        if r <= acc:
            return m
    return mix[-1][0]

def brick_courses(mb, rng, z0, nrows, x0=-1.0, x1=1.0, front=-0.12, M=None, flush=True, row_h=ROW,
                  lmin=0.36, lmax=0.62, mix=STONE_MIX, edge_mat="M_StoneA", prev=None, damage=True, bev_rng=(0.010, 0.022), back=-0.04):
    prev = prev or []
    for r in range(nrows):
        zb = z0 + r * row_h
        joints = []
        x = x0 + rng.uniform(0.14, min(0.55, (x1 - x0) * 0.5))
        while x < x1 - 0.16:
            for _ in range(3):
                bad = [p for p in prev if abs(x - p) < 0.11]
                if not bad:
                    break
                x = max(bad) + 0.12
            if x >= x1 - 0.16:
                break
            joints.append(x)
            x += rng.uniform(lmin, lmax)
        edges = [x0] + joints + [x1]
        for i in range(len(edges) - 1):
            a, b = edges[i], edges[i + 1]
            le = (i == 0); re = (i == len(edges) - 2)
            ga = 0.0 if (le and flush) else GAP / 2
            gb = 0.0 if (re and flush) else GAP / 2
            xa, xb = a + ga, b - gb
            w = xb - xa
            if w < 0.05:
                continue
            edge = (le or re) and flush
            fr = front if edge else front + rng.uniform(-0.012, 0.012)
            bev = 0.014 if edge else rng.uniform(*bev_rng)
            m = edge_mat if edge else pick(rng, mix)
            rot = (0, 0, 0) if edge else (rng.uniform(-0.5, 0.5), rng.uniform(-0.7, 0.7), rng.uniform(-0.6, 0.6))
            h = row_h - GAP
            zc = zb + row_h / 2
            if damage and not edge and rng.random() < 0.05:
                fr = front + 0.03; bev = 0.035
            cbox(mb, ((xa + xb) / 2, (fr + back) / 2, zc), (w, back - fr, h), m, bev, rot, M)
        prev = joints
    return prev

def mortar(mb, x0, x1, z0, z1, M=None, y0=-0.085, y1=0.05):
    box_mm(mb, (x0, y0, z0), (x1, y1, z1), "M_Mortar", 0.0, M)

def wall(name, kind, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    if kind == "base":
        mortar(mb, -1, 1, 0, 2.5)
        prev = brick_courses(mb, rng, 0.0, 1, row_h=0.5, lmin=0.7, lmax=1.1, front=-0.17,
                             mix=[("M_StoneB", 0.5), ("M_StoneC", 0.5)], edge_mat="M_StoneB", bev_rng=(0.025, 0.035))
        brick_courses(mb, rng, 0.5, 8, prev=prev)
    elif kind == "mid":
        mortar(mb, -1, 1, 0, 2.5)
        brick_courses(mb, rng, 0.0, 10)
    else:
        mortar(mb, -1, 1, 0, 2.5)
        brick_courses(mb, rng, 0.0, 9)
        brick_courses(mb, rng, 2.25, 1, row_h=0.09, lmin=0.8, lmax=1.0, front=-0.155, mix=[("M_StoneB", 1)],
                      edge_mat="M_StoneB", damage=False, bev_rng=(0.015, 0.02))
        brick_courses(mb, rng, 2.34, 1, row_h=0.16, lmin=0.8, lmax=1.0, front=-0.22, mix=[("M_StoneB", 1)],
                      edge_mat="M_StoneB", damage=False, bev_rng=(0.035, 0.045))
    return mb.finish()

def split_rect(rng, r, minsz, maxsz, out, depth=0):
    x0, y0, x1, y1 = r
    w, h = x1 - x0, y1 - y0
    can_x = w >= 2 * minsz; can_y = h >= 2 * minsz
    if depth > 8 or not (can_x or can_y) or (w <= maxsz and h <= maxsz and rng.random() < 0.35):
        out.append(r); return
    if can_x and (w >= h or not can_y):
        c = x0 + rng.uniform(minsz, w - minsz)
        split_rect(rng, (x0, y0, c, y1), minsz, maxsz, out, depth + 1)
        split_rect(rng, (c, y0, x1, y1), minsz, maxsz, out, depth + 1)
    else:
        c = y0 + rng.uniform(minsz, h - minsz)
        split_rect(rng, (x0, y0, x1, c), minsz, maxsz, out, depth + 1)
        split_rect(rng, (x0, c, x1, y1), minsz, maxsz, out, depth + 1)

def floor_tile(name, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    box_mm(mb, (-1, -1, -0.09), (1, 1, -0.025), "M_Grout")
    rects = []
    split_rect(rng, (-1, -1, 1, 1), 0.42, 1.0, rects)
    g = 0.012
    for (x0, y0, x1, y1) in rects:
        top = rng.uniform(-0.006, 0.006)
        cbox(mb, ((x0 + x1) / 2, (y0 + y1) / 2, (top - 0.09) / 2), (x1 - x0 - 2 * g, y1 - y0 - 2 * g, top + 0.09),
             pick(rng, FLOOR_MIX), rng.uniform(0.015, 0.03), (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), 0))
    return mb.finish()

def ceil_tile(name, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    box_mm(mb, (-1, -1, -0.04), (1, 1, 0.12), "M_Mortar")
    rects = []
    split_rect(rng, (-1, -1, 1, 1), 0.6, 1.4, rects)
    g = 0.014
    for (x0, y0, x1, y1) in rects:
        bot = -0.12 + rng.uniform(-0.015, 0.015)
        cbox(mb, ((x0 + x1) / 2, (y0 + y1) / 2, (bot + 0.04) / 2), (x1 - x0 - 2 * g, y1 - y0 - 2 * g, 0.04 - bot),
             pick(rng, CEIL_MIX), rng.uniform(0.02, 0.035))
    return mb.finish()

def corner_pillar(name, kind, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    z = 0.0
    if kind == "base":
        cbox(mb, (0, 0, 0.25), (0.76, 0.76, 0.49), "M_StoneB", 0.035)
        z = 0.5; n = 4
    elif kind == "mid":
        n = 5
    else:
        n = 4
    for i in range(n):
        sx = 0.6 + rng.uniform(-0.015, 0.015); sy = 0.6 + rng.uniform(-0.015, 0.015)
        if i % 2:
            sx -= 0.04
        else:
            sy -= 0.04
        cbox(mb, (rng.uniform(-0.006, 0.006), rng.uniform(-0.006, 0.006), z + 0.25), (sx, sy, 0.484),
             pick(rng, [("M_StoneB", 0.6), ("M_StoneA", 0.4)]), rng.uniform(0.02, 0.035), (0, 0, rng.uniform(-1, 1)))
        z += 0.5
    if kind == "top":
        cbox(mb, (0, 0, 2.1), (0.68, 0.68, 0.2), "M_StoneB", 0.025)
        cbox(mb, (0, 0, 2.35), (0.82, 0.82, 0.3), "M_StoneB", 0.045)
    return mb.finish()

def column(name, H, seed):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    cbox(mb, (0, 0, 0.15), (1.0, 1.0, 0.3), "M_StoneB", 0.03)
    lathe(mb, [(0.48, 0.3), (0.48, 0.36), (0.43, 0.43), (0.41, 0.5)], 16, "M_StoneB")
    z = 0.5; top = H - 0.75
    nd = max(2, int(round((top - z) / 1.1)))
    dh = (top - z) / nd
    for i in range(nd):
        r0 = 0.40 - 0.03 * (i / nd); r1 = 0.40 - 0.03 * ((i + 1) / nd)
        lathe(mb, [(r0 - 0.012, z + 0.004), (r0, z + 0.025), (r1, z + dh - 0.025), (r1 - 0.012, z + dh - 0.004)], 16,
              pick(rng, [("M_StoneB", 0.6), ("M_StoneA", 0.4)]), phase=rng.random())
        z += dh
    lathe(mb, [(0.37, top), (0.37, top + 0.08), (0.46, top + 0.3), (0.5, top + 0.42)], 16, "M_StoneB")
    cbox(mb, (0, 0, H - 0.165), (1.05, 1.05, 0.33), "M_StoneB", 0.03)
    return mb.finish()

def beam(name):
    mb = MB(name, seed=3)
    cbox(mb, (0, 0, -0.18), (2.0, 0.28, 0.36), "M_WoodDark", 0.03)
    return mb.finish()

# segmental arch geometry (shared with doors/gates)
ARCH_HALF = 1.7
ARCH_SPRING = 3.24
ARCH_R = 1.945
ARCH_CZ = ARCH_SPRING + 1.0 - ARCH_R   # crown at 4.24

def arch_inner_z(x):
    if abs(x) >= ARCH_HALF:
        return ARCH_SPRING
    return ARCH_CZ + math.sqrt(max(0.0, ARCH_R * ARCH_R - x * x))

def arch(name, seed, height=5.0):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    R, CZ, T = ARCH_R, ARCH_CZ, 0.5
    for s in (-1, 1):
        cbox(mb, (s * 2.06, 0, 0.2), (0.84, 0.92, 0.4), "M_StoneB", 0.03)
        z = 0.4; i = 0
        while z < 2.99:
            h = min(0.52, 3.0 - z)
            w = 0.70 if i % 2 == 0 else 0.62
            cbox(mb, (s * (1.7 + w / 2), 0, z + h / 2), (w - 0.012, 0.8, h - 0.014),
                 pick(rng, [("M_StoneB", 0.6), ("M_StoneA", 0.4)]), 0.03)
            z += h; i += 1
        cbox(mb, (s * 2.08, 0, 3.12), (0.76, 0.9, 0.24), "M_StoneB", 0.035)
    a_l = math.atan2(ARCH_SPRING - CZ, -ARCH_HALF)
    a_r = math.atan2(ARCH_SPRING - CZ, ARCH_HALF)
    N = 9; g = math.radians(0.35)
    for k in range(N):
        t0 = a_l + (a_r - a_l) * k / N - g
        t1 = a_l + (a_r - a_l) * (k + 1) / N + g
        key = (k == N // 2)
        th = 0.62 if key else T
        d = 0.46 if key else 0.40
        pts = []
        for yy in (-d, d):
            pts += [(R * math.cos(t0), yy, CZ + R * math.sin(t0)), (R * math.cos(t1), yy, CZ + R * math.sin(t1)),
                    ((R + th) * math.cos(t1), yy, CZ + (R + th) * math.sin(t1)), ((R + th) * math.cos(t0), yy, CZ + (R + th) * math.sin(t0))]
        hexa(mb, pts, "M_StoneB" if (k % 2 == 0) else "M_StoneA")
    xs = [-2.48, -1.7] + [-1.7 + 3.4 * i / 16 for i in range(1, 16)] + [1.7, 2.48]
    bot = [(x, 0, arch_inner_z(x)) for x in xs]
    top = [(x, 0, height) for x in xs]
    for yy, rev in ((-0.36, False), (0.36, True)):
        a = [(p[0], yy, p[2]) for p in bot]; b = [(p[0], yy, p[2]) for p in top]
        if rev:
            quad_strip(mb, b, a, "M_StoneC")
        else:
            quad_strip(mb, a, b, "M_StoneC")
    def ring_top(x):
        rr = R + 0.64
        if abs(x) >= rr:
            return -1e9
        return CZ + math.sqrt(rr * rr - x * x)
    for side in (-1, 1):
        M = Matrix.Translation((0, -0.32 if side < 0 else 0.32, 0)) @ (rot_m((0, 0, 0)) if side < 0 else rot_m((0, 0, 180)))
        z = ARCH_SPRING
        r = 0
        while z + 0.2 < height:
            joints = []
            x = -2.48 + rng.uniform(0.2, 0.5)
            while x < 2.3:
                joints.append(x); x += rng.uniform(0.4, 0.65)
            edges = [-2.48] + joints + [2.48]
            for i in range(len(edges) - 1):
                a, b = edges[i] + 0.009, edges[i + 1] - 0.009
                lo = max(ring_top(a), ring_top(b), ring_top(0.0) if a < 0 < b else -1e9)
                if z < lo + 0.02:
                    continue
                hh = min(ROW, height - z) - GAP
                cbox(mb, ((a + b) / 2, -0.04, z + hh / 2 + GAP / 2), (b - a, 0.08, hh), pick(rng, STONE_MIX),
                     rng.uniform(0.01, 0.02), (0, rng.uniform(-0.6, 0.6), 0), M)
            z += ROW; r += 1
    return mb.finish()

def stairs(name, n=12, run=10.0 / 12, rise=2.5 / 12, width=4.0, seed=7):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    for i in range(n):
        y0 = -i * run; y1 = -(i + 1) * run
        ztop = (i + 1) * rise
        if rng.random() < 0.6:
            cuts = sorted([rng.uniform(-1.3, -0.3), rng.uniform(0.3, 1.3)])
        else:
            cuts = [rng.uniform(-0.7, 0.7)]
        xs = [-width / 2] + cuts + [width / 2]
        for k in range(len(xs) - 1):
            xa = xs[k] + (0.008 if k > 0 else 0.0); xb = xs[k + 1] - (0.008 if k < len(xs) - 2 else 0.0)
            cbox(mb, ((xa + xb) / 2, (y0 + y1) / 2 - 0.004, ztop - 0.2 + rng.uniform(-0.004, 0.004)),
                 (xb - xa, run - 0.012, 0.4), pick(rng, [("M_StoneB", 0.5), ("M_StoneA", 0.3), ("M_StoneC", 0.2)]),
                 rng.uniform(0.02, 0.035))
    return mb.finish()

def pit(name, seed=11):
    mb = MB(name, seed=seed); rng = random.Random(seed)
    zt = lambda y: -1.4 + (1 - y) * 0.675
    pts = [(-2, 1, -1.6), (2, 1, -1.6), (2, -1, -1.6), (-2, -1, -1.6), (-2, 1, -1.4), (2, 1, -1.4), (2, -1, -0.05), (-2, -1, -0.05)]
    hexa(mb, pts, "M_StoneDark")
    for i in range(18):
        y = rng.uniform(-0.55, 0.85); x = rng.uniform(-1.75, 1.75)
        s = rng.uniform(0.14, 0.42)
        cbox(mb, (x, y, zt(y) + s * 0.28), (s * rng.uniform(0.8, 1.4), s * rng.uniform(0.7, 1.2), s * rng.uniform(0.5, 0.9)),
             pick(rng, STONE_MIX), rng.uniform(0.02, 0.05), (rng.uniform(-25, 25), rng.uniform(-25, 25), rng.uniform(0, 360)))
    M = Matrix.Translation((0, 1, 0))
    mortar(mb, -2, 2, -1.5, 0, M)
    brick_courses(mb, rng, -1.5, 6, x0=-2, x1=2, M=M)
    for sx, ang in ((2, -90), (-2, 90)):
        M = Matrix.Translation((sx, 0, 0)) @ rot_m((0, 0, ang))
        mortar(mb, -1, 1, -1.5, 0, M)
        brick_courses(mb, rng, -1.5, 6, M=M)
    for edge_y, sgn in ((1.0, -1),):
        x = -1.85
        while x < 1.7:
            w = rng.uniform(0.3, 0.6)
            dy = rng.uniform(0.12, 0.3)
            cbox(mb, (x + w / 2, edge_y + sgn * dy / 2, -0.045), (w - 0.03, dy + 0.1, 0.09), pick(rng, FLOOR_MIX),
                 0.02, (sgn * rng.uniform(2, 8), rng.uniform(-4, 4), rng.uniform(-6, 6)))
            x += w
    return mb.finish()

def build():
    dlib.reset()
    objs = []
    for v, sd in (("A", 101), ("B", 202), ("C", 303)):
        objs.append(wall("WallBase_" + v, "base", sd))
        objs.append(wall("WallMid_" + v, "mid", sd + 7))
        objs.append(wall("WallTop_" + v, "top", sd + 13))
        objs.append(floor_tile("Floor_" + v, sd + 21))
        objs.append(ceil_tile("Ceil_" + v, sd + 33))
    objs.append(corner_pillar("Pillar_Base", "base", 41))
    objs.append(corner_pillar("Pillar_Mid", "mid", 42))
    objs.append(corner_pillar("Pillar_Top", "top", 43))
    objs.append(column("Column_5", 5.0, 51))
    objs.append(column("Column_75", 7.5, 52))
    objs.append(beam("Beam_2"))
    objs.append(arch("Arch_4", 61, 5.0))
    objs.append(stairs("Stairs_12"))
    objs.append(pit("Pit_4x2"))
    return objs
