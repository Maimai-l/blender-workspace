"""Render a list of (name, frame, camera) at the current resolution and tile them: SHOTS = [...]; OUT = 'sheet.png'."""
import bpy, sys, time
LIB = r'C:\Users\blender\Documents\awakening\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import aw_sheet as SH
sc = bpy.context.scene
RD = r'C:\Users\blender\Documents\awakening\renders'
cams = {o.name[4:]: o for o in bpy.data.objects if o.name.startswith('CAM_')}
t0 = time.time()
paths = []
for name, frame, cam in SHOTS:
    sc.frame_set(frame); sc.camera = cams[cam]
    sc.render.filepath = RD + '\\%s.png' % name
    bpy.ops.render.render(write_still=True)
    paths.append(sc.render.filepath)
print('rendered %d in %.1fs' % (len(SHOTS), time.time() - t0))
print(SH.sheet(paths, RD + '\\' + OUT, cols=COLS if 'COLS' in dir() else 4, cell=(480, 270)))
