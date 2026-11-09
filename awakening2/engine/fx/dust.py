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

from . import core, palettes
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
            if core_r > 0.6:
                # the main mass: flattened and widened where it sits on the ground
                lobes.append((x0, y0, core_r, self.wp[i, 0] + wpd,
                              1.14 if near_ground else 1.0, 0.84 if near_ground else 1.0, 0.0, 0, 0, 0, 1.0))
            ld = None
            if lead is not None:
                ld = np.asarray(lead[j], np.float64)
                nl = float(np.hypot(ld[0], ld[1]))
                ld = ld / nl if nl > 1e-9 else None
            nb = self.nsub[i] + (2 if near_ground else 0)
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
                own = 1.0 if (sr > 0.4 * r0 and top > -0.3) else 0.0
                lobes.append((bx, by, sr, self.wp[i, k + 1] + wpd, 1.0, sq, ang, 0, 0, 0, own))
            # hook-shaped curl on the leading side: a forward-leaning lobe with its lower front
            # bitten out, so its tip curls over and down like a breaking wave
            if ld is not None and self.hook_on[i] and b < 0.75 and abs(ld[0]) > 0.55:
                # only on edges moving sideways: the curl rolls over the leading side
                up = np.array([0.0, -1.0])
                fw = np.array([1.0 if ld[0] > 0 else -1.0, 0.0])
                hr = self.hook_k[i] * r0 * (1 - 0.6 * b)
                hc = np.array([x0, y0]) + fw * (r0 * 0.74) + up * (r0 * self.hook_up[i])
                ang = math.atan2(-0.35, fw[0])
                bc = hc + fw * (hr * 0.62) - up * (hr * 0.62)
                lobes.append((hc[0], hc[1], hr, self.wp[i, -1] + wpd, 1.25, 0.9, ang,
                              bc[0], bc[1], hr * 0.52, 1.0))
            if lobes:
                groups.append((z[j], lobes, r0, int(i), None if gj is None else gj + 1.5))
            if self.hole_on[i] and b > 0.35:
                hr = r0 * self.hole_k[i] * smoothstep(0.3, 0.85, b)
                if hr > max(1.5, 0.3 * r0):
                    a = self.hole_ang[i] + phase[j] * 0.3
                    holes.append((x0 + math.cos(a) * r0 * 1.05, y0 + math.sin(a) * r0 * 1.05,
                                  hr, wob * 2.0, self.wp[i, 0] * 1.3 + wpd))
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
                 tex_scale=1.0, wisps=None):
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
        ts = np.where(A[:, 10] > 0.5, ts, -1.0)
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
    if texture > 0:
        core.brush_grain(layer, texture, centre if tex_anchor is None else tex_anchor, tex_scale, light)
    layer.onto(canvas, opacity)
    return canvas


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
                 aspect=0.7, vert=0.45, arms=0.9, texture=0.0):
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
        g = core.rng('dustpuff', name)
        a0 = math.atan2(direction[1], direction[0])
        u = (np.arange(n) + g.uniform(0.2, 0.8, n)) / n          # stratified across the fan
        self.ang = a0 + (u - 0.5) * spread
        edge = np.abs(u - 0.5) * 2                                # 0 centre .. 1 fan edge
        self.dist = size * (0.42 + arms * 0.62 * edge ** 1.5) * g.uniform(0.8, 1.05, n)
        # sizes: one dominant mass near the centre of the fan, then neighbours alternating
        # big / small along the fan so no two neighbouring billows match
        order = np.argsort(self.ang)
        main = int(np.argmin(edge))
        self.rad = np.zeros(n)
        k = 0
        for i in order:
            if i == main:
                self.rad[i] = size * 0.58
                continue
            big = (k % 2 == 0)
            self.rad[i] = size * (g.uniform(0.3, 0.4) if big else g.uniform(0.13, 0.21)) * (1.0 - 0.3 * edge[i])
            k += 1
        self.aspect = aspect
        self.delay = g.uniform(0, 0.05, n) + 0.04 * edge
        self.brk = g.uniform(-0.08, 0.08, n)
        self.rsign = np.where(np.cos(self.ang) >= 0, 1.0, -1.0)
        self.zj = g.uniform(-0.25, 0.25, n)
        self.zj[main] = 0.6                                      # the main mass sits in front
        self.bil = _Billow(name, n, sub)

    def rows(self, frame):
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0 or age > self.life:
            return [], [], 0.0, None
        t = age / self.life
        idx = np.nonzero(t >= self.delay)[0]
        if len(idx) == 0:
            return [], [], 0.0, None
        ti = np.clip((t - self.delay[idx]) / (1 - self.delay[idx]), 0, 1)
        trav = self.dist[idx] * ease_out(ti, 4.0)
        px = self.origin[0] + np.cos(self.ang[idx]) * trav + self.drift[0] * age
        py = (self.origin[1] + np.sin(self.ang[idx]) * trav * self.aspect
              - self.rise * self.size * ti ** 1.3 + self.drift[1] * age)
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
        return rows, holes, op, C

    def draw(self, canvas, frame, light=None):
        rows, holes, op, C = self.rows(frame)
        if not rows:
            return canvas
        return paint_groups(canvas, rows, holes, self.palette, self.light if light is None else light,
                            C, self.size, self.line, self.wobble, op, self.bias, self.vert,
                            texture=self.texture, tex_anchor=self.origin, tex_scale=self.size / 260.0,
                            wisps=self._wisps)


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
                 head=3, texture=0.0):
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
        return rows, holes, op, C, size

    def draw(self, canvas, frame, light=None):
        rows, holes, op, C, size = self.rows(frame)
        if not rows or op <= 0:
            return canvas
        return paint_groups(canvas, rows, holes, self.palette, self.light if light is None else light,
                            C, size, self.line, self.wobble, op, self.bias, self.vert,
                            ref_r=self.height * 0.4, texture=self.texture, tex_anchor=C,
                            tex_scale=self.height / 150.0, wisps=self._wisps)


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
