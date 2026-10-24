# Viewport proxies: lightweight stand-ins for heavily instanced parts. Renders always use the full sources
# (the XY_Instancer node group switches on "Is Viewport").
import bpy, math, random
from mathutils import Vector
import xy_core as C, xy_roof as RF

def _mk(name, build):
    o = bpy.data.objects.get(name)
    if o is None:
        mb = C.MB()
        build(mb)
        o = mb.finish(name, C.lib_coll(), recalc=False)
    return o

def proxies():
    L = RF.TILE_L + 0.02
    R = RF.COVER_R
    def cover(mb):
        segs = 3
        ring = lambda x: [(x, -R * math.cos(math.pi * k / segs), R * math.sin(math.pi * k / segs)) for k in range(segs + 1)]
        mb.quad_strip([ring(0.0), ring(L)], 'M_Tile')
    def pan(mb):
        w = RF.PAN_W / 2
        mb.face([(0, -w, 0.0), (L, -w, 0.02), (L, w, 0.02), (0, w, 0.0)], 'M_Tile')
    def leaves(mat, n, rad, size, seed):
        def b(mb):
            rng = random.Random(seed)
            for i in range(n):
                c = Vector((rng.gauss(0, rad), rng.gauss(0, rad), rng.gauss(0, rad * 0.7)))
                a = rng.uniform(0, 2 * math.pi)
                d = Vector((math.cos(a), math.sin(a), rng.uniform(-0.6, 0.2))).normalized()
                s = d.cross(Vector((0, 0, 1)))
                s = (s.normalized() if s.length > 1e-4 else Vector((1, 0, 0))) * size * 0.35
                mb.face([c, c + d * size * 0.5 + s, c + d * size, c + d * size * 0.5 - s], mat)
        return b
    return {
        'SRC_cover': _mk('SRC_cover_px', cover),
        'SRC_cover_eave': _mk('SRC_cover_px', cover),
        'SRC_pan': _mk('SRC_pan_px', pan),
        'SRC_pan_eave': _mk('SRC_pan_px', pan),
        'SRC_bamboo_spray': _mk('SRC_bamboo_px', leaves('M_LeafBamboo', 8, 0.18, 0.30, 3)),
        'SRC_leafspray_plum': _mk('SRC_leaf_px', leaves('M_LeafPurple', 14, 0.28, 0.16, 5)),
    }

def apply():
    px = proxies()
    n = 0
    for o in bpy.data.objects:
        for m in o.modifiers:
            if m.type == 'NODES' and m.node_group and m.node_group.name == 'XY_Instancer':
                sid = C._sock_id(m.node_group, 'Instance')
                src = getattr(m.properties.inputs, sid).value if hasattr(m, 'properties') else m[sid]
                if src is not None and src.name in px:
                    C.set_mod_input(m, 'Proxy', px[src.name])
                    C.set_mod_input(m, 'Use Proxy In Viewport', True)
                    n += 1
    return n
