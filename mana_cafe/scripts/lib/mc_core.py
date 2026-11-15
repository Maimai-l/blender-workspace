"""Shared helpers for the Mana cafe scene scripts (run inside Blender)."""
import bpy, os, math
import numpy as np

ROOT = r'D:\Blender\Projects\mana_cafe'
DEM = os.path.join(ROOT, 'dem')
ASSETS = os.path.join(ROOT, 'assets')
RENDERS = os.path.join(ROOT, 'renders')
BUILDING = 'C-组件#225'          # the cafe: never edited (geometry and interior stay as modelled)


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def link(obj, collection):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def remove_object(name):
    o = bpy.data.objects.get(name)
    if o is None:
        return
    me = o.data if o.type == 'MESH' else None
    bpy.data.objects.remove(o, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def grid_mesh(name, co, nr, ncol, keep=None, attrs=None):
    """Mesh from a structured grid of nr x ncol vertices (row-major). keep: optional bool [nr-1, ncol-1] of quads to
    create. attrs: dict name -> float array per vertex."""
    me = bpy.data.meshes.new(name)
    n = nr * ncol
    me.vertices.add(n)
    me.vertices.foreach_set('co', np.ascontiguousarray(co, np.float32).ravel())
    idx = np.arange(n, dtype=np.int32).reshape(nr, ncol)
    a = idx[:-1, :-1]
    b = idx[:-1, 1:]
    c = idx[1:, 1:]
    d = idx[1:, :-1]
    quads = np.stack([a, b, c, d], -1).reshape(-1, 4)
    if keep is not None:
        quads = quads[np.asarray(keep).ravel()]
    nq = quads.shape[0]
    me.loops.add(nq * 4)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(nq)
    me.polygons.foreach_set('loop_start', np.arange(0, nq * 4, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    for k, v in (attrs or {}).items():
        at = me.attributes.new(k, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.ascontiguousarray(v, np.float32).ravel())
    return me


def tri_mesh(name, co, tris, attrs=None):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', np.ascontiguousarray(co, np.float32).ravel())
    nt = len(tris)
    me.loops.add(nt * 3)
    me.loops.foreach_set('vertex_index', np.ascontiguousarray(tris, np.int32).ravel())
    me.polygons.add(nt)
    me.polygons.foreach_set('loop_start', np.arange(0, nt * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    for k, v in (attrs or {}).items():
        at = me.attributes.new(k, 'FLOAT', 'POINT')
        at.data.foreach_set('value', np.ascontiguousarray(v, np.float32).ravel())
    return me


def obj(name, mesh, collection, mat=None):
    remove_object(name)
    o = bpy.data.objects.new(name, mesh)
    collection.objects.link(o)
    if mat is not None:
        mesh.materials.append(mat)
    return o


# ------------------------------------------------------------------ node helpers
def new_mat(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes.clear()
    return m, m.node_tree


class NT:
    """Tiny builder: n = NT(tree); a = n.node('ShaderNodeMath', operation='ADD', inputs={0: x, 1: 2.0})"""

    def __init__(self, tree):
        self.t = tree
        self.x = 0

    def node(self, typ, inputs=None, label=None, **props):
        nd = self.t.nodes.new(typ)
        self.x += 1
        nd.location = (self.x * 40, -(self.x % 12) * 60)
        if label:
            nd.label = label
        for k, v in props.items():
            setattr(nd, k, v)
        for k, v in (inputs or {}).items():
            sock = nd.inputs[k]
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, sock)
            elif v is not None:
                sock.default_value = v
        return nd

    def link(self, a, b):
        self.t.links.new(a, b)

    def math(self, op, a, b=None, c=None, clamp=False):
        nd = self.node('ShaderNodeMath', operation=op, use_clamp=clamp, inputs={0: a})
        for i, v in ((1, b), (2, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, nd.inputs[i])
            else:
                nd.inputs[i].default_value = v
        return nd.outputs[0]

    def mix(self, fac, a, b, blend='MIX', clamp=True):
        nd = self.node('ShaderNodeMix', data_type='RGBA', blend_type=blend, clamp_factor=clamp)
        for i, v in ((0, fac), (6, a), (7, b)):
            sock = nd.inputs[i]
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, sock)
            elif i == 0:
                sock.default_value = float(v)
            else:
                sock.default_value = (v, v, v, 1) if isinstance(v, (int, float)) else v
        return nd.outputs[2]

    def mixf(self, fac, a, b):
        nd = self.node('ShaderNodeMix', data_type='FLOAT', clamp_factor=True)
        for sock, v in ((nd.inputs[0], fac), (nd.inputs[2], a), (nd.inputs[3], b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.t.links.new(v, sock)
            else:
                sock.default_value = v
        return nd.outputs[0]

    def ramp(self, fac, stops, interp='LINEAR'):
        nd = self.node('ShaderNodeValToRGB', inputs={0: fac})
        cr = nd.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        cr.elements[0].position = stops[0][0]
        cr.elements[0].color = stops[0][1]
        for p, c in stops[1:]:
            e = cr.elements.new(p)
            e.color = c
        return nd.outputs[0]

    def smooth(self, x, lo, hi):
        nd = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP',
                       inputs={0: x, 1: lo, 2: hi, 3: 0.0, 4: 1.0})
        return nd.outputs[0]

    def lin(self, x, lo, hi, a=0.0, b=1.0):
        nd = self.node('ShaderNodeMapRange', interpolation_type='LINEAR', clamp=True,
                       inputs={0: x, 1: lo, 2: hi, 3: a, 4: b})
        return nd.outputs[0]

    def attr(self, name):
        return self.node('ShaderNodeAttribute', attribute_name=name, attribute_type='GEOMETRY')

    def noise(self, vec, scale, detail=6.0, rough=0.55, lac=2.0, dist=0.0, dims='3D', w=None):
        nd = self.node('ShaderNodeTexNoise', noise_dimensions=dims,
                       inputs={'Scale': scale, 'Detail': detail, 'Roughness': rough, 'Lacunarity': lac,
                               'Distortion': dist})
        if vec is not None:
            self.t.links.new(vec, nd.inputs['Vector'])
        if w is not None:
            nd.inputs['W'].default_value = w
        return nd
