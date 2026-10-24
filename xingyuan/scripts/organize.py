# Tidy the scene: collection order by plan number, remove stray/test data, report the tree.
import bpy
sc = bpy.context.scene
root = sc.collection
for name in ('TEST', 'A1 台基', 'A2 台基', 'A3 台基', 'A4 台基', 'A5 台基'):
    c = bpy.data.collections.get(name)
    if c is not None and not c.objects and not c.children:
        bpy.data.collections.remove(c)
# temporary cameras from inspection renders
for o in list(bpy.data.objects):
    if o.type == 'CAMERA' and not (o.name.startswith('CAM_对照_') or o.name.startswith('CAM_效果_')):
        bpy.data.objects.remove(o, do_unlink=True)
for cd in list(bpy.data.cameras):
    if cd.users == 0:
        bpy.data.cameras.remove(cd)
# order of top-level collections
order = ['A1', 'A2', 'A3', 'A3-1', 'A4', 'A5', 'B1', 'B2', 'B3', '廊道', '地面', '灯光与相机', '_LIB']
kids = {c.name: c for c in root.children}
for n in order:
    if n in kids:
        root.children.unlink(kids[n]); root.children.link(kids[n])
for n, c in kids.items():
    if n not in order:
        print('extra top-level collection:', n)
lc = bpy.context.view_layer.layer_collection.children
if '_LIB' in lc:
    lc['_LIB'].hide_viewport = True
bpy.data.orphans_purge(do_recursive=True)
def tree(c, d=0):
    objs = len(c.objects)
    print('  ' * d + '%s  (%d objects)' % (c.name, objs))
    for ch in c.children:
        tree(ch, d + 1)
for c in root.children:
    tree(c)
