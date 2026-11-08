"""The guardian robot: parts built with bmesh in joint-local space, parented to empties (the rig)."""
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler
import aw_core as C, aw_shade as S, aw_mesh as M

# palette (linear-ish sRGB values typed as display colours; Standard view transform)
PAINT = (0.40, 0.50, 0.46)      # faded teal-sage paint
PAINT2 = (0.33, 0.42, 0.40)     # secondary darker plates
BRONZE = (0.30, 0.22, 0.15)     # joints
DARK = (0.10, 0.085, 0.08)      # recesses
RUST = (0.46, 0.25, 0.13)
MOSS = (0.33, 0.43, 0.16)
MOSS_LIGHT = (0.47, 0.55, 0.20)
METAL = (0.24, 0.23, 0.22)

# joint offsets (standing pose, metres); the robot faces -Y
HIP_Z = 9.1
J = {
    'hip': (0, 0, HIP_Z),
    'torso': (0, 0, 0.7),
    'neck': (0, -0.15, 5.45),
    'shoulder.L': (-2.55, 0.1, 4.75), 'shoulder.R': (2.55, 0.1, 4.75),
    'elbow': (0, 0, -3.4), 'wrist': (0, 0, -3.6),
    'thigh.L': (-1.4, 0, -0.45), 'thigh.R': (1.4, 0, -0.45),
    'knee': (0, 0, -4.0), 'ankle': (0, 0, -3.8),
}
FOOT_H = 0.85

def materials():
    mats = {}
    paint = S.cel_material('RB_Paint', PAINT, spec=0.35, rim=0.3)
    weathered_paint(paint, PAINT, rust_th=0.66)
    mats['paint'] = paint
    paint2 = S.cel_material('RB_Paint2', PAINT2, spec=0.3, rim=0.3)
    weathered_paint(paint2, PAINT2, rust_th=0.62)
    mats['paint2'] = paint2
    mats['bronze'] = S.cel_material('RB_Bronze', BRONZE, spec=0.5, line=(0.05, 0.03, 0.025, 1), rim=0.3)
    weathered_paint(mats['bronze'], BRONZE, rust_th=0.60, moss=True, moss_th=0.65)
    mats['dark'] = S.cel_material('RB_Dark', DARK, line=(0.03, 0.02, 0.02, 1))
    mats['rust'] = S.cel_material('RB_Rust', RUST)
    mats['moss'] = S.cel_material('RB_Moss', MOSS, line=(0.10, 0.12, 0.05, 1), rim=0.25)
    mats['eye'] = glow_material('RB_Eye', (1.0, 0.72, 0.25), (0.06, 0.05, 0.05))
    mats['core'] = glow_material('RB_Core', (1.0, 0.80, 0.45), (0.05, 0.045, 0.04))
    return mats

def glow_material(name, glow, off):
    """Emissive lamp: colour = off colour + Strength * glow; 'Glow' value node is keyframed."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    val = nt.nodes.new('ShaderNodeValue'); val.name = 'Glow'; val.label = 'Glow'; val.outputs[0].default_value = 0.0
    col = nt.nodes.new('ShaderNodeRGB'); col.outputs[0].default_value = (*glow, 1)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
    nt.links.new(col.outputs[0], mul.inputs[6])
    # scale colour by glow strength
    sc = nt.nodes.new('ShaderNodeMix'); sc.data_type = 'RGBA'; sc.blend_type = 'MIX'
    sc.inputs[6].default_value = (*off, 1)
    nt.links.new(col.outputs[0], sc.inputs[7]); nt.links.new(val.outputs[0], sc.inputs['Factor'])
    em = nt.nodes.new('ShaderNodeEmission')
    nt.links.new(sc.outputs[2], em.inputs['Color'])
    st = nt.nodes.new('ShaderNodeMath'); st.operation = 'MULTIPLY_ADD'
    nt.links.new(val.outputs[0], st.inputs[0]); st.inputs[1].default_value = 6.0; st.inputs[2].default_value = 1.0
    nt.links.new(st.outputs[0], em.inputs['Strength'])
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(em.outputs[0], out.inputs[0])
    mat.line_color = (0.05, 0.03, 0.02, 1)
    return mat

def set_glow(name, value, frame=None):
    mat = bpy.data.materials[name]
    n = mat.node_tree.nodes['Glow']
    n.outputs[0].default_value = value
    if frame is not None:
        n.outputs[0].keyframe_insert('default_value', frame=frame)

def weathered_paint(mat, base, rust_th=0.66, moss=True, chips=False, moss_th=0.50):
    """Procedural weathering feeding the cel group's Base Color.
    Orientation comes from the baked colour attribute 'weather' (R = upness while kneeling, G = height while
    kneeling), see bake_weather(), so moss sits where it grew during the long sleep, whatever the pose now."""
    nt = mat.node_tree
    grp = S.group_node(mat)
    n = nt.nodes
    tc = n.new('ShaderNodeTexCoord'); tc.location = (-1600, 0)
    wa = n.new('ShaderNodeAttribute'); wa.attribute_type = 'GEOMETRY'; wa.attribute_name = 'weather'; wa.location = (-1600, -500)
    sep = n.new('ShaderNodeSeparateColor'); sep.location = (-1400, -500)
    nt.links.new(wa.outputs['Color'], sep.inputs[0])
    upn = n.new('ShaderNodeMath'); upn.operation = 'MULTIPLY_ADD'; upn.location = (-1200, -500)
    nt.links.new(sep.outputs[0], upn.inputs[0]); upn.inputs[1].default_value = 2.0; upn.inputs[2].default_value = -1.0
    upness = upn.outputs[0]
    basec = n.new('ShaderNodeRGB'); basec.outputs[0].default_value = (*base, 1); basec.location = (-1000, 300)
    cur = basec.outputs[0]
    def noise(scale, detail=3.0, rough=0.5, loc=(0, 0), coords=None, distort=0.0):
        nz = n.new('ShaderNodeTexNoise'); nz.location = loc
        nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = detail
        nz.inputs['Roughness'].default_value = rough; nz.inputs['Distortion'].default_value = distort
        nt.links.new(coords or tc.outputs['Object'], nz.inputs['Vector'])
        return nz.outputs['Fac']
    def math(op, a, b, loc, clamp=False):
        m = n.new('ShaderNodeMath'); m.operation = op; m.location = loc; m.use_clamp = clamp
        if isinstance(a, (int, float)): m.inputs[0].default_value = a
        else: nt.links.new(a, m.inputs[0])
        if isinstance(b, (int, float)): m.inputs[1].default_value = b
        else: nt.links.new(b, m.inputs[1])
        return m.outputs[0]
    def mixc(fac, a, col, loc):
        mx = n.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.location = loc
        nt.links.new(fac, mx.inputs['Factor']); nt.links.new(a, mx.inputs[6]); mx.inputs[7].default_value = (*col, 1)
        return mx.outputs[2]
    # rust: large patches, more on the downward / sheltered sides (low upness)
    rn = noise(0.22, 3, 0.55, (-1000, 0), distort=0.5)
    bias = math('MULTIPLY', upness, 0.12, (-1000, -150))
    rv = math('SUBTRACT', rn, bias, (-800, 0))
    rmask = math('GREATER_THAN', rv, rust_th, (-650, 0))
    cur = mixc(rmask, cur, RUST, (-500, 200))
    rmask2 = math('GREATER_THAN', rv, rust_th + 0.08, (-650, -100))
    cur = mixc(rmask2, cur, (0.36, 0.17, 0.09), (-350, 150))
    if chips:
        cmask = math('GREATER_THAN', noise(2.4, 2, 0.6, (-1000, -600)), 0.78, (-800, -600))
        cur = mixc(cmask, cur, METAL, (-300, 100))
    if moss:
        mn = noise(0.45, 3, 0.6, (-1000, -900), distort=0.7)
        edge = math('MULTIPLY_ADD', mn, 0.7, (-800, -900))
        m2 = n.new('ShaderNodeMath'); m2.operation = 'ADD'; m2.location = (-650, -900)
        nt.links.new(upness, m2.inputs[0]); nt.links.new(edge, m2.inputs[1])
        mmask = math('GREATER_THAN', m2.outputs[0], 0.55 + moss_th, (-500, -900))
        cur = mixc(mmask, cur, MOSS, (-150, 50))
        mmask2 = math('GREATER_THAN', m2.outputs[0], 0.78 + moss_th, (-500, -1050))
        cur = mixc(mmask2, cur, MOSS_LIGHT, (0, 20))
    nt.links.new(cur, grp.inputs['Base Color'])

def bake_weather(coll_name='Robot', zmax=13.0):
    """Store per face corner: R = upness of the surface normal in the current (kneeling) pose, G = height / zmax.
    Flat faces use the face normal; smooth faces average only the neighbouring smooth faces within 60 degrees,
    so cylinder caps do not leak into the sides."""
    C.view_update()
    for ob in bpy.data.collections[coll_name].objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        if 'weather' in me.color_attributes:
            me.color_attributes.remove(me.color_attributes['weather'])
        attr = me.color_attributes.new('weather', 'FLOAT_COLOR', 'CORNER')
        mw = ob.matrix_world
        rot = mw.to_3x3()
        vfaces = [[] for _ in me.vertices]
        for p in me.polygons:
            for vi in p.vertices:
                vfaces[vi].append(p)
        for p in me.polygons:
            pn = p.normal
            for li in p.loop_indices:
                vi = me.loops[li].vertex_index
                if p.use_smooth:
                    acc = Vector((0, 0, 0))
                    for q in vfaces[vi]:
                        if q.use_smooth and q.normal.dot(pn) > 0.5:
                            acc += q.normal
                    n = acc.normalized() if acc.length > 1e-6 else pn
                else:
                    n = pn
                nw = (rot @ n).normalized()
                z = (mw @ me.vertices[vi].co).z
                attr.data[li].color = (0.5 + 0.5 * nw.z, max(0.0, min(1.0, z / zmax)), 0.0, 1.0)

# ---------------------------------------------------------------- rig
def rig(coll):
    E = {}
    def mk(name, loc, parent=None):
        e = C.empty('J_' + name, loc, parent, coll, size=0.6)
        E[name] = e
        return e
    root = mk('root', (0, 0, 0))
    hip = mk('hip', J['hip'], root)
    torso = mk('torso', J['torso'], hip)
    neck = mk('neck', J['neck'], torso)
    for side in ('L', 'R'):
        sh = mk('shoulder.' + side, J['shoulder.' + side], torso)
        el = mk('elbow.' + side, J['elbow'], sh)
        wr = mk('wrist.' + side, J['wrist'], el)
        th = mk('thigh.' + side, J['thigh.' + side], hip)
        kn = mk('knee.' + side, J['knee'], th)
        an = mk('ankle.' + side, J['ankle'], kn)
    return E

# ---------------------------------------------------------------- parts
def build_head(E, mats, coll):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['eye'], mats['paint2']]
    P, B, D, EYE, P2 = 0, 1, 2, 3, 4
    M.cyl(bm, 0.55, 0.48, 0.9, (0, 0, 0.3), B, segs=18)                       # neck
    M.sphere(bm, 1.35, (0, 0.05, 1.6), P, scale=(1.0, 1.05, 0.9), segs=32, rings=16, cut_below=-0.45)   # skull
    # brow visor: a thick curved hood over the eyes
    v, f = M.cyl(bm, 1.42, 1.5, 0.42, (0, -0.1, 1.45), P2, segs=32)
    M.box(bm, (2.2, 0.9, 0.3), (0, -1.0, 1.42), P2, taper=0.75)                # visor lip
    # dark eye sockets and lamps
    M.cyl(bm, 1.28, 1.28, 0.52, (0, -0.1, 1.0), D, segs=32)
    for sx in (-1, 1):
        M.torus(bm, 0.33, 0.07, (sx * 0.55, -1.22, 1.0), B, rot=(90, 0, 0), segs=20, rsegs=8)
        M.sphere(bm, 0.3, (sx * 0.55, -1.2, 1.0), EYE, scale=(1.0, 0.45, 1.0), segs=16, rings=8)
    # cheek guards and mouth grille
    for sx in (-1, 1):
        M.box(bm, (0.5, 0.9, 0.9), (sx * 0.95, -0.55, 0.45), P, rot=(0, 0, sx * 18), taper=1.1, bev=0.05)
    M.box(bm, (1.0, 0.5, 0.55), (0, -1.0, 0.4), D)
    for k in range(4):
        M.box(bm, (0.08, 0.16, 0.5), (-0.36 + 0.24 * k, -1.2, 0.4), B)
    M.box(bm, (1.5, 0.8, 0.3), (0, -0.65, 0.05), B, taper=1.2)                 # chin plate
    for sx in (-1, 1):
        M.cyl(bm, 0.45, 0.45, 0.5, (sx * 1.38, 0.1, 1.25), B, rot=(0, 90, 0), segs=16)   # ear discs
    M.cyl(bm, 0.07, 0.04, 1.3, (1.5, 0.1, 1.9), B, rot=(0, 18, 0), segs=8)    # one antenna (the other broke off long ago)
    M.sphere(bm, 0.12, (1.68, 0.1, 2.5), B, segs=10, rings=6)
    M.box(bm, (0.12, 1.3, 0.8), (0, 0.4, 2.65), P2, taper=0.25)                # crest fin
    return M.finish(bm, 'RB_head', ml, coll, parent=E['neck'])

def build_torso(E, mats, coll):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['core'], mats['paint2'], mats['rust']]
    P, B, D, CORE, P2, R = 0, 1, 2, 3, 4, 5
    M.cyl(bm, 1.45, 1.6, 0.75, (0, 0, 0.38), B, segs=24)                      # abdomen rings
    M.cyl(bm, 1.7, 1.85, 0.75, (0, 0, 1.12), D, segs=24)
    # barrel chest
    v, f = M.sphere(bm, 2.35, (0, 0.1, 3.4), P, scale=(1.08, 0.78, 0.95), segs=40, rings=20, cut_below=-0.78)
    M.groove(bm, (v, f), (0, 0, 2.55), (0, 0, 1))
    M.groove(bm, (v, f), (0, 0, 4.35), (0, 0, 1))
    # shoulder yoke across the top
    M.cyl(bm, 1.15, 1.15, 5.4, (0, 0.25, 4.85), P2, rot=(0, 90, 0), segs=28)
    M.cyl(bm, 0.85, 0.85, 0.6, (0, -0.1, 5.75), B, segs=24)                   # collar ring
    # chest hatch and core window
    M.cyl(bm, 1.1, 1.1, 0.35, (0, -1.72, 3.3), B, rot=(90, 0, 0), segs=32)
    M.cyl(bm, 0.86, 0.86, 0.12, (0, -1.96, 3.3), D, rot=(90, 0, 0), segs=32)
    M.cyl(bm, 0.52, 0.52, 0.12, (0, -2.0, 3.3), CORE, rot=(90, 0, 0), segs=24)
    M.torus(bm, 0.52, 0.06, (0, -2.05, 3.3), B, rot=(90, 0, 0), segs=28, rsegs=8)    # lens ring
    for k in range(4):                                                                   # lens bars
        M.box(bm, (0.08, 0.08, 1.05), (0, -2.08, 3.3), B, rot=(0, 45 + 90 * k, 0))
    for k in range(8):                                                                   # hatch bolts
        a = math.radians(k * 45 + 22.5)
        M.sphere(bm, 0.1, (math.cos(a) * 0.98, -1.92, 3.3 + math.sin(a) * 0.98), B, segs=10, rings=6)
    # shoulder balls
    for sx in (-1, 1):
        M.sphere(bm, 0.95, (sx * 2.55, 0.1, 4.75), B, segs=24, rings=12)
    # backpack and bell engines
    M.box(bm, (3.4, 1.3, 2.8), (0, 1.9, 3.4), P2, taper=0.9, bev=0.12)
    for sx in (-1, 1):
        M.cyl(bm, 0.78, 0.9, 2.9, (sx * 1.5, 2.3, 3.3), P, rot=(10, 0, 0), segs=24)
        M.cyl(bm, 0.9, 1.15, 0.9, (sx * 1.5, 2.62, 1.45), B, rot=(10, 0, 0), segs=24)
        M.cyl(bm, 1.05, 1.05, 0.1, (sx * 1.5, 2.7, 0.98), D, rot=(10, 0, 0), segs=24)
    for k in range(3):
        M.box(bm, (1.8, 0.25, 0.2), (0, 2.6, 4.4 - 0.5 * k), D)
    M.cyl(bm, 0.55, 0.55, 0.14, (1.45, -1.78, 2.2), R, rot=(90, 0, 0), segs=7)   # old rusted patch plate
    return M.finish(bm, 'RB_torso', ml, coll, parent=E['torso'])

def build_pelvis(E, mats, coll):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    M.sphere(bm, 1.9, (0, 0, 0.0), P2, scale=(1.0, 0.68, 0.55), segs=32, rings=16)   # hip saddle
    M.box(bm, (1.4, 0.7, 1.1), (0, -1.15, -0.25), P, taper=0.9, bev=0.08)        # front plate
    for sx in (-1, 1):
        M.sphere(bm, 0.9, (sx * 1.4, 0, -0.45), B, segs=24, rings=12)
    return M.finish(bm, 'RB_pelvis', ml, coll, parent=E['hip'])

def build_pauldron(E, mats, coll, side):
    sx = -1 if side == 'L' else 1
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    v, f = M.sphere(bm, 1.75, (sx * 0.5, 0, 0.5), P, scale=(1.0, 1.1, 0.75), segs=36, rings=18, cut_below=-0.12)
    M.groove(bm, (v, f), (sx * 0.5, -0.55, 0), (0, 1, 0))
    M.torus(bm, 1.75, 0.13, (sx * 0.5, 0, 0.3), B, segs=36, rsegs=8)
    M.sphere(bm, 0.35, (sx * 1.0, 0, 1.55), B, segs=16, rings=8)              # rivet cap
    return M.finish(bm, 'RB_pauldron.' + side, ml, coll, parent=E['shoulder.' + side])

def build_upperarm(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark']]
    P, B, D = 0, 1, 2
    M.cyl(bm, 0.72, 0.62, 3.1, (0, 0, -1.6), P, segs=24)
    M.cyl(bm, 0.8, 0.8, 0.35, (0, 0, -0.5), B, segs=24)                       # upper cuff
    M.sphere(bm, 0.7, (0, 0, -3.4), B, segs=20, rings=10)                     # elbow
    return M.finish(bm, 'RB_upperarm.' + side, ml, coll, parent=E['shoulder.' + side])

def build_forearm(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    v, f = M.cyl(bm, 0.66, 1.0, 3.2, (0, 0, -1.85), P, segs=24)               # gauntlet widening to the wrist
    M.groove(bm, (v, f), (0, 0, -2.7), (0, 0, 1))
    M.cyl(bm, 1.08, 1.08, 0.4, (0, 0, -3.35), B, segs=24)                     # cuff ring
    M.box(bm, (0.9, 0.3, 1.5), (0, -0.78, -1.5), P2, taper=1.25, bev=0.06)     # outer plate
    return M.finish(bm, 'RB_forearm.' + side, ml, coll, parent=E['elbow.' + side])

def build_hand(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark']]
    P, B, D = 0, 1, 2
    M.box(bm, (1.5, 0.9, 1.2), (0, 0, -0.6), P, taper=1.1, bev=0.15, bev_seg=2)
    for i, x in enumerate((-0.5, 0.0, 0.5)):
        M.cyl(bm, 0.24, 0.22, 0.9, (x, -0.1, -1.6), B, rot=(-15, 0, 0), segs=12)
        M.cyl(bm, 0.22, 0.17, 0.85, (x, -0.33, -2.3), P, rot=(-40, 0, 0), segs=12)
    M.cyl(bm, 0.24, 0.22, 0.8, (0.0, -0.75, -0.85), B, rot=(-65, 0, 0), segs=12)
    M.cyl(bm, 0.22, 0.17, 0.7, (0.0, -1.2, -1.25), P, rot=(-95, 0, 0), segs=12)
    return M.finish(bm, 'RB_hand.' + side, ml, coll, parent=E['wrist.' + side])

def build_thigh(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    M.cyl(bm, 0.95, 0.85, 3.3, (0, 0, -1.85), P, segs=24)
    M.cyl(bm, 1.05, 1.05, 0.4, (0, 0, -0.9), B, segs=24)                      # hip cuff
    M.sphere(bm, 0.95, (0, 0, -4.0), B, segs=24, rings=12)                    # knee ball
    v, f = M.sphere(bm, 1.1, (0, -0.35, -3.95), P2, scale=(1.0, 0.9, 1.0), segs=24, rings=12, cut_below=-0.0)   # knee dome
    return M.finish(bm, 'RB_thigh.' + side, ml, coll, parent=E['thigh.' + side])

def build_shin(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    v, f = M.cyl(bm, 0.85, 1.25, 3.3, (0, 0, -1.9), P, segs=24)               # column widening to the ankle
    M.groove(bm, (v, f), (0, 0, -2.6), (0, 0, 1))
    M.cyl(bm, 1.3, 1.3, 0.35, (0, 0, -3.55), B, segs=24)                      # ankle cuff
    M.box(bm, (1.2, 0.35, 1.6), (0, -0.95, -1.6), P2, taper=1.35, bev=0.06)    # shin plate
    return M.finish(bm, 'RB_shin.' + side, ml, coll, parent=E['knee.' + side])

def build_foot(E, mats, coll, side):
    bm = M.new_bm()
    ml = [mats['paint'], mats['bronze'], mats['dark'], mats['paint2']]
    P, B, D, P2 = 0, 1, 2, 3
    M.box(bm, (2.1, 2.8, FOOT_H), (0, -0.3, -FOOT_H / 2), P2, taper=0.75, bev=0.12, bev_seg=2)
    M.box(bm, (1.9, 1.0, 0.55), (0, -1.9, -FOOT_H + 0.28), B, taper=0.7, bev=0.08)   # toe cap
    return M.finish(bm, 'RB_foot.' + side, ml, coll, parent=E['ankle.' + side])

def build(coll_name='Robot'):
    C.clear_collection(coll_name)
    coll = C.coll(coll_name)
    mats = materials()
    E = rig(coll)
    parts = [build_head(E, mats, coll), build_torso(E, mats, coll), build_pelvis(E, mats, coll)]
    for s in ('L', 'R'):
        parts += [build_pauldron(E, mats, coll, s), build_upperarm(E, mats, coll, s), build_forearm(E, mats, coll, s),
                  build_hand(E, mats, coll, s), build_thigh(E, mats, coll, s), build_shin(E, mats, coll, s),
                  build_foot(E, mats, coll, s)]
    return E, parts

# ---------------------------------------------------------------- posing
def pose(E, angles, root=None, frame=None):
    """angles: {'joint': (rx, ry, rz) degrees}; root: (x, y, z) location of J_root."""
    for name, rot in angles.items():
        e = E[name]
        e.rotation_euler = [math.radians(a) for a in rot]
        if frame is not None:
            e.keyframe_insert('rotation_euler', frame=frame)
    if root is not None:
        E['root'].location = root
        if frame is not None:
            E['root'].keyframe_insert('location', frame=frame)
    C.view_update()

def joints(coll_name='Robot'):
    return {o.name[2:]: o for o in bpy.data.collections[coll_name].objects if o.name.startswith('J_')}

STAND = {k: (0, 0, 0) for k in ('hip', 'torso', 'neck', 'shoulder.L', 'shoulder.R', 'elbow.L', 'elbow.R', 'wrist.L', 'wrist.R',
                                 'thigh.L', 'thigh.R', 'knee.L', 'knee.R', 'ankle.L', 'ankle.R')}

# kneeling: right knee on the ground, left foot forward, torso bowed, right hand on the ground, left forearm on the knee
KNEEL = dict(STAND)
KNEEL.update({
    'hip': (14, 0, 4), 'torso': (10, 0, 0), 'neck': (24, 0, -5),
    'thigh.R': (14, 0, 6), 'knee.R': (78, 0, 0), 'ankle.R': (60, 0, 0),
    'thigh.L': (-90, 0, -8), 'knee.L': (86, 0, 0), 'ankle.L': (4, 0, 0),
    'shoulder.R': (-32, 0, 9), 'elbow.R': (-2, 0, 0), 'wrist.R': (-28, 0, 0),
    'shoulder.L': (-18, 0, -6), 'elbow.L': (-68, 0, 0), 'wrist.L': (-12, 0, 0),
})
KNEEL_ROOT_Z = -(HIP_Z - 0.45 - 4.0 * math.cos(math.radians(14)) - 0.95)

# ---------------------------------------------------------------- growth on the sleeping robot
def moss_clumps(E, coll_name='Robot', seed='moss'):
    """Rounded moss clumps and small plants on the surfaces that faced up while kneeling.
    Built while posed kneeling: clumps are parented to the part they sit on, so they ride along when it moves."""
    import bmesh
    C.view_update()
    rnd = C.rng(seed)
    coll = bpy.data.collections[coll_name]
    mats = {'moss': bpy.data.materials['RB_Moss'], 'moss2': S.cel_material('RB_Moss2', MOSS_LIGHT, line=(0.10, 0.12, 0.05, 1)),
            'grass': S.cel_material('RB_Grass', (0.45, 0.55, 0.22), line=(0.12, 0.14, 0.05, 1)),
            'flower': S.cel_material('RB_Flower', (0.95, 0.90, 0.75), line=(0.3, 0.25, 0.15, 1)),
            'flower2': S.cel_material('RB_Flower2', (0.85, 0.70, 0.85), line=(0.3, 0.2, 0.3, 1))}
    spots = {  # part: number of clumps, clump radius range
        'RB_pauldron.L': (9, 0.5, 1.1), 'RB_pauldron.R': (9, 0.5, 1.1), 'RB_head': (5, 0.35, 0.7),
        'RB_torso': (10, 0.45, 1.0), 'RB_thigh.L': (6, 0.4, 0.8), 'RB_forearm.L': (4, 0.3, 0.6), 'RB_forearm.R': (3, 0.3, 0.55),
        'RB_hand.L': (2, 0.25, 0.4), 'RB_shin.R': (4, 0.35, 0.7), 'RB_foot.R': (3, 0.3, 0.6), 'RB_pelvis': (3, 0.35, 0.7),
    }
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    for part_name, (n, r0, r1) in spots.items():
        part = bpy.data.objects[part_name]
        me = part.evaluated_get(dg).data
        mw = part.matrix_world
        rot = mw.to_3x3()
        # candidate faces: facing up in world, weighted by area
        cands = []
        for p in me.polygons:
            nw = (rot @ p.normal).normalized()
            if nw.z > 0.55 and p.area > 0.02:
                cands.append((p, nw))
        if not cands:
            continue
        for i in range(n):
            p, nw = rnd.choice(cands)
            center_w = mw @ p.center
            r = rnd.uniform(r0, r1)
            bm = M.new_bm()
            # clump: a squashed sphere with wobbled verts
            v, f = M.sphere(bm, r, (0, 0, 0), 0, scale=(1.0, rnd.uniform(0.7, 1.1), rnd.uniform(0.35, 0.5)), segs=14, rings=7, cut_below=-0.3)
            for vv in v:
                vv.co *= 1 + 0.18 * (rnd.random() - 0.5)
            mat = mats['moss'] if rnd.random() < 0.65 else mats['moss2']
            # some clumps carry a few grass blades or a flower
            extra = []
            if rnd.random() < 0.5:
                for k in range(rnd.randint(2, 5)):
                    ang = rnd.uniform(0, 6.28); rr = rnd.uniform(0, r * 0.6)
                    h = rnd.uniform(0.6, 1.4) * r
                    M.cyl(bm, 0.05 * r + 0.02, 0.0, h, (math.cos(ang) * rr, math.sin(ang) * rr, h * 0.5 + 0.1 * r), 1,
                          rot=(rnd.uniform(-25, 25), rnd.uniform(-25, 25), 0), segs=5, smooth=False)
                extra.append('grass')
            if rnd.random() < 0.35:
                ang = rnd.uniform(0, 6.28); rr = rnd.uniform(0, r * 0.5)
                h = rnd.uniform(0.9, 1.6) * r
                M.cyl(bm, 0.03 * r + 0.015, 0.03 * r + 0.015, h, (math.cos(ang) * rr, math.sin(ang) * rr, h * 0.5), 1, segs=5, smooth=False)
                M.sphere(bm, 0.14 * r + 0.05, (math.cos(ang) * rr, math.sin(ang) * rr, h + 0.05), 2, scale=(1.0, 1.0, 0.6), segs=8, rings=5)
                extra.append('flower')
            fmat = mats['flower'] if rnd.random() < 0.6 else mats['flower2']
            ob = M.finish(bm, 'RB_growth_%s_%d' % (part_name[3:], i), [mat, mats['grass'], fmat], coll)
            # place: world position on the face, oriented to the world normal
            q = nw.to_track_quat('Z', 'Y')
            ob.matrix_world = Matrix.Translation(center_w - nw * 0.05 * r) @ q.to_matrix().to_4x4()
            C.set_parent(ob, part, keep=True)
            out.append(ob)
    return out

def vines(E, coll_name='Robot', seed='vines'):
    """Hanging vines: bevelled curves from upper parts down toward the ground, parented to the part they hang from."""
    rnd = C.rng(seed)
    coll = bpy.data.collections[coll_name]
    mat = S.cel_material('RB_Vine', (0.30, 0.38, 0.16), line=(0.08, 0.10, 0.04, 1))
    leafm = S.cel_material('RB_VineLeaf', (0.38, 0.50, 0.20), line=(0.08, 0.10, 0.04, 1))
    C.view_update()
    hangs = [  # part, local start point, length, sway direction
        ('RB_pauldron.L', (-1.6, 0.6, 0.5), 7.5), ('RB_pauldron.L', (-1.0, -1.2, 0.6), 5.0),
        ('RB_pauldron.R', (1.7, 0.4, 0.5), 8.0), ('RB_pauldron.R', (1.2, 1.1, 0.5), 4.5),
        ('RB_torso', (2.3, 1.8, 4.4), 9.0), ('RB_torso', (-2.0, 2.2, 4.6), 7.0), ('RB_torso', (0.4, 2.6, 4.9), 6.0),
        ('RB_forearm.L', (0.8, -0.6, -1.0), 3.5), ('RB_upperarm.R', (0.5, 0.4, -1.2), 4.0), ('RB_head', (0.9, 0.9, 1.8), 3.0),
    ]
    out = []
    for i, (part_name, start, length) in enumerate(hangs):
        part = bpy.data.objects[part_name]
        mw = part.matrix_world
        p0 = mw @ Vector(start)
        cu = bpy.data.curves.new('RB_vine_%d' % i, 'CURVE'); cu.dimensions = '3D'
        sp = cu.splines.new('BEZIER')
        n = 5
        sp.bezier_points.add(n - 1)
        drift = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0)).normalized() * rnd.uniform(0.4, 1.4)
        for k, bp in enumerate(sp.bezier_points):
            t = k / (n - 1)
            pw = p0 + Vector((0, 0, -length * t)) + drift * math.sin(t * 3.0) + Vector((rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)) * t
            bp.co = pw
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.radius = 1.0 - 0.6 * t
        cu.bevel_depth = rnd.uniform(0.08, 0.14); cu.bevel_resolution = 3; cu.fill_mode = 'FULL'
        cu.materials.append(mat)
        ob = bpy.data.objects.new('RB_vine_%d' % i, cu); coll.objects.link(ob)
        C.set_parent(ob, part, keep=True)
        out.append(ob)
        # a few leaves along it
        for k in range(rnd.randint(3, 7)):
            t = rnd.uniform(0.1, 0.95)
            pw = p0 + Vector((0, 0, -length * t)) + drift * math.sin(t * 3.0)
            bm = M.new_bm()
            vs = [bm.verts.new(p) for p in ((0, -0.5, 0), (0.28, -0.1, 0.06), (0.12, 0.45, 0), (-0.12, 0.45, 0), (-0.28, -0.1, 0.06))]
            bm.faces.new(vs)
            sz = rnd.uniform(0.5, 0.9)
            lf = M.finish(bm, 'RB_vineleaf_%d_%d' % (i, k), [leafm], coll)
            lf.matrix_world = Matrix.Translation(pw) @ Euler((math.radians(rnd.uniform(-60, -20)), math.radians(rnd.uniform(-30, 30)), math.radians(rnd.uniform(0, 360)))).to_matrix().to_4x4() @ Matrix.Diagonal((sz, sz, sz, 1))
            C.set_parent(lf, part, keep=True)
            out.append(lf)
    return out

def sapling(E, coll_name='Robot'):
    """A small tree that took root on the right pauldron."""
    coll = bpy.data.collections[coll_name]
    part = bpy.data.objects['RB_pauldron.R']
    C.view_update()
    trunk = S.cel_material('RB_SapTrunk', (0.36, 0.28, 0.20), line=(0.08, 0.05, 0.03, 1))
    leaf = S.cel_material('RB_SapLeaf', (0.40, 0.52, 0.22), line=(0.08, 0.1, 0.04, 1))
    leaf2 = S.cel_material('RB_SapLeaf2', (0.52, 0.62, 0.26), line=(0.08, 0.1, 0.04, 1))
    rnd = C.rng('sapling')
    bm = M.new_bm()
    # trunk: a slightly bent tapered cylinder, two branches
    M.cyl(bm, 0.16, 0.08, 2.6, (0, 0, 1.3), 0, rot=(8, 4, 0), segs=8)
    M.cyl(bm, 0.07, 0.03, 1.4, (0.25, 0.1, 2.3), 0, rot=(-35, 30, 0), segs=6)
    M.cyl(bm, 0.07, 0.03, 1.2, (-0.2, -0.05, 2.0), 0, rot=(30, -40, 0), segs=6)
    # leaf clumps: flattened spheres
    for (c, r, mi) in (((0.1, 0.1, 3.0), 0.75, 1), ((0.75, 0.4, 2.9), 0.55, 2), ((-0.65, -0.3, 2.55), 0.5, 1), ((0.2, -0.4, 3.5), 0.45, 2), ((-0.1, 0.5, 3.4), 0.4, 1)):
        v, f = M.sphere(bm, r, c, mi, scale=(1.0, 1.0, 0.6), segs=12, rings=6)
        for vv in v:
            vv.co *= 1 + 0.2 * (rnd.random() - 0.5)
    ob = M.finish(bm, 'RB_sapling', [trunk, leaf, leaf2], coll)
    mw = part.matrix_world
    base = mw @ Vector((1.1, -0.3, 1.55))
    ob.matrix_world = Matrix.Translation(base) @ Euler((math.radians(6), math.radians(-8), 0)).to_matrix().to_4x4()
    C.set_parent(ob, part, keep=True)
    return ob
