# Xingyuan build library - procedural, physically based materials.
# Colours are linear-space values chosen to read as natural daylight material colours
# (the reference photos are colour-graded; these are corrected to plausible real values).
import bpy

def _new(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (900, 0)
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); bs.location = (600, 0)
    nt.links.new(bs.outputs[0], out.inputs['Surface'])
    return m, nt, bs, out

def _n(nt, t, loc=(0, 0), **props):
    n = nt.nodes.new(t)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n

def _mix(nt, fac, a, b, loc=(0, 0), blend='MIX'):
    """Colour mix; fac/a/b may be sockets or values. returns output socket."""
    mx = nt.nodes.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = blend; mx.location = loc
    L = nt.links
    for idx, v in ((0, fac), (6, a), (7, b)):
        if hasattr(v, 'is_linked') or hasattr(v, 'node'):
            L.new(v, mx.inputs[idx])
        else:
            mx.inputs[idx].default_value = v if idx == 0 else (tuple(v) + (1.0,))[:4]
    return mx.outputs[2]

def _ramp(nt, src, stops, loc=(0, 0)):
    r = nt.nodes.new('ShaderNodeValToRGB'); r.location = loc
    cr = r.color_ramp
    while len(cr.elements) > 1:
        cr.elements.remove(cr.elements[-1])
    cr.elements[0].position = stops[0][0]; cr.elements[0].color = tuple(stops[0][1]) + (1,)
    for p, c in stops[1:]:
        e = cr.elements.new(p); e.color = tuple(c) + (1,)
    nt.links.new(src, r.inputs['Fac'])
    return r.outputs['Color']

def _noise(nt, vec, scale, detail=4.0, rough=0.5, loc=(0, 0), dim='3D'):
    n = nt.nodes.new('ShaderNodeTexNoise'); n.location = loc
    try:
        n.noise_dimensions = dim
    except Exception:
        pass
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    if vec is not None:
        nt.links.new(vec, n.inputs['Vector'])
    return n

def _coords(nt, kind='Object', loc=(-1200, 0)):
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = loc
    return tc.outputs[kind]

def _world_pos(nt, loc=(-1200, -300)):
    g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = loc
    return g.outputs['Position']

def _rand(nt, loc=(-1200, 300)):
    oi = nt.nodes.new('ShaderNodeObjectInfo'); oi.location = loc
    return oi.outputs['Random']

def _bump(nt, h, strength, dist, loc=(300, -300), normal=None):
    b = nt.nodes.new('ShaderNodeBump'); b.location = loc
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = dist
    nt.links.new(h, b.inputs['Height'])
    if normal is not None:
        nt.links.new(normal, b.inputs['Normal'])
    return b.outputs['Normal']

def _math(nt, op, a, b=None, loc=(0, 0), clamp=False):
    m = nt.nodes.new('ShaderNodeMath'); m.operation = op; m.location = loc; m.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if hasattr(v, 'node'):
            nt.links.new(v, m.inputs[i])
        else:
            m.inputs[i].default_value = v
    return m.outputs[0]

# ------------------------------------------------------------------ materials
def tile():
    """青瓦 - fired grey clay roof tile, per-instance tone variation, light weathering."""
    m, nt, bs, out = _new('M_Tile')
    L = nt.links
    rnd = _rand(nt)
    pos = _world_pos(nt)
    nz = _noise(nt, pos, 2.2, 6, 0.55, (-900, -100))
    fine = _noise(nt, _coords(nt, 'Object', (-1200, -500)), 60.0, 3, 0.6, (-900, -450))
    tone = _math(nt, 'MULTIPLY_ADD', rnd, 0.55, (-700, 300))
    nt.nodes[-1].inputs[2].default_value = 0.2
    base = _ramp(nt, tone, [(0.0, (0.042, 0.045, 0.049)), (0.5, (0.064, 0.067, 0.071)), (1.0, (0.088, 0.090, 0.093))], (-450, 300))
    weather = _ramp(nt, nz.outputs['Fac'], [(0.35, (0.0, 0.0, 0.0)), (0.75, (1.0, 1.0, 1.0))], (-450, 0))
    col = _mix(nt, _math(nt, 'MULTIPLY', weather, 0.30, (-250, 100)), base, (0.11, 0.108, 0.10), (-100, 250))
    L.new(col, bs.inputs['Base Color'])
    rr = _ramp(nt, fine.outputs['Fac'], [(0.3, (0.70, 0.70, 0.70)), (0.7, (0.88, 0.88, 0.88))], (-250, -200))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, fine.outputs['Fac'], 0.12, 0.004), bs.inputs['Normal'])
    bs.inputs['Specular IOR Level'].default_value = 0.35
    return m

def lacquer_red(name='M_RedLacquer', base=(0.215, 0.022, 0.014), rough=0.42):
    """朱红/土红 lacquered timber - semi-gloss, subtle fading and wear."""
    m, nt, bs, out = _new(name)
    L = nt.links
    rnd = _rand(nt)
    pos = _world_pos(nt)
    big = _noise(nt, pos, 0.8, 5, 0.6, (-900, 100))
    grain = _noise(nt, _coords(nt, 'Object', (-1200, -500)), 25.0, 6, 0.65, (-900, -350))
    b2 = tuple(c * 0.78 for c in base)
    b3 = (base[0] * 1.12, base[1] * 1.35, base[2] * 1.35)
    tone = _ramp(nt, big.outputs['Fac'], [(0.3, b2), (0.7, b3)], (-600, 100))
    col = _mix(nt, _math(nt, 'MULTIPLY', rnd, 0.35, (-600, 350)), tone, b2, (-300, 200))
    L.new(col, bs.inputs['Base Color'])
    rr = _ramp(nt, grain.outputs['Fac'], [(0.3, (rough - 0.08,) * 3), (0.7, (rough + 0.12,) * 3)], (-300, -150))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, grain.outputs['Fac'], 0.06, 0.002), bs.inputs['Normal'])
    try:
        bs.inputs['Coat Weight'].default_value = 0.15
        bs.inputs['Coat Roughness'].default_value = 0.25
    except Exception:
        pass
    return m

def plaster():
    """白灰墙 - lime plaster, matte, faint grime."""
    m, nt, bs, out = _new('M_Plaster')
    L = nt.links
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 1.5, 6, 0.55, (-900, 100))
    n2 = _noise(nt, pos, 40.0, 4, 0.6, (-900, -300))
    col = _ramp(nt, n1.outputs['Fac'], [(0.25, (0.66, 0.645, 0.61)), (0.6, (0.76, 0.75, 0.715)), (0.85, (0.79, 0.785, 0.75))], (-500, 100))
    L.new(col, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.93
    L.new(_bump(nt, n2.outputs['Fac'], 0.08, 0.003), bs.inputs['Normal'])
    bs.inputs['Specular IOR Level'].default_value = 0.3
    return m

def plaster_red():
    m, nt, bs, out = _new('M_PlasterRed')
    L = nt.links
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 1.5, 6, 0.55, (-900, 100))
    col = _ramp(nt, n1.outputs['Fac'], [(0.25, (0.20, 0.028, 0.018)), (0.75, (0.27, 0.04, 0.025))], (-500, 100))
    L.new(col, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.8
    return m

def brick():
    """青砖 - grey-green fired brick, lime mortar joints, running bond (UV in metres)."""
    m, nt, bs, out = _new('M_Brick')
    L = nt.links
    uv = _coords(nt, 'UV')
    br = _n(nt, 'ShaderNodeTexBrick', (-700, 100))
    br.offset = 0.5; br.offset_frequency = 2; br.squash = 1.0; br.squash_frequency = 2
    L.new(uv, br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.009
    br.inputs['Mortar Smooth'].default_value = 0.15
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Brick Width'].default_value = 0.245
    br.inputs['Row Height'].default_value = 0.062
    br.inputs['Color1'].default_value = (0.052, 0.060, 0.058, 1)
    br.inputs['Color2'].default_value = (0.078, 0.086, 0.083, 1)
    br.inputs['Mortar'].default_value = (0.36, 0.36, 0.34, 1)
    n = _noise(nt, _world_pos(nt), 18.0, 5, 0.6, (-700, -300))
    col = _mix(nt, n.outputs['Fac'], br.outputs['Color'], (0.04, 0.045, 0.045), (-300, 100), blend='MULTIPLY')
    nt.nodes[-1].inputs[0].default_value = 0.25
    L.new(n.outputs['Fac'], nt.nodes[-1].inputs[0])
    L.new(col, bs.inputs['Base Color'])
    rr = _ramp(nt, br.outputs['Fac'], [(0.0, (0.78, 0.78, 0.78)), (1.0, (0.95, 0.95, 0.95))], (-300, -150))
    L.new(rr, bs.inputs['Roughness'])
    h = _math(nt, 'MULTIPLY_ADD', br.outputs['Fac'], -1.0, (-300, -400)); nt.nodes[-1].inputs[2].default_value = 1.0
    h2 = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.15, (-500, -500)), (-150, -400))
    L.new(_bump(nt, h2, 0.55, 0.006), bs.inputs['Normal'])
    return m

def brick_dark():
    """深色砖 for pavilion plinths (darker, slightly glazed look as in photos)."""
    m = brick()
    m2 = m.copy(); m2.name = 'M_BrickDark'
    nt = m2.node_tree
    br = next(n for n in nt.nodes if n.type == 'TEX_BRICK')
    br.inputs['Color1'].default_value = (0.030, 0.040, 0.038, 1)
    br.inputs['Color2'].default_value = (0.042, 0.054, 0.050, 1)
    br.inputs['Mortar'].default_value = (0.30, 0.30, 0.29, 1)
    bs = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    r = next(n for n in nt.nodes if n.type == 'VALTORGB' and n.outputs[0].links and n.outputs[0].links[0].to_socket.name == 'Roughness')
    r.color_ramp.elements[0].color = (0.45, 0.45, 0.45, 1)
    r.color_ramp.elements[1].color = (0.8, 0.8, 0.8, 1)
    return m2

def granite(name='M_Granite', base=(0.42, 0.41, 0.39), dark=(0.20, 0.20, 0.19), light=(0.56, 0.55, 0.53), rough=0.68, scale=1.0):
    """花岗岩 - speckled granite with stains, per-slab variation."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    rnd = _rand(nt)
    v1 = _n(nt, 'ShaderNodeTexVoronoi', (-900, 300)); v1.inputs['Scale'].default_value = 160 * scale
    L.new(pos, v1.inputs['Vector'])
    n1 = _noise(nt, pos, 260 * scale, 2, 0.5, (-900, 0))
    n2 = _noise(nt, pos, 0.6, 5, 0.6, (-900, -300))
    speck = _ramp(nt, n1.outputs['Fac'], [(0.36, dark), (0.42, base), (0.62, base), (0.68, light)], (-600, 100))
    stain = _ramp(nt, n2.outputs['Fac'], [(0.3, (0.82, 0.82, 0.82)), (0.7, (1.04, 1.04, 1.04))], (-600, -250))
    col = _mix(nt, 1.0, speck, stain, (-300, 0), blend='MULTIPLY')
    at = nt.nodes.new('ShaderNodeAttribute'); at.location = (-1200, 600)
    at.attribute_type = 'GEOMETRY'; at.attribute_name = 'slab'
    rmix = _math(nt, 'ADD', rnd, _math(nt, 'MULTIPLY', at.outputs['Fac'], 1.0, (-900, 600)), (-800, 450))
    rfrac = _math(nt, 'FRACT', rmix, None, (-700, 450))
    var = _ramp(nt, rfrac, [(0.0, (0.92, 0.92, 0.92)), (0.5, (0.98, 0.98, 0.975)), (1.0, (1.04, 1.035, 1.03))], (-600, 400))
    col2 = _mix(nt, 1.0, col, var, (-100, 150), blend='MULTIPLY')
    L.new(col2, bs.inputs['Base Color'])
    rr = _ramp(nt, n2.outputs['Fac'], [(0.3, (rough - 0.1,) * 3), (0.7, (rough + 0.1,) * 3)], (-300, -350))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, n1.outputs['Fac'], 0.05, 0.002), bs.inputs['Normal'])
    return m

def stone_grey():
    return granite('M_StoneGrey', base=(0.24, 0.24, 0.235), dark=(0.13, 0.13, 0.13), light=(0.33, 0.33, 0.32), rough=0.72)

def paver_dark():
    return granite('M_PaverDark', base=(0.20, 0.205, 0.205), dark=(0.12, 0.125, 0.125), light=(0.27, 0.275, 0.27), rough=0.8, scale=0.8)

def water():
    """Clear pond water: refractive surface + green-brown volume absorption (the stony bottom shows through)."""
    m, nt, bs, out = _new('M_Water')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 1.4, 3, 0.45, (-700, -200))
    n2 = _noise(nt, pos, 7.0, 2, 0.4, (-700, -500))
    h = _math(nt, 'ADD', n.outputs['Fac'], _math(nt, 'MULTIPLY', n2.outputs['Fac'], 0.3, (-500, -500)), (-400, -300))
    bs.inputs['Base Color'].default_value = (0.85, 0.95, 0.88, 1)
    bs.inputs['Roughness'].default_value = 0.03
    bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Transmission Weight'].default_value = 1.0
    L.new(_bump(nt, h, 0.03, 0.02), bs.inputs['Normal'])
    va = nt.nodes.new('ShaderNodeVolumeAbsorption'); va.location = (600, -250)
    va.inputs['Color'].default_value = (0.55, 0.78, 0.42, 1)
    va.inputs['Density'].default_value = 1.1
    L.new(va.outputs[0], out.inputs['Volume'])
    return m

def simple(name, color, rough=0.5, metal=0.0, coat=0.0, spec=0.5, emit=None, emit_strength=0.0):
    m, nt, bs, out = _new(name)
    bs.inputs['Base Color'].default_value = tuple(color) + (1,)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    bs.inputs['Specular IOR Level'].default_value = spec
    if coat:
        bs.inputs['Coat Weight'].default_value = coat
    if emit:
        bs.inputs['Emission Color'].default_value = tuple(emit) + (1,)
        bs.inputs['Emission Strength'].default_value = emit_strength
    return m

def wood_brown():
    m, nt, bs, out = _new('M_WoodBrown')
    L = nt.links
    co = _coords(nt, 'Object')
    w = _n(nt, 'ShaderNodeTexWave', (-800, 0)); w.wave_type = 'BANDS'; w.bands_direction = 'X'
    w.inputs['Scale'].default_value = 6.0; w.inputs['Distortion'].default_value = 6.0
    w.inputs['Detail'].default_value = 4.0
    L.new(co, w.inputs['Vector'])
    c = _ramp(nt, w.outputs['Fac'], [(0.2, (0.085, 0.040, 0.020)), (0.8, (0.15, 0.075, 0.038))], (-400, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.55
    return m

def soil():
    m, nt, bs, out = _new('M_Soil')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 12.0, 8, 0.65, (-700, 0))
    c = _ramp(nt, n.outputs['Fac'], [(0.3, (0.030, 0.022, 0.016)), (0.7, (0.065, 0.05, 0.036))], (-400, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.95
    L.new(_bump(nt, n.outputs['Fac'], 0.4, 0.01), bs.inputs['Normal'])
    return m

def gravel():
    m, nt, bs, out = _new('M_Gravel')
    L = nt.links
    pos = _world_pos(nt)
    v = _n(nt, 'ShaderNodeTexVoronoi', (-800, 0)); v.inputs['Scale'].default_value = 45.0
    L.new(pos, v.inputs['Vector'])
    n = _noise(nt, pos, 3.0, 4, 0.5, (-800, -300))
    c = _ramp(nt, v.outputs['Color'], [(0.0, (0.10, 0.10, 0.098)), (0.5, (0.2, 0.198, 0.19)), (1.0, (0.32, 0.31, 0.30))], (-400, 0))
    c2 = _mix(nt, 1.0, c, _ramp(nt, n.outputs['Fac'], [(0.3, (0.8, 0.8, 0.8)), (0.7, (1.05, 1.05, 1.05))], (-400, -300)), (-150, 0), blend='MULTIPLY')
    L.new(c2, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.85
    L.new(_bump(nt, v.outputs['Distance'], 0.6, 0.02), bs.inputs['Normal'])
    return m

def ceiling():
    """平棊天花 - painted coffer panels (ochre/gold ground, darker pattern)."""
    m, nt, bs, out = _new('M_Ceiling')
    L = nt.links
    uv = _coords(nt, 'UV')
    mp = _n(nt, 'ShaderNodeMapping', (-900, 0)); mp.inputs['Scale'].default_value = (2.5, 2.5, 2.5)
    L.new(uv, mp.inputs['Vector'])
    v = _n(nt, 'ShaderNodeTexVoronoi', (-650, 0)); v.feature = 'DISTANCE_TO_EDGE'
    v.inputs['Scale'].default_value = 3.0
    L.new(mp.outputs[0], v.inputs['Vector'])
    c = _ramp(nt, v.outputs['Distance'], [(0.0, (0.16, 0.07, 0.025)), (0.06, (0.42, 0.25, 0.08)), (0.2, (0.55, 0.36, 0.12))], (-350, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.6
    return m

def pool_bed():
    m, nt, bs, out = _new('M_PoolBed')
    L = nt.links
    pos = _world_pos(nt)
    v = _n(nt, 'ShaderNodeTexVoronoi', (-800, 0)); v.inputs['Scale'].default_value = 6.0
    L.new(pos, v.inputs['Vector'])
    c = _ramp(nt, v.outputs['Distance'], [(0.0, (0.16, 0.15, 0.11)), (0.35, (0.22, 0.20, 0.15)), (0.6, (0.10, 0.10, 0.075))], (-400, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.6
    L.new(_bump(nt, v.outputs['Distance'], 0.8, 0.05), bs.inputs['Normal'])
    return m

def ground():
    """compacted earth / fine gravel for the far ground"""
    m, nt, bs, out = _new('M_Ground')
    L = nt.links
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 0.6, 4, 0.5, (-900, 100))
    n2 = _noise(nt, pos, 30.0, 4, 0.6, (-900, -250))
    c = _ramp(nt, n1.outputs['Fac'], [(0.35, (0.105, 0.10, 0.088)), (0.65, (0.125, 0.118, 0.10))], (-500, 100))
    c2 = _mix(nt, 1.0, c, _ramp(nt, n2.outputs['Fac'], [(0.3, (0.85, 0.85, 0.85)), (0.7, (1.1, 1.1, 1.1))], (-500, -250)), (-200, 0), blend='MULTIPLY')
    L.new(c2, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.92
    L.new(_bump(nt, n2.outputs['Fac'], 0.3, 0.01), bs.inputs['Normal'])
    return m

def marble():
    m, nt, bs, out = _new('M_Marble')
    L = nt.links
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 3.0, 8, 0.65, (-900, 100))
    w = _n(nt, 'ShaderNodeTexWave', (-900, -200)); w.inputs['Scale'].default_value = 2.0; w.inputs['Distortion'].default_value = 12.0
    L.new(pos, w.inputs['Vector'])
    c = _ramp(nt, n1.outputs['Fac'], [(0.3, (0.52, 0.52, 0.5)), (0.7, (0.66, 0.66, 0.64))], (-500, 100))
    v = _ramp(nt, w.outputs['Fac'], [(0.0, (0.82, 0.82, 0.82)), (0.12, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))], (-500, -200))
    c2 = _mix(nt, 1.0, c, v, (-200, 0), blend='MULTIPLY')
    L.new(c2, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.55
    L.new(_bump(nt, n1.outputs['Fac'], 0.15, 0.004), bs.inputs['Normal'])
    return m

def leaf(name, c0, c1, trans=0.35):
    m, nt, bs, out = _new(name)
    L = nt.links
    rnd = _rand(nt)
    g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (-1000, -300)
    n = _noise(nt, g.outputs['Position'], 3.0, 2, 0.5, (-800, -200))
    mixf = _math(nt, 'ADD', _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.6, (-600, -200)), 0.2, (-450, -200))
    c = _mix(nt, mixf, c0, c1, (-300, 100))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.45
    try:
        bs.inputs['Transmission Weight'].default_value = 0.0
        bs.inputs['Subsurface Weight'].default_value = 0.0
    except Exception:
        pass
    # thin translucent leaf: mix principled with translucent
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); tr.location = (600, -250)
    L.new(c, tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (800, 0)
    mx.inputs[0].default_value = trans
    L.new(bs.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    out.location = (1000, 0)
    return m

def bark():
    m, nt, bs, out = _new('M_Bark')
    L = nt.links
    co = _coords(nt, 'Object')
    n = _noise(nt, co, 9.0, 8, 0.7, (-800, 0))
    c = _ramp(nt, n.outputs['Fac'], [(0.3, (0.035, 0.028, 0.024)), (0.7, (0.075, 0.062, 0.052))], (-400, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.85
    L.new(_bump(nt, n.outputs['Fac'], 0.6, 0.01), bs.inputs['Normal'])
    return m

def ceil_panel():
    """平棊 panel: ochre ground with a carved eight-petal flower (relief via bump), driven by 0..1 panel UVs."""
    m, nt, bs, out = _new('M_CeilPanel')
    L = nt.links
    uv = _coords(nt, 'UV', (-1500, 0))
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1300, 0)
    L.new(uv, sep.inputs[0])
    cx = _math(nt, 'SUBTRACT', sep.outputs[0], 0.5, (-1100, 100))
    cy = _math(nt, 'SUBTRACT', sep.outputs[1], 0.5, (-1100, -100))
    r = _math(nt, 'SQRT', _math(nt, 'ADD', _math(nt, 'MULTIPLY', cx, cx, (-950, 150)), _math(nt, 'MULTIPLY', cy, cy, (-950, -150)), (-850, 0)), None, (-750, 0))
    th = _math(nt, 'ARCTAN2', cy, cx, (-900, -300))
    petal = _math(nt, 'ABSOLUTE', _math(nt, 'COSINE', _math(nt, 'MULTIPLY', th, 4.0, (-750, -300)), None, (-650, -300)), None, (-550, -300))
    rlim = _math(nt, 'MULTIPLY_ADD', petal, 0.17, (-450, -300)); nt.nodes[-1].inputs[2].default_value = 0.16
    flower = _math(nt, 'LESS_THAN', r, rlim, (-300, -200))
    centre = _math(nt, 'LESS_THAN', r, 0.07, (-300, -400))
    ringv = _math(nt, 'MULTIPLY', _math(nt, 'GREATER_THAN', r, 0.40, (-450, -550)), _math(nt, 'LESS_THAN', r, 0.43, (-450, -650)), (-300, -600))
    h = _math(nt, 'ADD', _math(nt, 'ADD', flower, _math(nt, 'MULTIPLY', centre, 0.6, (-150, -400)), (0, -300)), _math(nt, 'MULTIPLY', ringv, 0.5, (-150, -600)), (100, -400))
    base = (0.36, 0.22, 0.085)
    dark = (0.21, 0.12, 0.045)
    col = _mix(nt, _math(nt, 'MULTIPLY', flower, 0.55, (0, 100)), base, (0.46, 0.30, 0.12), (200, 100))
    col2 = _mix(nt, _math(nt, 'MULTIPLY', ringv, 0.8, (100, 250)), col, dark, (350, 150))
    L.new(col2, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.7
    L.new(_bump(nt, h, 0.6, 0.012, (350, -350)), bs.inputs['Normal'])
    return m

def build_all():
    tile()
    lacquer_red()
    lacquer_red('M_DoorRed', base=(0.20, 0.024, 0.016), rough=0.45)
    lacquer_red('M_RedOrange', base=(0.30, 0.045, 0.018), rough=0.5)
    plaster()
    plaster_red()
    brick()
    brick_dark()
    granite()
    granite('M_GraniteOut', base=(0.36, 0.355, 0.335), dark=(0.18, 0.18, 0.17), light=(0.48, 0.47, 0.45), rough=0.72)
    stone_grey()
    pool_bed()
    ground()
    paver_dark()
    water()
    soil()
    gravel()
    ceiling()
    wood_brown()
    simple('M_Interior', (0.012, 0.010, 0.009), rough=0.9, spec=0.2)
    simple('M_Glass', (0.02, 0.025, 0.03), rough=0.05, spec=0.5)
    simple('M_Gold', (0.83, 0.58, 0.26), rough=0.28, metal=1.0)
    simple('M_BlackLacquer', (0.012, 0.012, 0.012), rough=0.32, coat=0.3)
    simple('M_Paper', (0.62, 0.64, 0.66), rough=0.25, spec=0.5)
    simple('M_RedPaint', (0.23, 0.035, 0.025), rough=0.6)
    simple('M_Bronze', (0.12, 0.08, 0.045), rough=0.45, metal=0.85)
    simple('M_Lamp', (0.9, 0.75, 0.5), rough=0.6, emit=(1.0, 0.72, 0.42), emit_strength=0.0)
    granite('M_StoneTurtle', base=(0.20, 0.20, 0.185), dark=(0.10, 0.105, 0.095), light=(0.28, 0.28, 0.265), rough=0.8, scale=0.8)
    granite('M_PoolStone', base=(0.12, 0.13, 0.10), dark=(0.06, 0.07, 0.05), light=(0.20, 0.20, 0.16), rough=0.6, scale=0.5)
    marble()
    ceil_panel()
    simple('M_CeilRib', (0.035, 0.055, 0.048), rough=0.55)
    simple('M_PanelDark', (0.030, 0.040, 0.036), rough=0.7, spec=0.3)
    simple('M_BlackStone', (0.010, 0.011, 0.011), rough=0.22, spec=0.5)
    bark()
    leaf('M_LeafPurple', (0.075, 0.022, 0.028), (0.15, 0.042, 0.048), trans=0.25)
    leaf('M_LeafBamboo', (0.045, 0.085, 0.020), (0.095, 0.15, 0.035), trans=0.3)
    simple('M_BambooCulm', (0.16, 0.20, 0.06), rough=0.4, spec=0.5)
    simple('M_LanternRed', (0.42, 0.03, 0.02), rough=0.6, spec=0.3)
    lacquer_red('M_DoorDark', base=(0.030, 0.012, 0.008), rough=0.5)
    return sorted(m.name for m in bpy.data.materials)
