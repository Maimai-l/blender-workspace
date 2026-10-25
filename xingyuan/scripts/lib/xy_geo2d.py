# Xingyuan - 2D plan geometry helpers (metres, X east, Y north): polygons, clipping, offsets, path frames.
import math

def dedupe(P, eps=1e-6):
    out = []
    for p in P:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append((float(p[0]), float(p[1])))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out

def area(P):
    a = 0.0
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0

def ccw(P):
    P = dedupe(P)
    return P if area(P) > 0 else list(reversed(P))

def centroid(P):
    A = area(P)
    n = len(P)
    if abs(A) < 1e-12:
        return (sum(p[0] for p in P) / n, sum(p[1] for p in P) / n)
    cx = cy = 0.0
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        c = x1 * y2 - x2 * y1
        cx += (x1 + x2) * c; cy += (y1 + y2) * c
    return (cx / (6 * A), cy / (6 * A))

def inside(pt, P):
    x, y = pt
    c = False
    n = len(P)
    for i in range(n):
        x1, y1 = P[i]; x2, y2 = P[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                c = not c
    return c

def dist_seg(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + dx * t, ay + dy * t
    return math.hypot(px - qx, py - qy)

def dist_poly_edge(p, P):
    n = len(P)
    return min(dist_seg(p, P[i], P[(i + 1) % n]) for i in range(n))

def _isect(s, e, ss, se):
    t = ss / (ss - se)
    return (s[0] + (e[0] - s[0]) * t, s[1] + (e[1] - s[1]) * t)

def clip(subject, clipper):
    """Sutherland-Hodgman: `subject` (any simple polygon) clipped by the convex CCW polygon `clipper`."""
    out = list(subject)
    n = len(clipper)
    for i in range(n):
        if not out:
            break
        a = clipper[i]; b = clipper[(i + 1) % n]
        ax, ay = a; dx, dy = b[0] - a[0], b[1] - a[1]
        inp = out; out = []
        s = inp[-1]; ss = dx * (s[1] - ay) - dy * (s[0] - ax)
        for e in inp:
            se = dx * (e[1] - ay) - dy * (e[0] - ax)
            if se >= 0:
                if ss < 0:
                    out.append(_isect(s, e, ss, se))
                out.append(e)
            elif ss >= 0:
                out.append(_isect(s, e, ss, se))
            s, ss = e, se
    return dedupe(out)

def halfplane(a, b, big=500.0):
    """Convex CCW polygon covering the LEFT side of the directed line a->b (a large rectangle)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    p0 = (a[0] - ux * big, a[1] - uy * big)
    p1 = (a[0] + ux * big, a[1] + uy * big)
    return [p0, p1, (p1[0] + nx * big, p1[1] + ny * big), (p0[0] + nx * big, p0[1] + ny * big)]

def _lnorm(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    return (-dy / L, dx / L)

def offset(P, d, max_miter=3.0):
    """Offset a CCW polygon INWARD by d (negative d = outward). Mitered corners, miter length clamped."""
    n = len(P)
    out = []
    for i in range(n):
        p0 = P[i - 1]; p1 = P[i]; p2 = P[(i + 1) % n]
        n1 = _lnorm(p0, p1); n2 = _lnorm(p1, p2)
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        L = math.hypot(mx, my)
        if L < 1e-9:
            mx, my = n1; L = 1.0
        mx, my = mx / L, my / L
        c = mx * n1[0] + my * n1[1]
        k = d / max(c, 1.0 / max_miter)
        out.append((p1[0] + mx * k, p1[1] + my * k))
    return out

def shrink_to(P, c, d):
    """Move every vertex toward point c by distance d (cheap inset for small convex pieces)."""
    out = []
    for p in P:
        vx, vy = p[0] - c[0], p[1] - c[1]
        L = math.hypot(vx, vy)
        k = 0.0 if L < 1e-9 else max(0.0, (L - d) / L)
        out.append((c[0] + vx * k, c[1] + vy * k))
    return out

def arc(c, r, a0, a1, n):
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]

def catmull(pts, step=0.5):
    """Resample a polyline as a centripetal-ish Catmull-Rom spline through its points, ~`step` spacing."""
    P = [(float(x), float(y)) for x, y in pts]
    if len(P) < 3:
        return P
    ext = [(2 * P[0][0] - P[1][0], 2 * P[0][1] - P[1][1])] + P + [(2 * P[-1][0] - P[-2][0], 2 * P[-1][1] - P[-2][1])]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        L = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        n = max(1, int(math.ceil(L / step)))
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in range(2)))
    out.append(P[-1])
    return out

class Path:
    """Arc-length parameterised polyline with smooth left normals: at(u, v) = point at distance u along the path,
    offset v to the LEFT (v < 0 = right)."""
    def __init__(self, pts):
        P = dedupe(pts)
        self.P = P
        n = len(P)
        self.s = [0.0]
        for i in range(n - 1):
            self.s.append(self.s[-1] + math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]))
        self.length = self.s[-1]
        segd = []
        for i in range(n - 1):
            dx, dy = P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]
            L = math.hypot(dx, dy)
            segd.append((dx / L, dy / L))
        self.N = []
        for i in range(n):
            if i == 0:
                t = segd[0]
            elif i == n - 1:
                t = segd[-1]
            else:
                t = (segd[i - 1][0] + segd[i][0], segd[i - 1][1] + segd[i][1])
                L = math.hypot(*t)
                t = (t[0] / L, t[1] / L)
            nrm = (-t[1], t[0])
            # miter so that the offset keeps the width on both adjacent segments
            ref = segd[min(i, n - 2)]
            c = abs(nrm[0] * -ref[1] + nrm[1] * ref[0])
            k = 1.0 / max(c, 0.5)
            self.N.append((nrm[0] * k, nrm[1] * k))
        self.segd = segd

    def _seg(self, u):
        s = self.s
        if u <= 0:
            return 0, 0.0
        if u >= self.length:
            return len(s) - 2, 1.0
        lo, hi = 0, len(s) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if s[mid] <= u:
                lo = mid
            else:
                hi = mid
        L = s[lo + 1] - s[lo]
        return lo, (u - s[lo]) / L if L > 0 else 0.0

    def at(self, u, v=0.0):
        i, t = self._seg(u)
        P, N = self.P, self.N
        if u < 0 or u > self.length:
            # extrapolate along the end tangent
            d = self.segd[0] if u < 0 else self.segd[-1]
            base = P[0] if u < 0 else P[-1]
            du = u if u < 0 else u - self.length
            nx, ny = -d[1], d[0]
            return (base[0] + d[0] * du + nx * v, base[1] + d[1] * du + ny * v)
        x = P[i][0] + (P[i + 1][0] - P[i][0]) * t
        y = P[i][1] + (P[i + 1][1] - P[i][1]) * t
        nx = N[i][0] + (N[i + 1][0] - N[i][0]) * t
        ny = N[i][1] + (N[i + 1][1] - N[i][1]) * t
        return (x + nx * v, y + ny * v)

    def tangent(self, u):
        i, t = self._seg(max(0.0, min(self.length, u)))
        return self.segd[i]

    def outline(self, w_left, w_right=None, step=0.5):
        """Closed CCW outline of the strip between offsets +w_left and -w_right."""
        w_right = w_left if w_right is None else w_right
        n = max(2, int(math.ceil(self.length / step)) + 1)
        us = [self.length * k / (n - 1) for k in range(n)]
        left = [self.at(u, w_left) for u in us]
        right = [self.at(u, -w_right) for u in us]
        return ccw(right + list(reversed(left)))

    def project(self, p):
        """(u, v) of the closest point on the path to p."""
        best = None
        P = self.P
        for i in range(len(P) - 1):
            ax, ay = P[i]; bx, by = P[i + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
            qx, qy = ax + dx * t, ay + dy * t
            d = math.hypot(p[0] - qx, p[1] - qy)
            if best is None or d < best[0]:
                side = dx * (p[1] - ay) - dy * (p[0] - ax)
                best = (d, self.s[i] + t * math.sqrt(L2), d if side >= 0 else -d)
        return best[1], best[2]


class Mask:
    """Boolean plan raster (cell centres at x0 + (i + .5) res, y0 + (j + .5) res; row 0 = south)."""
    def __init__(self, x0, y0, x1, y1, res=0.05):
        import numpy as np
        self.np = np
        self.x0, self.y0, self.res = x0, y0, res
        self.nx = int(round((x1 - x0) / res)); self.ny = int(round((y1 - y0) / res))
        self.m = np.zeros((self.ny, self.nx), dtype=bool)

    def fill_poly(self, P, val=True):
        n = len(P)
        if n < 3:
            return
        ys = [p[1] for p in P]
        res, x0, y0 = self.res, self.x0, self.y0
        j0 = max(0, int(math.floor((min(ys) - y0) / res)))
        j1 = min(self.ny, int(math.ceil((max(ys) - y0) / res)) + 1)
        edges = [(P[k], P[(k + 1) % n]) for k in range(n)]
        for j in range(j0, j1):
            yc = y0 + (j + 0.5) * res
            xi = []
            for (a, b) in edges:
                if (a[1] > yc) != (b[1] > yc):
                    xi.append(a[0] + (yc - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
            xi.sort()
            for k in range(0, len(xi) - 1, 2):
                ia = max(0, int(math.ceil((xi[k] - x0) / res - 0.5)))
                ib = min(self.nx - 1, int(math.floor((xi[k + 1] - x0) / res - 0.5)))
                if ib >= ia:
                    self.m[j, ia:ib + 1] = val

    def fill_circle(self, c, r, val=True):
        self.fill_poly(arc(c, r, 0, 2 * math.pi, 72)[:-1], val)

    def test(self, x, y):
        i = int((x - self.x0) / self.res); j = int((y - self.y0) / self.res)
        if 0 <= i < self.nx and 0 <= j < self.ny:
            return bool(self.m[j, i])
        return False

    def test_many(self, X, Y):
        np = self.np
        i = ((np.asarray(X) - self.x0) / self.res).astype(int); j = ((np.asarray(Y) - self.y0) / self.res).astype(int)
        ok = (i >= 0) & (i < self.nx) & (j >= 0) & (j < self.ny)
        out = np.zeros(len(i), dtype=bool)
        out[ok] = self.m[j[ok], i[ok]]
        return out


def _line_isect(p, d, q, e):
    """Intersection of lines p + t d and q + s e (None if parallel)."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)

def offset_var(P, ds, max_miter=3.0):
    """Inward offset of CCW polygon P with a separate distance per edge (ds[i] for edge P[i] -> P[i+1])."""
    n = len(P)
    lines = []
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        nx, ny = _lnorm(a, b)
        d = (b[0] - a[0], b[1] - a[1])
        lines.append(((a[0] + nx * ds[i], a[1] + ny * ds[i]), d))
    out = []
    for i in range(n):
        (p, d) = lines[i - 1]; (q, e) = lines[i]
        x = _line_isect(p, d, q, e)
        v = P[i]
        if x is None or math.hypot(x[0] - v[0], x[1] - v[1]) > max_miter * max(ds[i - 1], ds[i], 1e-6):
            nx1, ny1 = _lnorm(P[i - 1], v); nx2, ny2 = _lnorm(v, P[(i + 1) % n])
            dd = (ds[i - 1] + ds[i]) / 2
            mx, my = nx1 + nx2, ny1 + ny2
            L = math.hypot(mx, my) or 1.0
            x = (v[0] + mx / L * dd, v[1] + my / L * dd)
        out.append(x)
    return out
