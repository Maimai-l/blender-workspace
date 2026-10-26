# preview_assemble.py - re-import the exported FBX files and lay them out like the Unity scene (preview only)
import sys, importlib, json, math
sys.path.insert(0, r"C:/Users/blender/Documents/WordDefense/scripts")
import wdlib; importlib.reload(wdlib)
from wdlib import *
import bpy
from mathutils import Vector

reset()
def imp(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=MODELS + "/" + name + ".fbx")
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    return roots
data = json.load(open(UNITY + "/Data/path.json"))
cx, _, cz = data["castle"]
imp("WD_World")
for r in imp("WD_Castle"):
    r.location = r.location + U(cx, cz, 0)
bpy.context.view_layer.update()
mount = bpy.data.objects.get("CannonMount")
mw = mount.matrix_world.translation.copy() if mount else U(cx, cz, 3)
for r in imp("WD_Cannon"):
    r.location = mw
    r.rotation_euler = (r.rotation_euler[0], r.rotation_euler[1], r.rotation_euler[2] + math.radians(30))
for extra in EXTRA:
    name, ux, uz, uy, rot = extra
    for r in imp(name):
        r.location = r.location + U(ux, uz, uy)
        r.rotation_euler[2] += math.radians(rot)
print("assembled", len(bpy.data.objects), "objects")
