import numpy as np, math, json, sys
from PIL import Image
from scipy.ndimage import map_coordinates
CX, CY, S = 596.26, 597.08, 0.245
d = np.asarray(Image.open('/root/.cache/qiting/ref/photos/2390cc8d040e61ce45ed5e0b64655b0b.jpg').convert('RGB')).astype(float)
white = (d.min(axis=2) > 125).astype(float)
AZ = np.arange(0, 360, 0.5)
R = np.arange(20, 60, 0.05)
P = np.zeros((len(R), len(AZ)))
for i, r in enumerate(R):
    x = CX + r * np.cos(np.radians(AZ)) / S; y = CY - r * np.sin(np.radians(AZ)) / S
    P[i] = map_coordinates(white, [y, x], order=1)
def crossings(j):
    col = P[:, j]
    m = col > 0.45
    idx = np.nonzero(m[1:] & ~m[:-1])[0]
    out = []
    for k in idx:
        e = k + 1
        while e < len(m) and m[e]: e += 1
        out.append(R[(k + e) // 2])
    return np.array(out)
def track(az0, r0, direction=1, tol=0.9, max_gap=24):
    j0 = int(round(az0 / 0.5)) % len(AZ)
    res = {j0: r0}
    r = r0; gap = 0
    j = j0
    for step in range(1, len(AZ)):
        j = (j0 + direction * step) % len(AZ)
        c = crossings(j)
        if len(c):
            k = np.argmin(abs(c - r))
            if abs(c[k] - r) < tol:
                r = c[k]; res[j] = r; gap = 0
                continue
        gap += 1
        if gap > max_gap:
            break
    return res
seeds = json.loads(sys.argv[1])
out = {}
for name, az0, r0 in seeds:
    a = track(az0, r0, 1); b = track(az0, r0, -1)
    a.update(b)
    js = sorted(a)
    out[name] = [[float(AZ[j]), float(a[j])] for j in js]
    print(name, 'covered %.0f deg' % (len(js) * 0.5), 'r range %.1f-%.1f' % (min(a.values()), max(a.values())))
json.dump(out, open('/root/.cache/qiting/ring_trace.json', 'w'))
