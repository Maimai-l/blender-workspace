# Render a list of ad-hoc views: set SHOTS = [(name, loc, target, lens, (w,h)), ...], SAMPLES, EXPOSURE
import sys, importlib, bpy, os, time
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
sc = bpy.context.scene
xy_light.setup_world(sun_elev=globals().get('ELEV', 42), sun_azim=globals().get('AZIM', 135))
for (n, loc, tgt, lens, res) in SHOTS:
    t0 = time.time()
    xy_light.setup_render(samples=globals().get('SAMPLES', 48), res=res, exposure=globals().get('EXPOSURE', 0.6))
    cam = xy_light.camera('CAM_insp', loc, target=tgt, lens=lens)
    p = os.path.join(xy_core.ROOT, 'renders', n + '.png')
    xy_light.render_to(p, cam)
    img = bpy.data.images.load(p, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    img.save_render(p.replace('.png', '.jpg'), scene=sc); bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    print(n, '%.1fs' % (time.time() - t0))
