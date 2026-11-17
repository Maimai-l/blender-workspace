import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_fab, mc_beanbag
for m in (mc_core, mc_site, mc_fab, mc_beanbag): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
if globals().get('ARRANGE'):
    print(mc_beanbag.arrange())
else:
    print(mc_beanbag.build(only=globals().get('ONLY')), '%.1fs' % (time.time() - t0))
