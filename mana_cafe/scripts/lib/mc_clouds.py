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
    ('CL_valley', (-3700.0, -4700.0, -430.0), (2400.0, 700.0, 170.0), 100.0, dict(density=0.012, thresh=0.38, stretch=(0.5, 1.2, 2.2))),
]


def build(which=None):
    sc = bpy.context.scene
    for o in [o for o in bpy.data.objects if o.name.startswith('CL_')]:
        C.remove_object(o.name)
    for name, loc, size, rz, kw in WISPS:
        if which and name not in which:
            continue
        box(name, loc, size, rz, **kw)
    sc.cycles.volume_bounces = 6
    sc.cycles.volume_step_rate = 1.0
    sc.cycles.volume_max_steps = 256
    return len(WISPS)
