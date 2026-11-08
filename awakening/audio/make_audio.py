#!/usr/bin/env python3
"""
make_audio.py -- fully synthesized soundtrack for "Awakening"
(a giant ancient robot wakes in a misty forest at sunrise).

Output: mix.wav next to this file -- 56.0 s, 48 kHz, 16-bit stereo, about -18 LUFS
integrated, true peak below -1 dBTP, with real dynamics (quiet dawn -> tremor ->
rise -> launch -> fade).

Everything is generated from seeded noise and oscillators: no samples, no speech,
no borrowed music.  One numpy Generator (SEED) drives all randomness, so the file
is bit-identical between runs on the same numpy/scipy versions.

Run:  python3 make_audio.py              (writes mix.wav, prints level tables,
                                          verifies with ffmpeg's ebur128 if present)
      python3 make_audio.py --no-ffmpeg  (skip the ffmpeg verification pass)

Structure: one function per cue (see the cue sheet in README.md), each writing into
a stereo Bus with simple constant-power panning and two reverb sends (a long dark
"far" reverb for the forest, a short "near" one for the robot and the little bird).
The reverbs are convolutions with synthetic impulse responses (band-split
exponentially decaying noise plus a few early reflections).  The master chain is a
gentle RMS compressor, a gain calibration to the LUFS target, and a look-ahead
peak limiter.
"""
import os
import sys
import time
import subprocess

import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d

SR = 48000
DUR = 56.0
SEED = 20261108
TARGET_LUFS = -18.0
TP_LIMIT_DBTP = -1.0          # hard requirement
LIMITER_CEILING_DB = -1.5     # sample-peak ceiling, leaves margin for inter-sample peaks
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_WAV = os.path.join(HERE, "mix.wav")

rng = np.random.default_rng(SEED)
TWO_PI = 2.0 * np.pi
N = int(round(DUR * SR))
T = np.arange(N) / SR


# ============================================================================ helpers
def sec(t):
    return int(round(t * SR))


def tt(dur):
    return np.arange(sec(dur)) / SR


def db(x):
    return 10.0 ** (x / 20.0)


def to_db(x):
    return 20.0 * np.log10(max(float(x), 1e-12))


def norm_peak(x):
    return x / (np.abs(x).max() + 1e-12)


def norm_rms(x):
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def smooth(x, ms):
    """Zero-phase Hann smoothing (ms wide)."""
    n = sec(ms / 1000.0)
    if n < 3:
        return x
    w = np.hanning(n)
    w /= w.sum()
    return signal.fftconvolve(x, w, mode="same")


def envelope(dur, pts, smooth_ms=4.0):
    """Piecewise-linear envelope from (time, value) pairs, lightly smoothed."""
    t = tt(dur)
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    e = np.interp(t, ts, vs)
    return np.clip(smooth(e, smooth_ms), 0.0, None) if smooth_ms else e


def raised_cos(dur, attack, release=None):
    """Flat window with raised-cosine attack/release (seconds)."""
    n = sec(dur)
    e = np.ones(n)
    a = min(sec(attack), n)
    r = min(sec(attack if release is None else release), n)
    if a > 0:
        e[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    if r > 0:
        e[n - r:] *= 0.5 + 0.5 * np.cos(np.pi * np.arange(r) / r)
    return e


def exp_decay(dur, tau, attack=0.002):
    t = tt(dur)
    e = np.exp(-t / tau)
    a = sec(attack)
    if a > 0:
        e[:a] *= np.linspace(0.0, 1.0, a)
    return e


def slow_noise(dur, hz, order=2):
    """Band-limited random control signal (unit variance) for sub-Hz modulation."""
    n = sec(dur)
    k = max(4, int(dur * hz) + 3)
    pts = rng.standard_normal(k)
    y = np.interp(np.arange(n) / n * (k - 1), np.arange(k), pts)
    return norm_rms(smooth(y, 400.0 / hz) if n > 100 else y)


# ----------------------------------------------------------------------------- filters
def _butter(x, kind, f, order=4, zero_phase=False):
    nyq = 0.5 * SR
    if np.isscalar(f):
        f = float(min(f, 0.95 * nyq))
    else:
        f = (max(float(f[0]), 1.0), min(float(f[1]), 0.95 * nyq))
    sos = signal.butter(order, f, btype=kind, fs=SR, output="sos")
    return signal.sosfiltfilt(sos, x, axis=0) if zero_phase else signal.sosfilt(sos, x, axis=0)


def lp(x, f, order=4, zp=False):
    return _butter(x, "lowpass", f, order, zp)


def hp(x, f, order=4, zp=False):
    return _butter(x, "highpass", f, order, zp)


def bp(x, lo, hi, order=4, zp=False):
    return _butter(x, "bandpass", (lo, hi), order, zp)


def peak_coef(fc, q):
    """Second-order band-pass (peaking) biquad, unity gain at fc."""
    fc = float(np.clip(fc, 15.0, 0.45 * SR))
    return signal.iirpeak(fc, q, fs=SR)


def rlp_coef(fc, q):
    """RBJ resonant low-pass biquad."""
    fc = float(np.clip(fc, 15.0, 0.45 * SR))
    w0 = TWO_PI * fc / SR
    alpha = np.sin(w0) / (2.0 * q)
    c = np.cos(w0)
    b = np.array([(1 - c) / 2, 1 - c, (1 - c) / 2])
    a = np.array([1 + alpha, -2 * c, 1 - alpha])
    return b / a[0], a / a[0]


def tv_biquad(x, coef_fn, param, q, block=256):
    """Time-varying biquad: coefficients redesigned every `block` samples, state carried."""
    n = len(x)
    y = np.empty(n)
    zi = np.zeros(2)
    param = np.asarray(param, float)
    for s in range(0, n, block):
        e = min(n, s + block)
        b, a = coef_fn(param[(s + e) // 2], q)
        y[s:e], zi = signal.lfilter(b, a, x[s:e], zi=zi)
    return y


# ----------------------------------------------------------------------------- sources
def white(n):
    return rng.standard_normal(n)


def pink(n):
    # Paul Kellet's economy pink filter (flat 1/f within ~0.5 dB over the audio band)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1.0, -2.494956002, 2.017265875, -0.522189400]
    return norm_rms(signal.lfilter(b, a, white(n)))


def phase(f):
    """Phase (rad) from an instantaneous-frequency array (Hz)."""
    return TWO_PI * np.cumsum(f) / SR


def bl_saw(f, nharm=40, rolloff=1.0):
    """Band-limited sawtooth by additive synthesis; f is an array of Hz."""
    ph = phase(f)
    K = int(max(1, min(nharm, 0.45 * SR / np.max(f))))
    y = np.zeros_like(ph)
    for k in range(1, K + 1):
        y += np.sin(k * ph) / k ** rolloff
    return y * (2.0 / np.pi)


# ----------------------------------------------------------------------------- bus
class Bus:
    def __init__(self, dur):
        self.n = sec(dur)
        self.dry = np.zeros((self.n, 2))
        self.far = np.zeros((self.n, 2))    # long, dark forest reverb send
        self.near = np.zeros((self.n, 2))   # short, close reverb send
        self.events = []

    def add(self, x, t0, pan=0.0, gain=1.0, far=0.0, near=0.0, name=None):
        """x: mono (n,) with pan in [-1,1] (scalar or array), or stereo (n,2)."""
        x = np.asarray(x, float)
        if x.ndim == 1:
            p = np.clip(np.asarray(pan, float), -1.0, 1.0)
            ang = (p + 1.0) * np.pi / 4.0
            st = np.stack([x * np.cos(ang), x * np.sin(ang)], axis=1)
        else:
            st = x
        st = st * gain
        s = sec(t0)
        if s < 0:
            st = st[-s:]
            s = 0
        e = min(self.n, s + len(st))
        if e <= s:
            return
        seg = st[: e - s]
        self.dry[s:e] += seg
        if far:
            self.far[s:e] += far * seg
        if near:
            self.near[s:e] += near * seg
        if name:
            self.events.append((t0, name))

    def render(self, ir_far, ir_near):
        out = self.dry.copy()
        for send, ir in ((self.far, ir_far), (self.near, ir_near)):
            for ch in range(2):
                out[:, ch] += signal.fftconvolve(send[:, ch], ir[:, ch])[: self.n]
        return out


def make_ir(rt60, predelay, bands):
    """Synthetic stereo impulse response: band-split decaying noise + early reflections.
    bands: (lo, hi, decay multiplier) -- highs die faster.  Normalised to unit energy."""
    span = rt60 * 1.15
    n = sec(span)
    t = tt(span)
    ir = np.zeros((n + sec(predelay), 2))
    for ch in range(2):
        nz = white(n)
        tail = np.zeros(n)
        for lo, hi, mult in bands:
            tail += bp(nz, lo, hi, 2) * np.exp(-6.908 * t / (rt60 * mult))
        tail *= np.minimum(1.0, t / 0.012)          # diffusion builds up over 12 ms
        er = np.zeros(n)
        for k in range(7):                           # sparse early reflections
            er[sec(rng.uniform(0.008, 0.07))] += rng.uniform(0.3, 0.8) * (-1) ** k
        tail += 0.35 * lp(er, 4000, 2)
        ir[sec(predelay):, ch] = tail
    ir /= np.sqrt((ir ** 2).sum(axis=0)).max()
    return ir


# ============================================================================ cues
# ---------------------------------------------------------------- ambience bed (0-56)
def cue_ambience(bus):
    """Dawn forest bed: wind through leaves (time-varying band-passed noise driven by a
    gust envelope), a granular leaf texture, and a faint insect shimmer."""
    n, t = N, T
    # gusts every 6-10 s: asymmetric bumps (slow rise, slower fall)
    gust = np.zeros(n)
    gust_times = []
    tg = 1.2
    while tg < DUR:
        gust_times.append(tg)
        amp = rng.uniform(0.5, 1.0)
        rise, fall = rng.uniform(1.2, 2.2), rng.uniform(2.5, 4.5)
        i0, i1, i2 = sec(tg), min(n, sec(tg + rise)), min(n, sec(tg + rise + fall))
        if i1 > i0:
            gust[i0:i1] += amp * (0.5 - 0.5 * np.cos(np.pi * np.arange(i1 - i0) / (i1 - i0)))
        if i2 > i1:
            gust[i1:i2] += amp * (0.5 + 0.5 * np.cos(np.pi * np.arange(i2 - i1) / (i2 - i1)))
        tg += rng.uniform(6.0, 10.0)
    print("gusts at: " + ", ".join("%.1f" % g for g in gust_times))
    # natural gusts are held back while the robot acts (so the events read), replaced by the
    # scripted wind over 44.6-49.5, and gentle at the end
    gust *= envelope(DUR, [(0, 1), (23.5, 1), (28, 0.6), (44.0, 0.6), (44.6, 0), (49.5, 0), (50.5, 0.3), (56, 0.3)], 300)
    base = 0.32 + 0.10 * np.sin(TWO_PI * 0.045 * t + 1.0) + 0.06 * np.sin(TWO_PI * 0.11 * t + 2.0)
    # scripted: wind picks up from 44.6, settles after the launch
    script = envelope(DUR, [(0, 0), (44.6, 0), (45.8, 0.9), (47.3, 1.5), (48.6, 0.8),
                            (50.5, 0.35), (53.0, 0.05), (56, 0.05)], 300)
    wind = np.clip(base + gust + script, 0.02, None)
    # the forest "thins" 43-45 and comes back by 54 (applies to leaves/insects, not the wind)
    thin = envelope(DUR, [(0, 1), (43, 1), (45, 0.4), (49.5, 0.4), (54, 1), (56, 1)], 300)

    # level laws (dB) against wind strength: baseline wind ~0.4, gusts ~1.4, launch capped at 1.3
    w = np.clip(wind, 0.0, 1.3)
    body_g = db(-43.5 + 4.5 * w)      # about -42 dB RMS at rest .. -37 in a gust (before master gain)
    hiss_g = db(-56.0 + 13.0 * w)     # leaf hiss, mostly in gusts
    leaf_g = db(-44.0 + 8.0 * w) * thin
    out = np.zeros((n, 2))
    shared = pink(n)
    for ch in range(2):
        src = 0.65 * pink(n) + 0.35 * shared
        fc = 140.0 * (1 + 2.4 * wind) * (1 + 0.05 * (ch - 0.5))
        body = norm_rms(tv_biquad(src, peak_coef, fc, 0.7, block=512)) * body_g
        hiss = norm_rms(tv_biquad(white(n), peak_coef, 700.0 * (1 + 2.5 * wind), 1.4, block=512)) * hiss_g
        leaf = norm_rms(bp(white(n), 2500, 7500, 2))
        mod = np.clip(norm_rms(lp(white(n), 14, 2)), 0, 2.0) ** 1.4 / 1.5   # fluttery leaf gating
        leaf *= mod * leaf_g
        out[:, ch] = body + hiss + leaf
    bus.add(out, 0.0, far=0.12, name="wind bed")

    # insect shimmer: two faint high bands with irregular ~9-11 Hz amplitude modulation
    for pan, rate0, level in ((0.35, 9.0, -50), (-0.5, 11.0, -53)):
        ins = norm_rms(bp(white(n), 6500, 9500, 2))
        rate = rate0 + 0.8 * np.sin(TWO_PI * 0.07 * t + pan)
        am = (0.5 + 0.5 * np.sin(phase(rate))) ** 2
        slow = 0.6 + 0.4 * np.clip(slow_noise(DUR, 0.15), -1, 1)
        bus.add(ins * am * slow * thin * db(level), 0.0, pan=pan, far=0.3, name="insects")
    return wind, thin


# ---------------------------------------------------------------- birds
SPECIES = [  # distant species: f range, notes per phrase, note dur, gap, sweep, vibrato (Hz, depth), 2nd harmonic
    dict(f=(2200, 3300), notes=(2, 3), dur=(0.16, 0.26), gap=(0.10, 0.18), sweep="up", vib=(25, 0.012), h2=0.10),
    dict(f=(3300, 4600), notes=(5, 9), dur=(0.04, 0.06), gap=(0.02, 0.035), sweep="down", vib=(0, 0), h2=0.15),
    dict(f=(2600, 4200), notes=(3, 5), dur=(0.08, 0.14), gap=(0.05, 0.09), sweep="updown", vib=(40, 0.03), h2=0.12),
    dict(f=(650, 900), notes=(2, 3), dur=(0.22, 0.35), gap=(0.12, 0.22), sweep="downs", vib=(6, 0.008), h2=0.05),
    dict(f=(1800, 2600), notes=(1, 2), dur=(0.30, 0.50), gap=(0.15, 0.25), sweep="flat", vib=(5.5, 0.02), h2=0.08),
]
LITTLE = dict(f=(3300, 5600), notes=(2, 3), dur=(0.06, 0.11), gap=(0.04, 0.08), sweep="up", vib=(60, 0.02), h2=0.25)
SWEEP_RATIO = {"up": (1.25, 1.5), "down": (0.7, 0.85), "updown": (1.2, 1.4), "flat": (1.0, 1.0), "downs": (0.88, 0.95)}


def bird_note(fa, fb, dur, sweep, vib, h2):
    t = tt(dur)
    x = t / dur
    if sweep == "updown":
        f = fa + (fb - fa) * np.sin(np.pi * x)
    elif sweep == "up":
        f = fa + (fb - fa) * np.sqrt(x)
    else:
        f = fa + (fb - fa) * x
    if vib[0] > 0:
        f = f * (1 + vib[1] * np.sin(TWO_PI * vib[0] * t + rng.uniform(0, TWO_PI)))
    ph = phase(f)
    return (np.sin(ph) + h2 * np.sin(2 * ph)) * raised_cos(dur, 0.3 * dur, 0.4 * dur)


def bird_phrase(sp):
    cnt = int(rng.integers(sp["notes"][0], sp["notes"][1] + 1))
    key = rng.uniform(*sp["f"])
    parts = []
    for _ in range(cnt):
        fa = key * rng.uniform(0.94, 1.06)
        r = rng.uniform(*SWEEP_RATIO[sp["sweep"]])
        parts.append(bird_note(fa, fa * r, rng.uniform(*sp["dur"]), sp["sweep"], sp["vib"], sp["h2"]))
        parts.append(np.zeros(sec(rng.uniform(*sp["gap"]))))
    return norm_peak(np.concatenate(parts))


def cue_distant_birds(bus):
    """Sparse far phrases: 1 every 2-4 s before the tremor, a few hesitant ones after the
    robot stands, returning after the launch (from 53.5)."""
    windows = [(0.6, 24.3, (2.0, 4.0), 0.0), (38.5, 42.6, (4.0, 6.0), -5.0), (53.5, 55.4, (1.0, 1.8), -2.0)]
    for a, b, gap, extra in windows:
        t = a + rng.uniform(0, 0.4)
        while t < b:
            sp = SPECIES[int(rng.integers(len(SPECIES)))]
            ph = lp(bird_phrase(sp), 5500, 2)            # distance dulls the top
            d = rng.uniform(0.4, 1.0)                     # 0 near .. 1 far
            g = db(-33 + extra - 7 * d + rng.uniform(-2, 2))
            bus.add(ph, t, pan=rng.uniform(-0.9, 0.9), gain=g, far=0.9 + 1.1 * d, name="distant bird")
            t += rng.uniform(*gap)


def flutter(dur, rate, band=(900, 4500), body=0.3, jitter=0.08):
    """Wing flutter: short noise puffs at `rate` Hz, alternating down/up-stroke weight."""
    n = sec(dur)
    y = np.zeros(n)
    plen = 0.05
    t, k = 0.0, 0
    while t < dur - plen:
        i0, m = sec(t), sec(plen)
        puff = bp(white(m), band[0], band[1], 2) * exp_decay(plen, 0.011, 0.003)
        if body > 0:
            puff += body * bp(white(m), 150, 600, 2) * exp_decay(plen, 0.02, 0.004)
        amp = (1.0 if k % 2 == 0 else 0.55) * rng.uniform(0.8, 1.2)
        y[i0:i0 + m] += puff * amp
        t += rng.uniform(1 - jitter, 1 + jitter) / rate
        k += 1
    return norm_peak(y)


def scuffle(dur=0.25):
    n = sec(dur)
    y = np.zeros(n)
    for _ in range(int(rng.integers(4, 7))):
        i0 = sec(rng.uniform(0, dur - 0.03))
        m = sec(rng.uniform(0.004, 0.014))
        y[i0:i0 + m] += hp(white(m), 3000, 2) * np.exp(-np.arange(m) / (m / 2.5)) * rng.uniform(0.4, 1.0)
    y += 0.5 * norm_rms(lp(white(n), 350, 2)) * exp_decay(dur, 0.03, 0.002)
    return norm_peak(y)


def cue_little_bird(bus):
    # flies in 8.3-10.3, lands at 10.3
    d = 2.0
    fl = flutter(d, 9.5, (1000, 5000), body=0.25)
    fl *= envelope(d, [(0, 0.1), (0.7, 0.55), (1.4, 1.0), (1.8, 0.6), (2.0, 0.0)], 30)
    pan = np.interp(tt(d), [0, d], [0.55, -0.15])
    bus.add(fl, 8.3, pan=pan, gain=db(-27), near=0.35, far=0.15, name="little bird flies in")
    bus.add(scuffle(), 10.3, pan=-0.15, gain=db(-30), near=0.3, name="lands")
    # close chirps: brighter and drier than the distant ones
    for tc in (10.6, 12.2, 15.0, 18.5, 22.0):
        ph = bird_phrase(LITTLE)
        bus.add(ph, tc, pan=-0.15 + rng.uniform(-0.05, 0.05), gain=db(-24 + rng.uniform(-2, 1)),
                near=0.25, far=0.08, name="little bird chirp")
    # flies off at 25.7, left -> right, dulling as it goes
    d = 1.6
    fl = flutter(d, 10.0, (1000, 5000), body=0.25)
    fl *= envelope(d, [(0, 0.9), (0.3, 1.0), (0.9, 0.6), (1.6, 0.0)], 30)
    x = np.linspace(0, 1, sec(d)) ** 1.5
    fl = fl * (1 - x) + lp(fl, 1500, 2) * x
    pan = np.interp(tt(d), [0, d], [-0.15, 0.85])
    bus.add(fl, 25.7, pan=pan, gain=db(-27), near=0.2, far=0.3, name="little bird flies off")


# ---------------------------------------------------------------- sun shimmer (13-18)
def cue_sun(bus):
    """Barely audible high pad: E-major partials (E6 G#6 B6 E7 B7), chorused, slowly
    flickering, swelling over 13-18 s."""
    dur = 5.6
    t = tt(dur)
    n = len(t)
    freqs = [1318.5, 1661.2, 1975.5, 2637.0, 3951.1]
    out = np.zeros((n, 2))
    for i, f in enumerate(freqs):
        for ch in range(2):
            for dt in (-0.0035, 0.0, 0.0035):
                lfo = 1 + 0.0012 * np.sin(TWO_PI * rng.uniform(0.1, 0.35) * t + rng.uniform(0, TWO_PI))
                flick = 0.65 + 0.35 * np.sin(TWO_PI * rng.uniform(0.15, 0.6) * t + rng.uniform(0, TWO_PI))
                out[:, ch] += np.sin(phase(f * (1 + dt) * lfo)) * flick / (1.0 + 0.6 * i)
    out *= raised_cos(dur, 2.8, 2.6)[:, None]
    bus.add(norm_peak(out), 12.8, gain=db(-36), far=0.7, name="sun shimmer")


# ---------------------------------------------------------------- hum / lamp / eyes
def hum_tone(dur, f0, harm=((1, 1.0), (2, 0.5), (3, 0.35), (4, 0.15), (5, 0.12), (6, 0.06)), wander=0.002, buzz=0.0):
    t = tt(dur)
    f = f0 * (1 + wander * np.sin(TWO_PI * 0.3 * t))
    ph = phase(f)
    y = np.zeros(len(t))
    for k, a in harm:
        y += a * np.sin(k * ph + rng.uniform(0, TWO_PI))
    if buzz > 0:                                   # electrical edge
        y += buzz * norm_peak(bp(bl_saw(f, 60, 1.0), 400, 2500, 2))
    return norm_peak(y)


def warm_tone(dur, freqs, chorus=0.003):
    """Soft triangle-ish partials with three chorused voices per note."""
    t = tt(dur)
    y = np.zeros(len(t))
    for f in freqs:
        for dt in (-chorus, 0.0, chorus):
            lfo = 1 + 0.0015 * np.sin(TWO_PI * rng.uniform(0.08, 0.25) * t + rng.uniform(0, TWO_PI))
            ph = phase(f * (1 + dt) * lfo)
            y += np.sin(ph) + np.sin(2 * ph) / 4 + np.sin(3 * ph) / 9
    return norm_peak(y)


def crackle(dur=0.08):
    n = sec(dur)
    y = np.zeros(n)
    for _ in range(int(rng.integers(3, 8))):
        i0 = sec(rng.uniform(0, dur - 0.004))
        m = sec(rng.uniform(0.0008, 0.003))
        y[i0:i0 + m] += white(m) * np.exp(-np.arange(m) / (m / 2.5)) * rng.uniform(0.3, 1.0)
    return norm_peak(hp(y, 2500, 2))


def cue_lamp(bus):
    """Chest lamp flickering on: 55 Hz hum with harmonics gated at the flicker times,
    a crackle at each flicker; from 22.4 the hum holds (continued by cue_hum)."""
    flick = [19.3, 19.5, 20.3, 20.55, 20.8, 21.0, 21.4, 21.7]
    t0, dur = 19.3, 3.1
    h = hum_tone(dur, 55.0, buzz=0.25)
    gate = np.zeros(sec(dur))
    for tf in flick:
        on, lvl = rng.uniform(0.05, 0.14), rng.uniform(0.55, 1.0)
        i0, i1 = sec(tf - t0), min(len(gate), sec(tf - t0 + on))
        gate[i0:i1] = np.maximum(gate[i0:i1], lvl * raised_cos(on, 0.006, 0.012)[: i1 - i0])
    bus.add(h * gate, t0, pan=0.0, gain=db(-31), near=0.25, name="lamp flicker hum")
    for tf in flick:
        bus.add(crackle(), tf - 0.005, pan=rng.uniform(-0.1, 0.1), gain=db(-30 - rng.uniform(0, 4)),
                near=0.3, name="lamp crackle")


def cue_hum(bus):
    """The robot's continuous hum from 22.4: very quiet lamp hum (55 Hz), a warm hum
    (A2+E3) settling in with the eyes at 27, a step up when it stands (37.4), deepening
    with a sub-octave (E1) over 43-47, gone with the launch."""
    t0, dur = 22.4, 29.0
    rel = lambda x: x - t0
    lamp = hum_tone(dur, 55.0, buzz=0.2)
    lamp_env = envelope(dur, [(0, 0), (0.15, 1), (rel(48.0), 1), (rel(50.0), 0), (dur, 0)], 10)
    warm = warm_tone(dur, (110.0, 165.0))
    warm_env = envelope(dur, [(0, 0), (rel(27.0), 0), (rel(28.2), 1.0), (rel(37.4), 1.0), (rel(37.6), 1.3),
                              (rel(43.0), 1.3), (rel(47.0), 1.6), (rel(48.0), 1.6), (rel(50.5), 0), (dur, 0)], 60)
    deep = hum_tone(dur, 41.2, harm=((1, 1.0), (2, 0.6), (3, 0.3)), wander=0.001)
    deep_env = envelope(dur, [(0, 0), (rel(43.0), 0), (rel(46.5), 1), (rel(48.0), 1), (rel(50.0), 0), (dur, 0)], 100)
    y = lamp * lamp_env * db(-41) + warm * warm_env * db(-32) + deep * deep_env * db(-26)
    bus.add(y, t0, pan=0.0, near=0.2, far=0.15, name="robot hum")


def cue_eyes(bus):
    """Two partials gliding up over 1 s (G3->E4 and D4->B4), soft, then fading into the hum."""
    dur = 3.2
    t = tt(dur)
    g = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / 1.0, 0, 1))
    f1 = 196.0 * (329.6 / 196.0) ** g
    f2 = 293.7 * (493.9 / 293.7) ** g
    y = np.sin(phase(f1)) + 0.8 * np.sin(phase(f2)) + 0.15 * np.sin(phase(2 * f1))
    env = envelope(dur, [(0, 0), (0.2, 0.8), (1.0, 1.0), (1.6, 0.8), (dur, 0)], 40)
    bus.add(norm_peak(y) * env, 26.4, pan=0.0, gain=db(-27), near=0.3, far=0.4, name="eyes wake")


# ---------------------------------------------------------------- granular clouds
def grain_cloud(bus, t_start, t_end, rate_fn, grain_fn, gain_db, spread=0.8, center=0.0,
                far=0.0, near=0.0, jitter=6.0, name=None):
    """Poisson-timed grains; rate_fn(t) in grains/s."""
    t = t_start
    while True:
        r = max(float(rate_fn(t)), 0.05)
        t += rng.exponential(1.0 / r)
        if t >= t_end:
            break
        bus.add(grain_fn(), t, pan=np.clip(center + rng.uniform(-spread, spread), -1, 1),
                gain=db(gain_db - rng.uniform(0, jitter)), far=far, near=near)
    if name:
        bus.events.append((t_start, name))


def g_pebble():
    dur = rng.uniform(0.006, 0.03)
    b, a = peak_coef(rng.uniform(1500, 6500), rng.uniform(6, 18))
    return norm_peak(signal.lfilter(b, a, white(sec(dur))) * exp_decay(dur, dur / 3, 0.0005))


def g_patter():
    dur = rng.uniform(0.015, 0.06)
    n = sec(dur)
    b, a = peak_coef(rng.uniform(400, 2500), rng.uniform(3, 9))
    y = signal.lfilter(b, a, white(n)) + 0.3 * lp(white(n), 500, 2)
    return norm_peak(y * exp_decay(dur, dur / 3.5, 0.001))


def g_soil():
    dur = rng.uniform(0.08, 0.24)
    n = sec(dur)
    y = bp(white(n), rng.uniform(45, 90), rng.uniform(170, 330), 2)
    return norm_peak(y * np.hanning(n) ** rng.uniform(0.6, 1.5))


def g_leaf():
    dur = rng.uniform(0.015, 0.05)
    n = sec(dur)
    t = tt(dur)
    y = bp(white(n), 2500, 8500, 2) * (0.55 + 0.45 * np.sin(TWO_PI * rng.uniform(35, 90) * t))
    return norm_peak(y * np.hanning(n))


# ---------------------------------------------------------------- tremor (23.5-27.8)
def cue_tremor(bus):
    t0, dur = 23.4, 4.6
    t = tt(dur)
    n = len(t)
    env = envelope(dur, [(0, 0), (0.1, 0), (1.2, 0.25), (3.1, 1.0), (3.5, 0.85), (4.3, 0.08), (dur, 0)], 80)
    sub = norm_rms(bp(white(n), 20, 60, 2))
    wf = 40.0 * (1 + 0.07 * np.sin(TWO_PI * 1.3 * t))
    wob = np.sin(phase(wf)) * (0.75 + 0.25 * np.sin(TWO_PI * 6.3 * t))
    out = np.zeros((n, 2))
    for ch in range(2):
        mid = norm_rms(bp(white(n), 90, 260, 2))
        out[:, ch] = 0.55 * sub + 0.45 * wob + 0.22 * mid
    out = norm_peak(out) * (env ** 1.6)[:, None]
    bus.add(out, t0, gain=db(-16), far=0.12, name="ground tremor")
    envf = lambda x: float(np.interp(x, [23.5, 24.6, 26.5, 26.9, 27.7, 28.0], [0, 0.25, 1, 0.85, 0.08, 0]))
    grain_cloud(bus, 24.0, 27.5, lambda x: 3 + 45 * envf(x) ** 1.5, g_pebble, -33, spread=0.8,
                near=0.3, jitter=8, name="pebble patter")


# ---------------------------------------------------------------- flock (24.6-28.0)
def alarm_call(dur):
    n = sec(dur)
    y = np.zeros(n)
    rep, f0 = rng.uniform(7, 12), rng.uniform(2400, 3800)
    t = 0.0
    while t < dur - 0.05:
        nd = 0.045
        m, tn = sec(nd), tt(nd)
        f = f0 * rng.uniform(0.95, 1.05) * np.interp(tn, [0, nd], [1.15, 0.85])
        ph = phase(f)
        note = (np.sin(ph) + 0.45 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph)) * (0.7 + 0.3 * np.sin(TWO_PI * rng.uniform(150, 300) * tn))
        y[sec(t):sec(t) + m] += note * raised_cos(nd, 0.008, 0.015)
        t += rng.uniform(0.9, 1.1) / rep
    y *= envelope(dur, [(0, 1), (0.4 * dur, 0.8), (dur, 0.1)], 20)
    return norm_peak(y)


def cue_flock(bus):
    for _ in range(18):
        start = 24.6 + 0.9 * rng.beta(1.2, 2.5)
        dur = min(rng.uniform(1.5, 3.0), 28.0 - start - 0.05)
        fl = flutter(dur, rng.uniform(6.5, 9.5), (rng.uniform(350, 700), rng.uniform(1800, 3800)), body=0.5)
        env = envelope(dur, [(0, 0), (0.12, 1.0), (0.5 * dur, 0.55), (dur, 0)], 30)
        x = np.linspace(0, 1, sec(dur)) ** 1.3
        fl = (fl * (1 - x) + lp(fl, 800, 2) * x) * env           # moving away: darker, quieter
        side = rng.choice([-1, 1])
        pan = np.interp(tt(dur), [0, dur], [rng.uniform(-0.5, 0.5), side * rng.uniform(0.6, 1.0)])
        bus.add(fl, start, pan=pan, gain=db(-22 + rng.uniform(-4, 2)), far=0.5, name="flock wings")
    for _ in range(7):
        start = 24.7 + rng.uniform(0, 1.3)
        dur = min(rng.uniform(0.8, 1.8), 27.8 - start)
        side = rng.choice([-1, 1])
        pan = np.interp(tt(dur), [0, dur], [rng.uniform(-0.6, 0.6), side * rng.uniform(0.5, 1.0)])
        bus.add(alarm_call(dur), start, pan=pan, gain=db(-27 + rng.uniform(-4, 2)), far=0.8, name="alarm call")


# ---------------------------------------------------------------- the robot rises (29.8-37.6)
def groan(dur, f0, bend, grit=0.5, detune=0.7):
    """Detuned band-limited saws with a slow pitch bend, stick-slip grit, metal-body
    resonances and soft clipping."""
    t = tt(dur)
    n = len(t)
    f = f0 * np.interp(t, [0, 0.3 * dur, 0.7 * dur, dur], [1.0, 1 + 0.5 * bend, 1 + bend, 1 + 0.7 * bend])
    v = np.zeros(n)
    for d in (-detune, 0.0, detune):
        v += bl_saw(f * (1 + 0.008 * d), 40, 1.0)
    g = norm_rms(lp(white(n), 70, 2))
    v *= 1 - grit + grit * np.clip(0.5 + 0.5 * g, 0, 1.5)
    body = np.zeros(n)
    for fc, q, a in ((160, 6, 1.0), (390, 9, 0.7), (870, 12, 0.5), (1900, 10, 0.25)):
        b, aa = peak_coef(fc * rng.uniform(0.9, 1.1), q)
        body += a * signal.lfilter(b, aa, v)
    y = np.tanh(1.6 * norm_peak(0.6 * norm_peak(v) + norm_peak(body)))
    env = envelope(dur, [(0, 0), (0.12, 1), (dur - 0.5, 0.9), (dur, 0)], 30)
    return norm_peak(y * env)


def creak(dur):
    t = tt(dur)
    n = len(t)
    jit = norm_rms(lp(white(n), 9, 2))
    f = rng.uniform(700, 1500) * (1 + 0.06 * jit) * np.interp(t, [0, dur], [1.0, rng.uniform(0.85, 1.2)])
    ph = phase(f)
    y = np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph)
    am = 0.6 + 0.4 * np.clip(norm_rms(lp(white(n), 60, 2)), -1, 1)
    env = envelope(dur, [(0, 0), (0.1, 1), (dur - 0.15, 0.7), (dur, 0)], 10)
    return norm_peak(y * am * env)


def hiss(dur):
    t = tt(dur)
    n = len(t)
    nz = white(n)
    fc = np.interp(t, [0, 0.08, dur], [3800, 2400, 800])
    y = norm_rms(tv_biquad(nz, peak_coef, fc, 1.6, 128)) + 0.5 * norm_rms(bp(nz, 500, 2000, 2))
    return norm_peak(y * exp_decay(dur, dur / 3.2, 0.012))


def thud(f_start=95.0, f_end=34.0, dur=1.4):
    t = tt(dur)
    n = len(t)
    f = f_end + (f_start - f_end) * np.exp(-t / 0.09)
    sub = np.sin(phase(f)) * exp_decay(dur, 0.35, 0.004)
    rumble = norm_rms(lp(white(n), 120, 2)) * exp_decay(dur, 0.25, 0.005)
    click = norm_rms(bp(white(n), 800, 4000, 2)) * exp_decay(dur, 0.012, 0.001)
    return norm_peak(sub + 0.35 * rumble + 0.12 * click)


def clank(dur=2.2):
    """Inharmonic metal modes with slow beating, a noise transient and a low body."""
    t = tt(dur)
    n = len(t)
    y = np.zeros(n)
    for f, a, tau in ((412, 0.9, 0.9), (1130, 0.5, 0.6), (1860, 0.35, 0.45), (2740, 0.25, 0.3), (3620, 0.15, 0.22)):
        for d in (-1.5, 1.5):
            y += a * np.sin(TWO_PI * (f + d) * t + rng.uniform(0, TWO_PI)) * np.exp(-t / tau)
    y += 0.8 * norm_peak(bp(white(n), 1000, 6000, 2)) * np.exp(-t / 0.012)
    y += 1.2 * np.sin(phase(32 + 40 * np.exp(-t / 0.1))) * np.exp(-t / 0.35)
    return norm_peak(y * raised_cos(dur, 0.0005, 0.3))


def cue_debris(bus):
    dens = lambda x: float(np.interp(x, [30.0, 31.0, 32.5, 34.5, 35.5], [0.15, 0.4, 1.0, 1.0, 0.0]))
    grain_cloud(bus, 30.0, 35.5, lambda x: 4 + 22 * dens(x), g_soil, -27, spread=0.8, far=0.3, near=0.2, jitter=8, name="soil cascade")
    grain_cloud(bus, 30.0, 35.5, lambda x: 6 + 55 * dens(x), g_patter, -33, spread=0.9, near=0.3, jitter=10)
    grain_cloud(bus, 30.0, 35.5, lambda x: 3 + 30 * dens(x), g_pebble, -36, spread=0.9, near=0.3, jitter=10)
    grain_cloud(bus, 34.65, 35.6, lambda x: 60 * np.exp(-(x - 34.65) / 0.35), g_patter, -31, spread=0.8, near=0.3, name="footfall debris")


def cue_rise(bus):
    for tg, dur, f0, bend in ((29.8, 2.2, 55, 0.12), (31.2, 1.6, 73, -0.08), (32.6, 2.6, 62, 0.2), (34.2, 1.4, 82, -0.1), (36.0, 2.4, 55, 0.06)):
        bus.add(groan(dur, f0, bend), tg, pan=rng.uniform(-0.25, 0.25), gain=db(-19 + rng.uniform(-2, 1)),
                far=0.35, near=0.2, name="metal groan")
    for tc, dur in ((30.1, 0.7), (32.9, 0.5), (34.4, 0.4), (36.3, 0.8)):
        bus.add(creak(dur), tc, pan=rng.uniform(-0.4, 0.4), gain=db(-32 + rng.uniform(-3, 2)), far=0.5, name="creak")
    for th, dur in ((30.6, 0.8), (32.8, 0.6), (35.0, 0.9)):
        bus.add(hiss(dur), th, pan=rng.uniform(-0.35, 0.35), gain=db(-26 + rng.uniform(-2, 1)), near=0.3, far=0.2, name="hydraulic hiss")
    cue_debris(bus)
    bus.add(thud(), 34.6, pan=0.0, gain=db(-10), far=0.3, near=0.2, name="footfall")
    bus.add(clank(), 37.4, pan=0.05, gain=db(-18), far=0.45, near=0.2, name="settling clank")
    bus.add(thud(70.0, 30.0, 1.6), 37.42, gain=db(-17), far=0.3)


# ---------------------------------------------------------------- head lifts (40.8-41.6)
def servo(dur=0.95):
    t = tt(dur)
    n = len(t)
    f = np.interp(t, [0, 0.15, 0.6, 0.78, dur], [180, 420, 460, 380, 300])
    motor = norm_peak(bp(bl_saw(f, 14, 1.2), 300, 2000, 2))
    whine = 0.08 * np.sin(phase(f * 8.0)) + 0.04 * np.sin(phase(f * 12.02))
    nz = 0.06 * norm_rms(bp(white(n), 1500, 5000, 2))
    env = envelope(dur, [(0, 0), (0.08, 1), (0.7, 0.9), (0.8, 0.0), (dur, 0)], 8)
    y = (motor + whine + nz) * env
    td = dur - 0.8                                        # gentle mechanical stop at 0.8 s
    m, tk = sec(td), tt(td)
    tock = np.sin(TWO_PI * 520 * tk) * np.exp(-tk / 0.035) + 0.5 * np.sin(TWO_PI * 1480 * tk) * np.exp(-tk / 0.015)
    tock += 0.3 * hp(white(m), 3000, 2) * np.exp(-tk / 0.003)
    y[sec(0.8):sec(0.8) + m] += 0.9 * norm_peak(tock)
    return norm_peak(y)


def cue_servo(bus):
    bus.add(servo(), 40.8, pan=0.0, gain=db(-23), near=0.3, far=0.1, name="servo + stop")


# ---------------------------------------------------------------- ignition (44.2-47.4)
def whump(dur=0.8):
    t = tt(dur)
    n = len(t)
    f = 38 + (120 - 38) * np.exp(-t / 0.07)
    sub = np.sin(phase(f)) * exp_decay(dur, 0.22, 0.003)
    tail = norm_rms(lp(white(n), 500, 2)) * exp_decay(dur, 0.28, 0.004)
    burst = norm_rms(bp(white(n), 250, 1500, 2)) * exp_decay(dur, 0.05, 0.002)
    return norm_peak(sub + 0.45 * tail + 0.3 * burst)


def roar_build(dur=2.0):
    """Low-pass filtered noise with a slowly rising resonance plus a sub tone."""
    t = tt(dur)
    n = len(t)
    fc = np.interp(t, [0, dur], [150, 900]) * (1 + 0.04 * np.sin(TWO_PI * 5 * t))
    sub = np.sin(phase(np.interp(t, [0, dur], [42, 58])))
    env = envelope(dur, [(0, 0), (0.5, 0.25), (1.5, 0.7), (dur, 1.0)], 80) ** 1.3
    out = np.zeros((n, 2))
    for ch in range(2):
        res = norm_rms(tv_biquad(white(n), rlp_coef, fc, 3.5, 128))
        out[:, ch] = (res + 0.6 * sub) * env
    return norm_peak(out)


def whoosh(dur, fc_path, q=1.2, pan_path=(-0.9, 0.9), rattle=0.5):
    """Broadband wind sweep: band-pass centre follows fc_path, energy sweeps across the
    stereo field along pan_path, with a granular leaf-rattle layer."""
    t = tt(dur)
    n = len(t)
    fc = np.interp(t, fc_path[0], fc_path[1])
    env = envelope(dur, [(0, 0), (0.35 * dur, 1), (0.65 * dur, 0.85), (dur, 0)], 60)
    pan = np.interp(t, [0, dur], pan_path)
    ang = (pan + 1) * np.pi / 4
    out = np.zeros((n, 2))
    for ch, w in enumerate((np.cos(ang), np.sin(ang))):
        y = norm_rms(tv_biquad(white(n), peak_coef, fc * (1 + 0.05 * (ch - 0.5)), q, 128))
        if rattle > 0:
            mod = np.clip(norm_rms(lp(white(n), 25, 2)), 0, None) ** 2
            y += rattle * norm_rms(bp(white(n), 2500, 8000, 2)) * mod
        out[:, ch] = y * env * (0.4 + 0.9 * w)
    return norm_peak(out)


def cue_ignition(bus):
    for ts, g in ((44.35, -19), (44.8, -16), (45.4, -13)):
        bus.add(whump(), ts, pan=rng.uniform(-0.1, 0.1), gain=db(g), far=0.3, near=0.2, name="ignition sputter")
    bus.add(roar_build(2.0), 45.4, gain=db(-12), far=0.25, name="roar builds")
    w1 = whoosh(2.6, ([0, 1.0, 2.6], [250, 1800, 600]), pan_path=(-0.85, 0.85), rattle=0.45)
    bus.add(w1, 44.6, gain=db(-20), far=0.3, name="wind ring 1")


# ---------------------------------------------------------------- launch (47.4)
def blast(dur=3.0):
    t = tt(dur)
    n = len(t)
    f = 32 + (140 - 32) * np.exp(-t / 0.12)
    sub = np.sin(phase(f)) * exp_decay(dur, 0.6, 0.003)
    out = np.zeros((n, 2))
    for ch in range(2):
        body = norm_rms(bp(white(n), 60, 400, 2)) * exp_decay(dur, 0.35, 0.004)
        roar = norm_rms(bp(white(n), 200, 2500, 2)) * exp_decay(dur, 0.5, 0.006)
        crack = norm_rms(bp(white(n), 1500, 7000, 2)) * exp_decay(dur, 0.03, 0.001)
        out[:, ch] = 0.7 * sub + 0.7 * body + 0.6 * roar + 0.25 * crack
    return norm_peak(out)


def roar_launch(dur=6.0):
    """Roar: ramps up over 0.6 s, then recedes 48-52 with a Doppler-like pitch fall
    (tone and noise resonance both drop to 55 %) and a volume fall; returns the direct
    sound and a dark 'distant' copy whose share grows as the robot leaves."""
    t = tt(dur)
    n = len(t)
    amp = db(np.interp(t, [0, 0.6, 1.2, 4.6, 5.6, dur], [-14, 0, -4, -32, -42, -50]))
    pf = np.interp(t, [0, 0.6, 4.6, dur], [1.0, 1.0, 0.55, 0.5])
    tone = norm_rms(lp(bl_saw(68.0 * pf, 24, 1.2), 700, 2))
    turb = 1 + 0.25 * np.clip(norm_rms(lp(white(n), 18, 2)), -2, 2)
    out = np.zeros((n, 2))
    dist = np.zeros((n, 2))
    for ch in range(2):
        nz = white(n)
        res = norm_rms(tv_biquad(nz, rlp_coef, 1400.0 * pf, 2.5, 256))
        broad = norm_rms(lp(nz, 300, 2))
        y = (0.6 * res + 0.4 * broad + 0.4 * tone) * turb * amp
        out[:, ch] = y
        dist[:, ch] = lp(y, 250, 2) * np.interp(t, [0, 1.2, 4.0, dur], [0, 0, 1, 1])
    m = np.abs(out).max() + 1e-12
    return out / m, dist / m


def cue_launch(bus):
    bus.add(blast(), 47.4, gain=db(-6), far=0.5, near=0.3, name="LAUNCH blast")
    roar, dist = roar_launch(6.0)
    bus.add(roar, 47.4, gain=db(-7), far=0.3, name="launch roar")
    bus.add(dist, 47.4, gain=db(-7), far=0.8)
    w2 = whoosh(2.0, ([0, 0.6, 2.0], [180, 2600, 350]), pan_path=(0.85, -0.85), rattle=0.6)
    bus.add(w2, 47.5, gain=db(-15), far=0.35, name="wind ring 2")


# ---------------------------------------------------------------- aftermath (49.3-56)
def pad(dur=7.5):
    """A lydian chord (A2 E3 C#4 G#4 B4 D#5) of triangle-like partials, three chorused
    voices per note and channel; slow swell, peak ~51-53, gone by 56."""
    t = tt(dur)
    n = len(t)
    notes = [(110.0, 0.9), (164.8, 0.7), (277.2, 0.6), (415.3, 0.45), (493.9, 0.4), (622.3, 0.28)]
    out = np.zeros((n, 2))
    for f, a in notes:
        for ch in range(2):
            for dt in (-0.004, 0.0, 0.004):
                lfo = 1 + 0.002 * np.sin(TWO_PI * rng.uniform(0.1, 0.3) * t + rng.uniform(0, TWO_PI))
                ph = phase(f * (1 + dt) * lfo)
                out[:, ch] += a * (np.sin(ph) + np.sin(3 * ph) / 9 + np.sin(5 * ph) / 25) / 3
    env = envelope(dur, [(0, 0), (2.5, 0.75), (4.0, 1.0), (4.8, 0.9), (7.0, 0.1), (dur, 0)], 150)
    return norm_peak(out * env[:, None])


def cue_aftermath(bus):
    grain_cloud(bus, 49.5, 55.0, lambda x: float(np.interp(x, [49.5, 51, 55], [14, 8, 1.5])), g_leaf, -37,
                spread=0.9, far=0.4, jitter=10, name="falling leaves")
    bus.add(pad(7.5), 48.5, gain=db(-26), far=0.6, name="pad swell")


# ============================================================================ master
_K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def k_weight(x):
    y = signal.lfilter(_K1[0], _K1[1], x, axis=0)
    return signal.lfilter(_K2[0], _K2[1], y, axis=0)


def integrated_lufs(x):
    """ITU-R BS.1770-4 integrated loudness (400 ms blocks, 75 % overlap, -70 LUFS absolute
    and -10 LU relative gates)."""
    y = k_weight(x)
    blk, hop = sec(0.4), sec(0.1)
    cs = np.vstack([np.zeros((1, 2)), np.cumsum(y ** 2, axis=0)])
    idx = np.arange(0, len(y) - blk + 1, hop)
    ms = (cs[idx + blk] - cs[idx]) / blk
    lk = -0.691 + 10 * np.log10(ms.sum(axis=1) + 1e-20)
    keep = lk > -70
    if not keep.any():
        return -np.inf
    rel = -0.691 + 10 * np.log10(ms[keep].sum(axis=1).mean()) - 10
    keep &= lk > rel
    return -0.691 + 10 * np.log10(ms[keep].sum(axis=1).mean())


def true_peak_dbtp(x):
    up = signal.resample_poly(x, 4, 1, axis=0)
    return to_db(np.abs(up).max())


def compressor(x, thresh_db=-22.0, ratio=1.8, knee_db=8.0, attack_ms=20.0, release_ms=300.0, hop_ms=1.0):
    """Gentle RMS compressor; the detector runs on 1 ms frames, gain is interpolated."""
    hop = sec(hop_ms / 1000)
    n = len(x)
    nb = n // hop
    fr = (x[: nb * hop] ** 2).mean(axis=1).reshape(nb, hop).mean(axis=1)
    over = 10 * np.log10(fr + 1e-12) - thresh_db
    k = knee_db / 2
    slope = 1 - 1 / ratio
    gr = np.where(over <= -k, 0.0, np.where(over >= k, over * slope, slope * (over + k) ** 2 / (2 * knee_db)))
    aa, ar = np.exp(-hop / (attack_ms / 1000 * SR)), np.exp(-hop / (release_ms / 1000 * SR))
    sm = np.empty(nb)
    cur = 0.0
    for i in range(nb):
        c = aa if gr[i] > cur else ar
        cur = c * cur + (1 - c) * gr[i]
        sm[i] = cur
    gain = np.interp(np.arange(n), (np.arange(nb) + 0.5) * hop, db(-sm))
    return x * gain[:, None], sm


def limiter(x, ceiling_db=LIMITER_CEILING_DB, lookahead_ms=4.0, hold_ms=40.0, release_ms=150.0):
    """Look-ahead peak limiter.  The gain is the running minimum of the required gain over
    +-hold, Hann-smoothed over +-lookahead (which provably never exceeds the required gain),
    then given a one-pole release.  Sample peaks are guaranteed <= ceiling."""
    ceil = db(ceiling_db)
    peak = np.abs(x).max(axis=1)
    greq = np.minimum(1.0, ceil / np.maximum(peak, 1e-9))
    la = sec(lookahead_ms / 1000)
    hold = max(sec(hold_ms / 1000), la)
    gmin = minimum_filter1d(greq, size=2 * hold + 1, mode="nearest")
    w = np.hanning(2 * la + 1)
    w /= w.sum()
    gs = signal.fftconvolve(np.pad(gmin, la, mode="edge"), w, mode="same")[la:-la]
    gs = np.minimum(gs, greq)
    a = np.exp(-1.0 / (release_ms / 1000 * SR))
    rel, _ = signal.lfilter([1 - a], [1, -a], gs, zi=[a * gs[0]])
    g = np.minimum(gs, rel)
    return x * g[:, None], g


def per_second_table(x):
    y = k_weight(x)
    rows = []
    for s in range(int(DUR)):
        seg, kseg = x[s * SR:(s + 1) * SR], y[s * SR:(s + 1) * SR]
        rms = to_db(np.sqrt((seg ** 2).mean()))
        pk = to_db(np.abs(seg).max())
        lk = -0.691 + 10 * np.log10((kseg ** 2).mean(axis=0).sum() + 1e-20)
        rows.append((s, rms, pk, lk))
    return rows


def write_wav(path, x):
    dither = (rng.random(x.shape) - rng.random(x.shape)) / 32768.0      # TPDF, +-1 LSB
    y = np.clip(x + dither, -1.0, 1.0)
    wavfile.write(path, SR, np.round(y * 32767.0).astype(np.int16))


def ffmpeg_check(path):
    try:
        r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-af", "ebur128=peak=true",
                            "-f", "null", "-"], capture_output=True, text=True, timeout=180)
    except Exception as exc:  # ffmpeg missing or failing is not fatal
        print("ffmpeg verification skipped:", exc)
        return
    txt = r.stderr
    i = txt.rfind("Summary:")
    print("\nffmpeg ebur128 summary:")
    print(txt[i:].rstrip() if i >= 0 else txt[-1200:])


# ============================================================================ main
def main(run_ffmpeg=True):
    t_start = time.time()
    bus = Bus(DUR)
    ir_far = make_ir(2.8, 0.03, [(30, 200, 1.0), (200, 800, 0.9), (800, 2500, 0.6), (2500, 7000, 0.35)])
    ir_near = make_ir(1.1, 0.012, [(60, 300, 1.0), (300, 1200, 0.95), (1200, 4000, 0.8), (4000, 12000, 0.5)])

    cue_ambience(bus)
    cue_distant_birds(bus)
    cue_little_bird(bus)
    cue_sun(bus)
    cue_lamp(bus)
    cue_hum(bus)
    cue_tremor(bus)
    cue_flock(bus)
    cue_eyes(bus)
    cue_rise(bus)
    cue_servo(bus)
    cue_ignition(bus)
    cue_launch(bus)
    cue_aftermath(bus)
    print("cues placed in %.1f s (%d bus events)" % (time.time() - t_start, len(bus.events)))

    mix = bus.render(ir_far, ir_near)
    mix = hp(mix, 18, 2)                                            # DC / sub-sonic cleanup
    fade = np.where(T >= 55.0, 0.5 + 0.5 * np.cos(np.pi * np.clip((T - 55.0) / 1.0, 0, 1)), 1.0)  # hard fade 55 -> 56
    mix *= fade[:, None]
    print("pre-master: peak %.1f dBFS, LUFS %.1f" % (to_db(np.abs(mix).max()), integrated_lufs(mix)))

    comp, gr = compressor(mix)
    print("compressor: max gain reduction %.1f dB" % gr.max())

    # calibrate to the LUFS target through the limiter (the limiter changes loudness a little)
    gain = 1.0
    for _ in range(4):
        out, g = limiter(comp * gain)
        lufs = integrated_lufs(out)
        gain *= db(TARGET_LUFS - lufs)
    out, g = limiter(comp * gain)
    tp = true_peak_dbtp(out)
    if tp > TP_LIMIT_DBTP - 0.05:                                    # safety: scale to the true-peak limit
        out *= db(TP_LIMIT_DBTP - 0.05 - tp)
    lufs = integrated_lufs(out)
    tp = true_peak_dbtp(out)
    print("master gain %+.1f dB, limiter max reduction %.1f dB at %.2f s, compressor max %.1f dB"
          % (to_db(gain), -to_db(g.min()), np.argmin(g) / SR, gr.max()))
    print("RESULT: %.1f s, integrated %.2f LUFS, true peak %.2f dBTP, sample peak %.2f dBFS"
          % (len(out) / SR, lufs, tp, to_db(np.abs(out).max())))

    write_wav(OUT_WAV, out)
    print("wrote", OUT_WAV)

    print("\nper-second levels (RMS dBFS / peak dBFS / K-weighted momentary LUFS):")
    for s, rms, pk, lk in per_second_table(out):
        bar = "#" * int(max(0, (lk + 60) / 60 * 50))
        print("%4.0f-%2.0f  rms %6.1f  peak %6.1f  lufs %6.1f  %s" % (s, s + 1, rms, pk, lk, bar))

    print("\nsection summary (mean RMS dBFS):")
    sections = [("dawn, little bird", 0, 23), ("tremor + flock", 23, 28), ("eyes / pause", 28, 29.8),
                ("robot rises", 29.8, 37.6), ("standing, servo", 37.6, 43), ("tension + ignition", 43, 47.4),
                ("launch", 47.4, 49.3), ("aftermath", 49.3, 55), ("fade", 55, 56)]
    for name, a, b in sections:
        seg = out[sec(a):sec(b)]
        print("  %-22s %5.1f-%4.1f s  rms %6.1f  peak %6.1f" % (name, a, b, to_db(np.sqrt((seg ** 2).mean())), to_db(np.abs(seg).max())))
    print("total %.1f s" % (time.time() - t_start))
    if run_ffmpeg:
        ffmpeg_check(OUT_WAV)


if __name__ == "__main__":
    main(run_ffmpeg="--no-ffmpeg" not in sys.argv[1:])
