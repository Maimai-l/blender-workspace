"""Render a bird drawing (pose -> RGBA cel) and composite it onto a canvas."""
import numpy as np
import cv2
from . import raster as R
from .model import (build_rig, CM_PER_UNIT, rx, ry, rz, D, side_z, catmull, EYE_A, RING_A, EYE_DIR,
                    FW_OUTLINE)
from .palette import build_palette, Z, INK
from .shade import shade_core


class Light:
    """Screen-space light.  dir: 2D direction *toward* the light (x right, y up);
    depth: +1 light from the camera side, 0 side light, -1 backlight.
    rim: warm rim on the lit edge (default on when backlit)."""

    def __init__(self, dir=(0.55, 0.85), depth=0.35, rim=None, bias=0.06, rim_width=0.48,
                 shadow_mul=None, rim_color=None, highlight=True):
        d = np.asarray(dir, float)
        d = d / (np.linalg.norm(d) + 1e-9)
        dep = float(np.clip(depth, -0.97, 0.97))
        self.v = np.array([d[0] * np.sqrt(1 - dep * dep), d[1] * np.sqrt(1 - dep * dep), dep])
        self.rim = (dep < -0.12) if rim is None else bool(rim)
        self.bias, self.rim_width = bias, rim_width
        self.shadow_mul, self.rim_color, self.highlight = shadow_mul, rim_color, highlight

    def key(self):
        return (tuple(np.round(self.v, 3)), self.rim, self.bias, self.rim_width,
                None if self.shadow_mul is None else tuple(self.shadow_mul),
                None if self.rim_color is None else tuple(self.rim_color))


DEFAULT_LIGHT = Light()
_PAL = {}
_TEX = {}


def palette_for(light, overrides=None):
    k = (light.key(), None if overrides is None else tuple(sorted(overrides.items())))
    if k not in _PAL:
        _PAL[k] = build_palette(light.shadow_mul, light.rim_color, overrides=overrides)
    return _PAL[k]


def detail_for(scale):
    if scale >= 90:
        return 'full'
    if scale >= 40:
        return 'mid'
    if scale >= 18:
        return 'low'
    return 'tiny'


# ----------------------------------------------------------------------------- decal texture
TEX_X0, TEX_X1, TEX_Y0, TEX_Y1, TEX_RES = -4.8, 2.2, -2.4, 2.4, 0.012


def wing_texture(fw):
    key = tuple(np.round(fw['outline'].ravel(), 3))
    if key in _TEX:
        return _TEX[key]
    W = int((TEX_X1 - TEX_X0) / TEX_RES) + 1
    H = int((TEX_Y1 - TEX_Y0) / TEX_RES) + 1
    tex = np.zeros((H, W, 6), np.float32)
    for ch, name in enumerate(('outline', 'coverts', 'tertial')):
        m = np.zeros((H * 4, W * 4), np.uint8)
        pts = np.asarray(fw[name])
        if name == 'outline':
            pts = catmull(pts, 6, closed=True)
        uv = np.stack([(pts[:, 0] - TEX_X0) / TEX_RES, (TEX_Y1 - pts[:, 1]) / TEX_RES], 1)
        R.fill_polys(m, [uv], 4, 1)
        cov = R.coverage(m[:H * 4, :W * 4], 4)
        tex[:, :, ch] = cov
        tex[:, :, ch + 3] = cov
    if len(_TEX) > 64:
        _TEX.clear()
    _TEX[key] = tex
    return tex


# ----------------------------------------------------------------------------- helpers
def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def contour_ink(buf, mask_ss, ss, wbase, L, wmin=0.55, sigma=1.3, min_area=0.6):
    hd = np.array([-L[0], L[1] + 0.5])
    hd /= np.linalg.norm(hd) + 1e-9
    for c in R.mask_contours(mask_ss, ss):
        p = R.resample_closed(c, 0.5)
        if len(p) < 6:
            continue
        p = R.smooth_closed(p, sigma)
        n, area = R.closed_normals(p)
        if abs(area) < min_area:
            continue
        heavy = _smoothstep(-0.55, 0.85, n @ hd)
        w = wbase * (wmin + (1.22 - wmin) * heavy)
        # ink pooling at concave corners (where shapes tuck under each other)
        tu = R.turning(p) * (1.0 if area > 0 else -1.0)      # > 0 convex, < 0 concave
        k = max(1, int(round(4.0 / 0.5)))
        if len(tu) > 2 * k + 2:
            ker = np.hanning(2 * k + 3)[1:-1]
            ker /= ker.sum()
            conc = np.convolve(np.concatenate([tu[-k:], tu, tu[:k]]), ker, mode='same')[k:-k]
            w = w * (1.0 + 0.35 * np.clip(-conc / 0.10, 0.0, 1.0))
        R.stroke_poly(buf, p[:, 0].copy(), p[:, 1].copy(), (w * 0.5).astype(np.float64), True)


def open_stroke(buf, pts, w, t0=0.22, t1=0.30, clip=None, ss=4, step=0.5):
    pts = np.asarray(pts, float)
    if len(pts) < 2:
        return
    p = R.resample_open(pts, step)
    n = len(p)
    t = np.linspace(0, 1, n)
    prof = np.ones(n)
    if t0 > 0:
        prof = np.minimum(prof, t / t0)
    if t1 > 0:
        prof = np.minimum(prof, (1 - t) / t1)
    prof = np.clip(prof, 0, 1) ** 0.75
    rad = 0.5 * w * prof
    if clip is not None:
        H, W = clip.shape
        X = np.clip(np.round(p[:, 0] * ss + (ss - 1) * 0.5).astype(int), 0, W - 1)
        Y = np.clip(np.round(p[:, 1] * ss + (ss - 1) * 0.5).astype(int), 0, H - 1)
        vis = clip[Y, X] > 0
        rad = rad * vis
    R.stroke_poly(buf, p[:, 0].copy(), p[:, 1].copy(), rad.astype(np.float64), False)


def crescent(mask, L, d_ss):
    dx = int(round(L[0] * d_ss)); dy = int(round(-L[1] * d_ss))
    return mask & ~R.shift_mask(mask, dx, dy)


def hull(pts2):
    pts2 = np.asarray(pts2, np.float32)
    h = cv2.convexHull(pts2)
    return h[:, 0, :].astype(np.float64)


class Sprite:
    def __init__(self, rgba, ox, oy, info=None):
        self.rgba, self.ox, self.oy, self.info = rgba, ox, oy, info or {}


# ----------------------------------------------------------------------------- main render
def render(pose, scale, facing=1, light=None, ss=None, detail=None, style='cel', subpx=(0.0, 0.0),
           ink_color=None, line_scale=1.0, palette_overrides=None):
    """Render one drawing.  Returns Sprite(rgba straight float32, ox, oy): the root (feet contact
    point of the pose) sits at sprite pixel (ox + subpx[0], oy + subpx[1])."""
    light = light or DEFAULT_LIGHT
    detail = detail or detail_for(scale)
    sil = (style == 'silhouette')
    if ss is None:
        ss = 8 if scale < 14 else 6 if scale < 30 else 4 if scale <= 260 else 3
    rig = build_rig(pose)
    P = rig.P
    ppc = scale / CM_PER_UNIT
    mir = 1.0 if facing >= 0 else -1.0
    Rg = rx(D(P['view_el'])) @ ry(D(P['yaw'])) @ rz(D(P['pitch'])) @ rx(D(P['roll']))
    bc = rig.bc
    L = light.v.copy()
    pal = palette_for(light, palette_overrides)
    wbase = float(np.clip(0.0118 * scale, 0.7, 3.6)) * line_scale
    if detail == 'tiny':
        wbase = float(np.clip(0.03 * scale, 0.35, 0.7)) * line_scale
    wint = max(0.55, 0.52 * wbase)

    def scr(p):
        p = np.atleast_2d(np.asarray(p, float))
        c = (p - bc) @ Rg.T + bc
        return np.stack([mir * c[:, 0] * ppc, -c[:, 1] * ppc, c[:, 2] * ppc], 1)

    def camdir(v):
        c = Rg @ np.asarray(v, float)
        return np.array([mir * c[0], c[1], c[2]])

    # ---- gather geometry in screen space (relative to the root)
    S = scr(rig.sph_c)
    srad = rig.sph_r * ppc
    pts = [S[:, :2] - srad[:, None], S[:, :2] + srad[:, None]]
    fw = rig.fw
    lifted = {}
    if rig.folded:
        for side in (1, -1):
            extra = 0.0 if side > 0 else 3.5   # far wing droops a touch so its tips peek out
            o2 = fw['outline']
            if extra:
                piv = np.array([0.62, 0.78]); a = D(-extra)
                Rm = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
                o2 = (o2 - piv) @ Rm.T + piv
            oc = catmull(o2, 6, closed=True)
            z = side_z(oc[:, 0], oc[:, 1]) + 0.06 + P['wlift']
            o3 = np.stack([oc[:, 0], oc[:, 1], side * z], 1) @ rig.Rb.T + bc
            cv_ = catmull(fw['coverts'], 6, closed=True)
            zc = side_z(cv_[:, 0], cv_[:, 1]) + 0.06 + P['wlift']
            c3 = np.stack([cv_[:, 0], cv_[:, 1], side * zc], 1) @ rig.Rb.T + bc
            lines3 = []
            for l in fw['lines']:
                lc = catmull(l, 6)
                zl = side_z(lc[:, 0], lc[:, 1]) + 0.07 + P['wlift']
                lines3.append(np.stack([lc[:, 0], lc[:, 1], side * zl], 1) @ rig.Rb.T + bc)
            lifted[side] = dict(outline=scr(o3), coverts=scr(c3), lines=[scr(l) for l in lines3])
            pts.append(lifted[side]['outline'][:, :2])
    for wg in rig.wings:
        wg['s_outline'] = scr(catmull(wg['outline'], 3, closed=True))
        wg['s_coverts'] = scr(catmull(wg['coverts'], 3, closed=True))
        wg['s_lines'] = [scr(l) for l in wg['lines']]
        pts.append(wg['s_outline'][:, :2])
    tail = rig.tail
    tc = scr(tail['cen'])
    twv = np.array([camdir(v) * ppc for v in tail['wv']]); twv[:, 1] *= -1
    thv = np.array([camdir(v) * ppc for v in tail['hv']]); thv[:, 1] *= -1
    t_corners = []
    for i in range(len(tc)):
        c0 = tc[i, :2]
        t_corners.append(np.array([c0 + twv[i, :2] + thv[i, :2], c0 + twv[i, :2] - thv[i, :2],
                                   c0 - twv[i, :2] + thv[i, :2], c0 - twv[i, :2] - thv[i, :2]]))
    t_segs = [hull(np.vstack([t_corners[i], t_corners[i + 1]])) for i in range(len(tc) - 1)]
    for sgm in t_segs:
        pts.append(sgm)
    tail_up_cam = camdir(tail['up'])
    beak = rig.beak
    bu, bl = scr(beak['upper']), scr(beak['lower'])
    pts += [bu[:, :2], bl[:, :2]]
    legs_s = []
    for lg in rig.legs:
        d = {}
        for part in ('thigh', 'tarsus'):
            p3, r3 = lg[part]
            d[part] = (scr(p3), r3 * ppc)
        d['toes'] = [(scr(p3), r3 * ppc) for p3, r3 in lg['toes']]
        legs_s.append(d)
        pts.append(d['tarsus'][0][:, :2])
        for tp, _ in d['toes']:
            pts.append(tp[:, :2])
    smear_polys = []
    if P.get('smear_from') and not rig.folded and detail in ('full', 'mid') and not sil:
        from .poses import WINGS
        from .model import flight_wing
        src = WINGS[P['smear_from']]
        for t in (0.15, 0.35, 0.55, 0.75):
            Pq = dict(P)
            for k_ in ('el', 'sw', 'tw', 'ext', 'hel', 'hsw', 'fan'):
                a_ = src['n_' + k_]; b_ = P['n_' + k_]
                Pq['n_' + k_] = a_ + (b_ - a_) * t
            wq = flight_wing(Pq, 'n_', 1, rig.Rb, rig.bc)
            smear_polys.append(scr(catmull(wq['outline'], 3, closed=True))[:, :2])
        pts += smear_polys
    allp = np.vstack(pts)
    margin = 2.0 * wbase + 3.0
    x_min = np.floor(allp[:, 0].min() + subpx[0] - margin)
    y_min = np.floor(allp[:, 1].min() + subpx[1] - margin)
    x_max = np.ceil(allp[:, 0].max() + subpx[0] + margin)
    y_max = np.ceil(allp[:, 1].max() + subpx[1] + margin)
    w = int(x_max - x_min) + 1
    h = int(y_max - y_min) + 1
    ox, oy = -x_min, -y_min       # integer: root pixel (before subpx)
    offx, offy = ox + subpx[0], oy + subpx[1]

    def f2(p):        # screen-relative -> sprite final coords (N,2)
        p = np.asarray(p)
        return np.stack([p[:, 0] + offx, p[:, 1] + offy], 1)

    HS, WS = h * ss, w * ss
    ids = np.zeros((HS, WS), np.uint8)
    ink = np.zeros((h, w), np.float32)

    def paint(mask, zone, tone_mask=None, tone=1, rim=False):
        """write zone ids where mask; tone_mask marks shadow pixels"""
        z = Z[zone]
        base = z * 4
        ids[mask] = base
        if tone_mask is not None:
            ids[mask & tone_mask] = base + (2 if rim else tone)

    def push_ink(mask_ss, lyr_ink):
        nonlocal ink
        if mask_ss is not None:
            cov = R.coverage(mask_ss, ss)
            ink *= (1.0 - cov)
        np.maximum(ink, lyr_ink, out=ink)

    def layer_shadow(mask, size_px):
        """designed cel shadow (or rim crescent when backlit) for flat layers"""
        if L[2] < -0.12 and light.rim:
            lit = mask & ~R.shift_mask(mask, int(round(-L[0] * size_px * 0.22 * ss)), int(round(L[1] * size_px * 0.22 * ss)))
            return mask & ~lit, lit
        d = size_px * ss * (0.30 - 0.22 * L[2])
        return crescent(mask, L, d), None

    def flat_layer(mask, zone_main, size_px, zone_sub=None, sub_mask=None):
        shad, rimm = layer_shadow(mask, size_px)
        z = Z[zone_main] * 4
        ids[mask] = z
        if zone_sub is not None and sub_mask is not None:
            ids[mask & sub_mask] = Z[zone_sub] * 4
        if rimm is not None:
            ids[mask & ~rimm] += 1
            ids[mask & rimm] += 2
        else:
            ids[shad] += 1

    order = []      # (key, fn)
    # ------------------------------------------------------------------ tail
    tail_dir_cam = camdir(rig.Rb @ np.array([-1.0, 0, 0]))
    tail_after = tail_dir_cam[2] > 0.35

    def do_tail():
        m = np.zeros((HS, WS), np.uint8)
        R.fill_polys(m, [s + np.array([offx, offy]) for s in t_segs], ss)
        mb = m > 0
        size = 0.6 * ppc
        zt = 'tail_under' if tail_up_cam[2] < -0.3 else 'tail'
        flat_layer(mb, zt, size)
        li = np.zeros((h, w), np.float32)
        contour_ink(li, m, ss, wbase, L)
        if detail == 'full':
            for l3 in tail['lines']:
                open_stroke(li, f2(scr(l3)), wint * 0.75, 0.25, 0.35, clip=mb, ss=ss)
        push_ink(m, li)
    order.append((2.5 if tail_after else 0.5, do_tail))

    # ------------------------------------------------------------------ legs
    def do_legs():
        for k, lg in enumerate(legs_s):
            m = np.zeros((HS, WS), np.uint8)
            mt = np.zeros((HS, WS), np.uint8)
            tp, tr = lg['thigh']
            R.fill_capsules(mt, *f2(tp).T, tr, ss)
            p, r = lg['tarsus']
            thin = r.max() < 0.9
            R.fill_capsules(m, *f2(p).T, r, ss)
            for p2, r2 in lg['toes']:
                R.fill_capsules(m, *f2(p2).T, r2, ss)
            mb = m > 0
            mtb = (mt > 0) & ~mb
            flat_layer(mtb, 'thigh', tr.max() * 2)
            flat_layer(mb, 'leg', max(1.0, r.max() * 2))
            li = np.zeros((h, w), np.float32)
            allm = (mb | mtb).astype(np.uint8)
            if thin:
                q = f2(p)
                R.stroke_poly(li, q[:, 0].copy(), q[:, 1].copy(), np.maximum(r, 0.35).astype(np.float64), False)
                for p2, r2 in lg['toes']:
                    q = f2(p2)
                    R.stroke_poly(li, q[:, 0].copy(), q[:, 1].copy(), np.maximum(r2, 0.3).astype(np.float64), False)
            else:
                contour_ink(li, allm, ss, wint * 1.15, L, wmin=0.7)
            push_ink(allm, li)
    order.append((1.0, do_legs))

    # ------------------------------------------------------------------ folded wings
    near_side = 1 if camdir(rig.Rb @ np.array([0, 0, 1.0]))[2] >= 0 else -1
    core_holder = {}

    def wing_far_full():
        if not rig.folded:
            return
        side = -near_side
        lf = lifted[side]
        m = np.zeros((HS, WS), np.uint8)
        R.fill_polys(m, [f2(lf['outline'])], ss)
        mb = m > 0
        mc = np.zeros((HS, WS), np.uint8)
        R.fill_polys(mc, [f2(lf['coverts'])], ss)
        flat_layer(mb, 'flight', 1.2 * ppc, 'coverts', mc > 0)
        li = np.zeros((h, w), np.float32)
        contour_ink(li, m, ss, wbase * 0.9, L)
        push_ink(m, li)
    order.append((0.8, wing_far_full))

    # ------------------------------------------------------------------ core
    def do_core():
        HSS, WSS = HS, WS
        depth = np.full((HSS, WSS), -1e9, np.float32)
        idx = np.full((HSS, WSS), -1, np.int32)
        sx = (S[:, 0] + offx) * ss + (ss - 1) * 0.5
        sy = (S[:, 1] + offy) * ss + (ss - 1) * 0.5
        sz = S[:, 2] * ss
        R.zbuf_spheres(sx.astype(np.float64), sy.astype(np.float64), sz.astype(np.float64),
                       (srad * ss).astype(np.float64), depth, idx)
        nrm = np.zeros((HSS, WSS, 3), np.float32)
        R.smooth_normals(sx.astype(np.float64), sy.astype(np.float64), sz.astype(np.float64),
                         (srad * ss).astype(np.float64), depth, nrm, float(0.035 * ppc * ss))
        cid = np.zeros((HSS, WSS), np.uint8)
        tag = np.zeros((HSS, WSS), np.uint8)
        tex = wing_texture(fw) if rig.folded else np.zeros((2, 2, 6), np.float32)
        ed = EYE_DIR / np.linalg.norm(EYE_DIR)
        shade_core(depth, idx, nrm, float(ss), float(offx), float(offy), float(ppc), mir, Rg.T.copy(),
                   rig.sph_c.astype(np.float64), rig.sph_r.astype(np.float64), rig.sph_region.astype(np.int32),
                   rig.sph_s.astype(np.float64), rig.sph_tan.astype(np.float64), rig.sph_up.astype(np.float64),
                   float(rig.spine_len), rig.hc.astype(np.float64), rig.Rh.T.copy(), bc.astype(np.float64),
                   rig.Rb.T.copy(), bool(rig.folded), tex, TEX_X0, TEX_Y1, 1.0 / TEX_RES,
                   ed, EYE_A, RING_A, float(P['blink']), L.astype(np.float64), float(light.bias),
                   bool(light.rim), float(light.rim_width), bool(light.highlight and detail == 'full'),
                   False, cid, tag)
        core = idx >= 0
        # designed cast shadows: head onto breast/neck, folded near wing onto the flank
        if not sil and L[2] > -0.12:
            regm = np.where(core, rig.sph_region[np.maximum(idx, 0)], -1)
            lit_px = core & ((cid & 3) == 0)
            away = np.array([-L[0], L[1]])
            nrm2 = np.linalg.norm(away) + 1e-9
            away = away / nrm2
            dd = 0.20 * ppc * ss
            hm = regm == 2
            front = np.isin(cid >> 2, [Z['yellow'], Z['white'], Z['buff']])
            cast = np.zeros_like(hm)
            if rig.folded:
                wt = 2 if camdir(rig.Rb @ np.array([0, 0, 1.0]))[2] >= 0 else 3
                wm = tag == wt
                dw = 0.11 * ppc * ss
                cast |= R.shift_mask(wm, int(round(away[0] * dw)), int(round(away[1] * dw + 0.05 * ppc * ss))) & ~wm & lit_px & (regm == 0)
            keep = ((cid >> 2) == Z['eye']) | ((cid >> 2) == Z['ring'])
            cid[cast & ~keep] += 1
        ids[core] = cid[core]
        core_holder.update(core=core, tag=tag, depth=depth)
        li = np.zeros((h, w), np.float32)
        contour_ink(li, core.astype(np.uint8), ss, wbase, L)
        push_ink(core.astype(np.uint8), li)
        # eye-ring line (thin, partial) and blink lid
        if detail in ('full', 'mid') and not sil:
            ringm = ((cid >> 2) == Z['ring']) | ((cid >> 2) == Z['eye'])
            ringm &= core
            if ringm.any():
                lr = np.zeros((h, w), np.float32)
                contour_ink(lr, ringm.astype(np.uint8), ss, wint * 0.75, L, wmin=0.35, sigma=1.0)
                ink[:] = np.maximum(ink, lr * 0.85)
    order.append((2.0, do_core))

    def wing_near():
        if not rig.folded:
            return
        side = near_side
        lf = lifted[side]
        core = core_holder['core']
        tag = core_holder['tag']
        want = 2 if side > 0 else 3
        dec = (tag == want) & core
        m = np.zeros((HS, WS), np.uint8)
        R.fill_polys(m, [f2(lf['outline'])], ss)
        over = (m > 0) & ~core
        mc = np.zeros((HS, WS), np.uint8)
        R.fill_polys(mc, [f2(lf['coverts'])], ss)
        if over.any():
            sh = crescent(over | dec, L, 0.35 * ppc * ss) & over
            ids[over] = Z['flight'] * 4
            ids[over & (mc > 0)] = Z['coverts'] * 4
            if L[2] < -0.12 and light.rim:
                ids[over] += 1
            else:
                ids[sh] += 1
        un = (dec | over)
        li = np.zeros((h, w), np.float32)
        contour_ink(li, un.astype(np.uint8), ss, wbase * 0.92, L, wmin=0.6)
        if detail in ('full', 'mid'):
            for j, l in enumerate(lf['lines']):
                if detail == 'mid' and j not in (0, 1):
                    continue
                open_stroke(li, f2(l), wint * (0.95 if j == 0 else 0.8), 0.18, 0.35, clip=un, ss=ss)
        push_ink(over.astype(np.uint8), li)
        # far-side decal (only visible in back/three-quarter-back views)
        dec2 = (tag == (5 - want)) & core
        if dec2.sum() > 4 * ss * ss:
            l2 = np.zeros((h, w), np.float32)
            contour_ink(l2, dec2.astype(np.uint8), ss, wbase * 0.8, L, wmin=0.6)
            np.maximum(ink, l2, out=ink)
    order.append((2.2, wing_near))

    # ------------------------------------------------------------------ flight wings
    for wg in rig.wings:
        cen = wg['s_outline'][:, 2].mean()
        n_cam = camdir(wg['normal'])
        dorsal = n_cam[2] >= 0

        def do_wing(wg=wg, dorsal=dorsal, n_cam=n_cam):
            m = np.zeros((HS, WS), np.uint8)
            R.fill_polys(m, [f2(wg['s_outline'])], ss)
            mc = np.zeros((HS, WS), np.uint8)
            R.fill_polys(mc, [f2(wg['s_coverts'])], ss)
            mb = m > 0
            nv = n_cam if dorsal else -n_cam
            zmain, zsub = ('flight', 'coverts') if dorsal else ('uw_flight', 'uw_cov')
            ids[mb] = Z[zmain] * 4
            ids[mb & (mc > 0)] = Z[zsub] * 4
            lit = float(nv @ L) > light.bias - 0.05
            if L[2] < -0.12 and light.rim:
                rimm = mb & ~R.shift_mask(mb, int(round(-L[0] * 0.25 * ppc * ss)), int(round(L[1] * 0.25 * ppc * ss)))
                ids[mb & ~rimm] += 1
                ids[mb & rimm] += 2
            elif not lit:
                ids[mb] += 1
            else:
                sh = crescent(mb, L, 0.28 * ppc * ss)
                ids[sh & (mc > 0)] += 1
            li = np.zeros((h, w), np.float32)
            contour_ink(li, m, ss, wbase, L)
            if detail in ('full', 'mid'):
                cl = f2(wg['s_coverts'])
                # covert edge: the trailing part of the coverts polygon
                nseg = len(cl)
                open_stroke(li, cl[int(nseg * 0.22):int(nseg * 0.92)], wint * 0.8, 0.2, 0.3, clip=mb, ss=ss)
                if detail == 'full':
                    for l in wg['s_lines']:
                        open_stroke(li, f2(l), wint * 0.75, 0.05, 0.6, clip=mb, ss=ss)
            push_ink(m, li)
        order.append((2.0 + (0.6 if cen > S[:, 2].mean() + 0.05 * ppc else -1.6), do_wing))

    # ------------------------------------------------------------------ beak
    beak_dir = camdir(rig.Rh @ np.array([1.0, 0, 0]))

    def do_beak():
        m = np.zeros((HS, WS), np.uint8)
        mu = np.zeros((HS, WS), np.uint8)
        ml = np.zeros((HS, WS), np.uint8)
        hu = hull(f2(bu[:, :2])); hl = hull(f2(bl[:, :2]))
        R.fill_polys(mu, [hu], ss); R.fill_polys(ml, [hl], ss)
        mm = None
        if beak['mouth'] is not None:
            mo = scr(beak['mouth'])
            mm = np.zeros((HS, WS), np.uint8)
            R.fill_polys(mm, [hull(f2(mo[:, :2]))], ss)
        mb = (mu > 0) | (ml > 0)
        if mm is not None:
            mb |= mm > 0
            ids[mm > 0] = Z['mouth'] * 4 + 1
        size = 0.3 * ppc
        shl, _ = layer_shadow(ml > 0, size)
        ids[ml > 0] = Z['beak_lo'] * 4
        ids[shl] += 1
        shu, _ = layer_shadow(mu > 0, size)
        ids[mu > 0] = Z['beak_up'] * 4
        ids[shu] += 1
        if detail == 'full' and not sil:
            # glint on the culmen
            hl_ = (mu > 0) & ~R.shift_mask(mu > 0, 0, int(round(0.06 * ppc * ss))) & ~shu
            ids[hl_] = Z['beak_up'] * 4 + 3
        li = np.zeros((h, w), np.float32)
        mbu = mb.astype(np.uint8)
        contour_ink(li, mbu, ss, wbase * 0.8, L, wmin=0.65, sigma=0.9)
        if detail in ('full', 'mid'):
            g = f2(scr(beak['gape']))[0]
            tip = f2(scr(beak['upper'][-1:]))[0]
            mid = 0.5 * (g + tip)
            open_stroke(li, np.array([g, mid + (tip - g) * 0.05, tip]), wint * 0.85, 0.0, 0.45)
        push_ink(mbu, li)
    order.append((2.6 if beak_dir[2] > -0.45 else 1.9, do_beak))

    # ------------------------------------------------------------------ run layers
    order.sort(key=lambda t: t[0])
    for _, fn in order:
        fn()

    # ------------------------------------------------------------------ eyes: catch-lights + blink lid
    if detail != 'tiny' and not sil:
        core = core_holder.get('core')
        for e in rig.eyes:
            ncam = camdir(e['n'])
            if ncam[2] < 0.12:
                continue
            ec = f2(scr(e['c'][None]))[0]
            X = int(np.clip(round(ec[0] * ss + (ss - 1) / 2), 0, WS - 1))
            Y = int(np.clip(round(ec[1] * ss + (ss - 1) / 2), 0, HS - 1))
            if (ids[Y, X] >> 2) not in (Z['eye'], Z['ring']):
                continue
            er = EYE_A * rig.rh * ppc
            if P['blink'] > 0.5:
                # closed lid: a short curved line across the eye
                t = np.linspace(-1, 1, 9)
                fwd = camdir(rig.Rh @ np.array([1.0, 0, 0]))[:2]
                fwd2 = np.array([fwd[0], -fwd[1]])
                nn = np.linalg.norm(fwd2)
                fwd2 = fwd2 / nn if nn > 1e-6 else np.array([1.0, 0])
                perp = np.array([-fwd2[1], fwd2[0]])
                if perp[1] < 0:
                    perp = -perp
                pts_ = ec[None] + t[:, None] * fwd2[None] * er * 0.95 + (1 - t[:, None] ** 2) * perp[None] * er * 0.25
                open_stroke(ink, pts_, wint * 1.1, 0.25, 0.25)
                continue
            if P['blink'] > 0.0:
                continue
            cl = np.array([L[0], -L[1]])
            cl = cl / (np.linalg.norm(cl) + 1e-9)
            c1 = ec + (cl * 0.38 + np.array([0, -0.18])) * er
            r1 = max(0.55, 0.30 * er)
            m = np.zeros((HS, WS), np.uint8)
            cc = R.to_ss(c1[None], ss)[0]
            cv2.circle(m, (int(cc[0]), int(cc[1])), int(r1 * ss * 16), 1, -1, cv2.LINE_8, R.SHIFT)
            if scale >= 110:
                c2 = ec - cl * 0.45 * er + np.array([0, 0.25]) * er
                cc = R.to_ss(c2[None], ss)[0]
                cv2.circle(m, (int(cc[0]), int(cc[1])), int(max(0.4, 0.12 * er) * ss * 16), 1, -1, cv2.LINE_8, R.SHIFT)
            m = (m > 0) & (((ids >> 2) == Z['eye']))
            ids[m] = Z['catch'] * 4

    # ------------------------------------------------------------------ silhouette remap (flocks)
    if sil:
        zz = ids >> 2
        tt = ids & 3
        lightz = np.isin(zz, [Z['uw_cov'], Z['uw_flight'], Z['sil_lit']])
        new = np.where(tt == 2, Z['sil'] * 4 + 2,
                       np.where(lightz | (tt == 0) | (tt == 3), Z['sil_lit'] * 4, Z['sil'] * 4))
        ids = np.where(ids > 0, new, 0).astype(np.uint8)

    # ------------------------------------------------------------------ resolve
    paint = np.zeros((h, w, 4), np.float32)
    R.resolve_ids(ids, pal, ss, paint)
    ic = np.asarray(INK if ink_color is None else ink_color, np.float32)
    if sil:
        ic = np.asarray(pal[Z['sil'] * 4 + 0, :3] * 0.8, np.float32)
    a = ink[..., None]
    out = np.empty_like(paint)
    out[..., :3] = ic[None, None] * a + paint[..., :3] * (1 - a)
    out[..., 3:] = a + paint[..., 3:] * (1 - a)
    if smear_polys:
        ms = np.zeros((HS, WS), np.uint8)
        R.fill_polys(ms, [f2(sp_) for sp_ in smear_polys], ss)
        sa = (R.coverage(ms, ss) * 0.42)[..., None]
        scol = pal[Z['uw_cov'] * 4 + (1 if L[2] < -0.12 else 0), :3][None, None]
        out[..., :3] = out[..., :3] + scol * sa * (1 - out[..., 3:])
        out[..., 3:] = out[..., 3:] + sa * (1 - out[..., 3:])
    al = out[..., 3:]
    out[..., :3] = np.where(al > 1e-6, out[..., :3] / np.maximum(al, 1e-6), 0)
    return Sprite(out, int(ox), int(oy), dict(scale=scale, ss=ss, detail=detail))


# ----------------------------------------------------------------------------- compositing
def composite(canvas, rgba, x0, y0, opacity=1.0):
    """'over' a straight-alpha sprite onto a straight-alpha canvas at integer (x0, y0)."""
    H, W = canvas.shape[:2]
    h, w = rgba.shape[:2]
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(W, x0 + w), min(H, y0 + h)
    if cx1 <= cx0 or cy1 <= cy0:
        return canvas
    s = rgba[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    d = canvas[cy0:cy1, cx0:cx1]
    sa = s[..., 3:4] * opacity
    da = d[..., 3:4]
    oa = sa + da * (1 - sa)
    orgb = s[..., :3] * sa + d[..., :3] * da * (1 - sa)
    d[..., :3] = np.where(oa > 1e-6, orgb / np.maximum(oa, 1e-6), d[..., :3])
    d[..., 3:4] = oa
    return canvas


_CACHE = {}
_CACHE_ORDER = []


def _ckey(pose, x, y, scale, facing, light, kw):
    try:
        pk = tuple(sorted((k, round(v, 5) if isinstance(v, float) else v) for k, v in pose.items()))
        kk = tuple(sorted((k, v if not isinstance(v, (list, np.ndarray)) else tuple(np.ravel(v)))
                          for k, v in kw.items()))
        return (pk, round(x % 1.0, 4), round(y % 1.0, 4), round(float(scale), 4), facing,
                (light or DEFAULT_LIGHT).key(), kk)
    except TypeError:
        return None


def draw(canvas, pose, x, y, scale, facing=1, light=None, cache=True, **kw):
    """Render `pose` with its root (feet contact point) at canvas pixel (x, y) and composite.
    Identical drawings (e.g. the second frame of a drawing on 2s) are served from a small cache."""
    fx, fy = np.floor(x), np.floor(y)
    key = _ckey(pose, x, y, scale, facing, light, kw) if cache else None
    sp = _CACHE.get(key) if key is not None else None
    if sp is None:
        sp = render(pose, scale, facing, light, subpx=(x - fx, y - fy), **kw)
        if key is not None:
            _CACHE[key] = sp
            _CACHE_ORDER.append(key)
            if len(_CACHE_ORDER) > 16:
                _CACHE.pop(_CACHE_ORDER.pop(0), None)
    composite(canvas, sp.rgba, int(fx) - sp.ox, int(fy) - sp.oy)
    return sp
