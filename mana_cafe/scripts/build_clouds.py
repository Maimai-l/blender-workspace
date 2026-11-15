import bpy, sys, importlib
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_clouds
for m in (mc_core, mc_clouds): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
print('clouds', mc_clouds.build(globals().get('WHICH')))
