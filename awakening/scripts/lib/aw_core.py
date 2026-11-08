"""Core helpers for the Awakening anime scene (Blender 5.2, EEVEE)."""
import bpy, math, zlib, os, random
from mathutils import Vector, Euler, Matrix

ROOT = r'C:\Users\blender\Documents\awakening'
TEX = ROOT + r'\tex'
BLEND = ROOT + r'\awakening.blend'
FPS = 24

def seed(name):
    return zlib.crc32(name.encode()) & 0xffffffff

def rng(name):
    return random.Random(seed(name))

def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c

def link(obj, c):
    for uc in list(obj.users_collection):
        uc.objects.unlink(obj)
    c.objects.link(obj)
    return obj

def clear_collection(name):
    c = bpy.data.collections.get(name)
    if not c:
        return
    for o in list(c.all_objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for ch in list(c.children):
        clear_collection(ch.name)
        bpy.data.collections.remove(ch)

def purge():
    for _ in range(3):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

def new_mesh_obj(name, verts, faces, c=None, edges=()):
    me = bpy.data.meshes.new(name)
    me.from_pydata([Vector(v) for v in verts], list(edges), [list(f) for f in faces])
    me.update()
    ob = bpy.data.objects.new(name, me)
    (c or bpy.context.scene.collection).objects.link(ob)
    return ob

def empty(name, loc=(0, 0, 0), parent=None, c=None, size=0.3):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = 'PLAIN_AXES'
    e.empty_display_size = size
    e.location = loc
    (c or bpy.context.scene.collection).objects.link(e)
    if parent:
        e.parent = parent
    return e

def set_parent(child, parent, keep=False):
    if keep:
        mw = child.matrix_world.copy()
        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()
    else:
        child.parent = parent

def smooth(ob, angle=None):
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    if angle is not None:
        # Blender 4.1+: smooth by angle is a modifier/op; use the attribute-free op
        bpy.context.view_layer.objects.active = ob
        try:
            with bpy.context.temp_override(object=ob, selected_editable_objects=[ob]):
                bpy.ops.object.shade_smooth_by_angle(angle=angle)
        except Exception:
            pass

def bevel(ob, width=0.03, segments=2, angle=math.radians(40), name='bev'):
    m = ob.modifiers.new(name, 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = angle
    m.harden_normals = True
    return m

def view_update():
    bpy.context.view_layer.update()

def node_group(name):
    return bpy.data.node_groups.get(name)

def img_load(path, name=None, alpha=True):
    name = name or os.path.basename(path)
    im = bpy.data.images.get(name)
    if im is None or im.filepath != path:
        im = bpy.data.images.load(path, check_existing=True)
        im.name = name
    if alpha:
        im.alpha_mode = 'STRAIGHT'
    return im

def key(ob, frame, loc=None, rot=None, scale=None):
    if loc is not None:
        ob.location = loc
        ob.keyframe_insert('location', frame=frame)
    if rot is not None:
        ob.rotation_euler = [math.radians(a) for a in rot]
        ob.keyframe_insert('rotation_euler', frame=frame)
    if scale is not None:
        ob.scale = scale
        ob.keyframe_insert('scale', frame=frame)

def fcurves(ob):
    ad = ob.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    out = []
    # Blender 4.4+ layered actions: fcurves live in channelbags
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    out.extend(cb.fcurves)
    except Exception:
        pass
    if not out:
        try:
            out = list(act.fcurves)
        except Exception:
            pass
    return out

def stepped(ob, step=2, offset=0):
    """Animate on twos: stepped F-modifier on every F-curve of the object."""
    for fc in fcurves(ob):
        has = any(m.type == 'STEPPED' for m in fc.modifiers)
        if not has:
            m = fc.modifiers.new('STEPPED')
            m.frame_step = step
            m.frame_offset = offset

def set_interp(ob, interp='BEZIER', easing='AUTO'):
    for fc in fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = interp
            kp.easing = easing
