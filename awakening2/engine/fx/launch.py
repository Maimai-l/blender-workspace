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


def smear_stretch(cel, motion, stretch=0.35, tail=1.4, name='smear', frame=0, flatten=0.55,
                  flat=None, ss=2, density=1.0):
    """Stretched smear: the cel is stretched along `motion` (dx, dy px, the direction of
    travel), anchored at its leading edge, and its trailing edge is pulled into streaks of
    varied length (tail * |motion| px).  Returns a new straight RGBA image."""
    H0, W0 = cel.shape[:2]
    mv = np.asarray(motion, np.float64)
    mag = float(np.linalg.norm(mv))
    if mag < 1e-6:
        return cel.copy()
    ys, xs = np.nonzero(cel[..., 3] > 0.02)
    if len(xs) == 0:
        return cel.copy()
    ext = max(xs.max() - xs.min(), ys.max() - ys.min())
    P = tail * mag * 1.15 + stretch * ext + 16
    tr = -mv / mag                                     # streaks and stretch go behind the motion
    bx0 = int(max(0, xs.min() - 16 - P * max(0.0, -tr[0])))
    bx1 = int(min(W0, xs.max() + 17 + P * max(0.0, tr[0])))
    by0 = int(max(0, ys.min() - 16 - P * max(0.0, -tr[1])))
    by1 = int(min(H0, ys.max() + 17 + P * max(0.0, tr[1])))
    if math.hypot(bx1 - bx0, by1 - by0) * ss > 3600:
        ss = 1
    full = np.zeros_like(cel)
    full[by0:by1, bx0:bx1] = _smear_crop(cel[by0:by1, bx0:bx1], mv, mag, stretch, tail, name, frame,
                                          flatten, flat if flat is not None else _flat_colour(cel), ss, density)
    return full


def _smear_crop(cel, mv, mag, stretch, tail, name, frame, flatten, flat, ss, density):
    h, w = cel.shape[:2]
    ang = math.degrees(math.atan2(mv[1], mv[0]))
    D = int(math.ceil(math.hypot(h, w))) + 8
    big = D * ss
    # rotate so the motion is +x, supersampled
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    M[:, 2] += (D - w) / 2, (D - h) / 2
    S = np.array([[ss, 0, 0], [0, ss, 0]], np.float64)
    M3 = np.vstack([M, [0, 0, 1]])
    Mf = S @ M3
    pm = cel.copy()
    pm[..., :3] *= pm[..., 3:4]
    rot = cv2.warpAffine(pm, Mf, (big, big), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = rot[..., 3:4]
    rot[..., :3] = np.where(a > 1e-6, rot[..., :3] / np.maximum(a, 1e-6), 0)
    # stretch along x about the leading edge
    cols = np.nonzero((rot[..., 3] > 0.5).any(0))[0]
    if len(cols) == 0:
        return cel.copy()
    xl = float(cols.max())
    k = 1 + stretch
    Mst = np.array([[1 / k, 0, xl * (1 - 1 / k)], [0, 1, 0]], np.float64)
    rot = cv2.warpAffine(rot, Mst, (big, big), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                         borderValue=(0, 0, 0, 0))
    L = _streak_profile(big, name, frame, tail * mag, density, ss)
    flatc = np.asarray(flat, np.float32)
    out = np.zeros_like(rot)
    _row_smear(np.ascontiguousarray(rot, dtype=np.float32), L, flatc, float(flatten), out)
    out[..., :3] *= out[..., 3:4]
    if ss > 1:
        out = cv2.resize(out, (big // ss, big // ss), interpolation=cv2.INTER_AREA)
    back = cv2.warpAffine(out, cv2.invertAffineTransform(M), (w, h), flags=cv2.INTER_LINEAR,
                          borderValue=(0, 0, 0, 0))
    a = back[..., 3:4]
    back[..., :3] = np.where(a > 1e-6, back[..., :3] / np.maximum(a, 1e-6), 0)
    return np.clip(back, 0, 1).astype(np.float32)


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


def impact_frame(h, w, cel=None, centre=None, mode='black_gold', frame=0, n_lines=120,
                 inner=(0.18, 0.42), halo=None, detail=0.5, name='impact', burst=True):
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
        sil = (cel[..., 3] > 0.5).astype(np.uint8)
        if sil.any():
            rr = max(1, int(round(halo)))
            ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rr + 1, 2 * rr + 1))
            hal = cv2.dilate(sil, ker)
            hal_s = cv2.GaussianBlur(hal.astype(np.float32), (0, 0), 0.8)
            out[..., :3] = out[..., :3] * (1 - hal_s[..., None]) + field * hal_s[..., None]
            lum = cel[..., :3] @ np.array([0.3, 0.59, 0.11], np.float32)
            inside = sil > 0
            lo, hi = np.quantile(lum[inside], 0.05), np.quantile(lum[inside], 0.98)
            thr = max(np.quantile(lum[inside], 0.6 + 0.3 * (1 - detail)), lo + 0.55 * (hi - lo) + 0.03)
            dark = (lum <= thr) & inside
            # clean the posterized shapes (designed, no speckle)
            dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_OPEN,
                                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
            fig = cv2.GaussianBlur(cel[..., 3].astype(np.float32), (0, 0), 0.6)
            body = np.clip(fig, 0, 1)
            # figure: silhouette in the figure colour, lit (light) parts in the field colour
            # inset from the outline so the outline holds the shape
            er = cv2.erode(sil, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * max(1, int(3 * k)) + 1,) * 2))
            light_parts = (er > 0) & (dark == 0)
            lp = cv2.GaussianBlur(light_parts.astype(np.float32), (0, 0), 0.7)
            col = figure[None, None, :] * (1 - lp[..., None]) + field[None, None, :] * lp[..., None]
            out[..., :3] = out[..., :3] * (1 - body[..., None]) + col * body[..., None]
    return out
