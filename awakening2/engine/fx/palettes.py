"""palettes.py - sunrise effect palettes (sRGB 0..1).

Lobe palettes are (4, 3) arrays: rows = shadow, mid, lit, line.
Shape palettes are dicts of lit / shade / ink colours.
The light is warm gold; shadows lean to cool violet and blue-green so effects sit in
the same picture as the painted backgrounds.
"""
from .core import hexc, pal

# --- lobes: shadow, mid, lit, line ----------------------------------------------------------
DUST = pal('#7c6474', '#c39a6e', '#f2dcab', '#594252')        # forest-floor dust at sunrise
DUST_DRY = pal('#8a7584', '#d1ad80', '#f7e6bd', '#655061')    # paler, for the wind ring
DUST_DARK = pal('#5e4b5c', '#9a7660', '#d9b88c', '#3f2f3c')   # soil dust from the rise
SMOKE = pal('#56505f', '#857c88', '#b8adae', '#3c3644')       # engine sputter smoke
STEAM = pal('#9b98b4', '#d8d2d6', '#fbf6ec', '#7b789a')       # pale exhaust / mist
TRAIL_MIST = pal('#9a88c4', '#f3c7b6', '#fff7ea', '#7a68a6')  # climax trail mist (cool shadows)
VEIL = pal('#8d7a86', '#bea084', '#e8d2aa', '#6f5b69')        # thin dust veil behind soil

# --- debris: lit, shade, ink ------------------------------------------------------------------
INK = hexc('#23161d')
DEBRIS = {
    'clod':   dict(lit=hexc('#8f6548'), shade=hexc('#4c3743'), ink=hexc('#22151b')),
    'crumb':  dict(lit=hexc('#7d583f'), shade=hexc('#463240'), ink=hexc('#22151b')),
    'pebble': dict(lit=hexc('#b0a39b'), shade=hexc('#6c6478'), ink=hexc('#272230')),
    'moss':   dict(lit=hexc('#a3b957'), shade=hexc('#4d6d4f'), ink=hexc('#1f2e22')),
    'root':   dict(lit=hexc('#a07a58'), shade=hexc('#5b4049'), ink=hexc('#26171c')),
    'vine':   dict(lit=hexc('#86a650'), shade=hexc('#3f5e49'), ink=hexc('#1c2a1f')),
    'bark':   dict(lit=hexc('#8b7363'), shade=hexc('#4f4352'), ink=hexc('#241b22')),
}

# --- leaves: front lit/shade, back lit/shade, ink, vein ---------------------------------------
LEAF = {
    'green':  dict(f_lit=hexc('#a9c45a'), f_sh=hexc('#557a4c'), b_lit=hexc('#cfd9a0'),
                   b_sh=hexc('#8a9a7c'), ink=hexc('#26361f'), vein=hexc('#6f8f42')),
    'deep':   dict(f_lit=hexc('#7fa64d'), f_sh=hexc('#3f6047'), b_lit=hexc('#b9c992'),
                   b_sh=hexc('#76887a'), ink=hexc('#1d2b1c'), vein=hexc('#557a3b')),
    'gold':   dict(f_lit=hexc('#e7b649'), f_sh=hexc('#a86a3e'), b_lit=hexc('#efd59a'),
                   b_sh=hexc('#b3927a'), ink=hexc('#4a2a1c'), vein=hexc('#c08a3a')),
    'rust':   dict(f_lit=hexc('#d98a45'), f_sh=hexc('#8f4c3c'), b_lit=hexc('#e9c49a'),
                   b_sh=hexc('#a7887c'), ink=hexc('#3e1f1a'), vein=hexc('#b06a35')),
}

# --- flames (inner to outer) ---------------------------------------------------------------
FLAME = [hexc('#fffdf2'), hexc('#ffe46b'), hexc('#ffa036'), hexc('#c4482c')]
FLAME_LINE = hexc('#8e2f26')

# --- trail ribbon -----------------------------------------------------------------------------
TRAIL = dict(core=hexc('#fffef6'), gold=hexc('#ffe9a6'), edge=hexc('#ff9a62'),
             rim=hexc('#c7577a'))

# --- wind / grass -----------------------------------------------------------------------------
GRASS = dict(lit=hexc('#d6e39a'), mid=hexc('#9fbd66'), shade=hexc('#5d7f5a'))
WIND_LINE = hexc('#fff4d8')

# --- impact frames ----------------------------------------------------------------------------
IMPACT = {
    'black_gold': (hexc('#f5b631'), hexc('#140c0b')),   # (background, figure)
    'gold_black': (hexc('#140c0b'), hexc('#f5b631')),
    'inverted':   (hexc('#fbf3e3'), hexc('#120e14')),
    'red_black':  (hexc('#d8432a'), hexc('#120b0b')),
}

LIGHT_GOLD = hexc('#ffd889')
LIGHT_WARM = hexc('#ffc27a')
