# pp_final.py - presentation renders of the pop-up spread. Adds named cameras to WD_Popup.blend and renders each.
import bpy, time
from mathutils import Vector

assert bpy.data.filepath.replace('\\', '/').endswith('/popup/WD_Popup.blend'), "open WD_Popup.blend first"
scn = bpy.context.scene
OUT = r"C:/Users/blender/Documents/WordDefense/popup/renders/"
rig = bpy.data.collections.get("Rig")

VIEWS = [
    # name, location, target, lens, depth of field f-stop (None = off)
    ("Book", (0.3, -19.41, 18.75), (0.3, 6.8, 0.4), 55.0, None),
    ("Game", (0.3, -19.41, 18.75), (0.3, 6.35, 0.5), 66.0, None),
    ("Stage", (-2.4, -3.0, 1.5), (-1.0, 8.6, 1.3), 35.0, 5.6),
    ("Castle", (2.0, -3.9, 4.0), (5.5, 2.4, 1.3), 45.0, 4.0),
    ("Tear", (-0.6, 3.6, 3.3), (-0.9, 10.2, 1.2), 42.0, 5.6),
    ("Pond", (-6.5, -2.5, 3.6), (-4.2, 3.0, 0.6), 40.0, 5.6),
    ("Rows", (1.2, 1.2, 3.4), (1.6, 7.6, 0.4), 40.0, 5.6),
]

scn.eevee.taa_render_samples = 128
scn.render.resolution_x, scn.render.resolution_y = 1920, 1080
for name, loc, target, lens, fstop in VIEWS:
    cname = "Cam_" + name
    cd = bpy.data.cameras.get(cname) or bpy.data.cameras.new(cname)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_end = 300.0
    ob = bpy.data.objects.get(cname) or bpy.data.objects.new(cname, cd)
    if rig is not None and ob.name not in rig.objects:
        rig.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cd.dof.use_dof = fstop is not None
    if fstop is not None:
        cd.dof.focus_distance = d.length
        cd.dof.aperture_fstop = fstop
    scn.camera = ob
    scn.render.filepath = OUT + "WD_Popup_%s.png" % name.lower()
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print(name, round(time.time() - t, 1), "s")

scn.camera = bpy.data.objects["Cam_Game"]
scn.eevee.taa_render_samples = 64
bpy.ops.wm.save_mainfile()
print("saved", bpy.data.filepath)
