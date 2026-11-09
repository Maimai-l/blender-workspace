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
from ..imprint import paint_imprint

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
            # floor: a little darker and richer overall, cool dark foreground
            Xf, Yf = cv.coords()
            cv.multiply(0.88)
            cv.lock_tint(C(28, 38, 58), (smoothstep(880, 1060, Yf) * 0.45).astype(np.float32))
            # the imprint where the robot knelt (ground frame: gx right, gz toward the camera)
            O = (1000.0, 905.0)
            shapes = [
                dict(kind='ellipse', c=(110, 30), r=(130, 120), depth=1.0),                    # knee hollow
                dict(kind='capsule', a=(170, 0), b=(330, -120), r0=62, r1=46, depth=0.55),   # shin trough
                dict(kind='ellipse', c=(350, -170), r=(58, 85), depth=0.5),                  # toe dig
                dict(kind='ellipse', c=(-215, -60), r=(118, 106), depth=0.75),               # palm
            ]
            palm = np.array([-215.0, -60.0])
            for tip in [(-420, 95), (-310, 225), (-160, 260)]:                              # three fingers
                d_ = np.array(tip) - palm
                st = palm + d_ / np.hypot(*d_) * 80
                shapes.append(dict(kind='capsule', a=tuple(st), b=tip, r0=38, r1=31, depth=0.85, dig=0.8))
            paint_imprint(cv, rng, O, shapes, squash=0.34, box=(520, 740, 1480, 1040), sun=(0.45, -0.7, 0.55),
                          light_pool=(125, 45, 62, 50),
                          roots=[((30, -95), (60, -40), 9), ((215, -40), (185, 5), 7), ((-150, -120), (-170, -75), 6),
                                 ((-300, -10), (-255, 20), 6)],
                          flower_n=26, rim_moss=1.0)
            # scattered flowers and clods thrown out around it
            flowers(cv, rng, rng.normal(1000, 300, 14), rng.normal(900, 50, 14), rng.uniform(5, 9, 14))
            note = L['note'] + ' + the imprint: deep knee hollow, shin trough, three-fingered hand print, torn ' \
                'moss and roots, flowers at the rim, light pooling in the knee hollow'
        elif name == 'beams':
            angs = np.radians([101, 106, 111])
            beams(cv, rng, (SUN[0], SUN[1]), angs, 3000, [90, 140, 80], C(255, 240, 196), opacity=0.32,
                  spread_w=1.2, streak=0.55, start_fade=0.4, end_len=0.98)
            # the beam that lands on the imprint (strongest at the floor)
            top = np.array([1060.0, -60.0])
            bot = np.array([1120.0, 915.0])
            n_ = 16
            t_ = np.linspace(0, 1, n_)
            P_ = top[None] * (1 - t_[:, None]) + bot[None] * t_[:, None]
            stroke(cv, P_, 70 + 150 * t_, C(255, 238, 190), opacity=0.08 + 0.3 * t_ ** 1.5, edge=0.9, bristle=0.6,
                   rag=0.2, spacing=8.0, rng=rng)
            glow(cv, 1120, 915, 160, C(255, 236, 190), 0.3, squash=0.4)
            note = 'stronger sunbeams through the gap onto the empty clearing'
        else:
            note = L['note']
            if name in ('mist_far', 'mist_mid'):
                cv.img *= 0.72                                      # less cream veil
            elif name == 'near':
                Xn, Yn = cv.coords()
                cv.multiply(0.86)
                cv.lock_tint(C(24, 32, 50), (smoothstep(700, 1060, Yn) * 0.35).astype(np.float32))
            elif name == 'fg':
                cv.multiply(0.72)
            elif name == 'far':
                cv.multiply(0.94)
        P.add(name, L['depth'], cv, note)
    P.save(source='S01 end frame (rows 1860-2900)', sun=[SUN[0], SUN[1]], knee=list(KNEE), hand=list(HAND))
    return P
