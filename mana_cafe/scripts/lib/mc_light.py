"""World, sun and render settings."""
import bpy, os, math
import mc_core as C
from mc_core import NT

SUN_AZ = -26.0      # math azimuth of the sun in the scene (deg): ESE (compass 116), mid October about 8:30 solar time
SUN_EL = 28.6


def world(hdr='waterkloof_farm_16k.hdr', strength=0.78, sun_clamp=40.0, sky_az=None, gamma=1.16, sat=1.12,
          tint=(0.90, 0.96, 1.0), sun_az=SUN_AZ, cam_gamma=0.72, cam_sat=0.74, cam_gain=1.85):
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
    # what the camera sees of the sky is graded apart from what lights the scene: the light stays that of thin
    # air at 4400 m (dark, saturated sky dome), the picture gets the lighter, softer blue of the photographs
    colc = n.node('ShaderNodeGamma', inputs={'Color': col, 'Gamma': cam_gamma}).outputs[0]
    colc = n.node('ShaderNodeHueSaturation', inputs={'Saturation': cam_sat, 'Value': cam_gain, 'Color': colc}).outputs[0]
    lp = n.node('ShaderNodeLightPath')
    col = n.mix(lp.outputs['Is Camera Ray'], col, colc)
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


def render_settings(scale=50, samples=128, res=(3840, 2160), exposure=0.35, look='AgX - High Contrast'):
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


def grade(sat=0.82, wb=(0.975, 1.0, 1.035), curve=((0.0, 0.0), (0.08, 0.045), (0.2, 0.14), (0.5, 0.5), (1.0, 1.0))):
    """Picture grade, kept inside the file: a compositor chain in scene-linear light (white balance a touch cool,
    restrained saturation) and a display curve after the view transform. Returns a description of what was set."""
    sc = bpy.context.scene
    done = []
    try:
        t = bpy.data.node_groups.get('MC_grade')
        if t is not None:
            bpy.data.node_groups.remove(t)
        t = bpy.data.node_groups.new('MC_grade', 'CompositorNodeTree')
        t.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        N, L = t.nodes, t.links
        rl = N.new('CompositorNodeRLayers')
        rl.scene = sc
        go = N.new('NodeGroupOutput')
        hs = N.new('CompositorNodeHueSat')
        hs.inputs['Saturation'].default_value = sat
        L.new(rl.outputs['Image'], hs.inputs['Image'])
        mx = N.new('ShaderNodeMix')
        mx.data_type = 'RGBA'
        mx.blend_type = 'MULTIPLY'
        mx.inputs[0].default_value = 1.0
        L.new(hs.outputs['Image'], mx.inputs[6])
        mx.inputs[7].default_value = tuple(wb) + (1.0,)
        L.new(mx.outputs[2], go.inputs[0])
        sc.compositing_node_group = t
        sc.render.use_compositing = True
        done.append('compositor sat %.2f wb %s' % (sat, wb))
    except Exception as e:                       # the picture still renders; the grade then lives in the display curve only
        sc.render.use_compositing = False
        done.append('compositor not set: %s' % e)
    vs = sc.view_settings
    vs.use_curve_mapping = True
    cm = vs.curve_mapping
    cv = cm.curves[3]                            # combined curve
    while len(cv.points) > 2:
        cv.points.remove(cv.points[1])
    cv.points[0].location = curve[0]
    cv.points[1].location = curve[-1]
    for p in curve[1:-1]:
        cv.points.new(p[0], p[1])
    cm.update()
    done.append('display curve %s' % (curve,))
    return done
