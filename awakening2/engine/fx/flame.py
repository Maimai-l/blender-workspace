"""flame.py - engine flames for the thruster bells: ignition sputter, then a layered cel flame.

Layers (outer -> inner): red-brown edge, orange, yellow, white core.  Each layer is a body
(teardrop from the nozzle) plus several tapered licks at the tail whose lengths, waves and
splits change every frame (flames flicker on 1s).  Optional shock diamonds along the core,
heat-shimmer strokes past the tip, sparks and smoke puffs on the false starts, and a glow
in the light buffer (photography).

    fl = EngineFlame('S12_left', ignite=36, sputters=[(20, 0.35), (26, 0.5), (31, 0.3)])
    fl.draw(canvas, frame, nozzle=(x, y), direction=(dx, dy), radius=40, length=420, light=L)
"""
import math

import numpy as np

from . import core, palettes
from .core import PolyBatch, smoothstep

TAU = 2 * math.pi


class EngineFlame:
    """sputters: list of (frame, strength 0..1[, duration frames]) false starts before `ignite`.
    ignite: frame of the real ignition (power ramps with an overshoot over ~4 frames).
    shutoff: optional frame where the flame dies.  diamonds / shimmer / smoke: extras."""

    def __init__(self, name, ignite, sputters=(), shutoff=None, diamonds=True, shimmer=False,
                 smoke=True, sparks=True, palette=None, glow=1.0, licks=5):
        self.name = name
        self.ignite = int(ignite)
        self.sputters = [tuple(s) + (4,) * (3 - len(s)) for s in sputters]
        self.shutoff = shutoff
        self.diamonds = diamonds
        self.shimmer = shimmer
        self.smoke = smoke
        self.sparks = sparks
        self.pal = palettes.FLAME if palette is None else palette
        self.glow_gain = glow
        self.licks = licks

    # ------------------------------------------------------------------ timeline
    def power(self, frame):
        p = 0.0
        for f0, s, dur in self.sputters:
            a = frame - f0
            if 0 <= a <= dur:
                # pop up in one frame, choke out
                p = max(p, s * (1.0 if a < 1 else (1 - a / dur) ** 1.5) * (0.8 + 0.4 * self._rnd(frame, 'sp')))
        a = frame - self.ignite
        if a >= 0:
            ramp = float(smoothstep(0, 4, a))
            over = 0.18 * math.exp(-max(0, a - 3) / 4.0) * float(smoothstep(2, 4, a))
            p = max(p, ramp * (1 + over))
        if self.shutoff is not None and frame >= self.shutoff:
            p *= max(0.0, 1 - (frame - self.shutoff) / 4.0)
        return p

    def _rnd(self, frame, *k):
        return (core.seed(self.name, frame, *k) % 100003) / 100003.0

    # ------------------------------------------------------------------ shapes
    def _layer(self, frame, li, p, L, r, k_len, k_wid):
        """Body + licks for one layer in flame-local coords (s along, t across)."""
        g = core.rng('flame', self.name, frame, li)
        n = 28
        s = np.linspace(0, 1, n)
        bulge = 1.08 + 0.34 * np.sin(np.clip(s / 0.28, 0, 1) * math.pi * 0.5) * (1 - s)
        prof = r * k_wid * bulge * (1 - s ** 1.7) ** 0.75
        # travelling waves along the edges (flicker)
        ph = g.uniform(0, TAU, 2)
        wl = 1 + 0.10 * np.sin(s * 9 - frame * 1.9 + ph[0]) * s
        wr = 1 + 0.10 * np.sin(s * 9 - frame * 1.7 + ph[1]) * s
        Lb = L * k_len * 0.72
        left = np.stack([s * Lb, -prof * wl], 1)
        right = np.stack([s[::-1] * Lb, prof[::-1] * wr[::-1]], 1)
        body = np.concatenate([np.array([[-r * 0.15, -r * k_wid * 0.9]]), left, right,
                               np.array([[-r * 0.15, r * k_wid * 0.9]])], 0)
        polys = [body]
        # licks from the rear half of the body
        nl = self.licks if li < 3 else 2
        for j in range(nl):
            u = (j + 0.5) / nl
            t0 = (u - 0.5) * 1.6
            s0 = 0.35 + 0.25 * g.random()
            base_w = r * k_wid * (0.55 - 0.25 * abs(t0)) * g.uniform(0.7, 1.1)
            ln = L * k_len * g.uniform(0.35, 0.62) * (1 - 0.45 * abs(t0))
            x0 = s0 * Lb
            y0 = t0 * float(np.interp(s0, s, prof)) * 0.8
            ang = t0 * 0.18 + g.normal(0, 0.06)
            m = 8
            q = np.linspace(0, 1, m)
            wav = g.uniform(0.04, 0.12) * ln * np.sin(q * math.pi * g.uniform(1, 2) + g.uniform(0, TAU)) * q
            cx = x0 + q * ln * math.cos(ang) - wav * math.sin(ang)
            cy = y0 + q * ln * math.sin(ang) + wav * math.cos(ang)
            w = base_w * (1 - q) ** 0.9
            P = core.stroke_poly(np.stack([cx, cy], 1), np.maximum(w * 2, 0.3))
            polys.append(P)
        return polys

    def draw(self, canvas, frame, nozzle, direction, radius, length, light=None, intensity=1.0,
             smoke_light=(0.55, -0.83)):
        p = self.power(frame) * intensity
        d = core.unit(direction)
        nrm = np.array([-d[1], d[0]])
        N = np.asarray(nozzle, np.float64)

        def to_screen(P):
            return N[None, :] + P[:, :1] * d[None, :] + P[:, 1:2] * nrm[None, :]

        # sputter smoke (behind the flame): small billows popping out and drifting
        if self.smoke and self.sputters:
            from .dust import BillowSet, paint_groups
            if not hasattr(self, '_smoke_b'):
                self._smoke_b = BillowSet(self.name + '_smoke', 64, (3, 5))
            ids, PX, PY, RR, BR, PH, Z = [], [], [], [], [], [], []
            for q, (f0, s, dur) in enumerate(self.sputters + [(self.ignite, 0.8, 4)]):
                for k in range(3):
                    b = f0 + k
                    a = frame - b
                    life = 16.0
                    if a < 0 or a > life:
                        continue
                    g = core.rng('smoke', self.name, f0, k)
                    t = a / life
                    off = d * radius * (0.9 + 1.4 * k + g.uniform(0, 1) + 1.2 * t) + nrm * radius * g.normal(0, 0.45)
                    pos = N + off + np.array([0, -radius * 0.9 * t])
                    ids.append(q * 3 + k); PX.append(pos[0]); PY.append(pos[1])
                    RR.append(radius * 0.42 * (0.5 + 0.9 * min(1.0, a / 5)) * (0.6 + 0.6 * s) * g.uniform(0.8, 1.2))
                    BR.append(float(smoothstep(0.3, 1.0, t))); PH.append(t * 2.0); Z.append(-a)
            if ids:
                groups, holes = self._smoke_b.groups(ids, PX, PY, RR, BR, PH, Z, frame // 2)
                C = (float(np.mean(PX)), float(np.mean(PY)))
                paint_groups(canvas, groups, holes, palettes.SMOKE, smoke_light, C, radius * 2.5,
                             line=max(1.0, radius * 0.04), opacity=0.95)
        if p <= 0.02:
            return canvas
        L = length * p * (0.93 + 0.14 * self._rnd(frame, 'len'))
        r = radius * (0.75 + 0.25 * min(1.0, p))
        batch = PolyBatch()
        ks = [(1.0, 1.0), (0.82, 0.8), (0.62, 0.6), (0.4, 0.36)]
        cols = self.pal
        for li, (kl, kw) in enumerate(ks):
            for P in self._layer(frame, li, p, L, r, kl, kw):
                batch.add(to_screen(P), cols[3 - li] if li < 4 else cols[0])
        # shock diamonds along the core
        if self.diamonds and p > 0.6:
            nd = 4
            for j in range(nd):
                sj = 0.16 + 0.15 * j
                sz = r * 0.32 * (1 - 0.18 * j) * (0.9 + 0.2 * self._rnd(frame, 'dm', j))
                c = np.array([sj * L * 0.72, 0])
                dm = np.array([[c[0] - sz * 1.4, 0], [c[0], -sz * 0.55], [c[0] + sz * 1.4, 0], [c[0], sz * 0.55]])
                batch.add(to_screen(dm), cols[0], ink=cols[1], ink_w=max(1.0, r * 0.05))
        batch.draw(canvas)
        # sparks on the false starts and at ignition
        if self.sparks:
            sb = PolyBatch()
            for f0, s, dur in self.sputters + [(self.ignite, 1.0, 6)]:
                a = frame - f0
                if not (0 <= a <= 6):
                    continue
                g = core.rng('spark', self.name, f0)
                for j in range(int(6 + 8 * s)):
                    ang = g.normal(0, 0.45)
                    v = radius * g.uniform(0.25, 0.6)
                    dirj = d * math.cos(ang) + nrm * math.sin(ang)
                    pos = N + dirj * (radius * 0.5 + v * a) + np.array([0, 0.02 * radius * a * a])
                    ln = radius * g.uniform(0.15, 0.35) * (1 - a / 7)
                    seg = np.stack([pos - dirj * ln, pos], 0)
                    sb.add(core.stroke_poly(seg, [0.4, max(1.2, radius * 0.06)]), cols[1] if j % 3 else cols[0])
            sb.draw(canvas)
        # heat shimmer past the tip: faint wavy strokes
        if self.shimmer and p > 0.7:
            sh = PolyBatch()
            for j in range(4):
                g = core.rng('shimmer', self.name, frame, j)
                s0 = L * (0.78 + 0.1 * j) + radius * 0.3
                q = np.linspace(0, 1, 10)
                t0 = (j - 1.5) * r * 0.45
                P = np.stack([s0 + q * L * 0.18, t0 + np.sin(q * TAU * 1.5 + g.uniform(0, TAU)) * r * 0.12], 1)
                sh.add(core.stroke_poly(to_screen(P), np.sin(q * math.pi) * max(1.0, r * 0.05)),
                       palettes.LIGHT_GOLD, alpha=0.18)
            sh.draw(canvas)
        return canvas

    def glow(self, light, frame, nozzle, direction, radius, length, intensity=1.0, preglow=None):
        """Additive glow (photography) around the nozzle and along the flame.
        preglow=(start_frame, level): the bell warms up from start_frame until ignition."""
        p = self.power(frame) * intensity
        if light is None:
            return light
        if preglow is not None and frame < self.ignite + 4:
            f0, lev = preglow
            if frame >= f0:
                warm = lev * float(smoothstep(f0, self.ignite, frame)) * (0.85 + 0.3 * self._rnd(frame, 'pg'))
                from . import raster as _r
                N = np.asarray(nozzle, np.float64)
                _r.add_soft_discs(light, np.array([[N[0], N[1], radius * 0.5, radius * 2.2,
                                                    *palettes.LIGHT_WARM, warm, 1.4]], np.float64))
        if p <= 0.02:
            return light
        from . import raster
        d = core.unit(direction)
        N = np.asarray(nozzle, np.float64)
        L = length * p
        rows = []
        warm = palettes.LIGHT_WARM
        gold = palettes.LIGHT_GOLD
        fl = 0.9 + 0.2 * self._rnd(frame, 'glow')
        rows.append((N[0], N[1], radius * 0.6, radius * 3.2, *gold, 0.55 * p * fl * self.glow_gain, 1.6))
        for j in range(4):
            q = N + d * L * (0.15 + 0.2 * j)
            rows.append((q[0], q[1], radius * 0.2, radius * (2.4 - 0.3 * j), *warm,
                         0.22 * p * fl * self.glow_gain, 1.8))
        raster.add_soft_discs(light, np.asarray(rows, np.float64))
        return light
