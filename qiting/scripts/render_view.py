# Render one view. Set VIEW before running: name, loc, target, lens, roll, res, samples; optional elev, azim, sky, sun,
# exposure, look, shift, clip, hide (object name prefixes hidden for this render), thin (plan polygon: planting and
# lamp instances inside it are left out of this render), ky (vertical pixel scale), defer (render from a timer).
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
try:
    import qt_haze; importlib.reload(qt_haze)
    HD = qt_haze.DEFAULTS
    qt_haze.setup(color=V.get('haze_color', HD['color']), start=V.get('haze_start', HD['start']),
                  depth=V.get('haze_depth', HD['depth']), strength=V.get('haze', HD['strength']),
                  gamma=V.get('haze_gamma', HD['gamma']), enable=V.get('haze', HD['strength']) > 0)
except Exception as e:
    print('haze', e)
xy_light.setup_render(samples=V.get('samples', 64), res=V.get('res', (1280, 720)), exposure=V.get('exposure', 0.15),
                      look=V.get('look', 'AgX - Medium High Contrast'))
cam = xy_light.camera('CAM_' + V['name'], V['loc'], target=V['target'], lens=V.get('lens', 35), shift=V.get('shift', (0, 0)),
                      roll=V.get('roll', 0.0))
if V.get('ky', 1.0) != 1.0:            # stretched photo: render with non-square pixels so the frame matches
    # ky stretches the picture vertically (tools/calq.py); in Blender that is a wider pixel (aspect x = ky):
    # each row then spans 1/ky of the angle it would with square pixels
    sc.render.pixel_aspect_x, sc.render.pixel_aspect_y = V['ky'], 1.0
else:
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
cam.data.clip_start = V.get('clip', 0.1)
cam.data.clip_end = 5000
hidden = [o for o in bpy.data.objects if any(o.name.startswith(h) for h in V.get('hide', ())) and not o.hide_render]
for o in hidden:
    o.hide_render = True
# 'thin': drop the planting, shrub and lamp instances inside a plan polygon for this render only (older photos taken
# before the trees grew: the model keeps the planting the 2026 aerials show)
swapped = []
if V.get('thin'):
    _poly = [tuple(p) for p in V['thin']]

    def _contains(x, y):
        c = False
        j = len(_poly) - 1
        for i in range(len(_poly)):
            (xi, yi), (xj, yj) = _poly[i], _poly[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                c = not c
            j = i
        return c
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith(('QT_trees_', 'QT_far_trees_', 'QT_shrubs_', 'QT_lamps_', 'QT_hedges')) and len(o.data.vertices):
            me0 = o.data
            co = [(v.co.x, v.co.y) for v in me0.vertices]
            inside = [_contains(x, y) for x, y in co]
            if not any(inside):
                continue
            import bmesh as _bm
            bm = _bm.new(); bm.from_mesh(me0)
            bm.verts.ensure_lookup_table()
            _bm.ops.delete(bm, geom=[bm.verts[i] for i in range(len(co)) if inside[i]], context='VERTS')
            me1 = bpy.data.meshes.new(me0.name + '_thin'); bm.to_mesh(me1); bm.free()
            o.data = me1
            swapped.append((o, me0, me1))
out = os.path.join(xy_core.ROOT, 'renders', V['name'] + '.png')
jp = out.replace('.png', '.jpg')
marker = jp + '.done'
if os.path.exists(marker):
    os.remove(marker)


def _finish():
    t0 = time.time()
    try:
        xy_light.render_to(out, cam)
    finally:
        for o in hidden:
            o.hide_render = False
        for o, me0, me1 in swapped:
            o.data = me0
            bpy.data.meshes.remove(me1)
    img = bpy.data.images.load(out, check_existing=False)
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 92
    img.save_render(jp, scene=sc)
    bpy.data.images.remove(img)
    sc.render.image_settings.file_format = 'PNG'
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    msg = 'render %.1fs %s' % (time.time() - t0, jp)
    with open(marker, 'w') as fh:
        fh.write(msg)
    print(msg)
    return None


def _finish_safe():
    try:
        _finish()
    except Exception:
        import traceback
        with open(marker, 'w') as fh:
            fh.write('FAILED\n' + traceback.format_exc())
    return None


if V.get('defer'):
    # long renders: return at once and render from a timer, so the MCP reply cannot time out; the caller polls
    # for <jpg>.done (tools/cmpview.py does this through exec)
    bpy.app.timers.register(_finish_safe, first_interval=0.5)
    print('render deferred', jp)
else:
    _finish()
