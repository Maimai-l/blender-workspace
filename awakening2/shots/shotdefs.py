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


def face_cam_pos(dist, side, up, target_off=(0, 0, 0)):
    """Camera in front of the bowed face: dist along the face forward, side along its right, up."""
    return A['eyes'] + HFWD * dist + HRIGHT * side + np.array([0, 0, up], np.float32)


def v(*x):
    return np.array(x, np.float32)


SHOTS = [
    dict(id='S01', t0=0.0, t1=8.0, step=2,
         desc='Tilt-down reveal: crowns against the dawn sky through the canopy gap, down the trunks, to the kneeling robot in mist',
         cam=[(0.0, v(-17, 31, 3.2), v(-3, 6, 44), 30), (1.2, v(-17, 31, 3.2), v(-3, 6, 44), 30),
              (6.4, v(-17, 31, 3.2), A['pelvis'] + v(-1.0, 0, 3.6), 30), (8.0, v(-17, 31, 3.2), A['pelvis'] + v(-1.0, 0, 3.6), 30)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S01',
         notes='Fade in 0-1.5 s. Ends locked with the robot ~55% of frame height framed by two huge trunks. Bird crosses far at 6.8 s.'),
    dict(id='S02', t0=8.0, t1=13.5, step=2,
         desc='Shoulder: the mossy pauldron with flowers and a sapling; the small bird lands',
         cam=[(0.0, A['pauldron_L'] + v(-5.2, 6.8, 3.4), A['pauldron_L'] + v(2.2, 0.0, 0.2), 35)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S02',
         notes='Locked. Head edge in frame right. Bird lands at 2.1 s, hops 2.9 s, settles, looks around.'),
    dict(id='S03', t0=13.5, t1=20.0, step=2,
         desc='Face close-up, eyes closed: the first ray of sun slides across the weathered face',
         cam=[(0.0, face_cam_pos(10.5, -4.2, 0.6), A['eyes'] + v(0, 0, -0.35), 50),
              (6.5, face_cam_pos(9.2, -3.7, 0.55), A['eyes'] + v(0, 0, -0.3), 50)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_FACE, bg='S03',
         notes='Slow push on 1s. The ray (a warm light shape) slides from the brow down over the eyes, 1.0-4.5 s; motes sparkle in the beam.'),
    dict(id='S04', t0=20.0, t1=25.0, step=2,
         desc='Chest furnace grille: a faint light flickers deep inside, then a heartbeat glow spills between the slats',
         cam=[(0.0, A['chest'] + v(-3.0, 9.0, 0.6), A['chest'] + v(0, 0, -0.2), 55),
              (5.0, A['chest'] + v(-2.8, 8.4, 0.55), A['chest'] + v(0, 0, -0.2), 55)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S04',
         notes='Flicker 1.0, 1.5 s; steady 2.4 s; heartbeat pulses 3.4, 4.4 s. Moss and flowers around the door catch the glow.'),
    dict(id='S05', t0=25.0, t1=27.5, step=2,
         desc='Ground close-up by the knee: pebbles and dew jump, soil cracks (tremor)',
         cam=[(0.0, A['hand_R'] + v(-1.5, 8.0, -0.5), A['hand_R'] + v(-0.5, -2.0, 0.6), 30)],
         pose=[(0.0, 'KNEEL_DORMANT')], light=SUN_BACK, bg='S05', shake=(0.2, 2.5, 6.0),
         notes='Camera shake on 1s from 0.2 s. Robot knee and fingers in the background, out of focus.'),
    dict(id='S06', t0=27.5, t1=30.5, step=2,
         desc='Treetops against the dawn sky: birds burst from the canopy',
         cam=[(0.0, v(-14, 30, 2.0), v(-6, 8, 48), 24)],
         pose=[], light=SUN_BACK, bg='S06', shake=(0.0, 1.0, 2.0),
         notes='No robot (or only the roof edge at the bottom). Flock bursts at 0.1 s, leaves shaken loose.'),
    dict(id='S07', t0=30.5, t1=34.0, step=2,
         desc='Face: the lids crack open, the eyes flicker alive; the small bird startles and flies off',
         cam=[(0.0, face_cam_pos(8.2, -2.2, 0.4), A['eyes'] + v(0, 0, -0.2), 55)],
         pose=[(0.0, 'KNEEL_DORMANT'), (0.7, 'KNEEL_DORMANT'), (1.3, 'KNEEL_WAKE'), (3.5, 'KNEEL_WAKE')], light=SUN_FACE, bg='S03',
         notes='Lids open 0.7-1.3 s (on 2s with a hold), eyes flicker 1.3-2.0 s; bird flees 2.1 s.'),
    dict(id='S08', t0=34.0, t1=38.5, step=3,
         desc='RISE A, wide front between trunks: the hand presses into the earth, the whole body heaves up; soil, roots and vines pour off',
         cam=[(0.0, v(-6, 40, 2.6), v(0, 0, 8.6), 30)],
         pose=[(0.0, 'KNEEL_WAKE'), (0.6, 'KNEEL_WAKE'), (2.2, 'RISE_PUSH'), (3.0, 'RISE_PUSH'), (4.5, 'RISE_CROUCH')],
         light=SUN_BACK, bg='S08', shake=(0.5, 4.5, 4.0),
         notes='On 3s. Anticipation: settles down 0.3-0.6 s, then pushes. Hold at 2.2-3.0 s. Debris and soil curtains from the forearm, chest and roof.'),
    dict(id='S09', t0=38.5, t1=43.0, step=3,
         desc='RISE B, low angle from the side near the ground: it rises to standing; the tree on its back sways; vines swing; soil curtains fall toward camera',
         cam=[(0.0, v(-30, 10, 1.2), v(0, 0, 9.5), 24)],
         pose=[(0.0, 'RISE_CROUCH'), (0.5, 'RISE_CROUCH'), (2.8, 'STAND_HUNCH'), (4.5, 'STAND_HUNCH')],
         light=SUN_BACK, bg='S09',
         notes='Trees measure the scale. Birds circle high. Hold at the top 2.8-4.5 s with a settle.'),
    dict(id='S10', t0=43.0, t1=46.5, step=2,
         desc='RISE C, low-angle front: it lifts its head toward the gap in the canopy; sunlight on the face; eyes resolute',
         cam=[(0.0, v(-5, 17, 2.0), v(0, 2, 15), 30), (3.5, v(-5, 17, 2.0), v(0, 2, 18), 30)],
         pose=[(0.0, 'STAND_HUNCH'), (0.6, 'STAND_HUNCH'), (2.2, 'STAND_LOOKUP'), (3.5, 'STAND_LOOKUP')],
         light=SUN_FACE, bg='S10', notes='Slow tilt up on 1s following the head. Hold at the end.'),
    dict(id='S11', t0=46.5, t1=48.5, step=2,
         desc='POV up: the canopy gap, golden sky, sun flare, drifting leaves',
         cam=[(0.0, v(0, 4, 20), v(0.5, 9, 70), 28)], pose=[], light=SUN_BACK, bg='S11', notes='Locked.'),
    dict(id='S12', t0=48.5, t1=52.0, step=2,
         desc='Back 3/4 medium: the roof halves swing open, engine bells glow, a hard crouch, engines sputter and ignite',
         cam=[(0.0, v(-20, -24, 9.0), v(0, 0, 10.5), 35)],
         pose=[(0.0, 'STAND_LOOKUP'), (0.7, 'STAND_LOOKUP'), (1.4, 'LAUNCH_CROUCH'), (3.5, 'LAUNCH_CROUCH')],
         light=SUN_BACK, bg='S12', shake=(2.4, 3.5, 5.0),
         notes='Roof opens 0.5-1.3 s; crouch 1.4-1.9 s; sputter 2.4 s; ignition 3.0 s.'),
    dict(id='S13', t0=52.0, t1=55.0, step=2,
         desc='High-angle wide: a great ring of wind expands across the forest floor',
         cam=[(0.0, v(-22, 27, 36), v(0, 0, 3), 30)],
         pose=[(0.0, 'LAUNCH_CROUCH')], light=SUN_BACK, bg='S13', shake=(0.0, 3.0, 3.0),
         notes='Ring from 0.0 s to the frame edges by 2.6 s; ferns flatten; dust wall; leaves; mist pushed out.'),
    dict(id='S14', t0=55.0, t1=56.5, step=1,
         desc='LAUNCH: 2-3 smear frames, an impact frame, the robot leaves frame upward',
         cam=[(0.0, v(-8, 22, 3.0), v(0, 0, 12), 28)],
         pose=[(0.0, 'LAUNCH_CROUCH'), (0.2, 'LAUNCH_UP', dict(lift=2.0)), (0.5, 'LAUNCH_UP', dict(lift=30.0)), (1.5, 'LAUNCH_UP', dict(lift=90.0))],
         light=SUN_BACK, bg='S09', shake=(0.15, 1.5, 9.0),
         notes='0.0-0.2 s anticipation hold, 0.2 s smear x2, 0.3 s impact frame x2, then the robot exits frame top.'),
    dict(id='S15', t0=56.5, t1=59.5, step=2,
         desc='From below: it tears through the canopy gap; branches and leaves explode outward; light flare',
         cam=[(0.0, v(1, 6, 1.0), v(0.2, 2, 90), 24)],
         pose=[(0.0, 'LAUNCH_UP', dict(lift=8.0)), (0.5, 'LAUNCH_UP', dict(lift=40.0)), (1.2, 'LAUNCH_UP', dict(lift=110.0)), (3.0, 'LAUNCH_UP', dict(lift=400.0))],
         light=SUN_BACK, bg='S11',
         notes='Robot silhouette punches through the gap at 0.4 s, gone by 1.0 s; leaves burst and fall.'),
    dict(id='S16', t0=59.5, t1=67.5, step=3,
         desc='Golden sky, long lens: it climbs in a long curve leaving a wide trail of light and mist',
         cam=[(0.0, v(-95, 150, 78), v(-12, 12, 102), 50), (8.0, v(-95, 150, 78), v(50, -36, 200), 50)],
         pose=[(0.0, 'FLY', dict(lift=95.0, x=-14, y=14)), (4.0, 'FLY', dict(lift=165.0, x=18, y=-8)), (8.0, 'FLY', dict(lift=230.0, x=70, y=-50))],
         light=SUN_BACK, bg='S16', notes='Slow pan on 1s. Trail must read at thumbnail size.'),
    dict(id='S17', t0=67.5, t1=75.0, step=2,
         desc='Ending: the empty clearing, sunbeams, leaves spiral down; the small bird lands on the moss where the robot knelt; fade out',
         cam=[(0.0, v(-17, 31, 3.2), A['pelvis'] + v(-1.0, 0, 3.6), 30)], pose=[], light=SUN_BACK, bg='S17',
         notes='Locked (the S01 end framing, robot gone). Fade out from 72.5 s.'),
]


def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def cam_at(shot, t):
    """Camera at shot-local time t (seconds), interpolated on 1s with ease in/out."""
    keys = shot['cam']
    if len(keys) == 1 or t <= keys[0][0]:
        k = keys[0]
        return k[1], k[2], k[3]
    for a, b in zip(keys[:-1], keys[1:]):
        if t <= b[0]:
            u = ease((t - a[0]) / max(b[0] - a[0], 1e-6))
            return a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u
    k = keys[-1]
    return k[1], k[2], k[3]


def camera(shot, t, W_=W, H_=H):
    pos, tgt, lens = cam_at(shot, t)
    return r3d.Camera(pos, tgt, lens=lens, W=W_, H=H_)
