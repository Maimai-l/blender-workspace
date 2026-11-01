#!/usr/bin/env python3
"""Pinhole camera fit for the Qiting views, from fixed points and from the silhouette tips of horizontal circles.

    calq.py <view.json>            -> writes <view>_sol.json (loc, target, lens, roll) and prints residuals

view.json: {"W": .., "H": .., "f_px": null | number (fixed focal length in px), "init": [x, y, z, tx, ty, tz, lens],
            "obs": [ {"k": "pt", "X": [x, y, z], "uv": [u, v], "name": ".."},
                     {"k": "tipL" | "tipR", "z": .., "R": .., "uv": [u, v], "name": ".."},     # silhouette tip
                     {"k": "top" | "bot", "z": .., "R": .., "uv": [u, v]},                     # highest/lowest point
                     {"k": "u", "X": [x, y, z], "u": ..}  ]}                                  # only the column
Uses the camera convention of calib.py (yaw about z from +y, pitch up, roll); lens is in mm on a 36 mm sensor width.
"""
import json, math, os, sys
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calib import rot

CIRC = np.linspace(0, 2 * math.pi, 721)[:-1]


def proj(p, P, W, H):
    cx, cy, cz, yaw, pitch, roll, lens = p[:7]
    su, sv = (p[7], p[8]) if len(p) > 7 else (0.0, 0.0)      # principal point offset in px (cropped photos)
    fwd, right, up = rot(yaw, pitch, roll)
    d = np.atleast_2d(P) - np.array([cx, cy, cz])
    z = d @ fwd
    x = d @ right
    y = d @ up
    f = lens / 36.0 * W
    return np.stack([W / 2 + su + f * x / z, H / 2 + sv - f * y / z], 1), z


def circle_pts(z, R):
    return np.stack([R * np.cos(CIRC), R * np.sin(CIRC), np.full_like(CIRC, z)], 1)


def residuals(p, J):
    W, H = J['W'], J['H']
    r = []
    for o in J['obs']:
        w = o.get('w', 1.0)
        k = o['k']
        if k == 'pt':
            uv, _ = proj(p, o['X'], W, H)
            r += [w * (uv[0, 0] - o['uv'][0]), w * (uv[0, 1] - o['uv'][1])]
        elif k == 'u':
            uv, _ = proj(p, o['X'], W, H)
            r += [w * (uv[0, 0] - o['u'])]
        else:
            uv, zc = proj(p, circle_pts(o['z'], o['R']), W, H)
            ok = zc > 0.1
            uv = uv[ok]
            if len(uv) == 0:
                r += [1e4] if k in ('top', 'bot') else [1e4, 1e4]
                continue
            if k == 'tipL':
                i = np.argmin(uv[:, 0])
            elif k == 'tipR':
                i = np.argmax(uv[:, 0])
            elif k == 'top':
                i = np.argmin(uv[:, 1])
            else:
                i = np.argmax(uv[:, 1])
            if k in ('top', 'bot'):
                r += [w * (uv[i, 1] - o['uv'][1])]
            else:
                r += [w * (uv[i, 0] - o['uv'][0]), w * (uv[i, 1] - o['uv'][1])]
    return np.array(r)


def solve(J):
    W = J['W']
    cx, cy, cz, tx, ty, tz, lens = J['init']
    d = np.array([tx - cx, ty - cy, tz - cz])
    yaw = math.atan2(d[0], d[1])
    pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    fixed = J.get('f_px')
    if fixed:
        lens = fixed / W * 36.0

    shift = J.get('shift', False)
    nf = 0 if fixed else 1

    fz = J.get('fix_z')

    def res(q):
        p = list(q[:6]) + [lens if fixed else q[6]]
        if fz is not None:
            p[2] = fz
        if shift:
            p += [q[6 + nf], q[7 + nf]]
        return residuals(p, J)
    q0 = [cx, cy, cz, yaw, pitch, 0.0] + ([] if fixed else [lens]) + ([0.0, 0.0] if shift else [])
    sol = least_squares(res, q0, loss='soft_l1', f_scale=6.0, max_nfev=20000)
    p = list(sol.x[:6]) + [lens if fixed else sol.x[6]]
    if fz is not None:
        p[2] = fz
    if shift:
        p += [sol.x[6 + nf], sol.x[7 + nf]]
    return p, res(sol.x)


if __name__ == '__main__':
    path = sys.argv[1]
    J = json.load(open(path))
    p, r = solve(J)
    fwd, right, up = rot(p[3], p[4], p[5])
    loc = np.array(p[:3])
    tgt = loc + fwd * 20
    out = {'loc': [round(v, 4) for v in loc], 'target': [round(v, 4) for v in tgt], 'lens': round(p[6], 4),
           'roll': round(p[5], 6), 'W': J['W'], 'H': J['H'], 'f_px': round(p[6] / 36.0 * J['W'], 1)}
    if len(p) > 7:
        # Blender lens shift is in units of the larger sensor side: shift_x = -su / W, shift_y = sv / W
        out['shift'] = [round(-p[7] / J['W'], 5), round(p[8] / J['W'], 5)]
        out['pp_px'] = [round(p[7], 1), round(p[8], 1)]
    json.dump(out, open(path.replace('.json', '_sol.json'), 'w'), indent=1)
    print(json.dumps(out))
    # per-observation residual norms
    i = 0
    rows = []
    for o in J['obs']:
        n = 1 if o['k'] in ('u', 'top', 'bot') else 2
        e = r[i:i + n] / o.get('w', 1.0)
        i += n
        rows.append((o.get('name', o['k']), float(np.hypot(*e)) if n == 2 else float(abs(e[0]))))
    print('residuals px:', ', '.join('%s %.1f' % (a, b) for a, b in rows))
    print('rms %.2f px  (image %dx%d, f %.0f px, lens %.2f mm, cam height %.2f, dist %.1f m)' % (
        float(np.sqrt((r ** 2).mean())), J['W'], J['H'], out['f_px'], p[6], loc[2], math.hypot(loc[0], loc[1])))
