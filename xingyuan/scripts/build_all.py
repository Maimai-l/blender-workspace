# Full rebuild of the Xingyuan scene (runs inside Blender).
import sys, importlib, bpy, time
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_mats, xy_roof, xy_parts, xy_site, xy_layout, xy_build_site, xy_hall, xy_frame, xy_struct, xy_props
for m in (xy_core, xy_mats, xy_roof, xy_parts, xy_site, xy_layout, xy_build_site, xy_hall, xy_frame, xy_struct, xy_props):
    importlib.reload(m)
T = time.time()
STEPS = globals().get('STEPS', 'all')
def want(k):
    return STEPS == 'all' or k in STEPS
xy_core.clear_coll('TEST')
if want('src'):
    # rebuild part sources from scratch
    for o in [o for o in bpy.data.objects if o.name.startswith('SRC_')]:
        bpy.data.objects.remove(o, do_unlink=True)
if want('mats'):
    xy_mats.build_all()
if want('site'):
    xy_build_site.build_site(); print('site %.1f' % (time.time() - T))
if want('halls'):
    for k, s in xy_layout.HALLS.items():
        xy_hall.build_hall(k, s['ox'], s['oy'], s['rot'], s['D'], s['L'], s['nb'], s['doors'], s['back'], s['open_bay'],
                           seed=hash(k) % 97)
    print('halls %.1f' % (time.time() - T))
if want('corr'):
    xy_struct.build_corridors(); print('corridors %.1f' % (time.time() - T))
if want('pav'):
    xy_struct.build_pavilions(); print('pavilions %.1f' % (time.time() - T))
if want('gate'):
    xy_struct.build_gate(); print('gate %.1f' % (time.time() - T))
if want('a31'):
    xy_struct.build_A31(); xy_struct.build_B2_walls(); print('A3-1/B2 %.1f' % (time.time() - T))
if want('props'):
    xy_props.build_props(); print('props %.1f' % (time.time() - T))
print('objects', len(bpy.data.objects), 'total %.1fs' % (time.time() - T))
