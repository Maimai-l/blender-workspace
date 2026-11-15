"""Meadow scatter round the cafe."""
import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_assets, mc_stone, mc_ground
for m in (mc_core, mc_site, mc_assets, mc_stone, mc_ground): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
print(mc_ground.build(density=globals().get('DENSITY', 1.0)), '%.1fs' % (time.time() - t0))
