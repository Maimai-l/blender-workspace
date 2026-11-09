"""Animation helper: keys -> one drawing per `on` frames (on 2s by default) with holds,
spacing (ease) per segment, arcs (Catmull-Rom through key positions) and flap cycles.

    tr = Track(on=2)
    tr.key(0,  'flap_up', x=100, y=300, scale=40, facing=1, cycle='flap6')
    tr.key(24, 'glide',   x=600, y=260, ease='out')
    tr.key(30, 'flare',   x=650, y=280, ease='hold')
    st = tr.state(f)          # dict(pose, x, y, scale, facing, drawing) or None
    draw_state(canvas, st, light)

Times are frames of the caller's clock (shot-local frames are fine).
"""
import numpy as np
from .poses import pose as mkpose, blend, flap_pose, POSES
from .draw import draw, render, Light

EASES = {
    'linear': lambda u: u,
    'in': lambda u: u * u,                       # slow out of this key (accelerate)
    'out': lambda u: 1 - (1 - u) ** 2,           # slow into the next key (decelerate)
    'inout': lambda u: u * u * (3 - 2 * u),
    'snap': lambda u: 1 - (1 - u) ** 3,          # very fast start, cushioned end
    'hold': lambda u: 0.0,                       # keep this drawing until the next key
}


class Key:
    def __init__(self, frame, pose, x, y, scale, facing, ease, cycle, on, pos_ease, cycle_on, phase,
                 overrides):
        self.frame, self.pose, self.x, self.y = frame, pose, x, y
        self.scale, self.facing, self.ease, self.cycle, self.on = scale, facing, ease, cycle, on
        self.pos_ease, self.cycle_on, self.phase, self.overrides = pos_ease, cycle_on, phase, overrides


def _full(p, over=None):
    d = mkpose(p) if isinstance(p, str) else mkpose(None, **p)
    if over:
        d.update(over)
    return d


class Track:
    def __init__(self, on=2, light=None):
        self.keys = []
        self.on = on
        self.blinks = []
        self.light = light

    def key(self, frame, pose, x=None, y=None, scale=None, facing=None, ease='inout', cycle=None,
            on=None, pos_ease=None, cycle_on=None, phase=0, **overrides):
        """Add a key.  Missing x/y/scale/facing inherit from the previous key.
        ease: spacing of the segment that starts here ('hold' = no in-betweens).
        cycle: 'flap6' / 'flap4' drives the wings from this key to the next one."""
        prev = self.keys[-1] if self.keys else None
        x = prev.x if x is None else x
        y = prev.y if y is None else y
        scale = prev.scale if scale is None else scale
        facing = prev.facing if facing is None else facing
        k = Key(int(round(frame)), pose, float(x), float(y), float(scale), int(facing), ease, cycle,
                on or self.on, pos_ease or ease, cycle_on or (on or self.on), phase, overrides)
        self.keys.append(k)
        self.keys.sort(key=lambda k: k.frame)
        return self

    def blink(self, frame, length=3):
        self.blinks.append((int(frame), int(length)))
        return self

    @property
    def start(self):
        return self.keys[0].frame

    @property
    def end(self):
        return self.keys[-1].frame

    def _seg(self, f):
        ks = self.keys
        for i in range(len(ks) - 1):
            if ks[i].frame <= f < ks[i + 1].frame:
                return i
        return len(ks) - 1

    def _pos(self, i, e):
        ks = self.keys
        if i >= len(ks) - 1:
            return ks[-1].x, ks[-1].y
        p0 = ks[max(i - 1, 0)]; p1 = ks[i]; p2 = ks[i + 1]; p3 = ks[min(i + 2, len(ks) - 1)]
        P = np.array([[p0.x, p0.y], [p1.x, p1.y], [p2.x, p2.y], [p3.x, p3.y]])
        if i == 0:
            P[0] = 2 * P[1] - P[2]
        if i + 2 > len(ks) - 1:
            P[3] = 2 * P[2] - P[1]
        t = e
        q = 0.5 * ((2 * P[1]) + (-P[0] + P[2]) * t + (2 * P[0] - 5 * P[1] + 4 * P[2] - P[3]) * t * t
                   + (-P[0] + 3 * P[1] - 3 * P[2] + P[3]) * t ** 3)
        # a held key does not drift
        if p1.pos_ease == 'hold':
            return p1.x, p1.y
        return float(q[0]), float(q[1])

    def state(self, f, hold_before=False, hold_after=True):
        ks = self.keys
        if not ks:
            return None
        if f < ks[0].frame and not hold_before:
            return None
        if f > ks[-1].frame and not hold_after:
            return None
        f = max(f, ks[0].frame)
        i = self._seg(f)
        k = ks[i]
        fd = k.frame + k.on * ((f - k.frame) // k.on)          # drawing frame (on 2s)
        if i < len(ks) - 1:
            k2 = ks[i + 1]
            u = (fd - k.frame) / max(1, k2.frame - k.frame)
            e = EASES[k.ease](u)
            ep = EASES[k.pos_ease](u)
            pa = _full(k.pose, k.overrides)
            pb = _full(k2.pose, k2.overrides)
            P = pa if k.ease == 'hold' else blend(pa, pb, e)
            x, y = self._pos(i, ep)
            sc = k.scale + (k2.scale - k.scale) * ep
            facing = k.facing if u < 0.5 or k.ease == 'hold' else k2.facing
        else:
            P = _full(k.pose, k.overrides)
            x, y, sc, facing = k.x, k.y, k.scale, k.facing
        if k.cycle:
            n = (fd - k.frame) // k.cycle_on + k.phase
            P = flap_pose(P, n, k.cycle)
        for bf, bl in self.blinks:
            if bf <= fd < bf + bl:
                P['blink'] = 1.0
        return dict(pose=P, x=x, y=y, scale=sc, facing=facing, drawing=fd, frame=f)


def draw_state(canvas, st, light=None, **kw):
    if st is None:
        return None
    return draw(canvas, st['pose'], st['x'], st['y'], st['scale'], st['facing'], light, **kw)


# ============================================================================ acting sequences
def landing(x, y, scale, facing=1, t_flare=38, t_touch=50, t_hop=70, t_chirp=101, t_end=132,
            enter=(-2.6, -1.5), t_enter=None, hop_dx=0.42, looks=None, on=2, chirps=2):
    """S02 / S17 beat: approach glide, wings flare, touchdown, fold, hop, settle, look around,
    chirp.  (x, y): the feet contact point on the perch in canvas pixels; scale: perched
    height in pixels; facing: +1 flies/looks right.  enter: start offset in units of scale
    (negative x = behind the bird, negative y = above).  Times: shot-local frames.
    Pass t_hop=None / t_chirp=None to skip those beats."""
    s = scale * facing
    tr = Track(on=on)
    t_enter = t_flare - 22 if t_enter is None else t_enter
    P = lambda dx, dy: (x + dx * s, y + dy * scale)
    ex, ey = P(*enter)
    t_app = t_flare - 8
    tr.key(t_enter, 'glide', ex, ey, scale, facing, ease='linear', cycle='flap6', pos_ease='linear')
    ax, ay = P(-1.25, -0.80)
    tr.key(t_app, 'approach', ax, ay, ease='inout', pos_ease='linear')
    fx, fy = P(-0.52, -0.58)
    tr.key(t_flare, 'flare', fx, fy, ease='inout', pos_ease='out')
    f2x, f2y = P(-0.16, -0.26)
    tr.key(t_flare + (t_touch - t_flare) // 2, 'flare2', f2x, f2y, ease='out', pos_ease='out')
    tr.key(t_touch, 'touchdown', x, y, ease='hold')
    tr.key(t_touch + 4, 'touchdown2', x, y, ease='hold')
    tr.key(t_touch + 6, 'fold1', x, y, ease='hold')
    tr.key(t_touch + 8, 'fold2', x, y, ease='inout')
    tr.key(t_touch + 12, 'fold3', x, y, ease='out')
    tr.key(t_touch + 18, 'settle', x, y, ease='hold')
    cx, cy = x, y
    t_after = t_touch + 22
    if t_hop is not None:
        hx = x + hop_dx * s
        tr.key(t_hop - 8, 'settle', cx, cy, ease='inout')
        tr.key(t_hop - 4, 'crouch', cx, cy, ease='hold')
        tr.key(t_hop, 'hop_air', *P(hop_dx * 0.45, -0.22), ease='out', pos_ease='out')
        tr.key(t_hop + 4, 'hop_air', *P(hop_dx * 0.85, -0.08), ease='in', pos_ease='in')
        tr.key(t_hop + 6, 'hop_land', hx, y, ease='hold')
        tr.key(t_hop + 8, 'hop_land', hx, y, ease='inout', tail=14)
        tr.key(t_hop + 12, 'settle', hx, y, ease='out')
        tr.key(t_hop + 16, 'idle', hx, y, ease='hold')
        cx = hx
        t_after = t_hop + 18
    if looks is None:
        t_stop = (t_chirp - 4) if t_chirp is not None else t_end
        looks = []
        seq = ['look_cam', 'tilt', 'look_back', 'idle_alert']
        span = max(8, t_stop - t_after)
        n = max(1, min(len(seq), span // 9))
        for j in range(n):
            looks.append((t_after + j * span // n, seq[j]))
    for t, name in looks:
        tr.key(t, name, cx, y, ease='snap')
        tr.key(t + 2, name, cx, y, ease='hold')
    if t_chirp is not None:
        tr.key(t_chirp - 4, 'chirp_close', cx, y, ease='snap')
        for c in range(chirps):
            tc = t_chirp + c * 8
            tr.key(tc, 'chirp', cx, y, ease='hold')
            tr.key(tc + 4, 'chirp_close', cx, y, ease='hold')
        tr.key(t_chirp + chirps * 8 + 2, 'idle_alert', cx, y, ease='inout')
        tr.key(t_chirp + chirps * 8 + 8, 'idle', cx, y, ease='hold')
    tr.key(max(t_end, tr.end + 1), 'idle', cx, y, ease='hold')
    tr.blink(t_touch + 26, 3)
    if t_chirp is not None:
        tr.blink(t_chirp + chirps * 8 + 12, 3)
    return tr


def flee(x, y, scale, facing=1, t_startle=31, t_flee=50, t_exit=None, exit=(3.2, -3.0), on=2):
    """S07 beat: the perched bird startles (snap + hold), crouches, springs and flaps away.
    exit: end offset in units of scale (positive x = ahead, negative y = up)."""
    s = scale * facing
    tr = Track(on=on)
    tr.key(0, 'idle', x, y, scale, facing, ease='hold')
    tr.key(t_startle - 6, 'idle', x, y, ease='hold')
    tr.key(t_startle - 2, 'look_cam', x, y, ease='hold')
    tr.key(t_startle, 'startle', x, y, ease='hold')          # snap: no in-between
    tr.key(t_flee - 8, 'startle', x, y, ease='inout')
    tr.key(t_flee - 4, 'to_crouch', x, y, ease='hold')
    tr.key(t_flee - 2, 'to_spring', x, y - 0.06 * scale, ease='hold', on=1)
    t_exit = t_flee + 30 if t_exit is None else t_exit
    tr.key(t_flee, 'to_air', x + 0.25 * s, y - 0.32 * scale, ease='linear', cycle='flap6', phase=3,
           pos_ease='in')
    tr.key(t_flee + 10, dict(mkpose('glide'), tilt=16), x + 1.0 * s, y - 1.05 * scale, ease='linear',
           cycle='flap6', phase=1, pos_ease='linear')
    ex, ey = x + exit[0] * s, y + exit[1] * scale
    tr.key(t_exit, dict(mkpose('glide'), tilt=12), ex, ey, ease='linear', cycle='flap6', pos_ease='linear')
    return tr


def crossing(p0, p1, f0, f1, scale, facing=None, on=2, burst=8, bound=6, rise=0.35, seed=0):
    """Small passerine 'bounding' flight between two screen points: flap bursts (4-drawing
    cycle) alternate with closed-wing bounds.  scale: perched-height px (birds 8-60 px)."""
    rng = np.random.default_rng(seed)
    p0 = np.asarray(p0, float); p1 = np.asarray(p1, float)
    facing = facing if facing is not None else (1 if p1[0] >= p0[0] else -1)
    tr = Track(on=on)
    f = f0
    flap = True
    while f < f1:
        t = (f - f0) / max(1, f1 - f0)
        pos = p0 + (p1 - p0) * t
        wob = (-rise if flap else rise * 0.6) * scale * 0.5
        if flap:
            tr.key(f, 'glide', pos[0], pos[1] + wob, scale, facing, ease='linear', cycle='flap4',
                   pos_ease='linear', phase=int(rng.integers(0, 4)))
            f += burst
        else:
            tr.key(f, 'bound', pos[0], pos[1] + wob, scale, facing, ease='linear', pos_ease='linear')
            f += bound
        flap = not flap
    tr.key(f1, 'glide', p1[0], p1[1], scale, facing, ease='linear', cycle='flap4', pos_ease='linear')
    return tr


def follow_path(points, f0, f1, scale, cycle='flap6', base='glide', on=2, facing=None, ease='linear',
                glide_every=0, glide_len=6, scale_end=None):
    """Fly along a polyline of screen points from frame f0 to f1 at constant speed (or eased),
    flapping with `cycle`; facing follows the horizontal direction unless given.
    glide_every > 0 inserts a glide (wings held) of glide_len frames every N frames."""
    pts = np.asarray(points, float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-9)
    tr = Track(on=on)
    n = max(2, int((f1 - f0) // max(on * 3, 4)) + 1)
    fr = np.linspace(f0, f1, n)
    se = scale if scale_end is None else scale_end
    for j, f in enumerate(fr):
        u = EASES[ease](j / (n - 1))
        x = np.interp(u, s, pts[:, 0]); y = np.interp(u, s, pts[:, 1])
        k = min(len(pts) - 2, int(np.searchsorted(s, u, side='right') - 1))
        dx = pts[k + 1, 0] - pts[k, 0]
        fc = facing if facing is not None else (1 if dx >= 0 else -1)
        gl = glide_every and (int(f - f0) % glide_every) < glide_len
        tr.key(f, base, x, y, scale + (se - scale) * u, fc, ease='linear', pos_ease='linear',
               cycle=None if gl else cycle)
    return tr
