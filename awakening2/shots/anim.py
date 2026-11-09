"""Robot animation: key poses -> per-frame poses drawn on 2s/3s with holds.

Spacing is hand-style: drawings bunch up near the keys (slow-in/slow-out),
heavy parts overshoot a little and settle, and the drawing only changes
every `step` frames. Cameras are evaluated on 1s elsewhere.
"""
import numpy as np
import r3d
import shotdefs as SD


def _pose_of(k):
    name = k[1]
    kw = k[2] if len(k) > 2 else {}
    if 'M' in kw:                     # explicit world matrix (flight)
        p = dict(getattr(SD.PZ, name) if isinstance(name, str) else name)
        p['_root'] = np.asarray(kw['M'], np.float32)
        return p
    lift = kw.get('lift', 0.0)
    p = SD.posed(name, x=kw.get('x', 0.0), y=kw.get('y', 0.0)) if isinstance(name, str) else SD.PZ.grounded(SD.rig(), name)
    if lift:
        p = dict(p); R = p['_root'].copy(); R[2, 3] += lift; p['_root'] = R
    return p


def spacing(u, kind='inout'):
    u = min(max(u, 0.0), 1.0)
    if kind == 'linear':
        return u
    if kind == 'in':
        return u * u
    if kind == 'out':
        return 1 - (1 - u) * (1 - u)
    if kind == 'heavy':        # slow start, heavy push, settle with a small overshoot
        s = u * u * (3 - 2 * u)
        return s + 0.06 * np.sin(np.pi * u) * u * u * 4 * (1 - u)
    return u * u * (3 - 2 * u)


def lerp_pose(pa, pb, s):
    out = {}
    keys = set(pa) | set(pb)
    for k in keys:
        if k == '_root':
            continue
        a = np.asarray(pa.get(k, (0, 0, 0)), np.float32)
        b = np.asarray(pb.get(k, (0, 0, 0)), np.float32)
        out[k] = tuple((a + (b - a) * s).tolist())
    Ra, Rb = pa['_root'], pb['_root']
    root = np.eye(4, dtype=np.float32)
    root[:3, 3] = Ra[:3, 3] + (Rb[:3, 3] - Ra[:3, 3]) * s
    R = Ra[:3, :3] + (Rb[:3, :3] - Ra[:3, :3]) * s
    u, _, vt = np.linalg.svd(R)        # re-orthonormalise the blended rotation
    root[:3, :3] = (u @ vt).astype(np.float32)
    out['_root'] = root
    return out


_cache = {}


def pose_at(shot, t, kind='heavy'):
    """Pose at shot-local time t, quantised to the shot's drawing step."""
    kind = shot.get('spacing', kind)
    keys = shot['pose']
    if not keys:
        return None
    step = shot.get('step', 2)
    f = int(round(t * SD.FPS))
    fq = (f // step) * step
    tq = fq / SD.FPS
    ck = (shot['id'], fq, kind)
    if ck in _cache:
        return _cache[ck]
    poses = []
    for k in keys:
        kk = (shot['id'], id(k))
        if kk not in _cache:
            _cache[kk] = _pose_of(k)
        poses.append(_cache[kk])
    if tq <= keys[0][0] or len(keys) == 1:
        p = poses[0]
    elif tq >= keys[-1][0]:
        p = poses[-1]
    else:
        for i in range(len(keys) - 1):
            if keys[i][0] <= tq <= keys[i + 1][0]:
                u = (tq - keys[i][0]) / max(keys[i + 1][0] - keys[i][0], 1e-6)
                p = lerp_pose(poses[i], poses[i + 1], spacing(u, kind))
                break
    _cache[ck] = p
    return p
