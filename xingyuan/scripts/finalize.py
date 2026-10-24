# Final file state: default daylight, Cycles GPU render settings, active hero camera, save.
import sys, importlib, bpy, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
sc = bpy.context.scene
xy_light.setup_world(sun_elev=40, sun_azim=140)
xy_light.setup_render(samples=256, res=(1920, 1080), exposure=0.55, look='AgX - Medium High Contrast')
cam = bpy.data.objects.get('CAM_效果_B1')
if cam:
    sc.camera = cam
sc.render.filepath = os.path.join(xy_core.ROOT, 'renders', 'render_')
bpy.data.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(xy_core.ROOT, 'xingyuan.blend'))
cams = sorted(o.name for o in bpy.data.objects if o.type == 'CAMERA')
print('saved', bpy.data.filepath, os.path.getsize(bpy.data.filepath) // 1024, 'KB')
print('cameras', cams)
print('objects', len(bpy.data.objects), 'materials', len(bpy.data.materials))
print('renders dir', sorted(os.listdir(os.path.join(xy_core.ROOT, 'renders')))[:60])
