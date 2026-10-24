# Xingyuan build library - reusable part sources (kept in the hidden _LIB collection and instanced).
import bpy, math
from mathutils import Vector, Matrix
import xy_core as C

def _get(name):
    return bpy.data.objects.get(name)

def _drop(name):
    o = bpy.data.objects.get(name)
    if o is not None:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)

# ------------------------------------------------------------------ helpers
def _kansha_profile(L, H, k=0.16, n=4, left=True, right=True):
    """2D outline (x, z) of a bracket arm (栱) of length L, height H, centred at x=0,
    lower ends rounded off (卷杀) over k metres in n facets. Counter-clockwise (viewed from -y)."""
    pts = []
    hz = H * 0.55
    if left:
        for i in range(n + 1):
            ang = (math.pi / 2) * (i / n)
            pts.append((-L / 2 + k * (1 - math.cos(ang)), hz * (1 - math.sin(ang))))
    else:
        pts.append((-L / 2, 0.0))
    if right:
        for i in range(n + 1):
            ang = (math.pi / 2) * (1 - i / n)
            pts.append((L / 2 - k * (1 - math.cos(ang)), hz * (1 - math.sin(ang))))
    else:
        pts.append((L / 2, 0.0))
    pts.append((L / 2, H))
    pts.append((-L / 2, H))
    return pts

def _extrude_xz(mb, outline, y0, y1, m, M=None):
    """Extrude a CCW (x,z) outline between y0 and y1 (with optional transform)."""
    M = M or Matrix.Identity(4)
    A = [M @ Vector((x, y0, z)) for x, z in outline]
    B = [M @ Vector((x, y1, z)) for x, z in outline]
    n = len(outline)
    mb.face(list(reversed(A)), m) if False else mb.face(A, m)
    mb.face(list(reversed(B)), m)
    for i in range(n):
        j = (i + 1) % n
        mb.face([A[i], A[j], B[j], B[i]], m)

def dou(mb, cx, cy, z0, w, d, h, m='M_RedLacquer', taper=0.75, ear=0.55):
    """斗: block w (x) x d (y) x h, lower part (欹) tapered."""
    he = h * ear
    hq = h - he
    b = [(cx - w * taper / 2, cy - d * taper / 2), (cx + w * taper / 2, cy - d * taper / 2),
         (cx + w * taper / 2, cy + d * taper / 2), (cx - w * taper / 2, cy + d * taper / 2)]
    t = [(cx - w / 2, cy - d / 2), (cx + w / 2, cy - d / 2), (cx + w / 2, cy + d / 2), (cx - w / 2, cy + d / 2)]
    vb = [Vector((x, y, z0)) for x, y in b]
    vm = [Vector((x, y, z0 + hq)) for x, y in t]
    vt = [Vector((x, y, z0 + h)) for x, y in t]
    mb.face(list(reversed(vb)), m)
    mb.face(vt, m)
    for i in range(4):
        j = (i + 1) % 4
        mb.face([vb[i], vb[j], vm[j], vm[i]], m)
        mb.face([vm[i], vm[j], vt[j], vt[i]], m)

def arm_x(mb, cx, cy, z0, L, H=0.18, W=0.12, m='M_RedLacquer', k=0.16):
    """栱 along X centred at (cx, cy), bottom at z0."""
    ol = _kansha_profile(L, H, k)
    M = Matrix.Translation((cx, 0, z0))
    _extrude_xz(mb, ol, cy - W / 2, cy + W / 2, m, M)

def arm_y(mb, cx, y0, y1, z0, H=0.18, W=0.12, m='M_RedLacquer', k=0.14, round_inner=False):
    """华栱/耍头 along Y from y0 to y1 (outer end rounded at the bottom)."""
    L = y1 - y0
    ol = _kansha_profile(L, H, k, left=round_inner, right=True)
    # map local x -> y
    R = Matrix.Rotation(math.radians(90), 4, 'Z')
    M = Matrix.Translation((cx, (y0 + y1) / 2, z0)) @ R
    _extrude_xz(mb, ol, -W / 2, W / 2, m, M)

# ------------------------------------------------------------------ columns
def column_src(name, H, r0=0.21, r1=0.185, segs=20, m='M_RedLacquer'):
    """Round column with entasis and rounded top (卷杀). Origin at the base."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    prof = []
    N = 10
    for i in range(N + 1):
        t = i / N
        z = (H - 0.08) * t
        r = r0 + (r1 - r0) * (t ** 1.6)
        prof.append((r, z))
    prof += [(r1 * 0.97, H - 0.04), (r1 * 0.88, H - 0.01), (r1 * 0.78, H)]
    mb.lathe(prof, segs, m, cap_bot=True, cap_top=True)
    o = mb.finish(name, C.lib_coll())
    for p in o.data.polygons:
        p.use_smooth = True
    return o

def base_src(name='SRC_base_lotus', R=0.44, m='M_StoneGrey'):
    """覆盆柱础: wide, flat lotus base with 16 raised petals (pointed tips at the rim) on a square plinth
    flush with the floor. The column stands on the flat top (z = 0.15)."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    s = R * 1.12
    mb.box((-s, -s, -0.12), (s, s, 0.0), m)
    segs = 128
    NT = 9
    rows = []
    for jt in range(NT + 1):
        t = jt / NT                       # 0 = outer rim, 1 = inner top edge
        r_base = R * (1.0 - 0.40 * t)
        z_base = 0.15 * math.sin(math.pi / 2 * t) ** 0.75
        row = []
        for k in range(segs):
            a = 2 * math.pi * k / segs
            ph = abs(math.cos(8 * a))     # 1 at the petal centre line, 0 between petals
            # petal relief: rounded ridge, strongest mid-petal, fading at the top edge
            bump = (ph ** 0.6) * math.sin(math.pi * min(1.0, t * 1.15)) * 0.028
            groove = (1 - ph) ** 6 * 0.018 * (1 - t)
            r = r_base + 0.035 * (ph ** 3) * (1 - t) ** 2 - 0.012 * (1 - ph) ** 4 * (1 - t)
            z = z_base + bump - groove
            if jt == 0:
                z = 0.0
            row.append((r * math.cos(a), r * math.sin(a), z))
        rows.append(row)
    # flat top disc (column seat)
    rt = R * 0.60
    rows.append([(rt * 0.98 * math.cos(2 * math.pi * k / segs), rt * 0.98 * math.sin(2 * math.pi * k / segs), 0.165) for k in range(segs)])
    vrows, faces = mb.quad_strip(rows, m, smooth=True, closed_u=True)
    f = mb.bm.faces.new(vrows[-1]); f.material_index = mb.slot(m); f.smooth = True
    o = mb.finish(name, C.lib_coll())
    try:
        o.data.set_sharp_from_angle(angle=math.radians(60))
    except Exception:
        pass
    return o

def base_plain_src(name='SRC_base_plain', R=0.27, m='M_StoneGrey'):
    if _get(name):
        return _get(name)
    mb = C.MB()
    mb.box((-R, -R, -0.1), (R, R, 0.0), m)
    mb.lathe([(R * 0.8, 0.0), (R * 0.78, 0.05), (R * 0.7, 0.08), (R * 0.66, 0.09)], 24, m)
    return mb.finish(name, C.lib_coll())

# ------------------------------------------------------------------ bracket sets
def bracket_outer_src(name='SRC_brk_outer'):
    """双杪 bracket set for the hall eave columns. Local: origin at column top centre,
    X along the facade, +Y outward (to the eave), Z up. Height to the 替木 top = 0.96."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    R = 'M_RedLacquer'
    # 栌斗
    dou(mb, 0, 0, 0.0, 0.42, 0.42, 0.26, R, taper=0.74, ear=0.6)
    # tier 1 (z 0.14-0.32): 泥道栱 along X, 华栱 along Y
    arm_x(mb, 0, 0, 0.14, 1.24)
    arm_y(mb, 0, -0.45, 0.55, 0.14)
    for x in (-0.53, 0.53, 0.0):
        dou(mb, x, 0, 0.32, 0.21, 0.19, 0.12, R)
    dou(mb, 0, 0.48, 0.32, 0.21, 0.21, 0.12, R)
    # tier 2 (z 0.38-0.56): 慢栱, 华栱2, 瓜子栱 at y=0.48
    arm_x(mb, 0, 0, 0.38, 1.86)
    arm_y(mb, 0, -0.45, 1.0, 0.38)
    arm_x(mb, 0, 0.48, 0.38, 1.24)
    for x in (-0.85, 0.85, 0.0):
        dou(mb, x, 0, 0.56, 0.21, 0.19, 0.12, R)
    for x in (-0.53, 0.53):
        dou(mb, x, 0.48, 0.56, 0.21, 0.19, 0.12, R)
    dou(mb, 0, 0.93, 0.56, 0.21, 0.21, 0.12, R)
    # tier 3 (z 0.62-0.80): 令栱 at y=0.93, 耍头 along Y
    arm_x(mb, 0, 0.93, 0.62, 1.24)
    # 耍头: straight beam with a bevelled nose
    W = 0.12
    nose = [(-0.75, 0.0), (0.42, 0.0), (0.5, 0.08), (0.5, 0.18), (-0.75, 0.18)]
    Mz = Matrix.Translation((0, 0.75, 0.62)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
    _extrude_xz(mb, nose, -W / 2, W / 2, R, Mz)
    for x in (-0.53, 0.53, 0.0):
        dou(mb, x, 0.93, 0.80, 0.21, 0.19, 0.12, R)
    # 替木 under the eave purlin
    mb.box((-0.8, 0.93 - 0.07, 0.86), (0.8, 0.93 + 0.07, 0.98), R)
    o = mb.finish(name, C.lib_coll())
    return o

def bracket_inner_src(name='SRC_brk_inner'):
    """Simple bracket for wall columns / corridor: 栌斗 + 泥道栱 + 3 斗. Height 0.44."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    R = 'M_RedLacquer'
    dou(mb, 0, 0, 0.0, 0.40, 0.40, 0.25, R, taper=0.74, ear=0.6)
    arm_x(mb, 0, 0, 0.13, 1.24)
    arm_y(mb, 0, -0.30, 0.30, 0.13, round_inner=True)
    for x in (-0.53, 0.53, 0.0):
        dou(mb, x, 0, 0.31, 0.21, 0.19, 0.12, R)
    return mb.finish(name, C.lib_coll())

def bracket_small_src(name='SRC_brk_small'):
    """Corridor bracket: 栌斗 + 替木 (as seen on the galleries). Height 0.32."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    R = 'M_RedLacquer'
    dou(mb, 0, 0, 0.0, 0.30, 0.30, 0.18, R, taper=0.74, ear=0.6)
    arm_x(mb, 0, 0, 0.10, 0.95, H=0.15, W=0.11, k=0.12)
    for x in (-0.38, 0.38):
        dou(mb, x, 0, 0.25, 0.16, 0.15, 0.09, R)
    return mb.finish(name, C.lib_coll())

def bracket_pav_src(name='SRC_brk_pav'):
    """Pavilion column bracket: 单杪 with 令栱. Height 0.62."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    R = 'M_RedLacquer'
    dou(mb, 0, 0, 0.0, 0.36, 0.36, 0.22, R, taper=0.74, ear=0.6)
    arm_x(mb, 0, 0, 0.12, 1.1, H=0.16, W=0.11)
    arm_y(mb, 0, -0.35, 0.5, 0.12, H=0.16, W=0.11)
    for x in (-0.47, 0.47, 0.0):
        dou(mb, x, 0, 0.28, 0.19, 0.17, 0.11, R)
    dou(mb, 0, 0.43, 0.28, 0.19, 0.19, 0.11, R)
    arm_x(mb, 0, 0.43, 0.33, 1.1, H=0.16, W=0.11)
    arm_x(mb, 0, 0, 0.33, 1.6, H=0.16, W=0.11)
    for x in (-0.47, 0.47, 0.0):
        dou(mb, x, 0.43, 0.49, 0.19, 0.17, 0.11, R)
    mb.box((-0.7, 0.43 - 0.06, 0.55), (0.7, 0.43 + 0.06, 0.65), R)
    return mb.finish(name, C.lib_coll())

# ------------------------------------------------------------------ rafters
def rafter_pair_src(name, prof_fn, d_in, fly_back=1.15, fly_len=0.62, r_round=0.062, sq=(0.10, 0.115),
                    m='M_RedLacquer'):
    """One eave rafter pair (round 檐椽 + square 飞椽) built along +Y = outward (toward the eave),
    origin at the eave edge line (d=0) at height 0 = tile surface at the edge.
    prof_fn(d) -> tile-surface height relative to the edge. d grows inward (toward -Y)."""
    mb = C.MB()
    def pt(d, off):
        return Vector((0, -d, prof_fn(d) - off))
    # flying rafter (square)
    pts = [pt(0.02 + (fly_back - 0.02) * i / 6, 0.075 + sq[1] / 2) for i in range(7)]
    mb.sweep(pts, [(-sq[0] / 2, -sq[1] / 2), (sq[0] / 2, -sq[1] / 2), (sq[0] / 2, sq[1] / 2), (-sq[0] / 2, sq[1] / 2)], m,
             ups=[(0, 0, 1)] * 7)
    # round rafter
    pts = [pt(fly_len + (d_in - fly_len) * i / 8, 0.075 + sq[1] + 0.03 + r_round) for i in range(9)]
    sec = [(r_round * math.cos(2 * math.pi * j / 10), r_round * math.sin(2 * math.pi * j / 10)) for j in range(10)]
    mb.sweep(pts, sec, m, smooth=True, ups=[(0, 0, 1)] * 9)
    o = mb.finish(name, C.lib_coll())
    try:
        o.data.set_sharp_from_angle(angle=math.radians(40))
    except Exception:
        pass
    return o

# ------------------------------------------------------------------ railing parts
def baluster_src(name='SRC_baluster', h=0.36, m='M_RedLacquer'):
    if _get(name):
        return _get(name)
    mb = C.MB()
    mb.box((-0.022, -0.022, 0), (0.022, 0.022, h), m)
    return mb.finish(name, C.lib_coll())

def post_src(name='SRC_rail_post', h=0.95, m='M_RedLacquer'):
    """望柱 with a rounded finial."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    mb.box((-0.055, -0.055, 0), (0.055, 0.055, h - 0.16), m)
    mb.lathe([(0.065, h - 0.16), (0.07, h - 0.13), (0.05, h - 0.11), (0.06, h - 0.07), (0.055, h - 0.03), (0.03, h - 0.005), (0.0, h)],
             12, m, cap_bot=True)
    return mb.finish(name, C.lib_coll())

# ------------------------------------------------------------------ lantern
def lantern_src(name='SRC_lantern'):
    """Stone/metal garden lantern as in the B3 photos: red post on a stone base, black lantern with a hat."""
    if _get(name):
        return _get(name)
    mb = C.MB()
    S = 'M_StoneGrey'; R = 'M_RedPaint'; K = 'M_BlackLacquer'; L = 'M_Lamp'
    mb.box((-0.28, -0.28, 0), (0.28, 0.28, 0.12), S)
    mb.box((-0.2, -0.2, 0.12), (0.2, 0.2, 0.2), S)
    mb.cyl((0, 0, 0.2), (0, 0, 0.95), 0.085, 12, R, r1=0.07)
    mb.lathe([(0.1, 0.0), (0.16, 0.04), (0.17, 0.08), (0.0, 0.09)], 8, K, center=(0, 0, 0.95), smooth=False)
    # light box
    mb.box((-0.13, -0.13, 1.04), (0.13, 0.13, 1.28), L)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((sx * 0.13 - 0.02, sy * 0.13 - 0.02, 1.04), (sx * 0.13 + 0.02, sy * 0.13 + 0.02, 1.28), K)
    mb.box((-0.15, -0.15, 1.0), (0.15, 0.15, 1.05), K)
    # hat: wide flared pyramid
    mb.lathe([(0.0, 1.28), (0.30, 1.28), (0.32, 1.31), (0.2, 1.38), (0.08, 1.45), (0.035, 1.47), (0.04, 1.52), (0.0, 1.55)],
             4, K, center=(0, 0, 0), smooth=False)
    o = mb.finish(name, C.lib_coll())
    o.rotation_euler = (0, 0, 0)
    return o
