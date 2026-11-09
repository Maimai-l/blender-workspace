"""trees.py - unique painted trees: trunks, limbs, buttress roots, bark, moss, ivy, crowns.

paint_tube()    any woody tube (trunk / limb / root): cylinder light from the sun
                vector (lit side, warm rim, cool reflected light on the shadow edge),
                bark strokes that follow the form (with twist), fissures, lichen,
                moss patches, ivy, dappled light flecks, aerial perspective.
trunk_path()    a unique trunk centreline + width profile (lean, sway, bulges,
                buttress flare) from a few numbers.
paint_trunk()   trunk + buttress roots (+ limbs) for one tree.
crown_blobs()   foliage clusters for a crown at the end of a limb fan.
SPECIES         camphor (twisting, furrowed, buttressed), beech (smooth grey,
                eye marks, lichen), cedar (straight, fibrous red-brown strips).
"""
from dataclasses import dataclass, field, replace
import numpy as np
import cv2

from .canvas import dabs, stroke, catmull, normals, taper, tube_fields, wobble
from .color import (C, mix, ramp, ramp_lab, from_oklab, oklab, jitter, jitter_lab, shade,
                    aerial, smoothstep, lab_shift, DAWN)
from .noise import fbm, noise1d
from .foliage import Blobs


@dataclass
class Bark:
    dark: np.ndarray
    mid: np.ndarray
    lit: np.ndarray
    rim: np.ndarray
    refl: np.ndarray
    fissure: np.ndarray
    style: str = 'camphor'
    strokes: float = 1.0       # bark stroke density
    fissures: float = 1.0
    rag: float = 0.06          # silhouette roughness
    lichen: float = 0.0
    eyes: float = 0.0
    blotch: np.ndarray = None  # colour of large blotches (greenish algae / grey)


SPECIES = {
    'camphor': Bark(C(52, 46, 72), C(98, 86, 92), C(172, 146, 120), C(255, 214, 150), C(132, 136, 170),
                    C(34, 30, 52), 'camphor', 1.2, 1.3, 0.07, 0.15, 0.0, C(88, 104, 84)),
    'beech': Bark(C(60, 62, 88), C(110, 112, 126), C(178, 170, 154), C(255, 222, 166), C(140, 148, 178),
                  C(58, 58, 84), 'beech', 0.55, 0.0, 0.025, 1.0, 1.0, C(120, 138, 118)),
    'cedar': Bark(C(62, 40, 54), C(124, 80, 70), C(196, 132, 98), C(255, 206, 150), C(140, 120, 160),
                  C(44, 28, 44), 'cedar', 1.4, 0.6, 0.04, 0.1, 0.0, C(110, 96, 86)),
}


def species(name, depth=0.0, haze=None, **kw):
    b = replace(SPECIES[name], **kw)
    if depth > 0 and haze is not None:
        for k in ('dark', 'mid', 'lit', 'rim', 'refl', 'fissure', 'blotch'):
            setattr(b, k, aerial(getattr(b, k), depth, haze))
    return b


MOSS = dict(dark=C(36, 70, 72), mid=C(78, 122, 72), lit=C(160, 188, 86), tip=C(214, 214, 120))
IVY = dict(dark=C(24, 50, 56), mid=C(52, 96, 70), lit=C(122, 160, 84), gloss=C(206, 214, 160))


def _hazed(d, depth, haze):
    if depth <= 0 or haze is None:
        return d
    return {k: aerial(v, depth, haze) for k, v in d.items()}


class Frame:
    """Arclength frame of a resampled tube path for (s, t) -> image positions."""

    def __init__(self, path, widths):
        self.P = np.asarray(path, np.float32)
        self.w = np.asarray(widths, np.float32)
        T = np.gradient(self.P, axis=0)
        T /= np.maximum(np.hypot(*T.T)[:, None], 1e-6)
        self.T = T
        self.N = np.stack([-T[:, 1], T[:, 0]], 1)
        seg = np.hypot(*np.diff(self.P, axis=0).T)
        self.cum = np.concatenate([[0], np.cumsum(seg)]).astype(np.float32)
        self.L = float(self.cum[-1])
        self.s = self.cum / max(self.L, 1e-6)

    def at(self, s, t):
        s = np.clip(np.asarray(s, np.float32), 0, 1)
        f = s * (len(self.P) - 1)
        i = np.minimum(f.astype(int), len(self.P) - 2)
        u = (f - i)[..., None]
        P = self.P[i] * (1 - u) + self.P[i + 1] * u
        N = self.N[i] * (1 - u) + self.N[i + 1] * u
        w = self.w[i] * (1 - u[..., 0]) + self.w[i + 1] * u[..., 0]
        return P + N * (np.asarray(t, np.float32) * w * 0.5)[..., None], w, N


def light_value(TN, NdL, Lz, wrap=0.35, amb=0.12):
    """Cylinder lambert for across-coordinate TN given N.L2 (side facing) and Lz."""
    sz = np.sqrt(max(1 - Lz * Lz, 0))
    lam = TN * NdL * sz + np.sqrt(np.clip(1 - TN * TN, 0, 1)) * Lz
    v = np.clip((lam + wrap) / (1 + wrap), 0, 1)
    return amb + (1 - amb) * v


def paint_tube(cv, path, widths, rng, bark, light3=(0.6, -0.7, -0.25), depth=0.0, haze=None,
               moss=0.0, ivy=0.0, twist=0.0, detail=1.0, flecks=0.0, fleck_col=None,
               moss_base=0.35, rim_amt=1.0, refl_amt=0.5, ground_y=None, mist_fade=None,
               mist_col=None, opacity=1.0, end_fade=0.0, start_fade=0.0, tex=None,
               moss_pal=None, ivy_pal=None, sky_side=0.0, soft_edge=0.0):
    """Paint one woody tube. path runs from base to tip; widths are full widths.
    light3 = (sx, sy, z) toward the sun: z<0 sun behind (backlit rims), z>0 front-lit.
    mist_fade=(y_top, y_bottom): tint toward mist_col increasing downward (ground mist)."""
    path = catmull(np.asarray(path, np.float32), spacing=3.0)
    widths = np.interp(np.linspace(0, 1, len(path)), np.linspace(0, 1, len(widths)),
                       np.asarray(widths, np.float32)).astype(np.float32)
    fr = Frame(path, widths)
    if float(widths.max()) < 9:
        # thin twig/limb: one two-tone stroke (dark body, lit edge on the sun side)
        Lv = np.asarray(light3, np.float32)
        nd = fr.N[len(path) // 2]
        sgn = 1.0 if (nd[0] * Lv[0] + nd[1] * Lv[1]) > 0 else -1.0
        body = mix(bark.dark, bark.mid, 0.4)
        op = np.ones(len(path), np.float32) * opacity
        if end_fade > 0:
            op *= smoothstep(1.0, 1.0 - end_fade, np.linspace(0, 1, len(path)))
        stroke(cv, path if sgn > 0 else path, widths, body, opacity=op, color2=mix(bark.lit, bark.rim, 0.5),
               load2=0.55 if sgn > 0 else 0.0, bristle=0.25, rag=0.15, edge=0.25, rng=rng, smooth=False)
        return fr
    tex = int(rng.integers(0, 32)) if tex is None else tex
    F = tube_fields(cv, path, widths, rag=bark.rag, tex=tex)
    R, TN, S, HW = F['R'], F['TN'], F['S'], F['HW']
    if R.size == 0:
        return fr
    x0, y0 = F['x0'], F['y0']
    hh, ww = R.shape
    inside = R < 1.0
    if not inside.any():
        return fr
    L = np.asarray(light3, np.float32)
    L = L / np.linalg.norm(L)
    sn = np.hypot(L[0], L[1]) + 1e-6
    L2 = L[:2] / sn
    Lz = float(L[2])
    idx = np.clip((S * (len(path) - 1)).astype(int), 0, len(path) - 1)
    Nx, Ny = fr.N[idx, 0], fr.N[idx, 1]
    NdL = Nx * L2[0] + Ny * L2[1]
    v = light_value(TN, NdL, Lz)
    # designed value shapes: 4 bands with a meandering, painterly terminator
    wmax = float(widths.max())
    nb = fbm(hh, ww, max(wmax * 0.8, 20), rng, octaves=3)
    pert = (fbm(hh, ww, max(wmax * 0.35, 10), rng, octaves=3) - 0.5) * 0.22
    vb = v + pert
    e = 0.025
    vq = 0.06 + 0.34 * smoothstep(0.30 - e, 0.30 + e, vb) + 0.32 * smoothstep(0.56 - e, 0.56 + e, vb) \
        + 0.26 * smoothstep(0.80 - e, 0.80 + e, vb)
    vv = np.clip(0.78 * vq + 0.22 * v + 0.05 * (nb - 0.5), 0, 1)
    lab = ramp_lab([bark.dark, bark.mid, bark.lit, bark.rim], vv, [0.0, 0.42, 0.78, 1.0])
    # warm rim on the sun edge, cool reflected light on the far edge
    side = np.sign(NdL)
    rimk = smoothstep(0.80, 0.97, TN * side + pert * 0.5) * np.clip(np.abs(NdL) * 1.4, 0, 1) * rim_amt
    rimk *= np.clip(0.4 - Lz, 0, 1.0) / 0.65
    rimk = np.where(rimk > 0.5, 1.0, rimk * 0.6)
    lab = lab + (oklab(bark.rim) - lab) * (rimk * 0.85)[..., None]
    reflk = smoothstep(0.62, 0.9, -TN * side + pert) * refl_amt
    lab = lab + (oklab(bark.refl) - lab) * (reflk * 0.45)[..., None]
    if bark.blotch is not None:
        bk = smoothstep(0.6, 0.8, nb) * 0.4
        lab = lab + (oklab(mix(bark.blotch, bark.mid, 0.3)) - lab) * (bk * (1 - rimk))[..., None]
    if sky_side:
        lab = lab + (oklab(bark.refl) - lab) * (sky_side * smoothstep(0.2, 1.0, -TN * side) * 0.35)[..., None]
    rgb = np.clip(from_oklab(lab), 0, 1)
    if soft_edge > 0:
        # dry-brush soft edge: a wider ramp broken up by the paper tooth (not a blur)
        from .canvas import PAPER
        ph, pw = PAPER.shape
        yy_ = (np.arange(hh) + y0 - cv.m) % ph
        xx_ = (np.arange(ww) + x0 - cv.m) % pw
        pap = PAPER[yy_[:, None], xx_[None, :]]
        ramp_ = np.clip((1.0 - R) * HW / soft_edge, 0, 1)
        alpha = np.clip(ramp_ * (1.0 + 0.9 * (pap - 0.5)) * 1.1, 0, 1) * (R < 1.0) * opacity
    else:
        alpha = np.clip((1.0 - R) * HW / 1.1, 0, 1) * opacity
    if end_fade > 0:
        alpha *= smoothstep(1.0, 1.0 - end_fade, S)
    if start_fade > 0:
        alpha *= smoothstep(0.0, start_fade, S)
    cv.over_region(x0, y0, rgb, alpha.astype(np.float32))
    vfield = vv

    wmean = float(widths.mean())
    Ltot = fr.L

    def colour_for(t, s, extra=0.0):
        i = np.clip((np.asarray(s) * (len(path) - 1)).astype(int), 0, len(path) - 1)
        ndl = fr.N[i, 0] * L2[0] + fr.N[i, 1] * L2[1]
        # sample the painted value field where possible (keeps strokes on their band)
        pt, _w, _n = fr.at(s, t)
        pt = np.asarray(pt, np.float32).reshape(-1, 2)
        jx = np.clip((pt[:, 0] + cv.m - x0).astype(int), 0, ww - 1)
        jy = np.clip((pt[:, 1] + cv.m - y0).astype(int), 0, hh - 1)
        val = vfield[jy, jx]
        if np.ndim(t) == 0:
            val = val[0]
        val = np.clip(val + extra, 0, 1)
        return ramp_lab([bark.dark, bark.mid, bark.lit, bark.rim], val, [0.0, 0.42, 0.78, 1.0]), val, ndl

    # --- bark strokes following the form
    area = float(inside.sum())
    if wmean > 5 and bark.strokes > 0:
        st = bark.style
        if st == 'cedar':
            Ls, Ws = (1.5, 5.0), (0.015, 0.05)
        elif st == 'beech':
            Ls, Ws = (0.6, 2.0), (0.04, 0.12)
        else:
            Ls, Ws = (0.4, 1.6), (0.018, 0.06)
        nst = int(bark.strokes * detail * area / (wmean * wmean * np.mean(Ls) * np.mean(Ws)) * 3.5)
        nst = min(nst, 9000)
        for _ in range(nst):
            s0 = rng.uniform(0, 1)
            P0, w0, _N = fr.at(s0, 0)
            ln = rng.uniform(*Ls) * w0
            ds = ln / max(Ltot, 1)
            s1 = min(1.0, s0 + ds)
            k = max(4, int(ln / 12))
            ss = np.linspace(s0, s1, k)
            t0 = rng.uniform(-1.0, 1.0)
            tt = t0 + twist * (ss - s0) * Ltot / max(w0, 1) + (noise1d(k, 3, rng) - 0.5) * 0.08
            if np.abs(tt).max() > 1.02:
                good = np.abs(tt) < 1.0
                if good.sum() < 3:
                    continue
                ss, tt = ss[good], tt[good]
            pts, wl, _ = fr.at(ss, tt)
            labc, val, ndl = colour_for(tt.mean(), ss.mean(), extra=rng.normal(0, 0.05))
            lit_side = float(val) > 0.6
            r_ = rng.random()
            if r_ < 0.35:
                labc = lab_shift(labc, dl=rng.uniform(-0.09, -0.03), dc=1.15)
            elif r_ < 0.6:
                labc = lab_shift(labc, dl=rng.uniform(0.02, 0.07), dh=rng.uniform(-0.3, 0.3))
            if bark.blotch is not None and rng.random() < 0.15:
                labc = labc + (oklab(bark.blotch) - labc) * 0.4
            c = np.clip(from_oklab(jitter_lab(labc[None], rng, 0.03, 0.25, 0.15)[0]), 0, 1)
            wst = float(wl.mean()) * rng.uniform(*Ws)
            dry = rng.uniform(0.25, 0.6) if (lit_side and rng.random() < 0.6) else 0.0
            stroke(cv, pts, taper(len(pts), 0.4, 0.15, max(wst, 1.2)), c, opacity=rng.uniform(0.35, 0.85),
                   bristle=rng.uniform(0.4, 0.75), rag=0.25, edge=0.3, dry=dry, drytail=0.5,
                   mode='lock', rng=rng)
    # --- fissures (dark cracks; camphor/cedar)
    if wmean > 6 and bark.fissures > 0:
        nf = int(bark.fissures * detail * (area / (wmean * wmean)) * 22)
        nf = min(nf, 2500)
        for _ in range(nf):
            s0 = rng.uniform(0, 1)
            _, w0, _N = fr.at(s0, 0)
            ln = rng.uniform(0.6, 3.0) * w0
            s1 = min(1.0, s0 + ln / max(Ltot, 1))
            k = max(4, int(ln / 10))
            ss = np.linspace(s0, s1, k)
            t0 = rng.uniform(-0.95, 0.95)
            tt = t0 + twist * (ss - s0) * Ltot / max(w0, 1) + (noise1d(k, 4, rng) - 0.5) * 0.16
            good = np.abs(tt) < 0.98
            if good.sum() < 3:
                continue
            pts, wl, _ = fr.at(ss[good], tt[good])
            labc, val, ndl = colour_for(tt.mean(), ss.mean())
            f = oklab(bark.fissure)
            c = np.clip(from_oklab(labc + (f - labc) * rng.uniform(0.5, 0.9)), 0, 1)
            wf = max(float(wl.mean()) * rng.uniform(0.008, 0.025), 1.0)
            stroke(cv, pts, taper(len(pts), 0.2, 0.1, wf), c, opacity=rng.uniform(0.55, 0.95),
                   bristle=0.3, rag=0.3, edge=0.3, mode='lock', rng=rng)
            # lit lip next to the crack on the sun side
            if float(tt.mean() * np.sign(ndl)) > -0.2 and rng.random() < 0.6:
                off = np.sign(ndl) * 0.025
                pts2, _, _ = fr.at(ss[good], tt[good] + off)
                labl, _, _ = colour_for(tt.mean() + 0.2, ss.mean(), 0.12)
                stroke(cv, pts2, taper(len(pts2), 0.2, 0.1, wf * 1.2),
                       np.clip(from_oklab(labl), 0, 1), opacity=rng.uniform(0.3, 0.6), bristle=0.5,
                       rag=0.3, edge=0.35, mode='lock', rng=rng)
    # --- beech eye marks (short horizontal dark arcs) and lichen
    if bark.eyes > 0 and wmean > 8:
        ne = int(bark.eyes * Ltot / max(wmean, 1) * 2.2)
        for _ in range(ne):
            s0 = rng.uniform(0.05, 1)
            t0 = rng.uniform(-0.75, 0.6)
            tt = np.linspace(t0, t0 + rng.uniform(0.15, 0.4), 6)
            ss = s0 + np.sin(np.linspace(0, np.pi, 6)) * rng.uniform(-0.004, 0.004)
            pts, wl, _ = fr.at(ss, tt)
            labc, _, _ = colour_for(tt.mean(), s0, -0.25)
            stroke(cv, pts, taper(6, 0.3, 0.2, max(float(wl.mean()) * 0.03, 1.2)),
                   np.clip(from_oklab(labc), 0, 1), opacity=0.8, bristle=0.3, rag=0.3,
                   mode='lock', rng=rng)
    if bark.lichen > 0 and wmean > 6:
        nl = int(bark.lichen * area / (wmean * wmean) * 14 * detail)
        if nl > 0:
            ss = rng.uniform(0, 1, nl)
            tt = rng.uniform(-0.95, 0.95, nl)
            pts, wl, _ = fr.at(ss, tt)
            labc, val, _ = colour_for(tt, ss, 0.1)
            lc = oklab(mix(C(206, 212, 196), C(170, 196, 170), rng.uniform(0, 1, nl)[:, None]))
            labc = labc + (lc - labc) * 0.55
            c = np.clip(from_oklab(jitter_lab(labc, rng, 0.03, 0.15, 0.1)), 0, 1)
            dabs(cv, pts[:, 0], pts[:, 1], wl * rng.uniform(0.03, 0.09, nl), c, aspect=rng.uniform(0.5, 1, nl),
                 rag=0.6, edge=0.3, bristle=0.2, opacity=rng.uniform(0.4, 0.8, nl), mode='lock', rng=rng)
    # --- dappled sunlight flecks
    if flecks > 0 and wmean > 6:
        fc = fleck_col if fleck_col is not None else C(255, 194, 96)
        npatch = int(flecks * Ltot / wmean * 0.8) + 1
        for _ in range(npatch):
            s0 = rng.uniform(0.0, 1.0)
            sgn0 = 1.0 if (fr.N[len(path) // 2, 0] * L2[0] + fr.N[len(path) // 2, 1] * L2[1]) > 0 else -1.0
            t0 = rng.uniform(0.1, 0.85) * sgn0
            m = int(rng.integers(6, 18))
            ss = s0 + rng.normal(0, 0.25, m) * wmean / max(Ltot, 1)
            tt = np.clip(t0 + rng.normal(0, 0.1, m), -0.95, 0.95)
            pts, wl, Nn = fr.at(ss, tt)
            labc, val, _ = colour_for(tt, ss, 0.0)
            k = np.clip(0.35 + 0.4 * np.abs(tt), 0.2, 0.8)[:, None]
            labc = labc + (oklab(fc) - labc) * k * 0.6
            c = np.clip(from_oklab(jitter_lab(labc, rng, 0.02, 0.1, 0.05)), 0, 1)
            ang = np.arctan2(fr.T[0, 1], fr.T[0, 0]) + rng.normal(0, 0.3, m)
            dabs(cv, pts[:, 0], pts[:, 1], np.clip(wl * rng.uniform(0.035, 0.1, m), 3, 40), c,
                 aspect=rng.uniform(0.4, 0.8, m), angle=ang, edge=0.35, rag=0.6, bristle=0.25,
                 opacity=rng.uniform(0.5, 0.85, m), mode='lock', rng=rng)
    # --- moss: velvety patches (solid under-layer + textured top, lit on the sun side)
    if moss > 0 and wmean > 4:
        mp = _hazed(moss_pal or MOSS, depth, haze)
        npatch = int(moss * Ltot / wmean * 2.2) + 1
        for _ in range(npatch):
            if rng.random() < moss_base:
                s0 = rng.uniform(0, 0.25) ** 1.4
            else:
                s0 = rng.uniform(0, 1)
            t0 = rng.uniform(-1.0, 0.8)
            ext_s = rng.uniform(0.25, 1.4) * wmean / max(Ltot, 1)
            ext_t = rng.uniform(0.15, 0.6)
            dsz = np.clip(wmean * rng.uniform(0.025, 0.05), 2.0, 22.0)
            area_p = ext_s * Ltot * ext_t * wmean * 0.5
            m = int(np.clip(area_p / (dsz * dsz * 0.25), 12, 5000) * detail)
            # irregular patch: union of 3 gaussian sub-clumps
            cen = rng.integers(0, 3, m)
            offs = rng.normal(0, 1, (3, 2)) * [ext_s * 0.5, ext_t * 0.5]
            ss = s0 + offs[cen, 0] + rng.normal(0, 1, m) * ext_s * 0.35
            tt = t0 + offs[cen, 1] + rng.normal(0, 1, m) * ext_t * 0.35
            ok = (np.abs(tt) < 1.08) & (ss > -0.02) & (ss < 1.0)
            ss, tt = np.clip(ss[ok], 0, 1), tt[ok]
            if len(ss) < 3:
                continue
            pts, wl, Nn = fr.at(ss, tt)
            i = np.clip((ss * (len(path) - 1)).astype(int), 0, len(path) - 1)
            ndl = fr.N[i, 0] * L2[0] + fr.N[i, 1] * L2[1]
            val = light_value(np.clip(tt, -1, 1), ndl, Lz)
            # solid under-layer: a few big soft dabs in the patch's shadow tone
            nu = int(np.clip(ext_s * Ltot / max(dsz * 3, 1), 3, 40))
            iu = rng.integers(0, len(ss), nu)
            ucol = jitter(ramp([mp['dark'], mp['mid'], mp['lit']], np.clip(val[iu] * 0.8, 0, 1)), rng, dl=0.02, dc=0.08, dh=0.04)
            dabs(cv, pts[iu, 0], pts[iu, 1], dsz * rng.uniform(3.0, 5.5, nu), ucol, aspect=rng.uniform(0.5, 0.9, nu),
                 angle=rng.uniform(0, np.pi, nu), rag=0.7, edge=0.25, bristle=0.15, opacity=0.95, rng=rng)
            val = np.where(val > 0.62, 0.9, np.where(val > 0.35, 0.55, 0.25)) * 0.7 + 0.3 * val
            # moss catches light on top of the clump (-T is up the trunk)
            top = (ss - s0) / max(ext_s, 1e-6)
            val = np.clip(val + 0.12 * np.tanh(top) + rng.normal(0, 0.1, len(ss)), 0, 1)
            cols = ramp([mp['dark'], mp['mid'], mp['lit'], mp['tip']], val, [0, 0.38, 0.78, 1.0])
            cols = jitter(cols, rng, dl=0.03, dc=0.12, dh=0.07)
            sz = dsz * rng.uniform(0.6, 1.5, len(ss))
            order = np.argsort(val)
            dabs(cv, pts[order, 0], pts[order, 1], sz[order], cols[order], aspect=rng.uniform(0.5, 0.95, len(ss)),
                 angle=rng.uniform(0, np.pi, len(ss)), rag=0.5, edge=0.3, bristle=0.2,
                 opacity=rng.uniform(0.8, 1.0, len(ss)), rng=rng)
    # --- ivy
    if ivy > 0 and wmean > 8:
        ip = _hazed(ivy_pal or IVY, depth, haze)
        nst = int(ivy * 3) + (1 if rng.random() < ivy * 3 % 1 else 0)
        for _ in range(max(nst, 1)):
            s0 = rng.uniform(0, 0.15)
            s1 = min(1.0, s0 + rng.uniform(0.25, 0.75) * ivy * 1.5)
            k = int((s1 - s0) * Ltot / 8) + 6
            ss = np.linspace(s0, s1, k)
            t0 = rng.uniform(-0.8, 0.6)
            tt = t0 + np.cumsum(rng.normal(0, 0.05, k)) + np.sin(ss * Ltot / wmean * rng.uniform(0.6, 1.6)) * 0.25
            vis = np.abs(tt) < 0.97
            pts, wl, _ = fr.at(ss, np.clip(tt, -0.97, 0.97))
            stem = np.clip(mix(ip['dark'], C(110, 96, 80), 0.45), 0, 1)
            # stem segments (only visible parts)
            runs = np.split(np.arange(k), np.nonzero(np.diff(vis.astype(int)))[0] + 1)
            for rr in runs:
                if len(rr) > 2 and vis[rr[0]]:
                    stroke(cv, pts[rr], max(wmean * 0.006, 1.2), stem, opacity=0.6, bristle=0.3,
                           rag=0.2, rng=rng)
            # leaf clusters
            nlc = int(k * rng.uniform(0.35, 0.6))
            # leaves gather in clumps along the stem with bare stretches between
            dens = noise1d(k, max(3, k // 14), rng) ** 4.0 + 1e-4
            j = rng.choice(k, nlc, p=dens / dens.sum())
            j = j[vis[j]]
            if len(j) == 0:
                continue
            m = len(j) * 3
            jj = np.repeat(j, 3)
            leafL = np.clip(wl[jj] * rng.uniform(0.05, 0.1, m), 4.0, 34.0)
            ang = rng.uniform(0, 2 * np.pi, m)
            px = pts[jj, 0] + np.cos(ang) * leafL * 0.45
            py = pts[jj, 1] + np.sin(ang) * leafL * 0.45
            i = np.clip((ss[jj] * (len(path) - 1)).astype(int), 0, len(path) - 1)
            ndl = fr.N[i, 0] * L2[0] + fr.N[i, 1] * L2[1]
            val = light_value(np.clip(tt[jj], -1, 1), ndl, Lz) + rng.normal(0, 0.15, m) + \
                0.15 * (np.cos(ang) * L2[0] + np.sin(ang) * L2[1])
            cols = ramp([ip['dark'], ip['mid'], ip['lit'], ip['gloss']], np.clip(val, 0, 1), [0, 0.4, 0.8, 1.0])
            cols = jitter(cols, rng, dl=0.03, dc=0.1, dh=0.06)
            order = np.argsort(val)
            dabs(cv, px[order], py[order], leafL[order], cols[order], aspect=rng.uniform(0.6, 0.85, m),
                 angle=ang[order], shape='petal', edge=0.22, rag=0.2, bristle=0.1, split=0.12, rng=rng)
    # --- aerial / ground mist on the tube region (alpha-locked tint)
    if mist_fade is not None and mist_col is not None:
        yt, yb = mist_fade
        d = cv.img[y0:y0 + hh, x0:x0 + ww]
        yy = (np.arange(hh, dtype=np.float32) + y0 - cv.m)[:, None]
        k = smoothstep(yt, yb, yy) * 0.85
        k = np.broadcast_to(k, (hh, ww))[..., None]
        d[..., :3] += (np.asarray(mist_col, np.float32) * d[..., 3:4] - d[..., :3]) * k
    return fr


def trunk_path(rng, base, top, w_base, w_top, sway=0.03, bulge=0.06, flare=0.0, flare_h=0.08,
               n=40, lean_curve=0.0):
    """Centreline from base to top with smooth sway, width profile with bulges and a
    buttress flare near the base. Returns (pts (n,2), widths (n,))."""
    base = np.asarray(base, np.float32)
    top = np.asarray(top, np.float32)
    t = np.linspace(0, 1, n, dtype=np.float32)
    H = float(np.hypot(*(top - base)))
    pts = base[None] * (1 - t[:, None]) + top[None] * t[:, None]
    d = (top - base) / max(H, 1)
    nrm = np.array([-d[1], d[0]], np.float32)
    off = (noise1d(n, 3, rng) - 0.5) * 2 * sway * H + (noise1d(n, 7, rng) - 0.5) * sway * 0.35 * H
    off += lean_curve * H * np.sin(np.pi * t)
    off -= off[0]
    pts = pts + nrm[None] * off[:, None]
    w = w_base + (w_top - w_base) * t ** 0.7
    w = w * (1 + (noise1d(n, 6, rng) - 0.5) * 2 * bulge)
    if flare > 0:
        w = w * (1 + flare * np.exp(-t / max(flare_h, 1e-3)))
    return pts, w.astype(np.float32)


def buttress_roots(rng, frame, n, ground_y, w_base, spread=1.4, side_bias=0.0):
    """Root tubes from the trunk's lower flanks down and out to the ground."""
    roots = []
    sides = np.linspace(-1, 1, n) + rng.normal(0, 0.15, n) + side_bias
    for sd in sides:
        s0 = rng.uniform(0.02, 0.09)
        t0 = float(np.clip(sd * 0.75, -0.95, 0.95))
        p0, w0, N0 = frame.at(s0, t0)
        p0 = np.asarray(p0, np.float32)
        reach = w_base * rng.uniform(0.35, 1.0) * spread * (0.4 + 0.6 * abs(sd))
        x1 = p0[0] + np.sign(sd if sd != 0 else 1) * reach
        y1 = ground_y + rng.uniform(-0.02, 0.06) * w_base + (1 - abs(sd)) * 0.12 * w_base
        mid = np.array([p0[0] + (x1 - p0[0]) * 0.45, p0[1] + (y1 - p0[1]) * 0.75 + rng.normal(0, 0.03) * w_base])
        pts = catmull(np.array([p0, mid, [x1, y1]], np.float32), n=24)
        wr = w_base * rng.uniform(0.18, 0.32) * (1 - 0.82 * np.linspace(0, 1, 24) ** 0.8)
        roots.append((pts, wr.astype(np.float32), sd))
    return roots


def crown_blobs(rng, tips, sizes, blobs=None, sun2=(0.6, -0.8), light=1.0, hue=0.0, val=0.0,
                per_tip=(3, 7), spread=0.9, flatten=0.75, lumpy=0.14, scale_jit=0.35,
                under_dark=0.0):
    """Clusters around limb tips. tips (K,2), sizes (K,) cluster radii.
    Clusters on the sun side of each tip get more light."""
    if blobs is None:
        blobs = Blobs()
    sx, sy = sun2
    items = []
    for (tx, ty), r in zip(tips, sizes):
        k = int(rng.integers(*per_tip))
        for _ in range(k):
            ox, oy = rng.normal(0, spread * r, 2)
            oy *= flatten
            rr = r * rng.uniform(1 - scale_jit, 1 + scale_jit * 0.6)
            lt = light * (0.8 + 0.35 * np.clip((ox * sx + oy * sy) / (r + 1e-6), -1, 1)) * rng.uniform(0.85, 1.1)
            z = -(oy) + rng.normal(0, r * 0.3)      # lower clusters in front
            items.append((z, tx + ox, ty + oy, rr, rr * rng.uniform(0.62, 0.85), rng.normal(0, 0.3), lt,
                          hue + rng.normal(0, 0.04), val + rng.normal(0, 0.04) - under_dark * (oy > 0)))
    items.sort(key=lambda it: it[0])
    for z, x, y, rx, ry, rot, lt, hh, vv in items:
        blobs.add(x, y, rx, ry, rot=rot, light=lt, hue=hh, val=vv, rng=rng, lumpy=lumpy)
    return blobs


def limb_fan(rng, origin, angles, lengths, widths, levels=2, split=(1, 3), curl=0.25, droop=0.0):
    """Branch skeleton: returns limbs [(pts, widths)], tips [(x, y)], tip_widths."""
    limbs, tips, tw = [], [], []

    def grow(p0, ang, ln, w0, lvl):
        k = 8
        pts = [np.asarray(p0, np.float32)]
        a = ang
        for i in range(k):
            a += rng.normal(0, 0.12) + curl * rng.normal(0, 0.3) / k
            a += droop * 0.05 * np.cos(a) * (lvl + 1)
            pts.append(pts[-1] + (ln / k) * np.array([np.cos(a), np.sin(a)], np.float32))
        pts = np.array(pts)
        wprof = w0 * (1 - 0.55 * np.linspace(0, 1, k + 1))
        limbs.append((pts, wprof.astype(np.float32), lvl))
        if lvl >= levels:
            tips.append(pts[-1])
            tw.append(wprof[-1])
            return
        ns = int(rng.integers(split[0], split[1] + 1))
        for j in range(ns):
            at = rng.uniform(0.55, 1.0)
            i = min(int(at * k), k)
            sub_a = a + rng.uniform(-0.7, 0.7)
            grow(pts[i], sub_a, ln * rng.uniform(0.45, 0.7), wprof[i] * rng.uniform(0.55, 0.75), lvl + 1)
        tips.append(pts[-1])
        tw.append(wprof[-1])

    for a, ln, w in zip(angles, lengths, widths):
        grow(origin, a, ln, w, 0)
    return limbs, np.array(tips, np.float32), np.array(tw, np.float32)
