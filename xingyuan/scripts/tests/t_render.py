import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
xy_light.setup_world(sun_elev=40, sun_azim=235, strength=1.0, sun_strength=4.0)
xy_light.setup_render(samples=96, res=(1280, 720))
cam = xy_light.camera('CAM_test', (34.0, 9.0, 1.7), target=(44.5, 13.0, 3.2), lens=24)
t0 = time.time()
out = os.path.join(xy_core.ROOT, 'renders', 'test_A1.png')
xy_light.render_to(out, cam)
# convert to jpg for transfer
img = bpy.data.images.load(out, check_existing=False)
img.file_format = 'JPEG'
sc = bpy.context.scene
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 90
jp = out.replace('.png', '.jpg')
img.save_render(jp, scene=sc)
bpy.data.images.remove(img)
sc.render.image_settings.file_format = 'PNG'
print('render %.1fs' % (time.time() - t0), jp)
