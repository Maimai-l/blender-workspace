# Poke-through check: any non-roof geometry (incl. instanced parts) that rises above a roof's tile surface.
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOF_KEYS = ('QT_R1_', 'QT_R2_', 'QT_finial', 'QT_collar')     # roof parts themselves
SKIP = ('SRC_', 'QT_stage_ground')
dg = bpy.context.evaluated_depsgraph_get()
decks = []
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.endswith('_deck'):
        me = o.data
        ti = me.materials.find('M_Tile')
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world)
        for f in [f for f in bm.faces if f.material_index != ti]:
            bm.faces.remove(f)
        decks.append((o.name, BVHTree.FromBMesh(bm)))
        bm.free()
def covered(p):
    for (n, t) in decks:
        loc, nrm, idx, d = t.ray_cast(p + Vector((0, 0, 0.005)), Vector((0, 0, 1)), 30.0)
        if loc is not None:
            return True
    return False
def poke(p):
    for (n, t) in decks:
        loc, nrm, idx, d = t.ray_cast(p, Vector((0, 0, -1)), 4.0)
        if loc is not None and d > 0.02 and not covered(p):
            return n, d
    return None
report = {}
pts = []
BOX0 = (-7.0, -7.0, 7.0, 7.0)
def in_lib(o):
    # hidden instance sources (tree templates etc., in _LIB and its sub-collections) sit at the origin and never render
    return o is not None and (not o.visible_get() or any(c.name == '_LIB' for c in o.users_collection))
for o in bpy.data.objects:
    if o.type != 'MESH' or any(k in o.name for k in ROOF_KEYS) or o.name.startswith(SKIP) or any(s in o.name for s in SKIP):
        continue
    if in_lib(o):
        continue
    if any(m.type == 'NODES' for m in o.modifiers):
        continue
    M = o.matrix_world
    for v in o.data.vertices:
        pts.append((o.name, M @ v.co))
# instanced parts: test the 8 bbox corners of each instance
for inst in dg.object_instances:
    if not inst.is_instance:
        continue
    par = inst.parent.name if inst.parent else ''
    if any(k in par for k in ROOF_KEYS) or any(s in par for s in SKIP):
        continue
    if in_lib(bpy.data.objects.get(par)):
        continue
    ob = inst.object
    M = inst.matrix_world.copy()
    t = M.translation
    if not (BOX0[0] - 8 < t.x < BOX0[2] + 8 and BOX0[1] - 8 < t.y < BOX0[3] + 8):
        continue
    src = bpy.data.objects.get(ob.name) or ob
    verts = src.data.vertices if src.type == 'MESH' else []
    step = max(1, len(verts) // 400)
    for k in range(0, len(verts), step):
        pts.append((par, M @ verts[k].co))
# only points that could be under a roof deck: over the complex and above the eave line's lowest point
BOX = (-7.0, -7.0, 7.0, 7.0)
pts = [(n, p) for (n, p) in pts if p.z > 3.5 and BOX[0] < p.x < BOX[2] and BOX[1] < p.y < BOX[3]]
for (name, p) in pts:
    r = poke(p)
    if r:
        k = (name, r[0])
        if k not in report or report[k][0] < r[1]:
            report[k] = (round(r[1], 3), tuple(round(x, 2) for x in p))
print('points tested', len(pts), 'objects poking through roofs', len(report))
for k, v in sorted(report.items(), key=lambda kv: -kv[1][0])[:40]:
    print(k, v)
