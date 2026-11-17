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
    """Weathering steel from the Megascans 'Rusty Metal' scan (box-projected in the building's own axes, shifted per
    panel), mottled in three scales, with 'Wall Rust Leakage' decals running down from the panel seams, run-off
    streaks under the eaves and a darker splash zone at the foot."""
    import mc_fab
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
    shift = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: rnd.outputs['Color'], 'Scale': 7.0})
    vec = n.node('ShaderNodeVectorMath', operation='ADD', inputs={0: P, 1: shift.outputs[0]})
    vec = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: vec.outputs[0], 'Scale': 1.0 / 2.0})

    def tex(kind):
        nd = n.node('ShaderNodeTexImage', projection='BOX', projection_blend=0.15, inputs={'Vector': vec.outputs[0]})
        nd.image = mc_fab.image('rusty_metal', kind)
        return nd
    diff, rough, disp = tex('color'), tex('rough'), tex('disp')
    # --- mottling: no two panels alike, clouds within each panel
    n_l = n.noise(P, 0.55, 4, 0.55).outputs['Fac']               # metre-scale clouds
    n_m = n.noise(P, 4.5, 5, 0.6, dist=0.4).outputs['Fac']       # hand-sized blotches
    n_s = n.noise(P, 60.0, 4, 0.7).outputs['Fac']                # speckle
    col = n.node('ShaderNodeHueSaturation', inputs={
        'Hue': n.math('ADD', 0.497, n.math('ADD', n.math('MULTIPLY', n.math('SUBTRACT', rnd.outputs['Value'], 0.5), 0.022), n.math('MULTIPLY', n.math('SUBTRACT', n_l, 0.5), 0.03))),
        'Saturation': n.math('ADD', 0.90, n.math('MULTIPLY', n.math('SUBTRACT', n_l, 0.5), 0.36)),
        'Value': n.math('ADD', 0.66, n.math('ADD', n.math('MULTIPLY', n.math('SUBTRACT', n_l, 0.5), 0.60),
                                            n.math('MULTIPLY', n.math('SUBTRACT', rnd.outputs['Value'], 0.5), 0.34))),
        'Color': diff.outputs['Color']}).outputs[0]
    dark = (0.045, 0.024, 0.019, 1)             # deep red-brown, where the patina is oldest and wettest
    orange = (0.33, 0.135, 0.045, 1)            # fresh powdery orange
    n_b = n.noise(P, 1.7, 5, 0.62, dist=0.8).outputs['Fac']        # half-metre blotches: the patina never weathers evenly
    col = n.mix(n.math('MULTIPLY', n.smooth(n_b, 0.48, 0.70), 0.50), col, (0.070, 0.036, 0.030, 1))
    col = n.mix(n.math('MULTIPLY', n.smooth(n_m, 0.50, 0.78), 0.55), col, dark)
    col = n.mix(n.math('MULTIPLY', n.smooth(n_m, 0.44, 0.18), 0.30), col, orange)
    col = n.mix(n.math('MULTIPLY', n.smooth(n_s, 0.62, 0.85), 0.25), col, dark)
    # --- leakage decals: one scanned streak per seam on the walls, starting at the eave
    ztop = n.math('MINIMUM', n.math('ADD', 2.7, n.math('MULTIPLY', n.math('ADD', u, 6.9), 0.10294)),
                  n.math('SUBTRACT', 3.4, n.math('MULTIPLY', n.math('ADD', u, 0.1), 0.17647)))
    seam_id = n.math('ADD', n.mixf(gable, kv, n.math('ADD', ku, 57.0)), n.math('MULTIPLY', n.math('SIGN', n.mixf(gable, nu, nv)), 200.0))
    sr = n.node('ShaderNodeSeparateColor', inputs={0: n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D',
                                                             inputs={'W': n.math('ADD', seam_id, 0.37)}).outputs['Color']}).outputs
    d_signed = n.mixf(gable, n.math('SUBTRACT', v, n.math('ADD', SEAM_V0, n.math('MULTIPLY', kv, SEAM_VP))),
                      n.math('SUBTRACT', u, n.math('ADD', SEAM_U0, n.math('MULTIPLY', ku, SEAM_UP))))
    d_signed = n.math('MULTIPLY', d_signed, n.math('SIGN', n.math('SUBTRACT', sr[0], 0.5)))       # some are mirrored
    wd = n.math('ADD', 0.30, n.math('MULTIPLY', sr[1], 0.30))                                    # streak width, m
    ld = n.math('ADD', 1.4, n.math('MULTIPLY', sr[2], 1.5))                                      # streak length, m
    du_ = n.math('ADD', n.math('DIVIDE', d_signed, wd), 0.5)
    dvv = n.math('SUBTRACT', 1.0, n.math('DIVIDE', n.math('SUBTRACT', ztop, z), ld))
    duv = n.node('ShaderNodeCombineXYZ', inputs={0: du_, 1: dvv, 2: 0.0})
    leak_col, leak_a = None, None
    for i, key in enumerate(('leak_a', 'leak_b')):
        nd = n.node('ShaderNodeTexImage', extension='CLIP', inputs={'Vector': duv.outputs[0]})
        nd.image = mc_fab.image(key, 'color_alpha')
        if leak_col is None:
            leak_col, leak_a = nd.outputs['Color'], nd.outputs['Alpha']
        else:
            pick = n.math('GREATER_THAN', n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D',
                                                 inputs={'W': n.math('ADD', seam_id, 9.1)}).outputs['Value'], 0.5)
            leak_col = n.mix(pick, leak_col, nd.outputs['Color'])
            leak_a = n.mixf(pick, leak_a, nd.outputs['Alpha'])
    walls = n.math('SUBTRACT', 1.0, roof)
    has_leak = n.math('GREATER_THAN', n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D',
                                             inputs={'W': n.math('ADD', seam_id, 3.3)}).outputs['Value'], 0.22)   # most seams leak
    la = n.math('MULTIPLY', n.math('MULTIPLY', leak_a, walls), has_leak)
    # old run-off is a dark stain, fresh run-off a bright orange one
    fresh = n.math('GREATER_THAN', n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D', inputs={'W': n.math('ADD', seam_id, 5.7)}).outputs['Value'], 0.55)
    leak_tone = n.mix(fresh, n.mix(1.0, leak_col, (0.20, 0.15, 0.13, 1), 'MULTIPLY'), n.mix(1.0, leak_col, (0.95, 0.62, 0.36, 1), 'MULTIPLY'))
    col = n.mix(n.math('MINIMUM', n.math('MULTIPLY', la, 1.15), 0.92), col, leak_tone)
    # --- faint run-off streaks under the eaves between the seams, and down the fall of the roof
    sv_wall = n.node('ShaderNodeCombineXYZ', inputs={0: n.math('MULTIPLY', u, 26.0), 1: n.math('MULTIPLY', v, 26.0),
                                                     2: n.math('MULTIPLY', z, 0.55)})
    sv_roof = n.node('ShaderNodeCombineXYZ', inputs={0: n.math('MULTIPLY', u, 0.5), 1: n.math('MULTIPLY', v, 22.0), 2: 0.0})
    sv = n.node('ShaderNodeMix', data_type='VECTOR', inputs={0: roof})
    n.link(sv_wall.outputs[0], sv.inputs[4])
    n.link(sv_roof.outputs[0], sv.inputs[5])
    st = n.noise(sv.outputs[1], 1.0, 4, 0.6).outputs['Fac']
    st2 = n.noise(sv.outputs[1], 0.23, 3, 0.5).outputs['Fac']
    streak = n.math('MULTIPLY', n.smooth(st, 0.60, 0.80), n.smooth(st2, 0.42, 0.70))
    top = n.smooth(z, 1.0, 2.75)
    sw = n.math('MULTIPLY', streak, n.mixf(roof, n.math('MULTIPLY', n.smooth(z, 1.7, 2.75), 0.40), 0.05))
    col = n.mix(n.math('MINIMUM', n.math('MULTIPLY', sw, 0.5), 0.35), col, dark)
    bleed = n.math('MULTIPLY', n.smooth(d_seam, 0.035, 0.004), n.smooth(n_m, 0.3, 0.6))
    col = n.mix(n.math('MULTIPLY', bleed, 0.3), col, orange)
    # splash zone at the foot of the walls: darker, dusty
    foot = n.math('MULTIPLY', n.smooth(z, 0.45, 0.02), walls)
    foot = n.math('MULTIPLY', foot, n.math('ADD', 0.45, n.math('MULTIPLY', n_m, 0.7)))
    col = n.mix(n.math('MULTIPLY', foot, 0.6), col, (0.060, 0.042, 0.033, 1))
    # dust settles on the low-pitched roof: a little paler and flatter
    col = n.mix(n.math('MULTIPLY', roof, n.math('MULTIPLY', n.smooth(n_l, 0.3, 0.8), 0.22)), col, (0.24, 0.17, 0.125, 1))
    r = n.math('ADD', n.math('MULTIPLY', rough.outputs['Color'], 0.25), 0.72)
    r = n.math('MINIMUM', n.math('ADD', r, n.math('MULTIPLY', la, 0.05)), 1.0)
    bump = n.node('ShaderNodeBump', inputs={'Strength': 0.35, 'Distance': 0.004, 'Height': disp.outputs['Color']})
    bump2 = n.node('ShaderNodeBump', inputs={'Strength': 0.25, 'Distance': 0.0015, 'Height': n_s, 'Normal': bump.outputs[0]})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': r, 'Metallic': 0.0,
                                                      'Specular IOR Level': 0.12, 'Normal': bump2.outputs[0]})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


def planks(obj='_(Loose Entity)', name='MC_planks'):
    """Boardwalk: Megascans 'Worn Wooden Planks', boards laid across the walk (the mesh is not changed)."""
    import mc_fab
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    P, (u, v, z), Nl, _ = local_coords(n)
    mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': P, 'Scale': (0.5, 0.5, 0.5), 'Location': (0.13, 0.31, 0.0)})

    def tex(kind):
        nd = n.node('ShaderNodeTexImage', projection='BOX', projection_blend=0.05, inputs={'Vector': mp.outputs[0]})
        nd.image = mc_fab.image('planks', kind)
        return nd
    diff, rough, disp = tex('color'), tex('rough'), tex('disp')
    big = n.noise(P, 1.3, 3, 0.5).outputs['Fac']
    col = n.node('ShaderNodeHueSaturation', inputs={'Saturation': 0.75, 'Value': n.math('ADD', 0.62, n.math('MULTIPLY', big, 0.3)),
                                                    'Color': diff.outputs['Color']}).outputs[0]
    col = n.mix(0.25, col, (0.16, 0.155, 0.15, 1))                                        # silvered by the weather
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 0.03, 'Height': disp.outputs['Color']})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': n.math('ADD', n.math('MULTIPLY', rough.outputs['Color'], 0.4), 0.55),
                                                      'Normal': bump.outputs[0], 'Specular IOR Level': 0.25})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    o = bpy.data.objects.get(obj)
    if o is not None:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = m
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
    gap = 0.022
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
    frame_w = 0.030                               # anodised frame (drawn a little wide: it must survive 2 cm pixels)
    is_frame = n.math('MULTIPLY', n.math('GREATER_THAN', em, 0.0), n.math('LESS_THAN', em, frame_w))
    # cells: 6 across, 24 half-cells down, 2.2 mm gaps, a wider gap at mid height
    lam_a, lam_b = wa - 2 * frame_w - 0.016, wb - 2 * frame_w - 0.020
    ca = n.math('DIVIDE', n.math('SUBTRACT', ma, gap / 2 + frame_w + 0.008), lam_a / 6)
    cb = n.math('DIVIDE', n.math('SUBTRACT', mb, gap / 2 + frame_w + 0.010), lam_b / 24)
    ca_f = n.math('MULTIPLY', n.math('ABSOLUTE', n.math('SUBTRACT', n.math('FRACT', ca), 0.5)), lam_a / 6)
    cb_f = n.math('MULTIPLY', n.math('ABSOLUTE', n.math('SUBTRACT', n.math('FRACT', cb), 0.5)), lam_b / 24)
    cell_gap = n.math('MAXIMUM', n.math('GREATER_THAN', ca_f, lam_a / 12 - 0.0045),
                      n.math('GREATER_THAN', cb_f, lam_b / 48 - 0.0035))        # the white grid between the cells
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
    cell = n.mix(crnd, (0.004, 0.006, 0.013, 1), (0.008, 0.011, 0.026, 1))          # blue-black monocrystalline silicon
    cell = n.mix(n.math('MULTIPLY', bus, 0.45), cell, (0.30, 0.31, 0.33, 1))
    lam = n.mix(backsheet, cell, (0.62, 0.63, 0.65, 1))
    # dust and water marks: a film over everything, thicker towards the lower frame of each module
    npos = n.node('ShaderNodeVectorMath', operation='SCALE', inputs={0: tc.outputs['Object'], 'Scale': 1.0}).outputs[0]
    d1 = n.noise(npos, 2.2, 5, 0.6).outputs['Fac']
    d2 = n.noise(npos, 22.0, 4, 0.65).outputs['Fac']
    low = n.smooth(n.math('SUBTRACT', mb, gap / 2 + frame_w), 0.42, 0.0)     # b grows up-slope from the eave side?
    dust = n.math('ADD', n.math('MULTIPLY', n.smooth(d1, 0.35, 0.8), 0.10), n.math('MULTIPLY', low, n.math('ADD', 0.10, n.math('MULTIPLY', d2, 0.22))))
    dust = n.math('ADD', dust, n.math('MULTIPLY', mrnd, 0.03))
    lam = n.mix(dust, lam, (0.33, 0.29, 0.24, 1))
    glass_r = n.math('ADD', 0.20, n.math('MULTIPLY', dust, 0.45))      # textured, anti-reflection solar glass: no mirror
    glass = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': lam, 'Roughness': 0.45, 'Specular IOR Level': 0.0,
                                                       'Coat Weight': 0.5, 'Coat Roughness': glass_r, 'Coat IOR': 1.25,
                                                       'Coat Tint': (0.80, 0.88, 1.0, 1)})
    frame = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': (0.80, 0.81, 0.83, 1), 'Metallic': 0.85,
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


def door_frame(name='Door frame (added)'):
    """A real door frame for the entrance in the east wall (opening v 1.708..3.208, z 0.2..2.4 in a 150 mm wall whose
    outer skin showed as a sheet): a welded steel surround, 100 mm wide and 216 mm deep, standing 60 mm proud of the
    corten, with its lining just inside the reveal, a drip over the head and a sill plate on the boardwalk.
    Added geometry only: no existing mesh of the building is edited. Parented to the building."""
    V0, V1, Z0, Z1 = 1.708, 3.208, 0.200, 2.400              # the opening
    U_IN, U_OUT = 3.141, 3.357                               # through the wall, proud of the skin (3.297)
    W = 0.100                                                # face width of the surround
    T = 0.006                                                # how far the lining stands inside the reveal
    boxes = [  # (u0, u1, v0, v1, z0, z1)
        (U_IN, U_OUT, V0 - W, V0 + T, 0.0, Z1 + W),          # south jamb, down to the slab
        (U_IN, U_OUT, V1 - T, V1 + W, 0.0, Z1 + W),          # north jamb
        (U_IN, U_OUT, V0 + T, V1 - T, Z1 - T, Z1 + W),       # head
        (U_OUT - 0.004, U_OUT + 0.022, V0 - W - 0.012, V1 + W + 0.012, Z1 + W, Z1 + W + 0.012),   # drip over the head
        (U_IN, U_OUT + 0.03, V0 + T, V1 - T, Z0 - 0.004, Z0 + 0.012),                             # sill plate
    ]
    verts, faces = [], []
    for (u0, u1, v0, v1, z0, z1) in boxes:
        b = len(verts)
        for u in (u0, u1):
            for v in (v0, v1):
                for z in (z0, z1):
                    x, y = mc_site.to_world(u, v)
                    verts.append((x, y, z))
        faces += [(b, b + 1, b + 3, b + 2), (b + 4, b + 6, b + 7, b + 5), (b, b + 4, b + 5, b + 1), (b + 2, b + 3, b + 7, b + 6),
                  (b, b + 2, b + 6, b + 4), (b + 1, b + 5, b + 7, b + 3)]
    old = bpy.data.objects.get(name)
    if old is not None:
        d = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    root = bpy.data.objects[C.BUILDING]
    (root.users_collection[0] if root.users_collection else bpy.context.scene.collection).objects.link(o)
    o.parent = root
    o.matrix_parent_inverse = root.matrix_world.inverted()
    bv = o.modifiers.new('arris', 'BEVEL')                   # a 2 mm arris so the edges catch the light
    bv.width = 0.002
    bv.segments = 2
    bv.limit_method = 'ANGLE'
    # blackened, oiled steel that has begun to rust at the edges: darker and smoother than the cladding
    m, t = C.new_mat('MC_door_frame')
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    geo = n.node('ShaderNodeNewGeometry')
    P = geo.outputs['Position']
    n1 = n.noise(P, 9.0, 4, 0.6).outputs['Fac']
    n2 = n.noise(P, 70.0, 4, 0.7).outputs['Fac']
    col = n.mix(n.smooth(n1, 0.45, 0.75), (0.038, 0.030, 0.026, 1), (0.075, 0.042, 0.028, 1))
    edge = n.node('ShaderNodeNewGeometry').outputs['Pointiness']
    col = n.mix(n.math('MULTIPLY', n.smooth(edge, 0.52, 0.60), 0.6), col, (0.16, 0.075, 0.035, 1))       # rust on the arrises
    bump = n.node('ShaderNodeBump', inputs={'Strength': 0.3, 'Distance': 0.001, 'Height': n2})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Metallic': 0.6, 'Normal': bump.outputs[0],
                                                      'Roughness': n.math('ADD', 0.52, n.math('MULTIPLY', n2, 0.2))})
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    me.materials.append(m)
    return o


def plinth(name='[Color C04]'):
    """The stone base of the model keeps its own stone texture; its tone is brought down to the local rock and the
    dry-stone wall beside it (the image is a pale stock texture), and it loses its plastic sheen."""
    m = bpy.data.materials.get(name)
    if m is None or not m.use_nodes:
        return
    t = m.node_tree
    bs = next((x for x in t.nodes if x.type == 'BSDF_PRINCIPLED'), None)
    if bs is None or not bs.inputs['Base Color'].is_linked:
        return
    src = bs.inputs['Base Color'].links[0].from_socket
    if src.node.name == 'MC_plinth_hsv':
        return
    hs = t.nodes.new('ShaderNodeHueSaturation')
    hs.name = 'MC_plinth_hsv'
    hs.inputs['Saturation'].default_value = 0.7
    hs.inputs['Value'].default_value = 0.42
    t.links.new(src, hs.inputs['Color'])
    t.links.new(hs.outputs[0], bs.inputs['Base Color'])
    bs.inputs['Roughness'].default_value = 0.9
    bs.inputs['Specular IOR Level'].default_value = 0.25


def apply():
    corten()
    door_frame()
    plinth()
    planks()
    solar()
    glass()
    tune_simple()
    interior_lights()
