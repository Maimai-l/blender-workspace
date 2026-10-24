import sys, importlib, bpy, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
exec(open(os.path.join(LIB, 'views.py'), encoding='utf-8').read())
looks = [l.identifier for l in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items]
print('looks', looks)
sc = bpy.context.scene
try:
    sc.view_settings.view_transform = 'AgX'
except Exception as e:
    print(e)
print('looks for AgX', [l for l in looks])
V = VIEWS['B1court']
cam = xy_light.camera('CAM_cmp_B1court', V['loc'], target=V['target'], lens=V['lens'])
def pick(sub):
    for l in looks:
        if sub.lower() in l.lower():
            return l
    return 'None'
variants = [('e', 0.15, 5.0, 0.6, 0.55, 0.4, 'None'), ('f', 0.15, 5.0, 0.6, 0.55, 0.4, 'AgX - Medium High Contrast'),
            ('g', 0.15, 5.0, 0.7, 0.55, 0.4, 'AgX - High Contrast'), ('h', 0.15, 5.0, 0.5, 0.55, 0.4, 'AgX - Punchy')]
for (k, sky, sun, exp, ds, dust, look) in variants:
    xy_light.setup_world(sun_elev=V['elev'], sun_azim=V['azim'], strength=sky, sun_strength=sun, desat=ds, dust=dust)
    xy_light.setup_render(samples=32, res=(560, 418), exposure=exp, look=look)
    p = os.path.join(xy_core.ROOT, 'renders', 'lt_%s.png' % k)
    xy_light.render_to(p, cam)
    img = bpy.data.images.load(p, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    img.save_render(p.replace('.png', '.jpg'), scene=sc); bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    print(k, look)
sc.view_settings.look = 'None'
