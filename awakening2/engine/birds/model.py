"""The white-eye model: a pose dict -> 3D drawing primitives in the bird's root frame.

Root frame (cm): origin at the feet contact point, x forward (beak side), y up, z = the bird's
left side (toward the camera in a right-facing profile).  The body is a dense chain of
spheres along a curved spine (smooth, fluffy silhouette in any view); face features, wings,
tail and legs are curves/polygons attached to it.  Nothing here touches pixels.
"""
import numpy as np

CM_PER_UNIT = 6.0          # perched height (feet -> crown) in cm; `scale` = pixels per this

# body profile in the body frame (x along the body axis, y dorsal): (x, y, radius)
BODY_CTRL = np.array([
    (-2.15, 0.06, 0.40),
    (-1.84, 0.03, 0.74),
    (-1.40, 0.00, 1.05),
    (-0.78, -0.02, 1.32),
    (-0.08, -0.03, 1.45),
    (0.58, -0.02, 1.44),
    (1.10, 0.06, 1.29),
    (1.48, 0.24, 1.06),
])
SHOULDER = np.array([0.55, 0.80])         # body frame (x, y), wings attach at z = +-0.8
HEAD_R = 1.22
EYE_DIR = np.array([0.30, 0.17, 0.94])
EYE_A, RING_A = 0.25, 0.43                # angular radii on the head sphere (rad)

DEFAULT_POSE = dict(
    bx=0.0, by=2.70, tilt=38.0, fluff=1.0, neck=0.5, head_dx=0.0, head_dy=0.0,
    head_yaw=0.0, head_pitch=0.0, head_roll=0.0, beak=0.0, blink=0.0,
    tail=-14.0, tail_spread=0.0, tail_len=1.0, tail_side=0.0,
    # folded wings (decals on the body): droop rotates about the shoulder, lift pushes out
    fold=1.0, wdroop=0.0, wlift=0.0, wspread=0.0,
    # flight wings (used when fold == 0): near (n_) and far (f_) wing parameters
    n_el=10.0, n_sw=8.0, n_tw=4.0, n_ext=1.0, n_hel=0.0, n_hsw=0.0, n_fan=0.8,
    f_el=10.0, f_sw=8.0, f_tw=4.0, f_ext=1.0, f_hel=0.0, f_hsw=0.0, f_fan=0.8,
    # legs
    legs='perch', crouch=0.0, foot_x=0.12, foot_spread=0.0, toe_open=0.0, leg_reach=0.0,
    # whole-bird orientation about the body centre (flight / turnaround / flock views)
    yaw=0.0, pitch=0.0, roll=0.0, view_el=0.0,
)


# ----------------------------------------------------------------------------- maths
def rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):  # (1,0,0) -> (c,0,s): positive yaw turns the beak toward the camera
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def rz(a):  # (1,0,0) -> (c,s,0): nose up
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_axis(axis, ang):
    axis = np.asarray(axis, float)
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    x, y, z = axis
    c, s = np.cos(ang), np.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def catmull(P, n=8, closed=False):
    P = np.asarray(P, float)
    if closed:
        Q = np.vstack([P[-1:], P, P[:2]])
    else:
        Q = np.vstack([2 * P[:1] - P[1:2], P, 2 * P[-1:] - P[-2:-1]])
    out = []
    m = len(P) if closed else len(P) - 1
    t = np.linspace(0, 1, n, endpoint=False)[:, None]
    for i in range(m):
        p0, p1, p2, p3 = Q[i], Q[i + 1], Q[i + 2], Q[i + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    if not closed:
        out.append(P[-1:])
    return np.vstack(out)


def lerp(a, b, t):
    return a + (b - a) * t


D = np.deg2rad


# ----------------------------------------------------------------------------- body profile
_prof = catmull(BODY_CTRL, 12)


def body_profile(x):
    """spine y and radius at body-frame x (for lifting decals onto the body side)."""
    xs = _prof[:, 0]
    return np.interp(x, xs, _prof[:, 1]), np.interp(x, xs, _prof[:, 2], left=0.0, right=0.0)


def side_z(xb, yb, floor=0.42):
    ys, r = body_profile(xb)
    z = np.sqrt(np.maximum(r * r - (yb - ys) ** 2, 0.0))
    return np.maximum(z, floor)


# ----------------------------------------------------------------------------- folded wing design
# Hand-designed side view of the folded wing in the body frame (x back = negative).
FW_OUTLINE = np.array([
    (0.55, 0.98), (0.05, 1.24), (-0.65, 1.22), (-1.30, 1.00), (-1.95, 0.66), (-2.65, 0.30),
    (-3.12, 0.08), (-3.38, -0.04),                                   # primary tip
    (-3.06, -0.11), (-3.12, -0.14), (-2.82, -0.19), (-2.88, -0.22),  # stepped primary tips
    (-2.52, -0.28), (-2.02, -0.42), (-1.45, -0.58), (-0.80, -0.69),  # lower edge (secondaries)
    (-0.20, -0.65), (0.30, -0.45), (0.62, -0.10), (0.74, 0.35), (0.70, 0.74),
])
FW_COVERTS = np.array([
    (0.55, 0.98), (0.05, 1.24), (-0.65, 1.22), (-0.88, 1.16), (-1.06, 0.80), (-0.90, 0.32),
    (-0.44, -0.05), (0.12, -0.27), (0.48, -0.26), (0.62, -0.10), (0.74, 0.35), (0.70, 0.74),
])
FW_TERTIAL = np.array([(-0.88, 1.16), (-1.50, 0.93), (-1.95, 0.66), (-2.06, 0.42), (-1.66, 0.33),
                       (-1.22, 0.50), (-1.06, 0.80)])
# feather lines (open polylines) on the folded wing, body frame
FW_LINES = [
    np.array([(-1.08, 0.86), (-0.92, 0.32), (-0.44, -0.05), (0.12, -0.27), (0.50, -0.25)]),  # coverts edge
    np.array([(-1.95, 0.06), (-2.50, -0.08), (-3.06, -0.06)]),                                # primary edges
    np.array([(-1.78, -0.16), (-2.30, -0.27), (-2.80, -0.20)]),
    np.array([(-1.12, -0.40), (-1.68, -0.43)]),                                               # secondary edges
    np.array([(-0.50, -0.50), (-1.05, -0.55)]),
    np.array([(-1.22, 0.52), (-1.66, 0.36), (-2.04, 0.46)]),                                  # tertial
]


def folded_wing_2d(P):
    """Folded-wing outline/zones in the body frame after droop/spread (2D arrays)."""
    droop = D(P['wdroop'])
    sp = P['wspread']
    piv = SHOULDER
    R = np.array([[np.cos(-droop), -np.sin(-droop)], [np.sin(-droop), np.cos(-droop)]])

    def tf(pts):
        q = np.asarray(pts, float).copy()
        # spread: tips fan downward a little (primaries loosen)
        w = np.clip((-q[:, 0] - 1.6) / 2.3, 0, 1)
        q[:, 1] -= sp * 0.55 * w * w
        q[:, 0] -= sp * 0.15 * w
        return (q - piv) @ R.T + piv
    return dict(outline=tf(FW_OUTLINE), coverts=tf(FW_COVERTS), tertial=tf(FW_TERTIAL),
                lines=[tf(l) for l in FW_LINES])


# ----------------------------------------------------------------------------- flight wing
P_LEN = np.array([3.6, 4.0, 4.15, 4.1, 3.9, 3.65, 3.4, 3.2, 3.0])       # P9 .. P1
P_ROOT = np.array([1.0, 0.92, 0.82, 0.70, 0.57, 0.44, 0.30, 0.16, 0.03])
P_FAN = np.array([2, 10, 19, 29, 40, 51, 62, 73, 84], float)
S_LEN = np.array([2.55, 2.55, 2.5, 2.45, 2.42, 2.38, 2.3, 2.2])


def flight_wing(P, pre, side, Rb, bc):
    """Skeletal spread wing -> dict of 3D polylines in the root frame.  side=+1 near (z>0)."""
    el, sw, tw = D(P[pre + 'el']), D(P[pre + 'sw']), D(P[pre + 'tw'])
    ext, hel, hsw, fan = P[pre + 'ext'], D(P[pre + 'hel']), D(P[pre + 'hsw']), P[pre + 'fan']
    R = ry(sw) @ rx(-el) @ rz(tw)
    a = R @ np.array([0, 0, 1.0])
    c = R @ np.array([-1.0, 0, 0])
    S3 = np.array([SHOULDER[0], SHOULDER[1], 0.80])
    L_arm = lerp(1.45, 3.0, ext)
    W = np.array([L_arm, -0.2 * ext])
    th_h = D(lerp(72.0, -8.0, ext)) + hsw
    h = np.array([np.cos(th_h), np.sin(th_h)])
    L_hand = lerp(1.2, 1.5, ext)
    HT = W + L_hand * h
    fanf = 0.18 + 0.82 * fan
    tips, roots = [], []
    for k in range(9):
        root = W + P_ROOT[k] * L_hand * h
        ang = th_h + D(P_FAN[k] * fanf * lerp(0.55, 1.0, ext))
        d = np.array([np.cos(ang), np.sin(ang)])
        roots.append(root)
        tips.append(root + P_LEN[k] * lerp(0.92, 1.0, ext) * d)
    stips, sroots = [], []
    for j in range(8):
        root = W + (np.array([0.0, 0.0]) - W) * ((j + 0.6) / 8.8)
        ang = D(lerp(118.0, 92.0, ext)) + D(-2.0 * j)
        d = np.array([np.cos(ang), np.sin(ang)])
        sroots.append(root)
        stips.append(root + S_LEN[j] * d)
    B = np.array([-0.2, 1.95])
    LE1 = np.array([0.45 * L_arm, -0.32])
    fd_out = lerp(0.04, 0.26, fan)
    outline = [np.zeros(2), LE1, W, HT + 0.12 * np.array([-h[1], h[0]]) * -1, tips[0]]
    is_hand = [False, False, False, True, True]
    for k in range(1, 9):
        fd = fd_out * (1.0 if k <= 3 else 0.55 if k == 4 else 0.0)
        mr = 0.5 * (roots[k - 1] + roots[k]); mt = 0.5 * (tips[k - 1] + tips[k])
        if fd > 0.01:
            outline.append(mr + (mt - mr) * (1 - fd)); is_hand.append(True)
        outline.append(tips[k]); is_hand.append(True)
    for j in range(8):
        if j > 0 and j % 3 == 0:
            mr = 0.5 * (sroots[j - 1] + sroots[j]); mt = 0.5 * (stips[j - 1] + stips[j])
            outline.append(mr + (mt - mr) * 0.975); is_hand.append(False)
        outline.append(stips[j]); is_hand.append(False)
    outline.append(B); is_hand.append(False)
    outline = np.array(outline); is_hand = np.array(is_hand)
    cov = [np.zeros(2), LE1, W, HT, ]
    cov_hand = [False, False, False, True]
    for k in range(9):
        cov.append(roots[k] + (tips[k] - roots[k]) * (0.30 if k < 5 else 0.36)); cov_hand.append(True)
    for j in range(8):
        cov.append(sroots[j] + (stips[j] - sroots[j]) * 0.40); cov_hand.append(False)
    cov.append(B * 0.55); cov_hand.append(False)
    cov = np.array(cov); cov_hand = np.array(cov_hand)
    lines, lines_hand = [], []
    for k in range(1, 6):
        mr = 0.5 * (roots[k - 1] + roots[k]); mt = 0.5 * (tips[k - 1] + tips[k])
        fdk = fd_out * (1.0 if k <= 3 else 0.55 if k == 4 else 0.0)
        p0 = mr + (mt - mr) * (1 - fdk * 1.05 - 0.03); p1 = mr + (mt - mr) * 0.50
        lines.append(np.array([p0, p1])); lines_hand.append(True)
    for j in range(1, 7, 2):
        mr = 0.5 * (sroots[j - 1] + sroots[j]); mt = 0.5 * (stips[j - 1] + stips[j])
        lines.append(np.array([mr + (mt - mr) * 0.95, mr + (mt - mr) * 0.70])); lines_hand.append(False)
    hand_R = rot_axis(c, hel)
    W3 = S3 + W[0] * a + W[1] * c

    def to3(p2, hand):
        p2 = np.atleast_2d(p2)
        out = S3[None] + p2[:, :1] * a[None] + p2[:, 1:2] * c[None]
        if np.any(hand):
            rel = out[hand] - W3[None]
            out[hand] = W3[None] + rel @ hand_R.T
        out[:, 2] *= side
        return (out @ Rb.T) + bc[None]

    n_dorsal = np.cross(c, a)
    n_dorsal[2] *= side
    if side < 0:
        n_dorsal = n_dorsal
    return dict(outline=to3(outline, is_hand), coverts=to3(cov, cov_hand),
                lines=[to3(l, np.array([lh, lh])) for l, lh in zip(lines, lines_hand)],
                normal=Rb @ n_dorsal, side=side)


# ----------------------------------------------------------------------------- rig
class Rig:
    pass


def build_rig(pose):
    P = dict(DEFAULT_POSE)
    P.update(pose or {})
    rig = Rig()
    rig.P = P
    f = P['fluff']
    bc = np.array([P['bx'], P['by'], 0.0])
    Rb = rz(D(P['tilt']))
    rig.bc, rig.Rb = bc, Rb

    # --- body spheres
    prof = catmull(BODY_CTRL * [1, 1, 1], 10)
    # resample ~0.07 cm along x
    xs = np.arange(BODY_CTRL[0, 0], BODY_CTRL[-1, 0] + 1e-6, 0.07)
    ys = np.interp(xs, prof[:, 0], prof[:, 1])
    rs = np.interp(xs, prof[:, 0], prof[:, 2]) * f
    pts_b = np.stack([xs, ys, np.zeros_like(xs)], 1)
    body = pts_b @ Rb.T + bc
    tb = np.gradient(pts_b, axis=0)
    tb /= np.linalg.norm(tb, axis=1, keepdims=True)
    ub = np.stack([-tb[:, 1], tb[:, 0], np.zeros_like(xs)], 1)
    tan_b = tb @ Rb.T
    up_b = ub @ Rb.T
    s_b = (xs - xs[0]) / (xs[-1] - xs[0])

    # --- head position
    nb_ = body[-1]
    nv = np.array([0.20 + 0.16 * P['neck'], 0.70 + 0.50 * P['neck'], 0.0]) * (0.9 + 0.1 * f)
    hc = nb_ + nv + np.array([P['head_dx'], P['head_dy'], 0.0])
    Rh = ry(D(P['head_yaw'])) @ rz(D(P['head_pitch'])) @ rx(D(P['head_roll']))
    rig.hc, rig.Rh, rig.rh = hc, Rh, HEAD_R * (0.97 + 0.03 * f)

    # --- neck spheres
    nn = 9
    t = np.linspace(0, 1, nn + 2)[1:-1]
    hdir = (hc - nb_) / (np.linalg.norm(hc - nb_) + 1e-9)
    neck_end = hc - 0.25 * hdir
    neck = nb_[None] + (neck_end - nb_)[None] * t[:, None]
    r_nb = rs[-1]
    dip = 0.05 + 0.10 * P['neck']
    r_neck = lerp(r_nb, 0.98 * f, t) - dip * np.sin(np.pi * t)
    tan_n = np.repeat(hdir[None], nn, 0)
    up_n = np.repeat(np.array([-hdir[1], hdir[0], 0.0])[None], nn, 0)

    # --- head spheres (head-local offsets)
    hl = np.array([(0.0, 0.0, 0.0), (0.50, -0.11, 0.0), (-0.32, -0.26, 0.0), (0.22, 0.10, 0.0)])
    hr = np.array([rig.rh, 0.86, 1.04, 1.10]) * np.array([1, 1, f, 1])
    head = hc[None] + hl @ Rh.T

    c = np.vstack([body, neck, head])
    r = np.concatenate([rs, r_neck, hr])
    region = np.concatenate([np.zeros(len(body), np.int32), np.ones(nn, np.int32), np.full(len(head), 2, np.int32)])
    s = np.concatenate([s_b, np.full(nn, 1.0), np.full(len(head), 1.0)])
    tan = np.vstack([tan_b, tan_n, np.repeat(tan_n[:1], len(head), 0)])
    up = np.vstack([up_b, up_n, np.repeat(up_n[:1], len(head), 0)])
    rig.sph_c, rig.sph_r, rig.sph_region, rig.sph_s = c, r, region, s
    rig.sph_tan, rig.sph_up = tan, up
    rig.spine_len = (xs[-1] - xs[0])

    # --- eyes (root frame)
    rig.eyes = []
    for sgn in (1, -1):
        d = EYE_DIR * [1, 1, sgn]
        d = d / np.linalg.norm(d)
        rig.eyes.append(dict(c=hc + Rh @ (d * rig.rh), n=Rh @ d, dloc=d))

    # --- beak (head-local -> root)
    base = np.array([1.16, -0.14, 0.0])
    tip = np.array([2.08, -0.27, 0.0])
    db = (tip - base) / np.linalg.norm(tip - base)
    ub_ = np.array([-db[1], db[0], 0.0])
    wb = np.array([0, 0, 1.0])
    phi_u = np.linspace(0, np.pi, 9)
    phi_l = np.linspace(np.pi, 2 * np.pi, 9)
    upper = [base + ub_ * 0.25 * np.sin(p) + wb * 0.215 * np.cos(p) for p in phi_u]
    upper += [base + (tip - base) * 0.5 + ub_ * 0.105, tip]
    lower = [base + ub_ * 0.19 * np.sin(p) + wb * 0.19 * np.cos(p) for p in phi_l]
    lower += [base + (tip - base) * 0.5 - ub_ * 0.07, base + (tip - base) * 0.93 - ub_ * 0.015]
    upper, lower = np.array(upper), np.array(lower)
    gape = base - db * 0.12
    op = P['beak']
    Rl = rot_axis(wb, -D(21.0) * op)
    Ru = rot_axis(wb, D(6.0) * op)
    lower = (lower - gape) @ Rl.T + gape
    upper = (upper - gape) @ Ru.T + gape
    mouth = None
    if op > 0.05:
        mouth = np.array([gape + ub_ * 0.0 + db * 0.05, upper[-1] - db * 0.30 - ub_ * 0.03,
                          lower[-1] - db * 0.28 + ub_ * 0.03])
    tohead = lambda q: hc[None] + np.atleast_2d(q) @ Rh.T
    rig.beak = dict(upper=tohead(upper), lower=tohead(lower), mouth=None if mouth is None else tohead(mouth),
                    tip=tohead(tip)[0], base=tohead(base)[0], gape=tohead(gape)[0],
                    lores=tohead(np.array([base + ub_ * 0.16 + wb * 0.2]))[0])

    # --- tail (body frame -> root)
    ta = D(P['tail'])
    dirb = np.array([-np.cos(ta), np.sin(ta)])
    upb = np.array([dirb[1], -dirb[0]])
    if upb[1] < 0:
        upb = -upb
    root = np.array([-1.88, 0.02])
    L = 3.05 * P['tail_len']
    prof_pts = [(0.0, 0.34), (1.3, 0.24), (L - 0.32, 0.21), (L - 0.02, 0.17), (L + 0.04, 0.05),
                (L - 0.09, -0.01), (L + 0.03, -0.09), (L - 0.03, -0.19), (L - 0.38, -0.23),
                (1.3, -0.27), (0.0, -0.44)]
    wt = lerp(0.50, 1.95, P['tail_spread'])
    side_off = P['tail_side']
    n_sec = 9
    ps = np.linspace(0.0, L, n_sec)
    tt = ps / L
    half_w = lerp(0.36, wt, tt ** 0.8)                       # fan half-width (z)
    half_h = lerp(0.36, 0.16, np.sqrt(tt))                    # stack thickness (y)
    cen, wv, hv = [], [], []
    for p, hw, hh in zip(ps, half_w, half_h):
        xy = root + dirb * p
        cen.append([xy[0], xy[1] - 0.04 * (1 - p / L), side_off * p / L])
        wv.append([0.0, 0.0, hw])
        hv.append([upb[0] * hh, upb[1] * hh, 0.0])
    cen = np.array(cen) @ Rb.T + bc
    wv = np.array(wv) @ Rb.T
    hv = np.array(hv) @ Rb.T
    tip_c = cen[-1]
    rig.tail = dict(cen=cen, wv=wv, hv=hv,
                    up=Rb @ np.array([upb[0], upb[1], 0.0]),
                    lines=[np.array([cen[2] - hv[2] * 0.05, cen[-2] - hv[-2] * 0.05, tip_c - hv[-1] * 0.05]),
                           np.array([tip_c + hv[-1] * 0.1, tip_c - (cen[-1] - cen[-2]) * 0.35])],
                    root=(np.array([root[0], root[1], 0]) @ Rb.T + bc))

    # --- wings
    rig.folded = P['fold'] > 0.5
    rig.fw = folded_wing_2d(P) if rig.folded else None
    rig.wings = []
    if not rig.folded:
        rig.wings.append(flight_wing(P, 'f_', -1, Rb, bc))
        rig.wings.append(flight_wing(P, 'n_', 1, Rb, bc))

    # --- legs
    rig.legs = build_legs(P, bc, Rb)
    return rig


def build_legs(P, bc, Rb):
    legs = []
    mode = P['legs']
    if mode in ('none', 'tuck'):
        return legs
    Lt = 1.62
    for side in (-1, 1):
        zf = 0.40 * side
        attach = (np.array([0.20, -1.02, 0.42 * side]) @ Rb.T) + bc
        if mode == 'perch':
            fx = P['foot_x'] + (-0.24 if side < 0 else 0.0) + P['foot_spread'] * 0.3 * side
            F = np.array([fx, 0.0, zf])
            th = D(10.0 + 52.0 * P['crouch'])
            H = F + Lt * np.array([-np.sin(th), np.cos(th), 0.0])
            toe_dir_y = 0.0
            open_ = P['toe_open']
        else:
            # flight modes: reach (landing), tuck, hang
            reach = P['leg_reach']
            if mode == 'tuck':
                H = attach + Rb @ np.array([-0.55, -0.15, 0.0])
                F = H + Rb @ np.array([-0.9, 0.25, 0.0])
            else:
                down = Rb @ np.array([0.0, -1.0, 0.0])
                fwd = Rb @ np.array([1.0, 0.0, 0.0])
                H = attach + down * 0.55 + fwd * (0.15 + 0.35 * reach) - fwd * 0.4
                d = np.array([0.0, -1.0, 0.0]) * (1 - reach) + np.array([0.62, -0.78, 0.0]) * reach
                if mode == 'hang':
                    d = np.array([-0.35, -0.94, 0.0])
                d = d / np.linalg.norm(d)
                F = H + Lt * d
            F = F.copy(); F[2] = zf; H = H.copy(); H[2] = zf * 0.95
            toe_dir_y = -0.35 if mode != 'tuck' else 0.2
            open_ = P['toe_open']
        toes = []
        if mode != 'tuck':
            ang_f = D(lerp(-4.0, -38.0, open_))
            ang_b = D(lerp(184.0, 215.0, open_))
            for k, (ang, ln, dz) in enumerate([(ang_f, 0.84, 0.10), (ang_f + D(7), 0.74, -0.10), (ang_b, 0.62, 0.0)]):
                d = np.array([np.cos(ang), np.sin(ang) + toe_dir_y * (1 if k < 2 else -0.3), 0.0])
                d /= np.linalg.norm(d)
                p1 = F + d * ln * 0.55 + np.array([0, 0, dz * side])
                p2 = F + d * ln + np.array([0, -0.06 - 0.05 * (1 - open_), dz * side])
                claw = p2 + np.array([d[0] * 0.13, -0.10, 0.0])
                toes.append((np.array([F, p1, p2, claw]), np.array([0.085, 0.075, 0.060, 0.018])))
        legs.append(dict(side=side, tarsus=(np.array([H, F]), np.array([0.105, 0.090])),
                         thigh=(np.array([attach, H]), np.array([0.34, 0.20])), toes=toes))
    return legs
