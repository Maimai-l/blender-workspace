# Final file state: rename the comparison cameras, drop inspection cameras, default daylight, Cycles GPU settings,
# active beauty camera, collection order, purge unused data, save C:\Users\blender\Documents\qiting\qiting.blend.
import sys, importlib, bpy, os
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
TARGET = os.path.join(xy_core.ROOT, 'qiting.blend')
if bpy.data.filepath.lower() != TARGET.lower():
    raise SystemExit('open file is %r, not %s' % (bpy.data.filepath, TARGET))
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type == 'CAMERA' and o.name.startswith('CAM_cmp_'):
        o.name = 'CAM_对照_' + o.name[len('CAM_cmp_'):]
    elif o.type == 'CAMERA' and o.name in ('CAM_insp',):
        bpy.data.objects.remove(o, do_unlink=True)
cams = xy_core.coll('灯光与相机')
for o in bpy.data.objects:
    if o.type in ('CAMERA', 'LIGHT'):
        xy_core.link(o, cams)
xy_light.setup_world(sun_elev=38, sun_azim=225, strength=0.08, sun_strength=5.0, cam_sat=1.0, cam_val=1.0, sun_angle=2.0)
xy_light.setup_render(samples=256, res=(1920, 1080), exposure=0.15, look='AgX - Medium High Contrast')
cam = bpy.data.objects.get('CAM_效果_sw')
if cam:
    sc.camera = cam
sc.render.filepath = os.path.join(xy_core.ROOT, 'renders', 'render_')
# top-level collection order: parts first, then helpers
order = ['屋面', '檐下', '柱与墙身', '台基', '台阶与栏杆', '匾联', '地面', '临时背景（非复刻内容）', '灯光与相机', '_LIB']
root = sc.collection
for n in order:
    c = bpy.data.collections.get(n)
    if c and c.name in root.children:
        root.children.unlink(c); root.children.link(c)
bpy.data.orphans_purge(do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=TARGET)
print('saved', bpy.data.filepath, os.path.getsize(bpy.data.filepath) // 1024, 'KB')
print('collections', [c.name for c in root.children])
print('cameras', sorted(o.name for o in bpy.data.objects if o.type == 'CAMERA'))
print('objects', len(bpy.data.objects), 'materials', len(bpy.data.materials))
