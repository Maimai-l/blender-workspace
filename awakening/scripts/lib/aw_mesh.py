"""bmesh primitive helpers for building the robot parts in a part's local space."""
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler

def new_bm():
    """A bmesh with the Freestyle edge-mark layer created up front (creating layers later invalidates references)."""
    bm = bmesh.new()
    bm.edges.layers.bool.new('freestyle_edge')
    return bm

def _mat(center, rot=(0, 0, 0), scale=(1, 1, 1)):
    return Matrix.Translation(Vector(center)) @ Euler([math.radians(a) for a in rot]).to_matrix().to_4x4() @ Matrix.Diagonal((*scale, 1))

def _apply(bm, geom, m, mat_index, mark=False):
    verts = [g for g in geom if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.transform(bm, matrix=m, verts=verts)
    faces = [g for g in geom if isinstance(g, bmesh.types.BMFace)]
    for f in faces:
        f.material_index = mat_index
        f.smooth = False
    return verts, faces

def box(bm, size, center, mi=0, rot=(0, 0, 0), taper=1.0, taper_y=None, bev=0.0, bev_seg=1, subdiv=2):
    """Axis box; taper scales the +Z face (x and y) relative to the -Z face. bev > 0 chamfers edges."""
    r = bmesh.ops.create_cube(bm, size=1.0)
    verts = r['verts']
    ty = taper if taper_y is None else taper_y
    for v in verts:
        s = taper if v.co.z > 0 else 1.0
        sy = ty if v.co.z > 0 else 1.0
        v.co.x *= size[0] * s
        v.co.y *= size[1] * sy
        v.co.z *= size[2]
    faces = list({f for v in verts for f in v.link_faces})
    if bev > 0:
        edges = list({e for v in verts for e in v.link_edges})
        rb = bmesh.ops.bevel(bm, geom=edges, offset=bev, segments=bev_seg, profile=0.5, affect='EDGES', clamp_overlap=True)
        faces = list({f for f in faces if f.is_valid} | set(rb['faces']))
        verts = list({v for f in faces for v in f.verts})
    m = _mat(center, rot)
    bmesh.ops.transform(bm, matrix=m, verts=verts)
    for f in faces:
        f.material_index = mi
        f.smooth = bev > 0 and bev_seg > 1
    if subdiv:
        # finer vertices so baked per-vertex weathering can vary across a plate
        edges = list({e for f in faces for e in f.edges})
        r = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=subdiv, use_grid_fill=True)
        faces = list({f for f in faces if f.is_valid} | {g for g in r['geom_inner'] if isinstance(g, bmesh.types.BMFace)}
                     | {g for g in r['geom_split'] if isinstance(g, bmesh.types.BMFace)})
        for f in faces:
            f.material_index = mi
        verts = list({v for f in faces for v in f.verts})
    return verts, faces

def cyl(bm, r1, r2, h, center, mi=0, rot=(0, 0, 0), segs=24, cap=True, smooth=True):
    r = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=r1, radius2=r2, depth=h)
    verts = r['verts']
    faces = list({f for v in verts for f in v.link_faces})
    bmesh.ops.transform(bm, matrix=_mat(center, rot), verts=verts)
    for f in faces:
        f.material_index = mi
        # caps stay flat, sides smooth
        f.smooth = smooth and abs(f.normal.z) < 0.99 if False else smooth
    return verts, faces

def sphere(bm, rad, center, mi=0, scale=(1, 1, 1), rot=(0, 0, 0), segs=24, rings=12, cut_below=None):
    r = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=rad)
    verts = r['verts']
    if cut_below is not None:
        # remove the part below local z = cut_below (fraction of radius)
        low = [v for v in verts if v.co.z < cut_below * rad - 1e-6]
        bmesh.ops.delete(bm, geom=low, context='VERTS')
        verts = [v for v in verts if v.is_valid]
        # close the hole
        edges = [e for e in {e for v in verts for e in v.link_edges} if e.is_boundary]
        if edges:
            res = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
            for f in res['faces']:
                f.material_index = mi
                f.smooth = False
    faces = list({f for v in verts for f in v.link_faces})
    bmesh.ops.transform(bm, matrix=_mat(center, rot, scale), verts=verts)
    for f in faces:
        f.material_index = mi
        f.smooth = True
    return verts, faces

def torus(bm, R, r, center, mi=0, rot=(0, 0, 0), segs=32, rsegs=10):
    verts = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for j in range(rsegs):
            b = 2 * math.pi * j / rsegs
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            verts.append(bm.verts.new((x, y, z)))
    faces = []
    for i in range(segs):
        for j in range(rsegs):
            a0 = verts[i * rsegs + j]; a1 = verts[i * rsegs + (j + 1) % rsegs]
            b0 = verts[((i + 1) % segs) * rsegs + j]; b1 = verts[((i + 1) % segs) * rsegs + (j + 1) % rsegs]
            f = bm.faces.new((a0, b0, b1, a1)); f.material_index = mi; f.smooth = True
            faces.append(f)
    bmesh.ops.transform(bm, matrix=_mat(center, rot), verts=verts)
    return verts, faces

def mark_edges(bm, edges):
    lay = bm.edges.layers.bool.get('freestyle_edge')
    for e in edges:
        e[lay] = True

def groove(bm, verts_faces, plane_co, plane_no, mark=True):
    """Cut the given faces by a plane and mark the new edges for Freestyle (a drawn panel line)."""
    verts, faces = verts_faces
    geom = list(set(verts)) + list({e for f in faces for e in f.edges}) + list(faces)
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=plane_co, plane_no=plane_no, dist=1e-4)
    new_edges = [g for g in res['geom_cut'] if isinstance(g, bmesh.types.BMEdge)]
    if mark:
        mark_edges(bm, new_edges)
    allv = list({v for f in faces if f.is_valid for v in f.verts} | {g for g in res['geom_cut'] if isinstance(g, bmesh.types.BMVert)})
    allf = list({f for v in allv for f in v.link_faces})
    return allv, allf

def finish(bm, name, mats, coll, parent=None, loc=(0, 0, 0), rot=(0, 0, 0)):
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = [math.radians(a) for a in rot]
    if parent is not None:
        ob.parent = parent
    return ob
