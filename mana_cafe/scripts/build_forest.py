import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_assets, mc_mats, mc_trees
for m in (mc_core, mc_assets, mc_mats, mc_trees): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
o, n = mc_trees.build(); print('forest', n, 'trees %.1fs' % (time.time() - t0))
