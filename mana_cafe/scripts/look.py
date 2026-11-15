"""Apply world, sun, render settings and the landscape materials (no geometry changes)."""
import bpy, sys, importlib
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_mats, mc_light
for m in (mc_core, mc_mats, mc_light): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
mc_light.world(**globals().get('WORLD', {}))
mc_light.sun(**globals().get('SUN', {}))
mc_light.render_settings(**globals().get('RS', {}))
mat = mc_mats.mountain_material(P=globals().get('MP'))
for n in ('TER_far', 'TER_near'):
    o = bpy.data.objects.get(n)
    if o:
        o.data.materials.clear(); o.data.materials.append(mat)
cam = bpy.data.objects['CAM_sketch']; cam.data.lens = 24.0
print('look applied')
