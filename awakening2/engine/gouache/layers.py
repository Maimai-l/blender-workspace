"""layers.py - multiplane output: per-layer straight-alpha PNGs, flat.png, layers.json.

Painting(name, W, H, margin, outdir)
    .layer(name, depth)          -> new Canvas (flat W x H + margin overscan)
    .add(name, depth, cv, note)  grain, save PNG, composite into the flat image
    .save(**meta)                flat.png, preview.jpg, layers.json
Layer PNGs include the overscan margin: a layer file is (W+2m) x (H+2m) and its
top-left sits at (-m, -m) in painting coordinates ("offset" in layers.json).
"""
import json
import os
import time
import numpy as np
from PIL import Image

from .canvas import Canvas, grain, save_rgba, save_rgb


class Painting:
    def __init__(self, name, W, H, margin, outdir, grain_amt=0.03):
        self.name, self.W, self.H, self.m = name, int(W), int(H), int(margin)
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)
        self.flat = np.zeros((self.H + 2 * self.m, self.W + 2 * self.m, 4), np.float32)
        self.meta = []
        self.t0 = time.time()
        self.grain_amt = grain_amt
        self.times = {}

    def layer(self, name, depth=None, bg=None):
        self._lt = time.time()
        return Canvas(self.W, self.H, self.m, bg)

    def add(self, name, depth, cv, note='', blend='normal', grain_amt=None):
        g = self.grain_amt if grain_amt is None else grain_amt
        if g > 0:
            grain(cv, g)
        idx = len(self.meta)
        fn = f'{idx:02d}_{name}.png'
        save_rgba(os.path.join(self.outdir, fn), cv.img)
        s = cv.img
        self.flat *= (1 - s[..., 3:4])
        self.flat += s
        dt = time.time() - getattr(self, '_lt', self.t0)
        self.times[name] = round(dt, 1)
        cov = float((s[self.m:self.m + self.H, self.m:self.m + self.W, 3] > 0.01).mean())
        self.meta.append(dict(name=name, file=fn, depth=float(depth), size=[cv.img.shape[1], cv.img.shape[0]],
                              offset=[-self.m, -self.m], blend=blend, coverage=round(cov, 3), note=note))
        print(f'  [{self.name}] layer {name:12s} depth {depth:.2f}  {dt:6.1f}s', flush=True)

    def flat_rgb(self):
        m = self.m
        f = self.flat[m:m + self.H, m:m + self.W]
        a = np.maximum(f[..., 3:4], 1e-5)
        return np.clip(f[..., :3] / a, 0, 1) * np.clip(f[..., 3:4], 0, 1) + \
            (1 - np.clip(f[..., 3:4], 0, 1)) * 0.0

    def save(self, **extra):
        rgb = self.flat_rgb()
        save_rgb(os.path.join(self.outdir, 'flat.png'), rgb)
        im = Image.open(os.path.join(self.outdir, 'flat.png'))
        sc = 960 / max(im.size)
        im.resize((int(im.size[0] * sc), int(im.size[1] * sc)), Image.LANCZOS).save(
            os.path.join(self.outdir, 'preview.jpg'), quality=88)
        total = round(time.time() - self.t0, 1)
        meta = dict(painting=self.name, size=[self.W, self.H], margin=self.m,
                    note='Straight-alpha RGBA layers, far to near. Each PNG includes the overscan '
                         'margin; place its top-left at `offset` in painting coordinates. '
                         'depth: suggested parallax factor (0 = sky ... 1 = nearest). '
                         'flat.png = all layers composited with normal blending.',
                    layers=self.meta, seconds=total, layer_seconds=self.times)
        meta.update(extra)
        with open(os.path.join(self.outdir, 'layers.json'), 'w') as f:
            json.dump(meta, f, indent=2)
        print(f'[{self.name}] saved in {total}s -> {self.outdir}', flush=True)
        return rgb
