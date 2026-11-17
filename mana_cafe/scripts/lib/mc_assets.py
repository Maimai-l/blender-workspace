"""Poly Haven model library (CC0): appends each downloaded .blend into an unlinked collection 'PH_<asset>'."""
import bpy, os
import mc_core as C

PH = os.path.join(C.ASSETS, 'ph')


def load(asset, res=None):
    """Append the objects of assets/ph/<asset>/<asset>_<res>.blend; returns the collection (cached)."""
    name = 'PH_' + asset
    col = bpy.data.collections.get(name)
    if col is not None and len(col.objects):
        return col
    d = os.path.join(PH, asset)
    files = [f for f in os.listdir(d) if f.endswith('.blend') and (res is None or ('_%s.' % res) in f)]
    path = os.path.join(d, sorted(files)[0])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    if col is None:
        col = bpy.data.collections.new(name)        # not linked to the scene: only used through instances
    for o in dst.objects:
        if o is None:
            continue
        if o.type != 'MESH':
            bpy.data.objects.remove(o)
            continue
        col.objects.link(o)
    col.use_fake_user = True          # not linked to the scene: keep it through save and reload
    return col


def report(col):
    out = []
    for o in col.objects:
        me = o.data
        out.append('%s dims %s loc %s faces %d mats %s parent %s' % (
            o.name, [round(v, 3) for v in o.dimensions], [round(v, 2) for v in o.location], len(me.polygons),
            [m.name for m in me.materials if m], o.parent.name if o.parent else None))
    return out


def find(col, base):
    """Object of a library collection by name, tolerating the '.001' suffix of a re-appended copy."""
    o = col.objects.get(base)
    if o is None:
        c = sorted([x for x in col.objects if x.name.startswith(base + '.')], key=lambda x: x.name)
        o = c[0] if c else None
    if o is None:
        raise KeyError(base)
    return o
