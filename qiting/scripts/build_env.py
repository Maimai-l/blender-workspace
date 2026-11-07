# Build the surroundings of the Qiting replica (round 2) in the open qiting.blend. Each step deletes what it owns.
#   STEPS = ['all'] or any of: mats, terrain, paving, lake, plants, lamps, furniture, far
# Data: lib/qt_env_data.py and lib/qt_env_grid.py, made by qiting/env/make_env.py in the cloud session.
import sys, importlib, time, bpy
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import xy_core, xy_mats, xy_roof, xy_plants, qt_dims, qt_mats, qt_ground, qt_env_data, qt_env_grid, qt_env, qt_far
for m in (xy_core, xy_mats, xy_roof, xy_plants, qt_dims, qt_mats, qt_ground, qt_env_data, qt_env_grid, qt_env, qt_far):
    importlib.reload(m)
C = xy_core

TARGET = r'C:\Users\blender\Documents\qiting\qiting.blend'
if bpy.data.filepath.lower() != TARGET.lower():
    raise SystemExit('open file is %r, not %s - refusing to build' % (bpy.data.filepath, TARGET))

STEPS = globals().get('STEPS') or ['all']
if 'all' in STEPS:
    STEPS = ['mats', 'terrain', 'paving', 'lake', 'plants', 'lamps', 'furniture', 'far']

COLL = {k: C.coll(v) for k, v in (('terrain', '地形'), ('paving', '地面'), ('water', '水体'), ('plants', '植物'),
                                  ('lamps', '灯具与小品'), ('far', '远景'))}
C.lib_coll()
OWN = {
    'terrain': ('QT_terrain', 'QT_far_ground', 'QT_stage_ground'),
    'paving': ('QT_plaza', 'QT_paths', 'QT_promenade', 'QT_lakewalk', 'QT_garden_stairs'),
    'lake': ('QT_lake', 'QT_revetment', 'QT_lake_railing', 'QT_platform'),
    'plants': ('QT_trees_', 'QT_shrubs_', 'QT_lawn_grass', 'QT_hedges'),
    'lamps': ('QT_lamps_',),
    'furniture': ('QT_plaza_furniture', 'QT_sculptures', 'QT_gate', 'QT_cart'),
    'far': ('QT_far_land', 'QT_island', 'QT_far_trees_', 'QT_ziyun', 'QT_boats', 'QT_boatstage', 'QT_dock', 'QT_boathouse',
            'QT_island_pav', 'QT_far_hall', 'QT_city', 'QT_villas', 'QT_offices'),
}


def drop(prefixes):
    n = 0
    for o in list(bpy.data.objects):
        if o.name.startswith(tuple(prefixes)):
            me = o.data if o.type == 'MESH' else None
            bpy.data.objects.remove(o, do_unlink=True)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
            n += 1
    return n


log = []
t_all = time.time()
for st in STEPS:
    t0 = time.time()
    if st in OWN:
        drop(OWN[st])
    if st == 'mats':
        qt_mats.build_all()
        qt_env.plant_mats()
        qt_mats.build_env()
        log.append('mats: %d materials' % len(bpy.data.materials))
    elif st == 'terrain':
        qt_env.terrain(COLL['terrain'])
        qt_env.far_ground(COLL['terrain'])
        stage = bpy.data.collections.get('临时背景（非复刻内容）')
        if stage is not None and not stage.objects:
            bpy.data.collections.remove(stage)
        log.append('terrain')
    elif st == 'paving':
        src = qt_ground.sett_src()
        qt_env.plaza(COLL['paving'], src)
        qt_env.paths(COLL['paving'])
        qt_env.stairs(COLL['paving'])
        log.append('paving')
    elif st == 'lake':
        qt_env.lake(COLL['water'])
        log.append('lake')
    elif st == 'plants':
        T, sets = qt_env.templates()
        objs = qt_env.trees(COLL['plants'], T)
        qt_env.hedges(COLL['plants'])
        o2, ng = qt_env.shrubs_and_grass(COLL['plants'], T, sets)
        log.append('plants: %d tree instancers, %d grass clumps' % (len(objs), ng))
    elif st == 'lamps':
        objs = qt_env.lamps(COLL['lamps'])
        log.append('lamps: %d kinds' % len(objs))
    elif st == 'furniture':
        qt_env.furniture(COLL['lamps'])
        qt_env.sculptures(COLL['lamps'])
        qt_env.gate_and_cart(COLL['lamps'])
        log.append('furniture')
    elif st == 'far':
        qt_far.mats()
        qt_far.far_land(COLL['far'])
        T = qt_env.get_templates()
        objs, n = qt_far.far_trees(COLL['far'], T)
        qt_far.ziyun(COLL['far'])
        qt_far.boats(COLL['far'])
        qt_far.far_halls(COLL['far'])
        ov, nv = qt_far.villas(COLL['far'])
        qt_far.offices(COLL['far'])
        o, nb = qt_far.city(COLL['far'])
        log.append('far: %d far trees, %d houses, %d city blocks' % (n, nv, nb))
    log[-1] += '  (%.1fs)' % (time.time() - t0)

bpy.context.view_layer.update()
print('\n'.join(log))
print('objects', len(bpy.data.objects), 'total %.1fs' % (time.time() - t_all))
