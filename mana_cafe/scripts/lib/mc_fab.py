"""Megascans (Fab) library inside Blender: meshes from the glTF packs in D:\\fab_downloads, materials from the
render-sized texture copies written by proc/fab_prep.py (assets\\fab\\manifest.json).

Every asset lives in a collection 'FAB_<key>' that is not linked to the scene; the scene uses instances of it."""
import bpy, os, json, math
import numpy as np
import mc_core as C
from mc_core import NT

FAB = os.path.join(C.ASSETS, 'fab')
_MAN = None

# light variants of the heavy plants (Dwarf Birch is 24 M triangles in all)
VARIANTS = {'dwarf_birch': ('VarB', 'VarD', 'VarG', 'VarH', 'VarI', 'VarJ')}
# triangle budget per mesh for the 3D scans (nothing is nearer than 10 m to the camera)
BUDGET = {'granite_cliff': 500000, 'jp_wall': 300000, 'rock_formation': 600000, 'mossy_wall': 350000,
          'snowy_ground': 250000, 'boulder_a': 150000, 'boulder_b': 150000, 'rocky_ground_a': 500000,
          'rocky_ground_b': 500000, 'stone': 60000, 'dwarf_birch': 350000, 'yellow_flower': 60000,
          'tundra_grass': 60000, 'dwarf_willow': 80000, 'lingonberry': 40000, 'wild_grass': 40000}


def manifest():
    global _MAN
    if _MAN is None:
        _MAN = json.load(open(os.path.join(FAB, 'manifest.json'), encoding='utf-8'))
    return _MAN


def image(key, name, colorspace=None):
    """Image datablock of an asset's map: color, color_alpha, normal, orm, ort, rough, disp, ao, transl, fuzz, opacity."""
    m = manifest()[key]['maps'].get(name)
    if m is None:
        return None
    im = bpy.data.images.load(m['file'], check_existing=True)
    im.colorspace_settings.name = colorspace or ('sRGB' if name in ('color', 'color_alpha') else 'Non-Color')
    if name == 'color_alpha':
        im.alpha_mode = 'CHANNEL_PACKED'
    return im


def has(key, name):
    return name in manifest()[key]['maps']


# ------------------------------------------------------------------ import
def _trimmed_gltf(key, variants):
    """A copy of the asset's .gltf that keeps only the wanted nodes (written next to the texture copies)."""
    src = manifest()[key]['gltf']
    j = json.load(open(src, encoding='utf-8'))
    keep = [i for i, nd in enumerate(j['nodes']) if any(v in nd.get('name', '') for v in variants)]
    j['scenes'][j.get('scene', 0)]['nodes'] = keep
    base = os.path.dirname(src)
    out_dir = os.path.join(FAB, key)
    for part in ('buffers', 'images'):
        for it in j.get(part, []):
            if 'uri' in it:
                it['uri'] = os.path.relpath(os.path.normpath(os.path.join(base, it['uri'])), out_dir).replace('\\', '/')
    out = os.path.join(out_dir, 'sel.gltf')
    json.dump(j, open(out, 'w', encoding='utf-8'))
    return out


def import_asset(key, force=False, log=print):
    """Import an asset's meshes into collection 'FAB_<key>' (transforms applied, metres, Z up), decimated to its
    triangle budget, with this module's material. Returns the collection."""
    name = 'FAB_' + key
    col = bpy.data.collections.get(name)
    if col is not None and len(col.objects) and not force:
        return col
    if col is None:
        col = bpy.data.collections.new(name)
    for o in list(col.objects):
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if d.users == 0:
            bpy.data.meshes.remove(d)
    e = manifest()[key]
    path = e['gltf']
    if key in VARIANTS:
        path = _trimmed_gltf(key, VARIANTS[key])
    before_o = set(bpy.data.objects)
    before_m = set(bpy.data.materials)
    before_i = set(bpy.data.images)
    mat = plant_material(key) if e['kind'] == 'plant' else rock_material(key)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before_o]
    budget = BUDGET.get(key)
    dg = bpy.context.evaluated_depsgraph_get()
    made = []
    for o in sorted(new, key=lambda x: x.name):
        if o.type != 'MESH':
            continue
        me = o.data
        me.transform(o.matrix_world)
        o.matrix_world = __import__('mathutils').Matrix.Identity(4)
        nt = len(me.polygons)
        if budget and nt > budget * 1.2:
            md = o.modifiers.new('dec', 'DECIMATE')
            md.ratio = budget / nt
            dg = bpy.context.evaluated_depsgraph_get()
            me2 = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
            o.modifiers.remove(md)
            old = me
            o.data = me2
            bpy.data.meshes.remove(old)
            me = me2
        me.materials.clear()
        me.materials.append(mat)
        suffix = o.name.split('_')[-1] if e['kind'] == 'plant' else 'main'
        me.name = '%s_%s' % (name, suffix)
        o.name = me.name
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        made.append((o.name, nt, len(me.polygons), [round(v, 2) for v in o.dimensions]))
    for o in new:
        if o.type != 'MESH':
            bpy.data.objects.remove(o, do_unlink=True)
    for m in [m for m in bpy.data.materials if m not in before_m and m is not mat and m.users == 0]:
        bpy.data.materials.remove(m)
    for im in [im for im in bpy.data.images if im not in before_i and im.users == 0]:
        bpy.data.images.remove(im)
    col.use_fake_user = True
    for row in made:
        log('  ', row)
    return col


def objects(key, pattern=None):
    col = bpy.data.collections.get('FAB_' + key) or import_asset(key)
    return [o for o in sorted(col.objects, key=lambda x: x.name) if pattern is None or pattern in o.name]


# ------------------------------------------------------------------ materials
def _tex(n, key, name, vec=None, **kw):
    nd = n.node('ShaderNodeTexImage', **kw)
    nd.image = image(key, name)
    if vec is not None:
        n.link(vec, nd.inputs['Vector'])
    return nd


def plant_material(key, name=None, hue=0.5, sat=1.0, val=1.0, transl=0.35, jitter=(0.02, 0.15, 0.2), tint=None):
    """Scanned plant atlas: colour + opacity, normal, occlusion / roughness / translucency. Hue, saturation and
    value vary per instance and in drifts across the ground, so that no two neighbours match."""
    m, t = C.new_mat(name or ('FAB_' + key))
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    bo = _tex(n, key, 'color_alpha')
    ort = _tex(n, key, 'ort')
    nrm = _tex(n, key, 'normal')
    sep = n.node('ShaderNodeSeparateColor', inputs={0: ort.outputs['Color']}).outputs
    info = n.node('ShaderNodeObjectInfo')
    wn = n.node('ShaderNodeTexWhiteNoise', noise_dimensions='1D', inputs={'W': info.outputs['Random']})
    rs = n.node('ShaderNodeSeparateColor', inputs={0: wn.outputs['Color']}).outputs
    drift = n.noise(info.outputs['Location'], 0.22, 3, 0.5).outputs['Fac']        # metres-wide colour drifts
    hsv = n.node('ShaderNodeHueSaturation', inputs={
        'Hue': n.math('ADD', hue - jitter[0], n.math('MULTIPLY', rs[0], 2 * jitter[0])),
        'Saturation': n.math('ADD', sat - jitter[1], n.math('MULTIPLY', n.math('ADD', n.math('MULTIPLY', rs[1], 0.5), n.math('MULTIPLY', drift, 0.5)), 2 * jitter[1])),
        'Value': n.math('ADD', val - jitter[2], n.math('MULTIPLY', n.math('ADD', n.math('MULTIPLY', rs[2], 0.5), n.math('MULTIPLY', drift, 0.5)), 2 * jitter[2])),
        'Color': bo.outputs['Color']})
    col = hsv.outputs[0]
    if tint is not None:
        col = n.mix(1.0, col, tuple(tint) + (1,), 'MULTIPLY')
    col = n.mix(n.math('MULTIPLY', n.math('SUBTRACT', 1.0, sep[0]), 0.5), col, (0, 0, 0, 1))      # scanned occlusion
    nm = n.node('ShaderNodeNormalMap', inputs={'Strength': 0.8, 'Color': nrm.outputs['Color']})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': sep[1], 'Normal': nm.outputs[0],
                                                      'Specular IOR Level': 0.3})
    tr = n.node('ShaderNodeBsdfTranslucent', inputs={'Color': n.mix(1.0, col, (1.25, 1.3, 0.9, 1), 'MULTIPLY'),
                                                     'Normal': nm.outputs[0]})
    mx = n.node('ShaderNodeMixShader', inputs={0: n.math('MULTIPLY', sep[2], transl)})
    n.link(bsdf.outputs[0], mx.inputs[1])
    n.link(tr.outputs[0], mx.inputs[2])
    tp = n.node('ShaderNodeBsdfTransparent')
    cut = n.node('ShaderNodeMixShader', inputs={0: n.math('GREATER_THAN', bo.outputs['Alpha'], 0.35)})
    n.link(tp.outputs[0], cut.inputs[1])
    n.link(mx.outputs[0], cut.inputs[2])
    n.link(cut.outputs[0], out.inputs['Surface'])
    m.cycles.emission_sampling = 'NONE'
    return m


def rock_material(key, name=None, hue=0.5, sat=1.0, val=1.0, tint=None, bump=1.0):
    """Scanned rock / wall / ground asset with its own UVs: colour, normal, occlusion-roughness-metal, moss fuzz."""
    m, t = C.new_mat(name or ('FAB_' + key))
    n = NT(t)
    out = n.node('ShaderNodeOutputMaterial')
    b = _tex(n, key, 'color')
    nrm = _tex(n, key, 'normal')
    orm = _tex(n, key, 'orm') if has(key, 'orm') else None
    col = n.node('ShaderNodeHueSaturation', inputs={'Hue': hue, 'Saturation': sat, 'Value': val, 'Color': b.outputs['Color']}).outputs[0]
    if tint is not None:
        col = n.mix(1.0, col, tuple(tint) + (1,), 'MULTIPLY')
    rough = 0.85
    if orm is not None:
        sep = n.node('ShaderNodeSeparateColor', inputs={0: orm.outputs['Color']}).outputs
        col = n.mix(n.math('MULTIPLY', n.math('SUBTRACT', 1.0, sep[0]), 0.6), col, (0, 0, 0, 1))
        rough = sep[1]
    nm = n.node('ShaderNodeNormalMap', inputs={'Strength': bump, 'Color': nrm.outputs['Color']})
    bsdf = n.node('ShaderNodeBsdfPrincipled', inputs={'Base Color': col, 'Roughness': rough, 'Normal': nm.outputs[0],
                                                      'Specular IOR Level': 0.3})
    if has(key, 'fuzz'):
        fz = _tex(n, key, 'fuzz')
        n.link(n.math('MULTIPLY', fz.outputs['Color'], 0.6), bsdf.inputs['Sheen Weight'])
        bsdf.inputs['Sheen Roughness'].default_value = 0.6
    if has(key, 'transl'):                                      # snow: light scatters inside
        tl = _tex(n, key, 'transl')
        n.link(n.math('MULTIPLY', tl.outputs['Color'], 0.5), bsdf.inputs['Subsurface Weight'])
        bsdf.inputs['Subsurface Radius'].default_value = (0.35, 0.5, 0.7)
        bsdf.inputs['Subsurface Scale'].default_value = 0.08
    n.link(bsdf.outputs[0], out.inputs['Surface'])
    return m


def surface(n, key, vec, tile, box=True, blend=0.25, rot=0.0, offset=(0.0, 0.0, 0.0)):
    """Tileable scanned surface sampled with box (triplanar) projection. vec: position in metres; tile: metres per
    repeat. Returns dict of sockets: color, rough, normal_color (tangent-space colour), height (0..1), ao."""
    mp = n.node('ShaderNodeMapping', vector_type='POINT', inputs={'Vector': vec, 'Rotation': (0.0, 0.0, rot),
                                                                 'Location': offset, 'Scale': (1.0 / tile,) * 3})
    kw = dict(projection='BOX', projection_blend=blend) if box else {}
    o = {}
    o['color'] = _tex(n, key, 'color', mp.outputs[0], **kw).outputs['Color']
    if has(key, 'rough'):
        o['rough'] = _tex(n, key, 'rough', mp.outputs[0], **kw).outputs['Color']
    elif has(key, 'orm'):
        o['rough'] = n.node('ShaderNodeSeparateColor', inputs={0: _tex(n, key, 'orm', mp.outputs[0], **kw).outputs['Color']}).outputs[1]
    if has(key, 'disp'):
        o['height'] = _tex(n, key, 'disp', mp.outputs[0], **kw).outputs['Color']
    if has(key, 'normal'):
        o['normal_color'] = _tex(n, key, 'normal', mp.outputs[0], **kw).outputs['Color']
    if has(key, 'ao'):
        o['ao'] = _tex(n, key, 'ao', mp.outputs[0], **kw).outputs['Color']
    o['vector'] = mp.outputs[0]
    return o


def height_blend(n, ha, hb, mask, contrast=0.25):
    """Blend factor (0 = a, 1 = b) from two height maps and a 0..1 mask: the higher surface wins near the edge."""
    a = n.math('ADD', ha, n.math('SUBTRACT', 1.0, mask))
    b = n.math('ADD', hb, mask)
    return n.smooth(n.math('SUBTRACT', b, a), -contrast, contrast)
