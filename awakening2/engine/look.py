"""look.py - turn render passes into a drawn anime cel (RGBA).

Steps for one drawing:
  light     N.L against the shot's key light, times the cast-shadow map
  shadows   threshold -> morphological clean-up -> drop small islands -> smooth
            boundary => designed hard-edged shadow shapes (no 3D noise)
  fills     flat colours per material / decal region, light or shadow tone,
            a deeper tone in occluded crevices, a warm rim band on the sun side
  ink       lines traced from id / depth / normal discontinuities (ink.py)
  out       premultiplied RGBA at render scale, downsampled to frame size

All colours are sRGB floats 0..1.
"""
import math
import numpy as np
import cv2
import ink


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def disk(r):
    r = max(1, int(round(r)))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def remove_small(m, min_area):
    """Remove connected components smaller than min_area (both polarities)."""
    if min_area <= 0:
        return m
    m = m.astype(np.uint8)
    for val in (1, 0):
        src = (m == val).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(src, connectivity=4)
        small = np.where(stats[:, cv2.CC_STAT_AREA] < min_area)[0]
        small = small[small > 0]
        if len(small):
            kill = np.isin(lab, small)
            m[kill] = 1 - val
    return m.astype(bool)


def clean_mask(m, r_close, r_open, min_area, smooth_sigma, valid=None):
    """Designed shapes from a raw binary mask."""
    u = m.astype(np.uint8)
    if r_close > 0:
        u = cv2.morphologyEx(u, cv2.MORPH_CLOSE, disk(r_close))
    if r_open > 0:
        u = cv2.morphologyEx(u, cv2.MORPH_OPEN, disk(r_open))
    b = remove_small(u.astype(bool), min_area)
    if smooth_sigma > 0:
        f = cv2.GaussianBlur(b.astype(np.float32), (0, 0), smooth_sigma)
        b = f > 0.5
    if valid is not None:
        b &= valid
    return b


def screen_ao(depth, mask, radius_px, strength_m):
    """Cheap crevice term: how far a pixel sits behind the local max-filtered front.

    Returns 0..1 (1 = deep crevice)."""
    d = np.where(mask, depth, np.nan).astype(np.float32)
    big = np.nan_to_num(d, nan=1e6)
    k = disk(radius_px)
    front = -cv2.dilate(-big, k)            # local nearest depth (min filter)
    occ = np.clip((big - front) / strength_m, 0, 1)
    occ[~mask] = 0
    return occ


def downsample(rgba, s):
    if s == 1:
        return rgba
    H, W = rgba.shape[:2]
    return cv2.resize(rgba, (int(round(W / s)), int(round(H / s))), interpolation=cv2.INTER_AREA)


def over(dst, src):
    """Premultiplied alpha over: src on top of dst (both (H,W,4) premultiplied)."""
    a = src[..., 3:4]
    return src + dst * (1 - a)


def premul(rgb, a):
    return np.concatenate([rgb * a[..., None], a[..., None]], -1).astype(np.float32)
