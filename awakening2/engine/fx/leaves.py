"""leaves.py - drawn leaves: spiralling / fluttering falls and blown bursts.

A leaf is a designed outline (ovate, lance, round, serrate, maple) with ink, a lit / shade
split from the screen light, a midrib, and a flip: the leaf turns about its long axis, its
width foreshortens with cos(flip) and the back colour shows when cos(flip) < 0.  Positions
and rotations are held on 2s.
"""
import math

import numpy as np

from . import core, palettes, shapes
from .core import PolyBatch, held

DEFAULT_COLOURS = {'green': 0.42, 'deep': 0.22, 'gold': 0.24, 'rust': 0.12}
DEFAULT_KINDS = {'ovate': 0.15, 'lance': 0.08, 'round': 0.06, 'serrate': 0.17, 'maple': 0.1,
                 'willow': 0.1, 'birch': 0.12, 'heart': 0.1, 'lobed': 0.12}


def _pick(g, d, n):
    names = list(d)
    w = np.array([d[k] for k in names], np.float64)
    return [names[i] for i in g.choice(len(names), size=n, p=w / w.sum())]


def _linger(theta, k=0.38):
    """Time-warp a steady roll so the leaf lingers face-on and snaps through edge-on
    (d/dtheta = 1 - 2k cos 2theta: slow at 0 and pi, fast at pi/2)."""
    return theta - k * math.sin(2 * theta)


def _clip_half(P, o, nrm):
    """Part of polygon P on the side (x - o).nrm >= 0."""
    out = []
    n = len(P)
    for k in range(n):
        a, b = P[k], P[(k + 1) % n]
        da, db = float((a - o) @ nrm), float((b - o) @ nrm)
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append(a + (b - a) * t)
    return np.array(out) if len(out) >= 3 else None


def _bend(x, y, bend):
    """Curve a leaf along its length (local coords, x in -1..1)."""
    return x, y + bend * (x * x - 0.3)


def add_leaf(batch, outline, pos, ang, length, flip, colours, light, ink_w=1.2, sunlit=0.0,
             alpha=1.0, tilt=1.0, curl=0.0, bend=0.0, tint=None, veins=True, pitch=0.0):
    """Add one leaf (outline in -1..1 local units, tip at +x) to a PolyBatch.

    The leaf is a thin plate turned in 3D and projected: ang = in-plane screen angle,
    flip = roll about its long axis, pitch = tilt about its across axis.  Its width
    foreshortens with |cos(flip)|, its length with |cos(pitch)|, the two together skew it,
    and the side facing the camera (front: lit top colours, back: paler underside) follows
    the plate normal.  tilt: extra length factor (old API).
    curl : 0..1 one half of the blade turns away (narrower and toward the far side);
    bend : the midrib bends (local units);  tint: (r, g, b) multiplier for per-leaf variation."""
    cf, sf = math.cos(flip), math.sin(flip)
    cp, sp = math.cos(pitch), math.sin(pitch)
    nz = cp * cf                                         # plate normal toward the camera
    front = nz >= 0
    face = abs(nz)
    half = length * 0.5
    c, s = math.cos(ang), math.sin(ang)
    # projected local axes (orthographic): long axis and across axis
    Lx, Ly = cp * tilt, sp * sf * tilt
    Ax, Ay = 0.0, cf
    if abs(Ay) < 0.08:                                   # never fully a line
        Ay = 0.08 if Ay >= 0 else -0.08
    Lv = np.array([Lx * c - Ly * s, Lx * s + Ly * c])
    Av = np.array([Ax * c - Ay * s, Ax * s + Ay * c])
    oy = outline[:, 1] * np.where(outline[:, 1] > 0, 1 - 0.75 * curl, 1.0)
    bx, by = _bend(outline[:, 0], oy, bend)
    P = pos + (bx * half)[:, None] * Lv[None, :] + (by * half)[:, None] * Av[None, :]
    lit = colours['f_lit'] if front else colours['b_lit']
    sh = colours['f_sh'] if front else colours['b_sh']
    if tint is not None:
        tv = np.asarray(tint, np.float32)
        lit = np.clip(lit * tv, 0, 1)
        sh = np.clip(sh * tv, 0, 1)
    ink = core.mix(sh, colours['ink'], 0.55)              # a coloured line, not a black one
    if sunlit > 0:
        lit = core.mix(lit, palettes.LIGHT_GOLD, 0.45 * sunlit)
        sh = core.mix(sh, lit, 0.25 * sunlit)
    # 2 tones: the blade is folded a little along its midrib, so the half turned away from the
    # light takes the shade colour (a hard split that flips as the leaf rolls); edge-on leaves
    # are one darker tone
    l = core.unit(light)
    split = face > 0.32 and length > 7
    if not split:
        lit = core.mix(lit, sh, 0.6)
    iw = ink_w if length > 10 else ink_w * 0.7

    def to_screen(x, y):
        x, y = _bend(np.asarray(x, np.float64), np.asarray(y, np.float64), bend)
        return pos + (x * half)[:, None] * Lv[None, :] + (y * half)[:, None] * Av[None, :]

    # stem
    S = to_screen([-1.0, -1.28], [0.0, 0.06 * (1 if front else -1)])
    batch.add(core.stroke_poly(S, [max(1.0, length * 0.035)] * 2), ink, alpha=alpha)
    if split:
        batch.add(P, lit, alpha=alpha)
        nl = float(np.hypot(Lv[0], Lv[1])) + 1e-9
        npp = np.array([-Lv[1], Lv[0]]) / nl
        if float(npp @ l) > 0:
            npp = -npp
        # fold line: the (bent) midrib, approximated by its chord through the leaf centre
        o = np.asarray(pos, np.float64) + Av * (half * bend * 0.1)
        shp = _clip_half(P, o, npp)
        if shp is not None:
            batch.add(shp, sh, alpha=alpha)
        batch.add(core.stroke_poly(np.concatenate([P, P[:1]], 0), iw), ink, alpha=alpha)
    else:
        batch.add(P, lit, ink=ink, ink_w=iw, alpha=alpha)
    if face > 0.3 and length > 11 and veins:
        # midrib (front: vein colour, back: paler raised rib) and side veins on larger leaves
        vc = colours['vein'] if front else core.mix(colours['b_lit'], colours['b_sh'], 0.6)
        if tint is not None:
            vc = np.clip(vc * np.asarray(tint, np.float32), 0, 1)
        M = to_screen(np.linspace(-0.95, 0.72, 6), np.zeros(6))
        batch.add(core.stroke_poly(M, np.linspace(max(1.0, length * 0.035), 0.4, 6)), vc, alpha=alpha)
        if length > 22:
            for xv in (-0.45, -0.05, 0.32):
                for side in (-1, 1):
                    wdt = float(np.interp(xv, outline[:, 0], np.abs(outline[:, 1]))) * 0.75
                    if side > 0:
                        wdt *= (1 - 0.75 * curl)
                    V = to_screen([xv, xv + 0.22], [0.0, side * wdt])
                    batch.add(core.stroke_poly(V, [max(0.8, length * 0.018), 0.3]), vc, alpha=alpha * 0.9)
    elif length > 11 and veins:
        # edge-on: the curled rim shows as a lighter sliver along one edge
        M = to_screen(np.linspace(-0.9, 0.8, 6), np.full(6, -0.25 if front else 0.25))
        batch.add(core.stroke_poly(M, np.linspace(max(0.8, length * 0.03), 0.3, 6)),
                  colours['b_lit'] if front else colours['f_lit'], alpha=alpha * 0.85)


class _LeafSet:
    def __init__(self, name, count, size, kinds, colours):
        g = core.rng('leaves', name)
        self.n = count
        self.kind = _pick(g, kinds or DEFAULT_KINDS, count)
        self.col = _pick(g, colours or DEFAULT_COLOURS, count)
        u = g.random(count)
        self.len = size[0] + (size[1] - size[0]) * u ** 1.4
        self.len *= np.where(g.random(count) < 0.12, 1.45, 1.0)          # a few big ones
        self.len *= np.where(np.isin(self.kind, ['birch', 'round']), 0.75, 1.0)
        self.len *= np.where(np.isin(self.kind, ['willow']), 1.25, 1.0)
        self.outline = [shapes.leaf(k, core.rng('leaf_shape', name, i)) for i, k in enumerate(self.kind)]
        self.curl = np.where(g.random(count) < 0.35, g.uniform(0.35, 0.85, count), g.uniform(0, 0.15, count))
        self.bend = g.uniform(-0.25, 0.25, count) + np.where(self.curl > 0.3, 0.2, 0.0) * g.choice([-1, 1], count)
        self.tint = np.clip(1 + g.normal(0, 0.07, (count, 3)) + g.normal(0, 0.06, (count, 1)), 0.75, 1.2)
        self.g = g

    def paint(self, canvas, items, light, sunlit=None, ink=1.1):
        """items: (z, i, x, y, ang, flip, scale[, pitch])."""
        if not items:
            return canvas
        items.sort(key=lambda it: it[0])
        b = PolyBatch()
        H, W = canvas.shape[:2]
        for it in items:
            z, i, x, y, ang, flip, sc = it[:7]
            pitch = it[7] if len(it) > 7 else 0.0
            L = self.len[i] * sc
            if x < -L or x > W + L or y < -L or y > H + L:
                continue
            sl = float(sunlit(x, y)) if sunlit is not None else 0.0
            add_leaf(b, self.outline[i], (x, y), ang, L, flip, palettes.LEAF[self.col[i]], light,
                     min(1.4, ink * max(0.75, min(1.2, L / 30))), sl, curl=float(self.curl[i]),
                     bend=float(self.bend[i]), tint=self.tint[i], pitch=pitch)
        b.draw(canvas)
        return canvas


class LeafFall:
    """Leaves spiralling / fluttering down.

    region   : (x0, y0, x1, y1) where leaves start (y0..y1 may be above the frame)
    frame0   : first frame; leaves start staggered over `stagger` frames (negative ages allowed
               via `preroll` so the shot can open with leaves already in the air)
    fall     : (min, max) px/frame mean sink speed;  swing: (min, max) px half-width of the
               flutter / spiral;  period: (min, max) frames per swing cycle
    spiral   : 0 = pendulum flutter, 1 = helical spiral (depth changes the scale)
    wind     : (vx, vy) px/frame drift
    """

    def __init__(self, name, region, frame0, count=24, size=(18.0, 34.0), fall=(1.2, 2.4),
                 swing=(30.0, 80.0), period=(40.0, 70.0), spiral=0.5, wind=(0.5, 0.0), kinds=None,
                 colours=None, light=(0.55, -0.83), on=2, stagger=48, preroll=0, depth=0.18):
        self.name = name
        self.frame0 = int(frame0)
        self.on = on
        self.light = light
        self.wind = np.asarray(wind, np.float64)
        self.spiral = spiral
        self.depth = depth
        S = _LeafSet(name, count, size, kinds, colours)
        self.S = S
        g = S.g
        x0, y0, x1, y1 = region
        self.x0 = g.uniform(x0, x1, count)
        self.y0 = g.uniform(y0, y1, count)
        self.vf = g.uniform(fall[0], fall[1], count)
        self.A = g.uniform(swing[0], swing[1], count)
        self.T = g.uniform(period[0], period[1], count)
        self.ph = g.uniform(0, 2 * math.pi, count)
        self.start = g.uniform(-preroll, stagger, count)
        self.base = g.uniform(-0.6, 0.6, count) + math.pi * 0.5 * g.choice([-1, 1], count)
        # rocking leaves hang mostly face-on (top or underside) and swing through edge-on
        self.fl0 = g.choice([0.0, math.pi], count) + g.uniform(-0.55, 0.55, count)
        self.flr = g.uniform(0.7, 1.4, count) * g.choice([-1, 1], count)
        self.spin = g.uniform(-0.02, 0.02, count)
        self.sp = g.random(count) < spiral
        self.pp = g.uniform(0, 2 * math.pi, count)              # pitch phase (tumble wobble)
        self.pa = g.uniform(0.25, 0.6, count)                   # pitch amplitude

    def items(self, frame):
        fh = held(frame, self.on, self.frame0)
        out = []
        for i in range(self.S.n):
            t = fh - self.frame0 - self.start[i]
            if t < 0:
                continue
            w = 2 * math.pi / self.T[i]
            a = w * t + self.ph[i]
            if self.sp[i]:
                # helical spiral: x swings, depth changes size, the leaf keeps turning over
                x = self.x0[i] + self.A[i] * math.cos(a) + self.wind[0] * t
                y = self.y0[i] + self.vf[i] * t + self.wind[1] * t
                dz = math.sin(a)
                sc = 1 + self.depth * dz
                ang = self.base[i] + 0.9 * math.sin(a) + self.spin[i] * t
                flip = _linger(a + self.fl0[i])
                pitch = self.pa[i] * 0.6 * math.sin(0.5 * a + self.pp[i])
            else:
                # pendulum flutter: rises a little at the ends of each swing
                x = self.x0[i] + self.A[i] * math.sin(a) + self.wind[0] * t
                y = (self.y0[i] + self.vf[i] * t + self.wind[1] * t
                     - self.A[i] * 0.22 * (1 - math.cos(2 * a)) * 0.5)
                sc = 1.0
                dz = 0.0
                ang = self.base[i] + 0.75 * math.cos(a) + self.spin[i] * t
                # the rocking leaf rolls far enough to pass edge-on and show its underside
                flip = self.fl0[i] + 1.25 * math.sin(a) + self.flr[i] * 0.02 * t
                pitch = self.pa[i] * math.cos(a + self.pp[i])
            out.append((dz + 0.001 * i, i, x, y, ang, flip, sc, pitch))
        return out

    def draw(self, canvas, frame, light=None, sunlit=None):
        return self.S.paint(canvas, self.items(frame), self.light if light is None else light, sunlit)


class LeafBurst:
    """Leaves thrown out from `origin` (blown by a blast, shaken from a canopy, torn by the
    wind ring): fast at first (drag slows them), spinning and flipping, then they settle into
    a fluttering fall.

    origin_radius / origin_line: spread the start points over a disc or a segment.
    """

    def __init__(self, name, origin, frame0, count=30, direction=(0, -1), spread=2.0,
                 speed=(10.0, 30.0), drag=0.09, fall=1.6, size=(14.0, 30.0), kinds=None,
                 colours=None, light=(0.55, -0.83), on=2, origin_radius=0.0, wind=(0.0, 0.0),
                 spin=0.5, life=120, delay=0):
        self.name = name
        self.frame0 = int(frame0)
        self.on = on
        self.light = light
        self.drag = drag
        self.fall = fall
        self.life = life
        self.wind = np.asarray(wind, np.float64)
        S = _LeafSet(name, count, size, kinds, colours)
        self.S = S
        g = S.g
        a0 = math.atan2(direction[1], direction[0])
        ang = a0 + g.uniform(-0.5, 0.5, count) * spread
        sp = g.uniform(speed[0], speed[1], count)
        self.v0 = np.stack([np.cos(ang) * sp, np.sin(ang) * sp], 1)
        rr = origin_radius * np.sqrt(g.random(count))
        ra = g.uniform(0, 2 * math.pi, count)
        self.p0 = np.asarray(origin, np.float64)[None, :] + np.stack([np.cos(ra) * rr, np.sin(ra) * rr], 1)
        self.a0 = g.uniform(0, 2 * math.pi, count)
        self.w = g.uniform(-spin, spin, count)
        self.fl0 = g.uniform(0, 2 * math.pi, count)
        self.flr = g.uniform(0.25, 0.6, count) * g.choice([-1, 1], count)
        self.T = g.uniform(30, 60, count)
        self.A = g.uniform(10, 30, count) * (size[1] / 30.0)
        self.ph = g.uniform(0, 2 * math.pi, count)
        self.delay = np.floor(g.uniform(0, delay, count)) if delay else np.zeros(count)
        self.z = g.random(count)
        # tumbling: every leaf keeps rolling over (one turn in 14-34 frames) and pitches; ~30 %
        # go end over end
        self.tf = 2 * math.pi / g.uniform(14, 34, count) * g.choice([-1, 1], count)
        self.tp = 2 * math.pi / g.uniform(20, 44, count)
        self.pp = g.uniform(0, 2 * math.pi, count)
        self.eoe = g.random(count) < 0.3
        self.spin2 = g.uniform(-0.05, 0.05, count)

    def items(self, frame):
        fh = held(frame, self.on, self.frame0)
        out = []
        k = self.drag
        for i in range(self.S.n):
            t = fh - self.frame0 - self.delay[i]
            if t < 0 or t > self.life:
                continue
            e = math.exp(-k * t)
            dist = (1 - e) / k
            x = self.p0[i, 0] + self.v0[i, 0] * dist + self.wind[0] * t
            # gravity toward a slow terminal sink
            y = self.p0[i, 1] + self.v0[i, 1] * dist + self.fall * (t - dist) + self.wind[1] * t
            slow = 1 - e                    # flutter grows as the leaf slows down
            a = 2 * math.pi * t / self.T[i] + self.ph[i]
            x += self.A[i] * slow * math.sin(a)
            ang = self.a0[i] + self.w[i] * dist + self.spin2[i] * t + 0.5 * slow * math.cos(a)
            flip = _linger(self.fl0[i] + self.flr[i] * dist * 1.5 + self.tf[i] * t) + 0.4 * slow * math.sin(a)
            if self.eoe[i]:
                pitch = _linger(self.pp[i] + self.tp[i] * t, 0.42)        # end over end
            else:
                pitch = 0.55 * math.sin(self.tp[i] * t + self.pp[i])
            out.append((self.z[i], i, x, y, ang, flip, 1.0, pitch))
        return out

    def draw(self, canvas, frame, light=None, sunlit=None):
        return self.S.paint(canvas, self.items(frame), self.light if light is None else light, sunlit)
