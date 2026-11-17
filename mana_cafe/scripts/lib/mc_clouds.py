"""Wisps of cloud on the mountainsides: a few procedural volumes (noise-shaped, soft-edged), lit by the sun and the
sky with multiple scattering."""
import bpy, math, zlib
import mc_core as C
from mc_core import NT


def cloud_material(name, density=0.02, scale=1.0, thresh=0.52, seed=0.0, stretch=(1.0, 1.0, 1.0)):
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    geo = n.node('ShaderNodeNewGeometry')
    # envelope: 1 in the middle of the box, 0 at its faces (generated coordinates run 0..1)
    # (object coordinates of the unit cube run -0.5..0.5; 'Generated' is not usable in a volume here)
    g = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: tc.outputs['Object'], 'Scale': 2.0}).outputs[0]
    gx = n.node('ShaderNodeSeparateXYZ', inputs={0: g}).outputs
    rad = n.node('ShaderNodeVectorMath', operation='LENGTH', inputs={0: g}).outputs['Value']
    env = n.smooth(rad, 1.0, 0.0)
    env = n.math('MULTIPLY', env, n.smooth(gx[2], -1.0, -0.5))          # flatter base, feathered top
    P = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': geo.outputs['Position'],
               'Location': (seed * 131.0, seed * 57.0, seed * 91.0), 'Scale': tuple(s / (520.0 * scale) for s in stretch)}).outputs[0]
    warp = n.noise(P, 0.6, 4, 0.55).outputs['Color']
    Pw = n.node('ShaderNodeVectorMath', operation='ADD', inputs={0: P, 1: n.node('ShaderNodeVectorMath', operation='SCALE',
                inputs={0: warp, 'Scale': 1.3}).outputs[0]}).outputs[0]
    big = n.noise(Pw, 1.0, 8, 0.66, lac=2.15).outputs['Fac']
    fine = n.noise(Pw, 6.0, 5, 0.62).outputs['Fac']
    d = n.math('ADD', n.math('MULTIPLY', big, 0.8), n.math('MULTIPLY', fine, 0.2))
    # soft body from the envelope, torn by the noise: shreds at the rim, denser in the core
    th = n.math('ADD', thresh, n.math('MULTIPLY', n.math('SUBTRACT', 1.0, env), 0.30))
    dens = n.math('MULTIPLY', n.math('MULTIPLY', n.smooth(d, th, n.math('ADD', th, 0.20)), n.math('POWER', env, 0.7)), density)
    vol = n.node('ShaderNodeVolumePrincipled', inputs={'Color': (0.93, 0.95, 1.0, 1), 'Density': dens, 'Anisotropy': 0.55})
    n.link(vol.outputs[0], out.inputs['Volume'])
    return m


def box(name, loc, size, rot_z=0.0, **kw):
    C.remove_object(name)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    o.rotation_euler = (0, 0, math.radians(rot_z))
    C.link(o, C.coll('MC_clouds'))
    o.data.materials.append(cloud_material('MC_cloud_' + name, seed=(zlib.crc32(name.encode()) % 1000) / 100.0, **kw))
    o.display_type = 'BOUNDS'
    o.visible_shadow = True
    return o


# (name, centre, size, rotation, kwargs) in scene coordinates; azimuth of the view is about -127 deg
WISPS = [
    ('CL_flank', (-7000.0, -5300.0, 430.0), (3800.0, 800.0, 240.0), 118.0, dict(density=0.016, thresh=0.36, stretch=(0.45, 1.3, 2.2))),
    ('CL_shoulder', (-8700.0, -6900.0, 880.0), (2000.0, 600.0, 220.0), 110.0, dict(density=0.014, thresh=0.37, stretch=(0.5, 1.3, 2.0))),
    ('CL_gap', (-7300.0, -8600.0, 330.0), (2600.0, 700.0, 220.0), 95.0, dict(density=0.014, thresh=0.37, stretch=(0.5, 1.2, 2.2))),
    ('CL_banner', (-10200.0, -4500.0, 1150.0), (2800.0, 800.0, 300.0), 123.0, dict(density=0.012, thresh=0.37, stretch=(0.45, 1.3, 2.0))),
]


SEA_TOP = -890.0          # mean top of the cloud in the valley (m, scene z; the cafe floor is at 0.6)


def sea_material(name='MC_cloud_sea', top=SEA_TOP, density=0.040):
    """Morning cloud lying low in the valley, seen from above: a bank a few kilometres long that leaves the upper
    valley open. The density comes from a 3D noise whose threshold falls with depth below the top, so the top has
    real relief (broad billows, 600-1500 m across) that the low sun lights from the side, and the bank frays into
    the air at its rim instead of ending in a line. Long swells (5 km) raise and lower the top, which is what breaks
    the layer into banks."""
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    geo = n.node('ShaderNodeNewGeometry')
    P = geo.outputs['Position']
    z = n.node('ShaderNodeSeparateXYZ', inputs={0: P}).outputs['Z']
    big = n.noise(P, 1 / 5200.0, 2, 0.45).outputs['Fac']
    topz = n.math('ADD', top, n.math('MULTIPLY', n.math('SUBTRACT', big, 0.5), 340.0))
    Ps = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': P, 'Scale': (1 / 1350.0, 1 / 1350.0, 1 / 600.0)}).outputs[0]
    warp = n.noise(Ps, 0.7, 2, 0.5).outputs['Color']
    Pw = n.node('ShaderNodeVectorMath', operation='ADD', inputs={0: Ps, 1: n.node('ShaderNodeVectorMath', operation='SCALE',
                inputs={0: warp, 'Scale': 0.55}).outputs[0]}).outputs[0]
    f1 = n.noise(Pw, 1.0, 4, 0.50, lac=2.0).outputs['Fac']                    # billows, down to about 200 m
    depth = n.math('DIVIDE', n.math('SUBTRACT', topz, z), 280.0)              # 0 at the top, 1 = 280 m below it
    depth = n.math('MINIMUM', n.math('MAXIMUM', depth, -1.2), 2.4)
    th = n.math('SUBTRACT', 0.53, n.math('MULTIPLY', depth, 0.21))          # 0.1 of noise = 130 m of relief
    # a firm body, so that the sun shades each billow (free path of 25 m against billows of a kilometre), inside a
    # thin halo that lets the bank fray into the air
    core = n.math('MULTIPLY', n.smooth(f1, th, n.math('ADD', th, 0.055)), density)
    halo = n.math('MULTIPLY', n.smooth(f1, n.math('SUBTRACT', th, 0.15), n.math('ADD', th, 0.03)), density * 0.045)
    dens = n.math('ADD', core, halo)
    # far cloud takes a little of the air's colour, like everything else at that distance
    dist = n.node('ShaderNodeVectorMath', operation='DISTANCE', inputs={0: P, 1: (9.6, 32.79, 11.76)}).outputs['Value']
    col = n.mix(n.math('MULTIPLY', n.smooth(dist, 2500.0, 11000.0), 0.55), (0.87, 0.895, 0.94, 1), (0.72, 0.80, 0.93, 1))
    vol = n.node('ShaderNodeVolumePrincipled', inputs={'Color': col, 'Density': dens, 'Anisotropy': 0.35})
    n.link(vol.outputs[0], out.inputs['Volume'])
    return m


def sea(name='CL_sea', top=SEA_TOP, x=(-12500.0, 1500.0), y=(-12500.0, 1500.0), thick=1300.0, **kw):
    C.remove_object(name)
    zc = top + 520.0 - thick / 2
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=((x[0] + x[1]) / 2, (y[0] + y[1]) / 2, zc))
    o = bpy.context.object
    o.name = name
    o.scale = (x[1] - x[0], y[1] - y[0], thick)
    C.link(o, C.coll('MC_clouds'))
    o.data.materials.append(sea_material(top=top, **kw))
    o.display_type = 'BOUNDS'
    return o


def build(which=None, sea_kw=None):
    sc = bpy.context.scene
    for o in [o for o in bpy.data.objects if o.name.startswith('CL_') and (not which or o.name in which)]:
        C.remove_object(o.name)
    for name, loc, size, rz, kw in WISPS:
        if which and name not in which:
            continue
        box(name, loc, size, rz, **kw)
    if not which or 'CL_sea' in which:
        sea(**(sea_kw or {}))
    sc.cycles.volume_bounces = 10
    sc.cycles.volume_step_rate = 1.0
    sc.cycles.volume_max_steps = 256
    return len(WISPS)
