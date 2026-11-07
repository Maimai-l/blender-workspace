# Scene statistics: objects per collection, instances and triangles in the viewport and render depsgraphs.
import bpy
dg = bpy.context.evaluated_depsgraph_get()
tri = inst = 0
per = {}
for oi in dg.object_instances:
    ob = oi.object
    if ob.type != 'MESH':
        continue
    # hidden sources (tree templates in _LIB etc.) are evaluated but not drawn
    host = oi.parent if (oi.is_instance and oi.parent) else ob
    host = bpy.data.objects.get(host.name)
    if host is None or not host.visible_get():
        continue
    me = ob.data
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    tri += n
    key = (oi.parent.name if oi.is_instance and oi.parent else ob.name)
    per[key] = per.get(key, 0) + n
    if oi.is_instance:
        inst += 1
print('viewport triangles %.2f M, instances %d' % (tri / 1e6, inst))
for k, v in sorted(per.items(), key=lambda kv: -kv[1])[:12]:
    print('  %-26s %8.0f k tris' % (k, v / 1e3))
for c in bpy.context.scene.collection.children:
    print('collection', c.name, len(c.all_objects))
