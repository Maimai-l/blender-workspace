# scene_a.py - 孤城: a frontier fortress at dusk; enemies pour through a breach in the Great Wall.
import math
import sys
import numpy as np
from eng import *
from arch import *
from nature import *
from figures import *
from util import *
from geo2d import fbm, vnoise, shape_loops, sd_capsule, sd_ellipse, sd_circle, smin, cut_edge, sd_poly

W, H = 1600, 900
HW, D, BH = 8.2, 10.4, 8.0
CAM = dict(pos=(0.0, -13.2, 12.6), target=(0.0, 5.0, 1.5), lens=35)
LIGHT = dict(light_dir=(0.32, 0.85, 0.42), light_col='#ffc27a', amb=0.62, dif=0.8, amb_col='#b29cc0',
             shadow_col='#2c2346', edge_col='#ffd08c', edge_op=0.75)
EARTH = '#cf9a62'
ROOF = '#3d3741'
TIMBER = '#7b2f24'
WALLS = '#d2b48c'


def canvas(cam, seed=3):
    cv = Canvas(cam, seed=seed, **LIGHT)
    cv.bounce = 0.22
    cv.bounce_col = '#ffb070'
    return cv


# ------------------------------------------------------------------ elements (shared with the tiles)
def fortress(cv, cx, cy, hx=1.7, hy=1.25, Hw=0.82, gate_s=-0.45):
    C = Compound(cv)
    arch_fortress = globals()['_fortress_walls']
    arch_fortress(cv, C, cx, cy, hx, hy, 0.32, Hw, EARTH, layer_lines=(0.1, mul(EARTH, 0.8), 0.011),
                  gate=('front', gate_s, 0.38, 0.48, 'trap'), merlon=(0.13, 0.09, 0.13, 0.065))
    svg, faces = tower2(cv, cx + gate_s, cy - hy, Hw, 1.05, 0.48, 0.3, 0.26, roof=ROOF, wall=WALLS, column=TIMBER,
                        inset=0.11, overhang=0.19, rise1=0.11, rise2=0.36, lift=0.12, bays=3, lit1='#ffc76a', lit2='#ffb44d',
                        emit=False, gable='#8a3a2a')
    C.add(svg, (cx + gate_s, cy - hy, Hw + 0.5))
    C.faces += [np.asarray(f[0]) for f in faces]
    for sx in (-1, 1):
        for sy in (-1, 1):
            B, ov, R = hall(cv, cx + sx * hx, cy + sy * hy, Hw, 0.38, 0.38, 0.22, 0.21, kind='pyramid', bays=1, wall=WALLS,
                            column=TIMBER, roof=ROOF, base_h=0.0, overhang=0.1, lift=0.05, emit=False, ornament=False,
                            lit='#ffbf66' if sy < 0 else None)
            C.builder(B, ov, key_local=(0, 0, 0.35))
    for (x, y, w_, d_, hb, rh, kind, lit) in [(cx + 0.5, cy + 0.45, 1.15, 0.62, 0.4, 0.34, 'xieshan', '#ffc06a'),
                                              (cx - 0.85, cy + 0.6, 0.62, 0.42, 0.28, 0.22, 'gable', None),
                                              (cx + 1.0, cy - 0.55, 0.55, 0.38, 0.26, 0.2, 'gable', '#ffbf66')]:
        B, ov, R = hall(cv, x, y, 0.0, w_, d_, hb, rh, kind=kind, bays=3 if w_ < 0.8 else 5, wall=WALLS, column=TIMBER,
                        roof=ROOF, base='#a88560', base_h=0.06, overhang=0.13, lift=0.09 if kind != 'gable' else 0.0, lit=lit,
                        emit=False, ornament=kind != 'gable', gable='#8a3a2a')
        C.builder(B, ov, key_local=(0, 0, 0.3))
    for (bx_, by_, z0, h_) in [(cx - 1.3, cy - hy - 0.13, Hw, 0.62), (cx + 0.35, cy - hy - 0.13, Hw, 0.62), (cx + 1.3, cy - hy - 0.13, Hw, 0.62),
                               (cx - hx - 0.13, cy + 0.2, Hw, 0.62), (cx + 0.5, cy + 0.45, 0.85, 0.9)]:
        pole = [[(-0.009, 0), (0.009, 0), (0.009, h_), (-0.009, h_)]]
        flag = [[(0.0, h_ - 0.02), (0.3, h_ - 0.05), (0.25, h_ - 0.13), (0.31, h_ - 0.22), (0.0, h_ - 0.19)]]
        L3p = cv.card_loops3(pole, (bx_, by_, z0))
        L3f = cv.card_loops3(flag, (bx_, by_, z0))
        C.add(['<path d="%s" fill="#2a1d1a"/>' % cv.d3(L3p),
               '<path d="%s" fill="#b5352b" stroke="#5a1c18" stroke-width="0.8"/>' % cv.d3(L3f)], (bx_, by_ - 0.12, z0 + h_))
        cv.cast(L3f)
    for sx in (-1, 1):
        lp = (cx + gate_s + sx * 0.3, cy - hy - 0.2, 0.5)
        L3 = cv.card_loops3([[(-0.035, -0.06), (0.035, -0.06), (0.045, 0.0), (0.035, 0.06), (-0.035, 0.06), (-0.045, 0.0)]], lp)
        C.add(['<path d="%s" fill="#ff8c3a" stroke="#5a1c18" stroke-width="0.7"/>' % cv.d3(L3)], (lp[0], lp[1] - 0.2, lp[2]))
    it = C.emit((cx, cy - hy, 0.4))
    for sx in (-1, 1):
        glow(cv, (cx + gate_s + sx * 0.3, cy - hy - 0.22, 0.5), 0.28, '#ffb35c', 0.9, core='#fff1c8')
    glow(cv, (cx + gate_s, cy - hy - 0.22, 0.95), 0.6, '#ffb35c', 0.5)
    glow(cv, (cx + gate_s, cy - hy - 0.2, 0.22), 0.35, '#ff9a4a', 0.55)
    return it


def _fortress_walls(cv, C, cx, cy, hx, hy, T, Hw, col, layer_lines=None, merlon=None, gate=None):
    from arch import fortress as af
    af(cv, C, cx, cy, hx, hy, T, Hw, col, layer_lines=layer_lines, merlon=merlon, gate=gate)


def poplar_tree(cv, x, y, h, seed, flip=False, cols=('#4a3127', '#b8702c', '#dc9a3c', '#f2c35a')):
    tr, crowns, bnd = poplar2(seed, h=h, w=1.0 * h)
    st = Stack(cv)
    st.card(crowns[0], bnd, (x, y + 0.05, 0), cols[1], step=0.011, flip=flip, cast=True)
    st.card(tr, bnd, (x, y, 0), cols[0], step=0.01, flip=flip)
    for k, fn in enumerate(crowns[1:]):
        st.card(fn, bnd, (x, y + 0.005 - 0.045 * k, 0), cols[k + 2], step=0.011, flip=flip, cast=False)


def tamarisk_clump(cv, x, y, seed, h=0.55, w=0.6):
    """红柳: soft rust-mauve plumes over a clump of dry grass."""
    fn, bnd = plumes(seed, h=h, w=w, n=7)
    st = Stack(cv)
    st.card(fn, bnd, (x, y + 0.03, 0), '#8a5a52', step=0.008)
    fn2, bnd2 = tuft(seed + 50, h=h * 0.55, w=w * 0.9, n=16)
    st.card(fn2, bnd2, (x + 0.03, y - 0.03, 0), '#b0915f', step=0.006, cast=False)


def rider(cv, x, y, z, flip, h=0.9, k=0):
    parts, bnd = puppet_rider(h, stride=k * 1.3)
    glow(cv, (x, y + 0.05, z + h * 0.45), h * 0.6, '#ff9b4f', 0.4)
    st = Stack(cv)
    for name, col in [('weapon', '#2b1b1a'), ('horse', '#b5482f'), ('saddle', '#e0a040'), ('rider', '#3e6b5d'), ('rivets', '#2a1614')]:
        st.card(parts[name], bnd, (x, y, z), col, step=0.005 * h / 0.6, flip=flip, cast=(name not in ('weapon', 'rivets')),
                 stroke='#24110f', stroke_width='1.0', stroke_linejoin='round')


def soldier(cv, x, y, z, flip, h=0.62, k=0, flag=False):
    parts, bnd = puppet_soldier(h, stride=k * 1.1, kind='flag' if flag else 'spear')
    glow(cv, (x, y + 0.05, z + h * 0.45), h * 0.55, '#ff9b4f', 0.35)
    st = Stack(cv)
    for name, col in [('weapon', '#2b1b1a'), ('body', '#b04a33' if k % 2 else '#3f6a5e'), ('rivets', '#2a1614')]:
        st.card(parts[name], bnd, (x, y, z), col, step=0.005 * h / 0.42, flip=flip, cast=(name not in ('weapon', 'rivets')),
                 stroke='#24110f', stroke_width='1.0', stroke_linejoin='round')


def beacon_tower(cv, x, y, s=1.2, lit=False, smoke=0.0):
    it, top = beacon(cv, x, y, s, col='#b98457')
    if lit:
        # flames as a small paper cut-out over the hut
        fl = []
        for j, (dx, hh) in enumerate([(-0.05, 0.16), (0.0, 0.24), (0.05, 0.17)]):
            fl.append([(dx * s - 0.035 * s, 0.0), (dx * s + 0.035 * s, 0.0), (dx * s + 0.01 * s, hh * s), (dx * s - 0.006 * s, hh * s * 0.85)])
        cv.card(fl, (top[0], top[1] - 0.05, top[2]), '#ff9c3a', cast=False)
        glow(cv, top + np.array([0, -0.05, 0.12 * s]), 0.7 * s, '#ff9c4a', 0.9, core='#fff1c4')
    if smoke:
        def smoke_fn(U, V):
            d = None
            n = 22
            for k in range(n):
                t = k / (n - 1)
                z = t * smoke
                x = 0.05 * math.sin(t * 7.0) + 0.12 * t * t
                r = 0.06 * s + 0.16 * t
                di = sd_ellipse(U, V, x, z, r, r * 0.9)
                d = di if d is None else smin(d, di, 0.08)
            return cut_edge(d, U, V, 77, amp=0.03, freq=5, fine=0.006, fine_freq=30)
        sdf_card(cv, smoke_fn, (-0.6, -0.2, 0.9, smoke + 0.4), (top[0], top[1] - 0.03, top[2] + 0.15 * s), '#bfa7ae',
                 step=0.02, cast=False, opacity='0.62', band='smoke')
    return top


def storm(cv, x0, y0, scale=1.0):
    """A wall of dust rising behind the breach: billowing layers, lit along their crowns by the low sun."""
    def billow_fn(xa, xb, peak, height, seed, rmin, rmax):
        rng = np.random.default_rng(seed)
        cs = []
        x = xa
        while x < xb:
            r = rng.uniform(rmin, rmax)
            t = (x - (x0 + 0.35)) / max(1e-6, (xb - xa) / 2)
            zt = height * (1 - 0.4 * min(1.0, abs(t)) ** 1.3) * (0.9 + 0.18 * rng.random())
            cs.append((x, zt - r * 0.75, r * 1.15))
            x += r * rng.uniform(0.75, 1.1)

        def fn(U, V):
            d = sd_box(U, V, (xa + xb) / 2, height * 0.3, (xb - xa) / 2 * 0.98, height * 0.3)
            for (cx, cz, r) in cs:
                d = smin(d, sd_ellipse(U, V, cx, cz, r * 1.15, r * 0.82), 0.06)
                # keep the base flat-ish under each billow
                d = smin(d, sd_box(U, V, cx, (cz) / 2, r * 0.9, max(0.01, cz / 2)), 0.08)
            d = np.maximum(d, -V)
            return cut_edge(d, U, V, seed, amp=0.035, freq=3.5, fine=0.008, fine_freq=24)
        return fn
    from geo2d import sd_box
    layers = [
        (0.0, ('#7a4844', '#d08a6c'), 0.8, billow_fn(x0 - 2.4, x0 + 1.8, 0, 3.4 * scale, 31, 0.3, 0.55)),
        (-0.25, ('#64383a', '#b8735e'), 0.88, billow_fn(x0 - 2.0, x0 + 1.5, 0, 2.6 * scale, 32, 0.26, 0.46)),
        (-0.5, ('#4e2c30', '#9a5c4c'), 0.95, billow_fn(x0 - 1.6, x0 + 1.25, 0, 1.85 * scale, 33, 0.22, 0.38)),
        (-0.78, ('#3c2228', '#7b4840'), 1.0, billow_fn(x0 - 1.2, x0 + 1.0, 0, 1.15 * scale, 34, 0.18, 0.3)),
    ]
    cam = cv.cam
    for dy, (c0, c1), op, fn in layers:
        p0 = cam.p(np.array([x0, y0 + dy, 0.0]))
        p1 = cam.p(np.array([x0, y0 + dy, 3.4 * scale]))
        g = cv.lingrad(p0, p1, [(0, c0), (0.55, mix(c0, c1, 0.6)), (1, c1)])
        sdf_card(cv, fn, (x0 - 3.2, -0.2, x0 + 2.6, 4.2 * scale), (0, y0 + dy, 0), g, step=0.018, cast=False,
                 band='storm%.2f' % dy, opacity=str(op))
    # flecks of grit thrown forward
    rng = np.random.default_rng(5)
    fl = []
    for k in range(40):
        x = x0 + rng.uniform(-1.6, 1.4)
        z = rng.uniform(0.2, 2.2) * scale
        r = rng.uniform(0.015, 0.035)
        fl.append([(x - r, z - r * 0.6), (x + r, z - r * 0.3), (x + r * 0.4, z + r * 0.7)])
    cv.card(fl, (0, y0 - 0.9, 0), '#3e2526', cast=False, band='storm-fl')
    glow(cv, (x0, y0 - 0.6, 0.5), 1.8, '#ff8f4a', 0.28)


def arrows(cv, src, targets):
    """Fire arrows: glowing trails along arcs, the last one striking its target."""
    cam = cv.cam
    for k, (tgt, frac, hit) in enumerate(targets):
        tgt = np.array(tgt, float)
        A = arc3(np.array(src, float) + np.array([0.06 * k, 0, 0]), tgt, 1.7 + 0.35 * k, 80)
        n = int(len(A) * frac)
        seg_ = A[max(0, n - 26):n]
        seg_ = seg_[cam.depth(seg_) > 0.3]
        if len(seg_) < 2:
            continue
        P2 = cam.p(seg_)
        g = cv.lingrad(P2[0], P2[-1], [(0, '#ff6a2a', 0.0), (0.65, '#ff9a45', 0.75), (1, '#fff0b8', 1.0)])
        cv.add('fx', '<path d="%s" fill="none" stroke="%s" stroke-width="3.2" stroke-linecap="round" style="mix-blend-mode:screen"/>'
               % (path_d([P2], close=False), g))
        glow(cv, seg_[-1], 0.32, '#ffb057', 0.95, core='#fff6d8')
        if hit:
            burst(cv, seg_[-1])


def burst(cv, hp, s=1.0, cols=('#ffd27a', '#ff8a3d', '#d8452b')):
    cam = cv.cam
    if cam.depth(np.asarray(hp, float)) < 0.3:
        return
    c = cam.p(hp)
    sc = cam.scale(hp) * s
    shards = []
    for j in range(15):
        a = j / 15 * 2 * math.pi + 0.2
        r0, r1 = 0.1 * sc, (0.42 + 0.3 * ((j * 7) % 3) / 2) * sc
        w = 0.055 * sc
        pts = [(c[0] + math.cos(a) * r0 - math.sin(a) * w, c[1] + math.sin(a) * r0 * 0.8 + math.cos(a) * w),
               (c[0] + math.cos(a) * r1, c[1] + math.sin(a) * r1 * 0.8),
               (c[0] + math.cos(a) * r0 + math.sin(a) * w, c[1] + math.sin(a) * r0 * 0.8 - math.cos(a) * w)]
        shards.append('<path d="%s" fill="%s"/>' % (path_d([np.array(pts)]), cols[j % 3]))
    cv.add('fx', ''.join(shards))
    glow(cv, hp, 0.85 * s, '#ffb24f', 0.95, core='#fffbe6')


def banded_card(cv, xs_, zs_, bands, origin, hh, line=None):
    """One card with horizontal colour bands (strata), a single paper layer."""
    tot = sum(t for t, c in bands)
    zc = 0.0
    svg = []
    for t, col in bands:
        z0, z1 = zc / tot * hh * 1.08, (zc + t) / tot * hh * 1.08
        zc += t
        lp = band_loops(xs_, zs_, z0, z1 + 0.004)
        if lp:
            svg.append('<path d="%s" fill="%s"/>' % (cv.d3(cv.card_loops3(lp, origin)), col))
    L3 = cv.card_loops3([list(zip(xs_, zs_))], origin)
    cv.item(float(np.mean(cv.cam.depth(L3[0]))), svg)
    cv.cast(L3)


# ------------------------------------------------------------------ the scene
ROAD = [(-1.9, 10.25), (-1.85, 9.3), (-1.6, 8.3), (-1.25, 7.35), (-0.5, 6.5), (1.2, 6.05), (3.0, 5.85), (3.85, 5.35),
        (3.3, 4.7), (1.6, 4.35), (-1.0, 4.0), (-3.9, 3.6), (-5.35, 2.75), (-4.8, 1.75), (-2.8, 1.15), (0.5, 0.95),
        (3.0, 0.92), (4.6, 0.98), (5.1, 1.12), (5.2, 1.25)]
RIVER = [(-8.5, 6.7), (-6.3, 7.25), (-4.0, 6.8), (-1.3, 7.05), (1.0, 7.45), (3.5, 7.05), (5.8, 7.5), (8.5, 7.1)]
BREACH = -1.9


def build(cam=None, W=W, H=H):
    cam = cam or Cam(CAM['pos'], CAM['target'], CAM['lens'], W, H)
    cv = canvas(cam)
    rng = np.random.default_rng(7)
    SAND = '#c6955f'
    bk = Book(HW, D, BH)
    bk.draw(cv, page=SAND, edge='#dcc6a2', edge_line='#a8906c', cover='#2a2438', gutter=0.0)
    bk.back_page(cv, [(0, '#f6c584'), (0.1, '#eda66c'), (0.24, '#c07a68'), (0.42, '#7d5468'), (0.62, '#4a3a5f'), (1, '#1d1b36')])

    # sun, halo and its glitter
    sunP = bk.bp(2.9, 2.2)
    glow(cv, sunP, 4.6, '#ffd59a', 0.6, layer='backprint')
    c = cam.p(sunP)
    r = 1.0 * cam.scale(sunP)
    cv.add('backprint', '<circle cx="%s" cy="%s" r="%s" fill="#ffeac0"/>' % (fmt(c[0]), fmt(c[1]), fmt(r)))

    # thin cloud streaks crossing the sky page
    def streak(L, th, seed):
        def fn(U, V):
            d = sd_capsule(U, V, -L / 2, 0, L / 2, 0.0, th * 0.25, th)
            d = smin(d, sd_capsule(U, V, -L * 0.1, th * 0.9, L * 0.42, th * 0.7, th * 0.2, th * 0.55), 0.04)
            return cut_edge(d, U, V, seed, amp=0.015, freq=2.5, fine=0.004, fine_freq=18)
        return fn
    for (x, z, L, th, col) in [(-4.6, 6.7, 5.6, 0.09, '#3c3155'), (4.2, 5.9, 6.4, 0.08, '#4b3a5e'), (-1.2, 4.9, 6.2, 0.08, '#6a4762'),
                               (5.0, 3.9, 4.8, 0.07, '#a86668'), (-5.6, 4.1, 3.8, 0.06, '#93606a'), (2.0, 2.75, 3.6, 0.05, '#c97e66'),
                               (3.7, 2.45, 2.2, 0.04, '#d9906a')]:
        sdf_card(cv, streak(L, th, int(abs(x) * 10 + z * 3)), (-L / 2 - 0.3, -0.4, L / 2 + 0.3, 0.4), (x, D - 0.05, z), col,
                 step=0.02, cast=False)

    # ranges: two far massifs, the wall ridge
    xs, zs = crag(-HW, HW, [(-7.0, 3.6, 2.6), (-4.7, 4.5, 2.4), (-2.6, 3.4, 1.8), (0.2, 4.0, 2.6), (5.2, 4.7, 2.6), (7.6, 3.6, 2.0)],
                  seed=1, rough=1.1, rough_f=0.7, floor=1.0)
    cv.card(profile_loop(xs, zs), (0, D - 0.15, 0), '#7a6d84', cast=False)
    xs, zs = crag(-HW, HW, [(-6.4, 2.7, 2.2), (-3.6, 3.1, 2.0), (-0.6, 2.5, 1.9), (1.4, 1.6, 1.0), (4.6, 1.9, 1.4), (6.8, 3.0, 2.2)],
                  seed=2, rough=0.8, rough_f=1.0, floor=0.7)
    cv.card(profile_loop(xs, zs), (0, D - 0.55, 0), '#5f4c66', cast=False)
    xs, zs = crag(-HW, HW, [(-6.6, 1.7, 1.9), (-4.3, 2.1, 1.6), (-0.3, 1.65, 1.5), (1.9, 1.25, 1.4), (4.6, 1.55, 1.7), (7.0, 1.85, 1.6)],
                  seed=3, rough=0.35, rough_f=1.6, floor=0.55)
    notch = np.clip(np.abs(xs - BREACH) / 0.8, 0, 1)
    zs = 0.18 + (zs - 0.18) * (notch ** 1.7)
    yW = D - 1.2
    cv.card(profile_loop(xs, zs), (0, yW, 0), '#41303f', cast=False, band='wall')
    # the Great Wall on the crest, broken at the breach
    wl, seg = [], []
    for x, z in zip(xs, zs):
        if abs(x - BREACH) < 0.66:
            if seg:
                wl.append(seg)
                seg = []
            continue
        seg.append((x, z))
    if seg:
        wl.append(seg)
    wall_loops, crenels, towers = [], [], []
    for sg in wl:
        sg = np.array(sg)
        top = sg[:, 1] + 0.12
        bot = sg[:, 1] - 0.07
        wall_loops.append(list(zip(sg[:, 0], top)) + list(zip(sg[::-1, 0], bot[::-1])))
        for k in range(0, len(sg) - 1, 3):
            x, z = sg[k]
            crenels.append([(x - 0.03, z + 0.12), (x + 0.03, z + 0.12), (x + 0.03, z + 0.19), (x - 0.03, z + 0.19)])
    for tx in (-6.6, -4.3, -0.3, 1.9, 4.6, 7.0):
        z = float(np.interp(tx, xs, zs))
        towers.append([(tx - 0.17, z - 0.06), (tx + 0.17, z - 0.06), (tx + 0.17, z + 0.38), (tx - 0.17, z + 0.38)])
        for k in range(4):
            x = tx - 0.13 + 0.087 * k
            crenels.append([(x - 0.025, z + 0.38), (x + 0.025, z + 0.38), (x + 0.025, z + 0.45), (x - 0.025, z + 0.45)])
    cv.card(wall_loops + crenels + towers, (0, yW - 0.03, 0), '#8e6a5e', cast=False, band='wall')
    rub = []
    for k in range(12):
        x = BREACH + rng.uniform(-0.8, 0.8)
        z = float(np.interp(x, xs, zs)) - 0.02
        s = rng.uniform(0.04, 0.1)
        rub.append([(x - s, z - s * 0.4), (x + s, z - s * 0.5), (x + s * 0.6, z + s * 0.7), (x - s * 0.7, z + s * 0.5)])
    cv.card(rub, (0, yW - 0.05, 0), '#6d4f50', cast=False, band='wall')
    storm(cv, BREACH, yW - 0.25)

    # ---- floor prints
    road = smooth(ROAD, 8)
    river = smooth(RIVER, 10)
    clipx = lambda P: np.column_stack([np.clip(P[:, 0], -HW, HW), np.clip(P[:, 1], 0.0, D)])
    # the long shadow of the ranges over the back of the floor
    g0, g1 = cam.p(np.array([0, D, 0])), cam.p(np.array([0, D - 3.2, 0]))
    cv.add('floorprint', '<path d="%s" fill="%s"/>' % (cv.d3([np.array([(-HW, D - 3.2, 0), (HW, D - 3.2, 0), (HW, D, 0), (-HW, D, 0)])]),
                                                         cv.lingrad(g0, g1, [(0, '#3a2440', 0.55), (1, '#3a2440', 0.0)])))
    # gravel flats
    for k in range(22):
        x, y = rng.uniform(-HW + 0.4, HW - 0.4), rng.uniform(0.4, D - 2.0)
        if dist_to_poly(x, y, road) < 0.7 or dist_to_poly(x, y, river) < 0.8:
            continue
        n = 16
        ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
        rr = rng.uniform(0.3, 0.8) * (1 + 0.25 * np.sin(ang * 3 + k) + 0.1 * np.sin(ang * 7))
        cv.floor([clipx(np.column_stack([x + rr * np.cos(ang) * 1.7, y + rr * np.sin(ang)]))], '#b28150', opacity='0.5')
    # wind ripples: groups of parallel waves
    for g in range(16):
        x, y = rng.uniform(-HW + 0.8, HW - 0.8), rng.uniform(0.5, D - 2.2)
        if dist_to_poly(x, y, road) < 0.9 or dist_to_poly(x, y, river) < 0.9:
            continue
        a = rng.uniform(-0.3, 0.3)
        for j in range(int(rng.integers(4, 8))):
            t = np.linspace(-1, 1, 24)
            L = rng.uniform(0.8, 1.6)
            off = j * 0.12
            P = np.column_stack([x + t * L / 2 * math.cos(a) - off * math.sin(a),
                                 y + t * L / 2 * math.sin(a) + off * math.cos(a) + 0.04 * np.sin(t * 5 + j)])
            if min(dist_to_poly(px, py, road) for px, py in P[::6]) < 0.45:
                continue
            cv.floor_line(clipx(P), '#a97849', 1.0, opacity='0.5')
            cv.floor_line(clipx(P + np.array([0, 0.03])), '#e0b27c', 0.9, opacity='0.55')
    # river: wet banks, water, the sun's glitter
    wr = 0.95 + 0.15 * np.sin(arclen(river) * 0.7)
    cv.floor([clipx(ribbon(river, wr + 0.3, seed=3, wobble=0.12))], '#8e6142')
    cv.floor([clipx(ribbon(river, wr + 0.1, seed=4, wobble=0.1))], '#775041')
    rp0, rp1 = cam.p(np.array([0, 6.8, 0])), cam.p(np.array([0, 8.0, 0]))
    cv.floor([clipx(ribbon(river, wr, seed=5, wobble=0.08))],
             cv.lingrad((0, rp0[1]), (0, rp1[1]), [(0, '#9a7488'), (0.4, '#e09a74'), (1, '#fad49a')]))
    for k in range(120):
        s = rng.uniform(0.0, 1.0)
        p, d = at(river, s)
        off = rng.uniform(-0.4, 0.4)
        nrm = np.array([-d[1], d[0]])
        q = p + nrm * off
        near_sun = abs(q[0] - 2.9) < 1.4
        L = rng.uniform(0.12, 0.45) * (1.4 if near_sun else 1.0)
        if near_sun and rng.random() < 0.85:
            cv.floor_line(np.array([q - d * L / 2, q + d * L / 2]), '#fff2cc', 1.6, opacity='0.95')
        elif rng.random() < 0.5:
            cv.floor_line(np.array([q - d * L / 2, q + d * L / 2]), '#f3c08e', 1.0, opacity='0.7')
        else:
            cv.floor_line(np.array([q - d * L / 2, q + d * L / 2]), '#7b5f80', 1.0, opacity='0.6')
    # road: soft edges, surface, hoof prints
    cv.floor([clipx(ribbon(road, 0.78, seed=6, wobble=0.1))], '#a57748', opacity='0.8')
    cv.floor([clipx(ribbon(road, 0.64, seed=7, wobble=0.07))], '#e3bd86')
    prints = []
    for k in range(150):
        s = rng.uniform(0.0, 1.0)
        p, d = at(road, s)
        nrm = np.array([-d[1], d[0]])
        q = p + nrm * rng.uniform(-0.2, 0.2)
        rr = rng.uniform(0.018, 0.03)
        ang = np.linspace(0, 2 * math.pi, 6, endpoint=False)
        prints.append(clipx(np.column_stack([q[0] + rr * np.cos(ang) * 1.4, q[1] + rr * np.sin(ang)])))
    cv.floor(prints, '#b78b58', opacity='0.75')
    for k in range(70):
        s = rng.uniform(0.0, 1.0)
        p, d = at(road, s)
        nrm = np.array([-d[1], d[0]])
        q = p + nrm * rng.choice([-1, 1]) * rng.uniform(0.38, 0.6)
        rr = rng.uniform(0.03, 0.06)
        ang = np.linspace(0, 2 * math.pi, 7, endpoint=False)
        cv.floor([clipx(np.column_stack([q[0] + rr * np.cos(ang) * 1.3, q[1] + rr * np.sin(ang)]))], '#7f5a40', opacity='0.9')

    # plank bridge where the road crosses the river
    best = min(np.linspace(0, 0.3, 400), key=lambda s: dist_to_poly(*at(road, s)[0], river))
    pb, db = at(road, best)
    fr = Frame(pb[0], pb[1], math.atan2(db[1], db[0]))
    Bb = Builder(cv, fr)
    Bb.box(-0.85, 0.85, -0.34, 0.34, 0.03, 0.1, '#6e4a33', top='#8a6040')
    for sx in (-0.75, -0.25, 0.25, 0.75):
        for sy in (-0.33, 0.33):
            Bb.box(sx - 0.03, sx + 0.03, sy - 0.03, sy + 0.03, 0.0, 0.24, '#563826')
    cv.item(float(cam.depth(fr.w(np.array([0, -0.34, 0.1])))), Bb.emit())
    cv.cast([np.asarray(f[0], float) for f in Bb.faces])
    bridge_s = best

    # ---- mesas and dunes
    bands = [(0.22, '#9c603f'), (0.1, '#b77c50'), (0.2, '#985b3d'), (0.09, '#c18756'), (0.16, '#a56a45'), (0.12, '#c99260')]
    for (x, y, L, hh, sd, off, st) in [(-6.3, 8.95, 2.6, 1.55, 3, 0, 1), (6.3, 9.05, 2.4, 1.2, 4, 2, 1), (-5.0, 8.45, 1.4, 0.55, 5, 1, 0),
                                       (7.3, 8.6, 1.3, 0.6, 6, 3, 0)]:
        xs_, zs_ = mesa_profile(sd, L, hh, steps=st)
        banded_card(cv, xs_, zs_, bands[off:] + bands[:off], (x, y, 0), hh)
    for (x, y, L, hh, sd) in [(-6.3, 0.85, 2.6, 0.32, 1), (6.6, 6.4, 2.2, 0.28, 2), (-3.4, 5.15, 1.8, 0.22, 3), (2.4, 2.35, 1.7, 0.2, 4),
                              (-0.6, 8.6, 1.6, 0.2, 5)]:
        xs_, zs_, cr = dune(sd, L, hh)
        lit = [list(zip(xs_, zs_)) + [(xs_[-1], 0.0), (xs_[0], 0.0)]]
        cv.card(lit, (x, y, 0), '#d7a66c')
        sl = [[(cr, float(np.interp(cr, xs_, zs_)))] + [(xx, zz) for xx, zz in zip(xs_, zs_) if xx > cr] + [(xs_[-1], 0.0), (cr + 0.25 * (xs_[-1] - cr), 0.0)]]
        cv.card(sl, (x, y - 0.01, 0), '#b07c4c', cast=False)

    # ---- trees and shrubs
    for (x, y, h, sd) in [(-4.85, 6.25, 1.5, 3), (-3.6, 8.0, 1.15, 4), (-2.4, 6.4, 0.95, 14), (0.5, 8.35, 1.1, 5), (2.6, 6.55, 1.55, 6),
                          (4.6, 8.3, 1.2, 7), (7.2, 6.75, 1.4, 8), (7.6, 4.6, 1.6, 9), (-7.3, 1.6, 1.5, 10), (-6.4, 2.6, 1.1, 11)]:
        poplar_tree(cv, x, y, h, sd, flip=(sd % 2 == 0))
    for (x, y, sd) in [(-3.0, 4.75, 1), (-6.1, 4.15, 2), (-1.6, 2.3, 3), (1.4, 2.0, 4), (6.9, 0.6, 6), (0.9, 3.3, 7), (-4.4, 0.55, 8),
                       (3.1, 3.2, 9), (-2.2, 8.75, 10), (2.0, 8.85, 11), (5.4, 6.4, 12), (-0.5, 5.3, 13)]:
        tamarisk_clump(cv, x, y, sd, h=0.5, w=0.55)
    for k, (x, y) in enumerate(scatter_points(rng, 50, (-HW + 0.3, 0.3, HW - 0.3, D - 1.6), avoid=[(road, 0.55), (river, 0.75)], min_d=0.35)):
        fn, bnd = tuft(k, h=0.18, w=0.2, n=11)
        sdf_card(cv, fn, bnd, (x, y, 0), '#8c7350' if k % 3 else '#6d4a3a', step=0.007, cast=False)

    # ---- beacons
    beacon_tower(cv, -4.6, 9.05, 1.1, lit=True, smoke=4.2)
    beacon_tower(cv, -2.7, 5.55, 1.0)
    beacon_tower(cv, 6.9, 7.9, 0.95)

    # ---- the fortress
    fortress(cv, 5.75, 2.75)

    # ---- enemies on the road
    foes = [(0.03, 'rider'), (0.07, 'soldier'), (0.105, 'flag'), (0.15, 'rider'), (0.2, 'soldier'), (0.255, 'rider'),
            (0.31, 'soldier'), (0.355, 'flag'), (0.405, 'rider')]
    hits = []
    for k, (s, kind) in enumerate(foes):
        p, d = at(road, s)
        flip = d[0] > 0.0
        z = 0.1 if abs(s - bridge_s) < 0.015 else 0.0
        p = p + np.array([-d[1], d[0]]) * (0.1 if k % 2 else -0.1)
        if kind == 'rider':
            rider(cv, p[0], p[1], z, flip, 0.95, k)
        else:
            soldier(cv, p[0], p[1], z, flip, 0.66, k, flag=(kind == 'flag'))
        hits.append((p[0], p[1], z + 0.45))
    arrows(cv, (5.75 - 0.45, 2.75 - 1.25 - 0.05, 1.45), [(hits[8], 0.6, False), (hits[7], 0.8, False), (hits[8], 1.0, True), (hits[6], 0.42, False)])
    return cv, bk


def render(cv, out, W=W, H=H):
    floor_f = cv.paper_filter('floorpaper', 21, freq=0.006, fx=0.0035, fy=0.011, mottle=0.38, shadow=None, edge=0)
    back_f = cv.paper_filter('backpaper', 22, freq=0.006, mottle=0.32, shadow=None, edge=0)
    svg = cv.render(band_gap=0.7, band_default=dict(freq=0.0075, mottle=0.32, shadow=(-2.0, 4.0, 3.5, 0.42), edge=1.3),
                    floor_filter=floor_f, back_filter=back_f, shadow_blur=3.5, shadow_op=0.3, grain=0.06, vignette=0.5,
                    desk_col='#1d1820')
    open(out + '.svg', 'w').write(svg)


if __name__ == '__main__':
    import os
    os.makedirs('out', exist_ok=True)
    out = sys.argv[1] if len(sys.argv) > 1 else 'out/scene_a'
    cv, bk = build()
    render(cv, out)
    print('ok', len(cv.items), 'items')
