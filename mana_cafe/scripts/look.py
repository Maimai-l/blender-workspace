"""Apply world, sun, render settings and the landscape materials (no geometry changes)."""
import bpy, sys, importlib
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_site, mc_building, mc_mats, mc_light
for m in (mc_core, mc_site, mc_building, mc_mats, mc_light): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
mc_light.world(**globals().get('WORLD', {}))
mc_light.sun(**globals().get('SUN', {}))
mc_light.render_settings(**globals().get('RS', {}))
print(mc_light.grade(**globals().get('GRADE', {})))
for n, near in (('TER_far', False), ('TER_near', True)):
    o = bpy.data.objects.get(n)
    if o:
        mat = mc_mats.mountain_material('MC_ground' if near else 'MC_mountain', P=globals().get('MP'), near=near)
        o.data.materials.clear(); o.data.materials.append(mat)
mc_light.camera(**globals().get('CAM', {}))
print('look applied')
