import bpy, sys, math, importlib, time
LIB = r'C:\Users\blender\Documents\awakening\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import aw_core as C, aw_shade as S, aw_mesh as M, aw_robot as R
for m in (C, S, M, R): importlib.reload(m)
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name not in ('Sun', 'Cam', 'ground'):
        bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.materials):
    if m.name.startswith('RB_'): bpy.data.materials.remove(m)
C.purge()
E, parts = R.build()
R.pose(E, R.STAND, root=(0, 0, 0))
print('parts', len(parts), 'faces', sum(len(p.data.polygons) for p in parts))
# ground
if 'ground' not in bpy.data.objects:
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    g = bpy.context.active_object; g.name = 'ground'
    g.data.materials.append(S.cel_material('GroundTest', (0.30, 0.38, 0.22)))
S.setup_freestyle(sc, 'Robot', thickness=2.4)
bpy.data.objects['Sun'].data.energy = math.pi
sun = bpy.data.objects['Sun']; sun.rotation_euler = (math.radians(90 - 22), 0, math.radians(-50))
cam = bpy.data.objects['Cam']
def shoot(name, loc, rot, lens=35):
    cam.location = loc; cam.rotation_euler = [math.radians(a) for a in rot]; cam.data.lens = lens
    sc.render.filepath = r'C:\Users\blender\Documents\awakening\renders\%s.png' % name
    t0 = time.time(); bpy.ops.render.render(write_still=True); print(name, '%.1fs' % (time.time() - t0))
shoot('rb_front', (6, -30, 9), (84, 0, 11), 40)
shoot('rb_side', (-30, -6, 9), (84, 0, -79), 40)
