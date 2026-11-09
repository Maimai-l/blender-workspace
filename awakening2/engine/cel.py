"""cel.py - draw a posed rig as an anime cel.

render(rig, pose, cam, style) -> premultiplied RGBA float32 at cam resolution
(plus passes when asked). Steps:

  passes      our rasteriser at `ss` x resolution
  light       N.L against the shot's key light x cast shadows
  tones       designed shadow shapes (threshold -> clean-up -> no islands ->
              smooth edge); moss/foliage get a top-light and a deep band
  materials   per-pixel material / panel functions in part space
  decals      chipped paint, primer halos, rust patches and streaks
              (box-projected label maps, smooth edges at any magnification)
  extras      cel eyes, core glow, light spill, painted moss tufts, flowers
  ink         lines from id / depth / normal discontinuities (ink.py)

style keys (all optional except light/pal):
  light, pal{mat: (light, shadow[, deep, high])}, ss, seed, widths,
  shadow_thr, shadow_clean, high_thr, deep_thr, emissive{mat: rgb},
  matfn{part_idx: f}, panelfn{part_idx: f}, lens_fn, lens_mat,
  decals (surface.Decals), decal_cols, roof_decal_cols, decal_mats, roof_mats,
  flowers [(part_name, (n,6) local anchors)], tufts [(part_name, P, N)],
  spill (world_pos, radius_m, rgb, strength), ink, depth_rel, crease_deg
"""
import math
import numpy as np
import cv2
import r3d
import ink
import look


DEFAULT_WIDTHS = {ink.SIL: 3.2, ink.OCC: 2.6, ink.PART: 2.0, ink.CREASE: 1.5, ink.DETAIL: 1.0}
FLOWER_COLS = [((0.96, 0.95, 0.90), (0.72, 0.71, 0.80)),
               ((0.96, 0.88, 0.58), (0.72, 0.62, 0.45)),
               ((0.74, 0.65, 0.88), (0.48, 0.41, 0.64))]


def _bands(lam, castlit, m, thr, ss, clean, valid=None):
    raw = (lam > thr) & (castlit > 0.5) & m
    cc, co, ca, cs = clean
    return look.clean_mask(raw, cc * ss, co * ss, ca * ss * ss, cs * ss, valid=m if valid is None else valid)


def render(rig, pose, cam, style, extra=None, skip=(), return_passes=False, mats_out=None):
    ss = style.get('ss', 2)
    camS = cam.scaled(ss)
    sc, mats = rig.scene(pose, extra=extra, skip=skip)
    if mats_out is not None:
        mats_out.update(mats)
    ps = r3d.render_passes(sc, camS)
    m = ps['mask']
    H, W = m.shape
    L = np.asarray(style['light'], np.float32); L = L / np.linalg.norm(L)
    nrm = ps['nrm']
    lam = np.sum(nrm * L, -1)
    if style.get('cast_shadows', True) and m.any():
        P = ps['wpos'][m]
        ctr = np.median(P, 0)
        ext = float(np.percentile(np.abs(P - ctr), 99.5)) * 1.3 + 2.0
        sm = r3d.ShadowMap(sc, L, ctr, ext, style.get('shadow_res', 2048))
        castlit = np.ones((H, W), np.float32)
        castlit[m] = sm.lit(P, bias=style.get('shadow_bias', 0.08))
    else:
        castlit = np.ones((H, W), np.float32)
    clean = style.get('shadow_clean', (2.0, 2.0, 60, 1.2))
    lit = _bands(lam, castlit, m, style.get('shadow_thr', 0.05), ss, clean)
    high = _bands(lam, castlit, m, style.get('high_thr', 0.55), ss, clean) & lit
    deep = look.clean_mask((lam < style.get('deep_thr', -0.5)) & m, clean[0] * ss, clean[1] * ss,
                           clean[2] * ss * ss, clean[3] * ss, valid=m) & ~lit

    mat = ps['mat']; part = ps['part']; opos = ps['opos']; onrm = ps['onrm']
    for pi, fn in style.get('matfn', {}).items():
        sel = part == pi
        if sel.any():
            mat[sel] = fn(opos[sel], mat[sel])
    detail = part.astype(np.int32) * 1000
    for pi, fn in style.get('panelfn', {}).items():
        sel = part == pi
        if sel.any():
            detail[sel] += fn(opos[sel]).astype(np.int32)
    ps['detail'] = detail; ps['mat'] = mat

    # sky fill: inside the shadow, faces turned to the open sky get a lighter, cooler tone
    sky = np.asarray(style.get('sky_dir', (0.0, 0.0, 1.0)), np.float32); sky = sky / np.linalg.norm(sky)
    fill = look.clean_mask((np.sum(nrm * sky, -1) > style.get('fill_thr', 0.45)) & m & ~lit, clean[0] * ss, clean[1] * ss,
                           clean[2] * ss * ss, clean[3] * ss, valid=m) & ~lit & ~deep
    ps['fill'] = fill
    rgb = np.zeros((H, W, 3), np.float32)
    for k, cols in style['pal'].items():
        sel = mat == k
        if not sel.any():
            continue
        c = [None if x is None else np.asarray(x, np.float32) for x in cols]
        rgb[sel & lit] = c[0]
        rgb[sel & ~lit] = c[1]
        if len(c) > 4 and c[4] is not None:
            rgb[sel & fill] = c[4]
        if len(c) > 2 and c[2] is not None:
            rgb[sel & deep] = c[2]
        if len(c) > 3 and c[3] is not None:
            rgb[sel & high] = c[3]

    # decals on painted surfaces
    dec = style.get('decals')
    if dec is not None:
        dmats = list(style.get('decal_mats', ()))
        rmats = list(style.get('roof_mats', ()))
        for pi in np.unique(part[m]):
            if int(pi) not in dec.maps:
                continue
            sel = (part == pi) & np.isin(mat, dmats + rmats)
            if not sel.any():
                continue
            lab = dec.lookup(int(pi), opos[sel], onrm[sel])
            is_roof = np.isin(mat[sel], rmats)
            l_sel = lit[sel]
            sub = rgb[sel]
            for k, (cl, cs) in style['decal_cols'].items():
                kk = (lab == k) & ~is_roof
                sub[kk & l_sel] = cl; sub[kk & ~l_sel] = cs
            for k, (cl, cs) in style.get('roof_decal_cols', {}).items():
                kk = (lab == k) & is_roof
                sub[kk & l_sel] = cl; sub[kk & ~l_sel] = cs
            rgb[sel] = sub

    if style.get('lens_fn') is not None:
        sel = mat == style.get('lens_mat', 3)
        if sel.any():
            rgb[sel] = style['lens_fn'](opos[sel], lit[sel])
    for k, col in style.get('emissive', {}).items():
        rgb[mat == k] = np.asarray(col, np.float32)

    # light spill from a glowing source (e.g. the chest core), as a hard cel light shape
    sp = style.get('spill')
    if sp is not None and m.any():
        pos, rad, col, strength = sp
        d = np.linalg.norm(ps['wpos'] - np.asarray(pos, np.float32), axis=-1)
        fall = np.clip(1 - d / rad, 0, 1) * m
        band = look.clean_mask(fall > 0.35, 1.5 * ss, 1.5 * ss, 40 * ss * ss, 1.0 * ss, valid=m)
        band &= ~np.isin(mat, list(style.get('emissive', {}).keys()))
        rgb[band] = rgb[band] * (1 - 0.55 * strength) + np.asarray(col, np.float32) * 0.55 * strength
        ps['spill_soft'] = fall

    # painted moss tufts (object-anchored, so they never swim)
    if style.get('tufts'):
        _draw_tufts(rgb, ps, camS, mats, style, L, lit, ss)

    # ink
    label = part.astype(np.int32) * 64 + mat.astype(np.int32)
    cls = ink.edge_map(m, label, ps['depth'], nrm, detail,
                       depth_rel=style.get('depth_rel', 0.03),
                       crease_deg=style.get('crease_deg', 48.0))
    soft = np.isin(mat, list(style.get('soft_mats', ())))
    cls[(cls == ink.CREASE) & soft] = 0
    chains = ink.trace(cls, min_len=int(3 * ss))
    rng = np.random.default_rng(style.get('seed', 0))
    widths = {k: v * ss for k, v in style.get('widths', DEFAULT_WIDTHS).items()}

    def wfn(pts, k):
        ix = np.clip(pts[:, 0].astype(int), 0, W - 1); iy = np.clip(pts[:, 1].astype(int), 0, H - 1)
        sh = ~lit[iy, ix]
        return np.where(sh, 1.15, 0.88).astype(np.float32)

    strokes = ink.chains_to_strokes(chains, widths, rng, smooth_sigma=1.2 * ss, step=1.5 * ss,
                                    corner_deg=style.get('corner_deg', 62.0),
                                    taper_px=style.get('taper_px', 10.0) * ss,
                                    wob_amp=style.get('wobble', 0.35) * ss, wob_wl=40.0 * ss,
                                    width_fn=wfn)
    cov = ink.draw_strokes((H, W), [(s[0], s[1]) for s in strokes])
    inkc = np.asarray(style.get('ink', (0.17, 0.12, 0.12)), np.float32)
    a = m.astype(np.float32)
    rgb = rgb * (1 - cov[..., None]) + inkc * cov[..., None]
    a = np.maximum(a, cov)

    if style.get('rivets'):
        _draw_rivets(rgb, ps, camS, mats, style, L, lit, ss, inkc)
    if style.get('flowers'):
        _draw_flowers(rgb, a, ps, camS, mats, style, L, ss, inkc)

    rgba = np.concatenate([rgb * a[..., None], a[..., None]], -1)
    out = look.downsample(rgba, ss)
    if return_passes:
        ps['lit'] = lit; ps['ss'] = ss; ps['cam'] = camS
        return out, ps
    return out


def _draw_tufts(rgb, ps, camS, mats, style, L, lit, ss):
    H, W = lit.shape
    segs_l, segs_d = [], []
    mat = ps['mat']
    moss_mats = list(style.get('tuft_mats', (5,)))
    hi = np.asarray(style.get('tuft_light', (0.80, 0.84, 0.48)), np.float32)
    lo = np.asarray(style.get('tuft_dark', (0.17, 0.29, 0.25)), np.float32)
    for pname, P, N in style['tufts']:
        if pname not in mats:
            continue
        M = mats[pname]
        Pw = r3d.xform_points(M, P); Nw = r3d.xform_dirs(M, N)
        q = camS.project(Pw)
        ok = (q[:, 2] > 0.5) & (q[:, 0] >= 1) & (q[:, 0] < W - 1) & (q[:, 1] >= 1) & (q[:, 1] < H - 1)
        if not ok.any():
            continue
        q = q[ok]; Nw = Nw[ok]; Pw = Pw[ok]
        ix = q[:, 0].astype(int); iy = q[:, 1].astype(int)
        dep = ps['depth'][iy, ix]
        vis = (q[:, 2] <= dep + 0.12 + 0.01 * q[:, 2]) & np.isin(mat[iy, ix], moss_mats)
        view = Pw - camS.pos
        facing = np.sum(Nw * view, -1) / np.linalg.norm(view, axis=-1) < -0.15
        vis &= facing
        if not vis.any():
            continue
        q = q[vis]; Nw = Nw[vis]; ix = ix[vis]; iy = iy[vis]; Pv = Pw[vis]
        n2 = camS.project(Pv + Nw * 0.3)[:, :2] - q[:, :2]
        n2 /= np.linalg.norm(n2, axis=-1, keepdims=True) + 1e-6
        t2 = np.stack([-n2[:, 1], n2[:, 0]], -1)
        size = np.clip(camS.fpx * 0.16 / q[:, 2], 0, 40 * ss)
        keep = size > 1.6 * ss
        lam = np.sum(Nw * L, -1)
        for i in np.where(keep)[0]:
            c = q[i, :2]; s = size[i]
            p0 = c - t2[i] * s * 0.5; p1 = c + n2[i] * s * 0.28; p2 = c + t2[i] * s * 0.5
            pts = np.array([p0, p1, p2], np.float32)
            w = np.array([0.3, 1.0, 0.25], np.float32) * max(0.9 * ss, s * 0.16)
            (segs_l if (lit[iy[i], ix[i]] and lam[i] > 0.25) else segs_d).append((pts, w))
    sel = np.isin(mat, moss_mats).astype(np.float32)
    for segs, col, alpha in ((segs_d, lo, 0.75), (segs_l, hi, 0.9)):
        if segs:
            cov = ink.draw_strokes((H, W), segs) * alpha * sel
            rgb[:] = rgb * (1 - cov[..., None]) + col * cov[..., None]


def _draw_rivets(rgb, ps, camS, mats, style, L, lit, ss, inkc):
    H, W = lit.shape
    mat = ps['mat']
    ok_mats = list(style.get('decal_mats', ())) + list(style.get('roof_mats', ()))
    for pname, P, N in style['rivets']:
        if pname not in mats:
            continue
        M = mats[pname]
        Pw = r3d.xform_points(M, P); Nw = r3d.xform_dirs(M, N)
        q = camS.project(Pw)
        view = Pw - camS.pos
        facing = np.sum(Nw * view, -1) / (np.linalg.norm(view, axis=-1) + 1e-6) < -0.2
        for i in np.where(facing & (q[:, 2] > 0.5))[0]:
            x, y, z = q[i]
            if not (1 <= x < W - 1 and 1 <= y < H - 1):
                continue
            ix, iy = int(x), int(y)
            if z > ps['depth'][iy, ix] + 0.12 or mat[iy, ix] not in ok_mats:
                continue
            r = camS.fpx * 0.05 / z
            if r < 1.3 * ss:
                continue
            lt = bool(lit[iy, ix])
            base = rgb[iy, ix].copy()
            # a ring in a darker shade of the local paint, the head in the paint, a highlight toward the light
            cv2.circle(rgb, (int(x * 4), int(y * 4)), int(r * 4), (base * 0.55).tolist(), -1, cv2.LINE_AA, 2)
            cv2.circle(rgb, (int(x * 4), int(y * 4)), max(1, int(r * 0.62 * 4)), base.tolist(), -1, cv2.LINE_AA, 2)
            if lt:
                hx = x - r * 0.25; hy = y - r * 0.3
                cv2.circle(rgb, (int(hx * 4), int(hy * 4)), max(1, int(r * 0.28 * 4)),
                           np.clip(base * 1.35 + 0.08, 0, 1).tolist(), -1, cv2.LINE_AA, 2)


def _draw_flowers(rgb, a, ps, camS, mats, style, L, ss, inkc):
    H, W = a.shape
    for pname, F in style['flowers']:
        if pname not in mats or len(F) == 0:
            continue
        M = mats[pname]
        Pw = r3d.xform_points(M, F[:, :3].astype(np.float32))
        q = camS.project(Pw)
        for i in range(len(F)):
            x, y, z = q[i]
            if z < 0.5 or not (0 <= x < W and 0 <= y < H):
                continue
            if z > ps['depth'][int(y), int(x)] + 0.25 + 0.01 * z:
                continue
            r = camS.fpx * F[i, 3] / z
            if r < 1.2 * ss:
                continue
            kind = int(F[i, 4]) % 3; rot = float(F[i, 5])
            cl, cs = FLOWER_COLS[kind]
            col = np.asarray(cl, np.float32)
            for k in range(5):
                ang = rot + k * 2 * math.pi / 5
                px = x + math.cos(ang) * r * 0.55; py = y + math.sin(ang) * r * 0.42
                ax0 = max(2, int(r * 0.48 * 4)); ax1 = max(2, int(r * 0.3 * 4))
                cen = (int(px * 4), int(py * 4))
                cv2.ellipse(rgb, cen, (ax0, ax1), math.degrees(ang), 0, 360, inkc.tolist(), -1, cv2.LINE_AA, 2)
                cv2.ellipse(rgb, cen, (max(1, ax0 - int(2.4 * ss)), max(1, ax1 - int(2.4 * ss))), math.degrees(ang), 0, 360,
                            col.tolist(), -1, cv2.LINE_AA, 2)
                cv2.ellipse(a, cen, (ax0, ax1), math.degrees(ang), 0, 360, 1.0, -1, cv2.LINE_AA, 2)
            cv2.circle(rgb, (int(x * 4), int(y * 4)), max(2, int(r * 0.22 * 4)), (0.95, 0.70, 0.25), -1, cv2.LINE_AA, 2)


def on_paper(rgba, paper=(0.96, 0.94, 0.89)):
    p = np.asarray(paper, np.float32)
    return rgba[..., :3] + p * (1 - rgba[..., 3:4])


def to_u8(rgb):
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
