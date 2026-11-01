# Render one view. Set VIEW before running: name, loc, target, lens, roll, res, samples; optional elev, azim, sky, sun,
# exposure, look, shift, clip, hide (object name prefixes hidden for this render).
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
V = globals().get('VIEW')
sc = bpy.context.scene
xy_light.setup_world(sun_elev=V.get('elev', 38), sun_azim=V.get('azim', 225), strength=V.get('sky', 0.08),
                     sun_strength=V.get('sun', 5.0), cam_sat=V.get('cam_sat', 1.0), cam_val=V.get('cam_val', 1.0),
                     sun_angle=V.get('sun_angle', 2.0))
if 'sun_color' in V:
    bpy.data.objects['XY_Sun'].data.color = V['sun_color']
xy_light.setup_render(samples=V.get('samples', 64), res=V.get('res', (1280, 720)), exposure=V.get('exposure', 0.15),
                      look=V.get('look', 'AgX - Medium High Contrast'))
cam = xy_light.camera('CAM_' + V['name'], V['loc'], target=V['target'], lens=V.get('lens', 35), shift=V.get('shift', (0, 0)),
                      roll=V.get('roll', 0.0))
cam.data.clip_start = V.get('clip', 0.1)
cam.data.clip_end = 5000
hidden = [o for o in bpy.data.objects if any(o.name.startswith(h) for h in V.get('hide', ())) and not o.hide_render]
for o in hidden:
    o.hide_render = True
t0 = time.time()
out = os.path.join(xy_core.ROOT, 'renders', V['name'] + '.png')
try:
    xy_light.render_to(out, cam)
finally:
    for o in hidden:
        o.hide_render = False
img = bpy.data.images.load(out, check_existing=False)
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 92
jp = out.replace('.png', '.jpg')
img.save_render(jp, scene=sc)
bpy.data.images.remove(img)
sc.render.image_settings.file_format = 'PNG'
print('render %.1fs' % (time.time() - t0), jp)
