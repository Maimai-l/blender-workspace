"""World, sun and render settings."""
import bpy, os, math
import mc_core as C
from mc_core import NT

SUN_AZ = -26.0      # math azimuth of the sun in the scene (deg): ESE (compass 116), mid October about 8:30 solar time
SUN_EL = 28.6


def world(hdr='waterkloof_farm_16k.hdr', strength=0.78, sun_clamp=40.0, sky_az=None, gamma=1.16, sat=1.12,
          tint=(0.90, 0.96, 1.0), sun_az=SUN_AZ):
    """Photographed sky (Poly Haven 'waterkloof_farm', CC0). Its sun (pixel azimuth 216.08 deg, 37.7 deg high) is
    turned to sun_az and clamped out; MC_sun replaces it, so sun and sky can be balanced for 4400 m: a stronger
    sun and a darker, deeper blue sky than at the lowland site of the photograph.
    sky_az: turn the sky separately from the sun (degrees added to the rotation), to place the cirrus."""
    w = bpy.context.scene.world or bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    w.use_nodes = True
    t = w.node_tree
    t.nodes.clear()
    n = NT(t)
    out = n.node('ShaderNodeOutputWorld')
    tc = n.node('ShaderNodeTexCoord')
    # Blender's equirect lookup: u = 0.5 - atan2(d.y, d.x) / 2pi. The sun is at u = 0.6002 in the picture, i.e. at
    # azimuth -36.08 deg of the lookup vector. Mapping (POINT) rotates the lookup vector by +rot:
    #   az + rot = -36.08   (checked with a shadow probe: tools/rr.py, t02_sun)
    mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': tc.outputs['Generated']})
    mp.inputs['Rotation'].default_value = (0.0, 0.0, math.radians(-36.08 - sun_az + (sky_az or 0.0)))
    img = bpy.data.images.load(os.path.join(C.ASSETS, 'hdri', hdr), check_existing=True)
    img.use_half_precision = True
    env = n.node('ShaderNodeTexEnvironment', inputs={'Vector': mp.outputs[0]})
    env.image = img
    col = env.outputs['Color']
    cl = n.node('ShaderNodeMix', data_type='RGBA', blend_type='DARKEN', inputs={0: 1.0})
    n.link(col, cl.inputs[6])
    cl.inputs[7].default_value = (sun_clamp, sun_clamp, sun_clamp, 1)
    col = cl.outputs[2]
    col = n.node('ShaderNodeGamma', inputs={'Color': col, 'Gamma': gamma}).outputs[0]
    col = n.node('ShaderNodeHueSaturation', inputs={'Saturation': sat, 'Color': col}).outputs[0]
    col = n.mix(1.0, col, tuple(tint) + (1,), 'MULTIPLY')
    bg = n.node('ShaderNodeBackground', inputs={'Color': col, 'Strength': strength})
    n.link(bg.outputs[0], out.inputs['Surface'])
    # the sun is a lamp: a small importance map is enough for the clamped sky (a 16k map costs 2.5 GB)
    w.cycles.sampling_method = 'MANUAL'
    w.cycles.sample_map_resolution = 2048
    return w


def sun(strength=10.5, az=SUN_AZ, el=SUN_EL, color=(1.0, 0.975, 0.91), angle=0.53):
    o = bpy.data.objects.get('MC_sun')
    if o is None:
        o = bpy.data.objects.new('MC_sun', bpy.data.lights.new('MC_sun', 'SUN'))
        C.coll('MC_light').objects.link(o)
    o.data.energy = strength
    o.data.color = color
    o.data.angle = math.radians(angle)
    a, e = math.radians(az), math.radians(el)
    from mathutils import Vector
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))   # towards the sun
    o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    return o


def render_settings(scale=50, samples=128, res=(3840, 2160), exposure=-1.3, look='AgX - Medium High Contrast'):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    cy = sc.cycles
    cy.device = 'GPU'
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = scale
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = look
    except TypeError:
        sc.view_settings.look = 'None'
    sc.view_settings.exposure = exposure
    sc.render.film_transparent = False
    return sc


CAMERA = dict(loc=(15.0, 41.0, 13.5), az=-126.5, pitch=-6.3, lens=25.0)


def camera(name='CAM_final', loc=None, az=None, pitch=None, lens=None, fstop=None, focus=None):
    """The picture's camera: the sketch's direction, pulled back along it so that the whole terrace, the track and
    the meadow in front are in the frame. az / pitch in degrees (math convention)."""
    from mathutils import Vector
    p = dict(CAMERA)
    for k, v in (('loc', loc), ('az', az), ('pitch', pitch), ('lens', lens)):
        if v is not None:
            p[k] = v
    sc = bpy.context.scene
    o = bpy.data.objects.get(name)
    if o is None:
        o = bpy.data.objects.new(name, bpy.data.cameras.new(name))
        C.coll('MC_light').objects.link(o)
    o.location = p['loc']
    a, e = math.radians(p['az']), math.radians(p['pitch'])
    d = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    o.data.lens = p['lens']
    o.data.sensor_width = 36.0
    o.data.clip_start = 0.5
    o.data.clip_end = 200000.0
    if fstop:
        o.data.dof.use_dof = True
        o.data.dof.aperture_fstop = fstop
        o.data.dof.focus_distance = focus or 45.0
    sc.camera = o
    return o
