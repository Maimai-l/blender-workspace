"""raster.py - numba kernels that paint cel shapes with analytic anti-aliasing.

All paint kernels work on a premultiplied local buffer `buf` (h, w, 4) whose pixel (0, 0)
sits at canvas pixel (ox, oy).  Coordinates passed in are canvas pixels (pixel centres at
+0.5).  `over_premul` puts such a buffer onto the straight-alpha canvas.
"""
import math

import numpy as np
from numba import njit


@njit(cache=True, fastmath=True)
def _c01(x):
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


@njit(cache=True, fastmath=True)
def over_premul(canvas, buf, ox, oy, op):
    H, W = canvas.shape[0], canvas.shape[1]
    h, w = buf.shape[0], buf.shape[1]
    for j in range(h):
        y = oy + j
        if y < 0 or y >= H:
            continue
        for i in range(w):
            x = ox + i
            if x < 0 or x >= W:
                continue
            sa = buf[j, i, 3] * op
            if sa <= 1e-6:
                continue
            da = canvas[y, x, 3]
            k = da * (1.0 - sa)
            oa = sa + k
            inv = 1.0 / oa
            for c in range(3):
                canvas[y, x, c] = (buf[j, i, c] * op + canvas[y, x, c] * k) * inv
            canvas[y, x, 3] = oa


@njit(cache=True, fastmath=True)
def _wob(c, s, c2a, s2a, c3a, s3a, c5a, s5a):
    cos2 = c * c - s * s
    sin2 = 2.0 * s * c
    cos3 = c * (4.0 * c * c - 3.0)
    sin3 = s * (3.0 - 4.0 * s * s)
    cos5 = cos2 * cos3 - sin2 * sin3
    sin5 = sin2 * cos3 + cos2 * sin3
    return 0.5 * (cos2 * c2a + sin2 * s2a) + 0.33 * (cos3 * c3a + sin3 * s3a) \
        + 0.17 * (cos5 * c5a + sin5 * s5a)


@njit(cache=True, fastmath=True)
def paint_lobes(buf, ox, oy, L, P, lx, ly):
    """Cel lobes, painted back to front.

    L columns: cx cy r ls ss lw wa wp lk al sk tcx tcy tr li
      ls / ss : lit / shadow crescent size (fraction of the tone radius)
      lw      : silhouette colour line (px) on the shadow side.  Drawn as expanded discs
                *under* all lobes, so only the outer silhouette shows a line.
      li      : internal line (px) on each lobe's own shadow-side edge (overlap lines)
      tcx tcy tr : tone disc (tr <= 0: the lobe itself).  Sub-lobes pass their parent's disc
                so the bumps of one billow share one light/shadow shape.
    P rows: shadow, mid, lit, line."""
    h, w = buf.shape[0], buf.shape[1]
    n = L.shape[0]
    for ps in range(2):
        for q in range(n):
            cx = L[q, 0]
            cy = L[q, 1]
            R = L[q, 2]
            if R < 0.35:
                continue
            lw = L[q, 5]
            if ps == 0 and lw <= 0.05:
                continue
            ls = L[q, 3]
            ss = L[q, 4]
            wa = L[q, 6]
            wp = L[q, 7]
            lk = L[q, 8]
            al = L[q, 9]
            sk = L[q, 10]
            li = L[q, 14]
            ext = lw if ps == 0 else 0.0
            Rmax = R * (1.0 + abs(wa)) + 1.0 + ext
            x0 = max(0, int(math.floor(cx - Rmax - ox)))
            x1 = min(w, int(math.ceil(cx + Rmax - ox)) + 1)
            y0 = max(0, int(math.floor(cy - Rmax - oy)))
            y1 = min(h, int(math.ceil(cy + Rmax - oy)) + 1)
            if x0 >= x1 or y0 >= y1:
                continue
            tcx = L[q, 11]
            tcy = L[q, 12]
            tR = L[q, 13]
            own = tR <= 0.0
            if own:
                tcx = cx
                tcy = cy
                tR = R
            lcx = tcx - lx * ls * tR
            lcy = tcy - ly * ls * tR
            scx = tcx + lx * ss * tR
            scy = tcy + ly * ss * tR
            c2a = math.cos(wp)
            s2a = math.sin(wp)
            c3a = math.cos(1.7 * wp + 1.0)
            s3a = math.sin(1.7 * wp + 1.0)
            c5a = math.cos(2.3 * wp + 2.0)
            s5a = math.sin(2.3 * wp + 2.0)
            R2 = Rmax * Rmax
            for y in range(y0, y1):
                py = y + oy + 0.5
                dy = py - cy
                for x in range(x0, x1):
                    px = x + ox + 0.5
                    dx = px - cx
                    d2 = dx * dx + dy * dy
                    if d2 > R2:
                        continue
                    d = math.sqrt(d2) + 1e-6
                    c = dx / d
                    s = dy / d
                    wv = _wob(c, s, c2a, s2a, c3a, s3a, c5a, s5a)
                    Rw = R * (1.0 + wa * wv)
                    if ps == 0:
                        nd = -(c * lx + s * ly)
                        wl = lw * _c01((nd + 0.15) * 1.4)
                        if wl <= 0.05:
                            continue
                        cov = _c01(Rw + wl - d + 0.5) * min(1.0, wl)
                        if cov <= 0.0:
                            continue
                        r_ = P[3, 0]
                        g_ = P[3, 1]
                        b_ = P[3, 2]
                    else:
                        cov = Rw - d + 0.5
                        if cov <= 0.0:
                            continue
                        if cov > 1.0:
                            cov = 1.0
                        r_ = P[1, 0]
                        g_ = P[1, 1]
                        b_ = P[1, 2]
                        tw = tR * (1.0 + wa * wv) if own else tR
                        if ls > 0.0:
                            ex = px - lcx
                            ey = py - lcy
                            t = _c01(math.sqrt(ex * ex + ey * ey) - tw * lk + 0.5)
                            r_ += (P[2, 0] - r_) * t
                            g_ += (P[2, 1] - g_) * t
                            b_ += (P[2, 2] - b_) * t
                        if ss > 0.0:
                            ex = px - scx
                            ey = py - scy
                            t = _c01(math.sqrt(ex * ex + ey * ey) - tw * sk + 0.5)
                            r_ += (P[0, 0] - r_) * t
                            g_ += (P[0, 1] - g_) * t
                            b_ += (P[0, 2] - b_) * t
                        if li > 0.0:
                            nd = -(c * lx + s * ly)
                            wl = li * _c01((nd - 0.05) * 1.6)
                            if wl > 0.05:
                                t = _c01(wl - (Rw - d) + 0.5) * min(1.0, wl)
                                r_ += (P[3, 0] - r_) * t
                                g_ += (P[3, 1] - g_) * t
                                b_ += (P[3, 2] - b_) * t
                    a = cov * al
                    ia = 1.0 - a
                    buf[y, x, 0] = r_ * a + buf[y, x, 0] * ia
                    buf[y, x, 1] = g_ * a + buf[y, x, 1] * ia
                    buf[y, x, 2] = b_ * a + buf[y, x, 2] * ia
                    buf[y, x, 3] = a + buf[y, x, 3] * ia


@njit(cache=True, fastmath=True)
def paint_billows(buf, ox, oy, starts, D, GP, P, lx, ly):
    """Billows: groups of discs painted back to front (group order).

    Inside one group the tones are unions over its discs, so the lit cap and the shadow
    boundary are scalloped by the bumps:
      shape      = U disc(c, r)                         (wobbly)
      not-shadow = U disc(c + l*ts*r, r)                 ts: shadow crescent depth / r
      lit        = U disc(c + l*(1.9 - tl)*r, 0.9 r)     tl: lit cap depth / r (0 = none)
    D columns: cx cy r wa wp ts tl.   GP columns: alpha, inner line width (shadow side).
    P rows: shadow, mid, lit, line."""
    h, w = buf.shape[0], buf.shape[1]
    G = starts.shape[0] - 1
    for g in range(G):
        d0 = starts[g]
        d1 = starts[g + 1]
        if d1 <= d0:
            continue
        al = GP[g, 0]
        li = GP[g, 1]
        xmin = 1e18
        xmax = -1e18
        ymin = 1e18
        ymax = -1e18
        for d in range(d0, d1):
            R = D[d, 2] * (1.0 + abs(D[d, 3])) + 1.0
            if D[d, 0] - R < xmin:
                xmin = D[d, 0] - R
            if D[d, 0] + R > xmax:
                xmax = D[d, 0] + R
            if D[d, 1] - R < ymin:
                ymin = D[d, 1] - R
            if D[d, 1] + R > ymax:
                ymax = D[d, 1] + R
        x0 = max(0, int(math.floor(xmin - ox)))
        x1 = min(w, int(math.ceil(xmax - ox)) + 1)
        y0 = max(0, int(math.floor(ymin - oy)))
        y1 = min(h, int(math.ceil(ymax - oy)) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        nd_ = d1 - d0
        WC = np.empty((nd_, 10), np.float64)
        for d in range(d0, d1):
            wp = D[d, 4]
            q = d - d0
            WC[q, 0] = math.cos(wp)
            WC[q, 1] = math.sin(wp)
            WC[q, 2] = math.cos(1.7 * wp + 1.0)
            WC[q, 3] = math.sin(1.7 * wp + 1.0)
            WC[q, 4] = math.cos(2.3 * wp + 2.0)
            WC[q, 5] = math.sin(2.3 * wp + 2.0)
            R = D[d, 2]
            WC[q, 6] = D[d, 0] + lx * D[d, 5] * R
            WC[q, 7] = D[d, 1] + ly * D[d, 5] * R
            k = (1.9 - D[d, 6]) * R
            WC[q, 8] = D[d, 0] + lx * k
            WC[q, 9] = D[d, 1] + ly * k
        for y in range(y0, y1):
            py = y + oy + 0.5
            for x in range(x0, x1):
                px = x + ox + 0.5
                cs = 0.0
                cn = 0.0
                cl = 0.0
                best = -1e9
                bnd = 0.0
                for d in range(d0, d1):
                    R = D[d, 2]
                    if R < 0.35:
                        continue
                    q = d - d0
                    Rm = R * (1.0 + abs(D[d, 3])) + 1.0
                    Rm2 = Rm * Rm
                    dx = px - D[d, 0]
                    dy = py - D[d, 1]
                    d2 = dx * dx + dy * dy
                    nx = px - WC[q, 6]
                    ny = py - WC[q, 7]
                    n2 = nx * nx + ny * ny
                    tl = D[d, 6]
                    in_s = d2 <= Rm2
                    in_n = n2 <= Rm2
                    in_l = False
                    l2 = 0.0
                    if tl > 0.0:
                        mx = px - WC[q, 8]
                        my = py - WC[q, 9]
                        l2 = mx * mx + my * my
                        in_l = l2 <= 0.81 * Rm2
                    if not (in_s or in_n or in_l):
                        continue
                    dd = math.sqrt(d2) + 1e-6
                    c = dx / dd
                    s = dy / dd
                    wv = _wob(c, s, WC[q, 0], WC[q, 1], WC[q, 2], WC[q, 3], WC[q, 4], WC[q, 5])
                    Rw = R * (1.0 + D[d, 3] * wv)
                    if in_s:
                        v = _c01(Rw - dd + 0.5)
                        if v > cs:
                            cs = v
                        if Rw - dd > best:
                            best = Rw - dd
                            bnd = -(c * lx + s * ly)
                    if in_n:
                        v = _c01(Rw - math.sqrt(n2) + 0.5)
                        if v > cn:
                            cn = v
                    if in_l:
                        v = _c01(0.9 * Rw - math.sqrt(l2) + 0.5)
                        if v > cl:
                            cl = v
                if cs <= 0.0:
                    continue
                r_ = P[0, 0] + (P[1, 0] - P[0, 0]) * cn
                g_ = P[0, 1] + (P[1, 1] - P[0, 1]) * cn
                b_ = P[0, 2] + (P[1, 2] - P[0, 2]) * cn
                r_ += (P[2, 0] - r_) * cl
                g_ += (P[2, 1] - g_) * cl
                b_ += (P[2, 2] - b_) * cl
                if li > 0.0:
                    # line inside the group's own silhouette, on its shadow side
                    wl = li * _c01((bnd - 0.05) * 1.6)
                    if wl > 0.05:
                        v = _c01(wl - best + 0.5) * min(1.0, wl)
                        r_ += (P[3, 0] - r_) * v
                        g_ += (P[3, 1] - g_) * v
                        b_ += (P[3, 2] - b_) * v
                a = cs * al
                ia = 1.0 - a
                buf[y, x, 0] = r_ * a + buf[y, x, 0] * ia
                buf[y, x, 1] = g_ * a + buf[y, x, 1] * ia
                buf[y, x, 2] = b_ * a + buf[y, x, 2] * ia
                buf[y, x, 3] = a + buf[y, x, 3] * ia


@njit(cache=True, fastmath=True)
def paint_disc_lines(buf, ox, oy, D, LW, col, lx, ly):
    """Silhouette colour line: discs expanded by LW on the side away from the light, in the
    line colour.  Paint this *before* the fills so only the outer silhouette shows it.
    D columns: cx cy r wa wp."""
    h, w = buf.shape[0], buf.shape[1]
    for q in range(D.shape[0]):
        cx = D[q, 0]
        cy = D[q, 1]
        R = D[q, 2]
        lw = LW[q]
        if R < 0.35 or lw <= 0.05:
            continue
        wa = D[q, 3]
        wp = D[q, 4]
        Rmax = R * (1.0 + abs(wa)) + 1.0 + lw
        x0 = max(0, int(math.floor(cx - Rmax - ox)))
        x1 = min(w, int(math.ceil(cx + Rmax - ox)) + 1)
        y0 = max(0, int(math.floor(cy - Rmax - oy)))
        y1 = min(h, int(math.ceil(cy + Rmax - oy)) + 1)
        c2a = math.cos(wp)
        s2a = math.sin(wp)
        c3a = math.cos(1.7 * wp + 1.0)
        s3a = math.sin(1.7 * wp + 1.0)
        c5a = math.cos(2.3 * wp + 2.0)
        s5a = math.sin(2.3 * wp + 2.0)
        for y in range(y0, y1):
            py = y + oy + 0.5
            dy = py - cy
            for x in range(x0, x1):
                px = x + ox + 0.5
                dx = px - cx
                dd = math.sqrt(dx * dx + dy * dy) + 1e-6
                if dd > Rmax:
                    continue
                c = dx / dd
                s = dy / dd
                nd = -(c * lx + s * ly)
                wl = lw * _c01((nd + 0.15) * 1.4)
                if wl <= 0.05:
                    continue
                Rw = R * (1.0 + wa * _wob(c, s, c2a, s2a, c3a, s3a, c5a, s5a))
                a = _c01(Rw + wl - dd + 0.5) * min(1.0, wl)
                if a <= 0.0:
                    continue
                ia = 1.0 - a
                buf[y, x, 0] = col[0] * a + buf[y, x, 0] * ia
                buf[y, x, 1] = col[1] * a + buf[y, x, 1] * ia
                buf[y, x, 2] = col[2] * a + buf[y, x, 2] * ia
                buf[y, x, 3] = a + buf[y, x, 3] * ia


@njit(cache=True, fastmath=True)
def cut_discs(buf, ox, oy, Hs):
    """Erase wobbly discs.  Hs columns: cx cy r wa wp."""
    h, w = buf.shape[0], buf.shape[1]
    for q in range(Hs.shape[0]):
        cx = Hs[q, 0]
        cy = Hs[q, 1]
        R = Hs[q, 2]
        if R < 0.35:
            continue
        wa = Hs[q, 3]
        wp = Hs[q, 4]
        Rmax = R * (1.0 + abs(wa)) + 1.0
        x0 = max(0, int(math.floor(cx - Rmax - ox)))
        x1 = min(w, int(math.ceil(cx + Rmax - ox)) + 1)
        y0 = max(0, int(math.floor(cy - Rmax - oy)))
        y1 = min(h, int(math.ceil(cy + Rmax - oy)) + 1)
        c2a = math.cos(wp)
        s2a = math.sin(wp)
        c3a = math.cos(1.7 * wp + 1.0)
        s3a = math.sin(1.7 * wp + 1.0)
        for y in range(y0, y1):
            dy = y + oy + 0.5 - cy
            for x in range(x0, x1):
                dx = x + ox + 0.5 - cx
                d = math.sqrt(dx * dx + dy * dy) + 1e-6
                c = dx / d
                s = dy / d
                cos2 = c * c - s * s
                sin2 = 2.0 * s * c
                cos3 = c * (4.0 * c * c - 3.0)
                sin3 = s * (3.0 - 4.0 * s * s)
                wv = 0.6 * (cos2 * c2a + sin2 * s2a) + 0.4 * (cos3 * c3a + sin3 * s3a)
                cov = _c01(R * (1.0 + wa * wv) - d + 0.5)
                if cov > 0.0:
                    k = 1.0 - cov
                    buf[y, x, 0] *= k
                    buf[y, x, 1] *= k
                    buf[y, x, 2] *= k
                    buf[y, x, 3] *= k


@njit(cache=True, fastmath=True)
def _sort_small(a, n):
    for i in range(1, n):
        v = a[i]
        j = i - 1
        while j >= 0 and a[j] > v:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = v


@njit(cache=True, fastmath=True)
def paint_polys(buf, ox, oy, V, starts, fill, shade, ink, par):
    """Cel polygons, painted in order.  par columns: ink_w, tx, ty, tr, alpha.

    Fill colour; points outside the terminator disc (tx, ty, tr) get the shade colour;
    an ink line of width ink_w is centred on the outline."""
    h, w = buf.shape[0], buf.shape[1]
    npoly = starts.shape[0] - 1
    xs = np.empty(4096, np.float64)
    for p in range(npoly):
        a0 = starts[p]
        a1 = starts[p + 1]
        nv = a1 - a0
        if nv < 3:
            continue
        iw = par[p, 0]
        tx = par[p, 1]
        ty = par[p, 2]
        tr = par[p, 3]
        alpha = par[p, 4]
        m = iw * 0.5 + 1.5
        xmin = 1e18
        xmax = -1e18
        ymin = 1e18
        ymax = -1e18
        for k in range(a0, a1):
            if V[k, 0] < xmin:
                xmin = V[k, 0]
            if V[k, 0] > xmax:
                xmax = V[k, 0]
            if V[k, 1] < ymin:
                ymin = V[k, 1]
            if V[k, 1] > ymax:
                ymax = V[k, 1]
        bx0 = max(0, int(math.floor(xmin - m - ox)))
        bx1 = min(w, int(math.ceil(xmax + m - ox)) + 1)
        by0 = max(0, int(math.floor(ymin - m - oy)))
        by1 = min(h, int(math.ceil(ymax + m - oy)) + 1)
        if bx0 >= bx1 or by0 >= by1:
            continue
        bw = bx1 - bx0
        bh = by1 - by0
        dist = np.full((bh, bw), m + 1.0, np.float32)
        inside = np.zeros((bh, bw), np.uint8)
        if nv > xs.shape[0]:
            xs = np.empty(nv * 2, np.float64)
        # scanline inside test (even-odd) at pixel centres
        for j in range(bh):
            py = by0 + j + oy + 0.5
            k = 0
            for e in range(nv):
                x0 = V[a0 + e, 0]
                y0 = V[a0 + e, 1]
                e1 = a0 + ((e + 1) % nv)
                x1 = V[e1, 0]
                y1 = V[e1, 1]
                if (y0 <= py) != (y1 <= py):
                    xs[k] = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
                    k += 1
            if k < 2:
                continue
            _sort_small(xs, k)
            for q in range(0, k - 1, 2):
                ia = int(math.ceil(xs[q] - ox - 0.5)) - bx0
                ib = int(math.ceil(xs[q + 1] - ox - 0.5)) - bx0
                if ia < 0:
                    ia = 0
                if ib > bw:
                    ib = bw
                for i in range(ia, ib):
                    inside[j, i] = 1
        # distance to the outline, only near edges
        for e in range(nv):
            x0 = V[a0 + e, 0]
            y0 = V[a0 + e, 1]
            e1 = a0 + ((e + 1) % nv)
            x1 = V[e1, 0]
            y1 = V[e1, 1]
            ex = x1 - x0
            ey = y1 - y0
            ll = ex * ex + ey * ey
            ex0 = max(bx0, int(math.floor(min(x0, x1) - m - ox)))
            ex1 = min(bx1, int(math.ceil(max(x0, x1) + m - ox)) + 1)
            ey0 = max(by0, int(math.floor(min(y0, y1) - m - oy)))
            ey1 = min(by1, int(math.ceil(max(y0, y1) + m - oy)) + 1)
            for y in range(ey0, ey1):
                py = y + oy + 0.5
                for x in range(ex0, ex1):
                    px = x + ox + 0.5
                    if ll > 1e-12:
                        t = ((px - x0) * ex + (py - y0) * ey) / ll
                        if t < 0.0:
                            t = 0.0
                        elif t > 1.0:
                            t = 1.0
                    else:
                        t = 0.0
                    qx = x0 + t * ex - px
                    qy = y0 + t * ey - py
                    dd = math.sqrt(qx * qx + qy * qy)
                    if dd < dist[y - by0, x - bx0]:
                        dist[y - by0, x - bx0] = dd
        fr = fill[p, 0]
        fg = fill[p, 1]
        fb = fill[p, 2]
        for j in range(bh):
            y = by0 + j
            py = y + oy + 0.5
            for i in range(bw):
                sd = dist[j, i]
                if inside[j, i] == 1:
                    sd = -sd
                cov = _c01(0.5 - (sd - iw * 0.5))
                if cov <= 0.0:
                    continue
                x = bx0 + i
                px = x + ox + 0.5
                r_ = fr
                g_ = fg
                b_ = fb
                if tr > 0.0:
                    ex = px - tx
                    ey = py - ty
                    t = _c01(math.sqrt(ex * ex + ey * ey) - tr + 0.5)
                    r_ += (shade[p, 0] - r_) * t
                    g_ += (shade[p, 1] - g_) * t
                    b_ += (shade[p, 2] - b_) * t
                if iw > 0.0:
                    t = _c01(sd + iw * 0.5 + 0.5) * min(1.0, iw)
                    r_ += (ink[p, 0] - r_) * t
                    g_ += (ink[p, 1] - g_) * t
                    b_ += (ink[p, 2] - b_) * t
                a = cov * alpha
                ia = 1.0 - a
                buf[y, x, 0] = r_ * a + buf[y, x, 0] * ia
                buf[y, x, 1] = g_ * a + buf[y, x, 1] * ia
                buf[y, x, 2] = b_ * a + buf[y, x, 2] * ia
                buf[y, x, 3] = a + buf[y, x, 3] * ia


@njit(cache=True, fastmath=True)
def add_soft_discs(light, D):
    """Additive soft discs into a light buffer (H, W, 3).
    D columns: cx cy r(core) R(falloff) r g b intensity hardness."""
    H, W = light.shape[0], light.shape[1]
    for q in range(D.shape[0]):
        cx = D[q, 0]
        cy = D[q, 1]
        rc = D[q, 2]
        Rf = D[q, 3]
        inten = D[q, 7]
        hard = D[q, 8]
        Rt = rc + Rf
        x0 = max(0, int(math.floor(cx - Rt)))
        x1 = min(W, int(math.ceil(cx + Rt)) + 1)
        y0 = max(0, int(math.floor(cy - Rt)))
        y1 = min(H, int(math.ceil(cy + Rt)) + 1)
        for y in range(y0, y1):
            dy = y + 0.5 - cy
            for x in range(x0, x1):
                dx = x + 0.5 - cx
                d = math.sqrt(dx * dx + dy * dy)
                if d >= Rt:
                    continue
                if d <= rc:
                    v = 1.0
                else:
                    u = 1.0 - (d - rc) / max(Rf, 1e-6)
                    v = u ** hard * (u * u * (3.0 - 2.0 * u))
                v *= inten
                light[y, x, 0] += D[q, 4] * v
                light[y, x, 1] += D[q, 5] * v
                light[y, x, 2] += D[q, 6] * v


@njit(cache=True, fastmath=True)
def _ell(px, py, cx, cy, ca, sa, sx, sy):
    """Local elliptic coordinates of a pixel: (u, v) in disc units, and |(u, v)|."""
    dx = px - cx
    dy = py - cy
    u = (dx * ca + dy * sa) / sx
    v = (-dx * sa + dy * ca) / sy
    return u, v, math.sqrt(u * u + v * v) + 1e-6


@njit(cache=True, fastmath=True)
def paint_billows2(buf, ox, oy, starts, D, GP, P, lx, ly):
    """Billows with designed lobes (v2).

    D columns: cx cy r wa wp ts tl sx sy ang bx by br
      sx, sy, ang : the lobe is an ellipse (radii r*sx, r*sy, rotated by ang) - squashed bases,
                    sheared curls
      bx, by, br  : a bite disc removed from this lobe only (br <= 0: none) - hook-shaped curls
      ts, tl      : shadow crescent / lit cap depth (fractions of r), unions over the group
    GP columns: alpha, inner line width, ground cut y (pixels below it are cut flat; 1e9 = none)
    P rows: shadow, mid, lit, line."""
    h, w = buf.shape[0], buf.shape[1]
    G = starts.shape[0] - 1
    for g in range(G):
        d0 = starts[g]
        d1 = starts[g + 1]
        if d1 <= d0:
            continue
        al = GP[g, 0]
        li = GP[g, 1]
        gy = GP[g, 2]
        xmin = 1e18
        xmax = -1e18
        ymin = 1e18
        ymax = -1e18
        for d in range(d0, d1):
            R = D[d, 2] * max(D[d, 7], D[d, 8]) * (1.0 + abs(D[d, 3])) + 1.0
            if D[d, 0] - R < xmin:
                xmin = D[d, 0] - R
            if D[d, 0] + R > xmax:
                xmax = D[d, 0] + R
            if D[d, 1] - R < ymin:
                ymin = D[d, 1] - R
            if D[d, 1] + R > ymax:
                ymax = D[d, 1] + R
        if ymax > gy + 1.0:
            ymax = gy + 1.0
        x0 = max(0, int(math.floor(xmin - ox)))
        x1 = min(w, int(math.ceil(xmax - ox)) + 1)
        y0 = max(0, int(math.floor(ymin - oy)))
        y1 = min(h, int(math.ceil(ymax - oy)) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        nd_ = d1 - d0
        WC = np.empty((nd_, 14), np.float64)
        for d in range(d0, d1):
            wp = D[d, 4]
            q = d - d0
            WC[q, 0] = math.cos(wp)
            WC[q, 1] = math.sin(wp)
            WC[q, 2] = math.cos(1.7 * wp + 1.0)
            WC[q, 3] = math.sin(1.7 * wp + 1.0)
            WC[q, 4] = math.cos(2.3 * wp + 2.0)
            WC[q, 5] = math.sin(2.3 * wp + 2.0)
            R = D[d, 2]
            k = math.sqrt(D[d, 7] * D[d, 8])
            WC[q, 6] = D[d, 0] + lx * D[d, 5] * R * k
            WC[q, 7] = D[d, 1] + ly * D[d, 5] * R * k
            kk = (1.9 - D[d, 6]) * R * k
            WC[q, 8] = D[d, 0] + lx * kk
            WC[q, 9] = D[d, 1] + ly * kk
            WC[q, 10] = math.cos(D[d, 9])
            WC[q, 11] = math.sin(D[d, 9])
            WC[q, 12] = k
            WC[q, 13] = R * max(D[d, 7], D[d, 8]) * (1.0 + abs(D[d, 3])) + 1.0
        for y in range(y0, y1):
            py = y + oy + 0.5
            gcut = 1.0
            if py > gy - 0.5:
                gcut = gy - py + 0.5
                if gcut <= 0.0:
                    continue
                if gcut > 1.0:
                    gcut = 1.0
            for x in range(x0, x1):
                px = x + ox + 0.5
                cs = 0.0
                cn = 0.0
                cl = 0.0
                best = -1e9
                bnd = 0.0
                for d in range(d0, d1):
                    R = D[d, 2]
                    if R < 0.35:
                        continue
                    q = d - d0
                    Rm = WC[q, 13]
                    Rm2 = Rm * Rm
                    dx = px - D[d, 0]
                    dy = py - D[d, 1]
                    nx = px - WC[q, 6]
                    ny = py - WC[q, 7]
                    tl = D[d, 6]
                    in_s = dx * dx + dy * dy <= Rm2
                    # ts < 0 marks a shape-only lobe: it takes its tones from the others
                    in_n = D[d, 5] >= 0.0 and nx * nx + ny * ny <= Rm2
                    in_l = False
                    if tl > 0.0 and D[d, 5] >= 0.0:
                        mx = px - WC[q, 8]
                        my = py - WC[q, 9]
                        in_l = mx * mx + my * my <= 0.81 * Rm2
                    if not (in_s or in_n or in_l):
                        continue
                    ca = WC[q, 10]
                    sa = WC[q, 11]
                    sx = D[d, 7]
                    sy = D[d, 8]
                    kk = WC[q, 12]
                    u, v, dl = _ell(px, py, D[d, 0], D[d, 1], ca, sa, sx, sy)
                    c = u / dl
                    s = v / dl
                    wv = _wob(c, s, WC[q, 0], WC[q, 1], WC[q, 2], WC[q, 3], WC[q, 4], WC[q, 5])
                    Rw = R * (1.0 + D[d, 3] * wv)
                    if in_s:
                        sd = (Rw - dl) * kk
                        if D[d, 12] > 0.0:
                            bx = px - D[d, 10]
                            by = py - D[d, 11]
                            bd = math.sqrt(bx * bx + by * by) - D[d, 12]
                            if bd < sd:
                                sd = bd
                        v_ = _c01(sd + 0.5)
                        if v_ > cs:
                            cs = v_
                        if sd > best:
                            best = sd
                            # outward normal of the ellipse in screen space
                            gx = c / sx * ca - s / sy * sa
                            gyy = c / sx * sa + s / sy * ca
                            gn = math.sqrt(gx * gx + gyy * gyy) + 1e-9
                            bnd = -(gx * lx + gyy * ly) / gn
                    if in_n:
                        u2, v2, dl2 = _ell(px, py, WC[q, 6], WC[q, 7], ca, sa, sx, sy)
                        v_ = _c01((Rw - dl2) * kk + 0.5)
                        if v_ > cn:
                            cn = v_
                    if in_l:
                        u3, v3, dl3 = _ell(px, py, WC[q, 8], WC[q, 9], ca, sa, sx, sy)
                        v_ = _c01((0.9 * Rw - dl3) * kk + 0.5)
                        if v_ > cl:
                            cl = v_
                if cs <= 0.0:
                    continue
                r_ = P[0, 0] + (P[1, 0] - P[0, 0]) * cn
                g_ = P[0, 1] + (P[1, 1] - P[0, 1]) * cn
                b_ = P[0, 2] + (P[1, 2] - P[0, 2]) * cn
                r_ += (P[2, 0] - r_) * cl
                g_ += (P[2, 1] - g_) * cl
                b_ += (P[2, 2] - b_) * cl
                if li > 0.0:
                    wl = li * _c01((bnd - 0.05) * 1.6)
                    if wl > 0.05:
                        v_ = _c01(wl - best + 0.5) * min(1.0, wl)
                        r_ += (P[3, 0] - r_) * v_
                        g_ += (P[3, 1] - g_) * v_
                        b_ += (P[3, 2] - b_) * v_
                a = cs * al * gcut
                ia = 1.0 - a
                buf[y, x, 0] = r_ * a + buf[y, x, 0] * ia
                buf[y, x, 1] = g_ * a + buf[y, x, 1] * ia
                buf[y, x, 2] = b_ * a + buf[y, x, 2] * ia
                buf[y, x, 3] = a + buf[y, x, 3] * ia


@njit(cache=True, fastmath=True)
def paint_disc_lines2(buf, ox, oy, D, LW, GY, col, lx, ly):
    """Silhouette colour line for v2 lobes (ellipses with bites), shadow side only; paint before
    the fills.  D columns as paint_billows2; GY: ground cut per lobe."""
    h, w = buf.shape[0], buf.shape[1]
    for q in range(D.shape[0]):
        cx = D[q, 0]
        cy = D[q, 1]
        R = D[q, 2]
        lw = LW[q]
        if R < 0.35 or lw <= 0.05:
            continue
        wa = D[q, 3]
        wp = D[q, 4]
        sx = D[q, 7]
        sy = D[q, 8]
        ca = math.cos(D[q, 9])
        sa = math.sin(D[q, 9])
        kk = math.sqrt(sx * sy)
        Rmax = R * max(sx, sy) * (1.0 + abs(wa)) + 1.0 + lw
        x0 = max(0, int(math.floor(cx - Rmax - ox)))
        x1 = min(w, int(math.ceil(cx + Rmax - ox)) + 1)
        y0 = max(0, int(math.floor(cy - Rmax - oy)))
        y1 = min(h, int(math.ceil(min(cy + Rmax, GY[q] + 1.0) - oy)) + 1)
        c2a = math.cos(wp)
        s2a = math.sin(wp)
        c3a = math.cos(1.7 * wp + 1.0)
        s3a = math.sin(1.7 * wp + 1.0)
        c5a = math.cos(2.3 * wp + 2.0)
        s5a = math.sin(2.3 * wp + 2.0)
        for y in range(y0, y1):
            py = y + oy + 0.5
            gcut = _c01(GY[q] - py + 0.5)
            if gcut <= 0.0:
                continue
            for x in range(x0, x1):
                px = x + ox + 0.5
                u, v, dl = _ell(px, py, cx, cy, ca, sa, sx, sy)
                if dl * min(sx, sy) > Rmax:
                    continue
                c = u / dl
                s = v / dl
                gx = c / sx * ca - s / sy * sa
                gyy = c / sx * sa + s / sy * ca
                gn = math.sqrt(gx * gx + gyy * gyy) + 1e-9
                nd = -(gx * lx + gyy * ly) / gn
                wl = lw * _c01((nd + 0.15) * 1.4)
                if wl <= 0.05:
                    continue
                Rw = R * (1.0 + wa * _wob(c, s, c2a, s2a, c3a, s3a, c5a, s5a))
                sd = (Rw - dl) * kk + wl
                if D[q, 12] > 0.0:
                    bx = px - D[q, 10]
                    by = py - D[q, 11]
                    bd = math.sqrt(bx * bx + by * by) - (D[q, 12] - wl)
                    if bd < sd:
                        sd = bd
                a = _c01(sd + 0.5) * min(1.0, wl) * gcut
                if a <= 0.0:
                    continue
                ia = 1.0 - a
                buf[y, x, 0] = col[0] * a + buf[y, x, 0] * ia
                buf[y, x, 1] = col[1] * a + buf[y, x, 1] * ia
                buf[y, x, 2] = col[2] * a + buf[y, x, 2] * ia
                buf[y, x, 3] = a + buf[y, x, 3] * ia
