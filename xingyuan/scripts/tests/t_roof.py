import sys, importlib, bpy, math, time
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core as C, xy_mats, xy_roof as R
for m in (C, xy_mats, R): importlib.reload(m)
from mathutils import Matrix, Vector
t0 = time.time()
C.clear_coll('TEST')
col = C.coll('TEST')
P = R.Profile(8.6, 4.955, 9.2)
A = 12.72
S = R.RoofShape('gable', A, 8.6, P)
M = Matrix.Translation((14.63, 11.92, 0)) @ Matrix.Rotation(math.radians(90), 4, 'Z')
objs, n = R.place_tiles('T_A1', S, M, ['S', 'N'], col)
print('tiles', n, time.time()-t0)
R.deck('T_A1_deck', S, M, col, t_top=0.055, t_sof=0.215, soffit_step=(0.62, 0.075))
R.rafters('T_A1_raft', S, M, col, {'S': 2.6, 'N': 2.6}, ['S', 'N'])
R.eave_boards('T_A1_eb', S, M, col, ['S', 'N'])
R.main_ridge('T_A1_ridge', M, -A + 0.15, A - 0.15, P.f(8.6) - 0.06, col)
for xs in (-A + 0.04, A - 0.04):
    R.verge_ridge('T_A1_verge', M, S, xs, col)
    R.bargeboard('T_A1_barge', M, S, xs - (0.08 if xs > 0 else -0.08), col)
print('done', time.time()-t0, len(col.objects))
