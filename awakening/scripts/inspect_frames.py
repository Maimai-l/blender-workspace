"""Contact sheets of the final frames for inspection (run inside Blender):
    FD = frames folder; random frames (seeded) per shot and a dense strip of a chosen shot."""
import bpy, sys, os, random
LIB = r'C:\Users\blender\Documents\awakening\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import aw_sheet as SH
FD = globals().get('FD', r'C:\Users\blender\Documents\awakening\frames_final')
RD = r'C:\Users\blender\Documents\awakening\renders'
SEED = globals().get('SEED', 11)
rnd = random.Random(SEED)
shots = [(1, 168), (169, 312), (313, 432), (433, 552), (553, 672), (673, 912), (913, 1032), (1033, 1128), (1129, 1183), (1184, 1344)]
frames = []
for a, b in shots:
    frames += sorted(rnd.sample(range(a, b + 1), 2))
paths = [FD + '\\f_%04d.png' % f for f in frames]
paths = [p for p in paths if os.path.exists(p)]
print('frames', frames)
print(SH.sheet(paths, RD + '\\inspect_%d.png' % SEED, cols=5, cell=(576, 324)))
