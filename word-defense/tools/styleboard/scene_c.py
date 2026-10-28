# scene_c.py - 月下水乡: a moonlit water town; boats come out of the fog and sail the canal to the water gate.
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
LIGHT = dict(light_dir=(-0.12, -0.45, 0.88), light_col='#d6e2f6', amb=0.86, dif=0.42, amb_col='#a3b3d2',
             shadow_col='#0c1220', edge_col='#dfe8ff', edge_op=0.45)
WALLC = '#e4dfd4'
TILEC = '#2a2f39'
STONE = '#6d7482'
WATER = '#1a2536'
LANT = '#d9573a'
GLOW = '#ffb45a'


def canvas(cam, seed=9):
    cv = Canvas(cam, seed=seed, **LIGHT)
    cv.bounce = 0.05
    cv.bounce_col = '#9fb0d0'
    return cv


def lantern(cv, P, s=1.0, col=LANT, glow_col=GLOW, layer='fx', pool=True):
    cam = cv.cam
    if cam.depth(np.asarray(P, float)) < 0.3:
        return
    if pool:
        g = np.asarray(P, float).copy()
        g[2] = 0.0
        cg = cam.p(g)
        rr = 0.55 * s * cam.scale(g)
        gr = cv.radgrad(cg, (rr, rr * 0.55), [(0, '#ffb45a', 0.35), (1, '#ffb45a', 0.0)])
        cv.add('floorglow', '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s"/>' % (fmt(cg[0]), fmt(cg[1]), fmt(rr), fmt(rr * 0.55), gr))
    c = cam.p(np.asarray(P, float))
    r = 0.055 * s * cam.scale(np.asarray(P, float))
    glow(cv, P, 0.42 * s, glow_col, 0.75, layer=layer)
    cv.add(layer, '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s"/>' % (fmt(c[0]), fmt(c[1]), fmt(r * 0.85), fmt(r), col) +
           '<rect x="%s" y="%s" width="%s" height="%s" fill="#2a1a16"/>' % (fmt(c[0] - r * 0.45), fmt(c[1] - r * 1.15), fmt(r * 0.9), fmt(r * 0.25)) +
           '<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#ffd28a" opacity="0.7"/>' % (fmt(c[0]), fmt(c[1]), fmt(r * 0.35), fmt(r * 0.6)))


def awning_boat(cv, x, y, ang, s=1.0, mirror=False, spirit=True, k=0):
    """乌篷船: a slim hull with a black arched awning; an ink spirit with a pale lantern stands at the stern."""
    fr = MirrorFrame(x, y, ang, 0.0) if mirror else Frame(x, y, ang, 0.0)
    B = Builder(cv, fr)
    L, Wd, Hh = 0.75 * s, 0.17 * s, 0.07 * s
    xs = np.linspace(-L / 2, L / 2, 9)
    half = Wd / 2 * np.clip(1 - (np.abs(xs) / (L / 2)) ** 2.2, 0.08, 1)
    sheer = Hh + 0.035 * s * (np.abs(xs) / (L / 2)) ** 2
    hull = '#3a2c26'
    for sg in (-1, 1):
        for i in range(len(xs) - 1):
            q = [(xs[i], sg * half[i], 0.0), (xs[i + 1], sg * half[i + 1], 0.0), (xs[i + 1], sg * half[i + 1], sheer[i + 1]),
                 (xs[i], sg * half[i], sheer[i])]
            B.face(q, hull, out=(0, sg, 0))
    deck = [(xs[i], -half[i], sheer[i]) for i in range(len(xs))] + [(xs[i], half[i], sheer[i]) for i in range(len(xs))][::-1]
    B.face(deck, '#5a4436', out=(0, 0, 1), bias=0.5)
    # awning: a half-barrel over the middle third
    n = 8
    a0, a1 = -L * 0.2, L * 0.16
    r = Wd * 0.52
    for j in range(n):
        t0, t1 = math.pi * j / n, math.pi * (j + 1) / n
        q = [(a0, -r * math.cos(t0), Hh + r * math.sin(t0)), (a1, -r * math.cos(t0), Hh + r * math.sin(t0)),
             (a1, -r * math.cos(t1), Hh + r * math.sin(t1)), (a0, -r * math.cos(t1), Hh + r * math.sin(t1))]
        mid = (t0 + t1) / 2
        B.face(q, '#1a1c22', out=(0, -math.cos(mid), math.sin(mid)), bias=-0.2)
    for xx in (a0, a1):
        cap = [(xx, -r * math.cos(math.pi * j / n), Hh + r * math.sin(math.pi * j / n)) for j in range(n + 1)]
        B.face(cap, '#121318', out=(1 if xx > 0 else -1, 0, 0), bias=-0.25)
    svg = B.emit()
    if mirror:
        return svg
    it = cv.item(float(cv.cam.depth(fr.w(np.array([0, 0, 0.0])))), svg)
    cv.cast([np.asarray(f[0], float) for f in B.faces])
    if spirit:
        fn, bnd, lp = ink_spirit(0.34 * s, seed=k)
        stern = fr.w(np.array([L * 0.36 * (1 if (ang % (2 * math.pi)) < math.pi else -1) * 0 + L * 0.33, 0.0, Hh]))
        sdf_card(cv, fn, bnd, (stern[0], stern[1], stern[2]), '#14161c', step=0.004, cast=False, flip=math.cos(ang) > 0)
        lx = stern[0] + (-lp[0] if math.cos(ang) > 0 else lp[0])
        P = (lx, stern[1] - 0.01, stern[2] + lp[1])
        glow(cv, P, 0.35 * s, '#8fe0c8', 0.85, core='#e8fff6')
    return it


def plum_branch(cv, x, y, h, seed, flip=False):
    br, blossoms, bnd = plum(seed, h=h)
    sdf_card(cv, br, bnd, (x, y, 0), '#231a1a', step=0.006, flip=flip)
    loops = []
    for (bx, by, r) in blossoms:
        bx = -bx if flip else bx
        a2 = np.linspace(0, 2 * math.pi, 10, endpoint=False)
        rr = r * (1 + 0.25 * np.cos(a2 * 5))
        loops.append(list(zip(bx + rr * np.cos(a2), by + rr * np.sin(a2))))
    cv.card(loops, (x, y - 0.02, 0), '#e8b3bd', cast=False)


def willow_tree(cv, x, y, h, seed, flip=False):
    tr, cb, cf, bnd = willow(seed, h=h, w=0.9)
    st = Stack(cv)
    st.card(cb, bnd, (x, y + 0.04, 0), '#22383c', step=0.007, flip=flip)
    st.card(tr, bnd, (x, y, 0), '#1f1d22', step=0.007, flip=flip)
    st.card(cf, bnd, (x, y - 0.03, 0), '#3b5a55', step=0.007, flip=flip, cast=False)


def firework(cv, P, s=1.0, cols=('#ffd47a', '#ff8a5a', '#fff2cc')):
    cam = cv.cam
    if cam.depth(np.asarray(P, float)) < 0.5:
        return
    c = cam.p(np.asarray(P, float))
    sc = cam.scale(np.asarray(P, float)) * s
    out = []
    rng = np.random.default_rng(3)
    for j in range(40):
        a = j / 40 * 2 * math.pi + rng.uniform(-0.04, 0.04)
        r0 = 0.15 * sc
        r1 = sc * rng.uniform(0.75, 1.0)
        droop = 0.12 * sc * (r1 / sc) ** 2
        x0, y0 = c[0] + math.cos(a) * r0, c[1] + math.sin(a) * r0
        x1, y1 = c[0] + math.cos(a) * r1, c[1] + math.sin(a) * r1 + droop
        col = cols[j % len(cols)]
        out.append('<path d="M%s,%s Q%s,%s %s,%s" stroke="%s" stroke-width="%s" fill="none" stroke-linecap="round" opacity="0.9"/>'
                   % (fmt(x0), fmt(y0), fmt((x0 + x1) / 2), fmt((y0 + y1) / 2 - 0.05 * sc), fmt(x1), fmt(y1), col, fmt(max(0.8, 0.018 * sc))))
        out.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (fmt(x1), fmt(y1), fmt(max(0.9, 0.03 * sc)), col))
    cv.add('fx', '<g style="mix-blend-mode:screen">%s</g>' % ''.join(out))
    glow(cv, P, 1.2 * s, '#ffcf7a', 0.55, core='#fffbe8')


# ------------------------------------------------------------------ the water gate city
def water_city(cv, cx, cy, hx=1.35, hy=1.25, Hw=0.78, gate_x=5.45):
    """A walled city whose front wall has a water gate over the canal, with a gate tower above it."""
    C = Compound(cv)
    from arch import fortress as af
    s_gate = gate_x - cx
    af(cv, C, cx, cy, hx, hy, 0.3, Hw, '#6f7682', layer_lines=(0.075, '#5c6370', 0.008),
       gate=('front', s_gate, 0.56, 0.52, 'arch'), merlon=(0.1, 0.07, 0.11, 0.055))
    svg, faces = tower2(cv, gate_x, cy - hy, Hw, 1.0, 0.46, 0.3, 0.26, roof=TILEC, wall='#d8d2c6', column='#7a2a22',
                        inset=0.1, overhang=0.18, rise1=0.11, rise2=0.34, lift=0.12, bays=5, lit1='#ffc46a', lit2='#ffb04a',
                        emit=False)
    C.add(svg, (gate_x, cy - hy, Hw + 0.5))
    C.faces += [np.asarray(f[0]) for f in faces]
    for sy in (-1, 1):
        for sx in (-1, 1):
            B, ov, R = hall(cv, cx + sx * hx, cy + sy * hy, Hw, 0.36, 0.36, 0.22, 0.2, kind='pyramid', bays=1, wall='#d8d2c6',
                            column='#7a2a22', roof=TILEC, base_h=0.0, overhang=0.1, lift=0.06, emit=False, ornament=False, lit='#ffbf66')
            C.builder(B, ov, key_local=(0, 0, 0.35))
    for (x, y, w_, d_, h_) in [(cx + 0.55, cy + 0.55, 0.9, 0.55, 0.45), (cx + 0.6, cy - 0.45, 0.75, 0.5, 0.42), (cx - 0.55, cy + 0.5, 0.65, 0.5, 0.4)]:
        svg, B = house_hz(cv, x, y, w_, d_, h_, 0.24, rot=0.0, wall=WALLC, tile=TILEC, emit=False,
                          windows=[('front', 0.15, 0.2, 0.3, 0.32, True)])
        C.add(svg, (x, y, 0.4))
        C.faces += [np.asarray(f[0]) for f in B.faces]
    it = C.emit((cx, cy - hy, 0.4))
    for sx in (-1, 1):
        lantern(cv, (gate_x + sx * 0.36, cy - hy - 0.2, 0.62), 1.0)
    return it


# ------------------------------------------------------------------ the scene
CANAL = [(-1.9, 10.4), (-1.85, 9.2), (-1.6, 8.3), (-1.25, 7.35), (-0.5, 6.5), (1.2, 6.05), (3.0, 5.85), (3.85, 5.35),
         (3.3, 4.7), (1.6, 4.35), (-1.0, 4.0), (-3.9, 3.6), (-5.35, 2.75), (-4.8, 1.75), (-2.8, 1.15), (0.5, 0.95),
         (3.0, 0.92), (4.35, 0.98), (5.15, 1.3), (5.4, 1.9), (5.45, 2.6)]
CW = 1.0       # canal width
BANK = 0.28    # paved bank beside the water


def build(cam=None, W=W, H=H):
    cam = cam or Cam(CAM['pos'], CAM['target'], CAM['lens'], W, H)
    cv = canvas(cam)
    rng = np.random.default_rng(13)
    bk = Book(HW, D, BH)
    bk.draw(cv, page='#353d4c', edge='#c9c6bc', edge_line='#8c8a84', cover='#141a26', gutter=0.0)
    bk.back_page(cv, [(0, '#3a4c66'), (0.18, '#2a3a52'), (0.5, '#1b2638'), (1, '#0f1522')])

    # moon, halo, thin clouds
    moonP = bk.bp(3.4, 5.0)
    glow(cv, moonP, 3.0, '#c9d8ff', 0.35, layer='backprint')
    c = cam.p(moonP)
    r = 0.78 * cam.scale(moonP)
    cv.add('backprint', '<circle cx="%s" cy="%s" r="%s" fill="#f1ead6"/>' % (fmt(c[0]), fmt(c[1]), fmt(r)))
    cv.add('backprint', '<circle cx="%s" cy="%s" r="%s" fill="#d8cfb6" opacity="0.35"/>' % (fmt(c[0] + r * 0.25), fmt(c[1] - r * 0.15), fmt(r * 0.3)))

    def streak(L, th, seed):
        def fn(U, V):
            d = sd_capsule(U, V, -L / 2, 0, L / 2, 0.0, th * 0.3, th)
            d = smin(d, sd_capsule(U, V, -L * 0.2, th * 0.8, L * 0.3, th * 0.7, th * 0.25, th * 0.5), 0.05)
            return cut_edge(d, U, V, seed, amp=0.015, freq=2.5, fine=0.004, fine_freq=18)
        return fn
    for (x, z, L, th, col) in [(2.6, 5.2, 4.6, 0.08, '#3c4a63'), (4.8, 4.55, 3.6, 0.06, '#33415a'), (-4.0, 6.0, 5.0, 0.07, '#26324a'),
                               (-1.0, 4.6, 3.2, 0.05, '#2c3a52')]:
        sdf_card(cv, streak(L, th, int(abs(x) * 10 + z * 3)), (-L / 2 - 0.3, -0.4, L / 2 + 0.3, 0.4), (x, D - 0.05, z), col,
                 step=0.02, cast=False)
    # distant hills with a pagoda, a far town line
    xs, zs = ridge(-HW, HW, [(-6.2, 2.0, 2.6), (-3.0, 1.4, 2.2), (0.8, 1.7, 2.4), (4.6, 1.3, 2.0), (7.2, 1.9, 2.2)], shape='soft', floor=0.6)
    cv.card(profile_loop(xs, zs), (0, D - 0.15, 0), '#3b4a66', cast=False)
    pg = pagoda_outline(n=7, base_w=0.3, top_w=0.16, storey=0.21, eave=0.1, spire=0.28, curve=0.04)
    cv.card(pg, (-6.2, D - 0.17, float(np.interp(-6.2, xs, zs)) - 0.05), '#2a3652', cast=False)
    xs, zs = ridge(-HW, HW, [(-5.0, 1.0, 2.0), (-1.5, 0.8, 1.6), (2.4, 1.1, 2.2), (6.0, 0.9, 1.8)], shape='soft', floor=0.45)
    cv.card(profile_loop(xs, zs), (0, D - 0.5, 0), '#252f45', cast=False)
    # far rooftops: a skyline of gables in silhouette
    sky = []
    x = -HW
    while x < HW:
        w_ = rng.uniform(0.5, 0.9)
        h_ = rng.uniform(0.55, 0.8)
        sky += [(x, h_), (x + 0.06, h_), (x + 0.06, h_ + 0.12), (x + w_ * 0.3, h_ + 0.12), (x + w_ * 0.3, h_ + 0.25),
                (x + w_ * 0.7, h_ + 0.25), (x + w_ * 0.7, h_ + 0.12), (x + w_ - 0.06, h_ + 0.12), (x + w_ - 0.06, h_), (x + w_, h_)]
        x += w_
    sky = [(-HW, 0.0)] + sky + [(HW, 0.0)]
    cv.card([sky], (0, D - 0.9, 0), '#1a2233', cast=False)

    # ---- floor: lanes, canal with banks, reflections
    canal = smooth(CANAL, 8)
    clipx = lambda P: np.column_stack([np.clip(P[:, 0], -HW, HW), np.clip(P[:, 1], 0.0, D)])
    # paving: a stone grid over the whole floor, slightly varied
    for k in range(40):
        x, y = rng.uniform(-HW, HW), rng.uniform(0, D)
        rr = rng.uniform(0.3, 0.9)
        a2 = np.linspace(0, 2 * math.pi, 14, endpoint=False)
        cv.floor([clipx(np.column_stack([x + rr * np.cos(a2) * 1.5, y + rr * np.sin(a2)]))], '#4a5466', opacity='0.5')
    cv.floor([clipx(ribbon(canal, CW + 2 * BANK + 0.08))], '#59616f')
    cv.floor([clipx(ribbon(canal, CW + 0.12))], '#2e3746')
    water = clipx(ribbon(canal, CW))
    cv.floor([water], WATER)
    clip = cv.clip3([np.column_stack([water, np.zeros(len(water))])])
    # sky reflected down the middle of the canal, the moon's broken path
    refl = []
    refl.append('<path d="%s" fill="#2c3d58" opacity="0.7"/>' % cv.d3([np.column_stack([clipx(ribbon(canal, CW * 0.45)), np.zeros(len(ribbon(canal, CW * 0.45)))])]))
    for k in range(160):
        s = rng.uniform(0, 1)
        p, d = at(canal, s)
        nrm = np.array([-d[1], d[0]])
        q = p + nrm * rng.uniform(-0.4, 0.4)
        near_moon = abs(q[0] - 3.4) < 0.9
        L = rng.uniform(0.08, 0.3)
        col = '#f1e6c8' if near_moon and rng.random() < 0.85 else '#5b6d8c'
        op = 0.95 if near_moon else 0.5
        seg = np.array([(q[0] - L / 2, q[1], 0.0), (q[0] + L / 2, q[1], 0.0)])
        refl.append('<path d="%s" stroke="%s" stroke-width="%s" opacity="%s" stroke-linecap="round"/>'
                    % (cv.d3([seg], close=False), col, '1.6' if near_moon else '1.0', op))
    cv.add('floorprint', '<g clip-path="%s">%s</g>' % (clip, ''.join(refl)))
    # stone slabs along the banks
    slabs = []
    for side in (-1, 1):
        edge = offset_line(canal, side * (CW / 2 + BANK * 0.55))
        L = arclen(edge)
        for t in np.arange(0.2, L[-1], 0.22):
            i = int(np.searchsorted(L, t))
            if i <= 0 or i >= len(edge):
                continue
            p = edge[i]
            d = edge[i] - edge[i - 1]
            d = d / (np.linalg.norm(d) + 1e-9)
            nrm = np.array([-d[1], d[0]])
            a_ = p + nrm * BANK * 0.5
            b_ = p - nrm * BANK * 0.5
            slabs.append(clipx(np.array([a_, b_])))
    cv.add('floorprint', '<path d="%s" stroke="#4b5260" stroke-width="0.7" fill="none" opacity="0.8"/>'
           % path_d(cv.proj_loops([np.column_stack([s_, np.zeros(2)]) for s_ in slabs], close=False), close=False))

    # ---- houses along both banks (first row reflects in the canal)
    houses = []

    def free(cx_, cy_, rad):
        if not (-HW + 0.45 < cx_ < HW - 0.45 and 0.45 < cy_ < D - 1.15):
            return False
        if cx_ > 4.25 and 1.45 < cy_ < 4.55:
            return False   # the walled city
        if cx_ > 4.0 and cy_ < 1.45:
            return False   # the approach to the water gate
        if dist_to_poly(cx_, cy_, canal) < CW / 2 + BANK + rad * 0.8:
            return False
        for (hx_, hy_, hr) in houses:
            if math.hypot(hx_ - cx_, hy_ - cy_) < (hr + rad) * 0.7:
                return False
        return True
    reflections = []
    for row, off in ((0, CW / 2 + BANK + 0.34), (1, CW / 2 + BANK + 1.05), (2, CW / 2 + BANK + 1.75)):
        for side in (-1, 1):
            Ls = arclen(canal)
            t = 0.3 + (0.35 if side > 0 else 0.0)
            while t < Ls[-1] - 0.3:
                s = t / Ls[-1]
                p, d = at(canal, s)
                nrm = np.array([-d[1], d[0]])
                Wd = rng.uniform(0.7, 1.0)
                Dp = rng.uniform(0.55, 0.68)
                Hh = rng.uniform(0.45, 0.75) if row < 2 else rng.uniform(0.4, 0.6)
                cx_, cy_ = p + side * nrm * off
                rad = math.hypot(Wd, Dp) / 2
                if free(cx_, cy_, rad):
                    ang = math.atan2(d[1], d[0]) + (0 if side > 0 else math.pi)
                    lit = rng.random() < 0.55
                    wins = [('front', Wd * 0.18, Hh * 0.45, Wd * 0.34, Hh * 0.7, lit), ('front', Wd * 0.66, Hh * 0.45, Wd * 0.82, Hh * 0.7, rng.random() < 0.4)]
                    house_hz(cv, cx_, cy_, Wd, Dp, Hh, 0.26, rot=ang, wall=WALLC, tile=TILEC, windows=wins, steps=2 if Wd > 0.85 else 1)
                    houses.append((cx_, cy_, rad))
                    if row == 0:
                        reflections.append((cx_, cy_, Wd, Dp, Hh, ang, wins))
                        if lit:
                            # a lantern by the door
                            fx_ = cx_ - side * nrm[0] * (Dp / 2 + 0.02)
                            fy_ = cy_ - side * nrm[1] * (Dp / 2 + 0.02)
                            lantern(cv, (fx_ + d[0] * 0.18, fy_ + d[1] * 0.18, Hh * 0.82), 1.0)
                t += Wd + rng.uniform(0.02, 0.12)
    # fill the remaining blocks on a loose grid
    for gy in np.arange(0.75, D - 1.3, 0.78):
        for gx in np.arange(-HW + 0.7, HW - 0.6, 0.95):
            x_ = gx + rng.uniform(-0.12, 0.12)
            y_ = gy + rng.uniform(-0.1, 0.1)
            Wd = rng.uniform(0.7, 0.95)
            Dp = rng.uniform(0.55, 0.66)
            rad = math.hypot(Wd, Dp) / 2
            if not free(x_, y_, rad):
                continue
            ang = rng.choice([0.0, math.pi / 2, math.pi, -math.pi / 2])
            Hh = rng.uniform(0.42, 0.62)
            lit = rng.random() < 0.45
            wins = [('front', Wd * 0.2, Hh * 0.45, Wd * 0.36, Hh * 0.7, lit)]
            house_hz(cv, x_, y_, Wd, Dp, Hh, 0.25, rot=ang, wall=WALLC, tile=TILEC, windows=wins, steps=1 if Wd < 0.85 else 2)
            houses.append((x_, y_, rad))

    # reflections of the first row, the bridges and the boats, clipped to the water
    rsvg = []
    for (cx_, cy_, Wd, Dp, Hh, ang, wins) in reflections:
        svg, B = house_hz(cv, cx_, cy_, Wd, Dp, Hh, 0.26, rot=ang, wall=WALLC, tile=TILEC, windows=wins, emit=False, mirror=True,
                          steps=2 if Wd > 0.85 else 1)
        rsvg.append((float(np.linalg.norm(np.array([cx_, cy_, 0]) - cam.pos)), svg))

    # ---- bridges across the canal
    bridges = []
    for s in (0.3, 0.62):
        p, d = at(canal, s)
        ang = math.atan2(d[1], d[0]) + math.pi / 2
        arch_bridge(cv, p[0], p[1], CW + 2 * BANK + 0.5, 0.42, 0.42, rot=ang, col='#8c929c', deck='#a7acb4', rail='#9aa0a8', r=0.36)
        svg, B = arch_bridge(cv, p[0], p[1], CW + 2 * BANK + 0.5, 0.42, 0.42, rot=ang, col='#8c929c', deck='#a7acb4', rail='#9aa0a8',
                             r=0.36, emit=False, mirror=True)
        rsvg.append((float(np.linalg.norm(np.array([p[0], p[1], 0]) - cam.pos)), svg))
        bridges.append(s)
        for sx in (-1, 1):
            q = p + np.array([math.cos(ang), math.sin(ang)]) * sx * 0.32
            lantern(cv, (q[0], q[1], 0.62), 0.9)

    # ---- boats on the canal
    foes = [0.04, 0.09, 0.15, 0.21, 0.27, 0.34, 0.4, 0.46]
    hits = []
    for k, s in enumerate(foes):
        if any(abs(s - b) < 0.025 for b in bridges):
            s += 0.03
        p, d = at(canal, s)
        p = p + np.array([-d[1], d[0]]) * (0.12 if k % 2 else -0.12)
        ang = math.atan2(d[1], d[0])
        awning_boat(cv, p[0], p[1], ang, 1.0, k=k)
        rsvg.append((float(np.linalg.norm(np.array([p[0], p[1], 0]) - cam.pos)), awning_boat(cv, p[0], p[1], ang, 1.0, mirror=True)))
        hits.append(np.array([p[0], p[1], 0.35]))
    rsvg.sort(key=lambda t: -t[0])
    rid = cv.nid('ripple')
    cv.defs.append('<filter id="%s" x="-5%%" y="-5%%" width="110%%" height="110%%">'
                   '<feTurbulence type="fractalNoise" baseFrequency="0.004 0.09" numOctaves="2" seed="4" result="n"/>'
                   '<feDisplacementMap in="SourceGraphic" in2="n" scale="7" xChannelSelector="R" yChannelSelector="G"/></filter>' % rid)
    cv.add('floorprint', '<g clip-path="%s"><g filter="url(#%s)" opacity="0.42">%s</g></g>'
           % (clip, rid, ''.join(sv for _, svl in rsvg for sv in svl)))

    # lanterns on posts along the banks
    for k, s in enumerate(np.linspace(0.12, 0.95, 12)):
        p, d = at(canal, s)
        nrm = np.array([-d[1], d[0]])
        side = 1 if k % 2 else -1
        q = p + nrm * side * (CW / 2 + BANK * 0.6)
        if q[0] > 4.3 and q[1] > 1.4:
            continue
        post = [[(-0.012, 0.0), (0.012, 0.0), (0.012, 0.42), (-0.012, 0.42)]]
        cv.card(post, (q[0], q[1], 0.0), '#2a2422', cast=False)
        lantern(cv, (q[0], q[1] - 0.01, 0.46), 0.95)

    # ---- trees
    for k, (x, y, h, sd) in enumerate([(-6.9, 5.2, 1.3, 1), (-3.3, 8.6, 1.2, 2), (2.4, 7.2, 1.2, 3), (-6.2, 1.2, 1.25, 4), (1.2, 2.55, 1.0, 5)]):
        if free(x, y, 0.3):
            willow_tree(cv, x, y, h, 40 + sd, flip=(sd % 2 == 0))
            houses.append((x, y, 0.3))
    plum_branch(cv, -7.4, 0.5, 1.4, 7)

    # ---- the fog bank where the canal comes in
    def fog_fn(L, th, seed):
        r2 = np.random.default_rng(seed)
        lobes = [(r2.uniform(-L / 2, L / 2), r2.uniform(0.2, 1.0) * th, r2.uniform(0.25, 0.5) * L / 3) for _ in range(8)]

        def fn(U, V):
            d = sd_box(U, V, 0, th * 0.3, L / 2, th * 0.3)
            for (lx, lz, lr) in lobes:
                d = smin(d, sd_ellipse(U, V, lx, lz * 0.6, lr, lz), 0.15)
            d = np.maximum(d, -V)
            return cut_edge(d, U, V, seed, amp=0.03, freq=2.5, fine=0.005, fine_freq=12)
        return fn
    fid = cv.nid('fog')
    cv.defs.append('<filter id="%s" x="-5%%" y="-30%%" width="110%%" height="160%%"><feGaussianBlur stdDeviation="3.0"/></filter>' % fid)
    cv.band_opts['fog'] = {'filter': 'url(#%s)' % fid}
    for (y, L, th, col, op, sd) in [(D - 1.0, 8.0, 0.95, '#6f7f99', '0.72', 1), (D - 1.45, 6.8, 0.7, '#8494ad', '0.78', 2),
                                    (D - 1.95, 5.4, 0.5, '#9eabc0', '0.8', 3), (D - 2.45, 3.8, 0.32, '#b3bfcf', '0.7', 4)]:
        sdf_card(cv, fog_fn(L, th, sd), (-L / 2 - 0.6, -0.1, L / 2 + 0.6, th * 1.6), (-1.9, y, 0), col, step=0.025, cast=False,
                 band='fog', opacity=op)
    glow(cv, (-1.9, D - 1.6, 0.6), 2.2, '#9fc0e8', 0.3)

    # ---- the walled city with its water gate
    water_city(cv, 5.9, 3.0)

    # ---- fireworks over the leading boats, rockets rising from the gate tower
    src = np.array([5.45, 1.75, 1.6])
    for k, (tgt, frac) in enumerate([(hits[7] + np.array([0, 0, 1.3]), 1.0), (hits[6] + np.array([0, 0, 1.0]), 0.7)]):
        A = arc3(src, tgt, 0.8, 50)
        n = int(len(A) * frac)
        seg_ = A[max(0, n - 25):n]
        seg_ = seg_[cam.depth(seg_) > 0.3]
        if len(seg_) < 2:
            continue
        P2 = cam.p(seg_)
        g = cv.lingrad(P2[0], P2[-1], [(0, '#ffcf7a', 0.0), (1, '#fff3cf', 0.95)])
        cv.add('fx', '<path d="%s" fill="none" stroke="%s" stroke-width="2.2" stroke-linecap="round" style="mix-blend-mode:screen"/>'
               % (path_d([P2], close=False), g))
    firework(cv, hits[7] + np.array([0, 0, 1.3]), 0.9)
    return cv, bk


def render(cv, out, W=W, H=H):
    floor_f = cv.paper_filter('floorpaper', 41, freq=0.006, fx=0.004, fy=0.011, mottle=0.3, shadow=None, edge=0)
    back_f = cv.paper_filter('backpaper', 42, freq=0.006, mottle=0.3, shadow=None, edge=0)
    svg = cv.render(band_gap=0.6, band_default=dict(freq=0.0075, mottle=0.24, shadow=(-1.5, 3.5, 3.0, 0.45), edge=1.1),
                    floor_filter=floor_f, back_filter=back_f, shadow_blur=3.0, shadow_op=0.35, grain=0.06, vignette=0.55,
                    desk_col='#0b0e15')
    open(out + '.svg', 'w').write(svg)


if __name__ == '__main__':
    import os
    os.makedirs('out', exist_ok=True)
    out = sys.argv[1] if len(sys.argv) > 1 else 'out/scene_c'
    cv, bk = build()
    render(cv, out)
    print('ok', len(cv.items), 'items')
