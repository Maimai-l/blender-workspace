# Xingyuan - master layout (plan coordinates, metres; X east, Y north, Z up; hall floors at z = 0).
# All numbers come from the floor plan (column dots / wall lines) and the two sections; see notes.
import math

XC = 35.15            # symmetry axis of the B1 axis (gate, B1 pavilion)
Z0 = 0.0              # raised floors (halls, corridors, pavilions)
ZC = -0.60            # courtyards and surrounding ground
Z_WATER = -0.86       # B3 pool water
Z_POOL = -1.45        # B3 pool bottom

# halls: origin (porch column line, first end column), rotation, depth D, length L, bays, door bays
HALLS = {
    'A1': dict(ox=43.60, oy=0.36, rot=0, D=12.05, L=23.10, nb=7, doors=(2, 3, 4), back=(), open_bay=3, court_edge=1.60),
    'A2': dict(ox=26.70, oy=23.46, rot=180, D=12.02, L=23.10, nb=7, doors=(2, 3, 4), back=(), open_bay=None, court_edge=1.58),
    'A5': dict(ox=12.20, oy=48.29, rot=180, D=12.08, L=16.50, nb=5, doors=(1, 2, 3), back=(), open_bay=None, court_edge=0.80),
    'A4': dict(ox=29.10, oy=31.79, rot=0, D=12.18, L=16.50, nb=5, doors=(2,), back=(2,), open_bay=None, court_edge=0.80),
    'A3': dict(ox=58.09, oy=31.79, rot=0, D=12.11, L=16.50, nb=5, doors=(2,), back=(), open_bay=None, court_edge=0.80),
}

def hall_rect(h, back_edge=1.6, end_edge=1.45):
    """platform rectangle (x0, y0, x1, y1) of a hall"""
    s = HALLS[h]
    ox, oy, D, L = s['ox'], s['oy'], s['D'], s['L']
    if s['rot'] == 0:
        x0, x1 = ox - s['court_edge'], ox + D + back_edge
        y0, y1 = oy - end_edge, oy + L + end_edge
    else:
        x0, x1 = ox - D - back_edge, ox + s['court_edge']
        y0, y1 = oy - L - end_edge, oy + end_edge
    return (x0, y0, x1, y1)

# ------------------------------------------------------------------ raised floors (z = 0)
# label: 1 = hall (granite faces), 2 = corridor / pavilion (dark brick faces), 3 = gate
RAISED = []
for _h in HALLS:
    RAISED.append((hall_rect(_h), 1, _h))
RAISED += [
    # spine corridor (B1 north / B3 south), both column rows at y 26.57 / 28.67
    ((10.20, 25.67, 61.00, 29.57), 2, 'spine'),
    # links between the spine and A5 / A4 / A3 porches, and A2 / A1 porch north ends
    ((10.20, 29.00, 13.00, 31.00), 2, 'link_A5'),
    ((28.30, 29.00, 31.30, 31.00), 2, 'link_A4'),
    ((31.30, 29.57, 42.88, 30.34), 2, 'strip_A4S'),
    ((56.90, 29.00, 60.30, 31.00), 2, 'link_A3'),
    ((13.08, 24.50, 28.28, 26.00), 2, 'link_A2'),
    ((42.00, 24.50, 57.25, 26.00), 2, 'link_A1'),
    # B3 pavilions
    ((16.10, 25.67, 25.20, 31.37), 2, 'B3S'),
    ((16.10, 48.70, 25.20, 57.76), 2, 'B3N'),
    # B3 north corridors + links to the A5 / A4 porch ends
    ((10.20, 50.53, 16.10, 54.40), 2, 'B3N_W'),
    ((25.20, 50.53, 31.10, 54.40), 2, 'B3N_E'),
    ((10.20, 49.00, 13.00, 51.00), 2, 'link_A5N'),
    ((28.30, 49.00, 31.10, 51.00), 2, 'link_A4N'),
    # B1 pavilion
    ((30.60, 20.48, 39.70, 27.00), 2, 'B1P'),
    # gate complex (B1 south): wings + gate house
    ((23.37, -6.10, 27.10, 0.33), 3, 'gateW1'),
    ((27.10, -6.10, 31.10, -2.15), 3, 'gateW2'),
    ((31.10, -6.83, 39.20, -0.55), 3, 'gateH'),
    ((39.20, -6.10, 43.20, -2.15), 3, 'gateE2'),
    ((43.20, -6.10, 46.93, 0.33), 3, 'gateE1'),
    # A3-1
    ((59.50, 22.90, 66.40, 31.90), 2, 'A3-1'),
]

# ------------------------------------------------------------------ courtyards (z = -0.6) : paving per zone
COURTS = {
    'B1': dict(rect=(26.0, -2.40, 44.3, 22.0), mat='M_Granite', sw=0.60, sl=0.90, along='y'),
    'B3': dict(rect=(12.0, 28.5, 29.2, 51.5), mat='M_Granite', sw=0.75, sl=1.00, along='x'),
    'B2': dict(rect=(41.0, 29.0, 60.5, 56.2), mat='M_PaverDark', sw=0.40, sl=0.80, along='x'),
}

# B3 pool (outline at the terrace edge): rectangle with notches (plan)
POOL_C = (20.60, 40.05)
def pool_rects():
    cx, cy = POOL_C
    hx, hy = 6.165, 7.275
    nx, nd_tb, ny, nd_s = 2.76, 1.00, 4.00, 0.86
    r = [(cx - hx, cy - hy + nd_tb, cx + hx, cy + hy - nd_tb),          # middle band
         (cx - hx, cy - hy, cx - nx, cy - ny),                           # bottom-left ear
         (cx + nx, cy - hy, cx + hx, cy - ny),                           # bottom-right ear
         (cx - hx, cy + ny, cx - nx, cy + hy),                           # top-left ear
         (cx + nx, cy + ny, cx + hx, cy + hy)]                           # top-right ear
    cut = [(cx - hx, cy - ny, cx - hx + nd_s, cy + ny), (cx + hx - nd_s, cy - ny, cx + hx, cy + ny)]
    return r, cut

LANTERNS_B3 = [(16.19, 45.69), (25.08, 45.69), (16.19, 34.40), (25.08, 34.40)]
STELE_B3 = (20.60, 39.00)

# ------------------------------------------------------------------ stairs: (top-centre x, y), direction (down), width, steps, z_top, z_bot
STAIRS = [
    ((35.15, -6.83), (0, -1), 3.10, 4, Z0, ZC, 'gate_S'),
    ((35.15, -0.55), (0, 1), 3.70, 4, Z0, ZC, 'gate_N'),
    ((28.28, 11.95), (1, 0), 3.70, 4, Z0, ZC, 'A2'),
    ((42.00, 11.95), (-1, 0), 3.70, 4, Z0, ZC, 'A1'),
    ((35.15, 20.48), (0, -1), 3.40, 4, Z0, ZC, 'B1P'),
    ((13.00, 40.04), (1, 0), 3.70, 4, Z0, ZC, 'A5'),
    ((28.30, 40.04), (-1, 0), 3.70, 4, Z0, ZC, 'A4'),
    ((20.62, 31.37), (0, 1), 4.00, 4, Z0, ZC, 'B3S'),
    ((20.62, 48.70), (0, -1), 4.00, 4, Z0, ZC, 'B3N'),
    ((42.88, 40.04), (1, 0), 3.70, 4, Z0, ZC, 'A4B'),
    ((57.29, 40.04), (-1, 0), 3.70, 4, Z0, ZC, 'A3'),
]

# B1 tree planters (from the aerial and the B1 photos)
PLANTERS_B1 = [(32.00, 4.70), (38.30, 4.70), (32.00, 15.30), (38.30, 15.30)]   # from the calibrated aerial photo

SITE_BOX = (-8.0, -36.0, 78.0, 64.0)   # covers the env terraces / plaza next to the complex

# B2 bamboo garden: E-W path between the A4 and A3 stairs (dark stone) + a narrow N-S flagstone path; bamboo elsewhere
B2_PATH = (42.90, 37.84, 57.30, 42.24)
B2_PATH2 = (49.10, 29.60, 50.30, 37.84)
B2_BEDS = [('B2_竹丛_西南', (43.0, 29.75, 49.0, 37.75), 5), ('B2_竹丛_东南', (50.4, 29.75, 56.8, 37.75), 6),
           ('B2_竹丛_北', (43.0, 42.35, 56.8, 55.55), 7)]
