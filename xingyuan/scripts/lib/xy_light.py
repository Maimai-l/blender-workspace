# Xingyuan build library - sky, sun, render settings, cameras, render-to-file helper.
import bpy, math, os
from mathutils import Vector, Euler
import xy_core as C

def setup_world(sun_elev=42.0, sun_azim=215.0, strength=0.15, sun_strength=5.0, sun_angle=1.6, desat=0.55, dust=0.4,
                cam_sat=1.6, cam_val=0.88):
    """Physical sky for ambient light + Sun lamp for direct light.
    sun_azim: compass bearing the sun comes FROM (0 = north, 90 = east, 180 = south)."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new('XY_World')
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld'); out.location = (600, 0)
    bg = nt.nodes.new('ShaderNodeBackground'); bg.location = (350, 0)
    sky = nt.nodes.new('ShaderNodeTexSky'); sky.location = (0, 0)
    types = [i.identifier for i in bpy.types.ShaderNodeTexSky.bl_rna.properties['sky_type'].enum_items]
    for t in ('MULTIPLE_SCATTERING', 'SINGLE_SCATTERING', 'NISHITA', 'HOSEK_WILKIE'):
        if t in types:
            sky.sky_type = t
            break
    # direction: bearing -> Blender azimuth. Scene: +Y = north, +X = east.
    # sky.sun_rotation is measured from +X? We compute the lamp direction explicitly and match the sky.
    el = math.radians(sun_elev)
    az = math.radians(sun_azim)
    to_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    for attr, val in (('sun_elevation', el), ('sun_rotation', math.atan2(to_sun.y, to_sun.x) - math.pi / 2),
                      ('sun_disc', False), ('altitude', 50.0), ('air_density', 1.0), ('dust_density', dust),
                      ('ozone_density', 1.0), ('sun_intensity', 1.0)):
        if hasattr(sky, attr):
            try:
                setattr(sky, attr, val)
            except Exception as e:
                print('sky attr', attr, e)
    # the sky alone is very bright in physical units; scale it down and let the lamp do direct light.
    # Lighting uses a partly desaturated sky (less blue cast in the shade); camera rays see the real sky.
    bg.inputs['Strength'].default_value = strength
    hsv = nt.nodes.new('ShaderNodeHueSaturation'); hsv.location = (150, -200)
    hsv.inputs['Saturation'].default_value = desat
    nt.links.new(sky.outputs[0], hsv.inputs['Color'])
    lp = nt.nodes.new('ShaderNodeLightPath'); lp.location = (150, 250)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.location = (300, 100)
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs[0])
    cam_hsv = nt.nodes.new('ShaderNodeHueSaturation'); cam_hsv.location = (150, 50)
    cam_hsv.inputs['Saturation'].default_value = cam_sat
    cam_hsv.inputs['Value'].default_value = cam_val
    nt.links.new(sky.outputs[0], cam_hsv.inputs['Color'])
    nt.links.new(hsv.outputs[0], mix.inputs[6])
    nt.links.new(cam_hsv.outputs[0], mix.inputs[7])
    nt.links.new(mix.outputs[2], bg.inputs['Color'])
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    # sun lamp
    sun = bpy.data.objects.get('XY_Sun')
    if sun is None:
        ld = bpy.data.lights.new('XY_Sun', 'SUN')
        sun = bpy.data.objects.new('XY_Sun', ld)
        C.link(sun, C.coll('灯光与相机'))
    ld = sun.data
    ld.energy = sun_strength
    ld.angle = math.radians(sun_angle)
    ld.color = (1.0, 0.955, 0.90)
    # orient the lamp: its -Z axis points along the light travel direction (-to_sun)
    d = -to_sun
    rot = d.to_track_quat('-Z', 'Y').to_euler()
    sun.rotation_euler = rot
    sun.location = (35, 25, 60)
    return sky, sun

def setup_render(samples=256, res=(1920, 1080), engine='CYCLES', exposure=0.0, look=None):
    sc = bpy.context.scene
    try:
        sc.render.engine = engine
    except TypeError as e:
        print('engine', e)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    if engine == 'CYCLES':
        cy = sc.cycles
        cy.device = 'GPU'
        cy.samples = samples
        cy.use_adaptive_sampling = True
        cy.adaptive_threshold = 0.02
        cy.use_denoising = True
        try:
            cy.denoiser = 'OPENIMAGEDENOISE'
        except Exception:
            pass
        cy.max_bounces = 8
        cy.diffuse_bounces = 4
        cy.glossy_bounces = 4
        cy.transmission_bounces = 6
        cy.sample_clamp_indirect = 6.0
        cy.sample_clamp_direct = 0.0
        cy.caustics_reflective = False
        cy.caustics_refractive = False
    vs = sc.view_settings
    try:
        vs.view_transform = 'AgX'
    except Exception:
        pass
    if look:
        try:
            vs.look = look
        except Exception as e:
            print('look', e)
    vs.exposure = exposure
    sc.render.image_settings.file_format = 'PNG'

def camera(name, loc, target=None, rot=None, lens=35.0, shift=(0.0, 0.0), sensor=36.0, roll=0.0):
    cam = bpy.data.objects.get(name)
    if cam is None:
        cd = bpy.data.cameras.new(name)
        cam = bpy.data.objects.new(name, cd)
        C.link(cam, C.coll('灯光与相机'))
    cam.location = loc
    if target is not None:
        from mathutils import Quaternion
        d = Vector(target) - Vector(loc)
        q = d.to_track_quat('-Z', 'Y') @ Quaternion((0.0, 0.0, 1.0), -roll)
        cam.rotation_euler = q.to_euler()
    elif rot is not None:
        cam.rotation_euler = Euler([math.radians(a) for a in rot])
    cam.data.lens = lens
    cam.data.sensor_width = sensor
    cam.data.sensor_fit = 'HORIZONTAL'
    cam.data.shift_x, cam.data.shift_y = shift
    cam.data.clip_start = 0.1
    cam.data.clip_end = 1000
    return cam

def render_to(path, cam=None, samples=None, res=None, pct=100):
    sc = bpy.context.scene
    if cam is not None:
        sc.camera = cam if not isinstance(cam, str) else bpy.data.objects[cam]
    if samples:
        sc.cycles.samples = samples
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = pct
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
