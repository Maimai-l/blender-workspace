#!/usr/bin/env python3
"""dwgsheet.py x0 y0 x1 y1 out.png [zoom] [step_m]
Crop the DWG screenshot by MODEL coordinates (metres; X east, Y north, origin on the pavilion axis) and draw a
metre grid labelled in model coordinates, so plan positions can be read off directly."""
import sys
from PIL import Image, ImageDraw, ImageFont
DWG = '/root/.cache/qiting/ref/photos/2390cc8d040e61ce45ed5e0b64655b0b.jpg'
CX, CY, S = 596.26, 597.08, 0.245          # DWG pixel of the pavilion axis; metres per DWG pixel

def to_px(X, Y):
    return CX + X / S, CY - Y / S

def to_m(x, y):
    return (x - CX) * S, (CY - y) * S

if __name__ == '__main__':
    X0, Y0, X1, Y1 = map(float, sys.argv[1:5])
    out = sys.argv[5]
    zoom = float(sys.argv[6]) if len(sys.argv) > 6 else 3.0
    step = float(sys.argv[7]) if len(sys.argv) > 7 else 5.0
    px0, py0 = to_px(X0, Y1); px1, py1 = to_px(X1, Y0)
    im = Image.open(DWG).convert('RGB').crop((int(px0), int(py0), int(px1), int(py1)))
    im = im.resize((int(im.size[0] * zoom), int(im.size[1] * zoom)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
    import math
    gx = math.ceil(X0 / step) * step
    while gx <= X1:
        u = (to_px(gx, 0)[0] - int(px0)) * zoom
        big = abs(gx / (step * 2) - round(gx / (step * 2))) < 1e-6
        d.line([(u, 0), (u, im.size[1])], fill=(0, 200, 255) if big else (0, 90, 120), width=1)
        if big: d.text((u + 2, 2), '%g' % gx, fill=(255, 255, 0), font=font)
        gx += step
    gy = math.ceil(Y0 / step) * step
    while gy <= Y1:
        v = (to_px(0, gy)[1] - int(py0)) * zoom
        big = abs(gy / (step * 2) - round(gy / (step * 2))) < 1e-6
        d.line([(0, v), (im.size[0], v)], fill=(255, 80, 255) if big else (110, 40, 110), width=1)
        if big: d.text((2, v + 2), '%g' % gy, fill=(255, 255, 0), font=font)
        gy += step
    im.save(out)
    print(out, im.size)
