"""build.py - the complete Warden for production: model + growth + decals + style."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'engine'))
sys.path.insert(0, HERE)
import numpy as np
import ink
import warden as WD
import surface as SF
import poses as PZ

H_ = WD.hexc
# (light, shadow, deep, high, sky-fill)
PAL = {
    # one oxidised red-brown family: lit, shadow, deep shadow, highlight, sky fill (same hue, capped saturation)
    # lighter, warmer weathered red-ochre that catches the sunrise; dark maroon only in the deep/cast shadow
    WD.PAINT: (H_('b86a4a'), H_('70403a'), H_('3e2428'), H_('d6976f'), H_('8c5448')),
    WD.LIDS: (H_('a86048'), H_('633832'), H_('3a2024'), H_('c78763'), H_('7e4c42')),
    WD.ROOF: (H_('79ad9f'), H_('35574c'), None, H_('a9d1b6'), H_('557f74')),     # shadow: deep green, gaps read as moss shade
    WD.METAL: (H_('77706a'), H_('393545'), H_('2a2733'), None, H_('59576a')),
    WD.BRASS: (H_('d4a862'), H_('7a5a4c'), None, H_('f2d08a'), H_('a08068')),
    WD.LENS: (H_('3f4650'), H_('262a36')),
    WD.GLOW: (H_('ffdc8c'), H_('ffdc8c')),
    WD.DARK: (H_('3a2e36'), H_('241c26')),
    WD.MOSS: (H_('97ad4c'), H_('4a6741'), H_('2e4638'), H_('cdd270'), H_('6f8f55')),
    SF.FOLIAGE: (H_('76974a'), H_('375540'), H_('223b33'), H_('b0c262'), H_('557a52')),
    WD.WOOD: (H_('87694c'), H_('473a3f'), None, None, H_('6a5a58')),
    WD.SOIL: (H_('7a5d45'), H_('3f3238'), None, None, H_('5f4a46')),
}


def make(voxel=0.05, head_voxel=0.025, growth_voxel=0.035):
    rig = WD.build(voxel=voxel, head_voxel=head_voxel)
    rig.build_meshes(verbose=False)
    flowers = SF.add_growth(rig, voxel=growth_voxel)
    flowers.update(SF.add_ground_growth(rig))
    mats_k = rig.world_mats(PZ.grounded(rig, PZ.KNEEL_DORMANT))
    dec = SF.Decals(rig, SF.DECAL_PARTS, mats_k)
    mf, pf = WD.style_fns(rig)
    # moss tufts: sample points on the moss meshes (part-local), ~30 per m^2
    tufts = []
    rng = SF.rng_for('tufts')
    for nm in rig.order:
        if not (nm.startswith('moss_') or nm.startswith('gmoss_') or nm == 'foliage'):
            continue
        m = rig.parts[nm].mesh
        tri = m.V[m.F]
        area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        n = int(area.sum() * (40 if nm == 'foliage' else 22))
        idx = rng.choice(len(m.F), size=n, p=area / area.sum())
        w = rng.dirichlet((1, 1, 1), size=n).astype(np.float32)
        P = np.einsum('nk,nkd->nd', w, tri[idx]).astype(np.float32)
        N = np.einsum('nk,nkd->nd', w, m.N[m.F[idx]]).astype(np.float32)
        N /= np.linalg.norm(N, axis=1, keepdims=True)
        anchor = nm if rig.parts[nm].world else rig.parts[nm].parent
        tufts.append((anchor, P, N))   # anchored to the parent part's frame (same as moss); world growth to itself
    fl = [(p, F) for p, F in flowers.items()]
    rivets = make_rivets(rig)
    # grass sprouts from the moss (part-local anchors): height, blade count, lean
    sprouts = []
    rng2 = SF.rng_for('sprouts')
    for nm in rig.order:
        if not (nm.startswith('moss_') or nm.startswith('gmoss_')):
            continue
        m = rig.parts[nm].mesh
        tri = m.V[m.F]
        area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
        n = int(area.sum() * (3.2 if nm.startswith('gmoss_') else 1.6))
        if n == 0:
            continue
        idx = rng2.choice(len(m.F), size=n, p=area / area.sum())
        w = rng2.dirichlet((1, 1, 1), size=n).astype(np.float32)
        P = np.einsum('nk,nkd->nd', w, tri[idx]).astype(np.float32)
        N = np.einsum('nk,nkd->nd', w, m.N[m.F[idx]]).astype(np.float32)
        N /= np.linalg.norm(N, axis=1, keepdims=True)
        R = np.stack([rng2.uniform(0.35, 0.95, n), rng2.integers(3, 8, n), rng2.random(n)], -1).astype(np.float32)
        sprouts.append((nm if rig.parts[nm].world else rig.parts[nm].parent, P, N, R))
    style = dict(pal=PAL, matfn=mf, panelfn=pf, decals=dec, decal_cols=SF.DECAL_COLS,
                 roof_decal_cols=SF.ROOF_DECAL_COLS, decal_mats=(WD.PAINT, WD.LIDS), roof_mats=(WD.ROOF,),
                 lens_fn=lambda o, l: WD.eye_colour(o, 0.0, l), lens_mat=WD.LENS,
                 emissive={WD.GLOW: WD.hexc('3a2a30')}, flowers=fl, tufts=tufts,
                 soft_mats=(WD.MOSS, SF.FOLIAGE), tuft_mats=(WD.MOSS, SF.FOLIAGE), rivets=rivets, sprouts=sprouts,
                 widths={ink.SIL: 5.0, ink.OCC: 3.5, ink.PART: 2.2, ink.CREASE: 1.6, ink.DETAIL: 1.2})
    return rig, style


def make_rivets(rig):
    """Rivet rows along panel seams, as (part, local points, local normals), snapped to the mesh surface."""
    from scipy.spatial import cKDTree
    out = []
    def rows(part, pts):
        m = rig.parts[part].mesh
        tree = cKDTree(m.V)
        d, i = tree.query(pts)
        keep = d < 0.45
        out.append((part, m.V[i[keep]] + m.N[i[keep]] * 0.02, m.N[i[keep]]))
    ang = np.linspace(0, 2 * np.pi, 30, endpoint=False)
    # torso: rings just above/below the seams, and around the door
    for z, r in ((1.42, 3.0), (2.48, 3.4), (6.42, 3.6)):
        pts = np.stack([np.sin(ang) * r * 1.3, np.cos(ang) * r + 0.35, np.full_like(ang, z)], -1)
        rows('torso', pts)
    dz = np.linspace(2.85, 6.05, 7)
    for x in (-1.82, 1.82):
        rows('torso', np.stack([np.full_like(dz, x), np.full_like(dz, 3.6), dz], -1))
    dx = np.linspace(-1.7, 1.7, 7)
    for z in (2.85, 6.05):
        rows('torso', np.stack([dx, np.full_like(dx, 3.6), np.full_like(dx, z)], -1))
    for side in ('R', 'L'):
        sx = 1 if side == 'R' else -1
        a2 = np.linspace(0, 2 * np.pi, 22, endpoint=False)
        rows('pauldron_' + side, np.stack([sx * 0.45 + np.cos(a2) * 2.0, np.sin(a2) * 2.2, np.full_like(a2, 0.2)], -1))
        a3 = np.linspace(0, 2 * np.pi, 16, endpoint=False)
        for z in (-1.15, -2.75):
            rows('forearm_' + side, np.stack([np.cos(a3) * 1.45, np.sin(a3) * 1.45, np.full_like(a3, z)], -1))
        zz = np.linspace(-0.3, -2.6, 6)
        rows('shin_' + side, np.stack([np.full_like(zz, 0.55 * sx), np.full_like(zz, 1.3), zz], -1))

    def seam(part, cond, key, spacing):
        # rivets picked from the mesh along a seam: vertices where cond holds, ordered by key, spaced out
        m = rig.parts[part].mesh
        V, N = m.V, m.N
        idx = np.where(cond(V))[0]
        if len(idx) == 0:
            return
        idx = idx[np.argsort(key(V[idx]))]
        pick = [idx[0]]
        for i in idx[1:]:
            if np.linalg.norm(V[i] - V[pick[-1]]) >= spacing:
                pick.append(i)
        pick = np.array(pick)
        out.append((part, V[pick] + N[pick] * 0.02, N[pick]))
    # torso flank plates: a row beside each vertical seam and along the row seam
    for sx in (1, -1):
        seam('torso', lambda V, sx=sx: (np.abs(V[:, 0] - sx * 2.95) < 0.05) & (V[:, 1] > -0.6) & (V[:, 2] > 2.8) & (V[:, 2] < 6.35),
             lambda V: V[:, 2], 0.5)
    seam('torso', lambda V: (np.abs(V[:, 2] - 4.65) < 0.04) & ((np.abs(V[:, 0]) > 2.85) | (V[:, 1] < -1.1)),
         lambda V: np.arctan2(V[:, 0], V[:, 1]), 0.5)
    # the helmet cap
    seam('head', lambda V: (np.abs(V[:, 2] - 2.33) < 0.03) & (V[:, 1] < 1.5),
         lambda V: np.arctan2(V[:, 0], V[:, 1]), 0.36)
    return out
