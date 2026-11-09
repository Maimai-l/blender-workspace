"""rig.py - a rigid-part robot: SDF parts on a joint hierarchy.

A Part is modelled in its own local frame whose origin is its pivot (joint).
`joint` is the pivot position in the parent's local frame (rest pose).
A pose maps part name -> (rx, ry, rz) degrees, applied in the part's local
frame at the pivot. Left parts are mirrors of right parts (x -> -x).

Meshes are cached to disk (keyed by part name and a version string), so the
SDF meshing cost is paid once.
"""
import os
import hashlib
import numpy as np
import r3d
from r3d import rot_matrix, mat4

CACHE = os.environ.get('AW2_MESH_CACHE', '/home/user/aw2_cache/meshes')

# material classes
PAINT, METAL, LENS, GLOW, MOSS, WOOD, CABLE, DARK, LIDS, SOIL = range(1, 11)


class Part:
    def __init__(self, name, parent, joint, sdf, lo, hi, voxel=0.05, mat=PAINT,
                 mirror_of=None, version='1'):
        self.name = name; self.parent = parent
        self.joint = np.asarray(joint, np.float32)
        self.sdf = sdf; self.lo = lo; self.hi = hi; self.voxel = voxel
        self.mat = mat; self.mirror_of = mirror_of; self.version = version
        self.mesh = None
        self.index = -1


class Rig:
    def __init__(self, name):
        self.name = name
        self.parts = {}
        self.order = []

    def add(self, part):
        part.index = len(self.order)
        self.parts[part.name] = part
        self.order.append(part.name)
        return part

    def add_pair(self, name_r, parent_r, joint_r, sdf, lo, hi, voxel=0.05, mat=PAINT, version='1'):
        """Add a right part and its mirrored left twin (names *_R / *_L)."""
        # parent_r is the full name of the right-side parent ('torso', 'upperarm_R', ...)
        pr = self.add(Part(name_r + '_R', parent_r, joint_r, sdf, lo, hi, voxel, mat, None, version))
        jl = np.asarray(joint_r, np.float32) * np.array([-1, 1, 1], np.float32)
        parent_l = pr.parent[:-2] + '_L' if pr.parent.endswith('_R') else pr.parent
        pl = self.add(Part(name_r + '_L', parent_l, jl, sdf, lo, hi, voxel, mat, pr.name, version))
        return pr, pl

    # ------------------------------------------------------------------
    def build_meshes(self, verbose=True):
        os.makedirs(CACHE, exist_ok=True)
        for nm in self.order:
            p = self.parts[nm]
            if p.mirror_of is not None:
                continue
            key = hashlib.md5(f'{self.name}/{nm}/{p.version}/{p.voxel}/{p.lo}/{p.hi}'.encode()).hexdigest()[:10]
            path = os.path.join(CACHE, f'{self.name}_{nm}_{key}.npz')
            if os.path.exists(path):
                p.mesh = r3d.Mesh.load(path)
            else:
                V, F, N = r3d.mesh_sdf(p.sdf, p.lo, p.hi, p.voxel)
                p.mesh = r3d.Mesh(V, F, N, part=p.index, mat=p.mat, name=nm)
                p.mesh.save(path)
                if verbose:
                    print(f'  meshed {nm}: {len(F)} tris')
            p.mesh.part = p.index; p.mesh.mat = p.mat
        for nm in self.order:
            p = self.parts[nm]
            if p.mirror_of is None:
                continue
            src = self.parts[p.mirror_of].mesh
            V = src.V * np.array([-1, 1, 1], np.float32)
            N = src.N * np.array([-1, 1, 1], np.float32)
            F = src.F[:, [0, 2, 1]].copy()
            p.mesh = r3d.Mesh(V, F, N, part=p.index, mat=p.mat, name=nm)

    # ------------------------------------------------------------------
    def world_mats(self, pose, root=np.eye(4, dtype=np.float32)):
        """pose: dict name -> (rx, ry, rz) or a 4x4; '_root' may hold a 4x4 world matrix."""
        mats = {}
        rootM = pose.get('_root', root)
        for nm in self.order:
            p = self.parts[nm]
            r = pose.get(nm, (0.0, 0.0, 0.0))
            if p.mirror_of is not None and nm not in pose:
                rr = pose.get(p.mirror_of, None)
                if rr is not None:
                    r = (rr[0], -rr[1], -rr[2])     # mirror the rotation
            L = mat4(rot_matrix(*r), p.joint)
            if p.parent is None or p.parent == '':
                mats[nm] = rootM @ L
            else:
                mats[nm] = mats[p.parent] @ L
        return mats

    def scene(self, pose, extra=None, skip=()):
        mats = self.world_mats(pose)
        sc = r3d.Scene()
        for nm in self.order:
            if nm in skip:
                continue
            p = self.parts[nm]
            if p.mesh is None:
                continue
            sc.add(p.mesh, mats[nm])
        if extra:
            for mesh, M in extra:
                sc.add(mesh, M)
        return sc, mats
