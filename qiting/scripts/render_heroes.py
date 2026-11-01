# Render beauty shots from lib/heroes.py. Set NAMES (list), SAMPLES, SCALE (resolution factor) before running.
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
exec(open(os.path.join(LIB, 'heroes.py'), encoding='utf-8').read())
names = globals().get('NAMES') or list(HEROES)
samples = globals().get('SAMPLES', 64)
scale = globals().get('SCALE', 0.5)
sc = bpy.context.scene
for n in names:
    V = HEROES[n]
    t0 = time.time()
    xy_light.setup_world(sun_elev=V.get('elev', 38), sun_azim=V.get('azim', 225), strength=V.get('sky', 0.08),
                         sun_strength=V.get('sun', 5.0), cam_sat=1.0, cam_val=1.0, sun_angle=2.0)
    if 'sun_color' in V:
        bpy.data.objects['XY_Sun'].data.color = V['sun_color']
    W, H = V['res']
    xy_light.setup_render(samples=samples, res=(int(W * scale), int(H * scale)), exposure=V.get('exposure', 0.15),
                          look='AgX - Medium High Contrast')
    cam = xy_light.camera('CAM_效果_' + n.replace('hero_', ''), V['loc'], target=V['target'], lens=V.get('lens', 35))
    cam.data.clip_start = 0.1; cam.data.clip_end = 40000
    p = os.path.join(xy_core.ROOT, 'renders', n + '.png')
    xy_light.render_to(p, cam)
    img = bpy.data.images.load(p, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
    img.save_render(p.replace('.png', '.jpg'), scene=sc); bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    print(n, '%.1fs' % (time.time() - t0))
