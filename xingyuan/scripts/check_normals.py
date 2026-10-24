# Normal check: (1) closed shells with negative signed volume (inside-out); (2) roof decks / paving whose
# top faces point down; (3) non-manifold edge counts per object for information.
import bpy, bmesh
from mathutils import Vector
res = []
tot_closed = tot_inv = 0
for o in bpy.data.objects:
    if o.type != 'MESH' or not o.data.polygons:
        continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    seen = set(); inv = closed = 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        # flood fill island
        stack = [f0]; isl = []
        seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index); stack.append(g)
        edges = {e for f in isl for e in f.edges}
        if all(len(e.link_faces) == 2 for e in edges):
            closed += 1
            vol = 0.0
            for f in isl:
                vs = [v.co for v in f.verts]
                for i in range(1, len(vs) - 1):
                    vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
            if vol < -1e-9:
                inv += 1
    tot_closed += closed; tot_inv += inv
    if inv:
        res.append((o.name, closed, inv))
    bm.free()
print('closed shells', tot_closed, 'inside-out shells', tot_inv)
for r in sorted(res, key=lambda r: -r[2])[:30]:
    print(r)
# roof decks: tile-side faces must point up
bad = []
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.endswith('_望板'):
        me = o.data
        ti = me.materials.find('M_Tile')
        n_dn = sum(1 for p in me.polygons if p.material_index == ti and (o.matrix_world.to_3x3() @ p.normal).z < -0.2)
        if n_dn:
            bad.append((o.name, n_dn))
print('roof decks with downward tile faces', len(bad), bad[:10])
