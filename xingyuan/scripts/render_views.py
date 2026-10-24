# Render a list of comparison views. Set NAMES (list) and optionally SAMPLES / SCALE before running.
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
exec(open(os.path.join(LIB, 'views.py'), encoding='utf-8').read())
names = globals().get('NAMES') or list(VIEWS)
samples = globals().get('SAMPLES', 64)
scale = globals().get('SCALE', 0.7)
sc = bpy.context.scene
out = []
for n in names:
    V = VIEWS[n]
    t0 = time.time()
    xy_light.setup_world(sun_elev=V.get('elev', 42), sun_azim=V.get('azim', 200), strength=V.get('sky', 0.15), sun_strength=V.get('sun', 5.0))
    W, H = V['res']
    xy_light.setup_render(samples=samples, res=(int(W * scale), int(H * scale)), exposure=V.get('exposure', 0.6))
    cam = xy_light.camera('CAM_cmp_' + n, V['loc'], target=V['target'], lens=V.get('lens', 35), shift=V.get('shift', (0, 0)),
                          roll=V.get('roll', 0.0))
    cam.data.clip_start = V.get('clip', 0.1)
    p = os.path.join(xy_core.ROOT, 'renders', 'cmp_%s.png' % n)
    xy_light.render_to(p, cam)
    img = bpy.data.images.load(p, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 90
    jp = p.replace('.png', '.jpg'); img.save_render(jp, scene=sc); bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    out.append(jp)
    print(n, '%.1fs' % (time.time() - t0))
