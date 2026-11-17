"""Alpine meadow round the cafe: scatter of scanned grass clumps, dwarf shrubs, stones, boulders and flowers on the
graded ground (geometry nodes instancing), densest in front of the camera and thinning out with distance."""
import bpy, os, math, re, zlib
import numpy as np
import mc_core as C
import mc_site, mc_assets
from mc_stone import Ground

CAM = (9.6, 32.79, 11.76)
VIEW_AZ = -127.0


def vnoise(x, y, scale, seed, octaves=4):
    """Value-noise fbm in 0..1 (numpy)."""
    out = np.zeros(np.shape(x))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        rng = np.random.default_rng(seed + 31 * o)
        tab = rng.uniform(0, 1, (256, 256))
        u = np.asarray(x) / scale
        v = np.asarray(y) / scale
        i = np.floor(u).astype(int)
        j = np.floor(v).astype(int)
        fu = u - i
        fv = v - j
        fu = fu * fu * (3 - 2 * fu)
        fv = fv * fv * (3 - 2 * fv)
        a = tab[i % 256, j % 256]
        b = tab[(i + 1) % 256, j % 256]
        c = tab[i % 256, (j + 1) % 256]
        d = tab[(i + 1) % 256, (j + 1) % 256]
        out += amp * (a * (1 - fu) * (1 - fv) + b * fu * (1 - fv) + c * (1 - fu) * fv + d * fu * fv)
        tot += amp
        amp *= 0.5
        scale *= 0.5
    return out / tot


def mc_light_az(cam):
    d = cam.matrix_world.to_3x3() @ __import__('mathutils').Vector((0, 0, -1))
    return math.degrees(math.atan2(d.y, d.x))


def smooth(x, lo, hi):
    t = np.clip((np.asarray(x, float) - lo) / (hi - lo), 0, 1)
    return t * t * (3 - 2 * t)


def scatter_base(name='SCAT_base', R=185.0, half_angle=52.0, cell=0.4):
    """Hidden carrier mesh for the scatter: the graded ground in front of the camera with density weights."""
    g = Ground()
    co_ = bpy.data.objects.get('CAM_final')
    CAM = tuple(co_.location) if co_ else globals()['CAM']
    VIEW_AZ = mc_light_az(co_) if co_ else globals()['VIEW_AZ']
    xs = np.arange(CAM[0] - R, CAM[0] + 30.0, cell)
    ys = np.arange(CAM[1] - R, CAM[1] + 30.0, cell)
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X - CAM[0], Y - CAM[1])
    az = np.degrees(np.arctan2(Y - CAM[1], X - CAM[0]))
    da = (az - VIEW_AZ + 180) % 360 - 180
    keepv = ((np.abs(da) < half_angle) & (r < R)) | (r < 14.0)
    keepv &= (np.abs(X) < 128) & (np.abs(Y) < 128)
    Z = g.z(X, Y)
    sdf = g.sdf(X, Y)
    trk = g.track(X, Y)
    zx = (g.z(X + 0.4, Y) - g.z(X - 0.4, Y)) / 0.8
    zy = (g.z(X, Y + 0.4) - g.z(X, Y - 0.4)) / 0.8
    slope = np.hypot(zx, zy)
    fade = smooth(r, 180.0, 85.0)
    open_ = (sdf > 0.42) * (1 - np.clip(trk * 1.6, 0, 1))                 # not on the terrace, the wall or the track
    patch = vnoise(X, Y, 9.0, 3)                                           # where the sward is thick or thin
    bare = smooth(vnoise(X, Y, 5.0, 17) + 0.25 * smooth(slope, 0.45, 0.8), 0.63, 0.74)      # bare earth and scree
    lush = smooth(vnoise(X, Y, 16.0, 29), 0.42, 0.62)                      # greener hollows
    shrubby = smooth(vnoise(X, Y, 13.0, 41) + 0.2 * smooth(slope, 0.2, 0.6), 0.60, 0.70)
    flowery = smooth(vnoise(X, Y, 7.0, 55), 0.55, 0.70)
    stony = smooth(vnoise(X, Y, 6.0, 71) + 0.5 * bare, 0.55, 0.80)
    verge = np.clip(trk * 2.0, 0, 1) * (trk < 0.55)                        # sparse tufts creeping onto the track edge
    wallfoot = smooth(sdf, 1.3, 0.45) * (sdf > 0.42)                       # rank grass at the foot of the walls
    A = {
        'd_dry': fade * (open_ * (0.35 + 0.65 * patch) * (1 - 0.85 * bare) * (1 - 0.45 * lush) + 0.25 * verge),
        'd_green': fade * open_ * (0.15 + 0.85 * lush) * (1 - 0.9 * bare) + fade * wallfoot * 0.6,
        'd_shrub': fade * open_ * shrubby * (1 - bare) * (sdf > 2.0),
        'd_flower': fade * open_ * flowery * (1 - bare) * smooth(r, 120.0, 60.0),
        'd_stone': fade * (open_ * (0.25 + 0.75 * stony) + 0.5 * verge),
        'd_rock': smooth(r, 170.0, 110.0) * open_ * (0.3 + 0.7 * stony) * (sdf > 1.5),
    }
    kq = keepv[:-1, :-1] & keepv[1:, :-1] & keepv[:-1, 1:] & keepv[1:, 1:]
    co = np.stack([X, Y, Z], -1).reshape(-1, 3)
    me = C.grid_mesh(name, co, X.shape[0], X.shape[1], keep=kq, attrs={k: v.ravel() for k, v in A.items()})
    o = C.obj(name, me, C.coll('MC_scatter'))
    o.hide_render = True
    o.hide_viewport = True
    return o, int(kq.sum()) * cell * cell


def pick(asset, pattern, minz=0.0):
    """Objects of a library collection whose name matches the regular expression."""
    col = mc_assets.load(asset)
    return [o for o in col.objects if re.search(pattern, o.name) and o.dimensions.z >= minz]


def instance_collection(name, objs):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    for o in list(col.objects):
        col.objects.unlink(o)
    for o in objs:
        col.objects.link(o)
    return col


def gn_scatter(name, base, collection, attr, density, scale=(0.6, 1.0), seed=0, upright=True, sink=0.0, tilt=0.12,
               align=False, scale_attr=None, yaw=None):
    """Object that instances `collection` over `base`: density (per m2) x the named weight attribute."""
    ng = bpy.data.node_groups.get('GN_' + name)
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new('GN_' + name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo')
    oi.inputs['Object'].default_value = base
    oi.transform_space = 'RELATIVE'
    at = N.new('GeometryNodeInputNamedAttribute')
    at.data_type = 'FLOAT'
    at.inputs['Name'].default_value = attr
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = density
    L.new(at.outputs[0], mul.inputs[0])
    dp = N.new('GeometryNodeDistributePointsOnFaces')
    dp.distribute_method = 'RANDOM'
    dp.inputs['Seed'].default_value = seed
    L.new(oi.outputs['Geometry'], dp.inputs['Mesh'])
    L.new(mul.outputs[0], dp.inputs['Density'])
    ci = N.new('GeometryNodeCollectionInfo')
    ci.inputs['Collection'].default_value = collection
    ci.inputs['Separate Children'].default_value = True
    ci.inputs['Reset Children'].default_value = True
    ci.transform_space = 'RELATIVE'
    ip = N.new('GeometryNodeInstanceOnPoints')
    L.new(dp.outputs['Points'], ip.inputs['Points'])
    L.new(ci.outputs['Instances'], ip.inputs['Instance'])
    ip.inputs['Pick Instance'].default_value = True
    rv = N.new('FunctionNodeRandomValue')
    rv.data_type = 'FLOAT_VECTOR'
    t = 0.0 if upright is True else math.pi
    rv.inputs['Min'].default_value = (-tilt if upright else -t, -tilt if upright else -t, 0.0)
    rv.inputs['Max'].default_value = (tilt if upright else t, tilt if upright else t, 2 * math.pi)
    if yaw is not None:                            # bedded rock: one direction, a few degrees of play
        y0, yj = math.radians(yaw[0]), math.radians(yaw[1])
        rv.inputs['Min'].default_value = (-tilt, -tilt, y0 - yj)
        rv.inputs['Max'].default_value = (tilt, tilt, y0 + yj)
    rv.inputs['Seed'].default_value = seed + 1
    er = N.new('FunctionNodeEulerToRotation')
    L.new(rv.outputs['Value'], er.inputs['Euler'])
    if align:
        # lie on the slope: the surface rotation, then a random spin about the normal
        rr = N.new('FunctionNodeRotateRotation')
        rr.rotation_space = 'LOCAL'
        L.new(dp.outputs['Rotation'], rr.inputs['Rotation'])
        L.new(er.outputs['Rotation'], rr.inputs['Rotate By'])
        L.new(rr.outputs['Rotation'], ip.inputs['Rotation'])
    else:
        L.new(er.outputs['Rotation'], ip.inputs['Rotation'])
    rs = N.new('FunctionNodeRandomValue')
    rs.data_type = 'FLOAT'
    rs.inputs['Min'].default_value = scale[0]      # (sockets follow data_type in Blender 5)
    rs.inputs['Max'].default_value = scale[1]
    rs.inputs['Seed'].default_value = seed + 2
    scl = rs.outputs['Value']
    if scale_attr:                                 # e.g. plants drawn larger and sparser with distance
        sa = N.new('GeometryNodeInputNamedAttribute')
        sa.data_type = 'FLOAT'
        sa.inputs['Name'].default_value = scale_attr
        sm = N.new('ShaderNodeMath')
        sm.operation = 'MULTIPLY'
        L.new(rs.outputs['Value'], sm.inputs[0])
        L.new(sa.outputs[0], sm.inputs[1])
        scl = sm.outputs[0]
    L.new(scl, ip.inputs['Scale'])
    last = ip.outputs['Instances']
    if sink:
        # bury part of each stone: move down by a fraction of its size (instance scale x sink)
        ti = N.new('GeometryNodeTranslateInstances')
        cz = N.new('ShaderNodeCombineXYZ')
        m2 = N.new('ShaderNodeMath')
        m2.operation = 'MULTIPLY'
        m2.inputs[1].default_value = -sink
        L.new(scl, m2.inputs[0])
        L.new(m2.outputs[0], cz.inputs['Z'])
        L.new(last, ti.inputs['Instances'])
        L.new(cz.outputs[0], ti.inputs['Translation'])
        ti.inputs['Local Space'].default_value = False
        last = ti.outputs['Instances']
    L.new(last, go.inputs['Geometry'])
    C.remove_object(name)
    me = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, me)
    C.coll('MC_scatter').objects.link(o)
    md = o.modifiers.new('scatter', 'NODES')
    md.node_group = ng
    o.hide_viewport = True
    return o


def make_patch(name, seed, dry, green, n_dry=60, n_green=12, radius=0.75):
    """One square metre of sward as a single mesh: scanned clumps packed on a disc, thinning towards the rim so that
    neighbouring patches merge. Instancing these instead of single clumps keeps the instance count low."""
    seg, rings = 24, 6
    V, F, Wt = [(0.0, 0.0, 0.0)], [], [1.0]
    for i in range(1, rings + 1):
        r = radius * i / rings
        for j in range(seg):
            a = 2 * math.pi * j / seg
            V.append((r * math.cos(a), r * math.sin(a), 0.0))
            Wt.append(max(0.0, 1.0 - (i / rings) ** 2.2))
    for j in range(seg):
        F.append((0, 1 + j, 1 + (j + 1) % seg))
    for i in range(1, rings):
        for j in range(seg):
            a, b = 1 + (i - 1) * seg + j, 1 + (i - 1) * seg + (j + 1) % seg
            c, d = 1 + i * seg + (j + 1) % seg, 1 + i * seg + j
            F.append((a, d, c))
            F.append((a, c, b))
    disc = C.tri_mesh('tmp_disc', np.array(V, np.float32), np.array(F, np.int32), attrs={'w': np.array(Wt, np.float32)})
    carrier = bpy.data.objects.new('tmp_disc', disc)
    bpy.context.scene.collection.objects.link(carrier)
    area_w = math.pi * radius * radius * 0.52
    ng = bpy.data.node_groups.new('tmp_patch', 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    jn = N.new('GeometryNodeJoinGeometry')
    for k, (col, cnt, sc) in enumerate(((dry, n_dry, (0.6, 1.25)), (green, n_green, (0.7, 1.3)))):
        at = N.new('GeometryNodeInputNamedAttribute'); at.data_type = 'FLOAT'; at.inputs['Name'].default_value = 'w'
        mul = N.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = cnt / area_w
        L.new(at.outputs[0], mul.inputs[0])
        dp = N.new('GeometryNodeDistributePointsOnFaces'); dp.distribute_method = 'RANDOM'
        dp.inputs['Seed'].default_value = seed * 7 + k
        L.new(gi.outputs[0], dp.inputs['Mesh']); L.new(mul.outputs[0], dp.inputs['Density'])
        ci = N.new('GeometryNodeCollectionInfo')
        ci.inputs['Collection'].default_value = col
        ci.inputs['Separate Children'].default_value = True
        ci.inputs['Reset Children'].default_value = True
        ip = N.new('GeometryNodeInstanceOnPoints')
        L.new(dp.outputs['Points'], ip.inputs['Points']); L.new(ci.outputs['Instances'], ip.inputs['Instance'])
        ip.inputs['Pick Instance'].default_value = True
        rv = N.new('FunctionNodeRandomValue'); rv.data_type = 'FLOAT_VECTOR'
        rv.inputs['Min'].default_value = (-0.18, -0.18, 0.0); rv.inputs['Max'].default_value = (0.18, 0.18, 6.283)
        rv.inputs['Seed'].default_value = seed * 7 + k + 3
        er = N.new('FunctionNodeEulerToRotation'); L.new(rv.outputs['Value'], er.inputs['Euler'])
        L.new(er.outputs['Rotation'], ip.inputs['Rotation'])
        rs = N.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'
        rs.inputs['Min'].default_value = sc[0]; rs.inputs['Max'].default_value = sc[1]; rs.inputs['Seed'].default_value = seed * 7 + k + 5
        L.new(rs.outputs['Value'], ip.inputs['Scale'])
        L.new(ip.outputs['Instances'], jn.inputs[0])
    rz = N.new('GeometryNodeRealizeInstances')
    L.new(jn.outputs[0], rz.inputs[0])
    L.new(rz.outputs[0], go.inputs[0])
    md = carrier.modifiers.new('p', 'NODES')
    md.node_group = ng
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(carrier.evaluated_get(dg), depsgraph=dg)
    me.name = name
    bpy.data.objects.remove(carrier, do_unlink=True)
    bpy.data.meshes.remove(disc)
    bpy.data.node_groups.remove(ng)
    old_o = bpy.data.objects.get(name)
    if old_o is not None:
        om = old_o.data
        bpy.data.objects.remove(old_o, do_unlink=True)
        if om.users == 0:
            bpy.data.meshes.remove(om)
    return bpy.data.objects.new(name, me)


def tint_materials(objs, hue=0.5, sat=1.0, val=1.0, jitter=(0.02, 0.2, 0.25), mix_col=None, mix_fac=0.0):
    """Insert a per-instance colour variation (and an optional tint) before the Base Color of the objects'
    materials. Idempotent: reuses its own nodes."""
    done = set()
    for o in objs:
        for m in o.data.materials:
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            t = m.node_tree
            bs = next((n for n in t.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bs is None:
                continue

            def nm(n):
                try:
                    return n.name
                except UnicodeDecodeError:          # some library node names are not valid UTF-8
                    return ''
            mine = [n for n in t.nodes if nm(n).startswith('MC_')]
            for n in mine:
                if nm(n) == 'MC_hsv' and n.inputs['Color'].is_linked:      # restore the original link first
                    t.links.new(n.inputs['Color'].links[0].from_socket, bs.inputs['Base Color'])
            for n in mine:
                t.nodes.remove(n)
            if not bs.inputs['Base Color'].is_linked:
                continue
            src = bs.inputs['Base Color'].links[0].from_socket
            info = t.nodes.new('ShaderNodeObjectInfo'); info.name = 'MC_info'
            rnd = info.outputs['Random']
            w = t.nodes.new('ShaderNodeTexWhiteNoise'); w.name = 'MC_wn'; w.noise_dimensions = '1D'
            t.links.new(rnd, w.inputs['W'])
            sep = t.nodes.new('ShaderNodeSeparateColor'); sep.name = 'MC_sep'
            t.links.new(w.outputs['Color'], sep.inputs[0])
            hsv = t.nodes.new('ShaderNodeHueSaturation'); hsv.name = 'MC_hsv'

            def lin(sock, base, amp, name):
                mth = t.nodes.new('ShaderNodeMath'); mth.name = name; mth.operation = 'MULTIPLY_ADD'
                t.links.new(sock, mth.inputs[0])
                mth.inputs[1].default_value = 2 * amp
                mth.inputs[2].default_value = base - amp
                return mth.outputs[0]
            t.links.new(lin(sep.outputs[0], hue, jitter[0], 'MC_h'), hsv.inputs['Hue'])
            t.links.new(lin(sep.outputs[1], sat, jitter[1], 'MC_s'), hsv.inputs['Saturation'])
            t.links.new(lin(sep.outputs[2], val, jitter[2], 'MC_v'), hsv.inputs['Value'])
            t.links.new(src, hsv.inputs['Color'])
            out = hsv.outputs[0]
            if mix_col is not None:
                mx = t.nodes.new('ShaderNodeMix'); mx.name = 'MC_mix'; mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'
                mx.inputs[0].default_value = mix_fac
                t.links.new(out, mx.inputs[6])
                mx.inputs[7].default_value = tuple(mix_col) + (1,)
                out = mx.outputs[2]
            t.links.new(out, bs.inputs['Base Color'])


def tune_plants(objs, dead=None, hue=(0.5, 0.5), sat=(1.0, 1.0), val=(1.0, 1.0), noise_scale=2.5):
    """Poly Haven plant materials are one node group with Dead Amount / Hue / Saturation / Value inputs: drive them
    per instance (Object Info random) and per clump (a noise in world space), so no two tufts match."""
    done = set()
    for o in objs:
        for m in o.data.materials:
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            t = m.node_tree
            grp = next((n for n in t.nodes if n.type == 'GROUP' and 'Hue' in n.inputs), None)
            if grp is None:
                continue
            for n in list(t.nodes):
                try:
                    if n.name.startswith('MC_'):
                        t.nodes.remove(n)
                except UnicodeDecodeError:
                    pass
            info = t.nodes.new('ShaderNodeObjectInfo'); info.name = 'MC_info'
            geo = t.nodes.new('ShaderNodeNewGeometry'); geo.name = 'MC_geo'
            nz = t.nodes.new('ShaderNodeTexNoise'); nz.name = 'MC_noise'
            nz.inputs['Scale'].default_value = noise_scale
            nz.inputs['Detail'].default_value = 3.0
            t.links.new(geo.outputs['Position'], nz.inputs['Vector'])
            wn = t.nodes.new('ShaderNodeTexWhiteNoise'); wn.name = 'MC_wn'; wn.noise_dimensions = '1D'
            t.links.new(info.outputs['Random'], wn.inputs['W'])
            sep = t.nodes.new('ShaderNodeSeparateColor'); sep.name = 'MC_sep'
            t.links.new(wn.outputs['Color'], sep.inputs[0])

            def drive(sock_name, rng_, src):
                if sock_name not in grp.inputs or rng_ is None:
                    return
                mix = t.nodes.new('ShaderNodeMath'); mix.name = 'MC_m_' + sock_name[:6]; mix.operation = 'ADD'
                half = t.nodes.new('ShaderNodeMath'); half.name = 'MC_h_' + sock_name[:6]; half.operation = 'MULTIPLY'
                t.links.new(nz.outputs['Fac'], half.inputs[0]); half.inputs[1].default_value = 1.0
                t.links.new(src, mix.inputs[0]); t.links.new(half.outputs[0], mix.inputs[1])       # 0..2
                mr = t.nodes.new('ShaderNodeMapRange'); mr.name = 'MC_r_' + sock_name[:6]
                t.links.new(mix.outputs[0], mr.inputs[0])
                mr.inputs[1].default_value = 0.45; mr.inputs[2].default_value = 1.55
                mr.inputs[3].default_value = rng_[0]; mr.inputs[4].default_value = rng_[1]
                t.links.new(mr.outputs[0], grp.inputs[sock_name])
            drive('Dead Amount', dead, sep.outputs[0])
            drive('Hue', hue if hue[0] != hue[1] else None, sep.outputs[1])
            drive('Saturation', sat if sat[0] != sat[1] else None, sep.outputs[2])
            drive('Value', val if val[0] != val[1] else None, sep.outputs[1])
            if hue[0] == hue[1]:
                grp.inputs['Hue'].default_value = hue[0]
            if sat[0] == sat[1]:
                grp.inputs['Saturation'].default_value = sat[0]


def build(density=1.0):
    base, area = scatter_base()
    out = {'area_m2': round(area)}
    dry = pick('grass_medium_02', r'_[a-e]$')
    green = pick('grass_medium_01', r'(small|medium).*LOD1$') or pick('grass_medium_01', r'LOD1$', 0.1)
    shrubs = pick('shrub_02', r'LOD2$') + pick('wild_rooibos_bush', r'LOD3$') + pick('shrub_04', r'LOD2$')
    fl_y = pick('celandine_01', r'LOD1$') + pick('flower_empodium', r'LOD1$')
    fl_b = pick('periwinkle_plant', r'LOD3$')
    stones = pick('namaqualand_stones_01', r'LOD3$') + pick('rock_09', r'LOD3$') + pick('rock_07', r'LOD3$')
    rocks = pick('namaqualand_rocks_01', r'LOD3$')
    boulders = pick('rock_moss_set_02', r'rock\d+$') + pick('boulder_01', r'LOD3$') + pick('namaqualand_boulder_05', r'LOD2$')
    # autumn at 4400 m: straw and gold, some olive; dwarf shrubs from dark green to russet
    tune_plants(dry, dead=(0.55, 1.0), hue=(0.5, 0.525), sat=(0.9, 1.15), val=(1.0, 1.7))
    tune_plants(green, dead=(0.0, 0.8), sat=(0.85, 1.1), val=(1.0, 1.5))
    tune_plants(shrubs, hue=(0.36, 0.5), sat=(0.75, 1.05), val=(0.55, 0.95))
    tint_materials(stones + rocks + boulders, hue=0.5, sat=0.38, val=0.62, jitter=(0.01, 0.12, 0.22),
                   mix_col=(0.82, 0.84, 0.88), mix_fac=0.6)
    col_dry = instance_collection('LIB_clumps_dry', dry)
    col_green = instance_collection('LIB_clumps_green', green)
    patches = [make_patch('PATCH_meadow_%d' % i, 11 + i, col_dry, col_green, n_dry=nd, n_green=ng_)
               for i, (nd, ng_) in enumerate(((64, 6), (56, 14), (70, 2), (44, 26), (60, 10)))]
    out['patch_faces'] = [len(p.data.polygons) for p in patches]
    L = [
        ('SC_meadow', patches, 'd_dry', 2.6, (0.8, 1.3), 'align', 0.0),
        ('SC_grass_dry', dry, 'd_dry', 5.0, (0.7, 1.5), True, 0.0),
        ('SC_grass_green', green, 'd_green', 9.0, (0.7, 1.4), True, 0.0),
        ('SC_shrubs', shrubs, 'd_shrub', 0.55, (0.35, 0.75), True, 0.02),
        ('SC_flowers_y', fl_y, 'd_flower', 1.1, (0.8, 1.5), True, 0.0),
        ('SC_flowers_b', fl_b, 'd_flower', 0.8, (0.9, 1.6), True, 0.0),
        ('SC_stones', stones, 'd_stone', 1.6, (0.6, 2.4), False, 0.02),
        ('SC_rocks', rocks, 'd_stone', 0.16, (1.2, 3.6), False, 0.045),
        ('SC_boulders', boulders, 'd_rock', 0.010, (0.25, 0.75), False, 0.22),
    ]
    for i, (nm, objs, attr, dens, sc, up, sink) in enumerate(L):
        if not objs:
            out[nm] = 'NO OBJECTS'
            continue
        col = instance_collection('LIB_' + nm, objs)
        gn_scatter(nm, base, col, attr, dens * density, sc, seed=zlib.crc32(nm.encode()) % 10000, upright=bool(up), sink=sink,
                   align=(up == 'align'), tilt=0.05 if up == 'align' else 0.12)
        out[nm] = len(objs)
    return out


# ====================================================================== Megascans ground cover
class FarGround:
    """Graded ground on the 1 m grid out to 700 m (written by proc/mesh_near.py)."""

    def __init__(self):
        d = np.load(os.path.join(C.DEM, 'site_far.npz'))
        self.a = {k: d[k].astype(np.float32) for k in ('z', 'slope', 'rocky', 'curv', 'north', 'track', 'sdf')}
        self.x0, self.y0, self.cell = float(d['x0']), float(d['y0']), float(d['cell'])

    def s(self, k, x, y):
        a = self.a[k]
        c = np.clip((np.asarray(x, float) - self.x0) / self.cell, 0, a.shape[1] - 1.001)
        r = np.clip((np.asarray(y, float) - self.y0) / self.cell, 0, a.shape[0] - 1.001)
        c0, r0 = c.astype(int), r.astype(int)
        fc, fr = c - c0, r - r0
        return (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0 + 1, c0] * fr * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc +
                a[r0 + 1, c0 + 1] * fr * fc)


def _view():
    cam = bpy.data.objects.get('CAM_final')
    if cam is None:
        return CAM, VIEW_AZ
    return tuple(cam.location), mc_light_az(cam)


def cover_fields(X, Y, slope, r):
    """Where things grow (0..1 fields in world space): shrub thickets in drifts, turf between them, bare patches,
    golden grass drifts, flower patches, stony ground."""
    T = smooth(vnoise(X, Y, 12.0, 41) * 0.7 + vnoise(X, Y, 3.6, 43) * 0.3 + 0.12 * smooth(slope, 0.15, 0.55), 0.47, 0.56)
    B = smooth(vnoise(X, Y, 6.0, 17) + 0.2 * smooth(slope, 0.5, 0.9), 0.67, 0.75)
    G = smooth(vnoise(X, Y, 9.0, 55), 0.45, 0.70)
    F = smooth(vnoise(X, Y, 7.0, 71), 0.62, 0.75) * smooth(r, 95.0, 55.0)
    S = smooth(vnoise(X, Y, 6.5, 73) + 0.5 * B, 0.55, 0.80)
    return T, B, G, F, S


def base_near(name='SCAT_near', R=175.0, half_angle=52.0, cell=0.4):
    """Carrier mesh for the ground cover within R of the camera (inside the view), with a density weight per
    species and a scale factor that grows with distance while the density thins."""
    g = Ground()
    cam, az0 = _view()
    xs = np.arange(cam[0] - R, cam[0] + 30.0, cell)
    ys = np.arange(cam[1] - R, cam[1] + 30.0, cell)
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X - cam[0], Y - cam[1])
    da = (np.degrees(np.arctan2(Y - cam[1], X - cam[0])) - az0 + 180) % 360 - 180
    keepv = ((np.abs(da) < half_angle) & (r < R)) | (r < 14.0)
    keepv &= (np.abs(X) < 128) & (np.abs(Y) < 128)
    Z = g.z(X, Y)
    sdf = g.sdf(X, Y)
    trd = g._s(np.load(os.path.join(C.DEM, 'site_h.npz'))['trackd'].astype(np.float32), X, Y)
    slope = np.hypot((g.z(X + 0.4, Y) - g.z(X - 0.4, Y)) / 0.8, (g.z(X, Y + 0.4) - g.z(X, Y - 0.4)) / 0.8)
    T, B, G, F, S = cover_fields(X, Y, slope, r)
    lod = smooth(r, 50.0, 150.0)
    kd = (1.0 - 0.80 * lod) * smooth(r, R, R - 25.0)              # thinner with distance, out at the rim
    # the track: nothing in the ruts, turf on the crown and creeping in from the verges
    on_track = smooth(trd, 2.2, 1.7)
    tr_turf = np.maximum(smooth(trd, 0.42, 0.15) * 0.45, smooth(trd, 1.35, 1.9) * 0.7)
    U, V = mc_site.to_local(X, Y)
    in_v = (V > mc_site.WALL_V[0] - 0.3) & (V < mc_site.WALL_V[1] + 0.3)
    clear = (sdf > 0.25) & ~(in_v & (np.abs(U - mc_site.WALL_U) < 0.5))        # not under the box, not in the wall
    open_ = clear * ((1 - on_track) + on_track * tr_turf * smooth(vnoise(X, Y, 2.0, 81), 0.35, 0.6))
    shrub_ok = clear * (1 - on_track) * (sdf > 0.9)
    wallfoot = in_v * smooth(mc_site.WALL_U - U, 1.6, 0.5) * (U < mc_site.WALL_U - 0.5)      # rank grass at the wall's foot
    veg = open_ * (1 - B)
    A = {
        'd_wild': veg * (15.0 * (1 - T) + 4.0 * T + 5.0 * wallfoot),
        'd_mat': veg * (3.4 * (1 - T) + 0.6 * T),
        'd_tall': veg * (1 - T) * (0.5 + 1.6 * G),
        'd_dry': veg * (1 - 0.7 * T) * (0.25 + 1.6 * G),
        'd_tuft': veg * (1 - T) * (0.06 + 0.5 * G),
        'd_ling': veg * shrub_ok * (8.0 * T + 0.8 * (1 - T)),
        'd_will': veg * shrub_ok * (5.5 * T + 1.2 * (1 - T)),
        'd_birch': veg * shrub_ok * (5.5 * T + 1.4 * wallfoot),
        'd_flower': veg * (1 - T) * F * 0.7,
    }
    for k in A:
        A[k] = A[k] * kd
    A['sc'] = 1.0 + 0.75 * lod
    kq = keepv[:-1, :-1] & keepv[1:, :-1] & keepv[:-1, 1:] & keepv[1:, 1:]
    me = C.grid_mesh(name, np.stack([X, Y, Z], -1).reshape(-1, 3), X.shape[0], X.shape[1], keep=kq,
                     attrs={k: v.ravel() for k, v in A.items()})
    o = C.obj(name, me, C.coll('MC_scatter'))
    o.hide_render = True
    o.hide_viewport = True
    return o, int(kq.sum()) * cell * cell


def base_far(name='SCAT_far', R0=150.0, R1=640.0, half_angle=50.0, cell=2.0):
    """Carrier for the cover between R0 and R1: shrubs and tussocks as larger, sparser instances (3-10 px each)."""
    g = FarGround()
    cam, az0 = _view()
    xs = np.arange(max(g.x0 + 2, cam[0] - R1), min(cam[0] + 60.0, 318.0), cell)
    ys = np.arange(max(g.y0 + 2, cam[1] - R1), min(cam[1] + 60.0, 318.0), cell)
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X - cam[0], Y - cam[1])
    da = (np.degrees(np.arctan2(Y - cam[1], X - cam[0])) - az0 + 180) % 360 - 180
    keepv = (np.abs(da) < half_angle) & (r > R0 - 4) & (r < R1)
    Z = g.s('z', X, Y)
    slope = g.s('slope', X, Y)
    rocky = g.s('rocky', X, Y)
    trk = g.s('track', X, Y)
    T, B, G, F, S = cover_fields(X, Y, slope, r)
    curv = g.s('curv', X, Y)
    crest = smooth(curv, 0.2, 1.2)
    foot = smooth(slope, 0.25, 0.5) * smooth(curv, -0.2, -1.0)
    cluster = smooth(vnoise(X, Y, 16.0, 91), 0.64, 0.72)
    k = smooth(r, R0 - 4, R0 + 22.0) * smooth(r, R1, R1 - 120.0) * (1 - np.clip(trk * 2, 0, 1)) * smooth(slope, 1.3, 0.9)
    k = k * np.clip(260.0 / r, 0.25, 1.0)                               # thinner still far out
    A = {
        'd_shrub': k * (1 - B) * (0.55 * T + 0.05) * (1 - 0.6 * rocky),
        'd_grass': k * (1 - B) * (0.9 * (1 - T) + 0.15),
        'd_gold': k * (1 - B) * (1 - T) * 0.25 * G,
        # rock in the middle distance follows the ground: groups on the convex crests where the soil is thin and at
        # the foot of steep slopes, almost none in the grassy hollows
        'd_stone': k * cluster * (0.9 * crest + 0.7 * foot + 0.03) * 0.30,
        'd_block': k * cluster * (crest + foot) * 0.018,
        'sc': 1.0 + 0.8 * smooth(r, R0, 520.0),
    }
    kq = keepv[:-1, :-1] & keepv[1:, :-1] & keepv[:-1, 1:] & keepv[1:, 1:]
    me = C.grid_mesh(name, np.stack([X, Y, Z], -1).reshape(-1, 3), X.shape[0], X.shape[1], keep=kq,
                     attrs={k_: v.ravel() for k_, v in A.items()})
    o = C.obj(name, me, C.coll('MC_scatter'))
    o.hide_render = True
    o.hide_viewport = True
    return o, int(kq.sum()) * cell * cell


def build_fab(density=1.0):
    """Meadow of Megascans plants and stones: continuous cover growing in drifts (see cover_fields)."""
    import mc_fab
    for o in [o for o in bpy.data.objects if o.name.startswith(('SC_', 'PATCH_'))]:
        C.remove_object(o.name)
    near, a1 = base_near()
    far, a2 = base_far()
    out = {'near_m2': round(a1), 'far_m2': round(a2)}
    F = mc_fab.objects
    P = mc_fab.plant_material
    # autumn tundra at 4400 m: olive and straw turf, dark russet-brown shrubs
    P('wild_grass', hue=0.49, sat=0.50, val=0.46, jitter=(0.015, 0.16, 0.14))
    P('tundra_grass', hue=0.495, sat=0.52, val=0.52, jitter=(0.015, 0.16, 0.16))
    P('tufted_grass', hue=0.46, sat=0.45, val=0.55, jitter=(0.02, 0.14, 0.16))
    P('dry_grass', hue=0.5, sat=0.62, val=0.70, jitter=(0.01, 0.14, 0.18))
    P('lingonberry', hue=0.5, sat=0.55, val=0.38, jitter=(0.02, 0.18, 0.14))
    P('dwarf_willow', hue=0.47, sat=0.55, val=0.38, jitter=(0.025, 0.18, 0.14))
    P('dwarf_birch', hue=0.455, sat=0.60, val=0.32, jitter=(0.03, 0.18, 0.12), transl=0.2)
    P('yellow_flower', hue=0.5, sat=0.8, val=0.75, jitter=(0.01, 0.1, 0.1))
    for key in ('stone', 'boulder_a', 'boulder_b'):
        mc_fab.rock_material(key, sat=0.6, val=0.62)
    tg = F('tundra_grass')
    mats = [o for o in tg if o.name[-4:] in ('VarD', 'VarE', 'VarH', 'VarI')]
    tall = [o for o in tg if o.name[-4:] in ('VarA', 'VarB', 'VarC', 'VarF', 'VarG')]
    flowers = [o for o in F('yellow_flower') if o.name[-4:] in ('VarB', 'VarC', 'VarE', 'VarF', 'VarG', 'VarH')]
    stones = F('stone')
    boulders = F('boulder_a') + F('boulder_b')
    shrubs = F('dwarf_birch')
    L = [  # name, base, objects, attr, density per m2, scale range, upright, sink, tilt
        ('SC_wild', near, F('wild_grass'), 'd_wild', 1.0, (0.75, 1.5), True, 0.0, 0.15),
        ('SC_mat', near, mats, 'd_mat', 1.0, (0.6, 1.15), True, 0.0, 0.08),
        ('SC_tall', near, tall, 'd_tall', 1.0, (0.55, 1.0), True, 0.0, 0.12),
        ('SC_dry', near, F('dry_grass'), 'd_dry', 1.0, (0.6, 1.1), True, 0.0, 0.15),
        ('SC_tuft', near, F('tufted_grass'), 'd_tuft', 1.0, (0.35, 0.62), True, 0.0, 0.1),
        ('SC_ling', near, F('lingonberry'), 'd_ling', 1.0, (0.8, 1.5), True, 0.0, 0.12),
        ('SC_will', near, F('dwarf_willow'), 'd_will', 1.0, (0.8, 1.6), 'align', 0.0, 0.06),
        ('SC_birch', near, shrubs, 'd_birch', 1.0, (0.9, 1.7), True, 0.03, 0.2),
        ('SC_flower', near, flowers, 'd_flower', 1.0, (0.9, 1.6), True, 0.0, 0.1),
        # (no scattered stones here: the foreground rocks are placed by hand, lib/mc_rocks.py)
        ('SF_shrub', far, shrubs + F('dwarf_willow')[:3], 'd_shrub', 1.0, (1.1, 1.8), True, 0.05, 0.15),
        ('SF_grass', far, mats + F('wild_grass')[:4], 'd_grass', 1.0, (1.2, 2.0), True, 0.0, 0.1),
        ('SF_gold', far, F('dry_grass')[:3] + tall[:2], 'd_gold', 1.0, (1.4, 2.2), True, 0.0, 0.12),
        ('SF_stone', far, stones, 'd_stone', 1.0, (0.25, 0.9), 'bedded', 0.45, 0.08),
        ('SF_block', far, F('boulder_a'), 'd_block', 1.0, (0.35, 0.9), 'bedded', 0.5, 0.08),
    ]
    for nm, base, objs, attr, dens, sc, up, sink, tilt in L:
        if not objs:
            out[nm] = 'NO OBJECTS'
            continue
        col = instance_collection('LIB_' + nm, objs)
        import mc_rocks
        yaw = (mc_rocks.bedded_yaw('boulder_a' if nm == 'SF_block' else 'stone'), 8.0) if up == 'bedded' else None
        gn_scatter(nm, base, col, attr, dens * density, sc, seed=zlib.crc32(nm.encode()) % 10000, upright=bool(up), sink=sink,
                   align=(up == 'align'), tilt=tilt, scale_attr='sc', yaw=yaw)
        out[nm] = len(objs)
    return out
