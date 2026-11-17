"""(Re)load the terrain meshes built by scripts/proc into the open scene."""
import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_terrain
for m in (mc_core, mc_terrain): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
WHAT = globals().get('WHAT', ('near', 'far'))
mat = bpy.data.materials.get('MC_mountain') or mc_terrain.mountain_material()
for w in WHAT:
    o = getattr(mc_terrain, 'load_' + w)(mat=mat)
    print(w, 'loaded', len(o.data.vertices), len(o.data.polygons), '%.1fs' % (time.time() - t0))
for me in [m for m in bpy.data.meshes if m.users == 0 and m.name.startswith('TER_')]:
    bpy.data.meshes.remove(me)
