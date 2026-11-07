# Qiting - materials. Procedural, physically based; colours are linear values chosen as natural daylight
# material colours (the photos are graded: hazy blue in W02, warm morning sun in 340d, blue dusk in 419).
# Builds on the Xingyuan node helpers in xy_mats.
import bpy
import xy_mats as XM
from xy_mats import _new, _n, _mix, _ramp, _noise, _coords, _world_pos, _rand, _bump, _math, _grime


def _attr(nt, name, loc=(-1200, 700)):
    a = nt.nodes.new('ShaderNodeAttribute'); a.location = loc
    a.attribute_type = 'GEOMETRY'; a.attribute_name = name
    return a


def _inst_rand(nt, loc=(-1200, 500)):
    """per-instance random (instancer) or per-object random, whichever applies."""
    oi = nt.nodes.new('ShaderNodeObjectInfo'); oi.location = loc
    return oi.outputs['Random']


def tile():
    """青瓦: grey fired clay. Medium grey (W01/W02 read lighter than the Xingyuan tiles), per-tile tone,
    lighter weathering on the upper surfaces, darker in the channels."""
    m, nt, bs, out = _new('M_Tile')
    L = nt.links
    rnd = _inst_rand(nt)
    pos = _world_pos(nt)
    nz = _noise(nt, pos, 1.6, 6, 0.55, (-900, -100))
    fine = _noise(nt, _coords(nt, 'Object', (-1200, -500)), 55.0, 3, 0.6, (-900, -450))
    base = _ramp(nt, rnd, [(0.0, (0.070, 0.072, 0.075)), (0.5, (0.098, 0.100, 0.103)), (1.0, (0.135, 0.135, 0.133))], (-450, 300))
    weather = _ramp(nt, nz.outputs['Fac'], [(0.35, (0.0, 0.0, 0.0)), (0.78, (1.0, 1.0, 1.0))], (-450, 0))
    col = _mix(nt, _math(nt, 'MULTIPLY', weather, 0.35, (-250, 100)), base, (0.16, 0.155, 0.145), (-100, 250))
    L.new(_grime(nt, col, ao_strength=0.35), bs.inputs['Base Color'])
    rr = _ramp(nt, fine.outputs['Fac'], [(0.3, (0.68, 0.68, 0.68)), (0.7, (0.86, 0.86, 0.86))], (-250, -200))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, fine.outputs['Fac'], 0.15, 0.003), bs.inputs['Normal'])
    bs.inputs['Specular IOR Level'].default_value = 0.35
    return m


def lacquer(name, base, rough=0.45, coat=0.12, wear=0.30):
    """朱红/赭红 lacquer on timber or concrete: semi-matte, faded on the weather side, darker in crevices."""
    m, nt, bs, out = _new(name)
    L = nt.links
    rnd = _inst_rand(nt)
    pos = _world_pos(nt)
    big = _noise(nt, pos, 0.9, 5, 0.6, (-900, 100))
    grain = _noise(nt, _coords(nt, 'Object', (-1200, -500)), 22.0, 6, 0.65, (-900, -350))
    b2 = tuple(c * 0.80 for c in base)
    b3 = (min(1, base[0] * 1.10), base[1] * 1.30, base[2] * 1.35)
    tone = _ramp(nt, big.outputs['Fac'], [(0.3, b2), (0.7, b3)], (-600, 100))
    col = _mix(nt, _math(nt, 'MULTIPLY', rnd, wear, (-600, 350)), tone, b2, (-300, 200))
    L.new(_grime(nt, col, ao_strength=0.22), bs.inputs['Base Color'])
    rr = _ramp(nt, grain.outputs['Fac'], [(0.3, (rough - 0.08,) * 3), (0.7, (rough + 0.12,) * 3)], (-300, -150))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, grain.outputs['Fac'], 0.05, 0.002), bs.inputs['Normal'])
    bs.inputs['Coat Weight'].default_value = coat
    bs.inputs['Coat Roughness'].default_value = 0.3
    return m


def plaster(name='M_Plaster', base=(0.58, 0.55, 0.47)):
    """白灰 bracket-band walls: warm off-white lime plaster, grey water stains running down (W01, af3b)."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    mp = _n(nt, 'ShaderNodeMapping', (-1000, -100)); mp.inputs['Scale'].default_value = (3.0, 3.0, 0.6)
    L.new(pos, mp.inputs['Vector'])
    streak = _noise(nt, mp.outputs[0], 2.5, 6, 0.62, (-800, -100))
    n1 = _noise(nt, pos, 1.3, 6, 0.55, (-900, 150))
    n2 = _noise(nt, pos, 45.0, 4, 0.6, (-900, -400))
    lo = tuple(c * 0.86 for c in base)
    col = _ramp(nt, n1.outputs['Fac'], [(0.25, lo), (0.65, base), (0.9, tuple(min(1, c * 1.05) for c in base))], (-500, 150))
    st = _ramp(nt, streak.outputs['Fac'], [(0.45, (1, 1, 1)), (0.75, (0.80, 0.80, 0.80))], (-500, -100))
    col2 = _mix(nt, 1.0, col, st, (-250, 50), blend='MULTIPLY')
    L.new(_grime(nt, col2, ao_strength=0.30), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.92
    L.new(_bump(nt, n2.outputs['Fac'], 0.07, 0.003), bs.inputs['Normal'])
    bs.inputs['Specular IOR Level'].default_value = 0.3
    return m


def marble(name='M_Marble', base=(0.60, 0.585, 0.54), rough=0.55, veins=0.94):
    """汉白玉-type white stone of the balustrades, coping and relief: warm white, faint grey veins, weathering
    grime collecting in crevices and on the underside of mouldings."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    rnd = _inst_rand(nt)
    n1 = _noise(nt, pos, 2.2, 8, 0.62, (-900, 150))
    w = _n(nt, 'ShaderNodeTexWave', (-900, -200)); w.inputs['Scale'].default_value = 1.6
    w.inputs['Distortion'].default_value = 10.0; w.inputs['Detail'].default_value = 3.0
    L.new(pos, w.inputs['Vector'])
    dirt = _noise(nt, pos, 0.5, 4, 0.6, (-900, -500))
    lo = tuple(c * 0.86 for c in base)
    c = _ramp(nt, n1.outputs['Fac'], [(0.3, lo), (0.7, base)], (-550, 150))
    v = _ramp(nt, w.outputs['Fac'], [(0.0, (veins, veins, veins - 0.01)), (0.08, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))], (-550, -200))
    var = _ramp(nt, rnd, [(0.0, (0.94, 0.94, 0.93)), (1.0, (1.03, 1.03, 1.02))], (-550, 400))
    d = _ramp(nt, dirt.outputs['Fac'], [(0.4, (1.0, 1.0, 1.0)), (0.75, (0.86, 0.85, 0.82))], (-550, -450))
    c2 = _mix(nt, 1.0, c, v, (-300, 0), blend='MULTIPLY')
    c3 = _mix(nt, 1.0, c2, var, (-150, 100), blend='MULTIPLY')
    c4 = _mix(nt, 1.0, c3, d, (0, 0), blend='MULTIPLY')
    L.new(_grime(nt, c4, ao_strength=0.40), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    L.new(_bump(nt, n1.outputs['Fac'], 0.10, 0.004), bs.inputs['Normal'])
    bs.inputs['Subsurface Weight'].default_value = 0.05
    bs.inputs['Subsurface Radius'].default_value = (0.02, 0.02, 0.02)
    return m


def granite(name, base, dark, light, rough=0.72, scale=1.0, slab_var=0.06):
    """花岗岩 ashlar / slabs: speckle, per-block tone (attribute 'slab' or instance random), stains."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    rnd = _inst_rand(nt)
    n1 = _noise(nt, pos, 240 * scale, 2, 0.5, (-900, 0))
    n2 = _noise(nt, pos, 0.7, 5, 0.6, (-900, -300))
    speck = _ramp(nt, n1.outputs['Fac'], [(0.36, dark), (0.42, base), (0.62, base), (0.68, light)], (-600, 100))
    stain = _ramp(nt, n2.outputs['Fac'], [(0.3, (0.84, 0.84, 0.84)), (0.7, (1.04, 1.04, 1.04))], (-600, -250))
    col = _mix(nt, 1.0, speck, stain, (-300, 0), blend='MULTIPLY')
    at = _attr(nt, 'slab', (-1200, 650))
    rmix = _math(nt, 'ADD', rnd, at.outputs['Fac'], (-800, 450))
    rfrac = _math(nt, 'FRACT', rmix, None, (-700, 450))
    var = _ramp(nt, rfrac, [(0.0, (1 - slab_var,) * 3), (0.5, (1.0, 1.0, 0.995)), (1.0, (1 + slab_var * 0.8,) * 3)], (-600, 400))
    col2 = _mix(nt, 1.0, col, var, (-100, 150), blend='MULTIPLY')
    L.new(_grime(nt, col2, ao_strength=0.32), bs.inputs['Base Color'])
    rr = _ramp(nt, n2.outputs['Fac'], [(0.3, (rough - 0.08,) * 3), (0.7, (rough + 0.08,) * 3)], (-300, -350))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, n1.outputs['Fac'], 0.08, 0.002), bs.inputs['Normal'])
    return m


def setts(name, base, var=0.10):
    """plaza paving bricks: split-face grey stone/concrete, rough top, each sett its own tone (419)."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    rnd = _inst_rand(nt)
    n1 = _noise(nt, pos, 60.0, 4, 0.6, (-900, 0))
    n2 = _noise(nt, pos, 0.35, 4, 0.55, (-900, -300))
    lo = tuple(c * (1 - var) for c in base)
    hi = tuple(c * (1 + var) for c in base)
    tone = _ramp(nt, rnd, [(0.0, lo), (0.5, base), (1.0, hi)], (-600, 300))
    sp = _ramp(nt, n1.outputs['Fac'], [(0.35, (0.80, 0.80, 0.80)), (0.65, (1.08, 1.08, 1.08))], (-600, 0))
    patch = _ramp(nt, n2.outputs['Fac'], [(0.35, (0.88, 0.88, 0.88)), (0.7, (1.05, 1.05, 1.04))], (-600, -300))
    c = _mix(nt, 1.0, tone, sp, (-300, 150), blend='MULTIPLY')
    c2 = _mix(nt, 1.0, c, patch, (-150, 0), blend='MULTIPLY')
    L.new(_grime(nt, c2, ao_strength=0.45), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.88
    L.new(_bump(nt, n1.outputs['Fac'], 0.35, 0.003), bs.inputs['Normal'])
    return m


def gold(name='M_Gold', base=(0.80, 0.55, 0.18), rough=0.28):
    """宝顶 gilding: gold leaf, slightly worn (rougher, browner patches)."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    n = _noise(nt, pos, 6.0, 5, 0.6, (-900, 0))
    c = _ramp(nt, n.outputs['Fac'], [(0.35, tuple(x * 0.82 for x in base)), (0.65, base)], (-500, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Metallic'].default_value = 1.0
    rr = _ramp(nt, n.outputs['Fac'], [(0.3, (rough - 0.08,) * 3), (0.7, (rough + 0.12,) * 3)], (-500, -250))
    L.new(rr, bs.inputs['Roughness'])
    L.new(_bump(nt, n.outputs['Fac'], 0.08, 0.002), bs.inputs['Normal'])
    return m


def ceiling_lotus():
    """藻井 painting (W08): red rosette with green ring, yellow petals outlined dark, salmon band with blue and
    yellow flower scrolls, white outer ring. Drawn procedurally in polar coordinates of the object."""
    m, nt, bs, out = _new('M_CeilingLotus')
    L = nt.links
    co = _coords(nt, 'Object', (-1700, 0))
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1500, 0)
    L.new(co, sep.inputs[0])
    r = _math(nt, 'SQRT', _math(nt, 'ADD', _math(nt, 'MULTIPLY', sep.outputs['X'], sep.outputs['X'], (-1350, 100)),
                                     _math(nt, 'MULTIPLY', sep.outputs['Y'], sep.outputs['Y'], (-1350, -50)), (-1250, 0)), None, (-1150, 0))
    ang = _math(nt, 'ARCTAN2', sep.outputs['Y'], sep.outputs['X'], (-1250, -250))
    # 16 petals: cos(16 * angle)
    pet = _math(nt, 'COSINE', _math(nt, 'MULTIPLY', ang, 16.0, (-1100, -250)), None, (-1000, -250))
    petal_r = _math(nt, 'MULTIPLY_ADD', pet, 0.10, (-850, -250)); nt.nodes[-1].inputs[2].default_value = 0.92
    # radial zones (object radius normalised to the dome radius 2.7 m)
    rn = _math(nt, 'DIVIDE', r, 2.70, (-1000, 0))
    zone_petal = _math(nt, 'LESS_THAN', rn, _math(nt, 'MULTIPLY', petal_r, 0.62, (-750, -200)), (-650, -100))
    zone_core = _math(nt, 'LESS_THAN', rn, 0.20, (-650, 100))
    zone_ring = _math(nt, 'LESS_THAN', rn, 0.28, (-650, 250))
    zone_band = _math(nt, 'LESS_THAN', rn, 0.90, (-650, -350))
    flowers = _noise(nt, co, 9.0, 3, 0.5, (-900, -600))
    fl = _ramp(nt, flowers.outputs['Fac'], [(0.0, (0.55, 0.16, 0.10)), (0.52, (0.55, 0.16, 0.10)), (0.56, (0.06, 0.16, 0.42)),
                                             (0.62, (0.06, 0.16, 0.42)), (0.66, (0.65, 0.48, 0.06)), (1.0, (0.65, 0.48, 0.06))], (-650, -600))
    c = _mix(nt, zone_band, (0.72, 0.70, 0.64), fl, (-400, -400))
    c = _mix(nt, zone_petal, c, (0.70, 0.46, 0.04), (-300, -200))
    edge = _math(nt, 'LESS_THAN', _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', rn, _math(nt, 'MULTIPLY', petal_r, 0.62, (-750, -400)),
                                                                 (-600, -500)), None, (-500, -500)), 0.012, (-400, -550))
    c = _mix(nt, edge, c, (0.03, 0.03, 0.05), (-200, -300))
    c = _mix(nt, zone_ring, c, (0.06, 0.25, 0.05), (-100, 0))
    c = _mix(nt, zone_core, c, (0.50, 0.03, 0.02), (0, 100))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.7
    return m


def painted_band():
    """soffit / beam painting inside (W08): salmon ground with dark-outlined floral scrolls."""
    m, nt, bs, out = _new('M_PaintedPanel')
    L = nt.links
    co = _coords(nt, 'Object', (-1200, 0))
    n = _noise(nt, co, 7.0, 4, 0.55, (-900, 0))
    c = _ramp(nt, n.outputs['Fac'], [(0.0, (0.55, 0.20, 0.12)), (0.48, (0.55, 0.20, 0.12)), (0.52, (0.04, 0.12, 0.30)),
                                     (0.58, (0.04, 0.12, 0.30)), (0.62, (0.62, 0.45, 0.07)), (0.70, (0.08, 0.30, 0.10)), (1.0, (0.55, 0.20, 0.12))], (-500, 0))
    L.new(c, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.72
    return m


def ashlar(name='M_Ashlar', base=(0.30, 0.295, 0.28), course=0.3085, block=0.92, z0=-4.60):
    """granite ashlar of the terraces and the stair walls (W02, 419): blocks ~0.9 x 0.31 m in running bond
    (UV u = arc length / run, v = z), fine joints, each block its own tone, speckle and stains."""
    m, nt, bs, out = _new(name)
    L = nt.links
    uv = _coords(nt, 'UV', (-1700, 0))
    mp = _n(nt, 'ShaderNodeMapping', (-1500, 0))
    mp.inputs['Location'].default_value = (0.0, -z0, 0.0)
    L.new(uv, mp.inputs['Vector'])
    br = _n(nt, 'ShaderNodeTexBrick', (-1200, 0))
    br.offset = 0.5; br.offset_frequency = 2; br.squash = 1.0; br.squash_frequency = 2
    L.new(mp.outputs[0], br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.007
    br.inputs['Mortar Smooth'].default_value = 0.2
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Brick Width'].default_value = block
    br.inputs['Row Height'].default_value = course
    br.inputs['Color1'].default_value = (0.92, 0.92, 0.92, 1)
    br.inputs['Color2'].default_value = (1.06, 1.06, 1.05, 1)
    br.inputs['Mortar'].default_value = (0.55, 0.55, 0.53, 1)
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 240.0, 2, 0.5, (-900, -300))
    n2 = _noise(nt, pos, 0.8, 5, 0.6, (-900, -600))
    dark = tuple(c * 0.5 for c in base)
    light = tuple(min(1, c * 1.35) for c in base)
    speck = _ramp(nt, n1.outputs['Fac'], [(0.36, dark), (0.42, base), (0.62, base), (0.68, light)], (-600, -300))
    stain = _ramp(nt, n2.outputs['Fac'], [(0.3, (0.82, 0.82, 0.82)), (0.7, (1.04, 1.04, 1.04))], (-600, -600))
    c1 = _mix(nt, 1.0, speck, br.outputs['Color'], (-300, -100), blend='MULTIPLY')
    c2 = _mix(nt, 1.0, c1, stain, (-150, -300), blend='MULTIPLY')
    L.new(_grime(nt, c2, ao_strength=0.32), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.74
    h = _math(nt, 'ADD', _math(nt, 'MULTIPLY', br.outputs['Fac'], -1.0, (-300, -800)), 1.0, (-200, -800))
    h2 = _math(nt, 'ADD', h, _math(nt, 'MULTIPLY', n1.outputs['Fac'], 0.08, (-400, -900)), (-100, -850))
    L.new(_bump(nt, h2, 0.6, 0.006), bs.inputs['Normal'])
    return m


def build_all():
    tile()
    lacquer('M_Red', (0.26, 0.026, 0.020), rough=0.45)          # columns, beams (W01/W02 red)
    lacquer('M_RedDark', (0.15, 0.022, 0.016), rough=0.55, coat=0.05)   # brackets, rafters, soffit (darker oxblood)
    lacquer('M_RafterEnd', (0.30, 0.040, 0.026), rough=0.5, coat=0.05)  # rafter end faces (lighter red squares, W01)
    plaster('M_Plaster', (0.58, 0.55, 0.47))
    plaster('M_PlasterIn', (0.62, 0.60, 0.55))
    XM.simple('M_WindowPanel', (0.66, 0.64, 0.58), rough=0.85)     # white window panels of the upper drum
    marble('M_Marble', (0.54, 0.485, 0.37))           # warm cream white (340d sun, W01 overcast)
    marble('M_MarbleRelief', (0.52, 0.465, 0.355), rough=0.62, veins=0.975)
    ashlar('M_Ashlar')
    ashlar('M_TerraceTop', base=(0.085, 0.085, 0.082), course=0.6, block=0.6, z0=0.0)   # dark granite slabs (A1/A2)
    XM.simple('M_LampGlass', (0.78, 0.77, 0.72), rough=0.2)
    granite('M_GraniteLight', base=(0.30, 0.295, 0.28), dark=(0.15, 0.15, 0.145), light=(0.42, 0.415, 0.40))
    granite('M_GraniteStep', base=(0.20, 0.20, 0.195), dark=(0.10, 0.10, 0.10), light=(0.30, 0.30, 0.29), rough=0.78)
    granite('M_GraniteFloor', base=(0.24, 0.24, 0.232), dark=(0.12, 0.12, 0.118), light=(0.33, 0.33, 0.32), rough=0.75)
    setts('M_Setts', (0.235, 0.215, 0.190), var=0.08)   # light beige-grey setts (A1/A2 daylight; 419 was dark at dusk)
    setts('M_SettsLight', (0.17, 0.168, 0.16), var=0.08)
    gold('M_Gold')
    gold('M_GoldPaint', base=(0.66, 0.44, 0.12), rough=0.42)
    XM.simple('M_BlackLacquer', (0.012, 0.012, 0.013), rough=0.62)
    XM.simple('M_Dark', (0.010, 0.010, 0.011), rough=0.9)          # openings / voids
    XM.simple('M_DoorMetal', (0.045, 0.045, 0.048), rough=0.5, metal=0.6)
    XM.simple('M_Rod', (0.30, 0.25, 0.14), rough=0.35, metal=1.0)
    ceiling_lotus()
    painted_band()
    XM.simple('M_Ground', (0.075, 0.072, 0.060), rough=0.95)      # neutral staging ground (not part of the replica)
    return sorted(m.name for m in bpy.data.materials)


# ------------------------------------------------------------------ round 2: the surroundings
def pavers(name, base, block=(0.30, 0.15), var=0.10, joint=(0.30, 0.30, 0.28), rough=0.82, speck=0.6):
    """small pavers in running bond (UV u along the path, v across), per-block tone, stains."""
    m, nt, bs, out = _new(name)
    L = nt.links
    uv = _coords(nt, 'UV', (-1700, 0))
    br = _n(nt, 'ShaderNodeTexBrick', (-1200, 0))
    br.offset = 0.5; br.offset_frequency = 2; br.squash = 1.0; br.squash_frequency = 2
    L.new(uv, br.inputs['Vector'])
    br.inputs['Scale'].default_value = 1.0
    br.inputs['Mortar Size'].default_value = 0.006
    br.inputs['Mortar Smooth'].default_value = 0.25
    br.inputs['Brick Width'].default_value = block[0]
    br.inputs['Row Height'].default_value = block[1]
    lo = tuple(c * (1 - var) for c in base); hi = tuple(min(1, c * (1 + var)) for c in base)
    br.inputs['Color1'].default_value = lo + (1,)
    br.inputs['Color2'].default_value = hi + (1,)
    br.inputs['Mortar'].default_value = joint + (1,)
    pos = _world_pos(nt)
    n1 = _noise(nt, pos, 0.45, 4, 0.55, (-900, -300))
    n2 = _noise(nt, pos, 90.0, 2, 0.5, (-900, -600))
    st = _ramp(nt, n1.outputs['Fac'], [(0.3, (0.86, 0.86, 0.86)), (0.7, (1.06, 1.06, 1.05))], (-600, -300))
    sp = _ramp(nt, n2.outputs['Fac'], [(0.35, (1 - 0.12 * speck,) * 3), (0.65, (1 + 0.08 * speck,) * 3)], (-600, -600))
    c = _mix(nt, 1.0, br.outputs['Color'], st, (-300, 0), blend='MULTIPLY')
    c = _mix(nt, 1.0, c, sp, (-150, -100), blend='MULTIPLY')
    L.new(_grime(nt, c, ao_strength=0.3), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    h = _math(nt, 'ADD', _math(nt, 'MULTIPLY', br.outputs['Fac'], -1.0, (-300, -800)), 1.0, (-200, -800))
    L.new(_bump(nt, h, 0.5, 0.004), bs.inputs['Normal'])
    return m


def lake_water(name='M_Lake', deep=(0.032, 0.050, 0.043), rough=0.12):
    """large lake (A1/A2: grey-green, calm): opaque dark water body colour with Fresnel reflections and soft
    wind ripples; no transmission (the bed is far below)."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    mp = _n(nt, 'ShaderNodeMapping', (-1000, -300)); mp.inputs['Scale'].default_value = (1.0, 2.5, 1.0)
    L.new(pos, mp.inputs['Vector'])
    n = _noise(nt, mp.outputs[0], 0.35, 4, 0.55, (-700, -200))
    n2 = _noise(nt, pos, 2.8, 3, 0.5, (-700, -500))
    n3 = _noise(nt, pos, 0.02, 2, 0.5, (-700, 200))
    h = _math(nt, 'ADD', n.outputs['Fac'], _math(nt, 'MULTIPLY', n2.outputs['Fac'], 0.25, (-500, -500)), (-400, -300))
    col = _ramp(nt, n3.outputs['Fac'], [(0.3, deep), (0.7, tuple(c * 1.25 for c in deep))], (-400, 200))
    L.new(col, bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['IOR'].default_value = 1.333
    bs.inputs['Specular IOR Level'].default_value = 0.5
    L.new(_bump(nt, h, 0.10, 0.04), bs.inputs['Normal'])
    return m


def hedge(name='M_Hedge'):
    """clipped evergreen hedge (A1/A2): small-leaved, dense; leaf clusters from Voronoi cells, deep bump, darker in
    the crevices, sun-lit tips lighter."""
    m, nt, bs, out = _new(name)
    L = nt.links
    pos = _world_pos(nt)
    v = _n(nt, 'ShaderNodeTexVoronoi', (-1000, 0)); v.inputs['Scale'].default_value = 22.0
    L.new(pos, v.inputs['Vector'])
    v2 = _n(nt, 'ShaderNodeTexVoronoi', (-1000, -300)); v2.inputs['Scale'].default_value = 70.0
    L.new(pos, v2.inputs['Vector'])
    n = _noise(nt, pos, 1.2, 4, 0.6, (-1000, 300))
    c = _ramp(nt, v.outputs['Distance'], [(0.0, (0.050, 0.095, 0.022)), (0.45, (0.030, 0.062, 0.015)), (0.8, (0.012, 0.026, 0.007))], (-600, 0))
    c = _mix(nt, 1.0, c, _ramp(nt, n.outputs['Fac'], [(0.3, (0.85, 0.85, 0.85)), (0.7, (1.12, 1.15, 1.05))], (-600, 300)), (-300, 100), blend='MULTIPLY')
    L.new(_grime(nt, c, ao_strength=0.5), bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.6
    hgt = _math(nt, 'ADD', _math(nt, 'MULTIPLY', v.outputs['Distance'], -1.0, (-600, -400)), _math(nt, 'MULTIPLY', v2.outputs['Distance'], -0.4, (-600, -550)), (-400, -450))
    L.new(_bump(nt, hgt, 0.9, 0.05), bs.inputs['Normal'])
    bs.inputs['Subsurface Weight'].default_value = 0.05
    return m


def terrain_lawn():
    """ground cover: like xy_mats.terrain, with the lawn tuned to the aerials (fresh mown green, mowing stripes
    faint), forest floor of needles and soil under the cedars, bank of low planting."""
    import xy_mats as XM
    m = XM.terrain()
    nt = m.node_tree
    ramps = [n for n in nt.nodes if n.type == 'VALTORGB']
    lawn = ramps[0].color_ramp
    for e, c in zip(lawn.elements, ((0.092, 0.180, 0.026), (0.122, 0.222, 0.032), (0.152, 0.240, 0.042))):
        e.color = c + (1,)
    return m


def build_env():
    terrain_lawn()
    pavers('M_PathPavers', (0.20, 0.195, 0.18), block=(0.30, 0.15))
    pavers('M_PinkPavers', (0.30, 0.165, 0.135), block=(0.24, 0.12), var=0.12, joint=(0.22, 0.17, 0.15))
    pavers('M_WalkSlabs', (0.27, 0.235, 0.215), block=(0.60, 0.60), var=0.08)
    granite('M_Kerb', base=(0.36, 0.35, 0.33), dark=(0.18, 0.18, 0.17), light=(0.48, 0.47, 0.45), rough=0.7)
    granite('M_Revetment', base=(0.15, 0.15, 0.14), dark=(0.07, 0.07, 0.065), light=(0.22, 0.22, 0.21), rough=0.8)
    granite('M_DarkGranite', base=(0.075, 0.075, 0.072), dark=(0.04, 0.04, 0.039), light=(0.12, 0.12, 0.115), rough=0.55)
    granite('M_StoneTable', base=(0.30, 0.29, 0.27), dark=(0.16, 0.16, 0.15), light=(0.42, 0.41, 0.39), rough=0.65)
    granite('M_EggStone', base=(0.42, 0.40, 0.36), dark=(0.22, 0.21, 0.19), light=(0.55, 0.53, 0.49), rough=0.5, scale=0.5)
    lake_water()
    hedge()
    XM.simple('M_Iron', (0.016, 0.016, 0.016), rough=0.45, spec=0.5, coat=0.3)
    XM.simple('M_LampPost', (0.030, 0.032, 0.034), rough=0.45, metal=0.5)
    XM.simple('M_PostWhite', (0.62, 0.61, 0.58), rough=0.45)
    XM.simple('M_LanternRed', (0.42, 0.03, 0.02), rough=0.6, spec=0.3)
    XM.simple('M_LampGlow', (0.80, 0.78, 0.72), rough=0.35, emit=(1.0, 0.85, 0.62), emit_strength=0.0)
    XM.simple('M_Bronze', (0.10, 0.07, 0.04), rough=0.4, metal=0.85)
    XM.simple('M_SignBoard', (0.05, 0.035, 0.022), rough=0.6)
    return sorted(m.name for m in bpy.data.materials)
