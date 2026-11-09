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
from .core import Layer, LobeBatch, cut_holes, ease_out, held, smoothstep

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


class _Billow:
    """Shared machinery: primaries -> groups of discs (core + orbiting bumps) and bites."""

    def __init__(self, name, n, sub=(4, 7)):
        g = core.rng('billow', name)
        m = sub[1]
        self.nsub = g.integers(sub[0], sub[1] + 1, n)
        base = g.uniform(0, TAU, (n, 1))
        self.sphi = base + np.arange(m)[None, :] * (TAU / m) + g.uniform(-0.4, 0.4, (n, m))
        self.su = g.uniform(0.34, 0.62, (n, m))
        self.sp = g.uniform(0.38, 0.62, (n, m))     # how far each bump sticks out (x its r)
        self.send = g.uniform(0.80, 1.0, (n, m))
        self.wp = g.uniform(0, TAU, (n, m + 1))
        self.hole_on = g.random(n) < 0.35
        self.hole_ang = g.uniform(0, TAU, n)
        self.hole_k = g.uniform(0.55, 0.8, n)
        self.m = m

    def build(self, idx, px, py, R, brk, phase, z, wob, drawing, ground=None):
        """Groups [(z, discs[(cx, cy, r, wp)], r0)] and bites for primaries `idx`."""
        groups = []
        holes = []
        for j, i in enumerate(idx):
            r0 = R[j]
            if r0 < 0.6:
                continue
            b = brk[j]
            x0 = px[j]
            y0 = py[j]
            if ground is not None:
                y0 = min(y0, ground - r0 * 0.42)
            core_r = r0 * (1 - 0.88 * b)
            wpd = drawing * 0.8
            discs = []
            if core_r > 0.6:
                discs.append((x0, y0, core_r, self.wp[i, 0] + wpd))
            for k in range(self.nsub[i]):
                ph = self.sphi[i, k] + phase[j]
                fade = 1 - smoothstep(self.send[i, k] - 0.35, self.send[i, k], b)
                sr = r0 * self.su[i, k] * (1 - 0.3 * b) * fade
                if sr < 0.6:
                    continue
                rho = max(0.15 * r0, r0 * (1 - 0.88 * b) - sr * (1 - self.sp[i, k])) + 0.85 * b * r0
                sx = x0 + rho * math.cos(ph)
                sy = y0 + rho * math.sin(ph) * 0.9
                if ground is not None:
                    sy = min(sy, ground - sr * 0.3)
                discs.append((sx, sy, sr, self.wp[i, k + 1] + wpd))
            if discs:
                groups.append((z[j], discs, r0))
            if self.hole_on[i] and b > 0.15:
                hr = r0 * self.hole_k[i] * smoothstep(0.15, 0.8, b)
                if hr > 1:
                    a = self.hole_ang[i] + phase[j] * 0.3
                    holes.append((x0 + math.cos(a) * r0 * 0.8, y0 + math.sin(a) * r0 * 0.8,
                                  hr, wob * 2.0, self.wp[i, 0] * 1.3 + wpd))
        return groups, holes


def paint_groups(canvas, groups, holes, palette, light, centre, size, line=2.5, wob=0.05,
                 opacity=1.0, bias=0.0, vert=0.45, contrast=1.0, layer=None, ref_r=None,
                 alpha=1.0, inner=0.0):
    """Paint billow groups [(z, discs[(cx, cy, r, wp)], r0)] as one cel layer onto the canvas."""
    if not groups:
        return canvas
    groups = sorted(groups, key=lambda g: g[0])
    ref = ref_r if ref_r is not None else size * 0.35
    bb = core.BillowBatch()
    for z, discs, r0 in groups:
        A = np.asarray(discs, np.float64)
        tl, ts = shade_params(A[:, 0], A[:, 1], centre, size, light, bias, vert, contrast)
        D = np.stack([A[:, 0], A[:, 1], A[:, 2], np.full(len(A), wob), A[:, 3], ts, tl], 1)
        lw = line * float(np.clip(r0 / ref, 0.5, 1.3)) if line > 0 else 0.0
        li = inner * float(np.clip(r0 / ref, 0.4, 1.2)) if inner > 0 else 0.0
        bb.add(D, alpha=alpha, inner=li, line=lw)
    if layer is None:
        layer = Layer(canvas.shape, *bb.bbox())
    bb.paint(layer, palette, light)
    if holes:
        cut_holes(layer, holes)
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
                 aspect=0.75, vert=0.45, arms=0.6):
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
        g = core.rng('dustpuff', name)
        a0 = math.atan2(direction[1], direction[0])
        u = (np.arange(n) + g.uniform(0.2, 0.8, n)) / n          # stratified across the fan
        g.shuffle(u)
        self.ang = a0 + (u - 0.5) * spread
        edge = np.abs(u - 0.5) * 2                                # 0 centre .. 1 fan edge
        self.dist = size * (0.42 + arms * 0.62 * edge ** 1.5) * g.uniform(0.8, 1.05, n)
        self.rad = size * g.uniform(0.30, 0.44, n) * (1.0 - 0.38 * edge ** 1.2)
        self.rad[np.argmin(edge)] = size * 0.5
        self.aspect = aspect
        self.delay = g.uniform(0, 0.05, n) + 0.04 * edge
        self.brk = g.uniform(-0.08, 0.08, n)
        self.rsign = np.where(np.cos(self.ang) >= 0, 1.0, -1.0)
        self.zj = g.uniform(-0.25, 0.25, n)
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
        brk = smoothstep(0.46, 1.0, ti + self.brk[idx])
        phase = self.rsign[idx] * TAU * self.roll * ti
        z = py + self.zj[idx] * self.size
        drawing = age // max(self.on, 1)
        rows, holes = self.bil.build(idx, px, py, R, brk, phase, z, self.wobble, drawing, self.ground)
        w = R ** 2
        C = (np.sum(px * w) / w.sum(), np.sum(py * w) / w.sum())
        op = self.opacity * (1 - smoothstep(0.88, 1.0, t))
        return rows, holes, op, C

    def draw(self, canvas, frame, light=None):
        rows, holes, op, C = self.rows(frame)
        if not rows:
            return canvas
        return paint_groups(canvas, rows, holes, self.palette, self.light if light is None else light,
                            C, self.size, self.line, self.wobble, op, self.bias, self.vert)


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
                 head=3):
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
        self.nh = head
        self.nsp = int(math.ceil(self.duration / on)) + 1
        n = head + self.nsp
        g = core.rng('grounddust', name)
        self.u = g.uniform(0.8, 1.15, n)
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
        return base[0], gy - R * 0.62 + lat

    def rows(self, frame):
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0:
            return [], [], 0.0, None, 1.0
        _, vmax = self.front(0)
        sgn = 1.0 if self.dir[0] >= 0 else -1.0
        ids, PX, PY, RR, BR, PH, Z = [], [], [], [], [], [], []
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
            ids.append(i); PX.append(x); PY.append(y - h * 0.4 * t); RR.append(R)
            BR.append(smoothstep(0.35, 0.97, t + self.brk[i]))
            PH.append(sgn * TAU * self.roll * 0.4 * a / 18.0)
            Z.append(b + lat * 0.05)
        if not ids:
            return [], [], 0.0, None, 1.0
        PX, PY, RR = np.array(PX), np.array(PY), np.array(RR)
        drawing = age // max(self.on, 1)
        rows, holes = self.bil.build(np.array(ids), PX, PY, RR, np.array(BR), np.array(PH),
                                     np.array(Z), self.wobble, drawing, None)
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
                            ref_r=self.height * 0.4)


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

    def groups(self, idx, px, py, R, brk, phase, z, drawing, wob=0.05, ground=None):
        idx = np.asarray(idx, np.int64) % self.n
        return self.b.build(idx, np.asarray(px, np.float64), np.asarray(py, np.float64),
                            np.asarray(R, np.float64), np.asarray(brk, np.float64),
                            np.asarray(phase, np.float64), np.asarray(z, np.float64), wob, drawing, ground)
