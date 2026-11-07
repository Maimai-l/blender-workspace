# Beauty shots (效果图), 1920 x 1080. Each: camera (loc, target, lens) and its light: sun bearing (from north,
# clockwise), elevation, sky strength. Summer daylight in Xi'an (34 N): afternoon sun from the south-west, and late
# afternoon / evening sun from the west-north-west for the views of the north stair.
HEROES = {
    'hero_stair':  {'loc': (1.6, 31.0, -3.15), 'target': (0.0, 4.0, 3.2), 'lens': 30, 'res': (1920, 1080),
                    'azim': 296, 'elev': 24, 'sky': 0.09, 'exposure': 0.25},
    'hero_sw':     {'loc': (-30.1, -10.9, 0.0), 'eye': 1.6, 'target': (0.0, 0.0, 2.8), 'lens': 30, 'res': (1920, 1080),
                    'azim': 235, 'elev': 38, 'sky': 0.08, 'exposure': 0.15},
    'hero_eave':   {'loc': (2.2, 7.4, 1.65), 'target': (-0.6, 2.0, 5.6), 'lens': 20, 'res': (1920, 1080),
                    'azim': 300, 'elev': 28, 'sky': 0.10, 'exposure': 0.45},
    'hero_relief': {'loc': (-11.0, 5.2, -3.2), 'target': (-5.0, 1.6, -1.45), 'lens': 32, 'res': (1920, 1080),
                    'azim': 205, 'elev': 22, 'sky': 0.08, 'exposure': 0.20},
    'hero_aerial': {'loc': (30.0, 30.0, 26.0), 'target': (0.0, 0.0, -1.5), 'lens': 32, 'res': (1920, 1080),
                    'azim': 225, 'elev': 45, 'sky': 0.08, 'exposure': 0.05},
    'hero_dusk':   {'loc': (-20.0, 13.5, -3.25), 'target': (0.0, 0.0, 3.0), 'lens': 26, 'res': (1920, 1080),
                    'azim': 292, 'elev': 4.0, 'sky': 0.10, 'sun': 4.0, 'sun_color': (1.0, 0.60, 0.33), 'exposure': 0.55},
    # round 2: the surroundings. 'eye' = camera height above the terrain (the z of 'loc' is then ignored)
    'hero_lake':   {'loc': (-70.0, 85.0, 52.0), 'target': (8.0, -120.0, -14.0), 'lens': 24, 'res': (1920, 1080),
                    'azim': 250, 'elev': 36, 'sky': 0.08, 'exposure': 0.10},
    # eye-level cameras placed where the tree list leaves a clear line to the pavilion
    'hero_shore':  {'loc': (1.0, -57.0, 0.0), 'eye': 1.6, 'target': (0.0, 0.0, 5.0), 'lens': 32, 'res': (1920, 1080),
                    'azim': 205, 'elev': 42, 'sky': 0.08, 'exposure': 0.15},
    'hero_garden': {'loc': (57.7, 6.1, 0.0), 'eye': 1.6, 'target': (0.0, 1.0, 3.5), 'lens': 32, 'res': (1920, 1080),
                    'azim': 125, 'elev': 32, 'sky': 0.09, 'exposure': 0.20},
    'hero_vista':  {'loc': (3.0, -9.5, 1.3), 'target': (-6.0, -270.0, -2.0), 'lens': 32, 'res': (1920, 1080),
                    'azim': 260, 'elev': 34, 'sky': 0.08, 'exposure': 0.10},
}
