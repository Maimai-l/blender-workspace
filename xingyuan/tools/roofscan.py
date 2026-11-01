import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sys
from PIL import Image
import numpy as np
from xyp import S, font as _xyfont
im = np.asarray(Image.open(S + '/ref/xingyuan-images/杏园介绍-01_12.jpg').convert('L')).astype(int)
ppm = 88.6; xd = 1190
yd = float(sys.argv[1]); xa = float(sys.argv[2]); xb = float(sys.argv[3]); zlo = float(sys.argv[4]); zhi = float(sys.argv[5])
step = float(sys.argv[6]) if len(sys.argv) > 6 else 0.25
def runs(arr, thr=190, off=0):
    d = arr < thr; out = []; i = 0
    while i < len(d):
        if d[i]:
            j = i
            while j < len(d) and d[j]: j += 1
            out.append((off + i, off + j - 1)); i = j
        else: i += 1
    return out
y0 = int(yd - zhi * ppm); y1 = int(yd - zlo * ppm)
x = xa
while x <= xb + 1e-6:
    px = int(round(xd + x * ppm))
    r = runs(im[y0:y1, px], off=y0)
    hs = [round((yd - (a + b) / 2) / ppm, 3) for a, b in r]
    print(round(x, 2), hs[:5])
    x += step
