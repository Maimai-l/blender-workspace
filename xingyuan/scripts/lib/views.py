# Comparison camera set, matched to the reference photos. Used by render_views.py.
# loc/target in plan metres (X east, Y north, Z = hall floor). Calibrated: aerial (9 points, 3.7 px rms);
# B1court / B3north estimated from known sizes in the photo; the others hand-matched.
VIEWS = {
    'aerial':  dict(loc=(37.91, -62.43, 70.17), target=(37.82, -47.95, 56.38), lens=24.23, roll=-0.0092, res=(1400, 644),
                    elev=48, azim=125, exposure=0.15),
    'B1court': dict(loc=(35.15, 11.1, 0.5), target=(37.15, -8.9, 0.5), lens=11.1, res=(1400, 1046), elev=35, azim=150,
                    exposure=0.6),
    'B3south': dict(loc=(20.65, 50.2, 1.45), target=(20.65, 30.2, 1.45), lens=22.0, shift=(0.0, 0.07), res=(1400, 644),
                    elev=40, azim=330, exposure=0.6),
    'B3north': dict(loc=(20.62, 29.9, 1.59), target=(20.62, 49.9, 2.85), lens=48.5, res=(1400, 1822),
                    elev=40, azim=200, exposure=0.6),
    'A5':      dict(loc=(29.6, 41.0, 1.6), target=(12.2, 40.4, 3.4), lens=26.0, res=(1400, 1000), elev=38, azim=95,
                    exposure=0.6, clip=1.0),
    'A2':      dict(loc=(45.40, 15.09, 1.90), target=(25.41, 14.96, 2.57), lens=42.03, roll=-0.0018, res=(1400, 958),
                    elev=40, azim=110, exposure=0.6, stretch=1.467, hide=('B1_紫叶李',)),   # solved camera; photo stretched x1.47
    'B1pav':   dict(loc=(29.6, 16.4, 1.2), target=(35.4, 24.0, 2.6), lens=22.0, res=(1400, 1009), elev=40, azim=200,
                    exposure=0.6),
    'B2':      dict(loc=(55.2, 40.04, 1.0), target=(41.28, 40.04, 3.6), lens=30.0, res=(1400, 1596), elev=42, azim=120,
                    exposure=0.6),
    'A3porch': dict(loc=(59.2, 47.6, 1.55), target=(59.0, 32.0, 2.4), lens=20.0, res=(1400, 2318), elev=40, azim=110,
                    exposure=2.2),
}
