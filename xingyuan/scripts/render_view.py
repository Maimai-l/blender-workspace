# usage: set VIEW dict before running: name, loc, target, lens, res, samples
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
V = globals().get('VIEW')
sc = bpy.context.scene
if not sc.world or not any(n.type == 'TEX_SKY' for n in sc.world.node_tree.nodes):
    xy_light.setup_world(sun_elev=V.get('elev', 42), sun_azim=V.get('azim', 215), strength=V.get('sky', 0.03), sun_strength=4.0)
if V.get('relight'):
    xy_light.setup_world(sun_elev=V.get('elev', 42), sun_azim=V.get('azim', 215), strength=V.get('sky', 0.03), sun_strength=V.get('sun', 4.0))
xy_light.setup_render(samples=V.get('samples', 64), res=V.get('res', (1280, 720)), exposure=V.get('exposure', 0.0),
                      look=V.get('look'))
cam = xy_light.camera('CAM_' + V['name'], V['loc'], target=V['target'], lens=V.get('lens', 35), shift=V.get('shift', (0, 0)), roll=V.get('roll', 0.0))
cam.data.clip_start = V.get('clip', 0.1)
t0 = time.time()
out = os.path.join(xy_core.ROOT, 'renders', V['name'] + '.png')
xy_light.render_to(out, cam)
img = bpy.data.images.load(out, check_existing=False)
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 92
jp = out.replace('.png', '.jpg')
img.save_render(jp, scene=sc)
bpy.data.images.remove(img)
sc.render.image_settings.file_format = 'PNG'
print('render %.1fs' % (time.time() - t0), jp)
