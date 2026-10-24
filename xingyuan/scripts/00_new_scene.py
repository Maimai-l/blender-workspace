# Create a fresh scene for the Xingyuan model, drop the donut test scene, save as a new file.
import bpy, os
ROOT = r'C:\Users\blender\Documents\xingyuan'
for sub in ('', 'lib', 'renders', 'refs'):
    os.makedirs(os.path.join(ROOT, sub), exist_ok=True)

old_scenes = list(bpy.data.scenes)
new = bpy.data.scenes.new('Xingyuan')
for w in bpy.context.window_manager.windows:
    w.scene = new
for sc in old_scenes:
    bpy.data.scenes.remove(sc)
# remove all leftover data blocks from the test file
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
w = bpy.data.worlds.new('XY_World')
new.world = w
path = os.path.join(ROOT, 'xingyuan.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
print('saved', bpy.data.filepath, 'objects', len(bpy.data.objects), 'scenes', [s.name for s in bpy.data.scenes])
