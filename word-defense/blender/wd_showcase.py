# wd_showcase.py - studio renders of the Word Defense models for the README (not used by the game)
# Appends the models from the saved .blend files into a temporary scene, renders two shots with EEVEE,
# then removes the scene and everything it brought in, leaving the open file as it was.
import bpy, bmesh, math, os
from mathutils import Vector

W = r"C:/Users/blender/Documents/WordDefense"


def lin(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


orig = bpy.context.window.scene
old = bpy.data.scenes.get("WD_Showcase")
if old:
    for o in list(old.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.scenes.remove(old)
sc = bpy.data.scenes.new("WD_Showcase")
bpy.context.window.scene = sc
O = bpy.data.objects

for f in ("WD_Units.blend", "WD_Castle.blend", "WD_Cannon.blend"):
    with bpy.data.libraries.load(os.path.join(W, f), link=False) as (src, dst):
        dst.objects = list(src.objects)
    for o in dst.objects:
        if o is not None:
            sc.collection.objects.link(o)


def place(name, loc, rz=0.0, show=True):
    o = O[name]
    o.location = Vector(loc)
    o.rotation_euler = (0, 0, math.radians(rz))
    for c in [o] + list(o.children_recursive):
        c.hide_render = not show
        c.hide_viewport = not show


def cyclorama(name, back_y, radius, width, height, front):
    prof = [(front, 0.0)]
    for i in range(17):
        a = math.radians(90 * i / 16)
        prof.append((back_y + radius * math.sin(a), radius - radius * math.cos(a)))
    prof.append((back_y + radius, height))
    bm = bmesh.new()
    rows = [[bm.verts.new((x, y, z)) for (y, z) in prof] for x in (-width, width)]
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = O.new(name, me)
    sc.collection.objects.link(ob)
    return ob


# studio: curved backdrop, warm sun, soft lavender world light
floor = cyclorama("ShowFloor", 6.0, 6.0, 60.0, 40.0, -60.0)
fm = bpy.data.materials.new("ShowFloorMat")
fm.use_nodes = True
b = next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
b.inputs["Base Color"].default_value = lin("#D9D3E6") + (1,)
b.inputs["Roughness"].default_value = 1.0
floor.data.materials.append(fm)
sun = O.new("ShowSun", bpy.data.lights.new("ShowSun", 'SUN'))
sc.collection.objects.link(sun)
sun.data.energy = 2.4
sun.data.angle = math.radians(12)
sun.data.color = lin("#FFF4E6")
sun.rotation_euler = (math.radians(46), 0, math.radians(-30))
world = bpy.data.worlds.new("ShowWorld")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = lin("#DCD8EA") + (1,)
bg.inputs[1].default_value = 0.85
sc.world = world
cam = O.new("ShowCam", bpy.data.cameras.new("ShowCam"))
sc.collection.objects.link(cam)
sc.camera = cam
try:
    sc.render.engine = 'BLENDER_EEVEE'
except TypeError as e:
    print(e)
sc.view_settings.view_transform = 'Standard'
try:
    sc.eevee.use_raytracing = True
except Exception:
    pass
sc.eevee.taa_render_samples = 64
sc.render.image_settings.file_format = 'PNG'


def shoot(path, loc, target, lens, rx=1600, ry=820):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)


# shot 1: the ink army (boss, brute, soldier, scout) and a meaning shell
for n in ("WD_Castle", "WD_Cannon", "WD_Portal"):
    place(n, (0, 90, 0), show=False)
place("WD_Boss", (0.3, 1.4, 0), -8)
place("WD_Brute", (-3.1, -0.5, 0), 24)
place("WD_Soldier", (2.9, -0.4, 0), -22)
place("WD_Scout", (-0.9, -2.0, 0), 10)
place("WD_Shell", (1.3, -2.4, 1.05), 30)
bpy.context.view_layer.update()
shoot(W + "/showcase_units.png", (0.5, -19.0, 4.6), (0.1, 0, 2.55), 45)

# shot 2: castle with the cannon on its bastion, and the portal
for n in ("WD_Boss", "WD_Brute", "WD_Soldier", "WD_Scout", "WD_Shell"):
    place(n, (0, 90, 0), show=False)
place("WD_Castle", (0, -2.0, 0), 0)
bpy.context.view_layer.update()
place("WD_Cannon", tuple(O["CannonMount"].matrix_world.translation), 200)
place("WD_Portal", (11.5, 2.5, 0), 25)
bpy.context.view_layer.update()
shoot(W + "/showcase_castle.png", (-13.0, -36.0, 16.5), (2.3, -0.8, 2.6), 44)

# clean up: the open file keeps only what it had before
objs = list(sc.objects)
meshes = {o.data for o in objs if o.type == 'MESH' and o.data}
mats = {m for me in meshes for m in me.materials if m}
datas = [o.data for o in objs if o.type in ('LIGHT', 'CAMERA') and o.data]
bpy.context.window.scene = orig
for o in objs:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.scenes.remove(sc)
for me in meshes:
    if me.users == 0:
        bpy.data.meshes.remove(me)
for m in mats:
    if m.users == 0:
        bpy.data.materials.remove(m)
for d in datas:
    if d.users == 0:
        (bpy.data.lights if isinstance(d, bpy.types.Light) else bpy.data.cameras).remove(d)
if world.users == 0:
    bpy.data.worlds.remove(world)
print("showcase rendered to", W)
