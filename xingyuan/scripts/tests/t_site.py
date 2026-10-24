import sys, importlib, bpy, time
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_mats, xy_site, xy_layout, xy_build_site
for m in (xy_core, xy_mats, xy_site, xy_layout, xy_build_site): importlib.reload(m)
xy_mats.build_all()
t0 = time.time()
xy_build_site.build_site()
print('site built in %.1fs' % (time.time() - t0))
