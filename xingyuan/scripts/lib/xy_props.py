# Xingyuan - courtyard furnishings: plaques (匾额), couplet boards (楹联), stele on a turtle (碑/龟趺),
# lanterns, B1 tree planters with procedural trees, B2 bamboo beds, pool stones, gate lanterns.
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
import xy_core as C, xy_parts as PT, xy_layout as LY

FONT = r'C:\Windows\Fonts\simkai.ttf'

def _font():
    f = bpy.data.fonts.get('XY_KaiTi')
    if f is None:
        f = bpy.data.fonts.load(FONT)
        f.name = 'XY_KaiTi'
    return f

def text_mesh(name, txt, size, coll, mat, extrude=0.008, vertical=False, spacing=1.0):
    """Create a text mesh centred at the origin in the XZ plane (facing -Y). vertical: stack characters."""
    objs = []
    chars = list(txt)
    if not vertical:
        lines = [txt]
    else:
        lines = chars
    cu = bpy.data.curves.new(name, 'FONT')
    cu.font = _font()
    cu.body = txt if not vertical else '\n'.join(chars)
    cu.size = size
    cu.extrude = extrude
    cu.space_character = spacing
    cu.space_line = 0.95
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    cu.resolution_u = 4
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    bpy.data.objects.remove(o)
    bpy.data.curves.remove(cu)
    # text lies in XY, facing +Z; rotate to XZ facing -Y
    me.transform(Matrix.Rotation(math.radians(90), 4, 'X'))
    me.materials.clear()
    me.materials.append(bpy.data.materials[mat])
    ob = bpy.data.objects.new(name, me)
    C.link(ob, coll)
    return ob

def plaque(name, coll, center, facing, w, h, txt=None, tilt=8.0, frame='M_Gold', board='M_BlackLacquer', txt_mat='M_Gold',
           brackets=True):
    """Horizontal plaque (匾): board with a gold frame and raised gold characters (right-to-left reading).
    facing: (nx, ny) outward normal. tilt: degrees leaning forward (top out)."""
    mb = C.MB()
    t = 0.07
    # board in local frame: X along width, -Y = front, Z up; origin = board centre
    mb.box((-w / 2, -t / 2, -h / 2), (w / 2, t / 2, h / 2), board)
    fw = 0.07
    for k, (x0, x1, z0, z1) in enumerate(((-w / 2 - 0.003, w / 2 + 0.003, h / 2 - fw, h / 2 + 0.003),
                                          (-w / 2 - 0.003, w / 2 + 0.003, -h / 2 - 0.003, -h / 2 + fw),
                                          (-w / 2 - 0.002, -w / 2 + fw, -h / 2 + fw, h / 2 - fw),
                                          (w / 2 - fw, w / 2 + 0.002, -h / 2 + fw, h / 2 - fw))):
        mb.box((x0, -t / 2 - 0.018 - 0.002 * (k < 2), z0), (x1, t / 2 + 0.003, z1), frame)
    # inner thin red line
    fi = 0.11
    for (x0, x1, z0, z1) in ((-w / 2 + fi, w / 2 - fi, h / 2 - fi - 0.012, h / 2 - fi), (-w / 2 + fi, w / 2 - fi, -h / 2 + fi, -h / 2 + fi + 0.012),
                             (-w / 2 + fi, -w / 2 + fi + 0.012, -h / 2 + fi, h / 2 - fi), (w / 2 - fi - 0.012, w / 2 - fi, -h / 2 + fi, h / 2 - fi)):
        mb.box((x0, -t / 2 - 0.006, z0), (x1, t / 2, z1), 'M_RedPaint')
    if brackets:
        # 匾托: small scroll-shaped supports under both ends
        for sx in (-1, 1):
            x = sx * (w / 2 - 0.35)
            mb.box((x - 0.09, -t / 2 - 0.01, -h / 2 - 0.16), (x + 0.09, t / 2, -h / 2), frame)
            mb.box((x - 0.15, -t / 2 - 0.012, -h / 2 - 0.08), (x - 0.09, t / 2, -h / 2 - 0.02), frame)
            mb.box((x + 0.09, -t / 2 - 0.012, -h / 2 - 0.08), (x + 0.15, t / 2, -h / 2 - 0.02), frame)
    ob = mb.finish(name, coll)
    objs = [ob]
    if txt:
        n = len(txt)
        size = min(h * 0.62, (w - 0.4) / n * 0.95)
        # traditional plaques read right to left: reverse the string for left-to-right layout
        tm = text_mesh(name + '_字', txt[::-1], size, coll, txt_mat, extrude=0.010, spacing=1.15)
        tm.data.transform(Matrix.Translation((0, -t / 2 - 0.012, 0)))
        objs.append(tm)
    nx, ny = facing
    rz = math.atan2(nx, -ny)      # local -Y -> facing
    M = Matrix.Translation(center) @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Rotation(math.radians(tilt), 4, 'X')
    for o in objs:
        o.matrix_world = M
    return objs

def couplet(name, coll, col_xy, col_r, facing, z0, z1, width=0.34):
    """Blank couplet board (楹联) curved around the front of a column, with a cloud head and foot."""
    mb = C.MB()
    nx, ny = facing
    ang0 = math.atan2(ny, nx)
    R = col_r + 0.025
    half = (width / 2) / R
    N = 8
    t = 0.035
    rows_o = []; rows_i = []
    for z in (z0, z1):
        ro = []; ri = []
        for k in range(N + 1):
            a = ang0 - half + 2 * half * k / N
            ro.append(Vector((col_xy[0] + (R + t) * math.cos(a), col_xy[1] + (R + t) * math.sin(a), z)))
            ri.append(Vector((col_xy[0] + R * math.cos(a), col_xy[1] + R * math.sin(a), z)))
        rows_o.append(ro); rows_i.append(ri)
    # outer face
    for k in range(N):
        mb.face([rows_o[0][k], rows_o[0][k + 1], rows_o[1][k + 1], rows_o[1][k]], 'M_BlackLacquer')
        mb.face([rows_i[0][k + 1], rows_i[0][k], rows_i[1][k], rows_i[1][k + 1]], 'M_BlackLacquer')
        mb.face([rows_o[1][k], rows_o[1][k + 1], rows_i[1][k + 1], rows_i[1][k]], 'M_BlackLacquer')
        mb.face([rows_o[0][k + 1], rows_o[0][k], rows_i[0][k], rows_i[0][k + 1]], 'M_BlackLacquer')
    for (k, kk) in ((0, 0), (N, N)):
        mb.face([rows_i[0][k], rows_o[0][k], rows_o[1][k], rows_i[1][k]], 'M_BlackLacquer')
    # gold edge strips
    for sgn in (-1, 1):
        a = ang0 + sgn * (half - 0.06)
        p = Vector((col_xy[0] + (R + t + 0.003) * math.cos(a), col_xy[1] + (R + t + 0.003) * math.sin(a), 0))
        mb.box((p.x - 0.008, p.y - 0.008, z0 + 0.12), (p.x + 0.008, p.y + 0.008, z1 - 0.12), 'M_Gold')
    # cloud head and foot (gold)
    for (zc, hh) in ((z1 + 0.06, 0.12), (z0 - 0.05, 0.1)):
        c = Vector((col_xy[0] + (R + t) * math.cos(ang0), col_xy[1] + (R + t) * math.sin(ang0), zc))
        mb.lathe([(0.0, -hh / 2), (0.07, -hh / 2 + 0.01), (0.09, 0.0), (0.06, hh / 2 - 0.01), (0.0, hh / 2)], 10, 'M_Gold',
                 center=tuple(c))
    return mb.finish(name, coll)

# ------------------------------------------------------------------ stele + turtle (碑 / 龟趺)
def turtle(mb, cx, cy, z0, heading=0.0, s=1.0, m='M_StoneTurtle'):
    """Stylised bixi turtle: shell dome, plinth, dragon head and neck, four flippers, tail.
    heading: direction the head points (radians, 0 = +Y)."""
    R = Matrix.Rotation(heading, 4, 'Z')
    T = Matrix.Translation((cx, cy, z0))
    M = T @ R @ Matrix.Diagonal((s, s, s, 1))
    sub = C.MB()
    # base slab
    sub.box((-0.62, -1.05, 0.0), (0.62, 1.05, 0.12), m)
    # shell: scaled lathe (ellipse in plan)
    prof = [(0.92, 0.12), (0.95, 0.16), (0.90, 0.22), (0.80, 0.36), (0.62, 0.50), (0.36, 0.60), (0.12, 0.64), (0.02, 0.645)]
    sub.lathe(prof, 28, m, center=(0, 0, 0))
    # elongate along Y (heading axis): scale y by 1.05/0.95 later via transform of the shell verts
    # rim band
    sub.lathe([(0.97, 0.13), (1.0, 0.16), (0.97, 0.19)], 28, m)
    # neck + head (toward +Y)
    sub.cyl((0, 0.7, 0.30), (0, 1.15, 0.52), 0.17, 12, m, r1=0.15)
    sub.lathe([(0.03, -0.18), (0.16, -0.14), (0.2, -0.02), (0.18, 0.1), (0.12, 0.18), (0.03, 0.2)], 12, m, center=(0, 1.28, 0.6))
    sub.box((-0.1, 1.28, 0.48), (0.1, 1.52, 0.62), m)                 # snout
    for sx in (-1, 1):
        sub.cyl((sx * 0.1, 1.2, 0.72), (sx * 0.22, 1.08, 0.86), 0.04, 6, m, r1=0.02)   # horns / mane tufts
    # flippers
    for sx in (-1, 1):
        for sy in (-1, 1):
            p0 = (sx * 0.62, sy * 0.55, 0.18)
            p1 = (sx * 1.0, sy * 0.85, 0.14)
            sub.cyl(p0, p1, 0.13, 8, m, r1=0.09)
    # tail
    sub.cyl((0, -0.85, 0.2), (0, -1.15, 0.15), 0.08, 8, m, r1=0.03)
    # stele socket on the back
    sub.box((-0.55, -0.25, 0.55), (0.55, 0.25, 0.75), m)
    # stretch shell along local Y
    bm = sub.bm
    for v in bm.verts:
        if abs(v.co.y) < 1.0 and v.co.z > 0.1 and abs(v.co.x) <= 1.0 and v.co.z < 0.66:
            v.co.y *= 1.12
    sub.transform(M)
    return sub

def stele(coll, cx, cy, z_water, z_bottom):
    """The 许愿池 stele: white marble body, black lacquered north face with red characters, on a turtle
    facing south, standing on a stone pedestal rising out of the water."""
    mb = C.MB()
    zp = z_water + 0.12
    zp = z_water - 0.06                                                                          # turtle sits just in the water
    mb.box((cx - 0.55, cy - 0.85, z_bottom), (cx + 0.55, cy + 0.85, zp), 'M_StoneGrey')       # pedestal (submerged)
    tm = turtle(None, cx, cy, zp, heading=math.pi, s=0.62)
    tob = tm.finish('B3_碑_龟趺', coll, merge=0.0005)
    zt = zp + 0.62 * 0.75
    W, T, H = 0.88, 0.26, 2.15
    mb.box((cx - W / 2, cy - T / 2, zt - 0.05), (cx + W / 2, cy + T / 2, zt + H), 'M_Marble')
    # rounded top cap
    mb.box((cx - W / 2 + 0.02, cy - T / 2 + 0.01, zt + H), (cx + W / 2 - 0.02, cy + T / 2 - 0.01, zt + H + 0.05), 'M_Marble')
    # black facing on the north side
    mb.box((cx - W / 2 + 0.005, cy + T / 2, zt + 0.02), (cx + W / 2 - 0.005, cy + T / 2 + 0.012, zt + H - 0.005), 'M_BlackStone')
    ob = mb.finish('B3_碑_许愿池', coll)
    # red characters on the north face (read top to bottom)
    t = text_mesh('B3_碑_字', '許願池', 0.34, coll, 'M_RedPaint', extrude=0.004, vertical=True)
    t.matrix_world = Matrix.Translation((cx, cy + T / 2 + 0.014, zt + H * 0.55)) @ Matrix.Rotation(math.pi, 4, 'Z')
    return ob

def b1_stele(coll, cx, cy):
    """Stele inside the B1 pavilion: lotus pedestal, black stone with a gold relief panel (portrait shown as a raised panel)."""
    mb = C.MB()
    mb.box((cx - 0.85, cy - 0.45, 0.0), (cx + 0.85, cy + 0.45, 0.18), 'M_StoneGrey')
    segs = 32
    rows = []
    for (rx, ry, z) in ((0.80, 0.40, 0.18), (0.82, 0.42, 0.28), (0.72, 0.36, 0.42), (0.6, 0.3, 0.5), (0.62, 0.32, 0.56)):
        row = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            mod = 1.0 + 0.05 * (abs(math.cos(6 * a)) ** 0.7 - 0.5)
            row.append((cx + rx * mod * math.cos(a), cy + ry * mod * math.sin(a), z))
        rows.append(row)
    vr, _ = mb.quad_strip(rows, 'M_StoneGrey', smooth=True, closed_u=True)
    mb.bm.faces.new(vr[-1]).material_index = mb.slot('M_StoneGrey')
    W, T, H = 1.05, 0.28, 2.05
    z0 = 0.56
    mb.box((cx - W / 2, cy - T / 2, z0), (cx + W / 2, cy + T / 2, z0 + H), 'M_BlackStone')
    mb.box((cx - W / 2 - 0.04, cy - T / 2 - 0.02, z0 + H), (cx + W / 2 + 0.04, cy + T / 2 + 0.02, z0 + H + 0.12), 'M_BlackStone')
    # gold relief panel on the south face
    mb.box((cx - 0.36, cy - T / 2 - 0.02, z0 + 0.35), (cx + 0.36, cy - T / 2, z0 + 1.6), 'M_Gold')
    mb.box((cx - 0.30, cy - T / 2 - 0.035, z0 + 0.42), (cx + 0.30, cy - T / 2 - 0.02, z0 + 1.52), 'M_Gold')
    return mb.finish('B1亭_碑', coll)

# ------------------------------------------------------------------ trees (procedural)
def _branch(mb, rng, p, d, L, r, depth, tips, m='M_Bark'):
    q = p + d * L
    mb.cyl(p, q, r, 7 if r > 0.04 else 5, m, r1=r * 0.74, smooth=True)
    if depth == 0 or L < 0.22:
        tips.append(q)
        return
    n = 2 if depth > 2 else 3
    for i in range(n):
        ax = d.orthogonal().normalized()
        ax.rotate(Matrix.Rotation(rng.uniform(0, 2 * math.pi), 3, d))
        ang = math.radians(rng.uniform(24, 44))
        nd = d.copy(); nd.rotate(Matrix.Rotation(ang, 3, ax))
        nd.z += 0.10; nd.normalize()
        _branch(mb, rng, q, nd, L * rng.uniform(0.64, 0.80), r * 0.70, depth - 1, tips, m)
    tips.append(q)

def leaf_src(name='SRC_leafspray_plum', m='M_LeafPurple', n=70, rad=0.38, L=0.085, W=0.040):
    """A spray of small elliptic leaves inside a ball of radius rad (instanced many times per tree)."""
    o = bpy.data.objects.get(name)
    if o:
        return o
    mb = C.MB()
    rng = random.Random(4)
    for i in range(n):
        c = Vector((rng.gauss(0, rad * 0.5), rng.gauss(0, rad * 0.5), rng.gauss(0, rad * 0.4)))
        if c.length > rad:
            c = c.normalized() * rad
        a = rng.uniform(0, 2 * math.pi); b = rng.uniform(-0.5, 0.9)
        dx = Vector((math.cos(a) * math.cos(b), math.sin(a) * math.cos(b), math.sin(b) * 0.4)).normalized()
        dy = dx.cross(Vector((rng.gauss(0, 0.3), rng.gauss(0, 0.3), 1.0)).normalized()).normalized()
        l = L * rng.uniform(0.8, 1.25); w = W * rng.uniform(0.8, 1.2)
        mb.face([c, c + dx * l * 0.45 + dy * w, c + dx * l, c + dx * l * 0.45 - dy * w], m)
        mb.face([c, c + dx * l * 0.45 - dy * w, c + dx * l, c + dx * l * 0.45 + dy * w], m)  # back side
    return mb.finish(name, C.lib_coll(), recalc=False)

def tree(name, coll, base, seed=1, height=5.6, crown=2.3, leaf_src=None, n_spray=900):
    """紫叶李-like tree: short trunk, 4-5 ascending limbs, dense oval crown of leaf sprays."""
    rng = random.Random(seed)
    mb = C.MB()
    tips = []
    p = Vector(base)
    lean = Vector((rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), 1.0)).normalized()
    trunk_h = 1.9 + rng.uniform(-0.15, 0.15)
    mb.cyl(p - Vector((0, 0, 0.1)), p + lean * trunk_h, 0.105, 10, 'M_Bark', r1=0.085, smooth=True)
    top = p + lean * trunk_h
    nlimb = 5
    for i in range(nlimb):
        a = 2 * math.pi * i / nlimb + rng.uniform(-0.35, 0.35)
        nd = Vector((math.cos(a) * 0.62, math.sin(a) * 0.62, 1.0)).normalized()
        _branch(mb, rng, top, nd, height * 0.26, 0.058, 4, tips)
    ob = mb.finish(name + '_枝干', coll)
    # crown: ellipsoid, sprays biased to the outer shell and to branch tips
    cc = Vector((base[0], base[1], base[2] + trunk_h + (height - trunk_h) * 0.52))
    ry = (height - trunk_h) * 0.55
    tr = []
    for k in range(n_spray):
        if k % 3 == 0 and tips:
            q = rng.choice(tips) + Vector((rng.gauss(0, 0.25), rng.gauss(0, 0.25), rng.gauss(0, 0.2)))
        else:
            u = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
            rr = rng.uniform(0.62, 1.0) ** 0.5
            q = cc + Vector((u.x * crown * rr, u.y * crown * rr, u.z * ry * rr))
        rel = q - cc
        k2 = (rel.x / crown) ** 2 + (rel.y / crown) ** 2 + (rel.z / ry) ** 2
        if k2 > 1.0:
            q = cc + rel / math.sqrt(k2)
        rot = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, 6.28))
        tr.append((tuple(q), rot, rng.uniform(0.85, 1.35)))
    C.instancer(name + '_叶', leaf_src, tr, coll)
    return ob

def planter(name, coll, cx, cy, size=2.4, h=0.5, z0=LY.ZC, wood=True):
    mb = C.MB()
    s = size / 2; t = 0.18
    for (x0, y0, x1, y1) in ((-s, -s, s, -s + t), (-s, s - t, s, s), (-s, -s + t, -s + t, s - t), (s - t, -s + t, s, s - t)):
        mb.box((cx + x0, cy + y0, z0), (cx + x1, cy + y1, z0 + h), 'M_Granite')
    w = 0.26
    capm = 'M_WoodBrown' if wood else 'M_Granite'
    for (x0, y0, x1, y1) in ((-s - 0.02, -s - 0.02, s + 0.02, -s + w), (-s - 0.02, s - w, s + 0.02, s + 0.02),
                             (-s - 0.02, -s + w, -s + w, s - w), (s - w, -s + w, s + 0.02, s - w)):
        mb.box((cx + x0, cy + y0, z0 + h), (cx + x1, cy + y1, z0 + h + 0.05), capm)
    mb.box((cx - s + t, cy - s + t, z0), (cx + s - t, cy + s - t, z0 + h - 0.06), 'M_Soil')
    return mb.finish(name, coll)

# ------------------------------------------------------------------ bamboo
def bamboo_srcs():
    o = bpy.data.objects.get('SRC_bamboo_spray')
    if o:
        return o
    mb = C.MB()
    rng = random.Random(9)
    # one spray: a thin twig with ~22 drooping lanceolate leaves
    for i in range(40):
        a = rng.uniform(0, 2 * math.pi)
        c = Vector((rng.gauss(0, 0.22), rng.gauss(0, 0.22), rng.uniform(-0.3, 0.3)))
        d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.8, -0.15))).normalized()
        s = d.cross(Vector((0, 0, 1)))
        if s.length < 1e-4:
            s = Vector((1, 0, 0))
        s = s.normalized() * rng.uniform(0.018, 0.026)
        L = rng.uniform(0.16, 0.26)
        mid = c + d * (L * 0.35)
        mb.face([c, mid + s, c + d * L, mid - s], 'M_LeafBamboo')
        mb.face([c, mid - s, c + d * L, mid + s], 'M_LeafBamboo')
    return mb.finish('SRC_bamboo_spray', C.lib_coll(), recalc=False)

def bamboo_bed(name, coll, x0, y0, x1, y1, z0=LY.ZC, density=3.2, seed=3, hmax=6.2, curb=False):
    rng = random.Random(seed)
    mb = C.MB()
    if curb:
        t = 0.15
        for (a0, b0, a1, b1) in ((x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0 + t, x0 + t, y1 - t), (x1 - t, y0 + t, x1, y1 - t)):
            mb.box((a0, b0, z0), (a1, b1, z0 + 0.12), 'M_Granite')
    mb.box((x0, y0, z0 - 0.05), (x1, y1, z0 + 0.04), 'M_Soil')
    n = int((x1 - x0) * (y1 - y0) * density)
    sprays = []
    for i in range(n):
        x = rng.uniform(x0 + 0.15, x1 - 0.15); y = rng.uniform(y0 + 0.15, y1 - 0.15)
        h = rng.uniform(hmax * 0.55, hmax)
        p0 = Vector((x, y, z0))
        r = rng.uniform(0.016, 0.028)
        d = Vector((rng.gauss(0, 0.06), rng.gauss(0, 0.06), 1.0)).normalized()
        p = p0
        pts = [p0]
        for sgi in range(4):
            q = p + d * (h / 4)
            mb.cyl(p, q, r, 5, 'M_BambooCulm', r1=r * 0.92, smooth=True, cap=False)
            p = q; pts.append(q)
            d = (d + Vector((rng.gauss(0, 0.06), rng.gauss(0, 0.06), -0.02))).normalized()
            r *= 0.9
        # sprays along the upper 65% of the culm, denser near the top, drooping outward
        ns = rng.randint(22, 32)
        for k in range(ns):
            t_ = 1.0 - (rng.random() ** 1.3) * 0.78
            seg = min(3, int(t_ * 4)); f = t_ * 4 - seg
            base = pts[seg].lerp(pts[seg + 1], f)
            off = Vector((rng.gauss(0, 0.28), rng.gauss(0, 0.28), rng.gauss(0, 0.1))) * (0.5 + t_)
            sprays.append((tuple(base + off), (rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(0, 6.28)),
                           rng.uniform(0.9, 1.4)))
    ob = mb.finish(name + '_竹竿', coll, recalc=False)
    C.instancer(name + '_竹叶', bamboo_srcs(), sprays, coll)
    return ob

# ------------------------------------------------------------------ build
def build_props():
    for k in ('B1 陈设', 'B2 陈设', 'B3 陈设', 'A1 匾联', 'A2 匾联', 'A5 匾联'):
        C.clear_coll(k)
    cB1 = C.coll('B1 陈设', C.coll('B1'))
    cB2 = C.coll('B2 陈设', C.coll('B2'))
    cB3 = C.coll('B3 陈设', C.coll('B3'))
    cA2 = C.coll('A2 匾联', C.coll('A2'))
    cA5 = C.coll('A5 匾联', C.coll('A5'))
    # ---- plaques
    plaque('A2_匾_芙蓉學堂', cA2, (24.65 + 0.17, 11.91, 3.70), (1, 0), 2.6, 0.78, '芙蓉學堂', tilt=6)
    cA1 = C.coll('A1 匾联', C.coll('A1'))
    plaque('A1_匾_鳴鳳學堂', cA1, (45.65 - 0.17, 11.91, 3.70), (-1, 0), 2.6, 0.78, '鳴鳳學堂', tilt=6)
    plaque('A5_匾_太華春光', cA5, (10.15 + 0.17, 40.04, 3.70), (1, 0), 2.6, 0.78, '太華春光', tilt=6)
    plaque('B1亭_匾_春色滿園', cB1, (35.15, 21.38 - 0.25, 2.62), (0, -1), 2.2, 0.72, '春色滿園', tilt=14)
    plaque('B3南亭_匾_步蟾', cB3, (20.65, 30.47 + 0.25, 2.62), (0, 1), 1.9, 0.68, '步蟾', tilt=12)
    plaque('B3北亭_匾', cB3, (20.62, 49.6 - 0.25, 2.72), (0, -1), 2.0, 0.66, None, tilt=12)
    # ---- couplet boards (blank: text not legible in the photos)
    for (nm, cxy, r, f, cl) in (('A2_楹联_左', (26.7, 10.26), 0.19, (1, 0), cA2), ('A2_楹联_右', (26.7, 13.55), 0.19, (1, 0), cA2),
                                ('A1_楹联_左', (43.6, 13.56), 0.19, (-1, 0), cA1), ('A1_楹联_右', (43.6, 10.26), 0.19, (-1, 0), cA1),
                                ('A5_楹联_左', (12.2, 38.39), 0.19, (1, 0), cA5), ('A5_楹联_右', (12.2, 41.69), 0.19, (1, 0), cA5),
                                ('B1亭_楹联_左', (33.6, 21.38), 0.18, (0, -1), cB1), ('B1亭_楹联_右', (36.7, 21.38), 0.18, (0, -1), cB1),
                                ('B3南亭_楹联_左', (18.8, 30.47), 0.18, (0, 1), cB3), ('B3南亭_楹联_右', (22.5, 30.47), 0.18, (0, 1), cB3),
                                ('B3北亭_楹联_左', (18.78, 49.6), 0.18, (0, -1), cB3), ('B3北亭_楹联_右', (22.47, 49.6), 0.18, (0, -1), cB3)):
        top = 3.35 if nm.startswith(('A2', 'A5')) else 2.75
        couplet(nm, cl, cxy, r, f, top - 2.25, top)
    # ---- stele + turtle in the pool, B1 pavilion stele
    stele(cB3, LY.STELE_B3[0], 40.05, LY.Z_WATER, LY.Z_POOL)
    b1_stele(cB1, 35.15, 24.6)
    # ---- lanterns on pedestals at the pool corners, and at the gate stair
    lsrc = PT.lantern_src()
    tr = []
    mb = C.MB()
    for (x, y) in LY.LANTERNS_B3:
        mb.box((x - 0.36, y - 0.36, LY.Z_POOL), (x + 0.36, y + 0.36, LY.ZC + 0.02), 'M_StoneGrey')
        tr.append(((x, y, LY.ZC + 0.02), (0, 0, math.radians(45)), 1.0))
    mb.finish('B3_灯座', cB3)
    C.instancer('B3_石灯', lsrc, tr, cB3)
    C.instancer('B1_院门石灯', lsrc, [((33.22, -6.62, LY.Z0), (0, 0, math.radians(45)), 1.0), ((37.08, -6.62, LY.Z0), (0, 0, math.radians(45)), 1.0)], cB1)
    # ---- pool stones
    mb = C.MB()
    rng = random.Random(21)
    for i in range(70):
        x = rng.uniform(15.0, 26.2); y = rng.uniform(33.4, 46.7)
        if abs(x - 20.6) < 1.2 and abs(y - 40.05) < 1.6:
            continue
        r = rng.uniform(0.18, 0.5)
        mb.lathe([(r, 0.0), (r * 1.02, r * 0.25), (r * 0.8, r * 0.5), (r * 0.4, r * 0.66), (0.0, r * 0.7)], 9, 'M_PoolStone',
                 center=(x, y, LY.Z_POOL - 0.02))
    mb.finish('B3_池底卵石', cB3)
    # ---- B1 planters and purple-leaf trees
    ls = leaf_src()
    for i, (x, y) in enumerate(LY.PLANTERS_B1):
        planter('B1_树池%d' % (i + 1), cB1, x, y, size=2.0, wood=True)
        tree('B1_紫叶李%d' % (i + 1), cB1, (x, y, LY.ZC + 0.44), seed=31 + i * 7, height=6.2 + 0.4 * (i % 2), crown=1.95, leaf_src=ls)
    # ---- gate: red lanterns hanging under the south eave (red discs in the aerial view)
    mb = C.MB()
    for x in (32.75, 37.55):
        y = -6.55
        mb.cyl((x, y, 3.25), (x, y, 2.95), 0.012, 6, 'M_BlackLacquer')
        mb.lathe([(0.08, 0.0), (0.24, 0.06), (0.30, 0.2), (0.30, 0.34), (0.24, 0.48), (0.08, 0.54)], 16, 'M_LanternRed', center=(x, y, 2.4))
        mb.lathe([(0.1, -0.04), (0.1, 0.02)], 12, 'M_Gold', center=(x, y, 2.4))
        mb.lathe([(0.1, 0.52), (0.1, 0.58)], 12, 'M_Gold', center=(x, y, 2.4))
    mb.finish('院门_红灯笼', C.coll('B1 院门'))
    # ---- B2 bamboo beds flanking the path between the A4 and A3 stairs
    for (nm, rect, sd) in LY.B2_BEDS:
        bamboo_bed(nm, cB2, *rect, seed=sd)
