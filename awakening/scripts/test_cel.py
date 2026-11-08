import bpy, sys, math, importlib, time
LIB = r'C:\Users\blender\Documents\awakening\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import aw_core as C, aw_shade as S
importlib.reload(C); importlib.reload(S)
sc = bpy.context.scene
# fresh scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
C.purge()
S.setup_render(sc, 960, 540, samples=16)
S.setup_world(sc)
sun = S.setup_sun(sc, azim=55, elev=18)
rob = C.coll('Robot')
armor = S.cel_material('ArmorTest', (0.42, 0.50, 0.44), spec=0.6)
rust = S.cel_material('RustTest', (0.55, 0.30, 0.16))
def box(name, size, loc, mat, bev=0.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object; ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(scale=True)
    C.bevel(ob, bev, 2)
    ob.data.materials.append(mat)
    C.link(ob, rob)
    return ob
torso = box('torso', (2.2, 1.4, 2.4), (0, 0, 3.0), armor)
head = box('head', (1.0, 0.9, 0.9), (0, -0.2, 4.9), armor)
sh1 = box('shoulderL', (0.9, 1.0, 1.0), (-1.7, 0, 3.9), rust)
sh2 = box('shoulderR', (0.9, 1.0, 1.0), (1.7, 0, 3.9), armor)
arm1 = box('armL', (0.6, 0.6, 2.4), (-1.8, 0, 2.2), armor)
arm2 = box('armR', (0.6, 0.6, 2.4), (1.8, 0, 2.2), armor)
# cylinder joint
bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=0.5, location=(0, 0, 1.6), rotation=(0, 0, 0))
pel = bpy.context.active_object; pel.name = 'pelvis'; pel.data.materials.append(rust); C.link(pel, rob)
C.smooth(pel, math.radians(40))
# ground
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
gnd = bpy.context.active_object; gnd.name = 'ground'
gnd.data.materials.append(S.cel_material('GroundTest', (0.30, 0.38, 0.22)))
S.setup_freestyle(sc, 'Robot', thickness=2.2)
# camera
cam = bpy.data.cameras.new('Cam'); co = bpy.data.objects.new('Cam', cam); sc.collection.objects.link(co)
co.location = (6, -11, 3.2); co.rotation_euler = (math.radians(82), 0, math.radians(29)); cam.lens = 40
sc.camera = co
sc.render.filepath = r'C:\Users\blender\Documents\awakening\renders\test_cel.png'
t0 = time.time()
bpy.ops.render.render(write_still=True)
print('rendered %.1fs' % (time.time() - t0))
