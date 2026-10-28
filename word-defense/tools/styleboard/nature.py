# nature.py - the book itself, skies, ridges, mesas, trees and small plants as paper cards for eng.Canvas.
import math
import numpy as np
from eng import h2c, c2h, mix, mul, path_d, fmt
from geo2d import fbm, vnoise, sd_circle, sd_ellipse, sd_capsule, sd_box, sd_poly, sd_polyline, smin, umin, shape_loops, catmull, cut_edge
from arch import Builder, Frame, newell


# ------------------------------------------------------------------ the book
class Book:
    def __init__(s, HW=8.2, D=10.4, H=8.0, PT=0.28, CB=0.07, CO=0.22):
        s.HW, s.D, s.H, s.PT, s.CB, s.CO = HW, D, H, PT, CB, CO

    def draw(s, cv, page='#e8dcc4', edge='#d8ccb2', edge_line='#b7aa90', cover='#2a2438', cover_edge=None, gutter=0.35):
        HW, D, H, PT, CB, CO = s.HW, s.D, s.H, s.PT, s.CB, s.CO
        cam = cv.cam
        ce = cover_edge or mix(cover, '#000000', 0.35)
        zc = -PT - CB  # cover underside
        # contact shadow of the whole book on the desk
        sh = np.array([(-HW - CO - 0.3, -CO - 0.5, zc), (HW + CO + 0.3, -CO - 0.5, zc), (HW + CO + 0.6, D + PT + CO + 0.4, zc),
                       (-HW - CO - 0.6, D + PT + CO + 0.4, zc)])
        fid = cv.blur_filter(cv.nid('bks'), 16)
        cv.add('desk', '<path d="%s" fill="#000000" opacity="0.55" filter="%s"/>' % (cv.d3([sh]), fid))
        # floor cover board (lying), its visible front and side edges
        B = Builder(cv, Frame(0, 0))
        B.box(-HW - CO, HW + CO, -CO, D + PT, zc, zc + CB, cover, top=cover, front=ce, sides=ce)
        cv.add('book', ''.join(B.emit()))
        # back cover board (standing)
        B = Builder(cv, Frame(0, 0))
        B.box(-HW - CO, HW + CO, D + PT, D + PT + CB, zc, H + CO, cover, top=ce, front=cover, sides=ce)
        cv.add('book', ''.join(B.emit()))
        # page blocks: floor block (front + side edges with page lines)
        B = Builder(cv, Frame(0, 0))
        lines_front = [([[(0, k * PT / 9 - 0.004), (2 * HW, k * PT / 9 - 0.004), (2 * HW, k * PT / 9 + 0.004), (0, k * PT / 9 + 0.004)]],
                        edge_line, {'opacity': 0.5}) for k in range(1, 9)]
        lines_side = [([[(0, k * PT / 9 - 0.004), (D, k * PT / 9 - 0.004), (D, k * PT / 9 + 0.004), (0, k * PT / 9 + 0.004)]],
                       edge_line, {'opacity': 0.5}) for k in range(1, 9)]
        B.box(-HW, HW, 0, D, -PT, 0, edge, top=False, details={'front': lines_front, 'left': lines_side, 'right': lines_side})
        cv.add('book', ''.join(B.emit()))
        # back page block (standing): side edges and top edge
        B = Builder(cv, Frame(0, 0))
        lt = [([[(0, k * PT / 9 - 0.004), (2 * HW, k * PT / 9 - 0.004), (2 * HW, k * PT / 9 + 0.004), (0, k * PT / 9 + 0.004)]],
               edge_line, {'opacity': 0.5}) for k in range(1, 9)]
        B.box(-HW, HW, D, D + PT, -PT, H, edge, top=edge, front=False, details={})
        cv.add('book', ''.join(B.emit()))
        # the floor page and the back page surfaces
        floor = np.array([(-HW, 0, 0), (HW, 0, 0), (HW, D, 0), (-HW, D, 0)])
        back = np.array([(-HW, D, 0), (HW, D, 0), (HW, D, H), (-HW, D, H)])
        cv.add('floor', '<path d="%s" fill="%s"/>' % (cv.d3([floor]), page))
        s.floor_poly, s.back_poly = floor, back
        # gutter shading where the pages meet
        if gutter:
            g0 = cam.p(np.array([0, D, 0]))
            g1 = cam.p(np.array([0, D - 1.2, 0]))
            gr = cv.lingrad(g0, g1, [(0, '#000000', gutter), (1, '#000000', 0.0)])
            cv.add('floorshade', '<path d="%s" fill="%s"/>' % (cv.d3([np.array([(-HW, D - 1.2, 0), (HW, D - 1.2, 0), (HW, D, 0), (-HW, D, 0)])]), gr))
        return s

    def back_page(s, cv, stops, extra=()):
        """Sky print on the back page: vertical gradient stops [(offset, colour)] from bottom (0) to top (1)."""
        cam = cv.cam
        p0 = cam.p(np.array([0, s.D, 0]))
        p1 = cam.p(np.array([0, s.D, s.H]))
        gr = cv.lingrad(p0, p1, stops)
        cv.add('back', '<path d="%s" fill="%s"/>' % (cv.d3([s.back_poly]), gr))

    def bp(s, x, z, dy=0.0):
        """A point on the back page."""
        return np.array([x, s.D - dy, z])


# ------------------------------------------------------------------ profiles
def ridge(x0, x1, peaks, n=260, jag=0.0, jag_f=6.0, seed=0, base=0.0, shape='sharp', floor=0.0):
    """Height profile from a list of (x, height, half-width) peaks."""
    xs = np.linspace(x0, x1, n)
    h = np.full(n, floor, float)
    for px, ph, pw in peaks:
        d = np.abs(xs - px) / pw
        if shape == 'sharp':
            p = np.clip(1 - d, 0, 1) ** 1.25
        elif shape == 'round':
            p = np.sqrt(np.clip(1 - d * d, 0, 1)) ** 0.8
        elif shape == 'tall':  # steep sides, rounded top (青绿 peaks)
            p = np.clip(1 - d ** 2.4, 0, 1) ** 0.55
        else:  # soft hills
            p = np.cos(np.clip(d, 0, 1) * math.pi / 2) ** 2
        h = np.maximum(h, ph * p)
    if jag:
        nz = fbm(xs * jag_f, np.full(n, 0.37 + seed * 1.7), seed, 4)
        h = h + jag * nz * (0.3 + 0.7 * np.clip(h / (max(1e-6, h.max())), 0, 1))
    return xs, base + np.maximum(h, 0)


def profile_loop(xs, zs, z0=0.0):
    return [[(xs[0], z0)] + list(zip(xs, zs)) + [(xs[-1], z0)]]


def snow_caps(xs, zs, line, seed=0):
    """Polygons of the parts of a profile above a (noisy) snow line."""
    loops = []
    cur = []
    nz = fbm(xs * 3.0, np.full(len(xs), 2.1 + seed), seed + 9, 3)
    sl = line + 0.25 * nz
    for x, z, l in zip(xs, zs, sl):
        if z > l:
            cur.append((x, z, l))
        elif cur:
            loops.append(cur)
            cur = []
    if cur:
        loops.append(cur)
    out = []
    for c in loops:
        if len(c) < 3:
            continue
        top = [(x, z) for x, z, l in c]
        # the lower edge zig-zags down along the gullies
        bot = []
        for k, (x, z, l) in enumerate(c[::-1]):
            dz = 0.18 * (0.5 + 0.5 * math.sin(k * 1.7 + seed)) * (z - l)
            bot.append((x, l - dz))
        out.append(top + bot)
    return out


# ------------------------------------------------------------------ SDF helpers for organic cards
def blob_fn(blobs, edge_amp=0.02, edge_f=7.0, seed=0, extra=None):
    def fn(U, V):
        d = None
        for b in blobs:
            kind = b[0]
            if kind == 'c':
                _, x, y, r = b
                di = sd_circle(U, V, x, y, r)
            elif kind == 'e':
                _, x, y, rx, ry = b
                di = sd_ellipse(U, V, x, y, rx, ry)
            elif kind == 'cap':
                _, ax, ay, bx, by, ra, rb = b
                di = sd_capsule(U, V, ax, ay, bx, by, ra, rb)
            elif kind == 'poly':
                di = sd_poly(U, V, b[1])
            d = di if d is None else smin(d, di, b[-1] if False else 0.02)
        if extra is not None:
            d = extra(U, V, d)
        if edge_amp:
            d = cut_edge(d, U, V, seed, amp=edge_amp, freq=edge_f, fine=edge_amp * 0.25, fine_freq=edge_f * 5)
        return d
    return fn


def loops_of(fn, bounds, step=0.012):
    return shape_loops(fn, bounds, step)


# ------------------------------------------------------------------ trees
def poplar(seed, h=1.0, w=0.9, lean=0.0):
    """胡杨: a short gnarled trunk splitting into crooked limbs with clumped crowns.
    Returns (trunk_fn, crown_back_fn, crown_front_fn, bounds)."""
    rng = np.random.default_rng(seed)
    base_r = 0.06 * h
    fork = (lean * 0.1 + rng.uniform(-0.03, 0.03), 0.32 * h)
    limbs = []
    tips = []
    n = rng.integers(3, 5)
    for i in range(n):
        a = -0.95 + 1.9 * (i + rng.uniform(0.2, 0.8)) / n
        L = h * rng.uniform(0.32, 0.5)
        mx = fork[0] + math.sin(a) * L * 0.5 + rng.uniform(-0.05, 0.05)
        my = fork[1] + math.cos(a) * L * 0.45
        tx = fork[0] + math.sin(a) * L * (0.9 + 0.3 * abs(a))
        ty = fork[1] + math.cos(a * 0.8) * L
        limbs.append(((fork[0], fork[1]), (mx, my), (tx, ty)))
        tips.append((tx, ty))

    def trunk(U, V):
        d = sd_capsule(U, V, 0.0, -0.02, fork[0], fork[1], base_r * 1.25, base_r * 0.8)
        for (a, b, c) in limbs:
            d = smin(d, sd_capsule(U, V, a[0], a[1], b[0], b[1], base_r * 0.62, base_r * 0.4), 0.02)
            d = smin(d, sd_capsule(U, V, b[0], b[1], c[0], c[1], base_r * 0.4, base_r * 0.18), 0.015)
        # root flare
        d = smin(d, sd_ellipse(U, V, 0.0, 0.0, base_r * 2.2, base_r * 0.6), 0.03)
        return d

    clumps = []
    for (tx, ty) in tips:
        k = rng.integers(2, 4)
        for j in range(k):
            r = h * rng.uniform(0.11, 0.17) * (w / 0.9)
            clumps.append((tx + rng.uniform(-0.12, 0.12) * h, ty + rng.uniform(-0.04, 0.1) * h, r))

    def crown(scale, dy, seed2):
        def fn(U, V):
            d = None
            for (x, y, r) in clumps:
                di = sd_ellipse(U, V, x, y + dy, r * scale * 1.15, r * scale * 0.82)
                d = di if d is None else smin(d, di, 0.04 * h)
            # leafy scalloped edge
            return cut_edge(d, U, V, seed2, amp=0.022 * h, freq=9.0 / h, fine=0.008 * h, fine_freq=40.0 / h)
        return fn

    xs = [c[0] for c in clumps] + [0]
    ys = [c[1] for c in clumps]
    bounds = (min(xs) - 0.4 * h, -0.1, max(xs) + 0.4 * h, max(ys) + 0.35 * h)
    return trunk, crown(1.05, 0.03 * h, seed + 3), crown(0.86, -0.01 * h, seed + 5), bounds


def pine(seed, h=1.0, w=1.0, lean=0.15):
    """松 in the painting manner: a leaning trunk with flat, layered needle pads."""
    rng = np.random.default_rng(seed)
    pts = [(0.0, 0.0)]
    x = 0.0
    for k in range(1, 6):
        x += lean * 0.2 * h + rng.uniform(-0.04, 0.04) * h
        pts.append((x, h * 0.95 * k / 5))
    pads = []
    for k, (px, py) in enumerate(pts[2:]):
        side = 1 if k % 2 == 0 else -1
        L = h * rng.uniform(0.25, 0.42) * w
        bx = px + side * L
        by = py + rng.uniform(-0.04, 0.06) * h
        pads.append(((px, py), (bx, by), L))
    pads.append((pts[-1], (pts[-1][0] + 0.02, pts[-1][1] + 0.05 * h), h * 0.3 * w))

    def trunk(U, V):
        d = None
        for a, b in zip(pts[:-1], pts[1:]):
            di = sd_capsule(U, V, a[0], a[1], b[0], b[1], 0.045 * h * (1.2 - a[1] / h * 0.6), 0.04 * h * (1.2 - b[1] / h * 0.6))
            d = di if d is None else smin(d, di, 0.01)
        for (a, b, L) in pads:
            d = smin(d, sd_capsule(U, V, a[0], a[1], b[0] * 0.7 + a[0] * 0.3, b[1], 0.02 * h, 0.012 * h), 0.01)
        return d

    def needles(scale, dy, seed2):
        def fn(U, V):
            d = None
            for (a, b, L) in pads:
                cx = b[0] * 0.75 + a[0] * 0.25
                di = sd_ellipse(U, V, cx, b[1] + dy, L * 0.62 * scale, 0.075 * h * scale)
                di2 = sd_ellipse(U, V, cx + (b[0] - a[0]) * 0.15, b[1] + 0.05 * h + dy, L * 0.42 * scale, 0.06 * h * scale)
                di = smin(di, di2, 0.02)
                d = di if d is None else smin(d, di, 0.015)
            # bristly lower edges
            return cut_edge(d, U, V, seed2, amp=0.014 * h, freq=14.0 / h, fine=0.01 * h, fine_freq=60.0 / h)
        return fn

    allx = [p[0] for p in pts] + [p[1][0] for p in pads]
    bounds = (min(allx) - 0.5 * h, -0.05, max(allx) + 0.5 * h, h * 1.25)
    return trunk, needles(1.08, 0.012 * h, seed + 2), needles(0.9, 0.0, seed + 4), bounds


def willow(seed, h=1.0, w=1.0):
    """柳: a short leaning trunk, a high domed crown and long cascading strands that fan outward and down."""
    rng = np.random.default_rng(seed)
    top = (rng.uniform(-0.04, 0.04) * h, h * 0.55)

    def trunk(U, V):
        d = sd_capsule(U, V, 0, 0, top[0], top[1], 0.05 * h, 0.032 * h)
        for a in (-0.7, -0.2, 0.35, 0.8):
            d = smin(d, sd_capsule(U, V, top[0], top[1], top[0] + math.sin(a) * 0.3 * h, top[1] + math.cos(a) * 0.32 * h,
                                   0.026 * h, 0.01 * h), 0.012)
        return d

    strands = []
    n = 34
    for i in range(n):
        t = min(1.0, max(-1.0, -1 + 2 * i / (n - 1) + rng.uniform(-0.02, 0.02)))
        # strands spring from the crown's upper surface and arc outward before dropping
        x0 = t * 0.32 * w * h
        y0 = top[1] + 0.34 * h * (1 - t * t) ** 0.5 + rng.uniform(-0.02, 0.03) * h
        out = t * 0.3 * w * h
        L = h * rng.uniform(0.55, 0.8) * (1 - 0.35 * t * t)
        strands.append((x0, y0, out, L))

    def crown(scale, seed2, thin):
        def fn(U, V):
            d = sd_ellipse(U, V, top[0], top[1] + 0.26 * h, 0.3 * w * h * scale, 0.14 * h * scale)
            for (x0, y0, out, L) in strands:
                # arc: up-out to the shoulder, then straight down
                sx, sy = x0 + out * 0.55 * scale, y0 + 0.02 * h
                d = np.minimum(d, sd_capsule(U, V, x0, y0, sx, sy, thin * h * 1.2, thin * h))
                d = np.minimum(d, sd_capsule(U, V, sx, sy, sx + out * 0.25, sy - L * scale, thin * h, thin * h * 0.35))
            return cut_edge(d, U, V, seed2, amp=0.004 * h, freq=24.0 / h, fine=0.003 * h, fine_freq=70.0 / h)
        return fn

    bounds = (-0.95 * w * h, -0.05, 0.95 * w * h, h * 1.05)
    return trunk, crown(1.05, seed + 1, 0.014), crown(0.9, seed + 2, 0.011), bounds


def plum(seed, h=1.0):
    """梅: an angular dark branch with small round blossoms. Returns (branch_fn, blossoms list, bounds)."""
    rng = np.random.default_rng(seed)
    segs = []
    blossoms = []

    def grow(p, ang, L, r, depth):
        if depth == 0 or L < 0.05 * h:
            return
        q = (p[0] + math.cos(ang) * L, p[1] + math.sin(ang) * L)
        segs.append((p, q, r, r * 0.65))
        for k in range(rng.integers(1, 4)):
            t = rng.uniform(0.3, 1.0)
            bp = (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)
            blossoms.append((bp[0] + rng.uniform(-0.02, 0.02) * h, bp[1] + rng.uniform(-0.02, 0.02) * h, rng.uniform(0.018, 0.03) * h))
        grow(q, ang + rng.uniform(0.25, 0.7), L * rng.uniform(0.55, 0.8), r * 0.65, depth - 1)
        if rng.random() < 0.8:
            grow(q, ang - rng.uniform(0.3, 0.8), L * rng.uniform(0.45, 0.7), r * 0.6, depth - 1)

    grow((0.0, 0.0), math.pi / 2 - 0.35, 0.42 * h, 0.035 * h, 4)

    def branch(U, V):
        d = None
        for a, b, ra, rb in segs:
            di = sd_capsule(U, V, a[0], a[1], b[0], b[1], ra, rb)
            d = di if d is None else np.minimum(d, di)
        return d

    xs = [s[1][0] for s in segs] + [0]
    ys = [s[1][1] for s in segs] + [0]
    bounds = (min(xs) - 0.1 * h, -0.05, max(xs) + 0.1 * h, max(ys) + 0.1 * h)
    return branch, blossoms, bounds


def tamarisk(seed, h=0.5, w=0.7):
    """红柳: a low feathery mound."""
    rng = np.random.default_rng(seed)
    plumes = [(rng.uniform(-0.5, 0.5) * w, rng.uniform(0.5, 1.0) * h, rng.uniform(0.05, 0.09) * h / 0.5) for _ in range(14)]

    def fn(U, V):
        d = sd_ellipse(U, V, 0, h * 0.35, w * 0.5, h * 0.4)
        for (x, y, r) in plumes:
            d = smin(d, sd_capsule(U, V, x * 0.6, h * 0.3, x, y, r * 0.8, r * 0.3), 0.04)
        d = np.maximum(d, -V)
        return cut_edge(d, U, V, seed, amp=0.012, freq=26.0, fine=0.006, fine_freq=80.0)
    return fn, (-w * 0.8, -0.02, w * 0.8, h * 1.2)


def tuft(seed, h=0.18, w=0.22, n=7):
    """A small spiky tuft (camel thorn, reeds)."""
    rng = np.random.default_rng(seed)
    blades = [(rng.uniform(-0.4, 0.4) * w, rng.uniform(0.6, 1.0) * h, rng.uniform(-0.3, 0.3)) for _ in range(n)]

    def fn(U, V):
        d = None
        for x, hh, a in blades:
            di = sd_capsule(U, V, x * 0.4, 0.0, x + math.sin(a) * hh, hh, 0.012, 0.002)
            d = di if d is None else np.minimum(d, di)
        return np.maximum(d, -V)
    return fn, (-w, -0.01, w, h * 1.1)


def reeds(seed, h=0.5, w=0.4, n=12):
    rng = np.random.default_rng(seed)
    blades = [(rng.uniform(-0.5, 0.5) * w, rng.uniform(0.55, 1.0) * h, rng.uniform(-0.25, 0.25)) for _ in range(n)]

    def fn(U, V):
        d = None
        for x, hh, a in blades:
            tx, ty = x + math.sin(a) * hh, hh
            di = sd_capsule(U, V, x * 0.5, 0.0, tx, ty, 0.009, 0.003)
            di = np.minimum(di, sd_ellipse(U, V, tx + math.sin(a) * 0.04, ty + 0.03, 0.012, 0.045))
            d = di if d is None else np.minimum(d, di)
        return np.maximum(d, -V)
    return fn, (-w, -0.01, w, h * 1.2)


# ------------------------------------------------------------------ stacked strata (mesas / terraces as paper sheets)
def strata_stack(cv, cx, cy, layers, rot=0.0, seed=0, emit=True):
    """layers: list of (half_x, half_y, thickness, colour) bottom to top; each sheet an irregular rounded slab."""
    rng = np.random.default_rng(seed)
    fr = Frame(cx, cy, rot)
    B = Builder(cv, fr)
    z = 0.0
    k = 0
    ox, oy = 0.0, 0.0
    for (hx, hy, t, col) in layers:
        n = 28
        ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
        jit = 1 + 0.08 * np.array([vnoise(np.array([math.cos(a) * 2 + seed]), np.array([math.sin(a) * 2 + k]), seed + k)[0] - 0.5 for a in ang]) * 2
        # superellipse footprint
        px = ox + hx * np.sign(np.cos(ang)) * np.abs(np.cos(ang)) ** 0.55 * jit
        py = oy + hy * np.sign(np.sin(ang)) * np.abs(np.sin(ang)) ** 0.55 * jit
        bot = [(x, y, z) for x, y in zip(px, py)]
        top = [(x, y, z + t) for x, y in zip(px, py)]
        for i in range(n):
            j = (i + 1) % n
            mx, my = (px[i] + px[j]) / 2 - ox, (py[i] + py[j]) / 2 - oy
            B.face([bot[i], bot[j], top[j], top[i]], col, out=(mx, my, 0), bias=3.0 - k * 0.3)
        B.face(top, mix(col, '#ffffff', 0.12), out=(0, 0, 1), bias=2.9 - k * 0.3)
        z += t
        k += 1
        ox += rng.uniform(-0.05, 0.05)
        oy += rng.uniform(-0.03, 0.05)
    if emit:
        svg = B.emit()
        it = cv.item(float(cv.cam.depth(fr.w(np.array([0, -layers[0][1], z * 0.5])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it
    return B


# ------------------------------------------------------------------ crags: complex jagged ridgelines
def crag(x0, x1, peaks, n=420, seed=0, rough=0.35, rough_f=1.6, floor=0.0, ridged=True):
    """A jagged mountain profile: big asymmetric peaks plus ridged fractal detail."""
    xs = np.linspace(x0, x1, n)
    h = np.full(n, floor, float)
    rng = np.random.default_rng(seed)
    for px, ph, pw in peaks:
        skew = rng.uniform(0.7, 1.35)
        d = np.where(xs < px, (px - xs) / (pw * skew), (xs - px) / (pw / skew))
        p = np.clip(1 - d, 0, 1) ** 1.35
        h = np.maximum(h, ph * p)
    if rough:
        acc = np.zeros(n)
        amp, f, norm = 1.0, rough_f, 0.0
        for o in range(5):
            v = vnoise(xs * f + 13.1 * o + seed * 3.7, np.full(n, 0.5 + o * 1.3), seed + o)
            v = 1 - np.abs(2 * v - 1) if ridged else v
            acc += amp * v
            norm += amp
            amp *= 0.5
            f *= 2.1
        acc = acc / norm - 0.5
        h = h + rough * acc * (0.35 + 0.65 * np.clip(h / max(1e-6, h.max()), 0, 1))
    return xs, np.maximum(h, floor * 0.5)


def mesa(cv, cx, cy, foot, h, bands, top_col, seed=0, taper=0.06, skirt=0.25, skirt_h=0.18, skirt_col=None, rot=0.0, emit=True,
         line_col=None):
    """A flat-topped butte: footprint polygon (local x, y), cliff height h with horizontal colour bands, a talus skirt."""
    fr = Frame(cx, cy, rot)
    B = Builder(cv, fr)
    F = np.asarray(foot, float)
    c0 = F.mean(0)
    n = len(F)
    # talus skirt: from an outer ring on the ground up to the cliff foot
    if skirt:
        outer = c0 + (F - c0) * (1 + skirt / max(1e-6, np.linalg.norm(F - c0, axis=1).mean()))
        sc = skirt_col or mix(bands[0][1], '#000000', 0.05)
        for i in range(n):
            j = (i + 1) % n
            mx, my = (F[i] + F[j]) / 2 - c0
            B.face([(outer[i][0], outer[i][1], 0.0), (outer[j][0], outer[j][1], 0.0), (F[j][0], F[j][1], skirt_h), (F[i][0], F[i][1], skirt_h)],
                   sc, out=(mx, my, 0.6), bias=3.0)
    z0 = skirt_h if skirt else 0.0
    # cliffs: one face per edge with band details
    top = c0 + (F - c0) * (1 - taper)
    for i in range(n):
        j = (i + 1) % n
        a0, b0 = F[i], F[j]
        a1, b1 = top[i], top[j]
        mx, my = (a0 + b0) / 2 - c0
        poly = [(a0[0], a0[1], z0), (b0[0], b0[1], z0), (b1[0], b1[1], z0 + h), (a1[0], a1[1], z0 + h)]
        L = float(np.linalg.norm(b0 - a0))
        det = []
        zc = 0.0
        tot = sum(t for t, c in bands)
        for k, (t, c) in enumerate(bands):
            t0, t1 = zc / tot, (zc + t) / tot
            zc += t
            if k == 0:
                continue
            det.append(([[(0, t0 * h), (L, t0 * h), (L, t1 * h), (0, t1 * h)]], c, {}))
        # the face frame: s along the bottom edge, t up (approximate for tapered faces)
        B.faces.append((fr.w(np.array(poly)), bands[0][1], {'_details': [(pp, cc, oo, (a0[0], a0[1], z0), ((b0[0] - a0[0]) / L, (b0[1] - a0[1]) / L, 0),
                                                                           ((a1[0] - a0[0]) / h, (a1[1] - a0[1]) / h, 1.0)) for pp, cc, oo in det],
                                                             'bias': 2.0}))
    B.face([(p[0], p[1], z0 + h) for p in top], top_col, out=(0, 0, 1), bias=1.0)
    if emit:
        svg = B.emit()
        it = cv.item(float(cv.cam.depth(fr.w(np.array([c0[0], F[:, 1].min(), (z0 + h) * 0.5])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it
    return B


def footprint(seed, hx, hy, n=9, jag=0.18):
    rng = np.random.default_rng(seed)
    ang = np.sort(rng.uniform(0, 2 * math.pi, n))
    r = 1 + rng.uniform(-jag, jag, n)
    return np.column_stack([hx * np.cos(ang) * r, hy * np.sin(ang) * r])


def dune(seed, L=2.0, h=0.35):
    """A crescent dune seen side-on: a long gentle windward slope, a crest, a steep slip face."""
    rng = np.random.default_rng(seed)
    xs = np.linspace(-L / 2, L / 2, 80)
    c = rng.uniform(0.1, 0.3) * L
    up = np.where(xs < c, (xs + L / 2) / (c + L / 2), 0)
    down = np.where(xs >= c, 1 - (xs - c) / (L / 2 - c), 0)
    zz = h * np.where(xs < c, np.sin(np.clip(up, 0, 1) * math.pi / 2) ** 1.4, np.clip(down, 0, 1) ** 0.6)
    return xs, zz, c


def poplar2(seed, h=1.4, w=1.3):
    """胡杨 with a wide, broken crown of many leaf clumps. Returns (trunk_fn, [crown fns back to front], bounds)."""
    rng = np.random.default_rng(seed)
    r0 = 0.055 * h
    fork = (rng.uniform(-0.05, 0.05) * h, rng.uniform(0.28, 0.36) * h)
    limbs = []
    tips = []
    n = int(rng.integers(3, 6))
    for i in range(n):
        a = -1.1 + 2.2 * (i + rng.uniform(0.25, 0.75)) / n
        L = h * rng.uniform(0.3, 0.5)
        k1 = (fork[0] + math.sin(a) * L * 0.45 + rng.uniform(-0.04, 0.04) * h, fork[1] + math.cos(a) * L * 0.5)
        k2 = (fork[0] + math.sin(a) * L * (0.95 + 0.25 * abs(a)) * w / h * 1.0, fork[1] + math.cos(a * 0.85) * L * 0.95)
        limbs.append((fork, k1, k2))
        tips.append(k2)
        if rng.random() < 0.6:
            k3 = (k1[0] + math.sin(a + 0.6) * L * 0.4, k1[1] + math.cos(a + 0.6) * L * 0.45)
            limbs.append((k1, k1, k3))
            tips.append(k3)

    def trunk(U, V):
        d = sd_capsule(U, V, 0.0, -0.02, fork[0], fork[1], r0 * 1.35, r0 * 0.85)
        d = smin(d, sd_capsule(U, V, -0.02 * h, 0.0, 0.03 * h, 0.12 * h, r0 * 1.1, r0 * 0.6), 0.02)
        for (a, b, c) in limbs:
            if a != b:
                d = smin(d, sd_capsule(U, V, a[0], a[1], b[0], b[1], r0 * 0.6, r0 * 0.38), 0.02)
            d = smin(d, sd_capsule(U, V, b[0], b[1], c[0], c[1], r0 * 0.38, r0 * 0.14), 0.012)
        d = smin(d, sd_ellipse(U, V, 0.0, 0.0, r0 * 2.6, r0 * 0.55), 0.03)
        # knots and hollows
        d = np.maximum(d, -sd_ellipse(U, V, fork[0] * 0.5, fork[1] * 0.45, r0 * 0.35, r0 * 0.6))
        return d

    clumps = []
    for (tx, ty) in tips:
        for j in range(int(rng.integers(3, 6))):
            r = h * rng.uniform(0.07, 0.12)
            clumps.append((tx + rng.uniform(-0.16, 0.16) * h, ty + rng.uniform(-0.07, 0.1) * h, r, rng.random()))

    def crown(sel, scale, dy, seed2, holes=0):
        cl = [c for c in clumps if sel(c[3])]
        hr = np.random.default_rng(seed2 + 100)
        leaves = []
        for k in range(holes):
            (x, y, r, q) = cl[int(hr.integers(0, len(cl)))]
            a = hr.uniform(0, math.pi)
            leaves.append((x + hr.uniform(-0.8, 0.8) * r, y + dy + hr.uniform(-0.5, 0.5) * r, a, hr.uniform(0.6, 1.0)))

        def fn(U, V):
            d = np.full(U.shape, 1e3)
            for (x, y, r, q) in cl:
                d = smin(d, sd_ellipse(U, V, x, y + dy, r * scale * 1.25, r * scale * 0.8), 0.025 * h)
            d = cut_edge(d, U, V, seed2, amp=0.02 * h, freq=10.0 / h, fine=0.008 * h, fine_freq=45.0 / h)
            for (x, y, a, k) in leaves:
                ca, sa = math.cos(a), math.sin(a)
                Ur = (U - x) * ca + (V - y) * sa
                Vr = -(U - x) * sa + (V - y) * ca
                d = np.maximum(d, -sd_ellipse(Ur, Vr, 0, 0, 0.034 * h * k, 0.013 * h * k))
            return d
        return fn

    xs = [c[0] for c in clumps] + [0.0]
    ys = [c[1] for c in clumps]
    bounds = (min(xs) - 0.3 * h, -0.1, max(xs) + 0.3 * h, max(ys) + 0.3 * h)
    return trunk, [crown(lambda q: True, 1.1, 0.03 * h, seed + 3, holes=26), crown(lambda q: q < 0.65, 0.9, 0.0, seed + 5, holes=16),
                   crown(lambda q: q < 0.3, 0.75, -0.01 * h, seed + 7, holes=6)], bounds


def plumes(seed, h=0.6, w=0.6, n=9):
    """红柳: a clump of upright feathery plumes."""
    rng = np.random.default_rng(seed)
    pl = []
    for i in range(n):
        x = (-0.5 + i / (n - 1)) * w + rng.uniform(-0.05, 0.05)
        hh = h * rng.uniform(0.6, 1.0) * (1 - 0.35 * abs(x) / (w / 2 + 1e-6))
        a = x / w * 0.6 + rng.uniform(-0.1, 0.1)
        pl.append((x * 0.3, x + math.sin(a) * hh * 0.3, hh))

    def fn(U, V):
        d = np.full(U.shape, 1e3)
        for (x0, x1, hh) in pl:
            # a plume: narrow at the base, fat in the upper half, pointed tip
            d = np.minimum(d, sd_capsule(U, V, x0, 0.0, (x0 + x1) / 2, hh * 0.45, 0.008, 0.012))
            d = smin(d, sd_ellipse(U, V, x1, hh * 0.68, 0.045 * h / 0.6, hh * 0.3), 0.02)
        d = np.maximum(d, -V)
        return cut_edge(d, U, V, seed, amp=0.008, freq=30, fine=0.005, fine_freq=90)
    return fn, (-w, -0.01, w, h * 1.1)


def mesa_profile(seed, L=2.4, h=1.2, steps=2):
    """Flat-topped butte seen side-on: steep stepped flanks, a level top with a little erosion."""
    rng = np.random.default_rng(seed)
    xs = np.linspace(-L / 2, L / 2, 220)
    top = h * (1 + 0.04 * fbm(xs * 3, np.full(len(xs), 0.3 + seed), seed, 3))
    edge = L / 2 * rng.uniform(0.55, 0.7)
    z = np.where(np.abs(xs) < edge, top, 0.0)
    # stepped flanks: ledges at fractions of the height
    for k in range(steps):
        f = (k + 1) / (steps + 1)
        e2 = edge + (L / 2 - edge) * f
        z = np.where((np.abs(xs) >= edge + (L / 2 - edge) * k / (steps + 1)) & (np.abs(xs) < e2),
                     h * (1 - f) * (1 + 0.05 * fbm(xs * 5, np.full(len(xs), 2.0 + k), seed + k, 2)), z)
    # talus at the foot
    tal = np.clip(1 - (np.abs(xs) - (L / 2 - 0.35 * L / 2)) / (0.35 * L / 2), 0, 1) * h * 0.18
    z = np.maximum(z, tal)
    return xs, np.maximum(z, 0.0)


def band_loops(xs, zs, z0, z1):
    """The part of the silhouette under (xs, zs) between heights z0 and z1, as loops."""
    inside = zs > z0
    loops = []
    i = 0
    n = len(xs)
    while i < n:
        if not inside[i]:
            i += 1
            continue
        j = i
        while j < n and inside[j]:
            j += 1
        seg_x = xs[i:j]
        seg_t = np.minimum(zs[i:j], z1)
        lp = [(seg_x[0], z0)] + list(zip(seg_x, seg_t)) + [(seg_x[-1], z0)]
        loops.append(lp)
        i = j
    return loops
