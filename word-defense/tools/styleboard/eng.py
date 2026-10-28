# eng.py - a small paper-diorama renderer: perspective camera, vertical paper cards, floor prints,
# simple 3D meshes (buildings), soft floor shadows and per-layer paper filters, written out as SVG.
import math
import numpy as np
from geo2d import *  # noqa: F401,F403


# ------------------------------------------------------------------ colour
def h2c(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def c2h(c):
    c = np.clip(np.asarray(c, float), 0, 1)
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in c)


def mix(a, b, t):
    return c2h(h2c(a) * (1 - t) + h2c(b) * t)


def mul(a, k):
    return c2h(h2c(a) * k)


def tint(a, light, k):
    """Multiply a base colour by a light colour scaled by k."""
    return c2h(h2c(a) * h2c(light) * k)


# ------------------------------------------------------------------ camera
class Cam:
    def __init__(s, pos, target, lens, W=1600, H=900, sensor=36.0, shift=(0.0, 0.0)):
        s.pos = np.array(pos, float)
        t = np.array(target, float)
        f = t - s.pos
        f /= np.linalg.norm(f)
        r = np.cross(f, [0, 0, 1.0])
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        s.f, s.r, s.u = f, r, u
        s.W, s.H = W, H
        s.fpx = W * lens / sensor
        s.cx = W / 2 + shift[0] * W
        s.cy = H / 2 - shift[1] * W

    def p(s, P):
        d = np.asarray(P, float) - s.pos
        z = d @ s.f
        return np.stack([s.cx + s.fpx * (d @ s.r) / z, s.cy - s.fpx * (d @ s.u) / z], -1)

    def depth(s, P):
        return (np.asarray(P, float) - s.pos) @ s.f

    def scale(s, P):
        """Pixels per world unit at P (for a length perpendicular to the view)."""
        return s.fpx / s.depth(P)

    def view_dir(s, P):
        d = np.asarray(P, float) - s.pos
        return d / np.linalg.norm(d)


# ------------------------------------------------------------------ svg helpers
def fmt(v):
    return ('%.1f' % v).rstrip('0').rstrip('.') if abs(v) < 1e6 else '0'


def path_d(loops2d, close=True):
    out = []
    for lp in loops2d:
        lp = np.asarray(lp)
        if len(lp) < 2:
            continue
        out.append('M' + ' '.join('%s,%s' % (fmt(x), fmt(y)) for x, y in lp) + (' Z' if close else ''))
    return ' '.join(out)


def attrs(**kw):
    s = []
    for k, v in kw.items():
        if v is None:
            continue
        s.append('%s="%s"' % (k.rstrip('_').replace('_', '-'), v))
    return ' '.join(s)


class Item:
    __slots__ = ('depth', 'svg', 'band', 'shadow')

    def __init__(s, depth, svg, band=None, shadow=True):
        s.depth = depth
        s.svg = svg
        s.band = band
        s.shadow = shadow


# ------------------------------------------------------------------ the canvas
class Canvas:
    LAYERS = ('desk', 'book', 'floor', 'floorprint', 'floorshade', 'floorglow', 'back', 'backprint', 'cards', 'fx', 'post')

    def __init__(s, cam, light_dir=(0.3, 0.6, 0.75), light_col='#ffffff', amb=0.55, dif=0.55, amb_col='#ffffff',
                 shadow_col='#1a1420', edge_col='#fff3dc', edge_op=0.55, seed=1):
        s.cam = cam
        s.L = np.array(light_dir, float) / np.linalg.norm(light_dir)  # from surface toward the light
        s.light_col = light_col
        s.amb, s.dif = amb, dif
        s.amb_col = amb_col
        s.shadow_col = shadow_col
        s.edge_col, s.edge_op = edge_col, edge_op
        s.defs = []
        s.layers = {k: [] for k in s.LAYERS}
        s.items = []
        s.shadows = []
        s.uid = 0
        s.seed = seed
        s.band_opts = {}
        s.layer_attrs = {}
        s.style = ''
        s.clips = {}

    def nid(s, p='i'):
        s.uid += 1
        return '%s%d' % (p, s.uid)

    # ---- projection helpers (with near-plane clipping, so close-up cameras can sit inside the scene)
    NEAR = 0.15

    def clip_loop(s, P):
        P = np.asarray(P, float)
        dz = (P - s.cam.pos) @ s.cam.f - s.NEAR
        if np.all(dz >= 0):
            return P
        if np.all(dz < 0):
            return None
        out = []
        n = len(P)
        for i in range(n):
            a, b = P[i], P[(i + 1) % n]
            da, db = dz[i], dz[(i + 1) % n]
            if da >= 0:
                out.append(a)
            if (da >= 0) != (db >= 0):
                t = da / (da - db)
                out.append(a + (b - a) * t)
        return np.array(out) if len(out) >= 3 else None

    def clip_line(s, P):
        P = np.asarray(P, float)
        dz = (P - s.cam.pos) @ s.cam.f - s.NEAR
        if np.all(dz >= 0):
            return [P]
        runs, cur = [], []
        for i in range(len(P)):
            if dz[i] >= 0:
                if i > 0 and dz[i - 1] < 0:
                    t = dz[i - 1] / (dz[i - 1] - dz[i])
                    cur.append(P[i - 1] + (P[i] - P[i - 1]) * t)
                cur.append(P[i])
            else:
                if cur:
                    t = dz[i - 1] / (dz[i - 1] - dz[i])
                    cur.append(P[i - 1] + (P[i] - P[i - 1]) * t)
                    runs.append(np.array(cur))
                    cur = []
        if cur:
            runs.append(np.array(cur))
        return [r for r in runs if len(r) >= 2]

    def proj_loops(s, loops3, close=True):
        out = []
        for lp in loops3:
            if close:
                c = s.clip_loop(lp)
                if c is not None:
                    out.append(s.cam.p(c))
            else:
                out += [s.cam.p(r) for r in s.clip_line(lp)]
        return out

    def d3(s, loops3, close=True):
        return path_d(s.proj_loops(loops3, close), close)

    # ---- shading
    bounce = 0.0
    bounce_col = '#ffffff'

    def shade(s, base, n, k_amb=None, k_dif=None):
        n = np.asarray(n, float)
        n = n / (np.linalg.norm(n) + 1e-12)
        a = s.amb if k_amb is None else k_amb
        d = s.dif if k_dif is None else k_dif
        lam = max(0.0, float(n @ s.L))
        sky = 0.5 + 0.5 * float(n[2])  # surfaces facing up see more of the sky
        c = h2c(base) * (a * (0.75 + 0.25 * sky) * h2c(s.amb_col) + d * lam * h2c(s.light_col)
                         + s.bounce * (1 - abs(float(n[2]))) * h2c(s.bounce_col))
        return c2h(c)

    # ---- gradients
    def lingrad(s, p0, p1, stops, units='userSpaceOnUse'):
        gid = s.nid('g')
        st = ''.join('<stop offset="%.3f" stop-color="%s"%s/>' % (o, c, (' stop-opacity="%.3f"' % a) if a is not None else '')
                     for o, c, *rest in stops for a in [rest[0] if rest else None])
        s.defs.append('<linearGradient id="%s" gradientUnits="%s" x1="%s" y1="%s" x2="%s" y2="%s">%s</linearGradient>'
                      % (gid, units, fmt(p0[0]), fmt(p0[1]), fmt(p1[0]), fmt(p1[1]), st))
        return 'url(#%s)' % gid

    def radgrad(s, c, r, stops, fx=None):
        gid = s.nid('g')
        st = ''.join('<stop offset="%.3f" stop-color="%s"%s/>' % (o, col, (' stop-opacity="%.3f"' % a) if a is not None else '')
                     for o, col, *rest in stops for a in [rest[0] if rest else None])
        rx, ry = (r, r) if np.isscalar(r) else r
        if rx == ry:
            s.defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="%s" cy="%s" r="%s">%s</radialGradient>'
                          % (gid, fmt(c[0]), fmt(c[1]), fmt(rx), st))
        else:
            s.defs.append('<radialGradient id="%s" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="1" '
                          'gradientTransform="translate(%s %s) scale(%s %s)">%s</radialGradient>'
                          % (gid, fmt(c[0]), fmt(c[1]), fmt(rx), fmt(ry), st))
        return 'url(#%s)' % gid

    def clip3(s, loops3):
        cid = s.nid('cp')
        s.defs.append('<clipPath id="%s"><path d="%s" clip-rule="evenodd"/></clipPath>' % (cid, s.d3(loops3)))
        return 'url(#%s)' % cid

    # ---- adding things
    def add(s, layer, svg):
        s.layers[layer].append(svg)

    def item(s, depth, svg, band=None, shadow=True):
        it = Item(depth, svg if isinstance(svg, list) else [svg], band, shadow)
        s.items.append(it)
        return it

    def path(s, loops3, fill, close=True, **kw):
        return '<path d="%s" %s/>' % (s.d3(loops3, close), attrs(fill=fill, **kw))

    # vertical card: loops in (u, v) mapped to origin + u*U + v*Z
    def card_loops3(s, loops_uv, origin, rot=0.0, lean=0.0):
        ox, oy, oz = origin
        U = np.array([math.cos(rot), math.sin(rot), 0.0])
        V = np.array([0.0, math.sin(lean), math.cos(lean)])  # lean > 0 tips the card back (+y)
        out = []
        for lp in loops_uv:
            lp = np.asarray(lp, float)
            P = np.array([ox, oy, oz]) + lp[:, :1] * U + lp[:, 1:2] * V
            out.append(P)
        return out

    def card(s, loops_uv, origin, fill, rot=0.0, lean=0.0, depth=None, band=None, shadow=True, cast=True,
             extra=None, **kw):
        L3 = s.card_loops3(loops_uv, origin, rot, lean)
        if depth is None:
            # sort cards by where they stand, not by how tall they are
            allp = np.concatenate(L3)
            base = np.array([allp[:, 0].mean(), allp[:, 1].mean(), origin[2]])
            depth = float(s.cam.depth(base))
        svg = ['<path d="%s" %s/>' % (s.d3(L3), attrs(fill=fill, fill_rule='evenodd', **kw))]
        if extra:
            svg += extra
        it = s.item(depth, svg, band, shadow)
        if cast:
            s.cast(L3, strength='evenodd' if len(L3) > 1 else 1.0)
        return it, L3

    def floor(s, loops_xy, fill, z=0.0, layer='floorprint', **kw):
        L3 = [np.column_stack([np.asarray(lp)[:, 0], np.asarray(lp)[:, 1], np.full(len(lp), z)]) for lp in loops_xy]
        s.add(layer, '<path d="%s" %s/>' % (s.d3(L3), attrs(fill=fill, fill_rule='evenodd', **kw)))
        return L3

    def floor_line(s, pts_xy, stroke, width, z=0.0, layer='floorprint', **kw):
        P = np.column_stack([np.asarray(pts_xy)[:, 0], np.asarray(pts_xy)[:, 1], np.full(len(pts_xy), z)])
        s.add(layer, '<path d="%s" %s/>' % (s.d3([P], close=False),
                                             attrs(fill='none', stroke=stroke, stroke_width=width, stroke_linecap='round',
                                                   stroke_linejoin='round', **kw)))

    # ---- shadows: project outlines onto z=0 along the light
    def cast(s, loops3, strength=1.0):
        Lz = s.L[2]
        if Lz <= 0.05:
            return
        out = []
        for P in loops3:
            P = np.asarray(P, float)
            t = P[:, 2] / Lz
            S = P - t[:, None] * s.L
            S[:, 2] = 0.0
            out.append(S)
        s.shadows.append((out, strength))

    def shadow_poly(s, loops3, strength=1.0):
        s.shadows.append(([np.asarray(P, float) for P in loops3], strength))

    # ---- meshes: list of (poly3 Nx3, base colour, opts) drawn with culling, sorted far to near
    def mesh(s, faces, depth=None, band=None, cull=True, shadow=True, cast=True, outline=None, outline_w=0.6,
             extra_after=None, extra_before=None):
        cam = s.cam
        drawn = []
        for f in faces:
            P = np.asarray(f[0], float)
            base = f[1]
            opt = f[2] if len(f) > 2 else {}
            c = P.mean(0)
            n = np.cross(P[1] - P[0], P[2] - P[0])
            if np.linalg.norm(n) < 1e-12 and len(P) > 3:
                n = np.cross(P[2] - P[0], P[3] - P[0])
            n = n / (np.linalg.norm(n) + 1e-12)
            v = cam.view_dir(c)
            facing = float(n @ (-v))
            if cull and facing <= 0 and not opt.get('two_sided'):
                continue
            if opt.get('two_sided') and facing < 0:
                n = -n
            col = opt.get('flat') or s.shade(base, n, opt.get('amb'), opt.get('dif'))
            dk = cam.depth(c) + opt.get('bias', 0.0)
            pd = path_d([cam.p(P)])
            a = dict(fill=col)
            sw = opt.get('stroke_w', outline_w)
            a['stroke'] = opt.get('stroke', col if outline is None else outline)
            a['stroke-width'] = sw
            a['stroke-linejoin'] = 'round'
            if 'opacity' in opt:
                a['opacity'] = opt['opacity']
            svg = '<path d="%s" %s/>' % (pd, ' '.join('%s="%s"' % kv for kv in a.items()))
            drawn.append((dk, svg, opt.get('after', [])))
        drawn.sort(key=lambda t: -t[0])
        svg = list(extra_before or [])
        for dk, sv, aft in drawn:
            svg.append(sv)
            svg.extend(aft)
        if extra_after:
            svg += extra_after
        if depth is None:
            depth = float(np.mean([cam.depth(np.asarray(f[0], float).mean(0)) for f in faces]))
        it = s.item(depth, svg, band, shadow)
        if cast:
            s.cast([np.asarray(f[0], float) for f in faces])
        return it

    # ------------------------------------------------------------------ filters
    def paper_filter(s, fid, seed, freq=0.0065, mottle=0.55, shadow=(3, 5, 4.0, 0.42), edge=1.4, edge_col=None,
                     edge_op=None, fx=None, fy=None, grain=0.0):
        fx = freq if fx is None else fx
        fy = freq if fy is None else fy
        k = mottle
        parts = ['<filter id="%s" x="-3%%" y="-3%%" width="106%%" height="106%%" color-interpolation-filters="sRGB">' % fid]
        parts.append('<feTurbulence type="fractalNoise" baseFrequency="%.4f %.4f" numOctaves="4" seed="%d" result="t"/>'
                     % (fx, fy, seed))
        parts.append('<feColorMatrix in="t" type="matrix" values="%.3f 0 0 0 %.3f  %.3f 0 0 0 %.3f  %.3f 0 0 0 %.3f  0 0 0 0 1" result="g"/>'
                     % ((2 * k, 0.5 - k) * 3))
        parts.append('<feBlend in="g" in2="SourceGraphic" mode="soft-light" result="b"/>')
        parts.append('<feComposite in="b" in2="SourceAlpha" operator="in" result="tex"/>')
        merge = []
        if shadow:
            dx, dy, blur, op = shadow
            parts.append('<feGaussianBlur in="SourceAlpha" stdDeviation="%.2f" result="sbl"/>' % blur)
            parts.append('<feOffset in="sbl" dx="%.2f" dy="%.2f" result="sof"/>' % (dx, dy))
            parts.append('<feFlood flood-color="%s" flood-opacity="%.3f"/>' % (s.shadow_col, op))
            parts.append('<feComposite in2="sof" operator="in" result="sh"/>')
            merge.append('sh')
        merge.append('tex')
        if edge:
            ec = edge_col or s.edge_col
            eo = s.edge_op if edge_op is None else edge_op
            parts.append('<feOffset in="SourceAlpha" dx="0" dy="%.2f" result="adn"/>' % edge)
            parts.append('<feComposite in="SourceAlpha" in2="adn" operator="out" result="ed"/>')
            parts.append('<feFlood flood-color="%s" flood-opacity="%.3f"/>' % (ec, eo))
            parts.append('<feComposite in2="ed" operator="in" result="hl"/>')
            merge.append('hl')
        parts.append('<feMerge>%s</feMerge>' % ''.join('<feMergeNode in="%s"/>' % m for m in merge))
        parts.append('</filter>')
        s.defs.append(''.join(parts))
        return 'url(#%s)' % fid

    def blur_filter(s, fid, std):
        s.defs.append('<filter id="%s" x="-20%%" y="-20%%" width="140%%" height="140%%"><feGaussianBlur stdDeviation="%.2f"/></filter>'
                      % (fid, std))
        return 'url(#%s)' % fid

    # ------------------------------------------------------------------ output
    def render(s, band_gap=0.9, band_default=None, floor_filter=None, back_filter=None, shadow_blur=7.0,
               shadow_op=0.32, post=True, grain=0.07, vignette=0.45, desk_col='#1b1716'):
        W, H = s.cam.W, s.cam.H
        out = []
        # bands: consecutive (far to near) items grouped while their depth spread stays within band_gap
        items = sorted(s.items, key=lambda it: -it.depth)
        bands = []
        for it in items:
            key = it.band
            if bands and key is None and bands[-1]['key'] is None and (bands[-1]['d0'] - it.depth) <= band_gap:
                bands[-1]['items'].append(it)
                continue
            if bands and key is not None and bands[-1]['key'] == key:
                bands[-1]['items'].append(it)
                continue
            bands.append({'key': key, 'd0': it.depth, 'items': [it]})
        body = []
        # floor shadows
        if s.shadows:
            fid = s.blur_filter(s.nid('fsb'), shadow_blur)
            sh = []
            for loops, strength in s.shadows:
                if strength == 'evenodd':
                    sh.append('<path d="%s" fill="%s" fill-rule="evenodd"/>' % (s.d3(loops), s.shadow_col))
                    continue
                for lp in loops:
                    sh.append('<path d="%s" fill="%s"/>' % (s.d3([lp]), s.shadow_col))
            s.layers['floorshade'].insert(0, '<g filter="%s" opacity="%.3f">%s</g>' % (fid, shadow_op, ''.join(sh)))
        for name in s.LAYERS:
            if name == 'cards':
                for bi, b in enumerate(bands):
                    opts = s.band_opts.get(b['key'], band_default or {})
                    if isinstance(opts, dict) and 'filter' in opts:
                        body.append('<g filter="%s"%s>%s</g>' % (opts['filter'], (' opacity="%s"' % opts['opacity']) if 'opacity' in opts else '',
                                                                 ''.join(sv for it in b['items'] for sv in it.svg)))
                        continue
                    if opts is False:
                        body.append('<g>%s</g>' % ''.join(sv for it in b['items'] for sv in it.svg))
                        continue
                    fid = s.nid('pb')
                    flt = s.paper_filter(fid, seed=s.seed * 97 + bi * 13 + 5, **opts)
                    body.append('<g filter="%s">%s</g>' % (flt, ''.join(sv for it in b['items'] for sv in it.svg)))
                continue
            content = s.layers[name]
            if not content:
                continue
            la = s.layer_attrs.get(name, '')
            if name in ('floor', 'floorprint') and floor_filter is not None and name == 'floor':
                # floor base and prints share one paper filter
                body.append('<g filter="%s" %s>%s%s</g>' % (floor_filter, la, ''.join(content), ''.join(s.layers['floorprint'])))
                continue
            if name == 'floorprint' and floor_filter is not None:
                continue
            if name in ('back', 'backprint') and back_filter is not None:
                if name == 'back':
                    body.append('<g filter="%s" %s>%s%s</g>' % (back_filter, la, ''.join(content), ''.join(s.layers['backprint'])))
                continue
            body.append('<g %s>%s</g>' % (la, ''.join(content)))
        if post:
            # grain via a turbulence-driven gray layer in overlay mode
            gid2 = s.nid('grain')
            s.defs.append('<filter id="%s" x="0" y="0" width="100%%" height="100%%" color-interpolation-filters="sRGB">'
                          '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="11" result="t"/>'
                          '<feColorMatrix in="t" type="matrix" values="1 0 0 0 0  1 0 0 0 0  1 0 0 0 0  0 0 0 0 1"/>'
                          '</filter>' % gid2)
            body.append('<rect x="0" y="0" width="%d" height="%d" filter="url(#%s)" opacity="%.3f" style="mix-blend-mode:overlay"/>'
                        % (W, H, gid2, grain))
            vg = s.radgrad((W / 2, H * 0.48), (W * 0.75, H * 0.8), [(0.55, '#000000', 0.0), (1.0, '#000000', vignette)])
            body.append('<rect x="0" y="0" width="%d" height="%d" fill="%s"/>' % (W, H, vg))
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
               ('<style>%s</style>' % s.style) if s.style else '',
               '<defs>%s</defs>' % ''.join(s.defs),
               '<rect x="0" y="0" width="%d" height="%d" fill="%s"/>' % (W, H, desk_col)]
        svg += body
        svg.append('</svg>')
        return '\n'.join(svg)
