"""Effects: birds, engine flames, wind ring, launch trail, debris, leaves, dust."""
import bpy, bmesh, math, random
from mathutils import Vector
import aw_core as C, aw_shade as S, aw_mesh as M
from aw_anim import F

def fx_coll():
    return C.coll('FX')

# ---------------------------------------------------------------- materials
def emissive(name, color, strength=1.0, alpha=1.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    fade = nt.nodes.new('ShaderNodeValue'); fade.name = 'Fade'; fade.outputs[0].default_value = alpha
    nt.links.new(fade.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(mix.outputs[0], out.inputs[0])
    mat.surface_render_method = 'BLENDED'
    mat.use_backface_culling = False
    mat.line_color = (0.4, 0.2, 0.05, 1)
    try:
        mat.use_transparent_shadow = True
    except Exception:
        pass
    return mat

def key_fade(mat, frame, value):
    s = mat.node_tree.nodes['Fade'].outputs[0]
    s.default_value = value
    s.keyframe_insert('default_value', frame=frame)

# ---------------------------------------------------------------- birds
def bird_mesh(name, mats, coll, size=0.5):
    """Small bird: body, head, beak, tail; two wing objects hinged at the sides (children)."""
    bm = M.new_bm()
    B, L = 0, 1
    s = size
    M.sphere(bm, 0.16 * s * 2, (0, 0, 0), B, scale=(0.75, 1.3, 0.7), segs=16, rings=8)
    M.sphere(bm, 0.12 * s * 2, (0, -0.32 * s * 2, 0.12 * s * 2), B, segs=14, rings=7)
    M.cyl(bm, 0.045 * s * 2, 0.0, 0.16 * s * 2, (0, -0.5 * s * 2, 0.1 * s * 2), L, rot=(-90, 0, 0), segs=8)
    M.box(bm, (0.14 * s * 2, 0.3 * s * 2, 0.03 * s * 2), (0, 0.42 * s * 2, 0.03 * s * 2), B, rot=(8, 0, 0), taper=1.0, subdiv=0)
    body = M.finish(bm, name, [mats['bird'], mats['beak']], coll)
    wings = []
    for sx, nm in ((-1, 'L'), (1, 'R')):
        bmw = M.new_bm()
        M.box(bmw, (0.42 * s * 2, 0.22 * s * 2, 0.02 * s * 2), (sx * 0.21 * s * 2, 0.02 * s * 2, 0), 0, taper=1.0, subdiv=0)
        w = M.finish(bmw, name + '_wing' + nm, [mats['bird']], coll, parent=body, loc=(sx * 0.1 * s * 2, 0, 0.05 * s * 2))
        wings.append(w)
    return body, wings

def bird_materials():
    m = {}
    m['bird'] = S.cel_material('FX_Bird', (0.26, 0.28, 0.34), line=(0.05, 0.04, 0.05, 1))
    m['beak'] = S.cel_material('FX_Beak', (0.75, 0.55, 0.25), line=(0.1, 0.06, 0.02, 1))
    return m

def flap(wings, start_s, end_s, period_s=0.22, amp=55, rest=10, phase=0.0):
    """Wing flapping between the two times; folded (rest angle) outside."""
    for i, w in enumerate(wings):
        sx = -1 if i == 0 else 1
        w.animation_data_clear()
        def k(sec, ang):
            w.rotation_euler = (0, math.radians(sx * ang), 0)
            w.keyframe_insert('rotation_euler', frame=F(sec))
        k(start_s - 0.01, rest)
        t = start_s + phase
        up = True
        while t < end_s:
            k(t, amp if up else -amp * 0.7)
            up = not up
            t += period_s / 2
        k(end_s + 0.05, rest)
        C.set_interp(w, 'BEZIER', 'EASE_IN_OUT')

def path_flight(ob, points, t0, t1, up_bob=0.0, bank=True):
    """Fly through the points (world) between t0 and t1; orientation follows the direction of travel."""
    ob.animation_data_clear()
    n = len(points)
    for i, p in enumerate(points):
        sec = t0 + (t1 - t0) * i / (n - 1)
        ob.location = p
        ob.keyframe_insert('location', frame=F(sec))
        if i < n - 1:
            d = Vector(points[i + 1]) - Vector(p)
        else:
            d = Vector(p) - Vector(points[i - 1])
        if d.length > 1e-6:
            q = d.normalized().to_track_quat('-Y', 'Z')
            ob.rotation_euler = q.to_euler()
            ob.keyframe_insert('rotation_euler', frame=F(sec))
    C.set_interp(ob, 'BEZIER', 'EASE_IN_OUT')
    for fc in C.fcurves(ob):
        if fc.data_path == 'location':
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'; kp.handle_left_type = 'AUTO_CLAMPED'; kp.handle_right_type = 'AUTO_CLAMPED'

def little_bird(land_point, land_dir, t_in=8.3, t_land=10.3, t_off=25.7, t_gone=27.2):
    """The bird that lands on the shoulder: flies in from the left, perches, startles away."""
    coll = C.coll('Birds')
    mats = bird_materials()
    body, wings = bird_mesh('Bird_little', mats, coll, size=0.55)
    L = Vector(land_point)
    pts_in = [L + Vector((-26, -9, 7)), L + Vector((-17, -6, 5.5)), L + Vector((-9, -3.5, 3.2)), L + Vector((-3.5, -1.2, 1.3)), L + Vector((0, 0, 0.25))]
    pts_off = [L + Vector((0, 0, 0.3)), L + Vector((2.5, -2, 2.5)), L + Vector((9, -5, 7)), L + Vector((20, -8, 14)), L + Vector((34, -8, 22))]
    # fly in
    body.animation_data_clear()
    path_flight(body, pts_in, t_in, t_land)
    # perched: small head turns are not rigged; a couple of hops instead
    for sec, dz, yaw in ((t_land + 0.1, 0.0, 0), (12.0, 0.0, 25), (12.15, 0.35, 25), (12.3, 0.0, 25), (15.0, 0.0, -20), (22.0, 0.0, 10), (t_off - 0.05, 0.0, 10)):
        body.location = L + Vector((0, 0, 0.25 + dz)); body.keyframe_insert('location', frame=F(sec))
        body.rotation_euler = (0, 0, math.radians(yaw) + math.atan2(-land_dir[0], land_dir[1]) if False else math.radians(yaw))
        body.keyframe_insert('rotation_euler', frame=F(sec))
    # the flight away is keyed on top
    n = len(pts_off)
    for i, p in enumerate(pts_off):
        sec = t_off + (t_gone - t_off) * i / (n - 1)
        body.location = p; body.keyframe_insert('location', frame=F(sec))
        d = (Vector(pts_off[min(i + 1, n - 1)]) - Vector(pts_off[max(i - 1, 0)]))
        body.rotation_euler = d.normalized().to_track_quat('-Y', 'Z').to_euler(); body.keyframe_insert('rotation_euler', frame=F(sec))
    C.set_interp(body, 'BEZIER', 'EASE_IN_OUT')
    flap(wings, t_in - 0.2, t_land - 0.15, period_s=0.26, amp=50)
    # second flap block: startle flight
    for i, w in enumerate(wings):
        sx = -1 if i == 0 else 1
        t = t_off - 0.1
        up = True
        while t < t_gone:
            w.rotation_euler = (0, math.radians(sx * (60 if up else -45)), 0); w.keyframe_insert('rotation_euler', frame=F(t))
            up = not up; t += 0.11
    return body

def flock(treetops, t0=24.6, n=18, seed='flock'):
    """Birds bursting from the treetops into the sky."""
    coll = C.coll('Birds')
    mats = bird_materials()
    rnd = C.rng(seed)
    birds = []
    for i in range(n):
        body, wings = bird_mesh('Bird_flock_%02d' % i, mats, coll, size=0.7)
        base = Vector(rnd.choice(treetops)) + Vector((rnd.uniform(-4, 4), rnd.uniform(-4, 4), rnd.uniform(-2, 2)))
        ts = t0 + rnd.uniform(0, 0.9)
        dirn = Vector((rnd.uniform(-1, 1), rnd.uniform(-0.6, 1.0), 0)).normalized()
        pts = [base, base + dirn * 6 + Vector((0, 0, 7)), base + dirn * 16 + Vector((0, 0, 16)), base + dirn * 32 + Vector((0, 0, 26)), base + dirn * 60 + Vector((0, 0, 36))]
        path_flight(body, pts, ts, ts + 3.4)
        # hidden until it takes off, and after it is far away
        for sec, hide in ((0, True), (ts, False), (ts + 3.6, True)):
            for ob in (body, *wings):
                ob.hide_render = hide; ob.keyframe_insert('hide_render', frame=F(sec))
                ob.hide_viewport = hide; ob.keyframe_insert('hide_viewport', frame=F(sec))
        flap(wings, ts, ts + 3.4, period_s=0.2, amp=60, phase=rnd.uniform(0, 0.2))
        birds.append(body)
    return birds

# ---------------------------------------------------------------- engines
def engine_flames(torso):
    coll = fx_coll()
    core = emissive('FX_FlameCore', (1.0, 0.98, 0.85), 4.0)
    mid = emissive('FX_FlameMid', (1.0, 0.72, 0.25), 2.5)
    outer = emissive('FX_FlameOuter', (0.95, 0.40, 0.12), 1.4, alpha=0.85)
    flames = []
    for sx in (-1, 1):
        for name, mat, r0, r1, ln in (('outer', outer, 1.05, 0.25, 7.0), ('mid', mid, 0.72, 0.15, 5.2), ('core', core, 0.4, 0.05, 3.4)):
            bm = M.new_bm()
            # flame along -Z of the object, with a scalloped tip
            v, f = M.cyl(bm, r0, r1, ln, (0, 0, -ln / 2), 0, segs=14)
            rnd = C.rng(name + str(sx))
            for vv in v:
                if vv.co.z < -ln * 0.4:
                    vv.co.x *= 1 + 0.25 * (rnd.random() - 0.5); vv.co.y *= 1 + 0.25 * (rnd.random() - 0.5)
            ob = M.finish(bm, 'FX_flame_%s_%s' % (name, 'L' if sx < 0 else 'R'), [mat], coll, parent=torso,
                          loc=(sx * 1.5, 2.72, 0.95), rot=(10, 0, 0))
            ob.visible_shadow = False
            flames.append(ob)
    return flames

def animate_flames(flames):
    """Scale along the flame axis: dead until 44.3 s, sputtering, full at the launch, with a fast flicker."""
    for ob in flames:
        ob.animation_data_clear()
        def k(sec, sz, w=None):
            ob.scale = (w or sz ** 0.5 if sz > 0 else 0.001, w or sz ** 0.5 if sz > 0 else 0.001, max(sz, 0.001))
            ob.keyframe_insert('scale', frame=F(sec))
        k(0, 0); k(44.2, 0); k(44.35, 0.25); k(44.5, 0.05); k(44.8, 0.4); k(45.0, 0.15); k(45.4, 0.55); k(45.7, 0.45)
        k(46.4, 0.7); k(47.0, 0.8); k(47.4, 1.9); k(48.0, 2.1); k(56, 2.0)
        for fc in C.fcurves(ob):
            m = fc.modifiers.new('NOISE'); m.scale = 1.6; m.strength = 0.25; m.phase = fc.array_index * 7
            m.use_restricted_range = True; m.frame_start = F(44.3); m.frame_end = F(56); m.blend_in = 2
        C.stepped(ob, 2)

# ---------------------------------------------------------------- wind ring
def wind_ring(name='FX_ring', segs=96, rsegs=12, seed=None):
    """Dust skirt of the shockwave: a flattened, lumpy torus with a cel dust material. Scaled (r, r, 1) when it
    expands, so it gets wider but not taller."""
    coll = fx_coll()
    bm = M.new_bm()
    rnd = C.rng(seed or name)
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        lump = 1 + 0.10 * math.sin(a * 7 + 0.4) + 0.06 * math.sin(a * 13 + 2.0) + 0.04 * (rnd.random() - 0.5)
        for j in range(rsegs):
            b = 2 * math.pi * j / rsegs
            rr = 1.0 + 0.11 * lump * math.cos(b)          # horizontal tube radius 0.11 of the ring radius
            z = 0.45 * math.sin(b) * (0.75 + 0.25 * math.sin(a * 5 + 1.0))   # vertical half-thickness ~0.45 m: a low skirt
            verts.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, z)))
    for i in range(segs):
        for j in range(rsegs):
            a0 = verts[i * rsegs + j]; a1 = verts[i * rsegs + (j + 1) % rsegs]
            b0 = verts[((i + 1) % segs) * rsegs + j]; b1 = verts[((i + 1) % segs) * rsegs + (j + 1) % rsegs]
            f = bm.faces.new((a0, b0, b1, a1)); f.smooth = True
    mat = S.cel_material(name + '_mat', (0.96, 0.92, 0.84), line=(0.3, 0.25, 0.2, 1))
    g = S.group_node(mat)
    g.inputs['Shadow Mul'].default_value = (0.80, 0.78, 0.84, 1)
    g.inputs['Deep Mul'].default_value = (0.70, 0.68, 0.78, 1)
    g.inputs['Alpha'].default_value = 0.75
    mat.surface_render_method = 'BLENDED'
    ob = M.finish(bm, name, [mat], coll)
    ob.visible_shadow = False
    return ob

def animate_ring(ob, t0, t1, r0=3.0, r1=95.0, z=0.6, alpha=0.9):
    mat = ob.data.materials[0]
    g = S.group_node(mat)
    ob.animation_data_clear(); mat.node_tree.animation_data_clear()
    ob.location = (0, 0.6, z)
    def k(sec, r, a):
        ob.scale = (r, r, 1); ob.keyframe_insert('scale', frame=F(sec))
        g.inputs['Alpha'].default_value = a; g.inputs['Alpha'].keyframe_insert('default_value', frame=F(sec))
    k(t0 - 0.01, 0.01, 0.0); k(t0, r0, alpha); k(t0 + (t1 - t0) * 0.35, r0 + (r1 - r0) * 0.55, alpha * 0.85); k(t1, r1, 0.0)
    for fc in C.fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'; kp.easing = 'EASE_OUT'
    for sec, hide in ((0, True), (t0 - 0.02, False), (t1 + 0.05, True)):
        ob.hide_render = hide; ob.keyframe_insert('hide_render', frame=F(sec))
        ob.hide_viewport = hide; ob.keyframe_insert('hide_viewport', frame=F(sec))

# ---------------------------------------------------------------- launch trail
def trail(points, name='FX_trail', depth=1.6, color=(1.0, 0.88, 0.55), strength=3.0):
    coll = fx_coll()
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = p; bp.handle_left_type = bp.handle_right_type = 'AUTO'
        bp.radius = 1.0
    cu.bevel_depth = depth; cu.bevel_resolution = 6; cu.fill_mode = 'FULL'
    cu.use_fill_caps = True
    cu.bevel_factor_mapping_start = 'SPLINE'; cu.bevel_factor_mapping_end = 'SPLINE'
    # taper: wide near the start, thin at the end
    tp = bpy.data.curves.new(name + '_taper', 'CURVE'); tp.dimensions = '2D'
    ts = tp.splines.new('BEZIER'); ts.bezier_points.add(2)
    for bp, (x, y) in zip(ts.bezier_points, ((0, 0.35), (0.5, 0.6), (1.0, 0.12))):
        bp.co = (x, y, 0); bp.handle_left_type = bp.handle_right_type = 'AUTO'
    tpo = bpy.data.objects.new(name + '_taper', tp); coll.objects.link(tpo); tpo.hide_render = True; tpo.hide_viewport = True
    cu.taper_object = tpo
    ob = bpy.data.objects.new(name, cu); coll.objects.link(ob)
    # material: emissive, fading toward the trailing end by the curve's U coordinate
    mat = bpy.data.materials.get(name + '_mat') or bpy.data.materials.new(name + '_mat')
    mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); nt.links.new(tc.outputs['UV'], sep.inputs[0])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.name = 'Ramp'
    cr = ramp.color_ramp; cr.elements[0].position = 0.0; cr.elements[0].color = (0, 0, 0, 1)
    cr.elements[1].position = 1.0; cr.elements[1].color = (1, 1, 1, 1)
    nt.links.new(sep.outputs['X'], ramp.inputs['Fac'])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (*color, 1); em.inputs['Strength'].default_value = strength
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    mix = nt.nodes.new('ShaderNodeMixShader')
    glob = nt.nodes.new('ShaderNodeValue'); glob.name = 'Fade'; glob.outputs[0].default_value = 1.0
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(ramp.outputs['Color'], mul.inputs[0]); nt.links.new(glob.outputs[0], mul.inputs[1])
    lw = nt.nodes.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    soft = nt.nodes.new('ShaderNodeMath'); soft.operation = 'POWER'; soft.inputs[1].default_value = 1.6
    nt.links.new(lw.outputs['Facing'], soft.inputs[0])
    mul2 = nt.nodes.new('ShaderNodeMath'); mul2.operation = 'MULTIPLY'
    nt.links.new(mul.outputs[0], mul2.inputs[0]); nt.links.new(soft.outputs[0], mul2.inputs[1])
    nt.links.new(mul2.outputs[0], mix.inputs['Fac'])
    nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(mix.outputs[0], out.inputs[0])
    mat.surface_render_method = 'BLENDED'
    cu.materials.append(mat)
    ob.visible_shadow = False
    return ob

def animate_trail(ob, t_start, t_end, t_fade_end, keys):
    """keys: list of (second, bevel_factor_end) so the trail head follows the robot; the tail then dissolves."""
    cu = ob.data
    cu.animation_data_clear(); ob.data.materials[0].node_tree.animation_data_clear()
    for sec, fe in keys:
        cu.bevel_factor_end = fe; cu.keyframe_insert('bevel_factor_end', frame=F(sec))
    cu.bevel_factor_start = 0.0; cu.keyframe_insert('bevel_factor_start', frame=F(t_end))
    cu.bevel_factor_start = 0.98; cu.keyframe_insert('bevel_factor_start', frame=F(t_fade_end))
    for sec, hide in ((0, True), (t_start, False)):
        ob.hide_render = hide; ob.keyframe_insert('hide_render', frame=F(sec))
        ob.hide_viewport = hide; ob.keyframe_insert('hide_viewport', frame=F(sec))
    mat = ob.data.materials[0]
    base = mat.node_tree.nodes['Fade'].outputs[0].default_value
    key_fade(mat, F(t_end), base); key_fade(mat, F(t_fade_end), 0.0)

# ---------------------------------------------------------------- debris and leaves (particles)
def debris_collection():
    coll = C.coll('DebrisSrc')
    if len(coll.objects) > 0:
        return coll
    soil = S.cel_material('FX_Soil', (0.27, 0.19, 0.12), line=(0.08, 0.05, 0.03, 1))
    moss = S.cel_material('FX_MossChunk', (0.36, 0.46, 0.17), line=(0.08, 0.1, 0.04, 1))
    leaf1 = S.cel_material('FX_Leaf1', (0.80, 0.62, 0.25), line=(0.25, 0.15, 0.05, 1))
    leaf2 = S.cel_material('FX_Leaf2', (0.72, 0.38, 0.16), line=(0.25, 0.12, 0.05, 1))
    for m in (leaf1, leaf2):      # falling leaves stay warm and translucent-looking against the sky
        S.group_node(m).inputs['Shadow Mul'].default_value = (0.85, 0.80, 0.78, 1)
        S.group_node(m).inputs['Deep Mul'].default_value = (0.75, 0.70, 0.70, 1)
    rnd = C.rng('debris')
    for i in range(4):
        bm = M.new_bm()
        r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.35)
        for v in r['verts']:
            v.co *= 1 + 0.45 * (rnd.random() - 0.5)
        for f in bm.faces:
            f.smooth = False
        M.finish(bm, 'DS_clod%d' % i, [soil if i < 3 else moss], coll)
    for i in range(3):
        bm = M.new_bm()
        # leaf: a flat diamond with a slight fold
        vs = [bm.verts.new(p) for p in ((0, -0.45, 0), (0.22, -0.1, 0.06), (0.1, 0.4, 0), (-0.1, 0.4, 0), (-0.22, -0.1, 0.06))]
        bm.faces.new(vs)
        M.finish(bm, 'DS_leaf%d' % i, [leaf1 if i != 1 else leaf2], coll)
    for ob in coll.objects:
        ob.location = (0, 0, -400)          # out of sight; instances ignore the source location
    return coll

def particles(emitter, name, src_coll, t0, t1, count, life=2.0, vel_normal=0.6, vel_rand=0.4, size=0.5, size_rand=0.5,
              gravity=1.0, rot=True, damping=0.0, drag=0.0, emit_from='FACE', lifetime_rand=0.3, seed=1):
    ps_mod = emitter.modifiers.new(name, 'PARTICLE_SYSTEM')
    ps = ps_mod.particle_system
    st = ps.settings
    st.name = name
    st.count = count
    st.frame_start = F(t0); st.frame_end = F(t1)
    st.lifetime = F(life); st.lifetime_random = lifetime_rand
    st.emit_from = emit_from
    st.use_emit_random = True
    st.distribution = 'RAND'
    st.normal_factor = vel_normal; st.factor_random = vel_rand
    st.effector_weights.gravity = gravity
    st.effector_weights.drag = 1.0
    st.drag_factor = drag; st.damping = damping
    st.render_type = 'COLLECTION'
    st.instance_collection = src_coll
    st.use_collection_pick_random = True
    st.particle_size = size; st.size_random = size_rand
    st.use_rotations = rot
    if rot:
        st.rotation_mode = 'NOR_TAN'
        st.rotation_factor_random = 1.0
        st.phase_factor_random = 2.0
        st.angular_velocity_mode = 'RAND'
        st.angular_velocity_factor = 2.5
    st.use_rotation_instance = True
    st.display_method = 'RENDER'
    ps.seed = seed
    return ps

def collision_ground(terrain):
    if not any(m.type == 'COLLISION' for m in terrain.modifiers):
        terrain.modifiers.new('collide', 'COLLISION')
    col = terrain.collision
    col.use_particle_kill = True
    col.damping_factor = 0.8
    col.friction_factor = 0.9
    return col

def force_field(name, ftype, loc, strength, coll=None, **kw):
    """An empty with a force field (empties made from Python have no field until the operator adds one)."""
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    bpy.ops.object.effector_add(type=ftype, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    C.link(ob, coll or fx_coll())
    ob.field.strength = strength
    for k, v in kw.items():
        setattr(ob.field, k, v)
    return ob


def dust_card(name, image_name, size=1.0):
    """A camera-side dust puff sprite (painted texture), source object for particle instancing."""
    import aw_set as SET
    coll = C.coll('DebrisSrc')
    im = SET.tex(image_name)
    mat = S.card_material('CARD_dust_' + image_name, im, emit=1.05, tint=(1.0, 0.96, 0.9, 1))
    mat.surface_render_method = 'BLENDED'
    # dust is airy: scale the alpha down
    nt = mat.node_tree
    tex = next(nd for nd in nt.nodes if nd.type == 'TEX_IMAGE')
    mixs = next(nd for nd in nt.nodes if nd.type == 'MIX_SHADER')
    am = nt.nodes.new('ShaderNodeMath'); am.operation = 'MULTIPLY'; am.inputs[1].default_value = 0.62
    nt.links.new(tex.outputs['Alpha'], am.inputs[0]); nt.links.new(am.outputs[0], mixs.inputs['Fac'])
    me = bpy.data.meshes.new(name)
    hw = size / 2
    me.from_pydata([(-hw, 0, -hw), (hw, 0, -hw), (hw, 0, hw), (-hw, 0, hw)], [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    for li, co in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = co
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(mat)
    ob.location = (0, 0, -400)
    ob.visible_shadow = False
    return ob

def dust_collection():
    coll = C.coll('DustSrc')
    if len(coll.objects) == 0:
        for i, nm in enumerate(('dust_1', 'dust_2')):
            ob = dust_card('DU_%d' % i, nm, 1.0)
            C.link(ob, coll)
    return coll

def vert_emitter(name, points, loc=(0, 0, 0)):
    """A mesh of loose vertices: a particle emitter with no surface at all, so nothing can render or shadow."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in points], [], [])
    me.update()
    ob = bpy.data.objects.new(name, me)
    fx_coll().objects.link(ob)
    ob.location = loc
    ob.show_instancer_for_render = False
    ob.show_instancer_for_viewport = False
    return ob

def ring_emitter(name, r0, r1, z=0.4, n=600):
    """Random points in a flat ring around the robot (vertex-only emitter)."""
    rnd = C.rng(name)
    pts = []
    for i in range(n):
        r = math.sqrt(rnd.uniform(r0 * r0, r1 * r1)); a = rnd.uniform(0, 2 * math.pi)
        pts.append((math.cos(a) * r, math.sin(a) * r, 0))
    return vert_emitter(name, pts, loc=(0, 0.6, z))

def disc_emitter(name, radius, loc, n=800):
    rnd = C.rng(name)
    pts = []
    for i in range(n):
        r = radius * math.sqrt(rnd.random()); a = rnd.uniform(0, 2 * math.pi)
        pts.append((math.cos(a) * r, math.sin(a) * r, 0))
    return vert_emitter(name, pts, loc=loc)

def dust_particles(emitter, name, t0, t1, count, size, life=2.2, vel=1.2, gravity=-0.05, seed=3):
    ps = particles(emitter, name, dust_collection(), t0, t1, count, life=life, vel_normal=vel, vel_rand=0.5, size=size, size_rand=0.4,
                   gravity=gravity, rot=False, drag=0.6, seed=seed, lifetime_rand=0.35, emit_from='VERT')
    st = ps.settings
    st.use_rotations = False          # instances keep the card's own orientation (facing -Y)
    st.use_rotation_instance = False
    st.normal_factor = 0.0
    st.object_align_factor = (0.0, 0.0, vel)      # drift upward whatever the emitter's face normals
    st.factor_random = 0.6
    return ps


def trail_follow(trail, root, z_offset=-6.0, t0=47.4, t1=56.0, samples=60):
    """Key bevel_factor_end so the trail's head stays just below the robot: the curve is sampled into a polyline and
    the factor is found by the robot's height (the path only goes up)."""
    import aw_anim as A
    scene = bpy.context.scene
    cu = trail.data
    cu.animation_data_clear()
    # sample the curve: evaluated mesh of a bevel-less copy would be heavy; use the spline's bezier points via mathutils
    from mathutils.geometry import interpolate_bezier
    sp = cu.splines[0]
    pts = []
    bps = sp.bezier_points
    for i in range(len(bps) - 1):
        seg = interpolate_bezier(bps[i].co, bps[i].handle_right, bps[i + 1].handle_left, bps[i + 1].co, 24)
        pts.extend(seg[:-1] if i < len(bps) - 2 else seg)
    # cumulative length -> factor
    import math as _m
    L = [0.0]
    for a, b in zip(pts, pts[1:]):
        L.append(L[-1] + (b - a).length)
    total = L[-1]
    def factor_at_z(z):
        if z <= pts[0].z:
            return 0.0
        for k in range(len(pts) - 1):
            if pts[k].z <= z <= pts[k + 1].z:
                t = (z - pts[k].z) / max(1e-6, pts[k + 1].z - pts[k].z)
                return (L[k] + t * (L[k + 1] - L[k])) / total
        return 1.0
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert('bevel_factor_end', frame=A.F(t0) - 1)
    for i in range(samples + 1):
        sec = t0 + (t1 - t0) * i / samples
        f = A.F(sec)
        scene.frame_set(f)
        z = root.matrix_world.translation.z + z_offset
        cu.bevel_factor_end = max(0.002, min(1.0, factor_at_z(z)))
        cu.keyframe_insert('bevel_factor_end', frame=f)
    for fc in C.fcurves(cu):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'


def hide_emitter(ob):
    """Particle emitters must stay renderable for their particles, but their own surface must not show:
    camera ray visibility off, no shadow, and a fully transparent material as a second guard."""
    ob.show_instancer_for_render = False
    ob.show_instancer_for_viewport = False
    for attr in ('visible_camera', 'visible_shadow', 'visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_volume_scatter'):
        try:
            setattr(ob, attr, False)
        except Exception:
            pass
    mat = bpy.data.materials.get('FX_Invisible')
    if mat is None:
        mat = bpy.data.materials.new('FX_Invisible')
        mat.use_nodes = True
        nt = mat.node_tree; nt.nodes.clear()
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(tr.outputs[0], out.inputs[0])
        mat.surface_render_method = 'BLENDED'
        try:
            mat.use_transparent_shadow = True
        except Exception:
            pass
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob
