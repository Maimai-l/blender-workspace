#!/usr/bin/env python3
"""Refine a photo camera by aligning the model's known edges with the photo's edges (chamfer fit).

    edgefit.py <cal json> <image> [--box x0 y0 x1 y1] [--iters N] [--free-f]

The cal json is a calq.py input; its solution (<name>_sol.json) is the starting camera and is overwritten
with the refined one. Model edges (3D polylines from qt_dims): both eave tile edges, the coping, the terrace
rims (eight-lobed outlines), the upper drum window band and the stair parapets. They are projected with the
camera, compared with Canny edges of the photo through a distance transform (truncated at 6 px, so hidden
edges cannot pull the fit), and the camera (position, yaw, pitch, roll, focal length) is optimised.
Writes renders/edgefit_<name>.jpg showing the projected edges over the photo."""
import argparse, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'lib'))
import cv2
from scipy import optimize
from calib import rot
import xyp

import importlib.util
spec = importlib.util.spec_from_file_location('qt_dims', os.path.join(xyp.LIB, 'qt_dims.py'))
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)


def lobe_r(R, az):
    rq = R - 0.67
    rel = ((az - math.radians(D.COL_AZ0)) % (math.pi / 4)) / (math.pi / 8) - 1.0
    r = rq + 1.0 * (1.0 - abs(rel) ** 1.6)
    half = (0.30 / 2) / rq / (math.pi / 8)
    if abs(rel) > 1.0 - half:
        r = rq - 0.25
    return r


def model_curves():
    C = []
    t = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    def circ(R, z):
        return np.stack([R * np.cos(t), R * np.sin(t), np.full_like(t, z)], 1)
    C.append(('eave2', circ(D.EAVE2_R, D.roof2_z(D.EAVE2_R) - 0.02)))
    C.append(('eave1', circ(D.EAVE1_R, D.roof1_z(D.EAVE1_R) - 0.02)))
    C.append(('coping', circ(D.R_COPING, 0.0)))
    C.append(('coping_b', circ(D.R_COPING, -D.COPING_T)))
    C.append(('win_top', circ(D.R_DRUM2 + 0.07, D.Z_BEAM2[1])))
    C.append(('sill', circ(D.R_DRUM2 + 0.07, D.Z_SILL2[0])))
    for k in range(3):
        R = D.TIER_R[k]
        zt = D.Z_TIER_TOP - k * D.TIER_H
        P = np.array([[lobe_r(R, a) * math.cos(a), lobe_r(R, a) * math.sin(a), zt + 0.05] for a in t])
        C.append(('terr%d' % k, P))
        P2 = np.array([[lobe_r(R, a) * math.cos(a), lobe_r(R, a) * math.sin(a), zt - D.TIER_H] for a in t])
        C.append(('terr%d_b' % k, P2))
    # stair parapets (outer edges), the nosing line from the coping to the foot
    rise = -D.Z_STAIR_FOOT / D.STAIR_RISERS
    pts = [(D.STAIR_R0, 0.0)]
    r = D.STAIR_R0; z = 0.0
    for f, (n, tr) in enumerate(D.STAIR_FLIGHTS):
        r += (n - 1) * tr; z -= n * rise
        pts.append((r, z))
        if f < len(D.STAIR_LANDINGS):
            r += D.STAIR_LANDINGS[f]; pts.append((r, z))
    xo = D.STAIR_W_CLEAR / 2 + D.STAIR_PARAPET
    for sx in (-1, 1):
        P = []
        for (ra, za), (rb, zb) in zip(pts, pts[1:]):
            for u in np.linspace(0, 1, 30, endpoint=False):
                P.append([sx * xo, ra + (rb - ra) * u, za + (zb - za) * u + 0.10])
        C.append(('parapet%+d' % sx, np.array(P)))
    return C


K1 = [0.0]          # radial distortion (barrel < 0) of the photo, fitted with --k1
KY = [1.0]          # vertical pixel scale of the photo (1 = square pixels), fitted with --aspect


def project(p, P, W, H):
    cx, cy, cz, yaw, pitch, roll, f = p[:7]
    su, sv = (p[7], p[8]) if len(p) > 7 else (0.0, 0.0)
    fwd, right, up = rot(yaw, pitch, roll)
    d = P - np.array([cx, cy, cz])
    z = d @ fwd
    xn = (d @ right) / z
    yn = -(d @ up) / z
    k = 1.0 + K1[0] * (xn * xn + yn * yn)
    return np.stack([W / 2 + su + f * xn * k, H / 2 + sv + f * KY[0] * yn * k], 1), z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cal'); ap.add_argument('image')
    ap.add_argument('--box', type=int, nargs=4)
    ap.add_argument('--iters', type=int, default=3)
    ap.add_argument('--free-f', action='store_true')
    ap.add_argument('--trunc', type=float, default=6.0)
    ap.add_argument('--k1', action='store_true', help='fit radial distortion too')
    ap.add_argument('--aspect', action='store_true', help='fit a vertical pixel scale too (stretched photos)')
    a = ap.parse_args()
    J = json.load(open(a.cal))
    sol = json.load(open(a.cal.replace('.json', '_sol.json')))
    img = cv2.imread(a.image)
    H, W = img.shape[:2]
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    E = cv2.Canny(g, 40, 110)
    if a.box:
        m = np.zeros_like(E); x0, y0, x1, y1 = a.box; m[y0:y1, x0:x1] = 1; E = E * m
    DT = cv2.distanceTransform((255 - E).astype(np.uint8), cv2.DIST_L2, 5)
    curves = model_curves()
    allP = np.concatenate([c[1] for c in curves], 0)
    d = np.array(sol['target']) - np.array(sol['loc'])
    p0 = list(sol['loc']) + [math.atan2(d[0], d[1]), math.atan2(d[2], math.hypot(d[0], d[1])), sol['roll'], sol['f_px']]
    if 'pp_px' in sol:
        p0 += sol['pp_px']
    K1[0] = sol.get('k1', 0.0)
    KY[0] = sol.get('ky', 1.0)

    def cost(p):
        uv, z = project(p, allP, W, H)
        ok = (z > 0.5) & (uv[:, 0] > 1) & (uv[:, 0] < W - 2) & (uv[:, 1] > 1) & (uv[:, 1] < H - 2)
        if ok.sum() < 50:
            return 1e3
        u = uv[ok]
        dd = DT[u[:, 1].astype(int), u[:, 0].astype(int)]
        return float(np.mean(np.minimum(dd, a.trunc))) + 0.0 * (~ok).sum()
    p = np.array(p0, float)
    c0 = cost(p)
    for it in range(a.iters):
        idx = list(range(7 if a.free_f else 6)) + ([7, 8] if len(p) > 7 else [])
        scale = np.array([0.5, 0.5, 0.5, 0.004, 0.004, 0.004, 20.0, 5.0, 5.0])[idx]
        extra = (['k1'] if a.k1 else []) + (['ky'] if a.aspect else [])
        def sub(q):
            pp = p.copy(); pp[idx] = p[idx] + q[:len(idx)] * scale
            for j, nm in enumerate(extra):
                if nm == 'k1':
                    K1[0] = k1_0 + q[len(idx) + j] * 0.02
                else:
                    KY[0] = ky_0 + q[len(idx) + j] * 0.01
            return cost(pp)
        k1_0, ky_0 = K1[0], KY[0]
        n = len(idx) + len(extra)
        res = optimize.minimize(sub, np.zeros(n), method='Powell', options={'xtol': 1e-3, 'ftol': 1e-4, 'maxiter': 8000})
        p[idx] = p[idx] + res.x[:len(idx)] * scale
        sub(res.x)
        print('iter %d cost %.3f -> %.3f' % (it, c0, res.fun))
        c0 = res.fun
    fwd, right, up = rot(p[3], p[4], p[5])
    loc = p[:3]
    out = dict(sol)
    out.update({'loc': [round(v, 4) for v in loc], 'target': [round(v, 4) for v in loc + fwd * 20],
                'lens': round(p[6] / W * 36.0, 4), 'roll': round(p[5], 6), 'f_px': round(p[6], 1), 'edgefit_cost_px': round(c0, 3),
                'k1': round(K1[0], 5), 'ky': round(KY[0], 5)})
    if len(p) > 7:
        out['pp_px'] = [round(p[7], 1), round(p[8], 1)]
        out['shift'] = [round(-p[7] / W, 5), round(p[8] / W, 5)]
    json.dump(out, open(a.cal.replace('.json', '_sol.json'), 'w'), indent=1)
    print(json.dumps({k: out[k] for k in ('loc', 'lens', 'f_px', 'roll', 'edgefit_cost_px', 'k1', 'ky')}))
    vis = img.copy()
    vis[E > 0] = (0.5 * vis[E > 0] + np.array([0, 0, 128])).astype(np.uint8)
    for name, P in curves:
        uv, z = project(p, P, W, H)
        for (u0, v0), (u1, v1), z0 in zip(uv[:-1], uv[1:], z[:-1]):
            if z0 > 0.5 and abs(u1 - u0) < 50 and abs(v1 - v0) < 50:
                cv2.line(vis, (int(u0), int(v0)), (int(u1), int(v1)), (0, 255, 255), 1, cv2.LINE_AA)
    name = os.path.splitext(os.path.basename(a.cal))[0]
    out_img = os.path.join(xyp.S, 'renders', 'edgefit_%s.jpg' % name)
    if a.box:
        x0, y0, x1, y1 = a.box
        vis = vis[y0:y1, x0:x1]
    cv2.imwrite(out_img, vis)
    print('wrote', out_img)


if __name__ == '__main__':
    main()
