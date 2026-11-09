"""foliage.py - foliage masses painted from a cluster G-buffer.

A mass is a set of lumpy ellipsoid "clusters" (Blobs). They are rendered back to
front into a G-buffer (coverage, dome shading toward the sun, cluster id, radius),
then painted like a gouache painter would: a flat block-in of 3 value shapes,
leaf dabs sorted dark -> light (each lit cluster top ends up as a crisp shape of
small leaves), leafy broken edges, translucent / rim-lit leaves toward the sun.
Also: leaf sprays, hanging vines.
"""
import numpy as np
import cv2

from .canvas import dabs, stroke, catmull, normals, taper
from .color import ramp, ramp_lab, from_oklab, jitter_lab, lab_shift, oklab, mix, jitter, C
from .noise import fbm, noise1d


class Blobs:
    """Accumulates clusters. Order of add() = painter's order (far first)."""

    def __init__(self):
        self.d = {k: [] for k in ('x', 'y', 'rx', 'ry', 'rot', 'light', 'hue', 'val', 'ph', 'amp', 'frq')}

    def add(self, x, y, rx, ry=None, rot=0.0, light=1.0, hue=0.0, val=0.0, rng=None,
            lumpy=0.13, lobes=None):
        rng = rng or np.random.default_rng(int(x * 13 + y * 7) & 0xffff)
        ry = rx if ry is None else ry
        d = self.d
        d['x'].append(x); d['y'].append(y); d['rx'].append(rx); d['ry'].append(ry)
        d['rot'].append(rot); d['light'].append(light); d['hue'].append(hue); d['val'].append(val)
        lo = int(rng.integers(3, 7)) if lobes is None else lobes
        d['frq'].append([lo, lo + 2 + int(rng.integers(0, 3)), lo * 2 + 3 + int(rng.integers(0, 4)), 17])
        d['amp'].append([lumpy * rng.uniform(0.6, 1.2), lumpy * rng.uniform(0.3, 0.6),
                         lumpy * rng.uniform(0.15, 0.35), lumpy * 0.12])
        d['ph'].append(list(rng.uniform(0, 2 * np.pi, 4)))

    def __len__(self):
        return len(self.d['x'])

    def extend(self, other):
        for k in self.d:
            self.d[k].extend(other.d[k])

    def arrays(self):
        f = lambda k, dt=np.float32: np.ascontiguousarray(np.asarray(self.d[k], dt))
        return dict(x=f('x'), y=f('y'), rx=f('rx'), ry=f('ry'), rot=f('rot'), light=f('light'),
                    hue=f('hue'), val=f('val'), ph=f('ph'), amp=f('amp'), frq=f('frq', np.float32))


def render_gbuffer(cv, blobs, light3=(0.55, -0.7, 0.45), wrap=0.35, under=0.35):
    """Render Blobs into a G-buffer the size of the canvas buffer."""
    from .kernels import k_blobs
    h, w = cv.shape
    cov = np.zeros((h, w), np.float32)
    sh = np.zeros((h, w), np.float32)
    cid = np.full((h, w), -1, np.int32)
    rad = np.ones((h, w), np.float32)
    if len(blobs) == 0:
        return dict(cov=cov, shade=sh, cid=cid, rad=rad, b=blobs.arrays())
    L = np.asarray(light3, np.float32)
    L = L / np.linalg.norm(L)
    b = blobs.arrays()
    k_blobs(cov, sh, cid, rad, float(cv.m), float(cv.m), b['x'], b['y'], b['rx'], b['ry'], b['rot'],
            b['ph'], b['amp'], b['frq'], b['light'], float(L[0]), float(L[1]), float(L[2]),
            float(wrap), float(under))
    return dict(cov=cov, shade=sh, cid=cid, rad=rad, b=b)


def _sample_inside(mask_bool, n, rng, bbox):
    """n random pixel positions (buffer coords) where mask_bool is True (rejection)."""
    x0, y0, x1, y1 = bbox
    out_x, out_y = [], []
    need = n
    tries = 0
    while need > 0 and tries < 8:
        m = int(need * 2.2) + 64
        xs = rng.integers(x0, x1, m)
        ys = rng.integers(y0, y1, m)
        ok = mask_bool[ys, xs]
        out_x.append(xs[ok][:need]); out_y.append(ys[ok][:need])
        need -= int(min(ok.sum(), need))
        tries += 1
    if not out_x:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    return np.concatenate(out_x), np.concatenate(out_y)


def paint_mass(cv, G, rng, stops, pos=None, leaf=10.0, density=1.0, aspect=0.5, shape='leaf',
               vnoise=0.14, hue_var=0.06, sun2=(0.6, -0.8), trans=None, trans_amt=0.0,
               rim=None, rim_amt=0.0, tip=None, tip_amt=0.15, edge_leaves=1.0,
               underpaint=True, droop=0.35, size_dark=1.35, size_lit=0.75, bristle=0.2, rag=0.3,
               edge=0.28, split=0.08, bands=3, region=None, opacity=1.0, fringe=1.0,
               lit_cut=None, jit=(0.03, 0.08, 0.05), mode='over', orient='radial', rim_vary=0.0):
    """Paint the clusters of G with leaf dabs.

    stops/pos   value ramp (0 = deepest shadow .. 1 = sunlit top).
    leaf        leaf dab length in px.     density  dab count multiplier.
    trans       colour of sun-through leaves (backlight) near the sun-side edges.
    rim         rim colour along silhouette edges facing the sun (sun2 direction).
    tip         extra highlight colour for the brightest leaves.
    fringe      how far edge leaves stick out (in leaf lengths).
    """
    cov, sh, cid, rad, b = G['cov'], G['shade'], G['cid'], G['rad'], G['b']
    h, w = cov.shape
    if region is None:
        ys, xs = np.nonzero(cov > 0.02)
        if len(xs) == 0:
            return
        region = (max(int(xs.min()) - 2, 0), max(int(ys.min()) - 2, 0),
                  min(int(xs.max()) + 3, w), min(int(ys.max()) + 3, h))
    x0, y0, x1, y1 = region
    sub = (slice(y0, y1), slice(x0, x1))
    c = cov[sub]
    hh, ww = c.shape
    # value field: dome shading + per-cluster value offset + painterly noise
    nv = fbm(hh, ww, max(leaf * 9, 24), rng, octaves=3) - 0.5
    nv2 = fbm(hh, ww, max(leaf * 2.5, 8), rng, octaves=2) - 0.5
    cidr = cid[sub]
    valoff = np.where(cidr >= 0, b['val'][np.maximum(cidr, 0)], 0).astype(np.float32)
    v = np.clip(sh[sub] + valoff + vnoise * nv + vnoise * 0.5 * nv2, 0, 1)
    hue = np.where(cidr >= 0, b['hue'][np.maximum(cidr, 0)], 0).astype(np.float32)
    # outward normal of the silhouette (for edge leaves / rims)
    cb = cv2.GaussianBlur(c, (0, 0), max(leaf * 0.6, 1.5))
    gx = cv2.Sobel(cb, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(cb, cv2.CV_32F, 0, 1, ksize=3)
    gn = np.hypot(gx, gy) + 1e-6
    nx, ny = -gx / gn, -gy / gn
    sx, sy = sun2
    sn = np.hypot(sx, sy)
    sx, sy = sx / sn, sy / sn
    facing = np.clip(nx * sx + ny * sy, 0, 1)                  # edge faces the sun
    edgeness = np.clip(1 - np.abs(cb - 0.5) * 2.2, 0, 1)        # near the silhouette
    labs = None

    def colour_at(px, py, extra=0.0, sat=1.0):
        vv = np.clip(v[py, px] + extra, 0, 1)
        lab = ramp_lab(stops, vv, pos)
        lab = lab_shift(lab, dh=0.0)
        hh_ = hue[py, px]
        L = lab[:, 0]
        a, bb = lab[:, 1], lab[:, 2]
        ch = np.hypot(a, bb) * sat
        ang = np.arctan2(bb, a) + hh_
        lab = np.stack([L, ch * np.cos(ang), ch * np.sin(ang)], 1)
        lab = jitter_lab(lab, rng, *jit)
        return lab, vv

    def finish(lab, px, py, vv, edge_w):
        # translucency / rim toward the sun near edges
        if trans is not None and trans_amt > 0:
            k = trans_amt * facing[py, px] * edge_w * np.clip(0.3 + vv, 0, 1)
            lab = lab + (oklab(trans)[None, :] - lab) * np.clip(k, 0, 1)[:, None]
        return np.clip(from_oklab(lab), 0, 1)

    # 1. block-in: value shapes in `bands` flat-ish tones, eroded so edges are leaves
    if underpaint:
        core = (c > 0.5).astype(np.uint8)
        er = max(int(leaf * 0.35), 1)
        core = cv2.erode(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * er + 1, 2 * er + 1)))
        a = cv2.GaussianBlur(core.astype(np.float32), (0, 0), 0.8)
        q = np.floor(np.clip(v * 0.85 + 0.02, 0, 0.999) * bands) / max(bands - 1, 1) * 0.72
        if orient == 'tangent':
            # clouds: keep more of the soft form under the strokes
            q = 0.5 * q + 0.5 * np.clip(v * 0.9, 0, 1)
        q = cv2.GaussianBlur(q.astype(np.float32), (0, 0), max(leaf * 0.3, 1.0))
        rgb = ramp(stops, q, pos)
        d = cv.img[sub]
        A = (a * opacity)[..., None]
        if mode == 'over':
            d *= (1 - A)
            d[..., :3] += A * rgb
            d[..., 3:4] += A
        else:
            AA = A * d[..., 3:4]
            d[..., :3] = d[..., :3] * (1 - A) + AA * rgb
    # 2. body leaves, dark -> light
    area = float((c > 0.4).sum())
    n = int(density * area / (leaf * leaf * aspect * 0.55) * 1.6)
    if n > 0:
        px, py = _sample_inside(c > 0.4, n, rng, (0, 0, ww, hh))
        lab, vv = colour_at(px, py)
        if lit_cut is not None:
            keep = vv < lit_cut[1]
            keep |= rng.random(len(vv)) < lit_cut[0]
            px, py, lab, vv = px[keep], py[keep], lab[keep], vv[keep]
        cidp = cidr[py, px]
        bx = np.where(cidp >= 0, b['x'][np.maximum(cidp, 0)] + cv.m - x0, px)
        by = np.where(cidp >= 0, b['y'][np.maximum(cidp, 0)] + cv.m - y0, py)
        radial = np.arctan2(py - by, px - bx)
        if orient == 'tangent':
            radial = radial + np.pi / 2
        elif orient == 'horizontal':
            radial = np.zeros_like(radial)
        ang = radial + droop * np.angle(np.exp(1j * (np.pi / 2 - radial))) + rng.normal(0, 0.45 if orient == 'radial' else 0.25, len(px))
        size = leaf * rng.uniform(0.75, 1.3, len(px)) * (size_dark + (size_lit - size_dark) * vv)
        cols = finish(lab, px, py, vv, edgeness[py, px])
        order = np.argsort(vv + rng.normal(0, 0.03, len(vv)))
        dabs(cv, (px + x0 - cv.m)[order], (py + y0 - cv.m)[order], size[order], cols[order],
             aspect=rng.uniform(aspect * 0.8, aspect * 1.2, len(px))[order], angle=ang[order],
             shape=shape, edge=edge, rag=rag, bristle=bristle, split=split, opacity=opacity,
             rng=rng, mode=mode)
    # 3. edge leaves: stick out of the silhouette, oriented outward
    if edge_leaves > 0:
        band = (cb > 0.12) & (cb < 0.75)
        ne = int(edge_leaves * band.sum() / (leaf * 1.1))
        if ne > 0:
            px, py = _sample_inside(band, ne, rng, (0, 0, ww, hh))
            ne = len(px)
            onx, ony = nx[py, px], ny[py, px]
            # colour from slightly inside
            ix = np.clip((px - onx * leaf * 0.8).astype(int), 0, ww - 1)
            iy = np.clip((py - ony * leaf * 0.8).astype(int), 0, hh - 1)
            lab, vv = colour_at(ix, iy, extra=0.04)
            out = leaf * fringe * rng.uniform(0.0, 0.55, ne)
            fx = px + onx * out
            fy = py + ony * out
            ang = np.arctan2(ony, onx) + rng.normal(0, 0.6, ne) + (np.pi / 2 if orient == 'tangent' else 0.0)
            ang = ang + droop * 0.5 * np.angle(np.exp(1j * (np.pi / 2 - ang)))
            cols = finish(lab, ix, iy, vv, np.ones(ne, np.float32))
            order = np.argsort(vv)
            dabs(cv, (fx + x0 - cv.m)[order], (fy + y0 - cv.m)[order],
                 (leaf * rng.uniform(0.7, 1.15, ne))[order], cols[order],
                 aspect=aspect * rng.uniform(0.75, 1.1, ne)[order], angle=ang[order], shape=shape,
                 edge=edge, rag=rag * 0.8, bristle=bristle, split=split, opacity=opacity, rng=rng,
                 mode=mode)
    # 4. sun rim along edges that face the sun
    if rim is not None and rim_amt > 0:
        if rim_vary > 0:
            # per-cluster rim: some clusters unlit, others thin or broad, the rim's colour and the
            # part of the edge it sits on (rotated facing direction) change from clump to clump
            nb_ = len(b['x'])
            rr_ = np.random.default_rng(int(rng.integers(1 << 30)))
            k_on = rr_.random(nb_) > 0.35 * rim_vary
            k_w = rr_.uniform(0.5, 1.6, nb_)
            k_rot = rr_.normal(0, 0.55 * rim_vary, nb_)
            k_hue = rr_.uniform(0, 1, nb_)
            cidr_ = np.maximum(cidr, 0)
            rot_ = k_rot[cidr_]
            sx2, sy2 = sx * np.cos(rot_) - sy * np.sin(rot_), sx * np.sin(rot_) + sy * np.cos(rot_)
            facing_r = np.clip(nx * sx2 + ny * sy2, 0, 1)
            thr = 0.55 - 0.45 * np.clip(k_w[cidr_] - 0.5, 0, 1.1) / 1.1
            band = (cb > 0.22) & (cb < 0.45 + 0.3 * k_w[cidr_] / 1.6) & (facing_r > thr) & k_on[cidr_] & (cidr >= 0)
        else:
            band = (cb > 0.25) & (cb < 0.7) & (facing > 0.35)
        nr = int(rim_amt * band.sum() / (leaf * (0.6 if rim_vary > 0 else 0.9)))
        if nr > 0:
            px, py = _sample_inside(band, nr, rng, (0, 0, ww, hh))
            nr = len(px)
            f = facing[py, px]
            if rim_vary > 0:
                hk = k_hue[np.maximum(cidr[py, px], 0)]
                base_rim = ramp([C(255, 236, 190), np.asarray(rim, np.float32), C(250, 170, 120)], hk)
                cols = jitter(base_rim, rng, dl=0.04, dc=0.1, dh=0.04)
                f = np.maximum(f, 0.4)
            else:
                cols = jitter(np.broadcast_to(rim, (nr, 3)), rng, dl=0.04, dc=0.1, dh=0.06)
            onx, ony = nx[py, px], ny[py, px]
            ang = np.arctan2(ony, onx) + rng.normal(0, 0.7, nr)
            dabs(cv, px + x0 - cv.m + onx * leaf * 0.2, py + y0 - cv.m + ony * leaf * 0.2,
                 leaf * rng.uniform(0.45, 0.85, nr), cols, aspect=aspect, angle=ang, shape=shape,
                 edge=edge * 0.8, rag=rag * 0.6, bristle=bristle * 0.5,
                 opacity=np.clip(0.55 + 0.45 * f, 0, 1) * opacity, rng=rng, mode=mode)
    # 5. tips: brightest leaves get a warm highlight
    if tip is not None and tip_amt > 0:
        lit = (c > 0.5) & (v > 0.78)
        nt = int(tip_amt * density * lit.sum() / (leaf * leaf * 0.6))
        if nt > 0:
            px, py = _sample_inside(lit, nt, rng, (0, 0, ww, hh))
            nt = len(px)
            vv = v[py, px]
            cols = jitter(mix(stops[-1], tip, np.clip((vv - 0.78) / 0.22, 0, 1)[:, None]), rng,
                          dl=0.03, dc=0.1, dh=0.05)
            dabs(cv, px + x0 - cv.m, py + y0 - cv.m, leaf * rng.uniform(0.45, 0.8, nt), cols,
                 aspect=aspect, angle=rng.uniform(0, np.pi * 2, nt), shape=shape, edge=edge * 0.8,
                 rag=rag * 0.6, bristle=bristle * 0.5, opacity=opacity, rng=rng, mode=mode)


def spray(cv, x, y, ang, length, leaf, cols_dark, cols_lit, rng, n_leaves=None, sun2=(0.6, -0.8),
          droop=0.5, stem_col=None, width=None, curl=0.4, shape='leaf', opacity=1.0, aspect=0.42, rim=None):
    """A leafy twig: a bending stem with 1-3 side twigs; leaves gather in irregular
    clusters toward the twig ends (not a regular fishbone), sizes and angles vary,
    most leaves stay in the dark body colour, the ones facing the sun catch light,
    and an optional rim colour lights their sun-side edges."""
    def twig(x0, y0, a0, L, depth):
        pts = [np.array([x0, y0], np.float32)]
        a = a0
        k = 7
        for i in range(k):
            a += curl / k + rng.normal(0, 0.14) + droop * 0.06 * np.cos(a)
            pts.append(pts[-1] + (L / k) * np.array([np.cos(a), np.sin(a)], np.float32))
        return catmull(np.array(pts), n=40)
    twigs = [twig(x, y, ang, length, 0)]
    for j in range(int(rng.integers(1, 4))):
        P0 = twigs[0]
        i = int(rng.integers(len(P0) // 4, len(P0) - 6))
        t0 = np.gradient(P0, axis=0)[i]
        a0 = np.arctan2(t0[1], t0[0]) + rng.choice([-1, 1]) * rng.uniform(0.4, 0.9)
        twigs.append(twig(P0[i, 0], P0[i, 1], a0, length * rng.uniform(0.35, 0.6), 1))
    if stem_col is not None:
        for j, P in enumerate(twigs):
            stroke(cv, P, taper(len(P), 1.0, 0.15, (width or max(leaf * 0.12, 1.2)) * (1 if j == 0 else 0.6)),
                   stem_col, bristle=0.2, rag=0.1, opacity=opacity, rng=rng)
    sx, sy = sun2
    xs, ys, angs, Ls = [], [], [], []
    for j, P in enumerate(twigs):
        n = int((n_leaves or max(6, length / (leaf * 0.5))) * (1.0 if j == 0 else 0.5))
        t = 1 - rng.random(n) ** 1.8                  # bunched toward the tip
        t = np.clip(t * 0.85 + 0.12, 0, 1)
        idx = np.clip((t * (len(P) - 1)).astype(int), 0, len(P) - 1)
        tang = np.gradient(P, axis=0)[idx]
        ta = np.arctan2(tang[:, 1], tang[:, 0])
        la = ta + rng.choice([-1, 1], n) * rng.uniform(0.25, 1.5, n) + rng.normal(0, 0.3, n)
        la = la + droop * 0.35 * np.angle(np.exp(1j * (np.pi / 2 - la)))
        L = leaf * rng.uniform(0.55, 1.45, n) * (0.75 + 0.35 * t)
        xs.append(P[idx, 0] + np.cos(la) * L * 0.5)
        ys.append(P[idx, 1] + np.sin(la) * L * 0.5)
        angs.append(la)
        Ls.append(L)
    xs, ys, la, L = (np.concatenate(v) for v in (xs, ys, angs, Ls))
    n = len(xs)
    face = np.cos(la) * sx + np.sin(la) * sy
    lit = np.clip(0.2 + 0.55 * np.maximum(face, 0) ** 1.5 + rng.normal(0, 0.12, n), 0, 1)
    cols = jitter(mix(cols_dark, cols_lit, lit[:, None]), rng, dl=0.03, dc=0.1, dh=0.06)
    order = np.argsort(lit)
    dabs(cv, xs[order], ys[order], L[order], cols[order], aspect=(aspect * rng.uniform(0.75, 1.3, n))[order],
         angle=la[order], shape=shape, edge=0.25, rag=0.25, bristle=0.2, split=0.12, opacity=opacity, rng=rng)
    if rim is not None:
        k = face > 0.35
        if k.any():
            ox = np.cos(la[k] + np.pi / 2) * L[k] * 0.12 * np.sign(face[k])
            dabs(cv, xs[k] + sx * L[k] * 0.12, ys[k] + sy * L[k] * 0.12, L[k] * 0.8,
                 jitter(np.broadcast_to(rim, (int(k.sum()), 3)), rng, dl=0.03), aspect=aspect * 0.5, angle=la[k],
                 shape=shape, edge=0.3, rag=0.2, opacity=0.8 * opacity, rng=rng)


def vine(cv, x, y, length, rng, stem, leaf_dark, leaf_lit, leaf=9.0, width=2.5, sway=0.06,
         density=1.0, sun2=(0.6, -0.8), opacity=1.0, curtain=False):
    """Hanging vine: a drooping stem with leaf pairs and little side sprigs."""
    n = 18
    xs = x + np.cumsum(rng.normal(0, length * sway / 4, n)) + np.sin(np.linspace(0, rng.uniform(1, 3), n)) * length * sway
    ys = y + np.linspace(0, length, n) ** 1.0
    P = catmull(np.stack([xs, ys], 1), spacing=2.0)
    stroke(cv, P, taper(len(P), 1.0, 0.3, width), stem, bristle=0.2, rag=0.15, opacity=opacity, rng=rng)
    k = int(length / (leaf * 0.55) * density) + 3
    t = np.sort(rng.uniform(0.02, 1.0, k))
    idx = np.clip((t * (len(P) - 1)).astype(int), 0, len(P) - 1)
    side = np.where(rng.random(k) < 0.5, 1.0, -1.0)
    la = np.pi / 2 + side * rng.uniform(0.35, 1.3, k)
    L = leaf * rng.uniform(0.7, 1.3, k) * (1.0 - 0.35 * t)
    cx = P[idx, 0] + np.cos(la) * L * 0.5
    cy = P[idx, 1] + np.sin(la) * L * 0.5
    sx, sy = sun2
    lit = np.clip(0.45 + 0.6 * (np.cos(la) * sx + np.sin(la) * sy) * 0.5 + rng.normal(0, 0.22, k), 0, 1)
    cols = jitter(mix(leaf_dark, leaf_lit, lit[:, None]), rng, dl=0.03, dc=0.08, dh=0.06)
    dabs(cv, cx, cy, L, cols, aspect=0.48, angle=la, shape='leaf', edge=0.25, rag=0.2, bristle=0.15,
         split=0.1, opacity=opacity, rng=rng)
