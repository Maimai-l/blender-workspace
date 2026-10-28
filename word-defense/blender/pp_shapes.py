# pp_shapes.py - cut-paper silhouettes for the pop-up spread: trees, firs, bushes, hills, rocks, grass,
# clouds and mountain bands. Each returns (fn, bounds): fn(U, V) is a signed distance (negative inside)
# in the card's own plane, base on V = 0, centred on U = 0.
import math, random
import numpy as np
from pp_lib import (sd_circle, sd_ellipse, sd_capsule, sd_box, sd_poly, smin, umin, cut_edge, catmull)


def _ground(d, V):
    return np.maximum(d, -V)


def tree_round(seed, h=2.6, w=1.8, trunk=0.16, lobes=11, bare=0.0, part='all', grow=0.0):
    """Broadleaf tree: an oval crown with scalloped lobes on a tapering trunk with two branches.
    bare (0..1) thins the crown so branches show through, like the winter trees in the references."""
    rng = random.Random(seed)
    crown_h = h * rng.uniform(0.56, 0.64)
    cz = h - crown_h * 0.5
    rx, rz = w * 0.5, crown_h * 0.5
    lob = []
    for k in range(lobes):
        a = -0.35 * math.pi + 1.7 * math.pi * (k + rng.uniform(-0.25, 0.25)) / lobes
        r = rng.uniform(0.24, 0.36) * min(rx, rz) * 1.6
        lob.append((math.cos(a) * (rx - r * 0.55), cz + math.sin(a) * (rz - r * 0.55), r))
    holes = []
    for k in range(int(bare * 6)):
        holes.append((rng.uniform(-rx, rx) * 0.6, cz + rng.uniform(-rz, rz) * 0.5, rng.uniform(0.08, 0.16) * w))
    lean = rng.uniform(-0.06, 0.06) * w

    def fn(X, Y):
        crown = sd_ellipse(X, Y, lean, cz, rx * 0.72, rz * 0.72)
        for bx, bz, r in lob:
            crown = smin(crown, sd_circle(X, Y, bx + lean, bz, r), 0.035)
        crown = crown - grow
        crown = cut_edge(crown, X, Y, seed, amp=0.028, freq=3.5, fine=0.011, fine_freq=21.0)
        for hx, hz, hr in holes:
            crown = np.maximum(crown, -sd_circle(X, Y, hx + lean, hz, hr))
        tr = sd_capsule(X, Y, 0.0, 0.0, lean * 0.8, cz, trunk * 0.62, trunk * 0.3)
        flare = sd_ellipse(X, Y, 0.0, 0.0, trunk * 1.5, trunk * 0.7)
        b1 = sd_capsule(X, Y, lean * 0.4, cz - crown_h * 0.38, lean - rx * 0.5, cz - crown_h * 0.02, trunk * 0.2, trunk * 0.08)
        b2 = sd_capsule(X, Y, lean * 0.5, cz - crown_h * 0.28, lean + rx * 0.45, cz + crown_h * 0.08, trunk * 0.18, trunk * 0.07)
        b3 = sd_capsule(X, Y, lean * 0.7, cz - crown_h * 0.1, lean - rx * 0.2, cz + crown_h * 0.3, trunk * 0.14, trunk * 0.06)
        if part == 'crown':
            return crown
        wood = cut_edge(umin(tr, flare, b1, b2, b3), X, Y, seed + 3, amp=0.006, freq=7.0, fine=0.003)
        return _ground(np.minimum(crown, wood), Y)

    return fn, (-w * 0.8, 0.0, w * 0.8, h + 0.2)


def tree_fir(seed, h=3.0, w=1.3, tiers=5, teeth=7):
    """Fir: stacked tiers whose lower edges hang in points, like layered paper cut with scissors."""
    rng = random.Random(seed)
    trunk_h = h * 0.1
    polys = []
    span = h - trunk_h
    for k in range(tiers):
        t = k / max(1, tiers - 1)
        zb = trunk_h + span * 0.78 * (k / tiers)
        zt = min(h, zb + span * (0.42 - 0.08 * t))
        ww = w * (1.0 - 0.72 * t) * rng.uniform(0.92, 1.05)
        n = max(3, int(teeth * (1.0 - 0.5 * t)))
        pts = [(rng.uniform(-0.03, 0.03) * w, zt)]
        # left side with small notches
        for s in range(1, 4):
            f = s / 4
            x = -ww / 2 * f; z = zt - (zt - zb) * f
            pts.append((x + 0.04 * ww, z + 0.02 * span))
            pts.append((x - 0.02 * ww, z - 0.01 * span))
        pts.append((-ww / 2, zb))
        for i in range(1, n):
            x = -ww / 2 + ww * i / n
            pts.append((x - ww / n * 0.15, zb + span * rng.uniform(0.035, 0.06)))
            pts.append((x, zb - span * rng.uniform(0.0, 0.018)))
        pts.append((ww / 2, zb))
        for s in range(3, 0, -1):
            f = s / 4
            x = ww / 2 * f; z = zt - (zt - zb) * f
            pts.append((x + 0.02 * ww, z - 0.01 * span))
            pts.append((x - 0.04 * ww, z + 0.02 * span))
        polys.append(pts)

    def fn(X, Y):
        d = None
        for pts in polys:
            p = sd_poly(X, Y, pts)
            d = p if d is None else np.minimum(d, p)
        d = cut_edge(d, X, Y, seed, amp=0.01, freq=6.0, fine=0.005, fine_freq=30.0)
        d = np.minimum(d, sd_box(X, Y, 0.0, trunk_h * 0.7, w * 0.045, trunk_h * 0.7))
        return _ground(d, Y)

    return fn, (-w * 0.6, 0.0, w * 0.6, h + 0.1)


def bush(seed, w=1.6, h=0.7, lumps=None, flat_top=False):
    """Low rounded mounds standing in a row, like the ground rows of a stage set."""
    rng = random.Random(seed)
    n = lumps or max(2, int(round(w / 0.6)))
    blobs = []
    for k in range(n):
        x = -w / 2 + w * (k + 0.5) / n + rng.uniform(-0.07, 0.07) * w / n
        r = min(h, w / n * 0.75) * rng.uniform(0.75, 1.0)
        top = h * rng.uniform(0.7, 1.0)
        blobs.append((x, top - r, r * rng.uniform(1.05, 1.3), r))

    def fn(X, Y):
        d = None
        for x, z, rx, rz in blobs:
            e = sd_ellipse(X, Y, x, z, rx, rz)
            d = e if d is None else smin(d, e, 0.05)
        d = np.minimum(d, sd_box(X, Y, 0.0, 0.0, w / 2, max(0.05, min(z for _, z, _, _ in blobs)), 0.0))
        d = cut_edge(d, X, Y, seed, amp=0.014, freq=5.0, fine=0.006, fine_freq=24.0)
        return _ground(d, Y)

    return fn, (-w / 2 - h, 0.0, w / 2 + h, h * 1.25)


def hill(seed, w=4.0, h=1.6, peaks=3):
    """Wide rolling hill band."""
    rng = random.Random(seed)
    P = [(rng.uniform(-0.15, 0.15) * w, h * rng.uniform(0.9, 1.0), w * rng.uniform(0.28, 0.36))]
    for k in range(peaks - 1):
        side = -1 if k % 2 == 0 else 1
        P.append((side * rng.uniform(0.2, 0.36) * w, h * rng.uniform(0.45, 0.7), w * rng.uniform(0.18, 0.26)))

    def fn(X, Y):
        top = np.zeros_like(X)
        for px, ph, pw in P:
            top = np.maximum(top, ph * np.exp(-((X - px) / pw) ** 2))
        top = top * np.clip((w / 2 - np.abs(X)) / (w * 0.08), 0, 1)
        d = (Y - top) * 0.7
        d = cut_edge(d, X, Y, seed, amp=0.012, freq=4.0, fine=0.005, fine_freq=22.0)
        return _ground(np.maximum(d, np.abs(X) - w / 2), Y)

    return fn, (-w / 2 - 0.05, 0.0, w / 2 + 0.05, h * 1.1)


def rock(seed, w=0.7, h=0.5):
    rng = random.Random(seed)
    n = 7
    pts = []
    for k in range(n):
        a = math.pi * k / (n - 1)
        r = rng.uniform(0.82, 1.0)
        pts.append((math.cos(math.pi - a) * w / 2 * r, math.sin(a) * h * r))
    pts = [(-w / 2, 0.0)] + pts[1:-1] + [(w / 2, 0.0)]

    def fn(X, Y):
        d = sd_poly(X, Y, pts) - 0.03
        d = cut_edge(d, X, Y, seed, amp=0.01, freq=6.0, fine=0.004)
        return _ground(d, Y)

    return fn, (-w / 2 - 0.08, 0.0, w / 2 + 0.08, h + 0.08)


def grass(seed, w=0.5, h=0.35, blades=6):
    rng = random.Random(seed)
    B = []
    for k in range(blades):
        x = -w / 2 + w * (k + 0.5) / blades + rng.uniform(-0.03, 0.03)
        tip = (x + rng.uniform(-0.12, 0.12) * w, h * rng.uniform(0.55, 1.0))
        B.append([(x - w / blades * 0.45, 0.0), (x + w / blades * 0.45, 0.0), tip])

    def fn(X, Y):
        d = None
        for pts in B:
            p = sd_poly(X, Y, pts)
            d = p if d is None else np.minimum(d, p)
        return _ground(d, Y)

    return fn, (-w / 2 - 0.15, 0.0, w / 2 + 0.15, h + 0.05)


def cloud(seed, w=3.0, h=0.55):
    """Long cloud strip with a few puffs on top."""
    rng = random.Random(seed)
    puffs = []
    n = max(2, int(w / 0.9))
    for k in range(n):
        x = -w / 2 + w * (k + 0.6) / (n + 0.2) + rng.uniform(-0.1, 0.1)
        puffs.append((x, h * rng.uniform(0.35, 0.6), h * rng.uniform(0.38, 0.55)))

    def fn(X, Y):
        d = sd_capsule(X, Y, -w / 2 + h * 0.3, h * 0.3, w / 2 - h * 0.3, h * 0.3, h * 0.3)
        for x, z, r in puffs:
            d = smin(d, sd_circle(X, Y, x, z, r), 0.06)
        return cut_edge(d, X, Y, seed, amp=0.012, freq=4.0, fine=0.005, fine_freq=22.0)

    return fn, (-w / 2 - 0.1, -0.05, w / 2 + 0.1, h * 1.3)


def mountains(seed, x0, x1, base, h_lo, h_hi, n_peaks=7, soft=True):
    """Horizon band of peaks from x0 to x1, standing on `base`."""
    rng = random.Random(seed)
    pts = [(x0, base)]
    for k in range(n_peaks * 2 + 1):
        x = x0 + (x1 - x0) * (k + 0.5) / (n_peaks * 2 + 1) + rng.uniform(-0.15, 0.15)
        peak = k % 2 == 1
        z = base + (rng.uniform(h_lo * 0.75, h_hi) if peak else rng.uniform(h_lo * 0.35, h_lo * 0.7))
        pts.append((x, z))
    pts.append((x1, base))
    top = catmull(pts[1:-1], 8) if soft else pts[1:-1]
    poly = [(x0, base - 0.3)] + [(x0, top[0][1])] + top + [(x1, top[-1][1]), (x1, base - 0.3)]

    def fn(X, Y):
        d = sd_poly(X, Y, poly)
        return cut_edge(d, X, Y, seed, amp=0.015, freq=3.0, fine=0.005, fine_freq=18.0)

    return fn, (x0 - 0.05, base - 0.3, x1 + 0.05, base + h_hi + 0.2)


def tuft(seed, w=0.6, h=0.55, blades=9):
    """Clump of long pointed leaves fanning out from the ground."""
    rng = random.Random(seed)
    B = []
    for k in range(blades):
        a = math.radians(-55 + 110 * (k + rng.uniform(0.2, 0.8)) / blades)
        L = h * rng.uniform(0.6, 1.0) / max(0.5, math.cos(a))
        bx = rng.uniform(-0.08, 0.08) * w
        tip = (bx + math.sin(a) * L * 0.9, math.cos(a) * L)
        wd = w * rng.uniform(0.045, 0.07)
        B.append([(bx - wd, 0.0), (bx + wd, 0.0), (tip[0] + wd * 0.3 * math.cos(a), tip[1]), tip])

    def fn(X, Y):
        d = None
        for pts in B:
            p = sd_poly(X, Y, pts)
            d = p if d is None else np.minimum(d, p)
        return _ground(cut_edge(d, X, Y, seed, 0.004, 9.0, 0.002), Y)

    return fn, (-w * 0.9, 0.0, w * 0.9, h + 0.05)


def flowers(seed, w=0.6, h=0.5, n=5):
    """Stems topped with round heads, like a printed cluster of wild flowers."""
    rng = random.Random(seed)
    S = []
    for k in range(n):
        x0 = (k - (n - 1) / 2) * w / n + rng.uniform(-0.03, 0.03)
        top = (x0 + rng.uniform(-0.08, 0.08), h * rng.uniform(0.55, 1.0) - 0.06)
        S.append((x0, top, rng.uniform(0.045, 0.07)))

    def fn(X, Y):
        d = None
        for x0, (tx, tz), r in S:
            st = sd_capsule(X, Y, x0, 0.0, tx, tz, 0.011, 0.008)
            head = sd_circle(X, Y, tx, tz + r * 0.6, r)
            for a in range(5):
                ang = 2 * math.pi * a / 5
                head = np.minimum(head, sd_circle(X, Y, tx + math.cos(ang) * r * 0.9, tz + r * 0.6 + math.sin(ang) * r * 0.9, r * 0.55))
            p = np.minimum(st, head)
            d = p if d is None else np.minimum(d, p)
        lv = sd_ellipse(X, Y, 0.0, 0.0, w * 0.45, h * 0.18)
        return _ground(np.minimum(d, lv), Y)

    return fn, (-w * 0.8, 0.0, w * 0.8, h + 0.12)


def shrub(seed, w=0.9, h=0.75):
    """Small round tree on a short trunk."""
    return tree_round(seed, h=h, w=w, trunk=0.06, lobes=7)
