"""Terrain processing kit (numpy + numba): registration, DEM sampling, fractal noise, flow routing, erosion.

Runs outside Blender (pyrun.py on the PC, or in the cloud session). Scene frame = the Blender scene: x east-ish,
y north-ish (SketchUp's UTM grid north, 0.83 deg west of true north), origin at the cafe, z = 0 at the cafe floor.
"""
import math, os
import numpy as np
from numba import njit, prange

# registration of the scene frame against Copernicus GLO-30 (from tools: reg2.py, 55,836 Google terrain points)
LAT0, LON0, ROT, K, Z0 = 28.4302905, 100.648231, -1.44014023e-02, 1.00146232, 4395.857
R_EARTH = 6371000.0


def find_dem():
    for p in (r'D:\Blender\Projects\mana_cafe\dem', '/root/mana/dem'):
        f = os.path.join(p, 'Copernicus_DSM_COG_10_N28_00_E100_00_DEM.tif')
        if os.path.exists(f):
            return f
    raise FileNotFoundError('DEM tile')


_DEM = None


def dem_tile():
    """N28E100 tile as float32 [3600, 3600], row 0 = 29 N, col 0 = 100 E (pixel centres)."""
    global _DEM
    if _DEM is None:
        import rasterio
        with rasterio.open(find_dem()) as r:
            _DEM = r.read(1).astype(np.float32)
    return _DEM


def scene_to_geo(x, y):
    c, s = math.cos(ROT), math.sin(ROT)
    e = (x * c - y * s) * K
    n = (x * s + y * c) * K
    lat = LAT0 + np.degrees(n / R_EARTH)
    lon = LON0 + np.degrees(e / (R_EARTH * np.cos(np.radians((lat + LAT0) / 2))))
    return lat, lon


def dem_at(x, y, order=3):
    """Height above the cafe floor (m) of the real terrain at scene coordinates."""
    from scipy.ndimage import map_coordinates
    lat, lon = scene_to_geo(x, y)
    r = (29.0 - lat) * 3600.0 - 0.5
    c = (lon - 100.0) * 3600.0 - 0.5
    return map_coordinates(dem_tile(), [r, c], order=order, mode='nearest') - Z0


# ---------------------------------------------------------------- noise
def fbm_fft(shape, cell, seed, beta=2.0, lo=None, hi=None):
    """Gaussian random field with power spectrum ~ k^-beta between wavelengths hi..lo (metres); unit variance."""
    rng = np.random.default_rng(seed)
    n0, n1 = shape
    f = np.fft.rfft2(rng.standard_normal(shape).astype(np.float32))
    ky = np.fft.fftfreq(n0, d=cell)[:, None]
    kx = np.fft.rfftfreq(n1, d=cell)[None, :]
    k = np.sqrt(kx * kx + ky * ky)
    k[0, 0] = 1.0
    amp = k ** (-beta / 2.0)
    if lo is not None:
        amp *= np.exp(-(k * lo) ** 2)            # damp wavelengths shorter than lo
    if hi is not None:
        amp *= 1.0 - np.exp(-(k * hi) ** 2)      # damp wavelengths longer than hi
    amp[0, 0] = 0.0
    out = np.fft.irfft2(f * amp, s=shape).astype(np.float32)
    return out / out.std()


def ridged(shape, cell, seed, octaves=5, base_wl=600.0, gain=0.55, lac=2.1):
    """Ridged multifractal-like field in 0..1 built from band-limited FFT octaves."""
    out = np.zeros(shape, np.float32)
    w = 1.0
    amp = 1.0
    tot = 0.0
    wl = base_wl
    for o in range(octaves):
        n = fbm_fft(shape, cell, seed + 17 * o, beta=0.0, lo=wl * 0.35, hi=wl * 1.6)
        r = 1.0 - np.abs(np.tanh(n * 0.8))
        r = r * r
        out += r * amp * w
        tot += amp
        w = np.clip(r * 1.6, 0.0, 1.0)
        amp *= gain
        wl /= lac
    return out / tot


# ---------------------------------------------------------------- flow routing (priority-flood) and erosion
@njit(cache=True)
def _heap_push(hk, hi, n, key, idx):
    i = n
    hk[i] = key
    hi[i] = idx
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] <= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hi[p], hi[i] = hi[i], hi[p]
        i = p
    return n + 1


@njit(cache=True)
def _heap_pop(hk, hi, n):
    key = hk[0]
    idx = hi[0]
    n -= 1
    hk[0] = hk[n]
    hi[0] = hi[n]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= n:
            break
        r = l + 1
        m = l
        if r < n and hk[r] < hk[l]:
            m = r
        if hk[i] <= hk[m]:
            break
        hk[i], hk[m] = hk[m], hk[i]
        hi[i], hi[m] = hi[m], hi[i]
        i = m
    return key, idx, n


@njit(cache=True)
def flow_route(z):
    """Priority-flood from the border. Returns (order, rcv): order = cells from outlets upstream, rcv = receiver
    index of each cell (itself on the border). Depressions drain across their sill (no filling of z)."""
    ny, nx = z.shape
    N = ny * nx
    rcv = np.full(N, -1, np.int32)
    order = np.empty(N, np.int32)
    done = np.zeros(N, np.uint8)
    hk = np.empty(N, np.float32)
    hi = np.empty(N, np.int32)
    n = 0
    zf = z.ravel()
    for j in range(ny):
        for i in range(nx):
            if j == 0 or i == 0 or j == ny - 1 or i == nx - 1:
                k = j * nx + i
                n = _heap_push(hk, hi, n, zf[k], k)
                done[k] = 1
                rcv[k] = k
    dj = np.array([-1, -1, -1, 0, 0, 1, 1, 1])
    di = np.array([-1, 0, 1, -1, 1, -1, 0, 1])
    cnt = 0
    while n > 0:
        key, k, n = _heap_pop(hk, hi, n)
        order[cnt] = k
        cnt += 1
        j = k // nx
        i = k - j * nx
        for q in range(8):
            jj = j + dj[q]
            ii = i + di[q]
            if jj < 0 or ii < 0 or jj >= ny or ii >= nx:
                continue
            kk = jj * nx + ii
            if done[kk]:
                continue
            done[kk] = 1
            rcv[kk] = k
            zz = zf[kk]
            if zz < key:
                zz = key            # spill level: keeps the pop order monotone
            n = _heap_push(hk, hi, n, zz, kk)
    return order, rcv


@njit(cache=True)
def steepest_rcv(z, order, rcv, cell):
    """Replace the flood receiver by the steepest-descent neighbour where one exists (keeps the flood receiver in
    pits and flats, so every cell still drains to the border)."""
    ny, nx = z.shape
    zf = z.ravel()
    dj = np.array([-1, -1, -1, 0, 0, 1, 1, 1])
    di = np.array([-1, 0, 1, -1, 1, -1, 0, 1])
    dd = np.array([1.41421356, 1.0, 1.41421356, 1.0, 1.0, 1.41421356, 1.0, 1.41421356])
    # rank in flood order, so we only accept neighbours that were flooded earlier (guarantees no cycles)
    rank = np.empty(zf.size, np.int32)
    for r in range(order.size):
        rank[order[r]] = r
    out = rcv.copy()
    for k in range(zf.size):
        j = k // nx
        i = k - j * nx
        if j == 0 or i == 0 or j == ny - 1 or i == nx - 1:
            continue
        best = 0.0
        bk = -1
        for q in range(8):
            kk = (j + dj[q]) * nx + (i + di[q])
            s = (zf[k] - zf[kk]) / (dd[q] * cell)
            if s > best and rank[kk] < rank[k]:
                best = s
                bk = kk
        if bk >= 0:
            out[k] = bk
    return out


@njit(cache=True)
def accumulate(order, rcv, cell):
    A = np.full(order.size, cell * cell, np.float32)
    for r in range(order.size - 1, -1, -1):
        k = order[r]
        t = rcv[k]
        if t != k:
            A[t] += A[k]
    return A


@njit(cache=True)
def incise(z, order, rcv, A, cell, kdt, m, a_sat, max_cut):
    """Implicit stream-power incision (n = 1), receivers first. The drainage area saturates at a_sat so that the
    big real rivers are not deepened; each cell is lowered by at most max_cut per call."""
    ny, nx = z.shape
    zf = z.ravel()
    z0 = zf.copy()
    for r in range(order.size):
        k = order[r]
        t = rcv[k]
        if t == k:
            continue
        j = k // nx
        i = k - j * nx
        jt = t // nx
        it = t - jt * nx
        d = cell * (1.41421356 if (j != jt and i != it) else 1.0)
        a = A[k]
        ae = a / (1.0 + a / a_sat)
        f = kdt * ae ** m / d
        znew = (zf[k] + f * zf[t]) / (1.0 + f)
        if znew < z0[k] - max_cut:
            znew = z0[k] - max_cut
        if znew < zf[t] + 1e-4:
            znew = zf[t] + 1e-4
        if znew < zf[k]:
            zf[k] = znew


@njit(parallel=True, cache=True)
def thermal(z, cell, talus, rate, iters):
    """Talus relaxation: slopes steeper than `talus` (tan) shed material to the lower 4-neighbours."""
    ny, nx = z.shape
    for it in range(iters):
        dz = np.zeros_like(z)
        for j in prange(1, ny - 1):
            for i in range(1, nx - 1):
                h = z[j, i]
                tot = 0.0
                d0 = h - z[j - 1, i] - talus * cell
                d1 = h - z[j + 1, i] - talus * cell
                d2 = h - z[j, i - 1] - talus * cell
                d3 = h - z[j, i + 1] - talus * cell
                if d0 > 0:
                    tot += d0
                if d1 > 0:
                    tot += d1
                if d2 > 0:
                    tot += d2
                if d3 > 0:
                    tot += d3
                if tot > 0:
                    dz[j, i] -= rate * tot * 0.5
        # deposit: give each cell what its higher neighbours shed towards it
        for j in prange(1, ny - 1):
            for i in range(1, nx - 1):
                h = z[j, i]
                g = 0.0
                d = z[j - 1, i] - h - talus * cell
                if d > 0:
                    g += d
                d = z[j + 1, i] - h - talus * cell
                if d > 0:
                    g += d
                d = z[j, i - 1] - h - talus * cell
                if d > 0:
                    g += d
                d = z[j, i + 1] - h - talus * cell
                if d > 0:
                    g += d
                dz[j, i] += rate * g * 0.5
        for j in prange(1, ny - 1):
            for i in range(1, nx - 1):
                z[j, i] += dz[j, i]


@njit(parallel=True, cache=True)
def diffuse(z, w, coef, iters):
    """Hillslope creep: z += coef * w * laplacian(z); w is a per-cell weight (0..1)."""
    ny, nx = z.shape
    for it in range(iters):
        t = z.copy()
        for j in prange(1, ny - 1):
            for i in range(1, nx - 1):
                lap = t[j - 1, i] + t[j + 1, i] + t[j, i - 1] + t[j, i + 1] - 4.0 * t[j, i]
                z[j, i] = t[j, i] + coef * w[j, i] * lap


def erode(z, cell, rounds=12, kdt=0.02, m=0.45, a_sat=4e5, max_cut=2.5, talus=1.4, th_rate=0.25, th_iters=3,
          creep=None, creep_coef=0.12, log=print):
    """Rounds of flow routing + incision + talus relaxation (+ optional creep). Returns (z, A) with the last
    drainage area (m^2)."""
    z = np.ascontiguousarray(z, np.float32)
    A = None
    for r in range(rounds):
        order, rcv = flow_route(z)
        rcv = steepest_rcv(z, order, rcv, cell)
        # the steepest receivers are not ordered by the flood rank any more in general, but every accepted receiver
        # has a lower flood rank, so `order` is still a valid outlets-first ordering
        A = accumulate(order, rcv, cell)
        incise(z, order, rcv, A, cell, kdt, m, a_sat, max_cut)
        if th_iters:
            thermal(z, cell, talus, th_rate, th_iters)
        if creep is not None:
            diffuse(z, creep, creep_coef, 1)
        if log:
            log('  erosion round %d/%d' % (r + 1, rounds))
    order, rcv = flow_route(z)
    rcv = steepest_rcv(z, order, rcv, cell)
    A = accumulate(order, rcv, cell)
    return z, A.reshape(z.shape)


# ---------------------------------------------------------------- analysis helpers
def slope_normal(z, cell):
    gy, gx = np.gradient(z, cell)
    sl = np.sqrt(gx * gx + gy * gy)
    inv = 1.0 / np.sqrt(1.0 + sl * sl)
    return sl, -gx * inv, -gy * inv, inv


def hillshade(z, cell, az_deg=-35.0, el_deg=35.0, amb=0.25):
    sl, nx, ny, nz = slope_normal(z, cell)
    a, e = math.radians(az_deg), math.radians(el_deg)
    s = (math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e))
    return np.clip(nx * s[0] + ny * s[1] + nz * s[2], 0, 1) * (1 - amb) + amb


def save_png(path, a, lo=None, hi=None):
    from PIL import Image
    a = np.asarray(a, np.float32)
    lo = float(a.min()) if lo is None else lo
    hi = float(a.max()) if hi is None else hi
    Image.fromarray((np.clip((a - lo) / max(hi - lo, 1e-9), 0, 1) * 255).astype(np.uint8)[::-1]).save(path)
