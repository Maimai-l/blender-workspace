"""
aw2_instruments.py -- the synthesized orchestra for "Awakening II".

Every instrument returns float arrays at a nominal level (a single voice at velocity 1
peaks near 1.0; sections are normalised by sqrt(voices)).  The score decides gains,
pans and reverb sends.

  flute()            mono legato line: dynamic-spectrum additive tone, delayed vibrato,
                     pitched breath noise, tongued "chiff" onsets
  strings()          a string section playing one or more lines: N detuned PolyBLEP saw
                     players each with their own vibrato, timing and glide, a
                     dynamics-following low-pass, violin/cello body resonances, bow noise;
                     articulations sus / trem / harm (flautando harmonics) / spicc
  pizz()             plucked strings (modal)
  brass()            horn / trombone / tuba section: additive tone whose spectrum opens
                     with loudness (brightness lags the amplitude), lip scoop, breath blat
  piano()            soft felt piano: inharmonic partials, unison-string beating, double
                     decay, felt hammer thump, damper release
  musicbox(), celesta(), glock(), harp()   modal plucked/struck instruments
  timpani(), timp_roll(), taiko(), bass_drum(), crash(), cymbal_swell(),
  reverse_cymbal(), tamtam()               percussion
"""
import math

import numpy as np
from numba import njit
from scipy import signal

from aw2_core import (SR, TWO_PI, add_modes, additive_dyn, bp, cos_ramp, db, fades, hp, lp, mtof,
                      norm_rms, pan_stereo, peq, saw_blep, sec, shelf, slow_noise, smooth, svf_tv)


def tail_fade(buf, frac=0.25):
    """Raised-cosine fade over the last `frac` of a note buffer, so a ringing mode is never
    cut off (no click when the buffer ends before the note has died away)."""
    q = max(2, int(len(buf) * frac))
    w = cos_ramp(q)[::-1]
    buf[-q:] *= w[:, None] if buf.ndim == 2 else w
    return buf


# ============================================================================ notes
class Note:
    """t, d in seconds; m MIDI (float ok); v velocity 0..1 or [(frac, v), ...] swell points."""
    __slots__ = ("t", "d", "m", "v", "art", "slur")

    def __init__(self, t, d, m, v=0.7, art=None, slur=False):
        self.t, self.d, self.m, self.v, self.art, self.slur = float(t), float(d), float(m), v, art, slur

    def vmax(self):
        return max(p[1] for p in self.v) if isinstance(self.v, (list, tuple)) else float(self.v)

    def __repr__(self):
        return "Note(%.3f, %.3f, %.1f, %s)" % (self.t, self.d, self.m, self.v)


def vel_curve(note, n):
    if isinstance(note.v, (list, tuple)):
        fr = np.array([p[0] for p in note.v], float)
        vv = np.array([p[1] for p in note.v], float)
        return np.interp(np.linspace(0.0, 1.0, n), fr, vv)
    return np.full(n, float(note.v))


@njit(cache=True, fastmath=True)
def follow_ar(x, a_att, a_rel):
    """Asymmetric one-pole follower (coefficients per sample, not time constants)."""
    n = x.shape[0]
    y = np.empty(n)
    s = 0.0
    for i in range(n):
        c = a_att if x[i] > s else a_rel
        s += (x[i] - s) * c
        y[i] = s
    return y


def coef(tau):
    return 1.0 - math.exp(-1.0 / (max(tau, 1e-4) * SR))


def onepole(x, tau):
    c = coef(tau)
    y, _ = signal.lfilter([c], [1, c - 1], x, zi=[x[0] * (1 - c)])
    return y


def line_curves(notes, t0, n, tongue_ms=0.0, legato_gap=0.035):
    """Per-sample pitch target (log2 Hz, held through gaps), level target, and the
    sample indices of articulated (non-slurred) onsets for a monophonic line."""
    logf = np.full(n, np.nan)
    lev = np.zeros(n)
    onsets = []
    prev_end = -1e9
    for nt in notes:
        s = max(0, sec(nt.t - t0))
        e = min(n, max(s + 1, sec(nt.t + nt.d - t0)))
        logf[s:e] = math.log2(float(mtof(nt.m)))
        lev[s:e] = vel_curve(nt, e - s)
        joined = nt.t - prev_end < legato_gap
        if not (joined and nt.slur):
            onsets.append(s)
            if joined and tongue_ms > 0:              # re-articulation: a short tongue/bow gap
                g = sec(tongue_ms / 1000.0)
                lev[max(0, s - g // 2):s + g // 2] = 0.0
        prev_end = nt.t + nt.d
    ok = ~np.isnan(logf)
    idx = np.where(ok, np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    first = np.argmax(ok)
    logf = np.where(np.arange(n) < first, logf[first], logf[idx])
    return logf, lev, onsets


def vibrato_env(notes, t0, n, delay=0.28, ramp=0.5, min_len=0.45):
    """0..1 per-note delayed vibrato depth (resets at each articulated note)."""
    e = np.zeros(n)
    for nt in notes:
        if nt.d < min_len:
            continue
        s, ee = max(0, sec(nt.t - t0)), min(n, sec(nt.t + nt.d - t0))
        k = np.arange(ee - s) / SR
        e[s:ee] = np.clip((k - delay) / ramp, 0.0, 1.0) ** 1.5
    return smooth(e, 60)


def span_of(notes, pre=0.1, post=0.6):
    t0 = min(nt.t for nt in notes) - pre
    t1 = max(nt.t + nt.d for nt in notes) + post
    return t0, sec(t1 - t0)


# ============================================================================ flute
FLUTE_H = np.array([1.0, 0.62, 0.30, 0.17, 0.10, 0.065, 0.04, 0.026, 0.017, 0.011, 0.007, 0.005, 0.003, 0.002])


def flute(notes, rng, vib_rate=5.0, vib_depth=0.0045, breath=1.0, brightness=0.0):
    """Monophonic flute line.  Returns (t0, mono)."""
    notes = sorted(notes, key=lambda x: x.t)
    t0, n = span_of(notes, 0.12, 0.6)
    logf, lev, onsets = line_curves(notes, t0, n, tongue_ms=45.0)
    logf = onepole(logf, 0.009)                                  # quick fingered transitions
    ve = vibrato_env(notes, t0, n)
    rate = vib_rate * (1 + 0.05 * slow_noise(rng, n, 0.4))
    vib = np.sin(TWO_PI * np.cumsum(rate) / SR + rng.uniform(0, TWO_PI))
    drift = 0.0012 * slow_noise(rng, n, 0.7)                     # ~2 cents of breath wander
    f = 2.0 ** logf * (1 + vib_depth * ve * vib + drift)
    # amplitude: soft tongued attack, slow release, accent bump on articulated onsets
    tgt = lev.copy()
    for s in onsets:
        m = min(n - s, sec(0.07))
        tgt[s:s + m] *= 1.0 + 0.10 * cos_ramp(m)[::-1]
    a = follow_ar(tgt, coef(0.028), coef(0.075))
    a *= 1.0 + 0.07 * ve * np.sin(TWO_PI * np.cumsum(rate) / SR + 0.6)   # breath vibrato (mostly AM)
    a *= 1.0 + 0.025 * slow_noise(rng, n, 3.0)
    roll = np.clip(0.55 - 0.35 * a - 0.12 * brightness + 0.18 * np.clip(logf - 9.5, 0, 2), 0.05, 1.5)
    tone = np.empty(n)
    additive_dyn(f, a, np.zeros(n), roll, FLUTE_H, tone)
    tone /= FLUTE_H.sum() * 0.55
    # breath: broadband air + noise amplitude-modulated by the tone (pitched breath)
    nz = rng.standard_normal(n)
    air = bp(nz, 1400, 7000, 2) * (0.6 + 0.4 * np.abs(tone) / (np.abs(tone).max() + 1e-9))
    air *= (0.035 + 0.05 * (1 - np.clip(a / 0.8, 0, 1))) * a * breath
    chiff = np.zeros(n)
    for s in onsets:
        m = min(n - s, sec(0.05))
        fc = float(2.0 ** logf[min(n - 1, s + 10)]) * 3.0
        burst = bp(rng.standard_normal(m), max(400, fc * 0.6), min(12000, fc * 2.2), 2)
        chiff[s:s + m] += burst * np.exp(-np.arange(m) / sec(0.012)) * 0.18 * breath * lev[min(n - 1, s + 20)]
    y = tone + air + chiff
    y = lp(y, 9000, 2)
    return t0, y


# ============================================================================ strings
SECTIONS = {
    #        players, pan range,       cutoff pp..ff,  vibrato rate, depth (rel), glide s,  body
    "vln1": dict(n=8, pan=(-0.78, -0.30), fc=(1800, 7500), vr=(5.0, 6.4), vd=(0.0035, 0.0065), gl=0.045, body="vln", oct=0),
    "vln2": dict(n=7, pan=(-0.42, 0.02), fc=(1700, 6500), vr=(5.0, 6.2), vd=(0.0035, 0.006), gl=0.045, body="vln", oct=0),
    "vla": dict(n=6, pan=(0.02, 0.42), fc=(1400, 5000), vr=(4.8, 6.0), vd=(0.003, 0.0055), gl=0.05, body="vla", oct=0),
    "vc": dict(n=5, pan=(0.25, 0.62), fc=(1000, 4200), vr=(4.6, 5.8), vd=(0.003, 0.005), gl=0.055, body="vc", oct=0),
    "cb": dict(n=4, pan=(0.30, 0.70), fc=(600, 2200), vr=(4.3, 5.4), vd=(0.002, 0.004), gl=0.06, body="cb", oct=0),
}
BODY = {   # (freq, gain dB, Q): air mode, wood modes, bridge hill, top roll-off
    "vln": [(280, 3.0, 4), (460, 2.0, 5), (700, -2.0, 3), (1050, 1.5, 4), (2600, 3.5, 1.5), (4200, -2.5, 1.2), (6800, -5.0, 0.9)],
    "vla": [(220, 3.0, 4), (380, 2.0, 5), (620, -1.5, 3), (1500, 1.5, 2), (2300, 2.5, 1.6), (4500, -4.0, 1.0)],
    "vc": [(110, 2.0, 3), (200, 3.0, 4), (420, 2.0, 4), (700, -1.5, 3), (1500, 2.0, 1.8), (3200, -4.0, 1.0)],
    "cb": [(70, 2.0, 3), (120, 3.0, 3), (260, 1.5, 3), (500, -1.5, 2), (1200, 1.5, 1.5), (2200, -5.0, 1.0)],
}


BODY_RANGE = {"vln": (190.0, 7000.0), "vla": (150.0, 5500.0), "vc": (65.0, 3500.0), "cb": (40.0, 2200.0)}
_BODY_IR = {}


def body_ir(kind):
    """A synthetic instrument-body impulse response: ~90 damped modes spread over the body's
    range (dense, jagged response like real wood).  Fixed per section, so a section keeps one
    timbre all film long."""
    if kind not in _BODY_IR:
        from aw2_core import rng_for
        r = rng_for("body", kind)
        lo, hi = BODY_RANGE[kind]
        nm_ = 90
        f = np.exp(r.uniform(math.log(lo), math.log(hi), nm_))
        a = r.uniform(0.25, 1.0, nm_) * (lo / f) ** 0.25
        tau = r.uniform(0.004, 0.02, nm_) * (500.0 / f) ** 0.25
        ir = np.zeros(sec(0.06))
        add_modes(ir, 0, f, a, tau, r.uniform(0, TWO_PI, nm_), 3)
        ir /= np.sqrt(np.sum(ir ** 2))
        _BODY_IR[kind] = ir
    return _BODY_IR[kind]


def strings(lines, section, rng, art="sus", attack=0.35, release=0.6, players=None, trem_rate=13.0,
            spread=1.0, bright=0.0, detune_cents=7.0, timing_ms=14.0):
    """A string section.  lines: list of note lists (each a monophonic line; chords =
    several lines).  art: 'sus' legato/sustained, 'trem' unmeasured tremolo, 'harm'
    flautando harmonics, 'spicc' short bowed notes.  Returns (t0, stereo)."""
    P = SECTIONS[section]
    nply = players or P["n"]
    allnotes = [nt for ln in lines for nt in ln]
    t0, n = span_of(allnotes, 0.15, release + 0.4)
    out = np.zeros((n, 2))
    levsum = np.zeros(n)
    per_line = max(1, int(round(nply / max(1, len(lines)) ** 0.5)))
    a_att = coef(attack if art != "spicc" else 0.010)
    a_rel = coef(release if art != "spicc" else 0.07)
    for li, ln in enumerate(lines):
        ln = sorted(ln, key=lambda x: x.t)
        for v in range(per_line):
            off = rng.normal(0.0, timing_ms / 1000.0)
            sh = [Note(nt.t + off, nt.d, nt.m, nt.v, nt.art, nt.slur) for nt in ln]
            logf, lev, ons = line_curves(sh, t0, n, tongue_ms=0.0 if art != "spicc" else 30.0)
            logf = onepole(logf, P["gl"] * rng.uniform(0.7, 1.3))
            ve = vibrato_env(sh, t0, n, delay=rng.uniform(0.12, 0.3), ramp=0.45)
            if art in ("harm",):
                ve *= 0.5
            vr = rng.uniform(*P["vr"]) * (1 + 0.04 * slow_noise(rng, n, 0.3))
            vib = np.sin(TWO_PI * np.cumsum(vr) / SR + rng.uniform(0, TWO_PI))
            det = rng.normal(0.0, detune_cents) / 1200.0 * math.log(2)
            jitter = 0.0009 * slow_noise(rng, n, 25.0)            # bow roughness
            f = 2.0 ** logf * np.exp(det + 0.0015 * slow_noise(rng, n, 0.25)) * (1 + rng.uniform(*P["vd"]) * ve * vib + jitter)
            a = follow_ar(lev, a_att * rng.uniform(0.8, 1.2), a_rel * rng.uniform(0.8, 1.2))
            if art == "spicc":
                a = follow_ar(lev, a_att, coef(0.09))
            if art == "trem":
                tr = trem_rate * rng.uniform(0.85, 1.15) * (1 + 0.15 * slow_noise(rng, n, 2.0))
                ph = np.cumsum(tr) / SR + rng.uniform(0, 1)
                stroke = 0.5 + 0.5 * np.cos(TWO_PI * ph)
                a = a * (0.42 + 0.58 * stroke ** 2)
            a *= 1.0 + 0.04 * slow_noise(rng, n, 1.5)
            if art == "harm":
                ph = TWO_PI * np.cumsum(f) / SR + rng.uniform(0, TWO_PI)
                y = (np.sin(ph) + 0.06 * np.sin(2 * ph)) * a
            else:
                y = saw_blep(f, rng.uniform(0, 1)) * a
            pan = rng.uniform(*P["pan"]) * spread
            out += pan_stereo(y, pan)
            levsum += a
    out /= math.sqrt(per_line * max(1, len(lines)))
    lv = levsum / max(1e-9, levsum.max()) if levsum.max() > 0 else levsum
    if art != "harm":
        lo, hi = P["fc"]
        fc = lo + (hi - lo) * np.clip(lv * (1 + bright), 0, 1.3) ** 0.8
        fc = smooth(fc, 30)
        for ch in range(2):
            y = svf_tv(out[:, ch], fc, 0.6, 0)
            out[:, ch] = svf_tv(y, fc * 1.3, 0.55, 0)
        for f0, g, q in BODY[P["body"]]:
            out = peq(out, f0, g, q)
        ir = body_ir(P["body"])
        wet = np.stack([signal.oaconvolve(out[:, ch], ir)[: len(out)] for ch in range(2)], 1)
        wet *= (np.sqrt(np.mean(out ** 2)) + 1e-12) / (np.sqrt(np.mean(wet ** 2)) + 1e-12)
        out = 0.55 * out + 0.45 * wet
        # bow noise: band-passed noise following the dynamics
        nz = rng.standard_normal((n, 2))
        bn = bp(nz, 1800, 6500, 2) * (lv * (0.012 if art != "trem" else 0.03))[:, None]
        out += bn * np.sqrt(per_line * len(lines)) / math.sqrt(per_line * max(1, len(lines)))
    else:
        out = lp(out, 7000, 2)
    return t0, out


def pizz(notes, rng, section="vc", players=3, bright=0.5):
    """Ensemble pizzicato: modal plucks, a little detune and timing spread.  Returns (t0, stereo)."""
    P = SECTIONS[section]
    t0, n = span_of(notes, 0.05, 1.6)
    out = np.zeros((n, 2))
    for nt in notes:
        f0 = float(mtof(nt.m))
        for p in range(players):
            buf_n = min(n - max(0, sec(nt.t - t0)), sec(1.5))
            buf = np.zeros(buf_n)
            k = np.arange(1, 13)
            det = 2 ** (rng.normal(0, 5) / 1200)
            amps = np.abs(np.sin(np.pi * k * 0.18)) / k ** (1.5 - 0.5 * bright) * nt.vmax()
            tau0 = 0.55 * (110.0 / f0) ** 0.35
            taus = tau0 / (1 + 0.45 * (k - 1))
            add_modes(buf, 0, f0 * det * k * (1 + 0.0002 * k ** 2), amps, taus, rng.uniform(0, TWO_PI, 12), 48)
            thump = lp(rng.standard_normal(buf_n), 300, 2) * np.exp(-np.arange(buf_n) / sec(0.012)) * 0.25 * nt.vmax()
            thump[: sec(0.001)] *= cos_ramp(sec(0.001))
            buf += thump
            tail_fade(buf)
            s = max(0, sec(nt.t + rng.normal(0, 0.008) - t0))
            e = min(n, s + buf_n)
            out[s:e] += pan_stereo(buf[: e - s], rng.uniform(*P["pan"]))
    out /= math.sqrt(players)
    for f0, g, q in BODY[P["body"]][:3]:
        out = peq(out, f0, g, q)
    return t0, out


# ============================================================================ brass
BRASS = {
    #           players  pan range       roll pp..ff   tilt  formant (f, dB, Q)                lp
    "horn": dict(n=4, pan=(-0.55, -0.12), roll=(1.05, 0.16), tilt=0.55, form=[(420, 3.0, 1.2), (1100, 1.5, 1.5)], lpf=4200, scoop=0.010),
    "tbn": dict(n=3, pan=(0.10, 0.45), roll=(0.95, 0.07), tilt=0.45, form=[(520, 2.0, 1.2), (1250, 2.5, 1.5)], lpf=7000, scoop=0.006),
    "tuba": dict(n=1, pan=(0.25, 0.35), roll=(1.10, 0.28), tilt=0.6, form=[(230, 3.0, 1.2)], lpf=2500, scoop=0.006),
}


def brass(lines, section, rng, attack=0.06, release=0.25, players=None, timing_ms=12.0, detune_cents=4.0):
    """Brass section; each line is a legato line.  Spectrum opens with loudness and
    lags behind the amplitude (the 'bwah').  Returns (t0, stereo)."""
    P = BRASS[section]
    nply = players or P["n"]
    allnotes = [nt for ln in lines for nt in ln]
    t0, n = span_of(allnotes, 0.12, release + 0.5)
    out = np.zeros((n, 2))
    per_line = max(1, int(round(nply / max(1, len(lines)) ** 0.5)))
    hm = 1.0 / np.arange(1, 41) ** 0.0
    for ln in lines:
        ln = sorted(ln, key=lambda x: x.t)
        for v in range(per_line):
            off = rng.normal(0.0, timing_ms / 1000.0)
            sh = [Note(nt.t + off, nt.d, nt.m, nt.v, nt.art, nt.slur) for nt in ln]
            logf, lev, ons = line_curves(sh, t0, n, tongue_ms=40.0)
            logf = onepole(logf, 0.03)
            scoop = np.zeros(n)
            for s in ons:
                m = min(n - s, sec(0.25))
                scoop[s:s + m] -= P["scoop"] * np.exp(-np.arange(m) / sec(0.045))
            det = 2 ** (rng.normal(0, detune_cents) / 1200.0)
            f = 2.0 ** logf * det * (1 + scoop + 0.0012 * slow_noise(rng, n, 0.5))
            a = follow_ar(lev, coef(attack * rng.uniform(0.8, 1.25)), coef(release * rng.uniform(0.8, 1.2)))
            a *= 1.0 + 0.03 * slow_noise(rng, n, 2.0)
            br = follow_ar(a, coef(0.07), coef(0.12))                     # brightness lags amplitude
            r0, r1 = P["roll"]
            roll = r0 + (r1 - r0) * np.clip(br, 0, 1) ** 0.9
            y = np.empty(n)
            additive_dyn(f, a, np.full(n, P["tilt"]), roll, hm, y)
            # breath "blat" on articulated onsets, louder when loud
            for s in ons:
                m = min(n - s, sec(0.06))
                vv = float(lev[min(n - 1, s + sec(0.03))])
                nb = bp(rng.standard_normal(m), 700, 3500, 2) * np.exp(-np.arange(m) / sec(0.015))
                y[s:s + m] += nb * 0.10 * vv ** 2
            out += pan_stereo(y, rng.uniform(*P["pan"]))
    out /= math.sqrt(per_line * max(1, len(lines))) * 2.2
    for f0, g, q in P["form"]:
        out = peq(out, f0, g, q)
    out = lp(out, P["lpf"], 2)
    return t0, out


# ============================================================================ piano
def piano(notes, rng, felt=0.75, pedal=True, width=0.28):
    """Soft felt piano.  notes: Note list (d = how long the key/pedal holds).  Returns (t0, stereo)."""
    t0 = min(nt.t for nt in notes) - 0.02
    t1 = max(nt.t + nt.d for nt in notes) + 1.0
    n = sec(t1 - t0)
    out = np.zeros((n, 2))
    for nt in notes:
        f0 = float(mtof(nt.m))
        v = nt.vmax()
        B = float(np.clip(0.00012 * 2 ** ((nt.m - 60) / 16.0), 4e-5, 2e-3))
        K = int(min(48, max(6, 7500 // f0)))
        k = np.arange(1, K + 1)
        fk = k * f0 * np.sqrt(1 + B * k ** 2)
        x0 = 0.118
        bright = 0.9 + 1.2 * v
        amps = np.abs(np.sin(np.pi * k * x0)) / k ** (1.9 - 0.55 * v) * np.exp(-fk / (900 + 2600 * v * (1.15 - felt)))
        amps *= v ** 1.3
        t60 = float(np.interp(nt.m, [21, 48, 60, 72, 84, 96, 108], [24, 17, 13, 9, 5.5, 3.0, 1.5]))
        tau = t60 / 6.9
        tau_k = tau / (1 + (fk / 1800.0) ** 1.4 * 1.8)
        nstr = 3 if nt.m > 52 else (2 if nt.m > 34 else 1)
        dur = min(n - sec(nt.t - t0), sec(min(nt.d + 0.6, t60 * 0.8 + 0.5)))
        if dur <= 0:
            continue
        buf = np.zeros(dur)
        for sidx in range(nstr):
            cents = (sidx - (nstr - 1) / 2) * rng.uniform(0.4, 1.3)
            det = 2 ** (cents / 1200)
            # double decay: prompt (fast) + aftersound (slow), split per string
            add_modes(buf, 0, fk * det, amps * 0.75 / nstr, tau_k * 0.3, rng.uniform(0, TWO_PI, K), 110)
            add_modes(buf, 0, fk * det, amps * 0.25 / nstr, tau_k, rng.uniform(0, TWO_PI, K), 150)
        m = len(buf)
        tn = np.arange(m) / SR
        # felt hammer: soft low thump + faint felt noise (1.5-2 ms onsets: felt, not a click)
        ramp = np.minimum(1.0, tn / 0.0018)
        thump = lp(rng.standard_normal(m), 250 + 500 * v, 2) * np.exp(-tn / 0.010) * 0.10 * v * ramp
        felt_nz = bp(rng.standard_normal(m), 600, 3000, 4) * np.exp(-tn / 0.004) * 0.02 * v * ramp
        buf += thump + felt_nz
        # damper (end of key/pedal hold)
        off = sec(nt.d)
        if off < m:
            buf[off:] *= np.exp(-np.arange(m - off) / sec(0.11))
        tail_fade(buf, 0.15)
        pan = np.clip((nt.m - 64) / 30.0, -1, 1) * width
        s = sec(nt.t - t0)
        out[s:s + m] += pan_stereo(buf, pan)
    out = lp(out, 7000 - 3000 * felt, 2)
    out = peq(out, 140, 2.0, 1.0)        # soundboard warmth
    return t0, out * 2.2


# ============================================================================ mallets / plucked
def _modal_notes(notes, rng, table, tau_fn, click, pan_fn, tail=3.0, att=12):
    t0 = min(nt.t for nt in notes) - 0.01
    t1 = max(nt.t for nt in notes) + tail
    n = sec(t1 - t0)
    out = np.zeros((n, 2))
    for nt in notes:
        f0 = float(mtof(nt.m)) * 2 ** (rng.normal(0, 1.5) / 1200)
        v = nt.vmax()
        ratios = np.array([r for r, a, tm in table])
        amps = np.array([a for r, a, tm in table]) * v
        taus = np.array([tm for r, a, tm in table]) * tau_fn(f0)
        m = min(n - sec(nt.t - t0), sec(min(tail, taus.max() * 7)))
        if m <= 0:
            continue
        buf = np.zeros(m)
        add_modes(buf, 0, f0 * ratios, amps, taus, rng.uniform(0, TWO_PI, len(ratios)), att)
        if click:
            c = min(m, sec(0.004))
            buf[:c] += hp(rng.standard_normal(c), click[0], 2) * np.exp(-np.arange(c) / sec(click[1])) * click[2] * v
        tail_fade(buf)
        s = sec(nt.t - t0)
        out[s:s + m] += pan_stereo(buf, pan_fn(nt))
    return t0, out


def musicbox(notes, rng):
    table = [(1.0, 1.0, 1.0), (2.0, 0.05, 0.35), (5.4, 0.22, 0.10), (11.6, 0.06, 0.035)]
    return _modal_notes(notes, rng, table, lambda f: 1.5 * (880.0 / f) ** 0.4, (2500, 0.0008, 0.25),
                        lambda nt: np.clip((nt.m - 80) / 25.0, -0.4, 0.4), tail=4.0, att=6)


def celesta(notes, rng):
    table = [(1.0, 1.0, 1.0), (2.0, 0.16, 0.45), (3.0, 0.05, 0.25), (2.76, 0.10, 0.18), (5.4, 0.05, 0.06)]
    return _modal_notes(notes, rng, table, lambda f: 1.9 * (523.0 / f) ** 0.5, (1800, 0.001, 0.08),
                        lambda nt: 0.25 + np.clip((nt.m - 76) / 40.0, -0.15, 0.15), tail=4.5, att=18)


def glock(notes, rng):
    table = [(1.0, 1.0, 1.0), (2.76, 0.30, 0.35), (5.40, 0.12, 0.14), (8.93, 0.06, 0.06)]
    return _modal_notes(notes, rng, table, lambda f: 2.2 * (1047.0 / f) ** 0.3, (4000, 0.0005, 0.3),
                        lambda nt: 0.15 + np.clip((nt.m - 90) / 30.0, -0.2, 0.2), tail=5.0, att=6)


def harp(notes, rng, pan=-0.38):
    """Plucked harp strings (harmonic partials with a pluck-position comb, fast high decay)."""
    t0 = min(nt.t for nt in notes) - 0.01
    t1 = max(nt.t for nt in notes) + 5.0
    n = sec(t1 - t0)
    out = np.zeros((n, 2))
    for nt in notes:
        f0 = float(mtof(nt.m))
        v = nt.vmax()
        k = np.arange(1, 17)
        amps = np.abs(np.sin(np.pi * k * 0.27)) / k ** 1.25 * np.exp(-k / (3.0 + 6.0 * v)) * v
        tau0 = 3.6 * (130.0 / f0) ** 0.5
        taus = tau0 / (1 + 0.28 * (k - 1))
        m = min(n - sec(nt.t - t0), sec(min(5.0, tau0 * 6)))
        buf = np.zeros(m)
        add_modes(buf, 0, f0 * k * (1 + 0.00004 * k ** 2), amps, taus, np.zeros(16), 48)
        c = min(m, sec(0.01))
        pk = lp(rng.standard_normal(c), 2000, 2) * np.exp(-np.arange(c) / sec(0.002)) * 0.04 * v
        pk[: sec(0.0008)] *= cos_ramp(sec(0.0008))
        buf[:c] += pk
        tail_fade(buf)
        s = sec(nt.t - t0)
        out[s:s + m] += pan_stereo(buf, pan + np.clip((nt.m - 70) / 60.0, -0.2, 0.2))
    return t0, out * 1.4


# ============================================================================ percussion
def timpani(midi, vel, rng, dur=None):
    """One timpani stroke (mono).  Principal (1,1) mode glides down from a slightly sharp
    strike pitch; the other membrane modes are fixed."""
    f = float(mtof(midi))
    tau1 = 1.5 * (98.0 / f) ** 0.3 * (0.75 + 0.25 * vel)
    dur = dur or min(6.0, tau1 * 6)
    n = sec(dur)
    t = np.arange(n) / SR
    out = np.zeros(n)
    table = [(1.50, 0.55, 0.55), (1.98, 0.42, 0.42), (2.44, 0.30, 0.32), (2.94, 0.20, 0.25), (3.43, 0.11, 0.18),
             (1.70, 0.12, 0.18), (2.27, 0.08, 0.14), (0.62, 0.45, 0.06)]
    r = np.array([x[0] for x in table])
    a = np.array([x[1] for x in table]) * (0.6 + 0.6 * vel)
    tau = np.array([x[2] for x in table]) * tau1
    add_modes(out, 0, f * r, a, tau, rng.uniform(0, TWO_PI, len(r)), 20)
    glide = 1 + 0.022 * vel * np.exp(-t / 0.07)
    out += np.sin(TWO_PI * np.cumsum(f * glide) / SR) * np.exp(-t / tau1) * np.minimum(1, t / 0.002)
    mal = lp(rng.standard_normal(n), 900 + 1500 * vel, 2) * np.exp(-t / 0.005) * 0.5 * vel
    mal[: sec(0.0008)] *= cos_ramp(sec(0.0008))
    out = (out + mal) * vel
    return tail_fade(out * 0.6)


def timp_roll(dur, midi, vel_pts, rng, rate=15.0):
    """Timpani roll: alternating strokes ~rate/s, velocity from (frac, v) points."""
    n = sec(dur + 3.0)
    out = np.zeros(n)
    t = 0.0
    k = 0
    while t < dur:
        v = float(np.interp(t / dur, [p[0] for p in vel_pts], [p[1] for p in vel_pts]))
        v *= (1.0 if k % 2 == 0 else 0.88) * rng.uniform(0.9, 1.05)
        s = timpani(midi, max(0.03, v), rng, dur=min(2.5, 3.0))
        i = sec(t)
        m = min(len(s), n - i)
        out[i:i + m] += s[:m] * 0.45
        t += (1.0 / rate) * rng.uniform(0.9, 1.1)
        k += 1
    return out


def taiko(vel, rng, f0=56.0):
    """Large barrel drum: pitch-dropping head, membrane modes, stick slap, shell boom."""
    n = sec(2.5)
    t = np.arange(n) / SR
    out = np.zeros(n)
    fd = f0 * (1 + 0.6 * np.exp(-t / 0.035))
    out += np.sin(TWO_PI * np.cumsum(fd) / SR) * np.exp(-t / 0.42) * np.minimum(1, t / 0.0015)
    r = np.array([1.59, 2.14, 2.30, 2.65, 2.92, 3.16])
    add_modes(out, 0, f0 * 1.05 * r, np.array([0.5, 0.35, 0.3, 0.22, 0.15, 0.1]), np.array([0.16, 0.11, 0.1, 0.07, 0.06, 0.05]),
              rng.uniform(0, TWO_PI, 6), 10)
    slap = bp(rng.standard_normal(n), 350, 3200, 2) * np.exp(-t / 0.012) * 0.6
    shell = bp(rng.standard_normal(n), 120, 260, 2) * np.exp(-t / 0.09) * 0.5
    return (out + slap + shell) * vel


def bass_drum(vel, rng):
    n = sec(3.0)
    t = np.arange(n) / SR
    fd = 44.0 * (1 + 0.5 * np.exp(-t / 0.06))
    y = np.sin(TWO_PI * np.cumsum(fd) / SR) * np.exp(-t / 0.75) * np.minimum(1, t / 0.004)
    y += lp(rng.standard_normal(n), 350, 2) * np.exp(-t / 0.05) * 0.35
    return tail_fade(y * vel)


def _cymbal_modes(rng, nmodes=160, lo=320.0, hi=15000.0):
    f = np.exp(rng.uniform(np.log(lo), np.log(hi), nmodes))
    w = np.exp(-0.5 * ((np.log(f) - np.log(4500.0)) / 0.9) ** 2) + 0.15
    a = w * rng.uniform(0.3, 1.0, nmodes)
    tau = np.clip(2.8 * (1200.0 / f) ** 0.45 * rng.uniform(0.6, 1.4, nmodes), 0.12, 4.5)
    return f, a / np.sqrt(np.sum(a ** 2)), tau


def crash(vel, rng, dur=4.5):
    """Crash / clash cymbals, stereo (independent mode sets per side)."""
    n = sec(dur)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for ch in range(2):
        f, a, tau = _cymbal_modes(rng)
        y = np.zeros(n)
        add_modes(y, 0, f, a * 3.0, tau * (0.8 + 0.3 * vel), rng.uniform(0, TWO_PI, len(f)), 8)
        nz = hp(rng.standard_normal(n), 1800, 2)
        y += nz * (0.55 * np.exp(-t / 0.025) + 0.10 * np.exp(-t / 0.6)) * (0.5 + 0.5 * vel)
        out[:, ch] = y
    out *= vel * 0.5
    out[-sec(0.2):] *= cos_ramp(sec(0.2))[::-1, None]
    return out


def cymbal_swell(dur, rng, peak_frac=1.0):
    """Suspended cymbal mallet roll swelling to the end (or to peak_frac), stereo."""
    n = sec(dur)
    t = np.arange(n) / SR
    e = np.clip(t / (dur * peak_frac), 0, 1) ** 2.2
    out = np.zeros((n, 2))
    for ch in range(2):
        f, a, tau = _cymbal_modes(rng, 120, 500, 14000)
        y = np.zeros(n)
        add_modes(y, 0, f, a * 2.0, np.full(len(f), 60.0), rng.uniform(0, TWO_PI, len(f)), 200)
        roll = 1 + 0.25 * np.sin(TWO_PI * 18 * t + rng.uniform(0, TWO_PI))
        nz = svf_tv(rng.standard_normal(n), 2500 + 6000 * e, 0.6, 2)
        out[:, ch] = (y * 0.8 + 0.45 * nz) * e * roll
    return out * 0.5


def reverse_cymbal(dur, rng):
    """Time-reversed crash ending at full level (cut by the caller)."""
    c = crash(1.0, rng, dur=max(dur, 1.0) + 0.5)
    r = c[::-1][-sec(dur):].copy()
    r *= cos_ramp(len(r))[:, None] ** 0.7
    return r


def tamtam(vel, rng, dur=7.0):
    """Tam-tam: dense low inharmonic modes plus a slow 'bloom' of upper modes."""
    n = sec(dur)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for ch in range(2):
        lo = np.exp(rng.uniform(np.log(55), np.log(700), 70))
        y = np.zeros(n)
        add_modes(y, 0, lo, rng.uniform(0.2, 1.0, 70) / 6, np.clip(4.5 * (100 / lo) ** 0.3 * rng.uniform(0.7, 1.3, 70), 0.5, 7),
                  rng.uniform(0, TWO_PI, 70), 30)
        hi = np.exp(rng.uniform(np.log(700), np.log(6000), 90))
        z = np.zeros(n)
        add_modes(z, 0, hi, rng.uniform(0.2, 1.0, 90) / 9, np.clip(2.5 * (1000 / hi) ** 0.5, 0.3, 4), rng.uniform(0, TWO_PI, 90), 30)
        bloom = (1 - np.exp(-t / 0.7)) * np.exp(-t / 3.5)
        mal = lp(rng.standard_normal(n), 300, 2) * np.exp(-t / 0.03) * 0.6
        out[:, ch] = y + z * bloom * 2.5 + mal
    return tail_fade(out * vel * 0.5, 0.3)
