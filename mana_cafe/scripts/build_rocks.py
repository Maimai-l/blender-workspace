import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_fab, mc_stone, mc_ground, mc_rocks
for m in (mc_core, mc_site, mc_fab, mc_stone, mc_ground, mc_rocks): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
for row in mc_rocks.build(): print('  ', row)
print('rocks %.1fs' % (time.time() - t0))
