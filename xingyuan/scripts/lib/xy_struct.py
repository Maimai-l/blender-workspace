# Xingyuan - corridors (廊道), pavilions (B1 / B3 north / B3 south), gate (院门), A3-1, B2 walls.
import bpy, math
from mathutils import Vector, Matrix
import xy_core as C, xy_roof as RF, xy_parts as PT, xy_frame as FR

RED = 'M_RedLacquer'
HCC = 2.15          # corridor column height
C_EAVE, C_RIDGE, C_OVER = 2.56, 3.77, 0.80

def _between(v, ranges):
    return any(a - 1e-6 <= v <= b + 1e-6 for a, b in ranges)

# ------------------------------------------------------------------ corridor
def corridor(name, coll, axis, rows, stations, roof_span, rails=((), ()), walls=((), ()), skip=((), ()),
             gables=(False, False), wall_kind='window'):
    """axis 'x': rows = (y_a, y_b) column lines, stations = x positions; axis 'y': rows = (x_a, x_b).
    roof_span = (s0, s1) roof extent along the axis. rails/walls/skip: per row, list of (s0, s1) ranges.
    Row index 0 = rows[0] (its exterior normal points away from rows[1])."""
    fr = FR.Frame(name, coll)
    ra, rb = rows
    w = abs(rb - ra)
    mid = (ra + rb) / 2
    def P(s, r):
        return (s, r) if axis == 'x' else (r, s)
    pts = []
    for ri, r in enumerate(rows):
        for s in stations:
            if _between(s, skip[ri]):
                continue
            pts.append(P(s, r))
    FR.columns(fr, pts, HCC, 'SRC_col_corr', r0=0.15, r1=0.135)
    bsrc = PT.bracket_small_src()
    for (x, y) in pts:
        ang = 0.0 if axis == 'x' else math.pi / 2
        fr.add(bsrc, ((x, y, HCC), (0.0, 0.0, ang), 1.0))
    # beams along the rows + tie beams across
    s0, s1 = min(stations), max(stations)
    for ri, r in enumerate(rows):
        fr.beam(P(s0, r), P(s1, r), HCC - 0.22, HCC - 0.02, 0.13)
        fr.beam(P(roof_span[0] + 0.1, r), P(roof_span[1] - 0.1, r), HCC + 0.30, HCC + 0.44, 0.11)   # 槫/方 on the brackets
    for s in stations:
        if _between(s, skip[0]) and _between(s, skip[1]):
            continue
        a, b = P(s, ra), P(s, rb)
        fr.beam(a, b, HCC + 0.12, HCC + 0.34, 0.14)          # 乳栿 across
        # short king post + ridge purlin support
        cx, cy = P(s, mid)
        fr.box(cx - 0.05, cy - 0.05, HCC + 0.34, cx + 0.05, cy + 0.05, C_RIDGE - 0.32, RED)
    # ridge purlin
    fr.beam(P(roof_span[0] + 0.05, mid), P(roof_span[1] - 0.05, mid), C_RIDGE - 0.40, C_RIDGE - 0.28, 0.14)
    # railings and walls
    for ri, r in enumerate(rows):
        out_sign = 1 if (r - (rb if ri == 0 else ra)) > 0 else -1
        normal = (0, out_sign) if axis == 'x' else (out_sign, 0)
        for (a, b) in rails[ri]:
            ss = [s for s in stations if a - 1e-6 <= s <= b + 1e-6]
            for k in range(len(ss) - 1):
                p = P(ss[k] + 0.17, r); q = P(ss[k + 1] - 0.17, r)
                FR.railing(fr, p, q, z=0.0, h=0.78, post_h=0.95)
        for (a, b) in walls[ri]:
            ss = [s for s in stations if a - 1e-6 <= s <= b + 1e-6]
            for k in range(len(ss) - 1):
                FR.wall_bay(fr, P(ss[k], r), P(ss[k + 1], r), wall_kind, normal, z_top=HCC - 0.22, dado=0.7,
                            win=(0.85, 1.65), ww=min(1.3, ss[k + 1] - ss[k] - 0.8))
    fr.finish()
    # roof
    A = (roof_span[1] - roof_span[0]) / 2
    cs = (roof_span[0] + roof_span[1]) / 2
    cx, cy = P(cs, mid)
    FR.roof(name, coll, 'gable', cx, cy, A, w / 2 + C_OVER, C_EAVE, C_RIDGE, along=axis, horn=0.18, horn_len=0.4,
            gables=gables, rafters=True, d_in=1.45, xuanyu=False, ridge_scale=0.62, deck_sof=0.205)

# ------------------------------------------------------------------ pavilion frame
def pav_frame(name, coll, cols, perim, H, rails=(), walls=(), brk_dirs=None, lotus=True, beams_extra=()):
    """cols: list of (x, y); perim: ordered list of perimeter column positions (closed loop).
    rails: list of (p, q) pairs; walls: list of (p, q, kind, normal)."""
    fr = FR.Frame(name, coll)
    src = PT.column_src('SRC_col_pav_%d' % int(H * 100), H, r0=0.19, r1=0.17, segs=18)
    bsrc = PT.base_src() if lotus else PT.base_plain_src()
    for (x, y) in cols:
        fr.add(src, ((x, y, 0.0), (0, 0, 0), 1.0))
        fr.add(bsrc, ((x, y, 0.0), (0, 0, 0), 1.0))
    # perimeter beams (阑额 + 由额 with struts) and brackets facing outward
    cx = sum(p[0] for p in perim) / len(perim); cy = sum(p[1] for p in perim) / len(perim)
    bp = PT.bracket_pav_src()
    n = len(perim)
    for i in range(n):
        p, q = perim[i], perim[(i + 1) % n]
        fr.beam(p, q, H - 0.24, H - 0.02, 0.15)
        fr.beam(p, q, H - 0.62, H - 0.50, 0.12)
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        k = max(1, int(round(L / 0.7)))
        for j in range(1, k):
            t = j / k
            x = p[0] + (q[0] - p[0]) * t; y = p[1] + (q[1] - p[1]) * t
            fr.box(x - 0.035, y - 0.035, H - 0.50, x + 0.035, y + 0.035, H - 0.24, RED)
        # 柱头方 on the brackets
        fr.beam(p, q, H + 0.33, H + 0.49, 0.11)
    for (x, y) in perim:
        # corner columns: diagonal; others: perpendicular to the side they belong to
        xs = [q[0] for q in perim]; ys = [q[1] for q in perim]
        on_left = abs(x - min(xs)) < 1e-3; on_right = abs(x - max(xs)) < 1e-3
        on_bot = abs(y - min(ys)) < 1e-3; on_top = abs(y - max(ys)) < 1e-3
        if (on_left or on_right) and (on_bot or on_top):
            d = ((-1 if on_left else 1) * 0.7071, (-1 if on_bot else 1) * 0.7071)
        elif on_left or on_right:
            d = (-1 if on_left else 1, 0)
        else:
            d = (0, -1 if on_bot else 1)
        FR.bracket(fr, bp, x, y, H, d)
    for (p, q) in rails:
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        ux, uy = (q[0] - p[0]) / L, (q[1] - p[1]) / L
        FR.railing(fr, (p[0] + ux * 0.2, p[1] + uy * 0.2), (q[0] - ux * 0.2, q[1] - uy * 0.2), z=0.0, h=0.80, post_h=1.0)
    for (p, q, kind, normal) in walls:
        FR.wall_bay(fr, p, q, kind, normal, z_top=H - 0.62, dado=0.75, win=(0.9, 1.9), door_w=1.4, door_h=2.3)
    for (p, q, z0, z1, w) in beams_extra:
        fr.beam(p, q, z0, z1, w)
    fr.finish()

# ------------------------------------------------------------------ the buildings
def build_corridors():
    C.clear_coll('廊道')
    top = C.coll('廊道')
    def sub(n):
        return C.coll('廊道-' + n, top)
    # spine corridor (B1 north / B3 south)
    st = [10.2, 12.2, 14.6, 17.0, 24.3, 26.7, 29.1, 31.5, 33.6, 36.7, 38.8, 41.2, 43.6, 46.0, 48.43, 50.86, 53.26, 55.69, 58.1, 60.2]
    # rows: 0 = south row y=26.57, 1 = north row y=28.67
    corridor('廊道_中轴东西_西段', sub('中轴东西'), 'x', (26.57, 28.67), [10.2, 12.2, 14.6, 17.0], (9.4, 17.0),
             rails=((), ((12.2, 17.0),)), walls=(((10.2, 17.0),), ()), skip=(((17.0, 17.0),), ((17.0, 17.0),)),
             gables=(True, False))
    corridor('廊道_中轴东西_东段', sub('中轴东西'), 'x', (26.57, 28.67), st[4:], (24.3, 61.0),
             rails=(((26.7, 31.5), (38.8, 43.6)), ((24.3, 29.1), (43.6, 55.69))),
             walls=(((46.0, 60.2),), ()), skip=(((24.3, 24.3), (31.5, 38.8)), ((24.3, 24.3),)))
    # links to the hall porches
    corridor('廊道_A5南连廊', sub('B3西南'), 'y', (10.2, 12.2), [28.67, 30.77], (27.62, 31.25),
             rails=((), ((28.67, 30.77),)), walls=(((28.67, 30.77),), ()), skip=((), ()))
    corridor('廊道_A4南连廊', sub('B3东南'), 'y', (31.1, 29.1), [28.67, 30.77], (27.62, 31.25),
             rails=((), ((28.67, 30.77),)), walls=((), ()), skip=((), ()))
    corridor('廊道_A3南连廊', sub('B2南'), 'y', (60.1, 58.1), [28.67, 30.77], (27.62, 31.25),
             rails=((), ((28.67, 30.77),)), walls=(((28.67, 30.77),), ()), skip=((), ()))
    corridor('廊道_A2北连廊', sub('B1西北'), 'y', (24.6, 26.7), [24.47, 26.57], (24.0, 27.62),
             rails=((), ()), walls=(((24.47, 26.57),), ()), skip=(((26.57, 26.57),), ((26.57, 26.57),)))
    corridor('廊道_A1北连廊', sub('B1东北'), 'y', (45.7, 43.6), [24.47, 26.57], (24.0, 27.62),
             rails=((), ()), walls=(((24.47, 26.57),), ()), skip=(((26.57, 26.57),), ((26.57, 26.57),)))
    # B3 north corridors and links
    corridor('廊道_B3北_西段', sub('B3北'), 'x', (51.43, 53.5), [10.2, 12.2, 14.6, 16.98], (9.4, 16.98),
             rails=(((12.2, 16.98),), ()), walls=((), ((10.2, 16.98),)), skip=(((16.98, 16.98),), ((16.98, 16.98),)),
             gables=(True, False))
    corridor('廊道_B3北_东段', sub('B3北'), 'x', (51.43, 53.5), [24.27, 26.69, 29.1, 31.1], (24.27, 31.9),
             rails=(((24.27, 29.1),), ()), walls=((), ((24.27, 31.1),)), skip=(((24.27, 24.27),), ((24.27, 24.27),)),
             gables=(False, True))
    corridor('廊道_A5北连廊', sub('B3西北'), 'y', (10.2, 12.2), [49.3, 51.43], (48.9, 52.47),
             rails=((), ((49.3, 51.43),)), walls=(((49.3, 51.43),), ()), skip=(((51.43, 51.43),), ((51.43, 51.43),)))
    corridor('廊道_A4北连廊', sub('B3东北'), 'y', (31.1, 29.1), [49.3, 51.43], (48.9, 52.47),
             rails=((), ((49.3, 51.43),)), walls=(((49.3, 51.43),), ()), skip=(((51.43, 51.43),), ((51.43, 51.43),)))
    return top

def build_pavilions():
    # ---- B1 pavilion (悬山, ridge E-W)
    C.clear_coll('B1 亭')
    c = C.coll('B1 亭', C.coll('B1'))
    xs = [31.5, 33.6, 36.7, 38.8]
    perim = [(31.5, 21.38), (33.6, 21.38), (36.7, 21.38), (38.8, 21.38), (38.8, 23.48), (38.8, 26.58),
             (36.7, 26.58), (33.6, 26.58), (31.5, 26.58), (31.5, 23.48)]
    rails = [((31.5, 21.38), (33.6, 21.38)), ((36.7, 21.38), (38.8, 21.38)),
             ((38.8, 21.38), (38.8, 23.48)), ((38.8, 23.48), (38.8, 26.58)),
             ((31.5, 21.38), (31.5, 23.48)), ((31.5, 23.48), (31.5, 26.58))]
    pav_frame('B1亭', c, perim, perim, 3.10, rails=rails)
    FR.roof('B1亭', c, 'gable', 35.15, 23.98, 4.85, 3.90, 3.55, 6.24, along='x', horn=0.30, horn_len=0.7,
            gables=(True, True), d_in=1.6, ridge_scale=0.8)
    # ---- B3 south pavilion (歇山, ridge E-W)
    C.clear_coll('B3 南亭')
    c = C.coll('B3 南亭', C.coll('B3'))
    perim = [(17.0, 26.57), (18.8, 26.57), (22.5, 26.57), (24.3, 26.57), (24.3, 28.67), (24.3, 30.47),
             (22.5, 30.47), (18.8, 30.47), (17.0, 30.47), (17.0, 28.67)]
    rails = [((17.0, 30.47), (18.8, 30.47)), ((22.5, 30.47), (24.3, 30.47)),
             ((24.3, 28.67), (24.3, 30.47)), ((17.0, 28.67), (17.0, 30.47))]
    walls = []
    pav_frame('B3南亭', c, perim, perim, 3.10, rails=rails, walls=walls)
    # back (south) wall of dark brick with a central doorway, as in the photo
    mb = C.MB()
    yb, t = 26.57, 0.42
    for (x0, x1) in ((17.0 + 0.2, 19.9), (21.4, 24.3 - 0.2)):
        mb.box((x0, yb - t / 2, 0.0), (x1, yb + t / 2, 2.48), 'M_BrickDark')
    mb.box((19.9, yb - t / 2, 2.30), (21.4, yb + t / 2, 2.48), 'M_BrickDark')
    for (x0, x1, z0, z1) in ((19.78, 19.9, 0.0, 2.30), (21.4, 21.52, 0.0, 2.30), (19.78, 21.52, 2.30, 2.42)):
        mb.box((x0, yb - t / 2 - 0.03, z0), (x1, yb + t / 2 + 0.03, z1), 'M_Granite')
    mb.box((17.0, yb - 0.08, 2.48), (24.3, yb + 0.08, 2.86), 'M_Plaster')
    mb.finish('B3南亭_后墙', c)
    FR.stepped_roof('B3南亭', c, 20.65, 28.52, 4.55, 3.05, 3.90, 5.85, 7.20, d_cap=1.85, along='x', lift=0.46, lift_len=2.2,
                    upper_end_inset=0.38, upper_over=0.30, step_gap=0.14, horn=0.36, horn_len=0.55, d_in=1.35)
    # ---- B3 north pavilion (攒尖, square)
    C.clear_coll('B3 北亭')
    c = C.coll('B3 北亭', C.coll('B3'))
    perim = [(16.98, 49.6), (18.78, 49.6), (22.47, 49.6), (24.27, 49.6), (24.27, 51.43), (24.27, 53.5), (24.27, 56.86),
             (22.47, 56.86), (18.78, 56.86), (16.98, 56.86), (16.98, 53.5), (16.98, 51.43)]
    rails = [((16.98, 49.6), (18.78, 49.6)), ((22.47, 49.6), (24.27, 49.6)),
             ((24.27, 49.6), (24.27, 51.43)), ((16.98, 49.6), (16.98, 51.43))]
    walls = [((16.98, 56.86), (18.78, 56.86), 'plain', (0, 1)), ((18.78, 56.86), (22.47, 56.86), 'window', (0, 1)),
             ((22.47, 56.86), (24.27, 56.86), 'plain', (0, 1)),
             ((24.27, 53.5), (24.27, 56.86), 'window', (1, 0)), ((16.98, 53.5), (16.98, 56.86), 'window', (-1, 0))]
    pav_frame('B3北亭', c, perim, perim, 3.20, rails=rails, walls=walls)
    FR.roof('B3北亭', c, 'pyramid', 20.62, 53.23, 4.95, 4.95, 4.15, 7.0, along='x', lift=0.26, lift_len=2.0,
            d_in=1.5, finial=0.62, ridge_scale=0.8)

def build_gate():
    C.clear_coll('B1 院门')
    c = C.coll('B1 院门', C.coll('B1'))
    # ---- gate house (门屋): walls with a central passage, corner columns, 悬山 roof ridge E-W
    fr = FR.Frame('院门_门屋', c)
    x0, x1, y0, y1 = 31.57, 38.73, -6.18, -1.41
    H = 3.25
    cols = [(31.83, -1.66), (38.47, -1.66), (31.83, -5.93), (38.47, -5.93), (33.7, -1.66), (36.6, -1.66), (33.7, -5.93), (36.6, -5.93)]
    bi = PT.bracket_inner_src()
    for (x, y) in cols:
        FR.bracket(fr, bi, x, y, H, (0, 1 if y > -3 else -1))
    for yy in (-1.66, -5.93):
        fr.beam((31.4, yy), (38.9, yy), H + 0.38, H + 0.56, 0.12)
    # thick white walls (columns embedded), granite plinth course, central passage with granite frames
    t = 0.66
    zt = H - 0.24
    def wall(x0, y0, x1, y1):
        fr.box(x0, y0, 0.0, x1, y1, 0.45, 'M_Granite')
        fr.box(x0 + 0.02, y0 + 0.02, 0.45, x1 - 0.02, y1 - 0.02, zt, 'M_Plaster')
    xa, xb = 31.83 - t / 2, 38.47 + t / 2
    dx0, dx1, dh = 34.0, 36.3, 2.95                      # passage opening
    for (yy) in (-1.66, -5.93):
        wall(xa, yy - t / 2, dx0, yy + t / 2)
        wall(dx1, yy - t / 2, xb, yy + t / 2)
        fr.box(dx0, yy - t / 2 + 0.02, dh, dx1, yy + t / 2 - 0.02, zt, 'M_Plaster')
        # granite door surround
        for (a0, a1, z0, z1) in ((dx0 - 0.2, dx0, 0.0, dh + 0.2), (dx1, dx1 + 0.2, 0.0, dh + 0.2), (dx0 - 0.2, dx1 + 0.2, dh, dh + 0.22)):
            fr.box(a0, yy - t / 2 - 0.04, z0, a1, yy + t / 2 + 0.04, z1, 'M_Granite')
    for xx in (31.83, 38.47):
        wall(xx - t / 2, -5.93 + t / 2, xx + t / 2, -1.66 - t / 2)
    # passage side walls between the two faces
    for xx in (dx0, dx1):
        fr.box(xx - 0.1, -5.93 + t / 2, 0.0, xx + 0.1, -1.66 - t / 2, zt, 'M_Plaster')
    # closed double doors (dark timber with studs) set in the north opening
    yd = -1.66 + 0.05
    fr.box(dx0, yd - 0.05, 0.0, dx1, yd + 0.05, 0.12, 'M_Granite')
    for (a0, a1) in ((dx0, (dx0 + dx1) / 2 - 0.004), ((dx0 + dx1) / 2 + 0.004, dx1)):
        fr.box(a0, yd - 0.04, 0.12, a1, yd + 0.04, dh, 'M_DoorDark')
        for zz in (0.55, 1.25, 1.95, 2.6):
            for k in range(5):
                x = a0 + (a1 - a0) * (k + 0.5) / 5
                fr.box(x - 0.025, yd - 0.07, zz - 0.025, x + 0.025, yd - 0.04, zz + 0.025, 'M_Bronze')
    # red timber band under the eave (阑额 on the wall top) all around
    for yy in (-1.66, -5.93):
        fr.box(xa - 0.02, yy - t / 2 - 0.02, zt, xb + 0.02, yy + t / 2 + 0.02, H - 0.02, RED)
    for xx in (31.83, 38.47):
        fr.box(xx - t / 2 - 0.02, -5.93, zt, xx + t / 2 + 0.02, -1.66, H - 0.02, RED)
    fr.box(31.9, -5.85, H + 0.56, 38.4, -1.74, H + 0.62, 'M_Ceiling')
    fr.finish()
    FR.roof('院门_门屋', c, 'gable', 35.15, -3.795, 4.60, 3.64, 3.70, 5.78, along='x', horn=0.30, horn_len=0.6, d_in=1.5,
            ridge_scale=0.75)
    # ---- wings (hip roofs)
    for side in (-1, 1):
        nm = '院门_%s厢' % ('西' if side < 0 else '东')
        fr = FR.Frame(nm, c)
        X = lambda x: x if side < 0 else 2 * 35.15 - x
        H2 = 2.25
        cols = [(X(24.6), -4.88), (X(26.67), -4.88), (X(29.08), -4.88), (X(24.6), -2.77), (X(26.67), -2.77), (X(29.08), -2.77),
                (X(24.6), -0.67), (X(26.67), -0.67)]
        FR.columns(fr, cols, H2, 'SRC_col_corr2', r0=0.16, r1=0.145)
        bs = PT.bracket_small_src()
        for (x, y) in cols:
            fr.add(bs, ((x, y, H2), (0.0, 0.0, 0.0), 1.0))
        fr.beam((X(24.6), -4.88), (X(31.6), -4.88), H2 - 0.22, H2 - 0.02, 0.13)
        fr.beam((X(24.6), -2.77), (X(31.6), -2.77), H2 - 0.22, H2 - 0.02, 0.13)
        fr.beam((X(24.6), -4.88), (X(24.6), -0.67), H2 - 0.22, H2 - 0.02, 0.13)
        fr.beam((X(26.67), -4.88), (X(26.67), -0.67), H2 - 0.22, H2 - 0.02, 0.13)
        out_s = (0, -1)
        out_w = (-1 if side < 0 else 1, 0)
        for (a, b) in ((24.6, 26.67), (26.67, 29.08), (29.08, 31.57)):
            FR.wall_bay(fr, (X(a), -4.88), (X(b), -4.88), 'window', out_s, z_top=H2 - 0.22, dado=0.7, win=(0.85, 1.7), ww=1.2)
        for (a, b) in ((-4.88, -2.77), (-2.77, -0.67)):
            FR.wall_bay(fr, (X(24.6), a), (X(24.6), b), 'window', out_w, z_top=H2 - 0.22, dado=0.7, win=(0.85, 1.7), ww=1.2)
        for (a, b) in ((26.67, 29.08), (29.08, 31.57)):
            FR.railing(fr, (X(a) + 0.18 * (1 if side < 0 else -1), -2.77), (X(b) - 0.18 * (1 if side < 0 else -1), -2.77), h=0.78)
        fr.finish()
        cxw = X(27.2)
        FR.roof(nm, c, 'pyramid', cxw, -3.79, 3.83, 2.31, 2.62, 3.85, along='x', lift=0.18, lift_len=1.4, d_in=1.3, horn=0.2,
                ridge_scale=0.62)

def build_A31():
    C.clear_coll('A3-1')
    c = C.coll('A3-1')
    fr = FR.Frame('A3-1', c)
    x0, x1, y0, y1 = 60.0, 65.9, 22.9, 31.4
    H = 2.9
    xs = [x0, (x0 + x1) / 2, x1]
    ys = [y0, y0 + (y1 - y0) / 3, y0 + 2 * (y1 - y0) / 3, y1]
    cols = [(x, y) for x in (x0, x1) for y in ys] + [((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)]
    FR.columns(fr, cols, H, 'SRC_col_a31', r0=0.17, r1=0.155)
    bi = PT.bracket_inner_src()
    for (x, y) in cols:
        FR.bracket(fr, bi, x, y, H, (1, 0) if x in (x0, x1) else (0, 1))
    for yy in (y0, y1):
        fr.beam((x0, yy), (x1, yy), H - 0.22, H - 0.02, 0.15)
    for xx in (x0, x1):
        fr.beam((xx, y0), (xx, y1), H - 0.22, H - 0.02, 0.15)
    for k in range(3):
        FR.wall_bay(fr, (x1, ys[k]), (x1, ys[k + 1]), 'window', (1, 0), z_top=H - 0.22, ww=1.3)
        FR.wall_bay(fr, (x0, ys[k]), (x0, ys[k + 1]), 'door' if k == 0 else 'window', (-1, 0), z_top=H - 0.22, ww=1.3,
                    door_w=1.2, door_h=2.2)
    for yy, nrm in ((y0, (0, -1)), (y1, (0, 1))):
        FR.wall_bay(fr, (x0, yy), (xs[1], yy), 'window', nrm, z_top=H - 0.22, ww=1.2)
        FR.wall_bay(fr, (xs[1], yy), (x1, yy), 'window', nrm, z_top=H - 0.22, ww=1.2)
    fr.finish()
    FR.roof('A3-1', c, 'gable', (x0 + x1) / 2, (y0 + y1) / 2, 5.15, 3.80, 3.25, 5.48, along='y', horn=0.28, horn_len=0.6,
            d_in=1.6, ridge_scale=0.72)

def build_B2_walls():
    C.clear_coll('B2 院墙')
    c = C.coll('B2 院墙', C.coll('B2'))
    mb = C.MB()
    z0 = -0.6
    segs = [((41.28, 56.0), (45.9, 56.0), 1.6), ((45.9, 56.0), (52.6, 56.0), 2.4), ((52.6, 56.0), (60.2, 56.0), 1.6),
            ((60.2, 49.75), (60.2, 56.0), 1.6), ((41.28, 49.75), (41.28, 56.0), 1.6)]
    for (p, q, ztop) in segs:
        (xa, ya), (xb, yb) = p, q
        t = 0.48
        if abs(ya - yb) < 1e-6:
            mb.box((xa - 0.24, ya - t / 2, z0 - 0.05), (xb + 0.24, ya + t / 2, z0 + 0.5), 'M_Granite')
            mb.box((xa - 0.2, ya - t / 2 + 0.03, z0 + 0.5), (xb + 0.2, ya + t / 2 - 0.03, ztop), 'M_Plaster')
        else:
            mb.box((xa - t / 2, ya - 0.24, z0 - 0.05), (xa + t / 2, yb + 0.24, z0 + 0.5), 'M_Granite')
            mb.box((xa - t / 2 + 0.03, ya - 0.2, z0 + 0.5), (xa + t / 2 - 0.03, yb + 0.2, ztop), 'M_Plaster')
    mb.finish('B2_院墙_墙身', c)
    # tile copings (small gable roofs) on top of the walls
    for i, (p, q, ztop) in enumerate(segs):
        (xa, ya), (xb, yb) = p, q
        along = 'x' if abs(ya - yb) < 1e-6 else 'y'
        L = abs(xb - xa) if along == 'x' else abs(yb - ya)
        cx, cy = (xa + xb) / 2, (ya + yb) / 2
        FR.roof('B2院墙%d' % i, c, 'gable', cx, cy, L / 2 + 0.25, 0.55, ztop + 0.02, ztop + 0.38, along=along, horn=0.08,
                horn_len=0.25, rafters=False, barge=False, xuanyu=False, ridge_scale=0.4, deck_sof=0.10)
