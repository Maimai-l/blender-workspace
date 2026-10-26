# preview_cam.py - camera, sun and sky colour for looking at WD models from the planned Unity viewpoint (not exported)
import bpy, math
from mathutils import Vector
import sys, importlib
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import wdlib; importlib.reload(wdlib)
from wdlib import U
scn = bpy.context.scene
for name in ("PreviewCam", "PreviewSun"):
    o = bpy.data.objects.get(name)
    if o: bpy.data.objects.remove(o, do_unlink=True)
cam_data = bpy.data.cameras.new("PreviewCam")
cam_data.lens_unit = 'FOV'
cam_data.sensor_fit = 'VERTICAL'
cam_data.angle = math.radians(CAM_FOV)
cam = bpy.data.objects.new("PreviewCam", cam_data)
scn.collection.objects.link(cam)
cam.location = U(*CAM_POS)
target = U(*CAM_TARGET)
d = target - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scn.camera = cam
sun_data = bpy.data.lights.new("PreviewSun", 'SUN')
sun_data.energy = 3.2
sun_data.angle = math.radians(3)
sun = bpy.data.objects.new("PreviewSun", sun_data)
scn.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(140))
scn.render.resolution_x = 1600; scn.render.resolution_y = 900
w = scn.world or bpy.data.worlds.new("World")
scn.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.62, 0.78, 0.92, 1)
bg.inputs[1].default_value = 0.9
print("preview camera ready")
