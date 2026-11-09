"""kernels.py - numba rasterisers for the gouache engine.

All kernels paint into a premultiplied float32 RGBA image (H, W, 4). Coordinates
passed in are *flat* painting coordinates; (offx, offy) is added to get pixel
coordinates (the canvas margin). Composite modes:
  0 over      normal opaque-ish paint layering
  1 lock      alpha-locked: changes colour only where paint already is
  2 erase     removes paint (alpha and colour)
  3 behind    paints only where the canvas is still transparent (underneath)
"""
import math
import numpy as np
from numba import njit


@njit(cache=True, fastmath=True, nogil=True)
def _sm(x):
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    return x * x * (3.0 - 2.0 * x)


@njit(cache=True, fastmath=True, nogil=True)
def _put(img, y, x, al, c0, c1, c2, mode):
    if mode == 0:
        ia = 1.0 - al
        img[y, x, 0] = img[y, x, 0] * ia + al * c0
        img[y, x, 1] = img[y, x, 1] * ia + al * c1
        img[y, x, 2] = img[y, x, 2] * ia + al * c2
        img[y, x, 3] = img[y, x, 3] * ia + al
    elif mode == 1:
        A = img[y, x, 3]
        if A <= 0.0:
            return
        ia = 1.0 - al
        img[y, x, 0] = img[y, x, 0] * ia + al * c0 * A
        img[y, x, 1] = img[y, x, 1] * ia + al * c1 * A
        img[y, x, 2] = img[y, x, 2] * ia + al * c2 * A
    elif mode == 2:
        ia = 1.0 - al
        img[y, x, 0] *= ia
        img[y, x, 1] *= ia
        img[y, x, 2] *= ia
        img[y, x, 3] *= ia
    else:
        A = img[y, x, 3]
        k = al * (1.0 - A)
        img[y, x, 0] += k * c0
        img[y, x, 1] += k * c1
        img[y, x, 2] += k * c2
        img[y, x, 3] += k


@njit(cache=True, fastmath=True, nogil=True)
def _paper(paper, y, x, offy, offx):
    ph = paper.shape[0]
    pw = paper.shape[1]
    iy = (y - offy) % ph
    ix = (x - offx) % pw
    if iy < 0:
        iy += ph
    if ix < 0:
        ix += pw
    return paper[iy, ix]


@njit(cache=True, fastmath=True, nogil=True)
def k_dabs(img, offx, offy, X, Y, A, B, ANG, COL, OP, EDGE, RAG, BRIS, TEX, SHAPE,
           POOL, DRY, SPLIT, mode, paper, BR, E2):
    """Stamp dabs in the given order.
    A, B   semi-axes (px) along / across the dab direction ANG.
    SHAPE  0 round ellipse, 1 leaf (pointed, base at -u), 2 flat (squarish),
           3 petal/blade (round base, pointed tip at +u).
    EDGE   edge softness as a fraction of the radius. RAG ragged-edge amount.
    BRIS   bristle streak strength (streaks run along the dab direction).
    POOL   wet-edge pigment pooling (darker rim). DRY dry-brush (paper catches).
    SPLIT  two-tone loaded brush: lightness +-SPLIT on the -v / +v halves."""
    H = img.shape[0]
    W = img.shape[1]
    ioffx = int(offx)
    ioffy = int(offy)
    n = X.shape[0]
    for i in range(n):
        a = max(A[i], 0.4)
        b = max(B[i], 0.4)
        rag = RAG[i]
        R = max(a, b) * (1.0 + rag) + 2.0
        cx = X[i] + offx
        cy = Y[i] + offy
        x0 = int(math.floor(cx - R))
        x1 = int(math.ceil(cx + R)) + 1
        y0 = int(math.floor(cy - R))
        y1 = int(math.ceil(cy + R)) + 1
        if x0 < 0:
            x0 = 0
        if y0 < 0:
            y0 = 0
        if x1 > W:
            x1 = W
        if y1 > H:
            y1 = H
        if x1 <= x0 or y1 <= y0:
            continue
        ca = math.cos(ANG[i])
        sa = math.sin(ANG[i])
        tex = TEX[i]
        shp = SHAPE[i]
        br = BRIS[i]
        dry = DRY[i]
        pool = POOL[i]
        split = SPLIT[i]
        op = OP[i]
        cr = COL[i, 0]
        cg = COL[i, 1]
        cb = COL[i, 2]
        mn = min(a, b)
        e_n = max(EDGE[i], 0.9 / mn)
        for y in range(y0, y1):
            dy = y - cy
            for x in range(x0, x1):
                dx = x - cx
                u = dx * ca + dy * sa
                v = -dx * sa + dy * ca
                tu = u / a
                tv = v / b
                if shp == 1:
                    if tu <= -1.0 or tu >= 1.0:
                        continue
                    hw = (1.0 - tu * tu) * (1.0 - 0.3 * tu)
                    if hw < 1e-3:
                        continue
                    r = abs(tv) / hw
                elif shp == 2:
                    q2 = tu * tu
                    w2 = tv * tv
                    r = math.sqrt(math.sqrt(q2 * q2 + w2 * w2))
                elif shp == 3:
                    if tu >= 1.0:
                        continue
                    if tu < 0.0:
                        r = math.sqrt(tu * tu + tv * tv)
                    else:
                        hw = 1.0 - tu * tu * tu
                        if hw < 1e-3:
                            continue
                        r = abs(tv) / hw
                else:
                    r = math.sqrt(tu * tu + tv * tv)
                if rag > 0.0:
                    iu = int(tu * 13.0 + 32.0) & 63
                    iv = int(tv * 13.0 + 32.0) & 63
                    r = r * (1.0 + rag * E2[tex, iv, iu])
                if r >= 1.0:
                    continue
                al = _sm((1.0 - r) / e_n)
                if br > 0.0:
                    ib = int((tv * 0.5 + 0.5) * 100.0 + tex * 13) & 255
                    al *= 1.0 - br * BR[tex, ib]
                if dry > 0.0:
                    p = _paper(paper, y, x, ioffy, ioffx)
                    thr = dry * (1.3 - al)
                    dep = (p - thr) * 5.0 + 0.5
                    if dep < 0.0:
                        dep = 0.0
                    elif dep > 1.0:
                        dep = 1.0
                    al *= dep
                al *= op
                if al < 0.003:
                    continue
                f = 1.0
                if pool > 0.0:
                    f -= pool * _sm((r - 0.55) / 0.45)
                if split != 0.0:
                    if tv < 0.0:
                        f *= 1.0 + split
                    else:
                        f *= 1.0 - split
                c0 = cr * f
                c1 = cg * f
                c2 = cb * f
                if c0 > 1.0:
                    c0 = 1.0
                if c1 > 1.0:
                    c1 = 1.0
                if c2 > 1.0:
                    c2 = 1.0
                _put(img, y, x, al, c0, c1, c2, mode)


@njit(cache=True, fastmath=True, nogil=True)
def _sweep_fields(P, WD, offx, offy, H, W, rag, caps=True):
    """Nearest-segment fields of a polyline over its bounding box.
    Returns x0, y0, D2 (squared distance), S (0..1 along), T (signed side, px),
    HW (half width at the nearest point), total length."""
    M = P.shape[0]
    wmax = 0.0
    minx = 1e30
    maxx = -1e30
    miny = 1e30
    maxy = -1e30
    for i in range(M):
        if WD[i] > wmax:
            wmax = WD[i]
        px = P[i, 0] + offx
        py = P[i, 1] + offy
        minx = min(minx, px)
        maxx = max(maxx, px)
        miny = min(miny, py)
        maxy = max(maxy, py)
    pad = wmax * 0.5 * (1.0 + rag) + 2.0
    x0 = max(0, int(math.floor(minx - pad)))
    x1 = min(W, int(math.ceil(maxx + pad)) + 1)
    y0 = max(0, int(math.floor(miny - pad)))
    y1 = min(H, int(math.ceil(maxy + pad)) + 1)
    hh = max(y1 - y0, 0)
    ww = max(x1 - x0, 0)
    D2 = np.full((hh, ww), 1e30, np.float32)
    S = np.zeros((hh, ww), np.float32)
    T = np.zeros((hh, ww), np.float32)
    HW = np.zeros((hh, ww), np.float32)
    cum = np.zeros(M, np.float64)
    for i in range(M - 1):
        dx = P[i + 1, 0] - P[i, 0]
        dy = P[i + 1, 1] - P[i, 1]
        cum[i + 1] = cum[i] + math.sqrt(dx * dx + dy * dy)
    total = max(cum[M - 1], 1e-6)
    if hh == 0 or ww == 0:
        return x0, y0, D2, S, T, HW, total
    # open ends: directions of the first and last segment
    u0x = P[1, 0] - P[0, 0]
    u0y = P[1, 1] - P[0, 1]
    l0 = max(math.sqrt(u0x * u0x + u0y * u0y), 1e-6)
    u0x /= l0
    u0y /= l0
    ulx = P[M - 1, 0] - P[M - 2, 0]
    uly = P[M - 1, 1] - P[M - 2, 1]
    ll = max(math.sqrt(ulx * ulx + uly * uly), 1e-6)
    ulx /= ll
    uly /= ll
    p0x = P[0, 0] + offx
    p0y = P[0, 1] + offy
    plx = P[M - 1, 0] + offx
    ply = P[M - 1, 1] + offy
    for i in range(M - 1):
        ax = P[i, 0] + offx
        ay = P[i, 1] + offy
        bx = P[i + 1, 0] + offx
        by = P[i + 1, 1] + offy
        dx = bx - ax
        dy = by - ay
        L = math.sqrt(dx * dx + dy * dy)
        if L < 1e-6:
            continue
        ux = dx / L
        uy = dy / L
        wseg = max(WD[i], WD[i + 1]) * 0.5 * (1.0 + rag) + 2.0
        sx0 = max(x0, int(math.floor(min(ax, bx) - wseg)))
        sx1 = min(x1, int(math.ceil(max(ax, bx) + wseg)) + 1)
        sy0 = max(y0, int(math.floor(min(ay, by) - wseg)))
        sy1 = min(y1, int(math.ceil(max(ay, by) + wseg)) + 1)
        for y in range(sy0, sy1):
            for x in range(sx0, sx1):
                px = x - ax
                py = y - ay
                t = (px * ux + py * uy) / L
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                qx = px - t * L * ux
                qy = py - t * L * uy
                d2 = qx * qx + qy * qy
                j = y - y0
                k = x - x0
                if not caps:
                    if (x - p0x) * u0x + (y - p0y) * u0y < 0.0 or (x - plx) * ulx + (y - ply) * uly > 0.0:
                        continue
                if d2 < D2[j, k]:
                    D2[j, k] = d2
                    S[j, k] = (cum[i] + t * L) / total
                    T[j, k] = -px * uy + py * ux
                    HW[j, k] = 0.5 * (WD[i] + (WD[i + 1] - WD[i]) * t)
    return x0, y0, D2, S, T, HW, total


@njit(cache=True, fastmath=True, nogil=True)
def k_stroke(img, offx, offy, P, WD, COL, OPA, COL2, load2, edge, rag, bris, tex,
             pool, dry, drytail, mode, paper, BR, E2):
    """One continuous bristle stroke along polyline P with widths WD (full), colour
    COL (M,3) and opacity OPA (M,) along it; COL2 (3,) is a second colour loaded on
    the +side of the brush (load2 0..1). drytail: paint runs out toward the end."""
    H = img.shape[0]
    W = img.shape[1]
    M = P.shape[0]
    if M < 2:
        return
    x0, y0, D2, S, T, HW, total = _sweep_fields(P, WD, offx, offy, H, W, rag)
    hh = D2.shape[0]
    ww = D2.shape[1]
    ioffx = int(offx)
    ioffy = int(offy)
    for j in range(hh):
        for k in range(ww):
            d2 = D2[j, k]
            if d2 >= 1e29:
                continue
            half = max(HW[j, k], 0.4)
            r = math.sqrt(d2) / half
            s = S[j, k]
            tn = T[j, k] / half
            if tn > 1.0:
                tn = 1.0
            elif tn < -1.0:
                tn = -1.0
            if rag > 0.0:
                iu = int(s * total / max(half * 1.2, 2.5) * 3.0) & 63
                iv = int(tn * 9.0 + 32.0 + (1 if T[j, k] > 0 else 0) * 17) & 63
                r = r * (1.0 + rag * E2[tex, iv, iu])
            if r >= 1.0:
                continue
            e_n = max(edge, 0.9 / half)
            al = _sm((1.0 - r) / e_n)
            ib = int((tn * 0.5 + 0.5) * 120.0 + tex * 11) & 255
            if bris > 0.0:
                al *= 1.0 - bris * BR[tex, ib]
            fi = s * (M - 1)
            i0 = int(fi)
            if i0 >= M - 1:
                i0 = M - 2
            f = fi - i0
            op = OPA[i0] * (1.0 - f) + OPA[i0 + 1] * f
            dr = dry + drytail * s * s * s
            if dr > 0.0:
                p = _paper(paper, y0 + j, x0 + k, ioffy, ioffx)
                thr = dr * (1.3 - al)
                dep = (p - thr) * 5.0 + 0.5
                if dep < 0.0:
                    dep = 0.0
                elif dep > 1.0:
                    dep = 1.0
                al *= dep
            al *= op
            if al < 0.003:
                continue
            c0 = COL[i0, 0] * (1.0 - f) + COL[i0 + 1, 0] * f
            c1 = COL[i0, 1] * (1.0 - f) + COL[i0 + 1, 1] * f
            c2 = COL[i0, 2] * (1.0 - f) + COL[i0 + 1, 2] * f
            if load2 > 0.0:
                w2 = load2 * _sm(0.5 + 0.8 * tn + 0.9 * (BR[(tex + 7) & 31, ib] - 0.5))
                c0 = c0 * (1.0 - w2) + COL2[0] * w2
                c1 = c1 * (1.0 - w2) + COL2[1] * w2
                c2 = c2 * (1.0 - w2) + COL2[2] * w2
            if pool > 0.0:
                ff = 1.0 - pool * _sm((r - 0.6) / 0.4)
                c0 *= ff
                c1 *= ff
                c2 *= ff
            _put(img, y0 + j, x0 + k, al, c0, c1, c2, mode)


@njit(cache=True, fastmath=True, nogil=True)
def k_sweep(P, WD, offx, offy, H, W, rag, E2, tex, caps):
    """Form fields for a shaded tube (trunk, limb, root): over the bbox returns
    x0, y0, R (normalised distance, ragged), TN (-1..1 across), S (0..1 along),
    HW (half width px), total length."""
    x0, y0, D2, S, T, HW, total = _sweep_fields(P, WD, offx, offy, H, W, rag, caps)
    hh = D2.shape[0]
    ww = D2.shape[1]
    R = np.full((hh, ww), 9.0, np.float32)
    TN = np.zeros((hh, ww), np.float32)
    for j in range(hh):
        for k in range(ww):
            d2 = D2[j, k]
            if d2 >= 1e29:
                continue
            half = max(HW[j, k], 0.4)
            r = math.sqrt(d2) / half
            tn = T[j, k] / half
            if tn > 1.0:
                tn = 1.0
            elif tn < -1.0:
                tn = -1.0
            if rag > 0.0:
                iu = int(S[j, k] * total / max(half * 0.5, 3.0)) & 63
                iv = (32 + (1 if T[j, k] > 0 else 0) * 17) & 63
                r = r * (1.0 + rag * E2[tex, iv, iu])
            R[j, k] = r
            TN[j, k] = tn
    return x0, y0, R, TN, S, HW, total


@njit(cache=True, fastmath=True, nogil=True)
def k_blobs(cov, shade, cid, rad, offx, offy, BX, BY, BRX, BRY, BROT, BPH, BAMP, BFRQ,
            BLIGHT, lx, ly, lz, wrap, under):
    """Render lumpy ellipsoid blobs (painter's order: first = farthest) into a
    G-buffer: cov (coverage), shade (0..1 lambert-ish), cid (blob id), rad
    (normalised radius inside the blob, 0 centre .. 1 edge)."""
    H = cov.shape[0]
    W = cov.shape[1]
    n = BX.shape[0]
    nh = BPH.shape[1]
    for i in range(n):
        rx = BRX[i]
        ry = BRY[i]
        amp = 0.0
        for k in range(nh):
            amp += abs(BAMP[i, k])
        R = max(rx, ry) * (1.0 + amp) + 2.0
        cx = BX[i] + offx
        cy = BY[i] + offy
        x0 = max(0, int(math.floor(cx - R)))
        x1 = min(W, int(math.ceil(cx + R)) + 1)
        y0 = max(0, int(math.floor(cy - R)))
        y1 = min(H, int(math.ceil(cy + R)) + 1)
        if x1 <= x0 or y1 <= y0:
            continue
        c = math.cos(BROT[i])
        s = math.sin(BROT[i])
        mn = min(rx, ry)
        bl = BLIGHT[i]
        for y in range(y0, y1):
            dy = y - cy
            for x in range(x0, x1):
                dx = x - cx
                u = dx * c + dy * s
                v = -dx * s + dy * c
                nu = u / rx
                nv = v / ry
                d = math.sqrt(nu * nu + nv * nv)
                if d > 1.0 + amp + 0.05:
                    continue
                th = math.atan2(nv, nu)
                rr = 1.0
                for k in range(nh):
                    rr += BAMP[i, k] * math.cos(BFRQ[i, k] * th + BPH[i, k])
                dn = d / rr
                aa = 1.0 / (rr * mn)
                a = (1.0 - dn) / aa + 0.5
                if a <= 0.0:
                    continue
                if a > 1.0:
                    a = 1.0
                dd = min(dn, 1.0)
                nz = math.sqrt(max(1.0 - dd * dd, 0.0))
                if d > 1e-6:
                    ex = nu / d
                    ey = nv / d
                else:
                    ex = 0.0
                    ey = 0.0
                nxi = (ex * c - ey * s) * dd
                nyi = (ex * s + ey * c) * dd
                lam = nxi * lx + nyi * ly + nz * lz
                lam = (lam + wrap) / (1.0 + wrap)
                if lam < 0.0:
                    lam = 0.0
                if nyi > 0.0:
                    lam *= 1.0 - under * nyi
                val = lam * bl
                cv0 = cov[y, x]
                cov[y, x] = cv0 + a * (1.0 - cv0)
                shade[y, x] = shade[y, x] * (1.0 - a) + val * a
                if a >= 0.5:
                    cid[y, x] = i
                    rad[y, x] = dn
