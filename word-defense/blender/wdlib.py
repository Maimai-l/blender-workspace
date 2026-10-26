# wdlib.py - shared helpers for Word Defense asset generation (Blender 5.2)
# Mesh builder and primitives adapted from the Dungeon Escape kit; palette, paths and export settings are new.
import bpy, bmesh, math, random, os
from mathutils import Vector, Matrix, Euler, Quaternion

UNITY = r"D:/Unity/Projects/Word Defence/Assets/WordDefense"
MODELS = UNITY + "/Models"
WORK = r"C:/Users/blender/Documents/WordDefense"

def srgb(h):
    """'#RRGGBB' -> linear rgb tuple"""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

# name: (hex, metallic, roughness, emission_strength). Unity re-creates these by name (WDAssets.Palette).
PALETTE = {
    "M_Grass": ("#8CC27C", 0.0, 0.9, 0),
    "M_GrassDark": ("#7EB872", 0.0, 0.9, 0),
    "M_GrassLight": ("#9DCC88", 0.0, 0.9, 0),
    "M_Dirt": ("#C9A27A", 0.0, 0.95, 0),
    "M_Road": ("#EED9B0", 0.0, 0.9, 0),
    "M_RoadEdge": ("#D3BE97", 0.0, 0.9, 0),
    "M_Cliff": ("#E2C8A0", 0.0, 0.95, 0),
    "M_CliffB": ("#CDAE86", 0.0, 0.95, 0),
    "M_CliffC": ("#B39272", 0.0, 0.95, 0),
    "M_CliffDark": ("#8C7462", 0.0, 0.95, 0),
    "M_Rock": ("#BDB3A6", 0.0, 0.9, 0),
    "M_RockDark": ("#968C82", 0.0, 0.9, 0),
    "M_Water": ("#5CC6E6", 0.0, 0.15, 0),
    "M_Stone": ("#F3EEE4", 0.0, 0.85, 0),
    "M_StoneShade": ("#DCD3C4", 0.0, 0.85, 0),
    "M_StoneDark": ("#B8AD9C", 0.0, 0.85, 0),
    "M_Roof": ("#4B63D1", 0.0, 0.6, 0),
    "M_RoofDark": ("#3A4DA8", 0.0, 0.6, 0),
    "M_Gold": ("#F2B544", 0.6, 0.35, 0),
    "M_Flag": ("#FF6B5B", 0.0, 0.85, 0),
    "M_Wood": ("#9B6B47", 0.0, 0.85, 0),
    "M_WoodDark": ("#6E4A33", 0.0, 0.85, 0),
    "M_Door": ("#3C3049", 0.0, 0.8, 0),
    "M_Window": ("#2E3A66", 0.0, 0.4, 0),
    "M_WindowLit": ("#FFD27A", 0.0, 0.5, 2.0),
    "M_Steel": ("#3A4766", 0.5, 0.45, 0),
    "M_SteelLight": ("#6B7BA6", 0.5, 0.4, 0),
    "M_Leaf": ("#6CC072", 0.0, 0.85, 0),
    "M_LeafDark": ("#47A06A", 0.0, 0.85, 0),
    "M_LeafAutumn": ("#F4A64A", 0.0, 0.85, 0),
    "M_LeafPink": ("#F7A8C0", 0.0, 0.85, 0),
    "M_Trunk": ("#8A6447", 0.0, 0.9, 0),
    "M_Ink": ("#2A2A4C", 0.0, 0.45, 0),
    "M_InkLight": ("#45407A", 0.0, 0.45, 0),
    "M_InkArmor": ("#5D5B86", 0.3, 0.4, 0),
    "M_InkGlow": ("#FF4FA0", 0.0, 0.4, 4.0),
    "M_EyeWhite": ("#F6F3FF", 0.0, 0.3, 0),
    "M_Crystal": ("#B57CFF", 0.0, 0.2, 2.5),
    "M_PortalStone": ("#4A4462", 0.0, 0.85, 0),
    "M_PortalCore": ("#2B1748", 0.0, 0.5, 1.5),
    "M_Parchment": ("#F5E9CF", 0.0, 0.9, 0),
    "M_ShellGold": ("#FFC24D", 0.7, 0.3, 0),
    "M_ShellCore": ("#FFF1C2", 0.0, 0.3, 3.0),
    "M_Snow": ("#F4F8FF", 0.0, 0.6, 0),
    "M_Cloud": ("#FFFFFF", 0.0, 1.0, 0),
}

def reset():
    try:
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for b in list(coll):
            try:
                coll.remove(b)
            except Exception:
                pass
    scn = bpy.context.scene
    scn.render.fps = 30
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.scale_length = 1.0

def mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    hexcol, metal, rough, emit = PALETTE.get(name, ("#808080", 0, 0.8, 0))
    col = srgb(hexcol)
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    m.diffuse_color = (col[0], col[1], col[2], 1)
    try:
        bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = (col[0], col[1], col[2], 1)
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if emit:
            bsdf.inputs["Emission Color"].default_value = (col[0], col[1], col[2], 1)
            bsdf.inputs["Emission Strength"].default_value = emit
    except Exception as e:
        print("mat warn", name, e)
    return m

def rot_m(rot):
    return Euler((math.radians(rot[0]), math.radians(rot[1]), math.radians(rot[2])), 'XYZ').to_matrix().to_4x4()

def trs(loc=(0, 0, 0), rot=(0, 0, 0), scl=(1, 1, 1)):
    return Matrix.Translation(Vector(loc)) @ rot_m(rot) @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1))

class MB:
    """Accumulates parts into one bmesh with per-face materials and per-part UV offsets."""
    def __init__(self, name, uv_scale=1.0, seed=1):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.uvs = uv_scale
        self.part = 0
        self.part_off = {}
        self.rng = random.Random(seed)
        self.pl = self.bm.faces.layers.int.new("part")
        self.groups = {}   # vertex group name -> list of (BMVert, weight)

    def mi(self, m):
        if m not in self.mats:
            self.mats.append(m)
        return self.mats.index(m)

    def add(self, verts, faces, mat_name, M=None, uv_off=None, recalc=True, group=None):
        self.part += 1
        pid = self.part
        self.part_off[pid] = uv_off if uv_off is not None else (self.rng.random() * 3.0, self.rng.random() * 3.0)
        mi = self.mi(mat_name)
        bv = []
        for co in verts:
            v = Vector(co)
            if M is not None:
                v = M @ v
            bv.append(self.bm.verts.new(v))
        nf = []
        for f in faces:
            try:
                face = self.bm.faces.new([bv[i] for i in f])
            except ValueError:
                continue
            face.material_index = mi
            face[self.pl] = pid
            nf.append(face)
        if recalc and nf:
            bmesh.ops.recalc_face_normals(self.bm, faces=nf)
        if group is not None:
            if isinstance(group, str):
                self.groups.setdefault(group, []).extend((v, 1.0) for v in bv)
            else:  # callable(vert_world_pos) -> list[(name, w)]
                for v in bv:
                    for gname, w in group(v.co):
                        self.groups.setdefault(gname, []).append((v, w))
        return bv

    def finish(self, smooth_angle=38.0, link=True, flip=False):
        bm = self.bm
        bm.normal_update()
        uv = bm.loops.layers.uv.verify()
        for f in bm.faces:
            n = f.normal
            ax = max(range(3), key=lambda i: abs(n[i]))
            du, dv = self.part_off.get(f[self.pl], (0, 0))
            for l in f.loops:
                co = l.vert.co
                if ax == 0:
                    u, v = co.y, co.z
                elif ax == 1:
                    u, v = co.x, co.z
                else:
                    u, v = co.x, co.y
                l[uv].uv = (u * self.uvs + du, v * self.uvs + dv)
        if flip:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        # map BMVerts to indices for vertex groups
        bm.verts.index_update()
        gidx = {g: [(v.index, w) for v, w in lst if v.is_valid] for g, lst in self.groups.items()}
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(mat(m))
        for p in me.polygons:
            p.use_smooth = True
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception as e:
            print("sharp warn", e)
        ob = bpy.data.objects.new(self.name, me)
        if link:
            bpy.context.scene.collection.objects.link(ob)
        for g, lst in gidx.items():
            vg = ob.vertex_groups.new(name=g)
            for i, w in lst:
                vg.add([i], w, 'ADD')
        return ob

# ---------- primitives (geometry generators) ----------
def cbox_geo(hx, hy, hz, b):
    if b <= 0.0005:
        v = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        f = [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
        return v, f
    b = min(b, hx * 0.49, hy * 0.49, hz * 0.49)
    verts = []
    idx = {}
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                idx[(sx, sy, sz, 'x')] = len(verts); verts.append((sx * hx, sy * (hy - b), sz * (hz - b)))
                idx[(sx, sy, sz, 'y')] = len(verts); verts.append((sx * (hx - b), sy * hy, sz * (hz - b)))
                idx[(sx, sy, sz, 'z')] = len(verts); verts.append((sx * (hx - b), sy * (hy - b), sz * hz))
    faces = []
    for s in (-1, 1):
        faces.append([idx[(s, -1, -1, 'x')], idx[(s, 1, -1, 'x')], idx[(s, 1, 1, 'x')], idx[(s, -1, 1, 'x')]])
        faces.append([idx[(-1, s, -1, 'y')], idx[(1, s, -1, 'y')], idx[(1, s, 1, 'y')], idx[(-1, s, 1, 'y')]])
        faces.append([idx[(-1, -1, s, 'z')], idx[(1, -1, s, 'z')], idx[(1, 1, s, 'z')], idx[(-1, 1, s, 'z')]])
    for sy in (-1, 1):
        for sz in (-1, 1):
            faces.append([idx[(-1, sy, sz, 'y')], idx[(1, sy, sz, 'y')], idx[(1, sy, sz, 'z')], idx[(-1, sy, sz, 'z')]])
    for sx in (-1, 1):
        for sz in (-1, 1):
            faces.append([idx[(sx, -1, sz, 'x')], idx[(sx, 1, sz, 'x')], idx[(sx, 1, sz, 'z')], idx[(sx, -1, sz, 'z')]])
    for sx in (-1, 1):
        for sy in (-1, 1):
            faces.append([idx[(sx, sy, -1, 'x')], idx[(sx, sy, 1, 'x')], idx[(sx, sy, 1, 'y')], idx[(sx, sy, -1, 'y')]])
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                faces.append([idx[(sx, sy, sz, 'x')], idx[(sx, sy, sz, 'y')], idx[(sx, sy, sz, 'z')]])
    return verts, faces

def cbox(mb, center, size, mat_name, b=0.02, rot=(0, 0, 0), M=None, uv_off=None, group=None):
    v, f = cbox_geo(size[0] / 2.0, size[1] / 2.0, size[2] / 2.0, b)
    T = Matrix.Translation(Vector(center)) @ rot_m(rot)
    if M is not None:
        T = M @ T
    return mb.add(v, f, mat_name, T, uv_off, group=group)

def box_mm(mb, mn, mx, mat_name, b=0.0, M=None, rot=(0, 0, 0), group=None):
    c = ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    s = (abs(mx[0] - mn[0]), abs(mx[1] - mn[1]), abs(mx[2] - mn[2]))
    return cbox(mb, c, s, mat_name, b, rot, M, group=group)

def hexa(mb, pts, mat_name, M=None, group=None):
    f = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return mb.add(pts, f, mat_name, M, group=group)

def lathe(mb, profile, segs, mat_name, M=None, cap_bottom=True, cap_top=True, phase=0.0, group=None):
    """profile: list of (radius, z) bottom->top, revolved around Z."""
    verts = []
    rings = []
    for (r, z) in profile:
        if r < 1e-5:
            rings.append([len(verts)])
            verts.append((0, 0, z))
        else:
            ring = []
            for i in range(segs):
                a = phase + 2 * math.pi * i / segs
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    faces = []
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        if len(A) == 1 and len(B) == 1:
            continue
        for i in range(segs):
            j = (i + 1) % segs
            if len(A) == 1:
                faces.append([A[0], B[i], B[j]])
            elif len(B) == 1:
                faces.append([A[i], A[j], B[0]])
            else:
                faces.append([A[i], A[j], B[j], B[i]])
    if cap_bottom and len(rings[0]) > 1:
        faces.append(list(reversed(rings[0])))
    if cap_top and len(rings[-1]) > 1:
        faces.append(list(rings[-1]))
    return mb.add(verts, faces, mat_name, M, group=group)

def cyl(mb, center, r, h, segs, mat_name, rot=(0, 0, 0), r2=None, M=None, group=None):
    r2 = r if r2 is None else r2
    T = Matrix.Translation(Vector(center)) @ rot_m(rot)
    if M is not None:
        T = M @ T
    return lathe(mb, [(r, -h / 2), (r2, h / 2)], segs, mat_name, T, group=group)

def sphere(mb, center, radius, mat_name, segs=12, rings=8, scl=(1, 1, 1), rot=(0, 0, 0), M=None, group=None):
    prof = []
    for k in range(rings + 1):
        t = math.pi * k / rings
        prof.append((radius * math.sin(t), -radius * math.cos(t)))
    T = Matrix.Translation(Vector(center)) @ rot_m(rot) @ Matrix.Diagonal((scl[0], scl[1], scl[2], 1))
    if M is not None:
        T = M @ T
    return lathe(mb, prof, segs, mat_name, T, group=group)

def torus(mb, center, R, r, mat_name, segs=16, csegs=8, rot=(0, 0, 0), arc=1.0, M=None, group=None):
    verts = []
    faces = []
    n_main = segs if arc >= 0.999 else segs + 1
    for i in range(n_main):
        a = 2 * math.pi * arc * i / segs
        for j in range(csegs):
            b = 2 * math.pi * j / csegs
            x = (R + r * math.cos(b)) * math.cos(a)
            y = (R + r * math.cos(b)) * math.sin(a)
            z = r * math.sin(b)
            verts.append((x, y, z))
    rng_i = segs if arc >= 0.999 else segs
    for i in range(rng_i):
        i2 = (i + 1) % n_main
        for j in range(csegs):
            j2 = (j + 1) % csegs
            faces.append([i * csegs + j, i2 * csegs + j, i2 * csegs + j2, i * csegs + j2])
    if arc < 0.999:
        faces.append([j for j in range(csegs)])
        faces.append([(n_main - 1) * csegs + j for j in reversed(range(csegs))])
    T = Matrix.Translation(Vector(center)) @ rot_m(rot)
    if M is not None:
        T = M @ T
    return mb.add(verts, faces, mat_name, T, group=group)

def limb(mb, p0, p1, r0, r1, segs, mat_name, group=None, caps=True, bulge=0.0):
    p0 = Vector(p0); p1 = Vector(p1)
    d = p1 - p0
    L = d.length
    q = Vector((0, 0, 1)).rotation_difference(d.normalized())
    T = Matrix.Translation(p0) @ q.to_matrix().to_4x4()
    if bulge > 0:
        prof = [(r0, 0), ((r0 + r1) / 2 + bulge, L * 0.5), (r1, L)]
    else:
        prof = [(r0, 0), (r1, L)]
    return lathe(mb, prof, segs, mat_name, T, cap_bottom=caps, cap_top=caps, group=group)

def quad_strip(mb, pts_a, pts_b, mat_name, M=None, recalc=False, group=None):
    """Two polylines of equal length -> strip of quads (a_i, a_i+1, b_i+1, b_i)."""
    verts = list(pts_a) + list(pts_b)
    n = len(pts_a)
    faces = [[i, i + 1, n + i + 1, n + i] for i in range(n - 1)]
    return mb.add(verts, faces, mat_name, M, recalc=recalc, group=group)

# ---------- coordinates ----------
# The FBX export below maps Blender (x, y, z) to Unity (-x, z, -y). World layout is designed in Unity coordinates.
def U(ux, uz, uy=0.0):
    """Unity (x, z[, y]) -> Blender vector"""
    return Vector((-ux, -uz, uy))

# ---------- objects ----------
def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.location = Vector(loc)
    bpy.context.scene.collection.objects.link(e)
    if parent is not None:
        e.parent = parent
    return e

def parent_keep(child, parent):
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw

def set_origin(ob, world_point):
    """Moves the object origin to world_point without moving the geometry."""
    wp = Vector(world_point)
    local = ob.matrix_world.inverted() @ wp
    ob.data.transform(Matrix.Translation(-local))
    ob.matrix_world = ob.matrix_world @ Matrix.Translation(local)

def part(mb, origin):
    """Finishes a mesh builder whose geometry was authored in world space and puts the origin at 'origin'."""
    ob = mb.finish()
    set_origin(ob, origin)
    return ob

# ---------- export ----------
def export_fbx(objs, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y', bake_space_transform=True,
        object_types={'MESH', 'EMPTY'}, mesh_smooth_type='FACE', use_mesh_modifiers=True,
        add_leaf_bones=False, bake_anim=False, path_mode='AUTO', embed_textures=False)
    print("exported", path, len(objs))

def collect(root):
    out = [root]
    for c in root.children_recursive:
        out.append(c)
    return out

def save_blend(name):
    os.makedirs(WORK, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=WORK + "/" + name + ".blend", copy=True)
