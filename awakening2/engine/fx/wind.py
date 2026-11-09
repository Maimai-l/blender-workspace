"""wind.py - the engines' great ring of wind across the forest floor.

The ring lives on the ground plane in polar coordinates (rho, phi) around `centre` and is
projected to the screen as an ellipse (`ratio` = minor / major: ~0.4-0.6 for a high angle,
~0.08-0.15 at eye level; `persp` makes the near side, sin(phi) > 0, bigger; `tilt` rotates).
The front radius over time is r0 -> radius with an ease-out over `duration` frames (or pass
`radius_fn(age) -> px`).

What makes it read as WIND rather than a UI ellipse:
  * a rolling dust wall: billows born at the front on every drawing, rolling outward, left
    behind to rise and break up (the leading edge is a moving cloud, not a line);
  * flattened grass: radial pressed-grass strokes revealed as the front passes, which spring
    back later;
  * leaves thrown outward and up, tumbling;
  * short-lived radial speed lines just ahead of the front;
  * a pressure band of broken brush arcs (re-drawn every drawing, so it boils).

`draw(canvas, frame, part='back'|'front'|'all')`: back = far half (sin(phi) < 0) plus all
ground marks, front = near half; draw the robot between them.
"""
import math

import numpy as np

from . import core, palettes
from .core import PolyBatch, ease_out, held, smoothstep
from .dust import BillowSet, paint_groups
from .leaves import _LeafSet

TAU = 2 * math.pi


def _h(*a):
    """Deterministic hash -> [0, 1)."""
    return (core.seed(*a) % 1000003) / 1000003.0


class WindRing:
    def __init__(self, name, centre, frame0, radius=1100.0, duration=36, r0=60.0, ratio=0.45,
                 persp=0.3, tilt=0.0, light=(0.62, -0.78), on=2, slots=44, height=90.0, life=26,
                 palette=None, grass=700, leaves=60, lines=48, band=True, leaf_size=(14.0, 28.0),
                 grass_len=(26.0, 70.0), grass_life=(40, 70), ease=2.2, radius_fn=None,
                 line_width=3.0, dust_line=2.5, opacity=1.0, horizon=None, near=0.18, mist=0.0,
                 mist_palette=None):
        self.name = name
        self.c = np.asarray(centre, np.float64)
        self.frame0 = int(frame0)
        self.radius = float(radius)
        self.duration = int(duration)
        self.r0 = float(r0)
        self.ratio = float(ratio)
        self.persp = float(persp)
        self.tilt = float(tilt)
        self.light = light
        self.on = on
        self.slots = slots
        self.height = float(height)
        self.life = int(life)
        self.palette = palettes.DUST_DRY if palette is None else palette
        self.ease = ease
        self.radius_fn = radius_fn
        self.line_width = line_width
        self.dust_line = dust_line
        self.opacity = opacity
        self.band = band
        self.mist = mist
        self.mist_pal = palettes.STEAM if mist_palette is None else mist_palette
        self.mist_b = BillowSet(name + '_mist', 64, (4, 6))
        self.lift = 0.72 * math.sqrt(max(0.0, 1 - ratio * ratio)) + 0.1
        # true ground-plane perspective (eye-level shots): camera height hc above the ground,
        # ring centre at depth Z0, both in px at the centre's depth (ratio = hc / Z0)
        self.horizon = horizon
        if horizon is not None:
            self.hc = float(centre[1] - horizon)
            self.Z0 = self.hc / max(ratio, 1e-3)
            self.near = near
        nsp = int(math.ceil(duration / on)) + 2
        self.nsp = nsp
        self.bil = BillowSet(name + '_wall', slots * (nsp + 4), (4, 6))
        g = core.rng('windring', name)
        # grass streaks (uniform over the swept area)
        self.ng = grass
        self.g_rho = np.sqrt(g.uniform((r0 * 1.3) ** 2, (radius * 1.02) ** 2, grass))
        self.g_phi = g.uniform(0, TAU, grass)
        self.g_len = g.uniform(grass_len[0], grass_len[1], grass)
        self.g_w = g.uniform(2.5, 5.5, grass)
        self.g_life = g.uniform(grass_life[0], grass_life[1], grass)
        self.g_curl = g.uniform(-0.25, 0.25, grass)
        self.g_tone = g.random(grass)
        # leaves
        self.nl = leaves
        self.L = _LeafSet(name + '_leaves', leaves, leaf_size, None, {'green': 0.5, 'deep': 0.25, 'gold': 0.25})
        self.l_rho = np.sqrt(g.uniform((r0 * 1.5) ** 2, (radius * 0.75) ** 2, leaves))
        self.l_phi = g.uniform(0, TAU, leaves)
        self.l_sp = g.uniform(10, 26, leaves)
        self.l_up = g.uniform(0.4, 1.2, leaves)
        self.l_a0 = g.uniform(0, TAU, leaves)
        self.l_w = g.uniform(-0.5, 0.5, leaves)
        self.l_fl = g.uniform(0, TAU, leaves)
        # speed lines
        self.ns = lines
        self.s_phi = g.uniform(0, TAU, lines)
        self.s_per = g.integers(8, 15, lines)
        self.s_ph = g.integers(0, 15, lines)
        self.s_len = g.uniform(0.10, 0.22, lines)
        self.s_off = g.uniform(-0.04, 0.1, lines)
        self.s_curl = g.uniform(-0.12, 0.12, lines)

    # ------------------------------------------------------------------ geometry
    def R(self, age):
        if self.radius_fn is not None:
            return float(self.radius_fn(age))
        x = min(max(age / self.duration, 0.0), 1.0)
        return self.r0 + (self.radius - self.r0) * float(ease_out(x, self.ease))

    def speed(self, age):
        """Front speed relative to its start (1 .. 0)."""
        if self.radius_fn is not None:
            v = self.R(age + 1) - self.R(age)
            v0 = self.R(1) - self.R(0)
            return max(0.0, v / max(v0, 1e-6))
        x = min(max(age / self.duration, 0.0), 1.0)
        return (1 - x) ** (self.ease - 1)

    def t_pass(self, rho):
        """Age at which the front reaches rho (inf if never)."""
        if self.radius_fn is not None:
            lo, hi = 0.0, float(self.duration * 4)
            if self.R(hi) < rho:
                return math.inf
            for _ in range(30):
                m = 0.5 * (lo + hi)
                if self.R(m) < rho:
                    lo = m
                else:
                    hi = m
            return hi
        u = (rho - self.r0) / (self.radius - self.r0)
        if u >= 1:
            return math.inf
        if u <= 0:
            return 0.0
        return (1 - (1 - u) ** (1 / self.ease)) * self.duration

    def project(self, rho, phi):
        c, s = np.cos(phi), np.sin(phi)
        if self.horizon is not None:
            Z = self.Z0 - rho * s
            Z = np.maximum(Z, self.near * self.Z0)
            k = self.Z0 / Z
            return self.c[0] + rho * c * k, self.horizon + self.hc * k, k
        gx, gy = rho * c, rho * s * self.ratio
        ct, st = math.cos(self.tilt), math.sin(self.tilt)
        x = self.c[0] + gx * ct - gy * st
        y = self.c[1] + gx * st + gy * ct
        return x, y, 1 + self.persp * s

    def visible(self, rho, phi):
        if self.horizon is None:
            return True
        return self.Z0 - rho * math.sin(phi) > self.near * self.Z0 * 1.05

    def outward(self, phi, rho=None):
        if self.horizon is not None:
            r = self.R(0) if rho is None else rho
            x0, y0, _ = self.project(r, phi)
            x1, y1, _ = self.project(r + 5.0, phi)
            d = np.array([x1 - x0, y1 - y0], np.float64)
            return d / max(np.linalg.norm(d), 1e-9)
        c, s = math.cos(phi), math.sin(phi)
        ct, st = math.cos(self.tilt), math.sin(self.tilt)
        d = np.array([c * ct - s * self.ratio * st, c * st + s * self.ratio * ct])
        return d / max(np.linalg.norm(d), 1e-9)

    # ------------------------------------------------------------------ parts
    def _wall(self, age, part):
        """Head billows ride the front in fixed angular slots (so each keeps rolling as one
        billow); every 4 frames the head sheds short-lived tail billows that rise and break up,
        so the swept ground clears behind the wall."""
        ids, PX, PY, RR, BR, PH, Z, GB = [], [], [], [], [], [], [], []
        self._gy, self._lead = [], []
        l = core.unit(self.light)
        K = max(10, int(round(self.slots * 0.55)))       # fewer, larger masses
        R = self.R(age)
        spd = self.speed(age)
        if self.horizon is not None:
            circ = TAU * R          # ground units; add() scales by the depth factor
        else:
            circ = math.pi * R * (1 + self.ratio) * (1 + 0.3 * self.persp)
        spacing = circ / K
        end = smoothstep(self.duration * 0.7, self.duration + self.life * 1.4, age)
        hh = self.height * (0.5 + 0.5 * spd ** 0.6) * (0.55 + 0.75 * min(1.0, R / self.radius))
        grow = float(ease_out(min(1.0, (age + 2) / 8.0), 2))

        def add(i, rho, phi, r_base, brk, roll_a, rise):
            s = math.sin(phi)
            if part == 'back' and s >= 0:
                return
            if part == 'front' and s < 0:
                return
            if not self.visible(rho, phi):
                return
            x, y, sc = self.project(rho, phi)
            r = r_base * sc
            self._gy.append(y + 1.0 if rise < r * 0.3 else y + 1e6)
            y = y - r * self.lift - rise * sc
            ow = self.outward(phi, rho)
            self._lead.append((float(ow[0]), float(ow[1])))
            ids.append(i); PX.append(x); PY.append(y); RR.append(r); BR.append(brk)
            PH.append((1.0 if ow[0] >= 0 else -1.0) * TAU * roll_a)
            Z.append(y + r * 0.6)
            GB.append(0.16 * float(ow @ l))

        # clumpy size variation around the ring (smooth in phi, so neighbours agree)
        def clump(phi):
            v = 0.0
            for m in range(3):
                v += math.sin(phi * (2 + 2 * m) + TAU * _h(self.name, 'cl', m)) / (1 + m)
            return v / 1.8

        nseg = 3
        for k in range(K):
            phi = (k + 0.5 + (_h(self.name, 'hp', k) - 0.5) * 0.7) * TAU / K
            # strongly varied heights: towering billows, low ones, gaps, a few laggers
            hk = _h(self.name, 'hcls', k)
            if hk < 0.2:
                hcls = 1.5 + 0.5 * _h(self.name, 'ht', k)          # towering
            elif hk < 0.5:
                hcls = 0.45 + 0.2 * _h(self.name, 'hl', k)         # low
            else:
                hcls = 0.8 + 0.3 * _h(self.name, 'hn', k)
            u = (0.85 + 0.3 * _h(self.name, 'hu', k)) * (1 + 0.3 * clump(phi)) * hcls
            if _h(self.name, 'gap', k) < 0.1:
                continue                                  # gaps in the wall
            r = max(hh * 0.5 * u, spacing * 0.8 * min(u, 1.2)) * grow
            r = min(r, 0.3 * R + 6.0)          # a young ring is a thin ring, not a disc
            lag = hh * 0.3 * (_h(self.name, 'hf', k) - 0.5)
            if _h(self.name, 'lagger', k) < 0.15:
                lag -= hh * (0.6 + 0.6 * _h(self.name, 'lg', k))      # lags behind the front
                r *= 0.8
            brk = float(np.clip(end + (_h(self.name, 'hb', k) - 0.5) * 0.3 * end, 0, 1))
            for m in range(nseg):
                # head billow + followers trailing inward: a comet pointing outward
                fs = (1.0, 0.68, 0.46)[m]
                back = (0.0, 1.05, 1.85)[m]
                rho = R - r * 0.2 + lag - back * r * (0.9 + 0.3 * spd)
                bm = float(np.clip(brk + 0.18 * m * (0.3 + end), 0, 1))
                add(k + m * K, rho, phi + 0.03 * m * (_h(self.name, 'fs', k) - 0.5),
                    r * fs * (1 - 0.15 * m * (1 - spd)), bm, age / 16.0 + 0.3 * m,
                    hh * (0.3 * end + 0.12 * m))
            if hcls > 1.4:
                # a towering billow: a second, smaller mass stacked on the head
                rt = r * 0.72
                add(k + 3 * K, R - r * 0.35 + lag, phi + 0.02, rt, float(np.clip(brk + 0.1, 0, 1)),
                    age / 14.0 + 0.5, r * 1.15 + hh * 0.3 * end)
        # sporadic billows shed by the wall, left behind to rise and break up
        for k in range(K):
            per = 7 + int(6 * _h(self.name, 'sper', k))
            ph = int(per * _h(self.name, 'sph', k))
            for j in range(0, 3):
                b = ((age - ph) // per - j) * per + ph
                if b < 0 or b > age:
                    continue
                spd_b = self.speed(b)
                if spd_b < 0.12 or self.R(b) < 0.18 * self.radius:
                    continue
                a = age - b
                life = 12 * (0.8 + 0.5 * _h(self.name, 'tl', k, b))
                if a > life:
                    continue
                t = a / life
                Rb = self.R(b)
                hb = self.height * (0.55 + 0.45 * spd_b ** 0.6) * (0.55 + 0.75 * min(1.0, Rb / self.radius))
                phi = (k + _h(self.name, 'tp', k, b)) * TAU / K
                r = hb * 0.36 * (0.8 + 0.4 * _h(self.name, 'tu', k, b)) * (1 + 0.35 * t)
                rho = Rb - r * 1.6
                i = K * (nseg + 1) + (k * 7 + b) % (self.bil.n - K * (nseg + 1))
                add(i, rho, phi, r, float(smoothstep(0.15, 1.0, t)), a / 30.0, hb * 0.5 * t)
        return ids, PX, PY, RR, BR, PH, Z, GB

    def _mist(self, canvas, age, part, drawing):
        """Floor mist shoved outward ahead of the wall: big pale billows, translucent."""
        if self.mist <= 0:
            return
        K = 28
        R = self.R(age)
        spd = self.speed(age)
        fade = 1 - smoothstep(self.duration * 0.6, self.duration + self.life * 1.6, age)
        if fade <= 0:
            return
        ids, PX, PY, RR, BR, PH, Z = [], [], [], [], [], [], []
        circ = TAU * R if self.horizon is not None else math.pi * R * (1 + self.ratio)
        for k in range(K):
            phi = (k + _h(self.name, 'mp', k)) * TAU / K
            s = math.sin(phi)
            if (part == 'back' and s >= 0) or (part == 'front' and s < 0):
                continue
            r = max(self.height * 0.75, circ / K * 0.75) * (0.8 + 0.4 * _h(self.name, 'mu', k))
            rho = R + r * (0.55 + 0.3 * spd)
            if not self.visible(rho, phi):
                continue
            x, y, sc = self.project(rho, phi)
            rr = r * sc * float(ease_out(min(1.0, (age + 2) / 10.0), 2))
            ids.append(k); PX.append(x); PY.append(y - rr * self.lift * 0.6); RR.append(rr)
            BR.append(float(np.clip(1 - fade, 0, 1)) * 0.8); PH.append(age / 30.0); Z.append(y)
        if ids:
            groups, holes = self.mist_b.groups(ids, PX, PY, RR, BR, PH, Z, drawing)
            C = (float(np.mean(PX)), float(np.mean(PY)))
            paint_groups(canvas, groups, holes, self.mist_pal, self.light, C, self.height * 3.0,
                         line=0, opacity=self.mist * fade * self.opacity, local=0.6, vert=0.3)

    def _shock(self, age, part, canvas):
        """The shockwave front racing ahead of the dust: a wide translucent ground-hugging band
        of flattened-grass streaks and a thin bright pressure line at its leading edge."""
        spd = self.speed(age)
        if spd < 0.06 or age < 1:
            return
        R = self.R(age)
        drawing = age // max(self.on, 1)
        g = core.rng('windshock', self.name, drawing)
        fade = min(1.0, spd * 3.0)
        band = PolyBatch()
        # translucent band fill (an annulus on the ground, ahead of the wall)
        nseg = 90
        for half in (-1, 1):
            if (part == 'back' and half > 0) or (part == 'front' and half < 0):
                continue
            phis = np.linspace(0, math.pi, nseg // 2 + 1) * half
            phis = phis[np.array([self.visible(R * 1.3, p_) for p_ in phis])]
            if len(phis) < 2:
                continue
            xo, yo, _ = self.project(R * 1.28 * (1 + 0.02 * np.sin(phis * 7 + drawing)), phis)
            xi, yi, _ = self.project(np.full(len(phis), R * 1.0), phis)
            poly = np.concatenate([np.stack([xo, yo], 1), np.stack([xi, yi], 1)[::-1]], 0)
            band.add(poly, palettes.GRASS['lit'], alpha=0.16 * fade)
        # flattened grass streaks racing outward across the band (vectorised quads)
        G = palettes.GRASS
        n = 420
        phi = g.uniform(0, TAU, n)
        r0 = R * g.uniform(1.0, 1.27, n)
        L = R * g.uniform(0.04, 0.1, n) * (0.6 + 0.4 * spd)
        wd0 = g.uniform(1.4, 3.2, n) * self.line_width / 3.0
        tone = g.random(n) < 0.6
        s0 = np.sin(phi)
        keep = np.ones(n, bool)
        if part == 'back':
            keep &= s0 < 0
        elif part == 'front':
            keep &= s0 >= 0
        if self.horizon is not None:
            keep &= (self.Z0 - (r0 + L) * s0) > self.near * self.Z0 * 1.05
        phi, r0, L, wd0, tone = phi[keep], r0[keep], L[keep], wd0[keep], tone[keep]
        if len(phi):
            x0, y0, sc0 = self.project(r0, phi)
            x1, y1, sc1 = self.project(r0 + L, phi)
            dx, dy = x1 - x0, y1 - y0
            nn = np.hypot(dx, dy) + 1e-9
            px, py = -dy / nn, dx / nn
            w0 = wd0 * sc0 * 0.5
            w1 = wd0 * sc1 * 0.12
            quads = np.stack([np.stack([x0 + px * w0, y0 + py * w0], 1), np.stack([x1 + px * w1, y1 + py * w1], 1),
                              np.stack([x1 - px * w1, y1 - py * w1], 1), np.stack([x0 - px * w0, y0 - py * w0], 1)], 1)
            for qd, tn in zip(quads, tone):
                band.add(qd, G['lit'] if tn else G['mid'], alpha=0.6 * fade)
        band.draw(canvas, self.opacity)
        # the thin bright pressure line at the leading edge, nearly closed, slightly broken
        line = PolyBatch()
        a0 = g.uniform(0, TAU)
        k = 0
        while k < 9:
            span = g.uniform(0.5, 0.95)
            gap = g.uniform(0.03, 0.12)
            phi = a0 + np.linspace(0, span, 24)
            a0 += span + gap
            k += 1
            mid = float(phi[12])
            if (part == 'back' and math.sin(mid) >= 0) or (part == 'front' and math.sin(mid) < 0):
                continue
            ok = np.array([self.visible(R * 1.3, p_) for p_ in phi])
            if ok.sum() < 3:
                continue
            phi = phi[ok]
            rr = R * (1.29 + 0.006 * np.sin(phi * 9 + drawing))
            x, y, sc = self.project(rr, phi)
            q = np.linspace(0, 1, len(phi))
            wd = (1.2 + 1.8 * np.sin(np.pi * q) ** 0.6) * sc * self.line_width / 3.0 * (0.6 + 0.4 * fade)
            line.add(core.stroke_poly(np.stack([x, y], 1), wd), palettes.WIND_LINE, alpha=0.95 * fade)
        line.draw(canvas, self.opacity)

    def _grass(self, age, batch):
        l = core.unit(self.light)
        G = palettes.GRASS
        for i in range(self.ng):
            tp = self.t_pass(self.g_rho[i])
            a = age - tp
            if not (0 <= a <= self.g_life[i] + 12):
                continue
            press = float(ease_out(min(1.0, a / 3.0), 2))
            back = float(smoothstep(self.g_life[i], self.g_life[i] + 12, a))
            spd = self.speed(tp)
            L = self.g_len[i] * (0.45 + 0.55 * spd) * press * (1 - 0.75 * back)
            if L < 2:
                continue
            phi0 = self.g_phi[i]
            if not self.visible(self.g_rho[i] + L, phi0):
                continue
            n = 5
            ss = np.linspace(0, 1, n)
            rho = self.g_rho[i] - L * 0.25 + L * ss
            phi = phi0 + self.g_curl[i] * ss ** 2 * L / max(self.g_rho[i], 1)
            x, y, sc = self.project(rho, phi)
            P = np.stack([x, y], 1)
            w = self.g_w[i] * sc * (1 - 0.8 * ss) * (1 - 0.5 * back)
            ow = self.outward(phi0, self.g_rho[i])
            f = float(ow @ l) + (self.g_tone[i] - 0.5) * 0.8
            col = G['lit'] if f > 0.15 else (G['mid'] if f > -0.35 else G['shade'])
            batch.add(core.stroke_poly(P, w), col, alpha=1.0 - 0.6 * back)

    def _band(self, age, batch, part):
        spd = self.speed(age)
        if spd < 0.08 or age < 1:
            return
        drawing = age // max(self.on, 1)
        g = core.rng('windband', self.name, drawing)
        R = self.R(age)
        col = palettes.WIND_LINE
        n = 26
        for m in range(n):
            phi0 = g.uniform(0, TAU)
            span = g.uniform(0.12, 0.45)
            mid = phi0 + span / 2
            if part == 'back' and math.sin(mid) >= 0:
                continue
            if part == 'front' and math.sin(mid) < 0:
                continue
            ss = np.linspace(0, 1, 9)
            phi = phi0 + span * ss
            rho = R * (g.uniform(0.88, 0.97) + 0.015 * np.sin(ss * 5 + m))
            if not all(self.visible(float(rr), float(pp)) for rr, pp in zip(rho, phi)):
                continue
            x, y, sc = self.project(rho, phi)
            wmax = g.uniform(2.5, 8.0) * (0.5 + 0.5 * spd) * self.line_width / 3.0
            w = wmax * sc * np.sin(np.pi * ss) ** 0.7 + 0.3
            batch.add(core.stroke_poly(np.stack([x, y], 1), w), col, alpha=0.7 * min(1.0, spd * 2.5))

    def _lines(self, age, batch, part):
        spd = self.speed(age)
        if spd < 0.12:
            return
        R = self.R(age)
        col = palettes.WIND_LINE
        for j in range(self.ns):
            ph = (age + self.s_ph[j]) % self.s_per[j]
            if ph >= 6:
                continue
            t = ph / 6.0
            phi0 = self.s_phi[j]
            s0 = math.sin(phi0)
            if part == 'back' and s0 >= 0:
                continue
            if part == 'front' and s0 < 0:
                continue
            L = self.s_len[j] * R * (1 - 0.6 * t) * (0.5 + 0.5 * spd)
            start = R * (1 + self.s_off[j]) + R * 0.1 * t
            ss = np.linspace(0, 1, 7)
            rho = start + L * ss
            phi = phi0 + self.s_curl[j] * ss ** 2
            if not self.visible(float(rho[-1]), float(phi[-1])):
                continue
            x, y, sc = self.project(rho, phi)
            w = self.line_width * 1.6 * sc * np.sin(np.pi * np.clip(ss * 0.9 + 0.05, 0, 1)) ** 0.8 * (1 - 0.5 * t)
            batch.add(core.stroke_poly(np.stack([x, y], 1), w), col, alpha=0.9)

    def _leaf_items(self, age, part):
        items = []
        for i in range(self.nl):
            tp = self.t_pass(self.l_rho[i])
            t = age - tp
            if not (0 <= t <= 70):
                continue
            phi = self.l_phi[i]
            s0 = math.sin(phi)
            if not self.visible(self.l_rho[i], phi):
                continue
            x0, y0, sc = self.project(self.l_rho[i], phi)
            ow = self.outward(phi, self.l_rho[i])
            spd = self.speed(tp)
            v = ow * self.l_sp[i] * sc * (0.4 + 0.6 * spd)
            up = self.l_up[i] * self.l_sp[i] * 0.6 * (1 - 0.5 * self.ratio)
            k = 0.08
            e = math.exp(-k * t)
            dist = (1 - e) / k
            x = x0 + v[0] * dist
            y = y0 + v[1] * dist - up * dist + 1.6 * (t - dist)
            slow = 1 - e
            a = t * 0.15 + self.l_fl[i]
            x += 14 * slow * math.sin(a)
            # leaves fly above the dust: near side leaves in front, far side behind
            if part == 'back' and s0 >= 0:
                continue
            if part == 'front' and s0 < 0:
                continue
            items.append((y, i, x, y, self.l_a0[i] + self.l_w[i] * dist, self.l_fl[i] + 0.25 * dist + slow * math.sin(a),
                          sc))
        return items

    # ------------------------------------------------------------------ draw
    def draw(self, canvas, frame, light=None, part='all'):
        if light is not None:
            self.light = light
        fh = held(frame, self.on, self.frame0)
        age = fh - self.frame0
        if age < 0:
            return canvas
        drawing = age // max(self.on, 1)
        parts = ['back', 'front'] if part == 'all' else [part]
        for pt in parts:
            ground = PolyBatch()
            if pt == 'back':
                self._grass(age, ground)
            if self.band:
                self._band(age, ground, pt)
            ground.draw(canvas, self.opacity)
            self._shock(age, pt, canvas)
            self._mist(canvas, age, pt, drawing)
            ids, PX, PY, RR, BR, PH, Z, GB = self._wall(age, pt)
            if ids:
                groups, holes, wisps = self.bil.groups(ids, PX, PY, RR, BR, PH, Z, drawing,
                                                       ground=np.array(self._gy), lead=np.array(self._lead),
                                                       wisps=True)
                bias_by_id = dict(zip([i % self.bil.n for i in ids], GB))
                gbias = [bias_by_id.get(g_[3], 0.0) for g_ in groups]
                C = (float(np.mean(PX)), float(np.mean(PY)))
                paint_groups(canvas, groups, holes, self.palette, self.light, C,
                             max(self.height * 2.5, 1.0), line=self.dust_line, opacity=self.opacity,
                             local=0.75, vert=0.5, group_bias=gbias, wisps=wisps[::2])
            lines = PolyBatch()
            self._lines(age, lines, pt)
            lines.draw(canvas, self.opacity)
            self.L.paint(canvas, self._leaf_items(age, pt), self.light)
        return canvas
