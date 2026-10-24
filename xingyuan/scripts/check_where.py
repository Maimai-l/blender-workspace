# list locations of same-facing coplanar overlaps inside one object
import bpy, bmesh
from mathutils.bvhtree import BVHTree
name = globals().get('OBJ', 'A1_墙体门窗')
o = bpy.data.objects[name]
bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world); bm.faces.ensure_lookup_table()
t = BVHTree.FromBMesh(bm)
out = []
for f in bm.faces:
    if f.calc_area() < 0.005:
        continue
    c = f.calc_center_median(); n = f.normal
    for s in (1, -1):
        loc, nrm, idx, dist = t.ray_cast(c + n * 0.0015 * s, -n * s, 0.003)
        if loc is not None and nrm.dot(n) > 0.999 and idx != f.index:
            l2, n2, i2, d2 = t.ray_cast(c + n * 0.0002, n, 0.004)
            if l2 is not None:
                break
            mat = o.data.materials[f.material_index].name
            out.append((round(c.x, 2), round(c.y, 2), round(c.z, 2), tuple(round(v, 2) for v in n), round(f.calc_area(), 3), mat))
            break
print(len(out))
for r in out[:40]:
    print(r)
bm.free()
