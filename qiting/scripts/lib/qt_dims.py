# Qiting (旗亭) replica - every main dimension in one place, with where it came from.
# Units: metres. Frame: origin on the pavilion axis at the podium-top floor (Z = 0);
# +Y = north (the podium stair and the pavilion entrance face north, as in the DWG screenshot), +X = east.
#
# Sources (details and error estimates in qiting/docs/dimensions.md):
#   DWG  = screenshot of 芙蓉园规划地形图0917-1.dwg, scaled at 0.245 m/px by registering it to the 1:1500 master
#          plan (two shared pavilions, and a chamfer fit of the road, stream and lake shore: 0.243 / 0.248 m/px).
#   W02  = web photo 02 (Canon SX610 at 19.3 mm, ~170 m away): an almost orthographic elevation, 75.6 px/m once
#          the coping is fixed to the DWG radius. Floor line at y = 1500 px.
#   340d, W01, W03, W04, af3b, 419 = other photos used for checks (see the doc).
import math

# ------------------------------------------------------------------ podium (台基)
Z_PLAZA = -4.80          # plaza round the terraces (W02 terrace base -4.6); it falls to -5.0 at the stair foot (north)
R_COPING = 5.42          # podium coping edge (DWG circle 22.1 px; W02 410 px)
R_DRUM = 5.27            # relief ground; its raised border is 5 cm proud = 5.32 (W02 402 px)
COPING_T = 0.26          # coping slab thickness (W02 y 1500-1520)
RELIEF_H = 2.25          # carved band (W03 drum 2.52 m with plinth; 340d ~2.1 m; W07 vs the AC unit ~2.0-2.2 m)
PLINTH_H = 0.24          # moulded base course under the carving (340d, 419)
TIER_R = (7.33, 9.26, 11.20)    # three terraces (DWG notched outlines, median radius 29.9 / 37.8 / 45.7 px)
TIER_NOTCH_W, TIER_NOTCH_D = 0.60, 0.85   # 8 notches per terrace at the column azimuths (DWG ~2.5 px x 3.5 px)
Z_TIER_TOP = -(COPING_T + RELIEF_H + PLINTH_H)               # -2.75
TIER_H = (Z_TIER_TOP - Z_PLAZA) / 3.0                          # 0.617 each

# podium-top balustrade (W02 posts at 351-358 px; DWG inner circle 19.95 px = 4.89 m is its base)
R_BAL = 4.72
BAL_N = 24               # post pitch ~1.2 m (W02 front posts ~90 px apart) -> 24 = 3 per column bay
BAL_POST_W = 0.20        # W02 15 px
BAL_POST_H = 1.48        # W02 y 1388
BAL_RAIL_H = 0.93        # top of the hand rail (寻杖), W02 y 1430

# podium stair (north): three flights and two landings, measured on the calibrated W02 view (east parapet posts at
# r 8.47 / 10.50 and 14.47 / 15.58 with tops 1.45 and 3.10 m under the podium posts; the parapet ends at r 20.9, 5.0 m
# below the podium floor). Re-measured in round 2 with the corrected W02 camera (azimuth 14.8 deg); round 1 had used
# the first, unrotated W02 solution. 34 equal risers of 0.147 m; the aerials A1/A2 show three flights and two
# landings, and three more steps beyond the parapet ends down to the north path.
STAIR_W_CLEAR = 1.60     # between the parapets. The DWG (2.45 m) and master-plan (2.3 m) stair lines are the OUTER
                         # faces; the aerials A1/A2 show the stair 0.6x as wide as round 1 had it, and af3b fits a
                         # 1.6 m clear width best (round 1 took 2.4 m as the clear width)
STAIR_PARAPET = 0.30     # outer width 2.20 m
STAIR_FLIGHTS = [(10, 0.337), (11, 0.395), (13, 0.443)]    # (risers, tread) per flight, top flight first
STAIR_LANDINGS = [2.05, 1.13]
STAIR_R0 = 5.42          # top riser at the coping edge on the axis
STAIR_RISERS = sum(n for n, t in STAIR_FLIGHTS)            # 34
Z_STAIR_FOOT = -5.00     # plaza level at the stair foot (W02); the plaza falls 0.2 m from the terraces to here
STAIR_EXTRA = (3, 0.36, 0.15)   # steps beyond the parapet ends down to the north path: count, tread, riser (A1/A2)
STAIR_DOOR = (5.55, 0.50, -2.00, -1.30)   # small doors in both side walls by the drum (W02 east, 340d west): r, w, z0, z1

# ------------------------------------------------------------------ pavilion, lower storey
N_COL = 8
COL_AZ0 = 67.5           # deg from +X; columns at 67.5 + 45k so the entrance bay is centred on +Y (af3b, W02)
R_COL = 4.37             # outer ring (W02 front columns at +-0.924R / +-0.383R)
COL_D0, COL_D1 = 0.37, 0.33      # base / top diameter (W02 28 px)
R_COL_IN = 2.83          # inner ring = upper drum radius (W02 214 px; 340d inner columns at ~0.69 R)
COL_IN_D = 0.34
Z_ARCH = (3.17, 3.44)    # architrave 阑额 (W02 y 1240-1260)
Z_FRIEZE = (2.91, 3.17)  # lattice frieze, 3 openings per bay (W02 1260-1280; 340d)
Z_LOWBEAM = (2.78, 2.91) # lower beam (W02 1280-1290)
Z_BAND1 = (3.44, 4.29)   # plaster bracket band 栱眼壁 (W02 shows to 3.84 under the eave; af3b/W01 band ~0.8 m)
EAVE1_FASCIA_R = 6.24    # red fascia + rafter ends (W02 471.7 px, y 1180-1202 -> z 3.94-4.23)
EAVE1_FASCIA_Z = (3.94, 4.23)
EAVE1_R = 6.37           # tile edge (W02 481 px)
ROOF1 = [(6.38, 4.48), (6.08, 4.56), (5.62, 4.69), (5.18, 4.83), (4.74, 4.96), (4.30, 5.09), (3.87, 5.27),
         (3.43, 5.47), (2.98, 5.64)]    # tile-top profile (r, z) traced on W02
Z_ROOF1_TOP = 5.80       # roof meets the upper drum under a tiled collar (W02 junction 5.86)

# ------------------------------------------------------------------ upper storey
R_DRUM2 = R_COL_IN
Z_SILL2 = (5.80, 5.95)   # red sill (W02 1050-1057)
Z_WIN2 = (5.95, 6.48)    # window band, 3 panels per bay (W02 1010-1050, W01)
Z_BEAM2 = (6.48, 6.62)   # beam over the windows
Z_BAND2 = (6.62, 7.44)   # plaster bracket band (W02 visible to 7.21)
EAVE2_FASCIA_R = 4.82    # (W02 364.5 px, y 935-952 -> z 7.25-7.47)
EAVE2_FASCIA_Z = (7.25, 7.47)
EAVE2_R = 5.03           # tile edge (W02 380 px)
ROOF2 = [(5.00, 7.71), (4.37, 7.88), (3.93, 8.03), (3.48, 8.20), (3.04, 8.38), (2.60, 8.58), (2.17, 8.82),
         (1.73, 9.06), (1.29, 9.32), (0.84, 9.52)]   # tile-top profile traced on W02

# ------------------------------------------------------------------ finial (宝顶), W02 y 783 / 650 / 640 / 578
FINIAL_Z0 = 9.48
FINIAL_RINGS = 6         # stacked rings tapering upward (W02)
FINIAL_R0, FINIAL_R1 = 0.78, 0.40
FINIAL_Z_RINGS_TOP = 11.24
FINIAL_Z_NECK = 11.38
FINIAL_Z_TOP = 12.20     # top of the bulb
FINIAL_BULB_R = 0.37
FINIAL_ROD_TOP = 13.30   # thin rod above the bulb (W01, af3b; length estimated)

# ------------------------------------------------------------------ boards
PLAQUE_W, PLAQUE_H = 1.15, 0.66      # af3b: 225 x 130 px at ~200 px/m
COUPLET_W, COUPLET_L = 0.30, 1.95    # af3b; 5 characters, the lower ones hidden in every photo
PLAQUE_TEXT = '旗亭'                 # read right to left on the board
COUPLET_TEXT = ('時有落花', '遠聞流水')  # west column (upper line) / east column; 5th characters not visible -> blank

# ------------------------------------------------------------------ plaza (platform paving at the podium foot)
PLAZA_R_OUT = 29.5       # outer edge: the near-circular outer line of the DWG plaza (广场), 29-31 m; the dusk photo's
                         # camera (27 m west) stands on paving
# the lobed line inside (below) is drawn in the paving as a band of pale setts (the pale arcs in the dusk photo)
# r(theta) of the paved platform from the DWG (theta from +X, counter-clockwise, degrees); notches are planting beds
PLAZA_R = [(0, 24.3), (15, 24.6), (30, 24.8), (35, 23.8), (39, 17.6), (46, 17.6), (52, 23.6), (65, 24.8),
           (80, 24.4), (90, 24.5), (100, 24.2), (115, 24.0), (128, 24.4), (133, 17.6), (140, 17.6), (146, 24.4),
           (160, 24.2), (180, 24.2), (190, 23.3), (195, 21.8), (205, 17.8), (215, 16.8), (225, 15.2), (235, 18.2),
           (245, 17.9), (255, 17.4), (265, 15.9), (270, 15.8), (275, 15.9), (285, 17.4), (295, 17.7), (305, 16.3),
           (315, 15.2), (322, 15.4), (330, 17.3), (340, 18.9), (345, 21.9), (350, 23.2), (360, 24.3)]
# theta is measured counter-clockwise from east in the scene frame (the DWG image has y pointing south, so its
# angles were mirrored). North half ~24.5 m with planting beds on the diagonals; south half 15-18 m, lobed.

def col_az(k, inner=False):
    return math.radians(COL_AZ0 + 45.0 * k)

def interp(table, x):
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0.0
            return y0 + (y1 - y0) * t
    return table[-1][1]

def roof1_z(r):
    """lower roof tile-top height at radius r (extrapolated a little beyond the traced range)."""
    pts = sorted(ROOF1)
    return interp(pts, r)

def roof2_z(r):
    pts = sorted(ROOF2)
    return interp(pts, r)

def plaza_r(theta_deg):
    return interp(PLAZA_R, theta_deg % 360.0)


def plaza_z(x, y):
    """plaza surface: -4.80 round the terraces, falling 0.20 m toward the stair foot on the north (W02 stair foot -5.0)."""
    if y <= 12.0:
        return Z_PLAZA
    t = min(1.0, (y - 12.0) / 9.0)
    w = max(0.0, 1.0 - abs(x) / 14.0)              # only the north lobe falls
    return Z_PLAZA - 0.20 * t * w
