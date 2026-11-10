"""S13 - high angle down on the clearing (2200 x 1200, room for shake).

Forest floor: moss, litter, roots, fallen logs, stones, shrub tops; giant trunk bases
on the rim of the clearing lean out under the canopy; a band of dense treetops seen
from above frames the clearing (layer `canopy`, nearest). The clearing centre is where
the robot crouches in the shot (painting ~(950, 560); shotfx uses window (0, 0)).
Ferns are their own layer (the wind ring flattens them radially): opaque, two-tone
fronds of four species with soft cast shadows. Light from the bottom of the frame.
"""
import numpy as np
import cv2

from ..color import C, mix, ramp, jitter, aerial, smoothstep
from ..noise import rng_for, fbm
from ..canvas import dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs
from ..atmos import mist, dapple, glow
from ..trees import species, paint_tube, trunk_path
from ..forest import leafy_mass, surface_roots, giant, layered_mass
from ..sky import paint_planes
from ..foliage import render_gbuffer
from ..ground import fern, grass, stone, flowers, FERN_KINDS

W, H, M = 2200, 1200, 40
L3 = (0.15, 0.6, 0.55)          # sun toward the bottom of the frame, raised
SUN2 = (0.24, 0.97)
CENTRE = (950.0, 560.0)         # where the robot crouches (as composited in the shot)
OPEN = (980.0, 560.0, 760.0, 420.0)   # the canopy opening ellipse (cx, cy, rx, ry)
HAZE = C(236, 224, 210)


def build(outdir, quick=False):
    P = Painting('S13', W, H, M, outdir)
    rng = rng_for('S13')

    # ---------------------------------------------------------------- ground
    cv = P.layer('ground', 0.3)
    X, Y = cv.coords()
    hh_, ww_ = cv.shape
    cx_, cy_, rx_, ry_ = OPEN
    kc = np.hypot((X - cx_) / rx_, (Y - cy_) / ry_)
    open_k = np.clip(1.15 - kc, 0, 1)                          # 1 in the open clearing, 0 under the canopy
    f1 = fbm(hh_, ww_, 260, rng, octaves=3)
    f2 = fbm(hh_, ww_, 90, rng, octaves=3)
    f3 = (fbm(hh_, ww_, 34, rng, octaves=3) - 0.5) * 2.2       # ragged patch edges
    # 0 soil/litter, 1 dark moss, 2 bright moss, 3 grass
    dark_m = (f1 + 0.08 * f3 > 0.6 - 0.1 * (1 - open_k))
    bright_m = (~dark_m) & (f1 + 0.08 * f3 > 0.44) & (f2 + 0.1 * f3 > 0.42)
    grass_m = (~dark_m) & (~bright_m) & (f2 + 0.1 * f3 > 0.62 - 0.25 * open_k)
    soil_c = mix(np.broadcast_to(C(80, 68, 58), X.shape + (3,)), C(98, 84, 66), f2[..., None])
    cv.img[..., :3] = soil_c
    cv.img[..., 3] = 1
    pv = fbm(hh_, ww_, 160, rng, octaves=2)[..., None]
    for msk, c0, c1 in ((dark_m, C(38, 60, 54), C(50, 78, 60)), (bright_m, C(64, 96, 66), C(84, 114, 72)),
                        (grass_m, C(88, 108, 70), C(112, 126, 80))):
        a_ = cv2.GaussianBlur(msk.astype(np.float32), (0, 0), 0.8)
        cv.over(mix(np.broadcast_to(c0, X.shape + (3,)), c1, pv), a_)
        # tufts breaking each patch edge outward
        er = cv2.dilate(msk.astype(np.uint8), np.ones((9, 9), np.uint8)) & (~msk).astype(np.uint8)
        sel_e = np.flatnonzero(er.ravel())
        if len(sel_e):
            ke = min(len(sel_e), int(len(sel_e) / 10))
            pk = rng.choice(sel_e, ke, replace=False)
            ey, ex = np.unravel_index(pk, er.shape)
            ec = jitter(mix(np.broadcast_to(c0, (ke, 3)), c1, rng.random(ke)[:, None]), rng, dl=0.03, dc=0.1)
            dabs(cv, ex - cv.m, ey - cv.m, rng.uniform(5, 14, ke), ec, aspect=rng.uniform(0.5, 0.9, ke),
                 edge=0.3, rag=0.6, bristle=0.2, rng=rng)
    # texture per class: moss = stipple, grass = blade stars seen from above, soil = flat strokes + crumbs
    def pts_in(mask, n):
        sel = np.flatnonzero(mask.ravel())
        if len(sel) == 0:
            return np.zeros(0), np.zeros(0)
        pick = rng.choice(sel, min(n, len(sel)), replace=False)
        py, px = np.unravel_index(pick, mask.shape)
        return px.astype(np.float32) - cv.m, py.astype(np.float32) - cv.m
    for msk, cols_, n_, sz in ((dark_m, (C(30, 50, 48), C(44, 72, 58), C(62, 94, 64)), 26000, (5, 12)),
                               (bright_m, (C(56, 88, 62), C(82, 112, 70), C(112, 136, 80)), 22000, (5, 11))):
        px, py = pts_in(msk, n_)
        if len(px):
            t = rng.random(len(px))
            cc = jitter(ramp(list(cols_), t), rng, dl=0.03, dc=0.1, dh=0.05)
            order = np.argsort(t)
            dabs(cv, px[order], py[order], rng.uniform(*sz, len(px))[order], cc[order],
                 aspect=rng.uniform(0.7, 1.0, len(px))[order], edge=0.3, rag=0.5, bristle=0.2, rng=rng)
    px, py = pts_in(grass_m, 5000)
    gtone = rng.random(len(px))
    for i in range(len(px)):
        nb = int(rng.integers(4, 7))
        aa = rng.uniform(0, 2 * np.pi) + np.arange(nb) * 2 * np.pi / nb + rng.normal(0, 0.25, nb)
        L = rng.uniform(6, 13, nb)
        col = jitter(np.broadcast_to(ramp([C(66, 88, 60), C(100, 118, 72), C(136, 142, 88)], np.array([gtone[i]]))[0],
                                     (nb, 3)), rng, dl=0.05, dc=0.12)
        dabs(cv, px[i] + np.cos(aa) * L * 0.5, py[i] + np.sin(aa) * L * 0.5, L, col, aspect=0.22, angle=aa,
             shape='leaf', edge=0.3, rag=0.1, rng=rng)
    soil_m = ~(dark_m | bright_m | grass_m)
    px, py = pts_in(soil_m, 9000)
    if len(px):
        cc = jitter(mix(np.broadcast_to(C(92, 72, 56), (len(px), 3)), C(140, 112, 80), rng.random(len(px))[:, None]),
                    rng, dl=0.04, dc=0.1)
        dabs(cv, px, py, rng.uniform(6, 16, len(px)), cc, aspect=rng.uniform(0.3, 0.7, len(px)), shape='flat',
             edge=0.3, rag=0.5, bristle=0.4, rng=rng)
    # fallen leaves: on soil densely, a few on the moss
    for msk, n_ in ((soil_m, 1800), (dark_m | bright_m, 400)):
        px, py = pts_in(msk, n_)
        if len(px):
            k = len(px)
            lc = jitter(np.array([[(178, 140, 88), (156, 104, 72), (124, 92, 72), (196, 170, 104), (140, 122, 80),
                                   (104, 82, 64)][i] for i in rng.integers(0, 6, k)], np.float32) / 255, rng, dl=0.05,
                        dc=0.12, dh=0.05)
            la = rng.uniform(0, 2 * np.pi, k)
            Ls = rng.uniform(12, 26, k)
            dabs(cv, px, py, Ls, lc, aspect=rng.uniform(0.38, 0.55, k), angle=la, shape='leaf', edge=0.25, rag=0.15,
                 bristle=0.15, split=0.14, rng=rng)
            j = rng.random(k) < 0.35                            # midribs on some
            for i in np.flatnonzero(j)[:400]:
                d_ = np.array([np.cos(la[i]), np.sin(la[i])]) * Ls[i] * 0.42
                stroke(cv, [[px[i] - d_[0], py[i] - d_[1]], [px[i] + d_[0], py[i] + d_[1]]], 1.2, C(84, 58, 44),
                       opacity=0.7, rng=rng, smooth=False)
    # value key: compress the floor's values toward one mid tone so the robot (warm red, bright moss) reads
    # first; detail stays as hue and texture
    cv.lock_tint(C(64, 74, 62), (np.clip(1.3 - kc, 0, 1) * 0.22).astype(np.float32))
    # small ferns in the moss (top-view rosettes)
    px, py = pts_in((dark_m | bright_m) & (kc < 1.3), 26)
    for i in range(len(px)):
        fern(cv, rng, px[i], py[i], rng.uniform(26, 50), sun2=SUN2, light=rng.uniform(0.85, 1.05), spread=2.6,
             droop=0.4, kind=str(rng.choice(['sword', 'lady'])), lean=rng.uniform(-1, 1), body=1.0)
    # roots radiating from the trunk bases
    bases = [(260, 200, 300), (2000, 260, 280), (180, 1060, 260)]
    specs = []
    for (bx, by, w) in bases:
        for k in range(7):
            a = rng.uniform(0, 2 * np.pi)
            L = rng.uniform(250, 650)
            specs.append(((bx + np.cos(a) * w * 0.3, by + np.sin(a) * w * 0.3),
                          (bx + np.cos(a) * L, by + np.sin(a) * L * 0.8), rng.uniform(26, 50)))
    surface_roots(cv, rng, specs, L3)
    # fallen logs
    bark = species('camphor')
    for (p0, p1, w) in [((420, 760), (1080, 980), 90), ((1650, 900), (2150, 700), 70)]:
        p0 = np.asarray(p0, np.float32)
        p1 = np.asarray(p1, np.float32)
        pts = catmull(np.array([p0, (p0 + p1) / 2 + rng.normal(0, 20, 2), p1]), n=30)
        # its shadow on the ground, cast away from the light (up the frame), hard-edged
        sh_off = np.array([-SUN2[0], -SUN2[1]]) * w * 0.45
        stroke(cv, pts + sh_off, np.linspace(w * 1.05, w * 0.85, 30), C(24, 34, 40), opacity=0.55, edge=0.25,
               bristle=0.3, rag=0.4, rng=rng)
        paint_tube(cv, pts, np.linspace(w, w * 0.8, 30), rng, bark, L3, moss=2.5, detail=0.8)
        # the broken/cut end nearest the clearing shows pale wood with growth rings and a dark split
        e = pts[-1] if np.hypot(*(pts[-1] - np.array(CENTRE))) < np.hypot(*(pts[0] - np.array(CENTRE))) else pts[0]
        we = w * 0.8 if e is pts[-1] else w
        dirn = pts[-1] - pts[-2] if e is pts[-1] else pts[0] - pts[1]
        ang_e = float(np.arctan2(dirn[1], dirn[0]))
        dabs(cv, [e[0]], [e[1]], [we * 1.0], C(200, 168, 120), aspect=0.55, angle=ang_e + np.pi / 2, edge=0.25,
             rag=0.5, bristle=0.3, rng=rng)
        for k, f in enumerate((0.75, 0.5, 0.28)):
            dabs(cv, [e[0]], [e[1]], [we * f], [C(170, 132, 92), C(214, 182, 132), C(150, 110, 78)][k],
                 aspect=0.55, angle=ang_e + np.pi / 2, edge=0.35, rag=0.4, bristle=0.4, opacity=0.8, rng=rng)
        stroke(cv, [[e[0] - np.sin(ang_e) * we * 0.3, e[1] + np.cos(ang_e) * we * 0.3],
                    [e[0] + np.sin(ang_e) * we * 0.15, e[1] - np.cos(ang_e) * we * 0.15]], 3.0, C(70, 46, 40),
               opacity=0.8, rng=rng)
    # stones
    for (x, y, r) in [(820, 560, 50), (1960, 560, 44), (640, 1060, 60), (1180, 820, 34), (300, 640, 40)]:
        stone(cv, rng, x, y, r, sun2=SUN2, moss=1.6, flatten=0.8)
    fx = rng.uniform(0, W, 120)
    fy = rng.uniform(0, H, 120)
    flowers(cv, rng, fx, fy, rng.uniform(4, 8, 120))
    # light: the sun is low toward the bottom of the frame, so the bottom canopy casts a hard-edged shadow
    # up into the clearing; the rest of the clearing floor is in warm sun; sun flecks (hard-edged) fall
    # through the leaves into the shadow, leaf shadows dot the lit floor near the shadow edge
    Xg, Yg = cv.coords()
    off = 150.0
    qx, qy = Xg + SUN2[0] * off, Yg + SUN2[1] * off            # walk toward the sun: is the canopy there?
    th_ = np.arctan2(qy - cy_, qx - cx_)
    rag = 1 + 0.12 * np.sin(th_ * 5 + 0.8) + 0.07 * np.sin(th_ * 11 + 2.0) + 0.05 * np.sin(th_ * 29 + 1.1)
    kq = np.hypot((qx - cx_) / rx_, (qy - cy_) / ry_) / rag
    leafy = fbm(cv.shape[0], cv.shape[1], 14, rng, octaves=2) - 0.5
    dsh = (kq - 1.02 + 0.06 * leafy) * min(rx_, ry_)            # >0: in shadow (px from the shadow edge)
    sh = np.clip(dsh / 1.5 + 0.5, 0, 1).astype(np.float32)
    cv.lock_tint(C(30, 42, 60), (sh * 0.5).astype(np.float32))
    cv.lock_tint(C(236, 214, 140), ((1 - sh) * 0.18).astype(np.float32))
    # sun flecks inside the shadow near its edge, leaf shadows in the light near the edge
    band_sh = np.flatnonzero(((dsh > 6) & (dsh < 120)).ravel())
    band_lt = np.flatnonzero(((dsh < -6) & (dsh > -90)).ravel())
    for band, n_, col, op in ((band_sh, 60, C(226, 206, 130), (0.45, 0.7)), (band_lt, 45, C(36, 50, 62), (0.35, 0.55))):
        if len(band) == 0:
            continue
        pick = rng.choice(band, min(n_, len(band)), replace=False)
        py, px = np.unravel_index(pick, sh.shape)
        for i in range(len(px)):
            m_ = int(rng.integers(2, 6))
            r_ = rng.uniform(6, 22)
            dabs(cv, px[i] - cv.m + rng.normal(0, r_ * 0.6, m_), py[i] - cv.m + rng.normal(0, r_ * 0.6, m_),
                 rng.uniform(r_ * 0.6, r_ * 1.4, m_), jitter(np.broadcast_to(col, (m_, 3)), rng, dl=0.03),
                 aspect=rng.uniform(0.6, 0.95, m_), angle=rng.uniform(0, np.pi, m_), edge=0.12, rag=0.45,
                 bristle=0.1, opacity=rng.uniform(*op, m_), mode='lock', rng=rng)
    P.add('ground', 0.3, cv, 'forest floor seen from above: patches of dark moss, bright moss and grass, bare soil '
          'with fallen leaves, small ferns, roots, logs, stones; hard-edged canopy shadow and sun flecks; opaque')

    # ---------------------------------------------------------------- shrubs (tops seen from above)
    cv = P.layer('shrubs', 0.45)
    b = Blobs()
    for (cx, cy, n_) in [(520, 420, 9), (1900, 1000, 10), (980, 1120, 7), (120, 520, 6), (2120, 420, 7),
                         (1500, 1150, 5)]:
        for k in range(n_):
            r = rng.uniform(45, 90)
            b.add(cx + rng.normal(0, 90), cy + rng.normal(0, 70), r, r * 0.85, light=rng.uniform(0.85, 1.1),
                  hue=rng.normal(0, 0.06), val=rng.normal(0, 0.05), rng=rng, lumpy=0.22)
    leafy_mass(cv, rng, b, 0.0, HAZE, L3, SUN2, 12, density=0.9, trans_amt=0.3, rim_amt=0.6, lz=0.6, droop=0.0,
               under=0.0)
    P.add('shrubs', 0.45, cv, 'shrub tops')

    # ---------------------------------------------------------------- ferns (separate: flattened by the wind ring)
    cv = P.layer('ferns', 0.6)
    pts = []
    for i in range(70):
        x = rng.uniform(-40, W + 40)
        y = rng.uniform(-40, H + 40)
        if np.hypot((x - CENTRE[0]) / 520, (y - CENTRE[1]) / 400) < 1.0:
            continue
        pts.append((x, y))
    kinds = []
    for (x, y) in pts:
        kind = str(rng.choice(('sword', 'lady', 'bracken', 'hart'), p=[0.35, 0.25, 0.25, 0.15]))
        s_ = {'sword': rng.uniform(80, 160), 'lady': rng.uniform(70, 140), 'bracken': rng.uniform(110, 190),
              'hart': rng.uniform(50, 100)}[kind]
        nf = None if kind != 'sword' else int(rng.integers(7, 13))
        # soft cast shadow on the ground, away from the light (light comes from the bottom)
        ns = 14
        dabs(cv, x + rng.normal(0, s_ * 0.25, ns) - SUN2[0] * s_ * 0.18, y + rng.normal(0, s_ * 0.2, ns) - SUN2[1] * s_ * 0.18,
             rng.uniform(s_ * 0.5, s_ * 0.9, ns), C(18, 30, 30), aspect=0.75, edge=0.85, rag=0.4, bristle=0.3,
             opacity=0.18, rng=rng)
        fern(cv, rng, x, y, s_, sun2=SUN2, light=rng.uniform(0.85, 1.05), spread=2.5, n_fronds=nf,
             droop=rng.uniform(0.3, 0.6), kind=kind, lean=rng.uniform(-0.6, 0.6), body=1.0)
        kinds.append(kind)
    P.add('ferns', 0.6, cv, 'fern rosettes (centres listed in layers.json: flatten radially from the robot)')

    # ---------------------------------------------------------------- limbs at canopy height over the rim
    # (the trunk bases themselves are hidden under the crowns when seen from this high; a few big
    # mossy limbs reach out from under the canopy over the edge of the clearing, clear of the robot)
    cv = P.layer('trunks', 1.0)
    cx_, cy_, rx_, ry_ = OPEN
    sprays = Blobs()
    for (a_deg, w, L) in [(200, 46, 230), (338, 40, 200), (22, 52, 240), (128, 34, 170)]:
        a = np.radians(a_deg)
        p0 = np.array([cx_ + np.cos(a) * rx_ * 1.12, cy_ + np.sin(a) * ry_ * 1.12])
        d_ = -np.array([np.cos(a), np.sin(a) * ry_ / rx_])
        d_ /= np.hypot(*d_)
        pts = [p0]
        for j in range(4):
            d_ = d_ + rng.normal(0, 0.2, 2)
            d_ /= np.hypot(*d_)
            pts.append(pts[-1] + d_ * L / 4)
        pts = catmull(np.array(pts), n=24)
        bark = species('camphor')
        # its shadow far below on the ground is not visible from here; the limb itself is lit from below-frame
        paint_tube(cv, pts, np.linspace(w, w * 0.35, 24), rng, bark, L3, moss=2.0, ivy=0.0, detail=0.7,
                   flecks=0.0, end_fade=0.1)
        tip = pts[-1]
        layered_mass(sprays, rng, tip[0], tip[1], rng.uniform(40, 60), flat=0.8, droop=0.0)
        mid_ = pts[14]
        layered_mass(sprays, rng, mid_[0] + rng.normal(0, 20), mid_[1] + rng.normal(0, 20), rng.uniform(26, 40),
                     flat=0.8, droop=0.0)
    G = render_gbuffer(cv, sprays, light3=(0.25, 0.8, 0.45), wrap=0.25, under=0.0)
    paint_planes(cv, rng, sprays, (C(20, 32, 44), C(38, 64, 58), C(96, 130, 72), C(184, 190, 104)), G=G, glob=0.0,
                 th=(0.36, 0.6, 0.88), noise_amt=0.08, strokes=0.6, leafy_edge=0.9, leaf_px=12,
                 leaf_cols=[C(20, 32, 44), C(52, 86, 64), C(124, 152, 80)], rim=None, rim_amt=0.0, sun2=SUN2)
    P.add('trunks', 1.0, cv, 'a few big mossy limbs reaching from under the canopy over the rim of the clearing '
          '(trunk bases removed: from above they read as flat bands)')

    # ---------------------------------------------------------------- canopy: treetops seen from above
    cv = P.layer('canopy', 1.0)
    crowns = []
    for i in range(900):
        x = rng.uniform(-260, W + 260)
        y = rng.uniform(-260, H + 260)
        th = np.arctan2(y - cy_, x - cx_)
        rag = 1 + 0.12 * np.sin(th * 5 + 0.8) + 0.07 * np.sin(th * 11 + 2.0)
        k = np.hypot((x - cx_) / rx_, (y - cy_) / ry_) / rag
        if k < 1.08:
            continue
        crowns.append((k, x, y))
        if len(crowns) >= 120:
            break
    crowns.sort(key=lambda t: -t[0])                 # farthest-out (nearest the camera at the edges) first? no:
    crowns.sort(key=lambda t: t[0])                  # rim crowns first, the big outer ones on top
    b = Blobs()
    kinds_c = []
    for k, x, y in crowns:
        R = rng.uniform(90, 170) * (0.8 + 0.25 * min(k - 1.0, 1.5))
        kind = rng.choice(['broad', 'broad', 'conifer', 'flat'], p=[0.35, 0.3, 0.2, 0.15])
        if kind == 'conifer':
            # from above: a dark-centred star of radiating branch tiers
            for j in range(7):
                aa = j / 7 * 2 * np.pi + rng.normal(0, 0.2)
                b.add(x + np.cos(aa) * R * 0.45, y + np.sin(aa) * R * 0.45, R * 0.55, R * 0.22, rot=aa,
                      light=rng.uniform(0.85, 1.05), hue=0.12 + rng.normal(0, 0.03), val=-0.04, rng=rng, lumpy=0.3)
            b.add(x, y, R * 0.35, R * 0.35, light=0.9, hue=0.12, val=-0.02, rng=rng, lumpy=0.3)
        elif kind == 'flat':
            for j in range(int(rng.integers(5, 9))):
                b.add(x + rng.normal(0, R * 0.5), y + rng.normal(0, R * 0.5), R * rng.uniform(0.35, 0.55),
                      R * rng.uniform(0.3, 0.45), rot=rng.uniform(0, np.pi), light=rng.uniform(0.9, 1.1),
                      hue=-0.06 + rng.normal(0, 0.03), val=0.03, rng=rng, lumpy=0.22)
        else:
            # a broadleaf crown from above: many small domed clusters (each with a lit and a shadow side)
            for j in range(int(rng.integers(8, 14))):
                rr = R * rng.uniform(0.22, 0.42)
                rd = R * 0.6 * np.sqrt(rng.random())
                aa = rng.uniform(0, 2 * np.pi)
                b.add(x + np.cos(aa) * rd, y + np.sin(aa) * rd, rr, rr * rng.uniform(0.8, 0.95),
                      rot=rng.uniform(0, np.pi), light=rng.uniform(0.85, 1.1) * (1.05 - 0.25 * rd / R),
                      hue=rng.normal(0, 0.05), val=rng.normal(0, 0.04), rng=rng, lumpy=0.24)
        kinds_c.append(str(kind))
    G = render_gbuffer(cv, b, light3=(0.25, 0.8, 0.45), wrap=0.25, under=0.0)
    paint_planes(cv, rng, b, (C(20, 32, 44), C(38, 64, 58), C(96, 130, 72), C(184, 190, 104)), G=G, glob=0.0,
                 th=(0.36, 0.6, 0.88), noise_amt=0.08, strokes=0.6, leafy_edge=0.9, leaf_px=14,
                 leaf_cols=[C(20, 32, 44), C(52, 86, 64), C(124, 152, 80)], rim=C(232, 220, 146), rim_amt=0.5,
                 sun2=SUN2)
    P.add('canopy', 1.0, cv, 'band of dense treetops seen from above framing the clearing (nearest layer; the '
          'wind ring can cross it)')

    P.save(robot_centre=list(CENTRE), fern_centres=[list(map(float, p)) for p in pts], fern_kinds=kinds,
           light_dir=list(L3))
    return P
