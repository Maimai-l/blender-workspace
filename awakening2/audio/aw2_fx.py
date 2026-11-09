"""
aw2_fx.py -- designed sound effects and ambience for "Awakening II".

Every event in cues.json is handled by the function registered under its base name
(trailing _<number> stripped, so rise_groan_3 or core_flicker_4 just work); a sound that
lasts (the tremor, the hum, the engine spool, the roar, the trail) runs until the next
relevant event after it.  Ambience scenes (dawn forest, sky, the forest returning) are
derived from the events too.

Synthesis toolkit: stick-slip friction (an irregular pulse train whose rate drifts, run
through banks of high-Q metal or low-Q wood resonances) for groans and creaks; modal
clanks; motor/gear servo whines; band-swept hiss; filtered impulse-train textures for
soil, sand, pebbles, leaves and crackle; syllable-based birdsong with fast FM sweeps;
stroke-by-stroke wingbeats; a physical Doppler model (variable propagation delay, 1/r
and air absorption) for the launch roar.
"""
import math

import numpy as np

import aw2_instruments as I
from aw2_core import (SR, TWO_PI, Bus, add_modes, base_name, bp, cos_ramp, db, hp, launch_silence, lp, mtof, norm_peak,
                      norm_rms, peq, pink, reson, rng_for, saw_blep, sec, slow_noise, smooth, svf_tv, warn)


class Ctx:
    def __init__(self, C):
        self.C = C
        self.fx = Bus(C.n, sends=("near", "far", "sky"))
        self.amb = Bus(C.n, sends=("far", "sky"))
        self.onsets = []
        self.n = C.n

    def add(self, x, t, pan=0.0, g=0.0, near=0.0, far=0.0, sky=0.0, name=None, bus="fx", width=1.0, onset=None, sync=False):
        """sync=True marks the sound that is meant to land exactly on the cue (event check)."""
        b = self.fx if bus == "fx" else self.amb
        send = {k: v for k, v in (("near", near), ("far", far), ("sky", sky)) if v and k in b.sends}
        b.add(x, t, pan=pan, gain=float(db(g)), send=send, name=("*" + name) if (sync and name) else name, width=width,
              log_onset=onset)
        self.onsets.append(t)


# ============================================================================ building blocks
def grain_kernel(rng, k):
    """Noise grain with a smooth onset (10 %) and a tapered tail: no steps."""
    i = np.arange(k)
    w = np.exp(-i / (k / 4)) * (0.5 - 0.5 * np.cos(np.pi * np.minimum(1.0, i / max(9.0, 0.1 * k))))
    m = max(1, k // 5)
    w[-m:] *= cos_ramp(m)[::-1]
    return rng.standard_normal(k) * w


def ramp_in(x, ms):
    m = min(len(x), sec(ms / 1000.0))
    if m > 0:
        x[:m] *= cos_ramp(m)
    return x


def burst(rng, dur, lo, hi, tau, att=0.0008, order=2):
    n = sec(dur)
    t = np.arange(n) / SR
    y = bp(rng.standard_normal(n), lo, hi, order) * np.exp(-t / tau)
    return ramp_in(y, att * 1000)


def thud(rng, f0=90.0, f1=34.0, glide=0.08, tau=0.35, dur=1.6, click=0.12, rumble=0.35, attack_ms=3.0):
    n = sec(dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / glide)
    sub = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t / tau)
    rum = norm_rms(lp(rng.standard_normal(n), 170, 2)) * np.exp(-t / (tau * 0.6))
    clk = norm_rms(bp(rng.standard_normal(n), 600, 4000, 2)) * np.exp(-t / 0.012)
    y = sub + rumble * 0.4 * rum + click * 0.4 * clk
    return norm_peak(ramp_in(y, attack_ms))


def stick_slip(rng, dur, rate, amp, modes, jitter=0.25, grit=0.25, body=0.4, slip=0.0):
    """Friction: irregular pulses at `rate` Hz (array) with amplitudes `amp` (array),
    exciting resonators [(f, Q, gain)].  slip = chance per pulse of a big slip event."""
    n = sec(dur)
    rate = np.broadcast_to(np.asarray(rate, float), (n,))
    amp = np.broadcast_to(np.asarray(amp, float), (n,))
    r = rate * np.exp(jitter * slow_noise(rng, n, 140.0))
    ph = np.cumsum(r) / SR
    idx = np.nonzero(np.diff(np.floor(ph)))[0] + 1
    exc = np.zeros(n)
    a = amp[idx] * np.exp(0.35 * rng.standard_normal(len(idx)))
    if slip > 0:
        big = rng.random(len(idx)) < slip
        a[big] *= rng.uniform(2.0, 3.5, big.sum())
    exc[idx] = a
    exc = np.convolve(exc, PULSE)[:n]            # a slip takes ~0.3 ms, not one sample (no clicks)
    y = np.zeros(n)
    for f, q, g in modes:
        y += g * q * reson(exc, f, q)
    y = norm_peak(y)
    if grit > 0:
        k = grain_kernel(rng, sec(0.003))
        y += grit * norm_peak(bp(np.convolve(exc, k)[:n], 900, 7000, 2))
    if body > 0:
        y += body * norm_peak(lp(exc, 140, 2))
    return norm_peak(y)


PULSE = np.hanning(16)[1:-1]
PULSE /= PULSE.sum() / 4.0


def metal_modes(rng, base, count, spread=4.0, q=(25, 70), tilt=0.8):
    f = base * np.sort(np.exp(rng.uniform(0, math.log(spread * 6), count)))
    return [(float(fi), float(rng.uniform(*q)), float((base / fi) ** tilt * rng.uniform(0.5, 1.0))) for fi in f]


def wood_modes(rng, base, count):
    f = base * np.sort(np.exp(rng.uniform(0, math.log(8), count)))
    return [(float(fi), float(rng.uniform(5, 14)), float((base / fi) ** 0.5 * rng.uniform(0.5, 1.0))) for fi in f]


def groan(rng, dur, f_start, f_end, bend=0.0, rough=0.3, bright=1.0):
    """Deep metal stress groan: stick-slip rate (the pitch) drifts from f_start to f_end with
    a bend in the middle; big structure modes ring; a sub body under it."""
    n = sec(dur)
    x = np.linspace(0, 1, n)
    f = f_start * (f_end / f_start) ** x * (1 + bend * np.sin(np.pi * x)) * (1 + 0.04 * slow_noise(rng, n, 3.0))
    a = np.clip(np.minimum(x / 0.04, 1) * np.minimum((1 - x) / 0.15, 1), 0, 1) * (0.7 + 0.3 * slow_noise(rng, n, 4.0) ** 2)
    modes = metal_modes(rng, 70.0, 16, 5, (30, 90), 0.7 / bright) + [(46.0, 7.0, 0.8), (63.0, 9.0, 0.6)]
    y = stick_slip(rng, dur, f, a, modes, jitter=0.18 + rough * 0.4, grit=0.18 * bright, body=0.3, slip=0.01)
    return norm_peak(y)


def creak(rng, dur, f0, f1, material="metal", amp_pts=None):
    n = sec(dur)
    x = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** x * (1 + 0.08 * slow_noise(rng, n, 6.0))
    a = np.interp(x, *zip(*amp_pts)) if amp_pts else np.clip(np.minimum(x / 0.1, 1) * np.minimum((1 - x) / 0.2, 1), 0, 1)
    a = a * (0.6 + 0.4 * np.clip(slow_noise(rng, n, 12.0), -1, 1.5) ** 2)
    modes = metal_modes(rng, 380.0, 12, 4, (20, 60), 0.6) if material == "metal" else wood_modes(rng, 260.0, 10)
    return stick_slip(rng, dur, f, a, modes, jitter=0.3, grit=0.35, body=0.15 if material == "metal" else 0.3)


def clank(rng, base=320.0, dur=1.6, bright=0.6, low=0.6, n_modes=9):
    n = sec(dur)
    t = np.arange(n) / SR
    y = np.zeros(n)
    ratios = np.array([1.0, 2.31, 2.89, 3.92, 5.13, 6.27, 7.8, 9.4, 11.2])[:n_modes] * rng.uniform(0.96, 1.04, n_modes)
    amps = np.array([1.0, 0.7, 0.5, 0.45, 0.35, 0.25, 0.18, 0.12, 0.08])[:n_modes] * rng.uniform(0.6, 1.0, n_modes)
    taus = np.array([0.9, 0.6, 0.55, 0.4, 0.3, 0.22, 0.16, 0.12, 0.09])[:n_modes] * rng.uniform(0.7, 1.3, n_modes)
    add_modes(y, 0, base * ratios, amps, taus, rng.uniform(0, TWO_PI, n_modes), 12)
    y += bright * norm_peak(bp(rng.standard_normal(n), 1200, 7000, 2)) * np.exp(-t / 0.006)
    y += low * np.sin(TWO_PI * np.cumsum(38 + 50 * np.exp(-t / 0.05)) / SR) * np.exp(-t / 0.18)
    return norm_peak(ramp_in(y, 0.4))


def servo(rng, dur, times, freqs, gear=7.31, env_pts=None, whine=0.35):
    """Electric motor + gearbox: shaft harmonics, gear-mesh whine with shaft sidebands,
    commutator noise."""
    n = sec(dur)
    t = np.arange(n) / SR
    f = np.interp(t, times, freqs) * (1 + 0.01 * slow_noise(rng, n, 8.0))
    ph = TWO_PI * np.cumsum(f) / SR
    motor = sum(np.sin(k * ph + rng.uniform(0, TWO_PI)) / k ** 1.1 for k in range(1, 7))
    gearw = np.sin(gear * ph) * (1 + 0.35 * np.sin(ph)) + 0.4 * np.sin(2 * gear * ph + 0.5)
    brush = bp(rng.standard_normal(n), 2500, 9000, 2) * (0.5 + 0.5 * np.sin(2 * ph))
    y = 0.55 * motor / 2.5 + whine * gearw / 1.4 + 0.08 * norm_rms(brush)
    y = peq(y, 1100, 5.0, 2.0)
    e = np.interp(t, *zip(*env_pts)) if env_pts else np.minimum(1, np.minimum(t / 0.06, (dur - t) / 0.08))
    return norm_peak(y * e)


def hiss(rng, dur, fc_pts, q=1.4, env_pts=None, spit=0.15):
    n = sec(dur)
    t = np.arange(n) / SR
    fc = np.interp(t, *zip(*fc_pts))
    y = svf_tv(rng.standard_normal(n), fc, q, 1) + 0.35 * bp(rng.standard_normal(n), 400, 2500, 2)
    e = np.interp(t, *zip(*env_pts)) if env_pts else np.exp(-t / (dur / 3.0)) * np.minimum(1, t / 0.01)
    if spit:
        y += spit * crackle_mono(rng, n, 60, (2000, 8000)) * 3
    return norm_peak(y * e)


def crackle_mono(rng, n, rate, band, kernel_ms=1.0):
    p = np.clip(np.broadcast_to(np.asarray(rate, float), (n,)) / SR, 0, 0.5)
    m = rng.random(n) < p
    exc = np.zeros(n)
    exc[m] = np.exp(0.6 * rng.standard_normal(m.sum()))
    k = max(4, sec(kernel_ms / 1000))
    ker = grain_kernel(rng, k)
    return bp(np.convolve(exc, ker)[:n], band[0], band[1], 2)


def texture(rng, n, rate, filt, amp_sigma=0.6, kernel_ms=1.5, spread=1.0, center=0.0):
    """Stereo impulse-train texture.  rate: events/s (scalar or per-sample array);
    filt: list of ('res', f, q, gain) | ('bp', lo, hi, gain) | ('lp', f, 0, gain); each
    event is routed to one filter at random and panned at random within the spread."""
    rate = np.broadcast_to(np.asarray(rate, float), (n,))
    m = rng.random(n) < np.clip(rate / SR, 0, 0.5)
    idx = np.nonzero(m)[0]
    out = np.zeros((n, 2))
    if len(idx) == 0:
        return out
    a = np.exp(amp_sigma * rng.standard_normal(len(idx)))
    pan = np.clip(center + spread * rng.uniform(-1, 1, len(idx)), -1, 1)
    ang = (pan + 1) * np.pi / 4
    which = rng.integers(len(filt), size=len(idx))
    k = max(4, sec(kernel_ms / 1000))
    ker = grain_kernel(rng, k) if kernel_ms > 0 else PULSE
    for fi, spec in enumerate(filt):
        sel = which == fi
        if not sel.any():
            continue
        exc = np.zeros((n, 2))
        exc[idx[sel], 0] = a[sel] * np.cos(ang[sel])
        exc[idx[sel], 1] = a[sel] * np.sin(ang[sel])
        for ch in range(2):
            e = np.convolve(exc[:, ch], ker)[:n] if len(ker) > 1 else exc[:, ch]
            kind = spec[0]
            if kind == "res":
                y = reson(e, spec[1], spec[2]) * spec[2]
            elif kind == "bp":
                y = bp(e, spec[1], spec[2], 2)
            else:
                y = lp(e, spec[1], 2)
            out[:, ch] += spec[3] * y
    return out


def whoosh(rng, dur, fc_pts, q=0.9, env_pts=None, width_pts=None, rattle=0.0, rattle_band=(2500, 8000)):
    """Broadband air movement: band-pass centre follows fc_pts, a mid/side pair whose width
    follows width_pts (0 = centre, 1 = wide, never a delayed copy -> no comb filtering)."""
    n = sec(dur)
    t = np.arange(n) / SR
    fc = np.interp(t, *zip(*fc_pts))
    mid = norm_rms(svf_tv(rng.standard_normal(n), fc, q, 1))
    side = norm_rms(svf_tv(rng.standard_normal(n), fc * 1.07, q, 1))
    w = np.interp(t, *zip(*width_pts)) if width_pts else np.full(n, 0.6)
    e = np.interp(t, *zip(*env_pts)) if env_pts else np.sin(np.pi * t / dur) ** 2
    if rattle:
        lv = crackle_mono(rng, n, 900 * e + 20, rattle_band, 2.0)
        mid += rattle * norm_rms(lv) * 0.6
        side += rattle * norm_rms(crackle_mono(rng, n, 900 * e + 20, rattle_band, 2.0)) * 0.6
    L = (mid + w * side) * e
    R = (mid - w * side) * e
    return np.stack([L, R], 1) / (np.abs(np.stack([L, R], 1)).max() + 1e-9)


def dist(y, d):
    """Distance: 1/d level and air absorption (d in 'near-field units', >= 1)."""
    fc = float(np.clip(15000.0 / d ** 0.7, 1200, 16000))
    return lp(y, fc, 2) / d


# ============================================================================ birds
def _tone(rng, f, e, h2=0.12, h3=0.03, breath=0.02):
    ph = TWO_PI * np.cumsum(f) / SR + rng.uniform(0, TWO_PI)
    y = np.sin(ph) + h2 * np.sin(2 * ph + 0.3) + h3 * np.sin(3 * ph + 0.7)
    if breath:
        y += breath * hp(rng.standard_normal(len(f)), 3000, 2)
    return y * e


def _shape(n, att_s, rel_s):
    e = np.ones(n)
    a, r = min(n // 2, sec(att_s)), min(n // 2, sec(rel_s))
    if a:
        e[:a] = cos_ramp(a)
    if r:
        e[n - r:] *= cos_ramp(r)[::-1]
    return e


def syllable(rng, kind, s=1.0):
    U = rng.uniform
    if kind == "chip":
        d = U(0.018, 0.034)
        n = sec(d)
        x = np.linspace(0, 1, n)
        f0 = U(6000, 7600) * s
        f = f0 * (U(0.45, 0.6) + (1 - U(0.45, 0.6)) * np.exp(-3.2 * x))
        return _tone(rng, f, _shape(n, 0.0015, 0.008) * np.exp(-1.5 * x), 0.16, 0.05)
    if kind == "tsee":
        d = U(0.08, 0.2)
        n = sec(d)
        x = np.linspace(0, 1, n)
        f = U(7200, 8600) * s * (1 + 0.05 * x)
        return _tone(rng, f, _shape(n, 0.012, 0.025), 0.05, 0.0)
    if kind == "up":
        d = U(0.035, 0.07)
        n = sec(d)
        x = np.linspace(0, 1, n)
        f = U(3000, 4200) * s * (1 + U(0.55, 1.0) * x ** 0.7)
        return _tone(rng, f, _shape(n, 0.003, 0.012), 0.12, 0.03)
    if kind == "arch":
        d = U(0.05, 0.11)
        n = sec(d)
        x = np.linspace(0, 1, n)
        f = (U(3200, 4300) + U(900, 1800) * np.sin(np.pi * x)) * s
        return _tone(rng, f, _shape(n, 0.006, 0.015), 0.1, 0.02)
    if kind == "trill":
        parts = []
        fbase = U(4800, 6600) * s
        for _ in range(int(rng.integers(6, 14))):
            d = U(0.012, 0.02)
            n = sec(d)
            x = np.linspace(0, 1, n)
            f = fbase * (1 - U(0.18, 0.3) * x) * U(0.97, 1.03)
            parts.append(_tone(rng, f, _shape(n, 0.0015, 0.005), 0.14, 0.04))
            parts.append(np.zeros(sec(U(0.018, 0.032))))
        return np.concatenate(parts)
    if kind == "warble":
        d = U(0.1, 0.24)
        n = sec(d)
        t = np.arange(n) / SR
        f = U(2600, 4200) * s * (1 + U(0.08, 0.15) * np.sin(TWO_PI * U(25, 55) * t))
        return _tone(rng, f, _shape(n, 0.01, 0.03), 0.08, 0.02)
    if kind == "buzz":
        d = U(0.06, 0.12)
        n = sec(d)
        t = np.arange(n) / SR
        f = U(3500, 5000) * s + U(500, 900) * np.sin(TWO_PI * U(140, 240) * t)
        return _tone(rng, f, _shape(n, 0.004, 0.015), 0.25, 0.1, 0.05)
    if kind == "whistle":
        d = U(0.15, 0.38)
        n = sec(d)
        x = np.linspace(0, 1, n)
        t = np.arange(n) / SR
        f = U(2000, 3400) * s * (1 + U(-0.08, 0.12) * x) * (1 + 0.012 * np.sin(TWO_PI * 6.0 * t))
        return _tone(rng, f, _shape(n, 0.02, 0.05), 0.04, 0.0, 0.01)
    if kind == "coo":
        d = U(0.3, 0.48)
        n = sec(d)
        x = np.linspace(0, 1, n)
        f = U(450, 620) * (1 + 0.07 * np.sin(np.pi * x) - 0.05 * x)
        y = _tone(rng, f, _shape(n, 0.05, 0.12) ** 1.5, 0.22, 0.05, 0.0)
        return y + 0.04 * lp(rng.standard_normal(n), 1200, 2) * _shape(n, 0.05, 0.12)
    if kind == "tchk":
        n = sec(0.02)
        t = np.arange(n) / SR
        y = bp(rng.standard_normal(n), 2200, 7000, 2) * np.exp(-t / 0.004)
        return ramp_in(y + 0.6 * np.sin(TWO_PI * U(3500, 4500) * t) * np.exp(-t / 0.005), 0.3)
    raise ValueError(kind)


SPECIES = {
    "robin": (lambda r: [str(r.choice(["whistle", "warble", "trill", "tsee", "arch", "up"])) for _ in range(int(r.integers(5, 9)))], (0.03, 0.10)),
    "tit": (lambda r: ["up", "chip"] * int(r.integers(3, 5)), (0.04, 0.07)),
    "chaff": (lambda r: ["trill", "trill", "arch"], (0.01, 0.03)),
    "thrush": (lambda r: ["whistle", "whistle", "trill"] if r.random() < 0.5 else ["whistle", "warble", "whistle"], (0.06, 0.14)),
    "dove": (lambda r: ["coo", "coo", "coo"], (0.12, 0.2)),
    "wren": (lambda r: ["trill", "chip", "trill", "buzz", "trill", "chip", "chip"], (0.01, 0.04)),
}


def phrase(rng, species, s=1.0):
    gen, gap = SPECIES[species]
    parts = []
    for k in gen(rng):
        parts.append(syllable(rng, k, s))
        parts.append(np.zeros(sec(rng.uniform(*gap))))
    return norm_peak(np.concatenate(parts))


def little_bird_call(rng, kind):
    """The small bird: tsip calls, a happy twitter, or an alarm."""
    s = 1.05
    if kind == "tsip":
        seq = ["chip", "tsee"] if rng.random() < 0.5 else ["up", "chip", "chip"]
        gap = (0.05, 0.09)
    elif kind == "twitter":
        seq = ["up", "chip", "trill", "arch", "chip"]
        gap = (0.03, 0.06)
    else:
        seq = ["tchk", "tchk", "tsee", "tchk"]
        gap = (0.04, 0.07)
    parts = []
    for k in seq:
        parts.append(syllable(rng, k, s))
        parts.append(np.zeros(sec(rng.uniform(*gap))))
    return norm_peak(np.concatenate(parts))


WING = {"small": dict(band=(1800, 8500), flap=0.020, low=(0.12, 300), bound=(4, 7)),
        "medium": dict(band=(700, 6000), flap=0.034, low=(0.35, 320), bound=None),
        "large": dict(band=(350, 4500), flap=0.050, low=(0.6, 220), bound=None)}


def wings(rng, dur, rate, size="small", claps=0, bound=True, strength=None):
    """Wingbeats stroke by stroke: a down-stroke 'fff' (strong) and an up-stroke (weak) per
    cycle; small birds bound (bursts of flaps, short glides); pigeons clap at take-off."""
    P = WING[size]
    n = sec(dur)
    y = np.zeros(n)
    t, k, inburst = 0.0, 0, 0
    burst_len = int(rng.integers(*P["bound"])) if (P["bound"] and bound) else 10 ** 9
    while t < dur - P["flap"] * 1.3:
        r = rate(t) if callable(rate) else rate
        m = sec(P["flap"] * rng.uniform(0.85, 1.2))
        i0 = sec(t)
        if i0 + m > n:
            break
        lo, hi = P["band"][0] * rng.uniform(0.85, 1.15), P["band"][1] * rng.uniform(0.85, 1.1)
        tn = np.arange(m) / SR
        down = k % 2 == 0
        e = (1 - np.exp(-tn / 0.0025)) * np.exp(-tn / (P["flap"] * 0.38))
        q = max(2, m // 4)
        e[-q:] *= cos_ramp(q)[::-1]
        b = norm_rms(bp(rng.standard_normal(m), lo, hi, 2)) * e
        if P["low"][0] > 0 and down:
            b += P["low"][0] * norm_rms(lp(rng.standard_normal(m), P["low"][1], 2)) * e
        amp = (1.0 if down else 0.42) * rng.uniform(0.8, 1.15) * (strength(t) if strength else 1.0)
        if claps and down and k // 2 < claps:
            c = sec(0.002)
            b[:c] += ramp_in(hp(rng.standard_normal(c), 1500, 2) * np.exp(-np.arange(c) / sec(0.0006)), 0.35) * 2.2
        y[i0:i0 + m] += b * amp
        t += rng.uniform(0.94, 1.06) / (2.0 * r)
        k += 1
        if down:
            inburst += 1
            if inburst >= burst_len:
                t += rng.uniform(0.07, 0.18)
                inburst = 0
                burst_len = int(rng.integers(*P["bound"]))
    return y / (np.abs(y).max() + 1e-9)


# ============================================================================ ambience
def ambience(ctx):
    C, n = ctx.C, ctx.n
    rng = rng_for("amb")
    t = np.arange(n) / SR
    dur = C.duration
    T_imp = C.first("impact_frame", dur * 0.74)
    T_sky = C.first("sky_reveal", T_imp + 4.0)
    T_tf = C.first("trail_fades", T_sky + 6.5)
    c_in = C.section("coda", (T_tf + 1.5, dur))[0]
    T_burst = C.first("birds_burst", C.first("tremor_start", dur * 0.33) + 2.5)
    T_sun = C.first("sun_ray_reaches_face", dur * 0.2)
    T_wr = C.first("wind_ring", T_imp - 3.4)
    T_trem = C.first("tremor_start", T_burst - 2.5)
    forest = np.interp(t, [0, T_imp - 0.2, T_imp + 1.5, T_tf + 0.3, max(c_in, T_tf + 1.0) + 0.8, dur], [1, 1, 0.35, 0.35, 1, 1])
    sky = np.interp(t, [0, T_sky - 0.5, T_sky + 0.8, T_tf + 0.2, T_tf + 2.2, dur], [0, 0, 1, 1, 0, 0])
    forest = np.where(t < T_sky - 0.3, forest, np.minimum(forest, np.interp(t, [T_sky - 0.3, T_sky + 0.3], [forest[sec(min(dur, T_sky - 0.3)) - 1], 0.0])))
    forest = np.maximum(forest, np.interp(t, [0, T_tf + 0.4, max(c_in, T_tf + 1.0) + 0.8, dur], [0, 0, 0.75, 0.75]))
    forest = smooth(forest, 300)
    # wind: gusts (asymmetric bumps), quieter while the robot acts, scripted rise before the ring
    gust = np.zeros(n)
    tg = 1.0
    while tg < dur:
        amp = rng.uniform(0.4, 1.0)
        rise, fall = rng.uniform(1.2, 2.4), rng.uniform(2.5, 4.5)
        i0, i1, i2 = sec(tg), min(n, sec(tg + rise)), min(n, sec(tg + rise + fall))
        if i1 > i0:
            gust[i0:i1] += amp * cos_ramp(i1 - i0)
        if i2 > i1:
            gust[i1:i2] += amp * cos_ramp(i2 - i1)[::-1]
        tg += rng.uniform(5.5, 9.5)
    calm = np.interp(t, [0, T_trem, T_trem + 2, T_wr - 2.5, T_wr - 0.5, T_imp + 2, c_in, dur], [1, 1, 0.55, 0.55, 1.2, 0.4, 0.7, 0.7])
    wind = np.clip(0.30 + 0.08 * np.sin(TWO_PI * 0.045 * t + 1.0) + 0.6 * gust * calm, 0.05, 1.6)
    wind = smooth(wind, 200)
    out = np.zeros((n, 2))
    shared = pink(rng, n)
    for ch in range(2):
        src = 0.6 * pink(rng, n) + 0.4 * shared
        fc = 160.0 * (1 + 2.2 * wind) * (1 + 0.04 * (ch - 0.5))
        body = norm_rms(svf_tv(src, fc, 0.7, 1)) * db(-44 + 5.0 * wind)
        hissy = norm_rms(svf_tv(rng.standard_normal(n), 900 * (1 + 2.0 * wind), 1.2, 1)) * db(-58 + 12 * wind)
        out[:, ch] = body + hissy
    ctx.add(out * forest[:, None], 0.0, g=0.0, far=0.10, name="forest wind", bus="amb")
    # leaves: crinkle texture whose density follows the wind
    lv = texture(rng, n, 120 + 900 * np.clip(wind - 0.25, 0, 1.5) ** 1.5, [("bp", 2500, 9000, 1.0), ("bp", 1500, 5000, 0.6)],
                 kernel_ms=2.5, spread=0.95)
    ctx.add(lv * (forest * db(-49 + 5 * np.clip(wind, 0, 1.4)))[:, None] / (np.abs(lv).max() + 1e-9) * 6, 0.0, far=0.25,
            name="leaves", bus="amb")
    # crickets at dawn, fading as the sun arrives
    cri_end = T_sun + 2.0
    for k, (pan, fcar, rate, lvl) in enumerate(((-0.55, 4300, 28.0, -54), (0.6, 4750, 33.0, -57), (0.15, 4050, 24.0, -60))):
        m = sec(cri_end)
        tc = np.arange(m) / SR
        r2 = rng_for("amb", "cricket", k)
        chirp_on = (np.sin(TWO_PI * tc * r2.uniform(0.9, 1.4) + r2.uniform(0, TWO_PI)) > 0.1).astype(float)
        pulses = np.clip(np.sin(TWO_PI * rate * tc), 0, 1) ** 3
        car = np.sin(TWO_PI * fcar * tc) + 0.2 * np.sin(TWO_PI * 2 * fcar * tc)
        y = car * pulses * smooth(chirp_on, 8) * np.interp(tc, [0, 1.5, cri_end - 4.0, cri_end], [0.2, 1, 1, 0])
        ctx.add(y, 0.0, pan=pan, g=lvl, far=0.6, name="cricket", bus="amb")
    # a distant stream down in the valley
    st = pink(rng, n)
    stream = np.stack([bp(st, 250, 2500, 2), bp(pink(rng, n), 250, 2500, 2)], 1)
    stream *= (1 + 0.25 * slow_noise(rng, n, 0.5))[:, None]
    bub = texture(rng, n, 70, [("res", 700, 12, 1.0), ("res", 1100, 15, 0.8), ("res", 1600, 18, 0.6), ("res", 520, 10, 0.8)],
                  kernel_ms=0, spread=0.6)
    stream = norm_rms(stream) * db(-55) + norm_rms(bub) * db(-60)
    ctx.add(stream * forest[:, None], 0.0, far=0.5, name="distant stream", bus="amb", width=0.7)
    # distant birds: a dawn chorus that stops when the flock flees, returning in the coda
    windows = [(0.8, T_burst - 0.3, (1.3, 3.2), 0.0), (max(c_in, T_tf + 1.0) + 0.5, dur - 0.5, (1.4, 3.0), -3.0)]
    sp_list = ["robin", "tit", "chaff", "thrush", "dove", "wren"]
    for wi, (a, b, gap, extra) in enumerate(windows):
        r2 = rng_for("amb", "birds", wi)
        tb = a + r2.uniform(0, 0.6)
        last = None
        weights = np.array([1.0, 1.0, 1.0, 1.0, 0.35, 0.8])
        while tb < b - 0.3:
            choices = [i for i in range(len(sp_list)) if sp_list[i] != last]
            w = weights[choices] / weights[choices].sum()
            sp = sp_list[int(r2.choice(choices, p=w))]
            last = sp
            ph = phrase(r2, sp, r2.uniform(0.92, 1.08))
            d = r2.uniform(3.0, 9.0)
            g = -30 + extra + r2.uniform(-3, 2) - 4 * math.log2(d / 3.0) - (6 if sp == "dove" else 0)
            ctx.add(dist(ph, d), tb, pan=r2.uniform(-0.9, 0.9), g=g + 20 * math.log10(d), far=0.6 + 0.12 * d,
                    name="distant bird (%s)" % sp, bus="amb")
            tb += r2.uniform(*gap)
    # the sky: high-altitude wind, smooth and wide
    sk = np.zeros((n, 2))
    for ch in range(2):
        s0 = pink(rng, n)
        sk[:, ch] = norm_rms(lp(s0, 900, 2)) * 0.7 + norm_rms(svf_tv(pink(rng, n), 380 * (1 + 0.3 * slow_noise(rng, n, 0.25)), 1.6, 1)) * 0.35
    sk *= (1 + 0.3 * slow_noise(rng, n, 0.3))[:, None]
    ctx.add(sk * (sky * db(-42))[:, None], 0.0, sky=0.15, name="sky wind", bus="amb")
    # leaves spiralling down in the coda
    r2 = rng_for("amb", "coda leaves")
    tl = max(c_in, T_tf + 1.0)
    while tl < dur - 0.5:
        m = sec(r2.uniform(0.25, 0.6))
        x = np.arange(m) / SR
        fl = bp(r2.standard_normal(m), 2200, 7000, 2) * (0.5 + 0.5 * np.sin(TWO_PI * r2.uniform(7, 14) * x)) ** 2
        fl *= np.sin(np.pi * x / x[-1]) ** 2
        ctx.add(fl, tl, pan=r2.uniform(-0.8, 0.8), g=-50 + r2.uniform(-4, 2), far=0.4, name="leaf tumbling", bus="amb")
        tl += r2.exponential(0.9) + 0.25


# ============================================================================ event handlers
HANDLERS = {}
SILENT = {"fade_in_start", "fade_out_start", "end"}      # handled by the master fades


def on(name):
    def deco(fn):
        HANDLERS[name] = fn
        return fn
    return deco


@on("bird_crosses_far")
def h_bird_crosses(ctx, t, k):
    r = rng_for("fx", "cross", k)
    d = 2.2
    w = wings(r, d, 17.0, "small", bound=True)
    x = np.linspace(0, 1, len(w))
    w *= np.interp(x, [0, 0.25, 0.7, 1], [0.3, 0.9, 1.0, 0.4])
    ctx.add(dist(w, 5.0), t - 0.6, pan=np.interp(x, [0, 1], [0.85, -0.1]), g=-9, far=0.9, name="small bird crosses (far)")
    ctx.add(dist(little_bird_call(r, "tsip"), 5.0), t + 0.35, pan=0.2, g=-11, far=0.9, name="far tsip")


@on("bird_wings_flare")
def h_flare(ctx, t, k):
    r = rng_for("fx", "flare", k)
    d = 0.55
    w = wings(r, d, 11.5, "small", bound=False, strength=lambda tt_: 1.0 - 0.45 * tt_ / d)
    w = w * 0.85 + 0.15 * norm_peak(lp(w, 900, 2))
    x = np.linspace(0, 1, len(w))
    ctx.add(w, t, pan=np.interp(x, [0, 1], [0.35, -0.12]), g=-16, near=0.25, far=0.12, name="wings flare", sync=True)


@on("bird_touchdown")
def h_touchdown(ctx, t, k):
    r = rng_for("fx", "touch", k)
    for j, dt in enumerate((0.0, 0.035)):
        tick = burst(r, 0.02, 2500, 9000, 0.0025, 0.0002) + 0.4 * burst(r, 0.02, 600, 2000, 0.004)
        ctx.add(norm_peak(tick), t + dt, pan=-0.12 + 0.03 * j, g=-24 - 3 * j, near=0.3, name="claws touch" if j == 0 else None,
                sync=(j == 0))
    mo = texture(r, sec(0.35), 140, [("bp", 1500, 6000, 1.0)], kernel_ms=3.0, spread=0.15, center=-0.12)
    mo *= np.exp(-np.arange(len(mo)) / sec(0.09))[:, None]
    ctx.add(mo / (np.abs(mo).max() + 1e-9), t + 0.01, g=-30, near=0.3, name="moss scuffle")
    fold = wings(r, 0.12, 14.0, "small", bound=False)
    ctx.add(lp(fold, 5000, 2), t + 0.08, pan=-0.12, g=-28, near=0.25, name="wing fold")


@on("bird_hop")
def h_hop(ctx, t, k):
    r = rng_for("fx", "hop", k)
    fl = wings(r, 0.09, 16.0, "small", bound=False)
    ctx.add(fl, t, pan=-0.12, g=-23, near=0.25, name="hop flick", sync=True)
    tick = burst(r, 0.02, 2200, 8000, 0.003, 0.0002)
    ctx.add(norm_peak(tick), t + 0.14, pan=-0.1, g=-31, near=0.3, name="hop land")


@on("bird_chirp")
def h_chirp(ctx, t, k):
    r = rng_for("fx", "chirp", k)
    ctx.add(little_bird_call(r, "tsip" if k % 2 == 0 else "twitter"), t, pan=-0.12 + r.uniform(-0.04, 0.04), g=-18, sync=True,
            near=0.22, far=0.1, name="little bird chirp")


@on("sun_ray_reaches_face")
def h_sun(ctx, t, k):
    """Old metal warming in the first sun: a few tiny ticks of thermal expansion."""
    r = rng_for("fx", "sun", k)
    nxt = ctx.C.after(t, {"core_flicker", "tremor_start"}, t + 6.0)
    tk = t + r.uniform(0.8, 1.5)
    while tk < nxt - 0.6:
        c = clank(r, r.uniform(1800, 3200), 0.4, bright=0.3, low=0.0, n_modes=4)
        ctx.add(c, tk, pan=r.uniform(-0.35, 0.35), g=-40 + r.uniform(-3, 2), near=0.4, name="metal warms (tick)")
        tk += r.uniform(0.9, 2.2)


@on("core_flicker")
def h_flicker(ctx, t, k):
    """A light trying to start: gated buzz (A2 and harmonics, arcing edge), crackle, relay."""
    r = rng_for("fx", "flicker", k)
    d = 0.5
    n = sec(d)
    tn = np.arange(n) / SR
    f = 110.0 * (1 + 0.004 * np.sin(TWO_PI * 7 * tn))
    buzz = saw_blep(f, 0.0) * 0.5 + np.sin(TWO_PI * 55 * tn) * 0.8
    buzz = lp(buzz, 2200, 4) + 0.15 * bp(r.standard_normal(n), 2000, 7000, 2) * np.clip((np.sin(TWO_PI * 110 * tn) - 0.6) / 0.4, 0, 1) ** 2
    gate = np.zeros(n)
    tg = 0.0
    while tg < d - 0.03:
        on_ = r.uniform(0.02, 0.09)
        i0, i1 = sec(tg), min(n, sec(tg + on_))
        gate[i0:i1] = r.uniform(0.5, 1.0)
        tg += on_ + r.uniform(0.02, 0.08)
    gate = smooth(gate, 4)
    ctx.add(norm_peak(buzz * gate), t, g=-23 + 2 * k, near=0.35, name="core flicker buzz", sync=True)
    cr = norm_peak(crackle_mono(r, n, 90 * gate + 5, (2500, 9000), 1.2))
    ctx.add(cr, t, pan=r.uniform(-0.1, 0.1), g=-25 + 2 * k, near=0.3, name="core crackle")
    rel = clank(r, 900, 0.25, bright=0.5, low=0.4, n_modes=4)
    ctx.add(rel, t - 0.015, g=-33, near=0.3, name="relay")


def hum_tone(rng, n, f0=55.0, bright=None):
    t = np.arange(n) / SR
    f = f0 * (1 + 0.0015 * slow_noise(rng, n, 0.4))
    ph = TWO_PI * np.cumsum(f) / SR
    y = np.zeros(n)
    for kk, a in ((1, 1.0), (2, 0.55), (3, 0.32), (4, 0.2), (5, 0.12), (6, 0.08), (8, 0.04)):
        y += a * np.sin(kk * ph + rng.uniform(0, TWO_PI))
    y += 0.5 * np.sin(TWO_PI * np.cumsum(f * 1.004) / SR)               # slow beating
    if bright is not None:
        edge = bp(saw_blep(f * 2, 0.0), 300, 2500, 2)
        y += 0.25 * edge * bright
    return y / 2.6


@on("core_glow_steady")
def h_glow(ctx, t, k):
    """The core hum (A1, in the score's key) from here until the engines take over:
    spins up, swells with every heartbeat, brightens with the eyes, steps up on standing."""
    C = ctx.C
    r = rng_for("fx", "hum", k)
    end = C.after(t, {"engine_ignite", "impact_frame"}, t + 25.0)
    d = end - t + 1.5
    n = sec(d)
    tn = np.arange(n) / SR
    spin = np.interp(tn, [0, 0.9], [0.86, 1.0])
    lvl = [(0, 0.0), (0.8, 1.0)]
    for name, gain in (("tremor_start", 1.1), ("eyes_ignite", 1.6), ("stands_full_thud", 1.9), ("eyes_resolve", 2.2),
                       ("back_plates_open", 2.4)):
        te = C.first(name)
        if te is not None and t < te < end:
            lvl.append((te - t, gain))
    lvl = sorted(lvl)
    lvl += [(end - t, lvl[-1][1] * 0.8), (end - t + 1.2, 0.0)]
    e = np.interp(tn, [p[0] for p in lvl], [p[1] for p in lvl])
    e = smooth(e, 250)
    for hb in C.times("core_heartbeat"):
        if t <= hb < end:
            x = tn - (hb - t)
            e *= 1 + 0.9 * np.exp(-np.clip(x, 0, None) / 0.35) * (x >= -0.05) * np.minimum(1, (x + 0.05) / 0.05)
    br = np.interp(tn, [0, max(0.1, (C.first("eyes_ignite", end) or end) - t), d], [0.2, 0.9, 1.0])
    y = np.zeros(n)
    y += hum_tone(r, n, 55.0) * spin
    y += 0.5 * bp(saw_blep(110.0 * spin, 0.0), 200, 2000, 2) * br
    ctx.add(y * e, t, g=-25, near=0.15, far=0.1, name="core hum", width=1.0)
    up = whoosh(r, 1.2, [(0, 300), (1.2, 1800)], 1.5, [(0, 0), (0.9, 1), (1.2, 0)], [(0, 0), (1.2, 0.3)])
    ctx.add(up, t - 0.4, g=-31, near=0.2, name="power-up breath")


@on("core_heartbeat")
def h_heart(ctx, t, k):
    r = rng_for("fx", "heart", k)
    lub = thud(r, 100, 60, 0.035, 0.09, 0.6, click=0.06, rumble=0.5, attack_ms=6)
    dub = thud(r, 112, 68, 0.03, 0.07, 0.5, click=0.05, rumble=0.45, attack_ms=6)
    body = np.exp(-np.arange(sec(0.6)) / sec(0.05))
    lub = norm_peak(lub + 0.5 * norm_peak(bp(r.standard_normal(sec(0.6)), 90, 320, 2)) * body)
    dub = norm_peak(dub + 0.5 * norm_peak(bp(r.standard_normal(sec(0.5)), 100, 360, 2)) * body[: sec(0.5)])
    ring = np.zeros(sec(0.8))
    add_modes(ring, 0, np.array([118.0, 237.0, 410.0]), np.array([1.0, 0.5, 0.25]), np.array([0.18, 0.12, 0.08]), np.zeros(3), 300)
    g0 = -14 + 2.0 * k
    ctx.add(lub, t, g=g0, near=0.2, name="heartbeat lub", sync=True)
    ctx.add(dub, t + 0.27, g=g0 - 4, near=0.2, name="heartbeat dub")
    ctx.add(norm_peak(ring), t, g=g0 - 14, near=0.3)


@on("tremor_start")
def h_tremor(ctx, t, k):
    """Ground tremor from here to the hand pressing down: sub rumble, shaking mid rumble,
    soil stress crackle, pebbles and dew jumping, a far tree creak."""
    C = ctx.C
    r = rng_for("fx", "tremor", k)
    end = C.after(t, {"hand_presses_ground"}, t + 9.0) + 0.6
    burst_t = C.after(t - 1e-6, {"birds_burst"}, t + 2.5)
    lids = C.after(t - 1e-6, {"eye_lids_open"}, burst_t + 3.5)
    d = end - t
    n = sec(d)
    tn = np.arange(n) / SR
    pts = [(0, 0), (min(1.6, 0.6 * (burst_t - t)), 0.7), (burst_t - t, 1.0), (burst_t - t + 1.2, 0.6), (lids - t, 0.35),
           (d - 1.4, 0.5), (d - 0.6, 0.55), (d, 0.0)]
    pts = sorted([(min(max(a, 0), d), b) for a, b in pts])
    e = smooth(np.interp(tn, [p[0] for p in pts], [p[1] for p in pts]), 200)
    shake = 1 + 0.35 * np.clip(slow_noise(r, n, 7.0), -2, 2)
    sub = norm_rms(bp(r.standard_normal(n), 32, 70, 2)) * 0.7 + 0.25 * np.sin(TWO_PI * np.cumsum(38 * (1 + 0.06 * slow_noise(r, n, 1.2))) / SR)
    out = np.zeros((n, 2))
    for ch in range(2):
        mid = norm_rms(bp(r.standard_normal(n), 70, 260, 2)) * shake
        out[:, ch] = 0.6 * sub + 0.6 * mid
    out = out * (e ** 1.4)[:, None]
    ctx.add(out / (np.abs(out).max() + 1e-9), t, g=-8, far=0.12, name="ground tremor")
    ctx.add(thud(r, 80, 45, 0.05, 0.22, 1.0, click=0.15, rumble=0.8, attack_ms=4), t, g=-13, far=0.2, name="first jolt", sync=True)
    jp = texture(r, sec(0.5), np.interp(np.arange(sec(0.5)) / SR, [0, 0.03, 0.5], [0, 400, 0]),
                 [("res", 2800, 14, 1.0), ("res", 4300, 18, 0.8), ("res", 1900, 10, 0.9)], kernel_ms=0.9, spread=0.8)
    ctx.add(jp / (np.abs(jp).max() + 1e-9), t + 0.02, g=-24, near=0.35, name="pebbles jump")
    cr = texture(r, n, 40 + 260 * e ** 2, [("bp", 300, 1800, 1.0), ("bp", 1500, 5000, 0.5)], kernel_ms=3.0, spread=0.9)
    ctx.add(cr * e[:, None] / (np.abs(cr).max() + 1e-9), t, g=-33, near=0.2, far=0.2, name="soil stress crackle")
    focus = np.interp(tn, [0, burst_t - t + 0.8, burst_t - t + 1.6, d], [1.0, 1.0, 0.25, 0.25])
    rate = 4 + 140 * (e * focus) ** 1.6
    pb = texture(r, n, rate, [("res", r.uniform(2500, 3500), 14, 1.0), ("res", r.uniform(4000, 5200), 18, 0.8),
                              ("res", r.uniform(1700, 2300), 10, 0.9), ("res", r.uniform(5500, 7000), 20, 0.6)], kernel_ms=0.9, spread=0.85)
    ctx.add(pb / (np.abs(pb).max() + 1e-9), t, g=-23, near=0.35, name="pebbles rattle")
    cr2 = creak(r, 1.6, 55, 42, "wood")
    ctx.add(dist(cr2, 3.0), burst_t - 0.5, pan=0.6, g=-14, far=0.8, name="far tree creak")


@on("birds_burst")
def h_flock(ctx, t, k):
    """Birds burst from the treetops: ~36 birds of three sizes taking off within a second
    (pigeons clap), each flying off to a side, darker and quieter; canopy shaken; alarms."""
    r = rng_for("fx", "flock", k)
    for i in range(36):
        size = "large" if i < 8 else ("medium" if i < 14 else "small")
        start = t - 0.15 + 1.1 * r.beta(1.2, 3.0)
        dur = r.uniform(1.8, 3.4)
        rate = {"large": r.uniform(6.5, 8.5), "medium": r.uniform(4.5, 6.0), "small": r.uniform(14, 19)}[size]
        w = wings(r, dur, lambda tt_, rr=rate: rr * (1 - 0.15 * min(1.0, tt_ / 1.5)), size, claps=3 if size == "large" else 0,
                  bound=(size == "small"))
        x = np.linspace(0, 1, len(w))
        far_ = x ** 1.2
        w = (w * (1 - far_) + lp(w, 900, 2) * far_) * np.interp(x, [0, 0.08, 0.5, 1], [0.0, 1.0, 0.6, 0.0])
        side = r.choice([-1, 1])
        pan = np.interp(x, [0, 1], [r.uniform(-0.5, 0.5), side * r.uniform(0.6, 1.0)])
        g = {"large": -14, "medium": -17, "small": -19}[size] + r.uniform(-4, 1.5)
        ctx.add(w, start, pan=pan, g=g, far=0.45, near=0.1, name="flock wings" if i == 0 else None, onset=t if i == 0 else None)
    ca = texture(r, sec(2.6), np.interp(np.arange(sec(2.6)) / SR, [0, 0.15, 0.8, 2.6], [200, 2200, 900, 0]),
                 [("bp", 1800, 8000, 1.0), ("bp", 800, 3000, 0.6)], kernel_ms=3.0, spread=1.0)
    ctx.add(ca / (np.abs(ca).max() + 1e-9), t, g=-22, far=0.5, name="canopy shaken", sync=True)
    for j in range(7):
        st = t + r.uniform(0.0, 1.4)
        c = little_bird_call(r, "alarm") if j % 2 == 0 else phrase(r, "tit", 1.1)
        ctx.add(dist(c, r.uniform(1.5, 3.5)), st, pan=r.uniform(-0.8, 0.8), g=-17 + r.uniform(-3, 1), far=0.8, name="alarm call")


@on("eye_lids_open")
def h_lids(ctx, t, k):
    r = rng_for("fx", "lids", k)
    d = 0.75
    s = servo(r, d, [0, 0.1, 0.55, d], [90, 210, 230, 160], gear=6.1, env_pts=[(0, 0), (0.08, 1), (0.6, 0.8), (d, 0)])
    ctx.add(s, t, g=-28, near=0.3, name="lid servo", sync=True)
    sc = creak(r, 0.6, 520, 430, "metal")
    ctx.add(sc, t + 0.05, pan=-0.05, g=-34, near=0.3, far=0.2, name="lid scrape")
    ctx.add(clank(r, 640, 0.6, bright=0.3, low=0.3, n_modes=6), t + d - 0.04, g=-33, near=0.3, name="lid stop")
    du = texture(r, sec(1.2), np.interp(np.arange(sec(1.2)) / SR, [0, 0.2, 1.2], [300, 150, 0]), [("bp", 3000, 9000, 1.0)], kernel_ms=1.0, spread=0.4)
    ctx.add(du / (np.abs(du).max() + 1e-9), t + 0.1, g=-43, near=0.2, name="dust trickle")


@on("eyes_ignite")
def h_eyes(ctx, t, k):
    """The eyes light: an electric 'fwoom' gliding up a fifth (A3+E4 -> E4+A4, in key),
    and a small glass ping."""
    r = rng_for("fx", "eyes", k)
    d = 1.8
    n = sec(d)
    tn = np.arange(n) / SR
    g = 0.5 - 0.5 * np.cos(np.pi * np.clip(tn / 0.5, 0, 1))
    f1 = 220.0 * 1.5 ** g
    f2 = 329.63 * (440.0 / 329.63) ** g
    y = np.sin(TWO_PI * np.cumsum(f1) / SR) + 0.7 * np.sin(TWO_PI * np.cumsum(f2) / SR) + 0.15 * np.sin(TWO_PI * np.cumsum(2 * f1) / SR)
    y += 0.25 * svf_tv(r.standard_normal(n), 400 + 3000 * g, 2.0, 1)
    y *= np.interp(tn, [0, 0.06, 0.5, 1.0, d], [0, 0.9, 1.0, 0.45, 0])
    ctx.add(norm_peak(y), t, g=-26, near=0.3, far=0.3, name="eyes ignite")
    zap = norm_peak(crackle_mono(r, sec(0.09), 900, (2000, 9000), 1.2)) * np.exp(-np.arange(sec(0.09)) / sec(0.025))
    zap += 0.5 * norm_peak(np.sin(TWO_PI * 110 * np.arange(sec(0.09)) / SR) * np.exp(-np.arange(sec(0.09)) / sec(0.03)))
    ctx.add(ramp_in(zap, 0.3), t, g=-27, near=0.3, name="eyes zap", sync=True)
    ping = np.zeros(sec(1.2))
    add_modes(ping, 0, np.array([2637.0, 3951.0, 5274.0]), np.array([1.0, 0.4, 0.2]), np.array([0.35, 0.2, 0.1]), np.zeros(3), 20)
    ctx.add(ping, t + 0.42, pan=0.05, g=-40, near=0.3, far=0.3, name="lens ping")


@on("small_bird_flees")
def h_flee(ctx, t, k):
    r = rng_for("fx", "flee", k)
    ctx.add(little_bird_call(r, "alarm"), t, pan=-0.12, g=-24, near=0.2, name="alarm tchk")
    d = 1.6
    w = wings(r, d, lambda tt_: 21.0 - 4 * tt_, "small", bound=False)
    x = np.linspace(0, 1, len(w))
    w = (w * (1 - x ** 1.3) + lp(w, 1500, 2) * x ** 1.3) * np.interp(x, [0, 0.05, 0.4, 1], [0, 1, 0.75, 0])
    ctx.add(w, t, pan=np.interp(x, [0, 1], [-0.12, 0.85]), g=-19, near=0.2, far=0.3, name="small bird takes off", sync=True)


@on("hand_presses_ground")
def h_hand(ctx, t, k):
    """The hand presses into the earth: a soft heavy thud, soil crunch, roots creaking under
    load; soil keeps pouring from the body until the robot stands."""
    C = ctx.C
    r = rng_for("fx", "hand", k)
    ctx.add(thud(r, 72, 31, 0.09, 0.75, 3.0, click=0.08, rumble=1.0, attack_ms=14), t, g=2, far=0.35, near=0.2, name="hand presses earth",
            sync=True)
    cr = texture(r, sec(0.9), np.interp(np.arange(sec(0.9)) / SR, [0, 0.05, 0.6, 0.9], [0, 1500, 300, 0]),
                 [("bp", 200, 1200, 1.0), ("bp", 1200, 4500, 0.5), ("res", 160, 3, 0.8)], kernel_ms=4.0, spread=0.5)
    ctx.add(cr / (np.abs(cr).max() + 1e-9), t, g=-14, near=0.3, name="soil crunch")
    ctx.add(creak(r, 1.3, 95, 70, "wood"), t + 0.15, pan=-0.3, g=-17, near=0.2, far=0.3, name="roots strain")
    ctx.add(servo(r, 1.2, [0, 0.2, 1.0, 1.2], [60, 140, 120, 80], gear=8.3), t - 0.4, pan=0.15, g=-24, near=0.3, name="arm servo")
    # the long soil pour off the body, until standing
    end = C.after(t, {"stands_full_thud"}, t + 7.6) + 1.2
    d = end - t
    n = sec(d)
    tn = np.arange(n) / SR
    dens = np.interp(tn, [0, 0.8, 2.0, d - 2.0, d - 1.0, d], [0.1, 0.4, 0.8, 1.0, 0.5, 0.0])
    for name_, gev in (("rise_groan", 0.35), ("roots_tear", 0.3), ("soil_curtain", 0.6)):
        for te in C.times(name_):
            if t < te < end:
                dens = dens + gev * np.exp(-np.clip(tn - (te - t), 0, None) / 1.2) * (tn >= te - t)
    sand = texture(r, n, 200 + 1400 * dens, [("bp", 2500, 9000, 1.0), ("bp", 1200, 4000, 0.6)], kernel_ms=1.5, spread=0.9)
    clods = texture(r, n, 3 + 28 * dens, [("res", 110, 2.5, 1.0), ("res", 170, 3.0, 0.8), ("res", 240, 3.5, 0.6), ("lp", 400, 0, 0.5)],
                    kernel_ms=10.0, spread=0.8)
    peb = texture(r, n, 2 + 30 * dens, [("res", 2200, 12, 1.0), ("res", 3400, 16, 0.8), ("res", 1500, 9, 0.8)], kernel_ms=0.9, spread=0.9)
    pour = sand / (np.abs(sand).max() + 1e-9) * db(-6) + clods / (np.abs(clods).max() + 1e-9) + peb / (np.abs(peb).max() + 1e-9) * db(-8)
    ctx.add(pour * smooth(dens, 50)[:, None] ** 0.5, t + 0.2, g=-11, near=0.25, far=0.3, name="soil pouring")


@on("rise_groan")
def h_groan(ctx, t, k):
    r = rng_for("fx", "groan", k)
    nxt = ctx.C.after(t, {"rise_groan", "stands_full_thud"}, t + 4.5)
    d = float(np.clip(nxt - t + 0.6, 3.0, 4.8))
    f0, f1 = (36, 47) if k % 2 == 0 else (44, 33)
    ctx.add(clank(r, r.uniform(700, 950), 0.5, bright=0.7, low=0.3, n_modes=6), t, pan=r.uniform(-0.2, 0.2), g=-13, near=0.3, far=0.3,
            name="load tick", sync=True)
    for j, (dt_, f_a, f_b, pn) in enumerate(((0.35, r.uniform(150, 230), r.uniform(110, 160), -0.55), (d * 0.45, r.uniform(240, 320), r.uniform(170, 230), 0.5))):
        ctx.add(creak(r, min(3.0, d - dt_ + 0.4), f_a, f_b, "metal", amp_pts=[(0, 0), (0.08, 1), (0.5, 0.75), (0.85, 0.9), (1, 0)]), t + dt_,
                pan=pn, g=-12 - 2 * j, far=0.6, near=0.15, name="long creak" if j == 0 else None)
    ctx.add(groan(r, d, f0, f1, bend=0.12 if k % 2 == 0 else -0.08, rough=0.35), t, pan=r.uniform(-0.2, 0.2), g=-3, far=0.55,
            near=0.25, name="metal groan")
    ctx.add(groan(r, d * 0.8, f0 * 2.03, f1 * 1.97, rough=0.5, bright=1.5), t + 0.25, pan=r.uniform(-0.4, 0.4), g=-14, far=0.4,
            name="groan overtone")
    s = servo(r, d * 0.9, [0, 0.4, d * 0.7, d * 0.9], [70, 160 + 30 * k, 210 + 30 * k, 150], gear=7.7,
              env_pts=[(0, 0), (0.3, 0.8), (d * 0.6, 1.0), (d * 0.9, 0)])
    ctx.add(s, t + 0.1, pan=r.uniform(-0.3, 0.3), g=-21, near=0.3, name="servo whine")
    ctx.add(hiss(r, 1.0, [(0, 3800), (0.1, 2600), (1.0, 900)], env_pts=[(0, 0), (0.02, 1), (1.0, 0)]), t + d * 0.55,
            pan=r.uniform(-0.4, 0.4), g=-22, near=0.3, far=0.2, name="hydraulic hiss")
    for j in range(2):
        ctx.add(clank(r, r.uniform(260, 420), 1.0, bright=0.4, low=0.5), t + r.uniform(0.3, d - 0.3), pan=r.uniform(-0.5, 0.5),
                g=-21, near=0.3, far=0.3, name="joint clunk")


@on("roots_tear")
def h_roots(ctx, t, k):
    """Roots tearing: rising fibrous ripping, snaps, a woody creak; vines whip free."""
    r = rng_for("fx", "roots", k)
    d = 1.4
    n = sec(d)
    tn = np.arange(n) / SR
    dens = np.interp(tn, [0, 0.5, 0.75, 1.0, d], [100, 900, 2500, 300, 0])
    rip = texture(r, n, dens, [("bp", 400, 2500, 1.0), ("bp", 2000, 7000, 0.6), ("res", 900, 4, 0.5)], kernel_ms=2.0, spread=0.6, center=-0.2)
    ctx.add(rip / (np.abs(rip).max() + 1e-9), t - 0.5, g=-11, near=0.3, far=0.2, name="roots ripping")
    for j, dt in enumerate((0.0, 0.18, 0.31, 0.55)):
        sn = norm_peak(burst(r, 0.25, 600, 6000, 0.012, 0.0003) + 0.5 * clank(r, r.uniform(500, 900), 0.25, 0.6, 0.2, 5))
        ctx.add(sn, t + dt, pan=r.uniform(-0.6, 0.3), g=-9 - 2 * j, near=0.3, far=0.3, name="root snap" if j == 0 else None, sync=(j == 0))
    ctx.add(creak(r, 0.9, 140, 90, "wood"), t - 0.3, pan=-0.3, g=-15, near=0.2, far=0.3, name="root creak")
    for j in range(3):
        tw = t + 0.35 + j * r.uniform(0.18, 0.3)
        wh = whoosh(r, 0.22, [(0, 3500), (0.22, 700)], 1.2, [(0, 0), (0.15, 1), (0.22, 0.2)], [(0, 0.2), (0.22, 0.2)])
        ctx.add(wh, tw, pan=r.uniform(-0.6, 0.6), g=-18, near=0.2, name="vine whip" if j == 0 else None)
        slap = norm_peak(burst(r, 0.08, 500, 5000, 0.006, 0.0003))
        ctx.add(slap, tw + 0.2, pan=r.uniform(-0.6, 0.6), g=-20, near=0.3)


@on("soil_curtain")
def h_curtain(ctx, t, k):
    r = rng_for("fx", "curtain", k)
    d = 3.2
    n = sec(d)
    tn = np.arange(n) / SR
    dens = np.interp(tn, [0, 0.3, 1.6, d], [0.2, 1.0, 0.7, 0.0])
    rush = np.stack([svf_tv(r.standard_normal(n), 900 + 500 * dens, 0.8, 1) for _ in range(2)], 1) * dens[:, None]
    sand = texture(r, n, 600 + 4000 * dens, [("bp", 2000, 9000, 1.0), ("bp", 800, 3000, 0.5)], kernel_ms=1.2, spread=1.0)
    clods = texture(r, n, 8 + 50 * dens, [("res", 95, 2.5, 1.0), ("res", 150, 3.0, 0.8), ("res", 210, 3.0, 0.6)], kernel_ms=12.0, spread=0.9)
    y = rush / (np.abs(rush).max() + 1e-9) * db(-8) + sand / (np.abs(sand).max() + 1e-9) * db(-3) + clods / (np.abs(clods).max() + 1e-9)
    ctx.add(y * dens[:, None] ** 0.6, t, g=-6, near=0.2, far=0.4, name="soil curtain", sync=True)


@on("stands_full_thud")
def h_stand(ctx, t, k):
    r = rng_for("fx", "stand", k)
    ctx.add(thud(r, 84, 30, 0.1, 0.85, 3.2, click=0.14, rumble=1.0, attack_ms=8), t, g=3, far=0.4, near=0.2, name="stands: weight lands",
            sync=True)
    ctx.add(clank(r, 210, 2.4, bright=0.5, low=0.4), t + 0.05, pan=0.05, g=-7, near=0.25, far=0.4, name="frame clank")
    ctx.add(clank(r, 330, 1.8, bright=0.4, low=0.3), t + 0.32, pan=-0.2, g=-13, near=0.25, far=0.4, name="settle clank")
    ctx.add(groan(r, 1.6, 44, 38, rough=0.25), t + 0.4, g=-11, far=0.4, name="settle groan")
    sh = texture(r, sec(2.0), np.interp(np.arange(sec(2.0)) / SR, [0, 0.1, 2.0], [0, 900, 0]),
                 [("bp", 1500, 7000, 1.0), ("res", 140, 3, 0.8), ("res", 2600, 12, 0.6)], kernel_ms=2.0, spread=1.0)
    ctx.add(sh / (np.abs(sh).max() + 1e-9), t + 0.05, g=-15, near=0.2, far=0.3, name="debris shakes off")


@on("head_lift_creak")
def h_head(ctx, t, k):
    C = ctx.C
    r = rng_for("fx", "head", k)
    d = float(np.clip(C.after(t, {"eyes_resolve"}, t + 1.6) - t + 0.2, 1.0, 2.6))
    ctx.add(clank(r, 520, 0.6, bright=0.6, low=0.4, n_modes=6), t, pan=0.05, g=-17, near=0.3, far=0.3, name="neck unlocks", sync=True)
    ctx.add(creak(r, d + 0.6, 120, 82, "metal", amp_pts=[(0, 0.2), (0.04, 1), (0.6, 0.8), (0.9, 0.9), (1, 0)]), t, pan=0.05, g=-9,
            near=0.3, far=0.35, name="head lift creak")
    ctx.add(creak(r, d * 0.9, 620, 540, "metal"), t + 0.1, pan=-0.1, g=-23, near=0.2, far=0.3, name="neck squeal")
    ctx.add(servo(r, d, [0, 0.3, d - 0.3, d], [80, 190, 210, 120], gear=9.1), t, g=-21, near=0.3, name="neck servo")
    ctx.add(clank(r, 300, 1.2, bright=0.3, low=0.6, n_modes=6), t + d - 0.05, g=-18, near=0.3, far=0.3, name="neck stop")
    du = texture(r, sec(d), 200, [("bp", 2500, 8000, 1.0), ("res", 2800, 10, 0.5)], kernel_ms=1.0, spread=0.5)
    ctx.add(du / (np.abs(du).max() + 1e-9), t + 0.2, g=-34, near=0.2, name="dust falls")


@on("eyes_resolve")
def h_resolve(ctx, t, k):
    r = rng_for("fx", "resolve", k)
    d = 1.4
    n = sec(d)
    tn = np.arange(n) / SR
    y = np.sin(TWO_PI * 293.66 * tn) + 0.6 * np.sin(TWO_PI * 440.0 * tn) + 0.3 * np.sin(TWO_PI * 587.3 * tn)
    y *= np.interp(tn, [0, 0.15, 0.6, d], [0, 1, 0.6, 0])
    ctx.add(y / 1.9, t, g=-31, near=0.2, far=0.3, name="eyes focus", sync=True)
    ping = np.zeros(sec(0.9))
    add_modes(ping, 0, np.array([3520.0, 5274.0]), np.array([1.0, 0.35]), np.array([0.25, 0.12]), np.zeros(2), 20)
    ctx.add(ping, t + 0.05, g=-41, near=0.3, far=0.3, name="lens ping")


@on("back_plates_open")
def h_plates(ctx, t, k):
    r = rng_for("fx", "plates", k)
    for j in range(4):
        tj = t + j * r.uniform(0.12, 0.17)
        ctx.add(clank(r, r.uniform(380, 520), 0.9, bright=0.6, low=0.7, n_modes=7), tj, pan=(-0.3 + 0.2 * j), g=-15 - j,
                near=0.3, far=0.3, name="latch clunk" if j == 0 else None, sync=(j == 0))
    sl = creak(r, 1.1, 900, 760, "metal")
    ctx.add(sl, t + 0.6, pan=0.1, g=-25, near=0.3, far=0.2, name="plates slide")
    ctx.add(hiss(r, 1.3, [(0, 4200), (0.15, 3000), (1.3, 1200)], env_pts=[(0, 0), (0.03, 1), (0.5, 0.6), (1.3, 0)]), t + 0.55,
            g=-22, near=0.3, far=0.2, name="vent hiss", width=1.0)
    rip = texture(r, sec(0.8), np.interp(np.arange(sec(0.8)) / SR, [0, 0.2, 0.8], [800, 1500, 0]),
                  [("bp", 600, 3000, 1.0), ("bp", 2500, 7000, 0.5)], kernel_ms=3.0, spread=0.7)
    ctx.add(rip / (np.abs(rip).max() + 1e-9), t + 0.62, g=-29, near=0.2, name="moss tears")


@on("crouch_anticipation")
def h_crouch(ctx, t, k):
    r = rng_for("fx", "crouch", k)
    ctx.add(groan(r, 1.0, 62, 48, rough=0.4), t, g=-15, near=0.3, far=0.3, name="joints compress", sync=True)
    ctx.add(hiss(r, 0.7, [(0, 1500), (0.7, 600)], q=1.0, env_pts=[(0, 0), (0.05, 1), (0.7, 0)], spit=0.0), t + 0.1, g=-27, near=0.3,
            name="hydraulic squeeze")
    cr = texture(r, sec(0.6), np.interp(np.arange(sec(0.6)) / SR, [0, 0.08, 0.6], [0, 1200, 0]), [("bp", 200, 1500, 1.0), ("res", 130, 3, 0.8)],
                 kernel_ms=5.0, spread=0.6)
    ctx.add(cr / (np.abs(cr).max() + 1e-9), t + 0.25, g=-21, near=0.3, name="feet dig in")


@on("engine_sputter")
def h_sputter(ctx, t, k):
    r = rng_for("fx", "sputter", k)
    tc = t
    for j in range(int(r.integers(4, 6))):
        w = thud(r, r.uniform(110, 160), r.uniform(45, 60), 0.05, 0.12, 0.6, click=0.25, rumble=0.8, attack_ms=2)
        ctx.add(w, tc, pan=r.uniform(-0.15, 0.15), g=-14 - (2.5 if j else 0) + 0.8 * j, near=0.3, far=0.2, name="sputter cough" if j == 0 else None,
                sync=(j == 0))
        fl = norm_peak(burst(r, 0.15, 300, 3000, 0.04, 0.002))
        ctx.add(fl, tc + 0.005, g=-21 - (2.5 if j else 0) + 0.8 * j, near=0.3)
        tc += r.uniform(0.09, 0.17)
    s = servo(r, 0.6, [0, 0.3, 0.6], [200, 600, 300], gear=11.0, env_pts=[(0, 0), (0.25, 1), (0.6, 0)], whine=0.6)
    ctx.add(s, t + 0.05, g=-30, near=0.3, name="failing spool")
    ctx.add(norm_peak(crackle_mono(r, sec(0.7), 140, (2500, 9000), 1.2)), t, g=-31, near=0.3, name="sparks")


@on("engine_ignite")
def h_ignite(ctx, t, k):
    """Ignition WHOOMPH, then the spool-up (turbine whine, roar, rumble, crackle) building to
    the launch."""
    C = ctx.C
    r = rng_for("fx", "ignite", k)
    end = C.after(t, {"launch_smear", "impact_frame"}, t + 3.7)
    sil = launch_silence(C)
    if sil and t < sil[0] < end:
        end = sil[0]                                          # the held breath before the launch
    ctx.add(thud(r, 140, 44, 0.06, 0.35, 1.6, click=0.3, rumble=1.0, attack_ms=4), t, g=-6, far=0.3, near=0.2, name="ignition whoomph",
            sync=True)
    fl = whoosh(r, 0.9, [(0, 400), (0.15, 1800), (0.9, 600)], 0.8, [(0, 0), (0.04, 1), (0.9, 0)], [(0, 0.1), (0.9, 0.5)])
    ctx.add(fl, t, g=-14, near=0.2, far=0.2, name="flame bloom")
    d = end - t
    n = sec(d)
    tn = np.arange(n) / SR
    x = tn / d
    lvl = np.clip(x, 0, 1) ** 1.6 * np.minimum(1, (d - tn) / 0.04)
    whine_f = 420 + 2300 * x ** 1.5
    wn = np.sin(TWO_PI * np.cumsum(whine_f) / SR) + 0.35 * np.sin(TWO_PI * np.cumsum(whine_f * 2.02) / SR)
    wn *= (0.3 + 0.7 * x) * (1 + 0.04 * slow_noise(r, n, 9.0))
    roar = np.zeros((n, 2))
    for ch in range(2):
        roar[:, ch] = svf_tv(r.standard_normal(n), 180 + 2600 * x ** 1.3, 0.9, 0)
    roar /= np.abs(roar).max() + 1e-9
    rum = lp(r.standard_normal(n), 70, 2)
    rum = rum / (np.abs(rum).max() + 1e-9)
    crk = crackle_mono(r, n, 30 + 250 * x, (1500, 8000), 0.8)
    crk /= np.abs(crk).max() + 1e-9
    y = roar * 0.9 + (0.35 * wn / 1.35 + 0.6 * rum + 0.25 * crk)[:, None]
    ctx.add(y * lvl[:, None], t, g=-6, near=0.15, far=0.25, name="engine spool-up")


@on("wind_ring")
def h_wind_ring(ctx, t, k):
    """A great ring of wind: a pressure thump, then a whoosh that starts centred and spreads
    wide, with leaves, twigs and grass rattling, trees bending."""
    r = rng_for("fx", "ring", k)
    ctx.add(thud(r, 68, 36, 0.1, 0.45, 2.0, click=0.0, rumble=0.9, attack_ms=25), t, g=-8, far=0.3, name="pressure wave", sync=True)
    sil = launch_silence(ctx.C)
    d = float(np.clip((sil[0] - t) if (sil and sil[0] > t) else 3.4, 1.2, 3.4))
    w = whoosh(r, d, [(0, 220), (0.18 * d, 1500), (0.47 * d, 900), (d, 350)], 0.75, [(0, 0), (0.13 * d, 1), (0.41 * d, 0.75), (d, 0)],
               [(0, 0.0), (0.2 * d, 0.7), (d, 1.0)], rattle=0.9)
    ctx.add(w, t, g=-6, far=0.3, name="wind ring whoosh")
    deb = texture(r, sec(d), np.interp(np.arange(sec(d)) / SR, [0, 0.12 * d, 0.45 * d, d], [0, 2500, 900, 50]),
                  [("bp", 1800, 8000, 1.0), ("res", 2300, 10, 0.5), ("bp", 400, 1500, 0.5)], kernel_ms=2.5, spread=1.0)
    ctx.add(deb / (np.abs(deb).max() + 1e-9), t + 0.15, g=-16, far=0.4, name="debris and leaves")
    for j in range(3):
        ctx.add(dist(creak(r, min(1.4, 0.45 * d), r.uniform(40, 70), r.uniform(30, 45), "wood"), 2.5), t + (0.15 + 0.17 * j) * d, pan=r.uniform(-0.9, 0.9),
                g=-12, far=0.7, name="trees bend" if j == 0 else None)


@on("launch_smear")
def h_smear(ctx, t, k):
    C = ctx.C
    r = rng_for("fx", "smear", k)
    imp = C.after(t - 1e-6, {"impact_frame"}, t + 0.2)
    d = max(0.15, imp - t + 0.25)
    d = max(0.08, imp - t)                                     # out of the silence, into the impact
    w = whoosh(r, d, [(0, 900), (d, 5000)], 1.1, [(0, 0), (d - 0.008, 1), (d, 0)], [(0, 0.3), (d, 0.7)])
    ctx.add(w, t, g=-13, near=0.2, name="launch suck", sync=True)


def doppler_roar(rng, dur, lift_accel=44.0, vmax=230.0, d0=18.0, c=343.0):
    """The roar of the climbing robot heard from the ground: a turbulent source rendered in
    source time, then received through a time-varying delay r(t)/c (Doppler), 1/r and air
    absorption.  Returns (stereo, distance curve)."""
    n = sec(dur)
    ts = np.arange(n) / SR
    src_n = n + sec(3.0)
    tsrc = np.arange(src_n) / SR
    base = np.zeros((src_n, 2))
    turb = 1 + 0.3 * np.clip(slow_noise(rng, src_n, 16.0), -2, 2)
    tone_f = 72.0 * (1 + 0.02 * slow_noise(rng, src_n, 2.0))
    tone = lp(saw_blep(tone_f, 0.0), 900, 2) + 0.5 * np.sin(TWO_PI * np.cumsum(tone_f * 0.5) / SR)
    whine = np.sin(TWO_PI * np.cumsum(2700 * (1 + 0.01 * slow_noise(rng, src_n, 3.0))) / SR)
    for ch in range(2):
        nz = rng.standard_normal(src_n)
        res = svf_tv(nz, np.full(src_n, 1300.0), 1.8, 1)
        broad = lp(rng.standard_normal(src_n), 700, 2)
        base[:, ch] = (0.55 * norm_rms(res) + 0.6 * norm_rms(broad) + 0.35 * norm_rms(tone) + 0.05 * whine) * turb
    # trajectory: accelerate straight up, capped speed
    t_cap = vmax / lift_accel
    h = np.where(tsrc < t_cap, 0.5 * lift_accel * tsrc ** 2, 0.5 * lift_accel * t_cap ** 2 + vmax * (tsrc - t_cap))
    r_src = np.sqrt(d0 ** 2 + h ** 2)
    # received at ts: emitted te with te + r(te)/c = ts  (fixed point)
    te = ts - d0 / c
    for _ in range(8):
        te = ts - np.interp(te, tsrc, r_src) / c
    te = np.clip(te, 0, tsrc[-1])
    r_rec = np.interp(te, tsrc, r_src)
    out = np.zeros((n, 2))
    for ch in range(2):
        out[:, ch] = np.interp(te, tsrc, base[:, ch])
    out *= (d0 / r_rec)[:, None]
    fc = np.clip(16000.0 * (d0 / r_rec) ** 0.75, 250.0, 16000.0)
    for ch in range(2):
        out[:, ch] = svf_tv(out[:, ch], fc, 0.6, 0)
    return out, r_rec


@on("impact_frame")
def h_launch(ctx, t, k):
    """LAUNCH: sonic thump, blast body, crack, then the roar receding upward (Doppler),
    a debris shower."""
    C = ctx.C
    r = rng_for("fx", "launch", k)
    ctx.add(thud(r, 76, 36, 0.12, 0.5, 3.0, click=0.0, rumble=1.2, attack_ms=2.5), t, g=-3.0, far=0.25, name="LAUNCH sonic thump")
    n = sec(3.0)
    tn = np.arange(n) / SR
    body = np.stack([norm_rms(bp(r.standard_normal(n), 60, 700, 2)) for _ in range(2)], 1) * np.exp(-tn / 0.45)[:, None]
    roarb = np.stack([norm_rms(bp(r.standard_normal(n), 300, 3500, 2)) for _ in range(2)], 1) * np.exp(-tn / 0.6)[:, None]
    crack = np.stack([norm_rms(bp(r.standard_normal(n), 1800, 9000, 2)) for _ in range(2)], 1) * np.exp(-tn / 0.025)[:, None]
    blast = 0.8 * body + 0.55 * roarb + 0.55 * crack
    blast[: sec(0.002)] *= cos_ramp(sec(0.002))[:, None]
    ctx.add(blast / np.abs(blast).max(), t, g=-1, far=0.45, near=0.3, name="LAUNCH blast", sync=True)
    end = C.after(t, {"trail_fades"}, t + 10.5) + 2.0
    roar, rr = doppler_roar(r, end - t)
    nr = len(roar)
    trn = np.arange(nr) / SR
    ramp = np.interp(trn, [0, 0.06, 0.5, end - t - 1.0, end - t], [0, 0.8, 1, 1, 0])
    ctx.add(roar * ramp[:, None] / (np.abs(roar).max() + 1e-9), t, g=-3, far=0.35, sky=0.25, name="roar recedes (Doppler)")
    deb = texture(r, sec(4.0), np.interp(np.arange(sec(4.0)) / SR, [0, 0.4, 1.2, 4.0], [0, 1600, 600, 20]),
                  [("bp", 1800, 8000, 1.0), ("res", 120, 3, 0.9), ("res", 2400, 12, 0.6), ("bp", 400, 1600, 0.6)], kernel_ms=2.5, spread=1.0)
    ctx.add(deb / (np.abs(deb).max() + 1e-9), t + 0.25, g=-18, near=0.2, far=0.35, name="debris shower")


@on("canopy_burst")
def h_canopy(ctx, t, k):
    r = rng_for("fx", "canopy", k)
    for j in range(6):
        sn = norm_peak(burst(r, 0.3, 500, 7000, 0.015, 0.0003) + 0.6 * clank(r, r.uniform(350, 800), 0.3, 0.5, 0.3, 5))
        ctx.add(dist(sn, r.uniform(2.0, 3.5)), t + (0.0 if j == 0 else r.uniform(0.05, 0.5)), pan=r.uniform(-0.8, 0.8),
                g=(-4 if j == 0 else -6 + r.uniform(-4, 0)), far=0.6, name="branches snap" if j == 0 else None, sync=(j == 0))
    lv = texture(r, sec(2.5), np.interp(np.arange(sec(2.5)) / SR, [0, 0.12, 0.8, 2.5], [0, 4000, 1500, 0]),
                 [("bp", 1800, 8000, 1.0), ("bp", 700, 2500, 0.5)], kernel_ms=2.5, spread=1.0)
    ctx.add(lv / (np.abs(lv).max() + 1e-9), t, g=-17, far=0.5, name="leaves explode")
    w = whoosh(r, 1.2, [(0, 500), (0.3, 2500), (1.2, 600)], 0.8, [(0, 0), (0.2, 1), (1.2, 0)], [(0, 0.3), (1.2, 1.0)])
    ctx.add(w, t, g=-15, far=0.4, name="passing through")


@on("sky_reveal")
def h_sky(ctx, t, k):
    """The trail of light and mist: airy, slowly sweeping noise with faint E-major partials."""
    C = ctx.C
    r = rng_for("fx", "trail", k)
    tf = C.after(t, {"trail_fades"}, t + 6.5)
    d = tf - t + 2.0
    n = sec(d)
    tn = np.arange(n) / SR
    e = np.interp(tn, [0, 0.8, tf - t - 0.4, tf - t + 1.6, d], [0, 1, 0.8, 0, 0])
    air = np.zeros((n, 2))
    for ch in range(2):
        air[:, ch] = svf_tv(r.standard_normal(n), 3500 * (1 + 0.5 * slow_noise(r, n, 0.3)), 0.9, 1)
    air /= np.abs(air).max() + 1e-9
    parts = np.zeros((n, 2))
    for f in (1318.5, 1661.2, 1975.5, 2637.0, 3951.1):
        for ch in range(2):
            fl = 0.6 + 0.4 * np.sin(TWO_PI * r.uniform(0.15, 0.5) * tn + r.uniform(0, TWO_PI))
            parts[:, ch] += np.sin(TWO_PI * f * (1 + 0.002 * (ch - 0.5)) * tn + r.uniform(0, TWO_PI)) * fl / (f / 1318.5)
    parts /= np.abs(parts).max() + 1e-9
    ctx.add((air * 0.8 + parts * 0.25) * e[:, None], t, g=-20, sky=0.6, name="trail shimmer")


@on("trail_fades")
def h_trail_fades(ctx, t, k):
    r = rng_for("fx", "trailfade", k)
    w = whoosh(r, 2.5, [(0, 2500), (2.5, 900)], 0.8, [(0, 0), (0.6, 1), (2.5, 0)], [(0, 0.8), (2.5, 1.0)])
    ctx.add(w, t - 0.3, g=-30, sky=0.5, name="trail dissolves")


@on("bird_returns")
def h_return(ctx, t, k):
    r = rng_for("fx", "return", k)
    d = 1.1
    w = wings(r, d, 15.0, "small", bound=True, strength=lambda tt_: 0.6 + 0.4 * min(1.0, tt_ / 0.6))
    x = np.linspace(0, 1, len(w))
    ctx.add(w, t - d, pan=np.interp(x, [0, 1], [-0.7, 0.05]), g=-25, near=0.2, far=0.3, name="bird flies in")
    tick = burst(r, 0.02, 2500, 9000, 0.0025, 0.0002) + 0.4 * burst(r, 0.02, 600, 2000, 0.004)
    ctx.add(norm_peak(tick), t, pan=0.05, g=-22, near=0.3, name="bird lands on moss", sync=True)
    mo = texture(r, sec(0.3), 120, [("bp", 1500, 6000, 1.0)], kernel_ms=3.0, spread=0.1, center=0.05)
    mo *= np.exp(-np.arange(len(mo)) / sec(0.08))[:, None]
    ctx.add(mo / (np.abs(mo).max() + 1e-9), t + 0.01, g=-30, near=0.3, name="moss scuffle")
    ctx.add(little_bird_call(r, "twitter"), t + 0.45, pan=0.05, g=-24, near=0.2, far=0.15, name="happy chirp")


# ============================================================================ render
def render_fx(cues, irs, warn_unknown=True):
    ctx = Ctx(cues)
    ambience(ctx)
    counts = {}
    for t, name in cues.events:
        b = base_name(name)
        if b in SILENT:
            continue
        fn = HANDLERS.get(b) or HANDLERS.get(name)
        if fn is None:
            if warn_unknown:
                warn("unknown event '%s' at %.2f s ignored" % (name, t))
            continue
        k = counts.get(b, 0)
        counts[b] = k + 1
        ctx.fx.cue = ctx.amb.cue = t
        fn(ctx, t, k)
        ctx.fx.cue = ctx.amb.cue = None
    fx = ctx.fx.render(irs)
    amb = ctx.amb.render(irs)
    return fx, amb, ctx.fx.log + ctx.amb.log, ctx.onsets
