"""Forest instancing: simple conifer shapes (they are 2-60 px tall in this view) on the points from proc/trees.py."""
import bpy, os, math
import numpy as np
import mc_core as C
import mc_mats
from mc_core import NT


def conifer(name, seed, tiers=7, seg=9, spread=0.19, larch=False):
    """Unit-height tree: thin trunk and drooping tiers of boughs, irregular."""
    rng = np.random.default_rng(seed)
    V, F = [], []

    def cone(z0, z1, r0, droop):
        b = len(V)
        ang = np.linspace(0, 2 * math.pi, seg, endpoint=False) + rng.uniform(0, 1)
        rr = r0 * rng.uniform(0.62, 1.18, seg)
        for a, r in zip(ang, rr):
            V.append((r * math.cos(a), r * math.sin(a), z0 - droop * r / max(r0, 1e-6)))
        V.append((rng.normal(0, 0.006), rng.normal(0, 0.006), z1))
        for i in range(seg):
            F.append((b + i, b + (i + 1) % seg, b + seg))
        # underside so the tiers read as solid boughs from below
        V.append((0, 0, z0 + 0.015))
        for i in range(seg):
            F.append((b + (i + 1) % seg, b + i, b + seg + 1))
    base = 0.10 if not larch else 0.18
    for k in range(tiers):
        t = k / tiers
        z0 = base + (1 - base) * t
        z1 = min(1.0, z0 + (1 - base) / tiers * (2.1 if not larch else 1.7))
        r = spread * (1 - t) ** (0.85 if not larch else 0.7) * rng.uniform(0.85, 1.15) + 0.012
        cone(z0, z1, r, 0.035 if not larch else 0.01)
    # trunk
    b = len(V)
    for a in np.linspace(0, 2 * math.pi, 5, endpoint=False):
        V.append((0.014 * math.cos(a), 0.014 * math.sin(a), -0.03))
        V.append((0.008 * math.cos(a), 0.008 * math.sin(a), base + 0.05))
    for i in range(5):
        j = (i + 1) % 5
        F.append((b + 2 * i, b + 2 * j, b + 2 * j + 1))
        F.append((b + 2 * i, b + 2 * j + 1, b + 2 * i + 1))
    me = C.tri_mesh(name, np.array(V, np.float32), np.array(F, np.int32))
    return me


def tree_material(name, base, tip):
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    info = n.node('ShaderNodeObjectInfo')
    geo = n.node('ShaderNodeNewGeometry')
    # lighter towards the outside of each bough, darker inside; per-tree tone
    oz = n.node('ShaderNodeTexCoord').outputs['Object']
    r = n.node('ShaderNodeVectorMath', operation='LENGTH', inputs={0: n.node('ShaderNodeVectorMath', operation='MULTIPLY',
               inputs={0: oz, 1: (1.0, 1.0, 0.0)}).outputs[0]}).outputs['Value']
    col = n.mix(n.smooth(r, 0.02, 0.16), base + (1,), tip + (1,))
    hsv = n.node('ShaderNodeHueSaturation', inputs={
        'Hue': n.math('ADD', 0.485, n.math('MULTIPLY', info.outputs['Random'], 0.03)),
        'Saturation': n.math('ADD', 0.8, n.math('MULTIPLY', info.outputs['Random'], 0.4)),
        'Value': n.math('ADD', 0.7, n.math('MULTIPLY', n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D',
                        inputs={'W': info.outputs['Random']}).outputs['Value'], 0.6)), 'Color': col})
    nz = n.noise(geo.outputs['Position'], 0.9, 3, 0.6).outputs['Fac']
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 1.0, 'Height': n.math('MULTIPLY', nz, 0.6)})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': hsv.outputs[0], 'Roughness': 0.75,
                                                      'Specular IOR Level': 0.2, 'Normal': bump.outputs[0]})
    bsdf.inputs['Sheen Weight'].default_value = 0.3
    n.link(mc_mats.add_aerial(n, bsdf.outputs[0], 1.25), out.inputs['Surface'])
    mc_mats.no_light(m)
    return m


def _wrap_material(src, name, hue=0.5, sat=1.0, val=1.0):
    """Copy of a Poly Haven plant material with the air veil before its output and its colour inputs set."""
    m = bpy.data.materials.get(name)
    if m is not None:
        bpy.data.materials.remove(m)
    m = src.copy()
    m.name = name
    t = m.node_tree
    out = next(n for n in t.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    grp = next((n for n in t.nodes if n.type == 'GROUP' and 'Hue' in n.inputs), None)
    if grp is not None:
        grp.inputs['Hue'].default_value = hue
        grp.inputs['Saturation'].default_value = sat
        grp.inputs['Value'].default_value = val
    srcs = out.inputs['Surface'].links[0].from_socket
    air = t.nodes.new('ShaderNodeGroup')
    air.node_tree = mc_mats.aerial_group()
    air.inputs['Density'].default_value = 1.25
    t.links.new(srcs, air.inputs['Shader'])
    t.links.new(air.outputs['Shader'], out.inputs['Surface'])
    mc_mats.no_light(m)
    return m


def _unit_tree(src, name, mats):
    """Mesh copy scaled to unit height, base at z = 0, with the given material replacements."""
    old = bpy.data.objects.get(name)
    if old is not None:
        d = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    me = src.data.copy()
    me.name = name
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    co[:, 2] -= np.percentile(co[:, 2], 0.5)
    co /= co[:, 2].max()
    me.vertices.foreach_set('co', co.ravel())
    for i, m in enumerate(me.materials):
        if m is not None and m.name in mats:
            me.materials[i] = mats[m.name]
    me.update()
    return bpy.data.objects.new(name, me)


def build(name='MC_forest'):
    """Scanned firs (Poly Haven fir_tree_01 and fir_sapling_medium, LOD2) on the points from proc/trees.py; the
    'larches' are the same shapes in autumn gold."""
    import mc_assets
    d = np.load(os.path.join(C.DEM, 'trees.npz'))
    big = mc_assets.load('fir_tree_01')
    small = mc_assets.load('fir_sapling_medium')
    srcs = [big.objects['fir_tree_01_a_LOD2'], big.objects['fir_tree_01_b_LOD2'], big.objects['fir_tree_01_c_LOD2'],
            small.objects['fir_sapling_medium_a_LOD2'], big.objects['fir_tree_01_c_LOD2'],
            small.objects['fir_sapling_medium_b_LOD2']]
    lib = bpy.data.collections.get('LIB_trees') or bpy.data.collections.new('LIB_trees')
    for o in list(lib.objects):
        dd = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if dd.users == 0:
            bpy.data.meshes.remove(dd)
    green, gold = {}, {}
    for src in srcs:
        for m in src.data.materials:
            if m is None or m.name in green:
                continue
            leafy = 'twig' in m.name
            green[m.name] = _wrap_material(m, 'MC_' + m.name, 0.5, 0.9, 0.85 if leafy else 1.0)
            gold[m.name] = _wrap_material(m, 'MC_gold_' + m.name, 0.385 if leafy else 0.5, 1.5 if leafy else 1.0,
                                          2.1 if leafy else 1.0)
    for i, src in enumerate(srcs):
        lib.objects.link(_unit_tree(src, 'TREE_%d' % i, gold if i >= 4 else green))
    # points
    C.remove_object(name)
    me = bpy.data.meshes.new(name)
    co = d['co']
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    me.attributes.new('h', 'FLOAT', 'POINT').data.foreach_set('value', d['h'])
    me.attributes.new('yaw', 'FLOAT', 'POINT').data.foreach_set('value', d['yaw'])
    me.attributes.new('sp', 'INT', 'POINT').data.foreach_set('value', d['sp'])
    o = bpy.data.objects.new(name, me)
    C.coll('MC_forest').objects.link(o)
    ng = bpy.data.node_groups.get('GN_forest')
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new('GN_forest', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    mp = N.new('GeometryNodeMeshToPoints')
    L.new(gi.outputs[0], mp.inputs['Mesh'])
    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = lib
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True

    def attr(nm, typ):
        a = N.new('GeometryNodeInputNamedAttribute')
        a.data_type = typ
        a.inputs['Name'].default_value = nm
        return a.outputs[0]
    ip = N.new('GeometryNodeInstanceOnPoints')
    L.new(mp.outputs['Points'], ip.inputs['Points'])
    L.new(ci.outputs['Instances'], ip.inputs['Instance'])
    ip.inputs['Pick Instance'].default_value = True
    L.new(attr('sp', 'INT'), ip.inputs['Instance Index'])
    cz = N.new('ShaderNodeCombineXYZ')
    L.new(attr('yaw', 'FLOAT'), cz.inputs['Z'])
    er = N.new('FunctionNodeEulerToRotation')
    L.new(cz.outputs[0], er.inputs['Euler'])
    L.new(er.outputs['Rotation'], ip.inputs['Rotation'])
    L.new(attr('h', 'FLOAT'), ip.inputs['Scale'])
    L.new(ip.outputs['Instances'], go.inputs[0])
    md = o.modifiers.new('forest', 'NODES')
    md.node_group = ng
    o.hide_viewport = True
    return o, len(co)
