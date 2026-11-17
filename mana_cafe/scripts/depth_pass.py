"""Depth pass of the final view: every surface shaded with its distance and position (clouds off), written as
renders\\_dbg\\<NAME>.npz (d = view distance in m, z = height in m, r = horizontal distance from the sketch camera in
m, a = 0 on sky), at W x H. Run through tools/rdefer.py; tools/depthcheck.py reads the result.

    PRE: NAME = 'depth'; W = 960; H = 540"""
import bpy, os, time
import numpy as np
NAME = globals().get('NAME', 'depth')
W, H = globals().get('W', 960), globals().get('H', 540)
sc = bpy.context.scene
vl = bpy.context.view_layer
print(bpy.data.filepath, len(bpy.data.objects))
out_dir = r'D:\Blender\Projects\mana_cafe\renders\_dbg'
m = bpy.data.materials.get('DBG_depth') or bpy.data.materials.new('DBG_depth')
m.use_nodes = True
t = m.node_tree
t.nodes.clear()
N, L = t.nodes, t.links
o = N.new('ShaderNodeOutputMaterial')
em = N.new('ShaderNodeEmission')
cam = N.new('ShaderNodeCameraData')
geo = N.new('ShaderNodeNewGeometry')
sep = N.new('ShaderNodeSeparateXYZ')
L.new(geo.outputs['Position'], sep.inputs[0])


def math(op, a, b):
    nd = N.new('ShaderNodeMath')
    nd.operation = op
    for i, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            nd.inputs[i].default_value = v
        else:
            L.new(v, nd.inputs[i])
    return nd.outputs[0]


r = math('SQRT', math('ADD', math('POWER', math('SUBTRACT', sep.outputs[0], 9.6), 2.0),
                      math('POWER', math('SUBTRACT', sep.outputs[1], 32.79), 2.0)), 0.0)
cc = N.new('ShaderNodeCombineColor')
L.new(math('MULTIPLY', cam.outputs['View Distance'], 0.001), cc.inputs[0])
L.new(math('ADD', math('MULTIPLY', sep.outputs[2], 0.001), 10.0), cc.inputs[1])
L.new(math('MULTIPLY', r, 0.001), cc.inputs[2])
L.new(cc.outputs[0], em.inputs['Color'])
L.new(em.outputs[0], o.inputs['Surface'])

clouds = bpy.data.collections.get('MC_clouds')
keep = dict(ov=vl.material_override, ft=sc.render.film_transparent, uc=sc.render.use_compositing, sp=sc.cycles.samples,
            rx=sc.render.resolution_x, ry=sc.render.resolution_y, rp=sc.render.resolution_percentage,
            dn=sc.cycles.use_denoising, fp=sc.render.filepath, ff=sc.render.image_settings.file_format,
            cd=sc.render.image_settings.color_depth, cm=sc.render.image_settings.color_mode,
            ch=[(ob, ob.hide_render) for ob in (clouds.objects if clouds else [])])
path = os.path.join(out_dir, NAME + '.exr')
try:
    vl.material_override = m
    sc.render.film_transparent = True
    sc.render.use_compositing = False
    sc.cycles.samples = 4
    sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    for ob, _ in keep['ch']:
        ob.hide_render = True
    sc.render.image_settings.media_type = 'IMAGE'
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    print('depth rendered %.1fs' % (time.time() - t0))
finally:
    vl.material_override = keep['ov']
    sc.render.film_transparent = keep['ft']
    sc.render.use_compositing = keep['uc']
    sc.cycles.samples = keep['sp']
    sc.cycles.use_denoising = keep['dn']
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = keep['rx'], keep['ry'], keep['rp']
    for ob, h in keep['ch']:
        ob.hide_render = h
    sc.render.image_settings.file_format = keep['ff']
    sc.render.image_settings.color_depth = keep['cd']
    sc.render.image_settings.color_mode = keep['cm']
    sc.render.filepath = keep['fp']
img = bpy.data.images.load(path)
img.colorspace_settings.name = 'Non-Color'
a = np.empty(W * H * 4, np.float32)
img.pixels.foreach_get(a)
bpy.data.images.remove(img)
a = a.reshape(H, W, 4)[::-1]
al = np.maximum(a[..., 3], 1e-6)
d = a[..., 0] / al * 1000.0
z = (a[..., 1] / al - 10.0) * 1000.0
r = a[..., 2] / al * 1000.0
np.savez_compressed(os.path.join(out_dir, NAME + '.npz'), d=d.astype(np.float32), z=z.astype(np.float32),
                    r=r.astype(np.float32), a=a[..., 3].astype(np.float16))
ok = a[..., 3] > 0.5
print('saved', NAME, 'd pct', np.percentile(d[ok], [0, 5, 25, 50, 75, 95, 100]).round().tolist(), 'sky share', round(1 - ok.mean(), 3))
