# Xingyuan - plant library: leaf sprays, willow strands, tree templates (branches + instanced foliage),
# shrubs, bank plants, lotus, grass clumps, rocks. All geometry is procedural (no image textures).
# A tree template is ONE mesh object: branch faces + loose "foliage points" (attributes kind/rot/scl/rnd);
# its XY_Foliage modifier instances leaf sprays from a collection on those points (proxy set in the viewport).
import bpy, bmesh, math, random, zlib
from mathutils import Vector, Matrix, Quaternion
import xy_core as C

LIBC = '_LIB'

def lib():
    return C.lib_coll()

def src_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        lib().children.link(c)
    return c

def _clear_obj(name):
    o = bpy.data.objects.get(name)
    if o is not None:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and getattr(me, 'users', 1) == 0:
            bpy.data.meshes.remove(me)

def _finish_src(mb, name, coll):
    _clear_obj(name)
    o = mb.finish(name, coll, recalc=False)
    return o

# ------------------------------------------------------------------ leaves
def leaf(mb, c, dx, nz, L, W, m, fold=0.3, tip=0.62):
    """6-vertex leaf: base at c, axis dx, normal ~nz. W = half width."""
    dx = dx.normalized()
    dy = dx.cross(nz)
    if dy.length < 1e-6:
        dy = dx.orthogonal()
    dy.normalize()
    n2 = dy.cross(dx).normalized()
    f = W * fold
    pts = [c, c + dx * L * 0.22 + dy * W * 0.8 + n2 * f, c + dx * L * tip + dy * W * 0.95 + n2 * f,
           c + dx * L, c + dx * L * tip - dy * W * 0.95 + n2 * f, c + dx * L * 0.22 - dy * W * 0.8 + n2 * f]
    mb.face(pts, m)

def spray(name, coll, m, n, rad, L, W, seed, up_bias=0.35, flat=0.75, size_var=0.25):
    """A spray (cluster) of leaves around the origin, radius rad."""
    mb = C.MB()
    r = random.Random(seed)
    for i in range(n):
        c = Vector((r.gauss(0, rad * 0.5), r.gauss(0, rad * 0.5), r.gauss(0, rad * 0.38)))
        if c.length > rad:
            c = c.normalized() * rad * r.uniform(0.7, 1.0)
        a = r.uniform(0, 2 * math.pi)
        dx = Vector((math.cos(a), math.sin(a), r.uniform(-0.25, 0.55))).normalized()
        nz = Vector((r.gauss(0, 1 - flat), r.gauss(0, 1 - flat), 1.0)).normalized()
        nz = (nz + Vector((0, 0, up_bias))).normalized()
        s = 1 + r.uniform(-size_var, size_var)
        leaf(mb, c, dx, nz, L * s, W * s, m)
    return _finish_src(mb, name, coll)

def willow_strand(name, coll, length, seed, m='M_LeafWillow', twig='M_BarkWillow'):
    """A hanging willow strand (origin at the top, hangs along -Z) with narrow leaves along it."""
    mb = C.MB()
    r = random.Random(seed)
    n = max(4, int(length / 0.16))
    sway = r.uniform(0.04, 0.12)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(Vector((sway * math.sin(t * 2.4) * t, sway * 0.4 * math.sin(t * 3.1), -length * t)))
    # twig: a thin ribbon
    for i in range(n):
        a, b = pts[i], pts[i + 1]
        w0 = 0.004 * (1 - 0.7 * i / n); w1 = 0.004 * (1 - 0.7 * (i + 1) / n)
        mb.face([a + Vector((-w0, 0, 0)), a + Vector((w0, 0, 0)), b + Vector((w1, 0, 0)), b + Vector((-w1, 0, 0))], twig)
    # leaves: every ~5.5 cm, alternating around the twig, pointing down/outward
    k = int(length / 0.042)
    for j in range(k):
        t = (j + 0.5) / k
        i = min(n - 1, int(t * n)); f = t * n - i
        c = pts[i].lerp(pts[i + 1], f)
        a = j * 2.4 + r.uniform(-0.3, 0.3)
        out = Vector((math.cos(a), math.sin(a), 0))
        dx = (out * r.uniform(0.35, 0.65) + Vector((0, 0, -1))).normalized()
        nz = out.cross(Vector((0, 0, 1))).normalized() if r.random() < 0.5 else out
        L = r.uniform(0.075, 0.115) * (0.75 + 0.25 * min(1.0, t * 3))
        leaf(mb, c, dx, (nz + Vector((0, 0, 0.3))).normalized(), L, L * 0.085, m, fold=0.15, tip=0.55)
    return _finish_src(mb, name, coll)

def branchlet(name, coll, m, seed, twig='M_Bark', n_twigs=6, tw_len=(0.25, 0.45), L=0.09, W=0.022, step=0.03, tip_n=5,
              el=(-0.25, 0.55), tw_r=0.004):
    """Leafy branchlet: n twigs radiating from the origin, alternate leaves along each twig, a leaf cluster at the tip."""
    mb = C.MB()
    r = random.Random(seed)
    for t in range(n_twigs):
        a = 2 * math.pi * t / n_twigs + r.uniform(-0.45, 0.45)
        e = r.uniform(*el)
        d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
        Lt = r.uniform(*tw_len)
        p0 = d * 0.01
        p2 = d * Lt + Vector((0, 0, -0.08 * Lt * r.random()))
        p1 = d * Lt * 0.5 + Vector((0, 0, 0.06 * Lt))
        pts = bez(p0, p1, p2, 4)
        tube_r(mb, pts, [tw_r, tw_r * 0.85, tw_r * 0.7, tw_r * 0.6, tw_r * 0.45], twig, segs=3)
        n = max(2, int(Lt / step))
        side = 1
        for k in range(1, n + 1):
            sp = k / (n + 0.5)
            i = min(3, int(sp * 4)); f = sp * 4 - i
            c = pts[i].lerp(pts[i + 1], f)
            perp = d.cross(Vector((0, 0, 1)))
            if perp.length < 1e-4:
                perp = Vector((1, 0, 0))
            perp = perp.normalized() * side
            side = -side
            ax = (d * r.uniform(0.45, 0.8) + perp * 0.8 + Vector((0, 0, r.uniform(-0.15, 0.35)))).normalized()
            nz = Vector((r.gauss(0, 0.3), r.gauss(0, 0.3), 1.0)).normalized()
            sc = (0.7 + 0.4 * sp) * r.uniform(0.85, 1.15)
            leaf(mb, c, ax, nz, L * sc, W * sc, m)
        for k in range(tip_n):
            ang = 2 * math.pi * k / tip_n + r.uniform(-0.3, 0.3)
            ax = (d * 0.7 + Vector((math.cos(ang), math.sin(ang), 0.35)) * 0.6).normalized()
            nz = Vector((r.gauss(0, 0.3), r.gauss(0, 0.3), 1.0)).normalized()
            leaf(mb, p2, ax, nz, L * r.uniform(0.9, 1.15), W * r.uniform(0.9, 1.15), m)
    return _finish_src(mb, name, coll)

def willow_curtain(name, coll, length, seed, n_strands=6, m='M_LeafWillow', twig='M_BarkWillow', width=0.6):
    """A willow branchlet: a short twig arching out along +X from the origin, with n hanging leafy strands of
    varied length (nominal `length`). Leaves in opposite-ish pairs every ~3 cm."""
    mb = C.MB()
    r = random.Random(seed)
    arch = bez(Vector((0, 0, 0)), Vector((width * 0.45, 0, 0.14)), Vector((width, 0, -0.06)), 6)
    tube_r(mb, arch, [0.006 - 0.0006 * i for i in range(7)], twig, segs=3)
    for s_ in range(n_strands):
        t = 0.2 + 0.8 * s_ / max(1, n_strands - 1)
        i = min(5, int(t * 6)); f = t * 6 - i
        top = arch[i].lerp(arch[i + 1], f) + Vector((0, r.uniform(-0.12, 0.12), 0))
        Ls = length * r.uniform(0.55, 1.05)
        n = max(4, int(Ls / 0.16))
        sway = r.uniform(0.03, 0.10); ph = r.uniform(0, 6.28)
        pts = [top + Vector((sway * math.sin(ph + q / n * 2.4) * q / n + 0.05 * q / n, sway * 0.5 * math.sin(ph + q / n * 3.1) * q / n,
                             -Ls * q / n)) for q in range(n + 1)]
        tube_r(mb, pts, [0.0028 * (1 - 0.6 * q / n) for q in range(n + 1)], twig, segs=3)
        k = int(Ls / 0.030)
        for j in range(k):
            tt = (j + 0.5) / k
            ii = min(n - 1, int(tt * n)); ff = tt * n - ii
            c = pts[ii].lerp(pts[ii + 1], ff)
            for side in (0, 1):
                a = j * 2.4 + side * math.pi + r.uniform(-0.4, 0.4)
                out = Vector((math.cos(a), math.sin(a), 0))
                dx = (out * r.uniform(0.3, 0.6) + Vector((0, 0, -1))).normalized()
                nz = out.cross(Vector((0, 0, 1))).normalized() if r.random() < 0.5 else out
                L = r.uniform(0.075, 0.12) * (0.7 + 0.3 * min(1.0, tt * 3))
                leaf(mb, c, dx, (nz + Vector((0, 0, 0.3))).normalized(), L, L * 0.085, m, fold=0.15, tip=0.55)
    return _finish_src(mb, name, coll)

def lotus_clump(name, coll, seed, m='M_Lotus', stalk='M_LotusStalk'):
    """Lotus: 4-7 peltate, slightly cupped leaves on stalks (origin at the water surface)."""
    mb = C.MB()
    r = random.Random(seed)
    nl = r.randint(4, 7)
    for i in range(nl):
        a = r.uniform(0, 2 * math.pi); d = r.uniform(0.0, 0.45)
        h = r.choice([0.02, r.uniform(0.25, 0.55), r.uniform(0.5, 1.0)])
        R = r.uniform(0.18, 0.32)
        c = Vector((math.cos(a) * d, math.sin(a) * d, h))
        if h > 0.05:
            mb.cyl(Vector((c.x * 0.5, c.y * 0.5, -0.4)), c - Vector((0, 0, 0.01)), 0.008, 5, stalk, smooth=True, cap=False)
        tilt = Vector((r.gauss(0, 0.25), r.gauss(0, 0.25), 1.0)).normalized()
        q = Vector((0, 0, 1)).rotation_difference(tilt)
        segs = 14; rings = 3
        notch = r.uniform(0, 2 * math.pi)
        rows = []
        for k in range(1, rings + 1):
            rr = R * k / rings
            row = []
            for s in range(segs + 1):
                ang = notch + 0.18 + (2 * math.pi - 0.36) * s / segs
                z = 0.12 * R * (k / rings) ** 1.6 + 0.02 * math.sin(ang * 3)
                p = Vector((math.cos(ang) * rr, math.sin(ang) * rr, z))
                row.append(c + q @ p)
            rows.append(row)
        centre = c
        for s in range(segs):
            mb.face([centre, rows[0][s], rows[0][s + 1]], m)
        mb.quad_strip(list(reversed(rows)), m, smooth=True)
    return _finish_src(mb, name, coll)

def bank_clump(name, coll, seed, m='M_BankLeaf'):
    """Large-leaf bank / ground-cover clump (0.4-0.8 m)."""
    mb = C.MB()
    r = random.Random(seed)
    for i in range(r.randint(11, 17)):
        a = r.uniform(0, 2 * math.pi); el = r.uniform(0.35, 1.1)
        L = r.uniform(0.32, 0.6)
        stem_end = Vector((math.cos(a) * math.cos(el), math.sin(a) * math.cos(el), math.sin(el))) * L
        mb.cyl(Vector((0, 0, 0)), stem_end, 0.006, 4, 'M_LotusStalk', smooth=True, cap=False)
        dx = Vector((math.cos(a), math.sin(a), r.uniform(-0.3, 0.2))).normalized()
        nz = Vector((r.gauss(0, 0.3), r.gauss(0, 0.3), 1.0)).normalized()
        Ll = r.uniform(0.16, 0.26)
        leaf(mb, stem_end, dx, nz, Ll, Ll * 0.42, m, fold=0.25, tip=0.55)
    return _finish_src(mb, name, coll)

def grass_clump(name, coll, seed, m='M_Grass', h=(0.07, 0.15)):
    mb = C.MB()
    r = random.Random(seed)
    for i in range(r.randint(9, 13)):
        a = r.uniform(0, 2 * math.pi)
        base = Vector((r.gauss(0, 0.025), r.gauss(0, 0.025), -0.01))
        hh = r.uniform(*h)
        lean = Vector((math.cos(a), math.sin(a), 0)) * r.uniform(0.15, 0.55) * hh
        side = Vector((-math.sin(a), math.cos(a), 0)) * r.uniform(0.0022, 0.0035)
        mid = base + lean * 0.4 + Vector((0, 0, hh * 0.55))
        top = base + lean + Vector((0, 0, hh))
        mb.face([base - side, base + side, mid + side * 0.8, mid - side * 0.8], m)
        mb.face([mid - side * 0.8, mid + side * 0.8, top], m)
    return _finish_src(mb, name, coll)

def rock(name, coll, seed, m='M_Boulder'):
    """Weathered boulder: displaced icosphere, flattened base; origin at the base centre."""
    _clear_obj(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=0.5)
    r = random.Random(seed)
    sx, sy, sz = r.uniform(0.8, 1.3), r.uniform(0.7, 1.1), r.uniform(0.45, 0.75)
    import mathutils.noise as N
    off = Vector((r.uniform(0, 100), r.uniform(0, 100), r.uniform(0, 100)))
    for v in bm.verts:
        p = v.co.copy()
        d = 1.0 + 0.22 * N.noise(p * 2.2 + off) + 0.08 * N.noise(p * 6.0 + off)
        p *= d
        # facets: quantise slightly toward planes
        p = Vector((p.x * sx, p.y * sy, max(-0.08, p.z * sz)))
        v.co = p
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector((0, 0, 0.08)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(bpy.data.materials[m])
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    C.link(o, coll)
    return o

# ------------------------------------------------------------------ branch geometry
def tube(mb, path, r0, r1, segs, m):
    """Tapered tube along a polyline path (list of Vectors) from radius r0 to r1."""
    n = len(path)
    rows = []
    prev_side = None
    for i in range(n):
        t = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)])
        if t.length < 1e-6:
            t = Vector((0, 0, 1))
        t.normalize()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        side = t.cross(ref).normalized() if prev_side is None else (prev_side - t * prev_side.dot(t)).normalized()
        prev_side = side
        up = side.cross(t).normalized()
        rr = r0 + (r1 - r0) * (i / (n - 1))
        rows.append([path[i] + (side * math.cos(2 * math.pi * k / segs) + up * math.sin(2 * math.pi * k / segs)) * rr
                     for k in range(segs)])
    mb.quad_strip(rows, m, smooth=True, closed_u=True)

def bez(p0, p1, p2, n):
    return [p0 * ((1 - t) ** 2) + p1 * (2 * (1 - t) * t) + p2 * (t * t) for t in [i / n for i in range(n + 1)]]

class Template:
    """Collects branch faces + foliage points, then builds the template object."""
    def __init__(self, name):
        self.name = name
        self.mb = C.MB()
        self.pts = []          # (loc, rot_euler, scale, kind)

    def add_point(self, loc, rot, scl, kind):
        self.pts.append((tuple(loc), tuple(rot), scl, kind))

    def finish(self, coll, leaf_coll, proxy_coll, proxy_frac=0.06, proxy_scale=2.4):
        _clear_obj(self.name)
        o = self.mb.finish(self.name, coll)
        me = o.data
        nv0 = len(me.vertices)
        n = len(self.pts)
        me.vertices.add(n)
        co = []
        for p in self.pts:
            co.extend(p[0])
        me.vertices.foreach_set('co', [c for v in me.vertices[:nv0] for c in v.co] + co)
        isl = me.attributes.new('is_leaf', 'FLOAT', 'POINT')
        rot = me.attributes.new('rot', 'FLOAT_VECTOR', 'POINT')
        scl = me.attributes.new('scl', 'FLOAT_VECTOR', 'POINT')
        kind = me.attributes.new('kind', 'INT', 'POINT')
        rnd = me.attributes.new('rnd', 'FLOAT', 'POINT')
        rr = random.Random(zlib.crc32(self.name.encode('utf-8')))
        isl.data.foreach_set('value', [0.0] * nv0 + [1.0] * n)
        rv = [0.0] * (3 * nv0); sv = [1.0] * (3 * nv0); kv = [0] * nv0; dv = [1.0] * nv0
        for p in self.pts:
            rv.extend(p[1])
            s = p[2]
            sv.extend((s, s, s) if isinstance(s, (int, float)) else s)
            kv.append(p[3]); dv.append(rr.random())
        rot.data.foreach_set('vector', rv); scl.data.foreach_set('vector', sv)
        kind.data.foreach_set('value', kv); rnd.data.foreach_set('value', dv)
        me.update()
        ng = foliage_group()
        mod = o.modifiers.new('XY_Foliage', 'NODES')
        mod.node_group = ng
        C.set_mod_input(mod, 'Leaves', leaf_coll)
        C.set_mod_input(mod, 'Proxy', proxy_coll)
        C.set_mod_input(mod, 'Proxy Fraction', proxy_frac)
        C.set_mod_input(mod, 'Proxy Scale', proxy_scale)
        return o

FOLIAGE_VER = 2

def foliage_group():
    ng = bpy.data.node_groups.get('XY_Foliage')
    if ng and ng.get('ver') == FOLIAGE_VER:
        return ng
    if ng:
        ng.name = 'XY_Foliage_old'
    ng = bpy.data.node_groups.new('XY_Foliage', 'GeometryNodeTree')
    ng['ver'] = FOLIAGE_VER
    it = ng.interface
    it.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    it.new_socket(name='Leaves', in_out='INPUT', socket_type='NodeSocketCollection')
    it.new_socket(name='Proxy', in_out='INPUT', socket_type='NodeSocketCollection')
    s = it.new_socket(name='Proxy Fraction', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 0.06
    s = it.new_socket(name='Proxy Scale', in_out='INPUT', socket_type='NodeSocketFloat'); s.default_value = 2.4
    it.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes; L = ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    na = lambda nm, t: _named(N, nm, t)
    isl = na('is_leaf', 'FLOAT'); rot = na('rot', 'FLOAT_VECTOR'); scl = na('scl', 'FLOAT_VECTOR')
    kind = na('kind', 'INT'); rnd = na('rnd', 'FLOAT')
    cmp_leaf = N.new('FunctionNodeCompare'); cmp_leaf.data_type = 'FLOAT'; cmp_leaf.operation = 'GREATER_THAN'
    L.new(isl.outputs['Attribute'], cmp_leaf.inputs[0]); cmp_leaf.inputs[1].default_value = 0.5
    sep = N.new('GeometryNodeSeparateGeometry'); sep.domain = 'POINT'
    L.new(gi.outputs['Geometry'], sep.inputs['Geometry']); L.new(cmp_leaf.outputs[0], sep.inputs['Selection'])
    # viewport selection: rnd < fraction
    isv = N.new('GeometryNodeIsViewport')
    cmpv = N.new('FunctionNodeCompare'); cmpv.data_type = 'FLOAT'; cmpv.operation = 'LESS_THAN'
    L.new(rnd.outputs['Attribute'], cmpv.inputs[0]); L.new(gi.outputs['Proxy Fraction'], cmpv.inputs[1])
    notv = N.new('FunctionNodeBooleanMath'); notv.operation = 'NOT'; L.new(isv.outputs[0], notv.inputs[0])
    selv = N.new('FunctionNodeBooleanMath'); selv.operation = 'OR'
    L.new(notv.outputs[0], selv.inputs[0]); L.new(cmpv.outputs[0], selv.inputs[1])
    ci = N.new('GeometryNodeCollectionInfo'); ci.transform_space = 'ORIGINAL'
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    L.new(gi.outputs['Leaves'], ci.inputs['Collection'])
    cp = N.new('GeometryNodeCollectionInfo'); cp.transform_space = 'ORIGINAL'
    cp.inputs['Separate Children'].default_value = True; cp.inputs['Reset Children'].default_value = True
    L.new(gi.outputs['Proxy'], cp.inputs['Collection'])
    swi = N.new('GeometryNodeSwitch'); swi.input_type = 'GEOMETRY'
    L.new(isv.outputs[0], swi.inputs['Switch']); L.new(ci.outputs[0], swi.inputs['False']); L.new(cp.outputs[0], swi.inputs['True'])
    # scale: proxy scale in viewport
    sws = N.new('GeometryNodeSwitch'); sws.input_type = 'FLOAT'
    L.new(isv.outputs[0], sws.inputs['Switch']); sws.inputs['False'].default_value = 1.0
    L.new(gi.outputs['Proxy Scale'], sws.inputs['True'])
    vm = N.new('ShaderNodeVectorMath'); vm.operation = 'SCALE'
    L.new(scl.outputs['Attribute'], vm.inputs[0]); L.new(sws.outputs[0], vm.inputs['Scale'])
    e2r = N.new('FunctionNodeEulerToRotation'); L.new(rot.outputs['Attribute'], e2r.inputs['Euler'])
    iop = N.new('GeometryNodeInstanceOnPoints')
    L.new(sep.outputs['Selection'], iop.inputs['Points'])
    L.new(selv.outputs[0], iop.inputs['Selection'])
    L.new(swi.outputs[0], iop.inputs['Instance'])
    iop.inputs['Pick Instance'].default_value = True
    L.new(kind.outputs['Attribute'], iop.inputs['Instance Index'])
    L.new(e2r.outputs['Rotation'], iop.inputs['Rotation'])
    L.new(vm.outputs['Vector'], iop.inputs['Scale'])
    # viewport: drop the thin twigs of the branch mesh (renders keep them)
    msel = N.new('GeometryNodeMaterialSelection')
    tw = bpy.data.materials.get('M_Twig')
    if tw is not None:
        msel.inputs['Material'].default_value = tw
    andv = N.new('FunctionNodeBooleanMath'); andv.operation = 'AND'
    L.new(isv.outputs[0], andv.inputs[0]); L.new(msel.outputs[0], andv.inputs[1])
    dele = N.new('GeometryNodeDeleteGeometry'); dele.domain = 'FACE'
    L.new(sep.outputs['Inverted'], dele.inputs['Geometry']); L.new(andv.outputs[0], dele.inputs['Selection'])
    join = N.new('GeometryNodeJoinGeometry')
    L.new(dele.outputs[0], join.inputs[0]); L.new(iop.outputs['Instances'], join.inputs[0])
    L.new(join.outputs[0], go.inputs['Geometry'])
    return ng

def _named(N, name, dtype):
    n = N.new('GeometryNodeInputNamedAttribute'); n.data_type = dtype
    n.inputs['Name'].default_value = name
    return n

# ------------------------------------------------------------------ source sets
def make_sources():
    """Create all leaf / strand / clump sources and their viewport proxies (idempotent rebuild)."""
    sets = {}
    def coll_of(nm):
        c = src_coll(nm)
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        return c
    # leafy branchlets (render) and proxies (viewport); children sorted by name -> kind index
    defs = {
        #           material         twig        n  len           L      W      step   tip  rad(proxy)
        'broad':  ('M_LeafCamphor', 'M_Bark', 6, (0.28, 0.48), 0.095, 0.022, 0.032, 6, 0.45),
        'light':  ('M_LeafLight', 'M_Bark', 6, (0.26, 0.45), 0.080, 0.026, 0.030, 5, 0.42),
        'purple': ('M_LeafPurple', 'M_Bark', 6, (0.24, 0.40), 0.070, 0.025, 0.028, 5, 0.38),
        'red':    ('M_LeafRed', 'M_Bark', 6, (0.24, 0.40), 0.070, 0.025, 0.028, 5, 0.38),
        'shrub':  ('M_LeafBox', 'M_Bark', 8, (0.14, 0.22), 0.030, 0.009, 0.012, 4, 0.22),
        'shrubr': ('M_LeafRed', 'M_Bark', 8, (0.16, 0.26), 0.045, 0.014, 0.016, 4, 0.25),
        'far':    ('M_LeafCamphor', 'M_Bark', 6, (0.60, 0.90), 0.19, 0.05, 0.075, 5, 0.85),
    }
    for key, (m, tw, n, tl, L, W, step, tipn, rad) in defs.items():
        c = coll_of('XY_SRC_%s' % key)
        for k in range(3):
            branchlet('SRC_%s_%d' % (key, k), c, m, seed=31 * k + len(key), twig=tw, n_twigs=n, tw_len=tl, L=L, W=W, step=step,
                      tip_n=tipn, tw_r=0.004 if key != 'far' else 0.01)
        cp = coll_of('XY_PX_%s' % key)
        mb = C.MB()
        for a in range(3):
            ang = a * math.pi / 3
            d = Vector((math.cos(ang), math.sin(ang), 0)) * rad
            mb.face([-d + Vector((0, 0, -rad * 0.5)), d + Vector((0, 0, -rad * 0.5)), d + Vector((0, 0, rad * 0.6)),
                     -d + Vector((0, 0, rad * 0.6))], m)
        _finish_src(mb, 'PX_%s_0' % key, cp)
        sets[key] = (c, cp)
    # willow curtains (4 nominal lengths) + proxy ribbons
    c = coll_of('XY_SRC_willow'); cp = coll_of('XY_PX_willow')
    for k, Ls in enumerate((1.4, 2.2, 3.0, 3.9)):
        willow_curtain('SRC_willow_%d' % k, c, Ls, seed=7 + k)
        mb = C.MB()
        mb.face([Vector((0.1, 0, 0)), Vector((0.6, 0, 0)), Vector((0.6, 0, -Ls * 0.8)), Vector((0.1, 0, -Ls * 0.8))], 'M_LeafWillow')
        mb.face([Vector((0.35, -0.2, 0)), Vector((0.35, 0.2, 0)), Vector((0.35, 0.2, -Ls * 0.8)), Vector((0.35, -0.2, -Ls * 0.8))], 'M_LeafWillow')
        _finish_src(mb, 'PX_willow_%d' % k, cp)
    sets['willow'] = (c, cp)
    # ground layer sources, one collection per kind (kind index = child order by name)
    old = bpy.data.collections.get('XY_SRC_ground')
    if old is not None:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    c = coll_of('XY_SRC_lotus')
    for k in range(3):
        lotus_clump('SRC_lotus_%d' % k, c, seed=50 + k)
    sets['lotus'] = (c, c)
    c = coll_of('XY_SRC_bank')
    for k in range(3):
        bank_clump('SRC_bank_%d' % k, c, seed=60 + k)
    sets['bank'] = (c, c)
    c = coll_of('XY_SRC_grass')
    for k in range(4):
        grass_clump('SRC_grass_%d' % k, c, seed=70 + k)
    sets['grass'] = (c, c)
    c = coll_of('XY_SRC_rock')
    for k in range(6):
        rock('SRC_rock_%d' % k, c, seed=80 + k)
    sets['rock'] = (c, c)
    return sets

def get_sets():
    """The source collections made by make_sources() (without rebuilding them)."""
    sets = {}
    for key in ('broad', 'light', 'purple', 'red', 'shrub', 'shrubr', 'far', 'willow', 'lotus', 'bank', 'grass', 'rock'):
        c = bpy.data.collections.get('XY_SRC_%s' % key)
        cp = bpy.data.collections.get('XY_PX_%s' % key) or c
        sets[key] = (c, cp)
    return sets

def scatter(name, coll, pts, key, sets, frac=0.05, pscale=1.0):
    """Instances of a source set on points: pts = [(loc, rot_euler, scale, kind), ...] (XY_Foliage, viewport subset)."""
    T = Template(name)
    for (loc, rot, scl, kind) in pts:
        T.add_point(loc, rot, scl, kind)
    c, cp = sets[key]
    return T.finish(coll, c, cp, proxy_frac=frac, proxy_scale=pscale)

# ------------------------------------------------------------------ tree templates (space colonisation)
from mathutils import kdtree as _KD

def sca(attract, nodes, parents, D=0.3, di=2.4, dk=0.6, max_iter=160, trop=None):
    """Space colonisation (Runions et al. 2007). nodes/parents: the initial chain (trunk), grown in place toward
    the attraction points. trop: small vector added to every growth direction (e.g. gravity or light)."""
    A = list(attract)
    for it in range(max_iter):
        kd = _KD.KDTree(len(nodes))
        for i, p in enumerate(nodes):
            kd.insert(p, i)
        kd.balance()
        infl = {}
        keep = []
        for a in A:
            co, idx, dist = kd.find(a)
            if dist < dk:
                continue
            keep.append(a)
            if dist < di:
                d = (a - co) / dist
                if idx in infl:
                    infl[idx] += d
                else:
                    infl[idx] = d
        A = keep
        if not infl:
            break
        grew = 0
        for idx, d in infl.items():
            if d.length < 1e-6:
                continue
            d = d.normalized()
            if trop is not None:
                d = (d + trop).normalized()
            q = nodes[idx] + d * D
            co, j, dist = kd.find(q)
            if dist < D * 0.35:
                continue
            nodes.append(q); parents.append(idx); grew += 1
        if grew == 0 or not A:
            break
    return nodes, parents

def _children(parents):
    ch = [[] for _ in parents]
    for i, p in enumerate(parents):
        if p >= 0:
            ch[p].append(i)
    return ch

def pipe_radii(parents, ch, trunk_r, exp=2.2, r_min=0.005):
    n = len(parents)
    r = [1.0] * n
    tips = [0] * n
    for i in reversed(range(n)):
        if ch[i]:
            r[i] = sum(r[c] ** exp for c in ch[i]) ** (1.0 / exp)
            tips[i] = sum(tips[c] for c in ch[i])
        else:
            tips[i] = 1
    s = trunk_r / r[0]
    return [max(r_min, x * s) for x in r], tips

def smooth_nodes(nodes, parents, ch, it=2, fixed=0):
    for _ in range(it):
        new = [p.copy() for p in nodes]
        for i in range(fixed, len(nodes)):
            if parents[i] >= 0 and len(ch[i]) == 1:
                new[i] = nodes[i] * 0.5 + (nodes[parents[i]] + nodes[ch[i][0]]) * 0.25
        nodes[:] = new

def _sides(r):
    return 12 if r > 0.14 else 9 if r > 0.06 else 6 if r > 0.025 else 4 if r > 0.009 else 3

def tube_r(mb, path, radii, m, segs=None):
    """Tube along a polyline with per-point radii (parallel-transport frames)."""
    n = len(path)
    if n < 2:
        return
    segs = segs or _sides(max(radii))
    rows = []
    side = None
    for i in range(n):
        t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        if t.length < 1e-7:
            t = Vector((0, 0, 1))
        t.normalize()
        if side is None:
            ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            side = t.cross(ref).normalized()
        else:
            side = (side - t * side.dot(t))
            if side.length < 1e-6:
                side = t.orthogonal()
            side.normalize()
        up = side.cross(t).normalized()
        rr = radii[i]
        rows.append([path[i] + (side * math.cos(2 * math.pi * k / segs) + up * math.sin(2 * math.pi * k / segs)) * rr
                     for k in range(segs)])
    mb.quad_strip(rows, m, smooth=True, closed_u=True)

def build_branches(mb, nodes, parents, ch, r, tips, m, skip_r=0.0, twig_r=0.03, twig_m='M_Twig'):
    """Tubes along chains: each chain follows the child with the most tips; side children start new chains.
    Thin chains (max radius < twig_r) get twig_m, which the viewport drops; chains thinner than skip_r are not built."""
    stack = [0]
    while stack:
        s0 = stack.pop()
        chain = [s0] if parents[s0] < 0 else [parents[s0], s0]
        cur = s0
        while ch[cur]:
            kids = sorted(ch[cur], key=lambda c: -tips[c])
            stack.extend(kids[1:])
            cur = kids[0]
            chain.append(cur)
        if len(chain) < 2:
            continue
        rad = [r[i] for i in chain]
        if parents[s0] >= 0:
            rad[0] = rad[1] * 1.05          # a side branch starts with its own radius, inside the parent
        if max(rad) < skip_r:
            continue
        # taper the last segment to a point-ish tip
        rad[-1] = rad[-1] * 0.5
        tube_r(mb, [nodes[i] for i in chain], rad, twig_m if max(rad) < twig_r else m)

def crown_points(rng, n, center, rx, ry, rz, zmin=None, lump=0.12, shell=0.0, seed=0, top_flat=0.0):
    """Attraction points inside a lumpy ellipsoid. shell>0 pushes points toward the surface."""
    import mathutils.noise as MN
    off = Vector((seed * 3.17, seed * 1.31, seed * 2.07))
    pts = []
    tries = 0
    while len(pts) < n and tries < n * 20:
        tries += 1
        u = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)))
        L = u.length
        if L > 1 or L < 1e-6:
            continue
        if shell > 0 and rng.random() < shell:
            u = u / L * rng.uniform(0.75, 1.0)
        d = u.normalized()
        lim = 1.0 + lump * MN.noise(d * 1.6 + off)
        if u.length > lim:
            continue
        p = center + Vector((u.x * rx, u.y * ry, u.z * rz))
        if zmin is not None and p.z < zmin:
            continue
        if top_flat > 0 and u.z > 1 - top_flat and rng.random() < 0.6:
            continue
        pts.append(p)
    return pts

def trunk_chain(rng, base_z, top, D, lean_bend=0.15):
    """Initial node chain from the ground to `top`, slightly bent."""
    b = Vector((0, 0, base_z))
    mid = b.lerp(top, 0.5) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)) * lean_bend
    L = (top - b).length
    k = max(3, int(L / D))
    pts = bez(b, mid, top, k)
    return pts, [-1] + list(range(len(pts) - 1))

def _spray_rot(rng, tilt=0.5):
    return (rng.uniform(-tilt, tilt), rng.uniform(-tilt, tilt), rng.uniform(0, 6.283))

def broadleaf_template(name, coll, sets, key, seed, H=13.0, R=5.0, base=3.2, trunk_r=0.26, n_attr=2400, D=0.32, di=2.4,
                       dk=0.62, per_tip=5, spread=0.30, lean=0.3, bark='M_Bark', lump=0.14, shell=0.25, flat=0.9,
                       stems=1, kinds=3, spray_scale=(0.85, 1.25), proxy_frac=0.06, proxy_scale=2.4, skip_r=0.0,
                       twig_r=0.05):
    """Broadleaf tree grown by space colonisation inside a lumpy ellipsoid crown. Origin at the trunk base."""
    rng = random.Random(seed)
    T = Template(name)
    top = Vector((rng.uniform(-lean, lean), rng.uniform(-lean, lean), base))
    nodes, parents = trunk_chain(rng, -0.25, top, D)
    if stems > 1:
        # multi-stemmed: extra stems from near the ground
        for s in range(stems - 1):
            a = rng.uniform(0, 2 * math.pi)
            t2 = Vector((math.cos(a) * R * 0.25, math.sin(a) * R * 0.25, base * rng.uniform(0.8, 1.1)))
            p2, _ = trunk_chain(rng, 0.0, t2, D)
            i0 = len(nodes)
            root = min(2, len(nodes) - 1)
            for k, q in enumerate(p2[1:]):
                nodes.append(q); parents.append(root if k == 0 else i0 + k - 1)
    cz = base + (H - base) * 0.52
    rz = (H - base) * 0.5
    center = Vector((top.x * 0.6, top.y * 0.6, cz))
    attr = crown_points(rng, n_attr, center, R, R * rng.uniform(0.85, 1.0), rz, zmin=base + 0.3, lump=lump, shell=shell,
                        seed=seed)
    sca(attr, nodes, parents, D=D, di=di, dk=dk, trop=Vector((0, 0, 0.12)))
    ch = _children(parents)
    smooth_nodes(nodes, parents, ch, it=2)
    r, tips = pipe_radii(parents, ch, trunk_r)
    build_branches(T.mb, nodes, parents, ch, r, tips, bark, skip_r=skip_r, twig_r=twig_r)
    # root flare
    for k in range(5):
        a = k * 2 * math.pi / 5 + rng.uniform(-0.3, 0.3)
        tube(T.mb, [Vector((0, 0, 0.55)), Vector((math.cos(a) * trunk_r * 1.2, math.sin(a) * trunk_r * 1.2, 0.12)),
                    Vector((math.cos(a) * trunk_r * 2.0, math.sin(a) * trunk_r * 2.0, -0.08))], trunk_r * 0.55, trunk_r * 0.18, 6, bark)
    # foliage: sprays around tips and the last nodes of every twig
    depth_from_tip = [0] * len(nodes)
    for i in reversed(range(len(nodes))):
        depth_from_tip[i] = 0 if not ch[i] else 1 + min(depth_from_tip[c] for c in ch[i])
    for i, p in enumerate(nodes):
        dt = depth_from_tip[i]
        if dt > 2 or p.z < base * 0.9:
            continue
        nn = per_tip if dt == 0 else max(1, per_tip // (dt + 1))
        for k in range(nn):
            off = Vector((rng.gauss(0, spread), rng.gauss(0, spread), rng.gauss(0, spread * flat)))
            T.add_point(p + off, _spray_rot(rng), rng.uniform(*spray_scale), rng.randrange(kinds))
    c, cp = sets[key]
    return T.finish(coll, c, cp, proxy_frac=proxy_frac, proxy_scale=proxy_scale)

def willow_template(name, coll, sets, seed, H=12.5, R=6.0, fork=2.6, trunk_r=0.32, n_attr=2200, D=0.34, di=2.6, dk=0.7,
                    strands_per_tip=2, clear=(0.9, 2.4), proxy_frac=0.05, skip_r=0.0, twig_r=0.05):
    """Weeping willow: short leaning trunk, ascending limbs grown into a dome, hanging leaf strands from the
    twig ends all over the crown (lengths limited by the height above ground)."""
    rng = random.Random(seed)
    T = Template(name)
    bark = 'M_BarkWillow'
    lean = Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), 0))
    top = Vector((lean.x, lean.y, fork))
    nodes, parents = trunk_chain(rng, -0.25, top, D, lean_bend=0.25)
    cz = fork + (H - fork) * 0.42
    rz = (H - fork) * 0.62
    center = Vector((lean.x * 0.8, lean.y * 0.8, cz))
    attr = crown_points(rng, n_attr, center, R, R * rng.uniform(0.85, 1.0), rz, zmin=fork + 0.6, lump=0.16, shell=0.45,
                        seed=seed)
    sca(attr, nodes, parents, D=D, di=di, dk=dk, trop=Vector((0, 0, 0.18)))
    ch = _children(parents)
    smooth_nodes(nodes, parents, ch, it=2)
    r, tips = pipe_radii(parents, ch, trunk_r)
    build_branches(T.mb, nodes, parents, ch, r, tips, bark, skip_r=skip_r, twig_r=twig_r)
    for k in range(6):
        a = k * 2 * math.pi / 6 + rng.uniform(-0.3, 0.3)
        tube(T.mb, [Vector((0, 0, 0.7)), Vector((math.cos(a) * trunk_r * 1.3, math.sin(a) * trunk_r * 1.3, 0.15)),
                    Vector((math.cos(a) * trunk_r * 2.3, math.sin(a) * trunk_r * 2.3, -0.08))], trunk_r * 0.6, trunk_r * 0.2, 6, bark)
    lengths = (1.4, 2.2, 3.0, 3.9)
    depth_from_tip = [0] * len(nodes)
    for i in reversed(range(len(nodes))):
        depth_from_tip[i] = 0 if not ch[i] else 1 + min(depth_from_tip[c] for c in ch[i])
    for i, p in enumerate(nodes):
        dt = depth_from_tip[i]
        if dt > 2 or p.z < fork + 0.5:
            continue
        nn = strands_per_tip if dt == 0 else 1
        out = Vector((p.x - center.x, p.y - center.y, 0))
        out = out.normalized() if out.length > 1e-6 else Vector((1, 0, 0))
        for k in range(nn):
            pos = p + Vector((rng.gauss(0, 0.22), rng.gauss(0, 0.22), rng.gauss(0, 0.1)))
            maxL = pos.z - rng.uniform(*clear)
            choices = [j for j, L in enumerate(lengths) if L <= maxL]
            if not choices:
                continue
            kind = choices[-1] if rng.random() < 0.6 else rng.choice(choices)
            az = math.atan2(out.y, out.x) + rng.gauss(0, 0.7)
            T.add_point(pos, (rng.uniform(-0.06, 0.06), rng.uniform(-0.06, 0.06), az), rng.uniform(0.9, 1.1), kind)
    c, cp = sets['willow']
    return T.finish(coll, c, cp, proxy_frac=proxy_frac, proxy_scale=1.0)

def shrub_template(name, coll, sets, key, seed, R=0.8, Hs=0.9, per=1.0):
    rng = random.Random(seed)
    _clear_obj(name)
    T = Template(name)
    for k in range(5):
        a = rng.uniform(0, 2 * math.pi)
        tube(T.mb, [Vector((0, 0, -0.05)), Vector((math.cos(a) * R * 0.4, math.sin(a) * R * 0.4, Hs * 0.6))], 0.02, 0.008, 4, 'M_Twig')
    n = int((R * R * 110 + 30) * per)
    for k in range(n):
        u = Vector((rng.gauss(0, 1), rng.gauss(0, 1), abs(rng.gauss(0.4, 0.8)))).normalized()
        rr = rng.uniform(0.6, 1.0) ** 0.6
        pos = Vector((u.x * R * rr, u.y * R * rr, Hs * 0.15 + u.z * Hs * 0.85 * rr))
        T.add_point(pos, (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, 6.283)), rng.uniform(0.8, 1.2),
                    rng.randint(0, 2))
    c, cp = sets[key]
    return T.finish(coll, c, cp, proxy_frac=0.12, proxy_scale=2.0)

def make_templates(sets, only=None):
    """Build the tree / shrub templates (hidden library objects in XY_TREES). only: list of keys to rebuild."""
    c = src_coll('XY_TREES')
    specs = {
        'willow': [('TREE_willow_%d' % k, willow_template,
                    dict(seed=200 + k, H=10.5 + k * 0.7, R=4.4 + (k % 3) * 0.5, fork=2.4 + (k % 2) * 0.6)) for k in range(5)],
        'broad': [('TREE_broad_%d' % k, broadleaf_template,
                   dict(key='broad', seed=300 + k, H=12.0 + k * 1.1, R=4.6 + (k % 3) * 0.7, base=3.0 + (k % 2) * 0.8,
                        trunk_r=0.24 + 0.02 * k)) for k in range(5)],
        'purple': [('TREE_purple_%d' % k, broadleaf_template,
                    dict(key='purple' if k < 3 else 'red', seed=400 + k, H=6.5 + k * 0.5, R=3.0 + (k % 2) * 0.5,
                         base=1.5 + (k % 2) * 0.4, trunk_r=0.13, n_attr=1300, D=0.26, di=2.0, dk=0.5, stems=2 + k % 2,
                         per_tip=4, spread=0.26)) for k in range(4)],
        'light': [('TREE_light_%d' % k, broadleaf_template,
                   dict(key='light', seed=500 + k, H=10.5 + k * 1.2, R=3.6 + (k % 2) * 0.6, base=3.4, trunk_r=0.2,
                        n_attr=1500, dk=0.75, per_tip=4, spread=0.3, lump=0.22, shell=0.15)) for k in range(4)],
        'small': [('TREE_small_%d' % k, broadleaf_template,
                   dict(key='light', seed=600 + k, H=4.6, R=1.4, base=1.7, trunk_r=0.07, n_attr=420, D=0.2, di=1.2,
                        dk=0.35, per_tip=3, spread=0.2, spray_scale=(0.6, 0.9))) for k in range(2)],
        'far_broad': [('TREE_farbroad_%d' % k, broadleaf_template,
                       dict(key='far', seed=700 + k, H=11 + k * 2.5, R=5.0 + k * 0.7, base=1.6 + 0.3 * k, trunk_r=0.3, n_attr=800,
                            D=0.5, di=3.0, dk=1.1, per_tip=3, spread=0.5, twig_r=0.12)) for k in range(3)],
        'far_light': [('TREE_farlight_%d' % k, broadleaf_template,
                       dict(key='light', seed=750 + k, H=10 + k * 2.0, R=4.0, base=1.8, trunk_r=0.22, n_attr=700, D=0.45,
                            di=2.6, dk=0.95, per_tip=3, spread=0.4, spray_scale=(1.2, 1.6), twig_r=0.12)) for k in range(2)],
        'far_willow': [('TREE_farwillow_%d' % k, willow_template,
                        dict(seed=800 + k, H=12.5, R=6.0, n_attr=900, D=0.45, dk=0.95, strands_per_tip=2, twig_r=0.12)) for k in range(2)],
    }
    T = {}
    for key, lst in specs.items():
        if only is not None and key not in only:
            T[key] = [bpy.data.objects.get(nm) for nm, _, _ in lst]
            continue
        T[key] = []
        for nm, fn, kw in lst:
            _clear_obj(nm)
            if fn is willow_template:
                T[key].append(fn(nm, c, sets, **kw))
            else:
                k2 = dict(kw); key2 = k2.pop('key')
                T[key].append(fn(nm, c, sets, key2, **k2))
    sh = {
        'under': [('SHRUB_under_%d' % k, 'shrub' if k < 2 else 'light', dict(seed=920 + k, R=1.0 + 0.3 * k, Hs=1.3 + 0.35 * k, per=0.55))
                  for k in range(4)],
        'shrub': [('SHRUB_box_%d' % k, 'shrub', dict(seed=900 + k, R=0.55 + k * 0.2, Hs=0.65 + k * 0.15)) for k in range(3)],
        'shrubr': [('SHRUB_red_%d' % k, 'shrubr', dict(seed=950 + k, R=0.6 + k * 0.2, Hs=0.8 + k * 0.2)) for k in range(2)],
        'hedge': [('SHRUB_hedge_%d' % k, 'shrub', dict(seed=980 + k, R=0.55, Hs=0.75, per=1.3)) for k in range(2)],
    }
    for key, lst in sh.items():
        if only is not None and key not in only:
            T[key] = [bpy.data.objects.get(nm) for nm, _, _ in lst]
            continue
        T[key] = [shrub_template(nm, c, sets, sk, **kw) for nm, sk, kw in lst]
    return T
