"""Flocks: deterministic simulators (alarm burst from the treetops, wide circling) that return
per-frame bird states, and a fast sprite-based drawer.

A flock bird state is a dict: x, y (body centre, canvas px), span (wingspan px, 6-40 typical),
heading (deg, screen; 0 = flying right, 90 = straight up), drawing (int index into the flap cycle,
or -1 = glide), view ('below' | 'side' | 'low'), alpha.
"""
import numpy as np
import cv2
from .poses import pose as mkpose, flap_pose
from .draw import render, Light, composite

VIEWS = {'below': dict(view_el=-58, yaw=0), 'low': dict(view_el=-28, yaw=-10), 'side': dict(view_el=14, yaw=-6)}
SPAN_PER_SCALE = 2.55          # flying wingspan / perched height (white-eye proportions)
BUCKETS = np.array([3.0, 4.5, 6.5, 9.0, 13.0, 18.0, 26.0])   # render scales (perched-height px)

_SPR = {}


def flock_pose(drawing, view):
    base = mkpose('glide', tail_len=0.85, neck=0.1, **VIEWS[view])
    if drawing < 0:
        return base
    return flap_pose(base, drawing, 'flap6')


def sprite(drawing, view, scale_bucket, style, light):
    key = (drawing, view, float(scale_bucket), style, light.key())
    sp = _SPR.get(key)
    if sp is None:
        p = flock_pose(drawing, view)
        s = render(p, scale_bucket, 1, light, style=style)
        # pivot = body centre (root is the feet point; body centre is by above it)
        cx = s.ox + 0.0
        cy = s.oy - p['by'] * scale_bucket / 6.0
        sp = (s.rgba, cx, cy)
        _SPR[key] = sp
    return sp


def draw_flock(canvas, states, light=None, style='silhouette', on=None, tint=None):
    """Composite a list of flock-bird states onto canvas (straight-alpha float RGBA)."""
    light = light or Light(dir=(0.15, 1.0), depth=-0.35, rim=True)
    H, W = canvas.shape[:2]
    for st in sorted(states, key=lambda s: s['span']):
        scale = st['span'] / SPAN_PER_SCALE
        b = BUCKETS[min(len(BUCKETS) - 1, int(np.searchsorted(BUCKETS, scale * 1.15)))]
        rgba, cx, cy = sprite(int(st['drawing']), st.get('view', 'below'), b, style, light)
        k = scale / b
        hd = np.deg2rad(st['heading'])
        facing_left = np.cos(hd) < 0
        ang = np.rad2deg(np.arctan2(np.sin(hd), abs(np.cos(hd))))   # climb angle
        if facing_left:
            rgba = rgba[:, ::-1]
            cx = rgba.shape[1] - 1 - cx
            ang = -ang
        M = cv2.getRotationMatrix2D((float(cx), float(cy)), float(ang), float(k))
        M[0, 2] += st['x'] - cx
        M[1, 2] += st['y'] - cy
        h, w = rgba.shape[:2]
        corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float) @ M.T
        x0 = int(np.floor(corners[:, 0].min())) - 1; x1 = int(np.ceil(corners[:, 0].max())) + 1
        y0 = int(np.floor(corners[:, 1].min())) - 1; y1 = int(np.ceil(corners[:, 1].max())) + 1
        if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H:
            continue
        M2 = M.copy(); M2[0, 2] -= x0; M2[1, 2] -= y0
        pre = rgba.copy()
        pre[..., :3] *= pre[..., 3:4]
        patch = cv2.warpAffine(pre, M2, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = patch[..., 3:4] * st.get('alpha', 1.0)
        rgb = np.where(a > 1e-6, patch[..., :3] / np.maximum(patch[..., 3:4], 1e-6), 0)
        if tint is not None:
            t = np.asarray(tint[:3], np.float32); ta = tint[3] if len(tint) > 3 else 0.5
            rgb = rgb * (1 - ta) + t * ta
        out = np.concatenate([rgb, a], -1).astype(np.float32)
        composite(canvas, out, x0, y0)
    return canvas


# ============================================================================ simulators
class FlockSim:
    def __init__(self, frames):
        self.frames = frames          # dict frame -> list of states

    def at(self, f):
        return self.frames.get(int(f), [])


def burst(n=150, canopy=((200, 760), (1700, 700)), f_start=0, frames=72, seed=7,
          span=(8, 46), up_speed=(14, 24), groups=3, drift=(-0.45, -0.4), spread_deg=30,
          on_small=1, on_big=2, glide_prob=0.25, size=(1920, 1040), sources=None, stagger=3,
          launch_boost=1.9, recede=0.3):
    """Alarm burst: birds explode upward out of the canopy from a few source trees (staggered
    by `stagger` frames, an alarm ripple), fan out fast (launch_boost x cruise speed, decaying
    over ~10 frames), then bend into loose groups (one per source, mixed a little) that drift
    away in different directions and recede (shrink) with distance.
    canopy: two points defining the treetop line (birds start just below it)."""
    rng = np.random.default_rng(seed)
    (ax, ay), (bx, by) = canopy
    if sources is None:
        sources = [0.22 + rng.uniform(-0.06, 0.06), 0.52 + rng.uniform(-0.06, 0.06),
                   0.80 + rng.uniform(-0.06, 0.06)]
    sources = np.asarray(sources, float)
    ns = len(sources)
    src = rng.integers(0, ns, n)
    straggler = rng.random(n) < 0.12
    u = np.where(straggler, rng.random(n), sources[src] + rng.normal(0, 0.03, n))
    u = np.clip(u, 0, 1)
    x0 = ax + (bx - ax) * u
    y0 = ay + (by - ay) * u + rng.uniform(8, 45, n)
    src_t = rng.permutation(ns) * stagger
    t_launch = (f_start + src_t[src] + np.abs(rng.normal(0, 2.5, n))
                + rng.exponential(3.0, n) * (rng.random(n) < 0.2) * 3 + straggler * rng.uniform(2, 14, n))
    depth = rng.random(n) ** 1.3                          # 0 near, 1 far
    spans = span[1] + (span[0] - span[1]) * depth
    cruise = (up_speed[0] + (up_speed[1] - up_speed[0]) * rng.random(n)) * (0.45 + 0.55 * spans / span[1])
    off = (u - np.where(straggler, u, sources[src])) / 0.03          # -2..2 sigma within a tree
    ang = np.deg2rad(90 - off * 16 + rng.normal(0, spread_deg * 0.5, n))
    spd0 = cruise * launch_boost
    v = np.stack([np.cos(ang) * spd0, -np.sin(ang) * spd0], 1)
    gid = np.where(rng.random(n) < 0.85, src % groups, rng.integers(0, groups, n))
    base_a = np.arctan2(-drift[1], drift[0])
    g_dir = []
    for g in range(groups):
        a_ = base_a + np.deg2rad(-60 + 120 * (g + 0.5) / groups + rng.uniform(-10, 10))
        g_dir.append(np.array([np.cos(a_), -np.sin(a_)]))
    g_dir = np.array(g_dir)
    order = np.argsort(sources)
    flap_on = np.where(spans < 16, on_small, on_big)
    phase = rng.integers(0, 6, n)
    glide_at = rng.integers(26, 60, n)
    glide_len = rng.integers(4, 12, n) * (rng.random(n) < glide_prob)
    pos = np.stack([x0, y0], 1).astype(float)
    out = {}
    launched = np.zeros(n, bool)
    for fi in range(frames):
        f = f_start + fi
        launched |= t_launch <= f
        act = launched
        age = f - t_launch
        cent = np.zeros((groups, 2))
        for g in range(groups):
            m = act & (gid == g)
            cent[g] = pos[m].mean(0) if m.any() else 0
        for i in np.nonzero(act)[0]:
            a = age[i]
            sp = np.hypot(*v[i])
            # drag from the launch burst down to cruise speed
            if sp > cruise[i]:
                v[i] *= max(cruise[i] / sp, 0.90)
            if a > 9:
                want = g_dir[gid[i]] * cruise[i] * 0.8
                coh = (cent[gid[i]] - pos[i]) * 0.0025
                k = min(1.0, (a - 9) / 26.0) * 0.07
                v[i] += (want - v[i]) * k + coh * min(1.0, (a - 9) / 24.0)
            v[i] += rng.normal(0, 0.45, 2)
            pos[i] += v[i]
        states = []
        for i in np.nonzero(act)[0]:
            a = age[i]
            if glide_len[i] and glide_at[i] <= a < glide_at[i] + glide_len[i]:
                dr = -1
            else:
                dr = int((a // flap_on[i] + phase[i]) % 6)
            hd = np.rad2deg(np.arctan2(-v[i, 1], v[i, 0]))
            view = 'below' if 35 < hd < 145 else 'low'
            emerge = 1.0
            shrink = 1.0 - recede * min(1.0, max(0.0, a - 8) / 60.0)
            states.append(dict(x=float(pos[i, 0]), y=float(pos[i, 1]), span=float(spans[i] * shrink),
                               heading=float(hd), drawing=dr, view=view, alpha=emerge, id=int(i)))
        out[f] = states
    return FlockSim(out)


def circling(n=40, centre=(960, 360), radius=(420, 110), f_start=0, frames=120, seed=3,
             span=(6, 22), period=150, layers=3, direction=1, size=(1920, 1040)):
    """Wide circling flock (seen from far): birds orbit an ellipse in a few loose rings with
    phase scatter; near side of the orbit is lower and larger.  Flap bursts + glides."""
    rng = np.random.default_rng(seed)
    cx, cy = centre
    rx, ry = radius
    ph = rng.uniform(0, 2 * np.pi, n)
    ring = rng.integers(0, layers, n)
    rr = 1.0 + (ring - (layers - 1) / 2) * 0.12 + rng.normal(0, 0.04, n)
    alt = rng.normal(0, ry * 0.25, n)
    om = direction * 2 * np.pi / period * (1 + rng.normal(0, 0.06, n))
    base_span = span[0] + (span[1] - span[0]) * rng.random(n)
    flap_on = rng.choice([1, 2], n)
    burst_len = rng.integers(8, 18, n)
    glide_len = rng.integers(6, 16, n)
    out = {}
    for fi in range(frames):
        f = f_start + fi
        th = ph + om * fi
        x = cx + rx * rr * np.cos(th)
        y = cy + ry * rr * np.sin(th) + alt + 6 * np.sin(fi * 0.11 + ph * 3)
        near = (np.sin(th) + 1) / 2
        sp = base_span * (0.75 + 0.5 * near)
        vx = -rx * rr * np.sin(th) * om
        vy = ry * rr * np.cos(th) * om
        states = []
        for i in range(n):
            cyc = (fi + int(ph[i] * 10)) % (burst_len[i] + glide_len[i])
            dr = int((fi // flap_on[i] + i) % 6) if cyc < burst_len[i] else -1
            hd = float(np.rad2deg(np.arctan2(-vy[i], vx[i])))
            states.append(dict(x=float(x[i]), y=float(y[i]), span=float(sp[i]), heading=hd,
                               drawing=dr, view='side' if abs(np.sin(np.deg2rad(hd))) < 0.5 else 'low',
                               alpha=1.0, id=i))
        out[f] = states
    return FlockSim(out)
