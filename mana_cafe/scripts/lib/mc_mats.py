"""Materials for the landscape: aerial perspective group and the mountain surface."""
import bpy, math
import mc_core as C
from mc_core import NT

# sky radiance near the horizon in the view direction, measured in the HDRI (waterkloof_farm, 1-6 deg above the
# horizon, 95-110 deg from the sun), before the world's own grading
AIR_COLOR = (0.17, 0.44, 0.85)        # airlight of the clean air: towards the horizon sky the camera sees
CAM_Z = 11.76


# The massif stands 10.8 km from the cafe in this scene but 23-30 km in reality (proc/composite.py moves it
# SHIFT metres closer). The air is computed for the real distance, so the peak keeps the haze of a far range.
SHIFT = 12300.0
BLEND = (3000.0, 6000.0)               # the composite's blend radii round the sketch camera
BLEND_C = (9.6, 32.79)
MIST_TOP = -750.0                      # top of the moist air in the valley: just above the cloud (mc_clouds.SEA_TOP)
MIST_AIR = (0.44, 0.54, 0.68)
# tunables of the air, edited centrally: named Value nodes inside the group ("P_...")
AIR_PARAMS = dict(P_density=0.28, P_shift=SHIFT, P_mid=0.08, P_mist=0.5, P_keep=0.5)


def aerial_group(name='MC_aerial'):
    """Shader in -> shader out with the air between the camera and the surface (camera rays only).

        L = L_surface * (1 - keep * (1 - T)) + A_air * (1 - T_air) * T_mist + A_mist * (1 - T_mist)

    T_air: clean thin air, bluer than aerosol, thinning upwards (scale height 2.6 km), over the REAL distance
           d + shift, where shift fades in with the massif layer; plus a small fixed depth for anything beyond
           2.5 km (P_mid), which sets the ridges across the valley a step back from the foreground.
    T_mist: the moist layer below MIST_TOP, by the share of the ray that runs inside it.
    keep < 1 leaves the sunlit snow nearly as bright as it is (the photographs hold their highlights), while the
    airlight lifts and cools the shadows. Nothing is added in the foreground (d small)."""
    g = bpy.data.node_groups.get(name)
    if g is not None and 'Mask' not in [i.name for i in g.interface.items_tree]:
        g.interface.new_socket('Mask', in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
    if g is None:
        g = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        g.interface.new_socket('Shader', in_out='INPUT', socket_type='NodeSocketShader')
        g.interface.new_socket('Density', in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
        g.interface.new_socket('Air', in_out='INPUT', socket_type='NodeSocketColor').default_value = AIR_COLOR + (1,)
        g.interface.new_socket('Mask', in_out='INPUT', socket_type='NodeSocketFloat').default_value = 1.0
        g.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    g.nodes.clear()
    n = NT(g)
    gi = n.node('NodeGroupInput')
    go = n.node('NodeGroupOutput')

    def param(k):
        nd = n.node('ShaderNodeValue')
        nd.name = nd.label = k
        nd.outputs[0].default_value = AIR_PARAMS[k]
        return nd.outputs[0]
    p_density, p_shift, p_mid, p_mist, p_keep = (param(k) for k in ('P_density', 'P_shift', 'P_mid', 'P_mist', 'P_keep'))
    cam = n.node('ShaderNodeCameraData')
    geo = n.node('ShaderNodeNewGeometry')
    d = cam.outputs['View Distance']
    xyz = n.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Position']}).outputs
    z = xyz[2]
    # --- real distance: the massif layer is SHIFT metres further away than it stands here
    r = n.math('SQRT', n.math('ADD', n.math('POWER', n.math('SUBTRACT', xyz[0], BLEND_C[0]), 2.0),
                              n.math('POWER', n.math('SUBTRACT', xyz[1], BLEND_C[1]), 2.0)))
    wf = n.smooth(r, BLEND[0], BLEND[1])
    d_eff = n.math('ADD', d, n.math('MULTIPLY', wf, p_shift))
    H = 2600.0
    x = n.math('DIVIDE', n.math('SUBTRACT', z, CAM_Z), H)                 # dz / H
    # f = (1 - exp(-x)) / x, with the limit 1 at x -> 0
    ax = n.math('ABSOLUTE', x)
    xs = n.math('MAXIMUM', ax, 1e-3)
    sgn = n.math('SIGN', x)
    xx = n.math('MULTIPLY', xs, n.math('ADD', sgn, n.math('LESS_THAN', ax, 1e-9)))   # x with |x| >= 1e-3
    f = n.math('DIVIDE', n.math('SUBTRACT', 1.0, n.math('EXPONENT', n.math('MULTIPLY', xx, -1.0))), xx)
    f = n.math('MINIMUM', n.math('MAXIMUM', f, 0.3), 2.5)
    tau = n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY', d_eff, f), gi.outputs['Density']), p_density)
    tmid = n.math('MULTIPLY', n.smooth(d, 400.0, 2500.0), p_mid)
    # extinction per metre (R, G, B): clean thin air, a little bluer than pure aerosol
    beta = (1.05e-5, 1.75e-5, 2.9e-5)
    kmid = (0.45, 1.0, 1.9)
    T = [n.math('EXPONENT', n.math('MULTIPLY', n.math('ADD', n.math('MULTIPLY', tau, b), n.math('MULTIPLY', tmid, k)), -1.0))
         for b, k in zip(beta, kmid)]
    # --- the moist layer in the valley
    frac = n.math('DIVIDE', n.math('SUBTRACT', MIST_TOP, z), n.math('MAXIMUM', n.math('SUBTRACT', CAM_Z, z), 1.0))
    frac = n.math('MINIMUM', n.math('MAXIMUM', frac, 0.0), 1.0)
    tm = n.math('MULTIPLY', n.math('MULTIPLY', n.math('MULTIPLY', d, 8.0e-5), n.math('POWER', frac, 1.5)), p_mist)
    Tm = n.math('EXPONENT', n.math('MULTIPLY', tm, -1.0))
    Tavg = n.math('MULTIPLY', n.math('DIVIDE', n.math('ADD', n.math('ADD', T[0], T[1]), T[2]), 3.0), Tm)
    lp = n.node('ShaderNodeLightPath')
    cm = n.math('MULTIPLY', lp.outputs['Is Camera Ray'], gi.outputs['Mask'])
    # airlight
    one_m = n.node('ShaderNodeCombineColor', inputs={0: n.math('SUBTRACT', 1.0, T[0]), 1: n.math('SUBTRACT', 1.0, T[1]),
                                                     2: n.math('SUBTRACT', 1.0, T[2])}).outputs[0]
    pa = n.node('ShaderNodeRGB')
    pa.name = pa.label = 'P_air'
    pa.outputs[0].default_value = AIR_COLOR + (1,)
    air = n.mix(1.0, one_m, pa.outputs[0], 'MULTIPLY')
    air = n.mix(1.0, air, n.node('ShaderNodeCombineColor', inputs={0: Tm, 1: Tm, 2: Tm}).outputs[0], 'MULTIPLY')
    mist = n.mix(n.math('SUBTRACT', 1.0, Tm), (0, 0, 0, 1), MIST_AIR + (1,))
    veil = n.mix(1.0, air, mist, 'ADD', clamp=False)
    em = n.node('ShaderNodeEmission', inputs={'Color': veil, 'Strength': cm})
    black = n.node('ShaderNodeEmission', inputs={'Color': (0, 0, 0, 1), 'Strength': 0.0})
    att = n.math('MULTIPLY', n.math('MULTIPLY', n.math('SUBTRACT', 1.0, Tavg), p_keep), cm)      # share of the surface taken away
    mx = n.node('ShaderNodeMixShader', inputs={0: att})
    n.link(gi.outputs['Shader'], mx.inputs[1])
    n.link(black.outputs[0], mx.inputs[2])
    ad = n.node('ShaderNodeAddShader')
    n.link(mx.outputs[0], ad.inputs[0])
    n.link(em.outputs[0], ad.inputs[1])
    n.link(ad.outputs[0], go.inputs['Shader'])
    return g


def set_air(**kw):
    """Edit the air's tunables in place (P_density, P_shift, P_mid, P_mist, P_keep)."""
    g = aerial_group() if 'MC_aerial' not in bpy.data.node_groups else bpy.data.node_groups['MC_aerial']
    for k, v in kw.items():
        g.nodes[k].outputs[0].default_value = tuple(v) + (1,) if k == 'P_air' else v
    return {nd.name: ([round(c, 3) for c in nd.outputs[0].default_value][:3] if nd.name == 'P_air' else round(nd.outputs[0].default_value, 4))
            for nd in g.nodes if nd.name.startswith('P_')}


def wrap_aerial(m, density=1.25):
    """Put the air in front of an existing material (idempotent)."""
    t = m.node_tree
    out = next(x for x in t.nodes if x.type == 'OUTPUT_MATERIAL' and x.is_active_output)
    src = out.inputs['Surface'].links[0].from_socket
    if src.node.type == 'GROUP' and src.node.node_tree and src.node.node_tree.name == 'MC_aerial':
        return m
    grp = t.nodes.new('ShaderNodeGroup')
    grp.node_tree = aerial_group()
    grp.inputs['Density'].default_value = density
    t.links.new(src, grp.inputs['Shader'])
    t.links.new(grp.outputs['Shader'], out.inputs['Surface'])
    no_light(m)
    return m


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

    east, curv2 = A('east'), A('curv2')
    xyz = n.node('ShaderNodeSeparateXYZ', inputs={0: pos}).outputs
    clampf = lambda x, lo, hi: n.math('MINIMUM', n.math('MAXIMUM', x, lo), hi)
    # terrain structure shared by snow, rock and scree
    rib = n.smooth(curv, 0.35, 2.2)                                           # convex: ribs, spurs, crests
    gully = n.smooth(curv, -0.35, -2.2)                                       # concave: gullies, couloirs, hollows
    steep = n.smooth(n.math('ADD', slope, n.math('MULTIPLY', c(n_fine), 0.25)), 0.70, 1.25)
    wall = n.smooth(slope, 1.45, 2.3)
    # bedding of the rock: dipping beds, warped, of uneven thickness; their risers are bare, their ledges hold snow
    sc_ = n.math('ADD', n.math('ADD', xyz[2], n.math('MULTIPLY', xyz[0], 0.22)), n.math('MULTIPLY', xyz[1], 0.12))
    sc_ = n.math('ADD', sc_, n.math('ADD', n.math('MULTIPLY', n_mid, 70.0), n.math('MULTIPLY', n_big, 260.0)))
    bedn = n.node('ShaderNodeTexNoise', noise_dimensions='1D', inputs={'W': n.math('DIVIDE', sc_, 26.0), 'Scale': 1.0,
                                                                       'Detail': 4.0, 'Roughness': 0.75})
    riser = n.math('MULTIPLY', n.smooth(bedn.outputs['Fac'], 0.50, 0.62), n.smooth(n_mid2, 0.32, 0.55))   # broken bands
    vst = n.noise(n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': pos, 'Scale': (1 / 9.0, 1 / 9.0, 1 / 240.0)}).outputs[0], 1.0, 4, 0.62).outputs['Fac']

    # ---------------- snow cover: where fresh snow lies after the first autumn storms
    # effective altitude: shaded (north) slopes hold it lower, sunny ones lose it higher up
    eff = n.math('ADD', alt, n.math('MULTIPLY', north, p['aspect']))
    eff = n.math('SUBTRACT', eff, n.math('MULTIPLY', east, 70.0))                                     # the morning sun strips east faces
    eff = n.math('SUBTRACT', eff, n.math('MULTIPLY', n.math('SUBTRACT', 1.0, A('wfar')), 300.0))   # the ridge by the cafe is still bare
    s = n.math('DIVIDE', n.math('SUBTRACT', eff, p['snow_line']), p['snow_range'])
    # it lies in the gullies and hollows and is blown or slides off the ribs and crests
    s = n.math('ADD', s, n.math('MULTIPLY', clampf(n.math('MULTIPLY', curv, -0.42), -1.3, 1.3), n.mixf(steep, 0.9, 1.5)))
    s = n.math('ADD', s, clampf(n.math('MULTIPLY', curv2, -0.035), -0.5, 0.6))                        # bowls and cirques
    s = n.math('ADD', s, n.math('MULTIPLY', n.math('MINIMUM', n.math('SUBTRACT', flow, 2.6), 1.6), 0.20))
    # steep rock sheds it, except on the ledges of the beds and in the couloirs
    s = n.math('SUBTRACT', s, n.math('MULTIPLY', steep, n.math('ADD', 0.45, n.math('MULTIPLY', riser, 1.5))))
    s = n.math('ADD', s, n.math('MULTIPLY', n.math('MULTIPLY', steep, n.smooth(vst, 0.50, 0.68)), 0.75))
    s = n.math('SUBTRACT', s, n.math('MULTIPLY', wall, 1.4))
    s = n.math('ADD', s, n.math('MULTIPLY', c(n_big), 0.30))
    s = n.math('ADD', s, n.math('MULTIPLY', c(n_xl), 0.30))
    s = n.math('ADD', s, n.math('ADD', n.math('MULTIPLY', c(n_fine), 0.34), n.math('MULTIPLY', c(n_mid2), 0.30)))   # ragged, not dithered
    s = n.math('ADD', s, n.math('MULTIPLY', c(n.noise(pos, 1 / 5.0, 3, 0.6, dims='4D', w=13.0).outputs['Fac']), 0.16))
    firn = n.smooth(alt, 560.0, 900.0)                                       # permanent snow and glaciers
    s = n.math('ADD', s, n.math('MULTIPLY', firn, n.mixf(n.smooth(slope, 1.3, 2.1), 1.9, 0.3)))
    cover = n.smooth(s, -0.35, 0.45)
    snow = n.smooth(s, -0.045, 0.045)

    # ---------------- ground under the snow
    # rock: dark grey, a little warm, banded by its beds; the risers and overhangs darkest
    rock_bed = n.ramp(bedn.outputs['Fac'], [(0.25, (0.034, 0.034, 0.036, 1)), (0.45, (0.056, 0.055, 0.055, 1)),
                                            (0.62, (0.078, 0.074, 0.070, 1)), (0.8, (0.104, 0.100, 0.096, 1))])
    rock_flat = n.ramp(n_mid, [(0.25, (0.060, 0.058, 0.056, 1)), (0.75, (0.118, 0.110, 0.100, 1))])
    rock_tone = n.mix(n.smooth(slope, 0.75, 1.2), rock_flat, rock_bed)        # beds show on the faces, not on the slopes
    rock_var = n.ramp(n_fine, [(0.2, (0.70, 0.70, 0.70, 1)), (0.8, (1.25, 1.24, 1.22, 1))])
    rock = n.mix(1.0, rock_tone, rock_var, 'MULTIPLY')
    rock = n.mix(n.math('MULTIPLY', n.smooth(slope, 1.0, 1.6), n.math('MULTIPLY', n.smooth(vst, 0.5, 0.75), 0.5)), rock, (0.030, 0.030, 0.031, 1))   # wet streaks
    warm = n.smooth(n_big, 0.45, 0.75)                                        # iron-stained zones
    rock = n.mix(n.math('MULTIPLY', warm, 0.30), rock, (0.135, 0.100, 0.075, 1))
    rock = n.mix(n.math('MULTIPLY', n.math('MULTIPLY', riser, steep), 0.5), rock, (0.024, 0.024, 0.026, 1))
    rock = n.mix(n.math('MULTIPLY', rib, 0.25), rock, n.mix(1.0, rock, (1.5, 1.48, 1.44, 1), 'MULTIPLY'))    # weathered pale on the ribs
    # scree: fans and aprons below the rock, fresher and paler down the gully lines, lichen-dark where it has settled
    scree = n.ramp(n_tiny, [(0.2, (0.070, 0.069, 0.067, 1)), (0.8, (0.125, 0.122, 0.116, 1))])
    scree = n.mix(n.math('MULTIPLY', n.smooth(flow, 2.9, 3.7), 0.55), scree, (0.17, 0.165, 0.155, 1))
    scree = n.mix(n.math('MULTIPLY', n.smooth(n_mid, 0.5, 0.8), 0.5), scree, (0.070, 0.070, 0.064, 1))
    # alpine turf: dark olive and brown, straw on the sunny spurs
    meadow = n.ramp(n_mid, [(0.2, (0.085, 0.072, 0.038, 1)), (0.45, (0.125, 0.105, 0.052, 1)), (0.7, (0.165, 0.138, 0.070, 1)),
                            (0.9, (0.110, 0.100, 0.048, 1))])
    meadow = n.mix(n.math('MULTIPLY', n.smooth(north, 0.1, -0.4), 0.35), meadow, (0.21, 0.172, 0.085, 1))
    meadow = n.mix(1.0, meadow, n.ramp(n_tiny, [(0.2, (0.8, 0.8, 0.8, 1)), (0.8, (1.18, 1.18, 1.18, 1))]), 'MULTIPLY')
    shrub = n.ramp(n_fine, [(0.25, (0.020, 0.024, 0.014, 1)), (0.6, (0.040, 0.043, 0.024, 1)), (0.85, (0.068, 0.046, 0.030, 1))])
    forest = n.ramp(n_fine, [(0.3, (0.010, 0.016, 0.010, 1)), (0.7, (0.024, 0.034, 0.019, 1))])
    oak = n.ramp(n_fine, [(0.3, (0.040, 0.038, 0.022, 1)), (0.6, (0.075, 0.064, 0.036, 1)), (0.85, (0.105, 0.088, 0.050, 1))])   # sunny-side scrub
    earth = (0.11, 0.082, 0.055, 1)

    # belts (heights relative to the cafe: tree line about -150 m = 4250 m, shrubs to +120 m, turf to +420 m)
    a2 = n.math('ADD', alt, n.math('MULTIPLY', c(n_mid), 150.0))
    a2 = n.math('ADD', a2, n.math('MULTIPLY', c(n_big), 160.0))
    a2n = n.math('ADD', a2, n.math('MULTIPLY', north, -120.0))                # belts reach higher on sunny slopes
    f_forest = n.math('MULTIPLY', n.smooth(a2n, -110.0, -230.0), n.smooth(slope, 1.25, 0.8))
    f_dark = n.smooth(north, -0.25, 0.2)                                      # fir on shaded faces, oak scrub on sunny
    f_shrub = n.math('MULTIPLY', n.math('MULTIPLY', n.smooth(a2n, 150.0, -40.0), n.smooth(slope, 1.15, 0.7)),
                     n.smooth(n.math('ADD', n_mid2, n.math('MULTIPLY', north, 0.25)), 0.35, 0.6))
    # bare rock: the ribs and steps of steep ground, everything above the turf line, the rocky zones of the massif
    f_rock = n.smooth(n.math('ADD', n.math('ADD', slope, n.math('MULTIPLY', rib, 0.45)), n.math('MULTIPLY', c(n_mid), 0.35)), 1.05, 1.40)
    f_rock = n.math('MAXIMUM', f_rock, n.smooth(a2, 430.0, 640.0))
    f_rock = n.math('MAXIMUM', f_rock, n.math('MULTIPLY', n.smooth(n.math('ADD', rocky, n.math('MULTIPLY', c(n_fine), 0.5)), 0.66, 0.9), n.smooth(alt, 60.0, 320.0)))
    f_rock = n.math('MAXIMUM', f_rock, n.math('MULTIPLY', n.math('MULTIPLY', riser, n.smooth(slope, 0.8, 1.1)), 0.9))   # outcropping beds
    # scree gathers below it: in the gullies and on the moderate slopes of the high ground
    f_scree = n.math('MULTIPLY', n.smooth(slope, 0.55, 0.8), n.smooth(n.math('ADD', n.math('ADD', n_mid, n.math('MULTIPLY', rocky, 0.6)), n.math('MULTIPLY', gully, 0.35)), 0.55, 0.78))
    f_scree = n.math('MULTIPLY', f_scree, n.smooth(a2, -40.0, 240.0))
    chute = n.math('MULTIPLY', n.smooth(flow, 3.1, 3.8), n.smooth(slope, 0.55, 0.85))      # debris chutes in the gullies
    f_scree = n.math('MAXIMUM', f_scree, n.math('MULTIPLY', chute, n.smooth(a2, -150.0, 150.0)))
    f_earth = n.math('MULTIPLY', n.smooth(n.math('ADD', n.math('MULTIPLY', flow, 0.22), n.math('MULTIPLY', n_fine, 0.6)), 1.0, 1.2), 0.5)

    g = n.mix(f_earth, meadow, earth)
    # gullies hold shrubs (dark dendritic lines), crests are dry and stony
    nearl = n.math('SUBTRACT', 1.0, A('wfar'))                                 # the real ground within 3-6 km
    f_gully = n.math('MULTIPLY', n.smooth(n.math('ADD', flow, n.math('MULTIPLY', n.math('MULTIPLY', curv, -1.0), n.mixf(nearl, 0.12, 0.30))), n.mixf(nearl, 2.9, 2.5), n.mixf(nearl, 3.7, 3.2)), n.smooth(a2, 420.0, 180.0))
    f_crest = n.math('MULTIPLY', n.smooth(curv, n.mixf(nearl, 1.2, 0.4), n.mixf(nearl, 4.5, 2.0)), n.mixf(nearl, 0.55, 0.75))
    g = n.mix(f_crest, g, n.mix(n_tiny, (0.15, 0.135, 0.095, 1), (0.21, 0.20, 0.17, 1)))
    g = n.mix(n.math('MAXIMUM', f_shrub, n.math('MULTIPLY', f_gully, 0.8)), g, shrub)
    vor = n.node('ShaderNodeTexVoronoi', feature='F1', inputs={'Vector': pos, 'Scale': 1.0 / 6.5, 'Randomness': 1.0})
    dots = n.math('MULTIPLY', n.smooth(vor.outputs['Distance'], 0.34, 0.14),
                  n.smooth(n.math('ADD', n_mid2, n.math('MULTIPLY', c(n_fine), 0.6)), 0.42, 0.62))
    g = n.mix(n.math('MULTIPLY', dots, 0.7), g, (0.022, 0.025, 0.015, 1))                         # shrub clumps
    g = n.mix(f_forest, g, n.mix(f_dark, oak, forest))
    # on the slope across the valley: beds of rock cropping out in broken bands, scree running down from them
    f_band = n.math('MULTIPLY', n.math('MULTIPLY', riser, n.smooth(slope, 0.52, 0.80)), nearl)
    f_run = n.math('MULTIPLY', n.math('MULTIPLY', n.smooth(vst, 0.56, 0.72), n.smooth(slope, 0.48, 0.75)), n.math('MULTIPLY', nearl, 0.65))
    f_scree = n.math('MAXIMUM', f_scree, f_run)
    f_rock = n.math('MAXIMUM', f_rock, f_band)
    g = n.mix(f_scree, g, scree)
    g = n.mix(f_rock, g, rock)
    band = n.math('MULTIPLY', riser, n.math('MAXIMUM', steep, f_band))

    near_bump = None
    if near:
        # the first few hundred metres: Megascans ground, box (triplanar) projected and blended by the height maps
        import mc_fab
        cam = n.node('ShaderNodeCameraData')
        nearw = n.smooth(cam.outputs['View Distance'], 560.0, 180.0)

        def lay(key, tile, rot=0.0, off=(0.0, 0.0, 0.0), maps=('color', 'disp')):
            mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': pos, 'Rotation': (0, 0, rot),
                                                                         'Location': off, 'Scale': (1.0 / tile,) * 3})
            out_ = []
            for mname in maps:
                nd = n.node('ShaderNodeTexImage', projection='BOX', projection_blend=0.2, inputs={'Vector': mp.outputs[0]})
                nd.image = mc_fab.image(key, mname)
                out_.append(nd.outputs['Color'])
            return out_

        def two(key, tile, maps, scale2=1.31, rot2=1.1, off2=(3.3, 1.7, 0.4), nscale=1 / 5.5, w=0.0):
            """Two differently placed samples of one scan, switched by a noise and their heights: hides the repeat."""
            c1, h1 = lay(key, tile, 0.0, (0.0, 0.0, 0.0), maps)
            c2, h2 = lay(key, tile * scale2, rot2, off2, maps)
            m = n.smooth(n.noise(pos, nscale, 3, 0.5, dims='4D', w=w).outputs['Fac'], 0.40, 0.60)
            f = mc_fab.height_blend(n, h1, h2, m, 0.2)
            return n.mix(f, c1, c2), n.mixf(f, h1, h2)
        bk = ('bake_color', 'bake_height')
        ta = mc_fab.manifest()['rocky_ground_a']['bake']
        tb = mc_fab.manifest()['rocky_ground_b']['bake']
        ca, ha = two('rocky_ground_a', ta['tile_m'], bk, w=1.0)
        cb, hb = two('rocky_ground_b', tb['tile_m'], bk, scale2=1.27, rot2=2.3, off2=(5.1, 2.2, 0.7), w=2.0)
        drift = n.smooth(n.math('ADD', n.noise(pos, 1 / 17.0, 3, 0.5, dims='4D', w=5.0).outputs['Fac'], n.math('MULTIPLY', slope, 0.25)), 0.56, 0.76)
        fab_ = mc_fab.height_blend(n, ha, hb, drift, 0.3)                              # gravelly soil <-> mossy rubble
        gcol = n.mix(fab_, ca, n.mix(1.0, cb, (0.46, 0.46, 0.45, 1), 'MULTIPLY'))
        gh = n.mixf(fab_, n.math('MULTIPLY', ha, ta['height_m']), n.math('MULTIPLY', hb, tb['height_m']))     # metres
        hn = n.mixf(fab_, ha, hb)
        sc_, sh_ = two('grassy_soil', 2.0, ('color', 'disp'), scale2=1.43, rot2=0.7, off2=(1.3, 4.1, 0.2), w=3.0)
        bare = n.smooth(n.math('ADD', n.noise(pos, 1 / 6.0, 4, 0.55, dims='4D', w=9.0).outputs['Fac'], n.math('MULTIPLY', slope, 0.15)), 0.60, 0.70)
        fs_ = mc_fab.height_blend(n, hn, sh_, bare, 0.3)                               # bare earth patches
        gcol = n.mix(fs_, gcol, n.mix(1.0, sc_, (0.50, 0.46, 0.41, 1), 'MULTIPLY'))
        gh = n.mixf(fs_, gh, n.math('MULTIPLY', sh_, 0.016))
        # turf and litter under the shrubs: darker and a little less colourful than the open scans
        gcol = n.node('ShaderNodeHueSaturation', inputs={'Saturation': 0.70, 'Value': 0.43, 'Color': gcol}).outputs[0]
        g = n.mix(nearw, g, gcol)
        # ---- gravel: the terrace and the track
        gc_, gh_ = two('gravel', 2.0, ('color', 'disp'), scale2=1.37, rot2=0.9, off2=(0.7, 2.9, 0.5), nscale=1 / 3.0, w=4.0)
        trk, ter, trd = A('track'), A('terrace'), A('trackd')
        ragged = n.math('MULTIPLY', c(n.noise(pos, 1 / 0.9, 4, 0.6, dims='4D', w=6.0).outputs['Fac']), 0.9)
        tmask = n.smooth(n.math('ADD', trk, ragged), 0.30, 0.70)
        rut = n.math('EXPONENT', n.math('MULTIPLY', n.math('POWER', n.math('DIVIDE', n.math('SUBTRACT', trd, 0.78), 0.30), 2.0), -1.0))
        centre = n.math('MULTIPLY', n.smooth(trd, 0.50, 0.12), n.smooth(n.noise(pos, 1 / 2.5, 3, 0.5, dims='4D', w=7.0).outputs['Fac'], 0.35, 0.60))
        verge = n.math('MULTIPLY', n.smooth(trd, 1.25, 1.95), 0.6)
        tmask = n.math('MULTIPLY', tmask, n.math('SUBTRACT', 1.0, n.math('MULTIPLY', n.math('MAXIMUM', centre, verge), 0.75)))   # turf creeps in
        gmask = n.math('MAXIMUM', ter, tmask)
        fg_ = mc_fab.height_blend(n, hn, gh_, gmask, 0.22)
        fg_ = n.math('MAXIMUM', fg_, ter)
        stain = n.noise(pos, 1 / 4.0, 4, 0.6, dims='4D', w=8.0).outputs['Fac']
        tval = n.math('SUBTRACT', n.math('ADD', 0.52, n.math('MULTIPLY', stain, 0.18)), n.math('MULTIPLY', rut, 0.16))     # track: dark, damp ruts
        wear = n.smooth(n.noise(pos, 1 / 6.0, 3, 0.5, dims='4D', w=11.0).outputs['Fac'], 0.3, 0.75)
        pval = n.math('ADD', 0.66, n.math('MULTIPLY', wear, 0.22))                                                      # terrace
        gcol2 = n.node('ShaderNodeHueSaturation', inputs={'Saturation': 0.80, 'Value': n.mixf(ter, tval, pval), 'Color': gc_}).outputs[0]
        fine = n.mix(n.math('MULTIPLY', rut, 0.5), gcol2, n.mix(1.0, gcol2, (0.62, 0.58, 0.52, 1), 'MULTIPLY'))          # compacted fines in the ruts
        g = n.mix(fg_, g, fine)
        gh = n.mixf(fg_, gh, n.math('MULTIPLY', gh_, 0.04))
        near_bump = n.math('MULTIPLY', n.smooth(cam.outputs['View Distance'], 400.0, 120.0), gh)

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
        bh = n.math('ADD', n.math('MULTIPLY', bh, n.math('SUBTRACT', 1.0, n.math('MULTIPLY', nearw, 0.9))), n.math('MULTIPLY', near_bump, 1.6))
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
