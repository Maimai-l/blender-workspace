"""S17 - ending: the empty clearing = the S01 end frame (1920 x 1040) with the robot gone.

Built from the rendered S01 layers (so it matches S01 exactly): each layer is cropped
to the final framing; the mid layer gets the mound of moss and soil with the knee
and hand imprints, scattered flowers and broken vines; the beams are stronger.
Run S01 first.
"""
import json
import os
import numpy as np
from PIL import Image

from ..color import C, mix, ramp, jitter, smoothstep
from ..noise import rng_for
from ..canvas import Canvas, dabs, stroke, catmull, taper
from ..layers import Painting
from ..foliage import Blobs, render_gbuffer, paint_mass, vine
from ..atmos import beams, glow, dapple
from ..ground import flowers, fern

W, H, M = 1920, 1040, 48
Y0 = 1860                       # S01 end frame top
SUN = (1330.0, 175.0 - Y0)
L3 = (0.55, -0.78, -0.32)
SUN2 = (0.55, -0.83)
KNEE = (1090.0, 935.0)
HAND = (790.0, 852.0)


def load_crop(path, m_src):
    im = np.asarray(Image.open(path).convert('RGBA'), np.float32) / 255.0
    y0 = Y0 + m_src - M
    im = im[y0:y0 + H + 2 * M, m_src - M:m_src - M + W + 2 * M]
    cv = Canvas(W, H, M)
    a = im[..., 3:4]
    cv.img[..., :3] = im[..., :3] * a
    cv.img[..., 3:4] = a
    return cv


def imprint(cv, rng, x, y, rx, ry, rot=0.0):
    """A soft depression: dark soil hollow, torn moss lip lit on the far (top) edge."""
    t = np.linspace(0, 2 * np.pi, 40)
    n = 220
    a = rng.uniform(0, 2 * np.pi, n)
    r = np.sqrt(rng.random(n))
    px = x + np.cos(a) * r * rx
    py = y + np.sin(a) * r * ry
    cols = jitter(mix(C(58, 44, 46), C(104, 80, 66), (r * 0.6)[:, None]), rng, dl=0.03, dc=0.15)
    dabs(cv, px, py, rng.uniform(8, 18, n), cols, aspect=0.5, angle=rng.normal(0, 0.3, n), edge=0.3, rag=0.5,
         bristle=0.3, rng=rng)
    # rim: lit soil lip on the far edge, dark on the near edge
    m = 90
    a = rng.uniform(0, 2 * np.pi, m)
    px = x + np.cos(a) * rx * rng.uniform(0.95, 1.12, m)
    py = y + np.sin(a) * ry * rng.uniform(0.95, 1.12, m)
    far = np.sin(a) < 0
    cols = np.where(far[:, None], mix(C(176, 150, 112), C(214, 196, 126), rng.random(m)[:, None]),
                    mix(C(40, 50, 54), C(70, 90, 70), rng.random(m)[:, None]))
    dabs(cv, px, py, rng.uniform(6, 14, m), jitter(cols, rng, dl=0.03), aspect=0.6, angle=a + np.pi / 2,
         edge=0.3, rag=0.5, bristle=0.3, rng=rng)


def build(outdir, quick=False):
    src = os.path.join(os.path.dirname(outdir), 'S01')
    meta = json.load(open(os.path.join(src, 'layers.json')))
    m_src = meta['margin']
    P = Painting('S17', W, H, M, outdir, grain_amt=0.0)
    rng = rng_for('S17')
    for L in meta['layers']:
        P._lt = __import__('time').time()
        cv = load_crop(os.path.join(src, L['file']), m_src)
        name = L['name']
        if name == 'mid':
            # the mound of moss and soil where it knelt, the knee and hand imprints
            b = Blobs()
            for i in range(26):
                x = rng.normal(950, 170)
                y = rng.normal(905, 26)
                r = rng.uniform(30, 70)
                b.add(x, y, r * 1.4, r * 0.5, light=rng.uniform(0.85, 1.1), hue=rng.normal(0, 0.08),
                      val=rng.normal(0, 0.06), rng=rng, lumpy=0.25)
            G = render_gbuffer(cv, b, light3=(L3[0], L3[1], 0.3), wrap=0.5, under=0.5)
            paint_mass(cv, G, rng, [C(64, 50, 54), C(118, 92, 74), C(156, 132, 96), C(118, 146, 80), C(196, 200, 112)],
                       leaf=11, density=0.9, sun2=SUN2, droop=0.2, vnoise=0.25, shape='flat', aspect=0.55,
                       rim=C(255, 220, 150), rim_amt=0.4, edge_leaves=0.6)
            imprint(cv, rng, KNEE[0], KNEE[1], 120, 34)
            imprint(cv, rng, HAND[0], HAND[1], 95, 28)
            for k in range(4):                                  # finger grooves fanning forward
                fx = HAND[0] - 66 + k * 44
                imprint(cv, rng, fx + (k - 1.5) * 6, HAND[1] + 40 + abs(k - 1.5) * 4, 20, 8)
            # torn moss tufts and broken vines lying around
            for i in range(7):
                x = rng.uniform(720, 1300)
                y = rng.uniform(860, 990)
                a0 = rng.uniform(-0.3, 0.3)
                pts = np.array([[x, y], [x + 60 * np.cos(a0), y + rng.normal(0, 10)],
                                [x + 130 * np.cos(a0), y + rng.normal(0, 14)]], np.float32)
                stroke(cv, catmull(pts, n=20), taper(20, 1.0, 0.3, 3.0), C(70, 64, 56), bristle=0.3, rng=rng)
                k = 8
                lx = np.linspace(pts[0, 0], pts[-1, 0], k) + rng.normal(0, 6, k)
                ly = np.linspace(pts[0, 1], pts[-1, 1], k) + rng.normal(0, 6, k)
                dabs(cv, lx, ly, rng.uniform(12, 18, k), jitter(C(70, 110, 70), rng, k, dl=0.06), aspect=0.5,
                     shape='leaf', angle=rng.uniform(0, 6.28, k), split=0.1, rng=rng)
            flowers(cv, rng, rng.normal(960, 220, 70), rng.normal(900, 40, 70), rng.uniform(5, 9, 70))
            dapple(cv, rng, rng.uniform(760, 1250, 10), rng.uniform(860, 980, 10), rng.uniform(40, 80, 10),
                   C(232, 214, 128), flatten=0.25, opacity=(0.45, 0.8), cluster=7, mode='lock')
            note = L['note'] + ' + the mound with the knee/hand imprints, flowers, broken vines'
        elif name == 'beams':
            angs = np.radians([100, 104, 108, 112])
            beams(cv, rng, (SUN[0], SUN[1]), angs, 3000, [110, 170, 90, 150], C(255, 240, 196), opacity=0.42,
                  spread_w=1.2, streak=0.55, start_fade=0.4, end_len=0.98)
            glow(cv, 1000, 760, 520, C(255, 240, 204), 0.18, squash=0.6)
            note = 'stronger sunbeams through the gap onto the empty clearing'
        else:
            note = L['note']
        P.add(name, L['depth'], cv, note)
    P.save(source='S01 end frame (rows 1860-2900)', sun=[SUN[0], SUN[1]], knee=list(KNEE), hand=list(HAND))
    return P
