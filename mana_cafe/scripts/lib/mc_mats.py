"""Materials for the landscape: aerial perspective group and the mountain surface."""
import bpy, math
import mc_core as C
from mc_core import NT

# sky radiance near the horizon in the view direction, measured in the HDRI (waterkloof_farm, 1-6 deg above the
# horizon, 95-110 deg from the sun), before the world's own grading
AIR_COLOR = (0.235, 0.385, 0.545)
CAM_Z = 11.76


def aerial_group(name='MC_aerial'):
    """Shader in -> shader out with air between the camera and the surface.
    L = L_surface * T + A * (1 - T_c),  T_c = exp(-beta_c * d * f(dz)); f makes the air thinner upwards (scale
    height H) so that valleys haze more than summits."""
    g = bpy.data.node_groups.get(name)
    if g is None:
        g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        g.interface.new_socket('Shader', in_out='INPUT', socket_type='NodeSocketShader')
        g.interface.new_socket('Density', in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
        g.interface.new_socket('Air', in_out='INPUT', socket_type='NodeSocketColor').default_value = AIR_COLOR + (1,)
        g.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    g.nodes.clear()
    n = NT(g)
    gi = n.node('NodeGroupInput')
    go = n.node('NodeGroupOutput')
    cam = n.node('ShaderNodeCameraData')
    geo = n.node('ShaderNodeNewGeometry')
    d = cam.outputs['View Distance']
    z = n.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Position']}).outputs['Z']
    H = 2600.0
    x = n.math('DIVIDE', n.math('SUBTRACT', z, CAM_Z), H)                 # dz / H
    # f = (1 - exp(-x)) / x, with the limit 1 at x -> 0
    ax = n.math('ABSOLUTE', x)
    xs = n.math('MAXIMUM', ax, 1e-3)
    sgn = n.math('SIGN', x)
    xx = n.math('MULTIPLY', xs, n.math('ADD', sgn, n.math('LESS_THAN', ax, 1e-9)))   # x with |x| >= 1e-3
    f = n.math('DIVIDE', n.math('SUBTRACT', 1.0, n.math('EXPONENT', n.math('MULTIPLY', xx, -1.0))), xx)
    f = n.math('MINIMUM', n.math('MAXIMUM', f, 0.3), 2.5)
    tau = n.math('MULTIPLY', n.math('MULTIPLY', d, f), gi.outputs['Density'])
    # extinction per metre (R, G, B): clean thin air, a little bluer than pure aerosol
    beta = (1.05e-5, 1.75e-5, 2.9e-5)
    T = [n.math('EXPONENT', n.math('MULTIPLY', tau, -b)) for b in beta]
    Tavg = n.math('DIVIDE', n.math('ADD', n.math('ADD', T[0], T[1]), T[2]), 3.0)
    one_m = n.math('MAXIMUM', n.math('SUBTRACT', 1.0, Tavg), 1e-5)
    comb = n.node('ShaderNodeCombineColor', inputs={0: n.math('DIVIDE', n.math('SUBTRACT', 1.0, T[0]), one_m),
                                                    1: n.math('DIVIDE', n.math('SUBTRACT', 1.0, T[1]), one_m),
                                                    2: n.math('DIVIDE', n.math('SUBTRACT', 1.0, T[2]), one_m)})
    col = n.mix(1.0, comb.outputs[0], gi.outputs['Air'], 'MULTIPLY')
    em = n.node('ShaderNodeEmission', inputs={'Color': col, 'Strength': 1.0})
    # only camera rays see the veil (it must not light the scene)
    lp = n.node('ShaderNodeLightPath')
    fac = n.math('MULTIPLY', n.math('SUBTRACT', 1.0, Tavg), lp.outputs['Is Camera Ray'])
    mx = n.node('ShaderNodeMixShader', inputs={0: fac})
    n.link(gi.outputs['Shader'], mx.inputs[1])
    n.link(em.outputs[0], mx.inputs[2])
    n.link(mx.outputs[0], go.inputs['Shader'])
    return g


def no_light(m):
    """The air veil is an emission closure: keep these surfaces out of the light tree (20 M triangles would cost
    gigabytes there and add noise)."""
    m.cycles.emission_sampling = 'NONE'


def add_aerial(n, shader_socket, density=1.0):
    grp = n.node('ShaderNodeGroup')
    grp.node_tree = aerial_group()
    grp.inputs['Density'].default_value = density
    n.link(shader_socket, grp.inputs['Shader'])
    return grp.outputs['Shader']


def mountain_material(name='MC_mountain', P=None, near=False):
    """Snow, ice, rock, scree, alpine meadow, shrub and forest floor from the terrain attributes written by
    scripts/proc (alt = height above the cafe floor at 4396 m, slope = tan, north = north component of the normal,
    curv > 0 on crests, flow = log10 of the drainage area, rocky 0..1)."""
    p = dict(snow_line=185.0, snow_range=200.0, aspect=215.0, haze=1.25)
    p.update(P or {})
    m, t = C.new_mat(name)
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    A = lambda k: n.attr(k).outputs['Fac']
    alt, slope, north, curv, flow, rocky = A('alt'), A('slope'), A('north'), A('curv'), A('flow'), A('rocky')
    geo = n.node('ShaderNodeNewGeometry')
    pos = geo.outputs['Position']
    N = lambda s, d=5.0, r=0.6, dist=0.0: n.noise(pos, 1.0 / s, d, r, dist=dist).outputs['Fac']
    n_xl, n_big, n_mid, n_fine, n_tiny = N(2600.0, 4), N(700.0, 5), N(110.0, 6, 0.62), N(17.0, 6, 0.65), N(2.2, 5, 0.7)
    n_mid2 = n.noise(pos, 1.0 / 60.0, 5, 0.6, dist=0.6, dims='4D', w=3.1).outputs['Fac']
    c = lambda x: n.math('SUBTRACT', x, 0.5)

    # ---------------- snow cover: where fresh snow lies after the first autumn storms
    # effective altitude: shaded (north) slopes hold it lower, sunny ones lose it higher up
    eff = n.math('ADD', alt, n.math('MULTIPLY', north, p['aspect']))
    eff = n.math('SUBTRACT', eff, n.math('MULTIPLY', n.math('SUBTRACT', 1.0, A('wfar')), 300.0))   # the ridge by the cafe is still bare
    s = n.math('DIVIDE', n.math('SUBTRACT', eff, p['snow_line']), p['snow_range'])
    hollow = n.math('MULTIPLY', n.math('MAXIMUM', n.math('MINIMUM', n.math('MULTIPLY', curv, -0.30), 1.0), -1.0), 1.5)
    s = n.math('ADD', s, hollow)                                              # gullies and hollows fill, crests blow bare
    s = n.math('ADD', s, n.math('MULTIPLY', n.math('MINIMUM', n.math('SUBTRACT', flow, 2.4), 2.0), 0.22))
    # rock bands: the massif is built of dipping strata; on steep ground the risers of the beds are bare rock and
    # the ledges hold snow. Couloirs (fall-line chutes) stay filled and cut through the bands.
    xyz = n.node('ShaderNodeSeparateXYZ', inputs={0: pos}).outputs
    sc_ = n.math('ADD', n.math('ADD', xyz[2], n.math('MULTIPLY', xyz[0], 0.20)), n.math('MULTIPLY', xyz[1], 0.11))
    sc_ = n.math('ADD', sc_, n.math('ADD', n.math('MULTIPLY', n_mid, 46.0), n.math('MULTIPLY', n_big, 150.0)))

    def beds(spacing, lo, hi):
        f = n.math('FRACT', n.math('DIVIDE', sc_, spacing))
        return n.math('MULTIPLY', n.smooth(f, lo, lo + 0.10), n.smooth(f, 1.0, hi))
    broken = n.smooth(n_mid2, 0.30, 0.52)                                       # the bands are not continuous
    band = n.math('MAXIMUM', n.math('MULTIPLY', beds(47.0, 0.50, 0.88), broken),
                  n.math('MULTIPLY', beds(15.0, 0.52, 0.86), n.math('MULTIPLY', n.smooth(n_fine, 0.38, 0.58), 0.75)))
    vst = n.noise(n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': pos, 'Scale': (1 / 11.0, 1 / 11.0, 1 / 260.0)}).outputs[0], 1.0, 4, 0.62).outputs['Fac']
    couloir = n.smooth(vst, 0.50, 0.66)
    steep = n.smooth(n.math('ADD', slope, n.math('MULTIPLY', c(n_fine), 0.35)), 0.62, 1.25)
    s = n.math('SUBTRACT', s, n.math('MULTIPLY', steep, n.math('ADD', 0.35, n.math('MULTIPLY', band, 2.6))))
    s = n.math('ADD', s, n.math('MULTIPLY', n.math('MULTIPLY', steep, couloir), 1.15))
    s = n.math('SUBTRACT', s, n.math('MULTIPLY', n.smooth(slope, 1.5, 2.4), 1.2))          # walls hold nothing
    s = n.math('ADD', s, n.math('MULTIPLY', c(n_big), 0.28))
    s = n.math('ADD', s, n.math('MULTIPLY', c(n_xl), 0.30))
    firn = n.smooth(alt, 560.0, 900.0)                                       # permanent snow and glaciers
    s = n.math('ADD', s, n.math('MULTIPLY', firn, n.mixf(n.smooth(slope, 1.3, 2.1), 1.9, 0.3)))
    cover = n.smooth(s, -0.35, 0.45)
    # patchy at the edge: a fine threshold instead of a grey blend
    dith = n.math('ADD', n.math('MULTIPLY', n_fine, 0.5), n.math('ADD', n.math('MULTIPLY', n_mid2, 0.2), n.math('MULTIPLY', n_tiny, 0.3)))
    snow = n.smooth(n.math('SUBTRACT', cover, dith), -0.07, 0.07)
    snow = n.math('MAXIMUM', snow, n.smooth(cover, 0.82, 0.97))

    # ---------------- ground under the snow
    # rock: grey to brown, banded by the dipping strata, lichen and weathering variation
    strata_c = n.math('ADD', n.math('ADD', n.node('ShaderNodeSeparateXYZ', inputs={0: pos}).outputs['Z'],
                                    n.math('MULTIPLY', n_mid, 60.0)), n.math('MULTIPLY', n_big, 240.0))
    bn = n.node('ShaderNodeTexNoise', noise_dimensions='1D', inputs={'W': n.math('DIVIDE', strata_c, 46.0),
                                                                     'Scale': 1.0, 'Detail': 3.0, 'Roughness': 0.6})
    rock_tone = n.ramp(bn.outputs['Fac'], [(0.25, (0.066, 0.064, 0.063, 1)), (0.45, (0.115, 0.110, 0.104, 1)),
                                           (0.62, (0.165, 0.150, 0.135, 1)), (0.8, (0.225, 0.215, 0.20, 1))])
    rock_var = n.ramp(n_fine, [(0.2, (0.72, 0.70, 0.68, 1)), (0.8, (1.22, 1.2, 1.17, 1))])
    rock = n.mix(1.0, rock_tone, rock_var, 'MULTIPLY')
    # water and rockfall streaks down the steep faces
    rock = n.mix(n.math('MULTIPLY', n.smooth(slope, 1.0, 1.6), n.math('MULTIPLY', n.smooth(vst, 0.5, 0.75), 0.55)), rock, (0.045, 0.043, 0.042, 1))
    warm = n.smooth(n_big, 0.45, 0.75)                                        # iron-stained zones
    rock = n.mix(n.math('MULTIPLY', warm, 0.35), rock, (0.19, 0.135, 0.095, 1))
    rock = n.mix(n.math('MULTIPLY', n.smooth(alt, 300.0, 800.0), 0.5), rock, (0.035, 0.033, 0.032, 1))     # dark summit rock
    rock = n.mix(n.math('MULTIPLY', band, 0.45), rock, (0.030, 0.029, 0.030, 1))                          # overhung risers
    scree = n.ramp(n_tiny, [(0.2, (0.15, 0.142, 0.132, 1)), (0.8, (0.265, 0.25, 0.23, 1))])
    # meadow: dry gold with greener hollows and red-brown dwarf shrub patches
    meadow = n.ramp(n_mid, [(0.2, (0.19, 0.142, 0.060, 1)), (0.45, (0.30, 0.225, 0.092, 1)), (0.7, (0.37, 0.285, 0.125, 1)),
                            (0.9, (0.24, 0.20, 0.082, 1))])
    green = n.math('MULTIPLY', n.smooth(n.math('ADD', n.math('MULTIPLY', curv, -0.1), n_fine), 0.45, 0.8), 0.32)
    meadow = n.mix(green, meadow, (0.095, 0.11, 0.048, 1))
    meadow = n.mix(1.0, meadow, n.ramp(n_tiny, [(0.2, (0.8, 0.8, 0.8, 1)), (0.8, (1.18, 1.18, 1.18, 1))]), 'MULTIPLY')
    shrub = n.ramp(n_fine, [(0.25, (0.030, 0.040, 0.020, 1)), (0.6, (0.062, 0.072, 0.032, 1)), (0.85, (0.115, 0.07, 0.04, 1))])
    forest = n.ramp(n_fine, [(0.3, (0.012, 0.022, 0.013, 1)), (0.7, (0.032, 0.048, 0.024, 1))])
    oak = n.ramp(n_fine, [(0.3, (0.062, 0.055, 0.030, 1)), (0.6, (0.115, 0.095, 0.050, 1)), (0.85, (0.165, 0.135, 0.072, 1))])   # sunny-side scrub
    earth = (0.19, 0.135, 0.085, 1)

    # belts (heights relative to the cafe: tree line about -150 m = 4250 m, shrubs to +120 m, meadow to +420 m)
    a2 = n.math('ADD', alt, n.math('MULTIPLY', c(n_mid), 150.0))
    a2 = n.math('ADD', a2, n.math('MULTIPLY', c(n_big), 160.0))
    a2n = n.math('ADD', a2, n.math('MULTIPLY', north, -120.0))                # belts reach higher on sunny slopes
    f_forest = n.math('MULTIPLY', n.smooth(a2n, -110.0, -230.0), n.smooth(slope, 1.25, 0.8))
    f_dark = n.smooth(north, -0.25, 0.2)                                      # fir on shaded faces, oak scrub on sunny
    f_shrub = n.math('MULTIPLY', n.math('MULTIPLY', n.smooth(a2n, 150.0, -40.0), n.smooth(slope, 1.15, 0.7)),
                     n.smooth(n.math('ADD', n_mid2, n.math('MULTIPLY', north, 0.25)), 0.35, 0.6))
    f_rock = n.math('MAXIMUM', n.smooth(n.math('ADD', slope, n.math('MULTIPLY', c(n_mid), 0.3)), 1.0, 1.38), n.smooth(a2, 430.0, 640.0))
    f_rock = n.math('MAXIMUM', f_rock, n.smooth(n.math('ADD', rocky, n.math('MULTIPLY', c(n_fine), 0.5)), 0.66, 0.9))
    f_scree = n.math('MULTIPLY', n.smooth(slope, 0.62, 0.9), n.smooth(n.math('ADD', n_mid, n.math('MULTIPLY', rocky, 0.6)), 0.52, 0.74))
    f_scree = n.math('MULTIPLY', f_scree, n.smooth(a2, -40.0, 240.0))
    chute = n.math('MULTIPLY', n.smooth(flow, 3.1, 3.8), n.smooth(slope, 0.55, 0.85))      # debris chutes in the gullies
    f_scree = n.math('MAXIMUM', f_scree, n.math('MULTIPLY', chute, n.smooth(a2, -150.0, 150.0)))
    f_earth = n.math('MULTIPLY', n.smooth(n.math('ADD', n.math('MULTIPLY', flow, 0.22), n.math('MULTIPLY', n_fine, 0.6)), 1.0, 1.2), 0.6)

    g = n.mix(f_earth, meadow, earth)
    # gullies hold shrubs (dark dendritic lines), crests are dry and stony
    f_gully = n.math('MULTIPLY', n.smooth(n.math('ADD', flow, n.math('MULTIPLY', n.math('MULTIPLY', curv, -1.0), 0.12)), 2.9, 3.7), n.smooth(a2, 420.0, 180.0))
    f_crest = n.math('MULTIPLY', n.smooth(curv, 1.2, 4.5), 0.55)
    g = n.mix(f_crest, g, n.mix(n_tiny, (0.27, 0.235, 0.15, 1), (0.36, 0.33, 0.27, 1)))
    g = n.mix(n.math('MAXIMUM', f_shrub, n.math('MULTIPLY', f_gully, 0.8)), g, shrub)
    vor = n.node('ShaderNodeTexVoronoi', feature='F1', inputs={'Vector': pos, 'Scale': 1.0 / 6.5, 'Randomness': 1.0})
    dots = n.math('MULTIPLY', n.smooth(vor.outputs['Distance'], 0.34, 0.14),
                  n.smooth(n.math('ADD', n_mid2, n.math('MULTIPLY', c(n_fine), 0.6)), 0.42, 0.62))
    g = n.mix(n.math('MULTIPLY', dots, 0.7), g, (0.035, 0.040, 0.022, 1))                         # shrub clumps
    g = n.mix(f_forest, g, n.mix(f_dark, oak, forest))
    g = n.mix(f_scree, g, scree)
    g = n.mix(f_rock, g, rock)

    near_bump = None
    if near:
        # close to the cafe: scanned soil under the grass scatter, bare patches, and the gravel track
        import mc_building
        cam = n.node('ShaderNodeCameraData')
        nearw = n.smooth(cam.outputs['View Distance'], 300.0, 80.0)

        def flat(asset, tile, rot=0.0, kind='diff', res='2k'):
            mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': pos, 'Rotation': (0, 0, rot),
                                                                         'Scale': (1.0 / tile,) * 3})
            nd = n.node('ShaderNodeTexImage', inputs={'Vector': mp.outputs[0]})
            nd.image = mc_building.img(asset, kind, res)
            return nd.outputs['Color']
        soil_a = flat('rocks_ground_02', 3.1, 0.4)
        soil_b = flat('brown_mud_rocks_01', 4.7, 1.9)
        soil = n.mix(n.smooth(n_fine, 0.35, 0.65), soil_a, soil_b)
        lum = n.node('ShaderNodeRGBToBW', inputs={0: soil}).outputs[0]
        thatch = n.mix(1.0, meadow, n.node('ShaderNodeCombineColor', inputs={
            0: n.math('ADD', 0.42, n.math('MULTIPLY', lum, 1.7)), 1: n.math('ADD', 0.42, n.math('MULTIPLY', lum, 1.7)),
            2: n.math('ADD', 0.42, n.math('MULTIPLY', lum, 1.6))}).outputs[0], 'MULTIPLY')
        bare = n.smooth(n.math('ADD', n_mid2, n.math('MULTIPLY', slope, 0.25)), 0.60, 0.72)
        soil_t = n.mix(1.0, soil, (0.80, 0.68, 0.54, 1), 'MULTIPLY')
        near_col = n.mix(bare, thatch, soil_t)
        g = n.mix(n.math('MULTIPLY', nearw, n.math('SUBTRACT', 1.0, f_rock)), g, near_col)
        trk = A('track')
        gravel = flat('rocky_trail', 3.6, 0.9, res='4k')
        gravel = n.mix(1.0, gravel, n.ramp(n_fine, [(0.3, (0.78, 0.76, 0.72, 1)), (0.7, (1.08, 1.04, 1.0, 1))]), 'MULTIPLY')
        tmask = n.smooth(n.math('ADD', trk, n.math('MULTIPLY', c(n_tiny), 0.5)), 0.35, 0.65)
        g = n.mix(tmask, g, gravel)
        gl = n.node('ShaderNodeRGBToBW', inputs={0: gravel}).outputs[0]
        near_bump = n.math('MULTIPLY', nearw, n.math('ADD', n.math('MULTIPLY', lum, 0.05), n.math('MULTIPLY', n.math('MULTIPLY', tmask, gl), 0.04)))

    # ---------------- snow surface: clean, a little blue ice where the glaciers break up
    ice = n.math('MULTIPLY', n.math('MULTIPLY', firn, n.smooth(slope, 0.55, 1.1)), n.smooth(n_mid2, 0.55, 0.8))
    snow_col = n.mix(n.math('MULTIPLY', ice, 0.55), (0.90, 0.905, 0.91, 1), (0.60, 0.74, 0.82, 1))
    dirty = n.math('MULTIPLY', n.math('SUBTRACT', 1.0, cover), 0.25)          # thin snow lets the ground tint through
    snow_col = n.mix(dirty, snow_col, g)
    col = n.mix(snow, g, snow_col)
    rough = n.mixf(snow, n.mixf(f_rock, 0.9, 0.72), 0.42)

    # ---------------- relief below the mesh resolution
    b_rock = n.math('ADD', n.math('ADD', n.math('MULTIPLY', n_fine, 4.5), n.math('MULTIPLY', n_tiny, 0.9)), n.math('MULTIPLY', band, 5.0))
    sastr = n.noise(n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': pos, 'Rotation': (0, 0, 0.6), 'Scale': (1 / 9.0, 1 / 55.0, 1 / 20.0)}).outputs[0], 1.0, 4, 0.6).outputs['Fac']
    b_snow = n.math('ADD', n.math('ADD', n.math('MULTIPLY', n_fine, 2.4), n.math('MULTIPLY', n_mid, 5.0)), n.math('MULTIPLY', sastr, 1.6))   # drifts and wind crust
    b_veg = n.math('ADD', n.math('ADD', n.math('MULTIPLY', n_fine, 2.6), n.math('MULTIPLY', n_tiny, 0.7)), n.math('MULTIPLY', n_mid, 7.0))
    bh = n.mixf(f_rock, b_veg, b_rock)
    bh = n.mixf(snow, bh, n.math('ADD', b_snow, n.math('MULTIPLY', n.math('MULTIPLY', steep, vst), 9.0)))     # flutings
    if near_bump is not None:
        bh = n.math('ADD', n.math('MULTIPLY', bh, n.math('SUBTRACT', 1.0, n.math('MULTIPLY', nearw, 0.8))), near_bump)
    bump = n.node('ShaderNodeBump', inputs={'Strength': 1.0, 'Distance': 1.0, 'Height': bh})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': rough,
                                                      'Normal': bump.outputs[0],
                                                      'Specular IOR Level': n.mixf(snow, 0.15, 0.35)})
    # snow scatters light inside itself: soft, slightly blue in shade
    bsdf.inputs['Subsurface Weight'].default_value = 0.0
    sheen = n.mixf(snow, 0.0, 0.25)
    n.link(sheen, bsdf.inputs['Sheen Weight'])
    bsdf.inputs['Sheen Roughness'].default_value = 0.5
    sh = add_aerial(n, bsdf.outputs[0], p['haze'])
    n.link(sh, out.inputs['Surface'])
    no_light(m)
    return m
