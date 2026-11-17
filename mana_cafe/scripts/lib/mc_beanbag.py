"""Outdoor bean bags, shaped by cloth simulation: an under-filled sewn bag is dropped on the paving, somebody sits in
it (a collider) and gets up again; the simulated shape at that moment is kept as a static mesh."""
import bpy, math, zlib
import numpy as np
import mc_core as C
import mc_site
from mc_core import NT

SIM_AT = (400.0, 400.0)            # simulate far from the scene, then move the result into place


def _uv_sphere(seg=48, rings=30, rx=0.50, ry=0.50, rz=0.42, pear=0.0):
    V, F = [(0.0, 0.0, -rz)], []
    for i in range(1, rings):
        th = math.pi * i / rings
        zc = -math.cos(th)
        k = 1.0 - pear * 0.5 * (zc + 1.0)                 # pear: narrower towards the top
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            V.append((rx * k * math.sin(th) * math.cos(ph), ry * k * math.sin(th) * math.sin(ph), rz * zc))
    V.append((0.0, 0.0, rz))
    top = len(V) - 1
    for j in range(seg):
        F.append((0, 1 + (j + 1) % seg, 1 + j))
        F.append((top, top - seg + j, top - seg + (j + 1) % seg))
    for i in range(rings - 2):
        for j in range(seg):
            a, b = 1 + i * seg + j, 1 + i * seg + (j + 1) % seg
            F.append((a, b, b + seg, a + seg))
    return np.array(V), F


def _pillow(nx=56, ny=72, lx=1.35, ly=1.75, th=0.10):
    """Two sheets sewn at the rim (a big floor cushion)."""
    V, F = [], []
    idx = {}
    for side in (0, 1):
        for i in range(nx + 1):
            for j in range(ny + 1):
                rim = i in (0, nx) or j in (0, ny)
                if side == 1 and rim:
                    idx[(1, i, j)] = idx[(0, i, j)]
                    continue
                x = (i / nx - 0.5) * lx
                y = (j / ny - 0.5) * ly
                d = min(i, nx - i, j, ny - j) / 6.0
                z = (th * min(1.0, d) ** 0.5) * (1 if side == 0 else -1)
                idx[(side, i, j)] = len(V)
                V.append((x, y, z))
    for side in (0, 1):
        for i in range(nx):
            for j in range(ny):
                q = (idx[(side, i, j)], idx[(side, i + 1, j)], idx[(side, i + 1, j + 1)], idx[(side, i, j + 1)])
                F.append(q if side == 0 else q[::-1])
    return np.array(V), F


def _mesh(name, V, F):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F])
    me.update()
    return me


def simulate(name, kind='round', seed=0, frames=70, sit=(0.0, 0.05, 0.26), sit_size=(0.25, 0.23, 0.17), lean=0.0,
             volume=0.74, quality=9):
    """Returns a static mesh of the settled, sat-in bag (origin at its footprint centre, z = 0 on the ground)."""
    sc = bpy.context.scene
    rng = np.random.default_rng(seed)
    k = rng.uniform(0.94, 1.06)
    if kind == 'round':
        V, F = _uv_sphere(seg=72, rings=46, rx=0.76 * k, ry=0.76 * rng.uniform(0.95, 1.06), rz=0.62, pear=0.28)
    else:                                    # a longer lounger
        V, F = _uv_sphere(seg=72, rings=50, rx=0.78 * k, ry=1.08 * rng.uniform(0.95, 1.05), rz=0.50, pear=0.15)
    z0 = 0.72
    V = V + rng.normal(0, 0.004, V.shape)
    ox, oy = SIM_AT
    me = _mesh(name + '_sim', V, F)
    ob = bpy.data.objects.new(name + '_sim', me)
    sc.collection.objects.link(ob)
    ob.location = (ox, oy, z0)
    ob.rotation_euler = (lean, 0.0, 0.0)
    # seams gather the cloth a little: 8 gores on the round bag, the rim on the pillow
    vg = ob.vertex_groups.new(name='seam')
    if kind == 'round':
        ang = np.arctan2(V[:, 1], V[:, 0])
        w = np.exp(-(np.abs(((ang / (2 * math.pi) * 8) % 1.0) - 0.5) * 2 - 1.0) ** 2 / 0.01)
    else:
        ang = np.arctan2(V[:, 1], V[:, 0])
        w = np.exp(-(np.abs(((ang / (2 * math.pi) * 6) % 1.0) - 0.5) * 2 - 1.0) ** 2 / 0.01)
    for i, wi in enumerate(w):
        if wi > 0.05:
            vg.add([i], float(min(wi, 1.0)), 'REPLACE')
    # ground and sitter
    bpy.ops.mesh.primitive_plane_add(size=8, location=(ox, oy, 0.0))
    ground = bpy.context.object
    ground.name = name + '_ground'
    cm = ground.modifiers.new('c', 'COLLISION')
    ground.collision.thickness_outer = 0.012
    ground.collision.cloth_friction = 40.0
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, radius=1.0, location=(ox + sit[0], oy + sit[1], 2.0))
    sitter = bpy.context.object
    sitter.name = name + '_sitter'
    sitter.scale = sit_size
    sitter.modifiers.new('c', 'COLLISION')
    sitter.collision.thickness_outer = 0.01
    sitter.collision.cloth_friction = 20.0
    f_down0, f_down1 = int(frames * 0.42), int(frames * 0.72)
    sitter.location = (ox + sit[0], oy + sit[1], 2.0)
    sitter.keyframe_insert('location', frame=1)
    sitter.keyframe_insert('location', frame=f_down0)
    sitter.location = (ox + sit[0], oy + sit[1], sit[2])
    sitter.keyframe_insert('location', frame=f_down1)
    sitter.keyframe_insert('location', frame=frames)
    md = ob.modifiers.new('cloth', 'CLOTH')
    cs = md.settings
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    v0 = abs(bm.calc_volume())
    bm.free()
    cs.quality = quality
    cs.mass = 9.0 / len(V)                  # a 9 kg bag (the cloth mass is per vertex)
    cs.air_damping = 3.0
    cs.tension_stiffness = 22.0
    cs.compression_stiffness = 22.0
    cs.shear_stiffness = 9.0
    cs.bending_stiffness = 0.9
    cs.tension_damping = 8.0
    cs.compression_damping = 8.0
    cs.shear_damping = 8.0
    cs.bending_damping = 0.8
    cs.use_pressure = True                  # the filling keeps its volume: pressure rises as the bag is squeezed
    cs.uniform_pressure_force = 0.0
    cs.use_pressure_volume = True
    cs.target_volume = v0 * volume
    cs.pressure_factor = 9.0
    cs.fluid_density = 0.0
    cs.vertex_group_shrink = 'seam'
    cs.shrink_min = 0.0
    cs.shrink_max = 0.05
    co = md.collision_settings
    co.use_collision = True
    co.distance_min = 0.012
    co.collision_quality = 3
    co.use_self_collision = True
    co.self_distance_min = 0.008
    co.self_friction = 8.0
    md.point_cache.frame_start = 1
    md.point_cache.frame_end = frames
    f0 = sc.frame_current
    dg = bpy.context.evaluated_depsgraph_get()
    # the bag is under-filled: aim for a fraction of the sewn volume
    for f in range(1, frames + 1):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    out = bpy.data.meshes.new_from_object(ev, depsgraph=dg)
    out.name = name
    co_ = np.empty(len(out.vertices) * 3, np.float32)
    out.vertices.foreach_get('co', co_)
    co_ = co_.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    w = co_ @ M[:3, :3].T + M[:3, 3]
    w[:, 0] -= ox
    w[:, 1] -= oy
    out.vertices.foreach_set('co', w.astype(np.float32).ravel())
    out.update()
    for o in (ob, ground, sitter):
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    sc.frame_set(f0)
    out.shade_smooth()
    return out, (float(w[:, 2].min()), float(w[:, 2].max()), float(np.ptp(w[:, 0])), float(np.ptp(w[:, 1])))


def fabric(name, color, key='wool'):
    """Outdoor bean-bag cover from the Megascans wool / furniture fabric scan (box-projected, recoloured), slightly
    sun-faded on top, with dust in the folds."""
    import mc_fab
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    geo = n.node('ShaderNodeNewGeometry')
    tc = n.node('ShaderNodeTexCoord')
    P = tc.outputs['Object']
    mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': P, 'Scale': (1.6, 1.6, 1.6)})

    def tex(kind):
        nd = n.node('ShaderNodeTexImage', projection='BOX', projection_blend=0.3, inputs={'Vector': mp.outputs[0]})
        nd.image = mc_fab.image(key, kind)
        return nd
    base = tex('color').outputs['Color']
    lum = n.node('ShaderNodeRGBToBW', inputs={0: base}).outputs[0]
    weave = n.lin(lum, 0.25, 0.75, 0.72, 1.2)                                   # the scan's own light and dark threads
    Nz = n.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Normal']}).outputs['Z']
    big = n.noise(P, 2.2, 4, 0.55).outputs['Fac']
    col = n.mix(1.0, tuple(color) + (1,), n.node('ShaderNodeCombineColor', inputs={0: weave, 1: weave, 2: weave}).outputs[0], 'MULTIPLY')
    col = n.mix(1.0, col, n.ramp(big, [(0.25, (0.86, 0.86, 0.86, 1)), (0.75, (1.1, 1.1, 1.1, 1))]), 'MULTIPLY')
    col = n.mix(n.math('MULTIPLY', n.smooth(Nz, 0.2, 0.95), 0.10), col, (0.42, 0.41, 0.39, 1))        # bleached on top
    ao = n.node('ShaderNodeAmbientOcclusion', inputs={'Distance': 0.15}, samples=4)
    col = n.mix(n.math('MULTIPLY', n.smooth(ao.outputs['AO'], 0.8, 0.3), 0.3), col, (0.07, 0.06, 0.05, 1))   # dust in folds
    orm = n.node('ShaderNodeSeparateColor', inputs={0: tex('orm').outputs['Color']}).outputs
    nrm = tex('normal').outputs['Color']
    hgt = n.node('ShaderNodeRGBToBW', inputs={0: nrm}).outputs[0]
    bump = n.node('ShaderNodeBump', inputs={'Strength': 0.5, 'Distance': 0.002, 'Height': lum})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': n.math('MAXIMUM', orm[1], 0.75),
                                                      'Normal': bump.outputs[0], 'Specular IOR Level': 0.2})
    bsdf.inputs['Sheen Weight'].default_value = 0.4
    bsdf.inputs['Sheen Roughness'].default_value = 0.5
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


# muted outdoor colours that sit with rusted steel, slate and tundra
PALETTE = {
    'stone': (0.235, 0.215, 0.185), 'charcoal': (0.032, 0.033, 0.036), 'olive': (0.085, 0.090, 0.058),
    'taupe': (0.150, 0.125, 0.100), 'slate': (0.060, 0.075, 0.090), 'umber': (0.115, 0.058, 0.036),
}

# (name, kind, colour, fabric scan, u, v, yaw offset deg, sitter offset, sitter size)  -- local terrace coordinates;
# all look towards the peaks (-u). Round bags are 1.35 m across, loungers 1.45 x 1.9 m: the real things.
LAYOUT = [
    ('BAG_1', 'round', 'stone', 'wool', -3.5, 14.0, 10.0, (0.0, -0.12, 0.33), (0.31, 0.29, 0.20)),
    ('BAG_2', 'round', 'umber', 'wool', -1.3, 15.1, -16.0, (0.03, -0.10, 0.36), (0.30, 0.28, 0.20)),
    ('BAG_3', 'long', 'slate', 'furniture_fabric', 2.1, 14.4, 14.0, (-0.02, -0.26, 0.28), (0.32, 0.32, 0.19)),
    ('BAG_4', 'round', 'olive', 'wool', 4.9, 13.3, -8.0, (0.0, -0.11, 0.34), (0.31, 0.28, 0.21)),
    ('BAG_5', 'round', 'charcoal', 'wool', 6.4, 10.6, 30.0, (-0.04, -0.12, 0.31), (0.31, 0.29, 0.20)),
    ('BAG_6', 'long', 'taupe', 'wool', -5.6, 12.3, -22.0, (0.04, -0.28, 0.29), (0.32, 0.31, 0.18)),
]


def build(only=None):
    col = C.coll('MC_bags')
    info = {}
    for name, kind, cname, fkey, u, v, yaw, sit, ssize in LAYOUT:
        if only and name not in only:
            continue
        seed = zlib.crc32(name.encode()) % 100000
        me, dims = simulate(name, kind, seed, sit=sit, sit_size=ssize, volume=0.74 if kind == 'round' else 0.70)
        me.materials.append(fabric('MC_bag_' + cname, PALETTE[cname], fkey))
        o = C.obj(name, me, col)
        x, y = mc_site.to_world(u, v)
        # the bag's own +y is where the sitter's back was; it should look towards -u (the view)
        face = math.degrees(mc_site.ROT) + 180.0           # world azimuth of local -u
        o.rotation_euler = (0, 0, math.radians(face + 90.0 + yaw))
        o.location = (x, y, mc_site.Z_T + 0.018 - dims[0])
        sub = o.modifiers.new('sub', 'SUBSURF')
        sub.levels = 1
        sub.render_levels = 2
        info[name] = [round(d, 3) for d in dims]
    return info
