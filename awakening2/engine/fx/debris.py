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
    iw = float(np.clip(0.16 * size, 0.8, 2.6)) * ink_scale
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
                 veil_opacity=0.6, scatter=0.25, land_size=None):
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
        self.maxage = maxage
        self.veil_size = veil_size
        self.veil_opacity = veil_opacity
        self.scatter = scatter
        self.land_size = veil_size * 1.2 if land_size is None else land_size
        self.kinds = {'crumb': 0.66, 'clod': 0.22, 'moss': 0.05, 'root': 0.05, 'vine': 0.02} if kinds is None else kinds
        g = core.rng('pour', name)
        self.su = np.sort(g.uniform(0.08, 0.92, strands))
        self.sw = g.uniform(strand_width[0], strand_width[1], strands)
        self.clump_rate = 0.42
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

    def _emit(self, b, u):
        p0, p1 = self.em(b)
        p0 = np.asarray(p0, np.float64)
        p1 = np.asarray(p1, np.float64)
        q0, q1 = self.em(b - 1)
        pos = p0 + (p1 - p0) * u
        prev = np.asarray(q0, np.float64) + (np.asarray(q1, np.float64) - np.asarray(q0, np.float64)) * u
        return pos, (pos - prev) * self.inherit

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
        light = self.light if light is None else light
        fh = held(frame, self.on, self.start)
        if fh < self.start:
            return canvas
        H, W = canvas.shape[:2]
        l = core.unit(light)
        bmin = max(self.start, fh - self.maxage)
        bmax = min(self.end, fh)
        drawing = fh // max(self.on, 1)
        # ---- veil billows (behind) ------------------------------------------------------
        if self.veil:
            ids, PX, PY, RR, BR, PH, Z = [], [], [], [], [], [], []
            for b in range(self.start, min(self.end, fh) + 1, 2):
                t = fh - b
                life = self.maxage * 1.1
                if t > life:
                    continue
                g = core.rng('pour_veil', self.name, b)
                s = int(g.integers(0, len(self.su)))
                if g.random() > 0.35 + self.flow(s, b):
                    continue
                u = self.su[s] + g.normal(0, 0.05)
                pos, v = self._emit(b, u)
                y = pos[1] + v[1] * t * 0.6 + 0.5 * self.g * 0.22 * t * t
                x = pos[0] + v[0] * t * 0.6 + g.normal(0, 1.0) * t
                ids.append((b - self.start) // 2); PX.append(x); PY.append(y)
                RR.append(self.veil_size * (0.35 + 0.85 * min(1.0, t / 16)) * g.uniform(0.8, 1.2))
                BR.append(smoothstep(0.35, 1.0, t / life)); PH.append(t * 0.12 * (1 if x > pos[0] else -1))
                Z.append(-t)
            if ids:
                groups, holes = self.veil_b.groups(ids, PX, PY, RR, BR, PH, Z, drawing)
                C = (float(np.mean(PX)), float(np.mean(PY)))
                paint_groups(canvas, groups, holes, palettes.VEIL, light, C,
                             max(float(np.ptp(PY)), self.veil_size * 3), line=0, opacity=self.veil_opacity,
                             vert=0.15)
        batch = PolyBatch()
        streaks = PolyBatch()
        land = []
        puffs = []
        cpal = palettes.DEBRIS['clod']
        # ---- clumps: tear off each spill point, fall, split, shed crumbs and powder ----------
        for s, u in enumerate(self.su):
            for b in range(bmin, bmax + 1):
                g = core.rng('pour_clump', self.name, s, b)
                fl = self.flow(s, b)
                if g.random() > fl * self.clump_rate:
                    continue
                t = fh - b
                pos0, v0 = self._emit(b, float(np.clip(u + g.normal(0, 0.03), 0, 1)))
                v0 = v0 + np.array([g.normal(0, 0.45), g.uniform(0.0, 1.0)])
                csz = self.sw[s] * g.uniform(0.32, 0.55) * (0.65 + 0.5 * fl)
                tb = g.uniform(4.0, 10.0)
                shape = shapes.KINDS['clod'](core.rng('pour_clump_shape', self.name, s, b))
                a0, w0 = g.uniform(0, 2 * math.pi), g.uniform(-0.25, 0.25)
                if self.ground is not None:
                    dy = self.ground - pos0[1]
                    if dy > 0:
                        tl = (-v0[1] + math.sqrt(max(v0[1] ** 2 + 2 * self.g * dy, 0))) / self.g
                        land.append((s, b, pos0[0] + v0[0] * tl, tl))
                if t < tb:
                    p = pos0 + v0 * t + np.array([0, 0.5 * self.g * t * t])
                    if self.ground is not None and p[1] > self.ground:
                        continue
                    v = v0 + np.array([0, self.g * t])
                    self._streak(streaks, p, v, csz, cpal)
                    add_piece(batch, 'clod', shape, p, a0 + w0 * t, csz * (1 - 0.12 * t / tb), light, 0.9)
                    continue
                # split: 3-5 pieces drift apart, each sheds a column of crumbs and powder
                pb = pos0 + v0 * tb + np.array([0, 0.5 * self.g * tb * tb])
                vb = v0 + np.array([0, self.g * tb])
                tt = t - tb
                if tt < 10:
                    puffs.append((s, b, pb, tt, csz))
                npc = int(g.integers(3, 6))
                for k in range(npc):
                    ang = g.uniform(0, 2 * math.pi)
                    dv = np.array([math.cos(ang), math.sin(ang) * 0.6]) * g.uniform(0.4, 1.6)
                    pk = pb + (vb + dv) * tt + np.array([0, 0.5 * self.g * tt * tt])
                    if (self.ground is not None and pk[1] > self.ground) or pk[1] > H + 30:
                        continue
                    sz = csz * g.uniform(0.26, 0.5) * (1 - 0.35 * min(1.0, tt / 18))
                    kind = 'moss' if g.random() < 0.12 else ('crumb' if sz < 4 else 'clod')
                    sh = shapes.KINDS[kind](core.rng('pour_piece', self.name, s, b, k))
                    self._streak(streaks, pk, vb + dv + np.array([0, self.g * tt]), sz, cpal)
                    add_piece(batch, kind, sh, pk, a0 + k + w0 * t * 1.5, sz, light, 0.9)
                    # crumbs and powder shed from this piece (they fall a little slower)
                    for m in range(0, int(min(tt, 14)), 2):
                        am = tt - m
                        jit = np.array([g.normal(0, 0.35), g.normal(0, 0.2)])
                        q = pb + (vb + dv) * m + np.array([0, 0.5 * self.g * m * m]) \
                            + (vb + dv * 0.5 + jit) * am + np.array([0, 0.5 * self.g * 0.82 * am * am])
                        if (self.ground is not None and q[1] > self.ground) or q[1] > H + 10:
                            continue
                        qs = max(1.2, csz * g.uniform(0.06, 0.16))
                        batch.add(core.chaikin(core.rot(shapes.blob(g, n=5, rmin=0.5, rmax=1.0, smooth=0), g.uniform(0, 6)) * qs, 0) + q,
                                  cpal['shade'] if g.random() < 0.7 else cpal['lit'])
        # ---- loose bits and clumps ----------------------------------------------------------
        for b in range(bmin, bmax + 1):
            u, kinds, sz, vj, a0, w = self._bits(b)
            t = fh - b
            for i in range(len(u)):
                p = self._fall(b, u[i], t, vj[i])
                if p[1] > H + 30 or (self.ground is not None and p[1] > self.ground):
                    continue
                kind = self.kn[kinds[i]]
                parts = shapes.KINDS[kind](core.rng('pour_shape', self.name, b, i))
                add_piece(batch, kind, parts, p, a0[i] + w[i] * t, sz[i], light, 0.9)
        # ---- dust: small puffs where clumps break, kicked-up dust where they land ----------
        ids, PX, PY, RR, BR, PH, Z, GYs = [], [], [], [], [], [], [], []
        for s, b, pb, tt, csz in puffs:
            g = core.rng('pour_breakpuff', self.name, s, b)
            life = 10.0
            t_ = tt / life
            ids.append(5000 + (s * 997 + b) % 4000)
            PX.append(pb[0] + g.normal(0, csz * 0.3)); PY.append(pb[1] - csz * 0.6 * t_)
            RR.append(csz * (0.5 + 0.7 * min(1.0, tt / 4)) * g.uniform(0.7, 1.1))
            BR.append(float(smoothstep(0.25, 1.0, t_))); PH.append(t_ * 2); Z.append(-tt); GYs.append(1e9)
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
            paint_groups(canvas, groups, holes, palettes.DUST, light, C, self.land_size * 3,
                         line=2.0, opacity=1.0)
        streaks.draw(canvas)
        batch.draw(canvas)
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
