"""Tileable ground tiles from the top-down bakes of the Tundra Rocky Ground scans (bake_ground.py):
largest square inside the scan's outline, blended with its half-shifted copy where the heights allow.

    fab_seamless.py     -> assets\\fab\\rocky_ground_[ab]\\bake_{color.jpg,normal.png,height.png,rough.jpg}, manifest
"""
import os, sys, json
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, distance_transform_edt

Image.MAX_IMAGE_PIXELS = None
FAB = r'D:\Blender\Projects\mana_cafe\assets\fab'
OUT = 2048


def load(p):
    im = Image.open(p)
    a = np.asarray(im).astype(np.float32)
    return a / (65535.0 if a.max() > 255 else 255.0)


def largest_square(mask):
    """Largest axis-aligned square of True values (dynamic programming). Returns (row, col, size)."""
    m = mask.astype(np.int32)
    H, W = m.shape
    k = 8                                                        # work on a coarse grid
    c = m[:H // k * k, :W // k * k].reshape(H // k, k, W // k, k).min((1, 3))
    dp = np.zeros_like(c)
    best = (0, 0, 0)
    for i in range(c.shape[0]):
        for j in range(c.shape[1]):
            if c[i, j]:
                dp[i, j] = 1 + (min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1]) if i and j else 0)
                if dp[i, j] > best[2]:
                    best = (i, j, dp[i, j])
    i, j, s = best
    return (i - s + 1) * k, (j - s + 1) * k, s * k


def seamless(maps, h):
    n = h.shape[0]
    hp = h - gaussian_filter(h, n / 5.0, mode='reflect')        # heights without the scan's overall tilt
    sh = lambda a: np.roll(np.roll(a, n // 2, 0), n // 2, 1)
    yy, xx = np.mgrid[0:n, 0:n]
    d = np.minimum(np.minimum(xx, n - 1 - xx), np.minimum(yy, n - 1 - yy)) / (n / 2.0)     # 0 at the border, 1 centre
    w = np.clip((d - 0.04) / 0.5, 0, 1)
    hs = sh(hp)
    rng = hp.std() + 1e-6
    # the higher surface wins inside the transition band; the height term vanishes at both ends of the band
    f = np.clip(w + (hp - hs) / rng * 0.45 * 4.0 * w * (1.0 - w), 0, 1)
    f = (f * f * (3 - 2 * f)).astype(np.float32)
    f = gaussian_filter(f, 2.0)
    out = {k: v * (f[..., None] if v.ndim == 3 else f) + sh(v) * (1 - (f[..., None] if v.ndim == 3 else f)) for k, v in maps.items()}
    out['height'] = hp * f + hs * (1 - f)
    return out


def main():
    man = json.load(open(os.path.join(FAB, 'manifest.json'), encoding='utf-8'))
    for key in ('rocky_ground_a', 'rocky_ground_b'):
        d = os.path.join(FAB, key)
        meta = json.load(open(os.path.join(d, 'raw_meta.json')))
        col = load(os.path.join(d, 'raw_color.png'))
        alpha = col[..., 3]
        from scipy.ndimage import binary_fill_holes
        inside = distance_transform_edt(binary_fill_holes(alpha > 0.5)) > 60          # stay clear of the scan's rim
        r, c, s = largest_square(inside)
        px_m = col.shape[0] / meta['span']
        tile = s / px_m
        crop = lambda a: a[r:r + s, c:c + s]
        maps = {'color': crop(col[..., :3]), 'normal': crop(load(os.path.join(d, 'raw_normal.png'))[..., :3]),
                'rough': crop(load(os.path.join(d, 'raw_rough.png'))[..., 0])}
        h = crop(load(os.path.join(d, 'raw_height.png'))[..., 0]) * (meta['z1'] - meta['z0'])       # metres
        res = seamless(maps, h)
        hh = res['height']
        lo, hi = np.percentile(hh, 0.2), np.percentile(hh, 99.8)
        hn = np.clip((hh - lo) / (hi - lo), 0, 1)
        nrm = res['normal'] * 2 - 1
        nrm /= np.linalg.norm(nrm, axis=2, keepdims=True) + 1e-9

        def save(a, name, mode):
            im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), mode).resize((OUT, OUT), Image.LANCZOS)
            p = os.path.join(d, name)
            im.save(p, quality=94, subsampling=0) if name.endswith('.jpg') else im.save(p)
            return p
        e = man[key]
        e['maps']['bake_color'] = {'file': save(res['color'], 'bake_color.jpg', 'RGB'), 'size': [OUT, OUT]}
        e['maps']['bake_normal'] = {'file': save(nrm * 0.5 + 0.5, 'bake_normal.png', 'RGB'), 'size': [OUT, OUT]}
        e['maps']['bake_rough'] = {'file': save(res['rough'], 'bake_rough.jpg', 'L'), 'size': [OUT, OUT]}
        e['maps']['bake_height'] = {'file': save(hn, 'bake_height.png', 'L'), 'size': [OUT, OUT]}
        e['bake'] = {'tile_m': float(tile), 'height_m': float(hi - lo)}
        print(key, 'square', s, 'px =', round(tile, 2), 'm; height range', round(float(hi - lo), 3), 'm; mean colour',
              (res['color'].reshape(-1, 3).mean(0) * 255).round().tolist())
    json.dump(man, open(os.path.join(FAB, 'manifest.json'), 'w', encoding='utf-8'), indent=1)


if __name__ == '__main__':
    main()
