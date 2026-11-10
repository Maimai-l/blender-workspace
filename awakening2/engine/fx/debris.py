"""debris.py - drawn debris: soil clods, crumbs, pebbles, moss chunks, roots, vines, bark,
falling with gravity and tumbling on 2s, optional dust trails; and the pouring-soil stream.

Each piece is a small cel: ink outline + lit / shade tones (the shade is a crescent on the
side away from the screen-space light, so it stays put while the piece tumbles).
"""
import math

import numpy as np

from . import core, palettes, shapes
from .core import PolyBatch, held, smoothstep
from .dust import BillowSet, paint_groups

DEFAULT_MIX = {'clod': 0.35, 'crumb': 0.25, 'pebble': 0.12, 'moss': 0.12, 'root': 0.08,
               'vine': 0.04, 'bark': 0.04}


def _colours(kind, role):
    if role == 'cap':
        c = palettes.DEBRIS['vine' if kind == 'vine' else 'moss']
        if kind == 'vine':
            return c['lit'] * 1.08, c['shade'], c['ink']
        return c['lit'], c['shade'], c['ink']
    c = palettes.DEBRIS[kind]
    if role == 'grain':
        return c['ink'], c['ink'], c['ink']
    return c['lit'], c['shade'], c['ink']


def add_piece(batch, kind, parts, pos, ang, size, light, ink_scale=1.0, alpha=1.0, flat=False):
    """Add one transformed debris piece to a PolyBatch."""
    l = core.unit(light)
    c, s = math.cos(ang), math.sin(ang)
    R = size * 1.25
    term = (pos[0] + l[0] * 0.6 * R, pos[1] + l[1] * 0.6 * R, 1.05 * R)
    iw = float(np.clip(0.09 * size, 0.8, 1.4)) * ink_scale         # props stay lighter than the hero
    for poly, role in parts:
        P = np.empty_like(poly)
        P[:, 0] = (poly[:, 0] * c - poly[:, 1] * s) * size + pos[0]
        P[:, 1] = (poly[:, 0] * s + poly[:, 1] * c) * size + pos[1]
        lit, sh, ink = _colours(kind, role)
        if flat or size < 2.6:
            batch.add(P, sh, alpha=alpha)
        elif role == 'grain':
            batch.add(P, ink, alpha=alpha)
        else:
            batch.add(P, lit, sh, ink, iw, term, alpha)


def _ballistic(p0, v0, g, t, gy, e, fr):
    """Position, settle time after t frames; bounces on y = gy (or no ground)."""
    p = np.array(p0, np.float64)
    v = np.array(v0, np.float64)
    tl = float(t)
    settle = None
    if gy is not None:
        tt = 0.0
        for _ in range(4):
            # solve p_y + v_y*tau + 0.5*g*tau^2 = gy for the next positive root
            a, b, cc = 0.5 * g, v[1], p[1] - gy
            if cc >= 0 and v[1] >= 0:
                tau = 0.0
            else:
                disc = b * b - 4 * a * cc
                if disc < 0 or a == 0:
                    break
                tau = (-b + math.sqrt(disc)) / (2 * a)
            if tau < 0 or tau > tl:
                break
            p = p + v * tau + np.array([0, 0.5 * g * tau * tau])
            p[1] = gy
            v[1] = -(v[1] + g * tau) * e
            v[0] *= fr
            tl -= tau
            tt += tau
            if abs(v[1]) < 1.2:
                settle = tt
                v[:] = 0
                return p, settle
    p = p + v * tl + np.array([0, 0.5 * g * tl * tl])
    return p, settle


class DebrisBurst:
    """A burst of debris thrown from `origin` (a point, or a disc of `origin_radius`).

    kinds   : dict kind -> weight (clod, crumb, pebble, moss, root, vine, bark)
    size    : (min, max) px radius of the pieces
    speed   : (min, max) px/frame launch speed; direction + spread (radians) give the cone
    gravity : px/frame^2 (screen y down);  spin: max rad/frame
    ground  : screen y where pieces bounce (`bounce` restitution) and settle, or None
    trails  : fraction of the larger pieces that leave little dust puffs behind them
    on      : positions and rotations held on 2s
    """

    def __init__(self, name, origin, frame0, count=40, kinds=None, size=(4.0, 16.0),
                 direction=(0, -1), spread=1.2, speed=(8.0, 22.0), gravity=1.2, spin=0.35,
                 light=(0.55, -0.83), ground=None, bounce=0.3, friction=0.6, on=2, trails=0.25,
                 origin_radius=0.0, ink=1.0, life=90, delay=0.0, trail_palette=None):
        self.name = name
        self.frame0 = int(frame0)
        self.light = light
        self.ground = ground
        self.bounce = bounce
        self.friction = friction
        self.on = on
        self.ink = ink
        self.life = life
        self.g = gravity
        self.trail_palette = palettes.DUST_DARK if trail_palette is None else trail_palette
        kinds = DEFAULT_MIX if kinds is None else kinds
        names = list(kinds)
        w = np.array([kinds[k] for k in names], np.float64)
        w /= w.sum()
        g = core.rng('debris', name)
        self.kind = [names[i] for i in g.choice(len(names), size=count, p=w)]
        u = g.random(count)
        self.size = size[0] + (size[1] - size[0]) * u ** 2.2
        for i, k in enumerate(self.kind):
            if k == 'crumb':
                self.size[i] = min(self.size[i], size[0] + 0.25 * (size[1] - size[0]))
            elif k in ('bark', 'root'):
                self.size[i] *= 0.65
        a0 = math.atan2(direction[1], direction[0])
        ang = a0 + g.uniform(-0.5, 0.5, count) * spread
        sp = g.uniform(speed[0], speed[1], count) * (1.15 - 0.35 * u)       # big pieces slower
        self.v0 = np.stack([np.cos(ang) * sp, np.sin(ang) * sp], 1)
        rr = origin_radius * np.sqrt(g.random(count))
        ra = g.uniform(0, 2 * math.pi, count)
        self.p0 = np.asarray(origin, np.float64)[None, :] + np.stack([np.cos(ra) * rr, np.sin(ra) * rr], 1)
        self.a0 = g.uniform(0, 2 * math.pi, count)
        self.w = g.uniform(-spin, spin, count) * (1.4 - 0.6 * u)
        self.delay = np.floor(g.uniform(0, delay, count)) if delay else np.zeros(count)
        self.trail = (u > 0.45) & (g.random(count) < trails * 2)
        self.z = g.random(count)
        self.parts = []
        for i, k in enumerate(self.kind):
            self.parts.append(shapes.KINDS[k](core.rng('debris_shape', name, i)))

    def _state(self, i, t):
        r = self.size[i]
        gy = None if self.ground is None else self.ground - r * 0.6
        p, settle = _ballistic(self.p0[i], self.v0[i], self.g, t, gy, self.bounce, self.friction)
        ta = t if settle is None else settle
        return p, self.a0[i] + self.w[i] * ta

    def draw(self, canvas, frame, light=None):
        light = self.light if light is None else light
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0 or age > self.life:
            return canvas
        H, W = canvas.shape[:2]
        batch = PolyBatch()
        trails = PolyBatch()
        l = core.unit(light)
        dpal = self.trail_palette
        order = np.argsort(self.z)
        for i in order:
            t = age - self.delay[i]
            if t < 0:
                continue
            p, a = self._state(i, t)
            if p[1] > H + 60 or p[0] < -80 or p[0] > W + 80:
                continue
            if self.trail[i] and t > 1:
                # a short dust streak dragged along the path: tapered, breaking up with age
                n = 7
                ts = np.linspace(max(0.0, t - 8.0), t, n)
                pts = np.array([self._state(i, tt)[0] for tt in ts])
                seg = np.linalg.norm(pts[-1] - pts[0])
                if seg > self.size[i] * 1.5:
                    q = np.linspace(0, 1, n)
                    wid = self.size[i] * 1.1 * q ** 1.3
                    fade = max(0.0, 1 - t / 30.0)
                    if fade > 0.05:
                        trails.add(core.stroke_poly(pts, wid), dpal[1], alpha=0.85 * fade)
                        nrm, _ = core.polyline_normals(pts)
                        side = np.sign(np.sum(nrm * l[None, :], 1, keepdims=True))
                        trails.add(core.stroke_poly(pts + nrm * side * wid[:, None] * 0.22, wid * 0.45),
                                   dpal[2], alpha=0.85 * fade)
            add_piece(batch, self.kind[i], self.parts[i], p, a, self.size[i], light, self.ink)
        trails.draw(canvas)
        batch.draw(canvas)
        return canvas


def _as_emitter(emitter):
    if callable(emitter):
        return emitter
    arr = np.asarray(emitter, np.float64)

    def f(frame):
        k = int(np.clip(frame, 0, len(arr) - 1))
        e = arr[k]
        if e.shape == (2,):
            return e, e
        return e[0], e[1]
    return f


class SoilPour:
    """Soil pouring off a moving edge: a few spill points along the edge each pour a sheet
    that tears into clumps and bits; a thin dust veil billows behind; dust kicks up where
    the soil lands (if `ground` is given).

    emitter : callable frame -> ((x0, y0), (x1, y1)) screen segment (or a point (x, y)), or an
              array indexed by frame (n, 2, 2).  The lead passes projected robot edges here.
    start, end : frames during which soil leaves the emitter
    rate    : loose bits born per frame;  strands: number of spill points (sheets)
    inherit : fraction of the emitter's velocity the soil keeps
    """

    def __init__(self, name, emitter, start, end, rate=22, strands=5, size=(2.0, 8.0),
                 gravity=1.1, inherit=0.7, jitter=0.7, light=(0.55, -0.83), on=2, veil=True,
                 kinds=None, ground=None, strand_width=(10.0, 24.0), maxage=36, veil_size=34.0,
                 veil_opacity=0.6, scatter=0.25, land_size=None, style=None):
        self.name = name
        self.em = _as_emitter(emitter)
        self.start = int(start)
        self.end = int(end)
        self.rate = rate
        self.size = size
        self.g = gravity
        self.inherit = inherit
        self.jitter = jitter
        self.light = light
        self.on = on
        self.veil = veil
        self.ground = ground
        self.maxage = max(maxage, 44)
        self.veil_size = veil_size
        self.veil_opacity = veil_opacity
        self.scatter = scatter
        self.land_size = veil_size * 1.2 if land_size is None else land_size
        # style='soil': the veil and the landing dust are earthy brown-grey and settle quickly
        self.veil_pal = palettes.SOIL_DUST if style == 'soil' else palettes.VEIL
        self.land_pal = palettes.SOIL_DUST if style == 'soil' else palettes.DUST
        self.land_alpha = palettes.TONE_ALPHA['soil'] if style == 'soil' else None
        self.kinds = {'crumb': 0.72, 'clod': 0.24, 'moss': 0.04} if kinds is None else kinds
        g = core.rng('pour', name)
        ns = int(min(max(strands, 1), 3))
        self.su = np.sort((np.arange(ns) + g.uniform(0.25, 0.75, ns)) / ns) * 0.84 + 0.08
        strands = ns
        self.sw = g.uniform(strand_width[0], strand_width[1], strands)
        self.clump_rate = 0.42
        self.powder_h = max(40.0, 5.0 * float(np.mean(self.sw)))
        self.sbreak = g.uniform(6, 11, strands)
        self.sphase = g.uniform(0, 100, strands)
        self.sflow0 = g.uniform(0, 2 * math.pi, strands)
        kn = list(self.kinds)
        kw = np.array([self.kinds[k] for k in kn])
        self.kn, self.kw = kn, kw / kw.sum()
        nv = (self.end - self.start) // 2 + 2
        self.veil_b = BillowSet(name + '_veil', nv, (3, 5))
        self.land_b = BillowSet(name + '_land', nv * strands, (3, 5))

    def flow(self, s, b):
        """0..1 how much strand s pours at frame b (pulses, ramps at start / end)."""
        ramp = smoothstep(self.start, self.start + 4, b) * (1 - smoothstep(self.end - 6, self.end, b))
        pulse = 0.55 + 0.45 * math.sin(b * 0.23 + self.sflow0[s]) * math.sin(b * 0.071 + self.sflow0[s] * 2)
        return ramp * max(0.0, pulse)

    def _layout(self):
        """Streams sized from the emitter segment: ~40 px of ledge per stream, 30-80 px wide."""
        if getattr(self, '_laid', False):
            return
        p0, p1 = self.em(self.start)
        Le = float(np.hypot(p1[0] - p0[0], p1[1] - p0[1]))
        g = core.rng('pour_layout', self.name)
        n = int(np.clip(round(Le / 55.0), 1, len(self.su)))
        if Le < 1.0:
            n = 1
        self.su = np.sort((np.arange(n) + g.uniform(0.3, 0.7, n)) / n)
        base = max(Le * 0.85 / n, float(self.sw.min()))
        widths = base * np.array([1.25, 0.7, 1.05])[:n] * g.uniform(0.9, 1.1, n)     # unequal streams
        self.sw_eff = np.clip(widths, 6.0, 140.0)
        # the sheet hangs ~5-7 widths before it tears: frames to fall that far
        drop = self.sw_eff * g.uniform(3.2, 4.6, n)
        self.sheet_len = np.clip(np.sqrt(2 * drop / max(self.g, 1e-3)), 8, 30).astype(int)
        self.sw = self.sw_eff
        self._laid = True

    def _sheet_poly(self, batch, C, Wd, B, s, l, cpal, line, drawing):
        """A ragged, tapering two-tone sheet along the hanging centreline C (top first)."""
        n = len(C)
        if n > 2:
            Cs = core.chaikin(C, 1, closed=False)
            Ws = np.interp(np.linspace(0, 1, len(Cs)), np.linspace(0, 1, n), Wd)
            Bs = np.interp(np.linspace(0, 1, len(Cs)), np.linspace(0, 1, n), np.array(B, np.float64))
        else:
            Cs, Ws, Bs = C, Wd, np.array(B, np.float64)
        nrm, _ = core.polyline_normals(Cs)

        def hn(b, side):
            return ((math.sin(b * 12.9898 + s * 78.233 + side * 37.719) * 43758.5453) % 1.0) * 2 - 1

        boil = 0.07 * np.sin(drawing * 1.7 + Bs * 0.9)
        el = np.array([hn(math.floor(b_), 1) for b_ in Bs]) * 0.36 + boil
        er = np.array([hn(math.floor(b_), 2) for b_ in Bs]) * 0.36 - boil
        lump = 1 + 0.3 * np.array([hn(math.floor(b_ / 2), 3) for b_ in Bs])      # bulges along the fall
        sway = np.array([hn(math.floor(b_ / 3), 4) for b_ in Bs]) * 0.14 * Ws \
            * np.linspace(0.0, 1.0, len(Cs))                                    # loose material sways
        Cs = Cs + nrm * sway[:, None]
        Ws = Ws * lump
        L = Cs + nrm * (Ws * 0.5 * (1 + el))[:, None]
        R = Cs - nrm * (Ws * 0.5 * (1 + er))[:, None]
        # a torn, jagged lower end
        tip = Cs[-1]
        down = Cs[-1] - Cs[-2]
        down = down / max(np.linalg.norm(down), 1e-9)
        side = np.array([-down[1], down[0]])
        w_end = Ws[-1]
        g = core.rng('pour_tip', self.name, s, drawing)
        jag = [tip + side * w_end * 0.35 + down * w_end * g.uniform(0.2, 0.7),
               tip + side * w_end * 0.05 + down * w_end * g.uniform(0.0, 0.3),
               tip - side * w_end * 0.2 + down * w_end * g.uniform(0.3, 0.9)]
        poly = np.concatenate([L, np.array(jag), R[::-1]], 0)
        batch.add(poly, cpal['shade'], ink=line, ink_w=1.0)
        # lit side: a narrower ragged band toward the light
        sgn = np.sign(np.sum(nrm * l[None, :], 1, keepdims=True))
        Li = Cs + nrm * sgn * (Ws * 0.08)[:, None]
        wl = Ws * 0.74 * (1 + 0.45 * el * sgn[:, 0]) * np.linspace(1.0, 0.55, len(Cs))
        batch.add(core.stroke_poly(Li, wl), cpal['lit'])

    def _emit(self, b, u, inherit=None):
        p0, p1 = self.em(b)
        p0 = np.asarray(p0, np.float64)
        p1 = np.asarray(p1, np.float64)
        q0, q1 = self.em(b - 4)
        pos = p0 + (p1 - p0) * u
        prev = np.asarray(q0, np.float64) + (np.asarray(q1, np.float64) - np.asarray(q0, np.float64)) * u
        v = (pos - prev) / 4.0                    # smoothed: the robot moves on 3s with holds
        sp = float(np.hypot(v[0], v[1]))
        if sp > 4.0:
            v = v * (4.0 / sp)
        return pos, v * (self.inherit if inherit is None else inherit)

    def _bits(self, b):
        g = core.rng('pour_bits', self.name, b)
        n = int(g.poisson(self.rate))
        s = g.integers(0, len(self.su), n)
        loose = g.random(n) < self.scatter
        u = np.where(loose, g.random(n), self.su[s] + g.normal(0, 0.035, n))
        keep = np.array([loose[i] or g.random() < self.flow(s[i], b) * 1.3 for i in range(n)], bool)
        kinds = g.choice(len(self.kn), size=n, p=self.kw)
        sz = self.size[0] + (self.size[1] - self.size[0]) * g.random(n) ** 3.2
        vj = np.stack([g.normal(0, self.jitter, n), g.uniform(0, self.jitter * 1.5, n)], 1)
        a0 = g.uniform(0, 2 * math.pi, n)
        w = g.uniform(-0.4, 0.4, n)
        return u[keep], kinds[keep], sz[keep], vj[keep], a0[keep], w[keep]

    def _fall(self, b, u, t, extra=None):
        pos, v = self._emit(b, u)
        if extra is not None:
            v = v + extra
        return pos + v * t + np.array([0, 0.5 * self.g * t * t])

    def draw(self, canvas, frame, light=None):
        """A few concentrated streams per emitter: each a falling column of clumps that stay
        together near the edge (stretched by their fall), break into smaller bits lower down
        and into powder near the ground; gaps between streams; very few stray crumbs."""
        light = self.light if light is None else light
        fh = held(frame, self.on, self.start)
        if fh < self.start:
            return canvas
        H, W = canvas.shape[:2]
        l = core.unit(light)
        bmin = max(self.start, fh - self.maxage)
        bmax = min(self.end, fh)
        drawing = fh // max(self.on, 1)
        cpal = palettes.DEBRIS['clod']
        line = cpal['ink']
        self._layout()
        # ---- thin dust veil behind each stream -------------------------------------------
        if self.veil:
            ids, PX, PY, RR, BR, PH, Z = [], [], [], [], [], [], []
            for s, u in enumerate(self.su):
                for b in range(self.start - self.start % 3, min(self.end, fh) + 1, 3):
                    if b < self.start:
                        continue
                    t = fh - b
                    life = self.maxage * 1.1
                    if t > life or self.flow(s, b) < 0.3:
                        continue
                    g = core.rng('pour_veil2', self.name, s, b)
                    pos, v = self._emit(b, float(u))
                    y = pos[1] + v[1] * t * 0.5 + 0.5 * self.g * 0.2 * t * t
                    if self.ground is not None:
                        y = min(y, self.ground - self.veil_size * 0.3)
                    x = pos[0] + v[0] * t * 0.5 + g.normal(0, 0.8) * t
                    ids.append(s * 4099 + b); PX.append(x); PY.append(y)
                    RR.append(self.veil_size * (0.3 + 0.7 * min(1.0, t / 18)) * g.uniform(0.7, 1.2))
                    BR.append(float(smoothstep(0.3, 1.0, t / life))); PH.append(t * 0.1); Z.append(-t)
            if ids:
                groups, holes = self.veil_b.groups(ids, PX, PY, RR, BR, PH, Z, drawing)
                C = (float(np.mean(PX)), float(np.mean(PY)))
                paint_groups(canvas, groups, holes, self.veil_pal, light, C,
                             max(float(np.ptp(PY)), self.veil_size * 3), line=0, opacity=self.veil_opacity,
                             vert=0.15)
        sheets = PolyBatch()
        clumps = PolyBatch()
        bits = PolyBatch()
        land, powder = [], []
        ph = self.powder_h
        for s, u in enumerate(self.su):
            Wt = self.sw_eff[s]
            T = int(self.sheet_len[s])
            # ---- 1) the sheet: one ragged mass hanging from the ledge (material of the last T
            #         frames; it keeps the ledge's velocity, so it hangs instead of trailing) ----
            C, Wd, B = [], [], []
            if self.start <= fh <= self.end + T:
                now, vs = self._emit(min(fh, self.end), float(u), inherit=1.0)
            for a_ in range(0, T + 1):
                b = fh - a_
                if b < self.start or b > self.end:
                    break
                fl = self.flow(s, b)
                if fl < 0.18:
                    break
                # attached to the ledge as it is now: drops under gravity, lags a little behind the
                # ledge's (smoothed) motion and stretches when the ledge rises
                drop = 0.5 * self.g * a_ * a_ + max(0.0, -vs[1]) * a_ * 0.5
                lag = float(np.clip(-vs[0] * a_ * 0.35, -0.8 * drop - 2, 0.8 * drop + 2))
                p = now + np.array([lag, drop])
                if self.ground is not None and p[1] > self.ground - ph * 0.5:
                    break
                C.append(p)
                Wd.append(Wt * (0.55 + 0.45 * fl) * (1 - 0.68 * (a_ / max(T, 1)) ** 0.8))
                B.append(b)
            if len(C) >= 2:
                self._sheet_poly(sheets, np.array(C), np.array(Wd), B, s, l, cpal, line, drawing)
            # ---- 2) the torn lower end: clumps and crumbs spreading as they fall ------------------
            for a_ in range(T + 1, self.maxage + 1):
                b = fh - a_
                if b < self.start or b > self.end:
                    continue
                fl = self.flow(s, b)
                if fl < 0.18:
                    continue
                g = core.rng('pour_tear', self.name, s, b)
                pos0, v0 = self._emit(b, float(np.clip(u + g.normal(0, 0.05), 0, 1)))
                v0 = v0 + np.array([g.normal(0, 0.35), g.uniform(0.0, 0.6)])
                p = pos0 + v0 * a_ + np.array([0, 0.5 * self.g * a_ * a_])
                gd = (self.ground - p[1]) if self.ground is not None else 1e9
                if gd < 0 or p[1] > H + 40:
                    if gd < 0 and self.ground is not None:
                        dy = self.ground - pos0[1]
                        if dy > 0:
                            tl = (-v0[1] + math.sqrt(max(v0[1] ** 2 + 2 * self.g * dy, 0))) / self.g
                            land.append((s, b, pos0[0] + v0[0] * tl, tl))
                    continue
                spread = (a_ - T) * 0.55
                vy = v0[1] + self.g * a_
                if gd < ph:
                    for k in range(2):
                        q = p + np.array([g.normal(0, Wt * 0.3 + spread), g.normal(0, 4)])
                        r = max(1.0, Wt * g.uniform(0.04, 0.08))
                        bits.add(shapes.blob(g, n=5, rmin=0.6, rmax=1.0, smooth=0) * r + q, cpal['shade'])
                    powder.append((s, b, p, Wt * 0.3))
                    continue
                near_tear = a_ - T < 6
                if near_tear or g.random() < 0.4:
                    q = p + np.array([g.normal(0, 1.0) * (Wt * 0.22 + spread), 0])
                    sz = Wt * fl * (g.uniform(0.24, 0.42) if near_tear else g.uniform(0.1, 0.24)) \
                        * (1 - 0.35 * (a_ - T) / self.maxage)
                    poly = shapes.blob(g, n=7, rmin=0.62, rmax=1.0, smooth=1)
                    poly[:, 1] *= min(1.8, 1.0 + 0.05 * max(vy, 0.0))
                    poly = core.rot(poly, g.normal(0, 0.3)) * sz + q
                    if sz > 2.6:
                        term = (q[0] + l[0] * 0.6 * sz, q[1] + l[1] * 0.6 * sz, 1.05 * sz)
                        clumps.add(poly, cpal['lit'], cpal['shade'], line, 1.0, term)
                    else:
                        clumps.add(poly, cpal['shade'])
                for k in range(int(g.random() < 0.45)):
                    q = p + np.array([g.normal(0, Wt * 0.35 + spread * 1.3), g.normal(0, 6)])
                    r = max(1.0, Wt * g.uniform(0.03, 0.07))
                    bits.add(shapes.blob(g, n=5, rmin=0.6, rmax=1.0, smooth=0) * r + q, cpal['shade'])
        # ---- very few stray crumbs ------------------------------------------------------------
        for b in range(bmin, bmax + 1):
            g = core.rng('pour_stray', self.name, b)
            if g.random() > self.rate * 0.03:
                continue
            u0 = g.random()
            t = fh - b
            pos, v = self._emit(b, u0)
            v = v + np.array([g.normal(0, 0.6), g.uniform(0, 0.8)])
            p = pos + v * t + np.array([0, 0.5 * self.g * t * t])
            if (self.ground is not None and p[1] > self.ground) or p[1] > H + 20:
                continue
            sz = self.size[0] + (self.size[1] - self.size[0]) * g.random() ** 2
            kind = 'crumb' if g.random() < 0.8 else 'moss'
            add_piece(bits, kind, shapes.KINDS[kind](core.rng('pour_stray_shape', self.name, b)), p,
                      g.uniform(0, 6.28) + 0.2 * t, sz, light, 0.9)
        # ---- dust: puffs where the powder falls and where streams land ----------------------
        ids, PX, PY, RR, BR, PH, Z, GYs = [], [], [], [], [], [], [], []
        for s, b, p, size in powder[::3]:
            g = core.rng('pour_powder', self.name, s, b)
            ids.append(5000 + (s * 997 + b) % 4000)
            PX.append(p[0] + g.normal(0, size)); PY.append(p[1])
            RR.append(size * g.uniform(1.0, 1.8)); BR.append(0.35); PH.append(b * 0.3); Z.append(-b)
            GYs.append(1e9)
        if self.ground is not None:
            seen = set()
            for s, b, x, tl in land:
                key = (s, b // 3)
                if key in seen:
                    continue
                seen.add(key)
                a_ = fh - (b + tl)
                life = 22.0
                if a_ < 0 or a_ > life:
                    continue
                g = core.rng('pour_land', self.name, s, b)
                tt = a_ / life
                side = g.choice([-1.0, 1.0])
                R = self.land_size * (0.4 + 0.6 * min(1.0, a_ / 8)) * g.uniform(0.6, 1.15) * max(0.4, self.flow(s, b))
                ids.append(s * 997 + b)
                PX.append(x + side * self.land_size * 0.9 * (1 - math.exp(-a_ / 6)))
                PY.append(self.ground - R * 0.5 - self.land_size * 0.5 * tt)
                RR.append(R); BR.append(float(smoothstep(0.35, 1.0, tt))); PH.append(side * a_ * 0.15)
                Z.append(-a_); GYs.append(self.ground + 2)
        if ids:
            groups, holes = self.land_b.groups(ids, PX, PY, RR, BR, PH, Z, drawing, ground=np.array(GYs))
            C = (float(np.mean(PX)), float(np.mean(PY)))
            paint_groups(canvas, groups, holes, self.land_pal, light, C, self.land_size * 3,
                         line=1.5, opacity=0.95, tone_alpha=self.land_alpha)
        bits.draw(canvas)
        clumps.draw(canvas)
        sheets.draw(canvas)
        return canvas

    def _streak(self, batch, p, v, size, cpal):
        """Tapered dark streak behind a falling piece (drawn smear of its fall)."""
        sp = float(np.hypot(v[0], v[1]))
        if sp < 1.5 or size < 2:
            return
        dirv = v / sp
        L = min(sp * 2.4, size * 7)
        q = np.linspace(0, 1, 6)
        pts = p[None, :] - dirv[None, :] * (q[:, None] * L)
        wid = size * 0.9 * (1 - q) ** 1.4 + 0.2
        batch.add(core.stroke_poly(pts, wid), cpal['shade'], alpha=0.75)
