"""imprint.py - depressions pressed into the forest floor (the kneeling robot's imprint).

Shapes are given in a ground-plane frame (gx right, gz toward the camera, px) around an
origin in screen space; the floor is foreshortened by `squash` (screen y = cy + gz*squash).
A height field is built from bowls and capsules (with a raised lip of displaced soil),
lit by the sun (behind the scene: walls facing the camera are dark, walls facing away are
lit), cut into flat painted planes, then dressed: brush strokes following the contours,
torn moss clumps overhanging the rim, broken roots with pale cut ends and hanging rootlets,
crumbs and clods, flowers on the rim and a pool of light.
"""
import numpy as np
import cv2

from .color import C, mix, ramp, jitter, smoothstep, oklab, from_oklab
from .noise import fbm
from .canvas import dabs, stroke, catmull, taper
from .foliage import Blobs
from .ground import flowers

SOIL = (C(34, 24, 32), C(84, 58, 52), C(146, 106, 78), C(212, 170, 118))
MOSS = (C(26, 46, 48), C(52, 84, 58), C(100, 130, 68), C(160, 170, 96))


def _cap_dist(gx, gz, a, b):
    ax, az = a
    bx, bz = b
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz + 1e-6
    t = np.clip(((gx - ax) * dx + (gz - az) * dz) / L2, 0, 1)
    return np.hypot(gx - (ax + t * dx), gz - (az + t * dz)), t


def height_field(gx, gz, shapes, rng, lip=0.25):
    """shapes: dicts with kind 'ellipse' (c, r=(rx, rz), depth) or 'capsule' (a, b, r0, r1, depth,
    dig=extra depth at b). Returns (H <= 0 inside hollows, mask 0..1, depth01)."""
    D = np.zeros_like(gx)
    M = np.zeros_like(gx)
    LIP = np.zeros_like(gx)
    for s in shapes:
        if s['kind'] == 'ellipse':
            cx, cz = s['c']
            rx, rz = s['r']
            d = np.hypot((gx - cx) / rx, (gz - cz) / rz)
            prof = np.clip(1 - d * d, 0, 1) ** 0.55
            edge_d = (d - 1.0) * min(rx, rz)
        else:
            dist, t = _cap_dist(gx, gz, s['a'], s['b'])
            r = s['r0'] + (s['r1'] - s['r0']) * t
            d = dist / r
            prof = np.clip(1 - d * d, 0, 1) ** 0.55 * (1 + s.get('dig', 0.0) * t ** 3)
            edge_d = (d - 1.0) * r
        D = np.maximum(D, s['depth'] * prof)
        M = np.maximum(M, np.clip(1 - d, 0, 1) > 0)
        LIP = np.maximum(LIP, np.exp(-((edge_d - 10) / 12) ** 2) * s['depth'])
    nz = fbm(gx.shape[0], gx.shape[1], 40, rng, octaves=3) - 0.5
    H = -D * 85.0 * (1 + 0.25 * nz) + lip * 18.0 * LIP * (D < 0.02) * (0.6 + 0.8 * (nz + 0.5))
    return H.astype(np.float32), M.astype(np.float32), np.clip(D, 0, 1).astype(np.float32)


def paint_imprint(cv, rng, origin, shapes, squash=0.34, box=None, sun=(0.45, -0.7, 0.55), soil=SOIL, moss=MOSS,
                  light_pool=None, roots=(), flower_n=40, rim_moss=1.0):
    """Paint the imprint onto cv (flat coords). origin = screen point of ground (0, 0).
    box = (x0, y0, x1, y1) screen region to work in. light_pool = (gx, gz, rx, rz) ground ellipse of
    sunlight lying in the hollow. roots = list of ((gx0, gz0), (gx1, gz1), width) broken roots."""
    ox, oy = origin
    x0, y0, x1, y1 = box
    m = cv.m
    X0, Y0, X1, Y1 = int(x0 + m), int(y0 + m), int(x1 + m), int(y1 + m)
    hh, ww = Y1 - Y0, X1 - X0
    xs = np.arange(ww, dtype=np.float32) + x0
    ys = np.arange(hh, dtype=np.float32) + y0
    SX, SY = np.meshgrid(xs, ys)
    gx = SX - ox
    gz = (SY - oy) / squash
    H, Mk, D = height_field(gx, gz, shapes, rng)
    Hs = cv2.GaussianBlur(H, (0, 0), 2.0)
    dHx = cv2.Sobel(Hs, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    dHy = cv2.Sobel(Hs, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    dHz = dHy * squash                                   # d/dgz
    n = np.dstack([-dHx, -dHz, np.ones_like(dHx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    L = np.asarray(sun, np.float32)
    L /= np.linalg.norm(L)
    lam = np.clip(n @ L, 0, 1)
    # cast shadow: march toward the sun over the height field (the far rim shades the hollow)
    hx, hz = L[0], L[1]
    hn = np.hypot(hx, hz) + 1e-6
    tan_el = L[2] / hn
    shadow = np.zeros_like(H)
    Hs2 = Hs
    for t in np.arange(6.0, 160.0, 6.0):
        sxp = np.clip((np.arange(ww)[None, :] + hx / hn * t).astype(int), 0, ww - 1)
        syp = np.clip((np.arange(hh)[:, None] + hz / hn * t * squash).astype(int), 0, hh - 1)
        hit = Hs2[syp, sxp] > Hs2 + t * tan_el
        shadow = np.maximum(shadow, hit.astype(np.float32))
    shadow = cv2.GaussianBlur(shadow, (0, 0), 1.5)
    lam = lam * (1 - 0.85 * shadow)
    ao = 1.0 - 0.55 * D ** 0.8
    v = np.clip(lam * ao + (fbm(hh, ww, 30, rng, octaves=2) - 0.5) * 0.08, 0, 1)
    # where to paint: inside the hollows and on the lip; soft, ragged outer boundary
    area = np.clip(D * 6.0, 0, 1)
    lipk = np.clip((H > 0.5) * (H / 6.0), 0, 1) * (D < 0.02)
    edge_noise = fbm(hh, ww, 9, rng, octaves=2)
    a_in = np.clip(area * 1.4 - 0.15 + (edge_noise - 0.5) * 0.5, 0, 1)
    a_lip = np.clip(lipk * 1.2 - 0.2 + (edge_noise - 0.5) * 0.6, 0, 1)
    # soil planes
    labs = [oklab(c) for c in soil]
    t1 = smoothstep(0.30, 0.36, v)
    t2 = smoothstep(0.55, 0.61, v)
    t3 = smoothstep(0.80, 0.86, v)
    lab = labs[0] + (labs[1] - labs[0]) * t1[..., None]
    lab = lab + (labs[2] - lab) * t2[..., None]
    lab = lab + (labs[3] - lab) * (t3 * 0.8)[..., None]
    rgb = np.clip(from_oklab(lab), 0, 1).astype(np.float32)
    a = np.maximum(a_in, a_lip * 0.85).astype(np.float32)
    cv.over_region(X0, Y0, rgb, a)
    # brush strokes following the contours of the hollow (tangent to the depth isolines)
    gyy, gxx = np.gradient(cv2.GaussianBlur(D, (0, 0), 3.0))
    sel = np.flatnonzero((a.ravel() > 0.5))
    if len(sel):
        k = min(len(sel), int(len(sel) / 90))
        pick = rng.choice(sel, k, replace=False)
        py, px = np.unravel_index(pick, a.shape)
        ang = np.arctan2(gyy[py, px], gxx[py, px]) + np.pi / 2 + rng.normal(0, 0.2, k)
        cols = jitter(rgb[py, px], rng, dl=0.035, dc=0.12, dh=0.05)
        dabs(cv, px + x0, py + y0, rng.uniform(10, 26, k), cols, aspect=rng.uniform(0.2, 0.4, k), angle=ang,
             shape='flat', edge=0.35, rag=0.5, bristle=0.55, opacity=rng.uniform(0.5, 0.9, k), mode='lock', rng=rng)
    # crumbs and clods inside and around
    ncr = 160
    pick = rng.choice(np.flatnonzero((a.ravel() > 0.3)), ncr) if (a > 0.3).any() else []
    if len(pick):
        py, px = np.unravel_index(pick, a.shape)
        px = px + rng.normal(0, 30, ncr)
        py = py + rng.normal(0, 10, ncr)
        cc = jitter(mix(soil[1], soil[3], rng.random(ncr)[:, None] * 0.7), rng, dl=0.04)
        dabs(cv, px + x0, py + y0, rng.uniform(3, 9, ncr), cc, aspect=rng.uniform(0.5, 0.9, ncr),
             edge=0.3, rag=0.5, bristle=0.2, rng=rng)
    # light pooling in the hollow
    if light_pool is not None:
        lgx, lgz, lrx, lrz = light_pool
        cx_, cy_ = ox + lgx, oy + lgz * squash
        npool = 50
        aa = rng.uniform(0, 2 * np.pi, npool)
        rr = np.sqrt(rng.random(npool))
        pxs = cx_ + np.cos(aa) * rr * lrx
        pys = cy_ + np.sin(aa) * rr * lrz * squash
        pc = jitter(mix(C(255, 214, 140), C(255, 240, 196), rng.random(npool)[:, None]), rng, dl=0.03)
        dabs(cv, pxs, pys, rng.uniform(14, 34, npool), pc, aspect=rng.uniform(0.3, 0.55, npool),
             angle=rng.normal(0, 0.15, npool), opacity=rng.uniform(0.25, 0.55, npool), edge=0.6, rag=0.5,
             bristle=0.4, mode='lock', rng=rng)
        # a little glowing mist lying in the light
        dabs(cv, cx_ + rng.normal(0, lrx * 0.5, 14), cy_ + rng.normal(0, lrz * squash * 0.4, 14) - 6,
             rng.uniform(lrx * 0.5, lrx * 1.1, 14), C(255, 236, 196), aspect=0.25, angle=0.0,
             opacity=rng.uniform(0.06, 0.14, 14), edge=0.95, rag=0.3, bristle=0.4, rng=rng)
    # broken roots crossing the walls: dark tube, pale splintered cut end, hanging rootlets
    for (a0, b0, w0) in roots:
        p0 = np.array([ox + a0[0], oy + a0[1] * squash], np.float32)
        p1 = np.array([ox + b0[0], oy + b0[1] * squash], np.float32)
        mid = (p0 + p1) / 2 + rng.normal(0, 6, 2)
        P = catmull(np.array([p0, mid, p1]), n=20)
        stroke(cv, P, np.linspace(w0, w0 * 0.75, 20), C(70, 52, 52), color2=C(150, 112, 88), load2=0.45,
               edge=0.3, bristle=0.4, rag=0.3, rng=rng)
        dabs(cv, [p1[0]], [p1[1]], [w0 * 1.15], C(226, 196, 150), aspect=0.75, edge=0.3, rag=0.6, bristle=0.4,
             rng=rng)
        dabs(cv, [p1[0] + w0 * 0.1], [p1[1]], [w0 * 0.55], C(176, 136, 100), aspect=0.7, edge=0.3, rag=0.5,
             rng=rng)
        for k in range(int(rng.integers(3, 7))):
            q = P[int(rng.integers(8, 20))]
            Lr = rng.uniform(10, 34)
            stroke(cv, [q, q + [rng.normal(0, 4), Lr * 0.5], q + [rng.normal(0, 8), Lr]], taper(3, 1.0, 0.1, 1.6),
                   C(120, 92, 74), opacity=0.8, bristle=0.2, rng=rng)
    # torn moss on the rim: clumps around the outer edge, some overhanging into the hollow,
    # a few peeled flaps showing their brown underside
    if rim_moss > 0:
        outer = (D < 0.005) & (lipk > 0.15)
        # overhanging tufts only on the far (upper) rim: just inside the edge where the wall faces us
        overhang = (D > 0.02) & (D < 0.09) & (dHy < -0.05)
        sel_o = np.flatnonzero(outer.ravel())
        sel_h = np.flatnonzero(overhang.ravel())
        if len(sel_o):
            # moss in irregular groups along the rim, sizes from crumbs to big cushions, with gaps
            ng = int(16 * rim_moss)
            gpick = rng.choice(sel_o, min(ng, len(sel_o)), replace=False)
            if len(sel_h):
                gpick = np.concatenate([gpick, rng.choice(sel_h, min(len(sel_h), int(5 * rim_moss)), replace=False)])
            gy_, gx_ = np.unravel_index(gpick, D.shape)
            pxs, pys, rs = [], [], []
            for i in range(len(gpick)):
                big = rng.uniform(8, 22) * (1.0 if rng.random() < 0.7 else 1.5)
                m_ = int(rng.integers(2, 7))
                pxs.append(gx_[i] + rng.normal(0, big * 1.1, m_))
                pys.append(gy_[i] + rng.normal(0, big * 0.4, m_))
                rs.append(big * rng.uniform(0.3, 1.0, m_) ** 1.4)
            px = np.concatenate(pxs)
            py = np.concatenate(pys)
            rsz = np.concatenate(rs)
            k = len(px)
            from .sky import paint_planes
            b = Blobs()
            for i in range(k):
                r = float(max(rsz[i], 3.0))
                b.add(px[i] + x0, py[i] + y0, r * 1.3, r * 0.75, rot=rng.normal(0, 0.3),
                      light=rng.uniform(0.75, 1.1), hue=rng.normal(0, 0.06), rng=rng, lumpy=0.3)
            paint_planes(cv, rng, b, moss, light3=(sun[0], sun[1], 0.6), th=(0.3, 0.55, 0.82), strokes=0.0,
                         leafy_edge=0.8, leaf_px=6, leaf_cols=[moss[0], moss[1], moss[2]], noise_amt=0.1,
                         rim=C(232, 218, 146), rim_amt=0.3, sun2=(sun[0], sun[1]))
            nfl = int(14 * rim_moss)
            fl = rng.choice(len(px), nfl)
            for i in fl:
                cxp, cyp = px[i] + x0, py[i] + y0
                ang = rng.uniform(-0.6, 0.6)
                Lf = rng.uniform(16, 34)
                stroke(cv, [[cxp, cyp], [cxp + np.cos(ang) * Lf, cyp + np.sin(ang) * Lf * 0.4]],
                       taper(2, 1.0, 0.6, rng.uniform(8, 14)), C(112, 78, 58), color2=moss[2], load2=0.4,
                       edge=0.3, bristle=0.5, rag=0.5, rng=rng)
            if flower_n:
                fsel = rng.choice(sel_o, min(flower_n, len(sel_o)), replace=False)
                fy_, fx_ = np.unravel_index(fsel, D.shape)
                flowers(cv, rng, fx_ + x0 + rng.normal(0, 8, len(fsel)), fy_ + y0 - rng.uniform(2, 8, len(fsel)),
                        rng.uniform(5, 9, len(fsel)))
    return dict(H=H, D=D, box=(X0, Y0, X1, Y1))
