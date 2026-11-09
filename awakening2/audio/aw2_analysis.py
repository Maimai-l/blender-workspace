"""
aw2_analysis.py -- measuring the soundtrack: ITU-R BS.1770-4 loudness (integrated,
momentary, short-term), EBU Tech 3342 loudness range, 4x true peak, per-second tables,
onset detection for the event check, click / DC / clipping scans, and a spectrogram PNG
with the cue markers drawn on it.
"""
import math

import numpy as np
from scipy import signal

from aw2_core import SR, sec, to_db

_K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def k_weight(x):
    y = signal.lfilter(_K1[0], _K1[1], x, axis=0)
    return signal.lfilter(_K2[0], _K2[1], y, axis=0)


def _block_ms(y, blk, hop):
    """Mean square per channel of K-weighted y over sliding blocks; returns (starts, ms(nb,2))."""
    cs = np.vstack([np.zeros((1, y.shape[1])), np.cumsum(y ** 2, axis=0)])
    idx = np.arange(0, len(y) - blk + 1, hop)
    return idx, (cs[idx + blk] - cs[idx]) / blk


def integrated_lufs(x, y=None):
    y = k_weight(x) if y is None else y
    _, ms = _block_ms(y, sec(0.4), sec(0.1))
    z = ms.sum(axis=1)
    lk = -0.691 + 10 * np.log10(z + 1e-20)
    keep = lk > -70
    if not keep.any():
        return -np.inf
    rel = -0.691 + 10 * np.log10(z[keep].mean()) - 10
    keep &= lk > rel
    return -0.691 + 10 * np.log10(z[keep].mean())


def loudness_curve(x, win=0.4, hop=0.1, y=None):
    """Sliding loudness (LUFS) with window `win` (0.4 momentary, 3.0 short-term); returns
    (centre times, values)."""
    y = k_weight(x) if y is None else y
    blk = sec(win)
    if len(y) < blk:
        return np.zeros(0), np.zeros(0)
    idx, ms = _block_ms(y, blk, sec(hop))
    return (idx + blk / 2) / SR, -0.691 + 10 * np.log10(ms.sum(axis=1) + 1e-20)


def loudness_range(x, y=None):
    """EBU Tech 3342 LRA: short-term (3 s) values, -70 abs gate, -20 LU relative gate,
    10th..95th percentile spread."""
    _, st = loudness_curve(x, 3.0, 0.1, y)
    st = st[st > -70]
    if len(st) == 0:
        return 0.0, -70, -70
    rel = 10 * np.log10(np.mean(10 ** (st / 10))) - 20
    st = st[st > rel]
    lo, hi = np.percentile(st, 10), np.percentile(st, 95)
    return hi - lo, lo, hi


def true_peak(x):
    up = signal.resample_poly(x, 4, 1, axis=0)
    return to_db(np.abs(up).max())


def tp_envelope(x):
    """Per-sample true-peak estimate (max |.| over the 4 oversampled points)."""
    up = signal.resample_poly(x, 4, 1, axis=0)
    a = np.abs(up).max(axis=1) if up.ndim == 2 else np.abs(up)
    n = len(x)
    a = a[: 4 * n].reshape(n, 4).max(axis=1)
    return np.maximum(a, np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x))


def correlation(x):
    l, r = x[:, 0], x[:, 1]
    d = math.sqrt(float(np.sum(l * l)) * float(np.sum(r * r)))
    return float(np.sum(l * r)) / d if d > 0 else 1.0


def per_second(x, stems=None, dur=None):
    """Rows: second, RMS dBFS, sample peak, momentary LUFS (whole second), L/R correlation,
    side/mid dB, and per-stem LUFS."""
    y = k_weight(x)
    ys = {k: k_weight(v) for k, v in (stems or {}).items()}
    rows = []
    nsec = int(math.ceil((dur or len(x) / SR) - 1e-9))
    for s in range(nsec):
        a, b = s * SR, min(len(x), (s + 1) * SR)
        seg = x[a:b]
        if len(seg) == 0:
            break
        lk = -0.691 + 10 * np.log10((y[a:b] ** 2).mean(axis=0).sum() + 1e-20)
        m = 0.5 * (seg[:, 0] + seg[:, 1])
        sd = 0.5 * (seg[:, 0] - seg[:, 1])
        sm = to_db(math.sqrt(float(np.mean(sd ** 2)) + 1e-20)) - to_db(math.sqrt(float(np.mean(m ** 2)) + 1e-20))
        row = dict(s=s, rms=to_db(math.sqrt(float(np.mean(seg ** 2)))), peak=to_db(np.abs(seg).max()), lufs=lk,
                   corr=correlation(seg), sm=sm)
        for k, v in ys.items():
            row[k] = -0.691 + 10 * np.log10((v[a:b] ** 2).mean(axis=0).sum() + 1e-20)
        rows.append(row)
    return rows


# ============================================================================ onsets & clicks
def onset_strength(x, hop_ms=5.0, nfft=1024, fmin=150.0):
    """Spectral-flux onset strength (half-wave rectified log-magnitude rise), mono sum."""
    m = x.mean(axis=1) if x.ndim == 2 else x
    hop = sec(hop_ms / 1000)
    f, t, Z = signal.stft(m, fs=SR, nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=False)
    mag = np.log10(np.abs(Z) + 1e-7)
    band = f >= fmin
    d = np.diff(mag[band], axis=1)
    flux = np.maximum(d, 0).sum(axis=0)
    times = t[1:]                          # frame-centre times of the later frame
    return times, flux


def event_onset(times, flux, te, before=0.06, after=0.15):
    """Strongest flux peak near te: (offset s, strength relative to the local median)."""
    sel = (times >= te - before) & (times <= te + after)
    if not sel.any():
        return None, 0.0
    i = np.argmax(np.where(sel, flux, -1))
    ctx = (times >= te - 1.0) & (times <= te + 1.0)
    med = np.median(flux[ctx]) + 1e-9
    return times[i] - te, flux[i] / med


def discontinuity_scan(x, z_thresh=12.0, win_ms=2.0, floor_rel=3e-4):
    """Digital clicks: samples whose 2nd difference stands z_thresh times above the RMS
    2nd difference of the surrounding +-win_ms (centre excluded).  Smooth tones, noise and
    shaped transients score ~1-4; a waveform step or spike scores far higher.  Steps
    smaller than floor_rel x the stem's peak (-70 dB) are ignored.  Returns
    [(time, z, step dBFS)]."""
    from scipy.ndimage import uniform_filter1d
    out = []
    pk = np.abs(x).max() + 1e-12
    chans = [x[:, 0], x[:, 1]] if x.ndim == 2 else [x]
    hits = []
    for m in chans:
        d2 = np.zeros_like(m)
        d2[1:-1] = m[2:] - 2 * m[1:-1] + m[:-2]
        e = d2 ** 2
        w = sec(win_ms / 1000)
        tot = uniform_filter1d(e, 2 * w + 1, mode="nearest") * (2 * w + 1)
        cen = uniform_filter1d(e, 5, mode="nearest") * 5
        local = np.maximum(tot - cen, 0) / (2 * w - 4)
        z = np.abs(d2) / np.sqrt(local + (floor_rel * pk) ** 2)
        idx = np.nonzero(z > z_thresh)[0]
        hits += [(i, z[i], abs(d2[i])) for i in idx]
    hits.sort()
    for i, z, a in hits:
        t = i / SR
        if not out or t - out[-1][0] > 0.005:
            out.append((t, z, to_db(a)))
    return out


def click_scan(x, known, thresh_db=18.0, floor_db=-66.0, guard=0.05):
    """Find impulsive HF bursts not explained by a placed sound: 1 ms frames of >6 kHz
    energy that stand thresh_db above their +-40 ms median.  `known` = onset times of
    everything placed on the bus (grains included)."""
    m = x.mean(axis=1) if x.ndim == 2 else x
    h = signal.sosfilt(signal.butter(4, 6000, "highpass", fs=SR, output="sos"), m)
    fr = sec(0.001)
    nb = len(h) // fr
    e = 10 * np.log10((h[: nb * fr].reshape(nb, fr) ** 2).mean(axis=1) + 1e-20)
    from scipy.ndimage import median_filter
    med = median_filter(e, size=81, mode="nearest")
    cand = np.where((e - med > thresh_db) & (e > floor_db))[0]
    known = np.sort(np.asarray(known, float))
    out = []
    for i in cand:
        t = (i + 0.5) / 1000.0
        j = np.searchsorted(known, t)
        near = min(abs(t - known[j - 1]) if j > 0 else 9, abs(known[j] - t) if j < len(known) else 9)
        if near > guard:
            if not out or t - out[-1][0] > 0.01:
                out.append((t, e[i] - med[i], e[i]))
    return out


# ============================================================================ spectrogram PNG
_CMAP = np.array([[0, 0, 4], [28, 16, 68], [79, 18, 123], [129, 37, 129], [181, 54, 122], [229, 80, 100],
                  [251, 135, 97], [254, 194, 135], [252, 253, 191]], float)


def _colorize(v):
    """v in 0..1 -> RGB uint8 (magma-like)."""
    v = np.clip(v, 0, 1) * (len(_CMAP) - 1)
    i = np.minimum(v.astype(int), len(_CMAP) - 2)
    fr = (v - i)[..., None]
    return (_CMAP[i] * (1 - fr) + _CMAP[i + 1] * fr).astype(np.uint8)


def _spec_image(m, width, height, fmin=30.0, fmax=16000.0, top_db=0.0, range_db=96.0):
    nfft = 8192
    hop = max(64, len(m) // width)
    f, t, Z = signal.stft(m, fs=SR, nperseg=nfft, noverlap=nfft - hop, boundary="even", padded=True)
    P = 20 * np.log10(np.abs(Z) * 2 + 1e-10)          # scipy scales by 1/sum(win): a full-scale sine -> 0 dB
    edges = np.geomspace(fmin, fmax, height + 1)
    rows = np.empty((height, P.shape[1]))
    for r in range(height):
        lo, hi = np.searchsorted(f, edges[r]), np.searchsorted(f, edges[r + 1])
        if hi <= lo:
            hi = lo + 1
        rows[r] = P[lo:hi].max(axis=0)
    rows = rows[::-1]
    cols = np.linspace(0, P.shape[1] - 1, width)
    img = np.empty((height, width))
    for r in range(height):
        img[r] = np.interp(cols, np.arange(P.shape[1]), rows[r])
    return _colorize((img - (top_db - range_db)) / range_db), edges


def write_spectrogram(path, mix, stems, cues, dur, mom=None, title=""):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font = small = ImageFont.load_default()
    W, L, R = 2400, 70, 20
    pw = W - L - R
    panels = [("mix", mix, 420)] + [(k, v, 170) for k, v in stems.items()]
    H_top, H_curve = 44, 130
    H = H_top + H_curve + sum(h + 26 for _, _, h in panels) + 40
    im = Image.new("RGB", (W, H), (16, 16, 20))
    d = ImageDraw.Draw(im)
    d.text((L, 10), title, font=font, fill=(230, 230, 230))
    x_of = lambda t: L + int(round(t / dur * pw))
    # loudness curve panel
    y0 = H_top
    d.rectangle([L, y0, L + pw, y0 + H_curve], fill=(24, 24, 30))
    lo_db, hi_db = -50.0, -5.0
    for lv in (-40, -30, -23, -17, -10):
        yy = y0 + int((hi_db - lv) / (hi_db - lo_db) * H_curve)
        d.line([L, yy, L + pw, yy], fill=(50, 50, 60))
        d.text((8, yy - 7), "%d" % lv, font=small, fill=(150, 150, 160))
    if mom is not None:
        tm, lm = mom
        pts = [(x_of(a), y0 + int((hi_db - np.clip(b, lo_db, hi_db)) / (hi_db - lo_db) * H_curve)) for a, b in zip(tm, lm)]
        d.line(pts, fill=(120, 220, 160), width=2)
    d.text((L + 4, y0 + 2), "momentary loudness (LUFS)", font=small, fill=(120, 220, 160))
    y = y0 + H_curve + 8
    for name, sig_, h in panels:
        m = sig_.mean(axis=1) if sig_.ndim == 2 else sig_
        rgb, edges = _spec_image(m, pw, h)
        im.paste(Image.fromarray(rgb, "RGB"), (L, y + 18))
        d.text((L, y), name, font=font, fill=(230, 230, 230))
        for fq in (50, 100, 200, 500, 1000, 2000, 5000, 10000):
            fr = (math.log(fq) - math.log(edges[0])) / (math.log(edges[-1]) - math.log(edges[0]))
            yy = y + 18 + int((1 - fr) * h)
            d.line([L - 5, yy, L, yy], fill=(180, 180, 180))
            d.text((8, yy - 7), ("%dk" % (fq // 1000)) if fq >= 1000 else str(fq), font=small, fill=(170, 170, 170))
        y += h + 26
    # sections, events, time axis
    yb = H - 34
    for nme, (a, b) in cues.sections.items():
        d.line([x_of(a), H_top, x_of(a), yb], fill=(90, 160, 255), width=1)
        d.text((x_of(a) + 3, H_top + H_curve - 16), nme, font=small, fill=(120, 180, 255))
    lab_rows = [0] * 4
    for k, (te, nmv) in enumerate(cues.events):
        xx = x_of(te)
        for yy in range(H_top + H_curve + 8, yb, 6):
            d.line([xx, yy, xx, yy + 2], fill=(255, 255, 255))
        row = k % 4
        d.text((xx + 2, H_top + 2 + 14 * row + (0 if row < 4 else 0)), nmv[:16], font=small, fill=(255, 235, 150))
    for s in range(0, int(dur) + 1, 5):
        d.line([x_of(s), yb, x_of(s), yb + 6], fill=(200, 200, 200))
        d.text((x_of(s) - 6, yb + 8), "%d" % s, font=small, fill=(200, 200, 200))
    im.save(path)
