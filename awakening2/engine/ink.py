"""ink.py - hand-inked lines from render passes.

Pipeline:
  1. edge_map(): mark boundary pixels between regions (id change, depth
     discontinuity, normal crease, silhouette), each with a line class.
  2. trace(): thin the edge map and walk it into polylines (chains) that end at
     line ends and junctions.
  3. smooth / break chains at sharp corners, give each point a width from the
     class, a pressure profile (tapered ends, slow variation, heavier on the
     shadow side) and a per-drawing wobble (line boil on 2s).
  4. stroke(): numba rasteriser for variable-width anti-aliased strokes with
     max-compositing (overlaps never double-darken).

Because the lines are traced from the same id maps that define the fills,
they sit exactly on the fill edges.
"""
import math
import numpy as np
import cv2
from numba import njit
from skimage.morphology import thin

# line classes
SIL, OCC, PART, CREASE, DETAIL = 1, 2, 3, 4, 5


# ----------------------------------------------------------------------------
# edge detection
# ----------------------------------------------------------------------------

def edge_map(mask, label, depth, nrm, detail=None, depth_rel=0.035, crease_deg=42.0,
             depth_abs=0.0):
    """Return an int8 class map of boundary pixels (0 = none).

    mask   bool (H,W) object coverage
    label  int (H,W) region id (part*K+material); boundaries between labels are PART
    depth  float camera depth
    nrm    (H,W,3) normals
    detail int (H,W) panel ids; boundaries are DETAIL lines (thin)
    """
    H, W = mask.shape
    cls = np.zeros((H, W), np.int8)
    d = np.where(mask, depth, np.float32(1e9)).astype(np.float32)
    cos_t = math.cos(math.radians(crease_deg))

    for axis in (0, 1):
        if axis == 0:
            A = (slice(0, H - 1), slice(None)); B = (slice(1, H), slice(None))
        else:
            A = (slice(None), slice(0, W - 1)); B = (slice(None), slice(1, W))
        ma, mb = mask[A], mask[B]
        da, db = d[A], d[B]
        sil = ma != mb
        both = ma & mb
        zmin = np.minimum(da, db)
        occ = both & (np.abs(da - db) > (depth_rel * zmin + depth_abs))
        part = both & (label[A] != label[B]) & ~occ
        na, nb = nrm[A], nrm[B]
        cre = both & (np.sum(na * nb, -1) < cos_t) & ~occ & ~part
        if detail is not None:
            det = both & (detail[A] != detail[B]) & ~occ & ~part & ~cre
        else:
            det = None
        for c, k in ((det, DETAIL), (cre, CREASE), (part, PART), (occ, OCC), (sil, SIL)):
            if c is None:
                continue
            if k == SIL:
                a_side = c & ma          # mark the object pixel
                b_side = c & mb
            else:
                a_near = da <= db
                a_side = c & a_near
                b_side = c & ~a_near
            va = cls[A]; vb = cls[B]
            va[a_side] = k
            vb[b_side] = k
    return cls


# ----------------------------------------------------------------------------
# tracing
# ----------------------------------------------------------------------------

@njit(cache=True)
def _trace(sk, H, W, maxpts):
    # neighbour offsets (8-connected), ordered so straight steps come first
    oy = np.array([0, 1, 0, -1, 1, 1, -1, -1])
    ox = np.array([1, 0, -1, 0, 1, -1, 1, -1])
    deg = np.zeros((H, W), np.int8)
    for y in range(H):
        for x in range(W):
            if sk[y, x]:
                n = 0
                for k in range(8):
                    yy = y + oy[k]; xx = x + ox[k]
                    if 0 <= yy < H and 0 <= xx < W and sk[yy, xx]:
                        n += 1
                deg[y, x] = n
    visited = np.zeros((H, W), np.bool_)
    pts = np.empty((maxpts, 2), np.int32)
    starts = np.empty(maxpts // 2 + 1, np.int32)
    npts = 0
    nch = 0
    # pass 1: start at ends and junctions; pass 2: leftover loops
    for pas in range(2):
        for y in range(H):
            for x in range(W):
                if not sk[y, x] or visited[y, x]:
                    continue
                if pas == 0 and deg[y, x] == 2:
                    continue
                # walk from (y,x) along each unvisited branch
                for k0 in range(8):
                    if npts >= maxpts - 2:
                        break
                    sy = y + oy[k0]; sx = x + ox[k0]
                    if not (0 <= sy < H and 0 <= sx < W):
                        continue
                    if not sk[sy, sx] or visited[sy, sx]:
                        continue
                    starts[nch] = npts; nch += 1
                    pts[npts, 0] = y; pts[npts, 1] = x; npts += 1
                    cy = sy; cx = sx
                    while True:
                        pts[npts, 0] = cy; pts[npts, 1] = cx; npts += 1
                        visited[cy, cx] = True
                        if npts >= maxpts - 2:
                            break
                        if deg[cy, cx] != 2 and not (cy == y and cx == x):
                            break
                        moved = False
                        for k in range(8):
                            yy = cy + oy[k]; xx = cx + ox[k]
                            if 0 <= yy < H and 0 <= xx < W and sk[yy, xx] and not visited[yy, xx]:
                                # avoid stepping diagonally if a straight neighbour exists (handled by order)
                                cy = yy; cx = xx; moved = True
                                break
                        if not moved:
                            break
                visited[y, x] = True
                if deg[y, x] == 0:
                    pass
    starts[nch] = npts
    return pts[:npts].copy(), starts[:nch + 1].copy()


def trace(cls_map, min_len=4):
    """Thin a class map and return a list of chains: (pts float32 (n,2) as x,y; class)."""
    sk = thin(cls_map > 0)
    H, W = sk.shape
    maxpts = int(sk.sum() * 2 + 16)
    pts, starts = _trace(sk, H, W, maxpts)
    chains = []
    for i in range(len(starts) - 1):
        a, b = starts[i], starts[i + 1]
        if b - a < min_len:
            continue
        p = pts[a:b]
        c = cls_map[p[:, 0], p[:, 1]]
        c = c[c > 0]
        k = int(np.bincount(c).argmax()) if len(c) else PART
        chains.append((p[:, ::-1].astype(np.float32), k))
    return chains


# ----------------------------------------------------------------------------
# chain shaping
# ----------------------------------------------------------------------------

def smooth_chain(p, sigma=1.5, closed=False):
    n = len(p)
    if n < 3 or sigma <= 0:
        return p
    r = int(max(1, round(sigma * 2.5)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2); k /= k.sum()
    if closed:
        pp = np.concatenate([p[-r:], p, p[:r]])
        out = np.stack([np.convolve(pp[:, 0], k, 'valid'), np.convolve(pp[:, 1], k, 'valid')], -1)
    else:
        pp = np.concatenate([np.repeat(p[:1], r, 0), p, np.repeat(p[-1:], r, 0)])
        out = np.stack([np.convolve(pp[:, 0], k, 'valid'), np.convolve(pp[:, 1], k, 'valid')], -1)
        out[0] = p[0]; out[-1] = p[-1]
    return out.astype(np.float32)


def resample(p, step):
    d = np.sqrt(np.sum(np.diff(p, axis=0) ** 2, -1))
    s = np.concatenate([[0], np.cumsum(d)])
    L = s[-1]
    if L < step:
        return p[[0, -1]].copy() if len(p) > 1 else p
    n = max(2, int(round(L / step)) + 1)
    t = np.linspace(0, L, n)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], -1).astype(np.float32)


def split_corners(p, angle_deg=55.0, win=3):
    """Split a chain where it turns sharply (so strokes taper into corners)."""
    n = len(p)
    if n < 2 * win + 2:
        return [p]
    v1 = p[win:-win] - p[:-2 * win]
    v2 = p[2 * win:] - p[win:-win]
    c = np.sum(v1 * v2, -1) / (np.linalg.norm(v1, axis=-1) * np.linalg.norm(v2, axis=-1) + 1e-6)
    bad = np.where(c < math.cos(math.radians(angle_deg)))[0] + win
    if len(bad) == 0:
        return [p]
    cuts = []
    last = -10
    for b in bad:
        if b - last > win * 2:
            cuts.append(b)
        last = b
    out = []
    a = 0
    for c_ in cuts:
        if c_ - a >= 2:
            out.append(p[a:c_ + 1])
        a = c_
    out.append(p[a:])
    return [q for q in out if len(q) >= 2]


def pressure_profile(n, length_px, rng, taper_px=14.0, var=0.18, end_min=0.15):
    """Width multipliers along a stroke: tapered ends + slow pressure variation."""
    s = np.linspace(0, 1, n)
    L = max(length_px, 1.0)
    tp = min(taper_px / L, 0.45)
    a = np.clip(s / max(tp, 1e-3), 0, 1)
    b = np.clip((1 - s) / max(tp, 1e-3), 0, 1)
    # ease the tapers (a brush lands softly and lifts quickly)
    taper = end_min + (1 - end_min) * (np.sin(a * math.pi / 2) ** 1.2) * (np.sin(b * math.pi / 2) ** 0.8)
    ph = rng.uniform(0, 2 * math.pi, 3)
    fr = rng.uniform(0.6, 1.6, 3) * max(L / 140.0, 0.5)
    slow = 1 + var * (0.6 * np.sin(2 * math.pi * fr[0] * s + ph[0]) + 0.4 * np.sin(2 * math.pi * fr[1] * s + ph[1]))
    return (taper * slow).astype(np.float32)


def wobble(p, rng, amp=0.5, wl=40.0):
    """Low-frequency perpendicular wobble (hand tremor / line boil)."""
    n = len(p)
    if n < 3 or amp <= 0:
        return p
    d = np.gradient(p, axis=0)
    t = d / (np.linalg.norm(d, axis=-1, keepdims=True) + 1e-6)
    nrm = np.stack([-t[:, 1], t[:, 0]], -1)
    seg = np.sqrt(np.sum(np.diff(p, axis=0) ** 2, -1))
    s = np.concatenate([[0], np.cumsum(seg)])
    ph = rng.uniform(0, 2 * math.pi, 2)
    off = amp * (0.7 * np.sin(2 * math.pi * s / wl + ph[0]) + 0.3 * np.sin(2 * math.pi * s / (wl * 0.37) + ph[1]))
    return (p + nrm * off[:, None]).astype(np.float32)


# ----------------------------------------------------------------------------
# stroke rasteriser
# ----------------------------------------------------------------------------

@njit(cache=True, fastmath=True)
def _stroke_segments(acc, xs, ys, ws, starts):
    H, W = acc.shape
    nch = starts.shape[0] - 1
    for c in range(nch):
        a = starts[c]; b = starts[c + 1]
        for i in range(a, b - 1):
            x0 = xs[i]; y0 = ys[i]; r0 = ws[i] * 0.5
            x1 = xs[i + 1]; y1 = ys[i + 1]; r1 = ws[i + 1] * 0.5
            rm = max(r0, r1) + 1.0
            minx = max(int(math.floor(min(x0, x1) - rm)), 0)
            maxx = min(int(math.ceil(max(x0, x1) + rm)), W - 1)
            miny = max(int(math.floor(min(y0, y1) - rm)), 0)
            maxy = min(int(math.ceil(max(y0, y1) + rm)), H - 1)
            dx = x1 - x0; dy = y1 - y0
            l2 = dx * dx + dy * dy
            for py in range(miny, maxy + 1):
                fy = py + 0.5
                for px in range(minx, maxx + 1):
                    fx = px + 0.5
                    if l2 > 1e-9:
                        t = ((fx - x0) * dx + (fy - y0) * dy) / l2
                        if t < 0.0:
                            t = 0.0
                        elif t > 1.0:
                            t = 1.0
                    else:
                        t = 0.0
                    qx = x0 + t * dx - fx; qy = y0 + t * dy - fy
                    dist = math.sqrt(qx * qx + qy * qy)
                    r = r0 + (r1 - r0) * t
                    cov = r - dist + 0.5
                    if cov <= 0.0:
                        continue
                    if cov > 1.0:
                        cov = 1.0
                    if r < 0.5:      # thin lines get lighter instead of thinner
                        cov *= r * 2.0
                    if cov > acc[py, px]:
                        acc[py, px] = cov


def draw_strokes(shape, strokes):
    """strokes: list of (pts (n,2) float32 x,y, widths (n,) float32). Returns coverage (H,W)."""
    acc = np.zeros(shape, np.float32)
    if not strokes:
        return acc
    xs = np.concatenate([s[0][:, 0] for s in strokes]).astype(np.float32)
    ys = np.concatenate([s[0][:, 1] for s in strokes]).astype(np.float32)
    ws = np.concatenate([s[1] for s in strokes]).astype(np.float32)
    lens = np.array([len(s[0]) for s in strokes])
    starts = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    _stroke_segments(acc, xs, ys, ws, starts)
    return acc


def chains_to_strokes(chains, widths, rng, smooth_sigma=1.6, step=2.0, corner_deg=60.0,
                      taper_px=12.0, wob_amp=0.45, wob_wl=36.0, width_fn=None, var=0.18):
    """Turn traced chains into stroke polylines with pressure.

    widths: dict class -> base width in px (render scale)
    width_fn: optional f(pts, cls) -> per-point multiplier (e.g. heavier in shadow)
    """
    out = []
    for p, k in chains:
        if k not in widths:
            continue
        q = smooth_chain(p, smooth_sigma)
        for seg in split_corners(q, corner_deg):
            seg = resample(seg, step)
            if len(seg) < 2:
                continue
            L = float(np.sum(np.sqrt(np.sum(np.diff(seg, axis=0) ** 2, -1))))
            if L < 2.5:
                continue
            seg = wobble(seg, rng, wob_amp, wob_wl)
            w = widths[k] * pressure_profile(len(seg), L, rng, taper_px, var)
            if width_fn is not None:
                w = w * width_fn(seg, k)
            out.append((seg, w.astype(np.float32), k))
    return out
