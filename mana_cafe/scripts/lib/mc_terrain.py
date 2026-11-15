"""Terrain objects: loads the meshes built by scripts/proc and makes the mountain material."""
import bpy, os, json, math
import numpy as np
import mc_core as C
import mc_mats


def load_far(name='TER_far', mat=None):
    d = np.load(os.path.join(C.DEM, 'mesh_far.npz'))
    nr, ncol = int(d['nr']), int(d['ncol'])
    attrs = {k[2:]: d[k] for k in d.files if k.startswith('a_')}
    me = C.grid_mesh(name, d['co'], nr, ncol, attrs=attrs)
    o = C.obj(name, me, C.coll('MC_terrain'), mat or mc_mats.mountain_material())
    o.hide_viewport = True
    o['layer'] = json.dumps(json.load(open(os.path.join(C.DEM, 'mesh_far.json'))))
    return o


def load_near(name='TER_near', mat=None):
    d = np.load(os.path.join(C.DEM, 'mesh_near.npz'))
    attrs = {k[2:]: d[k] for k in d.files if k.startswith('a_')}
    co = d['co']
    quads = d['quads']
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set('co', co.ravel())
    nq = len(quads)
    me.loops.add(nq * 4)
    me.loops.foreach_set('vertex_index', quads.ravel())
    me.polygons.add(nq)
    me.polygons.foreach_set('loop_start', np.arange(0, nq * 4, 4, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    for k, v in attrs.items():
        me.attributes.new(k, 'FLOAT', 'POINT').data.foreach_set('value', v)
    o = C.obj(name, me, C.coll('MC_terrain'), mat or mc_mats.mountain_material())
    o.hide_viewport = True        # 10 M faces: keep them out of the viewport's GPU memory
    return o
