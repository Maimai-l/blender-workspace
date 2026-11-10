"""Colour design for the Japanese white-eye (mejiro) and the flock birds.

Every zone has four tones: 0 light, 1 shadow, 2 rim (warm backlight edge), 3 highlight.
Paint id = zone * 4 + tone (id 0 = empty).  Shadow tones default to base x cool multiplier
(the same rule as the robot look engine) with a few hand-picked overrides.
"""
import numpy as np


def _c(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


ZONES = ['none', 'olive', 'yellow', 'white', 'buff', 'undertail', 'ring', 'eye', 'lores',
         'forehead', 'coverts', 'flight', 'tail', 'beak_up', 'beak_lo', 'mouth', 'leg',
         'uw_cov', 'uw_flight', 'catch', 'edge', 'sil', 'sil_lit', 'thigh', 'tail_under']
Z = {n: i for i, n in enumerate(ZONES)}

INK = _c('#3a2519')            # warm dark brown line, not black

BASE = {
    'olive':     '#8f9c3f',
    'yellow':    '#ebd24c',
    'white':     '#eeebdf',
    'buff':      '#cfbc98',
    'undertail': '#e6d67e',
    'ring':      '#faf8f0',
    'eye':       '#2b1d17',
    'lores':     '#3d3d22',
    'forehead':  '#a8b246',
    'coverts':   '#8a983f',
    'flight':    '#5b5a36',
    'tail':      '#5f5e39',
    'beak_up':   '#4a4440',
    'beak_lo':   '#7e7d82',
    'mouth':     '#b0574c',
    'leg':       '#7a7780',
    'uw_cov':    '#e2dcc4',
    'uw_flight': '#bab59d',
    'catch':     '#ffffff',
    'edge':      '#a6b151',
    'sil':       '#2e2526',
    'sil_lit':   '#55463f',
    'thigh':     '#c9b896',
    'tail_under': '#77735a',
}
SHADOW_OVERRIDE = {
    'white':  '#b4b2ba',
    'ring':   '#d6d5d8',
    'yellow': '#b09a52',
    'eye':    '#2b1d17',
    'catch':  '#ffffff',
    'buff':   '#978c86',
    'sil':    '#2e2526',
    'sil_lit': '#4a3d38',
    'uw_cov': '#a59f8c',
    'uw_flight': '#8a8676',
}
DEFAULT_SHADOW_MUL = np.array([0.66, 0.70, 0.86])
DEFAULT_RIM = _c('#ffd890')


def build_palette(shadow_mul=None, rim_color=None, rim_mix=0.62, overrides=None):
    """Return (128, 4) premultiplied RGBA float32 palette indexed by paint id."""
    sm = DEFAULT_SHADOW_MUL if shadow_mul is None else np.asarray(shadow_mul, float)
    rc = DEFAULT_RIM if rim_color is None else np.asarray(rim_color, float)
    base = dict(BASE)
    if overrides:
        base.update(overrides)
    pal = np.zeros((128, 4), np.float32)
    for name, idx in Z.items():
        if name == 'none':
            continue
        b = _c(base[name]) if isinstance(base[name], str) else np.asarray(base[name], float)
        if name in SHADOW_OVERRIDE and shadow_mul is None and not (overrides and name in overrides):
            s = _c(SHADOW_OVERRIDE[name])        # (an overridden colour gets its shadow from its own hue)
        else:
            s = np.clip(b * sm, 0, 1)
        if name in ('eye', 'catch'):
            s = b
        # rim: warm light wrapping the edge, built on the shadow tone so it reads as backlight
        r = np.clip(s * (1 - rim_mix) + rc * rim_mix * (0.55 + 0.6 * b.mean()), 0, 1)
        hlt = np.clip(b + (1 - b) * 0.35, 0, 1)
        for tone, col in enumerate((b, s, r, hlt)):
            pal[idx * 4 + tone, :3] = col
            pal[idx * 4 + tone, 3] = 1.0
    return pal


def pid(zone, tone=0):
    return Z[zone] * 4 + tone
