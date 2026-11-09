"""trail.py - the climax light trail: a wide curving ribbon of light with billowing cel mist.

Give the trail's history as screen points (oldest first, newest = the robot) with the frame
each point was laid down; the lead projects them with the current camera, so the trail sits
in the sky while the camera pans.

Layers (back to front):
  * mist billows behind the ribbon (cool lilac shadows, peach mid, warm white tops) that are
    born at the head on every other drawing, swell, roll outward and break up with age;
  * the ribbon: hot rose rim, orange edge, gold, white core; wide at the head, tapering to the
    tail, edges re-drawn on 2s;
  * a few mist billows in front of the ribbon edges (ties the two together);
  * glow along the core and at the head (light buffer).

    tr = LightTrail('S16_trail', width=90)
    tr.draw(canvas, frame, points, births, light_buf=L)
"""
import math

import numpy as np

from . import core, palettes, raster
from .core import PolyBatch, ease_out, held, smoothstep
from .dust import BillowSet, paint_groups

TAU = 2 * math.pi


class LightTrail:
    def __init__(self, name, width=90.0, life=96, mist=True, mist_size=1.0, light=(0.6, -0.8),
                 on=2, palette=None, mist_palette=None, mist_every=4, glow=1.0, head_grow=6):
        self.name = name
        self.width = float(width)
        self.life = int(life)
        self.mist = mist
        self.mist_size = mist_size
        self.light = light
        self.on = on
        self.pal = palettes.TRAIL if palette is None else palette
        self.mpal = palettes.TRAIL_MIST if mist_palette is None else mist_palette
        self.every = mist_every
        self.glow_gain = glow
        self.head_grow = head_grow
        self.bil = BillowSet(name + '_mist', 4096, (4, 6))

    def _widths(self, ages, u, drawing):
        """ages: frames since laid; u: 0 at head .. 1 at tail (arc length fraction)."""
        grow = 0.8 + 0.2 * np.minimum(1.0, ages / self.head_grow)
        swell = 1 + 0.35 * smoothstep(0, 40, ages)
        taper = (1 - u) ** 0.55 * (1 - smoothstep(self.life * 0.7, self.life, ages))
        wob = 1 + 0.06 * np.sin(np.arange(len(ages)) * 0.9 + drawing * 1.7)
        return self.width * grow * swell * taper * wob

    def draw(self, canvas, frame, points, births=None, light=None, light_buf=None):
        P = np.asarray(points, np.float64)
        n = len(P)
        if n < 2:
            return canvas
        if births is None:
            births = np.arange(frame - n + 1, frame + 1)
        births = np.asarray(births, np.float64)
        light = self.light if light is None else light
        fh = held(frame, self.on)
        drawing = fh // max(self.on, 1)
        keep = births <= fh
        P, births = P[keep], births[keep]
        if len(P) < 2:
            return canvas
        ages = fh - births
        alive = ages <= self.life
        if alive.sum() < 2:
            return canvas
        P, births, ages = P[alive], births[alive], ages[alive]
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        u = 1 - s / max(s[-1], 1e-6)                   # 0 at head (last point)
        w = self._widths(ages, u, drawing)
        nrm, _ = core.polyline_normals(P)
        # ---- mist billows ---------------------------------------------------------------
        back_groups, front_groups, holes_b = [], [], []
        if self.mist:
            ids, PX, PY, RR, BR, PH, Z, FR = [], [], [], [], [], [], [], []
            for k in range(len(P)):
                b = int(births[k])
                if b % self.every:
                    continue
                a = ages[k]
                lifem = self.life * 0.9
                if a > lifem:
                    continue
                g = core.rng('trailmist', self.name, b)
                for side in (-1, 1):
                    if g.random() < 0.3:
                        continue
                    t = a / lifem
                    big = 1.0 + 0.7 * (g.random() < 0.18)
                    r = self.width * self.mist_size * g.uniform(0.35, 0.8) * big * (0.5 + 1.1 * float(ease_out(min(1.0, a / 26.0), 2)))
                    off = side * (w[k] * g.uniform(0.25, 0.5) + r * (0.15 + 0.6 * t) * g.uniform(0.6, 1.4)
                                  + self.width * 0.3 * t * g.uniform(0.3, 1.2))
                    x = P[k, 0] + nrm[k, 0] * off
                    y = P[k, 1] + nrm[k, 1] * off + self.width * 0.25 * t       # mist sinks slowly
                    idx = (b // self.every) * 2 + (side > 0)
                    ids.append(idx); PX.append(x); PY.append(y); RR.append(r)
                    BR.append(float(smoothstep(0.35, 1.0, t + g.uniform(-0.08, 0.08))))
                    PH.append(side * a / 20.0); Z.append(-a + g.random())
                    FR.append(g.random() < 0.3)
            if ids:
                groups, holes = self.bil.groups(ids, PX, PY, RR, BR, PH, Z, drawing)
                front_ids = set(i for i, f in zip(ids, FR) if f)
                for gg in groups:
                    (front_groups if gg[3] in front_ids else back_groups).append(gg)
                holes_b = holes
                C = (float(np.mean(PX)), float(np.mean(PY)))
                size = max(self.width * 3.0, 1.0)
                if back_groups:
                    paint_groups(canvas, back_groups, holes_b, self.mpal, light, C, size,
                                 line=max(1.5, self.width * 0.03), local=0.7, vert=0.35)
        # ---- ribbon -----------------------------------------------------------------------
        Ps = core.chaikin(P, 2, closed=False) if len(P) > 3 else P
        ws = np.interp(np.linspace(0, 1, len(Ps)), np.linspace(0, 1, len(w)), w)
        b = PolyBatch()
        pal = self.pal
        for k_w, col in ((1.0, pal['rim']), (0.92, pal['edge']), (0.84, pal['gold']), (0.7, pal['core'])):
            b.add(core.stroke_poly(Ps, ws * k_w, cap_pts=6), col)
        b.draw(canvas)
        if front_groups:
            C = (float(np.mean(P[:, 0])), float(np.mean(P[:, 1])))
            paint_groups(canvas, front_groups, [], self.mpal, light, C, max(self.width * 3.0, 1.0),
                         line=max(1.5, self.width * 0.03), local=0.7, vert=0.35)
        # ---- glow (photography) --------------------------------------------------------------
        if light_buf is not None and self.glow_gain > 0:
            rows = []
            gold = palettes.LIGHT_GOLD
            for k in range(0, len(P), 3):
                inten = 0.22 * (1 - u[k]) ** 1.5 * self.glow_gain
                if inten < 0.01:
                    continue
                rows.append((P[k, 0], P[k, 1], w[k] * 0.2, w[k] * 1.6 + 10, *gold, inten, 1.5))
            hx, hy = P[-1]
            rows.append((hx, hy, self.width * 0.3, self.width * 3.5, *gold, 0.6 * self.glow_gain, 1.4))
            raster.add_soft_discs(light_buf, np.asarray(rows, np.float64))
        return canvas
