"""cel.py - draw a posed rig as an anime cel (fills + designed shadows + ink).

draw(rig, pose, cam, style) -> premultiplied RGBA float32 at cam resolution.

`style` is a dict:
  light        world direction TO the key light
  pal          {mat: (light_rgb, shadow_rgb)} or {mat: (light, shadow, deep)}
  ink          ink colour
  widths       {line class: px at frame scale}
  ss           supersampling factor (render scale)
  shadow_thr   N.L threshold for the terminator
  shadow_clean (close_px, open_px, min_area_px, smooth_px) at frame scale
  seed         per-drawing seed (change every 2 frames for line boil)
  decal_fn     optional f(passes, ctx) -> dict of per-pixel overrides
"""
import math
import numpy as np
import cv2
import r3d
import ink
import look


DEFAULT_WIDTHS = {ink.SIL: 3.2, ink.OCC: 2.6, ink.PART: 2.0, ink.CREASE: 1.5, ink.DETAIL: 1.0}


def render(rig, pose, cam, style, extra=None, skip=(), return_passes=False):
    ss = style.get('ss', 2)
    camS = cam.scaled(ss)
    sc, mats = rig.scene(pose, extra=extra, skip=skip)
    ps = r3d.render_passes(sc, camS)
    m = ps['mask']
    H, W = m.shape
    L = np.asarray(style['light'], np.float32); L /= np.linalg.norm(L)
    nrm = ps['nrm']
    lam = np.sum(nrm * L, -1)
    if style.get('cast_shadows', True):
        P = ps['wpos'][m]
        ctr = P.mean(0) if len(P) else np.zeros(3, np.float32)
        ext = float(np.max(np.abs(P - ctr))) * 1.2 + 1.0 if len(P) else 10.0
        sm = r3d.ShadowMap(sc, L, ctr, ext, style.get('shadow_res', 2048))
        castlit = np.ones((H, W), np.float32)
        castlit[m] = sm.lit(P, bias=style.get('shadow_bias', 0.06))
    else:
        castlit = np.ones((H, W), np.float32)
    thr = style.get('shadow_thr', 0.05)
    lit_raw = (lam > thr) & (castlit > 0.5) & m
    cc, co, ca, cs = style.get('shadow_clean', (2.0, 2.0, 60, 1.2))
    lit = look.clean_mask(lit_raw, cc * ss, co * ss, ca * ss * ss, cs * ss, valid=m)

    mat = ps['mat']
    part = ps['part']
    opos = ps['opos']
    # per-pixel material and panel functions (evaluated in part space, so they stay on-model)
    for pi, fn in style.get('matfn', {}).items():
        sel = part == pi
        if sel.any():
            mat[sel] = fn(opos[sel], mat[sel])
    detail = part.astype(np.int32) * 1000
    for pi, fn in style.get('panelfn', {}).items():
        sel = part == pi
        if sel.any():
            detail[sel] += fn(opos[sel]).astype(np.int32)
    ps['detail'] = detail
    ps['mat'] = mat
    pal = style['pal']
    rgb = np.zeros((H, W, 3), np.float32)
    for k, cols in pal.items():
        sel = (mat == k)
        if not sel.any():
            continue
        lc = np.asarray(cols[0], np.float32); sh = np.asarray(cols[1], np.float32)
        rgb[sel & lit] = lc
        rgb[sel & ~lit] = sh
    # emissive materials ignore light
    for k in style.get('emissive', {}):
        sel = mat == k
        rgb[sel] = np.asarray(style['emissive'][k], np.float32)

    if style.get('lens_fn') is not None:
        sel = mat == style.get('lens_mat', 3)
        if sel.any():
            rgb[sel] = style['lens_fn'](opos[sel], lit[sel])
    if style.get('decal_fn') is not None:
        style['decal_fn'](rgb, ps, lit, style)

    # ink
    label = part.astype(np.int32) * 64 + mat.astype(np.int32)
    detail = ps.get('detail')
    cls = ink.edge_map(m, label, ps['depth'], nrm, detail,
                       depth_rel=style.get('depth_rel', 0.03),
                       crease_deg=style.get('crease_deg', 48.0))
    chains = ink.trace(cls, min_len=int(3 * ss))
    rng = np.random.default_rng(style.get('seed', 0))
    widths = {k: v * ss for k, v in style.get('widths', DEFAULT_WIDTHS).items()}

    def wfn(pts, k):
        # heavier on the shadow side of a form: sample lit mask at the points
        ix = np.clip(pts[:, 0].astype(int), 0, W - 1); iy = np.clip(pts[:, 1].astype(int), 0, H - 1)
        sh = ~lit[iy, ix]
        return np.where(sh, 1.18, 0.9).astype(np.float32)

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
    rgba = np.concatenate([rgb * a[..., None], a[..., None]], -1)
    out = look.downsample(rgba, ss)
    if return_passes:
        return out, ps, lit
    return out


def on_paper(rgba, paper=(0.96, 0.94, 0.89)):
    p = np.asarray(paper, np.float32)
    return rgba[..., :3] + p * (1 - rgba[..., 3:4])


def to_u8(rgb):
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
