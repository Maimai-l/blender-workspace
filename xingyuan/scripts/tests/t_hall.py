import sys, importlib, bpy, time
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_mats, xy_roof, xy_parts, xy_site, xy_hall
for m in (xy_core, xy_mats, xy_roof, xy_parts, xy_site, xy_hall): importlib.reload(m)
t0 = time.time()
xy_core.clear_coll('TEST')
for n in [o.name for o in bpy.data.objects if o.name.startswith('SRC_')]:
    o = bpy.data.objects[n]; bpy.data.objects.remove(o, do_unlink=True)
xy_hall.build_hall('A1', 43.6, 0.36, 0, 12.05, 23.1, 7, front_doors=(2, 3, 4), open_bay=3)
print('built in %.2fs' % (time.time() - t0))
print(len(bpy.data.objects), 'objects')
