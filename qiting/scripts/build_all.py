# Build the Qiting (旗亭) replica in the open Blender file. Every object comes from qiting/scripts/lib; each step
# deletes what it owns (objects and their instance sources) and builds it again.
#   STEPS = ['all'] or any of: mats, roof, frame, podium, ground, boards
# Run inside Blender with the library copied to C:\Users\blender\Documents\qiting\lib (tools/push.py does that).
import sys, importlib, time, bpy
LIB = r'C:\Users\blender\Documents\qiting\lib'
if LIB not in sys.path:
    sys.path.insert(0, LIB)
import xy_core, xy_mats, xy_roof, xy_parts, xy_props, qt_dims, qt_mats, qt_roof, qt_frame, qt_podium, qt_ground
for m in (xy_core, xy_mats, xy_roof, xy_parts, xy_props, qt_dims, qt_mats, qt_roof, qt_frame, qt_podium, qt_ground):
    importlib.reload(m)
C, D = xy_core, qt_dims

TARGET = r'C:\Users\blender\Documents\qiting\qiting.blend'
import os
if not bpy.data.filepath or os.path.realpath(bpy.data.filepath).lower() != os.path.realpath(TARGET).lower():   # C: path is a junction to D:
    raise SystemExit('open file is %r, not %s - refusing to build' % (bpy.data.filepath, TARGET))

STEPS = globals().get('STEPS') or ['all']
if 'all' in STEPS:
    STEPS = ['mats', 'roof', 'frame', 'podium', 'boards']      # the plaza ('ground') is built by build_env.py since round 2

# collections by part (names as asked: 屋面 檐下 柱与墙身 台基 台阶与栏杆 匾联 地面)
COLL = {k: C.coll(v) for k, v in (('roof', '屋面'), ('eave', '檐下'), ('cols', '柱与墙身'), ('podium', '台基'),
                                  ('stair', '台阶与栏杆'), ('boards', '匾联'), ('ground', '地面'))}
C.lib_coll()

OWN = {
    'roof': (('QT_R1_', 'QT_R2_', 'QT_finial', 'QT_collar'), ('SRC_cover', 'SRC_pan', 'SRC_cover_eave', 'SRC_pan_eave', 'SRC_fly', 'SRC_eaverafter')),
    'frame': (('QT_columns', 'QT_column_bases', 'QT_beams', 'QT_band', 'QT_brackets', 'QT_posts', 'QT_upper_windows', 'QT_ceiling',
               'QT_inner_wall', 'QT_caisson'), ('SRC_qt_col', 'SRC_qt_colin', 'SRC_qt_base', 'SRC_qt_brk1', 'SRC_qt_brk2', 'SRC_qt_post2')),
    'podium': (('QT_floor', 'QT_coping', 'QT_relief', 'QT_plinth', 'QT_terrace', 'QT_balustrade', 'QT_stair', 'QT_floodlights'), ('SRC_qt_post', 'SRC_qt_bay')),
    'ground': (('QT_plaza', 'QT_stage'), ('SRC_qt_sett', 'SRC_qt_sett_light', 'SRC_qt_sett_px', 'SRC_qt_sett_light_px')),
    'boards': (('QT_plaque', 'QT_couplet'), ()),
}


def drop(prefixes, srcs):
    n = 0
    for o in list(bpy.data.objects):
        if o.name.startswith(tuple(prefixes)) or o.name in srcs:
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
    if st == 'mats':
        names = qt_mats.build_all()
        log.append('mats: %d materials' % len(names))
        continue
    if st in OWN:
        nd = drop(*OWN[st])
    if st == 'roof':
        E1, E2 = qt_roof.eaves()
        o1, n1 = qt_roof.build_roof(E1, COLL['roof'], COLL['eave'])
        o2, n2 = qt_roof.build_roof(E2, COLL['roof'], COLL['eave'])
        qt_roof.collar('QT_collar_lower', D.R_DRUM2, D.Z_ROOF1_TOP - 0.20, D.Z_SILL2[0] + 0.02, COLL['roof'])
        qt_roof.finial(COLL['roof'])
        log.append('roof: tiles %d + %d; levels %s / %s' % (n1, n2, qt_roof.tile_levels(E1), qt_roof.tile_levels(E2)))
    elif st == 'frame':
        objs = qt_frame.lower_storey(COLL['cols'], COLL['eave'])
        objs += qt_frame.interior(COLL['cols'], COLL['eave'])
        objs += qt_frame.upper_storey(COLL['cols'], COLL['eave'])
        log.append('frame: %d objects' % len(objs))
    elif st == 'podium':
        objs = qt_podium.floor(COLL['podium'])
        objs.append(qt_podium.coping(COLL['podium']))
        objs += qt_podium.drum(COLL['podium'])
        objs += qt_podium.terraces(COLL['podium'])
        objs.append(qt_podium.floodlights(COLL['podium']))
        objs += qt_podium.podium_balustrade(COLL['stair'])
        objs += qt_podium.stair(COLL['stair'], COLL['stair'])
        log.append('podium: %d objects' % len(objs))
    elif st == 'ground':
        objs, n = qt_ground.plaza(COLL['ground'])
        qt_ground.stage_ground(C.coll('临时背景（非复刻内容）'))     # round-1 stand-in ground; round 2 has the terrain
        log.append('ground: %d setts' % n)
    elif st == 'boards':
        objs = qt_frame.boards(COLL['boards'])
        log.append('boards: %d objects' % len(objs))
    log[-1] += '  (%.1fs)' % (time.time() - t0)

bpy.context.view_layer.update()
print('\n'.join(log))
print('objects', len(bpy.data.objects), 'total %.1fs' % (time.time() - t_all))
