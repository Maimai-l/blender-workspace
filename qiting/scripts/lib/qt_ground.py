# Qiting - the platform at the foot of the podium (the plaza): grey setts ~200 x 100 mm laid in running bond on
# courses that follow circles round the podium, with wavy bands of lighter setts (419); a granite curb on the
# outline traced from the DWG; a joint bed; and a neutral staging ground beyond (temporary, not part of the replica).
import bpy, math, random, zlib
from mathutils import Vector
import xy_core as C
import qt_dims as D

SETT_L, SETT_W, SETT_H, JOINT = 0.20, 0.10, 0.07, 0.006


def sett_src(name='SRC_qt_sett'):
    o = bpy.data.objects.get(name)
    if o:
        return o
    mb = C.MB()
    # chamfered block: local X along the course (tangent), Y radial, top at z = 0
    l, w, h, b = SETT_L / 2, SETT_W / 2, SETT_H, 0.008
    B = [(-l, -w, -h), (l, -w, -h), (l, w, -h), (-l, w, -h)]
    M = [(-l, -w, -b), (l, -w, -b), (l, w, -b), (-l, w, -b)]
    T = [(-l + b, -w + b, 0.0), (l - b, -w + b, 0.0), (l - b, w - b, 0.0), (-l + b, w - b, 0.0)]
    mb.face(list(reversed(B)), 'M_Setts')
    mb.face(T, 'M_Setts')
    for i in range(4):
        j = (i + 1) % 4
        mb.face([B[i], B[j], M[j], M[i]], 'M_Setts')
        mb.face([M[i], M[j], T[j], T[i]], 'M_Setts')
    o = mb.finish(name, C.lib_coll(), recalc=True)
    return o


def sett_proxy(name, mat):
    """viewport stand-in: the sett's top face only (renders use the full bevelled block)."""
    o = bpy.data.objects.get(name)
    if o:
        return o
    mb = C.MB()
    l, w = SETT_L / 2 - 0.004, SETT_W / 2 - 0.004
    mb.face([(-l, -w, 0.0), (l, -w, 0.0), (l, w, 0.0), (-l, w, 0.0)], mat)
    return mb.finish(name, C.lib_coll(), recalc=False)


def _light_band(r, a):
    """band of pale setts along the lobed line of the DWG plaza outline (the pale arcs in the dusk photo)."""
    return abs(r - D.plaza_r(math.degrees(a))) < 0.24


def _under_stair(x, y):
    hw = D.STAIR_W_CLEAR / 2 + D.STAIR_PARAPET
    return y > 0 and abs(x) < hw + 0.02 and y < 25.0


def plaza(c):
    src = sett_src()
    try:
        import qt_podium as P
        _, _, r_foot = P.stair_profile()
    except Exception:
        r_foot = 20.0
    rng = random.Random(zlib.crc32(b'plaza'))
    r0 = D.TIER_R[2] + 0.02
    z = D.Z_PLAZA
    dark, light = [], []
    pitch_r = SETT_W + JOINT
    r = r0 + SETT_W / 2
    k = 0
    r_max = D.PLAZA_R_OUT
    while r < r_max:
        n = int(2 * math.pi * r / (SETT_L + JOINT))
        off = (k % 2) * 0.5
        for i in range(n):
            a = 2 * math.pi * (i + off) / n
            if r > D.PLAZA_R_OUT - 0.17 - SETT_W / 2:
                continue
            x, y = r * math.cos(a), r * math.sin(a)
            if _under_stair(x, y) and y < r_foot:
                continue
            jz = rng.uniform(-0.0025, 0.0015)
            rz = a + math.pi / 2 + rng.uniform(-0.01, 0.01)
            item = ((x, y, z + jz), (rng.uniform(-0.004, 0.004), rng.uniform(-0.004, 0.004), rz), 1.0)
            (light if _light_band(r, a) else dark).append(item)
        r += pitch_r
        k += 1
    o1 = C.instancer('QT_plaza_setts', src, dark, c, proxy=sett_proxy('SRC_qt_sett_px', 'M_Setts'))
    # light setts share the source but get the light material through a material override copy
    src_l = bpy.data.objects.get('SRC_qt_sett_light')
    if src_l is None:
        me = src.data.copy(); me.name = 'SRC_qt_sett_light'
        me.materials.clear(); me.materials.append(C.mat('M_SettsLight'))
        src_l = bpy.data.objects.new('SRC_qt_sett_light', me)
        C.link(src_l, C.lib_coll())
    o2 = C.instancer('QT_plaza_setts_light', src_l, light, c, proxy=sett_proxy('SRC_qt_sett_light_px', 'M_SettsLight'))
    # joint bed under the setts and the curb on the outline
    mb = C.MB()
    N = 360
    ring_in = [(r0 * math.cos(2 * math.pi * i / N), r0 * math.sin(2 * math.pi * i / N), z - 0.02) for i in range(N)]
    ring_out = []
    for i in range(N):
        a = 2 * math.pi * i / N
        rr = D.PLAZA_R_OUT
        ring_out.append((rr * math.cos(a), rr * math.sin(a), z - 0.02))
    mb.quad_strip([ring_in, ring_out], 'M_Dark', closed_u=True)
    bed = mb.finish('QT_plaza_bed', c, recalc=False)
    if bed.data.polygons[0].normal.z < 0:
        bed.data.flip_normals()
    mb = C.MB()
    prof_w, prof_h = 0.15, 0.12
    rows = []
    for i in range(N):
        a = 2 * math.pi * i / N
        rr = D.PLAZA_R_OUT + 0.02
        cx, cy = math.cos(a), math.sin(a)
        row = []
        for (dr, dz) in ((-0.20, -0.10), (-0.20, 0.015), (-0.20 + prof_w - 0.01, 0.02), (-0.20 + prof_w, 0.01), (-0.20 + prof_w, -0.10)):
            row.append(((rr + dr) * cx, (rr + dr) * cy, z + dz))
        rows.append(row)
    mb.quad_strip(rows + [rows[0]], 'M_GraniteLight', closed_u=False)
    curb = mb.finish('QT_plaza_curb', c, recalc=True)
    return [o1, o2, bed, curb], len(dark) + len(light)


def stage_ground(c):
    """neutral flat ground beyond the plaza so renders do not float in a void. NOT part of the replica: the hill,
    lawns and paths come in the next round."""
    mb = C.MB()
    N = 180
    rows = []
    for rr, dz in ((0.0, -0.2), (40.0, -0.2), (400.0, -4.0), (3000.0, -30.0), (30000.0, -300.0)):
        rows.append([(rr * math.cos(2 * math.pi * i / N), rr * math.sin(2 * math.pi * i / N), D.Z_PLAZA + dz) for i in range(N)])
    mb.quad_strip(rows, 'M_Ground', closed_u=True)
    o = mb.finish('QT_stage_ground', c, recalc=False)
    if o.data.polygons[len(o.data.polygons) // 2].normal.z < 0:
        o.data.flip_normals()
    return o
