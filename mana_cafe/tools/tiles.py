#!/usr/bin/env python3
"""tiles.py <image> [cols rows] : cut a render into overlapping tiles next to it (name_r<row>c<col>.jpg) for
region-by-region inspection at full resolution."""
import sys, os
from PIL import Image
src = sys.argv[1]
cols = int(sys.argv[2]) if len(sys.argv) > 2 else 3
rows = int(sys.argv[3]) if len(sys.argv) > 3 else 2
im = Image.open(src).convert('RGB')
W, H = im.size
tw, th = W // cols, H // rows
base = os.path.splitext(src)[0]
for r in range(rows):
    for c in range(cols):
        box = (max(0, c * tw - 40), max(0, r * th - 40), min(W, (c + 1) * tw + 40), min(H, (r + 1) * th + 40))
        im.crop(box).save('%s_r%dc%d.jpg' % (base, r, c), quality=92)
print(base, W, H, cols, rows)
