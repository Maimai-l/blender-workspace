# figures.py - enemies as paper cards: shadow-puppet riders and soldiers (皮影), ink beasts (墨兽), awning boats.
import math
import numpy as np
from geo2d import sd_circle, sd_ellipse, sd_capsule, sd_box, sd_poly, smin, shape_loops, cut_edge, fbm


def _u(*ds):
    out = ds[0]
    for d in ds[1:]:
        out = np.minimum(out, d)
    return out


def _holes(d, U, V, pts, r):
    for (x, y) in pts:
        d = np.maximum(d, -sd_circle(U, V, x, y, r))
    return d


# ------------------------------------------------------------------ 皮影 rider, facing -u (left); h is the overall height
def puppet_rider(h=0.6, stride=0.0, spear=True):
    s = h / 0.6
    parts = {}

    def horse(U, V):
        U = U / s
        V = V / s
        body = sd_ellipse(U, V, 0.0, 0.25, 0.2, 0.075)
        chest = sd_ellipse(U, V, -0.14, 0.27, 0.08, 0.07)
        neck = sd_capsule(U, V, -0.16, 0.29, -0.25, 0.41, 0.045, 0.03)
        head = sd_capsule(U, V, -0.25, 0.42, -0.33, 0.35, 0.03, 0.018)
        ear = sd_capsule(U, V, -0.235, 0.44, -0.225, 0.48, 0.008, 0.002)
        a = 0.35 * math.sin(stride)
        legs = _u(sd_capsule(U, V, -0.13, 0.22, -0.16 - 0.05 * a, 0.02, 0.022, 0.012),
                  sd_capsule(U, V, -0.09, 0.22, -0.06 + 0.05 * a, 0.02, 0.02, 0.011),
                  sd_capsule(U, V, 0.12, 0.22, 0.10 + 0.05 * a, 0.02, 0.024, 0.012),
                  sd_capsule(U, V, 0.16, 0.22, 0.19 - 0.05 * a, 0.02, 0.022, 0.011))
        tail = sd_capsule(U, V, 0.19, 0.28, 0.27, 0.16, 0.018, 0.008)
        d = smin(smin(body, chest, 0.03), neck, 0.03)
        d = _u(d, head, ear, legs, tail)
        # perforated flank pattern
        d = _holes(d, U, V, [(-0.06 + 0.045 * i, 0.27 + 0.02 * ((i % 2) * 2 - 1)) for i in range(5)], 0.011)
        d = np.maximum(d, -sd_ellipse(U, V, 0.0, 0.215, 0.12, 0.012))
        return d * s

    def saddle(U, V):
        U = U / s
        V = V / s
        d = sd_ellipse(U, V, 0.0, 0.31, 0.075, 0.035)
        cloth = sd_box(U, V, 0.0, 0.255, 0.065, 0.045)
        # scalloped lower edge
        for k in range(5):
            cloth = np.minimum(cloth, sd_circle(U, V, -0.052 + 0.026 * k, 0.21, 0.014))
        d = np.minimum(d, cloth)
        d = _holes(d, U, V, [(-0.03, 0.26), (0.0, 0.26), (0.03, 0.26)], 0.007)
        return d * s

    def rivets(U, V):
        U = U / s
        V = V / s
        pts = [(-0.13, 0.22), (-0.09, 0.22), (0.12, 0.22), (0.16, 0.22), (-0.16, 0.29), (0.0, 0.43), (-0.01, 0.31)]
        d = None
        for (x, y) in pts:
            di = sd_circle(U, V, x, y, 0.009)
            d = di if d is None else np.minimum(d, di)
        return d * s

    def rider(U, V):
        U = U / s
        V = V / s
        robe = sd_poly(U, V, [(-0.06, 0.3), (0.06, 0.3), (0.035, 0.46), (-0.03, 0.46)])
        leg = sd_capsule(U, V, -0.01, 0.31, -0.04, 0.2, 0.02, 0.014)
        head = sd_circle(U, V, -0.005, 0.5, 0.032)
        hat = sd_poly(U, V, [(-0.04, 0.515), (0.035, 0.515), (0.0, 0.575)])
        plume = sd_capsule(U, V, 0.0, 0.57, 0.04, 0.62, 0.006, 0.002)
        arm = sd_capsule(U, V, 0.0, 0.43, -0.08, 0.38, 0.015, 0.012)
        d = _u(robe, leg, head, hat, plume, arm)
        d = _holes(d, U, V, [(0.0, 0.34), (0.0, 0.38), (0.0, 0.42)], 0.008)
        return d * s

    def weapon(U, V):
        U = U / s
        V = V / s
        if not spear:
            return np.full(U.shape, 1.0)
        shaft = sd_capsule(U, V, 0.06, 0.25, -0.2, 0.62, 0.006, 0.006)
        tip = sd_poly(U, V, [(-0.2, 0.62), (-0.23, 0.69), (-0.19, 0.645)])
        flag = sd_poly(U, V, [(-0.185, 0.6), (-0.1, 0.62), (-0.13, 0.57), (-0.08, 0.55), (-0.165, 0.565)])
        return _u(shaft, tip, flag) * s

    parts['horse'] = horse
    parts['saddle'] = saddle
    parts['rivets'] = rivets
    parts['rider'] = rider
    parts['weapon'] = weapon
    bounds = (-0.3 * s, -0.01, 0.32 * s, 0.72 * s)
    return parts, bounds


def puppet_soldier(h=0.42, stride=0.0, kind='spear'):
    s = h / 0.42

    def body(U, V):
        U = U / s
        V = V / s
        a = 0.3 * math.sin(stride)
        robe = sd_poly(U, V, [(-0.06, 0.12), (0.07, 0.12), (0.045, 0.3), (-0.04, 0.3)])
        legs = _u(sd_capsule(U, V, -0.02, 0.13, -0.05 - 0.04 * a, 0.0, 0.016, 0.01),
                  sd_capsule(U, V, 0.02, 0.13, 0.05 + 0.04 * a, 0.0, 0.016, 0.01))
        head = sd_circle(U, V, -0.005, 0.335, 0.03)
        hat = sd_poly(U, V, [(-0.045, 0.35), (0.04, 0.35), (0.0, 0.405)])
        arm = sd_capsule(U, V, 0.0, 0.27, -0.07, 0.22, 0.014, 0.011)
        shield = sd_ellipse(U, V, 0.06, 0.2, 0.03, 0.055)
        d = _u(robe, legs, head, hat, arm, shield)
        d = _holes(d, U, V, [(0.0, 0.17), (0.0, 0.21), (0.0, 0.25)], 0.008)
        # robe hem cut in a band of small triangles
        for k in range(5):
            x = -0.045 + 0.022 * k
            d = np.maximum(d, -sd_poly(U, V, [(x - 0.008, 0.135), (x + 0.008, 0.135), (x, 0.15)]))
        d = np.maximum(d, -sd_ellipse(U, V, 0.06, 0.2, 0.012, 0.03))
        return d * s

    def rivets(U, V):
        U = U / s
        V = V / s
        pts = [(-0.02, 0.13), (0.02, 0.13), (0.0, 0.27), (-0.035, 0.24)]
        d = None
        for (x, y) in pts:
            di = sd_circle(U, V, x, y, 0.008)
            d = di if d is None else np.minimum(d, di)
        return d * s

    def weapon(U, V):
        U = U / s
        V = V / s
        shaft = sd_capsule(U, V, -0.07, 0.05, -0.1, 0.5, 0.005, 0.005)
        if kind == 'flag':
            flag = sd_poly(U, V, [(-0.1, 0.5), (-0.24, 0.48), (-0.2, 0.43), (-0.25, 0.38), (-0.1, 0.4)])
        else:
            flag = sd_poly(U, V, [(-0.1, 0.5), (-0.115, 0.56), (-0.088, 0.505)])
        return _u(shaft, flag) * s

    return {'body': body, 'weapon': weapon, 'rivets': rivets}, (-0.28 * s, -0.01, 0.12 * s, 0.6 * s)


# ------------------------------------------------------------------ 墨兽: an ink beast built from blots, facing -u
def ink_beast(h=0.42, seed=0, stride=0.0):
    s = h / 0.42
    rng = np.random.default_rng(seed)

    def fn(U, V):
        U = U / s
        V = V / s
        a = 0.3 * math.sin(stride)
        body = sd_ellipse(U, V, 0.02, 0.2, 0.17, 0.085)
        head = sd_ellipse(U, V, -0.17, 0.25, 0.07, 0.06)
        jaw = sd_ellipse(U, V, -0.22, 0.22, 0.05, 0.025)
        horn = sd_capsule(U, V, -0.16, 0.3, -0.12, 0.37, 0.012, 0.003)
        legs = _u(sd_capsule(U, V, -0.1, 0.16, -0.13 - 0.04 * a, 0.0, 0.03, 0.02),
                  sd_capsule(U, V, -0.05, 0.16, -0.02 + 0.04 * a, 0.0, 0.028, 0.02),
                  sd_capsule(U, V, 0.1, 0.16, 0.08 + 0.04 * a, 0.0, 0.03, 0.02),
                  sd_capsule(U, V, 0.14, 0.16, 0.17 - 0.04 * a, 0.0, 0.028, 0.02))
        tail = _u(sd_capsule(U, V, 0.18, 0.22, 0.27, 0.3, 0.025, 0.01), sd_circle(U, V, 0.28, 0.31, 0.022))
        mane = _u(*[sd_capsule(U, V, -0.12 + 0.05 * i, 0.27, -0.08 + 0.05 * i + 0.03, 0.34 + 0.02 * (i % 2), 0.02, 0.006) for i in range(4)])
        d = smin(smin(body, head, 0.05), jaw, 0.02)
        d = smin(d, mane, 0.02)
        d = _u(d, horn, legs, tail)
        # drips
        for i in range(3):
            x = -0.06 + 0.07 * i
            d = np.minimum(d, sd_capsule(U, V, x, 0.13, x + 0.005, 0.08 - 0.02 * i, 0.012, 0.004))
        d = cut_edge(d, U, V, seed, amp=0.008, freq=18, fine=0.003, fine_freq=70)
        return d * s

    def eye(U, V):
        U = U / s
        V = V / s
        return sd_ellipse(U, V, -0.185, 0.268, 0.02, 0.013) * s

    def sheen(U, V):
        U = U / s
        V = V / s
        d = sd_capsule(U, V, -0.1, 0.262, 0.1, 0.258, 0.012, 0.006)
        d = np.minimum(d, sd_capsule(U, V, -0.2, 0.29, -0.15, 0.3, 0.008, 0.004))
        return d * s

    return {'body': fn, 'eye': eye, 'sheen': sheen}, (-0.32 * s, -0.01, 0.34 * s, 0.45 * s)


# ------------------------------------------------------------------ 墨灵 (small ink spirit) for boats: a hooded figure
def ink_spirit(h=0.32, seed=0):
    s = h / 0.32

    def fn(U, V):
        U = U / s
        V = V / s
        body = sd_poly(U, V, [(-0.08, 0.0), (0.08, 0.0), (0.05, 0.2), (-0.05, 0.2)])
        hood = sd_ellipse(U, V, 0.0, 0.24, 0.055, 0.07)
        tip = sd_capsule(U, V, 0.0, 0.29, 0.04, 0.34, 0.02, 0.004)
        arm = sd_capsule(U, V, -0.02, 0.16, -0.11, 0.2, 0.016, 0.012)
        pole = sd_capsule(U, V, -0.11, 0.2, -0.13, 0.33, 0.005, 0.005)
        d = smin(smin(body, hood, 0.03), tip, 0.02)
        d = np.minimum(np.minimum(d, arm), pole)
        d = cut_edge(d, U, V, seed, amp=0.006, freq=20, fine=0.002, fine_freq=70)
        return d * s

    return fn, (-0.18 * s, -0.01, 0.12 * s, 0.4 * s), (-0.13 * s, 0.36 * s)  # lantern position


def sdf_loops(fn, bounds, step):
    return shape_loops(fn, bounds, step)
