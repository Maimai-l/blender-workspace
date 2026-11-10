"""dust.py - drawn cel dust: impact puffs, rolling ground dust and small puff trails.

A dust cloud is a set of *primary lobes* (each with a trajectory, growth and break-up
time).  Every primary carries 3-5 *sub-lobes* that orbit it (the bumps on the outline
travel round = the cloud rolls) and drift apart when it breaks up.  Sub-lobes sit behind
their primary and take their tones from the primary's *tone disc*, so one billow reads as
one bumpy mass with one designed light/shadow shape; different primaries overlap with tone
changes (no internal lines).  The silhouette gets a tapered colour line on the shadow side.
Late in life the primaries shrink, their bumps separate, bites open, and the pieces shrink
away at staggered times.
"""
import math

import numpy as np

from . import core, palettes, shapes
from .core import Layer, cut_holes, ease_out, held, smoothstep

TAU = 2 * math.pi


def shade_params(tx, ty, centre, size, light, bias=0.0, vert=0.45, contrast=1.0):
    """Lit-cap depth `tl` and shadow-crescent depth `ts` (fractions of r) for discs, from where
    each disc sits in its cloud.  Values are 0 or at least ~1/3 (no thin slivers)."""
    l = core.unit(light)
    tx = np.asarray(tx, np.float64)
    ty = np.asarray(ty, np.float64)
    e = ((tx - centre[0]) * l[0] + (ty - centre[1]) * l[1]) / size
    e = (e - vert * (ty - centre[1]) / size) * contrast + bias
    tl = 0.30 + 1.0 * e
    ts = 0.48 - 1.15 * e
    tl = np.where(tl < 0.30, 0.0, np.clip(tl, 0.40, 1.5))
    ts = np.where(ts < 0.28, 0.0, np.clip(ts, 0.38, 1.9))
    return tl, ts


# bump sizes cycle big / small / medium so neighbouring lobes never match
_PATTERN = np.array([1.0, 0.38, 0.72, 0.27, 0.9, 0.5, 0.33, 0.8, 0.44])


class _Billow:
    """Shared machinery: primaries -> designed billows (one mass + bumps of strongly varied size,
    small squashed bumps at the base, a hook-shaped curl on the leading side, flat ground cut,
    occasional thin wisps) and late break-up bites."""

    def __init__(self, name, n, sub=(4, 7)):
        g = core.rng('billow', name)
        m = sub[1]
        self.nsub = g.integers(sub[0], sub[1] + 1, n)
        base = g.uniform(0, TAU, (n, 1))
        self.sphi = base + np.arange(m)[None, :] * (TAU / m) + g.uniform(-0.35, 0.35, (n, m))
        self.su0 = g.uniform(0, 1, (n, 1)) + np.arange(m)[None, :] / m          # slots on the top arc
        start = g.integers(0, len(_PATTERN), n)
        self.su = 0.64 * _PATTERN[(start[:, None] + np.arange(m)[None, :]) % len(_PATTERN)] \
            * g.uniform(0.85, 1.15, (n, m))
        self.sp = g.uniform(0.38, 0.62, (n, m))     # how far each bump sticks out (x its r)
        self.sq = g.uniform(0.74, 1.0, (n, m))      # bump squash
        self.sang = g.uniform(0, TAU, (n, m))
        self.send = g.uniform(0.80, 1.0, (n, m))
        self.wp = g.uniform(0, TAU, (n, m + 2))
        self.hole_on = np.zeros(n, bool)          # break-up by shrinking / separating, no holes
        self.hole_ang = g.uniform(0, TAU, n)
        self.hole_k = g.uniform(0.55, 0.8, n)
        self.hook_on = g.random(n) < 0.75
        self.hook_k = g.uniform(0.36, 0.5, n)
        self.hook_up = g.uniform(0.15, 0.45, n)
        self.wisp_on = g.random(n) < 0.45
        self.wisp_c = g.uniform(-1, 1, n)
        self.m = m
        # cauliflower crown for grounded billows: 6-10 lobe slots per billow, each a size class
        # (2-3 big, the rest medium / small, neighbours alternating) that buds at the top centre,
        # rolls outward and down its side and is absorbed at the base
        mc = 10
        self.ncrown = g.integers(6, 11, n)
        cls = np.array([0.48, 0.2, 0.34, 0.16, 0.44, 0.26, 0.36, 0.18, 0.42, 0.28])
        shift = g.integers(0, mc, n)
        self.csize = cls[(shift[:, None] + np.arange(mc)[None, :]) % mc] * g.uniform(0.88, 1.12, (n, mc))
        self.cu0 = ((np.arange(mc)[None, :] // 2) + g.uniform(0.1, 0.9, (n, mc))) / 5.0
        self.cwp = g.uniform(0, TAU, (n, mc))
        self.csq = g.uniform(0.8, 1.0, (n, mc))
        self.mc = mc

    def build(self, idx, px, py, R, brk, phase, z, wob, drawing, ground=None, lead=None,
              wisps=False):
        """Groups [(z, lobes, r0, i, ground_y)] (lobes: cx cy r wp sx sy ang bx by br), bites, and
        optional wisps [(polyline, widths, tone)]."""
        groups, holes, wl = [], [], []
        n = len(idx)
        gr = None if ground is None else np.broadcast_to(np.asarray(ground, np.float64), (n,))
        for j, i in enumerate(idx):
            r0 = R[j]
            if r0 < 0.6:
                continue
            b = brk[j]
            x0 = px[j]
            y0 = py[j]
            gj = None if gr is None else float(gr[j])
            if gj is not None:
                y0 = min(y0, gj - r0 * 0.42)
            core_r = r0 * (1 - 0.88 * b ** 1.4)
            wpd = drawing * 0.8
            near_ground = gj is not None and y0 + r0 > gj - 2
            lobes = []
            ld = None
            if lead is not None:
                ld = np.asarray(lead[j], np.float64)
                nl = float(np.hypot(ld[0], ld[1]))
                ld = ld / nl if nl > 1e-9 else None
            crown = r0 > 3.0                       # grounded: crown on top; airborne: all round
            air = not near_ground
            if core_r > 0.6:
                # the main mass: flattened and widened where it sits on the ground; with a crown
                # it is shape-only, so its tones (and the scalloped terminator) come from the lobes
                lobes.append((x0, y0, core_r * (0.86 if crown else 1.0), self.wp[i, 0] + wpd,
                              1.14 if near_ground else 1.0, 0.84 if near_ground else 1.0, 0.0, 0, 0, 0,
                              0.0 if (crown and b < 0.4) else 1.0))
            if crown:
                cr = core_r * 0.86
                roll = abs(phase[j]) / TAU * 1.4
                # a standing central lobe at the top keeps the crown closed where new lobes bud
                rc = r0 * 0.38 * (1 - 0.4 * b)
                lobes.append((x0 + cr * 0.08, y0 - cr * 0.84 * 0.62, rc, self.wp[i, 2] + wpd, 1.08, 0.92, 0.0,
                              0, 0, 0, 1.0))
                for k in range(min(self.ncrown[i], 3 + int(r0 / 16.0))):     # small billows: fewer lobes
                    side = 1.0 if k % 2 == 0 else -1.0
                    u = (self.cu0[i, k] + roll) % 1.0
                    # bud at the top centre -> full size -> absorbed at the base corner
                    grow = (0.22 + 0.78 * smoothstep(0.0, 0.32, u)) * (1 - 0.75 * smoothstep(0.8, 1.0, u))
                    sr = r0 * self.csize[i, k] * grow * (1 - 0.35 * b)
                    if sr < max(0.6, 3.5):            # no speckle-sized lobes
                        continue
                    if air:
                        ang = -math.pi / 2 + side * (0.12 + u * (math.pi - 0.24))
                        sr *= (0.8 + 0.3 * max(0.0, -math.sin(ang)))     # bigger on top, smaller below
                    else:
                        ang = -math.pi / 2 + side * (0.12 + u * (math.pi / 2 + 0.25))
                    ca, sa = math.cos(ang), math.sin(ang)
                    ex, ey = (1.0, 1.0) if air else (1.14, 0.84)
                    re = cr / math.sqrt((ca / ex) ** 2 + (sa / ey) ** 2)     # core edge at ang
                    rho = re - sr * 0.3 + 0.6 * b ** 1.3 * r0
                    bx = x0 + rho * ca
                    by = y0 + rho * sa
                    if not air:
                        by = min(by, gj - sr * 0.45)
                    low = math.sin(ang) > -0.2 or sr < 0.3 * r0   # low or small lobes: no lit cap (no spots)
                    lobes.append((bx, by, sr, self.cwp[i, k] + wpd * 1.3, 1.0, self.csq[i, k], ang, 0, 0, 0,
                                  0.5 if low else 1.0))
                # belly lobes inside the mass (shade only, no lit cap): the mid tone reaches down
                # and the violet underside ends in a scalloped edge instead of one big arc
                shrink = (1 - 0.95 * b ** 1.2)
                for kb, tb in enumerate((-0.74, -0.3, 0.12, 0.58) if r0 > 30 else (-0.4, 0.4)):
                    rb = r0 * (0.36, 0.22, 0.31, 0.25)[(kb + i) % 4] * shrink
                    if rb < 0.8:
                        continue
                    lobes.append((x0 + (tb + 0.08 * math.sin(i * 1.7 + kb)) * cr,
                                  y0 + cr * (0.06 + 0.1 * ((kb + i) % 3)), rb, self.wp[i, 1] + kb + wpd,
                                  1.0, 0.9, 0.0, 0, 0, 0, 0.5))
                # a lumpy skirt: two small squashed lobes at the base corners (borrowed tones)
                for side in ((-1.0, 1.0) if (not air and r0 > 20) else ()):
                    sr = r0 * (0.3 if side > 0 else 0.22) * shrink
                    if sr < 0.8:
                        continue
                    lobes.append((x0 + side * cr * 0.95, gj - sr * 0.5, sr, self.wp[i, 1] + side + wpd,
                                  1.3, 0.62, 0.0, 0, 0, 0, 0.0))
            nb = 0 if crown else self.nsub[i] + (2 if near_ground else 0)
            for k in range(min(nb, self.m)):
                arcw = 1.0
                if near_ground:
                    # grounded billows: the bumps roll over the top arc (a cauliflower crown),
                    # swelling in at the back and shrinking away at the front
                    u = (self.su0[i, k] + phase[j] / TAU) % 1.0
                    ph = -math.pi / 2 + (u - 0.5) * 2.9 * (1 if (lead is None or lead[j][0] >= 0) else -1)
                    arcw = math.sin(math.pi * u) ** 0.6
                else:
                    ph = self.sphi[i, k] + phase[j]
                fade = (1 - smoothstep(self.send[i, k] - 0.35, self.send[i, k], b)) * arcw
                top = -math.sin(ph)                         # +1 at the top of the billow
                sr = r0 * self.su[i, k] * (1 - 0.3 * b) * fade * (0.72 + 0.38 * max(top, -0.3))
                if sr < 0.6:
                    continue
                rho = max(0.15 * r0, r0 * (1 - 0.88 * b ** 1.4) - sr * (1 - self.sp[i, k])) + 0.8 * b ** 1.3 * r0
                bx = x0 + rho * math.cos(ph)
                by = y0 + rho * math.sin(ph) * 0.9
                sq = self.sq[i, k]
                ang = self.sang[i, k]
                if gj is not None:
                    by = min(by, gj - sr * 0.3)
                    if top < -0.3:                          # base bumps: low and wide
                        sq = min(sq, 0.72)
                        ang = 0.0
                # small / base bumps borrow the mass's tones while the billow is whole;
                # once it breaks up the separating pieces shade themselves
                own = 1.0 if ((sr > 0.4 * r0 and top > -0.3) or b > 0.25) else 0.0
                lobes.append((bx, by, sr, self.wp[i, k + 1] + wpd, 1.0, sq, ang, 0, 0, 0, own))
            # hook-shaped curl on the leading side: a forward-leaning lobe with its lower front
            # bitten out, so its tip curls over and down like a breaking wave
            if ld is not None and self.hook_on[i] and b < 0.75 and abs(ld[0]) > 0.45 and r0 > 40:
                # only on edges moving sideways: the curl rolls over the leading side
                up = np.array([0.0, -1.0])
                fw = np.array([1.0 if ld[0] > 0 else -1.0, 0.0])
                hr = self.hook_k[i] * r0 * (1 - 0.6 * b)
                hc = np.array([x0, y0]) + fw * (r0 * 0.74) + up * (r0 * self.hook_up[i])
                ang = math.atan2(-0.35, fw[0])
                bc = hc + fw * (hr * 0.95) - up * (hr * 0.8)      # always notches the edge
                lobes.append((hc[0], hc[1], hr, self.wp[i, -1] + wpd, 1.15, 0.92, ang,
                              bc[0], bc[1], hr * 0.6, 1.0))
            if lobes:
                groups.append((z[j], lobes, r0, int(i), None if gj is None else gj + 1.5))
            if self.hole_on[i] and b > 0.35:
                hr = r0 * self.hole_k[i] * smoothstep(0.3, 0.85, b)
                if hr > max(1.5, 0.3 * r0):
                    a = self.hole_ang[i] + phase[j] * 0.3
                    holes.append((x0 + math.cos(a) * r0 * 1.05, y0 + math.sin(a) * r0 * 1.05,
                                  hr, wob * 2.0, self.wp[i, 0] * 1.3 + wpd))
            if wisps and ld is not None and abs(ld[0]) > 0.45 and r0 > 30 and b < 0.6 and self.hook_on[i]:
                # the leading edge curls over: a fat spiral lip in the lit tone
                fw = 1.0 if ld[0] > 0 else -1.0
                cx_ = x0 + fw * r0 * 0.78
                cy_ = y0 - r0 * 0.42
                th = np.linspace(-0.2, 3.6, 14)
                rad = r0 * 0.34 * (1 - 0.55 * th / 3.6) * (1 - 0.5 * b)
                pts = np.stack([cx_ + fw * np.sin(th) * rad, cy_ - np.cos(th) * rad], 1)
                wid = r0 * 0.2 * (1 - th / 3.7) ** 1.1 * (1 - 0.6 * b) + 0.4
                wl.append((pts, wid, 2))
            if wisps and self.wisp_on[i] and 0.2 < b < 0.95 and r0 > 4:
                back = -ld if ld is not None else np.array([self.wisp_c[i], 0.0])
                side = back[0] if abs(back[0]) > 0.3 else self.wisp_c[i]
                dw = np.array([side * 0.8, -0.75])          # wisps always rise and trail back
                dw = dw / max(np.linalg.norm(dw), 1e-9)
                pn = np.array([-dw[1], dw[0]])
                dw = dw / max(np.linalg.norm(dw), 1e-9)
                pn = np.array([-dw[1], dw[0]])
                L = r0 * (0.55 + 0.5 * b)
                s = np.linspace(0, 1, 11)
                st = np.array([x0, y0]) + dw * (r0 * 0.7)
                curl = (0.35 + 0.25 * self.wisp_c[i]) * L
                pts = st[None, :] + dw[None, :] * (s[:, None] * L) \
                    + pn[None, :] * (np.sin(s * math.pi * 1.6 + 0.4) * curl * s)[:, None]
                wid = r0 * 0.15 * np.sin(np.clip(s * 1.15, 0, 1) * math.pi) ** 0.8 * (1 - s) ** 0.6 * (1 - b) ** 0.5 + 0.3
                wl.append((pts, wid, 1 if self.wisp_c[i] < 0.3 else 2))
        if wisps:
            return groups, holes, wl
        return groups, holes


def paint_groups(canvas, groups, holes, palette, light, centre, size, line=2.5, wob=0.05,
                 opacity=1.0, bias=0.0, vert=0.45, contrast=1.0, layer=None, ref_r=None,
                 alpha=1.0, inner=0.0, local=0.0, group_bias=None, texture=0.0, tex_anchor=None,
                 tex_scale=1.0, wisps=None, tone_alpha=None):
    """Paint billow groups [(z, lobes, r0[, i[, ground_y]])] as one cel layer onto the canvas.

    lobes: rows (cx, cy, r, wp) or (cx, cy, r, wp, sx, sy, ang, bx, by, br).
    Shading comes from each lobe's place in the whole cloud (`centre`, `size`); `local` (0..1)
    blends in each lobe's place inside its own billow (for long walls of separate billows);
    `group_bias` (per group, same order as `groups`) brightens / darkens whole billows;
    `wisps` [(polyline, widths, tone 0..2)] are thin strands painted into the same cel."""
    if not groups:
        return canvas
    order = sorted(range(len(groups)), key=lambda i: groups[i][0])
    ref = ref_r if ref_r is not None else size * 0.35
    bb = core.BillowBatch()
    for gi in order:
        grp = groups[gi]
        z, discs, r0 = grp[:3]
        gy = grp[4] if len(grp) > 4 else None
        A = np.asarray([tuple(r) + (1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0) if len(r) == 4 else
                        (tuple(r) + (1.0,) if len(r) == 10 else tuple(r)) for r in discs], np.float64)
        gb = bias + (0.0 if group_bias is None else group_bias[gi])
        if local > 0:
            gc = (A[0, 0], A[0, 1])
            tl1, ts1 = shade_params(A[:, 0], A[:, 1], centre, size, light, gb, vert, contrast)
            tl2, ts2 = shade_params(A[:, 0], A[:, 1], gc, r0 * 2.4, light, gb, vert, contrast)
            tl = np.where((tl1 > 0) & (tl2 > 0), tl1 * (1 - local) + tl2 * local, np.maximum(tl1, tl2) * (1 - local) + tl2 * local)
            ts = ts1 * (1 - local) + ts2 * local
            tl = np.where(tl < 0.3, 0.0, np.maximum(tl, 0.4))
            ts = np.where(ts < 0.28, 0.0, np.maximum(ts, 0.38))
        else:
            tl, ts = shade_params(A[:, 0], A[:, 1], centre, size, light, gb, vert, contrast)
        if tone_alpha is not None and r0 < 0.55 * ref:
            tl = np.zeros_like(tl)          # translucent styles: lit crowns on the big billows only
        own = A[:, 10] > 0.25
        if not own.any():                 # broken-up remnants: every piece shades itself
            own[:] = True
        tl = np.where((A[:, 10] > 0.25) & (A[:, 10] < 0.75), 0.0, tl)     # 0.5: shade, no lit cap
        ts = np.where(own, ts, -1.0)
        D = np.stack([A[:, 0], A[:, 1], A[:, 2], np.full(len(A), wob), A[:, 3], ts, tl,
                      A[:, 4], A[:, 5], A[:, 6], A[:, 7], A[:, 8], A[:, 9]], 1)
        lw = line * float(np.clip(r0 / ref, 0.5, 1.3)) if line > 0 else 0.0
        li = inner * float(np.clip(r0 / ref, 0.4, 1.2)) if inner > 0 else 0.0
        bb.add(D, alpha=alpha, inner=li, line=lw, ground=gy)
    if layer is None:
        bx0, by0, bx1, by1 = bb.bbox()
        if wisps:
            allp = np.concatenate([w_[0] for w_ in wisps], 0)
            bx0, by0 = min(bx0, allp[:, 0].min() - 4), min(by0, allp[:, 1].min() - 4)
            bx1, by1 = max(bx1, allp[:, 0].max() + 4), max(by1, allp[:, 1].max() + 4)
        layer = Layer(canvas.shape, bx0, by0, bx1, by1)
    if wisps:
        # wisps go under the billows so they grow out of the mass
        pb = core.PolyBatch()
        for pts, wid, tone in wisps:
            pb.add(core.stroke_poly(pts, wid), np.asarray(palette, np.float32)[int(tone)])
        pb.paint(layer)
    bb.paint(layer, palette, light)
    if holes:
        cut_holes(layer, holes)
    if tone_alpha is not None and not layer.empty:
        _apply_tone_alpha(layer, palette, tone_alpha)
    if texture > 0:
        core.brush_grain(layer, texture, centre if tex_anchor is None else tex_anchor, tex_scale, light)
    layer.onto(canvas, opacity, merge=tone_alpha is not None)
    return canvas


def _apply_tone_alpha(layer, palette, tone_alpha):
    """Make a finished (opaque) billow cel translucent per tone: the tone of each pixel is read
    back from its luminance between the shadow and lit colours, so overlapping lobes inside the
    cel do not show as darker circles - the whole cel is one translucent mass."""
    P = np.asarray(palette, np.float32)
    wl = np.array([0.3, 0.59, 0.11], np.float32)
    ls, lm, ll = float(P[0] @ wl), float(P[1] @ wl), float(P[2] @ wl)
    buf = layer.buf
    a = buf[..., 3]
    m = a > 1e-4
    if not m.any():
        return
    lum = (buf[..., :3] @ wl) / np.maximum(a, 1e-4)
    ta = np.asarray(tone_alpha, np.float32)
    f = np.interp(lum, [min(ls, lm), max(ls, lm) if lm > ls else ls + 1e-3, ll if ll > lm else lm + 1e-3],
                  [ta[0], ta[1], ta[2]]).astype(np.float32)
    buf *= np.where(m, f, 1.0)[..., None]


def paint_rows(canvas, rows, holes, palette, light, centre, size, line=2.5, wob=0.05,
               opacity=1.0, bias=0.0, vert=0.45, contrast=1.0, layer=None, ref_r=None,
               alpha=1.0, inner=0.0):
    """Single-disc billows from rows (cx, cy, r, z, wp)."""
    groups = [(r[3], [(r[0], r[1], r[2], r[4])], r[2]) for r in rows]
    return paint_groups(canvas, groups, holes, palette, light, centre, size, line, wob, opacity,
                        bias, vert, contrast, layer, ref_r, alpha, inner)


class DustPuff:
    """An impact puff thrown out from `origin` at `frame0`.

    size      : px, rough radius of the grown cloud
    direction : main throw direction (screen); spread = fan angle (radians)
    aspect    : scales the vertical travel (0.5 = flat, ground-hugging fan)
    life      : frames until it has thinned out completely
    ground    : screen y of the ground line (lobes slide along it) or None
    rise, drift: buoyant rise (fraction of size over life) and wind drift (px/frame)
    roll      : revolutions of the rolling bumps over the life
    line      : silhouette colour-line width (px) for a lobe of 0.35*size
    on        : drawings held on 2s by default
    """

    def __init__(self, name, origin, frame0, size=150.0, direction=(0, -1), spread=2.6, life=40,
                 n=9, light=(0.55, -0.83), palette=None, ground=None, rise=0.25, drift=(0.0, 0.0),
                 roll=0.5, line=2.5, on=2, opacity=1.0, wobble=0.05, sub=(4, 7), bias=0.0,
                 aspect=0.7, vert=0.45, arms=0.9, texture=0.0, main=None, bits=None, style=None):
        self.name = name
        self.origin = np.asarray(origin, np.float64)
        self.frame0 = int(frame0)
        self.size = float(size)
        self.life = int(life)
        self.n = n
        self.light = light
        self.palette = palettes.DUST if palette is None else palette
        self.ground = ground
        self.rise = rise
        self.drift = np.asarray(drift, np.float64)
        self.roll = roll
        self.line = line
        self.on = on
        self.opacity = opacity
        self.wobble = wobble
        self.bias = bias
        self.vert = vert
        self.texture = texture
        # round 6 looks: 'soil' = dark clods + dirt sprays + a little short-lived brown-grey dust;
        # 'dust' = translucent warm grey with denser lit crowns (blast / engine wash)
        self.style = style
        self.tone_alpha = None
        self.dust_life = self.life
        if style == 'dust':
            self.palette = palettes.DUST_WARM
            self.tone_alpha = palettes.TONE_ALPHA['dust']
            self.line = 0.0
        elif style == 'soil':
            self.palette = palettes.SOIL_DUST
            self.tone_alpha = palettes.TONE_ALPHA['soil']
            self.dust_life = int(min(self.life, 18))
            self.line = min(self.line, 1.5)
        elif style == 'wall':
            # opaque 3-tone dust wall (launch): warm lit tops, cool underside, hard tone edges
            self.palette = palettes.DUST_WALL
            self.line = min(max(self.line, 2.0), 3.0)
        g = core.rng('dustpuff', name)
        a0 = math.atan2(direction[1], direction[0])
        u = (np.arange(n) + g.uniform(0.2, 0.8, n)) / n          # stratified across the fan
        self.ang = a0 + (u - 0.5) * spread
        edge = np.abs(u - 0.5) * 2                                # 0 centre .. 1 fan edge
        self.dist = size * (0.42 + arms * 0.62 * edge ** 1.5) * g.uniform(0.8, 1.05, n)
        # sizes: one dominant mass near the centre of the fan, then neighbours alternating
        # big / small along the fan so no two neighbouring billows match
        self.spray = (aspect < 0.6) if main is None else (not main)
        self.rk = np.ones(n)
        if self.spray:
            # a low, broken spray: clusters of small billows fanning out along the ground with gaps
            # between them, uneven heights, no single dome
            kc = 3 + int(n >= 9)
            uc = (np.arange(kc) + g.uniform(0.25, 0.75, kc)) / kc
            cl = np.arange(n) % kc
            u = np.clip(uc[cl] + g.normal(0, 0.035, n), 0.02, 0.98)
            self.ang = a0 + (u - 0.5) * spread
            edge = np.abs(u - 0.5) * 2
            self.dist = size * (0.35 + 0.8 * edge ** 1.2) * g.uniform(0.8, 1.1, n)
            first = np.zeros(n, bool)
            first[[int(np.nonzero(cl == c)[0][0]) for c in range(kc) if (cl == c).any()]] = True
            self.rad = size * np.where(first, g.uniform(0.22, 0.3, n), g.uniform(0.12, 0.22, n)) * (1 - 0.2 * edge)
            self.rk = g.uniform(0.0, 1.0, n) ** 1.5 * 1.6        # uneven heights
            main_i = None
        else:
            order = np.argsort(self.ang)
            main_i = int(np.argmin(edge))
            self.rad = np.zeros(n)
            k = 0
            for i in order:
                if i == main_i:
                    self.rad[i] = size * 0.58
                    continue
                big = (k % 2 == 0)
                self.rad[i] = size * (g.uniform(0.3, 0.4) if big else g.uniform(0.13, 0.21)) * (1.0 - 0.3 * edge[i])
                k += 1
        if style == 'soil':
            self.rad = self.rad * 0.62                            # only a little dust
        if style == 'wall':
            self.rise = min(self.rise, 0.12)                       # the wall rolls out, it does not rise
        self.aspect = aspect
        self.delay = g.uniform(0, 0.05, n) + 0.04 * edge
        self.brk = g.uniform(-0.08, 0.08, n)
        self.rsign = np.where(np.cos(self.ang) >= 0, 1.0, -1.0)
        self.zj = g.uniform(-0.25, 0.25, n)
        if main_i is not None:
            self.zj[main_i] = 0.6                                # the main mass sits in front
        self.bil = _Billow(name, n, sub)
        # small bits thrown out of the contact
        self.bits = self.spray if bits is None else bits
        nb = 18
        ba = a0 + g.normal(0, spread / 2.6, nb)
        bs = size * g.uniform(0.035, 0.08, nb)
        self.bit_v = np.stack([np.cos(ba) * bs, np.sin(ba) * bs * 0.8 - size * 0.02], 1)
        self.bit_r = np.clip(size * g.uniform(0.012, 0.03, nb), 1.2, 9.0)
        self.bit_d = g.integers(0, 4, nb)
        self.bit_tone = g.random(nb) < 0.65
        if style == 'soil':
            nc = 20
            ca = a0 + g.normal(0, spread / 3.0, nc)
            cs = size * g.uniform(0.045, 0.11, nc)
            self.clod_v = np.stack([np.cos(ca) * cs, np.sin(ca) * cs * 0.9 - size * 0.035], 1)
            self.clod_r = np.clip(size * g.uniform(0.035, 0.09, nc), 3.0, 26.0)
            self.clod_k = ['clod' if g.random() < 0.6 else 'crumb' for _ in range(nc)]
            self.clod_a = g.uniform(0, 6.28, nc)
            self.clod_w = g.uniform(-0.35, 0.35, nc)
            self.clod_shape = [shapes.KINDS[k](core.rng('puffclod', name, i)) for i, k in enumerate(self.clod_k)]
            ns = 5                                               # dirt sprays: arcs of specks
            sa = a0 + (np.arange(ns) + g.uniform(0.2, 0.8, ns)) / ns * spread * 0.8 - spread * 0.4
            ss = size * g.uniform(0.06, 0.1, ns)
            self.spray_v = np.stack([np.cos(sa) * ss, np.sin(sa) * ss * 0.9 - size * 0.03], 1)
            self.spray_j = g.normal(0, 1.0, (ns, 14, 2))
            self.spray_d = g.uniform(0, 5.0, (ns, 14))

    def rows(self, frame):
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0 or age > self.dust_life:
            return [], [], 0.0, None
        t = age / self.dust_life
        idx = np.nonzero(t >= self.delay)[0]
        if len(idx) == 0:
            return [], [], 0.0, None
        ti = np.clip((t - self.delay[idx]) / (1 - self.delay[idx]), 0, 1)
        trav = self.dist[idx] * ease_out(ti, 4.0)
        px = self.origin[0] + np.cos(self.ang[idx]) * trav + self.drift[0] * age
        py = (self.origin[1] + np.sin(self.ang[idx]) * trav * self.aspect
              - self.rise * self.size * ti ** 1.3 * self.rk[idx] + self.drift[1] * age)
        R = self.rad[idx] * (0.30 + 0.70 * ease_out(ti / 0.16, 2.5)) * (1 + 0.3 * ti)
        brk = smoothstep(0.42, 1.06, ti + self.brk[idx])
        phase = self.rsign[idx] * TAU * self.roll * ti
        z = py + self.zj[idx] * self.size
        drawing = age // max(self.on, 1)
        lead = np.stack([np.cos(self.ang[idx]), np.sin(self.ang[idx]) * self.aspect - 0.25], 1)
        rows, holes, wisps = self.bil.build(idx, px, py, R, brk, phase, z, self.wobble, drawing,
                                            self.ground, lead, True)
        self._wisps = wisps
        w = R ** 2
        C = (np.sum(px * w) / w.sum(), np.sum(py * w) / w.sum())
        op = self.opacity * (1 - smoothstep(0.88, 1.0, t))
        if self.style == 'dust':
            op *= 1 - 0.45 * float(smoothstep(0.3, 1.0, t))      # thins as it spreads
        return rows, holes, op, C

    def draw(self, canvas, frame, light=None):
        light = self.light if light is None else light
        rows, holes, op, C = self.rows(frame)
        if rows:
            paint_groups(canvas, rows, holes, self.palette, light,
                         C, self.size, self.line, self.wobble, op, self.bias, self.vert,
                         texture=self.texture, tex_anchor=self.origin, tex_scale=self.size / 260.0,
                         wisps=self._wisps, tone_alpha=self.tone_alpha)
            if self.bits and self.style != 'soil':
                self._draw_bits(canvas, frame, op)
        if self.style == 'soil':
            self._draw_soil(canvas, frame, light)
        return canvas

    def _draw_soil(self, canvas, frame, light):
        """Clods thrown on parabolic arcs (2 tones + a thin brown line) and arcs of dirt specks."""
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0 or age > self.life:
            return
        grav = self.size * 0.0065
        gy = self.ground
        b = core.PolyBatch()
        col = palettes.DEBRIS['crumb']
        for k in range(len(self.clod_r)):
            p = self.origin + self.clod_v[k] * age + np.array([0, 0.5 * grav * age * age])
            if gy is not None and p[1] > gy:
                # landed: stays put a moment, then is gone
                tl = self._land_t(self.clod_v[k, 1], grav, gy - self.origin[1])
                if tl is None or age - tl > 10:
                    continue
                p = self.origin + self.clod_v[k] * tl + np.array([0, 0.5 * grav * tl * tl])
                p[1] = gy
                ang = self.clod_a[k] + self.clod_w[k] * tl
            else:
                ang = self.clod_a[k] + self.clod_w[k] * age
            from .debris import add_piece
            add_piece(b, self.clod_k[k], self.clod_shape[k], p, ang, self.clod_r[k], light, 0.9)
        for s in range(len(self.spray_v)):
            for j in range(self.spray_j.shape[1]):
                t = age - self.spray_d[s, j]
                if t <= 0:
                    continue
                p = self.origin + self.spray_v[s] * t + np.array([0, 0.5 * grav * t * t]) \
                    + self.spray_j[s, j] * (1.5 + 0.35 * t)
                if gy is not None and p[1] > gy:
                    continue
                r = max(1.2, self.size * 0.016 * (1 - 0.5 * t / self.life))
                poly = shapes.blob(core.rng('spray', self.name, s, j), n=5, rmin=0.6, rmax=1.0, smooth=0) * r
                b.add(poly + p, col['shade'] if (j % 3) else col['lit'])
        b.draw(canvas)

    @staticmethod
    def _land_t(vy, g, dy):
        if dy <= 0:
            return 0.0
        disc = vy * vy + 2 * g * dy
        if disc < 0 or g <= 0:
            return None
        return (-vy + math.sqrt(disc)) / g

    def _draw_bits(self, canvas, frame, op):
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        g = core.rng('puffbits', self.name)
        b = core.PolyBatch()
        P = np.asarray(self.palette, np.float32)
        grav = self.size * 0.0035
        for k in range(len(self.bit_r)):
            t = age - self.bit_d[k]
            if t < 0 or t > self.life * 0.7:
                continue
            x = self.origin[0] + self.bit_v[k, 0] * t
            y = self.origin[1] + self.bit_v[k, 1] * t + 0.5 * grav * t * t
            if self.ground is not None and y > self.ground + 2:
                continue
            r = self.bit_r[k] * (1 - 0.6 * t / (self.life * 0.7))
            if r < 0.8:
                continue
            poly = shapes.blob(core.rng('puffbit', self.name, k), n=6, rmin=0.6, rmax=1.0, smooth=1) * r
            b.add(poly + np.array([x, y]), P[0] if self.bit_tone[k] else P[1], alpha=op)
        b.draw(canvas)


class GroundDust:
    """Rolling ground dust: a front pushed along the ground from `start` in `direction`.

    The *head* (2-3 big billows) travels with the front and rolls forward (its bumps go
    over the top); every drawing it sheds a *tail* billow that stays behind, rises, breaks
    up and thins.  distance/duration: how far (px) and how long (frames) the front travels
    (ease-out).  height: px height of the head at full speed.  grow: scale change along the
    path (0.6 = 60 % bigger at the end, e.g. rolling toward camera).  ground: screen y of
    the ground (default start[1]).
    """

    def __init__(self, name, start, direction, frame0, distance=600.0, duration=30, height=110.0,
                 life=26, light=(0.55, -0.83), palette=None, on=2, depth=0.3, roll=1.0,
                 line=2.5, grow=0.0, opacity=1.0, wobble=0.05, ground=None, bias=0.0, vert=0.45,
                 head=3, texture=0.0, style=None):
        self.name = name
        self.start = np.asarray(start, np.float64)
        self.dir = core.unit(direction)
        self.frame0 = int(frame0)
        self.distance = float(distance)
        self.duration = int(duration)
        self.height = float(height)
        self.life = int(life)
        self.light = light
        self.palette = palettes.DUST if palette is None else palette
        self.on = on
        self.depth = depth
        self.roll = roll
        self.line = line
        self.grow = grow
        self.opacity = opacity
        self.wobble = wobble
        self.bias = bias
        self.vert = vert
        self.ground = ground
        self.texture = texture
        self.tone_alpha = None
        self.style = style
        if style == 'dust':
            self.palette = palettes.DUST_WARM
            self.tone_alpha = palettes.TONE_ALPHA['dust']
            self.line = 0.0
        elif style == 'soil':
            self.palette = palettes.SOIL_DUST
            self.tone_alpha = palettes.TONE_ALPHA['soil']
            self.life = max(10, int(self.life * 0.65))           # earthy dust settles fast
            self.line = min(self.line, 1.5)
        elif style == 'wall':
            # an opaque rolling wall: a bigger head, tail billows that stay low and long enough to
            # join into one continuous lumpy wall behind the front
            self.palette = palettes.DUST_WALL
            self.life = int(self.life * 1.7)
            self.line = min(max(self.line, 2.0), 3.0)
            head = max(head, 4)
        self.wall = style == 'wall'
        self.nh = head
        self.nsp = int(math.ceil(self.duration / on)) + 1
        n = head + self.nsp
        g = core.rng('grounddust', name)
        self.u = g.uniform(0.85, 1.1, n) * np.where(np.arange(n) % 2 == 0, 1.12, 0.62)
        self.lat = g.uniform(-1, 1, n)
        self.fw = g.uniform(-0.15, 0.25, n)
        self.brk = g.uniform(-0.08, 0.08, n)
        self.lj = g.uniform(0.8, 1.2, n)
        self.hoff = np.array([[-0.15, 0.62, 0.0], [-0.75, 0.48, -0.15], [0.32, 0.34, 0.25],
                              [-1.2, 0.38, -0.3]])[:head]
        if head > len(self.hoff):
            self.hoff = np.concatenate([self.hoff, np.array([[-1.6, 0.42, -0.35]] * (head - len(self.hoff)))])
        self.bil = _Billow(name, n, (4, 7))

    def front(self, age):
        x = np.clip(age / self.duration, 0, 1)
        s = self.distance * ease_out(x, 2.2)
        v = self.distance * 2.2 * (1 - x) ** 1.2 / self.duration
        return s, v

    def _place(self, s, R, lat):
        base = self.start + self.dir * s
        gy = base[1] if self.ground is None else self.ground + self.dir[1] * s
        self._gy = gy + lat
        return base[0], gy - R * 0.62 + lat

    def rows(self, frame):
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0:
            return [], [], 0.0, None, 1.0
        _, vmax = self.front(0)
        sgn = 1.0 if self.dir[0] >= 0 else -1.0
        ids, PX, PY, RR, BR, PH, Z, GY = [], [], [], [], [], [], [], []
        s_now, v_now = self.front(age)
        spd = (v_now / vmax) ** 0.5
        sc_now = 1 + self.grow * s_now / max(self.distance, 1)
        # head billows ride the front
        hb = smoothstep(self.duration * 0.75, self.duration + self.life * 0.9, age)
        for k in range(self.nh):
            i = k
            off, rk, zk = self.hoff[k]
            h = self.height * sc_now * (0.55 + 0.45 * spd) * self.u[i] * ease_out(min(1, (age + 2) / 8), 2)
            R = h * rk
            s = s_now + off * self.height * sc_now
            x, y = self._place(s, R, 0.0)
            GY.append(self._gy)
            ids.append(i); PX.append(x); PY.append(y - h * 0.15 * hb); RR.append(R)
            BR.append(min(1.0, hb + self.brk[i] * hb))
            PH.append(sgn * TAU * self.roll * age / 18.0)
            Z.append(1e4 + zk * self.height)
        # tail billows shed by the head on every drawing
        for j in range(self.nsp):
            b = j * self.on
            if b > age:
                break
            s_b, v_b = self.front(b)
            if b > 0 and v_b < vmax * 0.08:
                break
            i = self.nh + j
            a = age - b
            life = self.life * self.lj[i]
            if a > life:
                continue
            t = a / life
            sc = 1 + self.grow * s_b / max(self.distance, 1)
            h = self.height * sc * (0.40 + 0.60 * (v_b / vmax) ** 0.6) * self.u[i]
            s = s_b - 0.45 * self.height * sc + h * self.fw[i] + h * 0.5 * (1 - math.exp(-a / 5.0)) * (v_b / vmax)
            if self.wall:
                h = h * 1.25
                R = h * 0.5 * (0.6 + 0.4 * ease_out(min(1, a / 8), 2)) * (1 + 0.2 * t)
                lat = self.lat[i] * self.depth * h * 0.5
                x, y = self._place(s, R, lat)
                GY.append(self._gy if t < 0.7 else self._gy + 1e6)
                ids.append(i); PX.append(x); PY.append(y - h * 0.12 * t); RR.append(R)
                BR.append(smoothstep(0.62, 1.0, t + self.brk[i]))
                PH.append(sgn * TAU * self.roll * 0.4 * a / 18.0)
                Z.append(b + lat * 0.05)
                continue
            R = h * 0.46 * (0.55 + 0.45 * ease_out(min(1, a / 8), 2)) * (1 + 0.3 * t)
            lat = self.lat[i] * self.depth * h
            x, y = self._place(s, R, lat)
            GY.append(self._gy if t < 0.35 else self._gy + 1e6)     # risen billows leave the ground
            ids.append(i); PX.append(x); PY.append(y - h * 0.4 * t); RR.append(R)
            BR.append(smoothstep(0.35, 0.97, t + self.brk[i]))
            PH.append(sgn * TAU * self.roll * 0.4 * a / 18.0)
            Z.append(b + lat * 0.05)
        if not ids:
            return [], [], 0.0, None, 1.0
        PX, PY, RR = np.array(PX), np.array(PY), np.array(RR)
        drawing = age // max(self.on, 1)
        lead = np.tile(np.array([self.dir[0], self.dir[1] - 0.3]), (len(ids), 1))
        rows, holes, wisps = self.bil.build(np.array(ids), PX, PY, RR, np.array(BR), np.array(PH),
                                            np.array(Z), self.wobble, drawing, np.array(GY), lead, True)
        self._wisps = wisps
        w = RR ** 2
        C = (np.sum(PX * w) / w.sum(), np.sum(PY * w) / w.sum())
        size = max(self.height * 1.4, RR.max() * 2.0)
        end = self.duration + self.life * 1.2
        op = self.opacity * (1 - smoothstep(end * 0.88, end, age))
        if self.style == 'dust':
            op *= 1 - 0.4 * float(smoothstep(end * 0.3, end, age))
        return rows, holes, op, C, size

    def draw(self, canvas, frame, light=None):
        rows, holes, op, C, size = self.rows(frame)
        if not rows or op <= 0:
            return canvas
        return paint_groups(canvas, rows, holes, self.palette, self.light if light is None else light,
                            C, size, self.line, self.wobble, op, self.bias, self.vert,
                            ref_r=self.height * 0.4, texture=self.texture, tex_anchor=C,
                            tex_scale=self.height / 150.0, wisps=self._wisps, tone_alpha=self.tone_alpha)


def puff_trail_rows(points, births, frame, size, life, name, on=2, rise=0.4, grow=1.6,
                    drift=(0.0, 0.0)):
    """Small dissipating puffs left at `points[k]` at frame `births[k]` (debris trails, smoke).

    Returns rows (cx, cy, r, z, wp) and holes for `paint_rows`."""
    g = core.rng('pufftrail', name)
    n = len(points)
    u = g.uniform(0.7, 1.2, max(n, 1))
    ph = g.uniform(0, TAU, max(n, 1))
    rows, holes = [], []
    fh = held(frame, on, 0)
    for k in range(n):
        a = fh - births[k]
        if a < 0 or a > life:
            continue
        t = a / life
        r = size * u[k] * (0.45 + 0.55 * ease_out(t, 2) * grow) * (1 - smoothstep(0.6, 1.0, t))
        if r < 0.6:
            continue
        x = points[k][0] + drift[0] * a + math.cos(ph[k]) * size * 0.4 * t
        y = points[k][1] + drift[1] * a - rise * size * t
        rows.append((x, y, r, y, ph[k] + (fh // on) * 0.9))
        if t > 0.45:
            hr = r * 0.8 * smoothstep(0.45, 1.0, t)
            holes.append((x + math.cos(ph[k] * 3) * r * 0.5, y + math.sin(ph[k] * 3) * r * 0.5, hr, 0.08, ph[k]))
    return rows, holes


class BillowSet:
    """Billow look for other effects: give primaries (index, x, y, r, break-up, phase, z) and get
    groups with orbiting bumps, ready for `paint_groups`."""

    def __init__(self, name, n, sub=(4, 6)):
        self.b = _Billow(name, n, sub)
        self.n = n

    def groups(self, idx, px, py, R, brk, phase, z, drawing, wob=0.05, ground=None, lead=None,
               wisps=False):
        """-> (groups, bites) or, with wisps=True, (groups, bites, wisps).  lead: per-primary
        screen direction of travel (hooked curls on that side); ground: scalar or per-primary y."""
        idx = np.asarray(idx, np.int64) % self.n
        return self.b.build(idx, np.asarray(px, np.float64), np.asarray(py, np.float64),
                            np.asarray(R, np.float64), np.asarray(brk, np.float64),
                            np.asarray(phase, np.float64), np.asarray(z, np.float64), wob, drawing,
                            ground, lead, wisps)


class DustVeil:
    """A thin, broken, 2-tone, semi-transparent dust sheet with lumpy edges, spreading sideways
    from `origin` along the ground (e.g. the S14 launch blast, behind the main dust).

    width / height: px span of the grown sheet; life: frames; opacity: of the whole cel (it
    also fades out over the last 30 %); gaps and late holes break it up; the top edge is lumpy,
    the base is cut flat at `ground` (default origin y)."""

    def __init__(self, name, origin, frame0, width=1400.0, height=240.0, life=48, light=(0.55, -0.83),
                 palette=None, opacity=0.55, on=2, ground=None, segments=14, rise=0.35, style=None):
        self.name = name
        self.origin = np.asarray(origin, np.float64)
        self.frame0 = int(frame0)
        self.width = float(width)
        self.height = float(height)
        self.life = int(life)
        self.light = light
        base = palettes.DUST_DRY if palette is None else palette
        if style == 'dust':
            base = palettes.DUST_WARM
        elif style == 'soil':
            base = palettes.SOIL_DUST
        elif style == 'wall':
            base = palettes.DUST_WALL
            opacity = max(opacity, 0.95)                         # a solid back row of the wall
        P = np.asarray(base, np.float32).copy()
        P[1] = P[2] * 0.55 + P[1] * 0.45            # 2 tones: a light top and a cool underside
        P[2] = P[1]
        self.palette = P
        self.opacity = opacity
        self.on = on
        self.ground = self.origin[1] if ground is None else float(ground)
        self.rise = rise
        g = core.rng('dustveil', name)
        n = segments
        self.n = n
        self.side = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
        self.reach = np.sort(g.uniform(0.08, 1.0, n))
        self.hk = g.uniform(0.45, 1.15, n) * np.where(g.random(n) < 0.25, 1.35, 1.0)
        self.gap = g.random(n) < 0.15
        self.nb = g.integers(3, 6, n)
        self.bu = g.uniform(0, 1, (n, 6))
        self.bs = g.uniform(0.22, 0.42, (n, 6))
        self.wp = g.uniform(0, TAU, (n, 8))
        self.hole_t = g.uniform(0.35, 0.8, n)
        self.hole_x = g.uniform(-0.6, 0.6, n)

    def draw(self, canvas, frame, light=None):
        light = self.light if light is None else light
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0 or age > self.life:
            return canvas
        t = age / self.life
        spread = float(ease_out(min(1.0, t / 0.55), 2.5))
        drawing = age // max(self.on, 1)
        groups, holes = [], []
        segw = self.width / self.n * 1.25
        for k in range(self.n):
            if self.gap[k]:
                continue
            x = self.origin[0] + self.side[k] * self.reach[k] * self.width * 0.5 * spread
            hgt = self.height * self.hk[k] * (0.35 + 0.65 * spread) * (1 - 0.3 * t)
            if hgt < 2:
                continue
            ybase = self.ground
            yc = ybase - hgt * 0.35 - self.height * self.rise * t
            wpd = drawing * 0.7
            lobes = [(x, yc, hgt * 0.5, self.wp[k, 0] + wpd, segw / hgt * 1.1, 0.75, 0.0, 0, 0, 0, 1.0)]
            for m in range(self.nb[k]):
                bx = x + (self.bu[k, m] - 0.5) * segw * 1.1
                rr = hgt * self.bs[k, m]
                lobes.append((bx, yc - hgt * 0.32, rr, self.wp[k, m + 1] + wpd, 1.15, 0.85, 0.0, 0, 0, 0, 1.0))
            groups.append((-abs(x - self.origin[0]) * 0.001 + k * 1e-4, lobes, hgt * 0.5, k,
                           ybase + 1.0 if t < 0.5 else None))
            if t > self.hole_t[k]:
                hr = hgt * 0.55 * float(smoothstep(self.hole_t[k], 1.0, t))
                holes.append((x + self.hole_x[k] * segw * 0.5, yc - hgt * 0.1, hr, 0.12, self.wp[k, 7] + wpd))
        if not groups:
            return canvas
        op = self.opacity * (1 - smoothstep(0.7, 1.0, t))
        return paint_groups(canvas, groups, holes, self.palette, light, (self.origin[0], self.ground - self.height * 0.5),
                            self.height * 1.2, line=0.0, opacity=op, local=0.6, vert=0.6)
