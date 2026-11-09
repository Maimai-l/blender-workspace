"""Key poses for the Warden (degrees, local part rotations).

Sign conventions (part local frames): +rx swings a hanging limb forward;
-rx bends the torso/head forward. Mirrored parts take (rx, -ry, -rz) of their
twin unless given explicitly. `grounded()` lifts/lowers the root so the
lowest point of the robot touches z = 0.
"""
import numpy as np
import r3d


def P(**kw):
    return {k: tuple(v) if not isinstance(v, np.ndarray) else v for k, v in kw.items()}


# lids: 0 = open, -66 = closed
KNEEL_DORMANT = dict(
    thigh_R=(4, 2, 0), shin_R=(-100, 0, 0), foot_R=(52, 0, 0),
    thigh_L=(82, -6, 0), shin_L=(-86, 0, 0), foot_L=(4, 0, 0),
    pelvis=(-6, 0, 0), torso=(-24, 0, -4), head=(-30, 0, 6),
    upperarm_R=(-4, -8, 0), forearm_R=(16, 0, 0), hand_R=(44, 0, 0),
    upperarm_L=(10, 8, 0), forearm_L=(64, 0, 0), hand_L=(22, 0, 0),
    lid_R=(-66, 0, 6), lid_L=(-66, 0, -6), roof_R=(0, 0, 0))

KNEEL_WAKE = dict(KNEEL_DORMANT, head=(-18, 0, 4), torso=(-21, 0, -3), lid_R=(-36, 0, 4), lid_L=(-36, 0, -4))

# rise: 1) the right hand plants and pushes, torso pitches forward over it
RISE_PUSH = dict(KNEEL_DORMANT, torso=(-38, 0, -8), head=(-6, 0, 0), pelvis=(-10, 0, 0),
                 upperarm_R=(38, 16, 0), forearm_R=(8, 0, 0), hand_R=(52, 0, 0),
                 upperarm_L=(52, -6, 0), forearm_L=(56, 0, 0),
                 lid_R=(-30, 0, 0), lid_L=(-30, 0, 0))
# 2) the kneeling knee comes up: a deep crouch on both feet
RISE_CROUCH = dict(
    thigh_R=(70, 6, 0), shin_R=(-92, 0, 0), foot_R=(22, 0, 0),
    thigh_L=(76, -8, 0), shin_L=(-90, 0, 0), foot_L=(14, 0, 0),
    pelvis=(-14, 0, 0), torso=(-30, 0, 0), head=(-4, 0, 0),
    upperarm_R=(30, 18, 0), forearm_R=(10, 0, 0), hand_R=(20, 0, 0),
    upperarm_L=(34, -18, 0), forearm_L=(16, 0, 0), hand_L=(20, 0, 0),
    lid_R=(-28, 0, 0), lid_L=(-28, 0, 0))
# 3) standing, still hunched
STAND_HUNCH = dict(
    thigh_R=(8, 3, 0), shin_R=(-12, 0, 0), foot_R=(4, 0, 0),
    thigh_L=(10, -3, 0), shin_L=(-14, 0, 0), foot_L=(4, 0, 0),
    pelvis=(-4, 0, 0), torso=(-16, 0, 0), head=(-4, 0, 0),
    upperarm_R=(10, 10, 0), forearm_R=(14, 0, 0), hand_R=(10, 0, 0),
    upperarm_L=(10, -10, 0), forearm_L=(14, 0, 0), hand_L=(10, 0, 0),
    lid_R=(-24, 0, 0), lid_L=(-24, 0, 0))
# 4) head lifted toward the canopy gap
STAND_LOOKUP = dict(STAND_HUNCH, torso=(-2, 0, 0), head=(34, 0, 0), pelvis=(2, 0, 0),
                    upperarm_R=(4, 12, 0), upperarm_L=(4, -12, 0),
                    lid_R=(-16, 0, -14), lid_L=(-16, 0, 14))
# launch anticipation: deep squat, arms swept back, roof wings open, head up
LAUNCH_CROUCH = dict(
    thigh_R=(84, 10, 0), shin_R=(-110, 0, 0), foot_R=(28, 0, 0),
    thigh_L=(84, -10, 0), shin_L=(-110, 0, 0), foot_L=(28, 0, 0),
    pelvis=(-18, 0, 0), torso=(-24, 0, 0), head=(30, 0, 0),
    upperarm_R=(-38, 24, 0), forearm_R=(14, 0, 0), hand_R=(-10, 0, 0),
    upperarm_L=(-38, -24, 0), forearm_L=(14, 0, 0), hand_L=(-10, 0, 0),
    roof_R=(0, -34, 0), roof_L=(0, 34, 0),
    lid_R=(-18, 0, -16), lid_L=(-18, 0, 16))
# launch extension: stretched up, arms down and back
LAUNCH_UP = dict(
    thigh_R=(-6, 4, 0), shin_R=(-4, 0, 0), foot_R=(-40, 0, 0),
    thigh_L=(-4, -4, 0), shin_L=(-8, 0, 0), foot_L=(-40, 0, 0),
    pelvis=(4, 0, 0), torso=(6, 0, 0), head=(24, 0, 0),
    upperarm_R=(-24, 16, 0), forearm_R=(6, 0, 0), hand_R=(-20, 0, 0),
    upperarm_L=(-24, -16, 0), forearm_L=(6, 0, 0), hand_L=(-20, 0, 0),
    roof_R=(0, -40, 0), roof_L=(0, 40, 0),
    lid_R=(-10, 0, -12), lid_L=(-10, 0, 12))
# flight: body pitched forward, roof wings spread, legs trailing
FLY = dict(LAUNCH_UP, pelvis=(-8, 0, 0), torso=(-6, 0, 0), head=(18, 0, 0),
           thigh_R=(-14, 6, 0), shin_R=(-22, 0, 0), thigh_L=(-6, -6, 0), shin_L=(-30, 0, 0),
           upperarm_R=(-30, 26, 0), upperarm_L=(-30, -26, 0),
           roof_R=(0, -46, 0), roof_L=(0, 46, 0))


def complete(pose):
    """Fill mirrored rotations explicitly where only one side is given."""
    return dict(pose)


def grounded(rig, pose, yaw=0.0, x=0.0, y=0.0, extra_z=0.0, pitch=0.0):
    """Return a pose with '_root' set so the lowest vertex sits on z = 0."""
    pose = dict(pose)
    R = r3d.rot_matrix(pitch, 0, yaw)
    pose['_root'] = r3d.mat4(R, (0, 0, 0))
    mats = rig.world_mats(pose)
    zmin = 1e9
    for nm in rig.order:
        p = rig.parts[nm]
        if p.mesh is None:
            continue
        V = p.mesh.V[::7]
        W = r3d.xform_points(mats[nm], V)
        zmin = min(zmin, float(W[:, 2].min()))
    root = r3d.mat4(R, (x, y, -zmin + extra_z))
    # the pelvis joint offset is applied inside the rig; root translation is extra
    pose['_root'] = root
    return pose
