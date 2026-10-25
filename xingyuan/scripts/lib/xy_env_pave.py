# Xingyuan - paving outside the complex (from the calibrated aerial): red-paver terrace west of A2 along the
# pond railing, ice-crack paving NW of A2, grey plaza south of the gate with the round sculpture plaza,
# SW pink plaza, pink path under the stone frames (grey diamond inlays, red-brown borders), stone-slab bridge,
# grey path to A5, concrete footpath in the east lawn. Every slab is a separate bevelled piece; kerbs are blocks.
import bpy, math, random
from mathutils import Vector
import xy_core as C, xy_site as S, xy_geo2d as G
import xy_env_data as ED

ZP = ED.ZP

def zones():
    """Paved env polygons (CCW, plan metres)."""
    red = G.ccw(ED.RED_TERRACE)
    crazy = G.ccw([(-4.48, 27.34), (-4.8, 24.0), (-3.8, 20.5), (-1.5, 17.6), (2.0, 15.9), (6.5, 15.0), (7.4, 13.6),
                   (10.08, 13.6), (10.08, 27.34)])
    (cx, cy), r = ED.SCULPT_PLAZA
    gray = G.ccw([(27.0, -33.0), (43.3, -33.0), (43.3, cy - r)] + G.arc((cx, cy), r, -math.pi / 2, math.pi / 2, 28) +
                 [(43.3, cy + r), (43.3, -9.1), (27.0, -9.1)])
    swp = G.ccw(ED.SW_PLAZA)
    return dict(red=red, crazy=crazy, gray=gray, swp=swp)

def bridge_ends():
    (a, b, w) = ED.SLAB_BRIDGE
    return Vector((a[0], a[1], 0)), Vector((b[0], b[1], 0)), w

def paths():
    A, B, w = bridge_ends()
    pink = G.Path(G.catmull(list(ED.PINK_PATH) + [(A.x, A.y)], 0.5))
    grayn = G.Path(G.catmull([(B.x, B.y)] + list(ED.GRAY_PATH_N), 0.5))
    east = G.Path(G.catmull(ED.EAST_PATH, 0.6))
    return dict(pink=(pink, ED.PINK_W), grayn=(grayn, ED.GRAY_N_W), east=(east, ED.EAST_W))

def landings():
    """Stone landings at both bridge ends: (centre, axis unit, half-length along, half-width across)."""
    A, B, w = bridge_ends()
    d = (B - A).normalized()
    return [(A - d * 0.75, d, 0.75, 1.6), (B + d * 0.75, d, 0.75, 1.6)]

def _rect(c, d, hl, hw):
    n = Vector((-d.y, d.x, 0))
    P = [c - d * hl - n * hw, c + d * hl - n * hw, c + d * hl + n * hw, c - d * hl + n * hw]
    return G.ccw([(p.x, p.y) for p in P])

def mask_polys():
    """All paved outlines (for the global ground mask): zones, path strips, landings, bridge."""
    Z = zones()
    out = [Z[k] for k in Z]
    for key, (p, W) in paths().items():
        out.append(p.outline(W / 2))
    for (c, d, hl, hw) in landings():
        out.append(_rect(c, d, hl, hw))
    A, B, w = bridge_ends()
    d = (B - A).normalized()
    out.append(_rect((A + B) / 2, d, (B - A).length / 2, w / 2))
    return out

# ------------------------------------------------------------------ building blocks
def prism(mb, P, z_top, z_bot, m, z_bot_fn=None, top=True):
    """Vertical prism over CCW footprint P: top face + side faces down to z_bot (or z_bot_fn(edge midpoint))."""
    n = len(P)
    T = [Vector((x, y, z_top)) for x, y in P]
    if top:
        mb.face(T, m)
    for i in range(n):
        j = (i + 1) % n
        zb = z_bot if z_bot_fn is None else z_bot_fn(((P[i][0] + P[j][0]) / 2, (P[i][1] + P[j][1]) / 2), i)
        if zb is None:
            continue
        mb.face([Vector((P[i][0], P[i][1], zb)), Vector((P[j][0], P[j][1], zb)), T[j], T[i]], m)

def pave_poly(pv, region, z, m, sw, sl, angle=0.0, origin=(0.0, 0.0), stagger=0.5, min_area=0.003, clippers=(),
              skip=None, gap=0.005):
    """Running-bond slabs (sw across, sl along the local y axis rotated by `angle`) clipped to `region` (CCW)."""
    ca, sa = math.cos(angle), math.sin(angle)
    ox, oy = origin
    loc = [((x - ox) * ca + (y - oy) * sa, -(x - ox) * sa + (y - oy) * ca) for x, y in region]
    u0 = min(p[0] for p in loc); u1 = max(p[0] for p in loc)
    v0 = min(p[1] for p in loc); v1 = max(p[1] for p in loc)
    def W(u, v):
        return (ox + u * ca - v * sa, oy + u * sa + v * ca)
    n = 0
    for k in range(int(math.floor(u0 / sw)), int(math.ceil(u1 / sw))):
        off = (k % 2) * stagger * sl
        for l in range(int(math.floor((v0 - off) / sl)), int(math.ceil((v1 - off) / sl))):
            ua, ub = k * sw, (k + 1) * sw
            va, vb = off + l * sl, off + (l + 1) * sl
            rect = [W(ua, va), W(ub, va), W(ub, vb), W(ua, vb)]
            P = G.clip(region, rect)
            for cl in clippers:
                if len(P) >= 3:
                    P = G.clip(P, cl)
            if len(P) < 3 or G.area(P) < min_area:
                continue
            if skip is not None and skip(G.centroid(P)):
                continue
            pv.poly(G.ccw(P), z, m, gap=gap)
            n += 1
    return n

def kerb_ring(mb, P, widths, z, m, seg=1.0, out_paved=None, z_low_fn=None, raise_h=0.02, flush_h=0.006, flush_ext=0.04,
              joint=0.003, edges=None):
    """Kerb blocks along the edges of CCW polygon P, inside it. widths: per-edge kerb width.
    A block is FLUSH (top +flush_h, extended outward by flush_ext) where the outside is paved, otherwise RAISED
    (top +raise_h, outer face down to z_low_fn(point outside)). Returns the inner (paving) polygon."""
    n = len(P)
    Pi = G.offset_var(P, widths)
    for i in range(n):
        if edges is not None and i not in edges:
            continue
        a, b = P[i], P[(i + 1) % n]
        ai, bi = Pi[i], Pi[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.02:
            continue
        nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L          # outward (right of a CCW edge)
        k = max(1, int(round(L / seg)))
        for q in range(k):
            t0 = q / k + (joint / 2 / L if q > 0 else 0.0)
            t1 = (q + 1) / k - (joint / 2 / L if q < k - 1 else 0.0)
            lp = lambda p0, p1, t: (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t)
            o0, o1 = lp(a, b, t0), lp(a, b, t1)
            i0, i1 = lp(ai, bi, t0), lp(ai, bi, t1)
            mid = ((o0[0] + o1[0]) / 2, (o0[1] + o1[1]) / 2)
            test = (mid[0] + nx * 0.18, mid[1] + ny * 0.18)
            flush = out_paved(test) if out_paved else False
            if flush:
                e = flush_ext
                o0 = (o0[0] + nx * e, o0[1] + ny * e); o1 = (o1[0] + nx * e, o1[1] + ny * e)
                zt = z + flush_h
                zl = z - 0.07
            else:
                zt = z + raise_h
                zl = z_low_fn(test) if z_low_fn else z - 0.15
            V3 = lambda p, zz: Vector((p[0], p[1], zz))
            zi = z - 0.06
            mb.face([V3(o0, zt), V3(o1, zt), V3(i1, zt), V3(i0, zt)], m)          # top
            mb.face([V3(o0, zl), V3(o1, zl), V3(o1, zt), V3(o0, zt)], m)          # outer face (down to the ground)
            mb.face([V3(i1, zi), V3(i0, zi), V3(i0, zt), V3(i1, zt)], m)          # inner face (above the slab bed)
            mb.face([V3(o1, zl), V3(i1, zi), V3(i1, zt), V3(o1, zt)], m)          # ends
            mb.face([V3(i0, zi), V3(o0, zl), V3(o0, zt), V3(i0, zt)], m)
    return Pi

def crazy_cells(region, spacing=0.62, seed=5, jitter=0.45):
    """Voronoi cells (ice-crack / 冰裂纹 pattern) of a jittered grid, clipped to the region."""
    r = random.Random(seed)
    xs = [p[0] for p in region]; ys = [p[1] for p in region]
    x0, x1, y0, y1 = min(xs) - spacing, max(xs) + spacing, min(ys) - spacing, max(ys) + spacing
    nx = int((x1 - x0) / spacing) + 1; ny = int((y1 - y0) / spacing) + 1
    seeds = {}
    for j in range(ny):
        for i in range(nx):
            # slightly anisotropic, irregular seeds -> angular, varied cells
            seeds[(i, j)] = (x0 + (i + 0.5 + r.uniform(-jitter, jitter)) * spacing,
                             y0 + (j + 0.5 + r.uniform(-jitter, jitter)) * spacing)
    cells = []
    for (i, j), p in seeds.items():
        cell = [(p[0] - 2 * spacing, p[1] - 2 * spacing), (p[0] + 2 * spacing, p[1] - 2 * spacing),
                (p[0] + 2 * spacing, p[1] + 2 * spacing), (p[0] - 2 * spacing, p[1] + 2 * spacing)]
        for dj in (-2, -1, 0, 1, 2):
            for di in (-2, -1, 0, 1, 2):
                if di == 0 and dj == 0:
                    continue
                q = seeds.get((i + di, j + dj))
                if q is None:
                    continue
                mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
                dx, dy = q[0] - p[0], q[1] - p[1]
                # line through m perpendicular to pq, oriented so that p is on its LEFT
                a = (mx, my); b = (mx - dy, my + dx)
                cell = G.clip(cell, G.halfplane(a, b, big=8 * spacing))
                if len(cell) < 3:
                    break
        if len(cell) < 3:
            continue
        piece = G.clip(region, G.ccw(cell))
        if len(piece) >= 3 and G.area(piece) > 0.01:
            cells.append(G.ccw(piece))
    # ice-crack character: split many cells by a random straight crack (angular, uneven pieces)
    out = []
    for P in cells:
        A = G.area(P)
        if A > 0.12 and r.random() < 0.55:
            cx, cy = G.centroid(P)
            ang = r.uniform(0, math.pi)
            ox, oy = cx + r.uniform(-0.08, 0.08), cy + r.uniform(-0.08, 0.08)
            a = (ox, oy); b = (ox + math.cos(ang), oy + math.sin(ang))
            p1 = G.clip(P, G.halfplane(a, b, big=4.0)); p2 = G.clip(P, G.halfplane(b, a, big=4.0))
            if len(p1) >= 3 and len(p2) >= 3 and min(G.area(p1), G.area(p2)) > 0.025:
                out += [G.ccw(p1), G.ccw(p2)]
                continue
        out.append(P)
    return out

# ------------------------------------------------------------------ build
def build(coll, paved_test, z_low_fn):
    """paved_test(x, y) -> True if the point is paved (any paving, incl. the complex);
    z_low_fn((x, y)) -> bottom height for a raised kerb's outer face at that point."""
    Z = zones()
    rng = random.Random(21)
    made = []
    # ---- red-paver terrace (kerb along the pond railing is wider: it carries the railing)
    nrail = len(ED.RAIL) - 1
    red = Z['red']
    # find which polygon edges are the railing edges (the polygon may have been reversed by ccw())
    rail_set = set()
    for i in range(len(red)):
        a, b = red[i], red[(i + 1) % len(red)]
        for k in range(nrail):
            p, q = ED.RAIL[k], ED.RAIL[k + 1]
            if (abs(a[0] - p[0]) + abs(a[1] - p[1]) < 1e-6 and abs(b[0] - q[0]) + abs(b[1] - q[1]) < 1e-6) or \
               (abs(a[0] - q[0]) + abs(a[1] - q[1]) < 1e-6 and abs(b[0] - p[0]) + abs(b[1] - p[1]) < 1e-6):
                rail_set.add(i)
    mbk = C.MB()
    widths = [0.36 if i in rail_set else 0.25 for i in range(len(red))]
    inner = kerb_ring(mbk, red, widths, ZP, 'M_Granite', out_paved=paved_test, z_low_fn=z_low_fn, raise_h=0.03)
    pv = S.Paver(seed=31)
    n = pave_poly(pv, G.ccw(inner), ZP, 'M_RedPaver', 0.30, 0.60, angle=0.0, origin=(35.15, 0.0), stagger=0.5)
    o = pv.finish('环境_红砖平台铺地', coll); S.recalc_up(o); made.append(o)
    print('red terrace slabs', n)
    # ---- grey plaza + sculpture circle
    inner = kerb_ring(mbk, Z['gray'], [0.25] * len(Z['gray']), ZP, 'M_Granite', out_paved=paved_test, z_low_fn=z_low_fn)
    pv = S.Paver(seed=32)
    n = pave_poly(pv, G.ccw(inner), ZP, 'M_GraniteOut', 0.60, 0.90, origin=(35.15, 0.0), stagger=0.5)
    o = pv.finish('环境_南广场铺地', coll); S.recalc_up(o); made.append(o)
    print('grey plaza slabs', n)
    # ---- ice-crack paving NW of A2
    inner = kerb_ring(mbk, Z['crazy'], [0.22] * len(Z['crazy']), ZP, 'M_Granite', out_paved=paved_test, z_low_fn=z_low_fn)
    pv = S.Paver(seed=33)
    cells = crazy_cells(G.ccw(inner))
    for P in cells:
        pv.poly(P, ZP, 'M_GraniteOut', gap=0.022, bev=0.004)
    # mortar bed between the stones (flush-ish, 6 mm below the stone tops)
    pv.mb.face([Vector((x, y, ZP - 0.006)) for (x, y) in G.ccw(inner)], 'M_Mortar')
    o = pv.finish('环境_冰裂纹铺地', coll); S.recalc_up(o); made.append(o)
    print('ice-crack cells', len(cells))
    # ---- SW pink plaza
    inner = kerb_ring(mbk, Z['swp'], [0.25] * len(Z['swp']), ZP, 'M_RedPaver', out_paved=paved_test, z_low_fn=z_low_fn)
    pv = S.Paver(seed=34)
    n = pave_poly(pv, G.ccw(inner), ZP, 'M_PinkPath', 0.60, 0.60, origin=(-14.0, -26.0), stagger=0.0)
    o = pv.finish('环境_西南广场铺地', coll); S.recalc_up(o); made.append(o)
    o = mbk.finish('环境_铺地路缘', coll, recalc=False); made.append(o)
    # ---- paths
    P = paths()
    made += build_paths(coll, P, Z, paved_test, z_low_fn)
    return made

def _cut_for_polygon(path, W, poly, at_start=True):
    """Half-plane that removes the part of a path strip lying inside `poly` at one end: the line through the two
    points where the strip edges cross the polygon boundary."""
    L = path.length
    pts = []
    for v in (W / 2, -W / 2):
        us = [L * k / 400 for k in range(401)]
        if not at_start:
            us = list(reversed(us))
        prev = None
        for u in us:
            p = path.at(u, v)
            ins = G.inside(p, poly)
            if prev is not None and prev[1] and not ins:
                pts.append(p)
                break
            prev = (p, ins)
    if len(pts) < 2:
        return None
    a, b = pts
    # orient so that the path interior (outside the polygon) is on the LEFT
    mid = path.at(L * (0.5), 0)
    d = (b[0] - a[0], b[1] - a[1])
    if d[0] * (mid[1] - a[1]) - d[1] * (mid[0] - a[0]) < 0:
        a, b = b, a
    return G.halfplane(a, b)

def _cut_line(a, b, keep_pt):
    d = (b[0] - a[0], b[1] - a[1])
    if d[0] * (keep_pt[1] - a[1]) - d[1] * (keep_pt[0] - a[0]) < 0:
        a, b = b, a
    return G.halfplane(a, b)

def path_slabs(pv, mbk, path, W, kerb_w, z, mat, kmat, n_across, sl, u0, u1, clippers=(), kerbs=True, z_low_fn=None,
               raise_h=0.02, inlay=None, avoid=()):
    """Slabs in path space (u along, v across) + side kerbs; everything clipped by `clippers` (convex CCW)."""
    inner = W / 2 - (kerb_w if kerbs else 0.0)
    w = 2 * inner / n_across
    nrow = max(1, int(round((u1 - u0) / sl)))
    dl = (u1 - u0) / nrow
    for r in range(nrow):
        ua, ub = u0 + r * dl, u0 + (r + 1) * dl
        for c in range(n_across):
            va, vb = -inner + c * w, -inner + (c + 1) * w
            Q = [path.at(ua, va), path.at(ub, va), path.at(ub, vb), path.at(ua, vb)]
            Q = G.ccw(Q)
            for cl in clippers:
                if len(Q) >= 3:
                    Q = G.clip(Q, cl)
            if len(Q) >= 3 and G.area(Q) > 0.003:
                Q = G.ccw(Q)
                zz = z
                for poly in avoid:
                    I = G.clip(poly, Q)
                    if len(I) >= 3 and G.area(I) > 1e-4:
                        zz = z - 0.004          # tucked under the neighbouring paving (no coplanar overlap)
                pv.poly(Q, zz, mat)
    if kerbs:
        nk = max(1, int(round((u1 - u0) / 0.9)))
        dk = (u1 - u0) / nk
        for side in (1, -1):
            for r in range(nk):
                ua, ub = u0 + r * dk + 0.0015, u0 + (r + 1) * dk - 0.0015
                vo, vi = side * W / 2, side * inner
                Q = G.ccw([path.at(ua, vo), path.at(ub, vo), path.at(ub, vi), path.at(ua, vi)])
                for cl in clippers:
                    if len(Q) >= 3:
                        Q = G.clip(Q, cl)
                if len(Q) < 3 or G.area(Q) < 0.002:
                    continue
                um = (ua + ub) / 2
                outp = path.at(um, side * (W / 2 + 0.2))
                zl = z_low_fn(outp) if z_low_fn else z - 0.15
                def zb(mid, i, zl=zl, um=um, side=side):
                    # outer face (on the path edge) goes down to the terrain; the rest is shallow
                    uu, vv = path.project(mid)
                    return zl if abs(abs(vv) - W / 2) < 0.03 else z - 0.06
                prism(mbk, Q, z + raise_h, None, kmat, z_bot_fn=zb)
    if inlay is not None:
        # grey diamond inlays, slightly proud of the slabs (no coplanar faces)
        step, size, imat = inlay
        u = u0 + step / 2
        while u < u1 - size:
            c = path.at(u, 0)
            t = path.tangent(u)
            n_ = (-t[1], t[0])
            D = [(c[0] + t[0] * size, c[1] + t[1] * size), (c[0] + n_[0] * size, c[1] + n_[1] * size),
                 (c[0] - t[0] * size, c[1] - t[1] * size), (c[0] - n_[0] * size, c[1] - n_[1] * size)]
            D = G.ccw(D)
            ok = True
            for cl in clippers:
                D2 = G.clip(D, cl)
                if len(D2) < 3 or G.area(D2) < 0.99 * G.area(D):
                    ok = False
            if ok:
                pv.poly(D, z + 0.004, imat, gap=0.004, bev=0.004, drop=0.02)
            u += step

def build_paths(coll, P, Z, paved_test, z_low_fn):
    made = []
    pv = S.Paver(seed=41); mbk = C.MB()
    # pink path: starts inside the SW plaza, ends at the bridge landing
    pink, Wp = P['pink']
    cuts = []
    c0 = _cut_for_polygon(pink, Wp, Z['swp'], at_start=True)
    if c0:
        cuts.append(c0)
    (lc, ld, lhl, lhw) = landings()[0]
    back = lc - ld * lhl              # landing edge facing the path
    nrm = Vector((-ld.y, ld.x, 0))
    a = (back - nrm * 3).to_2d(); b = (back + nrm * 3).to_2d()
    cuts.append(_cut_line(tuple(a), tuple(b), pink.at(pink.length * 0.5)))
    path_slabs(pv, mbk, pink, Wp, 0.2, ZP, 'M_PinkPath', 'M_RedPaver', 3, 0.5, 0.0, pink.length, clippers=cuts,
               z_low_fn=z_low_fn, raise_h=0.012, inlay=(3.2, 0.42, 'M_StoneGrey'), avoid=[Z['swp']])
    # grey path north: from the far bridge landing to the A5 apron (x = -4.48)
    grayn, Wg = P['grayn']
    (lc, ld, lhl, lhw) = landings()[1]
    front = lc + ld * lhl
    nrm = Vector((-ld.y, ld.x, 0))
    cuts = [_cut_line(tuple((front - nrm * 3).to_2d()), tuple((front + nrm * 3).to_2d()), grayn.at(grayn.length * 0.5)),
            _cut_line((-4.48, 20.0), (-4.48, 40.0), (-10.0, 30.0))]
    path_slabs(pv, mbk, grayn, Wg, 0.2, ZP, 'M_GraniteOut', 'M_Granite', 3, 0.6, 0.0, grayn.length, clippers=cuts,
               z_low_fn=z_low_fn)
    # east footpath: concrete panels, no kerbs, slightly lower
    east, We = P['east']
    path_slabs(pv, mbk, east, We, 0.0, ZP - 0.03, 'M_LightConcrete', 'M_LightConcrete', 2, 1.5, 0.0, east.length,
               kerbs=False)
    o = pv.finish('环境_园路铺地', coll); S.recalc_up(o); made.append(o)
    # east path edges: vertical faces down to the lawn (panel sides are only 12 mm deep)
    mbe = C.MB()
    n = int(east.length / 0.5)
    for side in (1, -1):
        for k in range(n):
            ua, ub = east.length * k / n, east.length * (k + 1) / n
            p0 = east.at(ua, side * We / 2); p1 = east.at(ub, side * We / 2)
            if side < 0:
                p0, p1 = p1, p0
            z0 = ZP - 0.03 - 0.012
            mbe.face([Vector((p0[0], p0[1], -0.74)), Vector((p1[0], p1[1], -0.74)), Vector((p1[0], p1[1], z0)),
                      Vector((p0[0], p0[1], z0))][::(-1 if side > 0 else 1)], 'M_LightConcrete')
    made.append(mbe.finish('环境_园路边', coll, recalc=False))
    # bridge landings (granite) and the bridge itself
    for k, (c, d, hl, hw) in enumerate(landings()):
        R = _rect(c, d, hl, hw)
        prism(mbk, R, ZP + 0.008, None, 'M_StoneGrey', z_bot_fn=lambda mid, i: z_low_fn(mid) - 0.1)
    made.append(mbk.finish('环境_园路路缘与桥台', coll, recalc=False))
    made.append(build_bridge(coll))
    return made

def build_bridge(coll):
    """Flat stone-slab bridge (2 x 8 pink granite slabs) on two granite beams and piers."""
    A, B, w = bridge_ends()
    d = (B - A).normalized(); n = Vector((-d.y, d.x, 0))
    L = (B - A).length
    mb = C.MB()
    pv = S.Paver(seed=44)
    nrow = 8
    for r in range(nrow):
        for c in range(2):
            a0, a1 = L * r / nrow, L * (r + 1) / nrow
            b0, b1 = -w / 2 + c * w / 2, -w / 2 + (c + 1) * w / 2
            Q = [A + d * a0 + n * b0, A + d * a1 + n * b0, A + d * a1 + n * b1, A + d * a0 + n * b1]
            pv.poly(G.ccw([(q.x, q.y) for q in Q]), ZP, 'M_PinkPath', gap=0.012, bev=0.008, drop=0.16)
    o = pv.finish('环境_石板桥_桥面', coll); S.recalc_up(o)
    # two longitudinal beams under the slabs, three piers
    for s in (-1, 1):
        c = (A + B) / 2 + n * s * (w / 2 - 0.22)
        mb.obox(Vector((c.x, c.y, ZP - 0.27)), (d, n, Vector((0, 0, 1))), (L / 2 + 0.3, 0.14, 0.1), 'M_Granite')
    for t in (0.0, 0.5, 1.0):
        c = A + (B - A) * t
        mb.obox(Vector((c.x, c.y, (ZP - 0.37 - 2.0) / 2)), (d, n, Vector((0, 0, 1))), (0.25, w / 2 + 0.05, (ZP - 0.37 + 2.0) / 2),
                'M_StoneGrey')
    mb.finish('环境_石板桥_梁墩', coll, recalc=True)
    return o
