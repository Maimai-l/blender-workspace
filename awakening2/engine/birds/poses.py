"""Pose library: named key drawings (partial pose dicts merged onto model.DEFAULT_POSE).

Perched poses keep the root at the feet contact point.  Flight poses keep the same root
convention (a point under the body) so a landing path ends exactly on the perch.
"""
import numpy as np
from .model import DEFAULT_POSE

# --------------------------------------------------------------------------- perched
PERCHED = {
    'idle':        dict(),
    'idle_fluff':  dict(fluff=1.07, neck=0.22, tilt=31, head_pitch=-4, tail=-19, by=2.62),
    'idle_alert':  dict(fluff=0.97, neck=0.85, tilt=45, head_pitch=6, tail=-9, by=2.78),
    'idle_lean':   dict(tilt=27, neck=0.38, head_pitch=-12, tail=-5, by=2.62, head_dx=0.12),
    'look_cam':    dict(head_yaw=52, neck=0.55),
    'look_back':   dict(head_yaw=-155, neck=0.45, head_pitch=4),
    'look_up':     dict(head_pitch=30, neck=0.7, tilt=42),
    'look_down':   dict(head_pitch=-34, neck=0.35, tilt=33, head_dx=0.12),
    'tilt':        dict(head_roll=26, head_yaw=28, neck=0.6),
    'tilt_other':  dict(head_roll=-22, head_yaw=-18, neck=0.6),
    'chirp':       dict(beak=1.0, head_pitch=22, neck=0.8, tilt=43, tail=-8, fluff=1.03),
    'chirp_close': dict(beak=0.0, head_pitch=18, neck=0.75, tilt=42, tail=-10, fluff=1.03),
    'blink':       dict(blink=1.0),
    'crouch':      dict(crouch=0.8, by=2.22, tilt=28, neck=0.28, head_pitch=-4, tail=-2, wdroop=-4),
    'hop_air':     dict(legs='hang', crouch=0.0, by=2.9, tilt=30, neck=0.4, tail=-24, wdroop=-10, wspread=0.25),
    'hop_land':    dict(crouch=0.62, by=2.32, tilt=33, neck=0.35, tail=6, wdroop=5),
    'settle':      dict(crouch=0.15, by=2.62, fluff=1.04, tail=-21, wdroop=2),
    'startle':     dict(fluff=0.9, neck=1.0, tilt=52, head_pitch=14, tail=10, crouch=0.25, by=2.62, wdroop=-7),
    'tail_flick':  dict(tail=8),
    'shake':       dict(fluff=1.14, neck=0.2, tail=-12, wspread=0.3, wdroop=6),
    'preen':       dict(head_yaw=-150, head_pitch=-30, neck=0.2, head_dx=-0.35, head_dy=-0.45, tilt=33),
}

# --------------------------------------------------------------------------- flight (side views)
FLIGHT_BASE = dict(fold=0, tilt=6, legs='tuck', tail=2, tail_len=0.92, neck=0.15, head_pitch=-4,
                   view_el=16, yaw=-6, by=2.7)


def _w(**k):
    d = {}
    for kk, v in k.items():
        d['n_' + kk] = v
        d['f_' + kk] = v
    return d


WINGS = {
    'up':     _w(el=78, sw=22, ext=0.95, fan=1.0, hel=12, tw=8, hsw=0),
    'down1':  _w(el=38, sw=2, ext=1.0, fan=0.95, hel=4, tw=-6, hsw=0),
    'down2':  _w(el=-12, sw=-6, ext=1.0, fan=0.85, hel=-6, tw=-10, hsw=0),
    'bottom': _w(el=-52, sw=-12, ext=0.95, fan=0.7, hel=-22, tw=-4, hsw=0),
    'upflick': _w(el=-4, sw=44, ext=0.56, fan=0.35, hsw=30, hel=16, tw=76),
    'up2':    _w(el=36, sw=32, ext=0.62, fan=0.45, hsw=26, hel=12, tw=40),
    'glide':  dict(_w(el=6, sw=6, ext=1.0, fan=0.85, tw=0, hel=0, hsw=0), n_el=-10, f_el=18),
    'tuck':   _w(el=8, sw=72, ext=0.25, fan=0.1, hsw=40, hel=0, tw=70),
}
# the flap cycle: six designed drawings + body bob (cm) and pitch wobble (deg)
FLAP = ['up', 'down1', 'down2', 'bottom', 'upflick', 'up2']
FLAP_BOB = [0.05, -0.04, -0.12, -0.06, 0.06, 0.10]
FLAP_TILT = [3, 0, -2, -1, 2, 3]
# a faster 4-drawing cycle for small/far birds
FLAP4 = ['up', 'down2', 'bottom', 'upflick']
FLAP4_BOB = [0.05, -0.12, -0.06, 0.08]
FLAP4_TILT = [3, -2, -1, 2]

FLIGHT = {
    'flap_' + k: dict(FLIGHT_BASE, **WINGS[k]) for k in WINGS
}
FLIGHT.update({
    'glide':     dict(FLIGHT_BASE, **WINGS['glide']),
    'bound':     dict(FLIGHT_BASE, **WINGS['tuck'], tilt=10),        # wings closed between flap bursts
    'approach':  dict(FLIGHT_BASE, **_w(el=26, sw=-14, ext=1.0, fan=1.0, tw=-14, hel=6, hsw=0),
                      tilt=24, legs='reach', leg_reach=0.8, toe_open=0.7, tail=-22, tail_spread=0.6,
                      neck=0.3),
    'flare':     dict(FLIGHT_BASE, **_w(el=58, sw=-38, ext=1.0, fan=1.0, tw=-38, hel=14, hsw=0),
                      tilt=58, legs='reach', leg_reach=1.0, toe_open=1.0, tail=-38, tail_spread=1.0,
                      neck=0.45, head_pitch=-12),
    'flare2':    dict(FLIGHT_BASE, **_w(el=72, sw=-26, ext=0.95, fan=1.0, tw=-30, hel=18, hsw=0),
                      tilt=50, legs='reach', leg_reach=0.9, toe_open=0.9, tail=-30, tail_spread=0.9,
                      neck=0.45, head_pitch=-10),
    'touchdown': dict(**_w(el=60, sw=-6, ext=0.78, fan=0.75, tw=-20, hel=10, hsw=6), fold=0, legs='perch',
                      crouch=0.72, by=2.25, tilt=40, tail=-6, tail_spread=0.55, neck=0.4, view_el=8,
                      head_pitch=-8),
    'touchdown2': dict(**_w(el=-14, sw=36, ext=0.58, fan=0.45, tw=4, hel=-6, hsw=14), fold=0, legs='perch',
                       crouch=0.55, by=2.38, tilt=38, tail=-8, tail_spread=0.45, neck=0.45, view_el=10),
    'fold1':     dict(fold=1, wdroop=20, wspread=1.0, crouch=0.40, by=2.46, tilt=37, tail=-12, tail_spread=0.3,
                      neck=0.45),
    'fold2':     dict(fold=1, wdroop=9, wspread=0.5, crouch=0.26, by=2.56, tilt=37, tail=-16, neck=0.5),
    'fold3':     dict(fold=1, wdroop=2, wspread=0.1, crouch=0.12, by=2.66, tilt=38, tail=-18, neck=0.5),
    'to_crouch': dict(fold=1, crouch=0.92, by=2.12, tilt=20, neck=0.2, head_pitch=-6, tail=6, wdroop=-9,
                      fluff=0.93),
    'to_spring': dict(**_w(el=74, sw=30, ext=0.66, fan=0.6, tw=22, hel=10, hsw=10), fold=0, legs='perch',
                      crouch=0.0, by=3.05, tilt=30, neck=0.4, tail=-4, tail_spread=0.3, view_el=10, fluff=0.93),
    'to_air':    dict(FLIGHT_BASE, **WINGS['bottom'], legs='hang', tilt=22, tail=-8, tail_spread=0.3, fluff=0.93),
})

POSES = {}
POSES.update(PERCHED)
POSES.update(FLIGHT)


def pose(name=None, **over):
    """Full pose dict for a library name (or {}), with overrides."""
    p = dict(DEFAULT_POSE)
    if name:
        p.update(POSES[name])
    p.update(over)
    return p


_ANG = ('el', 'sw', 'tw', 'hel', 'hsw')


def blend(a, b, t):
    """In-between two full pose dicts (numeric params lerped, discrete params switch at 0.5)."""
    out = {}
    for k in set(a) | set(b):
        va = a.get(k, DEFAULT_POSE.get(k)); vb = b.get(k, DEFAULT_POSE.get(k))
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool):
            out[k] = va + (vb - va) * t
        else:
            out[k] = va if t < 0.5 else vb
    # the fold switch is binary: keep decal wings until the target is folded
    if a.get('fold', 1) != b.get('fold', 1):
        out['fold'] = a.get('fold', 1) if t < 0.5 else b.get('fold', 1)
    return out


def flap_pose(base, i, cycle='flap6', smear=True):
    """Apply drawing i of a flap cycle to a (flight) pose dict.  The fast downstroke drawings
    get `smear_from` (a pale ghost of the wing's path, drawn by render())."""
    names, bob, tilt = (FLAP, FLAP_BOB, FLAP_TILT) if cycle == 'flap6' else (FLAP4, FLAP4_BOB, FLAP4_TILT)
    k = i % len(names)
    p = dict(base)
    p.update(WINGS[names[k]])
    if smear and names[k] in ('down2', 'bottom'):
        p['smear_from'] = names[(k - 1) % len(names)]
    else:
        p.pop('smear_from', None)
    p['fold'] = 0
    p['by'] = base.get('by', 2.7) + bob[k]
    p['tilt'] = base.get('tilt', 6) + tilt[k]
    return p
