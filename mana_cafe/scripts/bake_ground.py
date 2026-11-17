"""Top-down bakes of the two Tundra Rocky Ground scans (3D assets with their own UVs) so that they can be used as
tileable, box-projected ground textures: colour, world normal, height and roughness, rendered with an orthographic
camera and emission-only materials. Output: assets\\fab\\<key>\\raw_<map>.png ; proc/fab_seamless.py makes the tiles."""
import bpy, sys, importlib, os, time
LIB = r'D:\Blender\Projects\mana_cafe\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import mc_core, mc_fab
for m in (mc_core, mc_fab): importlib.reload(m)
from mc_core import NT
print(bpy.data.filepath, len(bpy.data.objects))
RES = 4096
main = bpy.context.scene
for key in ('rocky_ground_a', 'rocky_ground_b'):
    t0 = time.time()
    src = mc_fab.objects(key)[0]
    sc = bpy.data.scenes.get('BAKE') or bpy.data.scenes.new('BAKE')
    for o in list(sc.collection.objects): sc.collection.objects.unlink(o)
    ob = bpy.data.objects.new('BAKE_obj', src.data.copy()); sc.collection.objects.link(ob)
    bb = [ob.matrix_world @ __import__('mathutils').Vector(c) for c in ob.bound_box]
    x0, x1 = min(b.x for b in bb), max(b.x for b in bb); y0, y1 = min(b.y for b in bb), max(b.y for b in bb)
    z0, z1 = min(b.z for b in bb), max(b.z for b in bb)
    cam = bpy.data.objects.new('BAKE_cam', bpy.data.cameras.new('BAKE_cam')); sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; span = max(x1 - x0, y1 - y0); cam.data.ortho_scale = span
    cam.location = ((x0 + x1) / 2, (y0 + y1) / 2, z1 + 5.0); cam.data.clip_end = 100
    sc.camera = cam
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'GPU'; sc.cycles.samples = 16; sc.cycles.use_denoising = False
    sc.render.film_transparent = True; sc.render.resolution_x = sc.render.resolution_y = RES; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'; sc.render.image_settings.color_depth = '16'
    sc.view_settings.look = 'None'; sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
    w = bpy.data.worlds.get('BAKE_world') or bpy.data.worlds.new('BAKE_world'); w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.0; sc.world = w
    for what in ('color', 'normal', 'height', 'rough'):
        m, t = mc_core.new_mat('BAKE_mat'); n = NT(t)
        out = n.node('ShaderNodeOutputMaterial')
        if what == 'color':
            col = mc_fab._tex(n, key, 'color').outputs['Color']
        elif what == 'rough':
            col = n.node('ShaderNodeSeparateColor', inputs={0: mc_fab._tex(n, key, 'orm').outputs['Color']}).outputs[1]
        elif what == 'height':
            geo = n.node('ShaderNodeNewGeometry')
            z = n.node('ShaderNodeSeparateXYZ', inputs={0: geo.outputs['Position']}).outputs['Z']
            col = n.lin(z, z0, z1)
        else:
            nm = n.node('ShaderNodeNormalMap', inputs={'Strength': 1.0, 'Color': mc_fab._tex(n, key, 'normal').outputs['Color']})
            v = n.node('ShaderNodeVectorMath', operation='MULTIPLY_ADD', inputs={0: nm.outputs[0], 1: (0.5, 0.5, 0.5), 2: (0.5, 0.5, 0.5)})
            col = v.outputs[0]
        em = n.node('ShaderNodeEmission', inputs={'Color': col, 'Strength': 1.0})
        n.link(em.outputs[0], out.inputs['Surface'])
        ob.data.materials.clear(); ob.data.materials.append(m)
        sc.view_settings.view_transform = 'Standard' if what == 'color' else 'Raw'
        sc.render.filepath = os.path.join(mc_fab.FAB, key, 'raw_%s.png' % what)
        bpy.ops.render.render(write_still=True, scene=sc.name)
    meta = dict(span=span, z0=z0, z1=z1, x=(x0, x1), y=(y0, y1))
    import json
    json.dump(meta, open(os.path.join(mc_fab.FAB, key, 'raw_meta.json'), 'w'))
    d = ob.data; bpy.data.objects.remove(ob, do_unlink=True); bpy.data.meshes.remove(d)
    bpy.data.objects.remove(cam, do_unlink=True)
    print(key, meta, '%.1fs' % (time.time() - t0))
bpy.data.scenes.remove(bpy.data.scenes['BAKE'])
print('scene now', bpy.context.scene.name)
