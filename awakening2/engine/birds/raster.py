"""Low-level raster kernels for the bird drawings.

Conventions
-----------
* Final-resolution pixel (row r, col c) has its centre at continuous coords (x=c, y=r).
* Supersampled (SS) buffers are (h*ss, w*ss); final coord x maps to SS coord x*ss + (ss-1)/2.
* Ink strokes are rendered analytically at final resolution (box-filtered cross-section),
  fills are rasterised into SS id buffers and resolved by exact box averaging.
"""
import numpy as np
import numba as nb
import cv2

SHIFT = 4                      # cv2 fixed-point bits for sub-pixel polygon fills
_SCALE = float(1 << SHIFT)


# ----------------------------------------------------------------------------- z-buffer
@nb.njit(cache=True, fastmath=True)
def zbuf_spheres(sx, sy, sz, sr, depth, idx):
    """Front-most depth of a union of spheres (orthographic, screen coords, y down)."""
    H, W = depth.shape
    for k in range(sx.shape[0]):
        cx = sx[k]; cy = sy[k]; cz = sz[k]; r = sr[k]
        if r <= 0.0:
            continue
        x0 = max(0, int(np.floor(cx - r))); x1 = min(W - 1, int(np.ceil(cx + r)))
        y0 = max(0, int(np.floor(cy - r))); y1 = min(H - 1, int(np.ceil(cy + r)))
        r2 = r * r
        for y in range(y0, y1 + 1):
            dy = y - cy
            dy2 = dy * dy
            if dy2 > r2:
                continue
            for x in range(x0, x1 + 1):
                dx = x - cx
                d2 = dx * dx + dy2
                if d2 <= r2:
                    z = cz + np.sqrt(r2 - d2)
                    if z > depth[y, x]:
                        depth[y, x] = z
                        idx[y, x] = k


# ----------------------------------------------------------------------------- strokes
@nb.njit(cache=True, fastmath=True)
def stroke_poly(buf, xs, ys, rs, closed):
    """Variable-radius polyline, analytic AA, max-combined into buf (final res)."""
    H, W = buf.shape
    n = xs.shape[0]
    if n < 2:
        if n == 1 and rs[0] > 0:
            _dot(buf, xs[0], ys[0], rs[0])
        return
    nseg = n if closed else n - 1
    for i in range(nseg):
        j = i + 1
        if j == n:
            j = 0
        ax = xs[i]; ay = ys[i]; ar = rs[i]
        bx = xs[j]; by = ys[j]; br = rs[j]
        if ar <= 0.0 and br <= 0.0:
            continue
        rm = max(ar, br) + 1.0
        x0 = max(0, int(np.floor(min(ax, bx) - rm))); x1 = min(W - 1, int(np.ceil(max(ax, bx) + rm)))
        y0 = max(0, int(np.floor(min(ay, by) - rm))); y1 = min(H - 1, int(np.ceil(max(ay, by) + rm)))
        vx = bx - ax; vy = by - ay
        L2 = vx * vx + vy * vy
        for y in range(y0, y1 + 1):
            py = y - ay
            for x in range(x0, x1 + 1):
                px = x - ax
                t = 0.0
                if L2 > 1e-12:
                    t = (px * vx + py * vy) / L2
                    if t < 0.0:
                        t = 0.0
                    elif t > 1.0:
                        t = 1.0
                dx = px - t * vx; dy = py - t * vy
                d = np.sqrt(dx * dx + dy * dy)
                r = ar + (br - ar) * t
                if r <= 0.0:
                    continue
                hi = d + 0.5
                if r < hi:
                    hi = r
                lo = d - 0.5
                if -r > lo:
                    lo = -r
                c = hi - lo
                if c > 0.0:
                    if c > 1.0:
                        c = 1.0
                    if c > buf[y, x]:
                        buf[y, x] = c


@nb.njit(cache=True, fastmath=True)
def _dot(buf, cx, cy, r):
    H, W = buf.shape
    x0 = max(0, int(np.floor(cx - r - 1))); x1 = min(W - 1, int(np.ceil(cx + r + 1)))
    y0 = max(0, int(np.floor(cy - r - 1))); y1 = min(H - 1, int(np.ceil(cy + r + 1)))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            hi = min(d + 0.5, r); lo = max(d - 0.5, -r)
            c = hi - lo
            if c > 0:
                c = min(c, 1.0)
                if c > buf[y, x]:
                    buf[y, x] = c


# ----------------------------------------------------------------------------- resolve
@nb.njit(cache=True, fastmath=True)
def resolve_ids(ids, pal, ss, out):
    """Box-average palette colours (premultiplied RGBA) of an SS id buffer into out (h,w,4)."""
    h = out.shape[0]; w = out.shape[1]
    inv = 1.0 / (ss * ss)
    for y in range(h):
        for x in range(w):
            r = 0.0; g = 0.0; b = 0.0; a = 0.0
            for yy in range(y * ss, y * ss + ss):
                for xx in range(x * ss, x * ss + ss):
                    k = ids[yy, xx]
                    if k != 0:
                        r += pal[k, 0]; g += pal[k, 1]; b += pal[k, 2]; a += pal[k, 3]
            out[y, x, 0] = r * inv; out[y, x, 1] = g * inv
            out[y, x, 2] = b * inv; out[y, x, 3] = a * inv


def coverage(mask_ss, ss):
    """Exact box-filtered coverage of a bool/uint8 SS mask -> float32 (h, w)."""
    H, W = mask_ss.shape
    m = mask_ss.astype(np.float32)
    return m.reshape(H // ss, ss, W // ss, ss).mean(axis=(1, 3))


# ----------------------------------------------------------------------------- fills
def to_ss(pts, ss):
    """final coords (N,2) -> SS fixed-point int32 for cv2 (with SHIFT bits)."""
    p = np.asarray(pts, np.float64) * ss + (ss - 1) * 0.5
    return np.round(p * _SCALE).astype(np.int32)


def fill_polys(mask, polys, ss, value=1):
    """Rasterise polygons given in final coords into an SS uint8 mask (non-zero winding-ish)."""
    arrs = [to_ss(p, ss).reshape(-1, 1, 2) for p in polys if p is not None and len(p) >= 3]
    if arrs:
        cv2.fillPoly(mask, arrs, int(value), lineType=cv2.LINE_8, shift=SHIFT)
    return mask


def fill_capsules(mask, xs, ys, rs, ss, value=1):
    """Thick variable-radius polyline (final coords) rasterised into an SS mask."""
    n = len(xs)
    P = np.stack([xs, ys], 1)
    for i in range(n):
        c = to_ss(P[i:i + 1], ss)[0]
        r = int(round(rs[i] * ss * _SCALE))
        if r > 0:
            cv2.circle(mask, (int(c[0]), int(c[1])), r, int(value), -1, lineType=cv2.LINE_8, shift=SHIFT)
    for i in range(n - 1):
        a = P[i]; b = P[i + 1]
        d = b - a
        L = np.hypot(d[0], d[1])
        if L < 1e-9:
            continue
        nrm = np.array([-d[1], d[0]]) / L
        quad = np.array([a + nrm * rs[i], b + nrm * rs[i + 1], b - nrm * rs[i + 1], a - nrm * rs[i]])
        cv2.fillConvexPoly(mask, to_ss(quad, ss), int(value), lineType=cv2.LINE_8, shift=SHIFT)
    return mask


def shift_mask(m, dx, dy):
    """Shift a 2D mask by integer (dx, dy) pixels (zero fill)."""
    out = np.zeros_like(m)
    H, W = m.shape
    dx = int(dx); dy = int(dy)
    xs0, xs1 = max(0, -dx), min(W, W - dx)
    ys0, ys1 = max(0, -dy), min(H, H - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = m[ys0:ys1, xs0:xs1]
    return out


# ----------------------------------------------------------------------------- contours
def mask_contours(mask_ss, ss, min_pts=6):
    """Outer + hole contours of an SS mask, returned in final-res coords (list of (N,2))."""
    m = (mask_ss > 0).astype(np.uint8)
    if not m.any():
        return []
    cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if len(c) < min_pts:
            continue
        p = c[:, 0, :].astype(np.float64)
        p = (p - (ss - 1) * 0.5) / ss
        out.append(p)
    return out


def resample_closed(p, step):
    d = np.diff(np.vstack([p, p[:1]]), axis=0)
    seg = np.hypot(d[:, 0], d[:, 1])
    L = seg.sum()
    if L < 1e-6:
        return p
    n = max(8, int(L / step))
    s = np.concatenate([[0], np.cumsum(seg)])
    q = np.vstack([p, p[:1]])
    t = np.linspace(0, L, n, endpoint=False)
    return np.stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])], 1)


def resample_open(p, step):
    d = np.diff(p, axis=0)
    seg = np.hypot(d[:, 0], d[:, 1])
    L = seg.sum()
    if L < 1e-6:
        return p.copy()
    n = max(2, int(np.ceil(L / step)) + 1)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, L, n)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1)


def smooth_closed(p, sigma):
    if sigma <= 0 or len(p) < 5:
        return p
    r = int(np.ceil(3 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    n = len(p)
    idx = (np.arange(n)[:, None] + np.arange(-r, r + 1)[None, :]) % n
    return np.stack([(p[idx, 0] * k).sum(1), (p[idx, 1] * k).sum(1)], 1)


def closed_normals(p):
    """Unit outward normals for a closed polyline in image coords (y down)."""
    d = np.roll(p, -1, 0) - np.roll(p, 1, 0)
    L = np.hypot(d[:, 0], d[:, 1]) + 1e-12
    t = d / L[:, None]
    n = np.stack([t[:, 1], -t[:, 0]], 1)
    # orientation: signed area (image coords) ; make normals point outward
    x, y = p[:, 0], p[:, 1]
    area = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    if area < 0:
        n = -n
    return n, area


def turning(p):
    """Signed turning angle per vertex of a closed polyline (radians)."""
    a = p - np.roll(p, 1, 0)
    b = np.roll(p, -1, 0) - p
    ang = np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], (a * b).sum(1))
    return ang
