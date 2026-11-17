"""Meadow scatter round the cafe."""
import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_assets, mc_fab, mc_stone, mc_ground, mc_rocks
for m in (mc_core, mc_site, mc_assets, mc_fab, mc_stone, mc_ground, mc_rocks): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
print(mc_ground.build_fab(density=globals().get('DENSITY', 1.0)), '%.1fs' % (time.time() - t0))
dg = bpy.context.evaluated_depsgraph_get()
cnt = {}
for inst in dg.object_instances:
    if inst.is_instance and inst.parent:
        cnt[inst.parent.name] = cnt.get(inst.parent.name, 0) + 1
print('instances', cnt, sum(cnt.values()))
