"""Environment: terrain, mist, sky, forest cards."""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, noise
import aw_core as C, aw_shade as S

def terrain(size=1400, div=280, name='Terrain'):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    coll = C.coll('Set')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=div, y_segments=div, size=size / 2)
    rnd = C.rng('terrain')
    for v in bm.verts:
        x, y = v.co.x, v.co.y
        r = math.hypot(x, y)
        mound = 1.6 * math.exp(-(r * r) / (2 * 8.0 ** 2))              # the robot's mound
        roll = 0.9 * noise.noise(Vector((x * 0.025, y * 0.025, 0.3))) + 0.35 * noise.noise(Vector((x * 0.08, y * 0.08, 1.7)))
        slope = 0.015 * max(0.0, min(y, 120.0))                          # rises gently toward the back
        far = -0.004 * max(0.0, r - 150.0)                                # drops away so the far strips stand on it
        v.co.z = mound + roll + slope + far
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.data.materials.append(ground_material())
    return ob

def ground_material():
    """Cel ground: two moss tones broken by large noise, darker earth near the robot (object-space radius)."""
    mat = S.cel_material('SET_Ground', (0.30, 0.40, 0.19))
    nt = mat.node_tree; n = nt.nodes
    grp = S.group_node(mat)
    tc = n.new('ShaderNodeTexCoord'); tc.location = (-1200, 0)
    nz = n.new('ShaderNodeTexNoise'); nz.location = (-1000, 0)
    nz.inputs['Scale'].default_value = 0.08; nz.inputs['Detail'].default_value = 3; nz.inputs['Roughness'].default_value = 0.55
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    gt = n.new('ShaderNodeMath'); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.52; gt.location = (-800, 0)
    nt.links.new(nz.outputs['Fac'], gt.inputs[0])
    mix = n.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.location = (-600, 0)
    mix.inputs[6].default_value = (0.30, 0.40, 0.19, 1); mix.inputs[7].default_value = (0.36, 0.44, 0.20, 1)
    nt.links.new(gt.outputs[0], mix.inputs['Factor'])
    # earth near the origin
    ln = n.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; ln.location = (-1000, -300)
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    nz2 = n.new('ShaderNodeTexNoise'); nz2.location = (-1000, -500); nz2.inputs['Scale'].default_value = 0.35
    nt.links.new(tc.outputs['Object'], nz2.inputs['Vector'])
    ad = n.new('ShaderNodeMath'); ad.operation = 'MULTIPLY_ADD'; ad.location = (-800, -400)
    nt.links.new(nz2.outputs['Fac'], ad.inputs[0]); ad.inputs[1].default_value = 4.0; nt.links.new(ln.outputs['Value'], ad.inputs[2])
    lt = n.new('ShaderNodeMath'); lt.operation = 'LESS_THAN'; lt.inputs[1].default_value = 7.0; lt.location = (-600, -400)
    nt.links.new(ad.outputs[0], lt.inputs[0])
    mix2 = n.new('ShaderNodeMix'); mix2.data_type = 'RGBA'; mix2.location = (-400, 0)
    nt.links.new(lt.outputs[0], mix2.inputs['Factor']); nt.links.new(mix.outputs[2], mix2.inputs[6])
    mix2.inputs[7].default_value = (0.74, 0.64, 0.54, 1)
    mix2.blend_type = 'MULTIPLY'
    nt.links.new(mix2.outputs[2], grp.inputs['Base Color'])
    grp.inputs['Shadow Mul'].default_value = (0.55, 0.60, 0.80, 1)
    return mat

def mist_volume(size=760, height=22, density=0.006, name='Mist'):
    old = bpy.data.objects.get(name)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    coll = C.coll('Volumes')
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, height / 2 - 4))
    ob = bpy.context.active_object; ob.name = name
    ob.scale = (size, size, height)
    C.link(ob, coll)
    mat = bpy.data.materials.get('SET_Mist') or bpy.data.materials.new('SET_Mist')
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    vol = nt.nodes.new('ShaderNodeVolumePrincipled'); vol.location = (-300, 0)
    vol.inputs['Color'].default_value = (1.0, 0.93, 0.85, 1)
    vol.inputs['Anisotropy'].default_value = 0.35
    vol.inputs['Emission Strength'].default_value = 0.0
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1200, 0)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-1000, 0)
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    # object z goes -0.5..0.5 over the box; denser low
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-800, 0)
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = -0.5; mr.inputs['From Max'].default_value = 0.25
    mr.inputs['To Min'].default_value = 1.0; mr.inputs['To Max'].default_value = 0.0
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.location = (-800, -300)
    nz.inputs['Scale'].default_value = 0.03; nz.inputs['Detail'].default_value = 2
    nt.links.new(tc.outputs['Generated'], nz.inputs['Vector'])
    # noise 0..1 -> 0.5..1.3
    nm = nt.nodes.new('ShaderNodeMath'); nm.operation = 'MULTIPLY_ADD'; nm.location = (-600, -300)
    nt.links.new(nz.outputs['Fac'], nm.inputs[0]); nm.inputs[1].default_value = 0.8; nm.inputs[2].default_value = 0.5
    m1 = nt.nodes.new('ShaderNodeMath'); m1.operation = 'MULTIPLY'; m1.location = (-500, 0)
    nt.links.new(mr.outputs[0], m1.inputs[0]); nt.links.new(nm.outputs[0], m1.inputs[1])
    # radial fade so the box sides never show: full density inside 170 m, none beyond 300 m (object xy is -0.5..0.5)
    xy = nt.nodes.new('ShaderNodeCombineXYZ'); xy.location = (-1000, -600)
    nt.links.new(sep.outputs['X'], xy.inputs['X']); nt.links.new(sep.outputs['Y'], xy.inputs['Y'])
    ln = nt.nodes.new('ShaderNodeVectorMath'); ln.operation = 'LENGTH'; ln.location = (-800, -600)
    nt.links.new(xy.outputs[0], ln.inputs[0])
    rf = nt.nodes.new('ShaderNodeMapRange'); rf.location = (-600, -600); rf.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(ln.outputs['Value'], rf.inputs['Value'])
    rf.inputs['From Min'].default_value = 170.0 / size; rf.inputs['From Max'].default_value = 300.0 / size
    rf.inputs['To Min'].default_value = 1.0; rf.inputs['To Max'].default_value = 0.0
    m1b = nt.nodes.new('ShaderNodeMath'); m1b.operation = 'MULTIPLY'; m1b.location = (-450, -300)
    nt.links.new(m1.outputs[0], m1b.inputs[0]); nt.links.new(rf.outputs[0], m1b.inputs[1])
    m1 = m1b
    m2 = nt.nodes.new('ShaderNodeMath'); m2.operation = 'MULTIPLY'; m2.location = (-400, 0); m2.name = 'Density'
    nt.links.new(m1.outputs[0], m2.inputs[0]); m2.inputs[1].default_value = density
    nt.links.new(m2.outputs[0], vol.inputs['Density'])
    nt.links.new(vol.outputs[0], out.inputs['Volume'])
    ob.data.materials.clear(); ob.data.materials.append(mat)
    ob.display_type = 'WIRE'
    ob.hide_select = True
    return ob

def sky_world(scene, top=(0.22, 0.20, 0.42), mid=(0.80, 0.56, 0.52), horizon=(1.0, 0.82, 0.58), ambient=(0.55, 0.58, 0.72), amb_strength=0.25):
    """World: the camera sees a dawn gradient, surfaces receive a dim ambient (keeps the cel bands predictable)."""
    w = scene.world or bpy.data.worlds.new('World')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); out.location = (600, 0)
    lp = nt.nodes.new('ShaderNodeLightPath'); lp.location = (0, 300)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-800, 0)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-600, 0)
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    mr = nt.nodes.new('ShaderNodeMapRange'); mr.location = (-400, 0)
    nt.links.new(sep.outputs['Z'], mr.inputs['Value'])
    mr.inputs['From Min'].default_value = -0.02; mr.inputs['From Max'].default_value = 0.6
    ramp = nt.nodes.new('ShaderNodeValToRGB'); ramp.location = (-200, 0); ramp.name = 'SkyRamp'
    cr = ramp.color_ramp
    cr.interpolation = 'EASE'
    cr.elements[0].position = 0.0; cr.elements[0].color = (*horizon, 1)
    cr.elements[1].position = 1.0; cr.elements[1].color = (*top, 1)
    e = cr.elements.new(0.3); e.color = (*mid, 1)
    nt.links.new(mr.outputs[0], ramp.inputs['Fac'])
    sky = nt.nodes.new('ShaderNodeBackground'); sky.location = (100, 0); sky.inputs['Strength'].default_value = 1.0
    nt.links.new(ramp.outputs['Color'], sky.inputs['Color'])
    amb = nt.nodes.new('ShaderNodeBackground'); amb.location = (100, -200)
    amb.inputs['Color'].default_value = (*ambient, 1); amb.inputs['Strength'].default_value = amb_strength
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.location = (350, 0)
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs[0], mix.inputs[1]); nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ms = w.mist_settings
    ms.use_mist = True; ms.start = 30; ms.depth = 260; ms.falloff = 'QUADRATIC'
    return w

# ---------------------------------------------------------------- painted cards
import aw_anim as A

def terrain_h(x, y):
    r = math.hypot(x, y)
    mound = 1.6 * math.exp(-(r * r) / (2 * 8.0 ** 2))
    roll = 0.9 * noise.noise(Vector((x * 0.025, y * 0.025, 0.3))) + 0.35 * noise.noise(Vector((x * 0.08, y * 0.08, 1.7)))
    slope = 0.015 * max(0.0, min(y, 120.0))
    far = -0.004 * max(0.0, r - 150.0)
    return mound + roll + slope + far

def tex(name):
    path = C.TEX + '\\' + name + '.png'
    return C.img_load(path, name, alpha=True)

def card_mat(name, image, emit=1.0, tint=(1, 1, 1, 1), shadow=True):
    mat = S.card_material('CARD_' + name, image, emit=emit, tint=tint)
    mat.surface_render_method = 'DITHERED'
    try:
        mat.use_transparent_shadow = True
    except Exception:
        pass
    mat.line_color = (0.1, 0.1, 0.1, 1)
    return mat

def card(name, image, width, height, loc, yaw=0.0, coll=None, mat=None, bottom=True, pitch=0.0):
    """Vertical card facing -Y (toward the usual cameras), origin at the bottom centre."""
    coll = coll or C.coll('Cards')
    me = bpy.data.meshes.new(name)
    w, h = width / 2, height
    z0 = 0 if bottom else -h / 2
    me.from_pydata([(-w, 0, z0), (w, 0, z0), (w, 0, z0 + h), (-w, 0, z0 + h)], [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    for li, co in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = co
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (math.radians(pitch), 0, math.radians(yaw))
    me.materials.append(mat or card_mat(image.name, image))
    ob.visible_shadow = True
    return ob

def face_camera(ob, cam_loc):
    d = Vector(cam_loc) - ob.location
    ob.rotation_euler[2] = math.atan2(d.x, -d.y) * -1 if False else math.atan2(-d.x, d.y) + math.pi
    # the card's front is -Y: rotate so that -Y points toward the camera
    ang = math.atan2(d.y, d.x) + math.pi / 2
    ob.rotation_euler[2] = ang

def bake_billboards(cards, scene):
    """Per shot: turn each card around Z to face that shot's camera (constant keys at the cuts)."""
    cams = {o.name[4:]: o for o in bpy.data.objects if o.name.startswith('CAM_')}
    for name, a, b in A.SHOTS:
        f = A.F(a)
        cam = cams[name]
        keys = A.CAMS[name]
        cam_loc = A.resolve(keys[0][1], scene, f)
        for ob in cards:
            face_camera(ob, cam_loc)
            ob.keyframe_insert('rotation_euler', frame=f)
    for ob in cards:
        for fc in C.fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'

def forest(scene, seed='forest'):
    """Trees as painted cards: foreground giants, middle-distance trees, far strips; grass and flowers on the ground."""
    C.clear_collection('Cards')
    coll = C.coll('Cards')
    rnd = C.rng(seed)
    cards = []
    imgs_fg = [tex('tree_fg_%d' % i) for i in (1, 2, 3)]
    imgs_mid = [tex('tree_mid_%d' % i) for i in (1, 2, 3, 4)]
    imgs_far = [tex('forest_far_%d' % i) for i in (1, 2, 3)]
    mats_fg = [card_mat(im.name, im) for im in imgs_fg]
    mats_mid = [card_mat(im.name, im) for im in imgs_mid]
    mats_far = [card_mat(im.name, im) for im in imgs_far]
    # foreground giants (world positions chosen to frame the robot from the -Y cameras)
    FG = [(-30, 34, 38), (36, 26, 36), (-46, -2, 34), (50, 14, 35), (-16, 64, 40), (22, 72, 38), (-62, 30, 36), (64, 48, 37),
          (-40, -40, 34), (46, -46, 33), (-70, -20, 33), (72, -12, 34), (-24, 104, 40), (30, 110, 40), (0, 92, 42)]
    for i, (x, y, h) in enumerate(FG):
        im = imgs_fg[i % 3]
        w = h * im.size[0] / im.size[1]
        ob = card('TreeFG_%02d' % i, im, w, h, (x, y, terrain_h(x, y) - 0.6), mat=mats_fg[i % 3])
        if rnd.random() < 0.5:
            ob.scale.x = -1   # mirrored variant
        cards.append(ob)
    # middle distance: a ring of trees between 80 and 150 m, denser toward the back
    for i in range(46):
        ang = rnd.uniform(-1.35, 1.35) if rnd.random() < 0.8 else rnd.uniform(-math.pi, math.pi)
        r = rnd.uniform(80, 150)
        x, y = math.sin(ang) * r, math.cos(ang) * r
        h = rnd.uniform(24, 34)
        k = rnd.randrange(4)
        im = imgs_mid[k]
        w = h * im.size[0] / im.size[1]
        ob = card('TreeMid_%02d' % i, im, w, h, (x, y, terrain_h(x, y) - 1.0), mat=mats_mid[k])
        if rnd.random() < 0.5:
            ob.scale.x = -1
        cards.append(ob)
    # undergrowth: small tree cards as bushes between 18 and 85 m, denser away from the camera side
    for i in range(70):
        ang = rnd.uniform(-math.pi, math.pi)
        r = rnd.uniform(18, 85)
        x, y = math.sin(ang) * r, math.cos(ang) * r
        if r < 30 and abs(x) < 10 and y < 5:
            continue                      # keep the robot's immediate front clear
        h = rnd.uniform(4.0, 9.0)
        k = rnd.randrange(4)
        im = imgs_mid[k]
        w = h * im.size[0] / im.size[1]
        ob = card('Bush_%02d' % i, im, w, h, (x, y, terrain_h(x, y) - 0.4 - h * 0.25), mat=mats_mid[k])
        if rnd.random() < 0.5:
            ob.scale.x = -1
        cards.append(ob)
    # second ring of middle-distance trees at 55-85 m, behind the action
    for i in range(22):
        ang = rnd.uniform(-math.pi, math.pi)
        r = rnd.uniform(55, 85)
        x, y = math.sin(ang) * r, math.cos(ang) * r
        if abs(x) < 14 and y < 20 and y > -40:
            continue
        h = rnd.uniform(20, 30)
        k = rnd.randrange(4)
        im = imgs_mid[k]
        w = h * im.size[0] / im.size[1]
        ob = card('TreeMid2_%02d' % i, im, w, h, (x, y, terrain_h(x, y) - 1.0), mat=mats_mid[k])
        if rnd.random() < 0.5:
            ob.scale.x = -1
        cards.append(ob)
    # far strips: three rings
    for ring, (r, h, n) in enumerate(((190, 46, 7), (280, 60, 7), (390, 80, 7))):
        im = imgs_far[ring]
        w = h * im.size[0] / im.size[1]
        for i in range(n):
            ang = -1.6 + 3.2 * i / (n - 1) + rnd.uniform(-0.04, 0.04)
            x, y = math.sin(ang) * r, math.cos(ang) * r
            ob = card('Far%d_%02d' % (ring, i), im, w * 1.08, h, (x, y, terrain_h(x, y) - 3.0 - ring * 2.0), mat=mats_far[ring])
            face_camera(ob, (0, 0, 0))
            if i % 2:
                ob.scale.x = -1
            # far strips face the centre, not each camera
    # grass and flowers near the robot
    gimgs = [tex('grass_clump_%d' % i) for i in (1, 2, 3)]
    fimgs = [tex('flower_%d' % i) for i in (1, 2, 3)]
    gm = [card_mat(im.name, im) for im in gimgs]
    fm = [card_mat(im.name, im) for im in fimgs]
    plants = []
    for i in range(420):
        ang = rnd.uniform(-math.pi, math.pi)
        r = rnd.uniform(3.5, 75) ** 1.0
        x, y = math.sin(ang) * r, math.cos(ang) * r
        if rnd.random() < 0.72:
            k = rnd.randrange(3); s = rnd.uniform(0.9, 2.0)
            ob = card('Grass_%03d' % i, gimgs[k], s, s, (x, y, terrain_h(x, y) - 0.05), yaw=rnd.uniform(-25, 25), mat=gm[k])
        else:
            k = rnd.randrange(3); s = rnd.uniform(0.5, 0.9)
            ob = card('Flower_%03d' % i, fimgs[k], s, s, (x, y, terrain_h(x, y) - 0.03), yaw=rnd.uniform(-25, 25), mat=fm[k])
        plants.append(ob)
    bake_billboards(cards + plants, scene)
    return cards + plants

def canopy_overhangs(scene):
    """Backlit foliage hanging into the top of the frame, one or two per shot, only visible in that shot."""
    coll = C.coll('Cards')
    imgs = [tex('canopy_fg_1'), tex('canopy_fg_2')]
    mats = [card_mat(im.name, im) for im in imgs]
    cams = {o.name[4:]: o for o in bpy.data.objects if o.name.startswith('CAM_')}
    out = []
    # shot: list of (image index, distance ahead, frame fraction where the leafy edge hangs, width, side offset)
    plan = {
        's1_wide': [(0, 16, 0.30, 48, -6), (1, 22, 0.20, 64, 18)],
        's2_shoulder': [(1, 9, 0.18, 30, 2)],
        's5_tremble': [(0, 18, 0.24, 56, 4)],
        's6_rise': [(1, 12, 0.20, 46, -4)],
        's8_ignite': [(0, 20, 0.26, 70, -6), (1, 26, 0.16, 90, 20)],
    }
    for shot, items in plan.items():
        cam = cams[shot]
        a, b = A.shot_range(shot)
        scene.frame_set(a)
        mw = cam.matrix_world
        fwd = -(mw.to_3x3() @ Vector((0, 0, 1))).normalized()
        up = (mw.to_3x3() @ Vector((0, 1, 0))).normalized()
        right = fwd.cross(up).normalized()
        lens = cam.data.lens
        for j, (k, dist, frac, width, side) in enumerate(items):
            im = imgs[k]
            h = width * im.size[1] / im.size[0]
            # vertical extent of the frame at that distance
            half_h = dist * 12.0 / lens          # sensor height 24 mm /2 = 12
            top = mw.translation + fwd * dist + up * half_h
            leafy_edge = top - up * (2 * half_h * frac)
            loc = leafy_edge - up * (h * 0.73) + right * side      # the leafy edge is ~27 % down the image
            ob = card('Canopy_%s_%d' % (shot, j), im, width, h, loc, mat=mats[k])
            # orient: the card's -Y toward the camera, its Z along the camera's up
            q = (-fwd).to_track_quat('-Y', 'Z')
            ob.rotation_euler = q.to_euler()
            # the image's leafy edge is at the bottom: card bottom = bottom_edge, growing upward along +Z (camera up)
            ob.rotation_euler = (mw.to_3x3().to_4x4() @ Matrix.Rotation(0, 4, 'X')).to_euler() if False else ob.rotation_euler
            for sec_f, hide in ((1, True), (a, False), (b + 1, True)):
                ob.hide_render = hide; ob.keyframe_insert('hide_render', frame=sec_f)
                ob.hide_viewport = hide; ob.keyframe_insert('hide_viewport', frame=sec_f)
            out.append(ob)
    # the canopy ceiling around the gap for the launch shot: four big horizontal cards high above the camera, their
    # leafy edges (27 % down the image) toward the gap centre; side edges fall far outside the frame
    cam = cams['s10_sky']
    a, b = A.shot_range('s10_sky')
    scene.frame_set(a)
    gap_center = Vector((2.5, 3.5, 0))
    for j, ang in enumerate((25, 115, 205, 295)):
        im = imgs[j % 2]
        w = 320; h = w * im.size[1] / im.size[0]
        d = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
        # pitch 90: image-up (+Z) becomes -Y, then yawed to point along d. The leafy edge lies 27 % below the image
        # top, i.e. 0.23 h from the centre toward image-up; put that edge at the gap radius R
        R = 13.0
        center = gap_center + d * (R - h * 0.23) + Vector((0, 0, 40 + 2 * (j % 2)))
        ob = card('CanopyGap_%d' % j, im, w, h, center, mat=mats[j % 2], bottom=False, pitch=90)
        ob.rotation_euler = (math.radians(90), 0, math.atan2(d.y, d.x) + math.pi / 2)
        for sec_f, hide in ((1, True), (a, False)):
            ob.hide_render = hide; ob.keyframe_insert('hide_render', frame=sec_f)
            ob.hide_viewport = hide; ob.keyframe_insert('hide_viewport', frame=sec_f)
        out.append(ob)
    return out

def sky_image_world(scene, ambient=(0.55, 0.58, 0.72), amb_strength=0.25):
    """World: the camera sees the painted dawn sky (image v = elevation, u = azimuth); surfaces get a dim ambient."""
    w = scene.world or bpy.data.worlds.new('World')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld'); out.location = (800, 0)
    lp = nt.nodes.new('ShaderNodeLightPath'); lp.location = (200, 300)
    tc = nt.nodes.new('ShaderNodeTexCoord'); tc.location = (-1000, 0)
    sep = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-800, 0)
    nt.links.new(tc.outputs['Generated'], sep.inputs[0])
    at = nt.nodes.new('ShaderNodeMath'); at.operation = 'ARCTAN2'; at.location = (-600, 100)
    nt.links.new(sep.outputs['Y'], at.inputs[0]); nt.links.new(sep.outputs['X'], at.inputs[1])
    u = nt.nodes.new('ShaderNodeMath'); u.operation = 'MULTIPLY_ADD'; u.location = (-400, 100)
    nt.links.new(at.outputs[0], u.inputs[0]); u.inputs[1].default_value = 1 / (2 * math.pi); u.inputs[2].default_value = 0.5
    # elevation: z in [-0.05, 0.85] -> v in [0, 1]
    v = nt.nodes.new('ShaderNodeMapRange'); v.location = (-400, -150)
    nt.links.new(sep.outputs['Z'], v.inputs['Value'])
    v.inputs['From Min'].default_value = -0.04; v.inputs['From Max'].default_value = 1.5
    comb = nt.nodes.new('ShaderNodeCombineXYZ'); comb.location = (-200, 0)
    nt.links.new(u.outputs[0], comb.inputs['X']); nt.links.new(v.outputs[0], comb.inputs['Y'])
    img = nt.nodes.new('ShaderNodeTexImage'); img.location = (0, 0)
    img.image = C.img_load(C.TEX + r'\sky_gradient.png', 'sky_gradient', alpha=False)
    img.extension = 'EXTEND'; img.interpolation = 'Cubic'
    nt.links.new(comb.outputs[0], img.inputs['Vector'])
    sky = nt.nodes.new('ShaderNodeBackground'); sky.location = (300, 0); sky.inputs['Strength'].default_value = 1.0
    nt.links.new(img.outputs['Color'], sky.inputs['Color'])
    amb = nt.nodes.new('ShaderNodeBackground'); amb.location = (300, -200)
    amb.inputs['Color'].default_value = (*ambient, 1); amb.inputs['Strength'].default_value = amb_strength
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.location = (550, 0)
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(amb.outputs[0], mix.inputs[1]); nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    ms = w.mist_settings
    ms.use_mist = True; ms.start = 30; ms.depth = 260; ms.falloff = 'QUADRATIC'
    return w

def ground_texture(mat):
    """Paint the ground with the tiled painted texture (object space, one tile per 26 m)."""
    nt = mat.node_tree; n = nt.nodes
    grp = S.group_node(mat)
    mix2 = [x for x in n if x.type == 'MIX' and x.location.x == -400][0] if False else None
    tc = [x for x in n if x.type == 'TEX_COORD'][0]
    mp = n.new('ShaderNodeMapping'); mp.location = (-1000, 400); mp.inputs['Scale'].default_value = (1 / 26.0, 1 / 26.0, 1)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    img = n.new('ShaderNodeTexImage'); img.location = (-800, 400)
    img.image = C.img_load(C.TEX + r'\ground_tile.png', 'ground_tile', alpha=False)
    img.extension = 'REPEAT'; img.interpolation = 'Cubic'
    nt.links.new(mp.outputs[0], img.inputs['Vector'])
    # the existing chain ends in a Mix feeding Base Color; splice: base = image * 1.05 mixed with the earth patch
    link = [l for l in nt.links if l.to_node == grp and l.to_socket.name == 'Base Color'][0]
    earth_mix = link.from_node
    nt.links.remove(link)
    # earth_mix inputs[6] was the two-tone moss; replace it by the image
    for l in list(nt.links):
        if l.to_node == earth_mix and l.to_socket == earth_mix.inputs[6]:
            nt.links.remove(l)
    bright = n.new('ShaderNodeMix'); bright.data_type = 'RGBA'; bright.blend_type = 'MULTIPLY'; bright.location = (-600, 400)
    bright.inputs['Factor'].default_value = 1.0; bright.inputs[7].default_value = (1.0, 1.0, 0.95, 1)
    nt.links.new(img.outputs['Color'], bright.inputs[6])
    nt.links.new(bright.outputs[2], earth_mix.inputs[6])
    nt.links.new(earth_mix.outputs[2], grp.inputs['Base Color'])
    grp.inputs['Threshold'].default_value = 0.30
    grp.inputs['Shadow Mul'].default_value = (0.62, 0.66, 0.82, 1)
    return mat

def sunbeams(scene, loc=(30, 34, 80), target=(0, 2, 6), angle=14, energy=900):
    """A spot light that only lights the mist: the shafts of light through the canopy gap."""
    name = 'Beams'
    ob = bpy.data.objects.get(name)
    if ob is None:
        la = bpy.data.lights.new(name, 'SPOT')
        ob = bpy.data.objects.new(name, la)
        C.coll('Set').objects.link(ob)
    la = ob.data
    la.energy = energy
    la.color = (1.0, 0.9, 0.72)
    la.spot_size = math.radians(angle)
    la.spot_blend = 0.6
    la.diffuse_factor = 0.0
    la.specular_factor = 0.0
    la.volume_factor = 1.0
    la.use_shadow = True
    la.shadow_soft_size = 1.0
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def cloud_layer(z=650, size=(7000, 4200), center=(0, 900)):
    """The painted cloud wisps on a horizontal card high above: in perspective they thin toward the horizon."""
    coll = C.coll('Cards')
    im = C.img_load(C.TEX + r'\sky_clouds.png', 'sky_clouds', alpha=True)
    mat = card_mat('sky_clouds', im)
    mat.surface_render_method = 'BLENDED'
    me = bpy.data.meshes.new('Clouds')
    w, h = size[0] / 2, size[1] / 2
    me.from_pydata([(-w, -h, 0), (w, -h, 0), (w, h, 0), (-w, h, 0)], [], [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    for li, co in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = co
    ob = bpy.data.objects.new('Clouds', me)
    coll.objects.link(ob)
    ob.location = (center[0], center[1], z)
    me.materials.append(mat)
    ob.visible_shadow = False
    return ob
