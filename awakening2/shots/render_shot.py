"""render_shot.py - render one shot to frames.

  python3 render_shot.py S01 [--start N] [--end N] [--step K] [--ss 2] [--out DIR] [--jobs J]

Per frame:
  * the robot drawing is keyed by its pose time (2s/3s) and its reference
    camera; a held pose is drawn once. Between drawings the cel follows the 1s
    camera as a 2D layer (translate + scale about the anchor), like a cel under
    a rostrum camera;
  * the painted layers move with the same 2D camera, scaled by their parallax;
  * per-shot effects (shotfx.py) add drawn effects, birds, light;
  * the photography stage grades, blooms, adds grain.
"""
import os, sys, time, json, argparse, math
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('engine', 'robot', 'shots'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import numpy as np
import cv2
import r3d, cel, comp, look
import shotdefs as SD
import anim

ROOT = os.path.join(HERE, '..')
FRAMES = os.environ.get('AW2_FRAMES', '/home/user/aw2_frames')

_ROBOT = None


def robot():
    global _ROBOT
    if _ROBOT is None:
        import build
        rig, style = build.make()
        SD._RIG = rig
        _ROBOT = (rig, style)
    return _ROBOT


class Shot:
    def __init__(self, sid, ss=2):
        self.shot = next(s for s in SD.SHOTS if s['id'] == sid)
        self.sid = sid
        self.ss = ss
        self.dur = self.shot['t1'] - self.shot['t0']
        self.nf = int(round(self.dur * SD.FPS))
        import shotfx
        self.fx = shotfx.make(self)
        self.cel_cache = {}

    # ---------------------------------------------------------------- camera
    def cam(self, t):
        return SD.camera(self.shot, t)

    def shake(self, f):
        sh = self.shot.get('shake')
        if not sh:
            return 0.0, 0.0
        a, b, amp = sh
        t = f / SD.FPS
        if t < a or t > b:
            return 0.0, 0.0
        env = min(1.0, (t - a) / 0.25) * min(1.0, (b - t) / 0.4)
        env *= self.fx.shake_gain(t) if hasattr(self.fx, 'shake_gain') else 1.0
        rng = np.random.default_rng(1000 + f)          # new offset every frame (on 1s)
        return float(rng.normal(0, amp * env)), float(rng.normal(0, amp * env * 0.7))

    # ---------------------------------------------------------------- robot
    def drawing_time(self, t):
        step = self.shot.get('step', 2)
        f = int(round(t * SD.FPS))
        return (f // step) * step / SD.FPS

    def robot_key(self, t):
        """Key of the robot drawing at time t: changes only when the pose changes."""
        tq = self.drawing_time(t)
        pose = anim.pose_at(self.shot, tq)
        if pose is None:
            return None, None, None
        sig = tuple(np.round(np.concatenate([np.ravel(np.asarray(v, np.float32)) for k, v in sorted(pose.items())]), 3))
        extra = self.fx.robot_state(tq) if hasattr(self.fx, 'robot_state') else ()
        return (hash(sig), extra), tq, pose

    def ref_cam_time(self, t):
        """The camera a drawing is made from: the camera at the drawing's first frame."""
        return self.drawing_time(t)

    def robot_cel(self, t):
        key, tq, pose = self.robot_key(t)
        if key is None:
            return None
        tc = tq if self.fx.redraw_on_camera else self.fx.cel_cam_time(tq)
        ck = (key, round(tc, 4))
        if ck in self.cel_cache:
            return self.cel_cache[ck]
        rig, style0 = robot()
        cam = self.cam(tc)
        st = dict(style0)
        st.update(self.fx.style(tq, cam))
        st['ss'] = self.ss
        mats = {}
        rgba, ps = cel.render(rig, pose, cam, st, return_passes=True, mats_out=mats)
        ent = dict(rgba=rgba, cam=cam, pose=pose, mats=mats, light=st['light'], ps_small=_small_passes(ps, self.ss))
        extra = key[1] if isinstance(key, tuple) else ()
        if 'dual' in extra:
            st2 = dict(st)
            st2['light'] = comp.light_from_screen(cam, self.fx.ray_az, self.fx.ray_el)
            ent['lit_rgba'] = cel.render(rig, pose, cam, st2)
        if self.fx.ground:
            sc, _ = rig.scene(pose)
            m = ps['mask']
            Pw = ps['wpos'][m]
            if len(Pw):
                ctr = np.median(Pw, 0)
                ext = float(np.percentile(np.abs(Pw - ctr), 99.5)) * 1.3 + 8.0
                sm = r3d.ShadowMap(sc, st['light'], ctr, ext, 2048)
                ent['gshadow'] = cv2.GaussianBlur(comp.ground_shadow(cam, sm).astype(np.float32), (0, 0), 1.0)
        if len(self.cel_cache) > 3:
            self.cel_cache.clear()
        self.cel_cache[ck] = ent
        return ent

    # ---------------------------------------------------------------- frame
    def frame(self, f):
        t = f / SD.FPS
        cam = self.cam(t)
        layers = self.fx.compose(f, t, cam)
        return layers


def _small_passes(ps, ss):
    """Frame-resolution versions of the passes the effects need."""
    out = {}
    m = ps['mask']
    H, W = m.shape
    h, w = H // ss, W // ss
    d = np.where(m, ps['depth'], np.inf)
    out['depth'] = d[::ss, ::ss][:h, :w]
    out['wpos'] = ps['wpos'][::ss, ::ss][:h, :w]
    out['mask'] = cv2.resize(m.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    out['mat'] = ps['mat'][::ss, ::ss][:h, :w]
    out['part'] = ps['part'][::ss, ::ss][:h, :w]
    out['lit'] = cv2.resize(ps['lit'].astype(np.float32), (w, h), interpolation=cv2.INTER_AREA)
    return out


def warp_cel(rgba, M):
    return cv2.warpAffine(rgba, M, (rgba.shape[1], rgba.shape[0]), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def run(sid, start=0, end=None, step=1, ss=2, out=None, verbose=True):
    S = Shot(sid, ss=ss)
    out = out or os.path.join(FRAMES, sid)
    os.makedirs(out, exist_ok=True)
    end = S.nf if end is None else min(end, S.nf)
    for f in range(start, end, step):
        t0 = time.time()
        rgb = S.frame(f)
        g = int(round(S.shot['t0'] * SD.FPS)) + f
        cv2.imwrite(os.path.join(out, f'{sid}_{f:04d}.png'), comp.to_u8(rgb)[..., ::-1])
        if verbose:
            print(f'{sid} f{f:03d} (global {g}) {time.time() - t0:.1f}s', flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('sid')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=None)
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--ss', type=int, default=2)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    run(a.sid, a.start, a.end, a.step, a.ss, a.out)
