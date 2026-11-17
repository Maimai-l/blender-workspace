#!/usr/bin/env python3
"""Pinhole camera calibration from world<->image correspondences.
usage: calib.py <json file with {"W":..,"H":..,"pts":[[x,y,z,u,v],...], "init":[cx,cy,cz,tx,ty,tz,lens]}>
Prints blender camera (location, target, lens at 36mm sensor width) and residuals."""
import json, sys, math
import numpy as np
from scipy.optimize import least_squares

def rot(yaw, pitch, roll):
    # camera looks along +d where d from yaw (around z, 0 = +y) and pitch (up positive)
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    fwd = np.array([sy * cp, cy * cp, sp])
    right = np.array([cy, -sy, 0.0])
    up = np.cross(right, fwd)
    cr, sr = math.cos(roll), math.sin(roll)
    r2 = right * cr + up * sr
    u2 = -right * sr + up * cr
    return fwd, r2, u2

def project(p, P, W, H):
    cx, cy, cz, yaw, pitch, roll, f = p
    fwd, right, up = rot(yaw, pitch, roll)
    d = np.asarray(P) - np.array([cx, cy, cz])
    z = d @ fwd
    x = d @ right; y = d @ up
    fpx = f / 36.0 * W
    return W / 2 + fpx * x / z, H / 2 - fpx * y / z

def solve(W, H, pts, init, fix_lens=None):
    pts = np.array(pts, dtype=float)
    def res(p):
        if fix_lens:
            p = list(p) + [fix_lens]
        r = []
        for X, Y, Z, u, v in pts:
            pu, pv = project(p, (X, Y, Z), W, H)
            r += [pu - u, pv - v]
        return r
    cx, cy, cz, tx, ty, tz, lens = init
    d = np.array([tx - cx, ty - cy, tz - cz])
    yaw = math.atan2(d[0], d[1]); pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    p0 = [cx, cy, cz, yaw, pitch, 0.0] + ([] if fix_lens else [lens])
    sol = least_squares(res, p0, loss='soft_l1', f_scale=8.0)
    p = list(sol.x) + ([fix_lens] if fix_lens else [])
    r = np.array(res(sol.x)).reshape(-1, 2)
    fwd, right, up = rot(p[3], p[4], p[5])
    loc = np.array(p[:3]); tgt = loc + fwd * 20
    return p, loc, tgt, r

if __name__ == '__main__':
    J = json.load(open(sys.argv[1]))
    p, loc, tgt, r = solve(J['W'], J['H'], J['pts'], J['init'], J.get('fix_lens'))
    print('loc', [round(v, 2) for v in loc], 'target', [round(v, 2) for v in tgt], 'lens', round(p[6], 2),
          'roll_deg', round(math.degrees(p[5]), 2))
    print('residuals px', np.round(np.hypot(r[:, 0], r[:, 1]), 1).tolist(), 'rms', round(float(np.sqrt((r ** 2).mean())), 2))
    json.dump({'loc': loc.tolist(), 'target': tgt.tolist(), 'lens': p[6], 'roll': p[5]}, open(sys.argv[1].replace('.json', '_sol.json'), 'w'))

def solve_aspect(W, H, pts, init):
    """Same as solve() but with a free vertical pixel scale (detects stretched photos)."""
    pts = np.array(pts, dtype=float)
    def res(p):
        cam = p[:7]; k = p[7]
        r = []
        for X, Y, Z, u, v in pts:
            pu, pv = project(cam, (X, Y, Z), W, H)
            r += [pu - u, (pv - H / 2) * k + H / 2 - v]
        return r
    cx, cy, cz, tx, ty, tz, lens = init
    d = np.array([tx - cx, ty - cy, tz - cz])
    yaw = math.atan2(d[0], d[1]); pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    sol = least_squares(res, [cx, cy, cz, yaw, pitch, 0.0, lens, 1.0], loss='soft_l1', f_scale=8.0)
    r = np.array(res(sol.x)).reshape(-1, 2)
    return sol.x, r

def solve_shift(W, H, pts, init, bounds_z=None):
    """Camera with a free vertical principal-point shift (photo cropped off-centre). Returns params, residuals.
    params: cx, cy, cz, yaw, pitch, roll, lens, shift_px"""
    pts = np.array(pts, dtype=float)
    def res(p):
        cam = p[:7]; sh = p[7]
        r = []
        for X, Y, Z, u, v in pts:
            pu, pv = project(cam, (X, Y, Z), W, H)
            r += [pu - u, pv + sh - v]
        return r
    cx, cy, cz, tx, ty, tz, lens = init
    d = np.array([tx - cx, ty - cy, tz - cz])
    yaw = math.atan2(d[0], d[1]); pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    lo = [-np.inf] * 8; hi = [np.inf] * 8
    if bounds_z:
        lo[2], hi[2] = bounds_z
    lo[4], hi[4] = -0.02, 0.02          # keep the camera level (verticals stay vertical in the photos)
    lo[5], hi[5] = -0.05, 0.05
    lo[6], hi[6] = 10.0, 80.0
    p0 = [cx, cy, cz, yaw, 0.0, 0.0, lens, 0.0]
    p0[2] = min(max(p0[2], lo[2] + 1e-3), hi[2] - 1e-3) if bounds_z else p0[2]
    sol = least_squares(res, p0, bounds=(lo, hi), loss='soft_l1', f_scale=8.0)
    r = np.array(res(sol.x)).reshape(-1, 2)
    return sol.x, r

def solve_bounded(W, H, pts, init, box, lens_rng=(14.0, 70.0), vs_rng=(0.7, 1.7), level=0.35, free_vs=True):
    """Camera inside an xyz box, pitch within +-level rad, optional vertical stretch. Returns params, residuals."""
    pts = np.array(pts, dtype=float)
    def res(p):
        cam = p[:7]; k = p[7] if free_vs else 1.0
        r = []
        for X, Y, Z, u, v in pts:
            pu, pv = project(cam, (X, Y, Z), W, H)
            r += [pu - u, (pv - H / 2) * k + H / 2 - v]
        return r
    cx, cy, cz, tx, ty, tz, lens = init
    d = np.array([tx - cx, ty - cy, tz - cz])
    yaw = math.atan2(d[0], d[1]); pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    (x0, x1), (y0, y1), (z0, z1) = box
    lo = [x0, y0, z0, -10, -level, -0.06, lens_rng[0]] + ([vs_rng[0]] if free_vs else [])
    hi = [x1, y1, z1, 10, level, 0.06, lens_rng[1]] + ([vs_rng[1]] if free_vs else [])
    p0 = [min(max(cx, x0 + 1e-3), x1 - 1e-3), min(max(cy, y0 + 1e-3), y1 - 1e-3), min(max(cz, z0 + 1e-3), z1 - 1e-3),
          yaw, max(-level + 1e-3, min(level - 1e-3, pitch)), 0.0, lens] + ([1.0] if free_vs else [])
    sol = least_squares(res, p0, bounds=(lo, hi), loss='soft_l1', f_scale=6.0)
    r = np.array(res(sol.x)).reshape(-1, 2)
    return sol.x, r
