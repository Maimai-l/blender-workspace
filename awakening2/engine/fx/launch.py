"""launch.py - smear frames, impact frames and speed lines for the launch.

    smear_stretch(cel, motion)      robot cel stretched along its motion with a streaked tail
    smear_multi(cel, motion, n)     multiple-image smear (afterimages flattening toward the tail)
    impact_frame(h, w, cel, ...)    2-tone graphic frame (black/gold, inverted ...) with radial
                                    lines; the robot silhouette is posterized and haloed
    speed_lines(canvas, centre)     radial focus lines (wedges from the frame edge inward)
    streak_lines(canvas, direction) parallel speed streaks across the frame

`cel` is the robot drawing as a straight-alpha RGBA float32 image (any size, usually the full
frame with the robot where it is on screen); results are new RGBA images of the same size.
"""
import math

import cv2
import numpy as np
from numba import njit

from . import core, palettes
from .core import PolyBatch, held

TAU = 2 * math.pi


@njit(cache=True, fastmath=True)
def _row_smear(src, L, flat, flatk, out):
    """Motion is +x: pixels behind (smaller x) the trailing edge of each row get the colour
    of that edge for L[y] px, flattening toward `flat` along the tail."""
    h, w = src.shape[0], src.shape[1]
    for y in range(h):
        Ly = L[y]
        last = -1
        cr = 0.0
        cg = 0.0
        cb = 0.0
        for x in range(w - 1, -1, -1):
            a = src[y, x, 3]
            if a >= 0.5:
                last = x
                cr = src[y, x, 0]
                cg = src[y, x, 1]
                cb = src[y, x, 2]
                for c in range(4):
                    out[y, x, c] = src[y, x, c]
                continue
            if last >= 0 and Ly > 0:
                dist = last - x
                if dist <= Ly + 1:
                    k = dist / Ly
                    if k > 1.0:
                        k = 1.0
                    m = k * flatk
                    sa = Ly - dist + 0.5
                    if sa > 1.0:
                        sa = 1.0
                    if sa < 0.0:
                        sa = 0.0
                    ar = cr * (1 - m) + flat[0] * m
                    ag = cg * (1 - m) + flat[1] * m
                    ab = cb * (1 - m) + flat[2] * m
                    # under any partial source alpha
                    oa = a + sa * (1 - a)
                    if oa > 1e-6:
                        out[y, x, 0] = (src[y, x, 0] * a + ar * sa * (1 - a)) / oa
                        out[y, x, 1] = (src[y, x, 1] * a + ag * sa * (1 - a)) / oa
                        out[y, x, 2] = (src[y, x, 2] * a + ab * sa * (1 - a)) / oa
                    out[y, x, 3] = oa
                    continue
            for c in range(4):
                out[y, x, c] = src[y, x, c]


def _streak_profile(n, name, frame, length, density=1.0, ss=2):
    g = core.rng('smear', name, frame)
    y = np.arange(n, dtype=np.float64) / ss
    v = np.zeros(n)
    for k in range(5):
        f = g.uniform(0.02, 0.09) * density
        v += np.abs(np.sin(y * f + g.uniform(0, TAU))) ** g.uniform(0.6, 1.4) / (1 + 0.4 * k)
    v /= v.max() + 1e-9
    # cut into distinct streaks: some rows short
    gate = 0.35 + 0.65 * (np.sin(y * 0.11 * density + g.uniform(0, TAU)) > -0.3)
    return length * ss * (0.3 + 0.7 * v ** 1.2) * gate


def _flat_colour(cel):
    a = cel[..., 3] > 0.5
    if not a.any():
        return np.array([0.3, 0.3, 0.35], np.float32)
    c = cel[..., :3][a]
    lum = c @ np.array([0.3, 0.59, 0.11], np.float32)
    return c[lum <= np.median(lum)].mean(0).astype(np.float32)


def _sample(img, pts):
    """Bilinear sample an (h, w, c) image at float points (n, 2) -> (n, c)."""
    h, w = img.shape[:2]
    x = np.clip(pts[:, 0] - 0.5, 0, w - 1.001)
    y = np.clip(pts[:, 1] - 0.5, 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx_ = (x - x0)[:, None]
    fy_ = (y - y0)[:, None]
    return (img[y0, x0] * (1 - fx_) * (1 - fy_) + img[y0, x0 + 1] * fx_ * (1 - fy_)
            + img[y0 + 1, x0] * (1 - fx_) * fy_ + img[y0 + 1, x0 + 1] * fx_ * fy_)


def smear_stretch(cel, motion, stretch=0.35, tail=1.4, name='smear', frame=0, flatten=0.25,
                  flat=None, ss=2, density=1.0, streaks=True):
    """Stretched smear: the cel is stretched along `motion` (dx, dy px, the direction of travel)
    from its leading edge, keeping its own colours, and tapered speed streaks in the robot's
    colours trail from its trailing edge for up to tail * |motion| px, thinning and fading.
    Returns a new straight RGBA image of the same size."""
    H0, W0 = cel.shape[:2]
    mv = np.asarray(motion, np.float64)
    mag = float(np.linalg.norm(mv))
    if mag < 1e-6 or not (cel[..., 3] > 0.5).any():
        return cel.copy()
    d = mv / mag
    n = np.array([-d[1], d[0]])
    ys, xs = np.nonzero(cel[..., 3] > 0.5)
    P = np.stack([xs + 0.5, ys + 0.5], 1)
    along = P @ d
    across = P @ n
    s_lead = float(along.max())
    ext_d = float(along.max() - along.min())
    # 1) stretch behind the leading edge (inverse map, premultiplied to keep clean edges)
    k = stretch / (1 + stretch)
    A = np.eye(2) - k * np.outer(d, d)
    off = d * s_lead * k
    M = np.hstack([A, off[:, None]]).astype(np.float64)
    pm = cel.copy()
    pm[..., :3] *= pm[..., 3:4]
    st = cv2.warpAffine(pm, M, (W0, H0), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                        borderValue=(0, 0, 0, 0))
    a = st[..., 3:4]
    st[..., :3] = np.where(a > 1e-6, st[..., :3] / np.maximum(a, 1e-6), 0)
    out = np.zeros_like(cel)
    if streaks:
        # 2) speed streaks from the trailing edge, in the colours found there
        g = core.rng('smear', name, frame)
        body = cel[..., :3][cel[..., 3] > 0.5]
        lum = body @ np.array([0.3, 0.59, 0.11], np.float32)
        meanc = body[lum >= np.quantile(lum, 0.3)].mean(0).astype(np.float32)   # body colour, no ink
        flatc = meanc if flat is None else np.asarray(flat, np.float32)
        a_lo, a_hi = float(across.min()), float(across.max())
        N = int(max(6, (a_hi - a_lo) / 9.0 * density))
        N = min(N, 60)
        offs = np.sort(g.uniform(a_lo + 2, a_hi - 2, N))
        s_back = s_lead - ext_d * (1 + stretch) - 4
        steps = np.arange(s_back, s_lead + 2, 2.0)
        b = PolyBatch()
        wmax = max(2.0, (a_hi - a_lo) * 0.045)
        for o in offs:
            line = (n * o)[None, :] + d[None, :] * steps[:, None]
            al = _sample(st[..., 3:4], line)[:, 0]
            inside = np.nonzero(al > 0.5)[0]
            if len(inside) == 0:
                continue
            i0 = inside[0]                                   # trailing-most body pixel on the line
            pt = line[i0]
            depth_in = min(ext_d * 0.12 + 6.0, 40.0)
            col = _sample(st[..., :3], (pt + d * depth_in)[None, :])[0]
            if float(col @ np.array([0.3, 0.59, 0.11])) < 0.6 * float(meanc @ np.array([0.3, 0.59, 0.11])):
                col = meanc                                   # landed on ink / a crevice: use the body
            col = col * (1 - flatten) + flatc * flatten
            L = tail * mag * g.uniform(0.3, 1.0) * (0.6 + 0.4 * math.sin(o * 0.05 + frame))
            wd = wmax * g.uniform(0.35, 1.0)
            # three pieces of decreasing opacity -> a fading, tapering streak
            for j, (s0, s1, alp) in enumerate(((0.0, 0.42, 0.95), (0.42, 0.75, 0.65), (0.75, 1.0, 0.35))):
                q = np.linspace(s0, s1, 4)
                pts = pt[None, :] + d[None, :] * 6.0 - d[None, :] * (q[:, None] * (L + 6.0))
                wid = wd * (1 - q) ** 1.1 + 0.3
                b.add(core.stroke_poly(pts, wid), col, alpha=alp)
        if len(b):
            b.draw(out)
    core.over(out, st)
    return np.clip(out, 0, 1).astype(np.float32)


def smear_multi(cel, motion, n=3, spacing=1.0, flat=None, ghost_alpha=(0.55, 0.85), tail=0.5,
                name='smear_multi', frame=0):
    """Multiple-image smear: n-1 afterimages behind the cel along -motion (flattened toward
    one colour and partly transparent), short streaks joining them, the cel on top."""
    H0, W0 = cel.shape[:2]
    mv = np.asarray(motion, np.float64) * spacing
    ys, xs = np.nonzero(cel[..., 3] > 0.02)
    if len(xs) == 0:
        return cel.copy()
    mag = float(np.linalg.norm(mv))
    P = mag * (1 + tail * 1.2) + 16
    tr = -mv / max(mag, 1e-9)
    bx0 = int(max(0, xs.min() - 16 - P * max(0.0, -tr[0])))
    bx1 = int(min(W0, xs.max() + 17 + P * max(0.0, tr[0])))
    by0 = int(max(0, ys.min() - 16 - P * max(0.0, -tr[1])))
    by1 = int(min(H0, ys.max() + 17 + P * max(0.0, tr[1])))
    sub = cel[by0:by1, bx0:bx1]
    h, w = sub.shape[:2]
    flatc = _flat_colour(cel) if flat is None else np.asarray(flat, np.float32)
    out = np.zeros_like(sub)
    pm = sub.copy()
    pm[..., :3] *= pm[..., 3:4]
    for i in range(n - 1, 0, -1):
        off = -mv * i / max(n - 1, 1)
        M = np.array([[1, 0, off[0]], [0, 1, off[1]]], np.float64)
        sh = cv2.warpAffine(pm, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
        a = sh[..., 3:4]
        col = np.where(a > 1e-6, sh[..., :3] / np.maximum(a, 1e-6), 0)
        k = i / max(n - 1, 1)
        col = col * (1 - 0.75 * k) + flatc * 0.75 * k
        al = ghost_alpha[1] + (ghost_alpha[0] - ghost_alpha[1]) * k
        ghost = np.concatenate([col, a * al], -1).astype(np.float32)
        core.over(out, ghost)
    if tail > 0:
        st = smear_stretch(sub, mv, stretch=0.0, tail=tail, name=name, frame=frame, flat=flatc)
        core.over(out, st, opacity=0.9)
    core.over(out, sub)
    full = np.zeros_like(cel)
    full[by0:by1, bx0:bx1] = out
    return full


def speed_lines(canvas, centre, frame, n=90, inner=(0.28, 0.55), width=(2.0, 14.0), colour=None,
                alpha=1.0, on=2, name='focus', clear=None, length=None):
    """Radial focus lines: thin wedges from beyond the frame edge toward `centre`, stopping at
    a random fraction (inner) of the half-diagonal; `clear` = (rx, ry) keeps an ellipse free."""
    H, W = canvas.shape[:2]
    col = palettes.INK if colour is None else np.asarray(colour, np.float32)
    g = core.rng('speedlines', name, held(frame, on))
    cx, cy = centre
    Rf = math.hypot(max(cx, W - cx), max(cy, H - cy)) + 20
    Dn = math.hypot(W, H) * 0.5
    b = PolyBatch()
    angs = np.sort(g.uniform(0, TAU, n))
    for a in angs:
        r_in = Dn * g.uniform(inner[0], inner[1])
        if clear is not None:
            ca, sa = math.cos(a), math.sin(a)
            rc = 1.0 / math.sqrt((ca / clear[0]) ** 2 + (sa / clear[1]) ** 2)
            r_in = max(r_in, rc)
        r_out = Rf if length is None else r_in + length * g.uniform(0.6, 1.2)
        wd = g.uniform(width[0], width[1]) * (r_out / Rf)
        half = wd / 2 / max(r_out, 1)
        p0 = (cx + math.cos(a) * r_in, cy + math.sin(a) * r_in)
        p1 = (cx + math.cos(a - half) * r_out, cy + math.sin(a - half) * r_out)
        p2 = (cx + math.cos(a + half) * r_out, cy + math.sin(a + half) * r_out)
        b.add(np.array([p0, p1, p2]), col, alpha=alpha)
    b.draw(canvas)
    return canvas


def streak_lines(canvas, direction, frame, n=40, length=(200.0, 700.0), width=(1.5, 6.0),
                 colour=None, alpha=0.85, on=1, name='streaks', region=None, speed=120.0):
    """Parallel speed streaks along `direction` (screen), tapered both ends, re-drawn on `on`s
    and moving `speed` px per frame along the direction."""
    H, W = canvas.shape[:2]
    col = palettes.WIND_LINE if colour is None else np.asarray(colour, np.float32)
    d = core.unit(direction)
    nrm = np.array([-d[1], d[0]])
    fh = held(frame, on)
    g = core.rng('streaks', name)
    x0, y0, x1, y1 = (0, 0, W, H) if region is None else region
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    span_n = abs((x1 - x0) * nrm[0]) + abs((y1 - y0) * nrm[1])
    span_d = abs((x1 - x0) * d[0]) + abs((y1 - y0) * d[1])
    b = PolyBatch()
    for i in range(n):
        off = (g.random() - 0.5) * span_n
        L = g.uniform(*length)
        wd = g.uniform(*width)
        ph = g.uniform(0, span_d + L)
        s = ((ph + speed * fh) % (span_d + L)) - (span_d + L) / 2
        p = c + nrm * off + d * s
        q = np.linspace(-0.5, 0.5, 6)
        pts = p[None, :] + d[None, :] * (q[:, None] * L)
        b.add(core.stroke_poly(pts, wd * np.sin(np.pi * (q + 0.5)) ** 0.6 + 0.2), col, alpha=alpha)
    b.draw(canvas)
    return canvas


def clean_shape(mask, close=6.0, min_area=900.0, hole_area=2500.0, smooth=2.0, keep=None):
    """A designed silhouette from a raw mask: close small gaps, fill small holes, drop specks,
    smooth the outline; keep only the `keep` largest pieces if given.  Returns bool."""
    m = mask.astype(np.uint8)
    r = int(round(close))
    if r > 0:
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1,) * 2))
    # fill holes below hole_area
    inv = (1 - m).astype(np.uint8)
    nl, lab, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=4)
    h, w = m.shape
    for i in range(1, nl):
        x, y, bw, bh, area = stats[i]
        touches = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        if area < hole_area and not touches:
            m[lab == i] = 1
    # drop specks below min_area, keep the largest pieces
    nl, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    order = np.argsort(-areas) + 1
    good = [i for i in order if stats[i, cv2.CC_STAT_AREA] >= min_area]
    if keep is not None:
        good = good[:keep]
    m = np.isin(lab, good).astype(np.float32) if good else np.zeros_like(m, np.float32)
    if smooth > 0:
        m = cv2.GaussianBlur(m, (0, 0), smooth)
    return m > 0.5


def impact_frame(h, w, cel=None, centre=None, mode='black_gold', frame=0, n_lines=120,
                 inner=(0.18, 0.42), halo=None, detail=0.5, name='impact', burst=True, max_open=6):
    """A 2-tone graphic impact frame (opaque RGBA).

    mode: 'black_gold' (gold field, black lines and figure), 'gold_black', 'inverted'
    (paper-white field, black figure), 'red_black'.  The cel's silhouette is drawn in the
    figure colour with its darker half posterized inside (so it reads as the robot, not a
    blob), separated from the lines by a halo in the field colour."""
    field, figure = palettes.IMPACT[mode]
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = field
    out[..., 3] = 1
    k = w / 1920.0
    if centre is None:
        if cel is not None and (cel[..., 3] > 0.5).any():
            ys, xs = np.nonzero(cel[..., 3] > 0.5)
            centre = (float(xs.mean()), float(ys.mean()))
        else:
            centre = (w / 2, h / 2)
    halo = 9 * k if halo is None else halo
    lines = core.new_canvas(h, w)
    speed_lines(lines, centre, frame, n=n_lines, inner=inner, width=(3 * k, 26 * k), colour=figure,
                on=1, name=name)
    if burst:
        # a ring of heavy spikes close around the figure
        g = core.rng('impact_burst', name, frame)
        b = PolyBatch()
        for a in np.sort(g.uniform(0, TAU, 26)):
            r0 = math.hypot(w, h) * g.uniform(0.11, 0.2)
            r1 = r0 + math.hypot(w, h) * g.uniform(0.05, 0.16)
            wd = g.uniform(0.03, 0.07)
            cx, cy = centre
            b.add(np.array([(cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                            (cx + math.cos(a - wd) * r1, cy + math.sin(a - wd) * r1),
                            (cx + math.cos(a + wd) * r1 * 1.08, cy + math.sin(a + wd) * r1 * 1.08),
                            (cx + math.cos(a + wd * 0.3) * r1, cy + math.sin(a + wd * 0.3) * r1)]), figure)
        b.draw(lines)
    a = lines[..., 3:4]
    out[..., :3] = out[..., :3] * (1 - a) + lines[..., :3] * a
    if cel is not None:
        sil = clean_shape(cel[..., 3] > 0.5, close=6 * k, min_area=900 * k * k, hole_area=2500 * k * k,
                          smooth=2.2 * k)
        if sil.any():
            rr = max(1, int(round(halo)))
            ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1))
            hal = cv2.dilate(sil.astype(np.uint8), ker)
            hal_s = cv2.GaussianBlur(hal.astype(np.float32), (0, 0), 1.0)
            out[..., :3] = out[..., :3] * (1 - hal_s[..., None]) + field * hal_s[..., None]
            # open-ups: only the brightest few shapes (eyes, core, a lit rim), cleaned and smoothed
            lum = cel[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
            inside = sil & (cel[..., 3] > 0.5)
            opens = np.zeros_like(sil)
            if inside.any():
                thr = max(np.quantile(lum[inside], 0.97 - 0.06 * detail), 0.55)
                er = cv2.erode(sil.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(8 * k) | 1,) * 2)) > 0
                cand = (lum > thr) & er
                cand = clean_shape(cand, close=3 * k, min_area=250 * k * k, hole_area=400 * k * k,
                                   smooth=1.5 * k, keep=max_open)
                opens = cand & er
            fig = cv2.GaussianBlur(sil.astype(np.float32), (0, 0), 0.7)
            lp = cv2.GaussianBlur(opens.astype(np.float32), (0, 0), 0.7)
            col = figure[None, None, :] * (1 - lp[..., None]) + field[None, None, :] * lp[..., None]
            out[..., :3] = out[..., :3] * (1 - fig[..., None]) + col * fig[..., None]
    return out
