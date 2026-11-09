"""Timeline: shots, cameras and the robot's key poses (24 fps)."""
import bpy, math
import aw_core as C, aw_robot as R

FPS = 24
def F(sec):
    return int(round(sec * FPS))

# shots: name, start second, end second, camera settings (loc, rot deg, lens) at start and end, notes
SHOTS = [
    ('s1_wide',   0.0,  7.0),
    ('s2_shoulder', 7.0, 13.0),
    ('s3_face',  13.0, 18.0),
    ('s4_chest', 18.0, 23.0),
    ('s5_tremble', 23.0, 28.0),
    ('s6_rise',  28.0, 38.0),
    ('s7_lookup', 38.0, 43.0),
    ('s8_ignite', 43.0, 47.0),
    ('s9_launch', 47.0, 49.3),
    ('s10_sky', 49.3, 56.0),
]
END = F(56.0)

def P(**kw):
    """Pose = dict joint -> (rx, ry, rz) built on top of KNEEL/STAND defaults."""
    base = dict(R.KNEEL)
    base.update(kw)
    return base

Z0 = R.KNEEL_ROOT_Z + 0.05
# key poses (joint angles) and root positions
POSES = {
    'kneel': (P(), (0, 0, Z0)),
    'first_stir': (P(neck=(20, 0, -2)), (0, 0, Z0)),
    'anticipate': (P(hip=(22, 0, 4), torso=(12, 0, 0), neck=(38, 0, -4), **{'shoulder.R': (-36, 0, 9), 'elbow.R': (-2, 0, 0)}), (0, 0, Z0 - 0.25)),
    'push': (P(hip=(12, 0, 3), torso=(6, 0, 0), neck=(22, 0, -3),
               **{'thigh.R': (-18, 0, 6), 'knee.R': (62, 0, 0), 'ankle.R': (34, 0, 0),
                  'thigh.L': (-72, 0, -8), 'knee.L': (72, 0, 0),
                  'shoulder.R': (-20, 0, 9), 'elbow.R': (-6, 0, 0), 'wrist.R': (-20, 0, 0),
                  'shoulder.L': (-12, 0, -6), 'elbow.L': (-40, 0, 0)}), (0, 0.4, Z0 + 1.4)),
    'halfup': (P(hip=(5, 0, 2), torso=(3, 0, 0), neck=(10, 0, -2),
                 **{'thigh.R': (-30, 0, 5), 'knee.R': (42, 0, 0), 'ankle.R': (-8, 0, 0),
                    'thigh.L': (-42, 0, -6), 'knee.L': (44, 0, 0), 'ankle.L': (0, 0, 0),
                    'shoulder.R': (-14, 0, 8), 'elbow.R': (-12, 0, 0), 'wrist.R': (-10, 0, 0),
                    'shoulder.L': (-6, 0, -6), 'elbow.L': (-18, 0, 0), 'wrist.L': (-6, 0, 0)}), (0, 0.6, -1.1)),
    'stand_over': (dict(R.STAND, hip=(-2, 0, 0), torso=(-2, 0, 0), neck=(-4, 0, 0),
                        **{'thigh.R': (2, 0, 4), 'thigh.L': (2, 0, -4), 'knee.R': (2, 0, 0), 'knee.L': (2, 0, 0),
                           'shoulder.R': (4, 0, 8), 'shoulder.L': (4, 0, -8), 'elbow.R': (-8, 0, 0), 'elbow.L': (-8, 0, 0)}), (0, 0.6, 0.18)),
    'stand': (dict(R.STAND, **{'thigh.R': (0, 0, 4), 'thigh.L': (0, 0, -4), 'shoulder.R': (2, 0, 8), 'shoulder.L': (2, 0, -8),
                               'elbow.R': (-6, 0, 0), 'elbow.L': (-6, 0, 0), 'knee.R': (3, 0, 0), 'knee.L': (3, 0, 0)}), (0, 0.6, 0.0)),
    'lookup': (dict(R.STAND, hip=(-5, 0, 0), torso=(-8, 0, 0), neck=(-36, 0, 0),
                    **{'thigh.R': (3, 0, 4), 'thigh.L': (3, 0, -4), 'shoulder.R': (6, 0, 10), 'shoulder.L': (6, 0, -10),
                       'elbow.R': (-6, 0, 0), 'elbow.L': (-6, 0, 0), 'knee.R': (3, 0, 0), 'knee.L': (3, 0, 0)}), (0, 0.6, 0.0)),
    'crouch': (dict(R.STAND, hip=(10, 0, 0), torso=(6, 0, 0), neck=(-24, 0, 0),
                    **{'thigh.R': (-38, 0, 6), 'thigh.L': (-38, 0, -6), 'knee.R': (52, 0, 0), 'knee.L': (52, 0, 0),
                       'ankle.R': (-12, 0, 0), 'ankle.L': (-12, 0, 0),
                       'shoulder.R': (28, 0, 14), 'shoulder.L': (28, 0, -14), 'elbow.R': (-28, 0, 0), 'elbow.L': (-28, 0, 0)}), (0, 0.6, -1.35)),
    'launch': (dict(R.STAND, hip=(-6, 0, 0), torso=(-6, 0, 0), neck=(-30, 0, 0),
                    **{'thigh.R': (12, 0, 6), 'thigh.L': (12, 0, -6), 'knee.R': (-4, 0, 0), 'knee.L': (-4, 0, 0),
                       'ankle.R': (30, 0, 0), 'ankle.L': (30, 0, 0),
                       'shoulder.R': (40, 0, 16), 'shoulder.L': (40, 0, -16), 'elbow.R': (-10, 0, 0), 'elbow.L': (-10, 0, 0)}), (0, 0.6, 0.0)),
}

# (second, pose name, optional root override) — the robot's timing
KEYS = [
    (0.0, 'kneel'), (26.0, 'kneel'),
    (27.6, 'first_stir'), (28.4, 'first_stir'),
    (29.8, 'anticipate'), (30.6, 'anticipate'),
    (32.6, 'push'),
    (34.6, 'halfup'),
    (36.4, 'stand_over'),
    (37.6, 'stand'), (39.0, 'stand'),
    (40.8, 'lookup'), (43.8, 'lookup'),
    (45.6, 'crouch'), (46.9, 'crouch'),
    (47.45, 'launch', (0, 0.6, 1.5)),
    (48.0, 'launch', (0.8, 1.6, 8.0)),
    (49.0, 'launch', (4.5, 5.5, 36.0)),
    (50.5, 'launch', (16.0, 17.0, 110.0)),
    (56.0, 'launch', (62.0, 52.0, 420.0)),
]

def clear_anim(E):
    for e in E.values():
        e.animation_data_clear()

def animate_robot(E, keys=KEYS, step=2):
    clear_anim(E)
    for k in keys:
        sec, name = k[0], k[1]
        angles, root = POSES[name]
        if len(k) > 2:
            root = k[2]
        R.pose(E, angles, root=root, frame=F(sec))
    for e in E.values():
        C.set_interp(e, 'BEZIER', 'EASE_IN_OUT')
        # heavy machine: long slow eases
        for fc in C.fcurves(e):
            for kp in fc.keyframe_points:
                kp.handle_left_type = 'AUTO_CLAMPED'; kp.handle_right_type = 'AUTO_CLAMPED'
        if step > 1:
            C.stepped(e, step)
    # the launch rises fast: make the root z after 47 s accelerate (exponential feel) by using linear segments between
    # dense keys above; nothing else to do here

# ---------------------------------------------------------------- cameras
from mathutils import Vector

def look_rot(loc, target, roll=0.0):
    d = Vector(target) - Vector(loc)
    q = d.to_track_quat('-Z', 'Y')
    e = q.to_euler()
    e.rotate_axis('Z', 0) if False else None
    return e

def camera(name, coll):
    cam = bpy.data.cameras.get('CAM_' + name) or bpy.data.cameras.new('CAM_' + name)
    cam.sensor_width = 36
    cam.clip_start = 0.5; cam.clip_end = 3000
    cam.animation_data_clear()
    ob = bpy.data.objects.get('CAM_' + name)
    if ob is None:
        ob = bpy.data.objects.new('CAM_' + name, cam)
        coll.objects.link(ob)
    ob.data = cam
    ob.animation_data_clear()
    return ob

def resolve(target, scene, frame):
    """target: (x, y, z) point; (name, (dx, dy, dz)) = object/joint local offset at the frame;
    (name, (dx, dy, dz), (wx, wy, wz)) = the same plus a world-space offset."""
    if isinstance(target[0], str):
        scene.frame_set(frame)
        name, off = target[0], target[1]
        ob = bpy.data.objects.get(name) or bpy.data.objects['J_' + name]
        p = ob.matrix_world @ Vector(off)
        if len(target) > 2:
            p = p + Vector(target[2])
        return p
    return Vector(target)

def cam_keys(ob, keys, scene):
    """keys: list of (second, loc, target, lens); the camera aims at the target at each key."""
    for sec, loc, target, lens in keys:
        f = F(sec)
        tgt = resolve(target, scene, f)
        loc = resolve(loc, scene, f)
        ob.location = loc; ob.keyframe_insert('location', frame=f)
        ob.rotation_euler = look_rot(loc, tgt); ob.keyframe_insert('rotation_euler', frame=f)
        ob.data.lens = lens; ob.data.keyframe_insert('lens', frame=f)
    C.set_interp(ob, 'BEZIER', 'EASE_IN_OUT')
    for fc in C.fcurves(ob):
        for kp in fc.keyframe_points:
            kp.handle_left_type = 'AUTO_CLAMPED'; kp.handle_right_type = 'AUTO_CLAMPED'

HEAD = ('neck', (0, -0.3, 1.2))
HATCH = ('RB_torso', (0, -1.9, 3.3))
CAMS = {
    's1_wide':    [(0.0, (-17, -52, 5.5), ('torso', (0, 0, 2.0)), 35), (7.0, (-16, -47, 5.3), ('torso', (0, 0, 2.0)), 36)],
    's2_shoulder': [(7.0, ('RB_pauldron.L', (-0.5, 0.2, 1.8), (-10.5, -10.5, 2.6)), ('RB_pauldron.L', (0.2, 0.2, 1.4)), 55),
                    (13.0, ('RB_pauldron.L', (-0.5, 0.2, 1.8), (-10.0, -10.0, 2.5)), ('RB_pauldron.L', (0.2, 0.2, 1.4)), 58)],
    's3_face':    [(13.0, ('neck', (0, -0.6, 1.0), (-5.5, -8.0, -3.0)), ('neck', (0, -0.6, 1.0)), 62), (18.0, ('neck', (0, -0.6, 1.0), (-5.2, -7.5, -2.8)), ('neck', (0, -0.6, 1.0)), 68)],
    's4_chest':   [(18.0, (4.5, -11.5, 6.0), HATCH, 60), (23.0, (4.2, -10.8, 6.0), HATCH, 66)],
    's5_tremble': [(23.0, (30, -44, 7.5), ('torso', (0, 0, 1.5)), 35), (28.0, (30, -44, 7.5), ('torso', (0, 0, 1.5)), 35)],
    's6_rise':    [(28.0, (-12, -31, 1.3), ('neck', (0, 0, 0.5)), 28), (32.6, (-12, -31, 1.3), ('neck', (0, 0, 0.5)), 28),
                   (36.4, (-12, -31, 1.3), ('neck', (0, 0, 0.0)), 28), (38.0, (-12, -31, 1.3), ('neck', (0, 0, 0.0)), 28)],
    's7_lookup':  [(38.0, (9, -16, 8.0), ('neck', (0, 0, 1.4)), 62), (43.0, (9, -16, 8.0), ('neck', (0, 0, 2.0)), 66)],
    's8_ignite':  [(43.0, (-30, -37, 2.5), ('torso', (0, 0, 2.0)), 32), (47.0, (-30, -37, 2.5), ('torso', (0, 0, 2.0)), 32)],
    's9_launch':  [(47.0, (-7, -21, 2.5), ('torso', (0, 0, 3)), 24), (47.45, (-7, -21, 2.5), ('torso', (0, 0, 3)), 24),
                   (48.3, (-7, -21, 2.5), ('torso', (0, 0, 3)), 24), (49.3, (-7, -21, 2.5), (2, 3, 60), 24)],
    's10_sky':    [(49.3, (-6, -20, 2.0), (2.5, 3.5, 60), 24), (56.0, (-6, -20, 2.0), (2.5, 3.5, 60), 24)],
}

def setup_cameras(scene):
    coll = C.coll('Cameras')
    cams = {}
    cur = scene.frame_current
    for name, keys in CAMS.items():
        ob = camera(name, coll)
        cam_keys(ob, keys, scene)
        cams[name] = ob
    for m in list(scene.timeline_markers):
        scene.timeline_markers.remove(m)
    for name, a, b in SHOTS:
        mk = scene.timeline_markers.new(name, frame=F(a))
        mk.camera = cams[name]
    scene.frame_start = 1
    scene.frame_end = END
    scene.camera = cams['s1_wide']
    scene.frame_set(cur)
    return cams

def shot_range(name):
    for n, a, b in SHOTS:
        if n == name:
            return F(a), F(b) - 1

# ---------------------------------------------------------------- lights, glows, shakes
def key_value(node_socket, frame, value):
    node_socket.default_value = value
    node_socket.keyframe_insert('default_value', frame=frame)

def animate_glows():
    """Chest core flickers on in shot 4, eyes wake in shot 5/6, everything blazes at the launch."""
    core = bpy.data.materials['RB_Core'].node_tree.nodes['Glow'].outputs[0]
    eye = bpy.data.materials['RB_Eye'].node_tree.nodes['Glow'].outputs[0]
    for mat in ('RB_Core', 'RB_Eye'):
        bpy.data.materials[mat].node_tree.animation_data_clear()
    for s, v in [(0, 0), (19.0, 0), (19.3, 0.35), (19.5, 0.0), (20.1, 0.0), (20.3, 0.55), (20.55, 0.1), (20.8, 0.7), (21.0, 0.25),
                 (21.4, 0.9), (21.7, 0.6), (22.4, 1.0), (46.0, 1.0), (47.0, 1.6), (56, 1.6)]:
        key_value(core, F(s), v)
    for s, v in [(0, 0), (26.4, 0), (26.7, 0.4), (26.9, 0.05), (27.3, 0.7), (27.5, 0.3), (28.0, 1.0), (56, 1.0)]:
        key_value(eye, F(s), v)
    for mat in ('RB_Core', 'RB_Eye'):
        ad = bpy.data.materials[mat].node_tree.animation_data
        if ad and ad.action:
            for fc in C.fcurves(bpy.data.materials[mat].node_tree):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'

def shake(cam_ob, start_s, end_s, amp_deg=0.35, scale=2.5, build=0.6):
    """Earth tremor: noise on the camera rotation between the two times, fading in and out."""
    for fc in C.fcurves(cam_ob):
        if fc.data_path != 'rotation_euler':
            continue
        m = fc.modifiers.new('NOISE')
        m.scale = scale
        m.strength = math.radians(amp_deg) * (1.0 if fc.array_index != 1 else 0.4)
        m.phase = 11 * (fc.array_index + 1)
        m.use_restricted_range = True
        m.frame_start = F(start_s); m.frame_end = F(end_s)
        m.blend_in = F(build); m.blend_out = F(build)

def animate_sun(sun, shade_card=None):
    """Backlight by default; in the face shot the sun swings to the front and a shade card slides off the face."""
    sun.animation_data_clear()
    def k(sec, elev, azim, df=0):
        sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(-azim))
        sun.keyframe_insert('rotation_euler', frame=F(sec) + df)
    k(0, 14, 135); k(13.0, 14, 135, -1)
    k(13.0, 50, 70); k(14.2, 50, 70); k(16.6, 5, -25); k(18.0, 5, -25, -1)
    k(18.0, 14, 135); k(56, 14, 135)
    for fc in C.fcurves(sun):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    if shade_card is not None:
        shade_card.animation_data_clear()
        # slides so the lit edge travels down the face between 14 s and 16.8 s
        shade_card.location = (0, 0, 0); shade_card.keyframe_insert('location', frame=F(13.0))
        shade_card.keyframe_insert('location', frame=F(14.0))
        shade_card.location = (0, 0, -9); shade_card.keyframe_insert('location', frame=F(16.8))
        shade_card.keyframe_insert('location', frame=F(17.99))
        C.set_interp(shade_card, 'BEZIER', 'EASE_IN_OUT')
        shade_card.hide_render = False
        # only exists in the face shot
        for sec, hide in ((0, True), (13.0, False), (18.0, True)):
            shade_card.hide_render = hide; shade_card.keyframe_insert('hide_render', frame=F(sec))
            shade_card.hide_viewport = hide; shade_card.keyframe_insert('hide_viewport', frame=F(sec))

def make_shade_card(scene):
    """A big occluder between the front sun and the robot's head (face shot only)."""
    name = 'ShadeCard'
    ob = bpy.data.objects.get(name)
    if ob is None:
        me = bpy.data.meshes.new(name)
        me.from_pydata([(-40, -40, 0), (40, -40, 0), (40, 40, 0), (-40, 40, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new(name, me)
        C.coll('FX').objects.link(ob)
    # a plane whose normal points to the sun of the face shot: sun azimuth -35, elevation 22
    e, a = math.radians(22), math.radians(-35)
    # light travel direction (see aw_shade.setup_sun): (cos e sin a, cos e cos a, -sin e)
    d = Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), -math.sin(e)))
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    # the card's origin sits at the head height; its edge passes through the face when location z = 0
    head = bpy.data.objects['J_neck'].matrix_world.translation + Vector((0, -0.3, 1.0))
    # offset the card so its edge (local -Y edge at y=-40) is near the face: shift by 40 along the local +Y after rotation
    rot = ob.rotation_euler.to_matrix()
    ob.location = head - d * 20 + rot @ Vector((0, 40 - 1.5, 0))
    ob.hide_render = True
    ob.visible_camera = False
    m = bpy.data.materials.get('FX_Shade') or bpy.data.materials.new('FX_Shade')
    m.use_nodes = True
    ob.data.materials.clear(); ob.data.materials.append(m)
    return ob
