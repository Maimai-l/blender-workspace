# Build the garden environment around the complex (runs inside Blender after build_all.py).
# STEPS (default 'all'): mats, site, ground, pave, plants, struct, veg, grass
import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import numpy as np
import xy_core, xy_mats, xy_site, xy_layout, xy_geo2d, xy_env_data, xy_env_grid, xy_build_site, xy_terrain, xy_env_pave
MODS = [xy_core, xy_mats, xy_site, xy_layout, xy_geo2d, xy_env_data, xy_env_grid, xy_build_site, xy_terrain, xy_env_pave]
for name in ('xy_plants', 'xy_env_struct', 'xy_env_veg'):
    try:
        MODS.append(importlib.import_module(name))
    except ImportError as e:
        print('skip', name, e)
for m in MODS:
    importlib.reload(m)
C, G, TR, EP = xy_core, xy_geo2d, xy_terrain, xy_env_pave
T = time.time()
STEPS = globals().get('STEPS', 'all')
def want(k):
    return STEPS == 'all' or k in STEPS
CACHE = os.path.join(C.ROOT, 'cache')
os.makedirs(CACHE, exist_ok=True)
MASK_FILE = os.path.join(CACHE, 'ground_mask.npz')
ENV = C.coll('环境')
def sub(name):
    return C.coll(name, ENV)

def global_mask(site_all=None, R=None):
    """Fine (5 cm) plan mask of everything paved / built, over the terrain grid."""
    x0 = xy_env_grid.GX0; y1 = xy_env_grid.GY1
    x1 = x0 + xy_env_grid.GNX * xy_env_grid.GRES; y0 = y1 - xy_env_grid.GNY * xy_env_grid.GRES
    M = G.Mask(x0, y0, x1, y1, res=0.05)
    if site_all is not None:
        io = int(round((R.x0 - M.x0) / M.res)); jo = int(round((R.y0 - M.y0) / M.res))
        M.m[jo:jo + site_all.shape[0], io:io + site_all.shape[1]] |= site_all
    for P in EP.mask_polys():
        M.fill_poly(P)
    return M

if want('mats'):
    xy_mats.build_all(); print('mats %.1f' % (time.time() - T))

if want('site'):
    R, raised, pool, site_all = xy_build_site.build_site(env=True)
    o = bpy.data.objects.get('地面_基地')
    if o is not None:
        me = o.data; bpy.data.objects.remove(o, do_unlink=True)
        if me and me.users == 0: bpy.data.meshes.remove(me)
    M = global_mask(site_all, R)
    np.savez_compressed(MASK_FILE, m=M.m, x0=M.x0, y0=M.y0, res=M.res)
    print('site + mask %.1f' % (time.time() - T), M.m.shape, int(M.m.sum() * 0.0025), 'm2 paved')

def load_mask():
    d = np.load(MASK_FILE)
    M = G.Mask(float(d['x0']), float(d['y0']), float(d['x0']) + d['m'].shape[1] * float(d['res']),
               float(d['y0']) + d['m'].shape[0] * float(d['res']), res=float(d['res']))
    M.m = d['m']
    return M

if want('ground'):
    TR.refine_with_mask(load_mask())
    cg = sub('环境_地形水体')
    TR.build_terrain(cg); TR.build_far_ground(cg); TR.build_water(cg)
    print('ground %.1f' % (time.time() - T))

if want('pave'):
    M = load_mask()
    TR.refine_with_mask(M)
    C.clear_coll('环境_铺地')
    cp = sub('环境_铺地')
    def z_low(p):
        h = min(TR.height(p[0] + dx, p[1] + dy) for dx, dy in ((0, 0), (0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4)))
        return min(-0.72, h - 0.12)
    made = EP.build(cp, lambda p: M.test(p[0], p[1]), z_low)
    print('pave %.1f' % (time.time() - T), [o.name for o in made])

import xy_plants as PL, xy_env_struct as ST, xy_env_veg as VG
if want('plants'):
    sets = PL.make_sources()
    PL.make_templates(sets)
    print('plant library %.1f' % (time.time() - T))

if want('struct') or want('veg') or want('grass'):
    M = load_mask()
    TR.refine_with_mask(M)
    cs = sub('环境_构筑物')
    if want('struct'):
        ST.build(cs, M)
        print('structures %.1f' % (time.time() - T))
    planters = ST.planters_info() if hasattr(ST, 'planters_info') else None

if want('veg'):
    sets = PL.get_sets()
    T_ = PL.make_templates(sets, only=[])
    pl = ST.planters_info()
    ct = sub('环境_乔木'); VG._clear(ct)
    objs, n = VG.trees(ct, T_, pl)
    print('trees', n, 'instancers', len(objs), '%.1f' % (time.time() - T))
    csh = sub('环境_灌木'); VG._clear(csh)
    VG.shrubs(csh, T_, pl, M)
    print('understory', VG.understory(csh, T_, M), 'far understory', VG.far_understory(csh, T_))
    cgp = sub('环境_水生与地被'); VG._clear(cgp)
    print('lotus/rocks', VG.ground_plants(cgp, sets, M), 'forest cover', VG.forest_cover(cgp, sets, M))
    print('veg %.1f' % (time.time() - T))

if want('grass'):
    sets = PL.get_sets()
    cl = sub('环境_草坪'); VG._clear(cl)
    print('grass clumps', VG.lawn(cl, sets, M, ST.planters_info()), '%.1f' % (time.time() - T))

print('env total %.1fs' % (time.time() - T))
