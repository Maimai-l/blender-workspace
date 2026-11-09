"""Three robot concepts for the design round (blockouts, drawn by the look engine).

A  "Hearth Warden": a hunched furnace giant. Bell-shaped body like an old iron
   stove, a furnace door with louvres on the chest, a small domed head sunk
   low between huge shoulder domes, heavy brow over two round lamp eyes,
   barrel forearms, short massive legs, two engine bells on the back.
B  "Lantern Samurai": a tall armoured sentinel. Broad-brimmed helmet with a
   crest, a masked face with eye slits, hanging lamellar shoulder plates, a
   narrow waist and skirt plates, long greaved legs, tall back thrusters.
C  "Diving-Bell Titan": a riveted deep-sea giant. A big round diving helmet
   with portholes (two eyes, one grille), ribbed hoses to a boiler torso,
   long arms with big fists, short bowed legs, a turbine pack on the back.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
from r3d import (sd_sphere, sd_ellipsoid, sd_box, sd_capsule, sd_round_cone, sd_cyl,
                 sd_torus, U, SU, SUB, SSUB, INT, rot_matrix)
from rig import Rig, Part, PAINT, METAL, LENS, GLOW, DARK, LIDS

V = 0.07   # concept-round voxel size (m)


def concept_a():
    r = Rig('conceptA')
    # pelvis (root)
    def pelvis(p):
        a = sd_box(p, (0, 0, 0.2), (2.5, 1.8, 1.2), r=0.5)
        b = sd_box(p, (0, 1.3, -0.4), (1.1, 0.7, 1.0), r=0.35)   # front plate
        return SU(a, b, 0.2)
    r.add(Part('pelvis', None, (0, 0, 9.2), pelvis, (-3, -2.5, -1.8), (3, 2.5, 1.8), V))

    def torso(p):
        chest = sd_ellipsoid(p, (0, 0.2, 5.0), (4.1, 3.1, 3.6))
        belly = sd_round_cone(p, (0, 0.3, 0.6), (0, 0.4, 3.8), 2.3, 3.4)
        back = sd_box(p, (0, -2.2, 5.2), (2.8, 1.6, 2.4), r=0.6)       # engine housing
        d = SU(SU(chest, belly, 0.8), back, 0.5)
        # furnace door: a flat front face with a slight inset
        face = sd_box(p, (0, 3.35, 4.6), (1.9, 0.35, 1.7), r=0.3)
        d = SU(d, face, 0.25)
        slots = U(*[sd_box(p, (0, 3.75, 3.6 + i * 0.5), (1.4, 0.4, 0.09), r=0.05) for i in range(5)])
        d = SUB(d, slots)
        # top collar where the head sits
        collar = sd_torus(p, (0, 1.1, 7.6), 1.55, 0.45)
        d = SU(d, collar, 0.4)
        return d
    r.add(Part('torso', 'pelvis', (0, 0, 1.0), torso, (-4.6, -4.2, -0.5), (4.6, 4.2, 9.0), V))
    # engine bells (separate dark metal part)
    def bells(p):
        b1 = SUB(sd_round_cone(p, (1.4, -3.4, 4.6), (1.6, -4.4, 2.6), 0.7, 1.25),
                 sd_round_cone(p, (1.4, -3.45, 4.5), (1.62, -4.5, 2.4), 0.55, 1.1))
        b2 = SUB(sd_round_cone(p, (-1.4, -3.4, 4.6), (-1.6, -4.4, 2.6), 0.7, 1.25),
                 sd_round_cone(p, (-1.4, -3.45, 4.5), (-1.62, -4.5, 2.4), 0.55, 1.1))
        return U(b1, b2)
    r.add(Part('bells', 'torso', (0, 0, 0), bells, (-3.2, -6, 1.0), (3.2, -2.5, 6.0), V, METAL))
    def core(p):
        return sd_box(p, (0, 3.2, 4.6), (1.3, 0.2, 1.3), r=0.2)
    r.add(Part('core', 'torso', (0, 0, 0), core, (-1.6, 2.8, 3.1), (1.6, 3.6, 6.1), V, GLOW))

    def head(p):
        dome = sd_ellipsoid(p, (0, 0.2, 1.1), (1.65, 1.55, 1.45))
        jaw = sd_box(p, (0, 0.6, 0.15), (1.2, 1.1, 0.75), r=0.45)
        d = SU(dome, jaw, 0.4)
        brow = sd_box(p, (0, 1.25, 1.35), (1.75, 0.55, 0.32), r=0.25)
        d = SU(d, brow, 0.15)
        sockets = U(sd_sphere(p, (0.65, 1.55, 0.85), 0.5), sd_sphere(p, (-0.65, 1.55, 0.85), 0.5))
        d = SUB(d, sockets)
        vents = U(*[sd_box(p, (0, 1.75, 0.0 - i * 0.22), (0.55, 0.3, 0.05), r=0.03) for i in range(3)])
        d = SUB(d, vents)
        return d
    r.add(Part('head', 'torso', (0, 1.2, 7.4), head, (-2, -1.6, -1.0), (2, 2.4, 2.8), V * 0.6))
    def eyes(p):
        return U(sd_sphere(p, (0.65, 1.35, 0.85), 0.4), sd_sphere(p, (-0.65, 1.35, 0.85), 0.4))
    r.add(Part('eyes', 'head', (0, 0, 0), eyes, (-1.2, 0.8, 0.3), (1.2, 1.9, 1.4), V * 0.4, LENS))

    # shoulders: domes attached to the upper arms
    def upperarm(p):
        return sd_round_cone(p, (0, 0, -0.3), (0, 0, -3.9), 1.05, 0.95)
    r.add_pair('upperarm', 'torso', (4.0, 0.3, 6.6), upperarm, (-1.5, -1.5, -4.6), (1.5, 1.5, 0.6), V)
    def pauldron(p):
        dome = sd_ellipsoid(p, (0.5, 0, 0.5), (2.3, 2.5, 1.8))
        cut = sd_box(p, (0.5, 0, -1.6), (3, 3, 1.4))
        d = SUB(dome, cut)
        rim = sd_torus(p, (0.5, 0, -0.1), 2.05, 0.28, rot_matrix(0, 0, 0))
        return SU(d, rim, 0.1)
    r.add_pair('pauldron', 'upperarm_R', (0.2, 0, 0.3), pauldron, (-2.5, -3, -0.8), (3.2, 3, 2.6), V)
    def forearm(p):
        a = sd_round_cone(p, (0, 0, -0.2), (0, 0.1, -4.2), 1.15, 1.5)
        bands = U(sd_cyl(p, (0, 0.05, -1.5), (0, 0.05, -1.9), 1.42, 0.08),
                  sd_cyl(p, (0, 0.09, -3.4), (0, 0.09, -3.8), 1.62, 0.08))
        return SU(a, bands, 0.05)
    r.add_pair('forearm', 'upperarm_R', (0, 0, -4.1), forearm, (-2, -2, -4.8), (2, 2, 1.2), V)
    def hand(p):
        palm = sd_box(p, (0, 0.2, -0.9), (1.0, 0.75, 0.9), r=0.35)
        f1 = sd_capsule(p, (0.55, 0.65, -1.6), (0.6, 1.0, -2.7), 0.36)
        f2 = sd_capsule(p, (-0.05, 0.7, -1.7), (-0.05, 1.05, -2.85), 0.36)
        f3 = sd_capsule(p, (-0.62, 0.62, -1.6), (-0.7, 0.95, -2.6), 0.34)
        th = sd_capsule(p, (0.9, 0.5, -0.7), (1.3, 1.0, -1.5), 0.36)
        return SU(SU(palm, U(f1, f2, f3), 0.2), th, 0.2)
    r.add_pair('hand', 'forearm_R', (0, 0.1, -4.4), hand, (-1.6, -1, -3.4), (2, 1.8, 0.3), V * 0.8)

    def thigh(p):
        return sd_round_cone(p, (0, 0, 0), (0, 0.1, -3.6), 1.35, 1.15)
    r.add_pair('thigh', 'pelvis', (1.9, 0, -0.5), thigh, (-1.8, -1.8, -4.4), (1.8, 1.8, 1.6), V)
    def shin(p):
        a = sd_round_cone(p, (0, 0, -0.1), (0, -0.1, -3.6), 1.25, 1.55)
        knee = sd_ellipsoid(p, (0, 0.9, 0.1), (1.0, 0.7, 0.9))
        return SU(a, knee, 0.2)
    r.add_pair('shin', 'thigh_R', (0, 0.1, -3.7), shin, (-2, -2, -4.4), (2, 2, 1.2), V)
    def foot(p):
        a = sd_box(p, (0, 0.8, -0.9), (1.5, 2.3, 0.75), r=0.45)
        heel = sd_ellipsoid(p, (0, -0.4, -0.4), (1.3, 1.2, 0.9))
        return SU(a, heel, 0.4)
    r.add_pair('foot', 'shin_R', (0, -0.1, -3.6), foot, (-2, -2, -1.9), (2, 3.4, 0.6), V)
    return r


def concept_b():
    r = Rig('conceptB')
    def pelvis(p):
        a = sd_box(p, (0, 0, 0), (1.6, 1.2, 0.9), r=0.3)
        skirt = U(sd_box(p, (0, 1.2, -1.3), (1.1, 0.25, 1.4), r=0.15),
                  sd_box(p, (1.55, 0.3, -1.2), (0.25, 1.0, 1.3), r=0.15, R=rot_matrix(0, -12, 0)),
                  sd_box(p, (-1.55, 0.3, -1.2), (0.25, 1.0, 1.3), r=0.15, R=rot_matrix(0, 12, 0)))
        return U(a, skirt)
    r.add(Part('pelvis', None, (0, 0, 11.0), pelvis, (-2.3, -1.8, -3), (2.3, 1.8, 1.2), V))
    def torso(p):
        waist = sd_round_cone(p, (0, 0, 0.2), (0, 0.1, 2.5), 1.3, 2.0)
        chest = sd_box(p, (0, 0.2, 4.2), (2.6, 1.8, 1.9), r=0.7)
        d = SU(waist, chest, 0.6)
        plate = sd_box(p, (0, 1.85, 4.3), (1.4, 0.3, 1.3), r=0.2)
        d = SU(d, plate, 0.1)
        slit = sd_box(p, (0, 2.2, 4.3), (0.15, 0.3, 0.9), r=0.05)
        d = SUB(d, slit)
        pack = sd_box(p, (0, -2.0, 4.5), (1.6, 0.9, 1.8), r=0.4)
        return SU(d, pack, 0.3)
    r.add(Part('torso', 'pelvis', (0, 0, 0.8), torso, (-3.2, -3.2, -0.5), (3.2, 2.8, 6.8), V))
    def thrusters(p):
        return U(sd_cyl(p, (1.0, -2.9, 2.5), (1.0, -2.9, 8.0), 0.55, 0.15),
                 sd_cyl(p, (-1.0, -2.9, 2.5), (-1.0, -2.9, 8.0), 0.55, 0.15))
    r.add(Part('thrusters', 'torso', (0, 0, 0), thrusters, (-2, -4, 1.8), (2, -1.8, 8.8), V, METAL))
    def head(p):
        skull = sd_ellipsoid(p, (0, 0.1, 0.9), (0.95, 1.05, 1.0))
        brim = sd_cyl(p, (0, 0, 1.15), (0, 0, 1.4), 2.0, 0.1)
        crest = sd_box(p, (0, 0.6, 2.4), (0.12, 0.4, 1.0), r=0.08, R=rot_matrix(-20, 0, 0))
        mask = sd_box(p, (0, 0.85, 0.5), (0.8, 0.35, 0.65), r=0.25)
        d = U(SU(skull, mask, 0.2), brim, crest)
        slits = U(sd_box(p, (0.38, 1.25, 0.75), (0.28, 0.2, 0.06), r=0.03),
                  sd_box(p, (-0.38, 1.25, 0.75), (0.28, 0.2, 0.06), r=0.03))
        return SUB(d, slits)
    r.add(Part('head', 'torso', (0, 0.3, 6.2), head, (-2.3, -2.3, -0.4), (2.3, 2.3, 3.7), V * 0.6))
    def eyes(p):
        return U(sd_box(p, (0.38, 1.05, 0.75), (0.25, 0.1, 0.045)), sd_box(p, (-0.38, 1.05, 0.75), (0.25, 0.1, 0.045)))
    r.add(Part('eyes', 'head', (0, 0, 0), eyes, (-0.8, 0.8, 0.6), (0.8, 1.3, 0.9), V * 0.3, LENS))
    def upperarm(p):
        return sd_round_cone(p, (0, 0, -0.2), (0, 0, -3.8), 0.75, 0.7)
    r.add_pair('upperarm', 'torso', (3.0, 0.2, 5.2), upperarm, (-1.2, -1.2, -4.4), (1.2, 1.2, 0.6), V)
    def sode(p):
        plates = U(*[sd_box(p, (0.9, 0, -0.2 - i * 0.75), (0.25 + 0.04 * i, 1.6, 0.42), r=0.12,
                            R=rot_matrix(0, -14, 0)) for i in range(4)])
        return plates
    r.add_pair('sode', 'upperarm_R', (0.4, 0, 0.5), sode, (-0.5, -2.2, -3.8), (2.2, 2.2, 0.8), V)
    def forearm(p):
        return SU(sd_round_cone(p, (0, 0, -0.2), (0, 0.1, -4.0), 0.85, 0.95),
                  sd_box(p, (0.6, 0.0, -2.2), (0.35, 0.9, 1.5), r=0.2), 0.2)
    r.add_pair('forearm', 'upperarm_R', (0, 0, -3.9), forearm, (-1.4, -1.4, -4.8), (1.4, 1.4, 0.8), V)
    def hand(p):
        palm = sd_box(p, (0, 0.1, -0.7), (0.65, 0.45, 0.7), r=0.2)
        f = U(*[sd_capsule(p, (x, 0.25, -1.3), (x, 0.55, -2.3), 0.2) for x in (-0.45, -0.15, 0.15, 0.45)])
        th = sd_capsule(p, (0.6, 0.35, -0.6), (0.9, 0.8, -1.2), 0.22)
        return SU(palm, U(f, th), 0.12)
    r.add_pair('hand', 'forearm_R', (0, 0.1, -4.2), hand, (-1, -0.8, -2.8), (1.4, 1.4, 0.3), V * 0.7)
    def thigh(p):
        return sd_round_cone(p, (0, 0, 0), (0, 0.1, -4.6), 0.95, 0.8)
    r.add_pair('thigh', 'pelvis', (1.1, 0, -0.6), thigh, (-1.3, -1.3, -5.6), (1.3, 1.3, 1.2), V)
    def shin(p):
        a = sd_round_cone(p, (0, 0, 0), (0, -0.1, -4.6), 0.85, 0.75)
        greave = sd_box(p, (0, 0.55, -2.0), (0.8, 0.45, 2.4), r=0.25)
        return SU(a, greave, 0.2)
    r.add_pair('shin', 'thigh_R', (0, 0.1, -4.7), shin, (-1.3, -1.3, -5.5), (1.3, 1.5, 1.0), V)
    def foot(p):
        return sd_box(p, (0, 0.7, -0.6), (0.9, 1.7, 0.5), r=0.3)
    r.add_pair('foot', 'shin_R', (0, -0.1, -4.7), foot, (-1.2, -1.4, -1.3), (1.2, 2.7, 0.3), V)
    return r


def concept_c():
    r = Rig('conceptC')
    def pelvis(p):
        return sd_ellipsoid(p, (0, 0, 0), (2.2, 1.8, 1.3))
    r.add(Part('pelvis', None, (0, 0, 6.6), pelvis, (-2.6, -2.2, -1.6), (2.6, 2.2, 1.6), V))
    def torso(p):
        boiler = sd_round_cone(p, (0, 0, 0.5), (0, 0.6, 4.6), 2.4, 3.1)
        rings = U(*[sd_torus(p, (0, 0.15 + 0.12 * i, 1.0 + i * 1.1), 2.45 + 0.17 * i, 0.12) for i in range(4)])
        d = SU(boiler, rings, 0.05)
        pack = sd_cyl(p, (0, -2.8, 2.0), (0, -2.8, 6.0), 1.4, 0.3)
        return SU(d, pack, 0.4)
    r.add(Part('torso', 'pelvis', (0, 0, 0.6), torso, (-3.8, -4.5, -0.5), (3.8, 4.0, 8.2), V))
    def head(p):
        helm = sd_sphere(p, (0, 0, 1.6), 2.0)
        ring = sd_torus(p, (0, 0, 0.0), 1.6, 0.35)
        d = SU(helm, ring, 0.3)
        port = U(sd_cyl(p, (0.8, 1.6, 1.9), (0.9, 2.2, 1.9), 0.55, 0.12),
                 sd_cyl(p, (-0.8, 1.6, 1.9), (-0.9, 2.2, 1.9), 0.55, 0.12),
                 sd_cyl(p, (0, 1.8, 0.9), (0, 2.25, 0.9), 0.45, 0.1))
        d = U(d, port)
        holes = U(sd_cyl(p, (0.85, 1.7, 1.9), (0.95, 2.4, 1.9), 0.4, 0.05),
                  sd_cyl(p, (-0.85, 1.7, 1.9), (-0.95, 2.4, 1.9), 0.4, 0.05))
        return SUB(d, holes)
    r.add(Part('head', 'torso', (0, 0.8, 5.0), head, (-2.4, -2.4, -0.6), (2.4, 2.6, 3.8), V * 0.6))
    def eyes(p):
        return U(sd_sphere(p, (0.85, 1.55, 1.9), 0.38), sd_sphere(p, (-0.85, 1.55, 1.9), 0.38))
    r.add(Part('eyes', 'head', (0, 0, 0), eyes, (-1.4, 1.0, 1.3), (1.4, 2.1, 2.5), V * 0.4, LENS))
    def hoses(p):
        return U(*[sd_capsule(p, (s * 1.5, 1.2, 4.2), (s * 1.9, 0.8, 5.6), 0.32) for s in (-1, 1)])
    r.add(Part('hoses', 'torso', (0, 0, 0), hoses, (-2.6, 0.2, 3.6), (2.6, 1.8, 6.2), V, METAL))
    def upperarm(p):
        return sd_round_cone(p, (0, 0, 0), (0, 0, -4.8), 1.0, 0.9)
    r.add_pair('upperarm', 'torso', (3.4, 0.3, 4.2), upperarm, (-1.3, -1.3, -5.6), (1.3, 1.3, 1.2), V)
    def shoulder(p):
        return sd_sphere(p, (0.2, 0, 0.1), 1.6)
    r.add_pair('shoulder', 'upperarm_R', (0, 0, 0), shoulder, (-1.6, -1.8, -1.6), (2, 1.8, 1.9), V)
    def forearm(p):
        return sd_round_cone(p, (0, 0, 0), (0, 0.2, -5.2), 1.0, 1.25)
    r.add_pair('forearm', 'upperarm_R', (0, 0, -4.8), forearm, (-1.6, -1.6, -6.6), (1.6, 1.8, 1.2), V)
    def hand(p):
        fist = sd_box(p, (0, 0.3, -1.0), (1.2, 1.0, 1.1), r=0.55)
        return fist
    r.add_pair('hand', 'forearm_R', (0, 0.2, -5.4), hand, (-1.6, -1.2, -2.4), (1.6, 1.6, 0.4), V)
    def thigh(p):
        return sd_round_cone(p, (0, 0, 0), (0.2, 0.3, -2.6), 1.2, 1.0)
    r.add_pair('thigh', 'pelvis', (1.6, 0, -0.6), thigh, (-1.6, -1.6, -3.8), (1.8, 2.0, 1.4), V)
    def shin(p):
        return sd_round_cone(p, (0, 0, 0), (-0.1, -0.1, -2.6), 1.05, 1.3)
    r.add_pair('shin', 'thigh_R', (0.2, 0.3, -2.7), shin, (-1.6, -1.6, -4.0), (1.6, 1.6, 1.2), V)
    def foot(p):
        return sd_ellipsoid(p, (0, 0.6, -0.4), (1.5, 2.2, 0.8))
    r.add_pair('foot', 'shin_R', (-0.1, -0.1, -2.7), foot, (-1.8, -1.8, -1.4), (1.8, 3.0, 0.6), V)
    return r


CONCEPTS = {'A': concept_a, 'B': concept_b, 'C': concept_c}
