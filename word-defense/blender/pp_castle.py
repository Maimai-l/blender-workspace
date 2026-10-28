# pp_castle.py - the paper castle: folded card walls with cut-out windows, octagonal towers, paper-cone roofs,
# banners and flags, lit from inside so the walls glow like a paper lantern.
import math, random
import numpy as np
from mathutils import Vector, Matrix
from pp_lib import (MB, obj, solidify, frame, shape2d, sd_box, sd_circle, sd_poly, cut_edge, light, washi, glow, rgba, wood,
                    _new_mat, _coords, _noise, _map_range, _mix_rgb, _math, _set, _scale_vec)
import bpy


def stone_mat(name, base, mortar, var):
    """Card printed with irregular hand-drawn stones (cell outlines), a soft wash, and grime toward the base."""
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    tc = N.new('ShaderNodeTexCoord')
    wob = N.new('ShaderNodeTexNoise')
    L.new(tc.outputs['Object'], wob.inputs['Vector'])
    wob.inputs['Scale'].default_value = 3.0; wob.inputs['Detail'].default_value = 2.0
    off = N.new('ShaderNodeVectorMath'); off.operation = 'SUBTRACT'
    L.new(wob.outputs['Color'], off.inputs[0]); off.inputs[1].default_value = (0.5, 0.5, 0.5)
    sc = N.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'
    L.new(off.outputs[0], sc.inputs[0]); sc.inputs['Scale'].default_value = 0.04
    add = N.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    L.new(tc.outputs['Object'], add.inputs[0]); L.new(sc.outputs[0], add.inputs[1])
    squash = _scale_vec(N, L, add.outputs[0], (1.0, 1.0, 1.9))
    vor = N.new('ShaderNodeTexVoronoi')
    vor.feature = 'DISTANCE_TO_EDGE'
    L.new(squash, vor.inputs['Vector'])
    vor.inputs['Scale'].default_value = 6.5
    _set(vor, Randomness=0.85)
    lines = _map_range(N, L, vor.outputs['Distance'], 0.0, 0.022, 1.0, 0.0)
    m = _noise(N, L, vec, 0.9, 3.0, 0.55)
    col = _mix_rgb(N, L, _map_range(N, L, m, 0.35, 0.7, 0.0, 1.0), rgba(base), rgba(var))
    cell = N.new('ShaderNodeTexVoronoi'); cell.feature = 'F1'
    L.new(squash, cell.inputs['Vector']); cell.inputs['Scale'].default_value = 6.5
    _set(cell, Randomness=0.85)
    col = _mix_rgb(N, L, _map_range(N, L, cell.outputs['Color'], 0.0, 1.0, 0.0, 0.22), col, rgba(var))
    col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', lines, 0.55), col, rgba(mortar))
    sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    grime = _map_range(N, L, sep.outputs['Z'], 0.1, 0.75, 0.32, 0.0)
    col = _mix_rgb(N, L, grime, col, rgba(mortar))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.88)
    _set(bsdf, **{'Specular IOR Level': 0.15, 'Sheen Weight': 0.3, 'Sheen Roughness': 0.6})
    gn = _noise(N, L, vec, 170.0, 2.0, 0.5)
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.002
    L.new(gn, bump.inputs['Height']); L.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    tr = N.new('ShaderNodeBsdfTranslucent'); L.new(col, tr.inputs['Color'])
    mix = N.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.22
    L.new(bsdf.outputs[0], mix.inputs[1]); L.new(tr.outputs[0], mix.inputs[2])
    out = N.new('ShaderNodeOutputMaterial')
    L.new(mix.outputs[0], out.inputs['Surface'])
    if 'Thickness' in out.inputs:
        out.inputs['Thickness'].default_value = 0.02
    return mat


def tile_mat(name, base, line, var):
    """Roof card printed with rows of tiles (bands up the cone)."""
    mat, N, L = _new_mat(name)
    vec, oi = _coords(N, L)
    tc = N.new('ShaderNodeTexCoord')
    w = N.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = 'Z'
    L.new(tc.outputs['Object'], w.inputs['Vector'])
    w.inputs['Scale'].default_value = 5.2
    w.inputs['Distortion'].default_value = 0.0
    try:
        w.wave_profile = 'SAW'
    except Exception:
        pass
    lines = _map_range(N, L, w.outputs['Fac'], 0.86, 0.99, 0.0, 1.0)
    m = _noise(N, L, vec, 1.4, 3.0, 0.55)
    col = _mix_rgb(N, L, _map_range(N, L, m, 0.35, 0.7, 0.0, 1.0), rgba(base), rgba(var))
    col = _mix_rgb(N, L, _math(N, L, 'MULTIPLY', lines, 0.45), col, rgba(line))
    bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(col, bsdf.inputs['Base Color'])
    _set(bsdf, Roughness=0.8)
    _set(bsdf, **{'Specular IOR Level': 0.25, 'Sheen Weight': 0.2})
    out = N.new('ShaderNodeOutputMaterial')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def arch_fn(cx, z0, w, h):
    """Round-topped opening: box plus a half disc."""
    r = w / 2
    def fn(X, Y):
        box = sd_box(X, Y, cx, z0 + (h - r) / 2, r, (h - r) / 2)
        return np.minimum(box, sd_circle(X, Y, cx, z0 + h - r, r))
    return fn


def panel_fn(w, h, merlon=0.15, gap=0.11, notch=0.12, holes=(), seed=0):
    """A wall card w x h (base at 0) with crenellations along the top and cut-out holes."""
    period = merlon + gap
    n = max(0, int((w - merlon) / period))
    used = n * period + merlon
    start = -used / 2 + merlon + gap / 2

    def fn(X, Y):
        d = sd_box(X, Y, 0.0, h / 2, w / 2, h / 2)
        if merlon > 0 and notch > 0:
            for k in range(n):
                cx = start + k * period
                d = np.maximum(d, -sd_box(X, Y, cx, h - notch / 2 + 0.02, gap / 2, notch / 2 + 0.02))
        for hole in holes:
            d = np.maximum(d, -hole(X, Y))
        return cut_edge(d, X, Y, seed, amp=0.0025, freq=9.0, fine=0.0012, fine_freq=40.0)

    return fn, (-w / 2, 0.0, w / 2, h)


def build(C, origin, mats, rng_seed=3):
    """origin: (x, y) of the castle centre. The gate faces west (-X), toward the end of the path."""
    ox, oy = origin
    rng = random.Random(rng_seed)
    stone = stone_mat('P_Stone', '#E4DACA', '#B6A890', '#D8CCB8')
    stone_dark = stone_mat('P_StoneShade', '#D9CEBB', '#B9AA92', '#CFC3AE')
    roof = tile_mat('P_RoofTiles', '#A4503E', '#8A3C2F', '#B05C47')
    trim = washi('P_Trim', '#3B3F72', '#454A7C', transl=0.0)
    vellum = glow('P_Vellum', '#FFC27A', 5.5)
    flagm = washi('P_Flag', '#E7B44C', '#F0C463', transl=0.25)
    banner = washi('P_Banner', '#8C2F3C', '#9A3846', transl=0.15)
    emblem = washi('P_Emblem', '#E8B955', '#F2C86A', transl=0.0)
    plank = wood('P_Plank', '#5A3D2A', '#7A5639')
    base_m = washi('P_Plinth', '#9E99C2', '#AAA5CA', transl=0.0, mscale=0.6)

    walls = MB()      # slot 0 stone
    towers = MB()
    roofs = MB()
    glows = MB()
    trims = MB()
    flags = MB()
    banners = MB()

    def card_into(mb, fn_b, M, step=0.008, slot=0):
        fn, b = fn_b
        verts2d, faces = shape2d(fn, b, step)
        mb.add([(x, y, 0.0) for x, y in verts2d], faces, slot, M)

    def window_glow(mb, M, cx, z0, w, h, inset=0.035):
        Mi = M @ Matrix.Translation((0, 0, -inset))
        fn = arch_fn(cx, z0 - 0.02, w + 0.04, h + 0.04)
        verts2d, faces = shape2d(fn, (cx - w, z0 - 0.05, cx + w, z0 + h + 0.05), 0.01)
        mb.add([(x, y, 0.0) for x, y in verts2d], faces, 0, Mi)

    # ---- plinth: two stacked card layers with rounded corners
    for k, (pw, pd, z) in enumerate(((3.25, 2.35, 0.05), (3.0, 2.1, 0.1))):
        fn = lambda X, Y, pw=pw, pd=pd: cut_edge(sd_box(X, Y, 0.0, 0.0, pw / 2, pd / 2, 0.18), X, Y, 9 + k, 0.004, 6.0, 0.002)
        verts2d, faces = shape2d(fn, (-pw / 2, -pd / 2, pw / 2, pd / 2), 0.015)
        mb = MB().add([(x, y, 0.0) for x, y in verts2d], faces, 0)
        ob = obj("CastlePlinth%d" % k, mb, C, [base_m], loc=(ox, oy, z))
        solidify(ob, 0.05, -1.0)
    zb = 0.1

    # ---- curtain walls (2.5 x 1.7), gate in the west wall
    WX, WY, WH = 2.5, 1.7, 0.95
    slits = lambda w: [arch_fn(x, 0.42, 0.05, 0.26) for x in np.linspace(-w / 2 + 0.35, w / 2 - 0.35, max(2, int(w / 0.5)))]
    sides = {
        'front': (frame((ox, oy - WY / 2, zb), (1, 0, 0), (0, 0, 1)), WX),
        'back': (frame((ox, oy + WY / 2, zb), (-1, 0, 0), (0, 0, 1)), WX),
        'east': (frame((ox + WX / 2, oy, zb), (0, 1, 0), (0, 0, 1)), WY),
        'west': (frame((ox - WX / 2, oy, zb), (0, -1, 0), (0, 0, 1)), WY),
    }
    gate = arch_fn(0.0, 0.0, 0.42, 0.62)
    for name, (M, w) in sides.items():
        holes = slits(w) if name != 'west' else [gate]
        card_into(walls, panel_fn(w, WH, holes=holes, seed=len(name)), M)
        if name == 'west':
            window_glow(glows, M, 0.0, 0.0, 0.42, 0.62, inset=0.06)
        else:
            for x in np.linspace(-w / 2 + 0.35, w / 2 - 0.35, max(2, int(w / 0.5))):
                window_glow(glows, M, x, 0.42, 0.05, 0.26)

    # ---- gatehouse turrets either side of the gate
    def tower(cx, cy, r, h, roof_h, sides_n=8, windows=(), flag=True, crenel=True):
        ap = r * math.cos(math.pi / sides_n)
        pw = 2 * r * math.sin(math.pi / sides_n) + 0.006
        for k in range(sides_n):
            a = 2 * math.pi * k / sides_n + math.pi / sides_n
            n = (math.cos(a), math.sin(a), 0.0)
            u = (-math.sin(a), math.cos(a), 0.0)
            M = frame((cx + n[0] * ap, cy + n[1] * ap, zb), u, (0, 0, 1))
            holes = []
            for (kk, wz, ww, wh) in windows:
                if kk == k:
                    holes.append(arch_fn(0.0, wz, ww, wh))
                    window_glow(glows, M, 0.0, wz, ww, wh)
            card_into(towers, panel_fn(pw, h, merlon=pw * 0.3 if crenel else 0, gap=pw * 0.36, notch=0.1 if crenel else 0,
                                       holes=holes, seed=k + int(cx * 10)), M, 0.006)
        # roof: folded card pyramid, one facet per tower side, on a dark eave band
        rr = r * 1.26
        roofs.lathe([(rr, 0.0), (rr * 0.6, roof_h * 0.45), (rr * 0.18, roof_h * 0.86), (0.012, roof_h)], sides_n, 0,
                    Matrix.Translation((cx, cy, zb + h + 0.005)), smooth=False, cap_bottom=True, cap_top=False, phase=0.0)
        trims.lathe([(rr * 1.01, -0.04), (rr * 1.01, 0.012)], sides_n, 0, Matrix.Translation((cx, cy, zb + h + 0.005)),
                    cap_bottom=False, cap_top=False, phase=0.0)
        top = zb + h + 0.005 + roof_h
        if flag:
            flags.lathe([(0.011, 0.0), (0.011, 0.42)], 6, 1, Matrix.Translation((cx, cy, top - 0.02)))
            fz = top + 0.25
            side = 1 if rng.random() < 0.5 else -1
            tri = [(0.0, fz + 0.15, 0.0), (0.0, fz - 0.0, 0.0), (0.28, fz + 0.06, 0.0)]
            M = frame((cx, cy, 0.0), (1.0 * side, 0.0, 0.0), (0, 0, 1))
            pts = [(x * side, y) for x, y, _ in tri]
            fn = lambda X, Y, pts=pts: sd_poly(X, Y, pts)
            verts2d, faces = shape2d(fn, (min(p[0] for p in pts) - 0.02, fz - 0.02, max(p[0] for p in pts) + 0.02, fz + 0.17), 0.006)
            flags.add([(x, y, 0.0) for x, y in verts2d], faces, 0, frame((cx, cy, 0.0), (1, 0, 0), (0, 0, 1)))

    corner = [(-1, -1, 0.34, 1.45, 0.8), (1, -1, 0.34, 1.38, 0.78), (-1, 1, 0.36, 1.62, 0.86), (1, 1, 0.36, 1.55, 0.84)]
    for sx, sy, r, h, rh in corner:
        tower(ox + sx * WX / 2, oy + sy * WY / 2, r, h, rh, windows=[(5 if sy < 0 else 1, 0.75, 0.07, 0.22), (6, 1.05, 0.06, 0.16)])
    for s in (-1, 1):
        tower(ox - WX / 2 - 0.02, oy + s * 0.34, 0.17, 1.22, 0.42, sides_n=6, flag=False, crenel=False)

    # ---- keep with a tall round donjon
    KX, KY, KH = 1.15, 0.82, 1.85
    kx, ky = ox + 0.12, oy + 0.22
    kcols = lambda w: list(np.linspace(-w / 2 + 0.26, w / 2 - 0.26, 3)) if w > 1.0 else [0.0]
    kwin = lambda w: [arch_fn(x, z, 0.12, 0.26) for x in kcols(w) for z in (0.55, 1.15)]
    kp = {
        'front': (frame((kx, ky - KY / 2, zb), (1, 0, 0), (0, 0, 1)), KX),
        'back': (frame((kx, ky + KY / 2, zb), (-1, 0, 0), (0, 0, 1)), KX),
        'east': (frame((kx + KX / 2, ky, zb), (0, 1, 0), (0, 0, 1)), KY),
        'west': (frame((kx - KX / 2, ky, zb), (0, -1, 0), (0, 0, 1)), KY),
    }
    for name, (M, w) in kp.items():
        wins = kwin(w) if name in ('front', 'west', 'east') else []
        card_into(walls, panel_fn(w, KH, merlon=0.13, gap=0.1, notch=0.11, holes=wins, seed=20 + len(name)), M)
        if wins:
            for x in kcols(w):
                for z in (0.55, 1.15):
                    window_glow(glows, M, x, z, 0.12, 0.26)
    deck = MB().box((kx, ky, zb + KH - 0.13), (KX - 0.03, KY - 0.03, 0.02))
    obj("KeepDeck", deck, C, [trim])
    yard = MB().box((ox, oy, zb + 0.012), (WX - 0.04, WY - 0.04, 0.02))
    obj("Courtyard", yard, C, [base_m])
    # banners hanging on the keep front, gold disc printed on each
    for bx in (-0.33, 0.33):
        M = frame((kx + bx, ky - KY / 2 - 0.012, zb), (1, 0, 0), (0, 0, 1))
        fn = lambda X, Y: sd_poly(X, Y, [(-0.075, 1.72), (0.075, 1.72), (0.075, 1.12), (0.0, 1.03), (-0.075, 1.12)])
        verts2d, faces = shape2d(fn, (-0.09, 1.0, 0.09, 1.74), 0.004)
        banners.add([(x, y, 0.0) for x, y in verts2d], faces, 0, M)
        fn = lambda X, Y: sd_circle(X, Y, 0.0, 1.47, 0.045)
        verts2d, faces = shape2d(fn, (-0.06, 1.4, 0.06, 1.54), 0.003)
        banners.add([(x, y, 0.0) for x, y in verts2d], faces, 1, M @ Matrix.Translation((0, 0, 0.004)))
    tower(kx + KX / 2 - 0.2, ky + KY / 2 - 0.12, 0.3, 2.75, 1.05, windows=[(5, 1.9, 0.08, 0.24), (6, 2.3, 0.07, 0.2), (4, 2.1, 0.07, 0.2)])

    # ---- drawbridge across the moat to the end of the path, with chains
    bl = 1.22
    gx = ox - WX / 2 - 0.02
    planks = MB()
    for k in range(7):
        x = gx - 0.05 - (k + 0.5) * bl / 7
        planks.box((x, oy, 0.03), (bl / 7 - 0.012, 0.44, 0.022))
    planks.box((gx - bl / 2 - 0.05, oy - 0.235, 0.05), (bl, 0.03, 0.03))
    planks.box((gx - bl / 2 - 0.05, oy + 0.235, 0.05), (bl, 0.03, 0.03))
    obj("Drawbridge", planks, C, [plank])
    chains = MB()
    for s in (-1, 1):
        a = Vector((gx - bl + 0.02, oy + s * 0.22, 0.06)); b = Vector((gx - 0.03, oy + s * 0.22, zb + 0.78))
        dvec = b - a; L_ = dvec.length; dvec.normalize()
        M = Matrix.Translation(a) @ dvec.to_track_quat('Z', 'X').to_matrix().to_4x4()
        chains.lathe([(0.008, 0.0), (0.008, L_)], 5, 0, M)
    obj("Chains", chains, C, [trim])

    for name, mb, mlist, t in (("CastleWalls", walls, [stone], 0.02), ("CastleTowers", towers, [stone], 0.018),
                               ("CastleRoofs", roofs, [roof], 0.0), ("CastleGlow", glows, [vellum], 0.0),
                               ("CastleTrim", trims, [trim], 0.0), ("CastleFlags", flags, [flagm, trim], 0.004),
                               ("CastleBanners", banners, [banner, emblem], 0.003)):
        if not mb.v:
            continue
        ob = obj(name, mb, C, mlist)
        if t > 0:
            solidify(ob, t, -1.0)

    # ---- lights inside so the card walls glow
    LC = bpy.data.collections.get("Lights")
    for i, (x, y, z, e) in enumerate(((kx, ky, 1.1, 30.0), (kx + KX / 2 - 0.2, ky + KY / 2 - 0.12, 2.3, 18.0),
                                      (ox - WX / 2 + 0.25, oy, 0.5, 14.0), (ox + WX / 2 - 0.3, oy - WY / 2 + 0.3, 0.6, 10.0),
                                      (ox - WX / 2 + 0.05, oy - WY / 2 + 0.05, 0.9, 6.0), (ox + WX / 2, oy - WY / 2, 0.9, 6.0))):
        light("CastleLamp%d" % i, 'POINT', LC, (x, y, z), energy=e, color=(1.0, 0.6, 0.3), size=0.08)
    return (gx - bl - 0.05, oy)       # where the path should end
