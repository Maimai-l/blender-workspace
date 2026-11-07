# Qiting - aerial perspective: distance haze added in the compositor from the mist pass (one place for all
# materials, including the lake surface and the far scene). The aerials A1/A2 show strong haze over the city.
import bpy


# matched to A2: trees 300-600 m out stay dark green, the city 2-3 km out is pale blue-grey; the colour is the
# photo's horizon sky (linear), not brighter
DEFAULTS = dict(color=(0.52, 0.60, 0.70), start=200.0, depth=3600.0, strength=0.72, gamma=1.0, sky=0.25)


def setup(scene=None, color=DEFAULTS['color'], start=DEFAULTS['start'], depth=DEFAULTS['depth'], strength=DEFAULTS['strength'],
          enable=True, gamma=DEFAULTS['gamma'], sky=DEFAULTS['sky']):
    sc = scene or bpy.context.scene
    vl = bpy.context.view_layer
    vl.use_pass_mist = enable
    w = sc.world
    w.mist_settings.start = start
    w.mist_settings.depth = depth
    w.mist_settings.falloff = 'LINEAR'
    if not enable:
        sc.compositing_node_group = None
        return None
    ng = bpy.data.node_groups.get('QT_Haze')
    if ng is None:
        ng = bpy.data.node_groups.new('QT_Haze', 'CompositorNodeTree')
    N, L = ng.nodes, ng.links
    for n in list(N):
        N.remove(n)
    if not any(i.in_out == 'OUTPUT' for i in ng.interface.items_tree):
        ng.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = N.new('CompositorNodeRLayers'); rl.location = (-600, 0)
    rl.scene = sc
    curve = N.new('ShaderNodeMath'); curve.operation = 'POWER'; curve.location = (-350, -200)
    L.new(rl.outputs['Mist'], curve.inputs[0]); curve.inputs[1].default_value = gamma
    k = N.new('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.location = (-180, -200)
    L.new(curve.outputs[0], k.inputs[0]); k.inputs[1].default_value = strength
    # the sky (mist = 1) only gets a light veil, not the full haze: it is already the photos' pale horizon blue
    obj = N.new('ShaderNodeMath'); obj.operation = 'LESS_THAN'; obj.location = (-350, -400)
    L.new(rl.outputs['Mist'], obj.inputs[0]); obj.inputs[1].default_value = 0.9995
    fac = N.new('ShaderNodeMix'); fac.data_type = 'FLOAT'; fac.location = (-180, -400)
    L.new(obj.outputs[0], fac.inputs[0]); fac.inputs[2].default_value = sky
    L.new(k.outputs[0], fac.inputs[3])
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.location = (0, 0)
    L.new(fac.outputs[0], mix.inputs[0])
    L.new(rl.outputs['Image'], mix.inputs[6])
    mix.inputs[7].default_value = tuple(color) + (1.0,)
    out = N.new('NodeGroupOutput'); out.location = (250, 0)
    L.new(mix.outputs[2], out.inputs[0])
    sc.compositing_node_group = ng
    return ng
