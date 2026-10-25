# Xingyuan - build the ground: raised floors (union of all platforms), courtyards, apron, plaza, pool, stairs.
import bpy, math, random
import numpy as np
from mathutils import Vector
import xy_core as C, xy_site as S, xy_layout as LY

RES = 0.05

def _erode(m, k):
    m = m.copy()
    for _ in range(k):
        n = m.copy()
        n[1:, :] &= m[:-1, :]; n[:-1, :] &= m[1:, :]
        n[:, 1:] &= m[:, :-1]; n[:, :-1] &= m[:, 1:]
        n[0, :] = False; n[-1, :] = False; n[:, 0] = False; n[:, -1] = False
        m = n
    return m

def _dilate(m, k):
    """square (8-neighbour) dilation: rectangles stay rectangles"""
    m = m.copy()
    for _ in range(k):
        n = m.copy()
        n[1:, :] |= m[:-1, :]; n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]
        n[1:, 1:] |= m[:-1, :-1]; n[:-1, :-1] |= m[1:, 1:]
        n[1:, :-1] |= m[:-1, 1:]; n[:-1, 1:] |= m[1:, :-1]
        m = n
    return m

def _mask(R, rects):
    m = np.zeros((R.ny, R.nx), dtype=bool)
    for (x0, y0, x1, y1) in rects:
        i0, j0 = R.ij(x0, y0); i1, j1 = R.ij(x1, y1)
        m[max(0, j0):max(0, j1), max(0, i0):max(0, i1)] = True
    return m

SITE_PREFIXES = ('B1_庭院铺地', 'B2_庭院铺地', 'B3_庭院铺地', 'B3_许愿池')

def build_site(env=True):
    """env=True: the paving outside the complex (terrace, plaza, ...) and the ground come from xy_env_pave /
    xy_terrain; here the apron stops at those zones and no far ground is made."""
    rng = random.Random(11)
    C.clear_coll('地面')
    g = C.coll('地面')
    # remove stale site objects (and their meshes) wherever they live, then use dedicated sub-collections
    for o in [o for o in bpy.data.objects if o.name.startswith(SITE_PREFIXES)]:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    for k in ('B1', 'B2', 'B3'):
        C.clear_coll(k + ' 铺地')
    R = S.Raster(*LY.SITE_BOX, res=RES)
    lab = np.zeros((R.ny, R.nx), dtype=np.int8)
    # paint labels: corridors (2) first, then gate (3), then halls (1) win
    for pri in (2, 3, 1):
        for (rect, l, name) in LY.RAISED:
            if l == pri:
                x0, y0, x1, y1 = rect
                i0, j0 = R.ij(x0, y0); i1, j1 = R.ij(x1, y1)
                lab[j0:j1, i0:i1] = l
    raised = lab > 0
    pr, cut = LY.pool_rects()
    pool = _mask(R, pr) & ~_mask(R, cut)
    pool &= ~raised

    def at(mask, x, y):
        i, j = int((x - R.x0) / RES), int((y - R.y0) / RES)
        if 0 <= i < R.nx and 0 <= j < R.ny:
            return bool(mask[j, i])
        return False

    # ---------------- raised floors: paving inside an eroded mask + curbs/walls on the boundary
    pv = S.Paver(seed=5)
    inner = _erode(raised, int(round(0.40 / RES)))
    rects = S.rects_from_mask(inner)
    S.pave_rects(pv, R, rects, LY.Z0, 'M_Granite', 0.60, 0.60, along='y', origin=(LY.XC, 0.0), stagger=0.0)
    for (i0, j0, i1, j1) in rects:
        x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
        pv.grout(x0, y0, x1, y1, LY.Z0)
    o = pv.finish('地面_台明铺地', g)
    S.recalc_up(o)
    print('raised paving rects', len(rects), 'faces', len(o.data.polygons))

    mb = C.MB()
    def zlow(x, y):
        if at(raised, x, y):
            return None
        if at(pool, x, y):
            return LY.Z_POOL
        return LY.ZC
    def style(x, y):
        i, j = int((x - R.x0) / RES), int((y - R.y0) / RES)
        l = lab[min(max(j, 0), R.ny - 1), min(max(i, 0), R.nx - 1)]
        if l == 2:
            return ('M_BrickDark', 'M_Granite')
        return ('M_Granite', 'M_Granite')
    S.edge_walls(mb, R, raised, LY.Z0, zlow, style, curb_w=0.40, curb_len=1.0, rng=rng)
    o = mb.finish('地面_阶条石与台帮', g, recalc=False)
    print('edge faces', len(o.data.polygons))

    # ---------------- courtyards (kept clear of the 0.4 m pool coping band)
    coping = _dilate(pool, int(round(0.40 / RES))) & ~pool
    used = raised.copy() | pool | coping
    for key, cd in LY.COURTS.items():
        cm = _mask(R, [cd['rect']]) & ~used
        if key == 'B2':
            # only the paths are paved; the rest of B2 is planted (bamboo beds built in xy_props)
            beds = _mask(R, [r for (_, r, _) in LY.B2_BEDS])
            used |= cm
            cm = cm & ~beds
        else:
            used |= cm
        pv = S.Paver(seed=hash(key) % 1000)
        rects = S.rects_from_mask(cm)
        orig = (LY.XC, 0.0) if key == 'B1' else ((LY.POOL_C[0], LY.POOL_C[1]) if key == 'B3' else (50.0, 30.0))
        S.pave_rects(pv, R, rects, LY.ZC, cd['mat'], cd['sw'], cd['sl'], along=cd['along'], origin=orig, stagger=0.5)
        for (i0, j0, i1, j1) in rects:
            x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
            pv.grout(x0, y0, x1, y1, LY.ZC)
        o = pv.finish('%s_庭院铺地' % key, C.coll(key + ' 铺地', C.coll(key)))
        S.recalc_up(o)
        print(key, 'rects', len(rects), 'faces', len(o.data.polygons))

    # ---------------- B3 pool: coping band, walls, water, bottom
    terrace_band = _dilate(pool, int(round(0.40 / RES))) & ~pool & ~raised
    # (the coping is produced by edge_walls on the inverse mask)
    mbp = C.MB()
    notpool = ~pool
    def zlow_pool(x, y):
        return LY.Z_POOL if at(pool, x, y) else None
    S.edge_walls(mbp, R, notpool, LY.ZC, zlow_pool, lambda x, y: ('M_StoneGrey', 'M_Granite'), curb_w=0.40, curb_len=0.9, rng=rng)
    o = mbp.finish('B3_许愿池_池壁', C.coll('B3 铺地', C.coll('B3')), recalc=False)
    # water + bottom from pool rectangles
    mbw = C.MB(); mbb = C.MB()
    for (i0, j0, i1, j1) in S.rects_from_mask(pool):
        x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
        mbw.face([Vector((x0, y0, LY.Z_WATER)), Vector((x1, y0, LY.Z_WATER)), Vector((x1, y1, LY.Z_WATER)), Vector((x0, y1, LY.Z_WATER))], 'M_Water')
        mbb.face([Vector((x0, y0, LY.Z_POOL)), Vector((x1, y0, LY.Z_POOL)), Vector((x1, y1, LY.Z_POOL)), Vector((x0, y1, LY.Z_POOL))], 'M_PoolBed')
    # closed water volume: the box from the surface down to the bed (walls slightly inset from the pool walls)
    wb = C.MB()
    for (i0, j0, i1, j1) in S.rects_from_mask(pool):
        x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
        wb.box((x0 + 0.002, y0 + 0.002, LY.Z_POOL + 0.002), (x1 - 0.002, y1 - 0.002, LY.Z_WATER), 'M_Water')
    mbw.bm.free()
    ow = wb.finish('B3_许愿池_水面', C.coll('B3 铺地', C.coll('B3')), recalc=True)
    ow.data.polygons.foreach_set('use_smooth', [False] * len(ow.data.polygons))
    ob = mbb.finish('B3_许愿池_池底', C.coll('B3 铺地', C.coll('B3')), recalc=False, merge=0.001)

    # ---------------- apron around the complex and the entrance plaza
    envm = np.zeros((R.ny, R.nx), dtype=bool)
    if env:
        import xy_env_pave as EP, xy_geo2d as G2
        M = G2.Mask(*LY.SITE_BOX, res=RES)
        Z = EP.zones()
        for k in ('red', 'crazy', 'gray'):
            M.fill_poly(Z[k])
        envm = M.m
    near = _dilate(raised | pool | _mask(R, [LY.COURTS[k]['rect'] for k in LY.COURTS]), int(round(3.0 / RES)))
    plaza = np.zeros_like(near) if env else _mask(R, [(23.0, -20.0, 47.3, -6.0)])
    apron = (near | plaza) & ~used & ~envm
    pv = S.Paver(seed=77)
    edge_own = apron | raised | pool | coping | _mask(R, [LY.COURTS[k]['rect'] for k in LY.COURTS])
    edge_all = edge_own | envm
    apron_paved = apron & _erode(edge_all, int(round(0.25 / RES)))          # leave the kerb band free
    rects = S.rects_from_mask(apron_paved)
    S.pave_rects(pv, R, rects, LY.ZC, 'M_GraniteOut', 0.60, 0.90, along='y', origin=(LY.XC, 0.0), stagger=0.5)
    for (i0, j0, i1, j1) in rects:
        x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
        pv.grout(x0, y0, x1, y1, LY.ZC)
    o = pv.finish('地面_外围铺地', g)
    S.recalc_up(o)
    used |= apron
    # outer edge kerb of the apron (low granite edging)
    mbk = C.MB()
    S.edge_walls(mbk, R, edge_own, LY.ZC, lambda x, y: (LY.ZC - 0.08), lambda x, y: ('M_StoneGrey', 'M_StoneGrey'), curb_w=0.25, curb_len=1.0, rng=rng,
                 skip_fn=lambda x, y: at(envm, x, y))
    mbk.finish('地面_外围路缘', g, recalc=False)
    site_all = edge_all | used
    # far ground (gravel / compacted earth) slightly lower - only without the garden environment
    mbg = C.MB() if not env else None
    X0, Y0, X1, Y1 = -400, -400, 470, 460
    zg = LY.ZC - 0.08
    # ground everywhere except under the paved site (cut out with the site mask -> rectangles)
    site = edge_all | used
    if mbg is not None:
        hx0, hy0 = R.x0, R.y0; hx1, hy1 = R.x0 + R.nx * RES, R.y0 + R.ny * RES
        for (a0, b0, a1, b1) in ((X0, Y0, X1, hy0), (X0, hy1, X1, Y1), (X0, hy0, hx0, hy1), (hx1, hy0, X1, hy1)):
            mbg.face([Vector((a0, b0, zg)), Vector((a1, b0, zg)), Vector((a1, b1, zg)), Vector((a0, b1, zg))], 'M_Ground')
        for (i0, j0, i1, j1) in S.rects_from_mask(~site):
            x0, y0 = R.xy(i0, j0); x1, y1 = R.xy(i1, j1)
            mbg.face([Vector((x0, y0, zg)), Vector((x1, y0, zg)), Vector((x1, y1, zg)), Vector((x0, y1, zg))], 'M_Ground')
        mbg.finish('地面_基地', g, recalc=False)

    # ---------------- stairs
    mbs = C.MB()
    for (top, d, w, n, zt, zb, name) in LY.STAIRS:
        S.stairs(mbs, top, d, w, zt, zb, n, run=0.38, m='M_Granite', side_w=0.34, sides=True, m_side='M_Granite')
    o = mbs.finish('地面_台阶', g, recalc=True)
    return R, raised, pool, site_all
