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
TRAIL_MIST = pal('#c4b4dc', '#f7dfcf', '#fffaf0', '#a898c8')  # climax trail mist: soft lilac shadows
VEIL = pal('#8d7a86', '#bea084', '#e8d2aa', '#6f5b69')        # thin dust veil behind soil
SOIL_DUST = pal('#4a3d3c', '#6e5d52', '#9a8670', '#3a2e2c')   # earthy brown-grey soil dust (round 6)
DUST_WARM = pal('#8a8088', '#b3a89f', '#eadcc4', '#7a7078')   # translucent warm grey blast / wash dust
WIND_WHITE = pal('#c9cfd6', '#eef0ee', '#ffffff', '#b8c0c8')  # wind ring brush strokes and mist

# tone opacities (shadow, mid, lit) for the translucent styles
WIND_DUST = pal('#a9a6a8', '#d6d1c9', '#f6f1e6', '#9a979b')   # light mist / dust thrown by the wind ring
# round 9
DUST_WALL = pal('#7a6c86', '#c2a07c', '#f4dcae', '#5e5168')   # opaque launch dust wall: cool violet
                                                              # underside, warm tan body, cream-gold tops
EARTH = dict(lit=hexc('#b88a56'), shade=hexc('#7a5139'), ink=hexc('#4f3426'))   # warm rise soil
EARTH_DUST = pal('#8a7468', '#b89a7a', '#dcc29c', '#6f5a50')  # light two-tone soil dust
TRAIL_ENV = pal('#b7a3d8', '#f4d4b8', '#fff2d2', '#9d89c4')   # trail mist envelope: lilac shadow side,
                                                              # warm peach body, warm cream sun side

TONE_ALPHA = {'dust': (0.6, 0.62, 0.86), 'soil': (0.8, 0.86, 0.94), 'mist': (0.3, 0.38, 0.5),
              'wind': (0.42, 0.48, 0.74)}

# --- debris: lit, shade, ink ------------------------------------------------------------------
INK = hexc('#23161d')
DEBRIS = {      # coloured lines (brown for soil and wood, dark green for plants), never black
    'clod':   dict(lit=hexc('#8f6548'), shade=hexc('#4c3743'), ink=hexc('#3b2622')),
    'crumb':  dict(lit=hexc('#7d583f'), shade=hexc('#463240'), ink=hexc('#3b2622')),
    'pebble': dict(lit=hexc('#b0a39b'), shade=hexc('#6c6478'), ink=hexc('#45404d')),
    'moss':   dict(lit=hexc('#a3b957'), shade=hexc('#4d6d4f'), ink=hexc('#2c4429')),
    'root':   dict(lit=hexc('#a07a58'), shade=hexc('#5b4049'), ink=hexc('#46302a')),
    'vine':   dict(lit=hexc('#86a650'), shade=hexc('#3f5e49'), ink=hexc('#2c4429')),
    'bark':   dict(lit=hexc('#8b7363'), shade=hexc('#4f4352'), ink=hexc('#43342f')),
}

# stone variants for pebbles (lit, shade, line): warm / cool / brown / blue greys, sandstone
PEBBLES = [
    dict(lit=hexc('#b9ada0'), shade=hexc('#776a68'), ink=hexc('#4f4542')),
    dict(lit=hexc('#a9adb3'), shade=hexc('#666879'), ink=hexc('#45434e')),
    dict(lit=hexc('#a8988a'), shade=hexc('#6c5e5e'), ink=hexc('#4a3f3c')),
    dict(lit=hexc('#9ea6ab'), shade=hexc('#5d6473'), ink=hexc('#3f4350')),
    dict(lit=hexc('#c6b497'), shade=hexc('#85726a'), ink=hexc('#57483f')),
]

# --- leaves: front lit/shade, back lit/shade, ink, vein ---------------------------------------
LEAF = {
    'green':  dict(f_lit=hexc('#a9c45a'), f_sh=hexc('#557a4c'), b_lit=hexc('#cfd9a0'),
                   b_sh=hexc('#8a9a7c'), ink=hexc('#26361f'), vein=hexc('#4f6e38')),
    'deep':   dict(f_lit=hexc('#7fa64d'), f_sh=hexc('#3f6047'), b_lit=hexc('#b9c992'),
                   b_sh=hexc('#76887a'), ink=hexc('#1d2b1c'), vein=hexc('#3a5a31')),
    'gold':   dict(f_lit=hexc('#e7b649'), f_sh=hexc('#a86a3e'), b_lit=hexc('#efd59a'),
                   b_sh=hexc('#b3927a'), ink=hexc('#4a2a1c'), vein=hexc('#a1652f')),
    'rust':   dict(f_lit=hexc('#d98a45'), f_sh=hexc('#8f4c3c'), b_lit=hexc('#e9c49a'),
                   b_sh=hexc('#a7887c'), ink=hexc('#3e1f1a'), vein=hexc('#8a4a2c')),
}

# --- flames (inner to outer) ---------------------------------------------------------------
FLAME = [hexc('#fffdf2'), hexc('#ffe46b'), hexc('#ffa036'), hexc('#c4482c')]
FLAME_LINE = hexc('#8e2f26')

# --- trail ribbon -----------------------------------------------------------------------------
TRAIL = dict(core=hexc('#fffef6'), gold=hexc('#ffe2a2'), edge=hexc('#ffc98a'),
             rim=hexc('#f3b493'))

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
