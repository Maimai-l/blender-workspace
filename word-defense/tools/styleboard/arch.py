# arch.py - Chinese timber halls, curved roofs, city walls, gates and houses for eng.Canvas.
# Everything is built in a local frame (x along the facade, y toward the back, z up) and returned as
# "parts": (key point, [svg]) pairs that assemble() sorts far to near into one Item.
import math
import numpy as np
from eng import h2c, c2h, mix, mul, path_d, fmt


class Frame:
    def __init__(s, cx, cy, rot=0.0, z=0.0):
        s.c = np.array([cx, cy, z], float)
        s.ca, s.sa = math.cos(rot), math.sin(rot)

    def w(s, P):
        P = np.asarray(P, float)
        X, Y, Z = P[..., 0], P[..., 1], P[..., 2]
        return np.stack([s.c[0] + X * s.ca - Y * s.sa, s.c[1] + X * s.sa + Y * s.ca, s.c[2] + Z], -1)

    def vec(s, V):
        V = np.asarray(V, float)
        return np.array([V[0] * s.ca - V[1] * s.sa, V[0] * s.sa + V[1] * s.ca, V[2]])


def newell(P):
    P = np.asarray(P, float)
    Q = np.roll(P, -1, axis=0)
    n = np.array([np.sum((P[:, 1] - Q[:, 1]) * (P[:, 2] + Q[:, 2])),
                  np.sum((P[:, 2] - Q[:, 2]) * (P[:, 0] + Q[:, 0])),
                  np.sum((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1]))])
    return n / (np.linalg.norm(n) + 1e-12)


def prof(t, a=0.32):
    return a * t + (1 - a) * t * t


class Builder:
    """Collects faces and overlay strokes for one building; emits one sorted part list."""

    def __init__(s, cv, fr):
        s.cv, s.fr = cv, fr
        s.faces = []      # (poly3 world, colour, opts)
        s.parts = []      # (world key point, [svg]) for separately sorted pieces

    # ---- faces
    def face(s, P_local, col, out=None, **opt):
        P_local = np.asarray(P_local, float)
        if out is not None:
            if float(newell(P_local) @ np.asarray(out, float)) < 0:
                P_local = P_local[::-1]
        s.faces.append((s.fr.w(P_local), col, opt))

    def quad_strip(s, pts_fn, nu, nt, col, u0=-1.0, u1=1.0, t0=0.0, t1=1.0, **opt):
        us = np.linspace(u0, u1, nu + 1)
        ts = np.linspace(t0, t1, nt + 1)
        G = np.array([[pts_fn(u, t) for u in us] for t in ts])  # (nt+1, nu+1, 3)
        for i in range(nt):
            for j in range(nu):
                q = [G[i, j], G[i, j + 1], G[i + 1, j + 1], G[i + 1, j]]
                s.face(q, col, **opt)
        return G

    def box(s, x0, x1, y0, y1, z0, z1, col, top=None, sides=None, front=None, back=None, details=None, **opt):
        """details: {'front': [(polys_st, colour, opts)], 'left': ..., 'right': ..., 'back': ...}; st in face units."""
        details = details or {}
        P = lambda x, y, z: (x, y, z)
        fr_col = front or col
        sd_col = sides or col
        F = {
            'front': ([P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)], fr_col, (x0, y0, z0), (1, 0, 0), (0, 0, 1)),
            'back': ([P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)], back or col, (x1, y1, z0), (-1, 0, 0), (0, 0, 1)),
            'left': ([P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)], sd_col, (x0, y1, z0), (0, -1, 0), (0, 0, 1)),
            'right': ([P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)], sd_col, (x1, y0, z0), (0, 1, 0), (0, 0, 1)),
        }
        for k, (poly, c, O, A, B) in F.items():
            aft = []
            for polys, dc, dopt in details.get(k, []):
                aft.append((polys, dc, dopt, O, A, B))
            s.face(poly, c, _details=aft, **opt)
        if top is not False:
            s.face([P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)], top or col, **opt)

    # ---- emit
    def emit(s, key=None):
        cv, cam, fr = s.cv, s.cv.cam, s.fr
        mirrored = isinstance(fr, MirrorFrame)
        drawn = []
        for P, col, opt in s.faces:
            P = np.asarray(P, float)
            c = P.mean(0)
            n = newell(P)
            v = cam.view_dir(c)
            facing = float(n @ (-v))
            if mirrored:
                facing = -facing
                n = -n
            if facing <= 1e-4 and not opt.get('two_sided'):
                continue
            if facing < 0:
                n = -n
            shade_col = opt.get('flat') or cv.shade(col, n, opt.get('amb'), opt.get('dif'))
            Pc = cv.clip_loop(P)
            if Pc is None:
                continue
            svg = ['<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"%s/>'
                   % (path_d([cam.p(Pc)]), shade_col, opt.get('stroke', shade_col), opt.get('sw', 0.7),
                      (' opacity="%s"' % opt['opacity']) if 'opacity' in opt else '')]
            for polys, dc, dopt, O, A, B in opt.get('_details', []):
                O = np.asarray(O, float); A = np.asarray(A, float); B = np.asarray(B, float)
                loops = []
                for lp in polys:
                    lp = np.asarray(lp, float)
                    Pl = O[None, :] + lp[:, :1] * A[None, :] + lp[:, 1:2] * B[None, :]
                    # nudge details off the face toward the viewer side
                    Pl = Pl + n_local(A, B) * 0.004
                    Pw = cv.clip_loop(fr.w(Pl))
                    if Pw is not None:
                        loops.append(cam.p(Pw))
                col2 = dopt.get('flat') or cv.shade(dc, n, dopt.get('amb'), dopt.get('dif'))
                extra = ''
                if dopt.get('stroke'):
                    extra = ' stroke="%s" stroke-width="%s"' % (dopt['stroke'], dopt.get('sw', 0.6))
                svg.append('<path d="%s" fill="%s" fill-rule="evenodd"%s%s/>'
                           % (path_d(loops), col2, extra, (' opacity="%s"' % dopt['opacity']) if 'opacity' in dopt else ''))
            svg += opt.get('after', [])
            dist = float(np.linalg.norm(c - cam.pos)) + opt.get('bias', 0.0)
            drawn.append((dist, svg))
        drawn.sort(key=lambda t: -t[0])
        out = []
        for _, sv in drawn:
            out += sv
        return out


def n_local(A, B):
    n = np.cross(np.asarray(A, float), np.asarray(B, float))
    return n / (np.linalg.norm(n) + 1e-12)


# ------------------------------------------------------------------ roofs
class Roof:
    """A curved Chinese roof over the eave rectangle [-ex, ex] x [-ey, ey] (local), eaves at ze, rise H.
    kind: 'hip' 庑殿, 'xieshan' 歇山, 'gable' 悬山/硬山, 'pyramid' 攒尖."""

    def __init__(s, ze, ex, ey, H, kind='xieshan', lift=0.0, cr=None, a=0.32, tg=0.45, overhang_x=0.0):
        s.ze, s.ex, s.ey, s.H, s.kind = ze, ex, ey, H, kind
        s.lift = lift
        s.cr = cr if cr is not None else ey * 0.95
        s.a = a
        s.tg = tg
        s.xg = ex - tg * ey
        if kind == 'hip':
            s.xr = max(0.0, ex - ey)
        elif kind == 'xieshan':
            s.xr = s.xg
        elif kind == 'pyramid':
            s.xr = 0.0
        else:
            s.xr = ex

    def z(s, t, X=None, Y=None, side=False):
        z = s.ze + s.H * prof(t, s.a)
        if s.lift and X is not None:
            cr = s.cr
            if not side:
                k = np.clip((np.abs(X) - (s.ex - cr)) / cr, 0, 1) ** 2
            else:
                k = np.clip((np.abs(Y) - (s.ey - cr)) / cr, 0, 1) ** 2
            z = z + s.lift * k * (1 - t) ** 1.6
        return z

    def xr_at(s, t):
        if s.kind == 'gable':
            return s.ex
        if s.kind == 'xieshan':
            return max(s.xg, s.ex - t * s.ey) if t < s.tg else s.xg
        return max(0.0, s.ex - t * s.ey)

    def front_pt(s, u, t, sgn=-1):
        X = u * s.xr_at(t)
        Y = sgn * s.ey * (1 - t)
        return (X, Y, float(s.z(t, X, Y)))

    def side_top(s):
        return {'hip': 1.0, 'pyramid': 1.0, 'xieshan': s.tg}.get(s.kind, 0.0)

    def side_pt(s, v, t, sgn=-1):
        X = sgn * (s.ex - t * s.ey)
        Y = v * s.ey * (1 - t)
        return (X, Y, float(s.z(t, X, Y, side=True)))

    def build(s, B, col, nu=14, nt=7, ridge_col=None, gable_col=None, tile_col=None, fascia_col=None,
              tile_step=0.11, ridge_h=0.07, ornament=True, gable_trim=None, finial=None, fascia_t=None, t_top=None,
              edge_col=None):
        cv, cam, fr = B.cv, B.cv.cam, B.fr
        ridge_col = ridge_col or mul(col, 0.62)
        tile_col = tile_col or mul(col, 0.7)
        fascia_col = fascia_col or mul(col, 0.55)
        fascia_t = fascia_t if fascia_t is not None else 0.045 + 0.02 * s.H
        overlays = []
        ridge_h = min(ridge_h, 0.035 + 0.05 * s.ey)
        T1 = 1.0 if t_top is None else t_top
        # main slopes (front, back)
        for sgn in (-1, 1):
            B.quad_strip(lambda u, t: s.front_pt(u, t, sgn), nu, max(2, int(nt * T1 + 0.5)), col, t0=0.0, t1=T1, out=(0, sgn, 1.0))
        # side slopes
        st = s.side_top() if t_top is None else min(s.side_top(), t_top)
        if st > 0:
            for sgn in (-1, 1):
                ntt = max(2, int(nt * st + 0.5))
                B.quad_strip(lambda v, t: s.side_pt(v, t, sgn), max(4, nu // 2), ntt, col, t0=0.0, t1=st, out=(sgn, 0, 1.0))
        # gable triangles (歇山 山花) and gable ends
        if s.kind in ('xieshan', 'gable') and t_top is None:
            t0 = s.tg if s.kind == 'xieshan' else 0.0
            xg = s.xg if s.kind == 'xieshan' else s.ex
            gc = gable_col or mul(col, 1.0)
            for sgn in (-1, 1):
                ts = np.linspace(t0, 1.0, 9)
                top_f = [(sgn * xg, -s.ey * (1 - t), float(s.z(t))) for t in ts]
                top_b = [(sgn * xg, s.ey * (1 - t), float(s.z(t))) for t in ts[::-1]]
                zb = float(s.z(t0))
                poly = top_f + top_b[1:]
                B.face(poly, gc, out=(sgn, 0, 0))
        # fascia under the eave edge (front, back and hip/xieshan sides)
        def fascia(sgn, side):
            vs = np.linspace(-1, 1, nu * 2 + 1)
            if not side:
                top = [s.front_pt(u, 0.0, sgn) for u in vs]
            else:
                top = [s.side_pt(v, 0.0, sgn) for v in vs]
            bot = [(p[0], p[1], p[2] - fascia_t) for p in top]
            poly = top + bot[::-1]
            out = (sgn, 0, 0) if side else (0, sgn, 0)
            B.face(poly, fascia_col, out=out, amb=0.75, dif=0.35, bias=-0.02)
        for sgn in (-1, 1):
            fascia(sgn, False)
            if st > 0:
                fascia(sgn, True)
        # tile rows on the slopes that face the camera
        def visible(sample_local, normal_local):
            P = fr.w(np.array(sample_local))
            n = fr.vec(np.array(normal_local))
            return float(n @ (cam.pos - P)) > 0
        lw_scale = cam.scale(fr.w(np.array([0, 0, s.ze])))
        tw = max(0.35, 0.010 * lw_scale)
        rows = []
        for sgn in (-1, 1):
            if not visible(s.front_pt(0, 0.4, sgn), (0, sgn * 0.6, 0.8)):
                continue
            nx = int(2 * s.ex / tile_step)
            for i in range(nx + 1):
                X = -s.ex + (i + 0.5) * (2 * s.ex / (nx + 1))
                if s.kind in ('gable',):
                    tmax = 1.0
                elif s.kind == 'xieshan':
                    tmax = 1.0 if abs(X) <= s.xg else min(s.tg, (s.ex - abs(X)) / s.ey)
                else:
                    tmax = min(1.0, (s.ex - abs(X)) / s.ey)
                tmax = min(tmax, T1)
                if tmax <= 0.04:
                    continue
                ts = np.linspace(0.0, tmax * 0.985, 7)
                pts = [(X, sgn * s.ey * (1 - t), float(s.z(t, X, sgn * s.ey * (1 - t)))) for t in ts]
                rows.append(fr.w(np.array(pts)))
        if st > 0:
            for sgn in (-1, 1):
                if not visible(s.side_pt(0, 0.3, sgn), (sgn * 0.6, 0, 0.8)):
                    continue
                ny = int(2 * s.ey / tile_step)
                for j in range(ny + 1):
                    Y = -s.ey + (j + 0.5) * (2 * s.ey / (ny + 1))
                    tmax = min(st, (s.ey - abs(Y)) / s.ey)
                    if tmax <= 0.04:
                        continue
                    ts = np.linspace(0.0, tmax * 0.985, 6)
                    pts = [(sgn * (s.ex - t * s.ey), Y, float(s.z(t, sgn * (s.ex - t * s.ey), Y, side=True))) for t in ts]
                    rows.append(fr.w(np.array(pts)))
        if rows:
            overlays.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" opacity="0.55"/>'
                            % (path_d(cv.proj_loops(rows, close=False), close=False), tile_col, fmt(tw)))
        # eave edge highlight (tile ends)
        edge = []
        vs = np.linspace(-1, 1, 41)
        for sgn in (-1, 1):
            if visible(s.front_pt(0, 0.0, sgn), (0, sgn, 0.3)):
                edge.append(fr.w(np.array([s.front_pt(u, 0.0, sgn) for u in vs])))
            if st > 0 and visible(s.side_pt(0, 0.0, sgn), (sgn, 0, 0.3)):
                edge.append(fr.w(np.array([s.side_pt(v, 0.0, sgn) for v in vs])))
        if edge:
            overlays.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" opacity="0.8"/>'
                            % (path_d(cv.proj_loops(edge, close=False), close=False), mix(col, '#ffffff', 0.25), fmt(max(0.5, 0.012 * lw_scale))))
        # hip ridges (戗脊 / 垂脊)
        rw = max(0.8, ridge_h * 0.55 * lw_scale)
        hips = []
        if s.kind in ('hip', 'pyramid', 'xieshan'):
            t_hi = 1.0 if s.kind != 'xieshan' else s.tg
            t_hi = min(t_hi, T1)
            for sx in (-1, 1):
                for sy in (-1, 1):
                    ts = np.linspace(t_hi, 0.0, 9)
                    pts = [(sx * (s.ex - t * s.ey), sy * s.ey * (1 - t), float(s.z(t, sx * (s.ex - t * s.ey), sy * s.ey * (1 - t))) + 0.01)
                           for t in ts]
                    P = fr.w(np.array(pts))
                    # skip the ones hidden behind the roof (back corners), roughly
                    hips.append((float(np.linalg.norm(P.mean(0) - cam.pos)), P))
        if s.kind in ('xieshan', 'gable') and t_top is None:
            t0 = s.tg if s.kind == 'xieshan' else 0.0
            xg = s.xg if s.kind == 'xieshan' else s.ex
            for sx in (-1, 1):
                for sy in (-1, 1):
                    ts = np.linspace(1.0, t0, 7)
                    pts = [(sx * xg, sy * s.ey * (1 - t), float(s.z(t)) + 0.012) for t in ts]
                    P = fr.w(np.array(pts))
                    hips.append((float(np.linalg.norm(P.mean(0) - cam.pos)), P))
        # main ridge
        ridge = None
        if s.xr > 0.01 and t_top is None:
            xs = np.linspace(-s.xr, s.xr, 9)
            ridge = fr.w(np.array([(x, 0.0, s.ze + s.H + ridge_h * 0.5) for x in xs]))
        # ornaments (鸱吻): small upturned curls at the ridge ends
        orn = []
        if ornament and ridge is not None:
            for sx in (-1, 1):
                x = sx * s.xr
                h = min(ridge_h * 3.0, 0.16 * s.ey + 0.02)
                z0 = s.ze + s.H
                # centre line of the hook: up from the ridge end, then curling inward and down
                cl = []
                for k in range(13):
                    a = k / 12
                    if a < 0.5:
                        u = a / 0.5
                        cl.append((x + sx * 0.04 * h * u, z0 + h * (0.15 + 0.85 * u)))
                    else:
                        u = (a - 0.5) / 0.5
                        ang = math.pi * u * 1.05
                        cl.append((x + sx * 0.04 * h - sx * 0.32 * h * math.sin(ang), z0 + h * (1.0 - 0.0 + 0.0) - 0.32 * h * (1 - math.cos(ang)) * 0.9))
                cl = np.array(cl)
                wid = np.linspace(0.30, 0.10, len(cl)) * h
                tang = np.gradient(cl, axis=0)
                tang /= (np.linalg.norm(tang, axis=1, keepdims=True) + 1e-12)
                nrm = np.stack([-tang[:, 1], tang[:, 0]], 1)
                L = cl + nrm * wid[:, None] / 2
                R = cl - nrm * wid[:, None] / 2
                poly2 = np.concatenate([L, R[::-1]])
                orn.append(fr.w(np.array([(p[0], 0.0, p[1]) for p in poly2])))
        rc = ridge_col
        # draw back hips first, then ridge, then front hips
        hips.sort(key=lambda t: -t[0])
        mid = float(np.linalg.norm(fr.w(np.array([0, 0, s.ze + s.H])) - cam.pos))
        for d, P in hips:
            if d > mid:
                overlays.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>'
                                % (path_d(cv.proj_loops([P], close=False), close=False), rc, fmt(rw * 0.8)))
        if ridge is not None:
            overlays.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="butt"/>'
                            % (path_d(cv.proj_loops([ridge], close=False), close=False), rc, fmt(max(1.0, ridge_h * lw_scale))))
        for P in orn:
            overlays.append('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round"/>'
                            % (path_d(cv.proj_loops([P])), rc, rc, fmt(rw * 0.5)))
        for d, P in hips:
            if d <= mid:
                overlays.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round"/>'
                                % (path_d(cv.proj_loops([P], close=False), close=False), rc, fmt(rw * 0.8)))
        if finial is not None and cam.depth(fr.w(np.array([0, 0, s.ze + s.H]))) > 0.3:
            fh, fcol = finial
            P0 = fr.w(np.array([0, 0, s.ze + s.H]))
            P1 = fr.w(np.array([0, 0, s.ze + s.H + fh]))
            a, b = cam.p(P0), cam.p(P1)
            overlays.append('<path d="M%s,%s L%s,%s" stroke="%s" stroke-width="%s" stroke-linecap="round"/>'
                            % (fmt(a[0]), fmt(a[1]), fmt(b[0]), fmt(b[1]), fcol, fmt(max(1.0, 0.05 * lw_scale))))
            r = max(1.0, 0.07 * lw_scale)
            overlays.append('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (fmt(b[0]), fmt(b[1] + r * 0.6), fmt(r), fcol))
        return overlays


def emit_building(cv, B, overlays, depth_pt, band=None, shadow=True, cast=True):
    svg = B.emit() + overlays
    P = B.fr.w(np.array(depth_pt, float))
    it = cv.item(float(cv.cam.depth(P)), svg, band, shadow)
    if cast:
        cv.cast([np.asarray(f[0], float) for f in B.faces])
    return it


# ------------------------------------------------------------------ facade details (face units: s along, t up)
def rect(s0, t0, s1, t1):
    return [(s0, t0), (s1, t0), (s1, t1), (s0, t1)]


def lattice_door(s0, t0, s1, t1, n=4):
    """A lattice door panel: outer rectangle and a grid of small openings (evenodd)."""
    loops = [rect(s0, t0, s1, t1)]
    w = (s1 - s0) / n
    hh = (t1 - t0)
    for i in range(n):
        a = s0 + i * w + w * 0.18
        b = s0 + (i + 1) * w - w * 0.18
        loops.append(rect(a, t0 + hh * 0.42, b, t1 - hh * 0.1))
    return loops


def arch_opening(s0, s1, t0, t1, n=16):
    """A round-topped (券门) opening from s0 to s1, springing at t1 - half width."""
    r = (s1 - s0) / 2
    cx = (s0 + s1) / 2
    ts = t1 - r
    pts = [(s0, t0), (s1, t0), (s1, ts)]
    for k in range(1, n):
        a = math.pi * k / n
        pts.append((cx + r * math.cos(a), ts + r * math.sin(a)))
    pts.append((s0, ts))
    return pts


def trap_opening(s0, s1, t0, t1, slope=0.25):
    """A trapezoidal timber-lintel gate opening (唐宋过梁式)."""
    w = s1 - s0
    d = w * slope
    return [(s0, t0), (s1, t0), (s1 - d, t1), (s0 + d, t1)]


# ------------------------------------------------------------------ halls
def hall(cv, cx, cy, z0, W, Dp, Hb, roof_H, kind='xieshan', rot=0.0, bays=5, wall='#c9b79a', column='#8a3a2a',
         roof='#4a4a52', base='#9a8f80', base_h=0.12, overhang=0.32, lift=0.18, lit=None, door=None, gable=None,
         ridge=None, tile=None, upper=None, emit=True, finial=None, platform_pad=0.12, dark_inside='#2a2026',
         ornament=True, roof_a=0.32, nu=14, nt=7, tg=0.45):
    """A rectangular hall: platform, columns and walls, roof. W, Dp: body size; Hb: body (column) height.
    lit: window/door colour when lit from inside (None = dark lattice). Returns (Builder, overlays)."""
    fr = Frame(cx, cy, rot, z0)
    B = Builder(cv, fr)
    bx, by = W / 2, Dp / 2
    # platform
    if base_h > 0:
        px, py = bx + platform_pad, by + platform_pad
        B.box(-px, px, -py, py, 0, base_h, base, top=mix(base, '#ffffff', 0.08), bias=4.0)
    zb = base_h
    # body with facade details
    det_front = []
    bw = W / bays
    colw = min(0.07, bw * 0.16)
    for i in range(bays + 1):
        s = i * bw
        det_front.append(([rect(max(0, s - colw / 2), 0, min(W, s + colw / 2), Hb)], column, {}))
    for i in range(bays):
        s0 = i * bw + colw / 2 + bw * 0.06
        s1 = (i + 1) * bw - colw / 2 - bw * 0.06
        if lit:
            det_front.append(([rect(s0, Hb * 0.08, s1, Hb * 0.86)], lit, {'flat': lit}))
            det_front.append((lattice_grid(s0, Hb * 0.08, s1, Hb * 0.86, 3, 5), mul(column, 0.8), {'flat': mul(column, 0.55)}))
        else:
            det_front.append((lattice_door(s0, Hb * 0.08, s1, Hb * 0.86), mul(column, 0.85), {}))
    # a beam band under the eaves
    det_front.append(([rect(0, Hb * 0.86, W, Hb)], mul(column, 0.9), {}))
    det_side = []
    sb = Dp / max(2, round(Dp / bw))
    nsb = int(round(Dp / sb))
    for i in range(nsb + 1):
        s = i * sb
        det_side.append(([rect(max(0, s - colw / 2), 0, min(Dp, s + colw / 2), Hb)], column, {}))
    det_side.append(([rect(0, Hb * 0.86, Dp, Hb)], mul(column, 0.9), {}))
    B.box(-bx, bx, -by, by, zb, zb + Hb, wall, top=False, bias=2.0,
          details={'front': det_front, 'back': det_front, 'left': det_side, 'right': det_side})
    # roof
    R = Roof(zb + Hb, bx + overhang, by + overhang, roof_H, kind=kind, lift=lift, a=roof_a, tg=tg)
    ov = R.build(B, roof, nu=nu, nt=nt, ridge_col=ridge, gable_col=gable, tile_col=tile, ornament=ornament, finial=finial)
    if emit:
        return emit_building(cv, B, ov, (0, -by, zb + Hb * 0.5)), R
    return B, ov, R


def lattice_grid(s0, t0, s1, t1, nx, ny, bar=0.18):
    """Lattice bars as one evenodd shape: outer frame minus a grid of panes."""
    loops = [rect(s0, t0, s1, t1)]
    w = (s1 - s0) / nx
    h = (t1 - t0) / ny
    bx = w * bar
    by = h * bar
    for i in range(nx):
        for j in range(ny):
            loops.append(rect(s0 + i * w + bx / 2, t0 + j * h + by / 2, s0 + (i + 1) * w - bx / 2, t0 + (j + 1) * h - by / 2))
    return loops


# ------------------------------------------------------------------ multi-storey gate tower (城楼)
def facade(W, Hb, bays, column, lit=None, door_dark=None, colw=0.07, beam=True):
    det = []
    bw = W / bays
    colw = min(colw, bw * 0.16)
    for i in range(bays + 1):
        s = i * bw
        det.append(([rect(max(0, s - colw / 2), 0, min(W, s + colw / 2), Hb)], column, {}))
    for i in range(bays):
        s0 = i * bw + colw / 2 + bw * 0.07
        s1 = (i + 1) * bw - colw / 2 - bw * 0.07
        if lit:
            det.append(([rect(s0, Hb * 0.1, s1, Hb * 0.84)], lit, {'flat': lit}))
            det.append((lattice_grid(s0, Hb * 0.1, s1, Hb * 0.84, 3, 4), column, {'flat': mul(column, 0.5)}))
        else:
            det.append((lattice_door(s0, Hb * 0.1, s1, Hb * 0.84), door_dark or mul(column, 0.85), {}))
    if beam:
        det.append(([rect(0, Hb * 0.84, W, Hb)], mul(column, 0.9), {}))
    return det


def tower2(cv, cx, cy, z0, W, Dp, h1, h2, roof='#45454f', wall='#d6c6a8', column='#8a3a2a', inset=0.22, overhang=0.3,
           rise1=0.32, rise2=0.62, lift=0.2, bays=5, lit1=None, lit2=None, ridge=None, gable=None, rot=0.0, base=None,
           base_h=0.0, kind='xieshan', bal=None, emit=True, ornament=True):
    """Two-storey tower: storey 1 with a hip eave ring (腰檐), storey 2 with a top roof."""
    fr = Frame(cx, cy, rot, z0)
    B = Builder(cv, fr)
    bx1, by1 = W / 2, Dp / 2
    if base_h > 0:
        B.box(-bx1 - 0.1, bx1 + 0.1, -by1 - 0.1, by1 + 0.1, 0, base_h, base or wall, bias=6.0)
    zb = base_h
    side_bays = max(2, int(round(Dp / (W / bays))))
    B.box(-bx1, bx1, -by1, by1, zb, zb + h1, wall, top=False, bias=4.0,
          details={'front': facade(W, h1, bays, column, lit1), 'back': facade(W, h1, bays, column, lit1),
                   'left': facade(Dp, h1, side_bays, column, lit1), 'right': facade(Dp, h1, side_bays, column, lit1)})
    ex1, ey1 = bx1 + overhang, by1 + overhang
    R1 = Roof(zb + h1, ex1, ey1, rise1 / max(1e-6, prof((overhang + inset) / ey1)) , kind='hip', lift=lift * 0.8)
    t_top = (overhang + inset) / ey1
    ov1 = R1.build(B, roof, nu=12, nt=6, ridge_col=ridge, t_top=t_top, ornament=False)
    z2 = float(R1.z(t_top)) - 0.02
    bx2, by2 = bx1 - inset, by1 - inset
    W2, D2 = 2 * bx2, 2 * by2
    B2 = Builder(cv, fr)
    side2 = max(2, int(round(D2 / (W2 / max(3, bays - 2)))))
    B2.box(-bx2, bx2, -by2, by2, z2, z2 + h2, wall, top=False, bias=2.0,
           details={'front': facade(W2, h2, max(3, bays - 2), column, lit2), 'back': facade(W2, h2, max(3, bays - 2), column, lit2),
                    'left': facade(D2, h2, side2, column, lit2), 'right': facade(D2, h2, side2, column, lit2)})
    R2 = Roof(z2 + h2, bx2 + overhang, by2 + overhang, rise2, kind=kind, lift=lift)
    ov2 = R2.build(B2, roof, nu=14, nt=7, ridge_col=ridge, gable_col=gable, ornament=ornament)
    svg = B.emit() + ov1 + B2.emit() + ov2
    if emit:
        P = fr.w(np.array([0, -by1, zb + h1]))
        it = cv.item(float(cv.cam.depth(P)), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces + B2.faces])
        return it
    return svg, B.faces + B2.faces


# ------------------------------------------------------------------ city walls (城墙)
def wall_piece(cv, fr, x0, x1, T, Hw, col, top_col=None, inner_col=None, merlon=(0.16, 0.1, 0.13, 0.07),
               layer_lines=None, gates=(), parapet_col=None, inner_parapet=0.05, end_caps=True, bias=0.0, gate_col='#1d1517',
               gate_rim=None, batter=0.0):
    """One straight wall along local x from x0 to x1; the outer face looks toward -y. Returns a Builder.
    gates: (s_centre, width, height, 'arch'|'trap')."""
    B = Builder(cv, fr)
    y0, y1 = -T / 2, T / 2
    top_col = top_col or mix(col, '#ffffff', 0.1)
    inner_col = inner_col or col
    det = []
    L = x1 - x0
    if layer_lines:
        step, lc, lw = layer_lines
        k = 1
        while k * step < Hw - 0.02:
            det.append(([rect(0, k * step - lw / 2, L, k * step + lw / 2)], lc, {}))
            k += 1
    for sc, gw, gh, kind in gates:
        s0, s1 = sc - x0 - gw / 2, sc - x0 + gw / 2
        shape = arch_opening(s0, s1, 0.0, gh) if kind == 'arch' else trap_opening(s0, s1, 0.0, gh)
        rim = gate_rim or mix(col, '#000000', 0.25)
        # a rim around the opening (the depth of the gate passage)
        if kind == 'arch':
            r_out = arch_opening(s0 - 0.035, s1 + 0.035, 0.0, gh + 0.035)
        else:
            r_out = trap_opening(s0 - 0.04, s1 + 0.04, 0.0, gh + 0.04)
        det.append(([r_out], rim, {}))
        det.append(([shape], gate_col, {'flat': gate_col}))
    B.box(x0, x1, y0, y1, 0.0, Hw, col, top=top_col, back=inner_col, details={'front': det}, bias=bias + 1.0)
    # parapet with crenels on the outer edge, low parapet on the inner edge
    if merlon:
        mw, gap, mh, mt = merlon
        pc = parapet_col or col
        n = int((L + gap) / (mw + gap))
        used = n * mw + (n - 1) * gap
        start = x0 + (L - used) / 2
        # continuous low base of the parapet
        B.box(x0, x1, y0, y0 + mt, Hw, Hw + mh * 0.45, pc, top=mix(pc, '#ffffff', 0.1), bias=bias)
        for i in range(n):
            a = start + i * (mw + gap)
            B.box(a, a + mw, y0, y0 + mt, Hw + mh * 0.45, Hw + mh, pc, top=mix(pc, '#ffffff', 0.12), bias=bias - 0.01 * i)
        if inner_parapet:
            B.box(x0, x1, y1 - mt * 0.8, y1, Hw, Hw + inner_parapet, pc, top=mix(pc, '#ffffff', 0.1), bias=bias + 0.5)
    return B


def beacon(cv, cx, cy, s=1.0, col='#b88a5c', lit=True, rot=0.0, emit=True):
    """A tapered rammed-earth beacon tower (烽燧) with a small fire basket."""
    fr = Frame(cx, cy, rot)
    B = Builder(cv, fr)
    b, t, h = 0.32 * s, 0.22 * s, 0.85 * s
    P = [(-b, -b, 0), (b, -b, 0), (b, b, 0), (-b, b, 0), (-t, -t, h), (t, -t, h), (t, t, h), (-t, t, h)]
    P = [np.array(p) for p in P]
    faces = [([P[0], P[1], P[5], P[4]], (0, -1, 0.3)), ([P[1], P[2], P[6], P[5]], (1, 0, 0.3)),
             ([P[2], P[3], P[7], P[6]], (0, 1, 0.3)), ([P[3], P[0], P[4], P[7]], (-1, 0, 0.3)), ([P[4], P[5], P[6], P[7]], (0, 0, 1))]
    for poly, out in faces:
        det = []
        B.face(poly, col, out=out)
    # rammed-earth layer lines on the front
    lines = []
    for k in range(1, 7):
        z = h * k / 7
        w = b + (t - b) * z / h
        lines.append(fr.w(np.array([(-w, -w - 0.004, z), (w, -w - 0.004, z)])))
    svg = B.emit()
    lw = max(0.4, 0.012 * cv.cam.scale(fr.w(np.array([0, 0, h / 2]))))
    svg.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" opacity="0.45"/>'
               % (path_d(cv.proj_loops(lines, close=False), close=False), mul(col, 0.6), fmt(lw)))
    # small parapet hut on top
    hb = Builder(cv, Frame(cx, cy, rot, h))
    hb.box(-t * 0.8, t * 0.8, -t * 0.8, t * 0.8, 0, 0.1 * s, mul(col, 0.92))
    svg += hb.emit()
    if emit:
        it = cv.item(float(cv.cam.depth(fr.w(np.array([0, -b, h / 2])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it, fr.w(np.array([0, 0, h + 0.1 * s]))
    return svg


# ------------------------------------------------------------------ Huizhou / Jiangnan house with horse-head walls (马头墙)
def house_hz(cv, cx, cy, W, Dp, H, rise, rot=0.0, wall='#e3ded2', tile='#2b2f37', cap=None, steps=2, lit=None,
             windows=None, door=True, base='#8c8f94', emit=True, gable_w=0.06, eave=0.12, mirror=False, bias=0.0):
    """Body W (along x, the facade) x Dp (depth) x H with a gable roof along x; stepped gable walls at x = +-W/2.
    windows: list of (face, s0, t0, s1, t1, lit?)."""
    fr = MirrorFrame(cx, cy, rot) if mirror else Frame(cx, cy, rot)
    B = Builder(cv, fr)
    cap = cap or tile
    bx, by = W / 2, Dp / 2
    det = {'front': [], 'back': [], 'left': [], 'right': []}
    # plinth band
    for k, L in (('front', W), ('back', W), ('left', Dp), ('right', Dp)):
        det[k].append(([rect(0, 0, L, 0.06)], base, {}))
    for wdef in (windows or []):
        face, s0, t0, s1, t1, on = wdef
        if on:
            c = lit or '#f0b65a'
            det[face].append(([rect(s0, t0, s1, t1)], c, {'flat': c}))
            det[face].append((lattice_grid(s0, t0, s1, t1, 2, 2, 0.22), '#3a2a22', {'flat': '#4a3326'}))
        else:
            det[face].append(([rect(s0, t0, s1, t1)], '#2a2622', {}))
    if door:
        dw = min(0.22, W * 0.2)
        det['front'].append(([rect(W / 2 - dw / 2 - 0.03, 0.0, W / 2 + dw / 2 + 0.03, 0.42)], '#9a9690', {}))
        det['front'].append(([rect(W / 2 - dw / 2, 0.0, W / 2 + dw / 2, 0.38)], '#2c2523', {}))
    B.box(-bx, bx, -by, by, 0, H, wall, top=False, details=det, bias=bias + 3.0)
    # gable roof between the gable walls
    R = Roof(H, bx - gable_w * 0.5, by + eave, rise, kind='gable', lift=0.0, a=0.42)
    ov = R.build(B, tile, nu=8, nt=5, ridge_col=mul(tile, 0.8), ornament=False, tile_step=0.07, ridge_h=0.045)
    # stepped gable walls: profile along y (from front -by to back +by)
    zr = H + rise
    if steps == 2:
        prof_pts = [(-by - 0.02, H + 0.10), (-by * 0.42, H + 0.10), (-by * 0.42, H + rise * 0.62 + 0.08),
                    (-by * 0.12, H + rise * 0.62 + 0.08), (-by * 0.12, zr + 0.14)]
    else:
        prof_pts = [(-by - 0.02, H + 0.10), (-by * 0.55, H + 0.10), (-by * 0.55, H + rise * 0.45 + 0.08),
                    (-by * 0.3, H + rise * 0.45 + 0.08), (-by * 0.3, H + rise * 0.8 + 0.08), (-by * 0.1, H + rise * 0.8 + 0.08),
                    (-by * 0.1, zr + 0.14)]
    half = prof_pts
    full = half + [(-p[0], p[1]) for p in half[::-1]]
    gw = gable_w
    for sx in (-1, 1):
        x_out = sx * bx
        x_in = sx * (bx - gw)
        # outer face polygon (y, z) closed down to the eave line H
        poly_out = [(x_out, -by - 0.02, H - 0.02)] + [(x_out, y, z) for y, z in full] + [(x_out, by + 0.02, H - 0.02)]
        B.face(poly_out, wall, out=(sx, 0, 0), bias=bias - 5.0)     # the near gable covers the roof's end
        poly_in = [(x_in, -by - 0.02, H - 0.02)] + [(x_in, y, z) for y, z in full] + [(x_in, by + 0.02, H - 0.02)]
        B.face(poly_in, wall, out=(-sx, 0, 0), bias=bias + 5.0)     # the far gable sits behind the roof
        # coping caps on each horizontal step, with upturned ends
        for i in range(len(full) - 1):
            (ya, za), (yb, zb) = full[i], full[i + 1]
            if abs(za - zb) > 1e-6:
                # vertical step face of the wall (between levels): front / back facing
                out = (0, -1, 0) if zb > za and ya < 0 or (zb < za and ya > 0) else (0, 1, 0)
                if ya < 0:
                    out = (0, -1, 0)
                else:
                    out = (0, 1, 0)
                B.face([(x_out, ya, za), (x_in, ya, za), (x_in, yb, zb), (x_out, yb, zb)], wall, out=out, bias=bias - 5.1)
                continue
            # horizontal run: cap slab slightly wider than the wall
            ca, cb = ya - 0.035 * (1 if ya < yb else -1), yb + 0.035 * (1 if ya < yb else -1)
            xo, xi = x_out + sx * 0.03, x_in - sx * 0.03
            zt = za + 0.035
            y_lo, y_hi = min(ca, cb), max(ca, cb)
            # cap: top (two slopes) and sides
            mid_x = (xo + xi) / 2
            B.face([(xo, y_lo, za), (xo, y_hi, za), (mid_x, y_hi, zt), (mid_x, y_lo, zt)], cap, out=(sx, 0, 1), bias=bias - 6.0)
            B.face([(xi, y_lo, za), (xi, y_hi, za), (mid_x, y_hi, zt), (mid_x, y_lo, zt)], cap, out=(-sx, 0, 1), bias=bias - 6.0)
            # small upturned tips (马头) at both ends of the run
            for yy, d in ((y_lo, -1), (y_hi, 1)):
                tip = [(xo, yy, za + 0.01), (xi, yy, za + 0.01), (mid_x, yy + d * 0.022, zt + 0.02)]
                B.face(tip, cap, out=(0, d, 0.5), bias=bias - 6.2, two_sided=True)
    svg = B.emit() + ov
    if emit:
        it = cv.item(float(cv.cam.depth(fr.w(np.array([0, -by, H / 2])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it
    return svg, B


# ------------------------------------------------------------------ stone arch bridge (拱桥)
def arch_bridge(cv, cx, cy, span, rise, width, rot=0.0, col='#9aa0a6', deck=None, rail=None, z0=0.0, r=None, emit=True,
                hump=None, mirror=False, cull_pos=None):
    """Bridge along local x, centred at (cx, cy), water at z0. A semicircular arch of radius r under a humped deck."""
    fr = Frame(cx, cy, rot, z0)
    if mirror:
        fr = MirrorFrame(cx, cy, rot, z0)
    B = Builder(cv, fr)
    r = r or rise * 0.82
    hump = hump or rise
    th = 0.09
    L = span / 2
    xs = np.linspace(-L, L, 33)
    zd = hump * np.cos(np.clip(xs / L, -1, 1) * math.pi / 2) ** 1.3 + th  # deck top
    zd = np.maximum(zd, th)
    deck = deck or mix(col, '#ffffff', 0.15)
    rail = rail or mix(col, '#ffffff', 0.08)
    for sgn in (-1, 1):
        y = sgn * width / 2
        # side face: deck line, down to the abutment, arch cut-out
        top = [(x, y, z) for x, z in zip(xs, zd)]
        n = 20
        arch = [(r * math.cos(math.pi * k / n), y, r * math.sin(math.pi * k / n)) for k in range(n + 1)]
        poly = [(-L, y, 0.0)] + top + [(L, y, 0.0), (r, y, 0.0)] + arch[1:-1] + [(-r, y, 0.0)]
        B.face(poly, col, out=(0, sgn, 0), bias=0.0)
    # deck surface (steps)
    for i in range(len(xs) - 1):
        q = [(xs[i], -width / 2, zd[i]), (xs[i + 1], -width / 2, zd[i + 1]), (xs[i + 1], width / 2, zd[i + 1]), (xs[i], width / 2, zd[i])]
        B.face(q, deck, out=(0, 0, 1), bias=0.3)
    # arch barrel (intrados), seen through the opening
    n = 16
    for k in range(n):
        a0, a1 = math.pi * k / n, math.pi * (k + 1) / n
        q = [(r * math.cos(a0), -width / 2, r * math.sin(a0)), (r * math.cos(a1), -width / 2, r * math.sin(a1)),
             (r * math.cos(a1), width / 2, r * math.sin(a1)), (r * math.cos(a0), width / 2, r * math.sin(a0))]
        mid = (a0 + a1) / 2
        B.face(q, mul(col, 0.7), out=(-math.cos(mid), 0, -math.sin(mid)), bias=2.0)
    # low parapets along both edges
    for sgn in (-1, 1):
        y = sgn * (width / 2 - 0.025)
        for i in range(len(xs) - 1):
            q = [(xs[i], y, zd[i]), (xs[i + 1], y, zd[i + 1]), (xs[i + 1], y, zd[i + 1] + 0.11), (xs[i], y, zd[i] + 0.11)]
            B.face(q, rail, out=(0, -1, 0), two_sided=True, bias=-0.2 if sgn < 0 else 0.25)
    svg = B.emit()
    if emit:
        it = cv.item(float(cv.cam.depth(fr.w(np.array([0, -width / 2, rise / 2])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it
    return svg, B


class MirrorFrame(Frame):
    """A frame mirrored in the water plane z = z0 (for reflections)."""

    def w(s, P):
        Q = super().w(P)
        Q = np.array(Q, float)
        Q[..., 2] = 2 * s.c[2] - Q[..., 2]
        return Q


# ------------------------------------------------------------------ pagoda silhouette (for distant cards)
def pagoda_outline(n=7, base_w=0.9, top_w=0.45, storey=0.55, eave=0.28, spire=0.9, curve=0.12):
    """2D outline (u, v) of a multi-eave pagoda, centred at u = 0, standing on v = 0."""
    pts_r = []
    v = 0.0
    for i in range(n):
        w = base_w + (top_w - base_w) * i / max(1, n - 1)
        h = storey * (1.0 - 0.04 * i)
        # body
        pts_r.append((w / 2, v))
        pts_r.append((w / 2, v + h * 0.62))
        # eave: flares out with an upturned tip
        e = w / 2 + eave * (1 - 0.25 * i / n)
        pts_r.append((e, v + h * 0.62 + curve * 0.6))
        pts_r.append((e + 0.05, v + h * 0.62 + curve * 1.3))
        pts_r.append((e - 0.02, v + h * 0.62 + curve * 1.05))
        pts_r.append((w / 2 * 0.9, v + h * 0.95))
        v += h
    pts_r.append((top_w * 0.18, v))
    pts_r.append((0.03, v + spire * 0.8))
    pts_r.append((0.0, v + spire))
    left = [(-u, w) for u, w in pts_r[::-1]]
    return [[(0.0, 0.0)] + pts_r + left[1:]]


# ------------------------------------------------------------------ compounds: several parts sorted by distance as one item
class Compound:
    def __init__(s, cv):
        s.cv = cv
        s.parts = []   # (dist, svg list)
        s.faces = []

    def add(s, svg, key_world, bias=0.0):
        d = float(np.linalg.norm(np.asarray(key_world, float) - s.cv.cam.pos)) + bias
        s.parts.append((d, svg))

    def builder(s, B, ov=(), key_local=(0, 0, 0), bias=0.0):
        s.add(B.emit() + list(ov), B.fr.w(np.array(key_local, float)), bias)
        s.faces += [np.asarray(f[0], float) for f in B.faces]

    def emit(s, depth_world, band=None, cast=True):
        s.parts.sort(key=lambda t: -t[0])
        svg = []
        for _, sv in s.parts:
            svg += sv
        it = s.cv.item(float(s.cv.cam.depth(np.asarray(depth_world, float))), svg, band)
        if cast:
            s.cv.cast(s.faces)
        return it


def hall_parts(cv, cx, cy, z0, W, Dp, Hb, roof_H, **kw):
    B, ov, R = hall(cv, cx, cy, z0, W, Dp, Hb, roof_H, emit=False, **kw)
    return B, ov


def fortress(cv, C, cx, cy, hx, hy, T, Hw, col, top_col=None, inner_col=None, layer_lines=None, merlon=(0.16, 0.1, 0.13, 0.07),
             gate=None, corner=0.12, parapet_col=None, segs=3):
    """Four walls around (cx, cy). gate: (side, s_centre, width, height, kind) with side in 'front','left','right','back'."""
    sides = {
        'front': (cx, cy - hy, 0.0, hx),
        'back': (cx, cy + hy, math.pi, hx),
        'left': (cx - hx, cy, -math.pi / 2, hy),
        'right': (cx + hx, cy, math.pi / 2, hy),
    }
    for name, (ox, oy, rot, half) in sides.items():
        ext = half + T / 2
        gates = []
        if gate and gate[0] == name:
            gates = [(gate[1], gate[2], gate[3], gate[4])]
        # split long walls so they sort well against buildings inside
        edges = np.linspace(-ext, ext, segs + 1)
        for k in range(segs):
            a, b = edges[k], edges[k + 1]
            g = [gg for gg in gates if a <= gg[0] < b]
            if any(abs(gg[0] - a) < gg[1] or abs(gg[0] - b) < gg[1] for gg in gates):
                # keep a gate inside one piece: merge with neighbours by widening this piece
                pass
            fr = Frame(ox, oy, rot)
            B = wall_piece(cv, fr, a, b, T, Hw, col, top_col, inner_col, merlon, layer_lines, g, parapet_col)
            C.builder(B, key_local=((a + b) / 2, 0, Hw * 0.5))


# ------------------------------------------------------------------ square pagoda (楼阁式塔) with eave rings
def pagoda3d(cv, cx, cy, z0, n=7, w0=0.5, w1=0.26, h0=0.32, h1=0.2, roof='#3f7a6e', wall='#e6dccb', column='#b5432f',
             ridge=None, overhang=0.13, lift=0.08, spire='#c9a55a', base_h=0.12, base='#c8b89a', lit=None, emit=True):
    fr = Frame(cx, cy, 0.0, z0)
    B = Builder(cv, fr)
    if base_h:
        B.box(-w0 / 2 - 0.08, w0 / 2 + 0.08, -w0 / 2 - 0.08, w0 / 2 + 0.08, 0, base_h, base, bias=9.0)
    z = base_h
    ovs = []
    for i in range(n):
        f = i / max(1, n - 1)
        w = w0 + (w1 - w0) * f
        hh = h0 + (h1 - h0) * f
        bx = w / 2
        det = facade(w, hh, 3 if w > 0.3 else 1, column, lit, colw=0.035)
        B.box(-bx, bx, -bx, bx, z, z + hh, wall, top=False, bias=8.0 - i * 1.0,
              details={'front': det, 'back': det, 'left': det, 'right': det})
        ex = bx + overhang * (1 - 0.3 * f)
        wn = w0 + (w1 - w0) * min(1.0, (i + 1) / max(1, n - 1))
        inset = ex - wn / 2
        last = (i == n - 1)
        R = Roof(z + hh, ex, ex, 0.12 + 0.05 * (1 - f) if not last else 0.28, kind='pyramid', lift=lift)
        Bi = Builder(cv, fr)
        if not last:
            ov = R.build(Bi, roof, nu=8, nt=4, ridge_col=ridge, t_top=min(0.95, inset / ex), ornament=False)
        else:
            ov = R.build(Bi, roof, nu=8, nt=5, ridge_col=ridge, ornament=False, finial=(0.32, spire))
        for f_ in Bi.faces:
            P, col, opt = f_
            opt = dict(opt)
            opt['bias'] = opt.get('bias', 0.0) + 7.5 - i * 1.0
            B.faces.append((P, col, opt))
        ovs.append((i, ov))
        z = float(R.z(min(0.95, inset / ex))) - 0.01 if not last else z
    svg = B.emit()
    for i, ov in ovs:
        svg += ov
    if emit:
        it = cv.item(float(cv.cam.depth(fr.w(np.array([0, -w0 / 2, 0.5])))), svg)
        cv.cast([np.asarray(f[0], float) for f in B.faces])
        return it
    return svg, B.faces
