import sys, importlib, bpy, time, os
LIB = r'C:\Users\blender\Documents\xingyuan\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import xy_core, xy_light
for m in (xy_core, xy_light): importlib.reload(m)
sky, sun = xy_light.setup_world(sun_elev=40, sun_azim=235, strength=1.0, sun_strength=4.0)
print({a: getattr(sky, a) for a in dir(sky) if a.startswith('sun') or a in ('sky_type', 'altitude', 'air_density')})
xy_light.setup_render(samples=48, res=(640, 360))
cam = bpy.data.objects['CAM_test']
sc = bpy.context.scene
bg = next(n for n in sc.world.node_tree.nodes if n.type == 'BACKGROUND')
import numpy as np
for s in (0.02, 0.06, 0.15):
    bg.inputs['Strength'].default_value = s
    out = os.path.join(xy_core.ROOT, 'renders', 'cal_%g.png' % s)
    xy_light.render_to(out, cam)
    img = bpy.data.images.load(out, check_existing=False)
    px = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
    print(s, 'mean', px.mean(axis=0).round(3), 'p95', np.percentile(px, 95, axis=0).round(3))
    bpy.data.images.remove(img)
