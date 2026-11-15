"""Detail synthesis for a box of the real terrain: Copernicus 30 m -> `cell` m with ridged micro-relief, rock strata
and stream-power erosion, plus the masks the shaders use.

    far_build.py far_hi | far_lo | near            (presets)
    far_build.py <name> <x0> <y0> <x1> <y1> <cell> [north_rot_deg] [seed]

Box in the real scene frame (m). Writes <out>/<name>_h.npy (float32, row 0 = y0), <name>_masks.npz and previews.
north_rot_deg: rotation applied to this layer in the final scene (so "north-facing" is judged in the scene).
"""
import os, sys, time, math
import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_lib as tl

OUT = r'D:\Blender\Projects\mana_cafe\dem' if os.path.isdir(r'D:\Blender\Projects\mana_cafe') else '/root/mana/out'
os.makedirs(OUT, exist_ok=True)


def smooth(a, lo, hi):
    t = np.clip((a - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def tin_raster(xs, ys):
    """Surveyed site terrain (the SketchUp TIN) on the grid, NaN outside it, and a 0..1 weight feathered over
    120 m inside its outline."""
    from scipy.interpolate import LinearNDInterpolator
    from scipy.ndimage import distance_transform_edt
    f = os.path.join(os.path.dirname(OUT), 'tmp', 'site_geo.npz') if 'Projects' in OUT else '/root/mana/site_geo.npz'
    d = np.load(f)
    v = d['_G-Object.034_Loose_Mesh__v'].astype(np.float64)
    t = d['_G-Object.034_Loose_Mesh__t']
    m = d['_G-Object.034_Loose_Mesh__m']
    mats = [str(s) for s in d['_G-Object.034_Loose_Mesh__mats']]
    keep = np.unique(t.ravel())
    ix = (xs >= v[:, 0].min() - 5) & (xs <= v[:, 0].max() + 5)
    iy = (ys >= v[:, 1].min() - 5) & (ys <= v[:, 1].max() + 5)
    XX, YY = np.meshgrid(xs[ix], ys[iy])
    zi = LinearNDInterpolator(v[keep, :2], v[keep, 2])(XX, YY)
    out = np.full((ys.size, xs.size), np.nan, np.float32)
    out[np.ix_(iy, ix)] = zi
    inside = ~np.isnan(out)
    cell = xs[1] - xs[0]
    w = np.clip(distance_transform_edt(inside) * cell / 120.0, 0, 1)
    return out, (w * w * (3 - 2 * w)).astype(np.float32)


def build(name, x0, y0, x1, y1, cell, north_rot=0.0, seed=7, rounds=14, log=print, amp0=5.0, amp1=34.0,
          use_tin=False, kdt=0.018, max_cut=2.2):
    t0 = time.time()
    xs = np.arange(x0, x1 + 0.5 * cell, cell, dtype=np.float64)
    ys = np.arange(y0, y1 + 0.5 * cell, cell, dtype=np.float64)
    XX, YY = np.meshgrid(xs, ys)
    z = tl.dem_at(XX, YY, order=3).astype(np.float32)
    del XX, YY
    shape = z.shape
    log('grid', shape, 'cell', cell, 'z', float(z.min()), float(z.max()), '%.1fs' % (time.time() - t0))
    tinw = None
    if use_tin:
        zt, tinw = tin_raster(xs, ys)
        z = np.where(tinw > 0, z * (1 - tinw) + np.nan_to_num(zt) * tinw, z).astype(np.float32)
        log('TIN blended over', int((tinw > 0).sum()), 'cells')
    zreal = z.copy()

    # --- where the ground is bare rock / high alpine (drives how much relief is added)
    sl = tl.slope_normal(z, cell)[0]
    sl_s = gaussian_filter(sl, 40.0 / cell)
    high = smooth(z, 250.0, 900.0)                  # above ~4650..5300 m
    steep = smooth(sl_s, 0.45, 0.95)
    rocky = np.clip(0.25 * high + 0.75 * steep * (0.35 + 0.65 * high), 0, 1)

    # --- 1. restore the sharpness the 30 m radar DEM lost on crests and summits
    for sig, k in ((45.0, 0.36), (110.0, 0.24), (260.0, 0.12)):
        d = z - gaussian_filter(z, sig / cell)
        z += d * k * (0.25 + 0.75 * high) * np.where(d > 0, 1.0, 0.45)
    # --- 2. ridged micro-relief (seeds the gullies), stronger on rock
    rid = tl.ridged(shape, cell, seed, octaves=6, base_wl=900.0)
    rid2 = tl.ridged(shape, cell, seed + 101, octaves=5, base_wl=220.0)
    fb = tl.fbm_fft(shape, cell, seed + 5, beta=2.6, lo=2.5 * cell, hi=400.0)
    amp = amp0 + amp1 * rocky
    if tinw is not None:
        amp = amp * (1.0 - 0.85 * tinw)            # the surveyed ground keeps its shape
    z += (rid - 0.5) * amp * 1.6 + (rid2 - 0.5) * amp * 0.45 + fb * (1.2 + 3.0 * rocky)
    # --- 3. rock strata: dipping benches on steep high ground (cliff bands that hold snow on their ledges)
    dip = math.radians(18.0)
    strike = math.radians(35.0)
    X = xs[None, :].astype(np.float32)
    Y = ys[:, None].astype(np.float32)
    warp = tl.fbm_fft(shape, cell, seed + 31, beta=3.0, lo=60.0, hi=3000.0) * 28.0
    s = z + (X * math.cos(strike) + Y * math.sin(strike)) * math.tan(dip) + warp
    for spacing, a in ((95.0, 0.36), (38.0, 0.22)):
        ph = s / spacing
        fr = ph - np.floor(ph)
        step = (smooth(fr, 0.0, 0.28) - fr) * spacing        # staircase minus the ramp: benches and risers
        z += step * a * rocky * smooth(sl_s, 0.5, 0.9)
    del s, warp, rid, rid2, fb
    log('relief added', '%.1fs' % (time.time() - t0))

    # --- 4. erosion: gullies, sharper spurs, talus
    creep = (1.0 - rocky).astype(np.float32)
    if tinw is not None:
        creep = creep * (1.0 - tinw)
    z, A = tl.erode(z, cell, rounds=rounds, kdt=kdt, m=0.45, a_sat=3e5, max_cut=max_cut,
                    talus=1.55, th_rate=0.22, th_iters=2, creep=creep, creep_coef=0.10, log=log)
    # --- 5. rock ribs and ledges on the bare high faces, after the erosion so they stay crisp
    rib = tl.ridged(shape, cell, seed + 211, octaves=4, base_wl=70.0)
    rib2 = tl.ridged(shape, cell, seed + 223, octaves=3, base_wl=24.0)
    rib3 = tl.ridged(shape, cell, seed + 227, octaves=2, base_wl=11.0)
    z += ((rib - 0.5) * 17.0 + (rib2 - 0.5) * 6.5 + (rib3 - 0.5) * 2.4) * rocky * rocky
    del rib, rib2, rib3
    log('eroded', '%.1fs' % (time.time() - t0), 'dz', float((z - zreal).min()), float((z - zreal).max()))

    # --- masks
    sl, nx, ny, nz = tl.slope_normal(z, cell)
    lap = (gaussian_filter(z, 12.0 / cell) - gaussian_filter(z, 36.0 / cell))      # + on crests, - in hollows
    flow = np.log10(np.maximum(A, cell * cell)).astype(np.float32)
    np.save(os.path.join(OUT, name + '_h.npy'), z)
    np.savez(os.path.join(OUT, name + '_masks.npz'), slope=sl.astype(np.float16), nx=nx.astype(np.float16),
             ny=ny.astype(np.float16),
             curv=lap.astype(np.float16), flow=flow.astype(np.float16), rocky=rocky.astype(np.float16),
             box=np.array([x0, y0, cell, shape[1], shape[0]], np.float64))
    hs = tl.hillshade(z, cell, az_deg=-35.0 - north_rot, el_deg=38.0)
    tl.save_png(os.path.join(OUT, name + '_hs.png'), hs[::max(1, shape[0] // 2400), ::max(1, shape[1] // 2400)], 0, 1)
    log('saved', name, '%.1fs' % (time.time() - t0))
    return z, zreal


PRESETS = {
    # name: (x0, y0, x1, y1, cell, kwargs)   boxes in the real scene frame
    'far_hi': (-31000, -19000, -12000, 1000, 5.0, dict(seed=7)),
    'far_lo': (-45000, -34000, -5000, 12000, 15.0, dict(seed=11, rounds=8)),
    'near': (-7500, -8500, 3000, 1500, 2.5, dict(seed=23, amp0=1.6, amp1=26.0, use_tin=True, rounds=10, kdt=0.012,
                                                   max_cut=1.2)),
}

if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] in PRESETS:
        p = PRESETS[a[0]]
        build(a[0], *p[:5], **p[5])
    else:
        build(a[0], float(a[1]), float(a[2]), float(a[3]), float(a[4]), float(a[5]),
              float(a[6]) if len(a) > 6 else 0.0, int(a[7]) if len(a) > 7 else 7)
