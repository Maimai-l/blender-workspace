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

DEFAULT_COLOURS = {'green': 0.5, 'deep': 0.2, 'gold': 0.22, 'rust': 0.08}
DEFAULT_KINDS = {'ovate': 0.35, 'lance': 0.2, 'round': 0.15, 'serrate': 0.2, 'maple': 0.1}


def _pick(g, d, n):
    names = list(d)
    w = np.array([d[k] for k in names], np.float64)
    return [names[i] for i in g.choice(len(names), size=n, p=w / w.sum())]


def add_leaf(batch, outline, pos, ang, length, flip, colours, light, ink_w=1.2, sunlit=0.0,
             alpha=1.0, tilt=1.0):
    """Add one leaf (outline in -1..1 local units, tip at +x) to a PolyBatch.

    flip : radians about the long axis (cos < 0 shows the back);  tilt: length foreshortening."""
    cf = math.cos(flip)
    front = cf >= 0
    wsc = max(abs(cf), 0.1)
    half = length * 0.5
    c, s = math.cos(ang), math.sin(ang)
    lx = outline[:, 0] * half * tilt
    ly = outline[:, 1] * half * wsc
    P = np.stack([lx * c - ly * s + pos[0], lx * s + ly * c + pos[1]], 1)
    lit = colours['f_lit'] if front else colours['b_lit']
    sh = colours['f_sh'] if front else colours['b_sh']
    if sunlit > 0:
        lit = core.mix(lit, palettes.LIGHT_GOLD, 0.45 * sunlit)
        sh = core.mix(sh, lit, 0.25 * sunlit)
    # edge-on leaves are mostly one tone
    l = core.unit(light)
    R = half * 1.1
    term = (pos[0] + l[0] * 0.55 * R, pos[1] + l[1] * 0.55 * R, 1.05 * R) if wsc > 0.3 else None
    if term is None:
        lit = core.mix(lit, sh, 0.5)
    iw = ink_w if length > 10 else ink_w * 0.7
    # stem
    st = np.array([[-1.0, 0.0], [-1.28, 0.06 * (1 if front else -1)]])
    sx = st[:, 0] * half * tilt
    sy = st[:, 1] * half * wsc
    S = np.stack([sx * c - sy * s + pos[0], sx * s + sy * c + pos[1]], 1)
    batch.add(core.stroke_poly(S, [max(1.0, length * 0.035)] * 2), colours['ink'], alpha=alpha)
    batch.add(P, lit, sh, colours['ink'], iw, term, alpha)
    if wsc > 0.3 and length > 12:
        # midrib (front: vein colour, back: paler raised rib)
        mx = np.linspace(-0.95, 0.72, 5) * half * tilt
        my = np.zeros(5)
        M = np.stack([mx * c - my * s + pos[0], mx * s + my * c + pos[1]], 1)
        vc = colours['vein'] if front else core.mix(colours['b_lit'], colours['b_sh'], 0.6)
        batch.add(core.stroke_poly(M, np.linspace(max(1.0, length * 0.03), 0.4, 5)), vc, alpha=alpha)


class _LeafSet:
    def __init__(self, name, count, size, kinds, colours):
        g = core.rng('leaves', name)
        self.n = count
        self.kind = _pick(g, kinds or DEFAULT_KINDS, count)
        self.col = _pick(g, colours or DEFAULT_COLOURS, count)
        self.len = g.uniform(size[0], size[1], count)
        self.outline = [shapes.leaf(k, core.rng('leaf_shape', name, i)) for i, k in enumerate(self.kind)]
        self.g = g

    def paint(self, canvas, items, light, sunlit=None, ink=1.2):
        """items: (z, i, x, y, ang, flip, scale)."""
        if not items:
            return canvas
        items.sort(key=lambda it: it[0])
        b = PolyBatch()
        H, W = canvas.shape[:2]
        for z, i, x, y, ang, flip, sc in items:
            L = self.len[i] * sc
            if x < -L or x > W + L or y < -L or y > H + L:
                continue
            sl = float(sunlit(x, y)) if sunlit is not None else 0.0
            add_leaf(b, self.outline[i], (x, y), ang, L, flip, palettes.LEAF[self.col[i]], light,
                     ink * max(0.7, min(1.4, L / 26)), sl)
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
        self.fl0 = g.uniform(0, 2 * math.pi, count)
        self.flr = g.uniform(0.7, 1.4, count) * g.choice([-1, 1], count)
        self.spin = g.uniform(-0.02, 0.02, count)
        self.sp = g.random(count) < spiral

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
                flip = a + self.fl0[i]
            else:
                # pendulum flutter: rises a little at the ends of each swing
                x = self.x0[i] + self.A[i] * math.sin(a) + self.wind[0] * t
                y = (self.y0[i] + self.vf[i] * t + self.wind[1] * t
                     - self.A[i] * 0.22 * (1 - math.cos(2 * a)) * 0.5)
                sc = 1.0
                dz = 0.0
                ang = self.base[i] + 0.75 * math.cos(a) + self.spin[i] * t
                flip = self.fl0[i] + 0.9 * math.sin(a) + self.flr[i] * 0.03 * t
            out.append((dz + 0.001 * i, i, x, y, ang, flip, sc))
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
            ang = self.a0[i] + self.w[i] * dist + 0.6 * slow * math.cos(a)
            flip = self.fl0[i] + self.flr[i] * dist * 1.5 + 0.8 * slow * math.sin(a)
            out.append((self.z[i], i, x, y, ang, flip, 1.0))
        return out

    def draw(self, canvas, frame, light=None, sunlit=None):
        return self.S.paint(canvas, self.items(frame), self.light if light is None else light, sunlit)
