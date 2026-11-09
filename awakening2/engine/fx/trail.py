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

    def draw(self, canvas, frame, points, births=None, light=None, light_buf=None, scales=None):
        """scales: optional per-point width factors (perspective: near points wider)."""
        P = np.asarray(points, np.float64)
        sc = np.ones(len(P)) if scales is None else np.asarray(scales, np.float64)
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
        P, births, sc = P[keep], births[keep], sc[keep]
        if len(P) < 2:
            return canvas
        ages = fh - births
        alive = ages <= self.life
        if alive.sum() < 2:
            return canvas
        P, births, ages, sc = P[alive], births[alive], ages[alive], sc[alive]
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        s = np.concatenate([[0], np.cumsum(seg)])
        u = 1 - s / max(s[-1], 1e-6)                   # 0 at head (last point)
        w = self._widths(ages, u, drawing) * sc
        nrm, _ = core.polyline_normals(P)
        # ---- mist billows: uneven lumps, some long ones stretched along the path ----------------
        back_groups, front_groups, holes_b, wisps_all = [], [], [], []
        tang = np.stack([nrm[:, 1], -nrm[:, 0]], 1)
        if self.mist:
            ids, PX, PY, RR, BR, PH, Z, FR, ST, TA = [], [], [], [], [], [], [], [], [], []
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
                    if g.random() < 0.35:
                        continue
                    t = a / lifem
                    # strongly varied sizes: a few big lumps, many small, some long stretched ones
                    cls = g.random()
                    if cls < 0.18:
                        size_k, stretch = 1.3 * g.uniform(0.85, 1.15), g.uniform(2.2, 3.0)      # long lumps
                    elif cls < 0.62:
                        size_k = 0.8 * g.uniform(0.8, 1.2)
                        stretch = g.uniform(1.5, 2.3) if g.random() < 0.55 else 1.0
                    else:
                        size_k, stretch = 0.48 * g.uniform(0.8, 1.2), 1.0
                    W0 = self.width * sc[k]
                    r = W0 * self.mist_size * 0.55 * size_k * (0.5 + 1.1 * float(ease_out(min(1.0, a / 26.0), 2)))
                    off = side * (w[k] * g.uniform(0.05, 0.35) + r * (0.05 + 0.45 * t) * g.uniform(0.4, 1.2)
                                  + W0 * 0.3 * t * g.uniform(0.2, 1.2))
                    x = P[k, 0] + nrm[k, 0] * off + tang[k, 0] * g.normal(0, r * 0.4)
                    y = P[k, 1] + nrm[k, 1] * off + tang[k, 1] * g.normal(0, r * 0.4) + W0 * 0.25 * t
                    idx = (b // self.every) * 2 + (side > 0)
                    ids.append(idx); PX.append(x); PY.append(y); RR.append(r)
                    BR.append(float(smoothstep(0.3, 1.0, t + g.uniform(-0.08, 0.08))))
                    PH.append(side * a / 20.0); Z.append(-a + g.random())
                    FR.append(g.random() < 0.3 and size_k > 0.7)
                    ST.append(stretch); TA.append(math.atan2(tang[k, 1], tang[k, 0]))
            if ids:
                groups, holes, wisps = self.bil.groups(ids, PX, PY, RR, BR, PH, Z, drawing, wisps=True)
                wisps_all = wisps
                info = {ids[j] % self.bil.n: (ST[j], TA[j], PX[j], PY[j]) for j in range(len(ids))}
                out = []
                for gg in groups:
                    st, ta, cx, cy = info.get(gg[3], (1.0, 0.0, 0.0, 0.0))
                    if st > 1.01:
                        # stretch the whole billow along the path
                        ca, sa = math.cos(ta), math.sin(ta)
                        lob = []
                        for L in gg[1]:
                            L = list(L) + [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0][len(L) - 4:] if len(L) < 11 else list(L)
                            dx, dy = L[0] - cx, L[1] - cy
                            pa = dx * ca + dy * sa
                            pp = -dx * sa + dy * ca
                            pa *= st
                            L[0] = cx + pa * ca - pp * sa
                            L[1] = cy + pa * sa + pp * ca
                            L[4] = st
                            L[5] = min(L[5], 1.0) * 0.9
                            L[6] = ta
                            lob.append(tuple(L))
                        gg = (gg[0], lob, gg[2], gg[3]) + tuple(gg[4:])
                    out.append(gg)
                front_ids = set(i % self.bil.n for i, f in zip(ids, FR) if f)
                for gg in out:
                    (front_groups if gg[3] in front_ids else back_groups).append(gg)
                holes_b = holes
                C = (float(np.mean(PX)), float(np.mean(PY)))
                self._mist_c = C
                size = max(self.width * 3.0, 1.0)
                if back_groups:
                    paint_groups(canvas, back_groups, holes_b, self.mpal, light, C, size,
                                 line=0.0, local=0.75, vert=0.3, bias=0.15, wisps=wisps_all)
        # ---- ribbon: white-gold core, soft edge, lumpy, dissolving into wisps at the tail ----
        Ps = core.chaikin(P, 2, closed=False) if len(P) > 3 else P
        ws = np.interp(np.linspace(0, 1, len(Ps)), np.linspace(0, 1, len(w)), w)
        us = np.interp(np.linspace(0, 1, len(Ps)), np.linspace(0, 1, len(u)), u)
        lump = 1 + 0.14 * np.sin(np.arange(len(Ps)) * 0.37 + drawing * 0.9) \
            * np.sin(np.arange(len(Ps)) * 0.11 + 1.3)
        ws = ws * lump
        body = us < 0.72                       # solid ribbon from the head back to ~72 % of the length
        bt = PolyBatch()
        pal = self.pal
        if body.sum() >= 2:
            Pb, wb = Ps[body], ws[body]
            bt.add(core.stroke_poly(Pb, wb, cap_pts=6), core.mix(pal['gold'], pal['core'], 0.35))
            bt.add(core.stroke_poly(Pb, wb * 0.74, cap_pts=6), pal['core'])
        # the tail breaks into a few tapered wisps that drift apart
        tail = np.nonzero(us >= 0.66)[0]
        if len(tail) >= 3:
            Pt, wt = Ps[tail], ws[tail]
            nt, _ = core.polyline_normals(Pt)
            g = core.rng('trailwisp', self.name, drawing)
            q = np.linspace(0, 1, len(Pt))         # 0 near the body, 1 at the very tail
            for kk in range(3):
                spread = (kk - 1) * 0.55 + g.normal(0, 0.1)
                off = nt * (wt[:, None] * spread * q[:, None] * 1.2)
                wd = wt * (0.42 - 0.08 * abs(kk - 1)) * (1 - q) ** 1.1 + 0.3
                bt.add(core.stroke_poly(Pt + off, wd), pal['core'] if kk == 1 else core.mix(pal['gold'], pal['core'], 0.5))
        bt.draw(canvas)
        if front_groups:
            paint_groups(canvas, front_groups, [], self.mpal, light, self._mist_c, max(self.width * 3.0, 1.0),
                         line=0.0, local=0.75, vert=0.3, bias=0.25)
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
            wh = self.width * sc[-1]
            rows.append((hx, hy, wh * 0.3, wh * 3.5, *gold, 0.6 * self.glow_gain, 1.4))
            raster.add_soft_discs(light_buf, np.asarray(rows, np.float64))
        return canvas
