# Render beauty shots from lib/heroes.py. Set NAMES (list), SAMPLES, SCALE (resolution factor) before running.
# The shots render one after another from Blender timers, so this call returns at once (an MCP reply cannot
# outlast the tunnel's timeout); each shot writes renders/<name>.jpg.done when it is saved, and the batch ends
# with renders/heroes.done. tools/heroes_run.py starts a batch and waits for the markers through exec.
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
exec(open(os.path.join(LIB, 'heroes.py'), encoding='utf-8').read())
names = list(globals().get('NAMES') or list(HEROES))
samples = globals().get('SAMPLES', 64)
scale = globals().get('SCALE', 0.5)
sc = bpy.context.scene
RD = os.path.join(xy_core.ROOT, 'renders')
for n in names + ['heroes']:
    mk = os.path.join(RD, n + ('.done' if n == 'heroes' else '.jpg.done'))
    if os.path.exists(mk):
        os.remove(mk)


def render_one(n):
    V = HEROES[n]
    t0 = time.time()
    xy_light.setup_world(sun_elev=V.get('elev', 38), sun_azim=V.get('azim', 225), strength=V.get('sky', 0.08),
                         sun_strength=V.get('sun', 5.0), cam_sat=1.0, cam_val=1.0, sun_angle=2.0)
    if 'sun_color' in V:
        bpy.data.objects['XY_Sun'].data.color = V['sun_color']
    try:
        import qt_haze; importlib.reload(qt_haze)
        HD = qt_haze.DEFAULTS
        qt_haze.setup(color=V.get('haze_color', HD['color']), start=V.get('haze_start', HD['start']),
                      depth=V.get('haze_depth', HD['depth']), strength=V.get('haze', HD['strength']),
                      gamma=V.get('haze_gamma', HD['gamma']), enable=V.get('haze', HD['strength']) > 0)
    except Exception as e:
        print('haze', e)
    W, H = V['res']
    xy_light.setup_render(samples=V.get('samples', samples), res=(int(W * scale), int(H * scale)), exposure=V.get('exposure', 0.15),
                          look='AgX - Medium High Contrast')
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    loc = tuple(V['loc'])
    if 'eye' in V:                      # camera height given above the terrain
        import qt_env
        loc = (loc[0], loc[1], qt_env.height(loc[0], loc[1]) + V['eye'])
    cam = xy_light.camera('CAM_效果_' + n.replace('hero_', ''), loc, target=V['target'], lens=V.get('lens', 35))
    cam.data.clip_start = 0.1; cam.data.clip_end = 40000
    p = os.path.join(RD, n + '.png')
    xy_light.render_to(p, cam)
    img = bpy.data.images.load(p, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 92
    jp = p.replace('.png', '.jpg')
    img.save_render(jp, scene=sc); bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    msg = '%s %.1fs' % (n, time.time() - t0)
    with open(jp + '.done', 'w') as fh:
        fh.write(msg)
    print(msg)


queue = list(names)


def _next():
    if not queue:
        with open(os.path.join(RD, 'heroes.done'), 'w') as fh:
            fh.write('done %d' % len(names))
        return None
    n = queue.pop(0)
    try:
        render_one(n)
    except Exception as e:
        with open(os.path.join(RD, n + '.jpg.done'), 'w') as fh:
            fh.write('FAILED %s: %r' % (n, e))
    return 0.5


bpy.app.timers.register(_next, first_interval=0.5)
print('heroes deferred', names)
