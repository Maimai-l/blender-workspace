"""Hand-placed Megascans rock: the Massive Tundra Rock Formation as outcrops on the left ridge and at the platform
edges, Granite Cliff as crags on the nearest steep slopes, Snowy Ground as snow remnants in shaded hollows.
Positions are given as picture coordinates of the final camera (u to the right, v down, 0..1) and found on the
ground by marching the camera ray over the graded terrain."""
import bpy, math, zlib
import numpy as np
from mathutils import Vector, Euler, Matrix
import mc_core as C
import mc_ground


def picker():
    g = mc_ground.FarGround()
    cam = bpy.data.objects['CAM_final']
    sc = bpy.context.scene
    M = cam.matrix_world
    f = cam.data.lens / cam.data.sensor_width
    asp = sc.render.resolution_y / sc.render.resolution_x

    def pick(u, v, tmax=1800.0):
        d = M.to_3x3() @ Vector(((u - 0.5) / f, (0.5 - v) * asp / f, -1.0))
        d.normalize()
        o = M.translation
        t = 4.0
        while t < tmax:
            p = o + d * t
            if not (g.x0 + 2 < p.x < 316 and g.y0 + 2 < p.y < 316):
                return None
            z = float(g.s('z', p.x, p.y))
            if p.z <= z:
                return (p.x, p.y, z, t)
            t += max(0.25, t * 0.004)
        return None
    return pick, g


def place(name, src, loc, yaw=0.0, scale=1.0, sink=0.3, normal=None, follow=0.85):
    """Instance of a library mesh at loc, leaning with the ground (normal) and sunk into it by a fraction of its
    height, so that it reads as bedrock coming through the turf and not as a stone laid on top."""
    C.remove_object(name)
    o = bpy.data.objects.new(name, src.data)
    C.coll('MC_rocks').objects.link(o)
    zmin = min(v[2] for v in src.bound_box)
    zmax = max(v[2] for v in src.bound_box)
    s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
    o.scale = s
    q = Euler((0.0, 0.0, math.radians(yaw))).to_quaternion()
    up = Vector((0.0, 0.0, 1.0))
    if normal is not None:
        nv = up.lerp(Vector(normal).normalized(), follow).normalized()
        q = up.rotation_difference(nv) @ q
    else:
        nv = up
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = q
    o.location = Vector(loc) - nv * (zmin * s[2] + sink * (zmax - zmin) * s[2])
    return o


def ground_normal(g, x, y, e):
    gx = float(g.s('z', x + e, y) - g.s('z', x - e, y)) / (2 * e)
    gy = float(g.s('z', x, y + e) - g.s('z', x, y - e)) / (2 * e)
    return (-gx, -gy, 1.0)


# ---------------------------------------------------------------------------------------------------------------
# The rock of this ridge: one type (the Megascans tundra set: outcrop, two boulders, a stone, all given the same
# tone), bedded the same way everywhere. The beds strike 125 deg and dip 12 deg towards 35 deg (the same strike as
# the strata of the mountains, proc/far_build.py). Every rock is turned so that its own layering (read from the
# scans, see docs) lies along that strike, then tipped to the common dip.
STRIKE, DIP_AZ, DIP = 125.0, 35.0, 12.0
FOLIATION = {'rock_formation': 0.0, 'boulder_a': 20.0, 'boulder_b': -25.0, 'stone': 0.0}    # azimuth of the layering in each scan
BED_N = (math.sin(math.radians(DIP)) * math.cos(math.radians(DIP_AZ)), math.sin(math.radians(DIP)) * math.sin(math.radians(DIP_AZ)),
         math.cos(math.radians(DIP)))

# Foreground rocks, placed by hand one by one. A group is anchored at a picture position of the final camera
# (u right, v down); its members are offset in metres down the slope and along the contour from there.
#   member: (asset, down, along, scale, buried fraction, flipped end for end, yaw offset deg)
# Sites (convexity of the ground at 5 m scale, from tools: convex.py): crests where the soil is thin, and the foot
# of the slope below an outcrop. The hollows and the open meadow between the groups stay free of rock.
GROUPS = [
    # C  crest of the knoll behind the terrace (+120 cm convex): the bedrock comes through, blocks weather off it
    dict(name='crest', uv=(0.685, 0.690), rocks=[
        ('rock_formation', 0.0, 0.0, 0.34, 0.60, False, 0.0),
        ('boulder_a', 2.6, -3.2, 0.62, 0.45, False, 4.0),
        ('boulder_b', 4.4, 1.6, 0.40, 0.55, True, -5.0),
        ('stone', 3.4, -5.6, 0.70, 0.50, False, 6.0),
        ('stone', 5.6, -1.2, 0.42, 0.60, True, -3.0),
        ('stone', 6.3, 3.4, 0.30, 0.55, False, 8.0),
    ]),
    # D  where the knoll breaks off towards the valley (+80, 51 % slope): a ledge and what has slid from it
    dict(name='break', uv=(0.775, 0.752), rocks=[
        ('boulder_b', 0.0, 0.0, 0.95, 0.50, False, 0.0),
        ('boulder_a', 2.2, 2.4, 0.50, 0.55, True, 5.0),
        ('stone', 3.0, -1.6, 0.75, 0.45, False, -6.0),
        ('stone', 4.3, 0.9, 0.40, 0.60, True, 3.0),
    ]),
    # E  shoulder in the right foreground (+88, 53 %): outcrop on the convex edge
    dict(name='shoulder', uv=(0.925, 0.915), rocks=[
        ('rock_formation', 0.0, 0.0, 0.30, 0.62, True, 0.0),
        ('boulder_a', 3.0, -2.0, 0.78, 0.48, False, -4.0),
        ('boulder_b', 4.6, 2.2, 0.45, 0.58, False, 6.0),
        ('stone', 5.4, -3.6, 0.62, 0.50, True, 2.0),
        ('stone', 6.6, 0.4, 0.34, 0.62, False, -7.0),
    ]),
    # A  shoulder of the left ridge (+88, 52 %)
    dict(name='ridge_shoulder', uv=(0.275, 0.642), rocks=[
        ('rock_formation', 0.0, 0.0, 0.30, 0.62, False, 0.0),
        ('boulder_a', 2.8, 2.6, 0.70, 0.45, True, 5.0),
        ('stone', 4.0, -1.8, 0.80, 0.50, False, -4.0),
        ('stone', 5.2, 1.4, 0.38, 0.60, False, 7.0),
    ]),
    # B  top of the left ridge (+40..54)
    dict(name='ridge_top', uv=(0.095, 0.588), rocks=[
        ('rock_formation', 0.0, 0.0, 0.36, 0.60, True, 0.0),
        ('boulder_b', 2.4, -3.0, 0.80, 0.50, False, -5.0),
        ('boulder_a', 3.6, 2.8, 0.42, 0.55, False, 4.0),
        ('stone', 5.0, -0.6, 0.66, 0.48, True, 6.0),
    ]),
    # G  foot of the left ridge's slope (-44..-65: concave), below B: blocks that have come down and stopped here
    dict(name='slope_foot', uv=(0.080, 0.652), rocks=[
        ('boulder_a', 0.0, 0.0, 0.85, 0.42, False, 0.0),
        ('boulder_b', 1.6, 2.6, 0.52, 0.50, True, 9.0),
        ('stone', -1.4, -2.4, 0.85, 0.45, False, -8.0),
        ('stone', 2.4, -1.0, 0.44, 0.55, False, 5.0),
        ('stone', 3.2, 1.8, 0.30, 0.60, True, -4.0),
    ]),
    # F  a low rise in the near foreground (+32..36): one stone showing its back, two small ones beside it
    dict(name='foreground', uv=(0.640, 0.962), rocks=[
        ('boulder_b', 0.0, 0.0, 0.48, 0.62, False, 0.0),
        ('stone', 1.5, 1.1, 0.50, 0.55, True, 5.0),
        ('stone', 0.9, -1.4, 0.30, 0.60, False, -6.0),
    ]),
]


def bedded_yaw(kind, flip=False, offset=0.0):
    return STRIKE - FOLIATION[kind] + (180.0 if flip else 0.0) + offset


def build():
    import mc_fab
    pick, g = picker()
    col = C.coll('MC_rocks')
    for o in list(col.objects):
        C.remove_object(o.name)
    for key in ('rock_formation', 'boulder_a', 'boulder_b', 'stone'):
        mc_fab.rock_material(key, sat=0.55, val=0.50)                # one rock: the same tone on every scan
    mc_fab.rock_material('granite_cliff', sat=0.5, val=0.6)
    out = []
    for grp in GROUPS:
        hit = pick(*grp['uv'])
        if hit is None:
            out.append((grp['name'], 'no ground'))
            continue
        nrm = ground_normal(g, hit[0], hit[1], 3.0)
        L = math.hypot(nrm[0], nrm[1])
        dn = (nrm[0] / L, nrm[1] / L) if L > 1e-4 else (1.0, 0.0)    # down the slope
        al = (-dn[1], dn[0])                                         # along the contour
        for i, (kind, down, along, scale, bury, flip, yoff) in enumerate(grp['rocks']):
            x = hit[0] + dn[0] * down + al[0] * along
            y = hit[1] + dn[1] * down + al[1] * along
            if float(g.s('sdf', x, y)) < 1.2 or float(g.s('track', x, y)) > 0.05:
                out.append((grp['name'], i, 'skipped: on the terrace or the track'))
                continue
            z = float(g.s('z', x, y))
            src = mc_fab.objects(kind)[0]
            if kind == 'rock_formation':
                # the outcrop scan is a piece cut out of rocky ground: it lies in the slope with its cut rim under the
                # turf, so only its ledges and rubble show
                place('ROCK_%s_%d' % (grp['name'], i), src, (x, y, z), bedded_yaw(kind, flip, yoff), scale, max(bury, 0.74),
                      normal=ground_normal(g, x, y, 4.0), follow=0.9)
            else:
                place('ROCK_%s_%d' % (grp['name'], i), src, (x, y, z), bedded_yaw(kind, flip, yoff), scale, bury, normal=BED_N, follow=1.0)
        out.append((grp['name'], len(grp['rocks']), 'rocks at', [round(c, 1) for c in hit], 'slope %.0f %%' % (100 * L / max(nrm[2], 1e-6))))
    # --- what the camera sees of the nearest ground: one pick per 2 % of the picture
    sa, se = math.radians(-26.0), math.radians(28.6)
    sun = (math.cos(se) * math.cos(sa), math.cos(se) * math.sin(sa), math.sin(se))
    seen = []
    for v in np.arange(0.40, 0.995, 0.02):
        for u in np.arange(0.01, 1.0, 0.02):
            hit = pick(float(u), float(v))
            if hit is None:
                continue
            e = 3.0
            gx = float(g.s('z', hit[0] + e, hit[1]) - g.s('z', hit[0] - e, hit[1])) / (2 * e)
            gy = float(g.s('z', hit[0], hit[1] + e) - g.s('z', hit[0], hit[1] - e)) / (2 * e)
            nl = math.sqrt(gx * gx + gy * gy + 1.0)
            lit = (-gx * sun[0] - gy * sun[1] + sun[2]) / nl
            seen.append(dict(u=float(u), v=float(v), hit=hit, slope=math.hypot(gx, gy), gx=gx, gy=gy, lit=lit,
                             curv=float(g.s('curv', hit[0], hit[1])), sdf=float(g.s('sdf', hit[0], hit[1])),
                             track=float(g.s('track', hit[0], hit[1]))))
    out.append(('seen', len(seen), 'max slope', round(max(c['slope'] for c in seen), 2),
                'range m', round(min(c['hit'][3] for c in seen)), round(max(c['hit'][3] for c in seen))))
    rng = np.random.default_rng(5)

    def spread(cands, n, dmin):
        chosen = []
        for c in cands:
            if all(math.hypot(c['hit'][0] - k['hit'][0], c['hit'][1] - k['hit'][1]) > dmin for k in chosen):
                chosen.append(c)
            if len(chosen) >= n:
                break
        return chosen
    # --- crags: Granite Cliff where the ground is steepest within 1.5 km (ray casts on the terrain mesh itself:
    # beyond the knoll the first ground the camera sees is the far flank of the valley)
    ter = bpy.data.objects['TER_near']
    ter.hide_viewport = False                 # ray_cast needs the evaluated mesh; hidden again below
    bpy.context.view_layer.update()
    ter_e = ter.evaluated_get(bpy.context.evaluated_depsgraph_get())
    cam = bpy.data.objects['CAM_final']
    M = cam.matrix_world
    f = cam.data.lens / cam.data.sensor_width
    asp = bpy.context.scene.render.resolution_y / bpy.context.scene.render.resolution_x
    far_seen = []
    for v in np.arange(0.30, 0.80, 0.02):
        for u in np.arange(0.01, 1.0, 0.02):
            d = M.to_3x3() @ Vector(((float(u) - 0.5) / f, (0.5 - float(v)) * asp / f, -1.0))
            d.normalize()
            ok, loc, nrm, idx = ter_e.ray_cast(M.translation, d, distance=1600.0)
            if not ok:
                continue
            t = (loc - M.translation).length
            sl = math.sqrt(max(1e-9, 1.0 - nrm.z * nrm.z)) / max(nrm.z, 1e-3)
            far_seen.append(dict(u=float(u), v=float(v), hit=(loc.x, loc.y, loc.z, t), slope=sl, n=tuple(nrm)))
    ter.hide_viewport = True
    out.append(('far seen', len(far_seen), 'beyond 120 m', sum(1 for c in far_seen if c['hit'][3] > 120),
                'max slope', round(max([c['slope'] for c in far_seen if c['hit'][3] > 120] or [0]), 2)))
    cl = sorted([c for c in far_seen if 120.0 < c['hit'][3] < 1500.0 and c['slope'] > 0.7], key=lambda c: -c['slope'])
    cliff = mc_fab.objects('granite_cliff')[0]
    for i, c in enumerate(spread(cl, 4, 110.0)):
        down = math.degrees(math.atan2(c['n'][1], c['n'][0]))
        k = float(rng.uniform(0.9, 1.4))
        place('CLIFF_%d' % i, cliff, c['hit'][:3], STRIKE + float(rng.uniform(-8, 8)), k, 0.55,
              normal=c['n'], follow=0.6)                                    # bedded into the slope: an outcrop, not a tower
        out.append(('CLIFF_%d' % i, round(c['slope'], 2), c['u'], c['v'], [round(x) for x in c['hit']]))
    # --- snow remnants of the last fall, in the lee of the outcrops (small, deep in the turf)
    snow = mc_fab.objects('snowy_ground')[0]
    for i, (u, v, yaw, sc_, sink) in enumerate(SNOW):
        hit = pick(u, v)
        if hit is None:
            continue
        place('SNOW_%d' % i, snow, hit[:3], yaw, sc_, sink, normal=ground_normal(g, hit[0], hit[1], 3.0), follow=1.0)
        out.append(('SNOW_%d' % i, [round(x, 1) for x in hit]))
    return out
