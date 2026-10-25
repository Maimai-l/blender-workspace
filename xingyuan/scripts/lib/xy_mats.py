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

def _grime(nt, col, ao_strength=0.22, damp=0.0, damp_h=0.7, loc=(200, 300)):
    """Darken a colour socket in crevices (ambient occlusion) and, optionally, near the base of walls
    (rising damp / splash-back, measured from the local floor level z=0 or z=-0.6)."""
    L = nt.links
    ao = nt.nodes.new('ShaderNodeAmbientOcclusion'); ao.location = (loc[0] - 400, loc[1] + 200)
    ao.inputs['Distance'].default_value = 0.35
    ao.samples = 8
    occ = _math(nt, 'SUBTRACT', 1.0, ao.outputs['AO'], (loc[0] - 200, loc[1] + 200))
    k = _math(nt, 'MULTIPLY', occ, ao_strength, (loc[0] - 50, loc[1] + 200))
    out = _mix(nt, k, col, (0.05, 0.045, 0.04), loc, blend='MIX')
    if damp > 0:
        g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (loc[0] - 600, loc[1] - 100)
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (loc[0] - 450, loc[1] - 100)
        L.new(g.outputs['Position'], sep.inputs[0])
        # height above the nearer floor level (0 or -0.6)
        za = _math(nt, 'ABSOLUTE', sep.outputs['Z'], None, (loc[0] - 300, loc[1] - 50))
        zb = _math(nt, 'ABSOLUTE', _math(nt, 'ADD', sep.outputs['Z'], 0.6, (loc[0] - 350, loc[1] - 200)), None, (loc[0] - 300, loc[1] - 200))
        h = _math(nt, 'MINIMUM', za, zb, (loc[0] - 200, loc[1] - 120))
        f = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'DIVIDE', h, damp_h, (loc[0] - 100, loc[1] - 120), clamp=True), (loc[0], loc[1] - 120))
        nz = _noise(nt, g.outputs['Position'], 2.5, 4, 0.6, (loc[0] - 300, loc[1] - 350))
        f2 = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', f, f, (loc[0] + 100, loc[1] - 120)), nz.outputs['Fac'], (loc[0] + 200, loc[1] - 150))
        f3 = _math(nt, 'MULTIPLY', f2, damp, (loc[0] + 300, loc[1] - 150))
        out = _mix(nt, f3, out, (0.20, 0.20, 0.17), (loc[0] + 450, loc[1]), blend='MULTIPLY')
    return out

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
    L.new(_grime(nt, col, ao_strength=0.18), bs.inputs['Base Color'])
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
    L.new(_grime(nt, col, ao_strength=0.25, damp=0.9, damp_h=0.8), bs.inputs['Base Color'])
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

def granite(name='M_Granite', base=(0.34, 0.335, 0.32), dark=(0.17, 0.17, 0.16), light=(0.46, 0.455, 0.44), rough=0.68, scale=1.0):
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
    L.new(_grime(nt, col2, ao_strength=0.30), bs.inputs['Base Color'])
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

def pond_water(fountains=()):
    """Garden pond: refractive surface with wind ripples, murky green volume (absorption + scattering).
    fountains: [(x, y, r_in, r_out, 'disc'|'ring', R)] -> churned foam painted on the surface around each."""
    m, nt, bs, out = _new('M_PondWater')
    L = nt.links
    pos = _world_pos(nt, (-1600, -200))
    mp = _n(nt, 'ShaderNodeMapping', (-1000, -300)); mp.inputs['Scale'].default_value = (1.0, 2.2, 1.0)
    L.new(pos, mp.inputs['Vector'])
    n = _noise(nt, mp.outputs[0], 1.1, 4, 0.5, (-700, -200))
    n2 = _noise(nt, pos, 6.0, 2, 0.4, (-700, -500))
    h = _math(nt, 'ADD', n.outputs['Fac'], _math(nt, 'MULTIPLY', n2.outputs['Fac'], 0.35, (-500, -500)), (-400, -300))
    bs.inputs['Base Color'].default_value = (0.9, 0.95, 0.9, 1)
    bs.inputs['Roughness'].default_value = 0.02
    bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Transmission Weight'].default_value = 1.0
    va = nt.nodes.new('ShaderNodeVolumeAbsorption'); va.location = (600, -250)
    va.inputs['Color'].default_value = (0.45, 0.58, 0.40, 1)
    va.inputs['Density'].default_value = 2.2
    vs = nt.nodes.new('ShaderNodeVolumeScatter'); vs.location = (600, -450)
    vs.inputs['Color'].default_value = (0.55, 0.68, 0.62, 1)
    vs.inputs['Density'].default_value = 1.1
    vs.inputs['Anisotropy'].default_value = 0.35
    ad = nt.nodes.new('ShaderNodeAddShader'); ad.location = (800, -350)
    L.new(va.outputs[0], ad.inputs[0]); L.new(vs.outputs[0], ad.inputs[1])
    L.new(ad.outputs[0], out.inputs['Volume'])
    if not fountains:
        L.new(_bump(nt, h, 0.14, 0.03), bs.inputs['Normal'])
        return m
    # ---- foam mask around the fountains (max over all), with stronger ripples there
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1400, 400)
    L.new(pos, sep.inputs[0])
    mask = None
    y0 = 600
    for (fx, fy, r_in, r_out, kind, R) in fountains:
        dx = _math(nt, 'SUBTRACT', sep.outputs['X'], fx, (-1200, y0))
        dy = _math(nt, 'SUBTRACT', sep.outputs['Y'], fy, (-1200, y0 - 80))
        d = _math(nt, 'SQRT', _math(nt, 'ADD', _math(nt, 'MULTIPLY', dx, dx, (-1100, y0)), _math(nt, 'MULTIPLY', dy, dy, (-1100, y0 - 80)),
                                    (-1000, y0)), None, (-900, y0))
        if kind == 'ring':
            d = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', d, R, (-800, y0)), None, (-700, y0))
        t = _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', r_out, d, (-600, y0)), r_out - r_in, (-500, y0), clamp=True)
        mask = t if mask is None else _math(nt, 'MAXIMUM', mask, t, (-400, y0))
        y0 -= 220
    # churned foam: marbled noise (domain-distorted), threshold falls toward the fountain -> organic patches
    nd = _noise(nt, pos, 1.6, 3, 0.5, (-1100, 1150))
    dist = _n(nt, 'ShaderNodeVectorMath', (-950, 1150)); dist.operation = 'SCALE'
    L.new(nd.outputs['Color'], dist.inputs[0]); dist.inputs['Scale'].default_value = 0.8
    pd = _n(nt, 'ShaderNodeVectorMath', (-800, 1100)); pd.operation = 'ADD'
    L.new(pos, pd.inputs[0]); L.new(dist.outputs[0], pd.inputs[1])
    nf = _noise(nt, pd.outputs[0], 3.2, 8, 0.68, (-650, 1100))
    thr = _math(nt, 'SUBTRACT', 0.98, _math(nt, 'MULTIPLY', mask, 0.62, (-500, 800)), (-400, 800))
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-200, 950)
    mr.interpolation_type = 'SMOOTHSTEP'
    L.new(nf.outputs['Fac'], mr.inputs['Value'])
    L.new(_math(nt, 'SUBTRACT', thr, 0.06, (-300, 850)), mr.inputs['From Min'])
    L.new(_math(nt, 'ADD', thr, 0.06, (-300, 750)), mr.inputs['From Max'])
    foam = _math(nt, 'MULTIPLY', mr.outputs['Result'], _math(nt, 'MINIMUM', _math(nt, 'MULTIPLY', mask, 4.0, (0, 700)), 0.92, (100, 700)), (250, 850))
    fb = nt.nodes.new('ShaderNodeBsdfPrincipled'); fb.location = (600, 350)
    fb.inputs['Base Color'].default_value = (0.78, 0.81, 0.80, 1)
    fb.inputs['Roughness'].default_value = 0.55
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (900, 100)
    L.new(foam, mx.inputs[0]); L.new(bs.outputs[0], mx.inputs[1]); L.new(fb.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    # ripples: wind + rings spreading from the fountains
    ring_w = nt.nodes.new('ShaderNodeTexWave'); ring_w.location = (-700, 1400)
    ring_w.wave_type = 'RINGS'
    ring_w.inputs['Scale'].default_value = 1.0
    hh = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', mask, _math(nt, 'MULTIPLY', nf.outputs['Fac'], 1.6, (-300, 1300)), (-200, 1300)), (-100, -300))
    L.new(_bump(nt, hh, 0.16, 0.03, (500, -150)), bs.inputs['Normal'])
    out.location = (1100, 0)
    return m

def fountain_water():
    """The rising dome / jets of a fountain: glassy water, white where aerated (low on the dome, at the crown)."""
    m, nt, bs, out = _new('M_FountainWater')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 7.0, 5, 0.65, (-900, 0))
    bs.inputs['Base Color'].default_value = (0.9, 0.94, 0.94, 1)
    bs.inputs['Roughness'].default_value = 0.04
    bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Transmission Weight'].default_value = 1.0
    fb = nt.nodes.new('ShaderNodeBsdfPrincipled'); fb.location = (600, 350)
    fb.inputs['Base Color'].default_value = (0.80, 0.83, 0.83, 1)
    fb.inputs['Roughness'].default_value = 0.45
    fb.inputs['Subsurface Weight'].default_value = 0.4
    fb.inputs['Subsurface Radius'].default_value = (0.03, 0.035, 0.04)
    wf = _ramp(nt, n.outputs['Fac'], [(0.38, (0, 0, 0)), (0.62, (1, 1, 1))], (-500, 200))
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (900, 100)
    L.new(wf, mx.inputs[0]); L.new(bs.outputs[0], mx.inputs[1]); L.new(fb.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    L.new(_bump(nt, n.outputs['Fac'], 0.5, 0.02), bs.inputs['Normal'])
    out.location = (1100, 0)
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
    # per-instance (spray) random + spatial noise -> colour between c0 and c1
    mixf = _math(nt, 'ADD', _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.45, (-600, -200)),
                 _math(nt, 'MULTIPLY', rnd, 0.55, (-600, -350)), (-450, -200))
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

# ------------------------------------------------------------------ environment: plants
def leaf2(name, c0, c1, back=(0.0, 0.0, 0.0), back_mix=0.0, trans=0.32, rough=0.42, spec=0.5, var_tree=0.35,
          dry=None, dry_frac=0.0, sheen=0.0, sheen_tint=(1.0, 1.0, 1.0)):
    """Thin leaf for instanced sprays.
    colour = mix(c0, c1) by per-instance random + crown-scale noise + tree-scale noise (var_tree);
    a fraction of sprays (dry_frac) drift toward `dry` (older / sun-bleached leaves);
    underside paler (back, back_mix); light transmission through the blade (trans)."""
    m, nt, bs, out = _new(name)
    L = nt.links
    rnd = _rand(nt)
    g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (-1200, -300)
    n_hi = _noise(nt, g.outputs['Position'], 2.2, 2, 0.5, (-950, -150))
    n_lo = _noise(nt, g.outputs['Position'], 0.07, 2, 0.5, (-950, -450))
    a = _math(nt, 'MULTIPLY', rnd, 0.45, (-750, 100))
    b = _math(nt, 'MULTIPLY', n_hi.outputs['Fac'], 0.35, (-750, -150))
    lo = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', n_lo.outputs['Fac'], 0.5, (-750, -450)), var_tree * 2.0, (-600, -450))
    f = _math(nt, 'ADD', _math(nt, 'ADD', a, b, (-550, 0)), lo, (-420, -100), clamp=True)
    c = _mix(nt, f, c0, c1, (-250, 100))
    if dry is not None and dry_frac > 0:
        # per-instance: the top dry_frac of the random range fades toward the dry colour
        t = _math(nt, 'SUBTRACT', rnd, 1.0 - dry_frac, (-550, 300))
        t = _math(nt, 'DIVIDE', t, dry_frac, (-420, 300), clamp=True)
        c = _mix(nt, _math(nt, 'MULTIPLY', t, 0.7, (-300, 300)), c, dry, (-120, 200))
    if back_mix > 0:
        c = _mix(nt, _math(nt, 'MULTIPLY', g.outputs['Backfacing'], back_mix, (-250, -250)), c, back, (0, 50))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Specular IOR Level'].default_value = spec
    if sheen > 0:
        bs.inputs['Sheen Weight'].default_value = sheen
        bs.inputs['Sheen Tint'].default_value = tuple(sheen_tint) + (1,)
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); tr.location = (600, -300)
    tcol = _mix(nt, 1.0, c, (1.25, 1.35, 0.75), (300, -300), blend='MULTIPLY')
    L.new(tcol, tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (850, 0)
    mx.inputs[0].default_value = trans
    L.new(bs.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    out.location = (1050, 0)
    return m

def bark2(name, c0, c1, furrow=0.6, scale=9.0, stretch=4.0, moss=0.0):
    """Tree bark in the template's object space: vertical furrows (noise stretched along Z) + optional moss on
    the upward-facing side. Grime from AO."""
    m, nt, bs, out = _new(name)
    L = nt.links
    co = _coords(nt, 'Object', (-1400, 0))
    mp = _n(nt, 'ShaderNodeMapping', (-1200, 0)); mp.inputs['Scale'].default_value = (stretch, stretch, 1.0)
    L.new(co, mp.inputs['Vector'])
    n = _noise(nt, mp.outputs[0], scale, 8, 0.7, (-950, 0))
    n2 = _noise(nt, co, scale * 0.25, 3, 0.5, (-950, -300))
    v = _math(nt, 'ADD', _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.75, (-750, 0)),
              _math(nt, 'MULTIPLY', n2.outputs['Fac'], 0.25, (-750, -250)), (-600, -100))
    c = _ramp(nt, v, [(0.32, c0), (0.68, c1)], (-450, 0))
    if moss > 0:
        g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (-900, 400)
        sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-700, 400)
        L.new(g.outputs['Normal'], sep.inputs[0])
        mz = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs['Z'], 0.25, (-550, 400), clamp=True), moss * 1.6, (-400, 400))
        mz = _math(nt, 'MULTIPLY', mz, n2.outputs['Fac'], (-300, 350))
        # moss only low on the trunk (object-space height < ~2.5 m)
        sz = nt.nodes.new('ShaderNodeSeparateXYZ'); sz.location = (-900, 650)
        L.new(co, sz.inputs[0])
        low = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'DIVIDE', sz.outputs['Z'], 2.5, (-700, 650), clamp=True), (-550, 650))
        mz = _math(nt, 'MULTIPLY', mz, low, (-250, 500))
        c = _mix(nt, mz, c, (0.05, 0.075, 0.025), (-150, 150))
    c = _grime(nt, c, ao_strength=0.35, loc=(100, 250))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.88
    bs.inputs['Specular IOR Level'].default_value = 0.35
    L.new(_bump(nt, n.outputs['Fac'], furrow, 0.012), bs.inputs['Normal'])
    return m

def grass_blade():
    """Lawn grass blades: green with per-clump variation, paler dry tips (height from object Z)."""
    m, nt, bs, out = _new('M_Grass')
    L = nt.links
    rnd = _rand(nt)
    g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (-1200, -300)
    co = _coords(nt, 'Object', (-1200, -600))
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1000, -600)
    L.new(co, sep.inputs[0])
    n_lo = _noise(nt, g.outputs['Position'], 0.18, 3, 0.55, (-950, -250))
    f = _math(nt, 'ADD', _math(nt, 'MULTIPLY', rnd, 0.5, (-750, 100)), _math(nt, 'MULTIPLY', n_lo.outputs['Fac'], 0.6, (-750, -200)), (-600, 0), clamp=True)
    c = _mix(nt, f, (0.040, 0.088, 0.016), (0.115, 0.195, 0.038), (-450, 100))
    tip = _math(nt, 'DIVIDE', sep.outputs['Z'], 0.14, (-800, -600), clamp=True)
    tip = _math(nt, 'MULTIPLY', _math(nt, 'MULTIPLY', tip, tip, (-650, -600)), 0.45, (-500, -600))
    c = _mix(nt, tip, c, (0.20, 0.20, 0.07), (-300, 0))
    base = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'DIVIDE', sep.outputs['Z'], 0.05, (-650, -800), clamp=True), (-500, -800))
    c = _mix(nt, _math(nt, 'MULTIPLY', base, 0.6, (-350, -800)), c, (0.02, 0.03, 0.01), (-150, -100))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.5
    bs.inputs['Specular IOR Level'].default_value = 0.45
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); tr.location = (600, -300)
    L.new(c, tr.inputs['Color'])
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (850, 0)
    mx.inputs[0].default_value = 0.25
    L.new(bs.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    out.location = (1050, 0)
    return m

# ------------------------------------------------------------------ environment: ground and built surfaces
def _attr(nt, name, loc):
    a = nt.nodes.new('ShaderNodeAttribute'); a.location = loc
    a.attribute_type = 'GEOMETRY'; a.attribute_name = name
    return a.outputs['Fac']

def _edge(nt, w, nfac, amt, loc):
    """Irregular boundary for a 0..1 blend weight: smoothstep(w + amt*(noise-0.5)) around 0.5."""
    t = _math(nt, 'ADD', w, _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', nfac, 0.5, (loc[0] - 300, loc[1] - 80)), amt, (loc[0] - 180, loc[1] - 80)), (loc[0] - 60, loc[1]))
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = loc
    mr.interpolation_type = 'SMOOTHSTEP'
    mr.inputs['From Min'].default_value = 0.35; mr.inputs['From Max'].default_value = 0.65
    nt.links.new(t, mr.inputs['Value'])
    return mr.outputs['Result']

def terrain():
    """Ground of the garden. Point attributes from the terrain grid choose the cover:
    lawn (default), forest floor (w_forest: leaf litter, soil, moss), bare soil (w_bare), planted bank (w_bank),
    wet mud at the water line and under water (w_mud)."""
    m, nt, bs, out = _new('M_Terrain')
    L = nt.links
    pos = _world_pos(nt, (-1700, -200))
    wf = _attr(nt, 'w_forest', (-1700, 500)); wb = _attr(nt, 'w_bare', (-1700, 350))
    wk = _attr(nt, 'w_bank', (-1700, 200)); wm = _attr(nt, 'w_mud', (-1700, 50))
    n_big = _noise(nt, pos, 0.12, 4, 0.55, (-1400, -100))
    n_mid = _noise(nt, pos, 0.9, 5, 0.6, (-1400, -400))
    n_fine = _noise(nt, pos, 14.0, 6, 0.65, (-1400, -700))
    # lawn: green with mown patchiness and a few dry areas
    lawn = _ramp(nt, n_big.outputs['Fac'], [(0.25, (0.050, 0.095, 0.020)), (0.55, (0.072, 0.125, 0.026)),
                                            (0.85, (0.098, 0.130, 0.038))], (-1000, 600))
    lawn = _mix(nt, 1.0, lawn, _ramp(nt, n_fine.outputs['Fac'], [(0.3, (0.82, 0.82, 0.82)), (0.7, (1.12, 1.12, 1.12))], (-1000, 350)), (-750, 550), blend='MULTIPLY')
    # forest floor: dark soil + fallen leaves + moss
    vor = _n(nt, 'ShaderNodeTexVoronoi', (-1400, -1000)); vor.inputs['Scale'].default_value = 18.0
    L.new(pos, vor.inputs['Vector'])
    litter = _ramp(nt, vor.outputs['Color'], [(0.0, (0.045, 0.034, 0.021)), (0.45, (0.075, 0.055, 0.032)), (0.75, (0.10, 0.075, 0.042)),
                                             (1.0, (0.050, 0.060, 0.026))], (-1000, 100))
    # mostly shaded ground cover / thin grass, with patches of leaf litter and soil
    cover = _ramp(nt, n_fine.outputs['Fac'], [(0.3, (0.028, 0.050, 0.013)), (0.7, (0.045, 0.072, 0.018))], (-1000, -150))
    forest = _mix(nt, _ramp(nt, n_mid.outputs['Fac'], [(0.50, (0, 0, 0)), (0.68, (0.85, 0.85, 0.85))], (-1000, -300)), cover,
                  litter, (-750, 100))
    bare = _ramp(nt, n_mid.outputs['Fac'], [(0.3, (0.16, 0.12, 0.085)), (0.7, (0.22, 0.17, 0.12))], (-1000, -400))
    bank = _ramp(nt, n_mid.outputs['Fac'], [(0.3, (0.030, 0.062, 0.014)), (0.7, (0.055, 0.095, 0.022))], (-1000, -650))
    mud = _ramp(nt, n_mid.outputs['Fac'], [(0.3, (0.040, 0.036, 0.026)), (0.7, (0.070, 0.062, 0.042))], (-1000, -900))
    e_f = _edge(nt, wf, n_mid.outputs['Fac'], 0.45, (-500, 300))
    e_b = _edge(nt, wb, n_mid.outputs['Fac'], 0.55, (-500, 100))
    e_k = _edge(nt, wk, n_mid.outputs['Fac'], 0.40, (-500, -100))
    e_m = _edge(nt, wm, n_fine.outputs['Fac'], 0.30, (-500, -300))
    c = _mix(nt, e_f, lawn, forest, (-250, 400))
    c = _mix(nt, e_b, c, bare, (-100, 300))
    c = _mix(nt, e_k, c, bank, (50, 200))
    c = _mix(nt, e_m, c, mud, (200, 100))
    L.new(c, bs.inputs['Base Color'])
    rough = _mix(nt, e_m, (0.92, 0.92, 0.92), (0.45, 0.45, 0.45), (200, -150))
    L.new(rough, bs.inputs['Roughness'])
    bs.inputs['Specular IOR Level'].default_value = 0.22
    h = _math(nt, 'ADD', n_fine.outputs['Fac'], _math(nt, 'MULTIPLY', vor.outputs['Distance'], e_f, (0, -700)), (150, -600))
    L.new(_bump(nt, h, 0.35, 0.02, (400, -400)), bs.inputs['Normal'])
    return m

def mud_bed():
    """Pond bed: silt with darker organic patches and a green algae film."""
    m, nt, bs, out = _new('M_Mud')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 0.6, 5, 0.6, (-800, 0))
    n2 = _noise(nt, pos, 6.0, 4, 0.6, (-800, -300))
    c = _ramp(nt, n.outputs['Fac'], [(0.3, (0.028, 0.030, 0.018)), (0.55, (0.055, 0.058, 0.035)), (0.8, (0.075, 0.07, 0.045))], (-400, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.6
    L.new(_bump(nt, n2.outputs['Fac'], 0.4, 0.03), bs.inputs['Normal'])
    return m

def red_paver():
    """Fired clay pavers of the west terrace (natural colour; the photo grading pushes them to pink)."""
    m, nt, bs, out = _new('M_RedPaver')
    L = nt.links
    at = nt.nodes.new('ShaderNodeAttribute'); at.location = (-1200, 300); at.attribute_type = 'GEOMETRY'; at.attribute_name = 'slab'
    pos = _world_pos(nt)
    n = _noise(nt, pos, 3.0, 5, 0.6, (-900, -100))
    fine = _noise(nt, pos, 40.0, 3, 0.6, (-900, -400))
    base = _ramp(nt, at.outputs['Fac'], [(0.0, (0.17, 0.055, 0.035)), (0.5, (0.235, 0.085, 0.052)), (1.0, (0.29, 0.12, 0.075))], (-600, 300))
    dirt = _ramp(nt, n.outputs['Fac'], [(0.4, (0, 0, 0)), (0.75, (1, 1, 1))], (-600, 0))
    c = _mix(nt, _math(nt, 'MULTIPLY', dirt, 0.35, (-400, 0)), base, (0.11, 0.075, 0.055), (-300, 200))
    c = _grime(nt, c, ao_strength=0.3, loc=(0, 300))
    L.new(c, bs.inputs['Base Color'])
    L.new(_ramp(nt, fine.outputs['Fac'], [(0.3, (0.78, 0.78, 0.78)), (0.7, (0.9, 0.9, 0.9))], (-300, -300)), bs.inputs['Roughness'])
    L.new(_bump(nt, fine.outputs['Fac'], 0.2, 0.004), bs.inputs['Normal'])
    return m

def pink_stone():
    """Pinkish granite slabs of the west path (with grey diamond inlays in M_StoneGrey)."""
    return granite('M_PinkPath', base=(0.27, 0.19, 0.165), dark=(0.16, 0.11, 0.095), light=(0.36, 0.26, 0.22), rough=0.7, scale=1.2)

def concrete_light():
    m, nt, bs, out = _new('M_LightConcrete')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 1.2, 4, 0.55, (-900, 0))
    fine = _noise(nt, pos, 60.0, 2, 0.5, (-900, -300))
    c = _ramp(nt, n.outputs['Fac'], [(0.3, (0.30, 0.295, 0.28)), (0.7, (0.40, 0.395, 0.38))], (-500, 0))
    c = _mix(nt, 1.0, c, _ramp(nt, fine.outputs['Fac'], [(0.3, (0.9, 0.9, 0.9)), (0.7, (1.06, 1.06, 1.06))], (-500, -300)), (-250, 0), blend='MULTIPLY')
    c = _grime(nt, c, ao_strength=0.3, loc=(0, 300))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.88
    L.new(_bump(nt, fine.outputs['Fac'], 0.25, 0.003), bs.inputs['Normal'])
    return m

def corten():
    """Weathering steel: orange-brown rust with darker streaks and blotches."""
    m, nt, bs, out = _new('M_Corten')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 4.0, 8, 0.65, (-900, 0))
    mp = _n(nt, 'ShaderNodeMapping', (-1100, -350)); mp.inputs['Scale'].default_value = (6.0, 6.0, 0.6)
    L.new(pos, mp.inputs['Vector'])
    streak = _noise(nt, mp.outputs[0], 3.0, 3, 0.5, (-900, -350))
    c = _ramp(nt, n.outputs['Fac'], [(0.3, (0.060, 0.022, 0.010)), (0.55, (0.115, 0.040, 0.015)), (0.8, (0.165, 0.062, 0.022))], (-500, 0))
    c = _mix(nt, _ramp(nt, streak.outputs['Fac'], [(0.5, (0, 0, 0)), (0.75, (0.5, 0.5, 0.5))], (-500, -350)), c, (0.06, 0.025, 0.012), (-250, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.82
    bs.inputs['Specular IOR Level'].default_value = 0.4
    L.new(_bump(nt, n.outputs['Fac'], 0.3, 0.004), bs.inputs['Normal'])
    return m

def boulder():
    """Garden rock (yellow-grey limestone): tonal noise, darker crevices, moss and lichen on upward faces,
    darker wet band at the water line (z < -1.35)."""
    m, nt, bs, out = _new('M_Boulder')
    L = nt.links
    pos = _world_pos(nt, (-1500, -200))
    rnd = _rand(nt, (-1500, 300))
    n = _noise(nt, pos, 2.5, 8, 0.65, (-1200, 0))
    fine = _noise(nt, pos, 20.0, 4, 0.6, (-1200, -350))
    tone = _math(nt, 'ADD', _math(nt, 'MULTIPLY', n.outputs['Fac'], 0.7, (-1000, 0)), _math(nt, 'MULTIPLY', rnd, 0.3, (-1000, 250)), (-850, 100))
    c = _ramp(nt, tone, [(0.25, (0.055, 0.052, 0.045)), (0.55, (0.12, 0.112, 0.092)), (0.85, (0.18, 0.168, 0.14))], (-700, 100))
    g = nt.nodes.new('ShaderNodeNewGeometry'); g.location = (-1200, 600)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1000, 600)
    L.new(g.outputs['Normal'], sep.inputs[0])
    up = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs['Z'], 0.45, (-850, 600), clamp=True), 2.0, (-700, 600))
    mossn = _ramp(nt, fine.outputs['Fac'], [(0.45, (0, 0, 0)), (0.65, (1, 1, 1))], (-850, 400))
    moss = _math(nt, 'MULTIPLY', up, mossn, (-550, 500), clamp=True)
    c = _mix(nt, _math(nt, 'MULTIPLY', moss, 0.75, (-450, 500)), c, (0.045, 0.07, 0.022), (-350, 300))
    sepp = nt.nodes.new('ShaderNodeSeparateXYZ'); sepp.location = (-1300, -600)
    L.new(pos, sepp.inputs[0])
    wet = _math(nt, 'SUBTRACT', 1.0, _math(nt, 'DIVIDE', _math(nt, 'SUBTRACT', sepp.outputs['Z'], -1.45, (-1100, -600)), 0.12, (-950, -600), clamp=True), (-800, -600))
    c = _mix(nt, _math(nt, 'MULTIPLY', wet, 0.7, (-650, -600)), c, (0.035, 0.035, 0.025), (-200, 200))
    c = _grime(nt, c, ao_strength=0.45, loc=(50, 300))
    L.new(c, bs.inputs['Base Color'])
    rough = _mix(nt, wet, (0.82, 0.82, 0.82), (0.35, 0.35, 0.35), (0, -200))
    L.new(rough, bs.inputs['Roughness'])
    h = _math(nt, 'ADD', n.outputs['Fac'], _math(nt, 'MULTIPLY', fine.outputs['Fac'], 0.3, (-900, -450)), (-700, -400))
    L.new(_bump(nt, h, 0.7, 0.05, (300, -400)), bs.inputs['Normal'])
    return m

def foam():
    """Aerated fountain water: milky white, glinting, partly see-through at the thin edges."""
    m, nt, bs, out = _new('M_Foam')
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 18.0, 4, 0.6, (-700, -200))
    bs.inputs['Base Color'].default_value = (0.78, 0.82, 0.83, 1)
    bs.inputs['Roughness'].default_value = 0.22
    bs.inputs['Transmission Weight'].default_value = 0.35
    bs.inputs['IOR'].default_value = 1.33
    bs.inputs['Subsurface Weight'].default_value = 0.4
    bs.inputs['Subsurface Radius'].default_value = (0.04, 0.045, 0.05)
    vb = _n(nt, 'ShaderNodeTexVoronoi', (-700, -500)); vb.inputs['Scale'].default_value = 45.0
    L.new(pos, vb.inputs['Vector'])
    hb = _math(nt, 'ADD', n.outputs['Fac'], _math(nt, 'MULTIPLY', vb.outputs['Distance'], 0.8, (-500, -500)), (-350, -350))
    L.new(_bump(nt, hb, 0.6, 0.01), bs.inputs['Normal'])
    # thin, glancing parts let the pond show through
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.location = (200, -300)
    lw.inputs['Blend'].default_value = 0.35
    tr = nt.nodes.new('ShaderNodeBsdfTransparent'); tr.location = (600, -250)
    mx = nt.nodes.new('ShaderNodeMixShader'); mx.location = (800, 0)
    inv = _math(nt, 'SUBTRACT', 1.0, lw.outputs['Facing'], (400, -300))
    L.new(_math(nt, 'MULTIPLY', inv, 0.45, (500, -300)), mx.inputs[0])
    L.new(bs.outputs[0], mx.inputs[1]); L.new(tr.outputs[0], mx.inputs[2])
    L.new(mx.outputs[0], out.inputs['Surface'])
    out.location = (1000, 0)
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
    granite('M_GraniteOut', base=(0.29, 0.285, 0.27), dark=(0.15, 0.15, 0.14), light=(0.40, 0.395, 0.38), rough=0.72)
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
    simple('M_Gold', (0.86, 0.62, 0.28), rough=0.32, metal=1.0)
    simple('M_PlaqueRed', (0.045, 0.012, 0.008), rough=0.45, spec=0.4)
    simple('M_BlackLacquer', (0.012, 0.011, 0.010), rough=0.78, spec=0.2)
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
    leaf('M_LeafBamboo', (0.045, 0.085, 0.020), (0.095, 0.15, 0.035), trans=0.3)
    simple('M_BambooCulm', (0.16, 0.20, 0.06), rough=0.4, spec=0.5)
    simple('M_LanternRed', (0.42, 0.03, 0.02), rough=0.6, spec=0.3)
    lacquer_red('M_DoorDark', base=(0.030, 0.012, 0.008), rough=0.5)
    # ---- environment
    leaf2('M_LeafWillow', (0.060, 0.092, 0.032), (0.135, 0.180, 0.070), back=(0.20, 0.23, 0.17), back_mix=0.55, trans=0.32, rough=0.45,
          var_tree=0.30, dry=(0.17, 0.17, 0.06), dry_frac=0.08)
    leaf2('M_LeafCamphor', (0.026, 0.055, 0.008), (0.078, 0.122, 0.018), back=(0.10, 0.13, 0.05), back_mix=0.45, trans=0.28,
          rough=0.40, spec=0.5, var_tree=0.40, dry=(0.16, 0.12, 0.03), dry_frac=0.06)
    leaf2('M_LeafLight', (0.060, 0.115, 0.020), (0.15, 0.22, 0.040), back=(0.16, 0.20, 0.09), back_mix=0.45, trans=0.35, rough=0.45,
          var_tree=0.35, dry=(0.20, 0.19, 0.05), dry_frac=0.08)
    leaf2('M_LeafPurple', (0.060, 0.016, 0.024), (0.17, 0.048, 0.055), back=(0.11, 0.05, 0.05), back_mix=0.4, trans=0.30, rough=0.4,
          var_tree=0.30)
    leaf2('M_LeafRed', (0.085, 0.014, 0.018), (0.18, 0.030, 0.030), back=(0.14, 0.05, 0.045), back_mix=0.4, trans=0.3, rough=0.42,
          var_tree=0.30)
    leaf2('M_LeafBox', (0.018, 0.042, 0.009), (0.050, 0.090, 0.018), back=(0.07, 0.09, 0.04), back_mix=0.4, trans=0.2, rough=0.35,
          spec=0.6, var_tree=0.25, dry=(0.10, 0.10, 0.03), dry_frac=0.05)
    leaf2('M_Lotus', (0.045, 0.092, 0.026), (0.100, 0.170, 0.050), back=(0.12, 0.15, 0.07), back_mix=0.6, trans=0.18, rough=0.55,
          spec=0.3, var_tree=0.30, dry=(0.14, 0.12, 0.04), dry_frac=0.06, sheen=0.25, sheen_tint=(0.8, 0.9, 0.85))
    leaf2('M_BankLeaf', (0.030, 0.075, 0.014), (0.085, 0.160, 0.030), back=(0.10, 0.14, 0.06), back_mix=0.45, trans=0.3, rough=0.4,
          var_tree=0.35, dry=(0.17, 0.15, 0.04), dry_frac=0.07)
    simple('M_LotusStalk', (0.06, 0.10, 0.03), rough=0.5)
    grass_blade()
    bark2('M_Bark', (0.040, 0.034, 0.028), (0.105, 0.090, 0.075), furrow=0.5, scale=7.0, stretch=3.0, moss=0.4)
    bark2('M_BarkWillow', (0.038, 0.034, 0.030), (0.12, 0.11, 0.095), furrow=0.8, scale=6.0, stretch=5.0, moss=0.5)
    bark2('M_Twig', (0.045, 0.040, 0.034), (0.10, 0.090, 0.075), furrow=0.3, scale=12.0, stretch=2.0, moss=0.0)
    terrain()
    mud_bed()
    granite('M_RedPaver', base=(0.19, 0.112, 0.098), dark=(0.10, 0.060, 0.052), light=(0.27, 0.17, 0.15), rough=0.72, scale=1.0)
    granite('M_StepStone', base=(0.10, 0.10, 0.095), dark=(0.055, 0.055, 0.052), light=(0.15, 0.15, 0.14), rough=0.6, scale=0.8)
    try:
        import xy_env_data as _ED
        fs = [(x, y, r * 0.35, r * 1.5, 'disc', 0.0) for (x, y, r) in _ED.FOUNTAINS[:1]]
        fs += [(x, y, 0.1, 0.55, 'ring', r) for (x, y, r) in _ED.FOUNTAINS[1:]]
    except ImportError:
        fs = []
    pond_water(fs)
    fountain_water()
    pink_stone()
    concrete_light()
    corten()
    boulder()
    foam()
    simple('M_Iron', (0.016, 0.016, 0.016), rough=0.45, spec=0.5, coat=0.3)
    simple('M_Mortar', (0.11, 0.108, 0.10), rough=0.9, spec=0.3)
    ff = simple('M_FoamFleck', (0.75, 0.78, 0.78), rough=0.3, spec=0.5)
    _nt = ff.node_tree
    _bs = next(n for n in _nt.nodes if n.type == 'BSDF_PRINCIPLED')
    _bs.inputs['Alpha'].default_value = 0.55
    granite('M_DarkGranite', base=(0.075, 0.075, 0.072), dark=(0.04, 0.04, 0.039), light=(0.12, 0.12, 0.115), rough=0.55, scale=1.0)
    simple('M_Steel', (0.62, 0.62, 0.62), rough=0.28, metal=1.0)
    lg = simple('M_LampGlass', (0.86, 0.85, 0.80), rough=0.5, spec=0.5)
    _bs = next(n for n in lg.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    _bs.inputs['Transmission Weight'].default_value = 0.6
    simple('M_TeakBench', (0.11, 0.055, 0.025), rough=0.6)
    return sorted(m.name for m in bpy.data.materials)
