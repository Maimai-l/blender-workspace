# Xingyuan - garden terrain, far ground and water bodies, from the grids made by env/make_env.py.
# Terrain: one mesh on a 0.5 m vertex grid with cover weights (w_forest / w_bare / w_bank / w_mud / lawn) as point
# attributes for M_Terrain. Cells deep under paving / buildings are left out. The grid border is blended to the
# natural ground level so the far ground plane continues it without a step.
import bpy, math, base64, zlib
import numpy as np
from mathutils import Vector
import xy_core as C
import xy_env_grid as EG
import xy_env_data as ED

ZG = ED.ZG
WL = ED.WL
_G = {}

def _dec(b64, dtype):
    return np.frombuffer(zlib.decompress(base64.b64decode(b64)), dtype=dtype).reshape(EG.GNY, EG.GNX)

def grids():
    if _G:
        return _G
    H = _dec(EG.H_MM_B64, np.int16).astype(np.float64) / 1000.0
    ny, nx = H.shape
    jj, ii = np.mgrid[0:ny, 0:nx]
    dborder = np.minimum(np.minimum(ii, nx - 1 - ii), np.minimum(jj, ny - 1 - jj)) * EG.GRES
    t = np.clip(1.0 - dborder / 12.0, 0.0, 1.0)
    wb = t * t * (3 - 2 * t)
    H = H * (1 - wb) + ZG * wb
    _G.update(H=H, WF=_dec(EG.W_FOREST_B64, np.uint8) / 255.0, WB=_dec(EG.W_BARE_B64, np.uint8) / 255.0,
              WK=_dec(EG.W_BANK_B64, np.uint8) / 255.0, WM=_dec(EG.W_MUD_B64, np.uint8) / 255.0,
              WATER=_dec(EG.WATER_B64, np.uint8) > 0, PAVED=_dec(EG.PAVED_B64, np.uint8) > 0)
    return _G

def refine_with_mask(M):
    """Use the fine (5 cm) paved mask: vertices the 0.5 m grid called 'paved' but that lie outside the real
    paving get heights from their unpaved neighbours (no dips or lips beside kerbs and walls)."""
    g = grids()
    if g.get('refined'):
        return
    H = g['H']
    ny, nx = H.shape
    jj, ii = np.mgrid[0:ny, 0:nx]
    X = EG.GX0 + (ii + 0.5) * EG.GRES
    Y = EG.GY1 - (jj + 0.5) * EG.GRES
    fine = M.test_many(X.ravel(), Y.ravel()).reshape(ny, nx)
    coarse = g['PAVED']
    unknown = coarse & ~fine
    known = ~coarse
    Hn = H.copy()
    for it in range(8):
        acc = np.zeros_like(H); cnt = np.zeros_like(H)
        for dj in (-1, 0, 1):
            for di in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                k = np.zeros_like(known); h = np.zeros_like(H)
                ys0, ys1 = max(0, dj), ny + min(0, dj)
                xs0, xs1 = max(0, di), nx + min(0, di)
                k[ys0 - dj:ys1 - dj, xs0 - di:xs1 - di] = known[ys0:ys1, xs0:xs1]
                h[ys0 - dj:ys1 - dj, xs0 - di:xs1 - di] = Hn[ys0:ys1, xs0:xs1]
                acc += np.where(k, h, 0.0); cnt += k
        fillable = unknown & (cnt > 0)
        if not fillable.any():
            break
        Hn[fillable] = acc[fillable] / cnt[fillable]
        known = known | fillable
        unknown = unknown & ~fillable
    # anything still unknown, and every truly paved vertex, sits just under the slab bed
    Hn[unknown] = -0.69
    Hn[fine] = np.minimum(Hn[fine], -0.66)
    g['H'] = Hn
    g['PAVED'] = fine
    g['refined'] = True
    print('terrain refined:', int((coarse & ~fine).sum()), 'vertices freed,', int((fine & ~coarse).sum()), 'newly paved')

def vx(i):
    return EG.GX0 + (i + 0.5) * EG.GRES

def vy(j):
    return EG.GY1 - (j + 0.5) * EG.GRES

def height(x, y):
    """Bilinear terrain height at plan (x, y); ZG outside the grid."""
    H = grids()['H']
    fi = (x - EG.GX0) / EG.GRES - 0.5
    fj = (EG.GY1 - y) / EG.GRES - 0.5
    if fi < 0 or fj < 0 or fi > EG.GNX - 1 or fj > EG.GNY - 1:
        return ZG
    i0 = min(int(fi), EG.GNX - 2); j0 = min(int(fj), EG.GNY - 2)
    a = fi - i0; b = fj - j0
    return float(H[j0, i0] * (1 - a) * (1 - b) + H[j0, i0 + 1] * a * (1 - b) + H[j0 + 1, i0] * (1 - a) * b + H[j0 + 1, i0 + 1] * a * b)

def heights(X, Y):
    H = grids()['H']
    fi = np.clip((np.asarray(X) - EG.GX0) / EG.GRES - 0.5, 0, EG.GNX - 1.0001)
    fj = np.clip((EG.GY1 - np.asarray(Y)) / EG.GRES - 0.5, 0, EG.GNY - 1.0001)
    i0 = fi.astype(int); j0 = fj.astype(int)
    a = fi - i0; b = fj - j0
    return H[j0, i0] * (1 - a) * (1 - b) + H[j0, i0 + 1] * a * (1 - b) + H[j0 + 1, i0] * (1 - a) * b + H[j0 + 1, i0 + 1] * a * b

def _erode(m, k):
    m = m.copy()
    for _ in range(k):
        n = m.copy()
        n[1:, :] &= m[:-1, :]; n[:-1, :] &= m[1:, :]
        n[:, 1:] &= m[:, :-1]; n[:, :-1] &= m[:, 1:]
        m = n
    return m

def _dilate(m, k):
    m = m.copy()
    for _ in range(k):
        n = m.copy()
        n[1:, :] |= m[:-1, :]; n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]; n[:, :-1] |= m[:, 1:]
        n[1:, 1:] |= m[:-1, :-1]; n[:-1, :-1] |= m[1:, 1:]
        n[1:, :-1] |= m[:-1, 1:]; n[:-1, 1:] |= m[1:, :-1]
        m = n
    return m

def _mesh(name, verts, faces):
    me = bpy.data.meshes.get(name)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return me

def _point_attr(me, name, arr):
    a = me.attributes.get(name) or me.attributes.new(name, 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.asarray(arr, dtype=np.float32).ravel())

def _replace_obj(name, me, coll, mat):
    o = bpy.data.objects.get(name)
    if o is not None:
        old = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    me.materials.append(C.mat(mat))
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o

def build_terrain(coll, name='环境_地形'):
    g = grids()
    H = g['H']
    ny, nx = H.shape
    deep = _erode(g['PAVED'], 2)
    jj, ii = np.mgrid[0:ny, 0:nx]
    X = EG.GX0 + (ii + 0.5) * EG.GRES
    Y = EG.GY1 - (jj + 0.5) * EG.GRES
    verts = np.stack([X.ravel(), Y.ravel(), H.ravel()], axis=1)
    # quads between vertex (j, i), (j, i+1), (j+1, i+1), (j+1, i): row j+1 is SOUTH of row j
    keep = ~(deep[:-1, :-1] & deep[:-1, 1:] & deep[1:, :-1] & deep[1:, 1:])
    cj, ci = np.nonzero(keep)
    v00 = cj * nx + ci
    faces = np.stack([v00 + nx, v00 + nx + 1, v00 + 1, v00], axis=1)     # CCW seen from above
    me = _mesh(name, verts.tolist(), faces.tolist())
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    wf, wb, wk, wm = g['WF'], g['WB'], g['WK'], g['WM']
    water = g['WATER'].astype(np.float32)
    paved = g['PAVED'].astype(np.float32)
    lawn = np.clip(1.0 - (wf + wb + wk + wm), 0.0, 1.0) * (1 - paved) * (1 - water)
    for nm, arr in (('w_forest', wf), ('w_bare', wb), ('w_bank', wk), ('w_mud', np.maximum(wm, water)), ('lawn', lawn),
                    ('paved', paved)):
        _point_attr(me, nm, arr)
    o = _replace_obj(name, me, coll, 'M_Terrain')
    print('terrain verts', len(me.vertices), 'faces', len(me.polygons))
    return o

def build_far_ground(coll, name='环境_远景地面', R=900.0):
    """A large ring plane around the terrain grid (inner edge = grid border at ZG)."""
    x0 = EG.GX0 + 0.5 * EG.GRES; x1 = EG.GX0 + (EG.GNX - 0.5) * EG.GRES
    y1 = EG.GY1 - 0.5 * EG.GRES; y0 = EG.GY1 - (EG.GNY - 0.5) * EG.GRES
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    X0, X1, Y0, Y1 = cx - R, cx + R, cy - R, cy + R
    V = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1), (x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    verts = [(x, y, ZG) for x, y in V]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = _mesh(name, verts, faces)
    _point_attr(me, 'w_forest', [1.0] * 4 + [0.6] * 4)
    o = _replace_obj(name, me, coll, 'M_Terrain')
    return o

def build_water(coll, name='环境_水体', dil=3, z_bot=-2.6, mat='M_PondWater'):
    """Closed water volume over the (dilated) water cells: flat top at WL, walls buried in the banks."""
    g = grids()
    W = _dilate(g['WATER'], dil)
    ny, nx = W.shape
    vid = {}
    verts = []
    def V(I, J, z):
        k = (I, J, z)
        if k not in vid:
            vid[k] = len(verts)
            verts.append((EG.GX0 + I * EG.GRES, EG.GY1 - J * EG.GRES, z))
        return vid[k]
    faces = []
    js, is_ = np.nonzero(W)
    zt, zb = WL, z_bot
    for j, i in zip(js.tolist(), is_.tolist()):
        # cell corners: (I=i..i+1, J=j..j+1); J+1 is south
        a, b, c, d = (i, j + 1), (i + 1, j + 1), (i + 1, j), (i, j)       # SW, SE, NE, NW
        faces.append((V(*a, zt), V(*b, zt), V(*c, zt), V(*d, zt)))
        faces.append((V(*d, zb), V(*c, zb), V(*b, zb), V(*a, zb)))
        # walls where the neighbour is dry: south (j+1), north (j-1), east (i+1), west (i-1)
        if j + 1 >= ny or not W[j + 1, i]:
            faces.append((V(*a, zb), V(*b, zb), V(*b, zt), V(*a, zt)))
        if j - 1 < 0 or not W[j - 1, i]:
            faces.append((V(*c, zb), V(*d, zb), V(*d, zt), V(*c, zt)))
        if i + 1 >= nx or not W[j, i + 1]:
            faces.append((V(*b, zb), V(*c, zb), V(*c, zt), V(*b, zt)))
        if i - 1 < 0 or not W[j, i - 1]:
            faces.append((V(*d, zb), V(*a, zb), V(*a, zt), V(*d, zt)))
    me = _mesh(name, verts, faces)
    me.polygons.foreach_set('use_smooth', [False] * len(me.polygons))
    o = _replace_obj(name, me, coll, mat)
    print('water faces', len(faces), 'area m2', int(W.sum() * EG.GRES ** 2))
    return o
