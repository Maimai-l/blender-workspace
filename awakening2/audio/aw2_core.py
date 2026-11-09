"""
aw2_core.py -- shared DSP core for the "Awakening II" soundtrack.

Cue loading (everything is timed from cues.json), seeded random generators (one per
named cue, so retiming one event never changes the noise of another), envelopes,
filters, a few numba kernels (band-limited saw, time-varying state-variable filter,
damped-mode bank, dynamic-spectrum additive oscillator), the stereo Bus with reverb
sends, and synthetic convolution reverbs.
"""
import json
import math
import re
import sys
import zlib

import numpy as np
from numba import njit
from scipy import signal
from scipy.ndimage import uniform_filter1d

SR = 48000
NYQ = SR / 2.0
SEED = 20261109
TWO_PI = 2.0 * math.pi


# ============================================================================ helpers
def sec(t):
    return int(round(float(t) * SR))


def tt(dur):
    return np.arange(sec(dur)) / SR


def db(x):
    return np.power(10.0, np.asarray(x, float) / 20.0)


def to_db(x):
    return 20.0 * math.log10(max(float(x), 1e-12))


def mtof(m):
    return 440.0 * np.power(2.0, (np.asarray(m, float) - 69.0) / 12.0)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def norm_peak(x):
    return x / (np.abs(x).max() + 1e-12)


def norm_rms(x):
    return x / (np.sqrt(np.mean(np.square(x))) + 1e-12)


def warn(msg):
    print("WARNING: " + msg, file=sys.stderr, flush=True)


def rng_for(*keys):
    """Independent, reproducible generator per named cue (zlib.crc32, never hash())."""
    return np.random.default_rng([SEED] + [zlib.crc32(str(k).encode()) for k in keys])


NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nm(name):
    """'F#4' -> 66 (MIDI)."""
    m = NOTE_RE.match(name.strip())
    if not m:
        raise ValueError(name)
    pc = _PC[m.group(1).upper()] + {"#": 1, "b": -1, "": 0}[m.group(2)]
    return pc + 12 * (int(m.group(3)) + 1)


def name_of(midi):
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
    m = int(round(midi))
    return "%s%d" % (names[m % 12], m // 12 - 1)


# ============================================================================ cues
def base_name(name):
    """'rise_groan_2' -> 'rise_groan', 'core_flicker_1' -> 'core_flicker'."""
    return re.sub(r"_\d+$", "", name)


class Cues:
    """Everything the soundtrack knows about the picture comes from cues.json."""

    def __init__(self, path):
        with open(path) as fh:
            d = json.load(fh)
        self.path = path
        self.raw = d
        self.duration = float(d["duration"])
        self.fps = float(d.get("fps", 24))
        self.shots = [dict(s, **{"in": float(s["in"]), "out": float(s["out"])}) for s in d.get("shots", [])]
        ev = [(float(e["t"]), str(e["name"])) for e in d.get("events", [])]
        self.events = sorted(ev, key=lambda e: e[0])
        self.sections = {}
        for s in d.get("music", {}).get("sections", []):
            self.sections[s["name"]] = (float(s["in"]), float(s["out"]))
        self.n = sec(self.duration)

    def times(self, base):
        return [t for t, n in self.events if base_name(n) == base]

    def first(self, base, default=None):
        ts = self.times(base)
        return ts[0] if ts else default

    def get(self, base, default):
        """First time of an event (by base name), or the default with a note."""
        ts = self.times(base)
        if ts:
            return ts[0]
        warn("cue '%s' missing, using %.2f s" % (base, default))
        return default

    def after(self, t, bases, default=None, strict=True):
        """Earliest event among `bases` after t (strictly later if strict)."""
        best = None
        for te, n in self.events:
            if base_name(n) in bases and (te > t + 1e-9 if strict else te >= t):
                best = te if best is None else min(best, te)
        return default if best is None else best

    def section(self, name, default=None):
        if name in self.sections:
            return self.sections[name]
        if default is not None:
            warn("music section '%s' missing, using %s" % (name, default))
        return default

    def shot_at(self, t):
        for s in self.shots:
            if s["in"] <= t < s["out"]:
                return s
        return None

    def frame(self, t):
        return int(round(t * self.fps))


def launch_silence(C):
    """The held breath before the launch, shared by score, effects and master: it ends where
    the smear begins and lasts 15 % of the wind-ring -> smear build-up (0.3-0.7 s).
    Returns (start, end) or None when there is no launch in the cues."""
    imp = C.first("impact_frame")
    if imp is None:
        return None
    s1 = C.first("launch_smear", imp - 0.2)
    ref = C.first("wind_ring", C.first("engine_ignite", s1 - 3.2))
    if ref is None or ref >= s1:
        ref = s1 - 3.2
    L = float(np.clip(0.15 * (s1 - ref), 0.3, 0.7))
    return s1 - L, s1


# ============================================================================ envelopes
def smooth(x, ms):
    """Zero-phase smoothing (two box passes ~ triangle of width ms)."""
    n = max(1, sec(ms / 1000.0) // 2)
    if n < 2:
        return x
    y = uniform_filter1d(x, n, axis=0, mode="nearest")
    return uniform_filter1d(y, n, axis=0, mode="nearest")


def env(dur, pts, smooth_ms=0.0, n=None):
    """Piecewise-linear envelope from (time, value) points over dur seconds."""
    n = sec(dur) if n is None else n
    t = np.arange(n) / SR
    ts = np.array([p[0] for p in pts], float)
    vs = np.array([p[1] for p in pts], float)
    e = np.interp(t, ts, vs)
    return smooth(e, smooth_ms) if smooth_ms else e


def cos_ramp(n):
    """0 -> 1 raised-cosine ramp of n samples."""
    if n <= 0:
        return np.zeros(0)
    return 0.5 - 0.5 * np.cos(np.pi * np.arange(n) / n)


def fades(x, a_ms=0.3, r_ms=3.0):
    """Raised-cosine fade-in/out in place (mono or stereo); returns x."""
    n = len(x)
    a = min(n // 2, sec(a_ms / 1000.0))
    r = min(n // 2, sec(r_ms / 1000.0))
    if a > 0:
        w = cos_ramp(a)
        x[:a] *= w[:, None] if x.ndim == 2 else w
    if r > 0:
        w = cos_ramp(r)[::-1]
        x[n - r:] *= w[:, None] if x.ndim == 2 else w
    return x


def adsr(n, a, d, s, r, curve=1.0):
    """Linear-segment ADSR over n samples (a, d, r in seconds); release at the end."""
    e = np.full(n, float(s))
    ia, idd, ir = sec(a), sec(d), sec(r)
    ia = min(ia, n)
    if ia > 0:
        e[:ia] = cos_ramp(ia)
    if idd > 0 and ia < n:
        m = min(idd, n - ia)
        e[ia:ia + m] = 1.0 + (s - 1.0) * cos_ramp(idd)[:m]
    ir = min(ir, n)
    if ir > 0:
        e[n - ir:] *= cos_ramp(ir)[::-1]
    return e ** curve if curve != 1.0 else e


def exp_decay(n, tau, attack=0.0005):
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    a = min(n, sec(attack))
    if a > 0:
        e[:a] *= cos_ramp(a)
    return e


# ============================================================================ filters
_SOS = {}


def _sos(kind, f, order):
    key = (kind, f if np.isscalar(f) else tuple(f), order)
    if key not in _SOS:
        if np.isscalar(f):
            ff = float(min(max(f, 1.0), 0.95 * NYQ))
        else:
            ff = (max(float(f[0]), 1.0), min(float(f[1]), 0.95 * NYQ))
        _SOS[key] = signal.butter(order, ff, btype=kind, fs=SR, output="sos")
    return _SOS[key]


def lp(x, f, order=2, zp=False):
    s = _sos("lowpass", f, order)
    return signal.sosfiltfilt(s, x, axis=0) if zp else signal.sosfilt(s, x, axis=0)


def hp(x, f, order=2, zp=False):
    s = _sos("highpass", f, order)
    return signal.sosfiltfilt(s, x, axis=0) if zp else signal.sosfilt(s, x, axis=0)


def bp(x, lo, hi, order=2, zp=False):
    s = _sos("bandpass", (lo, hi), order)
    return signal.sosfiltfilt(s, x, axis=0) if zp else signal.sosfilt(s, x, axis=0)


def biquad_peq(f, gain_db, q):
    """RBJ peaking EQ coefficients."""
    f = float(np.clip(f, 10.0, 0.45 * SR))
    A = 10 ** (gain_db / 40.0)
    w = TWO_PI * f / SR
    al = math.sin(w) / (2 * q)
    c = math.cos(w)
    b = np.array([1 + al * A, -2 * c, 1 - al * A])
    a = np.array([1 + al / A, -2 * c, 1 - al / A])
    return b / a[0], a / a[0]


def biquad_shelf(f, gain_db, kind="low", s=1.0):
    f = float(np.clip(f, 10.0, 0.45 * SR))
    A = 10 ** (gain_db / 40.0)
    w = TWO_PI * f / SR
    c, sn = math.cos(w), math.sin(w)
    al = sn / 2 * math.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    sq = 2 * math.sqrt(A) * al
    if kind == "low":
        b = [A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq)]
        a = [(A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq]
    else:
        b = [A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq)]
        a = [(A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq]
    b, a = np.array(b), np.array(a)
    return b / a[0], a / a[0]


def peq(x, f, gain_db, q=1.0):
    b, a = biquad_peq(f, gain_db, q)
    return signal.lfilter(b, a, x, axis=0)


def shelf(x, f, gain_db, kind="low"):
    b, a = biquad_shelf(f, gain_db, kind)
    return signal.lfilter(b, a, x, axis=0)


def reson(x, f, q):
    """Unity-peak band-pass resonance (iirpeak)."""
    f = float(np.clip(f, 15.0, 0.45 * SR))
    b, a = signal.iirpeak(f, q, fs=SR)
    return signal.lfilter(b, a, x, axis=0)


def white(rng, n):
    return rng.standard_normal(n)


def pink(rng, n):
    """Paul Kellet's economy pink filter, unit RMS."""
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1.0, -2.494956002, 2.017265875, -0.522189400]
    return norm_rms(signal.lfilter(b, a, rng.standard_normal(n)))


def brown(rng, n, fc=60.0):
    return norm_rms(lp(rng.standard_normal(n), fc, 1))


def slow_noise(rng, n, hz):
    """Smooth random control signal, unit RMS, ~hz bandwidth."""
    k = max(4, int(n / SR * hz) + 4)
    pts = rng.standard_normal(k)
    x = np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
    return norm_rms(smooth(x, 600.0 / max(hz, 0.05)) if n > 64 else x)


def phase_of(f):
    return TWO_PI * np.cumsum(f) / SR


# ============================================================================ numba kernels
@njit(cache=True, fastmath=True)
def saw_blep(freq, ph0):
    """PolyBLEP sawtooth (-1..1) following an instantaneous-frequency array."""
    n = freq.shape[0]
    out = np.empty(n)
    ph = ph0
    for i in range(n):
        dt = freq[i] / 48000.0
        if dt > 0.45:
            dt = 0.45
        ph += dt
        if ph >= 1.0:
            ph -= 1.0
        v = 2.0 * ph - 1.0
        if ph < dt:
            x = ph / dt
            v -= x + x - x * x - 1.0
        elif ph > 1.0 - dt:
            x = (ph - 1.0) / dt
            v -= x * x + x + x + 1.0
        out[i] = v
    return out


@njit(cache=True, fastmath=True)
def svf_tv(x, fc, q, mode):
    """Topology-preserving state-variable filter with per-sample cutoff.
    mode 0 low-pass, 1 band-pass (unity peak), 2 high-pass."""
    n = x.shape[0]
    y = np.empty(n)
    ic1 = 0.0
    ic2 = 0.0
    k = 1.0 / q
    for i in range(n):
        f = fc[i]
        if f < 10.0:
            f = 10.0
        if f > 0.45 * 48000.0:
            f = 0.45 * 48000.0
        g = math.tan(math.pi * f / 48000.0)
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - ic2
        v1 = a1 * ic1 + a2 * v3
        v2 = ic2 + a2 * ic1 + a3 * v3
        ic1 = 2.0 * v1 - ic1
        ic2 = 2.0 * v2 - ic2
        if mode == 0:
            y[i] = v2
        elif mode == 1:
            y[i] = k * v1
        else:
            y[i] = x[i] - k * v1 - v2
    return y


@njit(cache=True, fastmath=True)
def add_modes(out, i0, freqs, amps, taus, phases, att):
    """out[i0:] += sum_m a_m exp(-t/tau_m) sin(2 pi f_m t + phi_m), with an `att`-sample
    linear onset ramp (no click).  Each mode stops when it falls below 1e-6."""
    n_out = out.shape[0]
    for m in range(freqs.shape[0]):
        f = freqs[m]
        a = amps[m]
        if f <= 0.0 or f >= 0.47 * 48000.0 or a == 0.0:
            continue
        tau = taus[m]
        nmax = int(tau * 48000.0 * math.log(abs(a) * 1e6 + 1.0)) + 1
        if nmax > n_out - i0:
            nmax = n_out - i0
        w = 2.0 * math.pi * f / 48000.0
        r = math.exp(-1.0 / (tau * 48000.0))
        cr = r * math.cos(w)
        sr = r * math.sin(w)
        re = a * math.cos(phases[m])
        im = a * math.sin(phases[m])
        for i in range(nmax):
            g = 1.0
            if i < att:
                g = i / att
            out[i0 + i] += im * g
            re2 = re * cr - im * sr
            im = re * sr + im * cr
            re = re2


@njit(cache=True, fastmath=True)
def additive_dyn(freq, amp, tilt, roll, hmul, out):
    """Harmonic oscillator with a time-varying spectrum:
    out = amp * sum_k hmul[k] * (k+1)^-tilt * exp(-roll*k) * sin((k+1) phase).
    Weights are refreshed every 16 samples; harmonics fade out before 0.45*SR."""
    n = freq.shape[0]
    nh = hmul.shape[0]
    w = np.zeros(nh)
    ph = 0.0
    for i in range(n):
        f = freq[i]
        ph += 2.0 * math.pi * f / 48000.0
        if ph > 2.0 * math.pi:
            ph -= 2.0 * math.pi
        if (i & 15) == 0:
            for k in range(nh):
                fk = (k + 1) * f
                edge = (0.45 * 48000.0 - fk) / (0.05 * 48000.0)
                if edge <= 0.0:
                    w[k] = 0.0
                else:
                    if edge > 1.0:
                        edge = 1.0
                    w[k] = edge * hmul[k] * math.exp(-tilt[i] * math.log(k + 1.0) - roll[i] * k)
        s1 = math.sin(ph)
        c2 = 2.0 * math.cos(ph)
        sp = 0.0
        sc = s1
        acc = 0.0
        for k in range(nh):
            if w[k] == 0.0 and k > 0:
                break
            acc += w[k] * sc
            sn = c2 * sc - sp
            sp = sc
            sc = sn
        out[i] = amp[i] * acc


def warmup_kernels():
    """Compile (or load from cache) the numba kernels once."""
    f = np.full(64, 440.0)
    saw_blep(f, 0.0)
    svf_tv(np.zeros(64), f * 2, 0.7, 0)
    o = np.zeros(64)
    add_modes(o, 0, np.array([440.0]), np.array([1.0]), np.array([0.1]), np.array([0.0]), 4)
    additive_dyn(f, np.ones(64), np.zeros(64), np.zeros(64), np.ones(4), o)


# ============================================================================ bus
def pan_stereo(x, pan):
    """Constant-power pan of a mono signal (pan scalar or array in [-1, 1])."""
    p = np.clip(np.asarray(pan, float), -1.0, 1.0)
    ang = (p + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(ang), x * np.sin(ang)], axis=1)


class Bus:
    """Stereo float bus with named reverb sends and an event log."""

    def __init__(self, n, sends=()):
        self.n = n
        self.dry = np.zeros((n, 2))
        self.sends = {k: np.zeros((n, 2)) for k in sends}
        self.log = []          # (t0, t1, name, peak_db, cue time, energy onset)
        self.cue = None        # cue time that placements are attributed to (set by event handlers)

    def add(self, x, t0, pan=0.0, gain=1.0, send=None, name=None, fade_in_ms=0.3,
            fade_out_ms=3.0, width=1.0, log_onset=None):
        x = np.asarray(x, float)
        if x.ndim == 1:
            st = pan_stereo(x, pan)
        else:
            st = x.copy()
            if width != 1.0:
                m = 0.5 * (st[:, 0] + st[:, 1])
                s = 0.5 * (st[:, 0] - st[:, 1]) * width
                st = np.stack([m + s, m - s], axis=1)
            if np.ndim(pan) == 0 and pan != 0.0:
                p = float(np.clip(pan, -1, 1))
                st[:, 0] *= math.sqrt(1 - p) if p > 0 else 1.0
                st[:, 1] *= math.sqrt(1 + p) if p < 0 else 1.0
        st = st * gain
        s0 = sec(t0)
        if s0 < 0:
            st = st[-s0:]
            s0 = 0
        e = min(self.n, s0 + len(st))
        if e <= s0:
            return
        seg = st[: e - s0]
        fades(seg, fade_in_ms, fade_out_ms if e - s0 == len(st) else 20.0)
        self.dry[s0:e] += seg
        if getattr(self, "keep", None) is not None:          # diagnostics: keep every placed sound
            self.keep.append((s0 / SR, name or "", seg.copy()))
        if send:
            for k, v in send.items():
                if v:
                    self.sends[k][s0:e] += v * seg
        if name or self.cue is not None:
            a = np.abs(seg).max(axis=1)
            pk = a.max()
            on = (s0 + int(np.argmax(a > 0.1 * pk))) / SR if pk > 0 else s0 / SR
            cue = log_onset if log_onset is not None else (self.cue if self.cue is not None else t0)
            self.log.append((s0 / SR, e / SR, name or "", to_db(pk), cue, on))

    def render(self, irs):
        out = self.dry.copy()
        for k, buf in self.sends.items():
            if not np.any(buf):
                continue
            ir = irs[k]
            for ch in range(2):
                out[:, ch] += signal.oaconvolve(buf[:, ch], ir[:, ch])[: self.n]
        return out


# ============================================================================ reverbs
def make_ir(key, rt60, predelay, bands, n_er=10, er_span=(0.008, 0.08), er_gain=0.4,
            diffusion_ms=15.0, er_lp=5000.0):
    """Synthetic stereo impulse response: band-split exponentially decaying noise
    (each band with its own RT60 multiplier) + sparse early reflections, independent
    per channel, unit energy per channel."""
    rng = rng_for("ir", key)
    span = rt60 * 1.1
    n = sec(span)
    t = np.arange(n) / SR
    pd = sec(predelay)
    ir = np.zeros((n + pd, 2))
    for ch in range(2):
        nz = rng.standard_normal(n)
        tail = np.zeros(n)
        for lo, hi, mult in bands:
            if lo <= 20:
                comp = lp(nz, hi, 2)
            elif hi >= 20000:
                comp = hp(nz, lo, 2)
            else:
                comp = bp(nz, lo, hi, 2)
            tail += comp * np.exp(-6.908 * t / (rt60 * mult))
        tail *= 1.0 - np.exp(-t / (diffusion_ms / 1000.0))
        er = np.zeros(n)
        for k in range(n_er):
            ti = rng.uniform(*er_span)
            er[min(n - 1, sec(ti))] += rng.uniform(0.35, 1.0) * (1 if rng.random() < 0.5 else -1) * (1 - 0.6 * ti / er_span[1])
        tail = tail / (np.sqrt(np.sum(tail ** 2)) + 1e-12) + er_gain * lp(er, er_lp, 2)
        ir[pd:, ch] = tail
    ir[-sec(0.05):] *= cos_ramp(sec(0.05))[::-1, None]
    ir /= np.sqrt((ir ** 2).sum(axis=0)).max()
    return ir


def standard_irs():
    """hall: the orchestra's room; far: the forest (long, dark); near: close and short;
    sky: huge, airy and dark for the flight."""
    return {
        "hall": make_ir("hall", 2.3, 0.022, [(20, 250, 1.25), (250, 1000, 1.0), (1000, 4000, 0.75), (4000, 20000, 0.45)],
                        n_er=14, er_span=(0.006, 0.085), er_gain=0.55, diffusion_ms=20),
        "far": make_ir("far", 2.7, 0.035, [(20, 200, 1.0), (200, 800, 0.95), (800, 2500, 0.6), (2500, 20000, 0.3)],
                       n_er=8, er_span=(0.015, 0.12), er_gain=0.3, diffusion_ms=30, er_lp=3000),
        "near": make_ir("near", 0.9, 0.008, [(20, 300, 0.9), (300, 1500, 1.0), (1500, 5000, 0.8), (5000, 20000, 0.5)],
                        n_er=9, er_span=(0.003, 0.03), er_gain=0.6, diffusion_ms=8),
        "sky": make_ir("sky", 4.5, 0.06, [(20, 300, 1.0), (300, 1500, 0.85), (1500, 5000, 0.5), (5000, 20000, 0.25)],
                       n_er=4, er_span=(0.04, 0.2), er_gain=0.15, diffusion_ms=60, er_lp=2000),
    }
