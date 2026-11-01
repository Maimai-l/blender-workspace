# Beauty shots (效果图), 1920 x 1080. Each: camera (loc, target, lens) and its light: sun bearing (from north,
# clockwise), elevation, sky strength. Summer daylight in Xi'an (34 N): afternoon sun from the south-west, and late
# afternoon / evening sun from the west-north-west for the views of the north stair.
HEROES = {
    'hero_stair':  {'loc': (1.6, 31.0, -3.15), 'target': (0.0, 4.0, 3.2), 'lens': 30, 'res': (1920, 1080),
                    'azim': 296, 'elev': 24, 'sky': 0.09, 'exposure': 0.25},
    'hero_sw':     {'loc': (-27.0, -21.0, -2.6), 'target': (0.0, 0.0, 2.6), 'lens': 34, 'res': (1920, 1080),
                    'azim': 235, 'elev': 38, 'sky': 0.08, 'exposure': 0.15},
    'hero_eave':   {'loc': (2.2, 7.4, 1.65), 'target': (-0.6, 2.0, 5.6), 'lens': 20, 'res': (1920, 1080),
                    'azim': 300, 'elev': 28, 'sky': 0.10, 'exposure': 0.45},
    'hero_relief': {'loc': (-11.0, 5.2, -3.2), 'target': (-5.0, 1.6, -1.45), 'lens': 32, 'res': (1920, 1080),
                    'azim': 205, 'elev': 22, 'sky': 0.08, 'exposure': 0.20},
    'hero_aerial': {'loc': (30.0, 30.0, 26.0), 'target': (0.0, 0.0, -1.5), 'lens': 32, 'res': (1920, 1080),
                    'azim': 225, 'elev': 45, 'sky': 0.08, 'exposure': 0.05},
    'hero_dusk':   {'loc': (-20.0, 13.5, -3.25), 'target': (0.0, 0.0, 3.0), 'lens': 26, 'res': (1920, 1080),
                    'azim': 292, 'elev': 4.0, 'sky': 0.10, 'sun': 4.0, 'sun_color': (1.0, 0.60, 0.33), 'exposure': 0.55},
}
