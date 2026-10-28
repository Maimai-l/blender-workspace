# scene_b.py - 青绿山水: a blue-green landscape on silk; ink beasts crawl out of a burnt hole and walk the causeway.
import math
import sys
import numpy as np
from eng import *
from arch import *
from nature import *
from figures import *
from util import *
from geo2d import fbm, vnoise, shape_loops, sd_capsule, sd_ellipse, sd_circle, sd_box, smin, cut_edge, sd_poly

W, H = 1600, 900
HW, D, BH = 8.2, 10.4, 8.0
CAM = dict(pos=(0.0, -13.2, 12.6), target=(0.0, 5.0, 1.5), lens=35)
LIGHT = dict(light_dir=(-0.42, -0.5, 0.76), light_col='#fff4e2', amb=0.66, dif=0.5, amb_col='#eae6da',
             shadow_col='#24403f', edge_col='#fffaf0', edge_op=0.6)
SILK = '#e8d8b6'
QING = '#2e6b8a'    # 石青
LV = '#3e8a76'      # 石绿
ZHE = '#c49a62'     # 赭石
ZHU = '#c2412d'     # 朱砂
JIN = '#c9a55a'     # 泥金
MO = '#1c1f26'      # 墨
TILE = '#3a7a70'
WALL = '#efe6d4'
COL = '#b5432f'


def canvas(cam, seed=5):
    cv = Canvas(cam, seed=seed, **LIGHT)
    cv.bounce = 0.08
    cv.bounce_col = '#fff0d8'
    cv.style = ("@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@900&amp;display=block');"
                "@import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&amp;display=block');")
    return cv


def grad_card(cv, loops_uv, origin, stops, zmax, cast=False, band=None, extra=None, **kw):
    cam = cv.cam
    p0 = cam.p(np.array([origin[0], origin[1], 0.0]))
    p1 = cam.p(np.array([origin[0], origin[1], zmax]))
    g = cv.lingrad(p0, p1, stops)
    return cv.card(loops_uv, origin, g, cast=cast, band=band, extra=extra, **kw)


def peaks_card(cv, xs, zs, y, stops, zmax, seed, gold=True, strokes=True, band=None, dark=None):
    """A 青绿 range: mineral gradient, fine vertical texture strokes, a thin gold contour."""
    cam = cv.cam
    loops = profile_loop(xs, zs)
    extra = []
    if strokes:
        rng = np.random.default_rng(seed)
        lines = []
        for k in range(int(len(xs) / 2.2)):
            i = int(rng.integers(2, len(xs) - 2))
            x, ztop = xs[i], zs[i]
            if ztop < 0.6:
                continue
            L = ztop * rng.uniform(0.25, 0.6)
            z0 = ztop - rng.uniform(0.05, 0.2)
            pts = [(x + 0.03 * math.sin(t * 3 + k), z0 - L * t) for t in np.linspace(0, 1, 6)]
            lines.append(cv.card_loops3([pts], (0, y - 0.004, 0))[0])
        extra.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.9" opacity="0.35" stroke-linecap="round"/>'
                     % (path_d(cv.proj_loops(lines, close=False), close=False), dark or '#1f4f66'))
    if gold:
        top = cv.card_loops3([list(zip(xs, zs))], (0, y - 0.003, 0))[0]
        extra.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3" opacity="0.9" stroke-linejoin="round"/>'
                     % (path_d(cv.proj_loops([top], close=False), close=False), JIN))
    return grad_card(cv, loops, (0, y, 0), stops, zmax, band=band, extra=extra)


def mist(cv, x, y, z, L, th, seed, col='#f5eedd', op='0.8'):
    """留白 mist: a meandering chain of soft lobes, thick in the middle, wisping out at both ends."""
    rng = np.random.default_rng(seed)
    lobes = []
    n = 9
    for k in range(n):
        t = -1 + 2 * k / (n - 1)
        lobes.append((t * L / 2 + rng.uniform(-0.1, 0.1) * L / n, th * 0.35 * math.sin(k * 1.3 + seed) + rng.uniform(-0.1, 0.1) * th,
                      L / n * rng.uniform(0.75, 1.1), th * (1 - 0.75 * t * t) * rng.uniform(0.75, 1.15)))

    def fn(U, V):
        d = np.full(U.shape, 1e3)
        for (lx, lz, rx, rz) in lobes:
            d = smin(d, sd_ellipse(U, V, lx, lz, rx, max(0.03, rz)), 0.12)
        return cut_edge(d, U, V, seed, amp=0.02, freq=2.5, fine=0.004, fine_freq=10)
    if 'mistblur' not in cv.band_opts:
        fid = cv.nid('mist')
        cv.defs.append('<filter id="%s" x="-5%%" y="-40%%" width="110%%" height="180%%"><feGaussianBlur stdDeviation="2.6"/></filter>' % fid)
        cv.band_opts['mistblur'] = {'filter': 'url(#%s)' % fid}
    return sdf_card(cv, fn, (-L / 2 - 0.6, -th * 2.2, L / 2 + 0.6, th * 2.2), (x, y, z), col, step=0.02, cast=False, opacity=op, band='mistblur')


def willow_tree(cv, x, y, h, seed, flip=False):
    tr, cb, cf, bnd = willow(seed, h=h, w=0.9)
    st = Stack(cv)
    st.card(cb, bnd, (x, y + 0.04, 0), '#5e8c55', step=0.007, flip=flip)
    st.card(tr, bnd, (x, y, 0), '#4e3b2c', step=0.008, flip=flip)
    st.card(cf, bnd, (x, y - 0.03, 0), '#9cbf6a', step=0.007, flip=flip, cast=False)


def pine_tree(cv, x, y, h, seed, flip=False):
    tr, nb, nf, bnd = pine(seed, h=h, w=1.0, lean=0.25)
    st = Stack(cv)
    st.card(nb, bnd, (x, y + 0.04, 0), '#1f4a42', step=0.008, flip=flip)
    st.card(tr, bnd, (x, y, 0), '#5a3a2a', step=0.008, flip=flip)
    st.card(nf, bnd, (x, y - 0.03, 0), '#2f6a58', step=0.008, flip=flip, cast=False)


def peach_tree(cv, x, y, h, seed, flip=False):
    tr, crowns, bnd = poplar2(seed, h=h, w=h * 0.9)
    sdf_card(cv, tr, bnd, (x, y, 0), '#5a3a2e', step=0.009, flip=flip)
    for k, (fn, col) in enumerate(zip(crowns, ['#d98a8f', '#eab0ad', '#f6d3cc'])):
        sdf_card(cv, fn, bnd, (x, y + 0.04 - 0.035 * k, 0), col, step=0.01, flip=flip, cast=(k == 0))


def rock(cv, x, y, w, h, seed, top=LV, base=ZHE):
    rng = np.random.default_rng(seed)

    def fn(U, V):
        d = sd_ellipse(U, V, 0, h * 0.45, w * 0.5, h * 0.55)
        for k in range(4):
            d = smin(d, sd_ellipse(U, V, rng.uniform(-0.3, 0.3) * w, rng.uniform(0.3, 0.8) * h, w * rng.uniform(0.15, 0.3), h * rng.uniform(0.2, 0.35)), 0.05)
        d = np.maximum(d, -V)
        return cut_edge(d, U, V, seed, amp=0.02, freq=6, fine=0.006, fine_freq=30)
    loops = shape_loops(fn, (-w, -0.02, w, h * 1.3), 0.012)
    return grad_card(cv, loops, (x, y, 0), [(0, base), (0.45, mix(base, top, 0.5)), (1, top)], h * 1.1, cast=True)


def boat(cv, x, y, s=1.0, flip=False, sail=True):
    hull = [[(-0.45 * s, 0.06 * s), (0.45 * s, 0.06 * s), (0.36 * s, -0.02 * s), (-0.32 * s, -0.02 * s)]]
    cv.card([[(u * (-1 if flip else 1), v) for u, v in hull[0]]], (x, y, 0.0), '#5b3f2c', cast=False)
    if sail:
        sl = [(-0.05 * s, 0.08 * s), (0.22 * s, 0.1 * s), (0.18 * s, 0.62 * s), (-0.04 * s, 0.66 * s)]
        sl = [(u * (-1 if flip else 1), v) for u, v in sl]
        ribs = []
        for k in range(1, 6):
            t = k / 6
            a = (sl[0][0] + (sl[3][0] - sl[0][0]) * t, sl[0][1] + (sl[3][1] - sl[0][1]) * t)
            b = (sl[1][0] + (sl[2][0] - sl[1][0]) * t, sl[1][1] + (sl[2][1] - sl[1][1]) * t)
            ribs.append(cv.card_loops3([[a, b]], (x, y - 0.004, 0.0))[0])
        extra = ['<path d="%s" stroke="#8a6f52" stroke-width="0.8" fill="none"/>' % path_d(cv.proj_loops(ribs, close=False), close=False)]
        cv.card([sl], (x, y - 0.01, 0.0), '#f3ead8', cast=False, extra=extra)
        mast = [[(-0.012 * s, 0.0), (0.012 * s, 0.0), (0.012 * s, 0.72 * s), (-0.012 * s, 0.72 * s)]]
        cv.card(mast, (x, y + 0.01, 0.0), '#4a3424', cast=False)


def ink_foe(cv, x, y, z, flip, h=0.55, k=0):
    parts, bnd = ink_beast(h, seed=k, stride=k * 1.2)
    st = Stack(cv)
    st.card(parts['body'], bnd, (x, y, z), MO, step=0.005 * h / 0.42, flip=flip, cast=True)
    st.card(parts['sheen'], bnd, (x, y - 0.008, z), '#46566e', step=0.003 * h / 0.42, flip=flip, cast=False, opacity='0.85')
    st.card(parts['eye'], bnd, (x, y - 0.012, z), '#f2d38a', step=0.003 * h / 0.42, flip=flip, cast=False)


def seal(cv, P, size, ch='破', rot=-0.12, col=ZHU):
    cam = cv.cam
    if cam.depth(np.asarray(P, float)) < 2.5:
        return
    c = cam.p(np.asarray(P, float))
    s = size * cam.scale(np.asarray(P, float))
    t = ('<g transform="translate(%s %s) rotate(%s)">' % (fmt(c[0]), fmt(c[1]), fmt(math.degrees(rot))) +
         '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"/>' % (fmt(-s / 2), fmt(-s / 2), fmt(s), fmt(s), fmt(s * 0.06), col) +
         '<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#fff3e6" stroke-width="%s"/>'
         % (fmt(-s * 0.4), fmt(-s * 0.4), fmt(s * 0.8), fmt(s * 0.8), fmt(max(1.0, s * 0.035))) +
         '<text x="0" y="%s" text-anchor="middle" font-family="Noto Serif SC" font-weight="900" font-size="%s" fill="#fff3e6">%s</text>'
         % (fmt(s * 0.24), fmt(s * 0.62), ch) + '</g>')
    cv.add('fx', t)


def gold_stroke(cv, A, w=4.0):
    cam = cv.cam
    A = np.asarray(A, float)
    A = A[cam.depth(A) > 0.3]
    if len(A) < 3:
        return
    P = cam.p(A)
    n = len(P)
    T = np.gradient(P, axis=0)
    T /= (np.linalg.norm(T, axis=1, keepdims=True) + 1e-12)
    N = np.stack([-T[:, 1], T[:, 0]], 1)
    wid = w * np.sin(np.linspace(0.05, math.pi * 0.95, n)) ** 0.7
    L = P + N * wid[:, None] / 2
    R = P - N * wid[:, None] / 2
    poly = np.concatenate([L, R[::-1]])
    g = cv.lingrad(P[0], P[-1], [(0, JIN, 0.2), (0.5, '#e8c977', 0.95), (1, '#fff1c2', 1.0)])
    cv.add('fx', '<path d="%s" fill="%s"/>' % (path_d([poly]), g))


# ------------------------------------------------------------------ the city: a Song town gate with a pagoda
def town(cv, cx, cy, hx=1.7, hy=1.25, Hw=0.62, gate_s=-0.45):
    C = Compound(cv)
    from arch import fortress as af
    af(cv, C, cx, cy, hx, hy, 0.26, Hw, '#c9a46e', layer_lines=None, gate=('front', gate_s, 0.36, 0.44, 'arch'),
       merlon=(0.1, 0.07, 0.1, 0.05))
    svg, faces = tower2(cv, cx + gate_s, cy - hy, Hw, 1.1, 0.5, 0.32, 0.28, roof=TILE, wall=WALL, column=COL,
                        inset=0.12, overhang=0.2, rise1=0.12, rise2=0.4, lift=0.16, bays=5, ridge=JIN, gable=COL, emit=False)
    C.add(svg, (cx + gate_s, cy - hy, Hw + 0.5))
    C.faces += [np.asarray(f[0]) for f in faces]
    for sx in (-1, 1):
        B, ov, R = hall(cv, cx + sx * hx, cy - hy, Hw, 0.4, 0.4, 0.24, 0.24, kind='xieshan', bays=1, wall=WALL, column=COL,
                        roof=TILE, ridge=JIN, gable=COL, base_h=0.0, overhang=0.12, lift=0.1, emit=False, ornament=True)
        C.builder(B, ov, key_local=(0, 0, 0.35))
    for (x, y, w_, d_, hb, rh, kind) in [(cx + 0.55, cy + 0.2, 1.1, 0.6, 0.38, 0.34, 'xieshan'), (cx - 0.9, cy + 0.45, 0.6, 0.42, 0.28, 0.24, 'hip')]:
        B, ov, R = hall(cv, x, y, 0.0, w_, d_, hb, rh, kind=kind, bays=5 if w_ > 0.8 else 3, wall=WALL, column=COL, roof=TILE,
                        ridge=JIN, gable=COL, base='#d8ccb0', base_h=0.08, overhang=0.14, lift=0.12, emit=False)
        C.builder(B, ov, key_local=(0, 0, 0.3))
    svg, faces = pagoda3d(cv, cx + 1.05, cy + 0.75, 0.0, n=7, w0=0.5, w1=0.25, h0=0.3, h1=0.19, roof=TILE, wall=WALL, column=COL,
                          ridge=JIN, emit=False)
    C.add(svg, (cx + 1.05, cy + 0.75, 1.2))
    C.faces += [np.asarray(f[0]) for f in faces]
    return C.emit((cx, cy - hy, 0.4))


# ------------------------------------------------------------------ the scene
ROAD = [(-1.9, 10.0), (-1.85, 9.2), (-1.6, 8.3), (-1.25, 7.35), (-0.5, 6.5), (1.2, 6.05), (3.0, 5.85), (3.85, 5.35),
        (3.3, 4.7), (1.6, 4.35), (-1.0, 4.0), (-3.9, 3.6), (-5.35, 2.75), (-4.8, 1.75), (-2.8, 1.15), (0.5, 0.95),
        (3.0, 0.92), (4.4, 0.98), (4.95, 1.12), (5.1, 1.32)]
HOLE = (-1.9, 1.75)


def build(cam=None, W=W, H=H):
    cam = cam or Cam(CAM['pos'], CAM['target'], CAM['lens'], W, H)
    cv = canvas(cam)
    rng = np.random.default_rng(11)
    bk = Book(HW, D, BH)
    bk.draw(cv, page='#dcd2a8', edge='#efe4ca', edge_line='#b8a888', cover='#25403e', gutter=0.0)
    bk.back_page(cv, [(0, '#e9e2c9'), (0.1, '#dfe2d0'), (0.3, '#ebdfc4'), (1, '#dccaa3')])

    # an inscription column and a seal on the silk, as on a hand scroll
    P = bk.bp(-3.6, 5.75)
    c = cam.p(P)
    sc = cam.scale(P)
    col_txt = ''.join('<text x="%s" y="%s" font-family="Ma Shan Zheng" font-size="%s" fill="#3b3a36" opacity="0.78" text-anchor="middle">%s</text>'
                      % (fmt(c[0]), fmt(c[1] + k * 0.36 * sc), fmt(0.34 * sc), ch) for k, ch in enumerate('千里江山'))
    cv.add('backprint', col_txt)
    s2 = 0.3 * sc
    y2 = c[1] + 4 * 0.36 * sc - 0.05 * sc
    cv.add('backprint', '<rect x="%s" y="%s" width="%s" height="%s" fill="%s" opacity="0.88"/>' % (fmt(c[0] - s2 / 2), fmt(y2), fmt(s2), fmt(s2), ZHU) +
           '<text x="%s" y="%s" font-family="Noto Serif SC" font-weight="900" font-size="%s" fill="#f4e6d6" text-anchor="middle">守</text>'
           % (fmt(c[0]), fmt(y2 + s2 * 0.76), fmt(s2 * 0.72)))

    # the burnt hole in the silk, with ink spilling out
    hx, hz = HOLE

    def hole_fn(sc):
        def fn(U, V):
            d = sd_ellipse(U, V, hx, hz, 1.05 * sc, 1.3 * sc)
            d = smin(d, sd_ellipse(U, V, hx + 0.1, 0.6, 0.85 * sc, 0.6), 0.2)
            d = np.maximum(d, -V)
            return cut_edge(d, U, V, 41, amp=0.08 * sc, freq=2.8, fine=0.02, fine_freq=14)
        return fn
    for sc, col in [(1.18, '#3a2416'), (1.1, '#6b3a1c'), (1.04, '#d9792f'), (1.0, '#15161c')]:
        loops = shape_loops(hole_fn(sc), (hx - 1.8, -0.1, hx + 1.8, hz + 1.9), 0.02)
        cv.add('backprint', '<path d="%s" fill="%s" fill-rule="evenodd"/>' % (cv.d3(cv.card_loops3(loops, (0, D - 0.001, 0))), col))
    # the dark inside: a faint blue sheen of wet ink
    glow(cv, bk.bp(hx + 0.2, hz + 0.3), 0.9, '#2d4f6a', 0.5, layer='backprint')

    # far peaks, main peaks (with a valley at the hole), mist, near hills
    def valley(xs, zs, depth=0.35, w=1.25):
        k = np.clip(np.abs(xs - hx) / w, 0, 1) ** 1.6
        return depth + (zs - depth) * k
    xs, zs = ridge(-HW, HW, [(-7.0, 4.2, 0.9), (-5.6, 5.3, 0.8), (-4.3, 4.4, 0.7), (0.4, 4.6, 0.8), (1.6, 5.4, 0.9), (3.1, 4.3, 0.7),
                             (5.0, 5.6, 0.9), (6.4, 4.5, 0.8), (7.6, 3.8, 0.7)], shape='tall', jag=0.06, seed=1, floor=1.2)
    zs = valley(xs, zs, 0.5, 1.5)
    peaks_card(cv, xs, zs, D - 0.12, [(0, '#c9ccb4'), (0.4, '#a8c2bd'), (1, '#8eb0ba')], 5.6, 1, gold=False, strokes=False)
    mist(cv, -5.0, D - 0.2, 1.3, 5.6, 0.45, 3)
    mist(cv, 3.8, D - 0.2, 1.5, 6.6, 0.5, 4)
    xs, zs = ridge(-HW, HW, [(-7.4, 2.8, 0.75), (-6.3, 3.6, 0.7), (-5.0, 2.6, 0.6), (-3.6, 3.2, 0.65), (0.0, 2.9, 0.6), (1.1, 3.9, 0.75),
                             (2.4, 3.1, 0.6), (3.8, 4.2, 0.8), (5.2, 3.3, 0.65), (6.5, 3.8, 0.75), (7.7, 2.7, 0.6)],
                   shape='tall', jag=0.05, seed=2, floor=0.8)
    zs = valley(xs, zs, 0.35, 1.25)
    peaks_card(cv, xs, zs, D - 0.6, [(0, ZHE), (0.25, '#a7a06a'), (0.5, LV), (0.85, QING), (1, '#285e7c')], 4.0, 2)
    # waterfall between two peaks on the right
    wf = [[(3.02, 0.55), (3.3, 0.55), (3.24, 2.7), (3.1, 2.7)]]
    streaks = [cv.card_loops3([[(3.08 + 0.045 * k, 0.6), (3.12 + 0.03 * k, 2.65)]], (0, D - 0.625, 0))[0] for k in range(4)]
    cv.card(wf, (0, D - 0.62, 0), '#f3f0e6', cast=False,
            extra=['<path d="%s" stroke="#a9c8c6" stroke-width="0.9" fill="none"/>' % path_d(cv.proj_loops(streaks, close=False), close=False)])
    mist(cv, -4.8, D - 0.75, 0.75, 6.6, 0.55, 5)
    mist(cv, 4.6, D - 0.75, 0.9, 6.0, 0.5, 6)
    mist(cv, 1.0, D - 0.9, 0.35, 3.2, 0.35, 7)
    # near hills at the sides
    xs, zs = ridge(-HW, -3.2, [(-7.2, 1.9, 0.9), (-5.9, 2.4, 0.8), (-4.5, 1.5, 0.7)], shape='tall', jag=0.04, seed=3, floor=0.5)
    peaks_card(cv, xs, zs, D - 1.25, [(0, ZHE), (0.35, '#9c9a64'), (0.6, LV), (1, '#2f6f7e')], 2.4, 3, band='near')
    xs, zs = ridge(1.4, HW, [(2.4, 1.3, 0.6), (4.9, 1.9, 0.9), (6.6, 2.3, 0.8), (7.7, 1.6, 0.6)], shape='tall', jag=0.04, seed=4, floor=0.45)
    peaks_card(cv, xs, zs, D - 1.25, [(0, ZHE), (0.35, '#9c9a64'), (0.6, LV), (1, '#2f6f7e')], 2.3, 4, band='near')
    # a small pagoda on the left hill, pines on ridges
    pg = pagoda_outline(n=7, base_w=0.22, top_w=0.12, storey=0.16, eave=0.08, spire=0.22, curve=0.035)
    cv.card(pg, (-5.9, D - 1.27, 2.3), '#5a4a3e', cast=False, band='near')

    # ---- floor: land, lake with fine wave lines, islands, the causeway
    road = smooth(ROAD, 8)
    clipx = lambda P: np.column_stack([np.clip(P[:, 0], -HW, HW), np.clip(P[:, 1], 0.0, D)])
    lake_out = []
    ang = np.linspace(0, 2 * math.pi, 140, endpoint=False)
    for a in ang:
        r = 1 + 0.06 * math.sin(a * 5) + 0.04 * math.sin(a * 9 + 1)
        lake_out.append((0.2 + 7.4 * r * math.cos(a), 4.6 + 3.9 * r * math.sin(a)))
    lake = clipx(np.array(lake_out))
    land = '#cfc59a'
    cv.floor([np.array([(-HW, 0, 0), (HW, 0, 0), (HW, D, 0), (-HW, D, 0)])[:, :2]], land)
    # land texture: soft patches
    for k in range(30):
        x, y = rng.uniform(-HW, HW), rng.uniform(0, D)
        rr = rng.uniform(0.3, 0.9)
        a2 = np.linspace(0, 2 * math.pi, 14, endpoint=False)
        cv.floor([clipx(np.column_stack([x + rr * np.cos(a2) * 1.5, y + rr * np.sin(a2)]))], '#bcb68a', opacity='0.45')
    cv.floor([lake], '#9cc2b6')
    cv.floor([clipx(np.array([(x, y) for x, y in zip(lake[:, 0], lake[:, 1])]) * 1.0)], '#acd0c2')
    # wave pattern (网巾水): rows of small arcs, clipped to the lake
    clip = cv.clip3([np.column_stack([lake, np.zeros(len(lake))])])
    arcs = []
    y = 0.6
    row = 0
    while y < 8.8:
        x = -8.0 + (0.17 if row % 2 else 0.0)
        while x < 8.0:
            t = np.linspace(0, math.pi, 9)
            arcs.append(np.column_stack([x + 0.17 * np.cos(t), y + 0.07 * np.sin(t), np.zeros(9)]))
            x += 0.34
        y += 0.13
        row += 1
    cv.add('floorprint', '<g clip-path="%s"><path d="%s" fill="none" stroke="#e8f2ea" stroke-width="0.8" opacity="0.75"/></g>'
           % (clip, path_d(cv.proj_loops(arcs, close=False), close=False)))
    # islands
    for (x, y, rx, ry, sd) in [(-5.3, 5.6, 0.9, 0.5, 1), (5.9, 6.6, 1.1, 0.55, 2), (-0.9, 2.3, 0.7, 0.35, 3)]:
        a2 = np.linspace(0, 2 * math.pi, 40, endpoint=False)
        rr = 1 + 0.12 * np.sin(a2 * 3 + sd) + 0.06 * np.sin(a2 * 7)
        cv.floor([clipx(np.column_stack([x + rx * rr * np.cos(a2) * 1.12, y + ry * rr * np.sin(a2) * 1.12]))], '#e4ecd8', opacity='0.8')
        cv.floor([clipx(np.column_stack([x + rx * rr * np.cos(a2), y + ry * rr * np.sin(a2)]))], '#b9b98a')
    # causeway: grassy banks, a pale walk, a dark waterline
    cv.floor([clipx(ribbon(road, 0.95, seed=6, wobble=0.05))], '#6f8f6a', opacity='0.55')
    cv.floor([clipx(ribbon(road, 0.82, seed=7, wobble=0.04))], '#8aa774')
    cv.floor([clipx(ribbon(road, 0.5, seed=8, wobble=0.03))], '#e6d6ad')
    cv.floor_line(clipx(offset_line(road, 0.41)), '#5d7a5c', 1.0, opacity='0.6')
    # ink spilt from the hole onto the floor and along the start of the causeway
    for k in range(70):
        s = rng.uniform(0.0, 0.22) ** 1.4
        p, d = at(road, s)
        nrm = np.array([-d[1], d[0]])
        q = p + nrm * rng.uniform(-0.35, 0.35)
        rr = rng.uniform(0.02, 0.08) * (1.5 - s * 4)
        a2 = np.linspace(0, 2 * math.pi, 9, endpoint=False)
        jj = 1 + 0.3 * np.sin(a2 * 3 + k)
        cv.floor([clipx(np.column_stack([q[0] + rr * jj * np.cos(a2) * 1.3, q[1] + rr * jj * np.sin(a2)]))], MO, opacity='0.85')
    pool = [(hx - 0.9, D - 0.02), (hx + 1.0, D - 0.02), (hx + 0.7, D - 0.9), (hx + 0.2, D - 1.3), (hx - 0.4, D - 1.1)]
    cv.floor([clipx(smooth(pool + [pool[0]], 6))], MO, opacity='0.9')

    # ---- arch bridges on the causeway
    for s in (0.33, 0.6):
        p, d = at(road, s)
        arch_bridge(cv, p[0], p[1], 1.0, 0.32, 0.6, rot=math.atan2(d[1], d[0]), col='#d9d2c0', deck='#ece6d6', rail='#e5ddca')

    # ---- trees, rocks, boats
    for k, s in enumerate(np.linspace(0.08, 0.95, 11)):
        p, d = at(road, s)
        nrm = np.array([-d[1], d[0]])
        side = 1 if k % 2 == 0 else -1
        q = p + nrm * side * 0.5
        willow_tree(cv, q[0], q[1], 1.2, 30 + k, flip=(k % 2 == 0))
    for (x, y, h, sd) in [(-7.3, 1.2, 1.6, 1), (-6.4, 0.7, 1.1, 2), (-5.2, 5.8, 1.1, 3), (6.2, 6.8, 1.2, 4), (-0.7, 2.45, 0.9, 5)]:
        pine_tree(cv, x, y, h, sd, flip=(sd % 2 == 0))
    for (x, y, w_, h_, sd) in [(-6.8, 1.5, 0.9, 0.8, 1), (-5.6, 5.55, 0.7, 0.55, 2), (6.4, 6.5, 0.8, 0.6, 3), (7.6, 2.0, 0.7, 0.6, 4),
                               (-7.6, 6.9, 0.8, 0.9, 5)]:
        rock(cv, x, y, w_, h_, sd)
    B, ov, R = hall(cv, 5.6, 6.75, 0.0, 0.45, 0.45, 0.26, 0.24, kind='pyramid', bays=1, wall=WALL, column=COL, roof=TILE,
                    ridge=JIN, base_h=0.06, overhang=0.12, lift=0.1, emit=False, finial=(0.14, JIN))
    emit_building(cv, B, ov, (0, -0.22, 0.2))
    for (x, y, s, f) in [(-3.3, 6.9, 1.0, False), (2.0, 7.4, 0.9, True), (-2.6, 2.75, 0.8, False), (1.8, 3.15, 0.7, True)]:
        boat(cv, x, y, s, flip=f)

    # ---- the town
    town(cv, 5.55, 2.75)

    # ---- ink beasts on the causeway
    foes = [0.035, 0.08, 0.13, 0.19, 0.25, 0.31, 0.36, 0.41]
    hits = []
    for k, s in enumerate(foes):
        p, d = at(road, s)
        flip = d[0] > 0.0
        p = p + np.array([-d[1], d[0]]) * (0.08 if k % 2 else -0.08)
        z = 0.0
        for sb in (0.33, 0.6):
            if abs(s - sb) < 0.02:
                z = 0.3
        ink_foe(cv, p[0], p[1], z, flip, 0.62 if k % 3 else 0.78, k)
        hits.append(np.array([p[0], p[1], z + 0.35]))
    src = np.array([5.55 - 0.45, 2.75 - 1.25, 1.55])
    for k, (tgt, frac) in enumerate([(hits[7], 1.0), (hits[6], 0.7), (hits[5], 0.5)]):
        A = arc3(src + np.array([0.05 * k, 0, 0]), tgt, 1.8 + 0.3 * k, 70)
        n = int(len(A) * frac)
        gold_stroke(cv, A[max(0, n - 30):n], w=5.0)
    seal(cv, hits[7] + np.array([0, 0, 0.45]), 0.62, '破')
    burst = []
    if cam.depth(hits[7]) < 2.5:
        return cv, bk
    c = cam.p(hits[7])
    sc = cam.scale(hits[7])
    for j in range(16):
        a = j / 16 * 2 * math.pi
        r = sc * (0.5 + 0.25 * ((j * 5) % 3) / 2)
        rr = sc * 0.04
        burst.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (fmt(c[0] + math.cos(a) * r), fmt(c[1] + math.sin(a) * r * 0.75), fmt(rr),
                                                                    [JIN, MO, ZHU][j % 3]))
    cv.add('fx', ''.join(burst))
    return cv, bk


def render(cv, out, W=W, H=H):
    floor_f = cv.paper_filter('floorpaper', 31, freq=0.006, fx=0.004, fy=0.011, mottle=0.3, shadow=None, edge=0)
    back_f = cv.paper_filter('backpaper', 32, freq=0.006, mottle=0.28, shadow=None, edge=0)
    svg = cv.render(band_gap=0.7, band_default=dict(freq=0.0075, mottle=0.26, shadow=(2.5, 3.5, 3.0, 0.32), edge=1.2),
                    floor_filter=floor_f, back_filter=back_f, shadow_blur=3.5, shadow_op=0.24, grain=0.05, vignette=0.42,
                    desk_col='#1b2222')
    open(out + '.svg', 'w').write(svg)


if __name__ == '__main__':
    import os
    os.makedirs('out', exist_ok=True)
    out = sys.argv[1] if len(sys.argv) > 1 else 'out/scene_b'
    cv, bk = build()
    render(cv, out)
    print('ok', len(cv.items), 'items')
