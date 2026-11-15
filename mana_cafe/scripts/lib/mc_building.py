"""Materials and interior light for the cafe. Geometry and furnishing are never touched: only the node trees of the
building's own materials are rebuilt, and lights (no visible geometry) are added inside."""
import bpy, os, math
import mc_core as C
from mc_core import NT
import mc_site

PH = os.path.join(C.ASSETS, 'ph')
SEAM_V0, SEAM_VP = 0.06, 1.37        # panel joints along the long axis: v = 0.06 + k * 1.37
SEAM_U0, SEAM_UP = -5.78, 1.132      # joints on the gables


def img(asset, kind, res='4k', ext=None, colorspace=None):
    """Poly Haven texture file -> image datablock. kind: diff, nor_gl, rough, disp."""
    d = os.path.join(PH, asset)
    if not any(os.path.isfile(os.path.join(d, f)) and not f.endswith('.blend') for f in os.listdir(d)):
        d = os.path.join(d, 'textures')
    alt = {'diff': ('diff', 'col', 'diffuse'), 'disp': ('disp', 'height'), 'rough': ('rough',), 'nor_gl': ('nor_gl',)}
    names = [f for f in os.listdir(d) for k in alt.get(kind, (kind,)) if ('_%s_%s.' % (k, res)) in f]
    im = bpy.data.images.load(os.path.join(d, names[0]), check_existing=True)
    im.colorspace_settings.name = colorspace or ('sRGB' if kind in ('diff', 'dry_diff') else 'Non-Color')
    return im


def local_coords(n):
    """Building-local position (u, v, z) and normal, from world space."""
    geo = n.node('ShaderNodeNewGeometry')
    rot = (0.0, 0.0, -mc_site.ROT)
    p = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': geo.outputs['Position'], 'Rotation': rot})
    nn = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': geo.outputs['True Normal'], 'Rotation': rot})
    ps = n.node('ShaderNodeSeparateXYZ', inputs={0: p.outputs[0]})
    ns = n.node('ShaderNodeSeparateXYZ', inputs={0: nn.outputs[0]})
    return p.outputs[0], ps.outputs, nn.outputs[0], ns.outputs


def seam_dist(n, x, x0, period):
    """Distance to the nearest joint of a regular lattice."""
    t = n.math('DIVIDE', n.math('SUBTRACT', x, x0), period)
    f = n.math('SUBTRACT', t, n.math('ROUND', t))
    return n.math('MULTIPLY', n.math('ABSOLUTE', f), period), n.math('ROUND', t)


def corten(name='Metal_06_1K'):
    """Weathering steel: a scanned coarse-rust surface (box-mapped, shifted per panel), mottled in three scales,
    with run-off streaks below the eaves and the panel joints and a darker splash zone at the foot."""
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    P, (u, v, z), Nl, (nu, nv, nz) = local_coords(n)
    roof = n.smooth(nz, 0.5, 0.8)
    longwall = n.smooth(n.math('ABSOLUTE', nu), 0.5, 0.8)            # east / west walls: panels step along v
    dv, kv = seam_dist(n, v, SEAM_V0, SEAM_VP)
    du, ku = seam_dist(n, u, SEAM_U0, SEAM_UP)
    gable = n.math('SUBTRACT', 1.0, n.math('MAXIMUM', roof, longwall))
    d_seam = n.mixf(gable, dv, du)
    pid = n.math('ADD', n.mixf(gable, kv, n.math('ADD', ku, 40.0)), n.math('MULTIPLY', roof, 100.0))
    rnd = n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D', inputs={'W': pid})
    # scanned rust, 2.2 m tile, random shift per panel so that no two panels match
    shift = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: rnd.outputs['Color'], 'Scale': 7.0})
    vec = n.node('ShaderNodeVectorMath', operation='ADD', inputs={0: P, 1: shift.outputs[0]})
    vec = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: vec.outputs[0], 'Scale': 1.0 / 2.2})

    def tex(kind):
        nd = n.node('ShaderNodeTexImage', projection='BOX', projection_blend=0.15, inputs={'Vector': vec.outputs[0]})
        nd.image = img('rust_coarse_01', kind)
        return nd
    diff, rough, disp = tex('diff'), tex('rough'), tex('disp')
    # --- mottling
    n_l = n.noise(P, 0.55, 4, 0.55).outputs['Fac']               # metre-scale clouds
    n_m = n.noise(P, 4.5, 5, 0.6, dist=0.4).outputs['Fac']       # hand-sized blotches
    n_s = n.noise(P, 60.0, 4, 0.7).outputs['Fac']                # speckle
    col = diff.outputs['Color']
    col = n.node('ShaderNodeHueSaturation', inputs={
        'Hue': n.math('ADD', 0.492, n.math('MULTIPLY', n.math('SUBTRACT', rnd.outputs['Value'], 0.5), 0.016)),
        'Saturation': n.math('ADD', 0.98, n.math('MULTIPLY', n.math('SUBTRACT', n_l, 0.5), 0.30)),
        'Value': n.math('ADD', 0.78, n.math('ADD', n.math('MULTIPLY', n.math('SUBTRACT', n_l, 0.5), 0.36),
                                            n.math('MULTIPLY', n.math('SUBTRACT', rnd.outputs['Value'], 0.5), 0.16))),
        'Color': col}).outputs[0]
    dark = (0.060, 0.028, 0.020, 1)             # deep red-brown, where the patina is oldest and wettest
    orange = (0.42, 0.165, 0.050, 1)            # fresh powdery orange
    col = n.mix(n.math('MULTIPLY', n.smooth(n_m, 0.52, 0.80), 0.55), col, dark)
    col = n.mix(n.math('MULTIPLY', n.smooth(n_m, 0.42, 0.18), 0.28), col, orange)
    col = n.mix(n.math('MULTIPLY', n.smooth(n_s, 0.62, 0.85), 0.25), col, dark)
    # --- run-off streaks: narrow vertical runs on the walls, down the fall on the roof
    sv_wall = n.node('ShaderNodeCombineXYZ', inputs={0: n.math('MULTIPLY', u, 26.0), 1: n.math('MULTIPLY', v, 26.0),
                                                     2: n.math('MULTIPLY', z, 0.55)})
    sv_roof = n.node('ShaderNodeCombineXYZ', inputs={0: n.math('MULTIPLY', u, 0.5), 1: n.math('MULTIPLY', v, 22.0),
                                                     2: 0.0})
    sv = n.node('ShaderNodeMix', data_type='VECTOR', inputs={0: roof})
    n.link(sv_wall.outputs[0], sv.inputs[4])
    n.link(sv_roof.outputs[0], sv.inputs[5])
    st = n.noise(sv.outputs[1], 1.0, 4, 0.6).outputs['Fac']
    st2 = n.noise(sv.outputs[1], 0.23, 3, 0.5).outputs['Fac']
    streak = n.math('MULTIPLY', n.smooth(st, 0.60, 0.80), n.smooth(st2, 0.42, 0.70))
    top = n.smooth(z, 1.0, 2.75)                                    # stronger under the eaves
    near_seam = n.smooth(d_seam, 0.16, 0.012)                       # and beside the joints
    wall_w = n.math('ADD', n.math('MULTIPLY', top, 0.55), n.math('MULTIPLY', near_seam, 0.75))
    wall_w = n.math('ADD', wall_w, 0.12)
    roof_w = n.math('ADD', 0.10, n.math('MULTIPLY', near_seam, 0.45))
    sw = n.math('MULTIPLY', streak, n.mixf(roof, wall_w, roof_w))
    col = n.mix(n.math('MINIMUM', n.math('MULTIPLY', sw, 0.7), 0.6), col, dark)
    # bright orange bleed right at the joints and along the lower panel edge
    bleed = n.math('MULTIPLY', n.smooth(d_seam, 0.05, 0.004), n.smooth(n_m, 0.3, 0.6))
    col = n.mix(n.math('MULTIPLY', bleed, 0.35), col, orange)
    # splash zone at the foot of the walls: darker, dusty
    foot = n.math('MULTIPLY', n.smooth(z, 0.45, 0.02), n.math('SUBTRACT', 1.0, roof))
    foot = n.math('MULTIPLY', foot, n.math('ADD', 0.45, n.math('MULTIPLY', n_m, 0.7)))
    col = n.mix(n.math('MULTIPLY', foot, 0.6), col, (0.075, 0.050, 0.038, 1))
    # dust settles on the low-pitched roof: a little paler and flatter
    col = n.mix(n.math('MULTIPLY', roof, n.math('MULTIPLY', n.smooth(n_l, 0.3, 0.8), 0.22)), col, (0.30, 0.21, 0.15, 1))
    r = n.math('ADD', n.math('MULTIPLY', rough.outputs['Color'], 0.25), 0.74)
    r = n.math('MINIMUM', n.math('ADD', r, n.math('MULTIPLY', sw, 0.08)), 1.0)
    bump = n.node('ShaderNodeBump', inputs={'Strength': 0.55, 'Distance': 0.004, 'Height': disp.outputs['Color']})
    bump2 = n.node('ShaderNodeBump', inputs={'Strength': 0.25, 'Distance': 0.0015, 'Height': n_s, 'Normal': bump.outputs[0]})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': r, 'Metallic': 0.0,
                                                      'Specular IOR Level': 0.12, 'Normal': bump2.outputs[0]})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


def solar(name='Asphalt_02_1K', obj='G-Object.165', nx=15, ny=2):
    """Monocrystalline modules on the roof slab: half-cut cells with light gaps, bus bars, anodised frames, low-iron
    glass with an anti-reflection sheen, and dust gathered along the lower frames."""
    o = bpy.data.objects[obj]
    bb = [tuple(c) for c in o.bound_box]
    x0, x1 = min(b[0] for b in bb), max(b[0] for b in bb)
    y0, y1 = min(b[1] for b in bb), max(b[1] for b in bb)
    z0, z1 = min(b[2] for b in bb), max(b[2] for b in bb)
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    tc = n.node('ShaderNodeTexCoord')
    tc.object = o
    xyz = n.node('ShaderNodeSeparateXYZ', inputs={0: tc.outputs['Object']}).outputs
    geo = n.node('ShaderNodeNewGeometry')
    long_x = (x1 - x0) > (y1 - y0)
    a = xyz[0] if long_x else xyz[1]             # along the ridge
    b = xyz[1] if long_x else xyz[0]             # down the slope
    a0, a1 = (x0, x1) if long_x else (y0, y1)
    b0, b1 = (y0, y1) if long_x else (x0, x1)
    slope_len = math.hypot(b1 - b0, z1 - z0)
    edge = 0.06                                   # bare roof margin round the array
    pa = (a1 - a0 - 2 * edge) / nx               # module pitch
    pb = (slope_len - 2 * edge) / ny
    gap = 0.018
    fa = n.math('DIVIDE', n.math('SUBTRACT', n.math('SUBTRACT', a, a0), edge), pa)
    bs = n.math('MULTIPLY', n.math('SUBTRACT', b, b0), slope_len / (b1 - b0))
    fb = n.math('DIVIDE', n.math('SUBTRACT', bs, edge), pb)
    ia, ib = n.math('FLOOR', fa), n.math('FLOOR', fb)
    ma = n.math('MULTIPLY', n.math('SUBTRACT', fa, ia), pa)       # metres inside the module
    mb = n.math('MULTIPLY', n.math('SUBTRACT', fb, ib), pb)
    inside = n.math('MULTIPLY', n.math('MULTIPLY', n.math('GREATER_THAN', fa, 0.0), n.math('LESS_THAN', fa, float(nx))),
                    n.math('MULTIPLY', n.math('GREATER_THAN', fb, 0.0), n.math('LESS_THAN', fb, float(ny))))
    wa, wb = pa - gap, pb - gap                   # module size
    ea = n.math('MINIMUM', n.math('SUBTRACT', ma, gap / 2), n.math('SUBTRACT', pa - gap / 2, ma))   # to module edge
    eb = n.math('MINIMUM', n.math('SUBTRACT', mb, gap / 2), n.math('SUBTRACT', pb - gap / 2, mb))
    em = n.math('MINIMUM', ea, eb)
    is_gap = n.math('LESS_THAN', em, 0.0)
    frame_w = 0.012
    is_frame = n.math('MULTIPLY', n.math('GREATER_THAN', em, 0.0), n.math('LESS_THAN', em, frame_w))
    # cells: 6 across, 24 half-cells down, 2.2 mm gaps, a wider gap at mid height
    lam_a, lam_b = wa - 2 * frame_w - 0.016, wb - 2 * frame_w - 0.020
    ca = n.math('DIVIDE', n.math('SUBTRACT', ma, gap / 2 + frame_w + 0.008), lam_a / 6)
    cb = n.math('DIVIDE', n.math('SUBTRACT', mb, gap / 2 + frame_w + 0.010), lam_b / 24)
    ca_f = n.math('MULTIPLY', n.math('ABSOLUTE', n.math('SUBTRACT', n.math('FRACT', ca), 0.5)), lam_a / 6)
    cb_f = n.math('MULTIPLY', n.math('ABSOLUTE', n.math('SUBTRACT', n.math('FRACT', cb), 0.5)), lam_b / 24)
    cell_gap = n.math('MAXIMUM', n.math('GREATER_THAN', ca_f, lam_a / 12 - 0.0012),
                      n.math('GREATER_THAN', cb_f, lam_b / 48 - 0.0011))
    mid = n.math('LESS_THAN', n.math('ABSOLUTE', n.math('SUBTRACT', cb, 12.0)), 0.07)
    lam_out = n.math('MAXIMUM', n.math('MAXIMUM', n.math('LESS_THAN', ca, 0.0), n.math('GREATER_THAN', ca, 6.0)),
                     n.math('MAXIMUM', n.math('LESS_THAN', cb, 0.0), n.math('GREATER_THAN', cb, 24.0)))
    backsheet = n.math('MAXIMUM', n.math('MAXIMUM', cell_gap, mid), lam_out)
    # bus bars: 10 hair lines per cell (far below a pixel here: they only lift the cell tone slightly)
    bus = n.math('LESS_THAN', n.math('ABSOLUTE', n.math('SUBTRACT', n.math('FRACT', n.math('MULTIPLY', ca, 10.0)), 0.5)), 0.035)
    cell_id = n.math('ADD', n.math('ADD', n.math('MULTIPLY', n.math('FLOOR', ca), 7.0), n.math('MULTIPLY', n.math('FLOOR', cb), 131.0)),
                     n.math('ADD', n.math('MULTIPLY', ia, 977.0), n.math('MULTIPLY', ib, 5003.0)))
    crnd = n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D', inputs={'W': cell_id}).outputs['Value']
    mrnd = n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D',
                  inputs={'W': n.math('ADD', n.math('MULTIPLY', ia, 13.0), n.math('MULTIPLY', ib, 71.0))}).outputs['Value']
    cell = n.mix(crnd, (0.006, 0.009, 0.022, 1), (0.011, 0.016, 0.040, 1))          # blue-black silicon
    cell = n.mix(n.math('MULTIPLY', bus, 0.45), cell, (0.30, 0.31, 0.33, 1))
    lam = n.mix(backsheet, cell, (0.50, 0.51, 0.53, 1))
    # dust and water marks: a film over everything, thicker towards the lower frame of each module
    npos = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: tc.outputs['Object'], 'Scale': 1.0}).outputs[0]
    d1 = n.noise(npos, 2.2, 5, 0.6).outputs['Fac']
    d2 = n.noise(npos, 22.0, 4, 0.65).outputs['Fac']
    low = n.smooth(n.math('SUBTRACT', mb, gap / 2 + frame_w), 0.42, 0.0)     # b grows up-slope from the eave side?
    dust = n.math('ADD', n.math('MULTIPLY', n.smooth(d1, 0.35, 0.8), 0.10), n.math('MULTIPLY', low, n.math('ADD', 0.10, n.math('MULTIPLY', d2, 0.22))))
    dust = n.math('ADD', dust, n.math('MULTIPLY', mrnd, 0.03))
    lam = n.mix(dust, lam, (0.33, 0.29, 0.24, 1))
    glass_r = n.math('ADD', 0.035, n.math('MULTIPLY', dust, 0.55))
    glass = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': lam, 'Roughness': 0.45, 'Specular IOR Level': 0.0,
                                                       'Coat Weight': 1.0, 'Coat Roughness': glass_r, 'Coat IOR': 1.47,
                                                       'Coat Tint': (0.80, 0.88, 1.0, 1)})
    frame = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.72, 0.73, 0.75, 1), 'Metallic': 1.0,
                                                       'Roughness': n.math('ADD', 0.30, n.math('MULTIPLY', d2, 0.2))})
    gapb = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.02, 0.02, 0.02, 1), 'Roughness': 0.8})
    roofb = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.05, 0.05, 0.055, 1), 'Roughness': 0.7})
    # relief: frames stand 1.5 mm proud of the glass, gaps drop
    h = n.math('SUBTRACT', n.math('MULTIPLY', is_frame, 0.0015), n.math('MULTIPLY', is_gap, 0.03))
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 1.0, 'Height': h})
    for b_ in (glass, frame, gapb):
        n.link(bump.outputs[0], b_.inputs['Normal'])
    s1 = n.node('ShaderNodeMixShader', inputs={0: is_frame})
    n.link(glass.outputs[0], s1.inputs[1]); n.link(frame.outputs[0], s1.inputs[2])
    s2 = n.node('ShaderNodeMixShader', inputs={0: is_gap})
    n.link(s1.outputs[0], s2.inputs[1]); n.link(gapb.outputs[0], s2.inputs[2])
    s3 = n.node('ShaderNodeMixShader', inputs={0: inside})
    n.link(roofb.outputs[0], s3.inputs[1]); n.link(s2.outputs[0], s3.inputs[2])
    n.link(s3.outputs[0], out.inputs['Surface'])
    return m


def glass(names=('glass', 'glass_clear')):
    """Window glass that renders cleanly as single panes: Fresnel mirror over a clear, faintly green pane."""
    for name in names:
        if name not in bpy.data.materials:
            continue
        m, t = C.new_mat(name)
        n = NT(t)
        out = n.node('ShaderNodeOutputMaterial')
        fr = n.node('ShaderNodeFresnel', inputs={'IOR': 1.52})
        f = n.math('MINIMUM', n.math('ADD', n.math('MULTIPLY', fr.outputs[0], 1.9), 0.02), 1.0)   # two surfaces
        tr = n.node('ShaderNodeBsdfTransparent', inputs={'Color': (0.93, 0.965, 0.95, 1)})
        gl = n.node('ShaderNodeBsdfGlossy', inputs={'Color': (1, 1, 1, 1), 'Roughness': 0.0})
        mx = n.node('ShaderNodeMixShader', inputs={0: f})
        n.link(tr.outputs[0], mx.inputs[1]); n.link(gl.outputs[0], mx.inputs[2])
        n.link(mx.outputs[0], out.inputs['Surface'])
        m.diffuse_color = (0.6, 0.75, 0.8, 0.3)


def tune_simple():
    """Roughness and sheen for the imported flat materials that show from outside."""
    def bs(name):
        m = bpy.data.materials.get(name)
        if m and m.use_nodes:
            return next((x for x in m.node_tree.nodes if x.type == 'BSDF_PRINCIPLED'), None)
    for name in ('4', '3', '1', '10260', '[Wood Veneer 01]', 'Walnut Hue', 'wood_01'):       # interior timber
        b = bs(name)
        if b:
            b.inputs['Roughness'].default_value = 0.42
            b.inputs['Specular IOR Level'].default_value = 0.4
    b = bs('*14')                                                                         # boardwalk and deck boards
    if b:
        b.inputs['Roughness'].default_value = 0.72
    for name in ('[Color_008]', '_3'):                                                    # flue: blued steel
        b = bs(name)
        if b:
            b.inputs['Base Color'].default_value = (0.022, 0.021, 0.021, 1)
            for l in list(b.inputs['Base Color'].links):
                b.id_data.links.remove(l)
            b.inputs['Metallic'].default_value = 0.85
            b.inputs['Roughness'].default_value = 0.48


def interior_lights(power=1.0):
    """Warm light inside (2900 K): the cafe is open. Lamps only, no fixtures: the interior stays as modelled."""
    col = C.coll('MC_interior_light')
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    warm = (1.0, 0.63, 0.34)
    spots = [  # (u, v, z, watts, radius)
        (2.45, 2.45, 2.45, 240, 0.10),      # vestibule behind the entrance door
        (2.45, 0.85, 2.45, 160, 0.10),
        (2.40, 8.30, 2.55, 260, 0.12),      # room behind the gable window
        (2.40, 5.60, 2.55, 180, 0.12),
        (1.20, -1.60, 2.45, 120, 0.10),
        (1.50, -6.00, 2.60, 160, 0.12),
    ] + [(-3.3, v, 2.55, 200, 0.14) for v in (-8.0, -5.0, -2.0, 1.2, 4.4, 7.6)] + \
        [(-1.4, v, 2.55, 140, 0.12) for v in (-6.5, -0.4, 6.0)]
    for i, (u, v, z, w, r) in enumerate(spots):
        ld = bpy.data.lights.new('MC_in_%02d' % i, 'POINT')
        ld.energy = w * power
        ld.color = warm
        ld.shadow_soft_size = r
        o = bpy.data.objects.new(ld.name, ld)
        x, y = mc_site.to_world(u, v)
        o.location = (x, y, z)
        col.objects.link(o)
    return col


def apply():
    corten()
    solar()
    glass()
    tune_simple()
    interior_lights()
