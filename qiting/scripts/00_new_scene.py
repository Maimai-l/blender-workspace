# Create a fresh scene for the Qiting model and save it as a new file.
# Refuses to run when Blender has another saved file open, so no other project is touched.
import bpy, os
ROOT = r'C:\Users\blender\Documents\qiting'
TARGET = os.path.join(ROOT, 'qiting.blend')
cur = bpy.data.filepath
print('open file before:', repr(cur), 'objects:', len(bpy.data.objects), 'dirty:', bpy.data.is_dirty)
if cur and os.path.normcase(cur) != os.path.normcase(TARGET):
    raise SystemExit('another file is open: ' + cur)
if not cur and len(bpy.data.objects) > 3:
    raise SystemExit('unsaved scene with %d objects is open; not touching it' % len(bpy.data.objects))
for sub in ('', 'lib', 'renders', 'refs', 'cache'):
    os.makedirs(os.path.join(ROOT, sub), exist_ok=True)
old_scenes = list(bpy.data.scenes)
new = bpy.data.scenes.new('Qiting')
for w in bpy.context.window_manager.windows:
    w.scene = new
for sc in old_scenes:
    bpy.data.scenes.remove(sc)
for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
             bpy.data.collections, bpy.data.images, bpy.data.node_groups, bpy.data.worlds, bpy.data.textures,
             bpy.data.curves):
    for b in list(coll):
        try:
            coll.remove(b)
        except Exception as e:
            print('skip', b.name, e)
bpy.data.orphans_purge(do_recursive=True)
new.unit_settings.system = 'METRIC'
new.unit_settings.scale_length = 1.0
new.world = bpy.data.worlds.new('QT_World')
bpy.ops.wm.save_as_mainfile(filepath=TARGET)
print('saved', bpy.data.filepath, 'objects', len(bpy.data.objects), 'scenes', [s.name for s in bpy.data.scenes])
