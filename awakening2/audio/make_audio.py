#!/usr/bin/env python3
"""
make_audio.py -- the complete, fully synthesized soundtrack for "Awakening II".

Everything is timed from cues.json (duration, shots, events, music sections): retime the
film by editing that file and run this script again.  Nothing here is a sample, a model
or a recording: oscillators, filtered noise, modal resonators and convolution with
synthetic impulse responses, all seeded (one generator per named cue).

    python3 make_audio.py                 # render mix.wav + stems + spectrogram.png, print checks
    python3 make_audio.py --no-ffmpeg     # skip the ffmpeg ebur128 cross-check
    python3 make_audio.py --workers 1     # single process (default 2)
    python3 make_audio.py --cues other.json --out /some/dir

Modules: aw2_core (DSP core, cue loader, bus, reverbs), aw2_instruments (the orchestra),
aw2_score (the theme and the cue-fitted score), aw2_fx (effects and ambience),
aw2_analysis (meters, checks, spectrogram).  This file mixes and masters.

History: started from awakening/audio/make_audio.py (the first film's generator); its
filters, bus, IR design, BS.1770 meter, compressor and limiter live on in the modules.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import multiprocessing as mp
import subprocess
import sys
import time
import wave
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from scipy import signal
from scipy.ndimage import minimum_filter1d

import aw2_analysis as A
from aw2_core import (SR, Cues, base_name, cos_ramp, db, hp, launch_silence, lp, rng_for, sec, shelf, standard_irs, to_db,
                      warmup_kernels, warn)

TARGET_LUFS = -17.0
TP_MAX = -1.0                 # dBTP, hard requirement
TP_CEIL = -1.35               # limiter ceiling on the 4x true-peak estimate
STEM_GAIN = {"music": 0.0, "fx": 8.0, "amb": 9.0}      # dB, applied before the master
PRE_LUFS = -20.0              # the summed stems are brought here before the compressor
KNOWN_TRANSIENTS = {"bird_wings_flare", "bird_touchdown", "bird_hop", "bird_chirp", "core_flicker", "core_heartbeat",
                    "birds_burst", "eye_lids_open", "eyes_ignite", "small_bird_flees", "hand_presses_ground", "rise_groan",
                    "roots_tear", "stands_full_thud", "head_lift_creak", "back_plates_open", "crouch_anticipation",
                    "engine_sputter", "engine_ignite", "wind_ring", "impact_frame", "canopy_burst", "bird_returns", "sun_spark"}


# ============================================================================ workers
def _job(kind, cues_path):
    t0 = time.time()
    warmup_kernels()
    C = Cues(cues_path)
    irs = standard_irs()
    if kind == "music":
        from aw2_score import render_music
        out, log, marks = render_music(C, irs)
        return kind, out.astype(np.float32), log, marks, time.time() - t0
    from aw2_fx import render_fx
    fx, amb, log, onsets = render_fx(C, irs, warn_unknown=False)     # validate_cues() already warned
    return kind, (fx.astype(np.float32), amb.astype(np.float32)), log, onsets, time.time() - t0


def render_all(cues_path, workers):
    res = {}
    if workers > 1:
        ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=2, mp_context=ctx) as ex:
            futs = [ex.submit(_job, k, cues_path) for k in ("music", "fx")]
            for f in futs:
                r = f.result()
                res[r[0]] = r
    else:
        for k in ("music", "fx"):
            r = _job(k, cues_path)
            res[k] = r
    return res


# ============================================================================ master
def stem_prep(x, kind):
    """Clean the low end of a stem: 25 Hz high-pass (DC, subsonics), bass to mono below
    ~120 Hz (side channel high-passed), and a gentle shelf under 45 Hz on the effects."""
    x = hp(x.astype(np.float64), 28.0, 4)
    m = 0.5 * (x[:, 0] + x[:, 1])
    s = hp(0.5 * (x[:, 0] - x[:, 1]), 120.0, 2)
    x = np.stack([m + s, m - s], 1)
    if kind == "fx":
        x = shelf(x, 50.0, -4.0, "low")
    return x


def automation(C, n):
    """Cue-driven stem rides: the music makes room for the launch blast, the ambience
    ducks under the launch roar; returns per-stem gain curves (linear)."""
    t = np.arange(n) / SR
    imp = C.first("impact_frame")
    canopy = C.first("canopy_burst", (imp or 0) + 1.5)
    g = {k: np.ones(n) for k in ("music", "fx", "amb")}
    if imp is not None:
        g["music"] *= db(np.interp(t, [imp - 0.01, imp + 0.05, imp + 0.6, max(imp + 1.0, canopy)], [0, -3.5, -3.0, 0]))
        g["amb"] *= db(np.interp(t, [imp - 0.3, imp, imp + 3.0, imp + 4.0], [0, -6, -6, 0]))
    sil = launch_silence(C)
    if sil is not None:                                   # the held breath: true silence, tails included
        a, b = sil
        gate = np.ones(n)
        i0, i1, i2 = sec(a), sec(a + 0.05), sec(b) - sec(0.003)
        gate[i0:i1] = cos_ramp(i1 - i0)[::-1]
        gate[i1:i2] = 0.0
        gate[i2:sec(b)] = cos_ramp(sec(b) - i2)
        for k in g:
            g[k] *= gate
    return g


def fades(C, n):
    """Picture fades: in from fade_in_start, out from fade_out_start to the end."""
    t = np.arange(n) / SR
    g = np.ones(n)
    fi = C.first("fade_in_start")
    if fi is not None:
        fin_len = 1.6
        x = np.clip((t - fi) / fin_len, 0, 1)
        g *= 0.5 - 0.5 * np.cos(np.pi * x)
    fo = C.first("fade_out_start")
    end = C.first("end", C.duration)
    if fo is not None:
        x = np.clip((t - fo) / max(0.1, min(end, C.duration) - fo), 0, 1)
        g *= 0.5 + 0.5 * np.cos(np.pi * x)
    g[-1] = 0.0
    return g


def compressor_gain(x, thresh_db=-20.0, ratio=1.7, knee_db=8.0, attack_ms=25.0, release_ms=350.0, hop_ms=1.0):
    """Gentle stereo-linked RMS compressor; returns the gain curve (linear) and max GR (dB)."""
    hop = sec(hop_ms / 1000)
    n = len(x)
    nb = n // hop
    fr = (x[: nb * hop] ** 2).mean(axis=1).reshape(nb, hop).mean(axis=1)
    fr = signal.lfilter([0.05], [1, -0.95], fr)                       # ~20 ms RMS window
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
    g = np.interp(np.arange(n), (np.arange(nb) + 0.5) * hop, db(-sm))
    return g, float(sm.max())


def limiter_gain(x, ceiling_db=TP_CEIL, lookahead_ms=3.0, hold_ms=30.0, release_ms=180.0):
    """True-peak look-ahead limiter gain: required gain from the 4x-oversampled peak
    estimate, running minimum over +-hold, Hann smoothing over +-lookahead (never above the
    requirement), one-pole release."""
    ceil = db(ceiling_db)
    pk = A.tp_envelope(x)
    greq = np.minimum(1.0, ceil / np.maximum(pk, 1e-9))
    la = sec(lookahead_ms / 1000)
    hold = max(sec(hold_ms / 1000), la)
    gmin = minimum_filter1d(greq, size=2 * hold + 1, mode="nearest")
    w = np.hanning(2 * la + 1)
    w /= w.sum()
    gs = signal.fftconvolve(np.pad(gmin, la, mode="edge"), w, mode="same")[la:-la]
    gs = np.minimum(gs, greq)
    a = np.exp(-1.0 / (release_ms / 1000 * SR))
    rel, _ = signal.lfilter([1 - a], [1, -a], gs, zi=[a * gs[0]])
    return np.minimum(gs, rel)


def write_wav24(path, x, seed_key):
    rng = rng_for("dither", seed_key)
    d = (rng.random(x.shape) - rng.random(x.shape)) / 8388608.0         # TPDF, +-1 LSB of 24 bit
    y = np.clip(x + d, -1.0, 1.0 - 1.0 / 8388608.0)
    q = np.round(y * 8388607.0).astype("<i4")
    b = q.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    tmp = path + ".part"                         # atomic: readers never see a half-written file
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(3)
        w.setframerate(SR)
        w.writeframes(b)
    os.replace(tmp, path)


def ffmpeg_check(path):
    try:
        r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
    except Exception as exc:
        print("ffmpeg verification skipped:", exc)
        return None
    txt = r.stderr
    i = txt.rfind("Summary:")
    s = txt[i:].rstrip() if i >= 0 else txt[-1500:]
    print("\nffmpeg ebur128 summary:\n" + s)
    return s


# ============================================================================ checks
def validate_cues(C):
    from aw2_fx import HANDLERS, SILENT
    known = set(HANDLERS) | SILENT
    bad = 0
    for t, n in C.events:
        if base_name(n) not in known:
            warn("cues.json: unknown event name '%s' (%.2f s) will be ignored" % (n, t))
        if not 0.0 <= t <= C.duration:
            warn("cues.json: event '%s' at %.2f s is outside 0..%.2f" % (n, t, C.duration))
            bad += 1
    e = C.first("end")
    if e is not None and abs(e - C.duration) > 1e-6:
        warn("cues.json: 'end' event at %.3f differs from duration %.3f; using duration" % (e, C.duration))
    for s in C.shots:
        if s["out"] <= s["in"]:
            warn("cues.json: shot %s has out <= in" % s.get("id"))
    return bad


def event_report(C, fx_out, logs):
    """For every cue: what its handler placed, where the loudest placed sound's energy
    actually starts (first sample above -20 dB of its peak) relative to the cue, and the
    nearest spectral-flux onset in the rendered effects stem (+ its strength vs the
    local median)."""
    times, flux = A.onset_strength(fx_out)
    print("\nEVENT CHECK (frames at %g fps; 'sound' = energy onset of the loudest sound placed for the cue;"
          " 'heard' = nearest flux onset in the effects stem, x local median)" % C.fps)
    print("  %-22s %7s %6s  %-8s %-14s  %s" % ("event", "time", "frame", "sound", "heard", "placed by the handler"))
    n_ok = n_tr = 0
    for te, name in C.events:
        b = base_name(name)
        if b in ("fade_in_start", "fade_out_start", "end"):
            print("  %-22s %7.2f %6d  %-8s %-14s  %s" % (name, te, C.frame(te), "-", "-", "master fade" if b != "end" else "file end"))
            continue
        placed = sorted([x for x in logs if abs(x[4] - te) < 1e-6], key=lambda x: -x[3])
        named = [x for x in placed if x[2]]
        desc = ", ".join("%s (%.0f dB)" % (x[2].lstrip("*"), x[3]) for x in named[:3]) + (" +%d" % (len(placed) - min(3, len(named))) if len(placed) > 3 else "")
        sync = [x for x in placed if x[2].startswith("*")]
        main = sync[0] if sync else (placed[0] if placed else None)
        son = "%+.0f ms" % ((main[5] - te) * 1000) if main else "-"
        off, strength = A.event_onset(times, flux, te)
        heard = "%+.0f ms x%.1f" % (off * 1000, strength) if off is not None else "-"
        flag = ""
        if b in KNOWN_TRANSIENTS:
            n_tr += 1
            if main and -0.005 <= main[5] - te <= 1.0 / C.fps:
                n_ok += 1
            else:
                flag = "  <-- check"
        print("  %-22s %7.2f %6d  %-8s %-14s  %s%s" % (name, te, C.frame(te), son, heard, desc or "(nothing placed)", flag))
    print("  transient cues whose main sound starts within one frame of the cue: %d / %d" % (n_ok, n_tr))
    return n_ok, n_tr


def music_sync_report(C, music, marks, mix):
    print("\nMUSIC SYNC")
    lv = lambda a, b: to_db(np.sqrt(np.mean(music[sec(max(0, a)):sec(min(C.duration, b))] ** 2)) + 1e-12)
    sr_ = C.first("sky_reveal")
    if "theme_peak" in marks and sr_ is not None:
        print("  theme peak (C#6 over Amaj7) at %.3f s; sky_reveal %.3f s (diff %+.0f ms)" % (marks["theme_peak"], sr_, 1000 * (marks["theme_peak"] - sr_)))
    if "sun_peak" in marks:
        print("  dawn: phrase b's peak (B5 over Gmaj7) at %.3f s, sun_ray_reaches_face %.3f s; its resolution at %.3f s, first core_flicker %s" % (
            marks["sun_peak"], C.first("sun_ray_reaches_face", -1), marks.get("dawn_resolution", -1), C.first("core_flicker")))
    sr_, cut, _ = C.sky_split()
    if cut is not None:
        print("  sky split: tracking shot %.2f-%.2f s (ostinato until %.2f), wide shot from %.2f s" % (sr_, cut, marks.get("ostinato_until", -1), cut))
    if C.spark_time() is not None:
        print("  spark (robot crosses the sun) at %.2f s%s; the theme resolves at %.2f s" % (
            C.spark_time(), "" if C.first("sun_spark") is not None else " (derived: end of the flight section - 0.5 s)", marks.get("flight_home", -1)))
    ts = C.first("tremor_start")
    if ts is not None:
        print("  near-silence before the tremor: music RMS %.1f dBFS over %.1f-%.1f s (dawn average %.1f)" % (
            lv(ts - 1.0, ts), ts - 1.0, ts, lv(C.section("dawn", (0, ts))[0] + 3, ts - 3)))
    if "held_breath" in marks:
        a, b = marks["held_breath"]
        print("  held breath %.1f-%.1f s: music RMS %.1f dBFS (crescendo after it %.1f)" % (a, b, lv(a, b), lv(b + 1.0, marks.get("music_cut", b + 3))))
    if "launch_silence" in marks:
        a, b = marks["launch_silence"]
        seg = mix[sec(a + 0.05):sec(b) - sec(0.003)]
        print("  held-breath silence before the launch: %.2f-%.2f s (%.0f ms), mix peak %.0f dBFS inside it" % (
            a, b, 1000 * (b - a), to_db(np.abs(seg).max()) if len(seg) else -999))
    if "music_cut" in marks:
        imp = C.first("impact_frame", marks["music_cut"] + 0.2)
        print("  cut before the launch: %.2f-%.2f s music RMS %.1f dBFS (the 0.5 s before %.1f)" % (
            marks["music_cut"] + 0.05, imp, lv(marks["music_cut"] + 0.05, imp), lv(marks["music_cut"] - 0.5, marks["music_cut"])))
    if "rise_tempo_bpm" in marks:
        print("  rise theme tempo %.0f BPM (slow and heavy: 2 bars of 4, or of 3 when the span is short)" % marks["rise_tempo_bpm"])
    for k in ("flute_start", "musicbox", "rise_theme", "major_resolve", "canopy_glow", "flight_home", "coda_open_third"):
        if k in marks:
            print("  %-16s %.2f s" % (k, marks[k]))


# ============================================================================ main
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--cues", default=os.path.join(HERE, "cues.json"))
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--no-ffmpeg", action="store_true")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    t_start = time.time()
    C = Cues(args.cues)
    print("cues: %s  duration %.3f s, %d shots, %d events, sections: %s" % (
        args.cues, C.duration, len(C.shots), len(C.events), ", ".join("%s %.1f-%.1f" % (k, a, b) for k, (a, b) in C.sections.items())))
    validate_cues(C)
    res = render_all(args.cues, max(1, min(2, args.workers)))
    _, music, mlog, marks, t_m = res["music"]
    _, (fx, amb), flog, onsets, t_f = res["fx"]
    print("rendered: music %.1f s, effects+ambience %.1f s (wall %.1f s)" % (t_m, t_f, time.time() - t_start))
    n = C.n
    stems = {"music": stem_prep(music, "music"), "fx": stem_prep(fx, "fx"), "amb": stem_prep(amb, "amb")}
    auto = automation(C, n)
    for k in stems:
        stems[k] *= (db(STEM_GAIN[k]) * auto[k])[:, None]
    mix = stems["music"] + stems["fx"] + stems["amb"]
    gf = fades(C, n)
    l0 = A.integrated_lufs(mix * gf[:, None])
    gf = gf * db(PRE_LUFS - l0)
    pre = mix * gf[:, None]
    print("pre-master: summed stems %.1f LUFS, normalised to %.1f (peak %.1f dBFS)" % (l0, PRE_LUFS, to_db(np.abs(pre).max())))
    gc, grmax = compressor_gain(pre)
    comp = pre * gc[:, None]
    G = 1.0
    for _ in range(5):
        gl = limiter_gain(comp * G)
        G *= db(TARGET_LUFS - A.integrated_lufs(comp * G * gl[:, None]))
    gl = limiter_gain(comp * G)
    total = gf * gc * G * gl
    out = mix * total[:, None]
    tp = A.true_peak(out)
    if tp > TP_MAX - 0.1:
        trim = db(TP_MAX - 0.1 - tp)
        total *= trim
        out *= trim
        tp = A.true_peak(out)
    for k in stems:
        stems[k] = stems[k] * total[:, None]
    lufs = A.integrated_lufs(out)
    lra, lra_lo, lra_hi = A.loudness_range(out)
    print("master: compressor max %.1f dB, gain %+.1f dB, limiter max %.1f dB at %.2f s" % (grmax, to_db(G), -to_db(gl.min()), np.argmin(gl) / SR))
    os.makedirs(args.out, exist_ok=True)
    write_wav24(os.path.join(args.out, "mix.wav"), out, "mix")
    for k, v in stems.items():
        write_wav24(os.path.join(args.out, k + ".wav"), v, k)
    print("wrote mix.wav, music.wav, fx.wav, amb.wav to %s (%d samples = %.3f s, 48 kHz, 24-bit PCM stereo)" % (args.out, n, n / SR))

    # ------------------------------------------------------------------ reports
    print("\nLOUDNESS: integrated %.2f LUFS, true peak %.2f dBTP, sample peak %.2f dBFS, LRA %.1f LU (%.1f .. %.1f)" % (
        lufs, tp, to_db(np.abs(out).max()), lra, lra_lo, lra_hi))
    print("stems (integrated): music %.1f, effects %.1f, ambience %.1f LUFS" % tuple(A.integrated_lufs(stems[k]) for k in ("music", "fx", "amb")))
    rows = A.per_second(out, stems, C.duration)
    print("\nPER SECOND  (mix momentary LUFS over the whole second, RMS, sample peak, L/R correlation, side-mid dB; stem LUFS)")
    print("   s    LUFS    RMS   peak  corr   S-M | music    fx   amb | shot")
    for r in rows:
        sh = C.shot_at(r["s"] + 0.5)
        bar = "#" * int(max(0, (r["lufs"] + 50) / 2))
        print("%4d  %6.1f %6.1f %6.1f %5.2f %5.1f | %5.1f %5.1f %5.1f | %-4s %s" % (
            r["s"], r["lufs"], r["rms"], r["peak"], r["corr"], r["sm"], r["music"], r["fx"], r["amb"], sh["id"] if sh else "", bar))
    print("\nSECTIONS (mean momentary LUFS of the mix)")
    for k, (a, b) in C.sections.items():
        sel = [r["lufs"] for r in rows if a <= r["s"] + 0.5 < b]
        print("  %-9s %5.1f-%5.1f s  %6.1f LUFS  (min %.1f, max %.1f)" % (k, a, b, 10 * np.log10(np.mean(10 ** (np.array(sel) / 10))), min(sel), max(sel)))
    # sub-bass share
    low = lp(out.mean(axis=1), 60, 4)
    print("\nSUB-BASS: energy below 60 Hz is %.1f dB relative to full band (whole film); loudest second %.1f dB" % (
        10 * np.log10(np.mean(low ** 2) / np.mean(out.mean(axis=1) ** 2)),
        max(10 * np.log10(np.mean(low[s * SR:(s + 1) * SR] ** 2) / (np.mean(out.mean(axis=1)[s * SR:(s + 1) * SR] ** 2) + 1e-20) + 1e-20)
            for s in range(int(C.duration)))))
    # stereo: correlation and mono fold-down
    mono = np.repeat(out.mean(axis=1, keepdims=True), 2, axis=1)
    corr_s = [r["corr"] for r in rows if r["rms"] > -60]
    print("\nSTEREO: overall L/R correlation %.2f (per second min %.2f, median %.2f); mono fold-down changes integrated loudness by %+.1f dB" % (
        A.correlation(out), min(corr_s), float(np.median(corr_s)), A.integrated_lufs(mono) - lufs))
    # integrity: clipping, DC, clicks
    clip = int(np.sum(np.abs(out) >= 0.999))
    dc = out.mean(axis=0)
    print("\nINTEGRITY: samples at full scale %d; DC offset L %.1e R %.1e; length %d samples (%.4f s); last sample %.1e" % (
        clip, dc[0], dc[1], len(out), len(out) / SR, np.abs(out[-1]).max()))
    for k in ("music", "fx", "amb"):
        cl = A.discontinuity_scan(stems[k])
        print("  discontinuity (click) scan %-5s: %d%s" % (k, len(cl), (": " + ", ".join("%.3f s (z %.0f, %.0f dBFS)" % c for c in cl[:6])) if cl else ""))
    event_report(C, stems["fx"], flog)
    music_sync_report(C, stems["music"], marks, out)
    if not args.no_png:
        png = os.path.join(args.out, "spectrogram.png")
        A.write_spectrogram(png + ".part.png", out, {k: stems[k] for k in ("music", "fx", "amb")}, C,
                            C.duration, A.loudness_curve(out), "Awakening II -- mix and stems (log frequency, 96 dB range), cue markers dotted")
        os.replace(png + ".part.png", png)
        print("\nwrote spectrogram.png")
    print("\ntotal %.1f s" % (time.time() - t_start))
    if not args.no_ffmpeg:
        ffmpeg_check(os.path.join(args.out, "mix.wav"))


if __name__ == "__main__":
    main()
