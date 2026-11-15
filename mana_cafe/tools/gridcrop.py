#!/usr/bin/env python3
"""gridcrop.py <image> <x0> <y0> <x1> <y1> <out.png> [zoom] [step]
Crop a region of a full-resolution reference image, enlarge it and draw a labelled pixel grid in the
ORIGINAL image coordinates, so positions can be read off by eye."""
import sys
from PIL import Image, ImageDraw, ImageFont
src, x0, y0, x1, y1, out = sys.argv[1], *map(int, sys.argv[2:6]), sys.argv[6]
zoom = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
step = int(sys.argv[8]) if len(sys.argv) > 8 else 20
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
im = im.resize((int((x1 - x0) * zoom), int((y1 - y0) * zoom)), Image.LANCZOS)
d = ImageDraw.Draw(im)
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
except Exception:
    font = ImageFont.load_default()
for x in range((x0 // step + 1) * step, x1, step):
    X = (x - x0) * zoom
    big = x % (step * 5) == 0
    d.line([(X, 0), (X, im.size[1])], fill=(0, 255, 255) if big else (0, 160, 160), width=1)
    if big:
        d.text((X + 2, 2), str(x), fill=(255, 255, 0), font=font)
for y in range((y0 // step + 1) * step, y1, step):
    Y = (y - y0) * zoom
    big = y % (step * 5) == 0
    d.line([(0, Y), (im.size[0], Y)], fill=(255, 0, 255) if big else (160, 0, 160), width=1)
    if big:
        d.text((2, Y + 2), str(y), fill=(255, 255, 0), font=font)
im.save(out)
print(out, im.size)
