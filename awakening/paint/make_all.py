#!/usr/bin/env python3
"""make_all.py - regenerate every asset of the painted-forest kit into out/.

    python3 make_all.py              # everything, 4 worker processes
    python3 make_all.py -j 2         # fewer workers
    python3 make_all.py --only tree  # only assets whose name contains 'tree'
    python3 make_all.py --list       # show the asset list

Every asset is deterministic: its random generator is seeded from its file name
(brush.rng_for), so re-running reproduces identical images.
"""
import argparse
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, 'out')

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import brush
from brush import Canvas, rng_for, paper_grain, save_rgba, save_rgb


# asset table: name, (w, h), mode, kind, arg, grain ------------------------------------
def paint(kind, arg, cv, rng):
    """Dispatch to the painter module (imported lazily inside the worker)."""
    if kind == 'tree_fg':
        import trees
        trees.paint_tree(cv, rng, trees.fg_spec(arg - 1, rng))
    elif kind == 'tree_mid':
        import trees
        trees.paint_tree(cv, rng, trees.mid_spec(arg - 1, rng))
    elif kind == 'far':
        import forest
        forest.paint_far_strip(cv, rng, arg)
    elif kind == 'canopy':
        import forest
        forest.paint_canopy_fg(cv, rng, arg)
    elif kind == 'ground':
        import ground
        ground.paint_ground_tile(cv, rng)
    elif kind == 'moss':
        import ground
        ground.paint_moss_patch(cv, rng, arg)
    elif kind == 'grass':
        import ground
        ground.paint_grass_clump(cv, rng, arg)
    elif kind == 'flower':
        import ground
        ground.paint_flower(cv, rng, arg)
    elif kind == 'leaf':
        import sprites
        sprites.paint_leaf(cv, rng, arg)
    elif kind == 'dust':
        import sprites
        sprites.paint_dust(cv, rng, arg)
    elif kind == 'sky':
        import sky
        sky.paint_sky(cv, rng)
    else:
        raise ValueError(kind)


ASSETS = []
for i in (1, 2, 3):
    ASSETS.append((f'tree_fg_{i}', (2048, 3072), 'RGBA', 'tree_fg', i, 0.02))
for i in (1, 2, 3, 4):
    ASSETS.append((f'tree_mid_{i}', (1024, 1536), 'RGBA', 'tree_mid', i, 0.018))
for i in (1, 2, 3):
    ASSETS.append((f'forest_far_{i}', (4096, 1024), 'RGBA', 'far', i, 0.015))
for i in (1, 2):
    ASSETS.append((f'canopy_fg_{i}', (2048, 1024), 'RGBA', 'canopy', i, 0.02))
ASSETS.append(('ground_tile', (2048, 2048), 'RGB', 'ground', 0, 0.02))
for i in (1, 2, 3):
    ASSETS.append((f'moss_patch_{i}', (768, 768), 'RGBA', 'moss', i, 0.02))
for i in (1, 2, 3):
    ASSETS.append((f'grass_clump_{i}', (512, 512), 'RGBA', 'grass', i, 0.02))
for i in (1, 2, 3):
    ASSETS.append((f'flower_{i}', (256, 256), 'RGBA', 'flower', i, 0.015))
for i in range(1, 7):
    ASSETS.append((f'leaf_{i}', (256, 256), 'RGBA', 'leaf', i, 0.02))
for i in (1, 2):
    ASSETS.append((f'dust_{i}', (512, 512), 'RGBA', 'dust', i, 0.02))
ASSETS.append(('sky_dawn', (4096, 2048), 'RGB', 'sky', 0, 0.012))
BY_NAME = {a[0]: a for a in ASSETS}
# big ones first so the pool balances
ASSETS.sort(key=lambda a: -a[1][0] * a[1][1])


def build(name):
    name, (w, h), mode, kind, arg, grain = BY_NAME[name]
    t0 = time.time()
    rng = rng_for(name)
    cv = Canvas(w, h)
    paint(kind, arg, cv, rng)
    paper_grain(cv, rng, amount=grain, fibre=grain * 0.6)
    path = os.path.join(OUT, name + '.png')
    if mode == 'RGBA':
        save_rgba(path, cv)
    else:
        save_rgb(path, cv)
    return name, time.time() - t0


def contact_sheet(path):
    """Thumbnails of every output over mid grey, labelled, as JPEG."""
    cell, pad = 300, 14
    cols = 6
    items = []
    for name, (w, h), mode, _, _, _ in ASSETS:
        p = os.path.join(OUT, name + '.png')
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGBA')
        span = 2 if w >= 2 * h else 1
        tw, th = cell * span + pad * (span - 1), cell
        im.thumbnail((tw, th - 26), Image.LANCZOS)
        items.append((name, w, h, im, span))
    # simple row packing
    rows, row, used = [], [], 0
    for it in items:
        if used + it[4] > cols:
            rows.append(row)
            row, used = [], 0
        row.append(it)
        used += it[4]
    if row:
        rows.append(row)
    W = cols * cell + (cols + 1) * pad
    H = len(rows) * (cell + pad) + pad
    sheet = Image.new('RGB', (W, H), (128, 128, 128))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', 15)
    except Exception:
        font = ImageFont.load_default()
    y = pad
    for row in rows:
        x = pad
        for name, w, h, im, span in row:
            bw = cell * span + pad * (span - 1)
            sheet.paste(im, (x + (bw - im.width) // 2, y + (cell - 26 - im.height) // 2), im)
            draw.text((x + 4, y + cell - 22), f'{name}  {w}x{h}', fill=(235, 235, 235), font=font)
            x += bw + pad
        y += cell + pad
    sheet.save(path, quality=88)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-j', '--jobs', type=int, default=4)
    ap.add_argument('--only', default='', help='substring filter on asset names')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--no-sheet', action='store_true')
    args = ap.parse_args()
    todo = [a for a in ASSETS if args.only in a[0]]
    if args.list:
        for name, (w, h), mode, _, _, _ in todo:
            print(f'{name:16s} {w}x{h} {mode}')
        return
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    if args.jobs > 1:
        with Pool(args.jobs) as pool:
            for name, dt in pool.imap_unordered(build, [a[0] for a in todo]):
                print(f'{name:16s} {dt:6.1f}s', flush=True)
    else:
        for a in todo:
            name, dt = build(a[0])
            print(f'{name:16s} {dt:6.1f}s', flush=True)
    if not args.no_sheet:
        contact_sheet(os.path.join(OUT, 'contact_sheet.jpg'))
    print(f'total {time.time() - t0:.1f}s -> {OUT}')


if __name__ == '__main__':
    main()
