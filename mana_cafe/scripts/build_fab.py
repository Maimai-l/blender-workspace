"""Import Megascans assets into library collections (FAB_<key>). KEYS = list of asset keys (default: all meshes)."""
import bpy, sys, importlib, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_fab
for m in (mc_core, mc_fab): importlib.reload(m)
print(bpy.data.filepath, len(bpy.data.objects))
import logging
logging.getLogger('glTFImporter').setLevel(logging.ERROR)
for o in [o for o in bpy.data.objects if o.name.startswith(('SM_', 'S_')) and o.users_collection and not o.users_collection[0].name.startswith('FAB_')]:
    d = o.data; bpy.data.objects.remove(o, do_unlink=True)
    if d and d.users == 0: bpy.data.meshes.remove(d)
ALL = ['dry_grass', 'tufted_grass', 'tundra_grass', 'wild_grass', 'yellow_flower', 'lingonberry', 'dwarf_willow',
       'dwarf_birch', 'stone', 'boulder_a', 'boulder_b', 'rock_formation', 'mossy_wall', 'jp_wall', 'granite_cliff',
       'snowy_ground', 'rocky_ground_a', 'rocky_ground_b']
for key in globals().get('KEYS', ALL):
    t0 = time.time()
    try:
        col = mc_fab.import_asset(key, force=globals().get('FORCE', False))
        print(key, len(col.objects), 'objects %.1fs' % (time.time() - t0))
    except Exception as e:
        import traceback
        print(key, 'FAILED', e); traceback.print_exc()
