"""Shot definitions: timing, cameras, robot key poses, light and layout notes.

World: the robot kneels at the origin facing +Y (local frame X = its right,
Y = forward, Z = up). Giant trunks stand around it; the canopy gap is above
and slightly in front, the low sun comes from behind-right of the robot.
Cameras are keyed in seconds *within the shot*; robot poses are keyed in
seconds and drawn on 2s or 3s (see anim.py).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(ROOT, 'engine'))
sys.path.insert(0, os.path.join(ROOT, 'robot'))
import numpy as np
import r3d
import warden as WD
import poses as PZ

FPS = 24
W, H = 1920, 1040

_RIG = None


def rig(voxel=0.07, head_voxel=0.035):
    global _RIG
    if _RIG is None:
        _RIG = WD.build(voxel=voxel, head_voxel=head_voxel)
        _RIG.build_meshes(verbose=False)
    return _RIG


def posed(name_or_pose, **kw):
    p = getattr(PZ, name_or_pose) if isinstance(name_or_pose, str) else name_or_pose
    return PZ.grounded(rig(), p, **kw)


def anchor(pose, part, local=(0, 0, 0)):
    mats = rig().world_mats(pose)
    return r3d.xform_points(mats[part], np.array([local], np.float32))[0]


def anchors(pose):
    a = {}
    a['head'] = anchor(pose, 'head', (0, 1.0, 1.2))
    a['eyes'] = anchor(pose, 'head', (0, 2.1, 1.1))
    a['brow'] = anchor(pose, 'head', (0, 1.9, 1.9))
    a['pauldron_L'] = anchor(pose, 'pauldron_L', (-0.5, 0, 1.4))
    a['chest'] = anchor(pose, 'torso', (0, 3.6, 4.35))
    a['hand_R'] = anchor(pose, 'hand_R', (0, 0.3, -1.2))
    a['knee_L'] = anchor(pose, 'shin_L', (0, 0.9, 0.2))
    a['roof'] = anchor(pose, 'torso', (0, -2.3, 10.4))
    a['pelvis'] = anchor(pose, 'pelvis', (0, 0, 0))
    return a


# sun: direction TO the sun (world). Low, behind-right of the robot as seen
# from the main front-left cameras, warm.
SUN_BACK = (0.35, -0.80, 0.48)
SUN_FACE = (-0.30, 0.70, 0.62)      # the "first ray": from the front-left, through the gap
SUN_SIDE = (0.85, 0.15, 0.50)

K = posed('KNEEL_DORMANT')
A = anchors(K)
_HM = rig().world_mats(K)['head']
HFWD = _HM[:3, :3] @ np.array([0, 1, 0], np.float32)     # face forward (bowed head)
HRIGHT = _HM[:3, :3] @ np.array([1, 0, 0], np.float32)
HUP = _HM[:3, :3] @ np.array([0, 0, 1], np.float32)
_PM = rig().world_mats(K)['pauldron_L']


def level_roll(pos, target, lens):
    """Camera roll (deg) that makes the robot's eye line horizontal on screen."""
    c = r3d.Camera(pos, target, lens=lens, W=W, H=H)
    q = c.project(np.array([A['eyes'] - HRIGHT, A['eyes'] + HRIGHT], np.float32))
    ang = float(np.degrees(np.arctan2(q[1, 1] - q[0, 1], q[1, 0] - q[0, 0])))
    while ang > 90:
        ang -= 180
    while ang < -90:
        ang += 180
    return -ang


def face_cam(dist, side, lens, tz=-0.5, up=0.0):
    pos = A['eyes'] + HFWD * dist + HRIGHT * side + np.array([0, 0, up], np.float32)
    tgt = A['eyes'] + np.array([0, 0, tz], np.float32)
    return pos, tgt, lens, level_roll(pos, tgt, lens)


def s05_cam(horizon_y=420.0, lens=30):
    """Ground-level camera by the right hand, pitched so the horizon matches the S05 painting."""
    pos = A['hand_R'] + v(-1.5, 8.0, -0.5)
    look = (A['hand_R'] + v(-0.5, -2.0, 0.6)) - pos
    hdir = np.array([look[0], look[1], 0.0], np.float32); hdir /= np.linalg.norm(hdir)
    fpx = lens / 36.0 * W
    pitch = np.arctan((H / 2 - horizon_y) / fpx)          # +: horizon above centre -> look down
    tgt = pos + hdir * 10.0 - np.array([0, 0, 10.0 * np.tan(pitch)], np.float32)
    pos = pos.copy(); pos[2] = max(pos[2], 0.6)
    return pos, tgt, lens


def face_cam_pos(dist, side, up, target_off=(0, 0, 0)):
    """Camera in front of the bowed face: dist along the face forward, side along its right, up."""
    return A['eyes'] + HFWD * dist + HRIGHT * side + np.array([0, 0, up], np.float32)


def v(*x):
    return np.array(x, np.float32)


SHOTS = [
    dict(id='S00', t0=0.0, t1=4.5, step=2,
         desc='Establishing vista: sunrise over the misty forest; a gap in the canopy where mist rises',
         cam=[(0.0, v(-17, 31, 3.2), v(-3, 6, 44), 30)], pose=[], light=SUN_BACK, bg='S00',
         notes='Fade in from black; slow pan left to right over the painting; a few birds cross; a shaft of light into the gap.'),
    dict(id='S01', t0=0.0, t1=8.0, step=2,
         desc='Tilt-down reveal: crowns against the dawn sky through the canopy gap, down the trunks, to the kneeling robot in mist',
         cam=[(0.0, v(15, 31, 3.0), v(3, 6, 44), 26), (1.2, v(15, 31, 3.0), v(3, 6, 44), 26),
              (6.4, v(15, 31, 3.0), A['pelvis'] + v(0.5, 0, 4.4), 26), (8.0, v(15, 31, 3.0), A['pelvis'] + v(0.5, 0, 4.4), 26)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S01',
         notes='Fade in 0-1.5 s. Ends locked with the robot ~55% of frame height framed by two huge trunks. Bird crosses far at 6.8 s.'),
    dict(id='S02', t0=8.0, t1=13.5, step=2,
         desc='Shoulder: the mossy pauldron with flowers and a sapling; the small bird lands',
         cam=[(0.0, A['pauldron_L'] + v(-5.2, 6.8, 3.4), A['pauldron_L'] + v(2.2, 0.0, 0.2), 35)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S02',
         notes='Locked. Head edge in frame right. Bird lands at 2.1 s, hops 2.9 s, settles, looks around.'),
    dict(id='S03', t0=13.5, t1=20.0, step=2,
         desc='Face close-up, eyes closed: the first ray of sun slides across the weathered face',
         cam=[(0.0, *face_cam(12.8, -1.9, 48, tz=-0.15)), (6.5, *face_cam(11.3, -1.6, 48, tz=-0.1))],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_FACE, bg='S03',
         notes='Slow push on 1s. The ray (a warm light shape) slides from the brow down over the eyes, 1.0-4.5 s; motes sparkle in the beam.'),
    dict(id='S04', t0=20.0, t1=25.0, step=2,
         desc='Chest furnace grille: a faint light flickers deep inside, then a heartbeat glow spills between the slats',
         cam=[(0.0, A['chest'] + v(-6.5, 12.5, -1.2), A['chest'] + v(-0.6, 0, 0.6), 42),
              (5.0, A['chest'] + v(-6.0, 11.6, -1.1), A['chest'] + v(-0.6, 0, 0.6), 42)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S04',
         notes='Flicker 1.0, 1.5 s; steady 2.4 s; heartbeat pulses 3.4, 4.4 s. Moss and flowers around the door catch the glow.'),
    dict(id='S05', t0=25.0, t1=27.5, step=2,
         desc='Ground close-up by the knee: pebbles and dew jump, soil cracks (tremor)',
         cam=[(0.0, *s05_cam())],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S05', shake=(0.2, 2.5, 4.0), impacts=[(0.3, 5.0), (1.3, 4.0)],
         notes='Camera shake on 1s from 0.2 s. Robot knee and fingers in the background, out of focus.'),
    dict(id='S06', t0=27.5, t1=30.5, step=2,
         desc='Treetops against the dawn sky: birds burst from the canopy',
         cam=[(0.0, v(-14, 30, 2.0), v(-6, 8, 48), 24)],
         pose=[], light=SUN_BACK, bg='S06', shake=(0.0, 1.0, 2.0),
         notes='No robot (or only the roof edge at the bottom). Flock bursts at 0.1 s, leaves shaken loose.'),
    dict(id='S07', t0=30.5, t1=34.0, step=2,
         desc='Face: the lids crack open, the eyes flicker alive; the small bird startles and flies off',
         cam=[(0.0, *face_cam(10.0, -1.2, 52, tz=-0.15))],
         pose=[(0.0, 'KNEEL_DORMANT'), (0.7, 'KNEEL_DORMANT'), (1.2, 'KNEEL_STIR'), (2.0, 'KNEEL_STIR'),
               (2.4, 'KNEEL_WAKE'), (2.58, 'KNEEL_WAKE'), (2.67, 'KNEEL_WAKE_BLINK'), (2.79, 'KNEEL_WAKE_BLINK'),
               (2.92, 'KNEEL_WAKE'), (3.25, 'KNEEL_WAKE_LOOK'), (3.5, 'KNEEL_WAKE_LOOK')], light=SUN_FACE, bg='S03',
         notes='Lids open 0.7-1.3 s (on 2s with a hold), eyes flicker 1.3-2.0 s; bird flees 2.1 s.'),
    dict(id='S08', t0=34.0, t1=38.5, step=3,
         desc='RISE A, wide front between trunks: the hand presses into the earth, the whole body heaves up; soil, roots and vines pour off',
         cam=[(0.0, v(23, 28, 2.2), v(0.5, 0, 7.4), 27), (4.5, v(23, 28, 2.2), v(0.5, 0, 7.4), 31)],
         pose=[(0.0, 'KNEEL_WAKE_LOOK'), (0.4, 'KNEEL_WAKE'), (0.9, 'KNEEL_SINK'), (1.6, 'PUSH_PLANT'), (2.5, 'PUSH_UP'),
               (3.1, 'PUSH_UP'), (4.5, 'RISE_CROUCH')],
         light=SUN_BACK, bg='S08', shake=(0.5, 4.5, 1.2), impacts=[(1.6, 6.0), (2.5, 4.0), (4.4, 5.0)],
         notes='On 3s. Anticipation: settles down 0.3-0.6 s, then pushes. Hold at 2.2-3.0 s. Debris and soil curtains from the forearm, chest and roof.'),
    dict(id='S09', t0=38.5, t1=43.0, step=3,
         desc='RISE B, low angle from the side near the ground: it rises to standing; the tree on its back sways; vines swing; soil curtains fall toward camera',
         cam=[(0.0, v(-21, 23, 1.2), v(0, 0, 10.6), 22)],
         pose=[(0.0, 'RISE_CROUCH'), (0.4, 'RISE_CROUCH'), (1.5, 'STAND_RISE'), (2.6, 'STAND_HUNCH'), (4.5, 'STAND_HUNCH')],
         light=SUN_BACK, bg='S09', shake=(0.3, 3.2, 1.0), impacts=[(0.6, 4.0), (2.6, 7.0)],
         notes='Trees measure the scale. Birds circle high. Hold at the top 2.8-4.5 s with a settle.'),
    dict(id='S10', t0=43.0, t1=46.5, step=2,
         desc='RISE C, low-angle front: it lifts its head toward the gap in the canopy; sunlight on the face; eyes resolute',
         cam=[(0.0, v(-5, 17, 2.0), v(0, 2, 15), 30), (3.5, v(-5, 17, 2.0), v(0, 2, 18), 30)],
         pose=[(0.0, 'STAND_HUNCH'), (0.5, 'STAND_HUNCH'), (1.3, 'STAND_TORSO_UP'), (2.2, 'STAND_LOOKUP'), (3.5, 'STAND_LOOKUP')],
         light=SUN_FACE, bg='S10', notes='Slow tilt up on 1s following the head. Hold at the end.'),
    dict(id='S11', t0=46.5, t1=48.5, step=2,
         desc='POV up: the canopy gap, golden sky, sun flare, drifting leaves',
         cam=[(0.0, v(0, 4, 20), v(0.5, 9, 70), 28)], pose=[], light=SUN_BACK, bg='S11', notes='Locked.'),
    dict(id='S12', t0=48.5, t1=52.0, step=2,
         desc='Back 3/4 medium: the roof halves swing open, engine bells glow, a hard crouch, engines sputter and ignite',
         cam=[(0.0, v(-20, -24, 9.0), v(0, 0, 10.5), 35)],
         pose=[(0.0, 'STAND_LOOKUP'), (0.7, 'STAND_LOOKUP'), (1.4, 'LAUNCH_CROUCH'), (3.5, 'LAUNCH_CROUCH')],
         spacing='in',
         light=SUN_BACK, bg='S12', shake=(3.0, 3.5, 3.0), impacts=[(1.4, 3.0), (3.0, 8.0)],
         notes='Roof opens 0.5-1.3 s; crouch 1.4-1.9 s; sputter 2.4 s; ignition 3.0 s.'),
    dict(id='S13', t0=52.0, t1=55.0, step=2,
         desc='High-angle wide: a great ring of wind expands across the forest floor',
         cam=[(0.0, v(-22, 27, 36), v(0, 0, 3), 30)],
         pose=[(0.0, 'LAUNCH_CROUCH')], light=SUN_BACK, bg='S13', shake=(0.0, 3.0, 2.0), impacts=[(0.0, 6.0)],
         notes='Ring from 0.0 s to the frame edges by 2.6 s; ferns flatten; dust wall; leaves; mist pushed out.'),
    dict(id='S14', t0=55.0, t1=56.5, step=1,
         desc='LAUNCH: 2-3 smear frames, an impact frame, the robot leaves frame upward',
         cam=[(0.0, v(-9, 30, 2.6), v(0, 0, 8.5), 28)],
         pose=[(0.0, 'LAUNCH_CROUCH'), (0.25, 'LAUNCH_CROUCH'), (0.29, 'LAUNCH_UP', dict(lift=2.0)),
               (0.45, 'LAUNCH_UP', dict(lift=6.0)), (0.75, 'LAUNCH_UP', dict(lift=14.0)), (1.1, 'LAUNCH_UP', dict(lift=34.0)),
               (1.5, 'LAUNCH_UP', dict(lift=120.0))],
         spacing='linear',
         light=SUN_BACK, bg='S09', shake=(0.3, 1.5, 4.0), impacts=[(0.3, 14.0)],
         notes='0.0-0.2 s anticipation hold, 0.2 s smear x2, 0.3 s impact frame x2, then the robot exits frame top.'),
    dict(id='S15', t0=56.5, t1=59.5, step=2,
         desc='From below: it tears through the canopy gap; branches and leaves explode outward; light flare',
         cam=[(0.0, v(1, 6, 1.0), v(0.2, 2, 90), 24)],
         pose=[(0.0, 'LAUNCH_UP', dict(lift=2.0)), (0.3, 'LAUNCH_UP', dict(lift=14.0)), (0.6, 'LAUNCH_UP', dict(lift=40.0)),
               (0.9, 'LAUNCH_UP', dict(lift=80.0)), (1.4, 'LAUNCH_UP', dict(lift=170.0)), (3.0, 'LAUNCH_UP', dict(lift=520.0))],
         spacing='linear', light=SUN_BACK, bg='S11',
         notes='Robot silhouette punches through the gap at 0.4 s, gone by 1.0 s; leaves burst and fall.'),
    dict(id='S16A', t0=59.5, t1=62.5, step=3,
         desc='Tracking beside the robot as it climbs: it fills the frame, moss and soil stream off, engines roar',
         cam=[(0.0, v(-28.0, 34.0, 2.0), v(0.0, 0.0, 9.0), 24)],
         pose=None,
         light=SUN_BACK, bg='S16A', notes='The camera flies with it; the sky and clouds stream past (down-left).'),
    dict(id='S16B', t0=62.5, t1=67.5, step=3,
         desc='Wide golden sky: the curving trail of light and mist; the robot becomes a spark crossing the sun',
         cam=[(0.0, v(-60, 230, 60), v(10, 0, 150), 40)],
         pose=None, light=SUN_BACK, bg='S16', notes='Locked. The trail curves from lower left to the sun at upper right.'),
    dict(id='S17', t0=67.5, t1=75.0, step=2,
         desc='Ending: the empty clearing, sunbeams, leaves spiral down; the small bird lands on the moss where the robot knelt; fade out',
         cam=[(0.0, v(15, 31, 3.0), A['pelvis'] + v(0.5, 0, 4.4), 26),
              (7.5, v(13.6, 28.1, 3.1), A['pelvis'] + v(0.5, 0, 4.0), 26)], pose=[], light=SUN_BACK, bg='S17',
         notes='Locked (the S01 end framing, robot gone). Fade out from 72.5 s.'),
]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _roll(k):
    return k[4] if len(k) > 4 else 0.0


def cam_at(shot, t, with_roll=False):
    """Camera at shot-local time t (seconds), interpolated on 1s with ease in/out."""
    keys = shot['cam']
    if len(keys) == 1 or t <= keys[0][0]:
        k = keys[0]
        out = (k[1], k[2], k[3], _roll(k))
    else:
        out = None
        for a, b in zip(keys[:-1], keys[1:]):
            if t <= b[0]:
                u = ease((t - a[0]) / max(b[0] - a[0], 1e-6))
                out = (a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u,
                       _roll(a) + (_roll(b) - _roll(a)) * u)
                break
        if out is None:
            k = keys[-1]
            out = (k[1], k[2], k[3], _roll(k))
    return out if with_roll else out[:3]


def camera(shot, t, W_=W, H_=H):
    pos, tgt, lens, roll = cam_at(shot, t, with_roll=True)
    return r3d.Camera(pos, tgt, lens=lens, W=W_, H=H_, roll=roll)


# ---------------------------------------------------------------- S16 flight path
def _bez(p, t):
    p = [np.asarray(x, np.float32) for x in p]
    u = 1 - t
    return u ** 3 * p[0] + 3 * u * u * t * p[1] + 3 * u * t * t * p[2] + t ** 3 * p[3]


S16_SCREEN = [(250, 770), (1150, 640), (360, 230), (1610, 205)]      # S-curve ending at the sun (px)
S16_DEPTH = (110.0, 900.0)


def s16_root(t, dur=5.0):
    """World root matrix of the robot along the S16 arc at shot time t (seconds), incl. before t=0."""
    sh = next(x for x in SHOTS if x['id'] == 'S16B')
    cam = camera(sh, 0.0)
    def world_at(tt):
        u = np.clip(tt / dur, -0.6, 1.0)
        uu = 0.12 + 0.88 * (1 - (1 - max(u, 0)) ** 1.6) if u >= 0 else 0.12 + u * 0.2
        sxy = _bez(S16_SCREEN, float(np.clip(uu, 0, 1))) if uu >= 0 else _bez(S16_SCREEN, 0.0) + np.array([-120, 400]) * (-uu)
        d = S16_DEPTH[0] + (S16_DEPTH[1] - S16_DEPTH[0]) * max(uu, 0)
        x = (sxy[0] - cam.cx) / cam.fpx; y = -(sxy[1] - cam.cy) / cam.fpx
        ray = cam.f + x * cam.r + y * cam.u
        ray /= np.linalg.norm(ray)
        return cam.pos + ray * d
    P = world_at(t); P2 = world_at(t + 0.15)
    vel = P2 - P; vel /= np.linalg.norm(vel) + 1e-6
    # body axis leans into the climb (70% along the velocity, 30% world up)
    up = 0.7 * vel + 0.3 * np.array([0, 0, 1.0], np.float32); up /= np.linalg.norm(up)
    # face turned three-quarters toward the camera, so the eyes and chest read in the climb
    toward = -np.array([cam.f[0], cam.f[1], 0.0], np.float32); toward /= np.linalg.norm(toward)
    side = np.cross(np.array([0, 0, 1.0], np.float32), toward)
    look = 0.75 * toward + 0.65 * side * np.sign(np.dot(side, vel) + 1e-6)
    fwd = look - up * np.dot(look, up); fwd /= np.linalg.norm(fwd) + 1e-6
    right = np.cross(fwd, up)
    M = np.eye(4, dtype=np.float32)
    M[:3, 0] = right; M[:3, 1] = fwd; M[:3, 2] = up
    pel = rig().parts['pelvis'].joint
    M[:3, 3] = P - M[:3, :3] @ pel
    return M


def s16a_root(t):
    """S16A: the robot held in a tracking camera; it banks and pitches a little (keys on 3s)."""
    roll = -45.0 + 6.0 * np.sin(t * 1.3)
    pitch = -10.0 + 4.0 * np.sin(t * 0.9 + 0.5)
    yaw = 30.0
    R = r3d.rot_matrix(pitch, roll, yaw)
    M = np.eye(4, dtype=np.float32)
    M[:3, :3] = R
    pel = rig().parts['pelvis'].joint
    M[:3, 3] = np.array([0.0, 0.0, 9.0], np.float32) - R @ pel + np.array([0, 0, 0.6 * np.sin(t * 2.1)], np.float32)
    return M


def _s16_keys():
    keys = []
    for k in range(0, 5 * 8 + 1):
        t = k / 8.0
        keys.append((t, 'FLY', dict(M=s16_root(t))))
    return keys


for _s in SHOTS:
    if _s['id'] == 'S16B':
        _s['pose'] = _s16_keys()
    if _s['id'] == 'S16A':
        def _fly(t):
            u = ease(t / 2.2)
            return dict(PZ.FLY, head=(18 + 16 * u, 0, -14 * u),
                        upperarm_R=(-30 - 10 * u, 26, 0), upperarm_L=(-30 - 10 * u, -26, 0),
                        forearm_R=(6 + 8 * u, 0, 0), forearm_L=(6 + 8 * u, 0, 0),
                        lid_R=(-10 + 6 * u, 10, 0), lid_L=(-10 + 6 * u, -10, 0))
        _s['pose'] = [(k / 8.0, _fly(k / 8.0), dict(M=s16a_root(k / 8.0))) for k in range(0, 3 * 8 + 1)]


# ---------------------------------------------------------------- timing from the cue sheet
def _sync_times():
    import json
    try:
        cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    except Exception:
        return
    tm = {c['id']: (c['in'], c['out']) for c in cues['shots']}
    for _s in SHOTS:
        if _s['id'] in tm:
            _s['t0'], _s['t1'] = tm[_s['id']]


_sync_times()
