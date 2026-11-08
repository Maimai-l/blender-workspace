"""Compositor: depth fog, bloom, grade, vignette (Blender 5 compositing node group; everything is a socket)."""
import bpy

def _menu(sock, *names):
    for nm in names:
        try:
            sock.default_value = nm
            return nm
        except Exception:
            pass
    return None

def setup(scene, fog_color=(0.98, 0.86, 0.72), fog=0.55, bloom=0.22, vignette=0.22, w=1920, robot_fog=0.35,
          mattes=('J_root',)):
    vb = scene.view_layers['Beauty']; vi = scene.view_layers['Ink']
    ng = bpy.data.node_groups.get('AW_Comp')
    if ng is None:
        ng = bpy.data.node_groups.new('AW_Comp', 'CompositorNodeTree')
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    n = ng.nodes
    rl = n.new('CompositorNodeRLayers'); rl.location = (-1600, 200); rl.scene = scene; rl.layer = vb.name
    ri = n.new('CompositorNodeRLayers'); ri.location = (-1600, -400); ri.scene = scene; ri.layer = vi.name
    # actor matte (robot + birds) from the cryptomatte asset pass
    cm = n.new('CompositorNodeCryptomatteV2'); cm.location = (-1300, -100); cm.name = 'Matte'
    cm.source = 'RENDER'; cm.scene = scene
    try:
        cm.layer_name = vb.name + '.CryptoAsset'
    except Exception as e:
        print('crypto layer', e, [i.identifier for i in cm.bl_rna.properties['layer_name'].enum_items])
    cm.matte_id = ','.join(mattes)
    ng.links.new(rl.outputs['Image'], cm.inputs['Image'])
    dil = n.new('CompositorNodeDilateErode'); dil.location = (-1100, -100)
    _menu(dil.inputs['Type'], 'FEATHER', 'DISTANCE')
    dil.inputs['Size'].default_value = int(4 * w / 1920 + 0.5)
    ng.links.new(cm.outputs['Matte'], dil.inputs['Mask'])
    # ink lines only where the actors are really visible in the beauty layer
    ao = n.new('CompositorNodeAlphaOver'); ao.location = (-850, 200); ao.name = 'Ink'
    ng.links.new(rl.outputs['Image'], ao.inputs['Background'])
    ng.links.new(ri.outputs['Freestyle'], ao.inputs['Foreground'])
    ng.links.new(dil.outputs['Mask'], ao.inputs['Factor'])
    cur = ao.outputs['Image']
    # fog from the mist pass; the sky keeps its painted colour; the actors get only part of the fog
    mm = n.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.location = (-900, -300); mm.name = 'FogAmount'
    ng.links.new(rl.outputs['Mist'], mm.inputs[0]); mm.inputs[1].default_value = fog
    sky = n.new('ShaderNodeMath'); sky.operation = 'LESS_THAN'; sky.location = (-900, -450)
    ng.links.new(rl.outputs['Depth'], sky.inputs[0]); sky.inputs[1].default_value = 2500.0
    mm2 = n.new('ShaderNodeMath'); mm2.operation = 'MULTIPLY'; mm2.location = (-750, -350)
    ng.links.new(mm.outputs[0], mm2.inputs[0]); ng.links.new(sky.outputs[0], mm2.inputs[1])
    keep = n.new('ShaderNodeMath'); keep.operation = 'MULTIPLY_ADD'; keep.location = (-750, -550)
    ng.links.new(cm.outputs['Matte'], keep.inputs[0]); keep.inputs[1].default_value = -(1.0 - robot_fog); keep.inputs[2].default_value = 1.0
    mm3 = n.new('ShaderNodeMath'); mm3.operation = 'MULTIPLY'; mm3.location = (-600, -400)
    ng.links.new(mm2.outputs[0], mm3.inputs[0]); ng.links.new(keep.outputs[0], mm3.inputs[1])
    fogc = n.new('CompositorNodeRGB'); fogc.location = (-600, -650); fogc.name = 'FogColor'
    fogc.outputs[0].default_value = (*fog_color, 1)
    mix = n.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MIX'; mix.location = (-450, 0); mix.name = 'FogMix'
    ng.links.new(mm3.outputs[0], mix.inputs['Factor'])
    ng.links.new(cur, mix.inputs[6]); ng.links.new(fogc.outputs[0], mix.inputs[7])
    cur = mix.outputs[2]
    # bloom
    gl = n.new('CompositorNodeGlare'); gl.location = (-250, 0); gl.name = 'Bloom'
    ng.links.new(cur, gl.inputs['Image'])
    _menu(gl.inputs['Type'], 'BLOOM')
    _menu(gl.inputs['Quality'], 'HIGH')
    gl.inputs['Threshold'].default_value = 0.85
    gl.inputs['Smoothness'].default_value = 0.3
    gl.inputs['Strength'].default_value = bloom
    gl.inputs['Size'].default_value = 0.6
    gl.inputs['Saturation'].default_value = 0.8
    cur = gl.outputs['Image']
    # grade: lift shadows cool, warm gain
    cb = n.new('CompositorNodeColorBalance'); cb.location = (0, 0); cb.name = 'Grade'
    _menu(cb.inputs['Type'], 'LIFT_GAMMA_GAIN')
    for sk in cb.inputs:
        if sk.type == 'RGBA' and sk.name == 'Lift': sk.default_value = (1.01, 1.0, 1.035, 1)
        if sk.type == 'RGBA' and sk.name == 'Gamma': sk.default_value = (1.0, 1.0, 1.0, 1)
        if sk.type == 'RGBA' and sk.name == 'Gain': sk.default_value = (1.03, 1.0, 0.96, 1)
    ng.links.new(cur, cb.inputs['Image'])
    cur = cb.outputs['Image']
    # vignette
    em = n.new('CompositorNodeEllipseMask'); em.location = (0, -400)
    em.inputs['Position'].default_value = (0.5, 0.5)
    em.inputs['Size'].default_value = (1.3, 1.1)
    bl = n.new('CompositorNodeBlur'); bl.location = (200, -400)
    _menu(bl.inputs['Type'], 'GAUSSIAN', 'GAUSS')
    bl.inputs['Size'].default_value = (w * 0.22, w * 0.22)
    bl.inputs['Extend Bounds'].default_value = False
    ng.links.new(em.outputs['Mask'], bl.inputs['Image'])
    vm = n.new('ShaderNodeMath'); vm.operation = 'MULTIPLY_ADD'; vm.location = (400, -400)
    ng.links.new(bl.outputs['Image'], vm.inputs[0]); vm.inputs[1].default_value = vignette; vm.inputs[2].default_value = 1.0 - vignette
    vmix = n.new('ShaderNodeMix'); vmix.data_type = 'RGBA'; vmix.blend_type = 'MULTIPLY'; vmix.location = (450, 0)
    vmix.inputs['Factor'].default_value = 1.0
    ng.links.new(cur, vmix.inputs[6]); ng.links.new(vm.outputs[0], vmix.inputs[7])
    cur = vmix.outputs[2]
    # paper grain
    gimg = bpy.data.images.get('grain') or bpy.data.images.load(r'C:\Users\blender\Documents\awakening\tex\grain.png')
    gimg.name = 'grain'
    gi = n.new('CompositorNodeImage'); gi.image = gimg; gi.location = (450, -700)
    gmix = n.new('ShaderNodeMix'); gmix.data_type = 'RGBA'; gmix.blend_type = 'OVERLAY'; gmix.location = (650, 0)
    gmix.inputs['Factor'].default_value = 0.35
    ng.links.new(cur, gmix.inputs[6]); ng.links.new(gi.outputs['Image'], gmix.inputs[7])
    cur = gmix.outputs[2]
    # fade in / out
    fade = n.new('ShaderNodeValue'); fade.name = 'Fade'; fade.location = (650, -300); fade.outputs[0].default_value = 1.0
    fmix = n.new('ShaderNodeMix'); fmix.data_type = 'RGBA'; fmix.blend_type = 'MULTIPLY'; fmix.location = (850, 0)
    fmix.inputs['Factor'].default_value = 1.0
    ng.links.new(cur, fmix.inputs[6]); ng.links.new(fade.outputs[0], fmix.inputs[7])
    cur = fmix.outputs[2]
    out = n.new('NodeGroupOutput'); out.location = (1050, 0)
    ng.links.new(cur, out.inputs[0])
    scene.compositing_node_group = ng
    try:
        scene.render.use_compositing = True
    except Exception:
        pass
    return ng

def fades(ng, frames):
    """frames: list of (frame, value) for the Fade value node (fade in / fade out)."""
    sock = ng.nodes['Fade'].outputs[0]
    for f, v in frames:
        sock.default_value = v
        sock.keyframe_insert('default_value', frame=f)
    if ng.animation_data and ng.animation_data.action:
        try:
            for fc in ng.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        except Exception:
            pass
