"""
aw2_score.py -- the score for "Awakening II", composed against the cue sheet.

The theme ("the old dream") is a 9-bar sentence in D major, 4/4:

  a  | F#4 A4 D5. E5 | F#5 - E5. D5 | D5 - C#5 B4 | A4 - - -  |      (D(add9) Bm7 Gmaj7 Asus4-A)
  b  | G4 B4 E5. F#5 | G5 - F#5. E5 | B5 -- A5 F#5 | E5 -- F#5 E5 | D5  (Em7 A7sus4 Gmaj7 Asus4-A D)

Phrase b is phrase a's opening sequenced a step up, then a leap of a fifth to the peak
(B5, the third of the IV chord) and a stepwise close.  Dawn: music box (fragment) then
the flute (phrase a) with felt piano, string pad and a harp at the first ray of sun.
Tremor: low pulse and tremolo rising in harmony (D pedal: D, Bb/D, C/D), a shimmer when
the eyes ignite.  Rise: phrase a in D minor in horns and cellos over low brass and
timpani (i - VI - iv - V), the minor third turning major as the eyes resolve, a Lydian
glow for the canopy gap.  Ignition: a held harmonic, then a crescendo C - D, a scale run,
a cut.  Flight: E major (a tone up): phrase b over a driving ostinato, its peak (C#6 over
Amaj7) placed exactly on sky_reveal, then the cadence.  Coda: felt piano alone with the
opening motif, ending on the open third.

Every time below is derived from cues.json (sections + named events); bar lengths are
fitted to the spans between anchor events, with sensible tempo limits.
"""
import math

import numpy as np

import aw2_instruments as I
from aw2_core import Bus, db, launch_silence, nm, rng_for, sec, warn
from aw2_instruments import Note

THEME = [
    (0, 0.0, 1.0, "F#4"), (0, 1.0, 1.0, "A4"), (0, 2.0, 1.5, "D5"), (0, 3.5, 0.5, "E5"),
    (1, 0.0, 2.0, "F#5"), (1, 2.0, 1.5, "E5"), (1, 3.5, 0.5, "D5"),
    (2, 0.0, 2.0, "D5"), (2, 2.0, 1.0, "C#5"), (2, 3.0, 1.0, "B4"),
    (3, 0.0, 4.0, "A4"),
    (4, 0.0, 1.0, "G4"), (4, 1.0, 1.0, "B4"), (4, 2.0, 1.5, "E5"), (4, 3.5, 0.5, "F#5"),
    (5, 0.0, 2.0, "G5"), (5, 2.0, 1.5, "F#5"), (5, 3.5, 0.5, "E5"),
    (6, 0.0, 3.0, "B5"), (6, 3.0, 0.5, "A5"), (6, 3.5, 0.5, "F#5"),
    (7, 0.0, 3.0, "E5"), (7, 3.0, 0.5, "F#5"), (7, 3.5, 0.5, "E5"),
    (8, 0.0, 4.0, "D5"),
]
MINOR = {6: -1, 11: -1, 1: -1}          # D major -> D natural minor: F#->F, B->Bb, C#->C


def theme(bars, transpose=0, minor=False):
    """[(beat from the first selected bar, dur beats, midi)] for the given bars."""
    b0 = min(bars)
    out = []
    for bar, beat, d, name in THEME:
        if bar in bars:
            m = nm(name)
            if minor:
                m += MINOR.get(m % 12, 0)
            out.append(((bar - b0) * 4 + beat, d, m + transpose))
    return out


class Tempo:
    """Beat -> time map: piecewise linear between (beat, time) anchors, extrapolated."""

    def __init__(self, anchors):
        a = sorted(anchors)
        self.b = np.array([x[0] for x in a], float)
        self.t = np.array([x[1] for x in a], float)

    def __call__(self, beat):
        b, t = self.b, self.t
        if beat <= b[0]:
            return t[0] + (beat - b[0]) * (t[1] - t[0]) / (b[1] - b[0])
        if beat >= b[-1]:
            return t[-1] + (beat - b[-1]) * (t[-1] - t[-2]) / (b[-1] - b[-2])
        return float(np.interp(beat, b, t))

    def dur(self, beat, d):
        return self(beat + d) - self(beat)


def rit_anchors(b0, b1, t0, t1, ratio=1.0, steps=16):
    """Anchors for beats b0..b1 filling t0..t1 with beat length growing linearly by `ratio`."""
    nb = b1 - b0
    L0 = (t1 - t0) / (nb * (1 + (ratio - 1) / 2))
    out = []
    for k in range(steps + 1):
        x = k / steps
        out.append((b0 + nb * x, t0 + L0 * nb * (x + (ratio - 1) * x * x / 2)))
    return out


def fit_beat(span, nbeats, lo, hi, name):
    b = span / nbeats
    if not lo <= b <= hi:
        warn("%s: span %.2f s for %g beats gives %.0f BPM; clamped" % (name, span, nbeats, 60 / b))
    return float(np.clip(b, lo, hi))


def notes_from(rows, tm, vel, slur_all=True, tongue=(), legato=1.0):
    """rows from theme(); tm Tempo; vel float or callable(i, beat, midi)."""
    out = []
    for i, (b, d, m) in enumerate(rows):
        t0 = tm(b)
        dur = tm.dur(b, d) * legato
        v = vel(i, b, m) if callable(vel) else vel
        out.append(Note(t0, dur, m, v, slur=slur_all and i not in tongue))
    return out


def voice_lines(chords, vel, gap=0.0):
    """chords: [(t, dur, [m1, m2, ...]), ...] with the same voice count -> one legato line per
    voice (slurred), so voices move like players instead of re-attacking."""
    nv = len(chords[0][2])
    lines = [[] for _ in range(nv)]
    for t, d, ms in chords:
        for k in range(nv):
            v = vel(t, k) if callable(vel) else vel
            lines[k].append(Note(t, d - gap, ms[k], v, slur=True))
    return lines


# ============================================================================ the score
SECTION_TRIM = {"dawn": 3.0, "tremor": -2.0, "rise": -3.0, "ignition": -3.0, "flight": -1.0, "coda": 2.0}


class Score:
    def __init__(self, cues):
        self.C = cues
        self.bus = Bus(cues.n, sends=("hall", "far"))
        self.marks = {}
        self.trim = 0.0

    def mark(self, k, t):
        self.marks[k] = tuple(float(x) for x in t) if isinstance(t, tuple) else float(t)

    def _put(self, key, t0, y, gain_db, hall, name=None, onset=None, pan=0.0, width=1.0):
        self.bus.add(y, t0, pan=pan, gain=float(db(gain_db + self.trim)), send={"hall": hall}, name=name or key,
                     log_onset=onset, width=width)

    def strings(self, key, lines, section, gain_db, hall=0.32, **kw):
        lines = [ln for ln in lines if ln]
        if not lines:
            return
        t0, y = I.strings(lines, section, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=min(n.t for ln in lines for n in ln))

    def brass(self, key, lines, section, gain_db, hall=0.45, **kw):
        t0, y = I.brass(lines, section, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=min(n.t for ln in lines for n in ln))

    def flute(self, key, notes, gain_db, hall=0.30, pan=-0.12, **kw):
        t0, y = I.flute(notes, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=notes[0].t, pan=pan)

    def piano(self, key, notes, gain_db, hall=0.26, **kw):
        t0, y = I.piano(notes, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=notes[0].t)

    def modal(self, key, fn, notes, gain_db, hall=0.4, **kw):
        t0, y = fn(notes, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=notes[0].t)

    def pizz(self, key, notes, gain_db, hall=0.3, **kw):
        t0, y = I.pizz(notes, rng_for("mus", key), **kw)
        self._put(key, t0, y, gain_db, hall, onset=notes[0].t)

    def perc(self, key, t, y, gain_db, hall=0.4, pan=0.0, width=1.0):
        self._put(key, t, y, gain_db, hall, onset=t, pan=pan, width=width)


# ---------------------------------------------------------------------------- dawn
def dawn(S):
    C = S.C
    d_in, d_out = C.section("dawn", (0.0, C.get("tremor_start", 25.0)))
    fade0 = max(d_in, C.first("fade_in_start", d_in))
    trem = C.first("tremor_start", d_out)
    sun = C.get("sun_ray_reaches_face", d_in + 0.6 * (trem - d_in))
    cross = C.first("bird_crosses_far", None)
    flick = C.first("core_flicker", None)
    glow = C.first("core_glow_steady", flick + 1.4 if flick else trem - 2.6)

    # flute phrase a: bar 2 (the Gmaj7, the warm chord) lands on the first ray of sun
    beat = 60.0 / 72
    if flick is not None:
        beat = min(beat, (flick + 1.0 - sun) / 8)
    if cross is not None:
        beat = min(beat, (sun - cross - 0.5) / 8)
    beat = fit_beat(beat * 8, 8, 60 / 92, 60 / 58, "dawn flute")
    tm = Tempo([(0, sun - 8 * beat), (8, sun), (16, sun + 8 * beat)])
    bar = lambda k: tm(4 * k)
    S.mark("flute_start", bar(0))
    S.mark("sun_chord", bar(2))

    # music box: the opening motif as a faint memory, winding down (each beat longer)
    mb_t0 = fade0 + min(2.4, 0.3 * (bar(0) - fade0))
    mb_end = min(bar(0) - 2.4, (cross - 0.2) if cross else bar(0) - 2.4)
    if mb_end - mb_t0 > 1.6:
        mt = Tempo(rit_anchors(0, 4, mb_t0, mb_end, ratio=1.7))
        rows = [(0, "F#5", "D5"), (1, "A5", None), (2, "D6", "A5"), (3.5, "E6", None), (4, "F#6", "D6")]
        mbn = []
        for b, top, low in rows:
            mbn.append(Note(mt(b), 1.0, nm(top), 0.55 if b < 4 else 0.5))
            if low:
                mbn.append(Note(mt(b) + 0.012, 1.0, nm(low), 0.28))
        S.modal("dawn/musicbox", I.musicbox, mbn, -23.0, hall=0.55)
        S.mark("musicbox", mb_t0)

    # string pad: D(add9) | Bm7 | Gmaj7 | Asus4 - A | A (fading into the core hum)
    p0 = fade0 + 1.0
    chords = [(p0, bar(1) - p0, ["D3", "A3", "E4", "F#4"]),
              (bar(1), 4 * beat, ["B2", "A3", "D4", "F#4"]),
              (bar(2), 4 * beat, ["G2", "B3", "D4", "F#4"]),
              (bar(3), 3 * beat, ["A2", "A3", "D4", "E4"]),
              (bar(3) + 3 * beat, max(1.0, trem - 0.9 - bar(3) - 3 * beat), ["A2", "A3", "C#4", "E4"])]
    pad_end = trem - 0.9
    sw = lambda t: float(np.interp(t, [p0, bar(1), bar(2) - 0.6, bar(2) + 1.2, bar(3) + 2 * beat, glow, pad_end],
                                   [0.18, 0.22, 0.25, 0.34, 0.29, 0.17, 0.02]))
    lines = voice_lines([(t, d, [nm(x) for x in ms]) for t, d, ms in chords], lambda t, k: sw(t))
    for ln in lines:            # swell inside each held chord, following sw()
        for nt in ln:
            nt.v = [(0, sw(nt.t)), (0.5, sw(nt.t + nt.d / 2)), (1, sw(nt.t + nt.d))]
    S.strings("dawn/pad_vc", [lines[0]], "vc", -12.0, attack=1.6, release=1.4, players=4)
    S.strings("dawn/pad_vla", lines[1:3], "vla", -13.0, attack=1.6, release=1.4)
    S.strings("dawn/pad_vln2", [lines[3]], "vln2", -16.0, attack=1.8, release=1.4, players=5, bright=-0.2)
    bass = [Note(t, d, nm(ms[0]) - 12, [(0, sw(t) * 0.8), (1, sw(t + d) * 0.8)], slur=True) for t, d, ms in chords]
    S.strings("dawn/pad_cb", [bass], "cb", -16.0, attack=1.8, release=1.6, players=3)
    # violins: the light (B5 over the Gmaj7, then A5)
    vl = [Note(bar(2) - 0.2, 4 * beat + 0.2, nm("B5"), [(0, 0.05), (0.35, 0.31), (1, 0.26)], slur=True),
          Note(bar(3), 6 * beat, nm("A5"), [(0, 0.32), (0.4, 0.24), (1, 0.02)], slur=True)]
    S.strings("dawn/light_vln1", [vl], "vln1", -17.0, attack=0.9, release=1.2, players=6)
    S.mark("dawn_strings_end", pad_end)

    # felt piano: a slow rocking accompaniment under the flute
    pat = [["D2", "A2", "F#3", "E3"], ["B1", "F#2", "D3", "A2"], ["G1", "D2", "B2", "F#3"], ["A1", "E2", "D3", "C#3"]]
    pn = []
    for k, notes in enumerate(pat):
        for j, x in enumerate(notes):
            t = bar(k) + j * beat
            hold = (4 - j) * beat + 0.2
            if k == 3 and j == 2:          # the suspended 4th lets go when the third arrives
                hold = beat
            v = (0.36 if j == 0 else 0.24) * (1.12 if k == 2 else 1.0)
            pn.append(Note(t, hold, nm(x), v))
    pn.append(Note(bar(4), 3.2, nm("A1"), 0.22))
    pn.append(Note(bar(4) + 0.02, 3.0, nm("E2"), 0.16))
    S.piano("dawn/piano", pn, -11.0)

    # the flute: phrase a, tongued at bar starts and on the repeated D
    rows = theme([0, 1, 2, 3])
    shape = {0: 0.42, 1: 0.46, 2: 0.52, 3: 0.55, 4: [(0, 0.55), (0.6, 0.64), (1, 0.56)], 5: 0.52, 6: 0.48,
             7: [(0, 0.55), (0.7, 0.5), (1, 0.46)], 8: 0.44, 9: 0.42, 10: [(0, 0.44), (0.35, 0.40), (1, 0.08)]}
    fl = notes_from(rows, tm, lambda i, b, m: shape[i], tongue=(0, 7), legato=1.0)
    fl[-1].d = min(fl[-1].d, max(1.0, glow - fl[-1].t))
    S.flute("dawn/flute", fl, -15.5, vib_depth=0.004)

    # harp: the first ray of sun (Gmaj9 unfolding)
    hn = [Note(sun - 0.05 + 0.16 * k * (1 + 0.04 * k), 1.0, nm(x), 0.42 + 0.03 * k)
          for k, x in enumerate(["G2", "D3", "A3", "B3", "D4", "F#4", "A4", "B4"])]
    S.modal("dawn/harp_sun", I.harp, hn, -16.0, hall=0.45)

    # a faint thread of the dream into the near-silence: violin harmonic E6
    th0 = bar(3) + 2 * beat
    th1 = trem - 0.5
    if th1 - th0 > 1.0:
        S.strings("dawn/thread", [[Note(th0, th1 - th0, nm("E6"), [(0, 0.0), (0.25, 0.18), (0.8, 0.03), (1, 0.0)])]], "vln1", -29.0,
                  art="harm", attack=0.8, release=0.5, players=3)
    S.mark("near_silence", trem)


# ---------------------------------------------------------------------------- tremor
def tremor(S):
    C = S.C
    t_in, t_out = C.section("tremor", (C.get("tremor_start", 25.0), C.get("hand_presses_ground", 34.6) - 0.6))
    T0 = C.first("tremor_start", t_in)
    burst = C.first("birds_burst", T0 + 0.28 * (t_out - T0))
    lids = C.first("eye_lids_open", T0 + 0.69 * (t_out - T0))
    eyes = C.first("eyes_ignite", lids + 0.6)
    flee = C.first("small_bird_flees", eyes + 0.8)
    HP = C.first("hand_presses_ground", t_out + 0.6)
    mid = burst + 0.5 * (lids - burst)

    # D pedal: basses and cellos tremolo, rising out of nothing
    vel = [(0, 0.06), ((burst - T0) / (eyes + 0.6 - T0), 0.62), ((lids - T0) / (eyes + 0.6 - T0), 0.32), (1, 0.18)]
    S.strings("trem/cb", [[Note(T0, eyes + 0.6 - T0, nm("D2"), vel)]], "cb", -9.0, art="trem", attack=0.6, release=0.6)
    S.strings("trem/vc", [[Note(T0 + 0.4, eyes + 0.4 - T0, nm("D3"), vel)]], "vc", -12.0, art="trem", attack=0.8, release=0.5)
    # timpani roll into the birds' burst, a stroke on it
    if burst - T0 > 1.0:
        S.perc("trem/timp_roll", T0 + 0.3, I.timp_roll(burst - T0 - 0.3, nm("D2"), [(0, 0.05), (0.7, 0.35), (1, 0.7)],
                                                       rng_for("mus", "trem/roll")), -9.0)
    S.perc("trem/timp_burst", burst, I.timpani(nm("D2"), 0.9, rng_for("mus", "trem/tb")), -6.0)
    # the pulse: the core's heartbeat tempo, accelerating, low pizzicato
    hb = C.times("core_heartbeat")
    ibi = float(np.clip(hb[-1] - hb[-2], 0.6, 1.4)) if len(hb) >= 2 else 1.0
    t = T0 + ibi * 0.5
    k = 0
    pz = []
    while t < lids - 0.1:
        x = (t - T0) / max(0.1, lids - T0)
        pz.append(Note(t, 0.5, nm("D2") if k % 2 == 0 else nm("A1"), 0.35 + 0.45 * x))
        t += ibi * (1 - 0.48 * x)
        k += 1
    if pz:
        S.pizz("trem/pulse", pz, -8.0, section="cb", players=3, bright=0.3)
        S.pizz("trem/pulse_vc", [Note(n.t, n.d, n.m + 12, n.v) for n in pz], -13.0, section="vc", players=3)
    # burst: a stab on Bb/D, then the tremolo chords climb (Bb/D -> C/D)
    S.brass("trem/stab_hn", [[Note(burst, 0.55, nm(x), [(0, 0.95), (0.25, 0.5), (1, 0.15)])] for x in ("Bb3", "D4", "F4")],
            "horn", -8.0, attack=0.02, release=0.35)
    S.brass("trem/stab_tbn", [[Note(burst, 0.5, nm(x), [(0, 0.9), (0.3, 0.4), (1, 0.1)])] for x in ("Bb2", "F3")],
            "tbn", -12.0, attack=0.02, release=0.3)
    ch = voice_lines([(burst, mid - burst, [nm("Bb3"), nm("D4"), nm("F4")]), (mid, lids - mid, [nm("C4"), nm("E4"), nm("G4")])],
                     lambda tt_, kk: 0.45)
    for ln in ch:
        ln[0].v = [(0, 0.75), (0.15, 0.32), (1, 0.42)]
        ln[1].v = [(0, 0.45), (1, 0.6)]
    S.strings("trem/vla", ch, "vla", -12.0, art="trem", attack=0.03, release=0.25)
    hi = [Note(T0 + 1.2, burst - T0 - 1.2, nm("D5"), [(0, 0.0), (1, 0.3)], slur=True),
          Note(burst, mid - burst, nm("D5"), [(0, 0.55), (0.2, 0.35), (1, 0.45)], slur=True),
          Note(mid, lids - mid, nm("E5"), [(0, 0.45), (1, 0.62)], slur=True)]
    S.strings("trem/vln1", [[n for n in hi if n.d > 0.2]], "vln1", -14.0, art="trem", attack=0.4, release=0.2)
    # the lids open: suspense, a thin high harmonic; the eyes ignite: the shimmer
    S.strings("trem/susp", [[Note(lids, eyes - lids + 0.3, nm("A5"), [(0, 0.15), (1, 0.3)])]], "vln1", -18.0, art="harm",
              attack=0.15, release=0.3, players=4)
    gl = [Note(eyes + 0.035 * k * (1 + 0.03 * k), 1.0, m, 0.36 + 0.015 * k)
          for k, m in enumerate([nm(x) for x in ("D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6", "E6", "F#6", "A6")])]
    S.modal("trem/harp_gliss", I.harp, gl, -17.0, hall=0.5)
    S.modal("trem/celesta", I.celesta, [Note(eyes + 0.45 + 0.13 * k, 1, nm(x), 0.5) for k, x in enumerate(("A5", "D6", "F#6", "E6"))],
            -20.0, hall=0.5)
    shim_end = min(HP - 1.4, flee + 1.6)
    S.strings("trem/shimmer", [[Note(eyes + 0.1, shim_end - eyes, nm(x), [(0, 0.0), (0.15, 0.35), (1, 0.0)])] for x in ("D6", "A6", "E6")],
              "vln1", -19.0, art="harm", attack=0.3, release=0.6)
    S.brass("trem/hn_glow", [[Note(eyes + 0.1, shim_end - eyes, nm(x), [(0, 0.0), (0.3, 0.32), (1, 0.0)])] for x in ("D4", "F#4", "A4")],
            "horn", -17.0, attack=0.4, release=0.6)
    S.mark("eyes_shimmer", eyes)
    # anacrusis into the rise: low A swell
    a0 = max(shim_end - 0.4, HP - 2.0)
    S.strings("trem/anac_cb", [[Note(a0, HP - a0 + 0.1, nm("A1"), [(0, 0.05), (1, 0.6)])]], "cb", -9.0, attack=0.5, release=0.12)
    S.strings("trem/anac_vc", [[Note(a0 + 0.2, HP - a0 - 0.1, nm("A2"), [(0, 0.05), (1, 0.55)])]], "vc", -11.0, attack=0.5, release=0.12)


# ---------------------------------------------------------------------------- rise
def rise(S):
    C = S.C
    r_in, r_out = C.section("rise", (C.get("hand_presses_ground", 34.6) - 0.6, C.get("back_plates_open", 49.2) - 0.7))
    HP = C.first("hand_presses_ground", r_in + 0.6)
    ST = C.first("stands_full_thud", HP + 7.6)
    HL = C.first("head_lift_creak", ST + 1.8)
    ER = C.first("eyes_resolve", HL + 1.6)
    # slow and heavy: two bars of 4 if that stays under ~72 BPM, otherwise the same two bars
    # in a broad 3/4 (6 beats) so the giant never hurries
    nbt = 8 if (ST - HP) / 8 >= 0.83 else 6
    beat = fit_beat(ST - HP, nbt, 0.6, 1.3, "rise theme")
    tm = Tempo([(0, HP), (nbt, HP + nbt * beat)])
    S.mark("rise_theme", HP)
    S.mark("rise_tempo_bpm", 60.0 / beat)

    # the theme, phrase a in D minor, low: horns + cellos (+ violas from bar 2)
    rows = theme([0, 1], transpose=-12, minor=True)
    if nbt == 6:
        rows = [(b, d, m) for (b, d, m) in zip([0, 1, 2, 2.75, 3, 4.5, 5.5], [1, 1, 0.75, 0.25, 1.5, 1.0, 0.5], [r[2] for r in rows])]
    hv = lambda i, b, m: [(0, 0.62 + 0.04 * i), (1, 0.66 + 0.04 * i)]
    hn = notes_from(rows, tm, hv, tongue=(0, 4))
    hn.append(Note(ST, max(0.8, HL - ST), nm("D4"), [(0, 0.95), (0.3, 0.8), (1, 0.7)], slur=False))
    S.brass("rise/hn_theme", [hn], "horn", -5.0, attack=0.07, release=0.3)
    vc = [Note(n.t, n.d, n.m, n.v, slur=True) for n in hn]
    S.strings("rise/vc_theme", [vc], "vc", -9.0, attack=0.12, release=0.4, bright=0.2)
    # harmony: Dm(add9) | Bbmaj7 | (ST) Gm7 | (HL) Asus4 -> A | (ER) D major
    b1 = HP + (nbt // 2) * beat
    amid = HL + 0.5 * (ER - HL)
    low = [(HP, b1 - HP, "D1", "D2"), (b1, ST - b1, "Bb0", "Bb1"), (ST, HL - ST, "G0", "G1"), (HL, ER - HL, "A0", "A1"),
           (ER, max(1.5, r_out - ER), "D1", "D2")]
    cb = [Note(t, d, nm(b), [(0, 0.55 + 0.2 * (k == 2)), (1, 0.6)], slur=True) for k, (t, d, a, b) in enumerate(low)]
    cb[-1].v = [(0, 0.6), (0.4, 0.4), (1, 0.0)]
    S.strings("rise/cb", [cb], "cb", -6.0, attack=0.15, release=0.5)
    tuba = [Note(t, d * 0.97, nm(b), [(0, 0.5), (1, 0.62)] if k < 4 else [(0, 0.55), (1, 0.0)]) for k, (t, d, a, b) in enumerate(low)]
    S.brass("rise/tuba", [tuba], "tuba", -10.0, attack=0.1, release=0.4)
    tb = [(HP, b1 - HP, ["A2", "D3", "F3"]), (b1, ST - b1, ["F2", "Bb2", "D3"]), (ST, HL - ST, ["G2", "Bb2", "D3"]),
          (HL, amid - HL, ["A2", "D3", "E3"]), (amid, ER - amid, ["A2", "C#3", "E3"]), (ER, max(1.2, r_out - ER - 0.6), ["A2", "D3", "F#3"])]
    tl = voice_lines([(t, d, [nm(x) for x in ms]) for t, d, ms in tb], 0.5)
    for ln in tl:
        for k, nt in enumerate(ln):
            nt.v = [(0, 0.35), (0.7, 0.62), (1, 0.55)] if k < 2 else ([(0, 0.85), (0.3, 0.55), (1, 0.6)] if k == 2 else
                                                                     ([(0, 0.5), (1, 0.75)] if k < 5 else [(0, 0.7), (0.5, 0.4), (1, 0.0)]))
    S.brass("rise/tbn", tl, "tbn", -9.5, attack=0.08, release=0.35)
    # upper strings: sustained, swelling to the stand; violins rise with the head; F -> F# at the resolve
    vla = voice_lines([(HP, b1 - HP, [nm("A3"), nm("F4")]), (b1, ST - b1, [nm("A3"), nm("F4")]), (ST, HL - ST, [nm("Bb3"), nm("D4")]),
                       (HL, amid - HL, [nm("A3"), nm("D4")]), (amid, ER - amid, [nm("A3"), nm("C#4")]),
                       (ER, max(1.0, r_out - ER - 0.4), [nm("A3"), nm("F#4")])], 0.5)
    for ln in vla:
        for k, nt in enumerate(ln):
            nt.v = [(0, 0.3 + 0.12 * k), (1, 0.38 + 0.12 * k)] if k < 5 else [(0, 0.8), (0.5, 0.5), (1, 0.0)]
    S.strings("rise/vla", vla, "vla", -11.0, attack=0.5, release=0.6)
    v2 = [Note(b1, ST - b1, nm("D5"), [(0, 0.1), (1, 0.55)], slur=True), Note(ST, HL - ST, nm("D5"), [(0, 0.85), (0.4, 0.6), (1, 0.55)], slur=True),
          Note(HL, ER - HL, nm("E5"), [(0, 0.5), (1, 0.75)], slur=True), Note(ER, max(1.0, r_out - ER - 0.5), nm("F#5"), [(0, 0.85), (0.5, 0.45), (1, 0.0)], slur=True)]
    S.strings("rise/vln2", [v2], "vln2", -12.0, attack=0.6, release=0.6)
    seg = (ER - HL) / 4
    v1 = [Note(ST, HL - ST, nm("G5"), [(0, 0.8), (1, 0.55)], slur=True)]
    v1 += [Note(HL + k * seg, seg, nm(x), [(0, 0.5 + 0.08 * k), (1, 0.56 + 0.08 * k)], slur=True) for k, x in enumerate(("E5", "F5", "G5", "A5"))]
    v1 += [Note(ER, max(1.0, r_out - ER - 0.5), nm("A5"), [(0, 0.9), (0.5, 0.45), (1, 0.0)], slur=True)]
    S.strings("rise/vln1", [v1], "vln1", -12.0, attack=0.25, release=0.6)
    # the resolve: horns sing the opening motif in major
    rows = theme([0], transpose=0)[:3]
    rt = Tempo([(0, ER), (1, ER + 0.62)])
    hm = notes_from(rows, rt, 0.8, tongue=(0,))
    hm[-1].d = max(0.8, r_out - 0.8 - hm[-1].t)
    hm[-1].v = [(0, 0.85), (0.4, 0.55), (1, 0.0)]
    S.brass("rise/hn_resolve", [hm], "horn", -6.0, attack=0.06, release=0.5)
    S.mark("major_resolve", ER)
    # timpani and the stand
    rg = lambda k: rng_for("mus", "rise/timp", k)
    half = nbt // 2
    for k, (t, m, v) in enumerate([(HP, "D2", 0.9), (HP + (half - 1) * beat, "A1", 0.5), (b1, "F2", 0.75), (b1 + (half - 1) * beat, "F2", 0.5)]):
        S.perc("rise/timp%d" % k, t, I.timpani(nm(m), v, rg(k)), -6.0)
    S.perc("rise/timp_stand", ST, I.timpani(nm("G2"), 1.0, rg(9)), -4.0)
    S.perc("rise/bd_stand", ST, I.bass_drum(0.9, rg(10)), -13.0)
    S.perc("rise/tamtam", ST + 0.02, I.tamtam(0.8, rg(11), dur=min(7.0, r_out - ST + 2)), -15.0, hall=0.5)
    if ER - HL > 0.6:
        S.perc("rise/timp_roll", HL + 0.1, I.timp_roll(ER - HL - 0.1, nm("A1"), [(0, 0.15), (1, 0.75)], rg(12)), -8.0)
    S.perc("rise/timp_resolve", ER, I.timpani(nm("D2"), 0.8, rg(13)), -6.0)
    S.perc("rise/swell", ER - 1.2, I.cymbal_swell(1.2, rg(14)), -20.0, hall=0.4)
    # the canopy gap: a Lydian glow (E major over D) foreshadowing the flight key
    g0 = ER + 1.0
    if r_out - g0 > 1.0:
        S.strings("rise/glow", [[Note(g0, r_out - g0 + 0.8, nm(x), [(0, 0.0), (0.4, 0.3), (1, 0.12)])] for x in ("E6", "G#6", "B6")],
                  "vln1", -15.0, art="harm", attack=0.5, release=0.6)
        S.modal("rise/celesta_gap", I.celesta, [Note(g0 + 0.3 + 0.22 * k, 1, nm(x), 0.45 - 0.03 * k)
                                                for k, x in enumerate(("E6", "G#6", "B6", "E7", "B6", "G#6"))], -17.0, hall=0.55)
        S.modal("rise/harp_gap", I.harp, [Note(g0 + 0.15 + 0.09 * k, 1, nm(x), 0.35) for k, x in enumerate(("D3", "A3", "E4", "G#4", "B4", "E5"))],
                -15.0, hall=0.5)
    S.mark("canopy_glow", g0)


# ---------------------------------------------------------------------------- ignition
def ignition(S):
    C = S.C
    i_in, i_out = C.section("ignition", (C.get("back_plates_open", 49.2) - 0.7, C.get("impact_frame", 55.4)))
    EI = C.first("engine_ignite", i_in + 0.43 * (i_out - i_in))
    WR = C.first("wind_ring", EI + 0.5)
    IF = C.first("impact_frame", i_out)
    LS = C.first("launch_smear", IF - 0.2)
    sil = launch_silence(C)
    cut = sil[0] if sil else min(LS, IF - 0.12)
    S.mark("held_breath", (i_in, EI))
    S.mark("music_cut", cut)
    if sil:
        S.mark("launch_silence", sil)
    # held breath: one high harmonic over a breath of low D
    S.strings("ign/held", [[Note(i_in - 0.4, EI + 0.6 - i_in, nm("E6"), [(0, 0.12), (0.5, 0.2), (1, 0.05)])]], "vln1", -19.0,
              art="harm", attack=0.6, release=0.6, players=4)
    S.strings("ign/held_cb", [[Note(i_in, EI - i_in + 0.4, nm("D2"), [(0, 0.0), (0.5, 0.12), (1, 0.05)])]], "cb", -13.0,
              attack=1.0, release=0.5, players=3)
    # crescendo: C major, then D major, everything cut on the smear
    mid = EI + 0.55 * (cut - EI)
    run0 = max(mid + 0.2, cut - 1.25)
    cres = lambda a, b: [(0, a), (1, b)]
    for key, sec_, ms, g, art in (("cb", "cb", (("C2", "D2"),), -7.0, "trem"), ("vc", "vc", (("C3", "D3"), ("G3", "A3")), -10.0, "trem"),
                                  ("vla", "vla", (("E4", "F#4"), ("G4", "A4")), -12.0, "trem"), ("vln2", "vln2", (("C5", "D5"), ("E5", "F#5")), -13.0, "trem"),
                                  ("vln1", "vln1", (("G5", "A5"),), -13.0, "trem")):
        lines = []
        for a, b in ms:
            end1 = run0 if key in ("vln1", "vln2") else cut
            ln = [Note(EI, mid - EI, nm(a), cres(0.12, 0.55), slur=True), Note(mid, end1 - mid, nm(b), cres(0.55, 0.95), slur=True)]
            lines.append(ln)
        S.strings("ign/" + key, lines, sec_, g, art=art, attack=0.25, release=0.04)
    S.brass("ign/hn", voice_lines([(EI + 0.3, mid - EI - 0.3, [nm("C4"), nm("E4"), nm("G4")]), (mid, cut - mid, [nm("D4"), nm("F#4"), nm("A4")])],
                                  lambda t, k: [(0, 0.2), (1, 0.6)] if t < mid else [(0, 0.6), (1, 1.0)]), "horn", -7.0, attack=0.3, release=0.03)
    S.brass("ign/tbn", voice_lines([(EI + 0.6, mid - EI - 0.6, [nm("C3"), nm("G3")]), (mid, cut - mid, [nm("D3"), nm("A3")])],
                                   lambda t, k: [(0, 0.2), (1, 0.55)] if t < mid else [(0, 0.55), (1, 0.95)]), "tbn", -10.0, attack=0.3, release=0.03)
    rg = lambda k: rng_for("mus", "ign/timp", k)
    r1 = I.timp_roll(mid - EI, nm("C2"), [(0, 0.08), (1, 0.6)], rg(1))
    r2 = I.timp_roll(cut - mid, nm("D2"), [(0, 0.55), (1, 1.0)], rg(2))
    r2[sec(cut - mid):] *= np.exp(-np.arange(len(r2) - sec(cut - mid)) / sec(0.03))
    S.perc("ign/roll1", EI, r1, -9.0)
    S.perc("ign/roll2", mid, r2, -8.0)
    S.perc("ign/timp_ring", WR, I.timpani(nm("C2"), 0.85, rg(3)), -7.0)
    sw = I.cymbal_swell(cut - WR, rg(4))
    S.perc("ign/swell", WR, sw, -13.0, hall=0.3)
    # rising scale run in the violins (D major), accelerating into the cut
    scale = [nm(x) for x in ("D4", "E4", "F#4", "G4", "A4", "B4", "C#5", "D5", "E5", "F#5", "G5", "A5", "B5", "C#6", "D6", "E6")]
    nrun = len(scale)
    times = [run0 + (cut - run0) * (k / nrun) ** 0.8 for k in range(nrun)]
    run = [Note(times[k], (times[k + 1] if k + 1 < nrun else cut) - times[k], m, 0.55 + 0.4 * k / nrun, slur=True)
           for k, m in enumerate(scale)]
    S.strings("ign/run1", [run], "vln1", -11.0, art="sus", attack=0.02, release=0.03)
    S.strings("ign/run2", [[Note(n.t, n.d, n.m - 12, n.v, slur=True) for n in run]], "vln2", -13.0, attack=0.02, release=0.03)
    rc = I.reverse_cymbal(min(1.6, cut - EI), rg(5))
    S.perc("ign/revcym", cut - len(rc) / 48000.0, rc, -14.0, hall=0.25)


# ---------------------------------------------------------------------------- flight
def flight(S):
    C = S.C
    f_in, f_out = C.section("flight", (C.get("impact_frame", 55.4), C.get("trail_fades", 66.0) + 1.5))
    IF = C.first("impact_frame", f_in)
    SRv = C.get("sky_reveal", IF + 4.1)
    CB = C.first("canopy_burst", IF + 0.37 * (SRv - IF))
    TF = C.first("trail_fades", f_out - 1.5)
    E = 2                                            # the flight is a whole tone up: E major
    rg = lambda k: rng_for("mus", "flt", k)

    # the launch hit: E major tutti
    S.perc("flt/timp_hit", IF, I.timpani(nm("E2"), 1.0, rg(1)), -2.0)
    S.perc("flt/taiko", IF, I.taiko(1.0, rg(2)), -6.0, hall=0.5)
    S.perc("flt/bd", IF, I.bass_drum(1.0, rg(3)), -11.0)
    S.perc("flt/crash", IF, I.crash(1.0, rg(4)), -10.0, hall=0.35)
    sfz = lambda a: [(0, 1.0), (0.12, 0.45), (1, a)]
    S.brass("flt/hit_tbn", [[Note(IF, 1.6, nm(x), sfz(0.3))] for x in ("E2", "B2", "E3")], "tbn", -7.0, attack=0.015, release=0.3)
    S.brass("flt/hit_hn", [[Note(IF, 1.0, nm(x), sfz(0.25))] for x in ("E4", "G#4", "B4")], "horn", -7.0, attack=0.015, release=0.25)
    S.strings("flt/hit_str", [[Note(IF, 0.9, nm(x), sfz(0.2))] for x in ("E3", "B3", "G#4", "E5")], "vla", -8.0, attack=0.01, release=0.3)

    # phrase b, bars 4-5, launch -> sky reveal (slight broadening into the peak)
    nb = 8
    beat = fit_beat(SRv - IF, nb, 0.36, 0.75, "flight build")
    tm = Tempo(rit_anchors(0, nb, IF, SRv, ratio=1.18))
    rows = theme([4, 5], transpose=E)
    v = lambda i, b, m: [(0, 0.72 + 0.03 * i), (1, 0.78 + 0.03 * i)]
    mel = notes_from(rows, tm, v, tongue=(0, 4))
    S.strings("flt/b_vln1", [[Note(n.t, n.d, n.m + 12, n.v, slur=n.slur) for n in mel]], "vln1", -8.0, attack=0.06, release=0.2, bright=0.2)
    S.strings("flt/b_vln2", [mel], "vln2", -9.0, attack=0.06, release=0.2)
    S.brass("flt/b_hn", [[Note(n.t, n.d, n.m - 12, n.v, slur=n.slur) for n in mel]], "horn", -6.0, attack=0.05, release=0.2)
    bar5 = tm(4)
    # harmony: F#m7 | D (bVII) ; driving spiccato eighths in the low strings
    S.brass("flt/b_tbn", voice_lines([(IF + 0.5, bar5 - IF - 0.5, [nm("F#2"), nm("C#3"), nm("A3")]), (bar5, SRv - bar5, [nm("D2"), nm("A2"), nm("F#3")])],
                                     lambda t, k: [(0, 0.35), (1, 0.6)] if t < bar5 else [(0, 0.55), (1, 0.85)]), "tbn", -11.0, attack=0.2, release=0.1)
    eighths = []
    for k in range(nb * 2):
        t = tm(k * 0.5)
        root = nm("F#2") if k < 8 else nm("D2")
        eighths.append(Note(t, tm.dur(k * 0.5, 0.5) * 0.7, root if k % 2 == 0 else root + 12, 0.55 + 0.25 * (k % 4 == 0) + 0.01 * k))
    S.strings("flt/ost_vc", [eighths], "vc", -9.0, art="spicc")
    lowest = nm("E1")                   # keep the basses out of the deep sub (no D1)
    S.strings("flt/ost_cb", [[Note(n.t, n.d, n.m - 12 if n.m - 12 >= lowest else n.m, n.v) for n in eighths[::2]]], "cb", -9.0, art="spicc")
    vla = []
    for k in range(nb * 2):
        t = tm(k * 0.5)
        tones = (nm("A3"), nm("C#4"), nm("E4"), nm("C#4")) if k < 8 else (nm("A3"), nm("D4"), nm("F#4"), nm("D4"))
        vla.append(Note(t, tm.dur(k * 0.5, 0.5) * 0.65, tones[k % 4], 0.5 + 0.02 * k))
    S.strings("flt/ost_vla", [vla], "vla", -13.0, art="spicc")
    for k, b in enumerate((0, 2, 4, 6)):
        S.perc("flt/timp_b%d" % k, tm(b), I.timpani(nm("F#2") if b < 4 else nm("D2"), 0.6 + 0.08 * k, rg(10 + k)), -9.0)
    S.perc("flt/crash_canopy", CB, I.crash(0.8, rg(20)), -13.0, hall=0.35)
    S.perc("flt/timp_canopy", CB, I.timpani(nm("F#2") if CB < bar5 else nm("D2"), 0.9, rg(21)), -7.0)
    # into the sky: harp glissando and a cymbal swell landing on the peak
    hg = [nm(x) for x in ("B3", "C#4", "E4", "F#4", "G#4", "A4", "B4", "C#5", "E5", "F#5", "G#5", "A5", "B5", "C#6")]
    S.modal("flt/harp_up", I.harp, [Note(SRv - 0.55 + 0.55 * (k / len(hg)) ** 0.85, 1, m, 0.5) for k, m in enumerate(hg)], -10.0, hall=0.45)
    S.perc("flt/swell_peak", SRv - 1.3, I.cymbal_swell(1.3, rg(22)), -15.0, hall=0.3)

    # THE PEAK: bars 6-8 on sky_reveal
    end_t = min(TF - 0.5, f_out - 1.6)
    pb = fit_beat(end_t - SRv, 8, 0.5, 0.95, "flight peak")
    tp = Tempo(rit_anchors(0, 8, SRv, SRv + 8 * pb, ratio=1.12))
    rows = theme([6, 7, 8], transpose=E)
    pv = lambda i, b, m: [(0, 0.95), (0.5, 0.9), (1, 0.85)] if i == 0 else [(0, 0.8), (1, 0.78)]
    pk = notes_from(rows, tp, pv, tongue=(0, 3))
    fin = pk[-1]
    fin.d = max(2.5, f_out + 1.2 - fin.t)
    fin.v = [(0, 0.8), (0.3, 0.6), (1, 0.0)]
    S.mark("theme_peak", pk[0].t)
    S.strings("flt/pk_vln1", [[Note(n.t, n.d, n.m + 12, n.v, slur=n.slur) for n in pk]], "vln1", -7.5, attack=0.05, release=0.6, bright=0.25)
    S.strings("flt/pk_vln1b", [pk], "vln1", -9.5, attack=0.05, release=0.6, players=6)
    S.flute("flt/pk_flute", [Note(n.t, n.d, n.m + 12, n.v, slur=n.slur) for n in pk[:-1]] + [Note(fin.t, min(2.0, fin.d), fin.m + 12, [(0, 0.7), (1, 0.0)])],
            -14.0, hall=0.4, pan=-0.2, brightness=0.6)
    S.modal("flt/glock_peak", I.glock, [Note(SRv, 1, nm("C#7"), 0.6), Note(tp(4), 1, nm("F#6"), 0.4), Note(tp(8), 1, nm("E6"), 0.4)], -13.0, hall=0.5)
    b7, b7m, b8 = tp(4), tp(6), tp(8)
    harm = [(SRv, b7 - SRv, ["A1", "A2", "E3", "C#4", "E4", "G#4"]), (b7, b7m - b7, ["G#1", "G#2", "D#3", "B3", "F#4", "B4"]),
            (b7m, b8 - b7m, ["B1", "B2", "F#3", "A3", "E4", "A4"]), (b8, fin.d, ["E2", "B2", "E3", "G#3", "E4", "B4"])]
    hl = voice_lines([(t, d, [nm(x) for x in ms]) for t, d, ms in harm], 0.7)
    for ln in hl:
        ln[0].v = [(0, 0.9), (1, 0.75)]
        ln[-1].v = [(0, 0.75), (0.35, 0.55), (1, 0.0)]
    S.strings("flt/pk_cb", [hl[0]], "cb", -8.0, attack=0.1, release=0.8)
    S.strings("flt/pk_vc", [hl[1], hl[2]], "vc", -8.0, attack=0.1, release=0.8)
    S.strings("flt/pk_vla", [hl[3], hl[4]], "vla", -10.0, attack=0.12, release=0.8)
    S.strings("flt/pk_vln2", [hl[5]], "vln2", -10.0, attack=0.12, release=0.8)
    hh = voice_lines([(SRv, b7 - SRv, [nm("A3"), nm("C#4"), nm("E4")]), (b7, b7m - b7, [nm("G#3"), nm("B3"), nm("D#4")]),
                      (b7m, b8 - b7m, [nm("A3"), nm("B3"), nm("E4")]), (b8, min(3.0, fin.d), [nm("G#3"), nm("B3"), nm("E4")])], 0.8)
    for ln in hh:
        ln[-1].v = [(0, 0.75), (1, 0.0)]
    S.brass("flt/pk_hn", hh, "horn", -6.5, attack=0.08, release=0.5)
    tbl = voice_lines([(SRv, b7 - SRv, [nm("A2"), nm("E3")]), (b7, b7m - b7, [nm("G#2"), nm("D#3")]), (b7m, b8 - b7m, [nm("B2"), nm("F#3")]),
                       (b8, min(3.0, fin.d), [nm("E2"), nm("B2")])], 0.7)
    for ln in tbl:
        ln[-1].v = [(0, 0.7), (1, 0.0)]
    S.brass("flt/pk_tbn", tbl, "tbn", -11.0, attack=0.1, release=0.5)
    S.brass("flt/pk_tuba", [[Note(t, d * 0.98, nm(ms[0]) + 12, 0.6 if t < b8 else [(0, 0.6), (1, 0.0)]) for t, d, ms in harm[:3]] +
                            [Note(b8, min(3.0, fin.d), nm("E2"), [(0, 0.6), (1, 0.0)])]], "tuba", -10.0, attack=0.1, release=0.5)
    S.perc("flt/timp_peak", SRv, I.timpani(nm("A2"), 1.0, rg(30)), -4.0)
    S.perc("flt/crash_peak", SRv, I.crash(0.9, rg(31)), -11.0, hall=0.35)
    S.perc("flt/timp_b7", b7, I.timpani(nm("G#2"), 0.6, rg(32)), -9.0)
    S.perc("flt/timp_b7m", b7m, I.timpani(nm("F#2"), 0.7, rg(33)), -9.0)
    if b8 - b7m > 0.8:
        S.perc("flt/roll_end", b7m + 0.3, I.timp_roll(b8 - b7m - 0.3, nm("F#2"), [(0, 0.2), (1, 0.6)], rg(34)), -11.0)
    S.perc("flt/timp_home", b8, I.timpani(nm("E2"), 0.8, rg(35)), -7.0)
    S.perc("flt/crash_home", b8, I.crash(0.6, rg(36)), -16.0, hall=0.4)
    # the trail of light: soft celesta/glockenspiel sparkles in E pentatonic, thinning out
    pent = [nm(x) for x in ("E6", "F#6", "G#6", "B6", "C#7", "E7", "F#7")]
    r = rg(40)
    t = SRv + 0.35
    sp = []
    while t < TF + 0.8:
        x = (t - SRv) / max(0.5, TF + 0.8 - SRv)
        sp.append(Note(t, 1, pent[int(r.integers(len(pent)))], 0.3 * (1 - 0.6 * x) + 0.05))
        t += r.exponential(0.16 + 0.35 * x)
    S.modal("flt/sparkle", I.celesta, sp, -17.0, hall=0.6)
    S.mark("flight_home", b8)


# ---------------------------------------------------------------------------- coda
def coda(S):
    C = S.C
    c_in, c_out = C.section("coda", (C.get("trail_fades", 66.0) + 1.5, C.duration))
    BR = C.first("bird_returns", c_in + 3.0)
    FO = C.first("fade_out_start", c_out - 2.5)
    END = C.duration
    E = 2
    # a soft E(add9) bed that the flight's last chord dissolves into
    pad = [[Note(c_in - 0.8, END - c_in + 0.8, nm(x), [(0, 0.0), (0.15, 0.2), (0.7, 0.16), (1, 0.08)])] for x in ("E3", "B3", "F#4", "G#4")]
    S.strings("coda/pad", pad[:2], "vc", -15.0, attack=1.5, release=1.0)
    S.strings("coda/pad_hi", pad[2:], "vla", -17.0, attack=1.5, release=1.0)
    S.strings("coda/harm", [[Note(c_in + 1.0, END - c_in - 1.0, nm("B5"), [(0, 0.0), (0.3, 0.18), (1, 0.1)])]], "vln1", -22.0,
              art="harm", attack=1.2, release=0.8, players=3)
    # piano alone: the opening motif in E, reaching the open third; IV under it, then I
    start = c_in + 0.35
    beat = fit_beat(min(BR + 0.5, FO - 1.4) - start, 4, 0.62, 1.0, "coda")
    tm = Tempo([(0, start), (4, start + 4 * beat)])
    rows = theme([0, 1], transpose=E)[:5]
    rh = notes_from(rows, tm, lambda i, b, m: [0.44, 0.4, 0.47, 0.4, 0.52][i], slur_all=False)
    top = rh[-1]
    top.d = END - top.t
    lh = [Note(tm(0), tm.dur(0, 4), nm("E2"), 0.3), Note(tm(1), tm.dur(1, 3), nm("B2"), 0.22), Note(tm(2), tm.dur(2, 2), nm("E3"), 0.2),
          Note(tm(4), 1.7 * beat, nm("A2"), 0.26), Note(tm(4.4), 1.3 * beat, nm("E3"), 0.2), Note(tm(4.8), 0.9 * beat, nm("C#4"), 0.18)]
    fin = tm(4) + 1.7 * beat
    lh += [Note(fin, END - fin, nm("E2"), 0.24), Note(fin + 0.05, END - fin, nm("B2"), 0.18), Note(fin + 0.1, END - fin, nm("G#3"), 0.16)]
    S.piano("coda/piano", rh + lh, -2.0)
    S.mark("coda_open_third", top.t)
    # the music box answers once, very softly: the dream remembered
    mbt = max(fin + 0.9, FO + 0.2)
    if mbt < END - 1.0:
        S.modal("coda/musicbox", I.musicbox, [Note(mbt, 1, nm("G#6"), 0.4), Note(mbt + 0.02, 1, nm("E6"), 0.25)], -24.0, hall=0.6)


SECTION_FUNCS = {"dawn": dawn, "tremor": tremor, "rise": rise, "ignition": ignition, "flight": flight, "coda": coda}


def render_music(cues, irs):
    S = Score(cues)
    for name in cues.sections:
        if name not in SECTION_FUNCS:
            warn("music section '%s' has no composition; ignored" % name)
    for name, fn in SECTION_FUNCS.items():
        if name in cues.sections:
            S.trim = SECTION_TRIM.get(name, 0.0)
            fn(S)
        else:
            warn("music section '%s' missing from cues.json; skipped" % name)
    out = S.bus.render(irs)
    return out, S.bus.log, S.marks
