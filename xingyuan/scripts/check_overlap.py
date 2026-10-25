# Detect coplanar overlapping faces (z-fighting risk) between and within unique (non-instanced) mesh objects.
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
dg = bpy.context.evaluated_depsgraph_get()
# optional: ONLY = name prefix of the objects to test against everything; SKIP = name prefixes left out entirely
ONLY = globals().get('ONLY')
SKIP = tuple(globals().get('SKIP', ('环境_地形', '环境_远景地面', '环境_水体')))
objs = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('SRC_') and o.visible_get()
        and not o.name.startswith(SKIP)
        and not any(m.type == 'NODES' for m in o.modifiers) and len(o.data.polygons) > 0]
data = {}
for o in objs:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bm.faces.ensure_lookup_table()
    data[o.name] = (bm, BVHTree.FromBMesh(bm, epsilon=0.0))
issues = []
# candidate pairs by bbox overlap
def bbox(o):
    cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs), max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs))
bbs = {o.name: bbox(o) for o in objs}
names = list(data)
def ov(a, b, e=0.01):
    return all(a[i] <= b[i + 3] + e and b[i] <= a[i + 3] + e for i in range(3))
count = 0
for ai, an in enumerate(names):
    bmA, tA = data[an]
    for bn in names[ai:]:
        if ONLY and not (an.startswith(ONLY) or bn.startswith(ONLY)):
            continue
        if not ov(bbs[an], bbs[bn]):
            continue
        bmB, tB = data[bn]
        hits = 0
        tested = 0
        for f in bmA.faces:
            if f.calc_area() < 0.01:
                continue
            c = f.calc_center_median(); n = f.normal
            tested += 1
            # same-facing coplanar faces within 1.5 mm = z-fighting risk (opposite-facing touching faces are hidden)
            for s in (1, -1):
                loc, nrm, idx, dist = tB.ray_cast(c + n * 0.0015 * s, -n * s, 0.003)
                if loc is not None and nrm.dot(n) > 0.999:
                    if bn == an and idx == f.index:
                        continue
                    # visible only if nothing (in A or B) sits directly in front within 4 mm
                    covered = False
                    for tt in (tA, tB):
                        l2, n2, i2, d2 = tt.ray_cast(c + n * 0.0002, n, 0.004)
                        if l2 is not None:
                            covered = True
                            break
                    if not covered:
                        hits += 1
                    break
        if hits:
            issues.append((an, bn, hits, tested))
issues.sort(key=lambda t: -t[2])
print('objects checked', len(objs), 'pairs with coplanar overlaps', len(issues))
for t in issues[:70]:
    print(t)
for bm, t in data.values():
    bm.free()
