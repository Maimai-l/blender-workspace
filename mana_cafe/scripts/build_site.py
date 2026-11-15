"""Terrace: dry-stone walls, flagstone paving and its bed."""
import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_stone
for m in (mc_core, mc_site, mc_stone): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
t0 = time.time()
o, n = mc_stone.build_walls(); print('walls', n, 'stones', len(o.data.polygons), 'faces %.1fs' % (time.time() - t0))
o, n = mc_stone.build_paving(); print('paving', n, 'slabs', len(o.data.polygons), 'faces %.1fs' % (time.time() - t0))
mc_stone.build_paving_bed()
for me in [m for m in bpy.data.meshes if m.users == 0 and m.name.startswith('MC_')]: bpy.data.meshes.remove(me)
# the old site's leftover wall pieces are not part of the building: out of the render
for nme in ('G-Object.021','G-Object.022','G-Object.023','G-Object.024','G-Object.025','G-Object.026','G-Object.027','G-Object.028','G-Object.029','G-Object.031','G-Object.045'):
    ob = bpy.data.objects.get(nme)
    if ob: ob.hide_render = True; ob.hide_viewport = True
print('site built %.1fs' % (time.time() - t0))
