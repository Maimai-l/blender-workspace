# Xingyuan build library - core helpers (collections, bmesh building, instancing, UVs).
# World frame: X = east (0 on the B1 / A4-ridge axis), Y = north (0 at the south walls of A1/A2),
# Z = 0 at the hall floor level. Units: metres.
import bpy, bmesh, math
from mathutils import Vector, Matrix, Euler

ROOT = r'C:\Users\blender\Documents\xingyuan'

# ---------------------------------------------------------------- collections
def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    elif parent is None and c.users > 0:
        return c                      # already placed somewhere: leave it there
    par = parent if parent is not None else bpy.context.scene.collection
    if isinstance(par, str):
        par = coll(par)
    if c.name not in [x.name for x in par.children]:
        # unlink from other parents first (keep tree clean)
        for p in [bpy.context.scene.collection] + list(bpy.data.collections):
            if p != par and c.name in [x.name for x in p.children]:
                p.children.unlink(c)
        par.children.link(c)
    return c

def clear_coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        return
    for ch in list(c.children):
        clear_coll(ch.name)
        bpy.data.collections.remove(ch)
    for o in list(c.objects):
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)

def link(o, c):
    if isinstance(c, str):
        c = coll(c)
    for uc in list(o.users_collection):
        uc.objects.unlink(o)
    c.objects.link(o)
    return o

def lib_coll():
    c = coll('_LIB')
    c.hide_render = True
    try:
        bpy.context.view_layer.layer_collection.children['_LIB'].exclude = False
        bpy.context.view_layer.layer_collection.children['_LIB'].hide_viewport = True
    except Exception:
        pass
    return c

# ---------------------------------------------------------------- materials
def mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        raise KeyError('material missing: ' + name)
    return m

# ---------------------------------------------------------------- bmesh builder
class MB:
    """Accumulates geometry in a bmesh with per-face material slot names."""
    def __init__(self):
        self.bm = bmesh.new()
        self.slots = []
        self.uv = self.bm.loops.layers.uv.new('UVMap')

    def slot(self, mname):
        if mname not in self.slots:
            self.slots.append(mname)
        return self.slots.index(mname)

    def face(self, pts, m, smooth=False):
        vs = [self.bm.verts.new(p) for p in pts]
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        f.material_index = self.slot(m)
        f.smooth = smooth
        return f

    def quad_strip(self, rows, m, smooth=False, closed_u=False):
        """rows: list of rows (each a list of points). Creates a grid surface."""
        vrows = [[self.bm.verts.new(p) for p in r] for r in rows]
        idx = self.slot(m)
        faces = []
        nu = len(rows[0])
        for i in range(len(rows) - 1):
            a, b = vrows[i], vrows[i + 1]
            rng = range(nu) if closed_u else range(nu - 1)
            for j in rng:
                j2 = (j + 1) % nu
                try:
                    f = self.bm.faces.new((a[j], a[j2], b[j2], b[j]))
                except ValueError:
                    continue
                f.material_index = idx
                f.smooth = smooth
                faces.append(f)
        return vrows, faces

    def box(self, mn, mx, m, faces='all'):
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        if z1 < z0: z0, z1 = z1, z0
        P = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        F = {'-z': (0, 3, 2, 1), '+z': (4, 5, 6, 7), '-y': (0, 1, 5, 4),
             '+y': (2, 3, 7, 6), '-x': (3, 0, 4, 7), '+x': (1, 2, 6, 5)}
        vs = [self.bm.verts.new(p) for p in P]
        idx = self.slot(m)
        for k, f in F.items():
            if faces != 'all' and k not in faces:
                continue
            ff = self.bm.faces.new([vs[i] for i in f])
            ff.material_index = idx

    def obox(self, center, axes, half, m):
        """Oriented box: center Vector, axes (3 unit Vectors), half extents (hx,hy,hz)."""
        c = Vector(center)
        ax, ay, az = [Vector(a) for a in axes]
        hx, hy, hz = half
        P = []
        for sz in (-1, 1):
            for sy, sx in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
                P.append(c + ax * (sx * hx) + ay * (sy * hy) + az * (sz * hz))
        vs = [self.bm.verts.new(p) for p in P]
        idx = self.slot(m)
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)):
            ff = self.bm.faces.new([vs[i] for i in f])
            ff.material_index = idx

    def prism(self, poly, z0, z1, m, cap=True, smooth=False):
        """Extrude a closed 2D polygon (list of (x,y), CCW) from z0 to z1."""
        n = len(poly)
        b = [self.bm.verts.new((x, y, z0)) for x, y in poly]
        t = [self.bm.verts.new((x, y, z1)) for x, y in poly]
        idx = self.slot(m)
        for i in range(n):
            j = (i + 1) % n
            f = self.bm.faces.new((b[i], b[j], t[j], t[i]))
            f.material_index = idx
            f.smooth = smooth
        if cap:
            f = self.bm.faces.new(list(reversed(b))); f.material_index = idx
            f = self.bm.faces.new(t); f.material_index = idx

    def lathe(self, prof, segs, m, center=(0, 0, 0), smooth=True, cap_top=True, cap_bot=True):
        """prof: list of (r, z) from bottom to top."""
        cx, cy, cz = center
        rows = []
        for r, z in prof:
            rows.append([(cx + r * math.cos(2 * math.pi * k / segs), cy + r * math.sin(2 * math.pi * k / segs), cz + z)
                         for k in range(segs)])
        vrows, faces = self.quad_strip(rows, m, smooth=smooth, closed_u=True)
        idx = self.slot(m)
        if cap_bot and prof[0][0] > 1e-6:
            f = self.bm.faces.new(list(reversed(vrows[0]))); f.material_index = idx
        if cap_top and prof[-1][0] > 1e-6:
            f = self.bm.faces.new(vrows[-1]); f.material_index = idx
        return vrows

    def sweep(self, path, section, m, ups=None, smooth=False, cap=True, closed_sec=True):
        """Sweep a 2D section [(u,v)...] along a 3D polyline path. u = side axis, v = up axis.
        ups: optional list of up vectors per path point."""
        P = [Vector(p) for p in path]
        n = len(P)
        rows = []
        for i in range(n):
            if i == 0:
                t = (P[1] - P[0])
            elif i == n - 1:
                t = (P[-1] - P[-2])
            else:
                t = (P[i + 1] - P[i - 1])
            t.normalize()
            up = Vector(ups[i]) if ups else Vector((0, 0, 1))
            side = t.cross(up)
            if side.length < 1e-6:
                side = t.cross(Vector((1, 0, 0)))
            side.normalize()
            upv = side.cross(t).normalized()
            rows.append([P[i] + side * u + upv * v for u, v in section])
        vrows, faces = self.quad_strip(rows, m, smooth=smooth, closed_u=closed_sec)
        if cap and closed_sec:
            idx = self.slot(m)
            try:
                f = self.bm.faces.new(list(reversed(vrows[0]))); f.material_index = idx
                f = self.bm.faces.new(vrows[-1]); f.material_index = idx
            except ValueError:
                pass
        return vrows

    def cyl(self, p0, p1, r, segs, m, r1=None, smooth=True, cap=True):
        """Cylinder between two points (r at p0, r1 at p1)."""
        p0 = Vector(p0); p1 = Vector(p1)
        r1 = r if r1 is None else r1
        d = (p1 - p0)
        L = d.length
        t = d.normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a).normalized()
        rows = []
        for (pp, rr) in ((p0, r), (p1, r1)):
            rows.append([pp + (a * math.cos(2 * math.pi * k / segs) + b * math.sin(2 * math.pi * k / segs)) * rr
                         for k in range(segs)])
        vrows, faces = self.quad_strip(rows, m, smooth=smooth, closed_u=True)
        if cap:
            idx = self.slot(m)
            f = self.bm.faces.new(list(reversed(vrows[0]))); f.material_index = idx
            f = self.bm.faces.new(vrows[1]); f.material_index = idx

    def transform(self, M):
        bmesh.ops.transform(self.bm, matrix=M, verts=self.bm.verts)

    def finish(self, name, collection, uv_scale=1.0, merge=0.0, recalc=True, smooth_angle=None, origin=None):
        bm = self.bm
        if recalc:
            # weld coincident vertices so face-by-face built solids become closed shells, then orient outward
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=max(merge, 1e-6))
            try:
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            except Exception:
                pass
            orient_closed_shells(bm)
        elif merge > 0:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
        box_uv(bm, self.uv, uv_scale)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for s in self.slots:
            me.materials.append(mat(s))
        o = bpy.data.objects.new(name, me)
        if smooth_angle is not None:
            try:
                me.set_sharp_from_angle(angle=smooth_angle)
            except Exception:
                pass
        link(o, collection)
        if origin is not None:
            o.location = Vector(origin)
            me.transform(Matrix.Translation(-Vector(origin)))
        return o

def orient_closed_shells(bm):
    """Exact outward orientation: flip every closed (2-manifold) island whose signed volume is negative."""
    bm.faces.ensure_lookup_table()
    seen = set()
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack = [f0]; isl = []
        seen.add(f0.index)
        while stack:
            f = stack.pop(); isl.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index); stack.append(g)
        if not all(len(e.link_faces) == 2 for f in isl for e in f.edges):
            continue
        vol = 0.0
        for f in isl:
            vs = [v.co for v in f.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1]))
        if vol < 0:
            for f in isl:
                f.normal_flip()

def box_uv(bm, uvl, s=1.0):
    """World-scale box projection UVs (metres)."""
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else:
                u, v = co.x, co.y
            l[uvl].uv = (u * s, v * s)

# ---------------------------------------------------------------- instancing
def instancer_group():
    ng = bpy.data.node_groups.get('XY_Instancer')
    if ng:
        return ng
    ng = bpy.data.node_groups.new('XY_Instancer', 'GeometryNodeTree')
    itf = ng.interface
    itf.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    itf.new_socket(name='Instance', in_out='INPUT', socket_type='NodeSocketObject')
    itf.new_socket(name='Proxy', in_out='INPUT', socket_type='NodeSocketObject')
    s = itf.new_socket(name='Use Proxy In Viewport', in_out='INPUT', socket_type='NodeSocketBool')
    s.default_value = False
    itf.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo'); oi.transform_space = 'ORIGINAL'
    oi.inputs['As Instance'].default_value = True
    op = N.new('GeometryNodeObjectInfo'); op.transform_space = 'ORIGINAL'
    op.inputs['As Instance'].default_value = True
    L.new(gi.outputs['Instance'], oi.inputs['Object'])
    L.new(gi.outputs['Proxy'], op.inputs['Object'])
    isv = N.new('GeometryNodeIsViewport')
    andn = N.new('FunctionNodeBooleanMath'); andn.operation = 'AND'
    L.new(isv.outputs[0], andn.inputs[0]); L.new(gi.outputs['Use Proxy In Viewport'], andn.inputs[1])
    sw = N.new('GeometryNodeSwitch'); sw.input_type = 'GEOMETRY'
    L.new(andn.outputs[0], sw.inputs['Switch'])
    L.new(oi.outputs['Geometry'], sw.inputs['False'])
    L.new(op.outputs['Geometry'], sw.inputs['True'])
    ra = N.new('GeometryNodeInputNamedAttribute'); ra.data_type = 'FLOAT_VECTOR'; ra.inputs['Name'].default_value = 'rot'
    sa = N.new('GeometryNodeInputNamedAttribute'); sa.data_type = 'FLOAT_VECTOR'; sa.inputs['Name'].default_value = 'scl'
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(ra.outputs['Attribute'], e2r.inputs['Euler'])
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(gi.outputs['Geometry'], iop.inputs['Points'])
    L.new(sw.outputs[0], iop.inputs['Instance'])
    L.new(e2r.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(sa.outputs['Attribute'], iop.inputs['Scale'])
    L.new(iop.outputs['Instances'], go.inputs['Geometry'])
    return ng

def _sock_id(ng, name):
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', None) == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)

def set_mod_input(mod, name, value):
    """Set a Geometry Nodes modifier input (Blender 5.2 API, with 4.x fallback)."""
    sid = _sock_id(mod.node_group, name)
    props = getattr(mod, 'properties', None)
    if props is not None and hasattr(props, 'inputs'):
        getattr(props.inputs, sid).value = value
    else:
        mod[sid] = value

def instancer(name, src, transforms, collection, proxy=None):
    """transforms: list of (loc, rot_euler(xyz), scale(xyz) or float). src: object to instance."""
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(transforms))
    co = []
    rot = []
    scl = []
    for t in transforms:
        loc, r, s = t
        co.extend(loc)
        rot.extend(r)
        if isinstance(s, (int, float)):
            scl.extend((s, s, s))
        else:
            scl.extend(s)
    me.vertices.foreach_set('co', co)
    a = me.attributes.new('rot', 'FLOAT_VECTOR', 'POINT'); a.data.foreach_set('vector', rot)
    b = me.attributes.new('scl', 'FLOAT_VECTOR', 'POINT'); b.data.foreach_set('vector', scl)
    me.update()
    o = bpy.data.objects.new(name, me)
    link(o, collection)
    ng = instancer_group()
    mod = o.modifiers.new('XY_Instancer', 'NODES')
    mod.node_group = ng
    set_mod_input(mod, 'Instance', src)
    if proxy is not None:
        set_mod_input(mod, 'Proxy', proxy)
        set_mod_input(mod, 'Use Proxy In Viewport', True)
    return o

def rot_from_axes(fx, fy, fz=None):
    """Euler (XYZ) for a rotation whose local X maps to fx and local Y maps to fy."""
    fx = Vector(fx).normalized()
    fy = Vector(fy)
    fz = fx.cross(fy).normalized() if fz is None else Vector(fz).normalized()
    fy = fz.cross(fx).normalized()
    M = Matrix((fx, fy, fz)).transposed()
    return tuple(M.to_euler('XYZ'))

# ---------------------------------------------------------------- misc
def lerp(a, b, t):
    return a + (b - a) * t

def interp(table, x):
    """Piecewise-linear interpolation in a sorted list of (x, y)."""
    if x <= table[0][0]:
        return table[0][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0) if x1 > x0 else 0
            return y0 + (y1 - y0) * t
    return table[-1][1]

def set_parent_keep(o, parent):
    o.parent = parent
    o.matrix_parent_inverse = parent.matrix_world.inverted()
