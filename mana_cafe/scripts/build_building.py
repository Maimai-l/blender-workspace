"""Apply the cafe's materials and interior lights."""
import bpy, sys, importlib
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_building
for m in (mc_core, mc_site, mc_building): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
mc_building.apply()
print('building materials applied')
