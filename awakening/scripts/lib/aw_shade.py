"""Cel shading, ink lines (Freestyle), light, world and render settings for the Awakening scene."""
import bpy, math
from mathutils import Vector
import aw_core as C

# ---------------------------------------------------------------- cel shader node group
def cel_group():
    """Node group: Base Color, Shadow Mul, Deep Mul, Threshold, Deep Threshold, Spec, Spec Color, Emit, Alpha -> Shader.
    Light bands come from Shader to RGB on a white diffuse, so cast shadows are included.
    shadow = base * Shadow Mul (darker, cooler), deep = base * Deep Mul."""
    name = 'AW_Cel'
    g = bpy.data.node_groups.get(name)
    if g:
        return g
    g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    it = g.interface
    for nm, ty, dflt in (('Base Color', 'NodeSocketColor', (0.5, 0.5, 0.5, 1)),
                         ('Shadow Mul', 'NodeSocketColor', (0.56, 0.62, 0.80, 1)),
                         ('Deep Mul', 'NodeSocketColor', (0.40, 0.44, 0.62, 1)),
                         ('Threshold', 'NodeSocketFloat', 0.42),
                         ('Deep Threshold', 'NodeSocketFloat', 0.08),
                         ('Spec', 'NodeSocketFloat', 0.0),
                         ('Spec Color', 'NodeSocketColor', (1.0, 0.97, 0.9, 1)),
                         ('Emit', 'NodeSocketColor', (0, 0, 0, 1)),
                         ('Alpha', 'NodeSocketFloat', 1.0),
                         ('Rim', 'NodeSocketFloat', 0.0),
                         ('Rim Color', 'NodeSocketColor', (1.0, 0.93, 0.78, 1))):
        s = it.new_socket(nm, in_out='INPUT', socket_type=ty)
        try:
            s.default_value = dflt
        except Exception:
            pass
    it.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    n = g.nodes
    gi = n.new('NodeGroupInput'); gi.location = (-900, 0)
    go = n.new('NodeGroupOutput'); go.location = (1150, 100)
    diff = n.new('ShaderNodeBsdfDiffuse'); diff.location = (-600, 300)
    diff.inputs['Color'].default_value = (1, 1, 1, 1)
    s2r = n.new('ShaderNodeShaderToRGB'); s2r.location = (-400, 300)
    g.links.new(diff.outputs[0], s2r.inputs[0])
    bw = n.new('ShaderNodeRGBToBW'); bw.location = (-200, 300)
    g.links.new(s2r.outputs['Color'], bw.inputs[0])
    gt = n.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.location = (0, 400)
    g.links.new(bw.outputs[0], gt.inputs[0]); g.links.new(gi.outputs['Threshold'], gt.inputs[1])
    lt = n.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.location = (0, 200)
    g.links.new(bw.outputs[0], lt.inputs[0]); g.links.new(gi.outputs['Deep Threshold'], lt.inputs[1])
    shd = n.new('ShaderNodeMix'); shd.data_type = 'RGBA'; shd.blend_type = 'MULTIPLY'; shd.location = (0, 0)
    shd.inputs['Factor'].default_value = 1.0
    g.links.new(gi.outputs['Base Color'], shd.inputs[6]); g.links.new(gi.outputs['Shadow Mul'], shd.inputs[7])
    dp = n.new('ShaderNodeMix'); dp.data_type = 'RGBA'; dp.blend_type = 'MULTIPLY'; dp.location = (0, -200)
    dp.inputs['Factor'].default_value = 1.0
    g.links.new(gi.outputs['Base Color'], dp.inputs[6]); g.links.new(gi.outputs['Deep Mul'], dp.inputs[7])
    mix1 = n.new('ShaderNodeMix'); mix1.data_type = 'RGBA'; mix1.location = (250, 300)
    g.links.new(lt.outputs[0], mix1.inputs['Factor'])
    g.links.new(shd.outputs[2], mix1.inputs[6]); g.links.new(dp.outputs[2], mix1.inputs[7])
    mix2 = n.new('ShaderNodeMix'); mix2.data_type = 'RGBA'; mix2.location = (450, 300)
    g.links.new(gt.outputs[0], mix2.inputs['Factor'])
    g.links.new(mix1.outputs[2], mix2.inputs[6]); g.links.new(gi.outputs['Base Color'], mix2.inputs[7])
    gl = n.new('ShaderNodeBsdfGlossy'); gl.location = (-600, -400); gl.inputs['Roughness'].default_value = 0.25
    s2 = n.new('ShaderNodeShaderToRGB'); s2.location = (-400, -400)
    g.links.new(gl.outputs[0], s2.inputs[0])
    bw2 = n.new('ShaderNodeRGBToBW'); bw2.location = (-200, -400)
    g.links.new(s2.outputs['Color'], bw2.inputs[0])
    sgt = n.new('ShaderNodeMath'); sgt.operation = 'GREATER_THAN'; sgt.location = (0, -400)
    sgt.inputs[1].default_value = 1.2
    g.links.new(bw2.outputs[0], sgt.inputs[0])
    smul = n.new('ShaderNodeMath'); smul.operation = 'MULTIPLY'; smul.location = (200, -400)
    g.links.new(sgt.outputs[0], smul.inputs[0]); g.links.new(gi.outputs['Spec'], smul.inputs[1])
    smul2 = n.new('ShaderNodeMath'); smul2.operation = 'MULTIPLY'; smul2.location = (350, -400)
    g.links.new(smul.outputs[0], smul2.inputs[0]); g.links.new(gt.outputs[0], smul2.inputs[1])
    mix3 = n.new('ShaderNodeMix'); mix3.data_type = 'RGBA'; mix3.location = (600, 200)
    g.links.new(smul2.outputs[0], mix3.inputs['Factor'])
    g.links.new(mix2.outputs[2], mix3.inputs[6]); g.links.new(gi.outputs['Spec Color'], mix3.inputs[7])
    # backlight rim: grazing surfaces that still receive some direct sun get a thin warm band
    lw = n.new('ShaderNodeLayerWeight'); lw.location = (-200, -700); lw.inputs['Blend'].default_value = 0.5
    rth = n.new('ShaderNodeMath'); rth.operation = 'SUBTRACT'; rth.location = (0, -650)
    rth.inputs[0].default_value = 1.0; g.links.new(gi.outputs['Rim'], rth.inputs[1])
    rgt = n.new('ShaderNodeMath'); rgt.operation = 'GREATER_THAN'; rgt.location = (200, -650)
    g.links.new(lw.outputs['Facing'], rgt.inputs[0]); g.links.new(rth.outputs[0], rgt.inputs[1])
    lit2 = n.new('ShaderNodeMath'); lit2.operation = 'GREATER_THAN'; lit2.location = (200, -800); lit2.inputs[1].default_value = 0.9
    g.links.new(bw.outputs[0], lit2.inputs[0])
    rim = n.new('ShaderNodeMath'); rim.operation = 'MULTIPLY'; rim.location = (400, -700)
    g.links.new(rgt.outputs[0], rim.inputs[0]); g.links.new(lit2.outputs[0], rim.inputs[1])
    # no rim where Rim is 0
    rim_on = n.new('ShaderNodeMath'); rim_on.operation = 'GREATER_THAN'; rim_on.location = (400, -850); rim_on.inputs[1].default_value = 0.001
    g.links.new(gi.outputs['Rim'], rim_on.inputs[0])
    rim2 = n.new('ShaderNodeMath'); rim2.operation = 'MULTIPLY'; rim2.location = (550, -750)
    g.links.new(rim.outputs[0], rim2.inputs[0]); g.links.new(rim_on.outputs[0], rim2.inputs[1])
    mix4 = n.new('ShaderNodeMix'); mix4.data_type = 'RGBA'; mix4.location = (650, 100)
    g.links.new(rim2.outputs[0], mix4.inputs['Factor'])
    g.links.new(mix3.outputs[2], mix4.inputs[6]); g.links.new(gi.outputs['Rim Color'], mix4.inputs[7])
    add = n.new('ShaderNodeMix'); add.data_type = 'RGBA'; add.blend_type = 'ADD'; add.location = (750, 50)
    add.inputs['Factor'].default_value = 1.0
    g.links.new(mix4.outputs[2], add.inputs[6]); g.links.new(gi.outputs['Emit'], add.inputs[7])
    em = n.new('ShaderNodeEmission'); em.location = (900, 200)
    g.links.new(add.outputs[2], em.inputs['Color'])
    tr = n.new('ShaderNodeBsdfTransparent'); tr.location = (900, -100)
    mixs = n.new('ShaderNodeMixShader'); mixs.location = (1000, 100)
    g.links.new(gi.outputs['Alpha'], mixs.inputs['Fac'])
    g.links.new(tr.outputs[0], mixs.inputs[1]); g.links.new(em.outputs[0], mixs.inputs[2])
    g.links.new(mixs.outputs[0], go.inputs['Shader'])
    return g

def shadow_of(base, k=0.62, cool=(0.82, 0.9, 1.15)):
    """Anime shadow colour: darker and shifted cool."""
    r, g, b = base[:3]
    out = [min(1, r * k * cool[0]), min(1, g * k * cool[1]), min(1, b * k * cool[2])]
    return (out[0], out[1], out[2], 1)

def cel_material(name, base, shadow=None, deep=None, spec=0.0, threshold=0.42, line=(0.07, 0.045, 0.04, 1), rim=0.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    grp = nt.nodes.new('ShaderNodeGroup'); grp.node_tree = cel_group(); grp.location = (0, 0)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (300, 0)
    nt.links.new(grp.outputs[0], out.inputs[0])
    base = tuple(base[:3]) + (1,)
    grp.inputs['Base Color'].default_value = base
    if shadow:
        grp.inputs['Shadow Mul'].default_value = shadow
    if deep:
        grp.inputs['Deep Mul'].default_value = deep
    grp.inputs['Spec'].default_value = spec
    grp.inputs['Threshold'].default_value = threshold
    grp.inputs['Rim'].default_value = rim
    mat.line_color = line
    mat.diffuse_color = base
    try:
        mat.surface_render_method = 'DITHERED'
    except Exception:
        pass
    return mat

def group_node(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'GROUP')

# ---------------------------------------------------------------- flat / painted card materials
def card_material(name, image, emit=1.0, tint=(1, 1, 1, 1), shadow_catch=False):
    """Unlit painted card: image colour straight to emission, alpha from image (dithered)."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = image; tex.location = (-600, 0)
    tex.interpolation = 'Cubic'
    tex.extension = 'CLIP'      # no wrap-around of the opaque top row along the card edges
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.location = (-300, 0)
    mul.inputs['Factor'].default_value = 1.0
    mul.inputs[7].default_value = tint
    nt.links.new(tex.outputs['Color'], mul.inputs[6])
    em = nt.nodes.new('ShaderNodeEmission'); em.location = (-100, 0); em.inputs['Strength'].default_value = emit
    nt.links.new(mul.outputs[2], em.inputs['Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); tr.location = (-100, -200)
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.location = (150, 0)
    nt.links.new(tex.outputs['Alpha'], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (400, 0)
    nt.links.new(mix.outputs[0], out.inputs[0])
    try:
        mat.surface_render_method = 'DITHERED'
    except Exception:
        pass
    mat.use_backface_culling = False
    return mat

# ---------------------------------------------------------------- Freestyle ink
def setup_layers(scene, ink_exclude=('Cards', 'Volumes', 'FX', 'DustSrc', 'FieldsNone', 'FieldsWind', 'FieldsSky', 'Cameras')):
    """Two view layers: 'Beauty' renders everything without ink and carries the cryptomatte; 'Ink' renders only the
    solid actors (no transparent cards, which Freestyle would treat as opaque occluders) and outputs the Freestyle pass."""
    vb = scene.view_layers[0]
    vb.name = 'Beauty'
    vi = scene.view_layers.get('Ink') or scene.view_layers.new('Ink')
    def set_excl(vl, names, exclude):
        def rec(lc):
            if lc.collection.name in names:
                lc.exclude = exclude
            for c in lc.children:
                rec(c)
        rec(vl.layer_collection)
    set_excl(vi, set(ink_exclude), True)
    set_excl(vb, set(ink_exclude), False)
    vb.use_freestyle = False
    vb.use_pass_mist = True
    vb.use_pass_z = True
    vb.use_pass_cryptomatte_asset = True
    vb.pass_cryptomatte_depth = 2
    vi.use_freestyle = True
    vi.use_pass_z = False
    vi.use_pass_mist = False
    vi.freestyle_settings.as_render_pass = True
    return vb, vi

def setup_freestyle(scene, linesets=(('Robot', 1.25),), vl=None):
    """One Freestyle lineset per (collection, thickness); thickness is relative (1 = one pixel at 480 px height)."""
    scene.render.use_freestyle = True
    scene.render.line_thickness_mode = 'RELATIVE'
    vl = vl or scene.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.mode = 'EDITOR'
    fs.use_culling = True
    fs.crease_angle = math.radians(128)
    fs.use_smoothness = True
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    out = []
    for coll_name, thickness in linesets:
        if bpy.data.collections.get(coll_name) is None:
            continue
        ls = fs.linesets.new('ink_' + coll_name)
        ls.select_by_visibility = True
        ls.visibility = 'VISIBLE'
        ls.select_by_edge_types = True
        ls.select_silhouette = True
        ls.select_border = True
        ls.select_crease = True
        ls.select_edge_mark = True
        ls.select_material_boundary = True
        ls.select_contour = False
        ls.select_external_contour = False
        ls.select_by_collection = True
        ls.collection = bpy.data.collections[coll_name]
        ls.collection_negation = 'INCLUSIVE'
        style_ink(ls.linestyle, thickness, 'AW_Ink_' + coll_name)
        out.append(ls)
    return out

def style_ink(st, thickness, name):
    st.name = name
    st.color = (0.09, 0.055, 0.05)
    st.alpha = 1.0
    st.thickness = thickness
    st.thickness_position = 'CENTER'
    st.caps = 'ROUND'
    st.use_chaining = True
    st.chaining = 'PLAIN'
    st.use_same_object = True
    st.use_split_length = False
    st.use_length_min = True
    st.length_min = 6
    for coll in (st.thickness_modifiers, st.geometry_modifiers, st.alpha_modifiers, st.color_modifiers):
        for m in list(coll):
            coll.remove(m)
    al = st.thickness_modifiers.new('taper', 'ALONG_STROKE')
    al.blend = 'MULTIPLY'; al.influence = 1.0
    al.mapping = 'CURVE'
    pts = al.curve.curves[0].points
    pts[0].location = (0.0, 0.35)
    pts[1].location = (1.0, 0.35)
    pts.new(0.25, 0.95); pts.new(0.6, 1.0)
    al.curve.update()
    cal = st.thickness_modifiers.new('brush', 'CALLIGRAPHY')
    cal.orientation = math.radians(50); cal.thickness_min = 0.55; cal.thickness_max = 1.35
    cal.blend = 'MULTIPLY'
    nz = st.thickness_modifiers.new('hand', 'NOISE')
    nz.amplitude = 0.55; nz.period = 18; nz.seed = 7; nz.blend = 'ADD'; nz.use_asymmetric = True
    dc = st.thickness_modifiers.new('dist', 'DISTANCE_FROM_CAMERA')
    dc.range_min = 8; dc.range_max = 120; dc.value_min = 1.0; dc.value_max = 0.6; dc.blend = 'MULTIPLY'
    st.geometry_modifiers.new('sample', 'SAMPLING').sampling = 3.0
    bz = st.geometry_modifiers.new('bezier', 'BEZIER_CURVE'); bz.error = 2.5
    pn = st.geometry_modifiers.new('wobble', 'PERLIN_NOISE_1D')
    pn.frequency = 9; pn.amplitude = 0.7; pn.octaves = 2; pn.seed = 3; pn.angle = math.radians(35)
    cm = st.color_modifiers.new('mat', 'MATERIAL'); cm.blend = 'MIX'; cm.influence = 0.85
    cm.use_ramp = False
    return st

# ---------------------------------------------------------------- light and world
def setup_world(scene, color=(0.52, 0.56, 0.68), strength=0.22):
    w = scene.world or bpy.data.worlds.new('World')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (*color, 1)
    bg.inputs['Strength'].default_value = strength
    out = nt.nodes.new('ShaderNodeOutputWorld')
    nt.links.new(bg.outputs[0], out.inputs['Surface'])
    # the camera never sees the world: a painted sky card covers it; keep the film transparent off
    scene.render.film_transparent = False
    return w

def setup_sun(scene, name='Sun', azim=55, elev=14, strength=1.0, color=(1.0, 0.93, 0.80)):
    ob = bpy.data.objects.get(name)
    if ob is None:
        la = bpy.data.lights.new(name, 'SUN')
        ob = bpy.data.objects.new(name, la)
        scene.collection.objects.link(ob)
    la = ob.data
    la.energy = strength
    la.color = color
    la.angle = math.radians(0.6)
    la.use_shadow = True
    try:
        la.shadow_filter_radius = 0.6
        la.shadow_maximum_resolution = 0.0015
        la.use_shadow_jitter = False
    except Exception:
        pass
    # azimuth measured from +Y toward +X, elevation above horizon; the light points toward -Z of the object
    ob.rotation_euler = (math.radians(90 - elev), 0, math.radians(-azim))
    return ob

def sun_dir(ob):
    return (ob.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()

# ---------------------------------------------------------------- render
def setup_render(scene, w=1920, h=1080, samples=24):
    r = scene.render
    try:
        r.engine = 'BLENDER_EEVEE'
    except TypeError as e:
        print(e)
    r.resolution_x = w; r.resolution_y = h; r.resolution_percentage = 100
    r.fps = C.FPS
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.color_depth = '8'
    r.film_transparent = False
    r.use_motion_blur = False
    ee = scene.eevee
    ee.taa_render_samples = samples
    ee.taa_samples = 8
    ee.use_shadows = True
    try:
        ee.shadow_ray_count = 2
        ee.shadow_step_count = 4
        ee.shadow_resolution_scale = 1.0
    except Exception:
        pass
    ee.use_raytracing = False
    ee.volumetric_tile_size = '4'
    ee.volumetric_samples = 128
    ee.use_volume_custom_range = True
    ee.volumetric_start = 0.5
    ee.volumetric_end = 420.0
    ee.volumetric_sample_distribution = 0.85
    ee.volumetric_shadow_samples = 16
    ee.use_volumetric_shadows = True
    vs = scene.view_settings
    try:
        vs.view_transform = 'Standard'
    except TypeError:
        pass
    vs.look = 'None'
    vs.exposure = 0.0
    vs.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
    return r
