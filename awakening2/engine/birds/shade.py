"""Per-pixel zone + cel-tone evaluation on the sphere-chain core (numba)."""
import numpy as np
import numba as nb

# zone ids (must match palette.ZONES)
Z_OLIVE, Z_YELLOW, Z_WHITE, Z_BUFF, Z_UNDERTAIL, Z_RING, Z_EYE, Z_LORES, Z_FOREHEAD = 1, 2, 3, 4, 5, 6, 7, 8, 9
Z_COVERTS, Z_FLIGHT = 10, 11
Z_SIL, Z_SIL_LIT = 21, 22

# olive/yellow head boundary: elevation (rad) as a function of |azimuth| (rad)
_BAZ = np.array([0.0, 0.5, 1.2, 1.9, 2.5, 3.1416])
_BEL = np.array([-0.30, -0.34, -0.40, -0.74, -1.15, -1.57])


@nb.njit(cache=True, fastmath=True)
def _interp(x, xs, ys):
    n = xs.shape[0]
    if x <= xs[0]:
        return ys[0]
    for i in range(1, n):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + (ys[i] - ys[i - 1]) * t
    return ys[n - 1]


@nb.njit(cache=True, fastmath=True)
def _bilin(tex, ch, u, v):
    Hd = tex.shape[0]; Wd = tex.shape[1]
    if u < 0 or v < 0 or u > Wd - 1.001 or v > Hd - 1.001:
        return 0.0
    x0 = int(u); y0 = int(v)
    fx = u - x0; fy = v - y0
    a = tex[y0, x0, ch] * (1 - fx) + tex[y0, x0 + 1, ch] * fx
    b = tex[y0 + 1, x0, ch] * (1 - fx) + tex[y0 + 1, x0 + 1, ch] * fx
    return a * (1 - fy) + b * fy


@nb.njit(cache=True, fastmath=True)
def head_zone(dx, dy, dz, eye_d, eye_a, ring_a, blink, baz, bel):
    sgn = 1.0
    if dz < 0:
        sgn = -1.0
    ex = eye_d[0]; ey = eye_d[1]; ez = eye_d[2] * sgn
    cosang = dx * ex + dy * ey + dz * ez
    if cosang > 1.0:
        cosang = 1.0
    ang = np.arccos(cosang)
    if ang < eye_a:
        if blink <= 0.0:
            return Z_EYE
        # upper lid comes down: keep the part below the lid line
        el_e = np.arcsin(ey)
        el = np.arcsin(max(-1.0, min(1.0, dy)))
        lid = el_e + eye_a * (1.0 - 2.0 * blink)
        if el < lid:
            return Z_EYE
        return Z_RING
    if ang < ring_a:
        return Z_RING
    az = np.arctan2(abs(dz), dx)
    el = np.arcsin(max(-1.0, min(1.0, dy)))
    # lores: dark stripe from the beak base to the front of the eye-ring
    u = (az - 0.30) / (0.86 - 0.30)
    if u > 0.0 and u < 1.0:
        el_line = -0.06 + u * 0.18
        if abs(el - el_line) < 0.050 + 0.012 * u:
            return Z_LORES
    elb = _interp(az, baz, bel)
    if el > elb:
        if az < 0.50 and el < 0.62:
            return Z_FOREHEAD
        return Z_OLIVE
    return Z_YELLOW


@nb.njit(cache=True, fastmath=True)
def shade_core(depth, idx, sx, sy, sz, sr, mirror, Rinv,
               c_loc, r_loc, region, s_arr, tan, up, spine_len,
               hc, RhT, bc, RbT, folded, tex, tex_x0, tex_y1, tex_inv,
               eye_d, eye_a, ring_a, blink, L, bias, rim_on, rim_w, hilite, sil_mode,
               ids, tag):
    H, W = depth.shape
    Lxy = np.sqrt(L[0] * L[0] + L[1] * L[1]) + 1e-9
    lx2 = L[0] / Lxy; ly2 = L[1] / Lxy
    backlit = L[2] < -0.12
    hx = L[0]; hy = L[1]; hz = L[2] + 1.0
    hn = np.sqrt(hx * hx + hy * hy + hz * hz)
    hx /= hn; hy /= hn; hz /= hn
    for y in range(H):
        for x in range(W):
            k = idx[y, x]
            if k < 0:
                continue
            rr = sr[k]
            nsx = (x - sx[k]) / rr
            nsy = -(y - sy[k]) / rr
            nsz = (depth[y, x] - sz[k]) / rr
            # camera-frame normal (undo mirror), then root frame
            ncx = nsx * mirror
            n0 = Rinv[0, 0] * ncx + Rinv[0, 1] * nsy + Rinv[0, 2] * nsz
            n1 = Rinv[1, 0] * ncx + Rinv[1, 1] * nsy + Rinv[1, 2] * nsz
            n2 = Rinv[2, 0] * ncx + Rinv[2, 1] * nsy + Rinv[2, 2] * nsz
            px = c_loc[k, 0] + r_loc[k] * n0
            py = c_loc[k, 1] + r_loc[k] * n1
            pz = c_loc[k, 2] + r_loc[k] * n2
            reg = region[k]
            zone = Z_OLIVE
            tg = 1
            if reg >= 1:
                vx = px - hc[0]; vy = py - hc[1]; vz = pz - hc[2]
                dx = RhT[0, 0] * vx + RhT[0, 1] * vy + RhT[0, 2] * vz
                dy = RhT[1, 0] * vx + RhT[1, 1] * vy + RhT[1, 2] * vz
                dz = RhT[2, 0] * vx + RhT[2, 1] * vy + RhT[2, 2] * vz
                dn = np.sqrt(dx * dx + dy * dy + dz * dz) + 1e-9
                zone = head_zone(dx / dn, dy / dn, dz / dn, eye_d, eye_a, ring_a, blink, _BAZ, _BEL)
            else:
                upc = n0 * up[k, 0] + n1 * up[k, 1] + n2 * up[k, 2]
                side = abs(n2)
                sh = s_arr[k] + (n0 * tan[k, 0] + n1 * tan[k, 1] + n2 * tan[k, 2]) * r_loc[k] / spine_len
                if upc > -0.10:
                    zone = Z_OLIVE
                else:
                    if sh > 0.86 - 0.13 * (-upc):
                        zone = Z_YELLOW
                    elif sh < 0.17 + 0.05 * (-upc):
                        zone = Z_UNDERTAIL
                    elif side > 0.45 and upc > -0.74:
                        zone = Z_BUFF
                    else:
                        zone = Z_WHITE
                if folded:
                    qx = px - bc[0]; qy = py - bc[1]; qz = pz - bc[2]
                    bxp = RbT[0, 0] * qx + RbT[0, 1] * qy + RbT[0, 2] * qz
                    byp = RbT[1, 0] * qx + RbT[1, 1] * qy + RbT[1, 2] * qz
                    bzp = RbT[2, 0] * qx + RbT[2, 1] * qy + RbT[2, 2] * qz
                    if abs(bzp) > 0.12:
                        u = (bxp - tex_x0) * tex_inv
                        v = (tex_y1 - byp) * tex_inv
                        ch0 = 0
                        if bzp < 0:
                            ch0 = 3
                        if _bilin(tex, ch0, u, v) > 0.5:
                            if _bilin(tex, ch0 + 1, u, v) > 0.5:
                                zone = Z_COVERTS
                            else:
                                zone = Z_FLIGHT
                            tg = 2
                            if bzp < 0:
                                tg = 3
            # ---- tone
            nl = nsx * L[0] + nsy * L[1] + nsz * L[2]
            tone = 0
            if backlit and rim_on:
                d2 = nsx * lx2 + nsy * ly2
                if d2 > 0.18 and nsz < rim_w and nl > bias:
                    tone = 2
                else:
                    tone = 1
            else:
                if nl < bias:
                    tone = 1
                elif hilite and reg == 2 and (zone == Z_OLIVE or zone == Z_FOREHEAD):
                    if nsx * hx + nsy * hy + nsz * hz > 0.955:
                        tone = 3
            if zone == Z_EYE:
                tone = 0
            if sil_mode:
                if tone == 1:
                    zone = Z_SIL; tone = 0
                elif tone == 2:
                    zone = Z_SIL; tone = 2
                else:
                    zone = Z_SIL_LIT; tone = 0
            ids[y, x] = zone * 4 + tone
            tag[y, x] = tg
